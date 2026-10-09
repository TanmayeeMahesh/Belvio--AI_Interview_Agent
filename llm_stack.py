"""
llm_stack.py — Multi-LLM call layer with fallback chain.

Routing (per the team's decision):
  - PARSING / QUESTION-FRAMING jobs  → prefer Gemini (best at structured extraction in our testing),
    fall back to Claude, then Groq.
  - REALTIME interview jobs          → prefer Groq (fastest = lowest latency for live conversation),
    fall back to Gemini, then Claude.

Keys: read from env by default, but can be OVERRIDDEN per-user (the API-key sidebar passes a dict).
When every provider in the chain fails with a rate/quota error, we raise LLMExhausted so the UI can
prompt the user to add a fresh key.

NOTE on the "best at X" claims: these reflect OUR testing preference, not an objective benchmark.
The ROUTING (which provider first) is configurable below — adjust if your own tests disagree.
"""
import os, json, re, logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("llm_stack")


class LLMExhausted(Exception):
    """Raised when every provider in the chain failed due to rate/quota limits."""
    def __init__(self, providers_tried):
        self.providers_tried = providers_tried
        super().__init__(f"All providers exhausted: {', '.join(providers_tried)}")


def _is_rate_error(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in ("429", "quota", "rate", "resourceexhausted", "exhaust", "limit"))


def parse_json(text: str):
    """Tolerant JSON extraction from an LLM reply (strips fences, grabs first {...} or [...])."""
    try:
        text = text.replace("```json", "").replace("```", "").strip()
        m = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
        if m:
            text = m.group(1)
        return json.loads(text)
    except Exception as e:
        logger.warning(f"parse_json failed: {str(e)[:150]}")
        return None


# ─── Individual provider callers (each returns text or raises) ────────────
def _call_gemini(system: str, user: str, max_tokens: int, key: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=system)
    resp = model.generate_content(user, generation_config={"max_output_tokens": max_tokens})
    return resp.text

def _call_claude(system: str, user: str, max_tokens: int, key: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=key)
    resp = client.messages.create(
        model="claude-3-5-sonnet-20240620", max_tokens=max_tokens,
        system=system, messages=[{"role": "user", "content": user}])
    return resp.content[0].text

def _call_groq(system: str, user: str, max_tokens: int, key: str) -> str:
    from groq import Groq
    client = Groq(api_key=key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile", max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    return resp.choices[0].message.content


_PROVIDERS = {
    "gemini": (_call_gemini, "GEMINI_API_KEY"),
    "claude": (_call_claude, "ANTHROPIC_API_KEY"),
    "groq":   (_call_groq,   "GROQ_API_KEY"),
}

# Fallback chains per job type (first = preferred)
_CHAINS = {
    "parsing":  ["gemini", "claude", "groq"],   # structured extraction / question framing
    "realtime": ["groq", "gemini", "claude"],   # live interview (latency-sensitive)
}


def call(system: str, user: str, job: str = "parsing", max_tokens: int = 1500,
         keys: dict = None) -> str:
    """
    Run the fallback chain for the given job type.
    keys: optional {"gemini": "...", "claude": "...", "groq": "..."} per-user override;
          falls back to env vars when a provider's key isn't supplied.
    Raises LLMExhausted if every provider hit a rate/quota wall.
    """
    keys = keys or {}
    chain = _CHAINS.get(job, _CHAINS["parsing"])
    rate_failures = []
    last_err = None

    for provider in chain:
        fn, env_name = _PROVIDERS[provider]
        key = keys.get(provider) or os.getenv(env_name)
        if not key:
            logger.info(f"{provider}: no key, skipping")
            continue
        try:
            text = fn(system, user, max_tokens, key)
            if text and text.strip():
                logger.info(f"{provider}: ok")
                return text
        except Exception as e:
            last_err = str(e)
            if _is_rate_error(last_err):
                logger.warning(f"{provider}: rate/quota — falling back")
                rate_failures.append(provider)
            else:
                logger.warning(f"{provider}: error ({last_err[:120]}) — falling back")

    # If we got here, nothing succeeded. If ALL failures were rate-limits, signal exhaustion.
    if rate_failures and len(rate_failures) == len([p for p in chain
                                                    if (keys.get(p) or os.getenv(_PROVIDERS[p][1]))]):
        raise LLMExhausted(rate_failures)
    raise Exception(f"All providers failed. Last error: {last_err}")


def call_json(system: str, user: str, job: str = "parsing", max_tokens: int = 1500,
              keys: dict = None):
    """call() + tolerant JSON parse. Returns parsed object or None."""
    return parse_json(call(system, user, job=job, max_tokens=max_tokens, keys=keys))