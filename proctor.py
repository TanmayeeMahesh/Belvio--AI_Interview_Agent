"""
proctor.py — Post-interview INTEGRITY analysis (Mode A). Fail-safe, runs in a background thread.

Two independent signals, both FLAGS FOR HUMAN REVIEW (never verdicts):
  1. TRANSCRIPT AUTHENTICITY (text, Groq) — answers that read like AI text read aloud.
  2. VIDEO (fully local, CPU-only — no cloud, candidate frames never leave the server):
       YuNet + SFace (OpenCV DNN) → face presence, 2nd person, same-person verification;
       YOLOX-Nano (onnxruntime)   → phone detection. Every strong event carries a timestamp AND an
     embedded evidence thumbnail. CV libs are imported LAZILY, so app boot never depends on them.

Design rules:
  - NEVER raises into the caller — any failure saves {assessed: false}/partial and returns.
  - Decoupled integrity_reports table (no write race with the evaluator).
  - Transcript result is saved immediately; the slower video result updates the row when ready.
"""
import os, json, time, base64, threading, requests
from groq import Groq
from dotenv import load_dotenv
import db

load_dotenv()

_PROCTOR_MODEL = "qwen/qwen3.8-27b"   # llama-3.3-70b retired on Groq; text reasoning, runs in background

# ── Local CV models (baked into the image at build time; see Dockerfile) ──
_MODELS_DIR = os.getenv("PROCTOR_MODELS_DIR", os.path.join(os.path.dirname(__file__), "models"))
_YUNET_PATH = os.path.join(_MODELS_DIR, "face_detection_yunet_2023mar.onnx")
_SFACE_PATH = os.path.join(_MODELS_DIR, "face_recognition_sface_2021dec.onnx")
_YOLOX_PATH = os.path.join(_MODELS_DIR, "yolox_nano.onnx")

# ── Video sampling / thresholds (env-tunable) ──
_FRAME_SEC   = int(os.getenv("PROCTOR_FRAME_SEC", "3"))      # face-detect sample interval (s)
_PHONE_SEC   = int(os.getenv("PROCTOR_PHONE_SEC", "6"))      # YOLOX phone-scan interval (s)
_VIDEO_WAIT  = int(os.getenv("PROCTOR_VIDEO_WAIT", "20"))    # poll attempts for the video URL (×30s)
_2P_MIN_SEC  = int(os.getenv("PROCTOR_2P_MIN_SEC", "10"))    # 2nd person must persist ≥Ns (ignore pass-by)
_DP_MIN_SEC  = int(os.getenv("PROCTOR_DP_MIN_SEC", "10"))    # different-person must persist ≥Ns
_NOFACE_MIN_SEC = int(os.getenv("PROCTOR_NOFACE_MIN_SEC", "6"))  # missing face ≥Ns → one event
_SFACE_COS   = float(os.getenv("PROCTOR_SFACE_COS", "0.363"))    # SFace cosine same-identity cutoff
_PHONE_CONF  = float(os.getenv("PROCTOR_PHONE_CONF", "0.35"))    # YOLOX phone confidence cutoff
_COCO_CELLPHONE = 67                                             # COCO class id for "cell phone"
_EVIDENCE_MAX = int(os.getenv("PROCTOR_EVIDENCE_MAX", "6"))      # cap embedded evidence thumbnails
_THUMB_W = 320                                                   # evidence thumbnail width (px)
_CAMERA_OFF_PCT = 20                                             # face seen in <N% of frames → camera off
_video_lock = threading.Lock()   # serialize the CPU-bound scan (avoid contention on the 2-vCPU tier)

_groq = None
def _client():
    global _groq
    if _groq is None:
        _groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq


def _candidate_answers(session_id):
    """Pull the candidate's answers (paired with their question) from the transcript rows."""
    rows = db.read_answers(session_id)
    by_qid = {}
    for r in rows:
        qid = r.get("q_id")
        if not qid or qid in ("intro", "closing"):
            continue
        slot = by_qid.setdefault(qid, {"topic": r.get("topic"), "question": "", "answer": ""})
        role = r.get("role")
        text = (r.get("text") or "").strip()
        if role in ("question", "followup_question"):
            slot["question"] = text
        elif role in ("answer", "followup_answer"):
            slot["answer"] = (slot["answer"] + " " + text).strip()
    return [s for s in by_qid.values() if s.get("answer")]


def analyze_transcript_authenticity(session_id):
    """
    LLM check: does any answer read like it was copied from AI rather than spoken spontaneously?
    Returns {ai_likelihood: low|medium|high, flagged_answers: [...]}. SOFT signal for review only.
    """
    pairs = _candidate_answers(session_id)
    if not pairs:
        return {"ai_likelihood": "unknown", "flagged_answers": [], "note": "no answers to analyse"}

    transcript = "\n\n".join(
        f"TOPIC: {p['topic']}\nQ: {p['question']}\nA: {p['answer']}" for p in pairs)
    prompt = f"""You are checking whether interview answers were likely READ from AI-generated text
(e.g. ChatGPT/Gemini) rather than spoken spontaneously. Input is speech-to-text, so written formatting
is lost — judge by CONTENT PATTERNS, not formatting. This is a soft signal for human review: balance
the two errors — don't falsely accuse honest candidates, but DO surface answers with the hallmarks of
read-aloud AI text.

NOT evidence on their own (these are normal human speech):
- being articulate, fluent, confident, or using good vocabulary
- a correct answer; formal phrasing; non-native English phrasing
- absence of "um"/"uh" (speech-to-text strips those)

HALLMARKS of read-aloud AI text — weigh how MANY appear together, across answers:
- comprehensive, textbook-style coverage that cleanly names AND defines every relevant concept
- sustained essay structure in a spoken answer ("firstly… secondly…", tidy enumerated points)
- polished complete sentences with NO spontaneous-speech markers at all — no self-correction, no
  restarts, no "I think/I guess", no tangents, and no personal specifics or anecdotes
- register reads like written prose rather than conversation
- explicit AI artifacts: "as an AI language model", "here are N points/ways", "in summary,"

Scoring:
- low    = reads like real speech (some spontaneity, personal specifics, small imperfections)
- medium = one or two answers show SEVERAL hallmarks together (esp. comprehensive + zero spontaneity)
- high   = most answers show the hallmarks, OR any explicit AI artifact appears
Genuine human answers almost always carry personal specifics or small imperfections — their COMPLETE
absence across polished, textbook-comprehensive answers is the main signal. When truly balanced between
low and medium, pick medium only if spontaneity markers are entirely absent.

Only list an answer in flagged_answers if it shows the hallmarks; cite the specific pattern.

TRANSCRIPT:
{transcript}

Reply ONLY valid JSON, no markdown:
{{"ai_likelihood":"low|medium|high",
"flagged_answers":[{{"topic":"<topic>","reason":"<the specific pattern, <=12 words>"}}]}}"""
    try:
        resp = _client().chat.completions.create(
            model=_PROCTOR_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=400, temperature=0.2)
        raw = resp.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
        r = json.loads(raw)
        r.setdefault("ai_likelihood", "low")
        r.setdefault("flagged_answers", [])
        return r
    except Exception as e:
        print(f"[PROCTOR] transcript authenticity failed: {e}")
        return {"ai_likelihood": "unknown", "flagged_answers": [], "note": "analysis failed"}


# ─────────────────────────── VIDEO ANALYSIS (local CV stack) ───────────────────────────
def _fmt(sec):
    sec = max(0, int(sec))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _thumb(cv2, base64mod, frame, boxes=None):
    """Downscaled JPEG (optionally with drawn boxes) as a data: URI — embedded as HR evidence."""
    try:
        img = frame.copy()
        for (x1, y1, x2, y2, label) in (boxes or []):
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
            if label:
                cv2.putText(img, label, (x1, max(12, y1 - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        h, w = img.shape[:2]
        if w > _THUMB_W:
            img = cv2.resize(img, (_THUMB_W, int(h * _THUMB_W / w)))
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 60])
        return ("data:image/jpeg;base64," + base64mod.b64encode(buf.tobytes()).decode()) if ok else None
    except Exception:
        return None


def _yolox_input_size(sess):
    shp = sess.get_inputs()[0].shape          # e.g. [1, 3, 416, 416] (dims may be strings if dynamic)
    h = shp[2] if isinstance(shp[2], int) else 416
    w = shp[3] if isinstance(shp[3], int) else 416
    return h, w


def _yolox_phone(sess, cv2, np, frame, inp_hw):
    """YOLOX-Nano on one frame → (confidence, (x1,y1,x2,y2)) for the best 'cell phone', else (0.0, None).
    Implements the official letterbox preprocess (BGR, no normalization) + demo_postprocess grid decode."""
    ih, iw = frame.shape[:2]
    H, W = inp_hw
    r = min(H / ih, W / iw)
    nh, nw = int(round(ih * r)), int(round(iw * r))
    padded = np.full((H, W, 3), 114.0, dtype=np.float32)
    padded[:nh, :nw] = cv2.resize(frame, (nw, nh)).astype(np.float32)
    blob = np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32)   # 1,3,H,W
    out = sess.run(None, {sess.get_inputs()[0].name: blob})[0]        # 1, N, 85 (obj/cls already sigmoid)
    grids, strides = [], []
    for stride in (8, 16, 32):
        hs, ws = H // stride, W // stride
        xv, yv = np.meshgrid(np.arange(ws), np.arange(hs))
        grids.append(np.stack((xv, yv), 2).reshape(1, -1, 2))
        strides.append(np.full((1, hs * ws, 1), stride))
    grids = np.concatenate(grids, 1)
    strides = np.concatenate(strides, 1)
    box = out[..., :4].copy()
    box[..., :2] = (box[..., :2] + grids) * strides                   # decode xy
    box[..., 2:4] = np.exp(box[..., 2:4]) * strides                   # decode wh
    scores = out[0, :, 4] * out[0, :, 5 + _COCO_CELLPHONE]            # obj * P(cell phone)
    i = int(scores.argmax())
    if scores[i] < _PHONE_CONF:
        return 0.0, None
    cx, cy, bw, bh = box[0, i]
    return float(scores[i]), (int((cx - bw / 2) / r), int((cy - bh / 2) / r),
                              int((cx + bw / 2) / r), int((cy + bh / 2) / r))


def _dedupe_events(events, per_type=8, total=25):
    """Dedupe by (type, at) and cap PER TYPE so a noisy minor type can't evict significant ones."""
    seen, counts, out = set(), {}, []
    for e in events:
        key = (e.get("type"), e.get("at"))
        if key in seen:
            continue
        typ = e.get("type")
        if counts.get(typ, 0) >= per_type:
            continue
        seen.add(key)
        counts[typ] = counts.get(typ, 0) + 1
        out.append(e)
    return out[:total]


def _scan_video(cv2, np, ort, path):
    """Sample frames; run YuNet (presence/count), SFace (same-person), YOLOX-Nano (phone). Aggregate."""
    if not os.path.exists(_YUNET_PATH):
        return {"assessed": False, "note": "face model missing (models not baked in)"}
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return {"assessed": False, "note": "could not open video"}
    # OpenCV 5.x returns -1 (not 0) for unavailable properties → guard with > 0, not falsiness
    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps and fps > 0 else 25.0
    frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    frame_count = frame_count if frame_count and frame_count > 0 else 0
    duration = (frame_count / fps) if frame_count else 0
    if duration <= 0:
        cap.release()
        return {"assessed": False, "note": "empty/zero-length video"}
    ok, frame0 = cap.read()                       # read one frame to learn the frame size
    if not ok or frame0 is None:
        cap.release()
        return {"assessed": False, "note": "could not read frames"}
    fh, fw = frame0.shape[:2]

    detector = cv2.FaceDetectorYN.create(_YUNET_PATH, "", (fw, fh), 0.7, 0.3, 5000)
    recog = None                                  # SFace same-person (optional)
    if os.path.exists(_SFACE_PATH):
        try:
            recog = cv2.FaceRecognizerSF.create(_SFACE_PATH, "")
        except Exception as e:
            print(f"[PROCTOR] SFace load failed: {e}")
    yolox = yolox_hw = None                        # YOLOX phone detection (optional)
    if ort is not None and os.path.exists(_YOLOX_PATH):
        try:
            yolox = ort.InferenceSession(_YOLOX_PATH, providers=["CPUExecutionProvider"])
            yolox_hw = _yolox_input_size(yolox)
        except Exception as e:
            print(f"[PROCTOR] YOLOX load failed: {e}")

    sampled = face_frames = fails = embedded = 0
    events, centers = [], []                       # centers → head-movement hint
    ref_feat, min_sim = None, None                 # SFace enrolled feature + lowest similarity seen
    run = {"no_face": None, "second_person": None, "different_person": None}
    last_phone_t = -_PHONE_SEC
    _MIN = {"no_face": _NOFACE_MIN_SEC, "second_person": _2P_MIN_SEC, "different_person": _DP_MIN_SEC}

    def _close_run(kind, end_at):
        nonlocal embedded
        st = run[kind]
        run[kind] = None
        if not st:
            return
        dur = max(0, int(end_at - st["start"]))
        if dur >= _MIN[kind]:
            ev = {"type": kind, "at": _fmt(st["start"]), "duration_s": dur}
            if st.get("thumb") and embedded < _EVIDENCE_MAX:   # attach start-frame evidence (capped)
                ev["frame"] = st["thumb"]
                embedded += 1
            events.append(ev)

    def _open_or_extend(kind, at, frame, boxes):
        # On open, snapshot the START frame as pending evidence — attached later only if the run
        # qualifies (≥ its min duration). Guarantees every qualified event carries a frame even when
        # the sampling interval never lands past the threshold mid-run. (no_face frames aren't useful.)
        if run[kind] is None:
            thumb = _thumb(cv2, base64, frame, boxes) if (kind != "no_face" and frame is not None) else None
            run[kind] = {"start": at, "thumb": thumb}

    t = 0.0
    while t < duration:
        if t == 0.0:
            frame, at = frame0, 0.0                # reuse the frame we already read
        else:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                fails += 1
                if fails >= 3:                     # a few consecutive seek/read failures → stop
                    break
                t += _FRAME_SEC
                continue
            fails = 0
            at = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0   # actual decoded time (keyframe-accurate)
            if at <= 0:
                at = t
        sampled += 1

        detector.setInputSize((frame.shape[1], frame.shape[0]))
        _, faces = detector.detect(frame)
        faces = faces if faces is not None else []
        n_faces = len(faces)

        # ── presence / no-face run ──
        if n_faces >= 1:
            face_frames += 1
            _close_run("no_face", at)
        else:
            _open_or_extend("no_face", at, None, None)

        # ── second person (count ≥2 persisting ≥_2P_MIN_SEC → ignores pass-by) ──
        if n_faces >= 2:
            boxes = [(int(r[0]), int(r[1]), int(r[0] + r[2]), int(r[1] + r[3]), "face") for r in faces]
            _open_or_extend("second_person", at, frame, boxes)
        else:
            _close_run("second_person", at)

        # ── same-person (SFace) — ONLY on unambiguous single-face frames, so min_similarity and the
        #    different_person signal reflect the candidate (2-face frames are handled by second_person) ──
        if n_faces == 1:
            face = faces[0]
            centers.append(((float(face[0]) + float(face[2]) / 2) / frame.shape[1],
                            (float(face[1]) + float(face[3]) / 2) / frame.shape[0]))
            if recog is not None:
                try:
                    feat = recog.feature(recog.alignCrop(frame, face))
                    if ref_feat is None:
                        ref_feat = feat            # enroll from the first clean single-face frame
                        _close_run("different_person", at)
                    else:
                        sim = recog.match(ref_feat, feat, cv2.FaceRecognizerSF_FR_COSINE)
                        min_sim = sim if min_sim is None else min(min_sim, sim)
                        if sim < _SFACE_COS:
                            pb = [(int(face[0]), int(face[1]), int(face[0] + face[2]),
                                   int(face[1] + face[3]), "different")]
                            _open_or_extend("different_person", at, frame, pb)
                        else:
                            _close_run("different_person", at)
                except Exception:
                    pass                            # alignment/feature can fail on odd crops — skip frame
        else:
            _close_run("different_person", at)      # 0 or ≥2 faces → can't assert same-person here

        # ── phone (YOLOX) — periodic, plus whenever the face is missing (look-away/look-down) ──
        if yolox is not None and ((at - last_phone_t) >= _PHONE_SEC or n_faces == 0):
            last_phone_t = at
            try:
                conf, pbox = _yolox_phone(yolox, cv2, np, frame, yolox_hw)
                if pbox:
                    ev = {"type": "phone_visible", "at": _fmt(at), "confidence": round(conf, 2)}
                    if embedded < _EVIDENCE_MAX:
                        th = _thumb(cv2, base64, frame, [(*pbox, f"phone {conf:.2f}")])
                        if th:
                            ev["frame"] = th
                            embedded += 1
                    events.append(ev)
            except Exception as e:
                print(f"[PROCTOR] yolox frame failed: {e}")

        t += _FRAME_SEC

    cap.release()
    for kind in list(run.keys()):                  # flush any still-open runs at end of video
        _close_run(kind, duration)

    if sampled == 0:
        return {"assessed": False, "note": "no frames sampled"}
    face_pct = round(100 * face_frames / sampled)
    hm_score, hm_level = 0.0, "low"                 # head-movement hint (LOW-CONFIDENCE)
    if len(centers) >= 3:
        deltas = [((centers[i][0] - centers[i - 1][0]) ** 2 +
                   (centers[i][1] - centers[i - 1][1]) ** 2) ** 0.5 for i in range(1, len(centers))]
        hm_score = round(sum(deltas) / len(deltas), 3)
        hm_level = "high" if hm_score >= 0.07 else "medium" if hm_score >= 0.03 else "low"

    return {
        "assessed": True,
        "engine": "yunet+sface+yolox-nano (local, cpu)",
        "face_present_pct": face_pct,
        "camera_off": face_pct < _CAMERA_OFF_PCT,   # essentially never saw a face
        "same_person": {"checked": recog is not None, "enrolled": ref_feat is not None,
                        "min_similarity": round(min_sim, 3) if min_sim is not None else None,
                        "threshold": _SFACE_COS},
        "head_movement": {"level": hm_level, "score": hm_score},
        "phone_check": yolox is not None,
        "sampled_frames": sampled,
        "event_types": sorted({e.get("type") for e in events}),  # FULL set → flag is truncation-proof
        "events": _dedupe_events(events),                        # capped list (with thumbs) for display
    }


def analyze_video(bot_id):
    """Download the candidate's video from Recall and scan it. Fail-safe. Only the CPU-bound scan is
    serialized — the I/O (polling + download) runs OUTSIDE the lock so parallel sessions don't block on it."""
    if not bot_id:
        return {"assessed": False, "note": "no bot_id"}
    try:
        import cv2, numpy as np, tempfile   # lazy: app boot never depends on these
    except Exception as e:
        return {"assessed": False, "note": f"cv libraries unavailable: {e}"}
    try:
        import onnxruntime as ort           # optional: phone detection degrades gracefully if absent
    except Exception as e:
        ort = None
        print(f"[PROCTOR] onnxruntime unavailable (phone detection off): {e}")
    import app_full                          # lazy: avoids circular import at load time
    # poll for the video URL (I/O — outside the lock; recording takes minutes to process)
    url = None
    for _ in range(_VIDEO_WAIT):
        url = app_full.get_fresh_recording_url(bot_id, "video")
        if url:
            break
        time.sleep(30)
    if not url:
        return {"assessed": False, "note": "video recording not available"}
    # download to a temp file created atomically (I/O — outside the lock)
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
        with _video_lock:                    # serialize ONLY the CPU-bound scan (2-vCPU tier)
            return _scan_video(cv2, np, ort, path)
    except Exception as e:
        return {"assessed": False, "note": f"video analysis failed: {e}"}
    finally:
        try:
            os.remove(path)                  # data minimization: don't keep the video
        except Exception:
            pass


# ─────────────────────────── FLAG COMBINATION ───────────────────────────
_SEV = {"clean": 0, "minor": 1, "significant": 2}

def _transcript_flag(ta):
    lvl = (ta or {}).get("ai_likelihood", "low")
    return {"high": "significant", "medium": "minor"}.get(lvl, "clean")

def _video_flag(video):
    if not video or not video.get("assessed"):
        return "clean"   # not assessed adds no flag
    # prefer the full event_types set (truncation-proof); fall back to the displayed events
    vtypes = set(video.get("event_types") or [e.get("type") for e in video.get("events", [])])
    if (video.get("camera_off") or "second_person" in vtypes
            or "different_person" in vtypes or "phone_visible" in vtypes):
        return "significant"
    if "no_face" in vtypes:
        return "minor"
    return "clean"

def _combine(*flags):
    worst = max((_SEV.get(f, 0) for f in flags), default=0)
    return {0: "clean", 1: "minor", 2: "significant"}[worst]


def _summary(flag, ta, video):
    bits = []
    n = len((ta or {}).get("flagged_answers", []))
    if n:
        bits.append(f"{n} answer(s) possibly AI-assisted ({(ta or {}).get('ai_likelihood')})")
    if video and video.get("assessed"):
        vtypes = set(video.get("event_types") or [e.get("type") for e in video.get("events", [])])
        if video.get("camera_off"):
            bits.append("camera off / face rarely visible")
        if "different_person" in vtypes:
            bits.append("a different person appeared (identity mismatch)")
        if "second_person" in vtypes:
            bits.append("a second person appeared on camera")
        if "phone_visible" in vtypes:
            bits.append("a phone was visible")
        if "no_face" in vtypes and not video.get("camera_off"):
            bits.append("candidate left the frame")
    if not bits:
        if video and not video.get("assessed"):
            return "No transcript concerns. Video analysis pending or unavailable."
        return "No integrity concerns detected."
    s = "; ".join(bits)
    return s[:1].upper() + s[1:] + " — review recommended."


def analyze_session(session_id, bot_id=None):
    """
    MAIN ENTRY — runs post-interview in a daemon thread. Fail-safe: never raises.
    Saves the fast transcript result immediately, then updates the row once the slower video
    analysis (poll for URL → download → scan) completes.
    """
    # 1) transcript signal (fast) — save right away so the dashboard shows something quickly
    try:
        ta = analyze_transcript_authenticity(session_id)
    except Exception as e:
        print(f"[PROCTOR] transcript failed: {e}")
        ta = {"ai_likelihood": "unknown", "flagged_answers": []}
    ta_flag = _transcript_flag(ta)
    db.save_integrity_report(session_id, {
        "assessed": True, "integrity_flag": ta_flag,
        "transcript_authenticity": ta,
        "video": {"assessed": False, "note": "analysing video…"},
        "summary": _summary(ta_flag, ta, None),
    })
    print(f"[PROCTOR] {session_id} transcript → {ta_flag}")

    # 2) video signal (slow) — then update the row with the combined result
    try:
        video = analyze_video(bot_id)
    except Exception as e:
        print(f"[PROCTOR] video failed: {e}")
        video = {"assessed": False, "note": f"video error: {e}"}
    flag = _combine(ta_flag, _video_flag(video))
    db.save_integrity_report(session_id, {
        "assessed": True, "integrity_flag": flag,
        "transcript_authenticity": ta, "video": video,
        "summary": _summary(flag, ta, video),
    })
    print(f"[PROCTOR] {session_id} → {flag} (transcript={ta_flag}, video={_video_flag(video)})")
