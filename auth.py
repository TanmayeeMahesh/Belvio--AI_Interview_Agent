"""
auth.py — Supabase auth (verify the frontend's JWT) + per-user API-key storage.

The frontend logs in via Supabase Auth (signInWithPassword) and sends the JWT as
'Authorization: Bearer <token>'. verify_token() validates it and returns the user.

API keys (Gemini/Claude/Groq) are entered per-user in the sidebar. We store them ENCRYPTED
at rest (Fernet), keyed by user id, and only ever return a MASKED form to the UI
(sk-ab••••••wx9f). The full key is decrypted server-side only when making an LLM call.

Setup:
  pip install supabase cryptography
  .env: SUPABASE_URL, SUPABASE_KEY (service_role), APP_ENCRYPTION_KEY (Fernet key)
  Generate APP_ENCRYPTION_KEY once:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  DB table needed (run in Supabase):
    create table user_api_keys (
      user_id uuid primary key,
      gemini_key text, claude_key text, groq_key text,
      updated_at timestamptz default now()
    );
"""
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

_URL = os.getenv("SUPABASE_URL")
_KEY = os.getenv("SUPABASE_KEY")
_ENC = os.getenv("APP_ENCRYPTION_KEY")
_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")   # Supabase → Settings → API → JWT Secret (HS256)
# Escape hatch for LOCAL dev only: if no JWT secret is set, auth is normally REFUSED (fail closed).
# Set AUTH_ALLOW_UNVERIFIED=true locally to permit unverified token decode for testing.
_ALLOW_UNVERIFIED = os.getenv("AUTH_ALLOW_UNVERIFIED", "").strip().lower() == "true"

_sb = None
def _db():
    global _sb
    if _sb is None:
        try:
            from supabase import create_client
            _sb = create_client(_URL, _KEY)
        except Exception as e:
            print(f"❌ auth Supabase init failed: {e}")
            _sb = False
    return _sb or None

_fernet = None
def _cipher():
    global _fernet
    if _fernet is None:
        try:
            from cryptography.fernet import Fernet
            _fernet = Fernet(_ENC.encode()) if _ENC else False
            if not _ENC:
                print("⚠️ APP_ENCRYPTION_KEY missing — API keys cannot be stored securely")
        except Exception as e:
            print(f"❌ cipher init failed: {e}")
            _fernet = False
    return _fernet or None


# ─── AUTH ─────────────────────────────────────────────────
import base64 as _b64, json as _json

_warned_unverified = False


def _decode_unverified(token: str) -> dict:
    """Read the payload WITHOUT verifying the signature. Only reached when SUPABASE_JWT_SECRET
    is not configured — INSECURE, dev-only (any forged token is accepted)."""
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError("Malformed JWT")
    padded = parts[1] + '=' * (-len(parts[1]) % 4)
    payload = _json.loads(_b64.urlsafe_b64decode(padded))
    uid = payload.get('sub') or payload.get('user_id')
    if not uid:
        raise ValueError("No user ID in token")
    return {"id": uid, "email": payload.get('email', '')}


def verify_token(authorization: str):
    """
    Validate a Supabase JWT from the 'Authorization: Bearer <token>' header. Returns {id, email}
    or raises ValueError.

    When SUPABASE_JWT_SECRET is set we VERIFY the HS256 signature + expiry + audience (secure).
    When it's missing we fall back to an UNVERIFIED payload decode and log a loud warning — so
    local dev isn't blocked, but every DEPLOYED environment MUST set the secret or anyone can
    forge a token and impersonate a super-admin.
    """
    global _warned_unverified
    if not authorization or not authorization.startswith("Bearer "):
        raise ValueError("Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]

    if _JWT_SECRET:
        try:
            import jwt  # PyJWT
        except ImportError:
            # Secret is configured but the library is missing → FAIL CLOSED. Never silently
            # skip signature verification (that would accept forged tokens in production).
            raise ValueError("Auth misconfigured: PyJWT is not installed but SUPABASE_JWT_SECRET is set.")
        try:
            payload = jwt.decode(
                token, _JWT_SECRET, algorithms=["HS256"],
                audience="authenticated", leeway=10,
                options={"require": ["exp", "sub"]},
            )
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired — please log in again")
        except Exception as e:
            raise ValueError(f"Invalid token: {e}")
        uid = payload.get("sub") or payload.get("user_id")
        if not uid:
            raise ValueError("No user ID in token")
        return {"id": uid, "email": payload.get("email", "")}

    # ── no secret configured ──
    # FAIL CLOSED by default: refuse auth unless an operator has explicitly opted into the
    # insecure dev fallback (AUTH_ALLOW_UNVERIFIED=true). A prod deploy that forgets the secret
    # then rejects every request (loud + safe) instead of silently accepting forged tokens.
    if not _ALLOW_UNVERIFIED:
        raise ValueError("Auth not configured: set SUPABASE_JWT_SECRET "
                         "(or AUTH_ALLOW_UNVERIFIED=true for local dev only).")
    if not _warned_unverified:
        _warned_unverified = True   # set first: a print failure must never re-fire or block auth
        print("[SECURITY] AUTH_ALLOW_UNVERIFIED=true and no SUPABASE_JWT_SECRET - JWTs are NOT "
              "signature-verified. LOCAL DEV ONLY. Never set this in a deployed environment.")
    return _decode_unverified(token)


def user_id_from(user) -> str:
    return getattr(user, "id", None) or (user.get("id") if isinstance(user, dict) else None)


# ─── API KEY STORAGE (encrypted, masked) ──────────────────
def _mask(key: str) -> str:
    """Show only first 3 and last 4 chars: 'sk-ab••••••wx9f'. Never returns the full key."""
    if not key:
        return ""
    if len(key) <= 8:
        return "••••"
    return f"{key[:3]}{'•' * 8}{key[-4:]}"


def save_user_keys(user_id: str, keys: dict) -> bool:
    """
    Store/update a user's API keys (encrypted). keys = {"gemini":..,"claude":..,"groq":..}.
    Only non-empty values are updated (so partial saves don't wipe existing keys).
    """
    db, cipher = _db(), _cipher()
    if not db or not cipher or not user_id:
        return False
    row = {"user_id": user_id, "updated_at": datetime.now(timezone.utc).isoformat()}
    for provider in ("gemini", "claude", "groq"):
        val = (keys.get(provider) or "").strip()
        if val:
            row[f"{provider}_key"] = cipher.encrypt(val.encode()).decode()
    try:
        db.table("user_api_keys").upsert(row, on_conflict="user_id").execute()
        return True
    except Exception as e:
        print(f"❌ save_user_keys failed: {e}")
        return False


def get_user_keys_decrypted(user_id: str) -> dict:
    """Server-side only: returns the FULL decrypted keys for making LLM calls. Never sent to UI."""
    db, cipher = _db(), _cipher()
    if not db or not cipher or not user_id:
        return {}
    try:
        res = db.table("user_api_keys").select("*").eq("user_id", user_id).execute()
        if not res.data:
            return {}
        row = res.data[0]
        out = {}
        for provider in ("gemini", "claude", "groq"):
            enc = row.get(f"{provider}_key")
            if enc:
                try:
                    out[provider] = cipher.decrypt(enc.encode()).decode()
                except Exception:
                    pass
        return out
    except Exception as e:
        print(f"❌ get_user_keys_decrypted failed: {e}")
        return {}


def get_user_keys_masked(user_id: str) -> dict:
    """For the UI: returns masked keys only (first3+last4). Safe to send to the browser."""
    full = get_user_keys_decrypted(user_id)
    return {provider: _mask(full.get(provider, "")) for provider in ("gemini", "claude", "groq")}