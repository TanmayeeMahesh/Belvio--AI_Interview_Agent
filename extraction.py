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
- fresher = <1 year, junior = 1–3 years, mid = 3–5 years, senior = 5+ years.
- Scan the resume text for the candidate's email address if present.

Return EXACTLY this JSON (no deviations):
{{
  "candidateName": "extracted full name or 'Candidate'",
  "candidateEmail": "extracted email or null",
  "jobRole": "the specific role title from the JD or the provided role",
  "detectedLevel": "fresher|junior|mid|senior",
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

# ─── ROLE RESOLUTION (map an arbitrary job title to a stored bank role) ──────
_ROLE_ALIASES = {
    "frontend developer": "Frontend Developer", "front end developer": "Frontend Developer",
    "front-end developer": "Frontend Developer", "frontend engineer": "Frontend Developer",
    "react developer": "Frontend Developer", "angular developer": "Frontend Developer",
    "ui developer": "Frontend Developer",
    "backend developer": "Backend Developer", "back end developer": "Backend Developer",
    "back-end developer": "Backend Developer", "backend engineer": "Backend Developer",
    "api developer": "Backend Developer", "server side developer": "Backend Developer",
    "full stack developer": "Full-Stack Developer", "fullstack developer": "Full-Stack Developer",
    "full-stack engineer": "Full-Stack Developer", "mern developer": "Full-Stack Developer",
    "web developer": "Full-Stack Developer",
    "software developer": "Software Engineer", "sde": "Software Engineer", "programmer": "Software Engineer",
    "qa engineer": "Software Engineer", "test engineer": "Software Engineer",
    "ml engineer": "Data Scientist", "machine learning engineer": "Data Scientist",
    "ai engineer": "Data Scientist", "data engineer": "Data Analyst",
    "scrum master": "Project Manager",
    "sales executive": "Sales / Business Development Executive",
    "business development executive": "Sales / Business Development Executive",
}

_ROLE_STOPWORDS = {"a", "an", "the", "of", "and", "senior", "junior", "lead", "principal",
                   "sr", "jr", "associate", "staff", "i", "ii", "iii", "engineer", "developer",
                   "specialist", "executive", "analyst", "manager"}


def list_bank_roles() -> list:
    """Canonical role names, parsed live from question_bank.md headers (## N. Name)."""
    try:
        with open("question_bank.md", "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []
    return [m.strip() for m in re.findall(r'^## \d+\.\s+(.+)$', content, flags=re.MULTILINE)]


def _role_tokens(s: str) -> set:
    return {t for t in re.split(r'[^a-z0-9]+', (s or "").lower()) if t and t not in _ROLE_STOPWORDS}


def resolve_bank_role(job_role: str):
    """Map an arbitrary job title to a stored bank role.
    Returns (canonical_role or None, method): exact → substring → alias → token-overlap."""
    roles = list_bank_roles()
    if not roles or not job_role:
        return (None, "none")
    jr = job_role.strip().lower()
    for r in roles:                                    # 1. exact
        if r.lower() == jr:
            return (r, "exact")
    for r in roles:                                    # 2. substring (either direction)
        rl = r.lower()
        if jr in rl or rl in jr:
            return (r, "substring")
    if jr in _ROLE_ALIASES and _ROLE_ALIASES[jr] in roles:   # 3. alias map
        return (_ROLE_ALIASES[jr], "alias")
    jt = _role_tokens(job_role)                        # 4. token overlap (Jaccard)
    best, best_score = None, 0.0
    for r in roles:
        rt = _role_tokens(r)
        if jt and rt:
            score = len(jt & rt) / len(jt | rt)
            if score > best_score:
                best, best_score = r, score
    if best and best_score >= 0.34:
        return (best, "nearest")
    return (None, "none")


# ─── EXPERIENCE LEVELS (4 tiers, 1:1 with the question-bank bands) ───────────
# fresher 0–1 yr | junior 1–3 yr | mid 3–5 yr | senior 5+ yr
LEVELS = ("fresher", "junior", "mid", "senior")
_LEVEL_ALIASES = {
    "fresher": "fresher", "entry": "fresher", "graduate": "fresher", "intern": "fresher",
    "junior": "junior", "jr": "junior", "associate": "junior",
    "mid": "mid", "intermediate": "mid", "middle": "mid", "mid-level": "mid", "midlevel": "mid",
    "senior": "senior", "experienced": "senior", "lead": "senior",
    "principal": "senior", "staff": "senior", "expert": "senior", "sr": "senior",
}


def _normalize_level(level: str) -> str:
    """Map any level string (incl. legacy 'intermediate'/'experienced'/'lead') to one of the
    4 canonical tiers: fresher | junior | mid | senior. Unknown/empty → 'mid'."""
    return _LEVEL_ALIASES.get(str(level or "").strip().lower(), "mid")


def parse_question_bank(job_role: str, level: str, num_questions: int) -> list:
    lvl = _normalize_level(level)
    # 1:1 map from the 4 canonical tiers to the bank's 4 experience bands.
    level_map = {
        "fresher": ["Fresher (0–1 year of experience)"],
        "junior":  ["Experienced (1–3 years of experience)"],
        "mid":     ["Experienced (3–5 years of experience)"],
        "senior":  ["Experienced (5+ years of experience)"],
    }
    target_levels = level_map.get(lvl, level_map["mid"])
    _depth = {"fresher": "surface", "junior": "medium", "mid": "medium", "senior": "deep"}[lvl]

    try:
        with open("question_bank.md", "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []

    roles = re.split(r'\n## \d+\.\s+', content)
    role_titles = [chunk.split('\n')[0].strip() for chunk in roles[1:]]

    jr = (job_role or "").strip().lower()
    best_idx = None
    for i, rt in enumerate(role_titles):               # exact match first
        if rt.lower() == jr:
            best_idx = i
            break
    if best_idx is None:                               # then substring (either direction)
        for i, rt in enumerate(role_titles):
            rl = rt.lower()
            if jr and (jr in rl or rl in jr):
                best_idx = i
                break
    if best_idx is None:
        return []          # NO silent default to the first role — caller decides the fallback

    best_role_chunk = roles[1:][best_idx]

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
                    "depth": _depth,
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

def generate_tech_questions_llm(role, level, count, analysis, jd_text="", resume_text="", keys=None) -> list:
    """Generate `count` role/level technical questions via the LLM stack — used when HR chooses
    'Generate with AI' for a role that isn't in the question bank."""
    if count <= 0:
        return []
    system = ("You are a world-class technical interviewer. Generate precise, role-appropriate "
              "technical interview questions. ALWAYS return ONLY a valid JSON array.")
    user = f"""Generate EXACTLY {count} technical interview questions for this role.

ROLE: {role}
CANDIDATE LEVEL: {level}
SKILLS FROM RESUME: {', '.join(analysis.get('skills', []) or [])}
TECH STACK: {', '.join(analysis.get('technicalStack', []) or [])}

Rules:
- Questions must be specific to the {role} role and appropriate for a {level} candidate.
- Progress from fundamentals to applied/scenario depth.
- Phrase each to be read aloud (TTS) — natural and clear.

Return ONLY a JSON array, each item EXACTLY:
[{{"question": "...", "topic": "short topic", "question_type": "technical",
   "depth": "surface|medium|deep", "target_skill": "...", "key_concepts": ["..."]}}]"""
    try:
        plan = llm_stack.call_json(system, user, job="parsing", max_tokens=2000, keys=keys)
    except llm_stack.LLMExhausted:
        raise
    except Exception as e:
        logger.error(f"generate_tech_questions_llm failed: {e}")
        return []
    if not isinstance(plan, list):
        return []
    out = []
    for q in plan[:count]:
        if isinstance(q, dict) and q.get("question"):
            out.append({
                "question": q.get("question", "").strip(),
                "topic": q.get("topic", "Technical"),
                "question_type": "technical",
                "depth": q.get("depth", "medium"),
                "target_skill": q.get("target_skill", role),
                "key_concepts": q.get("key_concepts", []) if isinstance(q.get("key_concepts"), list) else [],
            })
    return out


def _intro_pool(level: str) -> list:
    """The static intro/closing pool. [0],[1] = opening; [2],[3] = closing. Slot [2] is the
    level-aware forward-looking closer (Leadership & Growth for experienced/senior/lead).
    Single source of truth — used by both generate_question_plan and build_static_plan."""
    level = _normalize_level(level)
    is_senior_or_lead = level == "senior"
    return [
        {
            "question": "To begin, could you please introduce yourself? Feel free to walk us through your educational background, professional experience, and anything else you'd like us to know.",
            "topic": "Introduction", "question_type": "introduction", "depth": "surface",
            "target_skill": "communication", "key_concepts": ["introduction", "background"],
        },
        {
            "question": ("Could you tell us about a project you've worked on that you're particularly proud of? Please describe the problem you were solving, your specific role and contributions, the tools or technologies you used, and the final outcome or impact."
                         if level == "fresher" else
                         "Could you walk us through your core responsibilities in your most recent role, particularly highlighting a challenging problem you successfully resolved?"),
            "topic": "Projects" if level == "fresher" else "Responsibilities",
            "question_type": "behavioral", "depth": "medium",
            "target_skill": "experience", "key_concepts": ["project", "impact", "tools"],
        },
        {
            "question": ("As we near the end, I'd like to focus on leadership and growth. Could you describe a time you led a team or initiative through a difficult challenge — what you did, what you learned, and how you see your leadership scope growing over the next few years?"
                         if is_senior_or_lead else
                         "As we wrap up, where do you see yourself professionally over the next five years, and how do you feel this role would fit into that journey?"),
            "topic": "Leadership & Growth" if is_senior_or_lead else "Career Goals",
            "question_type": "closing", "depth": "medium",
            "target_skill": "leadership" if is_senior_or_lead else "motivation",
            "key_concepts": ["leadership", "growth"] if is_senior_or_lead else ["future", "goals"],
        },
        {
            "question": "Finally, do you have any questions for us — about the role, the team, the company, or anything else you'd like to know before we conclude the interview?",
            "topic": "Candidate Questions", "question_type": "closing", "depth": "surface",
            "target_skill": "curiosity", "key_concepts": ["questions"],
        },
    ]


def _build_technical(role, level, count, role_source="bank", analysis=None, jd_text="", resume_text="", keys=None) -> list:
    """The ~50% technical middle: question bank (exact role), nearest-role match, or the LLM —
    per role_source. Falls back to the first bank role so a plan is never empty."""
    if count <= 0:
        return []
    analysis = analysis or {}
    if role_source == "llm":
        tech = generate_tech_questions_llm(role, level, count, analysis, jd_text, resume_text, keys)
    else:
        canonical = role
        if role_source == "match":
            resolved, _method = resolve_bank_role(role)
            canonical = resolved or role
        tech = parse_question_bank(canonical, level, count)
    if not tech:
        fb_roles = list_bank_roles()
        fb = fb_roles[0] if fb_roles else role
        logger.warning(f"No technical questions for role '{role}' (source={role_source}) — falling back to bank '{fb}'")
        tech = parse_question_bank(fb, level, count)
    return tech


def build_static_plan(role: str, level: str, total_questions: int = 12, role_source: str = "bank",
                      analysis: dict = None, jd_text: str = "", keys: dict = None) -> dict:
    """The reusable, per-role-per-level STATIC portion (opening + technical + closing) with NO gap.
    Stored once per role card; each candidate's ~20% gap questions are merged in later via
    assemble_plan(). `gap_count` records how many gap slots to reserve for the candidate."""
    level = _normalize_level(level)
    total_questions = max(10, min(16, int(total_questions or 12)))
    intro_count = math.floor(0.3 * total_questions)
    gap_count = math.floor(0.2 * total_questions)
    pool = _intro_pool(level)
    opening_to_add = min(2, intro_count)
    closing_to_add = min(2, max(0, intro_count - opening_to_add))
    tech_count = total_questions - intro_count - gap_count   # reserve the gap slots for the candidate
    tech = _build_technical(role, level, tech_count, role_source, analysis or {}, jd_text, "", keys)
    return {
        "opening": pool[:opening_to_add],
        "technical": tech,
        "closing": pool[2:2 + closing_to_add],
        "gap_count": gap_count,
        "level": level,
        "total_questions": total_questions,
    }


def assemble_plan(static: dict, gap_questions: list = None) -> list:
    """Merge a stored static plan with this candidate's gap questions → final ordered plan:
    opening → technical → gap → closing."""
    static = static or {}
    gap_questions = gap_questions or []
    return (list(static.get("opening", []))
            + list(static.get("technical", []))
            + list(gap_questions)
            + list(static.get("closing", [])))


def generate_question_plan(analysis: dict, role: str = None, jd_text: str = "", resume_text: str = "",
                           total_questions: int = 10, role_source: str = "bank", keys: dict = None) -> list:
    role = role or analysis.get("jobRole", "Software Engineer")
    level = _normalize_level(analysis.get("detectedLevel") or "fresher")

    # Central 10-16 clamp so EVERY endpoint respects the meeting-length limit (US spec).
    total_questions = max(10, min(16, int(total_questions or 10)))

    # senior (5+ yrs) gets the Leadership & Growth closing; the other 3 tiers get the
    # standard forward-looking career-goals closer.
    is_senior_or_lead = level == "senior"

    intro_count = math.floor(0.3 * total_questions)
    gap_count = math.floor(0.2 * total_questions)
    
    questions = []
    
    intro_pool = _intro_pool(level)
    
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
    
    # 3. Technical (~50% middle) — shared helper (bank / nearest-match / LLM, with fallback).
    tech_count = total_questions - (intro_count + actual_gap_count)
    questions.extend(_build_technical(role, level, tech_count, role_source, analysis, jd_text, resume_text, keys))
        
    # Append gap questions AFTER technical questions
    questions.extend(gap_questions)
        
    # 4. Closing Questions
    for i in range(closing_to_add):
        questions.append(intro_pool[2 + i])
    
    return questions