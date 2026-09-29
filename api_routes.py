"""
api_routes.py — HR-facing API matching the other team's frontend contract.

Their React dashboard calls these (via axios at localhost:8000):
  POST /api/analyse            multipart: resume, jd, role  → {analysis, tempFiles}
  POST /api/schedule           json: {analysis, role, questionCount, confirmedEmail,
                                      manualMeetingLink, meetingPlatform} → {scheduled_at, ...}
  GET  /api/hr/sessions        → [{id, candidate_name, role, status, scheduled_at, created_at}]
  GET  /api/hr/session/{id}    → full session detail
  GET  /api/hr/report/{id}     → report row
  GET  /api/hr/report/{id}/pdf → the generated PDF (download)
  GET  /api/keys               → masked per-user API keys (sidebar)
  POST /api/keys               json: {gemini, claude, groq} → store encrypted

Wires together: extraction (US-AG-01/02), scheduler (invite+schedule), auth (login/keys),
report_pdf (US-AG-08 AC-06), and our Supabase via db.py.
"""
import os, uuid, json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, UploadFile, File, Form, Request, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse

import db, extraction, scheduler, auth, report_pdf, evaluator
from supabase import create_client as _supa_create
import os as _os

router = APIRouter()

UPLOAD_DIR = os.path.join("uploads", "documents")
JD_DIR = os.path.join("uploads", "jd")           # JD PDFs, one per job opening (preview)
RESUME_DIR = os.path.join("uploads", "resumes")   # resume PDFs, one per candidate (preview)
for _d in (UPLOAD_DIR, JD_DIR, RESUME_DIR):
    os.makedirs(_d, exist_ok=True)


# ─── AUTH LOGIN ───────────────────────────────────────────
@router.post("/api/auth/login")
async def login(request: Request):
    body = await request.json()
    email    = (body.get("email") or "").strip()
    password = (body.get("password") or "").strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required.")
    try:
        sb = _supa_create(_os.getenv("SUPABASE_URL"), _os.getenv("SUPABASE_KEY"))
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
        token = res.session.access_token
        return {"token": token, "email": res.user.email}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password.")


def _require_user(authorization):
    try:
        return auth.verify_token(authorization)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


def _require_membership(authorization):
    """Authenticated user + their org/role membership (403 if they belong to no org)."""
    user = _require_user(authorization)
    m = db.get_user_membership(auth.user_id_from(user))
    if not m:
        raise HTTPException(status_code=403, detail="No organization membership for this user.")
    return user, m


def _require_role(authorization, *roles):
    """Authenticated user whose role is one of `roles` (403 otherwise). Roles: SUPER_ADMIN/ORG_ADMIN/HR."""
    user, m = _require_membership(authorization)
    if m.get("role") not in roles:
        raise HTTPException(status_code=403, detail="You don't have permission for this action.")
    return user, m


def _org_of(m) -> str:
    """The caller's organization_id, or 400 if their account isn't linked to an org.
    Guards the multi-tenant write/read paths against orphaning rows under a null tenant."""
    org = m.get("organization_id")
    if not org:
        raise HTTPException(status_code=400, detail="Your account is not linked to an organization.")
    return org


def _sanitize_questions(raw):
    """Normalise an HR-reviewed question list (LLM items keep their fields; HR-added items get
    sensible defaults) into the shape db.save_questions / the interview engine expect."""
    clean = []
    for q in (raw or []):
        if isinstance(q, str):
            q = {"question": q}
        if not isinstance(q, dict):
            continue
        text = (q.get("question") or "").strip()
        if not text:
            continue
        clean.append({
            "question": text,
            "topic": q.get("topic") or "Custom (HR)",
            "question_type": q.get("question_type") or "custom",
            "depth": q.get("depth") or "medium",
            "target_skill": q.get("target_skill") or "",
            "key_concepts": q.get("key_concepts") or [],
        })
    return clean


# ─── RBAC: who am I (frontend routes by role) + SUPER_ADMIN org management ──
@router.get("/api/whoami")
async def whoami(authorization: str = Header(None)):
    user = _require_user(authorization)
    m = db.get_user_membership(auth.user_id_from(user)) or {}
    return {"email": user.get("email") if isinstance(user, dict) else getattr(user, "email", None),
            "role": m.get("role"), "organization_id": m.get("organization_id"),
            "organization_name": m.get("organization_name")}


@router.get("/api/admin/organizations")
async def admin_list_organizations(authorization: str = Header(None)):
    _require_role(authorization, "SUPER_ADMIN")
    return db.list_organizations()   # bare array — the UI does orgs.map(...)


@router.post("/api/admin/create-organization")
async def admin_create_organization(request: Request, authorization: str = Header(None)):
    _require_role(authorization, "SUPER_ADMIN")
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Organization name is required.")
    org = db.create_organization(name)
    if not org:
        raise HTTPException(status_code=500, detail="Could not create organization.")
    # Optionally seed the org's first ORG_ADMIN in the same step (PENDING until they set a password).
    admin_email = (body.get("adminEmail") or "").strip().lower()
    admin_name  = (body.get("adminName") or "").strip() or None
    admin = None
    if admin_email:
        if db.get_membership_by_email(admin_email):
            admin = {"email": admin_email, "status": "exists"}   # don't duplicate an existing user
        else:
            row = db.add_organization_user(org["id"], "ORG_ADMIN", email=admin_email,
                                           name=admin_name, status="PENDING")
            admin = {"email": admin_email, "status": "PENDING"} if row else None
    return {"organization": org, "admin": admin}


@router.post("/api/admin/create-user")
async def admin_create_user(request: Request, authorization: str = Header(None)):
    """SUPER_ADMIN: create a login (Supabase Auth) AND grant a role in ONE step.
    Body: {email, password, role, organizationId?, name?}. organizationId defaults to the
    caller's org. Use this to mint super-admins / org-admins / HRs without the dashboard."""
    _, caller = _require_role(authorization, "SUPER_ADMIN")
    body = await request.json()
    email    = (body.get("email") or "").strip().lower()
    password = (body.get("password") or "").strip()
    role     = (body.get("role") or "").strip().upper()
    org_id   = (body.get("organizationId") or caller.get("organization_id") or "").strip()
    name     = (body.get("name") or "").strip() or None
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required.")
    if role not in ("SUPER_ADMIN", "ORG_ADMIN", "HR"):
        raise HTTPException(status_code=400, detail="role must be SUPER_ADMIN, ORG_ADMIN, or HR.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters.")
    if not org_id:
        raise HTTPException(status_code=400, detail="organizationId is required (caller has no org to default to).")
    # 1) create the login in Supabase Auth (auto-confirmed)
    try:
        authu = db.create_auth_user(email, password)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=f"Could not create login: {e}")
    # 2) grant the role — ACTIVE, since the login already exists (no PENDING invite needed)
    member = db.add_organization_user(org_id, role, email=email,
                                      user_id=authu["id"], name=name, status="ACTIVE")
    if not member:
        raise HTTPException(status_code=500,
            detail=f"Login created (user_id {authu['id']}) but role assignment failed — "
                   f"retry the role grant with this user_id.")
    return {"user": {"user_id": authu["id"], "email": email, "role": role,
                     "organization_id": org_id, "status": "ACTIVE"}}


@router.delete("/api/admin/organizations/{org_id}")
async def admin_delete_organization(org_id: str, authorization: str = Header(None)):
    _require_role(authorization, "SUPER_ADMIN")
    db.delete_organization(org_id)
    return {"status": "deleted", "id": org_id}


@router.post("/api/admin/organizations/{org_id}/invite-admin")
async def admin_invite_org_admin(org_id: str, request: Request, authorization: str = Header(None)):
    """SUPER_ADMIN: seed an ORG_ADMIN (PENDING) for an existing org. Closes the bootstrap gap so an
    org has an admin who can log in (they set a password on first login) without a dashboard visit."""
    _require_role(authorization, "SUPER_ADMIN")
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    name  = (body.get("name") or "").strip() or None
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if not db.get_organization(org_id):
        raise HTTPException(status_code=404, detail="Organization not found.")
    if db.get_membership_by_email(email):
        raise HTTPException(status_code=409, detail="A user with this email already exists.")
    row = db.add_organization_user(org_id, "ORG_ADMIN", email=email, name=name, status="PENDING")
    if not row:
        raise HTTPException(status_code=500, detail="Could not create the invitation.")
    return {"user": {"id": row["id"], "email": email, "name": name,
                     "role": "ORG_ADMIN", "status": "PENDING"}}


# ─── REGISTRATION / INVITE FLOW ──────────────────────────
# Every user is pre-seeded as a PENDING organization_users row (by a super-admin creating an org,
# or an org-admin adding an HR). On first login they set a password → we create their Supabase
# Auth login and flip the row to ACTIVE. No self-service signup.
@router.post("/api/auth/check-email")
async def check_email(request: Request):
    """Step 1 of login: is this email known, and does it still need to set a password?"""
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    m = db.get_membership_by_email(email)
    if not m:
        raise HTTPException(status_code=404,
            detail="No account found for this email. Ask your administrator to invite you first.")
    return {"exists": True, "status": m.get("status"), "role": m.get("role")}


@router.post("/api/auth/complete-registration")
async def complete_registration(request: Request):
    """Step 2 (PENDING users only): create the Supabase Auth login and activate the membership."""
    body = await request.json()
    email    = (body.get("email") or "").strip().lower()
    password = (body.get("password") or "").strip()
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    m = db.get_membership_by_email(email)
    if not m:
        raise HTTPException(status_code=404, detail="No invitation found for this email.")
    if m.get("status") == "ACTIVE" and m.get("user_id"):
        raise HTTPException(status_code=400, detail="This account is already registered — please log in.")
    try:
        authu = db.create_auth_user(email, password)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=f"Could not complete registration: {e}")
    db.activate_membership(m["id"], authu["id"])
    return {"status": "ACTIVE", "email": email}


# ─── DASHBOARDS (role-scoped landing tiles) ───────────────
@router.get("/api/dashboard/super-admin")
def dashboard_super_admin(authorization: str = Header(None)):
    _require_role(authorization, "SUPER_ADMIN")
    n_int = db.count_rows("scheduled_interviews")
    return {
        "organizations": db.count_rows("organizations"),
        "org_admins": db.count_rows("organization_users", role="ORG_ADMIN"),
        "hrs": db.count_rows("organization_users", role="HR"),
        "job_openings": db.count_rows("job_openings"),
        "candidates": db.count_rows("candidates"),
        "interviews": n_int,
        "scheduled_interviews": n_int,   # UI tile reads this key
    }


@router.get("/api/dashboard/org-admin")
def dashboard_org_admin(authorization: str = Header(None)):
    _, m = _require_role(authorization, "ORG_ADMIN", "SUPER_ADMIN")
    org = _org_of(m)
    return {
        "hrs": db.count_rows("organization_users", organization_id=org, role="HR"),
        "job_openings": db.count_rows("job_openings", organization_id=org),
        "candidates": db.count_rows("candidates", organization_id=org),
        "scheduled_interviews": db.count_rows("scheduled_interviews", organization_id=org),
    }


@router.get("/api/dashboard/hr")
def dashboard_hr(authorization: str = Header(None)):
    _, m = _require_role(authorization, "HR", "ORG_ADMIN", "SUPER_ADMIN")
    org = _org_of(m)
    return {
        "total_jobs": db.count_rows("job_openings", organization_id=org),
        "total_candidates": db.count_rows("candidates", organization_id=org),
        "total_interviews": db.count_rows("scheduled_interviews", organization_id=org),
    }


# ─── ORG-ADMIN: manage HRs + org settings ─────────────────
@router.get("/api/org-admin/hrs")
def org_list_hrs(authorization: str = Header(None)):
    _, m = _require_role(authorization, "ORG_ADMIN", "SUPER_ADMIN")
    users = db.list_org_users(m["organization_id"])
    return [{"id": u["id"], "name": u.get("name"), "role": u.get("role"),
             "email": u.get("email"), "status": u.get("status")}
            for u in users if u.get("role") != "SUPER_ADMIN"]


@router.post("/api/org-admin/create-hr")
async def org_create_hr(request: Request, authorization: str = Header(None)):
    """Invite an HR (or recruiter/interviewer/org-admin) — seeds a PENDING membership row.
    They activate it by setting a password on first login (check-email → complete-registration)."""
    _, m = _require_role(authorization, "ORG_ADMIN", "SUPER_ADMIN")
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    name  = (body.get("name") or "").strip() or None
    role  = (body.get("role") or "HR").strip().upper()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    if role not in ("HR", "RECRUITER", "INTERVIEWER", "ORG_ADMIN"):
        raise HTTPException(status_code=400, detail="Invalid role.")
    if db.get_membership_by_email(email):
        raise HTTPException(status_code=409, detail="A user with this email already exists.")
    row = db.add_organization_user(m["organization_id"], role, email=email, name=name, status="PENDING")
    if not row:
        raise HTTPException(status_code=500, detail="Could not create the invitation.")
    return {"user": {"id": row["id"], "email": email, "name": name, "role": role, "status": "PENDING"}}


@router.delete("/api/org-admin/hr/{row_id}")
def org_delete_hr(row_id: str, authorization: str = Header(None)):
    _, m = _require_role(authorization, "ORG_ADMIN", "SUPER_ADMIN")
    # tenant safety: only delete a membership that belongs to the caller's org
    target = next((u for u in db.list_org_users(m["organization_id"]) if u["id"] == row_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="User not found in your organization.")
    # privilege guard: an ORG_ADMIN can't remove another admin / a super-admin (only SUPER_ADMIN can)
    if target.get("role") in ("ORG_ADMIN", "SUPER_ADMIN") and m.get("role") != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="You can't remove an admin account.")
    db.delete_org_user(row_id)
    return {"status": "deleted", "id": row_id}


@router.get("/api/org-admin/settings")
def org_get_settings(authorization: str = Header(None)):
    _, m = _require_role(authorization, "ORG_ADMIN", "SUPER_ADMIN")
    org = db.get_organization(m["organization_id"]) or {}
    return {"email_template": org.get("email_template") or ""}


@router.put("/api/org-admin/settings")
async def org_put_settings(request: Request, authorization: str = Header(None)):
    _, m = _require_role(authorization, "ORG_ADMIN", "SUPER_ADMIN")
    body = await request.json()
    db.update_organization(m["organization_id"], email_template=(body.get("email_template") or ""))
    return {"status": "saved"}


# ─── JOB OPENINGS (role cards: JD uploaded ONCE, 4-level static question sets stored) ──
@router.get("/api/job-openings")
def list_job_openings(authorization: str = Header(None)):
    _, m = _require_membership(authorization)
    return db.list_job_openings(m["organization_id"])


@router.post("/api/job-openings")
async def create_job_opening(title: str = Form(...), description: str = Form(""),
                             role: str = Form(""), roleSource: str = Form(""),
                             questionCount: int = Form(12), jd_file: UploadFile = File(None),
                             authorization: str = Header(None)):
    """Create a role card. The JD is uploaded here ONCE; we analyse it and pre-build the 80%
    static question set for all 4 experience levels, reused for every candidate under this role."""
    user, m = _require_role(authorization, "HR", "ORG_ADMIN", "SUPER_ADMIN")
    uid = auth.user_id_from(user)
    keys = auth.get_user_keys_decrypted(uid)
    org = _org_of(m)

    jd_bytes, jd_text = None, ""
    if jd_file:
        jd_bytes = await jd_file.read()
        tmp = os.path.join(JD_DIR, f"_tmp_{uuid.uuid4()}_{jd_file.filename}")
        with open(tmp, "wb") as f:
            f.write(jd_bytes)
        jd_text = extraction.extract_text(tmp)
        os.remove(tmp)

    # Role for the question bank: honour HR's explicit choice (dropdown, or "Other" → match|llm),
    # else resolve from the title (bank if it matches a stored role, else LLM).
    chosen_role = (role or "").strip() or title
    src = (roleSource or "").strip().lower()
    role_info = None
    if src not in ("bank", "match", "llm"):
        resolved, _m = extraction.resolve_bank_role(chosen_role)
        role_source = "bank" if resolved else "llm"
        role_for_bank = resolved or chosen_role
    elif src == "match":
        resolved, method = extraction.resolve_bank_role(chosen_role)
        role_for_bank = resolved or chosen_role
        role_source = "match"
        if resolved and resolved.strip().lower() != chosen_role.strip().lower():
            role_info = {"requested": chosen_role, "resolved": resolved, "method": method}
    else:   # 'bank' (exact stored role) or 'llm' (generate with AI) — use as given
        role_for_bank = chosen_role
        role_source = src

    jd_analysis = {}
    if jd_text:
        try:
            jd_analysis = extraction.analyze_documents(jd_text, "", title, keys=keys)
        except extraction.llm_stack.LLMExhausted:
            jd_analysis = {}   # non-fatal: card still usable, gap analysis just won't have JD context

    qc = max(10, min(16, int(questionCount or 12)))
    # Per-level static sets are NOT pre-built here anymore: each candidate's plan is generated at
    # review time via the v2.1.0 engine (generate_question_plan), reusing this card's role/
    # role_source + JD. Skipping the 4x build keeps job creation instant and dodges LLM timeouts
    # for 'llm'-source roles. (role_for_bank is still resolved above for role_source detection.)
    row = db.create_job_opening(org, title, description, jd_text, jd_analysis,
                                {}, role_source, qc)
    if not row:
        raise HTTPException(status_code=500, detail="Could not create the job opening.")
    if jd_bytes:   # keep the JD PDF on disk for the preview iframe, keyed by opening id
        with open(os.path.join(JD_DIR, f"{row['id']}.pdf"), "wb") as f:
            f.write(jd_bytes)
    return {"id": row["id"], "title": title, "description": description,
            "status": row.get("status", "open"), "role_source": role_source,
            "question_count": qc, "roleInfo": role_info}


@router.delete("/api/job-openings/{job_id}")
def delete_job_opening(job_id: str, authorization: str = Header(None)):
    _, m = _require_role(authorization, "HR", "ORG_ADMIN", "SUPER_ADMIN")
    org = _org_of(m)
    if not db.get_job_opening(job_id, org):
        raise HTTPException(status_code=404, detail="Job opening not found.")
    db.delete_job_opening(job_id, org)
    return {"status": "deleted", "id": job_id}


def _candidate_dto(c: dict, sched: dict) -> dict:
    s = sched.get(c["id"])
    return {"id": c["id"], "name": c.get("name"), "email": c.get("email"),
            "role": c.get("role"), "job_opening_id": c.get("job_opening_id"),
            "is_scheduled": bool(s),
            "scheduled_time": (s.get("scheduled_for") if s else None),
            "analysis": c.get("analysis") or {}}


@router.get("/api/job-openings/{job_id}/candidates")
def job_opening_candidates(job_id: str, authorization: str = Header(None)):
    _, m = _require_membership(authorization)
    org = _org_of(m)
    if not db.get_job_opening(job_id, org):
        raise HTTPException(status_code=404, detail="Job opening not found.")
    cands = db.list_candidates(org, job_opening_id=job_id)
    sched = db.candidate_scheduled_map([c["id"] for c in cands])
    return [_candidate_dto(c, sched) for c in cands]


@router.get("/api/job-openings/{job_id}/stats")
def job_opening_stats(job_id: str, authorization: str = Header(None)):
    _, m = _require_membership(authorization)
    org = _org_of(m)
    if not db.get_job_opening(job_id, org):
        raise HTTPException(status_code=404, detail="Job opening not found.")
    cands = db.list_candidates(org, job_opening_id=job_id)
    ids = [c["id"] for c in cands]
    sched = db.candidate_scheduled_map(ids)
    sess_status = db.sessions_status_map([s.get("session_id") for s in sched.values()])
    scheduled = in_progress = completed = 0
    for cid in ids:
        s = sched.get(cid)
        if not s:
            continue
        st = (sess_status.get(s.get("session_id")) or s.get("status") or "").lower()
        if st in ("completed", "done"):
            completed += 1
        elif st in ("in_progress", "launching", "interviewing", "joining", "waiting"):
            in_progress += 1
        else:
            scheduled += 1
    return {"total_candidates": len(cands), "scheduled": scheduled,
            "in_progress": in_progress, "completed": completed}


# ─── CANDIDATES (resume uploaded against a job opening; JD reused from the role card) ──
@router.get("/api/candidates")
def list_candidates(authorization: str = Header(None)):
    _, m = _require_membership(authorization)
    cands = db.list_candidates(m["organization_id"])
    sched = db.candidate_scheduled_map([c["id"] for c in cands])
    return [_candidate_dto(c, sched) for c in cands]


@router.post("/api/candidates/upload")
async def upload_candidate(resume: UploadFile = File(...), job_opening_id: str = Form(...),
                           authorization: str = Header(None)):
    """Upload a candidate's resume against a job opening. The JD comes from the role card, so the
    candidate only ever uploads a resume. Returns the JD-match analysis for HR review."""
    user, m = _require_role(authorization, "HR", "ORG_ADMIN", "SUPER_ADMIN")
    uid = auth.user_id_from(user)
    keys = auth.get_user_keys_decrypted(uid)
    org = _org_of(m)

    job = db.get_job_opening(job_opening_id, org)
    if not job:
        raise HTTPException(status_code=404, detail="Job opening not found.")

    resume_bytes = await resume.read()
    tmp = os.path.join(RESUME_DIR, f"_tmp_{uuid.uuid4()}_{resume.filename}")
    with open(tmp, "wb") as f:
        f.write(resume_bytes)
    resume_text = extraction.extract_text(tmp)
    os.remove(tmp)
    if not resume_text:
        raise HTTPException(status_code=400, detail="Could not read any text from the resume.")

    jd_text = job.get("jd_text") or ""
    title = job.get("title") or "Software Engineer"
    try:
        analysis = extraction.analyze_documents(jd_text, resume_text, title, keys=keys)
    except extraction.llm_stack.LLMExhausted as e:
        raise HTTPException(status_code=429,
                            detail={"error": "llm_exhausted", "providers": e.providers_tried})

    cand = db.create_candidate_full(org, job_opening_id,
                                    analysis.get("candidateName") or "Candidate",
                                    analysis.get("candidateEmail"), title, resume_text, analysis)
    if not cand:
        raise HTTPException(status_code=500, detail="Could not save the candidate.")
    with open(os.path.join(RESUME_DIR, f"{cand['id']}.pdf"), "wb") as f:
        f.write(resume_bytes)
    return {"analysis": analysis,
            "candidate": {"id": cand["id"], "name": cand.get("name"), "email": cand.get("email"),
                          "role": title, "job_opening_id": job_opening_id}}


def _candidate_plan(cand: dict, job: dict, qc: int, keys: dict) -> dict:
    """Build a candidate's question plan via the EXACT v2.1.0 engine (generate_question_plan):
    opening → technical → gap → closing, always filling to `qc` — technical backfills any gap
    shortfall (so a plan is never short when the gap model returns fewer than reserved). JD comes
    from the role card (uploaded once); resume + analysis from the candidate. Pure — no DB writes."""
    job = job or {}
    analysis = cand.get("analysis") or {}
    role = cand.get("role") or job.get("title") or analysis.get("jobRole") or "Software Engineer"
    role_source = job.get("role_source") or "bank"
    jd_text = job.get("jd_text") or ""
    resume_text = cand.get("resume_text") or ""
    questions = extraction.generate_question_plan(
        analysis, role, jd_text=jd_text, resume_text=resume_text,
        total_questions=qc, role_source=role_source, keys=keys)
    level = extraction._normalize_level(analysis.get("detectedLevel") or "fresher")
    return {"questions": questions, "role": role, "level": level}


@router.post("/api/candidate/{cand_id}/generate-questions")
async def generate_candidate_questions(cand_id: str, request: Request, authorization: str = Header(None)):
    """PREVIEW the interview question plan so HR can review / edit / add / remove BEFORE scheduling.
    Stateless — nothing is persisted until /api/candidate/{id}/schedule is called with the final list."""
    user, m = _require_role(authorization, "HR", "ORG_ADMIN", "SUPER_ADMIN")
    keys = auth.get_user_keys_decrypted(auth.user_id_from(user))
    org = _org_of(m)
    cand = db.get_candidate(cand_id, org)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    try:
        body = await request.json()
    except Exception:
        body = {}
    qc = max(10, min(16, int(body.get("question_count") or 12)))
    job = db.get_job_opening(cand.get("job_opening_id"), org) or {}
    try:
        plan = _candidate_plan(cand, job, qc, keys)
    except extraction.llm_stack.LLMExhausted as e:
        raise HTTPException(status_code=429,
                            detail={"error": "llm_exhausted", "providers": e.providers_tried})
    return {"questions": plan["questions"], "role": plan["role"],
            "level": plan["level"], "count": len(plan["questions"])}


@router.post("/api/candidate/{cand_id}/schedule")
async def schedule_candidate(cand_id: str, request: Request, authorization: str = Header(None)):
    """Schedule a candidate's interview. If the request carries an HR-reviewed `questions` array we
    use it verbatim (v2 review-then-schedule flow); otherwise we generate the plan on the fly.
    Creates the session + bot job and emails the invite. Enforces one interview per candidate."""
    user, m = _require_role(authorization, "HR", "ORG_ADMIN", "SUPER_ADMIN")
    uid = auth.user_id_from(user)
    keys = auth.get_user_keys_decrypted(uid)
    org = _org_of(m)

    cand = db.get_candidate(cand_id, org)
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    if db.candidate_has_interview(cand_id):
        raise HTTPException(status_code=409, detail="This candidate already has a scheduled interview.")

    body = await request.json()
    meeting_url = (body.get("meeting_url") or "").strip()
    qc = max(10, min(16, int(body.get("question_count") or 12)))
    delay_minutes = int(body.get("delay_minutes") or 30)
    if not meeting_url:
        raise HTTPException(status_code=400, detail="A meeting link is required.")
    if not scheduler.is_supported_meeting_url(meeting_url):
        raise HTTPException(status_code=400, detail=(
            f"That doesn't look like a supported meeting link. Please paste a "
            f"{scheduler.SUPPORTED_MEETING_PLATFORMS} link — the interview bot can't join a "
            f"YouTube or other link."))

    job = db.get_job_opening(cand.get("job_opening_id"), org) or {}
    analysis = cand.get("analysis") or {}
    role = cand.get("role") or job.get("title") or analysis.get("jobRole") or "Software Engineer"
    jd_text = job.get("jd_text") or ""
    resume_text = cand.get("resume_text") or ""

    # 1. use the HR-reviewed plan if the client sent one; else generate it now (backward compatible)
    questions = _sanitize_questions(body.get("questions"))
    if not questions:
        try:
            questions = _candidate_plan(cand, job, qc, keys)["questions"]
        except extraction.llm_stack.LLMExhausted as e:
            raise HTTPException(status_code=429,
                                detail={"error": "llm_exhausted", "providers": e.providers_tried})

    name = cand.get("name") or analysis.get("candidateName") or "Candidate"
    # HR may correct the invite address at schedule time (v2.1.0 parity); else fall back to stored.
    email = (body.get("confirmedEmail") or body.get("email") or cand.get("email")
             or analysis.get("candidateEmail") or "").strip()
    session_id = db.create_session(bot_id=None, total_questions=len(questions),
                                   candidate_name=name, candidate_email=email, role=role,
                                   status="scheduled", candidate_id=cand_id, organization_id=org)
    scheduled_for = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    db.update_session_analysis(session_id, analysis, meeting_url, scheduled_for.isoformat(),
                               jd_text, resume_text)
    db.save_questions(session_id, questions)
    db.create_scheduled_interview(meeting_url=meeting_url, scheduled_for_iso=scheduled_for.isoformat(),
                                  candidate_email=email, candidate_name=name, role=role,
                                  session_id=session_id, organization_id=org, candidate_id=cand_id)

    IST = timezone(timedelta(hours=5, minutes=30))
    when_human = scheduled_for.astimezone(IST).strftime("%Y-%m-%d %H:%M") + " IST"
    email_ok = scheduler.send_invite(email, name, meeting_url, role=role, when=when_human) if email else False

    return {"status": "scheduled", "session_id": session_id,
            "scheduled_at": scheduled_for.isoformat().replace("+00:00", ""),
            "email_sent": email_ok, "questions_generated": len(questions)}


# ─── LIVE INTERVIEWS TABLE (org-scoped, polled by the UI) ──
@router.get("/api/interviews")
def list_interviews(authorization: str = Header(None)):
    _, m = _require_membership(authorization)
    org = _org_of(m)
    rows = db.list_org_interviews(org)
    sess_status = db.sessions_status_map([r.get("session_id") for r in rows])
    # attach each candidate's detectedLevel (UI shows it); one batched read, not N+1
    cand_by_id = {c["id"]: c for c in db.list_candidates(org)}
    out = []
    for r in rows:
        cand = cand_by_id.get(r.get("candidate_id")) or {}
        status = sess_status.get(r.get("session_id")) or r.get("status")
        out.append({
            "id": r["id"], "session_id": r.get("session_id"),
            "candidate_name": r.get("candidate_name"), "candidate_email": r.get("candidate_email"),
            "role": r.get("role"), "status": status,
            "scheduled_time": r.get("scheduled_for"), "created_at": r.get("created_at"),
            "meeting_url": r.get("meeting_url"),
            "analysis": cand.get("analysis") or {},
        })
    return out


# ─── DOCUMENT PREVIEW (served by id for iframe <src>; UUID-scoped, no header — see note) ──
# NOTE: these are loaded as iframe/window.open sources, which cannot send an Authorization
# header, so they authenticate by unguessable UUID only. Fine for an internal tool; Phase 3
# should move to short-lived signed URLs (esp. for resumes, which are candidate PII).
def _is_uuid(s: str) -> bool:
    try:
        uuid.UUID(str(s)); return True
    except Exception:
        return False


@router.get("/api/documents/job/{job_id}")
def document_job(job_id: str):
    if not _is_uuid(job_id):   # reject non-UUID ids (path-traversal defence-in-depth)
        raise HTTPException(status_code=404, detail="Not found.")
    path = os.path.join(JD_DIR, f"{job_id}.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No JD document on file for this opening.")
    return FileResponse(path, media_type="application/pdf")


@router.get("/api/documents/candidate/{cand_id}")
def document_candidate(cand_id: str):
    if not _is_uuid(cand_id):
        raise HTTPException(status_code=404, detail="Not found.")
    path = os.path.join(RESUME_DIR, f"{cand_id}.pdf")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No resume on file for this candidate.")
    return FileResponse(path, media_type="application/pdf")


# ─── US-AG-01: upload + parse JD/resume ───────────────────
@router.post("/api/analyse")
async def analyse(resume: UploadFile = File(None), jd: UploadFile = File(None),
                  role: str = Form("Software Engineer"), roleId: str = Form(None),
                  authorization: str = Header(None)):
    user = _require_user(authorization)
    keys = auth.get_user_keys_decrypted(auth.user_id_from(user))  # per-user LLM keys

    resume_text, jd_text, temp = "", "", {}
    if resume:
        rp = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{resume.filename}")
        with open(rp, "wb") as f:
            f.write(await resume.read())
        resume_text = extraction.extract_text(rp)
        temp["resume_path"] = rp
    if jd:
        jp = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{jd.filename}")
        with open(jp, "wb") as f:
            f.write(await jd.read())
        jd_text = extraction.extract_text(jp)
        temp["jd_path"] = jp
    # Role card: the JD was uploaded ONCE when the card was created — reuse it here so the
    # candidate only uploads a resume.
    if roleId and not jd_text:
        card = db.get_job_role(roleId, auth.user_id_from(user))
        if card:
            jd_text = card.get("jd_text") or ""
            role = card.get("role_name") or role
            temp["roleId"] = roleId
    if not resume_text and not jd_text:
        raise HTTPException(status_code=400, detail="Upload at least one document.")

    try:
        analysis = extraction.analyze_documents(jd_text, resume_text, role, keys=keys)
    except extraction.llm_stack.LLMExhausted as e:
        # signal the UI to prompt for a fresh key
        raise HTTPException(status_code=429,
                            detail={"error": "llm_exhausted", "providers": e.providers_tried})
    temp["resume_text"] = resume_text
    temp["jd_text"] = jd_text
    return {"analysis": analysis, "tempFiles": temp}


# ─── stored question-bank roles (populate the HR role dropdown) ──
@router.get("/api/roles")
async def roles(authorization: str = Header(None)):
    _require_user(authorization)
    return {"roles": extraction.list_bank_roles()}


# ─── ROLE CARDS: JD uploaded ONCE per role; 80% static set stored per experience level ──
@router.post("/api/role-cards")
async def create_role_card(jd: UploadFile = File(None),
                           roleName: str = Form("Software Engineer"),
                           roleSource: str = Form("bank"), questionCount: int = Form(12),
                           authorization: str = Header(None)):
    """Create a role card from a one-time JD upload. Stores the JD + the 80% static question set
    per experience level, reused for every candidate under this role."""
    user = _require_user(authorization)
    uid = auth.user_id_from(user)
    keys = auth.get_user_keys_decrypted(uid)
    if not jd:
        raise HTTPException(status_code=400, detail="A job description (PDF) is required.")
    jp = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{jd.filename}")
    with open(jp, "wb") as f:
        f.write(await jd.read())
    jd_text = extraction.extract_text(jp)
    try:
        jd_analysis = extraction.analyze_documents(jd_text, "", roleName, keys=keys)
    except extraction.llm_stack.LLMExhausted as e:
        raise HTTPException(status_code=429,
                            detail={"error": "llm_exhausted", "providers": e.providers_tried})
    qc = max(10, min(16, int(questionCount or 12)))
    question_sets = {
        lvl: extraction.build_static_plan(roleName, lvl, qc, roleSource,
                                          analysis=jd_analysis, jd_text=jd_text, keys=keys)
        for lvl in extraction.LEVELS   # 4 tiers: fresher | junior | mid | senior
    }
    card = db.create_job_role(uid, roleName, roleSource, qc, jd_text, jd_analysis, question_sets)
    if not card:
        raise HTTPException(status_code=500, detail="Could not save the role card.")
    return {"id": card["id"], "role_name": roleName, "role_source": roleSource,
            "question_count": qc, "jd_preview": (jd_text or "")[:600]}


@router.get("/api/role-cards")
async def list_role_cards(authorization: str = Header(None)):
    user = _require_user(authorization)
    return {"roleCards": db.list_job_roles(auth.user_id_from(user))}


@router.get("/api/role-cards/{role_id}")
async def get_role_card(role_id: str, authorization: str = Header(None)):
    user = _require_user(authorization)
    card = db.get_job_role(role_id, auth.user_id_from(user))
    if not card:
        raise HTTPException(status_code=404, detail="Role card not found.")
    return {"id": card["id"], "role_name": card["role_name"], "role_source": card["role_source"],
            "question_count": card["question_count"], "jd_preview": (card.get("jd_text") or "")[:600]}


# ─── US-AG-02 preview: generate the question plan for HR review (no DB writes) ──
@router.post("/api/generate-questions")
async def generate_questions(request: Request, authorization: str = Header(None)):
    """Return the LLM question plan so HR can review/edit it BEFORE the interview is scheduled.
    Stateless — nothing is persisted until /api/schedule is called with the confirmed plan."""
    user = _require_user(authorization)
    keys = auth.get_user_keys_decrypted(auth.user_id_from(user))
    body = await request.json()
    analysis = body.get("analysis", {})
    role     = body.get("role") or analysis.get("jobRole", "Software Engineer")
    qcount   = int(body.get("questionCount", 12))
    role_source = body.get("roleSource", "bank")
    role_id  = body.get("roleId")
    temp     = body.get("tempFiles", {})
    jd_text  = temp.get("jd_text", "")
    resume_text = temp.get("resume_text", "")

    # ── Role card: reuse the stored 80% static set for the candidate's level; add ~20% gap ──
    if role_id:
        card = db.get_job_role(role_id, auth.user_id_from(user))
        if not card:
            raise HTTPException(status_code=404, detail="Role card not found.")
        level = extraction._normalize_level(analysis.get("detectedLevel") or "fresher")
        sets = card.get("question_sets") or {}
        static = sets.get(level) or next(iter(sets.values()), None)
        if not static:
            raise HTTPException(status_code=400, detail="Role card has no stored question set.")
        jd_for_gap = jd_text or card.get("jd_text") or ""
        gap, gap_n = [], int(static.get("gap_count", 0))
        if resume_text and jd_for_gap and gap_n > 0:
            gap_text = analysis.get("gapAnalysisText") or ""
            if not gap_text:
                missing = analysis.get("missingSkills", [])
                gap_text = (f"Candidate lacks experience with {', '.join(missing)}."
                            if missing else "No major skill gaps identified.")
            gap = extraction.generate_gap_questions(card.get("role_name", role), gap_text,
                                                    jd_for_gap, resume_text, gap_n)
        return {"questions": extraction.assemble_plan(static, gap),
                "roleInfo": None, "roleMismatch": None}

    try:
        questions = extraction.generate_question_plan(
            analysis, role, jd_text=jd_text, resume_text=resume_text,
            total_questions=qcount, role_source=role_source, keys=keys)
    except extraction.llm_stack.LLMExhausted as e:
        raise HTTPException(status_code=429,
                            detail={"error": "llm_exhausted", "providers": e.providers_tried})
    # tell the UI how an "Other" role was resolved (so it can show "matched X → Y")
    role_info = None
    if role_source == "match":
        resolved, method = extraction.resolve_bank_role(role)
        if not resolved:
            fb = extraction.list_bank_roles()
            resolved, method = (fb[0] if fb else role), "fallback"
        role_info = {"requested": role, "resolved": resolved, "method": method}
    # warn (non-blocking) if HR's chosen role contradicts the role detected from the documents
    role_mismatch = None
    detected = (analysis.get("jobRole") or "").strip()
    if detected:
        sel_c, _ = extraction.resolve_bank_role(role)
        det_c, _ = extraction.resolve_bank_role(detected)
        sel = (sel_c or role).strip().lower()
        det = (det_c or detected).strip().lower()
        if sel and det and sel != det:
            role_mismatch = {"selected": role, "detected": detected}
    return {"questions": questions, "roleInfo": role_info, "roleMismatch": role_mismatch}


# ─── US-AG-02 + scheduling: generate questions, store, email, schedule bot ──
@router.post("/api/schedule")
async def schedule(request: Request, authorization: str = Header(None)):
    user = _require_user(authorization)
    uid = auth.user_id_from(user)
    keys = auth.get_user_keys_decrypted(uid)
    body = await request.json()

    analysis      = body.get("analysis", {})
    role          = body.get("role") or analysis.get("jobRole", "Software Engineer")
    qcount        = int(body.get("questionCount", 12))
    role_source   = body.get("roleSource", "bank")
    email         = (body.get("confirmedEmail") or analysis.get("candidateEmail") or "").strip()
    meeting_url   = (body.get("manualMeetingLink") or "").strip()
    temp          = body.get("tempFiles", {})
    delay_minutes = int(body.get("delayMinutes", 30))

    if not meeting_url:
        raise HTTPException(status_code=400, detail="A meeting link is required.")
    if not scheduler.is_supported_meeting_url(meeting_url):
        raise HTTPException(status_code=400, detail=(
            f"That doesn't look like a supported meeting link. Please paste a "
            f"{scheduler.SUPPORTED_MEETING_PLATFORMS} link — the interview bot can't join a "
            f"YouTube or other link."))

    # 1. use the HR-reviewed plan if provided, else generate one (backward-compatible)
    questions = _sanitize_questions(body.get("questions"))
    if not questions:
        try:
            questions = extraction.generate_question_plan(
                analysis, role,
                jd_text=temp.get("jd_text", ""), resume_text=temp.get("resume_text", ""),
                total_questions=qcount, role_source=role_source, keys=keys)
        except extraction.llm_stack.LLMExhausted as e:
            raise HTTPException(status_code=429,
                                detail={"error": "llm_exhausted", "providers": e.providers_tried})

    # 2. create candidate + session in OUR Supabase, store analysis + questions
    candidate_name  = analysis.get("candidateName", "Candidate")
    session_id = db.create_session(
        bot_id=None, total_questions=len(questions),
        candidate_name=candidate_name, candidate_email=email, role=role,
        status="scheduled")

    scheduled_for = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
    db.update_session_analysis(session_id, analysis, meeting_url, scheduled_for.isoformat(),
                               temp.get("jd_text"), temp.get("resume_text"))
    db.save_questions(session_id, questions)

    # 3. create the scheduled-interview row (the worker auto-deploys the bot at scheduled_for)
    sched = db.create_scheduled_interview(
        meeting_url=meeting_url, scheduled_for_iso=scheduled_for.isoformat(),
        candidate_email=email, candidate_name=candidate_name, role=role,
        session_id=session_id)

    # 4. email the invite now
    IST = timezone(timedelta(hours=5, minutes=30))   # India Standard Time (no DST → fixed offset)
    when_human = scheduled_for.astimezone(IST).strftime("%Y-%m-%d %H:%M") + " IST"
    email_ok = scheduler.send_invite(email, candidate_name, meeting_url, role=role, when=when_human) if email else False

    return {"status": "scheduled", "session_id": session_id,
            "scheduled_at": scheduled_for.isoformat().replace("+00:00", ""),
            "email_sent": email_ok, "questions_generated": len(questions)}


# ─── HR dashboard reads (TENANT-SCOPED: an org only sees its own sessions/reports) ──
def _require_session_in_org(authorization, session_id):
    """Authenticated member whose org owns `session_id`; 404 otherwise. Blocks cross-tenant IDOR
    on transcripts / reports / recordings (these tables use the service_role key → no RLS)."""
    _, m = _require_membership(authorization)
    if not db.session_in_org(session_id, _org_of(m)):
        raise HTTPException(status_code=404, detail="Session not found.")
    return m


@router.get("/api/hr/sessions")
def hr_sessions(authorization: str = Header(None)):
    _, m = _require_membership(authorization)
    return db.list_sessions_with_reports(_org_of(m))

@router.get("/api/hr/session/{session_id}")
def hr_session(session_id: str, authorization: str = Header(None)):
    _require_session_in_org(authorization, session_id)
    return db.get_session_full(session_id)

@router.get("/api/hr/report/{session_id}")
def hr_report(session_id: str, authorization: str = Header(None)):
    _require_session_in_org(authorization, session_id)
    return db.get_report(session_id)

@router.post("/api/hr/session/{session_id}/analyze-integrity")
def hr_analyze_integrity(session_id: str, authorization: str = Header(None)):
    """Run (or re-run) integrity analysis for a session on demand. Runs in the background."""
    _require_session_in_org(authorization, session_id)
    import proctor, threading
    bot_id = db.get_bot_id_for_session(session_id)   # so a manual re-run can also test video analysis
    threading.Thread(target=proctor.analyze_session, args=(session_id, bot_id), daemon=True).start()
    return {"status": "started", "session_id": session_id, "bot_id": bot_id}


@router.get("/api/hr/session/{session_id}/recording")
def hr_recording_url(session_id: str, authorization: str = Header(None)):
    _require_user(authorization)

    session = db.get_session_full(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 1. Try to get a fresh URL from Recall
    bot_id = db.get_bot_id_for_session(session_id)

    if bot_id:
        import app_full
        url = app_full.get_fresh_recording_url(bot_id)

        if url:
            return {"url": url}

    # 2. If Recall is unavailable, use the URL saved in Supabase
    saved_url = session.get("session", {}).get("recording_url")

    if saved_url:
        return {"url": saved_url}

    # 3. Nothing available
    raise HTTPException(
        status_code=404,
        detail="Recording is no longer available"
    )


@router.get("/api/hr/report/{session_id}/pdf")
def hr_report_pdf(session_id: str, authorization: str = Header(None)):
    _require_session_in_org(authorization, session_id)
    report = db.get_report(session_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report["session_id"] = session_id
    report["per_topic"] = report.get("per_topic", [])
    report["candidate"] = db.get_candidate_for_session(session_id)
    transcript = [{"speaker": a["speaker"], "text": a["text"],
                   "timestamp": a.get("created_at", "")} for a in db.read_answers(session_id)]
    path = report_pdf.build_report_pdf(report, transcript, out_dir="uploads/reports")
    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))


# ─── API-key sidebar (per-user, encrypted, masked) ────────
@router.get("/api/keys")
def get_keys(authorization: str = Header(None)):
    user = _require_user(authorization)
    return auth.get_user_keys_masked(auth.user_id_from(user))

@router.post("/api/keys")
async def set_keys(request: Request, authorization: str = Header(None)):
    user = _require_user(authorization)
    body = await request.json()
    ok = auth.save_user_keys(auth.user_id_from(user),
                             {"gemini": body.get("gemini"), "claude": body.get("claude"),
                              "groq": body.get("groq")})
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to save keys")
    return {"status": "saved", "keys": auth.get_user_keys_masked(auth.user_id_from(user))}