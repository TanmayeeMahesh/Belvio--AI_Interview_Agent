import base64, io, json, requests, time, threading, uuid, sys

# Windows consoles default to cp1252 and CRASH on emoji in print() with UnicodeEncodeError.
# Force UTF-8 so the emoji log lines never break send_invite() or any other code path.
# (Linux / HF Spaces already use UTF-8 — this is a harmless no-op there.)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse
from gtts import gTTS
from groq import Groq
import uvicorn, os
from dotenv import load_dotenv
import db          # Supabase persistence (fail-safe)
import evaluator   # final scoring + report (US-AG-07/08)
import scheduler   # email invite + (optional) meeting creation
import proctor     # post-interview integrity analysis (fail-safe, background)

load_dotenv()
app = FastAPI(title="AI Interview Bot")

import api_routes
app.include_router(api_routes.router)
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ─── CONFIG ───────────────────────────────────────────────
RECALLAI_API_KEY = os.getenv("RECALLAI_API_KEY")
NGROK_URL        = os.getenv("NGROK_URL")
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")

# ─── TTS (pluggable: Sarvam for Indian voices, gTTS as the free fallback) ──
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
# default to Sarvam when a key is present, else gTTS; override with TTS_PROVIDER=gtts|sarvam
TTS_PROVIDER   = os.getenv("TTS_PROVIDER", "sarvam" if SARVAM_API_KEY else "gtts").lower()
SARVAM_MODEL   = os.getenv("SARVAM_MODEL", "bulbul:v2")    # documented; v2 default speaker = anushka
SARVAM_SPEAKER = os.getenv("SARVAM_SPEAKER", "anushka")
SARVAM_LANG    = os.getenv("SARVAM_LANG", "en-IN")

# ─── Proctoring (post-interview integrity). Instant off-switch: PROCTORING_ENABLED=false ──
PROCTORING_ENABLED = os.getenv("PROCTORING_ENABLED", "true").lower() == "true"

BOT_NAME    = "AI Interviewer (Sandbox)"
RECALL_BASE = f"https://{os.getenv('RECALL_REGION', 'ap-northeast-1')}.recall.ai/api/v1"
GATE_MODEL  = "llama-3.1-8b-instant"
REPLY_MODEL = "llama-3.1-8b-instant"

FOLLOWUPS_PER_Q    = 1
SILENCE_GATE       = 2.0
MAX_TURN_WAIT      = 12.0
# Timeouts — env-tunable. The first two directly control Recall bot-runtime COST (the bot is billed
# the whole time it waits in the lobby / for consent), so keep them tight for no-shows.
WAITING_ROOM_TIMEOUT = int(os.getenv("WAITING_ROOM_TIMEOUT", "180"))   # leave lobby if not admitted (was 600)
NO_SHOW_TIMEOUT      = int(os.getenv("NO_SHOW_TIMEOUT", "120"))        # leave if no consent after admission (was 300)
SILENCE_END_SEC      = int(os.getenv("SILENCE_END_SEC", "180"))        # end interview after this much silence
MAX_INTERVIEW_SEC    = int(os.getenv("MAX_INTERVIEW_SEC", str(45 * 60)))
SCHEDULED_EXPIRY_MIN = int(os.getenv("SCHEDULED_EXPIRY_MIN", "30"))    # scheduled→no_show if never joined
TTS_WPS            = 2.6

groq_client = Groq(api_key=GROQ_API_KEY)

# Static fallback questions (used only when a session has no DB-generated plan)
with open("speech_interview_logic/sample_questions.json") as f:
    STATIC_QUESTIONS = json.load(f)


# ═══════════════════════════════════════════════════════════
#  PER-SESSION STATE — one Session per live interview, keyed by bot_id.
#  This is what allows MULTIPLE interviews to run at once without colliding.
# ═══════════════════════════════════════════════════════════
class Session:
    def __init__(self, bot_id, session_id=None, questions=None):
        self.bot_id = bot_id
        self.session_id = session_id            # Supabase session row id
        self.questions = questions or STATIC_QUESTIONS   # THIS candidate's question set
        self.question_index = 0
        self.followup_count = 0
        self.awaiting_followup = False
        self.interview_started = False
        self.interview_over = False
        self.completion_status = "completed"
        self.transcript = []
        self.covered_concepts = []
        self.answer_buffer = []
        self.confirming_completion = False
        self.bot_speaking = False
        self.last_asked = ""
        self.join_time = 0.0
        self.turn_start_time = 0.0
        self.interview_start_time = 0.0
        self.last_activity = 0.0
        self.silence_timer = None
        self.routing_key = ""           # webhook routing key embedded in the Recall endpoint URL
        self.intro_spoken = False       # True once consent prompt has been spoken (poll or late-join)
        self.intro_text = ""            # stored so webhook handler can speak it if bot admitted late
        # per-session locks so sessions never block or corrupt each other
        self.process_lock = threading.Lock()
        self.speak_lock = threading.Lock()

SESSIONS   = {}   # bot_id      -> Session  (cleared when session ends)
ROUTING    = {}   # routing_key -> Session  (cleared when session ends)
COMPLETED  = {}   # routing_key -> session_id  (kept after end so recording.done can find it)
_registry_lock = threading.Lock()

def register(sess: Session):
    with _registry_lock:
        SESSIONS[sess.bot_id] = sess
        if sess.routing_key:
            ROUTING[sess.routing_key] = sess

def get_session(bot_id) -> Session:
    return SESSIONS.get(bot_id)


def recall_headers():
    return {"Authorization": f"Token {RECALLAI_API_KEY}", "Content-Type": "application/json"}

def _normalize_questions(rows: list) -> list:
    """Map DB question rows → the shape the engine expects ({question, topic, key_concepts})."""
    out = []
    for r in rows:
        out.append({
            "question": r.get("question_text") or r.get("question") or "",
            "topic": r.get("topic") or "General",
            "key_concepts": r.get("key_concepts") if isinstance(r.get("key_concepts"), list) else [],
        })
    return [q for q in out if q["question"]]


# ─── TEXT-TO-SPEECH (returns base64 MP3 — the only kind Recall output_audio accepts) ──
def _gtts_mp3_b64(text: str) -> str:
    buf = io.BytesIO()
    gTTS(text=text, lang="en", slow=False).write_to_fp(buf)
    return base64.b64encode(buf.getvalue()).decode()

def _sarvam_mp3_b64(text: str):
    """Sarvam Bulbul TTS → base64 MP3 (output_audio_codec=mp3, so no transcoding). None on failure."""
    r = requests.post("https://api.sarvam.ai/text-to-speech",
        headers={"api-subscription-key": SARVAM_API_KEY, "Content-Type": "application/json"},
        json={"text": text, "target_language_code": SARVAM_LANG, "speaker": SARVAM_SPEAKER,
              "model": SARVAM_MODEL, "output_audio_codec": "mp3"},
        timeout=20)
    if r.status_code == 200:
        audios = r.json().get("audios") or []
        if audios and audios[0]:
            return audios[0]            # already base64-encoded MP3
    print(f"⚠️ Sarvam TTS {r.status_code}: {r.text[:150]} — falling back to gTTS")
    return None

def synthesize_mp3_b64(text: str) -> str:
    """Base64 MP3 for `text`. Uses Sarvam (Indian voices) when configured, always falls back to
    gTTS so TTS never hard-fails. Both return standard-alphabet base64 MP3 for Recall."""
    if TTS_PROVIDER == "sarvam" and SARVAM_API_KEY:
        try:
            b64 = _sarvam_mp3_b64(text)
            if b64:
                return b64
        except Exception as e:
            print(f"⚠️ Sarvam TTS error: {e} — falling back to gTTS")
    return _gtts_mp3_b64(text)

# ─── SPEAK (per-session serialized + blocking so audio never overlaps) ─
def speak(sess: Session, text: str):
    with sess.speak_lock:
        sess.bot_speaking = True
        try:
            b64 = synthesize_mp3_b64(text)
            for _att in range(2):
                r = requests.post(f"{RECALL_BASE}/bot/{sess.bot_id}/output_audio/",
                                  headers=recall_headers(), json={"kind": "mp3", "b64_data": b64})
                print(f"📤 [{sess.bot_id[:8]}] output_audio → {r.status_code}")
                if r.status_code in (200, 201):
                    break
                if _att == 0 and r.status_code == 400 and "cannot_command_unstarted_bot" in r.text:
                    print(f"⏳ [{sess.bot_id[:8]}] bot not ready yet — retrying in 3s...")
                    time.sleep(3)
                    continue
                print(f"❌ speak() failed: {r.status_code} — {r.text[:150]}")
                return
            est = max(2.0, len(text.split()) / TTS_WPS + 0.8)
            time.sleep(est)
        except Exception as e:
            print(f"❌ speak() exception: {e}")
        finally:
            sess.bot_speaking = False
            sess.last_activity = time.time()
            sess.answer_buffer = []

def leave_call(bot_id):
    try:
        r = requests.post(f"{RECALL_BASE}/bot/{bot_id}/leave_call/", headers=recall_headers())
        print(f"👋 leave_call → {r.status_code}")
    except Exception as e:
        print(f"❌ leave_call(): {e}")

def get_bot_status(bot_id):
    r = requests.get(f"{RECALL_BASE}/bot/{bot_id}/", headers=recall_headers())
    if r.status_code == 200:
        sc = r.json().get("status_changes", [])
        return sc[-1].get("code", "unknown") if sc else "unknown"
    return "error"

def _find_download_url(obj):
    """Recursively search any nested dict/list for a non-empty 'download_url'. Recall nests it
    under media_shortcuts.<kind>.data.download_url, but the <kind> key varies by recording config."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "download_url" and isinstance(v, str) and v:
                return v
            found = _find_download_url(v)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_download_url(item)
            if found:
                return found
    return None

def get_fresh_recording_url(bot_id, kind="audio"):
    """Re-fetch a CURRENT pre-signed recording URL from Recall on demand (they expire in hours).
    kind: "audio" → the mixed-audio track (report player); "video" → the mixed-video track (proctoring).
    Prefers a media_shortcut whose key matches `kind`; falls back to any available download URL."""
    if not bot_id:
        return None
    try:
        r = requests.get(f"{RECALL_BASE}/bot/{bot_id}/", headers=recall_headers())
        if r.status_code == 200:
            for rec in r.json().get("recordings", []):
                shortcuts = rec.get("media_shortcuts") or {}
                # prefer the track matching the requested kind (e.g. "video_mixed" for kind="video")
                for key, node in shortcuts.items():
                    if kind in key:
                        url = ((node or {}).get("data") or {}).get("download_url")
                        if url:
                            return url
                url = _find_download_url(rec)   # fallback: any download_url
                if url:
                    return url
        else:
            print(f"❌ get_fresh_recording_url: Recall API {r.status_code}")
    except Exception as e:
        print(f"❌ get_fresh_recording_url(): {e}")
    return None

def fetch_and_save_recording(bot_id, session_id):
    """Retrieve the recording download URL after the call and save it (US-AG-06). S3 URL is temporary."""
    if not session_id:
        return
    time.sleep(15)
    for attempt in range(20):   # 20 × 30s = 10 min; Recall recording processing can take several min
        try:
            r = requests.get(f"{RECALL_BASE}/bot/{bot_id}/", headers=recall_headers())
            if r.status_code == 200:
                data = r.json()
                recs = data.get("recordings", [])
                # DIAGNOSTIC: dump the full recording shape ONCE — even when the URL is found —
                # so we can see exactly which tracks Recall produced (mixed vs separate, bot vs candidate).
                if recs and attempt == 0:
                    print(f"   🎥 [diag] recording[0] keys = {list(recs[0].keys())}")
                    print(f"   🎥 [diag] media_shortcuts = {json.dumps(recs[0].get('media_shortcuts', {}))[:1500]}")
                # search the whole recording object — the media_shortcuts key name varies by config
                for rec in recs:
                    url = _find_download_url(rec)
                    if url:
                        print(f"🎥 recording URL retrieved (attempt {attempt+1})")
                        db.save_recording_url(session_id, url)
                        return
                if not recs:
                    print(f"   🎥 no recordings array yet (attempt {attempt+1}/20)...")
                else:
                    status_code = (recs[0].get("status") or {}).get("code", "?")
                    print(f"   🎥 {len(recs)} rec(s), status={status_code!r}, URL not ready (attempt {attempt+1}/20)...")
            else:
                print(f"   🎥 API {r.status_code} (attempt {attempt+1}/20)...")
        except Exception as e:
            print(f"❌ fetch_and_save_recording(): {e}")
        time.sleep(30)
    print("⚠️ recording URL not available after 10 min of retries")

def wait_for_join_and_speak(sess: Session, intro: str):
    polls = max(30, WAITING_ROOM_TIMEOUT // 2)   # 2s per poll; matches the lobby timeout
    print(f"⏳ Polling bot {sess.bot_id[:8]} for admission (up to {WAITING_ROOM_TIMEOUT // 60} min)...")
    for i in range(polls):
        time.sleep(2)
        status = get_bot_status(sess.bot_id)
        if i < 5 or i % 15 == 14:   # log first 5 + every 30s after
            print(f"   [{sess.bot_id[:8]}] [{i+1}/{polls}] status = '{status}'")
        if status in ("in_call_recording", "in_call_not_recording"):
            print(f"🎉 [{sess.bot_id[:8]}] admitted — speaking intro")
            sess.join_time = time.time()
            sess.intro_spoken = True
            threading.Thread(target=no_show_watchdog, args=(sess,), daemon=True).start()
            log_to_transcript(sess, BOT_NAME, intro, q_id="intro", role="intro")
            speak(sess, intro)
            return
        if status in ("done", "error", "fatal", "call_ended"):
            print(f"❌ [{sess.bot_id[:8]}] ended early: {status}"); return
    print(f"❌ [{sess.bot_id[:8]}] admission timeout — never reached in_call (late-join via webhook now active)")


# ─── WATCHDOGS (per session) ──────────────────────────────
def no_show_watchdog(sess: Session):
    deadline = sess.join_time + NO_SHOW_TIMEOUT
    while time.time() < deadline:
        time.sleep(5)
        if sess.interview_started or get_session(sess.bot_id) is not sess:
            return
    if not sess.interview_started and get_session(sess.bot_id) is sess:
        print(f"⏰ [{sess.bot_id[:8]}] no consent — leaving")
        sess.interview_over = True
        sess.completion_status = "no_show"
        speak(sess, "I haven't received a response, so I'll end the session now. Thank you.")
        leave_call(sess.bot_id)
        if sess.session_id:
            db.close_session(sess.session_id, "no_show", 0)   # persist now (was missing → row stuck 'scheduled')
        with _registry_lock:
            SESSIONS.pop(sess.bot_id, None)
            if sess.routing_key:
                ROUTING.pop(sess.routing_key, None)

def cap_watchdog(sess: Session):
    while get_session(sess.bot_id) is sess and not sess.interview_over:
        time.sleep(10)
        if sess.interview_start_time and (time.time() - sess.interview_start_time) >= MAX_INTERVIEW_SEC:
            if sess.interview_over:
                return
            sess.completion_status = "capped"
            print(f"⏲️ [{sess.bot_id[:8]}] 45-min cap reached")
            end_session(sess,
                "We're at our time limit for today, so I'll wrap up here. Thank you for your time — "
                "your responses will be sent for further assessment and our team will be in touch.")
            return

def silence_end_watchdog(sess: Session):
    while get_session(sess.bot_id) is sess and not sess.interview_over:
        time.sleep(5)
        if not sess.interview_started or sess.bot_speaking:
            continue
        if sess.last_activity and (time.time() - sess.last_activity) >= SILENCE_END_SEC:
            if sess.interview_over:
                return
            sess.completion_status = "incomplete_no_response"
            print(f"🔇 [{sess.bot_id[:8]}] no response too long — closing incomplete")
            end_session(sess,
                "I haven't heard a response for a while, so I'll conclude the session here. "
                "Thank you for your time — what we covered will be sent for further assessment.")
            return

def end_session(sess: Session, closing_text: str):
    if sess.interview_over and sess.completion_status == "completed":
        return
    sess.interview_over = True
    log_to_transcript(sess, BOT_NAME, closing_text, q_id="closing", role="closing")
    speak(sess, closing_text)
    save_transcript(sess)
    sid = sess.session_id
    db.close_session(sid, sess.completion_status, sess.question_index + 1)
    leave_call(sess.bot_id)
    if sid:
        threading.Thread(target=evaluator.evaluate_session,
                         args=(sid, sess.completion_status), daemon=True).start()
        threading.Thread(target=fetch_and_save_recording, args=(sess.bot_id, sid), daemon=True).start()
        if PROCTORING_ENABLED:
            threading.Thread(target=proctor.analyze_session, args=(sid, sess.bot_id), daemon=True).start()
    # keep routing_key → session_id so recording.done (fires minutes later) can still find it
    if sess.routing_key and sid:
        COMPLETED[sess.routing_key] = sid
    # unregister so the bot_id/routing_key can't be reused/contaminated
    with _registry_lock:
        SESSIONS.pop(sess.bot_id, None)
        if sess.routing_key:
            ROUTING.pop(sess.routing_key, None)

def log_to_transcript(sess: Session, speaker, text, category=None, topic=None, q_id=None, role=None):
    entry = {"timestamp": datetime.now().strftime("%H:%M:%S"),
             "q_id": q_id, "role": role, "speaker": speaker, "topic": topic,
             "text": text, "category": category}
    sess.transcript.append(entry)
    c = f" | {category}" if category else ""
    qs = f" [{q_id}/{role}]" if q_id else ""
    print(f"📝 [{sess.bot_id[:8]}]{qs} {speaker}: {text[:55]}{c}")
    db.insert_answer(sess.session_id, q_id, role, speaker, topic, text, category)

def save_transcript(sess: Session):
    fn = f"transcript_{sess.bot_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    payload = {"completion_status": sess.completion_status,
               "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "questions_reached": sess.question_index + 1,
               "total_questions": len(sess.questions),
               "transcript": sess.transcript}
    with open(fn, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"💾 [{sess.bot_id[:8]}] Saved → {fn}  ({sess.completion_status})")


# ─── SHARED MODALITY PREFIX ───────────────────────────────
IO_CONTEXT = """INPUT NOTE: The candidate's words come from speech-to-text — no punctuation, words may
be dropped or doubled, homophones may appear (e.g. "emb" may mean "MBA"). Judge MEANING charitably;
never penalize transcription noise.
OUTPUT NOTE: If you write a spoken line, it is read aloud by text-to-speech: short sentences, no
symbols, no lists, no markdown. Sound human and warm, not robotic."""

# ─── 3-STATE TURN DETECTION ───────────────────────────────
def turn_verdict(sess: Session, text: str) -> str:
    if len(text.split()) >= 25:
        return "complete"
    if sess.confirming_completion:
        return "complete"
    prompt = f"""{IO_CONTEXT}

Is this spoken interview answer COMPLETE, still going (INCOMPLETE), or genuinely UNCERTAIN?

ANSWER SO FAR: "{text}"

Reply ONE word:
COMPLETE   — a finished thought
INCOMPLETE — clearly trailed off mid-sentence ("and i", "firstly i will")
UNCERTAIN  — grammatically complete but likely more to say ("i would use some algorithms")"""
    try:
        resp = groq_client.chat.completions.create(
            model=GATE_MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=4)
        v = resp.choices[0].message.content.strip().upper()
        verdict = "incomplete" if "INCOMPLETE" in v else ("uncertain" if "UNCERTAIN" in v else "complete")
        print(f"🧠 [{sess.bot_id[:8]}] turn verdict: '{text[:35]}...' → {verdict}")
        return verdict
    except Exception as e:
        print(f"❌ turn_verdict(): {e} — defaulting complete")
        return "complete"

# ─── LIVE GATE (stateless) ────────────────────────────────
def gate_answer(question, answer, key_concepts, topic) -> dict:
    prompt = f"""{IO_CONTEXT}

You are gating ONE interview answer to decide whether to follow up. NOT a final grade.

QUESTION: {question}
TOPIC: {topic}
EXPECTED KEY CONCEPTS: {key_concepts}
CANDIDATE ANSWER: {answer}

Judge: COVERAGE (addressed key concepts?), RELEVANCE (on-topic or dodged?), and most importantly
UNDERSTANDING — did they DEMONSTRATE understanding (explain how/why, give specifics) or just NAME
things (say a term with no explanation)? Confident jargon with no real explanation is NAMING.

Pick ONE category:
  "strong"    — relevant, covers key concepts, shows real understanding
  "thin"      — only NAMES concepts, or confident without substance
  "vague"     — too little / unclear to judge
  "off_topic" — didn't answer, dodged, or drifted

Reply ONLY valid JSON, no markdown:
{{"category":"strong|thin|vague|off_topic","covered":["<demonstrated concept>"],"note":"<5-8 words>"}}"""
    try:
        resp = groq_client.chat.completions.create(
            model=GATE_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=200, temperature=0.2)
        raw = resp.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        r = json.loads(raw)
        print(f"🎯 gate={r.get('category')} | covered={r.get('covered')} | {r.get('note','')}")
        return r
    except Exception as e:
        print(f"❌ gate_answer(): {e} — defaulting 'vague'")
        return {"category": "vague", "covered": [], "note": "gate failed"}

# ─── SPOKEN LINES (stateless) ─────────────────────────────
def followup_line(question, answer, category) -> str:
    styles = {
        "thin": ("They sound confident but may only be NAMING concepts. Ask ONE pointed follow-up "
                 "that tests whether they truly understand a specific term or claim they made."),
        "vague": ("Their answer was unclear or thin. Ask ONE follow-up that helps them give a fuller, "
                  "more specific answer."),
        "off_topic": ("They didn't actually answer. Gently redirect them back to the question with ONE "
                      "clear restatement."),
    }
    prompt = f"""{IO_CONTEXT}

QUESTION ASKED: {question}
CANDIDATE SAID: {answer}

{styles.get(category, styles['vague'])}
Reference a SPECIFIC detail they actually said. Reply with ONLY the spoken follow-up."""
    try:
        resp = groq_client.chat.completions.create(
            model=REPLY_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=80, temperature=0.7)
        return (resp.choices[0].message.content.strip().strip('"') or "Could you go a bit deeper on that?")
    except Exception as e:
        print(f"❌ followup_line(): {e}"); return "Could you go a bit deeper on that?"

def intro_followup_line(answer) -> str:
    """Purposeful follow-up for the opening 'tell me about yourself' question — always steers the
    candidate to describe a concrete project, instead of a random gate-based follow-up."""
    prompt = f"""{IO_CONTEXT}

This is a candidate's opening background answer at the start of an interview:
"{answer}"

Ask ONE warm follow-up that invites them to pick ONE project or piece of work they mentioned and
describe it concretely — what it was, their specific role, and the technologies or approach they used.
If they did not clearly mention any project, ask them to walk you through a recent project they are
proud of. Reference something specific they said. Reply with ONLY the spoken follow-up question."""
    try:
        resp = groq_client.chat.completions.create(
            model=REPLY_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=90, temperature=0.6)
        return (resp.choices[0].message.content.strip().strip('"')
                or "Could you tell me about one project you worked on and what your role was?")
    except Exception as e:
        print(f"❌ intro_followup_line(): {e}")
        return "Could you tell me about one project you worked on and what your role was?"

def rephrase_question(question, key_concepts) -> str:
    prompt = f"""{IO_CONTEXT}
The candidate did not understand this question. Rephrase it more simply and concretely with a tiny
hint of what you're looking for. Do NOT just repeat it.
QUESTION: {question}
LOOKING FOR: {key_concepts}
Reply with ONLY the rephrased spoken question."""
    try:
        resp = groq_client.chat.completions.create(
            model=REPLY_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=90, temperature=0.6)
        return resp.choices[0].message.content.strip().strip('"') or f"Let me put it differently. {question}"
    except Exception as e:
        print(f"❌ rephrase_question(): {e}"); return f"Let me put it differently. {question}"

def transition_line(answer, next_question) -> str:
    """Returns ONLY a brief acknowledgment/segue — NOT the question. The caller appends the
    verbatim question, so the question is always asked clearly (never paraphrased away)."""
    prompt = f"""{IO_CONTEXT}

The candidate just said: "{answer}"

Briefly acknowledge something specific they said in ONE short clause, then add a natural lead-in
like "Let's move on." Do NOT ask any question and do NOT add a new topic — only the acknowledgment
and the short segue. Reply with ONLY that short spoken sentence."""
    try:
        resp = groq_client.chat.completions.create(
            model=REPLY_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=60, temperature=0.7)
        return resp.choices[0].message.content.strip().strip('"') or "Thank you. Let's move on."
    except Exception as e:
        print(f"❌ transition_line(): {e}"); return "Thank you. Let's move on."

def ack_line(answer) -> str:
    prompt = f"""{IO_CONTEXT}
The candidate just said: "{answer}"
Give a brief, warm one-line acknowledgment referencing something specific they said, then stop.
Reply with ONLY the spoken sentence."""
    try:
        resp = groq_client.chat.completions.create(
            model=REPLY_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=60, temperature=0.7)
        return (resp.choices[0].message.content.strip().strip('"') or "Thank you.")
    except Exception as e:
        print(f"❌ ack_line(): {e}"); return "Thank you."

# ─── CROSS-QUESTION CHECK ─────────────────────────────────
def check_if_already_answered(sess: Session, next_q, next_concepts) -> dict:
    if not sess.covered_concepts:
        return {"already_answered": False}
    prompt = f"""{IO_CONTEXT}

NEXT QUESTION: {next_q}
ITS KEY CONCEPTS: {next_concepts}
CONCEPTS ALREADY DEMONSTRATED: {sess.covered_concepts}

Has the candidate substantially answered this already?
Reply ONLY valid JSON:
{{"already_answered":false,"acknowledgment":null,"adjusted_question":null}}
OR:
{{"already_answered":true,"acknowledgment":"You touched on this earlier.","adjusted_question":"Building on that, can you go deeper into X?"}}"""
    try:
        resp = groq_client.chat.completions.create(
            model=GATE_MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=150)
        raw = resp.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        r = json.loads(raw)
        if r.get("already_answered"):
            print(f"⚡ [{sess.bot_id[:8]}] Cross-Q: already covered — adapting")
        return r
    except Exception as e:
        print(f"❌ check_if_already_answered(): {e}")
        return {"already_answered": False}

# ─── TURN ENDING (per session) ────────────────────────────
def schedule_processing(sess: Session):
    if sess.silence_timer:
        sess.silence_timer.cancel()
    t = threading.Timer(SILENCE_GATE, run_gate_check, args=(sess,))
    t.daemon = True
    sess.silence_timer = t
    t.start()

def run_gate_check(sess: Session):
    if sess.interview_over:
        return
    if not sess.process_lock.acquire(blocking=False):
        print(f"🔒 [{sess.bot_id[:8]}] already processing — skipping duplicate fire")
        return
    try:
        if not sess.answer_buffer or sess.bot_speaking:
            return
        full_answer = " ".join(sess.answer_buffer).strip()
        waited = time.time() - (sess.turn_start_time or time.time())
        verdict = turn_verdict(sess, full_answer) if waited < MAX_TURN_WAIT else "complete"

        if verdict == "incomplete":
            print(f"   [{sess.bot_id[:8]}] ↳ incomplete — keep listening")
            schedule_processing(sess); return
        if verdict == "uncertain":
            print(f"   [{sess.bot_id[:8]}] ↳ uncertain — asking if done")
            sess.confirming_completion = True
            speak(sess, "Did you want to add anything, or shall we continue?")
            schedule_processing(sess); return

        sess.answer_buffer = []
        sess.turn_start_time = 0.0
        sess.confirming_completion = False
        print(f"🧩 [{sess.bot_id[:8]}] Full answer: '{full_answer[:60]}'")
        process_answer(sess, full_answer)
    finally:
        sess.process_lock.release()

# ─── CORE FLOW (per session) ──────────────────────────────
def process_answer(sess: Session, candidate_text: str):
    if sess.interview_over:
        return
    low = candidate_text.lower()
    item = sess.questions[sess.question_index]
    q_num = sess.question_index + 1
    q_now = item["question"]

    sess.confirming_completion = False
    last = sess.last_asked or q_now

    if any(p in low for p in ["repeat", "say again", "come again", "didn't catch", "didn't hear",
                              "what's my question", "what is my question", "what's the question",
                              "what was the question", "what's my next question", "didn't get the question",
                              "ask me the question", "i didn't hear a question", "you didn't ask"]):
        print(f"🔁 [{sess.bot_id[:8]}] Meta: restate last-asked"); speak(sess, f"Of course. {last}"); return
    if any(p in low for p in ["don't understand", "didn't understand", "not clear", "what do you mean", "confused", "rephrase"]):
        print(f"💡 [{sess.bot_id[:8]}] Meta: rephrase"); speak(sess, rephrase_question(last, item["key_concepts"])); return
    if any(p in low for p in ["still thinking", "give me a moment", "one moment", "hold on", "let me think"]):
        print(f"🧠 [{sess.bot_id[:8]}] Meta: thinking"); speak(sess, "Take your time. I'm listening whenever you're ready."); return

    gate = gate_answer(item["question"], candidate_text, item["key_concepts"], item["topic"])
    category = gate.get("category", "vague")
    sess.covered_concepts = list(set(sess.covered_concepts + gate.get("covered", [])))

    if sess.awaiting_followup:
        log_to_transcript(sess, "Candidate", candidate_text, category=category,
                          topic=item["topic"], q_id=f"{q_num}.1", role="followup_answer")
        advance(sess, candidate_text)
        return

    log_to_transcript(sess, "Candidate", candidate_text, category=category,
                      topic=item["topic"], q_id=str(q_num), role="answer")

    # Intro/background question → always one purposeful project-focused follow-up (not random)
    is_intro = sess.question_index == 0 or (item.get("topic") or "").strip().lower() == "introduction"
    if is_intro and sess.followup_count < FOLLOWUPS_PER_Q:
        sess.followup_count += 1
        sess.awaiting_followup = True
        fu = intro_followup_line(candidate_text)
        sess.last_asked = fu
        print(f"🔄 [{sess.bot_id[:8]}] Intro project follow-up {q_num}.1")
        log_to_transcript(sess, BOT_NAME, fu, topic=item["topic"], q_id=f"{q_num}.1", role="followup_question")
        speak(sess, fu)
        return

    if category != "strong" and sess.followup_count < FOLLOWUPS_PER_Q:
        sess.followup_count += 1
        sess.awaiting_followup = True
        fu = followup_line(item["question"], candidate_text, category)
        sess.last_asked = fu
        print(f"🔄 [{sess.bot_id[:8]}] Follow-up {q_num}.1 ({category})")
        log_to_transcript(sess, BOT_NAME, fu, topic=item["topic"], q_id=f"{q_num}.1", role="followup_question")
        speak(sess, fu)
        return

    advance(sess, candidate_text)

def advance(sess: Session, last_answer: str):
    if sess.interview_over:
        return
    sess.awaiting_followup = False
    sess.followup_count = 0
    sess.question_index += 1

    if sess.question_index < len(sess.questions):
        nxt = sess.questions[sess.question_index]
        nxt_num = sess.question_index + 1
        cc = check_if_already_answered(sess, nxt["question"], nxt["key_concepts"])
        if cc.get("already_answered") and cc.get("adjusted_question"):
            ack = ack_line(last_answer)
            to_say = f"{ack} {cc.get('acknowledgment','')} {cc['adjusted_question']}"
            sess.last_asked = cc["adjusted_question"]
        else:
            # segue (ack only) + the VERBATIM question, so the question is always asked clearly
            segue = transition_line(last_answer, nxt["question"])
            to_say = f"{segue} {nxt['question']}"
            sess.last_asked = nxt["question"]
        log_to_transcript(sess, BOT_NAME, to_say, topic=nxt["topic"], q_id=str(nxt_num), role="question")
        speak(sess, to_say)
    else:
        sess.completion_status = "completed"
        ack = ack_line(last_answer)
        end_session(sess, f"{ack} That completes our interview. Thank you for your time — your "
                          "responses will be sent for further assessment and our team will be in touch.")
        print(f"✅ [{sess.bot_id[:8]}] Interview complete")


# ─── SCHEDULER WORKER (DB-backed; now launches concurrent interviews) ──
SCHEDULER_POLL_SEC = 30

def scheduler_worker():
    print(f"🗓️  scheduler worker started (poll every {SCHEDULER_POLL_SEC}s)")
    while True:
        try:
            for row in db.due_scheduled_interviews():
                print(f"🗓️  launching scheduled interview {row['id']}")
                result = deploy_bot(row["meeting_url"], session_id=row.get("session_id"))
                if result.get("status") == "deployed":
                    db.update_scheduled_interview(row["id"], status="launched",
                                                  bot_id=result.get("bot_id"))
                else:
                    db.update_scheduled_interview(row["id"], status="failed")
        except Exception as e:
            print(f"❌ scheduler_worker loop: {e}")
        time.sleep(SCHEDULER_POLL_SEC)

def stuck_session_cleaner():
    """Every 10 min: close sessions stuck in_progress >2h (→ stopped), and expire scheduled
    sessions the candidate never joined (→ no_show)."""
    time.sleep(300)  # wait 5 min after startup before first check
    while True:
        try:
            for row in db.list_stuck_sessions(older_than_minutes=120):
                sid = row["id"]
                stuck_bot_id = row.get("bot_id", "")
                # Verify the bot is actually gone before closing
                bot_gone = True
                if stuck_bot_id:
                    try:
                        r = requests.get(f"{RECALL_BASE}/bot/{stuck_bot_id}/", headers=recall_headers())
                        if r.status_code == 200:
                            sc = r.json().get("status_changes", [])
                            last = sc[-1].get("code", "") if sc else ""
                            bot_gone = last in ("done", "fatal", "call_ended", "error") or not last
                        else:
                            bot_gone = True  # can't reach bot, assume gone
                    except Exception:
                        bot_gone = True
                if bot_gone:
                    db.close_session(sid, "stopped", row.get("questions_reached") or 0)
                    threading.Thread(target=evaluator.evaluate_session, args=(sid, "stopped"), daemon=True).start()
                    print(f"🔧 Stuck session cleaner: closed {sid[:8]} (bot {stuck_bot_id[:8] if stuck_bot_id else '?'})")
            # scheduled sessions the candidate never joined → mark no_show (closes the 'scheduled forever' gap)
            for row in db.list_stale_scheduled_sessions(older_than_minutes=SCHEDULED_EXPIRY_MIN):
                sid = row["id"]
                db.close_session(sid, "no_show", 0)
                print(f"🔧 Scheduled expiry: {sid[:8]} never joined → no_show")
        except Exception as e:
            print(f"❌ stuck_session_cleaner: {e}")
        time.sleep(600)  # check every 10 min

@app.on_event("startup")
def _start_scheduler():
    threading.Thread(target=scheduler_worker, daemon=True).start()
    threading.Thread(target=stuck_session_cleaner, daemon=True).start()
    # Warm the fine-tuned gap-question model in the background (downloads from the private HF
    # repo on first cloud boot, then cached). Never blocks startup or fails the app.
    try:
        import extraction
        extraction.prewarm_gap_model()
    except Exception as e:
        print(f"⚠️ gap model prewarm skipped: {e}")


# ─── DEPLOY ───────────────────────────────────────────────
def deploy_bot(meeting_url: str, session_id: str = None) -> dict:
    """
    Create a Recall bot for meeting_url and register a Session for it.
    If session_id is given (scheduled flow), load THAT candidate's questions from the DB;
    otherwise (manual /trigger-bot) use the static fallback and create the session at consent.
    """
    routing_key = str(uuid.uuid4())   # pre-generated before the API call — embedded in webhook URL
    print(f"\n🚀 Deploying to: {meeting_url}  (session_id={session_id})")
    payload = {
        "bot_name": BOT_NAME, "meeting_url": meeting_url,
        "recording_config": {
            "audio_mixed_mp4": {},   # both bot TTS + candidate voice (used for the report's player)
            "video_mixed_mp4": {},   # candidate video — sampled post-interview for proctoring (Mode A)
            # force the bot's own output_audio into the mix (bypasses platform echo cancellation,
            # which otherwise leaves only the candidate's voice in the recording). Default is false.
            "include_bot_in_recording": {"audio": True},
            # TODO: upload to Azure Blob for permanent storage; Recall URL expires ~7 days
            "transcript": {"provider": {"recallai_streaming": {
                "mode": "prioritize_low_latency", "language_code": "en"}}},
            "realtime_endpoints": [{"type": "webhook",
                "url": f"{NGROK_URL}/webhook/transcription/{routing_key}",
                "events": ["transcript.data", "transcript.partial_data"]}]
        },
        "automatic_leave": {"waiting_room_timeout": WAITING_ROOM_TIMEOUT,
                            "in_call_not_recording_timeout": 3600,
                            "silence_detection": {"timeout": 3600}}
    }
    r = requests.post(f"{RECALL_BASE}/bot/", headers=recall_headers(), json=payload)
    if r.status_code != 201:
        print(f"❌ Deploy failed: {r.status_code} — {r.text}")
        return {"status": "failed", "detail": r.text}

    bot_id = r.json()["id"]
    # load this candidate's questions if we have a session, else static fallback
    questions = STATIC_QUESTIONS
    if session_id:
        rows = db.get_questions(session_id)
        if rows:
            questions = _normalize_questions(rows)
            print(f"📋 [{bot_id[:8]}] loaded {len(questions)} questions from session {session_id[:8]}")
        else:
            print(f"⚠️ [{bot_id[:8]}] no DB questions for session — using static fallback")
        db.set_session_bot_id(session_id, bot_id)

    sess = Session(bot_id, session_id=session_id, questions=questions)
    sess.routing_key = routing_key
    register(sess)

    intro = ("Hello! I'm your AI interviewer today. This session is recorded — both audio and "
             "video — and transcribed. Do you consent to proceed? Please say yes to continue.")
    sess.intro_text = intro   # stored for late-join fallback in webhook handler
    threading.Thread(target=wait_for_join_and_speak, args=(sess, intro), daemon=True).start()
    print(f"✅ Bot deployed: {bot_id}")
    return {"status": "deployed", "bot_id": bot_id}


# ─── ENDPOINTS ────────────────────────────────────────────
@app.get("/")
def home():
    return {"status": "running", "active_interviews": len(SESSIONS),
            "bots": list(SESSIONS.keys())}

@app.get("/trigger-bot")
def trigger_bot(meeting_url: str, session_id: str = None):
    """Manual deploy (testing). Optionally pass session_id to use that candidate's DB questions."""
    return deploy_bot(meeting_url, session_id=session_id)

@app.get("/test-speak/{bot_id}")
def test_speak(bot_id):
    sess = get_session(bot_id)
    if not sess:
        return {"status": "no active session for that bot_id"}
    speak(sess, "Hello, this is a test. Can you hear me?")
    return {"status": "attempted"}

@app.post("/schedule-interview")
async def schedule_interview(request: Request):
    """Lightweight manual scheduling (operator console). Full flow is api_routes /api/schedule."""
    body = await request.json()
    meeting_url = (body.get("meeting_url") or "").strip()
    email = (body.get("candidate_email") or "").strip()
    name  = (body.get("candidate_name") or "").strip()
    role  = (body.get("role") or "").strip()
    delay = int(body.get("delay_minutes", 10))
    if not meeting_url:
        return {"status": "error", "detail": "meeting_url is required"}
    scheduled_for = datetime.now(timezone.utc) + timedelta(minutes=delay)
    when_human = scheduled_for.astimezone(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M") + " IST"
    row = db.create_scheduled_interview(meeting_url=meeting_url,
        scheduled_for_iso=scheduled_for.isoformat(), candidate_email=email or None,
        candidate_name=name or None, role=role or None)
    email_ok = scheduler.send_invite(email, name, meeting_url, role=role, when=when_human) if email else False
    if row and email_ok:
        db.update_scheduled_interview(row["id"], email_sent=True)
    return {"status": "scheduled", "scheduled_for": scheduled_for.isoformat(),
            "join_in_minutes": delay, "email_sent": email_ok,
            "schedule_id": row["id"] if row else None}

@app.get("/scheduled")
def scheduled():
    return {"scheduled": db.list_scheduled_interviews()}

@app.post("/webhook/transcription/{routing_key}")
@app.post("/webhook/transcription")
async def handle_transcription(request: Request, background_tasks: BackgroundTasks,
                               routing_key: str = ""):
    payload = await request.json()
    event = payload.get("event", "")
    data  = payload.get("data", {})

    # Support both payload shapes:
    #   Shape A: data.data.words  (nested)
    #   Shape B: data.words       (flat)
    if isinstance(data, dict) and "data" in data:
        inner = data.get("data", {})
    else:
        inner = data if isinstance(data, dict) else {}
    words = inner.get("words", [])
    text  = " ".join(w.get("text", "") for w in words).strip()
    speaker = (inner.get("participant", {}) or {}).get("name", "")
    is_final = (event == "transcript.data")

    # PRIMARY ROUTING: use routing_key embedded in the webhook URL (set at deploy time).
    # This is the only method that's correct when multiple interviews run concurrently,
    # because Recall.ai does not include bot_id in realtime transcription webhook payloads.
    sess = ROUTING.get(routing_key) if routing_key else None

    # Derive bot_id for logging and legacy paths (not for routing)
    bot_id = sess.bot_id if sess else (
        payload.get("bot_id", "") or
        (payload.get("bot") or {}).get("id", "") or
        (data.get("bot_id", "") if isinstance(data, dict) else "") or
        (inner.get("bot_id", "") if isinstance(inner, dict) else "")
    )
    # Last-resort: if only one interview is live and routing_key lookup missed (old-style deploy)
    if not sess and not bot_id:
        with _registry_lock:
            if len(SESSIONS) == 1:
                bot_id = next(iter(SESSIONS))
    if not sess and bot_id:
        sess = get_session(bot_id)

    if event in ("transcript.data", "transcript.partial_data") and text:
        label = (sess.bot_id[:8] if sess else (bot_id[:8] if bot_id else "????"))
        print(f"🔍 [{label}] {event} | speaker={speaker!r} | text={text[:60]!r}")

    if event in ("bot.done", "call.ended"):
        if sess and not sess.interview_over:
            # Bot left externally (host ended call, network drop, etc.) before end_session() ran
            sess.interview_over = True
            if sess.transcript:
                save_transcript(sess)
            sid = sess.session_id
            db.close_session(sid, sess.completion_status, sess.question_index + 1)
            if sid:
                if sess.routing_key:
                    COMPLETED[sess.routing_key] = sid
                threading.Thread(target=fetch_and_save_recording, args=(bot_id, sid), daemon=True).start()
                threading.Thread(target=evaluator.evaluate_session, args=(sid, sess.completion_status), daemon=True).start()
            with _registry_lock:
                SESSIONS.pop(bot_id, None)
                if sess.routing_key:
                    ROUTING.pop(sess.routing_key, None)
        elif not sess and bot_id:
            # Session not in memory (server restarted, routing miss) — close via DB if still open
            sid = db.get_session_id_by_bot_id(bot_id)
            if sid:
                db.close_session(sid, "stopped", 0)
                threading.Thread(target=evaluator.evaluate_session, args=(sid, "stopped"), daemon=True).start()
                threading.Thread(target=fetch_and_save_recording, args=(bot_id, sid), daemon=True).start()
                print(f"🔧 Closed orphaned session {sid[:8]} via bot.done webhook")
        return {"status": "ok"}

    if event == "recording.done":
        # Recall has finished processing the recording — get the URL immediately instead of polling
        sid = (sess.session_id if sess else None) or COMPLETED.get(routing_key)
        bid = sess.bot_id if sess else bot_id
        if sid and bid:
            try:
                rec_resp = requests.get(f"{RECALL_BASE}/bot/{bid}/", headers=recall_headers())
                if rec_resp.status_code == 200:
                    for rec in rec_resp.json().get("recordings", []):
                        am  = (rec.get("media_shortcuts") or {}).get("audio_mixed") or {}
                        url = (am.get("data") or {}).get("download_url")
                        if url:
                            db.save_recording_url(sid, url)
                            print(f"🎥 [webhook] recording.done → URL saved for session {sid[:8]}")
                            COMPLETED.pop(routing_key, None)
                            break
            except Exception as e:
                print(f"❌ recording.done handler: {e}")
        return {"status": "ok"}

    if not sess or not text or speaker == BOT_NAME or sess.interview_over:
        return {"status": "ok"}
    if sess.bot_speaking:
        return {"status": "ok"}

    if not sess.interview_started:
        if not is_final:
            return {"status": "ok"}
        # Late-join: bot was admitted after the polling window — speak intro now, wait for consent next turn
        if not sess.intro_spoken and sess.intro_text:
            sess.intro_spoken = True
            sess.join_time = time.time()
            threading.Thread(target=no_show_watchdog, args=(sess,), daemon=True).start()
            log_to_transcript(sess, BOT_NAME, sess.intro_text, q_id="intro", role="intro")
            background_tasks.add_task(speak, sess, sess.intro_text)
            return {"status": "ok"}
        no_words  = ["no", "don't", "stop", "refuse"]
        yes_words = ["yes", "sure", "okay", "ok", "proceed", "agree", "yeah", "yep", "consent"]
        if any(w in text.lower() for w in no_words):
            # candidate explicitly declined consent → close immediately as 'declined' (distinct status)
            sess.interview_over = True
            sess.completion_status = "declined"
            background_tasks.add_task(speak, sess, "Understood. The interview is cancelled. Thank you for your time.")
            background_tasks.add_task(leave_call, bot_id)
            if sess.session_id:
                db.close_session(sess.session_id, "declined", 0)
            with _registry_lock:
                SESSIONS.pop(sess.bot_id, None)
                if sess.routing_key:
                    ROUTING.pop(sess.routing_key, None)
            print(f"🚫 [{bot_id[:8]}] candidate declined consent → declined")
            return {"status": "ok"}
        elif any(w in text.lower() for w in yes_words) or len(text.split()) <= 3:
            sess.interview_started = True
            sess.interview_start_time = time.time()
            sess.last_activity = time.time()
            # manual path: no session yet → create one now; scheduled path: flip to in_progress
            if not sess.session_id:
                sess.session_id = db.create_session(bot_id, len(sess.questions))
            else:
                db.mark_session_started(sess.session_id)
            threading.Thread(target=cap_watchdog, args=(sess,), daemon=True).start()
            threading.Thread(target=silence_end_watchdog, args=(sess,), daemon=True).start()
            first = sess.questions[0]
            sess.last_asked = first["question"]
            log_to_transcript(sess, BOT_NAME, first["question"], topic=first["topic"], q_id="1", role="question")
            background_tasks.add_task(speak, sess, f"Wonderful, thank you. Let's begin. {first['question']}")
            print(f"✅ [{bot_id[:8]}] Consent received — interview starting ({len(sess.questions)} Qs)")
        else:
            background_tasks.add_task(speak, sess, "Please say yes to begin.")
        return {"status": "ok"}

    if sess.question_index < len(sess.questions):
        if is_final:
            sess.last_activity = time.time()
            if not sess.answer_buffer:
                sess.turn_start_time = time.time()
            sess.answer_buffer.append(text)
        schedule_processing(sess)
    return {"status": "ok"}

@app.get("/transcript/{bot_id}")
def get_transcript(bot_id):
    sess = get_session(bot_id)
    if not sess:
        return {"error": "no active session"}
    return {"completion_status": sess.completion_status, "session_id": sess.session_id,
            "entries": sess.transcript, "count": len(sess.transcript)}

@app.get("/bot-status/{bot_id}")
def bot_status(bot_id):
    return {"bot_id": bot_id, "status": get_bot_status(bot_id)}

@app.get("/stop-bot/{bot_id}")
def stop_bot(bot_id):
    sess = get_session(bot_id)
    if sess:
        sess.interview_over = True
        save_transcript(sess)
        db.close_session(sess.session_id, "stopped", sess.question_index + 1)
        with _registry_lock:
            SESSIONS.pop(bot_id, None)
    leave_call(bot_id)
    return {"status": "stopped"}

if __name__ == "__main__":
    print("\n" + "="*55)
    print(f"  PER-SESSION engine | concurrent interviews | dynamic questions")
    print(f"  fallback {len(STATIC_QUESTIONS)} static Qs | {FOLLOWUPS_PER_Q} follow-up/Q | DB on")
    print("="*55 + "\n")
    uvicorn.run("app_full:app", host="0.0.0.0", port=8000, reload=True)