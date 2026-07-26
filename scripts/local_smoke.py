"""
local_smoke.py — exercise the multi-tenant API against a running local server.

Logs in, then hits the read endpoints (always safe). With --roundtrip it also creates a
uniquely-named test organization and immediately DELETES it, so it verifies create+list+delete
without leaving junk in the (shared) database.

IMPORTANT: local shares the SAME Supabase + Recall.ai as prod. This script never schedules an
interview (that would send a real email and let prod's scheduler deploy a real bot). Keep the
server on SCHEDULER_ENABLED=false while testing.

Usage (server running on :8000):
  python scripts/local_smoke.py --email companies@bellurbis.com --password ****
  python scripts/local_smoke.py --email you@acme.test --password **** --roundtrip
"""
import argparse, sys, uuid, requests


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--roundtrip", action="store_true",
                    help="also create + delete a throwaway org (SUPER_ADMIN only)")
    a = ap.parse_args()
    s = requests.Session()

    def call(method, path, ok=None, **kw):
        r = s.request(method, a.base + path, **kw)
        tag = "" if (ok is None or r.status_code == ok) else "  <-- unexpected"
        print(f"  {method.upper():6s} {path:45s} {r.status_code}{tag}")
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, r.text

    print(f"\n== login as {a.email} ==")
    code, body = call("post", "/api/auth/login", json={"email": a.email, "password": a.password})
    if code != 200:
        print("  login failed:", body)
        sys.exit(1)
    s.headers["authorization"] = f"Bearer {body['token']}"

    print("== identity ==")
    _, who = call("get", "/api/whoami", ok=200)
    print("     ->", who)

    print("== dashboards (403 just means your role can't see that one) ==")
    call("get", "/api/dashboard/super-admin")
    call("get", "/api/dashboard/org-admin")
    call("get", "/api/dashboard/hr")

    print("== org-scoped reads ==")
    call("get", "/api/admin/organizations")
    call("get", "/api/job-openings", ok=200)
    call("get", "/api/candidates", ok=200)
    call("get", "/api/interviews", ok=200)

    if a.roundtrip:
        print("== create -> verify -> delete a throwaway org (no residue) ==")
        name = f"zz-smoke-{uuid.uuid4().hex[:8]}"
        code, org = call("post", "/api/admin/create-organization", ok=200, json={"name": name})
        if code == 200:
            oid = org.get("organization", {}).get("id")
            _, orgs = call("get", "/api/admin/organizations", ok=200)
            found = any(o.get("id") == oid for o in (orgs.get("organizations") or orgs or []))
            print(f"     created {oid}, visible in list: {found}")
            if oid:
                call("delete", f"/api/admin/organizations/{oid}", ok=200)
                print("     deleted (cleaned up)")

    print("\nDone.\n")


if __name__ == "__main__":
    main()
