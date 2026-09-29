"""
evaluator.py — Final candidate evaluation (US-AG-07) + recommendation report (US-AG-08).
Runs ONCE at interview end, over the whole transcript read from the DB. Separate from the
live category gate — this is the rigorous, auditable scoring that produces the HR report.

Scoring (US-AG-07 AC-02): each TOPIC scored 1-10 on four dimensions:
  Technical Accuracy 40% | Depth 30% | Clarity 20% | Problem-Solving 10%
Per-topic = weighted avg of those four (AC-03). Composite = avg across topics (AC-04).
"""
import os, json
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv
import db

load_dotenv()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
EVAL_MODEL = "qwen/qwen3.8-27b"     # llama-3.3-70b retired on Groq; rigorous judge, runs in background

# Dimension weights (backend-defined, not HR-editable — US-AG-07 AC-01)
# 4 dimensions per spec; "clarity_communication" merges the old clarity + communication.
WEIGHTS = {"technical_accuracy": 0.40, "depth": 0.30, "clarity_communication": 0.20, "problem_solving": 0.10}


def _group_by_topic(answers: list) -> dict:
    """
    Group transcript rows into {topic: {question, answer, followup_q, followup_a, live_categories}}.
    Uses role to assemble the full exchange per question/topic.
    """
    topics = {}
    for row in answers:
        role = row.get("role")
        topic = row.get("topic") or "General"
        if role in ("intro", "closing") or not topic:
            continue
        t = topics.setdefault(topic, {"question": "", "answer": "", "followup_q": "",
                                      "followup_a": "", "categories": []})
        text = (row.get("text") or "").strip()
        if role == "question":
            t["question"] = text
        elif role == "answer":
            t["answer"] = text
            if row.get("category"): t["categories"].append(row["category"])
        elif role == "followup_question":
            t["followup_q"] = text
        elif role == "followup_answer":
            t["followup_a"] = text
            if row.get("category"): t["categories"].append(row["category"])
    return topics


def _calibration(level: str) -> str:
    """Level-relative scoring baseline so a strong fresher isn't judged like a weak senior."""
    lv = (level or "").strip().lower()
    if any(k in lv for k in ("fresher", "junior", "entry", "graduate", "0-2")):
        return ("Score against a 0-2 year (fresher) candidate. Reward solid fundamentals, clear "
                "thinking, and learning aptitude. Do NOT expect production-scale, deep architecture, "
                "or leadership — their absence is NOT a penalty at this level.")
    if any(k in lv for k in ("experienced", "senior", "lead", "expert", "5+")):
        return ("Score against a 5+ year (experienced) candidate. Expect depth, trade-offs, real-world "
                "scale, and leadership. Correct fundamentals ALONE are average (5-6), not strong.")
    return ("Score against a 2-5 year (intermediate) candidate. Expect hands-on implementation and "
            "practical trade-off awareness. Solid practical answers are strong; deep architecture or "
            "leadership is a bonus, not a requirement.")


def _score_topic(topic: str, block: dict, context: str = "",
                 level: str = "intermediate", key_concepts: list = None) -> dict:
    """Score ONE topic on the four dimensions with the 70B model, anchored + level-calibrated."""
    live_hint = ", ".join(block["categories"]) or "none"
    ctx_line = f"\nJD/RESUME CONTEXT: {context}" if context else ""
    concepts = ", ".join(key_concepts or []) or "(none specified)"
    lvl = level or "intermediate"
    prompt = f"""You are scoring ONE interview topic for a {lvl} candidate, producing a FINAL, auditable score.
Input is speech-to-text (no punctuation, words may be doubled or dropped, "emb" may mean "MBA") —
judge MEANING charitably, never penalize transcription noise.

LEVEL CALIBRATION ({lvl}): {_calibration(lvl)}
{ctx_line}
TOPIC: {topic}
QUESTION: {block['question']}
EXPECTED KEY CONCEPTS (the answer key): {concepts}
CANDIDATE ANSWER: {block['answer']}
FOLLOW-UP ASKED: {block['followup_q'] or '(none)'}
FOLLOW-UP ANSWER: {block['followup_a'] or '(none)'}
LIVE FIRST-PASS SIGNAL (hint only, may be wrong): {live_hint}

SCORING ANCHORS — match observed behavior to a band, do NOT default to low:
  9-10: correct + specific examples + trade-offs; DEMONSTRATES understanding, not just naming
  7-8 : correct + some specifics; solid working understanding for this level, minor gaps
  5-6 : partially correct OR correct but shallow (names concepts, light on how/why)
  3-4 : major errors, mostly vague, or buzzwords only
  1-2 : wrong, off-topic, or no real content

Score EACH dimension 1-10, anchored to the bands above and the {lvl} baseline:
  technical_accuracy — coverage of the EXPECTED KEY CONCEPTS + correctness. Driven by how many of those
                       concepts they genuinely DEMONSTRATED (not merely named): 0 demonstrated = 1-2,
                       all demonstrated with real explanation = 9-10.
  depth — specifics, examples, trade-offs vs a vague one-liner
  clarity_communication — structured, coherent, easy to follow
  problem_solving — visible reasoning / methodology

A strong answer FOR THIS LEVEL should land 7-8, not 5. Use the FULL range. Reserve 9-10 for genuinely
excellent and 1-3 for genuinely poor — do not cluster everyone in the middle or bottom.

Set "answered": false ONLY if the candidate gave essentially NO content (just "yes", "I don't know",
silence, or repeated a prior answer without addressing THIS topic). A genuine attempt with real
content — even if weak — is "answered": true.

Reply ONLY valid JSON, no markdown:
{{"technical_accuracy":<1-10>,"depth":<1-10>,"clarity_communication":<1-10>,"problem_solving":<1-10>,
"answered":<true|false>,"note":"<one sentence citing something specific they said>"}}"""
    try:
        resp = groq_client.chat.completions.create(
            model=EVAL_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=300, temperature=0.2)
        raw = resp.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        r = json.loads(raw)
        weighted = round(sum(r[k] * w for k, w in WEIGHTS.items()), 2)   # per-topic weighted (AC-03)
        r["topic_score"] = weighted
        r["topic"] = topic
        r["answered"] = bool(r.get("answered", True))
        flag = "" if r["answered"] else "  ⚠️ UNANSWERED"
        print(f"   📐 {topic}: T{r['technical_accuracy']} D{r['depth']} "
              f"CC{r['clarity_communication']} P{r['problem_solving']} → {weighted}{flag}")
        return r
    except Exception as e:
        print(f"❌ _score_topic({topic}): {e}")
        return {"topic": topic, "technical_accuracy": 5, "depth": 5, "clarity_communication": 5,
                "problem_solving": 5, "topic_score": 5.0, "answered": True,
                "note": "scoring failed — defaulted"}


def _recommendation(composite: float) -> str:
    """Map composite to the four required bands (US-AG-08 AC-03)."""
    if composite >= 8.0:   return "Strongly Recommended"
    if composite >= 6.5:   return "Recommended"
    if composite >= 5.0:   return "Needs Further Review"
    return "Not Recommended"


def _summarize(topic_scores: list, composite: float, recommendation: str,
               candidate: dict, status: str, context: str = "", level: str = "intermediate") -> dict:
    """One more LLM call to write strengths, gaps, and a justification citing the scores."""
    breakdown = "\n".join(f"- {t['topic']}: {t['topic_score']}/10 ({t.get('note','')})"
                          for t in topic_scores)
    incomplete = status != "completed"
    ctx_block = f"\nJD/RESUME CONTEXT:\n{context}\n" if context else ""
    prompt = f"""You are writing the narrative section of a hiring evaluation report. Be specific and
reference the per-topic results. Do not invent facts not in the breakdown. Judge strengths and gaps
against a {level} candidate's expected baseline — do not fault a fresher for lacking senior-level
experience, and do not over-credit a senior for only covering fundamentals.

CANDIDATE: {candidate.get('name') or 'Unknown'}  ROLE: {candidate.get('role') or 'Unspecified'}  LEVEL: {level}
OVERALL COMPOSITE: {composite}/10
RECOMMENDATION: {recommendation}
SESSION STATUS: {status}{"  (INTERVIEW INCOMPLETE — note this)" if incomplete else ""}
{ctx_block}
PER-TOPIC BREAKDOWN:
{breakdown}

Reply ONLY valid JSON, no markdown:
{{"executive_summary":"<2-3 sentence high-level TL;DR a busy recruiter can read in 10 seconds>",
"strengths":"<2-3 sentences on what was strong, citing topics>",
"gaps":"<2-3 sentences on weaknesses/gaps, citing topics>",
"justification":"<2-3 sentences explaining the recommendation, referencing specific scores>"}}"""
    try:
        resp = groq_client.chat.completions.create(
            model=EVAL_MODEL, messages=[{"role": "user", "content": prompt}],
            max_tokens=450, temperature=0.3)
        raw = resp.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        return json.loads(raw)
    except Exception as e:
        print(f"❌ _summarize(): {e}")
        return {"executive_summary": f"Composite {composite}/10 — {recommendation}.",
                "strengths": "See per-topic scores.", "gaps": "See per-topic scores.",
                "justification": f"Composite {composite}/10 → {recommendation}."}


def evaluate_session(session_id: str, status: str = "completed") -> dict:
    """
    MAIN ENTRY. Reads the transcript, scores per topic, computes composite + recommendation,
    writes the report row, and returns the report dict. Called once at interview end.
    """
    print(f"\n🧮 Evaluating session {session_id} (status={status})...")
    answers = db.read_answers(session_id)
    if not answers:
        print("⚠️ no answers to evaluate")
        return {}

    candidate = db.get_candidate_for_session(session_id)

    # Build a concise context string from the session's JD/resume analysis
    ctx = db.get_session_context(session_id)
    skills_str = ", ".join(ctx.get("key_skills") or [])[:120]
    missing_str = ", ".join(ctx.get("missing_skills") or [])[:120]
    context = ""
    if ctx:
        context = (f"Role: {ctx.get('role') or 'N/A'} | "
                   f"JD match: {ctx.get('jd_match_score') or 'N/A'}% | "
                   f"Key skills: {skills_str or 'N/A'} | "
                   f"Missing: {missing_str or 'N/A'} | "
                   f"Summary: {(ctx.get('analysis_summary') or '')[:200]}")

    # candidate level + the pre-generated key_concepts act as the level-calibrated answer key
    level = (ctx.get("detected_level") if ctx else None) or "intermediate"
    concept_map = {}
    for q in db.get_questions(session_id):
        tp = q.get("topic") or "General"
        kc = q.get("key_concepts") if isinstance(q.get("key_concepts"), list) else []
        concept_map.setdefault(tp, [])
        for c in kc:
            if c not in concept_map[tp]:
                concept_map[tp].append(c)

    topics = _group_by_topic(answers)
    # only score topics that actually got an answer row
    all_scores = [_score_topic(t, b, context, level, concept_map.get(t))
                  for t, b in topics.items() if b["answer"]]
    if not all_scores:
        print("⚠️ no answered topics")
        return {}

    # Split: genuinely-answered vs near-empty (the scorer's "answered" flag)
    answered  = [t for t in all_scores if t.get("answered", True)]
    unanswered = [t for t in all_scores if not t.get("answered", True)]
    unanswered_topics = [t["topic"] for t in unanswered]

    scored = answered or all_scores   # safety: if somehow all unanswered, fall back to all
    # Composite = average of ANSWERED topics only (AC-04, adjusted per decision)
    composite = round(sum(t["topic_score"] for t in scored) / len(scored), 2)
    recommendation = _recommendation(composite)

    narrative = _summarize(scored, composite, recommendation, candidate, status, context, level)

    # Dimension averages across ANSWERED topics (headline metrics)
    def davg(dim): return round(sum(t[dim] for t in scored) / len(scored), 2)

    gaps_text = narrative["gaps"]
    if unanswered_topics:
        gaps_text += (f" Topics with no substantive answer (excluded from the score): "
                      f"{', '.join(unanswered_topics)}.")

    rec_final = recommendation if status == "completed" else f"{recommendation} (Incomplete Session)"

    report = {
        "technical_accuracy": davg("technical_accuracy"),
        "depth": davg("depth"),
        "clarity_communication": davg("clarity_communication"),
        "problem_solving": davg("problem_solving"),
        "overall_score": composite,
        "recommendation": rec_final,
        "executive_summary": narrative.get("executive_summary", ""),
        "strengths": narrative["strengths"],
        "gaps": gaps_text,
        "justification": narrative["justification"],
        "per_topic": all_scores,   # persisted (jsonb) so the dashboard can show per-answer scores
    }
    db.save_report(session_id, report)

    full = {**report, "session_id": session_id, "candidate": candidate, "status": status,
            "scored_topics": len(scored), "unanswered_topics": unanswered_topics,
            "per_topic": all_scores, "generated_at": datetime.now().isoformat()}
    fn = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(fn, "w") as f:
        json.dump(full, f, indent=2)
    print(f"📄 Report: composite {composite}/10 (from {len(scored)} answered topics) → "
          f"{rec_final}  (saved {fn})")

    try:
        from report_pdf import build_report_pdf
        transcript_for_pdf = [
            {**a, "timestamp": str(a.get("created_at", ""))[:19].replace("T", " ")}
            for a in answers
        ]
        pdf_path = build_report_pdf(full, transcript_for_pdf)
        print(f"📄 PDF → {pdf_path}")
    except Exception as e:
        print(f"⚠️  PDF generation failed: {e}")

    return full