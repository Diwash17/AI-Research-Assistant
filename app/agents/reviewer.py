# app/agents/reviewer.py
"""
Reviewer agent — evaluates a report draft against the original research plan
and returns a structured ReviewResult.

Revision logic (enforced by the caller / workflow node):
  - revision_needed = (not result.approved) AND (result.score < REVISION_THRESHOLD)
  - Even if the report is not approved, revisions stop once score >= REVISION_THRESHOLD
    (good-enough gate) or once MAX_REVISIONS is reached (infinite-loop guard).
  - If any planned subtask is not addressed in the report, a "critical" coverage
    issue is always injected regardless of other scores.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel
from typing import Literal

from app.config import get_llm
from app.schemas.models import Finding

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_REVISIONS: int = 3          # absolute ceiling — no infinite loops
REVISION_THRESHOLD: float = 7.0 # score below this triggers a revision request
                                 # score >= this → accept even if approved=False

# ---------------------------------------------------------------------------
# Structured output contracts (LLM must return these)
# ---------------------------------------------------------------------------

class ReviewIssue(BaseModel):
    severity: Literal["critical", "major", "minor"]
    category: str          # e.g. "coverage", "citation", "clarity"
    description: str
    recommendation: str


class ReviewResult(BaseModel):
    approved: bool
    score: float                        # overall 0-10
    completeness_score: float           # 0-10  all planned subtasks addressed?
    evidence_score: float               # 0-10  claims backed by citations?
    citation_score: float               # 0-10  [N] format used correctly?
    readability_score: float            # 0-10  clear professional prose?
    factual_consistency_score: float    # 0-10  no contradictions between sources?
    issues: list[ReviewIssue]
    revision_instructions: list[str]    # actionable directives for the writer

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_REVIEW_PROMPT = """\
You are a rigorous research report reviewer. Evaluate the report below against
the original research plan and the source findings.

## Research Topic
{topic}

## Original Research Plan (subtasks that MUST be addressed)
{plan_block}

## Source Findings Used
{sources_block}

## Report Draft
{report}

---

Return ONLY valid JSON — no markdown fences, no explanation — matching this schema:

{{
  "approved": <bool>,
  "score": <float 0-10>,
  "completeness_score": <float 0-10>,
  "evidence_score": <float 0-10>,
  "citation_score": <float 0-10>,
  "readability_score": <float 0-10>,
  "factual_consistency_score": <float 0-10>,
  "issues": [
    {{
      "severity": "critical"|"major"|"minor",
      "category": "<string>",
      "description": "<string>",
      "recommendation": "<string>"
    }}
  ],
  "revision_instructions": ["<actionable instruction>", ...]
}}

Scoring guide:
- completeness_score: deduct heavily if ANY planned subtask is not addressed.
- evidence_score: every factual claim needs an inline [N] citation.
- citation_score: [N] numbers must match the References section.
- approved: set true only if score >= 8.0 and no critical issues remain.
- revision_instructions: must be empty when approved=true.
"""

_RETRY_PROMPT = """\
Your previous response was not valid JSON. Return ONLY the raw JSON object — 
no markdown, no explanation. Schema:

{{
  "approved": bool,
  "score": float,
  "completeness_score": float,
  "evidence_score": float,
  "citation_score": float,
  "readability_score": float,
  "factual_consistency_score": float,
  "issues": [{{"severity":..., "category":..., "description":..., "recommendation":...}}],
  "revision_instructions": [...]
}}
"""

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    match = _FENCE_RE.search(text)
    return match.group(1) if match else text.strip()


def _check_plan_coverage(
    plan: list[str],
    report: str,
    result: ReviewResult,
) -> ReviewResult:
    """Inject a critical issue for any planned subtask not mentioned in the report.

    This is the plan-coverage gate: even a high-scoring report must address
    every subtask the planner produced.  If any are missing, a critical issue
    is appended and scores/approved are adjusted accordingly.
    """
    missing: list[str] = []
    report_lower = report.lower()

    for subtask in plan:
        # Heuristic: check if at least a few key words from the subtask appear
        keywords = [w for w in subtask.lower().split() if len(w) > 4]
        if keywords and not any(kw in report_lower for kw in keywords):
            missing.append(subtask)

    if not missing:
        return result

    issues = list(result.issues)
    instructions = list(result.revision_instructions)

    for subtask in missing:
        issues.append(
            ReviewIssue(
                severity="critical",
                category="coverage",
                description=f"Planned subtask not addressed in the report: '{subtask}'",
                recommendation=f"Add a section or paragraph that directly answers: {subtask}",
            )
        )
        instructions.append(
            f"The report does not address the planned subtask: '{subtask}'. "
            "Add content covering this question."
        )

    # Force score down and unapprove when coverage gaps exist
    penalised_score = min(result.score, 6.0)
    penalised_completeness = min(result.completeness_score, 4.0)

    return ReviewResult(
        approved=False,
        score=penalised_score,
        completeness_score=penalised_completeness,
        evidence_score=result.evidence_score,
        citation_score=result.citation_score,
        readability_score=result.readability_score,
        factual_consistency_score=result.factual_consistency_score,
        issues=issues,
        revision_instructions=instructions,
    )


def _should_revise(result: ReviewResult, revision_count: int) -> bool:
    """Decide whether to send the report back for revision.

    Rules (all must be satisfied to trigger a revision):
    1. revision_count < MAX_REVISIONS              — infinite-loop guard
    2. not result.approved                         — reviewer not satisfied
    3. result.score < REVISION_THRESHOLD           — below good-enough gate
       (score >= REVISION_THRESHOLD → accept as-is even if not formally approved)
    """
    if revision_count >= MAX_REVISIONS:
        return False
    if result.approved:
        return False
    if result.score >= REVISION_THRESHOLD:
        return False  # good enough — stop cycling
    return True

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def review_report(
    topic: str,
    plan: list[str],
    findings: list[Finding],
    report: str,
    revision_count: int = 0,
) -> tuple[ReviewResult, bool]:
    """Evaluate *report* and decide whether it needs revision.

    Parameters
    ----------
    topic:
        Original research topic.
    plan:
        Subtask list produced by the planner — used for coverage checking.
    findings:
        Deduplicated findings used to write the report.
    report:
        Current report draft in Markdown.
    revision_count:
        How many writer→reviewer cycles have already completed.

    Returns
    -------
    result : ReviewResult
        Structured evaluation including scores, issues, and instructions.
    needs_revision : bool
        True when the workflow should send the draft back to the writer.
        Always False once MAX_REVISIONS is reached or score >= REVISION_THRESHOLD.
    """
    # Build context blocks for the prompt
    plan_block = "\n".join(f"{i+1}. {subtask}" for i, subtask in enumerate(plan))
    sources_block = "\n".join(
        f"[{i+1}] {f.title} — {f.url}" for i, f in enumerate(findings)
    )

    prompt = _REVIEW_PROMPT.format(
        topic=topic,
        plan_block=plan_block,
        sources_block=sources_block,
        report=report,
    )

    llm = get_llm(temperature=0.1)  # low temp for consistent structured output
    response = llm.invoke(prompt)
    raw = _strip_fences(response.content)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        retry_response = llm.invoke(_RETRY_PROMPT)
        data = json.loads(_strip_fences(retry_response.content))

    result = ReviewResult(**data)

    # Always run the plan-coverage gate regardless of LLM scores
    result = _check_plan_coverage(plan, report, result)

    needs_revision = _should_revise(result, revision_count)
    return result, needs_revision
