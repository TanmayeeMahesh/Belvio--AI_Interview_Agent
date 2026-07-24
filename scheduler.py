"""
scheduler.py — Candidate invitation + (optional) meeting creation.

Email priority:
  1. SendGrid HTTP API  (SENDGRID_API_KEY)  — free 100/day, works with a Gmail sender, no domain needed
  2. Gmail SMTP         (GMAIL_ADDRESS + GMAIL_APP_PASSWORD) — works locally, blocked in cloud/HF Spaces

SendGrid setup (5 min, free, no domain required):
  1. Sign up at https://sendgrid.com  (free plan)
  2. Settings → Sender Authentication → Single Sender Verification → Create a Sender
     • Fill in your Gmail address as "From Email Address" → save → click the verification link in your Gmail
  3. Settings → API Keys → Create API Key (Restricted: Mail Send only) → copy key
  4. Add to .env / HF Spaces secrets:
       SENDGRID_API_KEY=SG.xxxx...
       SENDGRID_FROM_EMAIL=yourname@gmail.com   ← must match the address you verified above
"""
import os, re, smtplib, ssl, requests as _http
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY    = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


# ─── Meeting-link validation (only platforms the interview bot / Recall.ai can join) ──
SUPPORTED_MEETING_PLATFORMS = "Zoom, Google Meet, or Microsoft Teams"
_MEETING_URL_RE = re.compile(
    r'^https?://('
    r'([\w-]+\.)?zoom\.us/|'                   # Zoom
    r'meet\.google\.com/|'                     # Google Meet
    r'teams\.(microsoft|live)\.com/|'          # Microsoft Teams
    r'([\w-]+\.)?webex\.com/'                   # Webex
    r')', re.IGNORECASE)


def is_supported_meeting_url(url: str) -> bool:
    """True only for a meeting link the bot can actually join (Zoom / Google Meet / Teams / Webex).
    A YouTube or other random URL returns False so we can reject it before scheduling."""
    return bool(_MEETING_URL_RE.match((url or "").strip()))


def _build_body(candidate_name, role, meeting_url, when):
    name      = candidate_name or "Candidate"
    role_line = f" for the {role} position" if role else ""
    when_line = f"\n\nScheduled time: {when}" if when else ""
    return (
        f"Hello {name},\n\n"
        f"You're invited to an AI-conducted technical interview{role_line}. "
        f"The session is conducted by an AI interviewer and will be recorded (audio and video) "
        f"and transcribed for evaluation.{when_line}\n\n"
        f"Join using this link at your scheduled time:\n{meeting_url}\n\n"
        f"Please join from a quiet space with a working microphone. When the AI interviewer asks "
        f"for your consent at the start, please respond verbally to begin.\n\n"
        f"Best regards,\nRecruitment Team"
    )


def send_invite(to_email: str, candidate_name: str, meeting_url: str,
                role: str = None, when: str = None) -> bool:
    """
    Email the interview invite to the candidate.
    Tries SendGrid HTTP API first, falls back to Gmail SMTP.
    Returns True on success, False on failure.
    """
    if not to_email:
        print("[ERROR] send_invite: no candidate email provided")
        return False

    role_line = f" for the {role} position" if role else ""
    subject   = f"Your Interview Invitation{role_line}"
    body      = _build_body(candidate_name, role, meeting_url, when)

    # ── Method 1: SendGrid HTTP API (works in cloud, no domain needed) ──
    if SENDGRID_API_KEY:
        if not SENDGRID_FROM_EMAIL:
            print("[WARN]  SENDGRID_FROM_EMAIL not set in .env — add the Gmail you verified in SendGrid")
        else:
            try:
                resp = _http.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": f"Bearer {SENDGRID_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "personalizations": [{"to": [{"email": to_email}]}],
                        "from": {"email": SENDGRID_FROM_EMAIL},
                        "subject": subject,
                        "content": [{"type": "text/plain", "value": body}],
                    },
                    timeout=15,
                )
                if resp.status_code == 202:   # SendGrid returns 202 Accepted on success
                    print(f"[EMAIL] Invite sent via SendGrid to {to_email}")
                    return True
                print(f"[WARN]  SendGrid returned {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"[WARN]  SendGrid error: {e}")

    # ── Method 2: Gmail SMTP (works locally, blocked on HF Spaces) ──────
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        print("[ERROR] send_invite: no email service configured — set SENDGRID_API_KEY or GMAIL creds in .env")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = to_email
    msg.set_content(body)

    try:
        ctx = ssl.create_default_context()
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
                server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                server.send_message(msg)
        except (OSError, smtplib.SMTPException) as e465:
            print(f"[WARN]  SMTP port 465 failed ({e465}), trying STARTTLS port 587…")
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo(); server.starttls(context=ctx); server.ehlo()
                server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                server.send_message(msg)
        print(f"[EMAIL] Invite sent via Gmail SMTP to {to_email}")
        return True
    except Exception as e:
        print(f"[ERROR] send_invite failed: {e}")
        return False


# ─── GOOGLE MEET CREATION (gated on OAuth setup) ────────────────────────
# Google Calendar API supports full read/write — create, update, delete events.
# Setup: pip install google-auth google-auth-oauthlib google-api-python-client
#        Then follow the OAuth flow (credentials.json from Google Cloud Console).
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

def create_google_meet(subject: str, start_iso: str, end_iso: str,
                       candidate_email: str = None) -> str | None:
    """
    Create a Google Calendar event with a Meet link. Returns the Meet join URL or None.
    start_iso / end_iso: RFC3339, e.g. "2026-06-10T10:00:00+05:30".
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        print("[ERROR] create_google_meet: run pip install google-auth google-auth-oauthlib google-api-python-client")
        return None

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", GOOGLE_SCOPES)
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists("credentials.json"):
                    print("[ERROR] create_google_meet: credentials.json missing")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", GOOGLE_SCOPES)
                creds = flow.run_local_server(port=0)
            with open("token.json", "w") as f:
                f.write(creds.to_json())
        except Exception as e:
            print(f"[ERROR] create_google_meet auth failed: {e}")
            return None

    try:
        service = build("calendar", "v3", credentials=creds)
        event = {
            "summary": subject,
            "start": {"dateTime": start_iso},
            "end":   {"dateTime": end_iso},
            "conferenceData": {"createRequest": {
                "requestId": f"meet-{abs(hash(subject + start_iso))}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }},
        }
        if candidate_email:
            event["attendees"] = [{"email": candidate_email}]
        created = service.events().insert(
            calendarId="primary", body=event,
            conferenceDataVersion=1, sendUpdates="all").execute()
        link = created.get("hangoutLink")
        print(f"[MEET] Google Meet created: {link}")
        return link
    except Exception as e:
        print(f"[ERROR] create_google_meet failed: {e}")
        return None
