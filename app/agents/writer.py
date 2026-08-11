# app/agents/writer.py
from __future__ import annotations

from datetime import date
from urllib.parse import urlparse

from app.config import get_llm
from app.schemas.models import Finding

# ---------------------------------------------------------------------------
# Prompt templates (module-level constants)
# ---------------------------------------------------------------------------

# Used for the initial draft
_WRITE_PROMPT = """\
You are an expert research writer. Write a well-structured research report on the
topic below, drawing exclusively on the provided sources.

Topic: {topic}
Today's date: {today}

--- SOURCES ---
{sources_block}
--- END SOURCES ---

Requirements:
- Cite sources inline using [1], [2], … matching the numbered source list above.
- Every factual claim must be backed by at least one inline citation.
- Use the following section headers EXACTLY (in this order):
    ## Executive Summary
    ## Key Findings
    ## Detailed Analysis
    ## Conclusion
    ## References
- Under ## References, list each source in this APA-adapted web format:
    [N] Author/Title. (n.d.). Site Name. Retrieved {today}, from URL
  where:
    • Title   = the source title provided above
    • Site Name = the domain name inferred from the URL (e.g. "bbc.com")
    • URL     = the full source URL
- Write in clear, professional prose. Do not add sections beyond those listed.
"""

# Used when revision feedback is present — extends the base prompt
_REVISE_PROMPT = """\
You are an expert research writer. Revise the report below to address the reviewer's
feedback, keeping all content grounded in the provided sources.

Topic: {topic}
Today's date: {today}

--- SOURCES ---
{sources_block}
--- END SOURCES ---

--- REVIEWER FEEDBACK ---
{review_feedback}
--- END FEEDBACK ---

Requirements (same as before):
- Cite sources inline using [1], [2], … matching the numbered source list above.
- Every factual claim must be backed by at least one inline citation.
- Use the following section headers EXACTLY (in this order):
    ## Executive Summary
    ## Key Findings
    ## Detailed Analysis
    ## Conclusion
    ## References
- Under ## References, list each source in this APA-adapted web format:
    [N] Author/Title. (n.d.). Site Name. Retrieved {today}, from URL
  where:
    • Title   = the source title provided above
    • Site Name = the domain name inferred from the URL (e.g. "bbc.com")
    • URL     = the full source URL
- Directly address every point raised in the reviewer feedback.
- Write in clear, professional prose. Do not add sections beyond those listed.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _domain(url: str) -> str:
    """Extract bare hostname from *url*, stripping 'www.' prefix."""
    try:
        host = urlparse(url).netloc
        return host.removeprefix("www.") or url
    except Exception:
        return url


def _build_sources_block(findings: list[Finding]) -> tuple[str, dict[int, str]]:
    """Build the numbered source block for the prompt and the citations dict.

    Returns
    -------
    sources_block : str
        Human-readable numbered list of sources for the prompt.
    citations : dict[int, str]
        1-based mapping of citation number → URL.
    """
    lines: list[str] = []
    citations: dict[int, str] = {}

    for idx, finding in enumerate(findings, start=1):
        citations[idx] = finding.url
        lines.append(
            f"[{idx}] Title: {finding.title}\n"
            f"    URL: {finding.url}\n"
            f"    Content: {finding.content}"
        )

    return "\n\n".join(lines), citations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_report(
    topic: str,
    findings: list[Finding],
    review_feedback: str | None = None,
) -> tuple[str, dict[int, str]]:
    """Write (or revise) a structured research report from *findings*.

    Parameters
    ----------
    topic:
        The original research topic / question.
    findings:
        Deduplicated findings to write from.
    review_feedback:
        When provided, the LLM is asked to revise and address this feedback
        rather than produce a fresh draft.

    Returns
    -------
    report_markdown : str
        The full report in Markdown.
    citations : dict[int, str]
        Mapping of 1-based citation index → source URL.
    """
    today = date.today().strftime("%B %d, %Y")  # e.g. "August 11, 2026"
    sources_block, citations = _build_sources_block(findings)

    if review_feedback:
        prompt = _REVISE_PROMPT.format(
            topic=topic,
            today=today,
            sources_block=sources_block,
            review_feedback=review_feedback,
        )
    else:
        prompt = _WRITE_PROMPT.format(
            topic=topic,
            today=today,
            sources_block=sources_block,
        )

    llm = get_llm()  # default temperature=0.3
    response = llm.invoke(prompt)
    return response.content, citations
