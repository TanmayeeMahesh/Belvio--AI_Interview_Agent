"""
extraction.py — US-AG-01 (parse JD + resume) and US-AG-02 (generate question plan).

Pipeline:
  1. extract_text()        — pull raw text from a PDF (pypdf, no OCR — scanned PDFs won't work)
  2. analyze_documents()   — LLM extracts candidate name/email, experience level, skills,
                             gap analysis (JD vs resume). Uses the Gemini-first parsing chain.
  3. generate_question_plan() — builds a hybrid, level-appropriate question plan:
                             ~30% intro/closing (static pool), ~50% role/level technical questions
                             from question_bank.md, ~20% candidate-specific gap questions from a
                             fine-tuned Flan-T5 (frozen encoder). Total clamped to 10-16.

analyze_documents() is routed through our llm_stack (Gemini→Claude→Groq); the gap questions come
from the local/HF-hosted fine-tuned model (see _load_gap_model).
"""
import os, logging, math
from pypdf import PdfReader
import llm_stack

logger = logging.getLogger("extraction")


# ─── 1. PDF TEXT EXTRACTION (no OCR) ──────────────────────
def extract_text(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")
    text = ""
    try:
        for page in PdfReader(file_path).pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    except Exception as e:
        raise Exception(f"Failed to parse PDF: {e}")
    return text.strip()


# ─── 2. ANALYZE JD + RESUME ───────────────────────────────
def analyze_documents(jd_text: str, resume_text: str, role: str = "Software Engineer",
                      keys: dict = None) -> dict:
    system = ("You are a senior technical recruiter with 15+ years experience. Analyse resumes and "
              "JDs with precision. ALWAYS return ONLY valid JSON — no prose, no markdown.")
    user = f"""Analyse this resume against the job description and return a structured analysis.

JOB DESCRIPTION:
{jd_text or f"Role: {role} — no JD provided"}

CANDIDATE RESUME:
{resume_text or "No resume provided"}

Rules:
- Detect experience level from years of experience, job titles, project complexity, responsibilities.
- fresher = <1 year, intermediate = 1-5 years, experienced = 5+ years.
- Scan the resume text for the candidate's email address if present.

Return EXACTLY this JSON (no deviations):
{{
  "candidateName": "extracted full name or 'Candidate'",
  "candidateEmail": "extracted email or null",
  "jobRole": "the specific role title from the JD or the provided role",
  "detectedLevel": "fresher|intermediate|experienced",
  "levelReason": "one short line (e.g. '3 years React experience')",
  "yearsExperience": 0,
  "skills": ["..."],
  "technicalStack": ["..."],
  "missingSkills": ["skills in the JD weak/absent in the resume"],
  "jdMatchScore": 0,
  "analysisSummary": "2-3 sentence briefing for the interviewer agent",
  "gapAnalysisText": "1-2 short sentences explicitly stating what key skills from the JD the candidate lacks."
}}"""
    result = llm_stack.call_json(system, user, job="parsing", max_tokens=1200, keys=keys)
    if not result:
        logger.warning("analyze_documents: parse failed, returning minimal fallback")
        return {"candidateName": "Candidate", "candidateEmail": None, "jobRole": role,
                "detectedLevel": "fresher", "levelReason": "", "yearsExperience": 0,
                "skills": [], "technicalStack": [], "missingSkills": [], "jdMatchScore": 0,
                "analysisSummary": "", "gapAnalysisText": "No significant skill gaps identified."}
    return result


# ─── 3. GENERATE DYNAMIC QUESTION PLAN (US-AG-02) ─────────
import re

_gap_model = None
_gap_tokenizer = None

# Fine-tuned Flan-T5 (frozen encoder) artifact — ~990 MB, NOT committed to git.
# Dev: load the saved dir if present. Cloud: pull once from a private HF model repo
# (set GAP_MODEL_REPO, e.g. "tanmayee2025/belvio-gap-flan-t5"); transformers caches it on disk.
_GAP_LOCAL_DIR = "flan_t5_finetuned_frozen_encoder_local_save"
_GAP_MODEL_REPO = os.getenv("GAP_MODEL_REPO", "")

# Training-time constants — the frozen encoder makes the model prompt-layout sensitive, so
# inference must reproduce these exactly (see frontend/Final_Model_Training notebook).
_GAP_MAX_INPUT_LEN = 640
_GAP_MAX_OUTPUT_LEN = 220


def _trim(text, n: int) -> str:
    text = "" if text is None else str(text)
    return text[:n]


def _gap_model_source() -> str:
    """Prefer the local saved dir (dev); else the private HF repo id (cloud)."""
    if os.path.isdir(_GAP_LOCAL_DIR):
        return _GAP_LOCAL_DIR
    return _GAP_MODEL_REPO


def _load_gap_model():
    global _gap_model, _gap_tokenizer
    if _gap_model is not None:
        return
    source = _gap_model_source()
    if not source:
        logger.error("GAP model unavailable: no local dir and GAP_MODEL_REPO not set")
        return
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        token = os.getenv("HF_TOKEN") or None
        logger.info(f"Loading fine-tuned GAP model from: {source}")
        _gap_tokenizer = AutoTokenizer.from_pretrained(source, token=token)
        _gap_model = AutoModelForSeq2SeqLM.from_pretrained(source, token=token)
        _gap_model.eval()
        logger.info("GAP model loaded.")
    except Exception as e:
        logger.error(f"Failed to load GAP model from {source}: {e}")


def prewarm_gap_model():
    """Load the model in a background thread at boot so the first HR request isn't slow."""
    import threading
    threading.Thread(target=_load_gap_model, daemon=True).start()

def parse_question_bank(job_role: str, level: str, num_questions: int) -> list:
    level_map = {
        "fresher": ["Fresher (0–1 year of experience)"],
        "intermediate": ["Experienced (1–3 years of experience)", "Experienced (3–5 years of experience)"],
        "experienced": ["Experienced (5+ years of experience)"]
    }
    
    target_levels = level_map.get(level.lower(), level_map["intermediate"])
    
    try:
        with open("question_bank.md", "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []

    roles = re.split(r'\n## \d+\.\s+', content)
    
    best_role_chunk = None
    for chunk in roles[1:]:
        role_title = chunk.split('\n')[0].strip().lower()
        if job_role.lower() in role_title or role_title in job_role.lower():
            best_role_chunk = chunk
            break
            
    if not best_role_chunk:
        best_role_chunk = roles[1] if len(roles) > 1 else ""

    categories = re.split(r'\n###\s+', best_role_chunk)
    category_lists = []

    for cat_chunk in categories[1:]:
        lines = cat_chunk.split('\n')
        topic = lines[0].strip()
        
        current_level_match = False
        cat_q = []
        for line in lines[1:]:
            if line.startswith('#### '):
                level_title = line.replace('#### ', '').strip()
                current_level_match = any(t in level_title for t in target_levels)
            elif current_level_match and re.match(r'^\d+\.\s+', line):
                q_text = re.sub(r'^\d+\.\s+', '', line).strip()
                cat_q.append({
                    "question": q_text,
                    "topic": topic,
                    "question_type": "technical",
                    "depth": "medium" if level == "intermediate" else ("surface" if level == "fresher" else "deep"),
                    "target_skill": topic,
                    "key_concepts": [topic]
                })
                
        if cat_q:
            category_lists.append(cat_q)
            
    questions = []
    # Round-robin selection to mix topics evenly
    # (e.g. 1 from Core Concepts, 1 from Tools, etc. before taking a 2nd from Core Concepts)
    while True:
        added_in_round = 0
        for cat in category_lists:
            if cat and len(questions) < num_questions:
                questions.append(cat.pop(0))
                added_in_round += 1
        if added_in_round == 0 or len(questions) >= num_questions:
            break
            
    return questions


_Q_STEMS = ("who", "what", "when", "where", "why", "how", "can", "could", "would", "do",
            "does", "did", "have", "has", "tell", "describe", "walk", "explain", "give",
            "share", "is", "are", "which")


def _is_wellformed_question(q: str) -> bool:
    """Well-formed = long enough AND ends with '?' or opens with a question/imperative stem.
    Drops the truncated fragments the model sometimes emits (e.g. a trailing 5th item)."""
    if len(q) < 25 or len(q.split()) < 6:
        return False
    if q.rstrip().endswith("?"):
        return True
    return q.split()[0].lower().strip(",.:;\"'") in _Q_STEMS


def _echoes_input(q: str, *sources, chunk: int = 40) -> bool:
    """True if a >=chunk-char contiguous slice of q appears verbatim in any source text
    (the small model tends to parrot the resume/JD — we rank such questions lower)."""
    ql = " ".join(q.lower().split())
    if len(ql) < chunk:
        return False
    for src in sources:
        sl = " ".join((src or "").lower().split())
        if sl and any(ql[i:i + chunk] in sl for i in range(0, len(ql) - chunk + 1, 8)):
            return True
    return False


def generate_gap_questions(job_title: str, gap_analysis_text: str, jd_text: str, resume_text: str, num_questions: int) -> list:
    """Generate candidate-specific gap questions with the fine-tuned Flan-T5.

    The model was trained to always emit EXACTLY 5 numbered questions from a fixed prompt layout.
    We reproduce that layout verbatim, generate 5, then return the top `num_questions`.
    """
    _load_gap_model()
    if not _gap_model or not _gap_tokenizer:
        return []

    try:
        # EXACT training prompt layout — do NOT reword (frozen encoder is layout-sensitive).
        prompt = (
            "generate 5 interview questions from this gap analysis.\n"
            f"Role: {job_title}\n"
            f"Gap Analysis: {gap_analysis_text}\n"
            f"Resume: {_trim(resume_text, 1200)}\n"
            f"Job Description: {_trim(jd_text, 1200)}"
        )
        input_ids = _gap_tokenizer.encode(
            prompt, return_tensors="pt", truncation=True, max_length=_GAP_MAX_INPUT_LEN)
        output_ids = _gap_model.generate(
            input_ids,
            max_length=_GAP_MAX_OUTPUT_LEN,
            num_beams=4,
            no_repeat_ngram_size=3,
        )
        raw = _gap_tokenizer.decode(output_ids[0], skip_special_tokens=True)

        # Target format is "1) ... \n2) ... \n ... 5) ...". Split into candidate lines.
        parts = re.split(r'\n?\d\)\s*', raw)
        clean_lines = [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]

        # Quality filter: keep well-formed questions (drops truncated fragments), then rank
        # questions that DON'T just parrot the resume/JD above ones that do. The 248M model echoes
        # input text and occasionally emits fragments; this lifts the top N. HR still reviews the plan.
        wellformed = [q for q in clean_lines if _is_wellformed_question(q)] or clean_lines
        fresh = [q for q in wellformed if not _echoes_input(q, resume_text, jd_text)]
        echoy = [q for q in wellformed if _echoes_input(q, resume_text, jd_text)]
        selected = (fresh + echoy)[:num_questions]

        gap_questions = []
        for q_text in selected:
            gap_questions.append({
                "question": q_text,
                "topic": "Gap Skills",
                "question_type": "technical",
                "depth": "deep",
                "target_skill": "Missing Skills",
                "key_concepts": ["Missing Skills"]
            })
        return gap_questions
    except Exception as e:
        logger.error(f"Failed to generate gap questions: {e}")
        return []

def generate_question_plan(analysis: dict, role: str = None, jd_text: str = "", resume_text: str = "", total_questions: int = 10) -> list:
    role = role or analysis.get("jobRole", "Software Engineer")
    level = str(analysis.get("detectedLevel", "fresher") or "fresher").lower()

    # Central 10-16 clamp so EVERY endpoint respects the meeting-length limit (US spec).
    total_questions = max(10, min(16, int(total_questions or 10)))

    # "experienced" (5+ yrs) is our senior/lead tier; the upcoming HR experience-level UI may
    # also pass an explicit "senior"/"lead" — both get the Leadership & Growth closing variant.
    is_senior_or_lead = level in ("experienced", "senior", "lead")

    intro_count = math.floor(0.3 * total_questions)
    gap_count = math.floor(0.2 * total_questions)
    
    questions = []
    
    intro_pool = [
        {
            "question": "To begin, could you please introduce yourself? Feel free to walk us through your educational background, professional experience, and anything else you'd like us to know.",
            "topic": "Introduction",
            "question_type": "introduction",
            "depth": "surface",
            "target_skill": "communication",
            "key_concepts": ["introduction", "background"]
        },
        {
            "question": "Could you tell us about a project you've worked on that you're particularly proud of? Please describe the problem you were solving, your specific role and contributions, the tools or technologies you used, and the final outcome or impact." if level == "fresher" else "Could you walk us through your core responsibilities in your most recent role, particularly highlighting a challenging problem you successfully resolved?",
            "topic": "Projects" if level == "fresher" else "Responsibilities",
            "question_type": "behavioral",
            "depth": "medium",
            "target_skill": "experience",
            "key_concepts": ["project", "impact", "tools"]
        },
        {
            "question": (
                "As we near the end, I'd like to focus on leadership and growth. Could you describe a time you "
                "led a team or initiative through a difficult challenge — what you did, what you learned, and how "
                "you see your leadership scope growing over the next few years?"
                if is_senior_or_lead else
                "As we wrap up, where do you see yourself professionally over the next five years, and how do you feel this role would fit into that journey?"
            ),
            "topic": "Leadership & Growth" if is_senior_or_lead else "Career Goals",
            "question_type": "closing",
            "depth": "medium",
            "target_skill": "leadership" if is_senior_or_lead else "motivation",
            "key_concepts": ["leadership", "growth"] if is_senior_or_lead else ["future", "goals"]
        },
        {
            "question": "Finally, do you have any questions for us — about the role, the team, the company, or anything else you'd like to know before we conclude the interview?",
            "topic": "Candidate Questions",
            "question_type": "closing",
            "depth": "surface",
            "target_skill": "curiosity",
            "key_concepts": ["questions"]
        }
    ]
    
    # Determine how many opening vs closing questions to add from the pool
    opening_to_add = min(2, intro_count)
    closing_to_add = min(2, max(0, intro_count - opening_to_add))
    
    # 1. Opening Questions
    for i in range(opening_to_add):
        questions.append(intro_pool[i])
        
    # 2. Gap Questions (20%)
    gap_questions = []
    if jd_text and resume_text and gap_count > 0:
        gap_analysis_text = analysis.get("gapAnalysisText", "")
        if not gap_analysis_text:
            missing_skills = analysis.get("missingSkills", [])
            gap_analysis_text = f"Candidate lacks experience with {', '.join(missing_skills)}." if missing_skills else "No major skill gaps identified."
        
        gap_questions = generate_gap_questions(role, gap_analysis_text, jd_text, resume_text, gap_count)
        
    actual_gap_count = len(gap_questions)
    
    # 3. Technical Questions (Remaining questions to reach total perfectly)
    tech_count = total_questions - (intro_count + actual_gap_count)
    if tech_count > 0:
        bank_questions = parse_question_bank(role, level, tech_count)
        questions.extend(bank_questions)
        
    # Append gap questions AFTER technical questions
    questions.extend(gap_questions)
        
    # 4. Closing Questions
    for i in range(closing_to_add):
        questions.append(intro_pool[2 + i])
    
    return questions