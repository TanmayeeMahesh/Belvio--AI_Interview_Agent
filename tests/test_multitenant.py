"""
test_multitenant.py — RBAC + multi-tenant endpoint tests (no real Supabase needed).

Mocks db.* and auth.verify_token so we exercise the request plumbing, role gates, the
invite/registration flow, tenant-ownership 404s and the one-interview-per-candidate guard
in isolation.

Run either way:
    pytest tests/test_multitenant.py -q
    python  tests/test_multitenant.py
"""
import os, sys
from contextlib import ExitStack
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.testclient import TestClient
import api_routes, db, auth

H = {"authorization": "Bearer faketoken"}   # any non-empty Bearer passes the mocked verifier


def _client():
    app = FastAPI()
    app.include_router(api_routes.router)
    return TestClient(app, raise_server_exceptions=True)


def _fake_verify(authz):
    if not authz or not authz.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header")
    return {"id": "user-1", "email": "caller@acme.test"}


def _as(role, org="org-1", stack=None):
    """Patch the caller's identity + membership for the duration of `stack`."""
    stack.enter_context(mock.patch.object(auth, "verify_token", _fake_verify))
    stack.enter_context(mock.patch.object(
        db, "get_user_membership",
        lambda uid: {"role": role, "organization_id": org, "organization_name": "Acme"}))
    # insulate from real Supabase: endpoints that load per-user LLM keys shouldn't hit the DB here
    stack.enter_context(mock.patch.object(auth, "get_user_keys_decrypted", lambda uid: {}))


# ─── RBAC ─────────────────────────────────────────────────
def test_no_auth_is_401():
    c = _client()
    for path in ("/api/whoami", "/api/dashboard/super-admin", "/api/job-openings", "/api/interviews"):
        assert c.get(path).status_code == 401, path


def test_super_admin_dashboard_role_gate():
    c = _client()
    with ExitStack() as s:
        _as("HR", stack=s)
        assert c.get("/api/dashboard/super-admin", headers=H).status_code == 403
    with ExitStack() as s:
        _as("SUPER_ADMIN", stack=s)
        s.enter_context(mock.patch.object(db, "count_rows", lambda *a, **k: 3))
        r = c.get("/api/dashboard/super-admin", headers=H)
        assert r.status_code == 200
        assert r.json()["scheduled_interviews"] == 3   # UI-facing alias present


def test_create_hr_requires_org_admin():
    c = _client()
    with ExitStack() as s:                       # HR may not create HRs
        _as("HR", stack=s)
        assert c.post("/api/org-admin/create-hr", headers=H,
                      json={"email": "new@acme.test", "name": "New", "role": "HR"}).status_code == 403
    with ExitStack() as s:                       # ORG_ADMIN may
        _as("ORG_ADMIN", stack=s)
        s.enter_context(mock.patch.object(db, "get_membership_by_email", lambda e: None))
        s.enter_context(mock.patch.object(
            db, "add_organization_user",
            lambda org, role, **k: {"id": "m-9", "role": role, **k}))
        r = c.post("/api/org-admin/create-hr", headers=H,
                   json={"email": "new@acme.test", "name": "New", "role": "HR"})
        assert r.status_code == 200
        assert r.json()["user"]["status"] == "PENDING"


# ─── invite / registration flow ──────────────────────────
def test_check_email():
    c = _client()
    with mock.patch.object(db, "get_membership_by_email", lambda e: None):
        assert c.post("/api/auth/check-email", json={"email": "ghost@acme.test"}).status_code == 404
    with mock.patch.object(db, "get_membership_by_email",
                           lambda e: {"status": "PENDING", "role": "HR"}):
        r = c.post("/api/auth/check-email", json={"email": "invited@acme.test"})
        assert r.status_code == 200 and r.json()["status"] == "PENDING"


def test_complete_registration():
    c = _client()
    with ExitStack() as s:
        s.enter_context(mock.patch.object(
            db, "get_membership_by_email",
            lambda e: {"id": "m-1", "status": "PENDING", "user_id": None}))
        s.enter_context(mock.patch.object(db, "create_auth_user",
                                          lambda email, pw: {"id": "auth-1", "email": email}))
        activated = {}
        s.enter_context(mock.patch.object(
            db, "activate_membership",
            lambda rid, uid: activated.update({"rid": rid, "uid": uid})))
        r = c.post("/api/auth/complete-registration",
                   json={"email": "invited@acme.test", "password": "longenough1"})
        assert r.status_code == 200 and r.json()["status"] == "ACTIVE"
        assert activated == {"rid": "m-1", "uid": "auth-1"}
    # too-short password rejected before any Auth call
    assert c.post("/api/auth/complete-registration",
                  json={"email": "x@acme.test", "password": "short"}).status_code == 400


# ─── tenant safety ────────────────────────────────────────
def test_job_stats_404_when_job_not_in_org():
    c = _client()
    with ExitStack() as s:
        _as("HR", stack=s)
        s.enter_context(mock.patch.object(db, "get_job_opening", lambda jid, org=None: None))
        assert c.get("/api/job-openings/other-org-job/stats", headers=H).status_code == 404
        assert c.get("/api/job-openings/other-org-job/candidates", headers=H).status_code == 404


def test_one_interview_per_candidate():
    c = _client()
    with ExitStack() as s:
        _as("HR", stack=s)
        s.enter_context(mock.patch.object(
            db, "get_candidate", lambda cid, org=None: {"id": cid, "job_opening_id": "j1",
                                                        "analysis": {}, "resume_text": ""}))
        s.enter_context(mock.patch.object(db, "candidate_has_interview", lambda cid: True))
        r = c.post("/api/candidate/c1/schedule", headers=H,
                   json={"meeting_url": "https://zoom.us/j/123", "question_count": 12})
        assert r.status_code == 409


# ─── standalone runner ────────────────────────────────────
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
