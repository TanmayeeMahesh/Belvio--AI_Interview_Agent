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
os.makedirs(UPLOAD_DIR, exist_ok=True)


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
    return {"organizations": db.list_organizations()}


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
    admin_email = (body.get("adminEmail") or "").strip()
    if admin_email:  # seed the org's first admin (PENDING until they register)
        db.add_organization_user(org["id"], "ORG_ADMIN", email=admin_email, status="PENDING")
    return {"organization": org}


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
        for lvl in ("fresher", "intermediate", "experienced")
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
        level = str(analysis.get("detectedLevel") or "fresher").lower()
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


# ─── HR dashboard reads ───────────────────────────────────
@router.get("/api/hr/sessions")
def hr_sessions(authorization: str = Header(None)):
    _require_user(authorization)
    return db.list_sessions_with_reports()

@router.get("/api/hr/session/{session_id}")
def hr_session(session_id: str, authorization: str = Header(None)):
    _require_user(authorization)
    return db.get_session_full(session_id)

@router.get("/api/hr/report/{session_id}")
def hr_report(session_id: str, authorization: str = Header(None)):
    _require_user(authorization)
    return db.get_report(session_id)

@router.post("/api/hr/session/{session_id}/analyze-integrity")
def hr_analyze_integrity(session_id: str, authorization: str = Header(None)):
    """Run (or re-run) integrity analysis for a session on demand — handy for local testing on an
    existing transcript without conducting a fresh interview. Runs in the background; returns immediately."""
    _require_user(authorization)
    import proctor, threading
    bot_id = db.get_bot_id_for_session(session_id)   # so a manual re-run can also test video analysis
    threading.Thread(target=proctor.analyze_session, args=(session_id, bot_id), daemon=True).start()
    return {"status": "started", "session_id": session_id, "bot_id": bot_id}


@router.get("/api/hr/session/{session_id}/recording")
def hr_recording_url(session_id: str, authorization: str = Header(None)):
    """Return a FRESH pre-signed recording URL (Recall's links expire in hours, so we re-fetch
    on demand using the session's bot_id instead of serving the stale cached URL)."""
    _require_user(authorization)
    bot_id = db.get_bot_id_for_session(session_id)
    if not bot_id:
        raise HTTPException(status_code=404, detail="No recording for this session")
    import app_full  # lazy import avoids a circular import at module load
    url = app_full.get_fresh_recording_url(bot_id)
    if not url:
        raise HTTPException(status_code=404, detail="Recording not available yet")
    return {"url": url}


@router.get("/api/hr/report/{session_id}/pdf")
def hr_report_pdf(session_id: str, authorization: str = Header(None)):
    _require_user(authorization)
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