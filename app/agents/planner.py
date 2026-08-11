# app/agents/planner.py
import json
import re

from app.config import get_llm

# ---------------------------------------------------------------------------
# Prompt templates (module-level constants)
# ---------------------------------------------------------------------------

PLAN_PROMPT = """\
You are a research planning assistant.

Break the following research topic into 3-5 focused sub-questions that together
would give a comprehensive understanding of the subject.

Topic: {topic}

Return ONLY a JSON array of strings — no explanation, no markdown, no extra text.
Example format:
["sub-question 1", "sub-question 2", "sub-question 3"]
"""

RETRY_PROMPT = """\
Your previous response could not be parsed as JSON.

Return ONLY a valid JSON array of strings. No markdown fences, no explanation,
no extra text whatsoever — just the raw JSON array.

Topic: {topic}
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences if present, return inner content."""
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_research(topic: str) -> list[str]:
    """Break *topic* into 3-5 focused sub-questions via the LLM.

    Returns a list of sub-question strings.  Retries once with a stricter
    prompt on JSONDecodeError; propagates the error on a second failure.
    """
    llm = get_llm()  # default temperature=0.3

    # --- first attempt ---
    response = llm.invoke(PLAN_PROMPT.format(topic=topic))
    raw = _strip_fences(response.content)

    try:
        plan: list[str] = json.loads(raw)
    except json.JSONDecodeError:
        # --- single retry with stricter instruction ---
        retry_response = llm.invoke(RETRY_PROMPT.format(topic=topic))
        retry_raw = _strip_fences(retry_response.content)
        plan = json.loads(retry_raw)  # propagate JSONDecodeError if it fails again

    return plan
