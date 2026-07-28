"""
db.py — Supabase persistence for the interview bot (Size 1: save-as-you-go, one interview at a time).
All functions fail SAFE: if Supabase is unreachable, they log and return None so the live
interview is never interrupted by a DB problem. The local JSON transcript remains the backup.
"""
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Lazy client so a missing/broken config doesn't crash import
_client = None
def _db():
    global _client
    if _client is None:
        try:
            from supabase import create_client
            _client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
            print("[DB]  Supabase client ready")
        except Exception as e:
            print(f"[ERROR] Supabase init failed (interview will still run): {e}")
            _client = False          # mark as failed so we don't retry every call
    return _client or None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _is_conn_error(e) -> bool:
    """Transient dropped-connection errors worth one reconnect+retry (Supabase/httpx on idle HTTP/2)."""
    s = str(e).lower()
    return any(k in s for k in (
        "server disconnected", "connectionterminated", "connection terminated",
        "connection reset", "remotedisconnected", "connection aborted",
        "broken pipe", "connection closed", "ConnectError".lower()))


def _exec(op, default=None, label="db"):
    """
    Run a DB operation with ONE reconnect-and-retry on a dropped connection.
    `op` is a function taking the supabase client. Fail-safe: returns `default` and logs
    on terminal failure, so a DB blip never crashes the caller.
    """
    global _client
    for attempt in range(2):
        db = _db()
        if not db:
            return default
        try:
            return op(db)
        except Exception as e:
            if attempt == 0 and _is_conn_error(e):
                print(f"[DB]  {label}: connection dropped — reconnecting & retrying once...")
                _client = None          # force _db() to rebuild the client on the retry
                continue
            print(f"[ERROR] {label}() failed: {e}")
            return default
    return default


def create_session(bot_id: str, total_questions: int,
                   candidate_name: str = None, candidate_email: str = None,
                   role: str = None, status: str = "in_progress",
                   candidate_id: str = None, organization_id: str = None) -> str | None:
    """
    Create a session row. Returns session_id (uuid str) or None.
    - candidate_id given (multi-tenant): link the pre-existing candidate (no new candidate row).
    - candidate_id None (legacy): create a minimal candidate row first.
    status: 'in_progress' for live/manual starts; 'scheduled' when created at schedule time.
    """
    def op(db):
        cid = candidate_id
        if not cid:
            cand = db.table("candidates").insert({
                "name": candidate_name, "email": candidate_email, "role": role,
            }).execute()
            cid = cand.data[0]["id"]
        sess_row = {
            "candidate_id": cid, "bot_id": bot_id,
            "status": status, "total_questions": total_questions,
            "started_at": _now(),
        }
        if organization_id:
            sess_row["organization_id"] = organization_id
        sess = db.table("sessions").insert(sess_row).execute()
        sid = sess.data[0]["id"]
        print(f"[DB]  session created → {sid} ({status})")
        return sid
    return _exec(op, default=None, label="create_session")


def mark_session_started(session_id: str) -> None:
    """Flip a scheduled session to in_progress when the candidate consents and the interview begins."""
    db = _db()
    if not db or not session_id:
        return
    try:
        db.table("sessions").update({"status": "in_progress", "started_at": _now()}) \
          .eq("id", session_id).execute()
    except Exception as e:
        print(f"[ERROR] mark_session_started() failed: {e}")


def insert_answer(session_id: str, q_id: str, role: str, speaker: str,
                  topic: str, text: str, category: str = None) -> None:
    """Insert one transcript row (question / answer / followup_* / intro / closing)."""
    db = _db()
    if not db or not session_id:
        return
    try:
        db.table("answers").insert({
            "session_id": session_id, "q_id": q_id, "role": role,
            "speaker": speaker, "topic": topic, "text": text,
            "category": category, "created_at": _now(),
        }).execute()
    except Exception as e:
        print(f"[ERROR] insert_answer() failed (continuing): {e}")


def close_session(session_id: str, status: str, questions_reached: int) -> None:
    """Mark the session finished with its completion status."""
    if not session_id:
        return
    def op(db):
        db.table("sessions").update({
            "status": status, "questions_reached": questions_reached,
            "ended_at": _now(),
        }).eq("id", session_id).execute()
        print(f"[DB]  session closed → {status}")
    _exec(op, label="close_session")


def read_answers(session_id: str) -> list:
    """Read all answer rows for a session, ordered by time (for the final evaluation)."""
    db = _db()
    if not db or not session_id:
        return []
    try:
        res = (db.table("answers").select("*")
               .eq("session_id", session_id)
               .order("created_at").execute())
        return res.data or []
    except Exception as e:
        print(f"[ERROR] read_answers() failed: {e}")
        return []


def get_session_context(session_id: str) -> dict:
    """Return concise JD/resume analysis fields for the scorer (keeps prompts small)."""
    db = _db()
    if not db or not session_id:
        return {}
    try:
        res = db.table("sessions").select(
            "role, detected_level, key_skills, missing_skills, analysis_summary, jd_match_score"
        ).eq("id", session_id).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        print(f"[ERROR] get_session_context() failed: {e}")
        return {}


def get_candidate_for_session(session_id: str) -> dict:
    """Fetch candidate name/email/role linked to a session (for the report header)."""
    db = _db()
    if not db or not session_id:
        return {}
    try:
        sess = db.table("sessions").select("candidate_id").eq("id", session_id).execute()
        if not sess.data:
            return {}
        cid = sess.data[0]["candidate_id"]
        cand = db.table("candidates").select("*").eq("id", cid).execute()
        return cand.data[0] if cand.data else {}
    except Exception as e:
        print(f"[ERROR] get_candidate_for_session() failed: {e}")
        return {}


def save_report(session_id: str, report: dict) -> None:
    """Upsert the final report row (one per session)."""
    if not session_id:
        return
    def op(db):
        row = {"session_id": session_id, **report}
        db.table("reports").upsert(row, on_conflict="session_id").execute()
        print(f"[DB]  report saved for session {session_id}")
    _exec(op, label="save_report")


def save_recording_url(session_id: str, url: str) -> None:
    """Store the Recall MP4 recording URL on the session (for the HR dashboard).
    Note: this URL is a short-lived pre-signed link (a 'recording exists' flag) — for playback the
    dashboard re-fetches a fresh URL on demand via the bot_id, since cached ones expire in hours."""
    if not session_id or not url:
        return
    def op(db):
        db.table("sessions").update({"recording_url": url}).eq("id", session_id).execute()
        print(f"[DB]  recording_url saved for session {session_id}")
    _exec(op, label="save_recording_url")


def session_in_org(session_id: str, organization_id: str) -> bool:
    """Tenant-safety gate: True only if the session belongs to the given org. Used by the
    /api/hr/* by-id endpoints so one org can't read another org's transcript/report/recording."""
    if not session_id or not organization_id:
        return False
    def op(db):
        res = db.table("sessions").select("organization_id").eq("id", session_id).limit(1).execute()
        return bool(res.data) and res.data[0].get("organization_id") == organization_id
    return _exec(op, default=False, label="session_in_org")


def get_bot_id_for_session(session_id: str) -> str | None:
    """Return the bot_id linked to a session (used to re-fetch a fresh recording URL)."""
    if not session_id:
        return None
    def op(db):
        res = db.table("sessions").select("bot_id").eq("id", session_id).execute()
        return res.data[0].get("bot_id") if res.data else None
    return _exec(op, default=None, label="get_bot_id_for_session")


# ─── SCHEDULED INTERVIEWS (robust, survives restarts) ─────
def create_scheduled_interview(meeting_url: str, scheduled_for_iso: str,
                               candidate_email: str = None, candidate_name: str = None,
                               role: str = None, session_id: str = None,
                               organization_id: str = None, candidate_id: str = None) -> dict | None:
    """Insert a scheduled-interview row. Returns the row (with id) or None.
    organization_id/candidate_id are set by the multi-tenant flow; omitted (None) by the
    legacy single-tenant /api/schedule path."""
    def op(db):
        row_in = {
            "meeting_url": meeting_url, "scheduled_for": scheduled_for_iso,
            "candidate_email": candidate_email, "candidate_name": candidate_name,
            "role": role, "status": "scheduled", "session_id": session_id,
        }
        if organization_id:
            row_in["organization_id"] = organization_id
        if candidate_id:
            row_in["candidate_id"] = candidate_id
        res = db.table("scheduled_interviews").insert(row_in).execute()
        row = res.data[0]
        print(f"[DB]  scheduled interview {row['id']} for {scheduled_for_iso}")
        return row
    return _exec(op, default=None, label="create_scheduled_interview")


def set_session_bot_id(session_id: str, bot_id: str) -> None:
    """Link a pre-created session (made at schedule time) to the bot that's now running it."""
    if not session_id:
        return
    _exec(lambda db: db.table("sessions").update({"bot_id": bot_id}).eq("id", session_id).execute(),
          label="set_session_bot_id")


def due_scheduled_interviews() -> list:
    """Rows that are due now (scheduled_for <= now) and still 'scheduled'.
    Wrapped in _exec so a transient connection drop doesn't silently skip a due interview."""
    def op(db):
        res = (db.table("scheduled_interviews").select("*")
               .eq("status", "scheduled")
               .lte("scheduled_for", _now())
               .order("scheduled_for").execute())
        return res.data or []
    return _exec(op, default=[], label="due_scheduled_interviews")


def claim_scheduled_interview(row_id: str) -> bool:
    """Atomically claim a due row for launch: flip 'scheduled' -> 'launching' ONLY if it is still
    'scheduled'. Returns True only for the caller that won the claim, so multiple schedulers sharing
    this database can never both deploy a bot for the same interview (Postgres serializes the update;
    the loser's WHERE no longer matches and affects 0 rows)."""
    if not row_id:
        return False
    def op(db):
        res = (db.table("scheduled_interviews").update({"status": "launching"})
               .eq("id", row_id).eq("status", "scheduled").execute())
        return bool(res.data)
    return _exec(op, default=False, label="claim_scheduled_interview")


# ─── JOB ROLES (JD uploaded once per role; 80% static set stored per experience level) ──
def create_job_role(owner_id: str, role_name: str, role_source: str, question_count: int,
                    jd_text: str, jd_analysis: dict, question_sets: dict) -> dict | None:
    """Insert a role card. Returns the row (with id) or None."""
    def op(db):
        res = db.table("job_roles").insert({
            "owner_id": owner_id, "role_name": role_name, "role_source": role_source,
            "question_count": question_count, "jd_text": jd_text,
            "jd_analysis": jd_analysis, "question_sets": question_sets,
        }).execute()
        row = res.data[0]
        print(f"[DB]  job_role {row['id']} — {role_name}")
        return row
    return _exec(op, default=None, label="create_job_role")


def list_job_roles(owner_id: str) -> list:
    """Role cards for an HR user, newest first (light columns for the card grid)."""
    if not owner_id:
        return []
    def op(db):
        res = (db.table("job_roles")
               .select("id,role_name,role_source,question_count,created_at")
               .eq("owner_id", owner_id).order("created_at", desc=True).execute())
        return res.data or []
    return _exec(op, default=[], label="list_job_roles")


def get_job_role(role_id: str, owner_id: str = None) -> dict | None:
    """Full role card (incl. jd_text + question_sets). Scoped to owner_id when provided.
    NOTE: superseded by the job_openings-based role cards (multi-tenant) — kept for the
    single-tenant fallback until the job_openings migration lands."""
    if not role_id:
        return None
    def op(db):
        q = db.table("job_roles").select("*").eq("id", role_id)
        if owner_id:
            q = q.eq("owner_id", owner_id)
        res = q.limit(1).execute()
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="get_job_role")


# ─── ORGANIZATIONS / RBAC (multi-tenant: SUPER_ADMIN → ORG_ADMIN → HR) ──────────
def get_user_membership(user_id: str) -> dict | None:
    """Resolve a user's org + role from organization_users (joined to the org name).
    Returns {..., organization_id, role, organization_name} or None if the user has no membership."""
    if not user_id:
        return None
    def op(db):
        res = (db.table("organization_users").select("*")
               .eq("user_id", user_id).limit(1).execute())
        row = res.data[0] if res.data else None
        if not row:
            return None
        org = (db.table("organizations").select("name")
               .eq("id", row["organization_id"]).limit(1).execute())
        row["organization_name"] = org.data[0]["name"] if org.data else None
        return row
    return _exec(op, default=None, label="get_user_membership")


def create_organization(name: str) -> dict | None:
    def op(db):
        res = db.table("organizations").insert({"name": name, "status": "active"}).execute()
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="create_organization")


def list_organizations() -> list:
    def op(db):
        res = db.table("organizations").select("*").order("created_at", desc=True).execute()
        return res.data or []
    return _exec(op, default=[], label="list_organizations")


def add_organization_user(organization_id: str, role: str, email: str = None,
                          user_id: str = None, name: str = None, status: str = "PENDING") -> dict | None:
    """Add an HR/OrgAdmin membership (status PENDING until they accept the invite and register)."""
    def op(db):
        res = db.table("organization_users").insert({
            "organization_id": organization_id, "role": role, "email": email,
            "user_id": user_id, "name": name, "status": status,
        }).execute()
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="add_organization_user")


def create_auth_user(email: str, password: str) -> dict:
    """Create a Supabase Auth login (the actual credential) via the admin API — needs the
    service_role key (our SUPABASE_KEY). Auto-confirms the email so they can log in immediately.
    Raises RuntimeError with the provider message on failure (e.g. 'email already registered')."""
    db = _db()
    if not db:
        raise RuntimeError("Auth backend unavailable.")
    try:
        res = db.auth.admin.create_user({
            "email": email, "password": password, "email_confirm": True,
        })
    except Exception as e:
        raise RuntimeError(str(e))
    u = getattr(res, "user", None) or res
    uid = getattr(u, "id", None)
    if not uid:
        raise RuntimeError("Auth user was not created.")
    return {"id": uid, "email": getattr(u, "email", email)}


def list_org_users(organization_id: str, role: str = None) -> list:
    def op(db):
        q = db.table("organization_users").select("*").eq("organization_id", organization_id)
        if role:
            q = q.eq("role", role)
        return q.order("created_at", desc=True).execute().data or []
    return _exec(op, default=[], label="list_org_users")


def get_membership_by_email(email: str) -> dict | None:
    """Look up a membership row by email (for the invite → registration flow). Case-insensitive."""
    if not email:
        return None
    def op(db):
        res = (db.table("organization_users").select("*")
               .ilike("email", email).limit(1).execute())
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="get_membership_by_email")


def activate_membership(row_id: str, user_id: str) -> dict | None:
    """Attach the freshly-created Auth user_id to a PENDING invite row and flip it ACTIVE
    (called when an invited user completes registration)."""
    def op(db):
        res = (db.table("organization_users")
               .update({"user_id": user_id, "status": "ACTIVE"})
               .eq("id", row_id).execute())
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="activate_membership")


def update_org_user(row_id: str, **fields) -> dict | None:
    """Patch a membership row (name/role/status). Used by org-admin user management."""
    if not row_id or not fields:
        return None
    def op(db):
        res = db.table("organization_users").update(fields).eq("id", row_id).execute()
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="update_org_user")


def delete_org_user(row_id: str) -> bool:
    def op(db):
        db.table("organization_users").delete().eq("id", row_id).execute()
        return True
    return _exec(op, default=False, label="delete_org_user")


def get_organization(org_id: str) -> dict | None:
    if not org_id:
        return None
    def op(db):
        res = db.table("organizations").select("*").eq("id", org_id).limit(1).execute()
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="get_organization")


def update_organization(org_id: str, **fields) -> dict | None:
    """Patch an org row (e.g. name, email_template)."""
    if not org_id or not fields:
        return None
    def op(db):
        res = db.table("organizations").update(fields).eq("id", org_id).execute()
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="update_organization")


def delete_organization(org_id: str) -> bool:
    def op(db):
        db.table("organizations").delete().eq("id", org_id).execute()
        return True
    return _exec(op, default=False, label="delete_organization")


def count_rows(table: str, **eq) -> int:
    """Exact row count for a table with optional equality filters (dashboard tiles)."""
    def op(db):
        q = db.table(table).select("id", count="exact")
        for k, v in eq.items():
            q = q.eq(k, v)
        res = q.execute()
        return res.count or 0
    return _exec(op, default=0, label=f"count_{table}")


# ─── JOB OPENINGS (multi-tenant role cards: JD uploaded once, 4-level question_sets) ──
def create_job_opening(organization_id: str, title: str, description: str, jd_text: str,
                       jd_analysis: dict, question_sets: dict, role_source: str = "bank",
                       question_count: int = 12, status: str = "open") -> dict | None:
    """Insert a job opening (role card). Stores the JD + the 80% static question set per level."""
    def op(db):
        res = db.table("job_openings").insert({
            "organization_id": organization_id, "title": title, "description": description,
            "jd_text": jd_text, "jd_analysis": jd_analysis, "question_sets": question_sets,
            "role_source": role_source, "question_count": question_count, "status": status,
        }).execute()
        row = res.data[0]
        print(f"[DB]  job_opening {row['id']} — {title}")
        return row
    return _exec(op, default=None, label="create_job_opening")


def list_job_openings(organization_id: str) -> list:
    """Job openings for an org, newest first (light columns for the grid)."""
    if not organization_id:
        return []
    def op(db):
        res = (db.table("job_openings")
               .select("id,title,description,status,role_source,question_count,created_at")
               .eq("organization_id", organization_id).order("created_at", desc=True).execute())
        return res.data or []
    return _exec(op, default=[], label="list_job_openings")


def get_job_opening(job_id: str, organization_id: str = None) -> dict | None:
    """Full job opening (incl. jd_text + question_sets). Scoped to org when provided (tenant safety)."""
    if not job_id:
        return None
    def op(db):
        q = db.table("job_openings").select("*").eq("id", job_id)
        if organization_id:
            q = q.eq("organization_id", organization_id)
        res = q.limit(1).execute()
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="get_job_opening")


def delete_job_opening(job_id: str, organization_id: str = None) -> bool:
    def op(db):
        q = db.table("job_openings").delete().eq("id", job_id)
        if organization_id:
            q = q.eq("organization_id", organization_id)
        q.execute()
        return True
    return _exec(op, default=False, label="delete_job_opening")


# ─── CANDIDATES (multi-tenant: resume uploaded against a job opening) ─────────
def create_candidate_full(organization_id: str, job_opening_id: str, name: str, email: str,
                          role: str, resume_text: str, analysis: dict) -> dict | None:
    """Insert a candidate with their parsed resume + JD-match analysis (JSON)."""
    def op(db):
        res = db.table("candidates").insert({
            "organization_id": organization_id, "job_opening_id": job_opening_id,
            "name": name, "email": email, "role": role,
            "resume_text": resume_text, "analysis": analysis,
        }).execute()
        row = res.data[0]
        print(f"[DB]  candidate {row['id']} — {name} ({email})")
        return row
    return _exec(op, default=None, label="create_candidate_full")


def list_candidates(organization_id: str, job_opening_id: str = None) -> list:
    """Candidates for an org (optionally one job opening), newest first."""
    if not organization_id:
        return []
    def op(db):
        q = db.table("candidates").select("*").eq("organization_id", organization_id)
        if job_opening_id:
            q = q.eq("job_opening_id", job_opening_id)
        return q.order("created_at", desc=True).execute().data or []
    return _exec(op, default=[], label="list_candidates")


def get_candidate(cand_id: str, organization_id: str = None) -> dict | None:
    if not cand_id:
        return None
    def op(db):
        q = db.table("candidates").select("*").eq("id", cand_id)
        if organization_id:
            q = q.eq("organization_id", organization_id)
        res = q.limit(1).execute()
        return res.data[0] if res.data else None
    return _exec(op, default=None, label="get_candidate")


def candidate_scheduled_map(candidate_ids: list) -> dict:
    """Map candidate_id -> its latest scheduled_interview row, for the ones that have one.
    Lets the candidates list mark is_scheduled / scheduled_time without an N+1 query."""
    if not candidate_ids:
        return {}
    def op(db):
        res = (db.table("scheduled_interviews").select("*")
               .in_("candidate_id", candidate_ids).execute())
        out = {}
        for r in (res.data or []):
            cid = r.get("candidate_id")
            if cid:
                out[cid] = r   # last one wins (fine — one interview per candidate is enforced)
        return out
    return _exec(op, default={}, label="candidate_scheduled_map")


def sessions_status_map(session_ids: list) -> dict:
    """Map session_id -> live status (the Interviews table shows the real interview state,
    which lives on the session, not the scheduled_interviews row)."""
    ids = [s for s in (session_ids or []) if s]
    if not ids:
        return {}
    def op(db):
        res = db.table("sessions").select("id,status").in_("id", ids).execute()
        return {r["id"]: r.get("status") for r in (res.data or [])}
    return _exec(op, default={}, label="sessions_status_map")


def candidate_has_interview(candidate_id: str) -> bool:
    """True if this candidate already has a scheduled interview (one-per-candidate guard)."""
    if not candidate_id:
        return False
    def op(db):
        res = (db.table("scheduled_interviews").select("id")
               .eq("candidate_id", candidate_id).limit(1).execute())
        return bool(res.data)
    return _exec(op, default=False, label="candidate_has_interview")


def list_org_interviews(organization_id: str, limit: int = 200) -> list:
    """All scheduled interviews for an org, newest first (Interviews table + dashboards)."""
    if not organization_id:
        return []
    def op(db):
        res = (db.table("scheduled_interviews").select("*")
               .eq("organization_id", organization_id)
               .order("created_at", desc=True).limit(limit).execute())
        return res.data or []
    return _exec(op, default=[], label="list_org_interviews")


def update_scheduled_interview(row_id: str, **fields) -> None:
    """Patch a scheduled-interview row (status, bot_id, email_sent, ...)."""
    if not row_id:
        return
    _exec(lambda db: db.table("scheduled_interviews").update(fields).eq("id", row_id).execute(),
          label="update_scheduled_interview")


def list_scheduled_interviews(limit: int = 50) -> list:
    """All scheduled interviews, newest first (for the operator UI/dashboard)."""
    db = _db()
    if not db:
        return []
    try:
        res = (db.table("scheduled_interviews").select("*")
               .order("created_at", desc=True).limit(limit).execute())
        return res.data or []
    except Exception as e:
        print(f"[ERROR] list_scheduled_interviews() failed: {e}")
        return []


# ─── ANALYSIS + QUESTIONS + DASHBOARD READS ───────────────
def update_session_analysis(session_id, analysis: dict, meeting_url: str,
                            scheduled_for_iso: str, jd_text=None, resume_text=None) -> None:
    """Store the JD/resume analysis + scheduling info on the session row (US-AG-01)."""
    if not session_id:
        return
    def op(db):
        db.table("sessions").update({
            "candidate_name": analysis.get("candidateName"),
            "candidate_email": analysis.get("candidateEmail"),
            "role": analysis.get("jobRole"),
            "detected_level": analysis.get("detectedLevel"),
            "level_reason": analysis.get("levelReason"),
            "key_skills": analysis.get("skills"),
            "missing_skills": analysis.get("missingSkills"),
            "technical_stack": analysis.get("technicalStack"),
            "jd_match_score": analysis.get("jdMatchScore"),
            "analysis_summary": analysis.get("analysisSummary"),
            "meeting_url": meeting_url, "scheduled_at": scheduled_for_iso,
            "jd_text": jd_text, "resume_text": resume_text,
        }).eq("id", session_id).execute()
    _exec(op, label="update_session_analysis")


def save_questions(session_id, questions: list) -> None:
    """Persist the generated dynamic question plan (US-AG-02)."""
    if not session_id:
        return
    rows = [{
        "session_id": session_id, "question_number": i + 1,
        "question_text": q.get("question"), "topic": q.get("topic"),
        "question_type": q.get("question_type"), "depth": q.get("depth"),
        "target_skill": q.get("target_skill"), "key_concepts": q.get("key_concepts", []),
        "status": "pending",
    } for i, q in enumerate(questions)]
    if not rows:
        return
    _exec(lambda db: db.table("questions").insert(rows).execute(), label="save_questions")


def get_questions(session_id) -> list:
    """Read the question plan for a session, ordered (for the interview engine to use)."""
    db = _db()
    if not db or not session_id:
        return []
    try:
        res = (db.table("questions").select("*").eq("session_id", session_id)
               .order("question_number").execute())
        return res.data or []
    except Exception as e:
        print(f"[ERROR] get_questions() failed: {e}")
        return []


def list_sessions_with_reports(organization_id: str = None) -> list:
    """
    Dashboard list, shaped for their frontend:
    adds recommendation/overall_score, selection_status (their SessionsTab filter field),
    and created_at alias (their components read created_at; our column is started_at).
    Scoped to `organization_id` when given (multi-tenant: an org only sees its own sessions).
    """
    db = _db()
    if not db:
        return []
    try:
        _q = db.table("sessions").select("*")
        if organization_id:
            _q = _q.eq("organization_id", organization_id)
        sess = (_q.order("started_at", desc=True).execute()).data or []
        reps = (db.table("reports").select("session_id, recommendation, overall_score").execute()).data or []
        rep_map = {r["session_id"]: r for r in reps}
        for s in sess:
            r = rep_map.get(s["id"])
            s["recommendation"] = r.get("recommendation") if r else None
            s["overall_score"] = r.get("overall_score") if r else None
            s["selection_status"] = s["recommendation"] or "N/A"          # their filter field
            s.setdefault("created_at", s.get("started_at"))               # their time field
        return sess
    except Exception as e:
        print(f"[ERROR] list_sessions_with_reports() failed: {e}")
        return []


def _pair_transcript(rows: list, per_topic: list) -> list:
    """
    Their ReportsTab expects paired Q&A: {question_text, answer_text, overall_score,
    evaluation_note}. Our answers table stores transcript ROWS (one per utterance),
    so pair question→answer by q_id and attach the per-topic score by topic.
    """
    topic_scores = {t.get("topic"): t for t in (per_topic or []) if isinstance(t, dict)}
    pairs, by_qid = [], {}
    for r in rows:
        qid = r.get("q_id")
        if not qid or qid in ("intro", "closing"):
            continue
        slot = by_qid.setdefault(qid, {"q_id": qid, "topic": r.get("topic")})
        if r.get("role") in ("question", "followup_question"):
            slot["question_text"] = r.get("text")
        elif r.get("role") in ("answer", "followup_answer"):
            slot["answer_text"] = r.get("text")
            slot["evaluation_note"] = r.get("category")
    for qid in sorted(by_qid, key=lambda k: [int(p) if p.isdigit() else 0 for p in str(k).split(".")]):
        slot = by_qid[qid]
        if not slot.get("question_text") and not slot.get("answer_text"):
            continue
        ts = topic_scores.get(slot.get("topic"), {})
        slot["overall_score"] = ts.get("topic_score")
        if ts.get("note"):
            slot["evaluation_note"] = ts["note"]
        pairs.append(slot)
    return pairs


def get_session_full(session_id) -> dict:
    """
    Full session detail in the NESTED shape their frontend consumes:
      {session: {...}, questions: [...], answers: [paired Q&A], report: {...}}
    (SessionsTab reads .questions for the plan modal; ReportsTab reads .session/.report/.answers)
    """
    db = _db()
    if not db or not session_id:
        return {}
    try:
        s = db.table("sessions").select("*").eq("id", session_id).execute()
        session = s.data[0] if s.data else {}
        session.setdefault("created_at", session.get("started_at"))
        report = get_report(session_id)
        return {
            "session": session,
            "questions": get_questions(session_id),
            "answers": _pair_transcript(read_answers(session_id), report.get("per_topic")),
            "report": report or None,
            "integrity": get_integrity_report(session_id) or None,   # proctoring signals (server-side join)
        }
    except Exception as e:
        print(f"[ERROR] get_session_full() failed: {e}")
        return {}


def get_session_id_by_bot_id(bot_id: str) -> str | None:
    """Return the session_id of an in_progress session for this bot (used when Session is gone from memory)."""
    db = _db()
    if not db or not bot_id:
        return None
    try:
        res = (db.table("sessions").select("id")
               .eq("bot_id", bot_id).eq("status", "in_progress").execute())
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        print(f"❌ get_session_id_by_bot_id() failed: {e}")
        return None


def list_stuck_sessions(older_than_minutes: int = 120) -> list:
    """Sessions still in_progress for longer than the given threshold — likely orphaned."""
    db = _db()
    if not db:
        return []
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)).isoformat()
        res = (db.table("sessions").select("id, bot_id, questions_reached")
               .eq("status", "in_progress").lt("started_at", cutoff).execute())
        return res.data or []
    except Exception as e:
        print(f"❌ list_stuck_sessions() failed: {e}")
        return []


def list_stale_scheduled_sessions(older_than_minutes: int = 30) -> list:
    """Sessions still 'scheduled' whose scheduled_at is well past — candidate never joined → no_show."""
    db = _db()
    if not db:
        return []
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)).isoformat()
        res = (db.table("sessions").select("id, scheduled_at")
               .eq("status", "scheduled").lt("scheduled_at", cutoff).execute())
        return res.data or []
    except Exception as e:
        print(f"❌ list_stale_scheduled_sessions() failed: {e}")
        return []


def get_report(session_id) -> dict:
    """Read the report row for a session."""
    db = _db()
    if not db or not session_id:
        return {}
    try:
        res = db.table("reports").select("*").eq("session_id", session_id).execute()
        return res.data[0] if res.data else {}
    except Exception as e:
        print(f"[ERROR] get_report() failed: {e}")
        return {}


# ─── PROCTORING / INTEGRITY (separate table → no write race with reports) ──
def save_integrity_report(session_id: str, data: dict) -> None:
    """Upsert the integrity/proctoring result (one row per session). Fail-safe."""
    if not session_id:
        return
    row = {"session_id": session_id, **data}
    _exec(lambda db: db.table("integrity_reports").upsert(row, on_conflict="session_id").execute(),
          label="save_integrity_report")


def get_integrity_report(session_id: str) -> dict:
    """Read the integrity/proctoring row for a session (empty dict if none)."""
    if not session_id:
        return {}
    def op(db):
        res = db.table("integrity_reports").select("*").eq("session_id", session_id).execute()
        return res.data[0] if res.data else {}
    return _exec(op, default={}, label="get_integrity_report")