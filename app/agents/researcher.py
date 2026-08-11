# app/agents/researcher.py
import asyncio
import logging

from langchain_tavily import TavilySearch

from app.schemas.models import Finding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tavily tool (module-level; picks up TAVILY_API_KEY from the environment
# automatically — loaded by app.config at startup).
# ---------------------------------------------------------------------------

_tavily = TavilySearch(max_results=3)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _search_subtask(subtask: str) -> list[Finding]:
    """Run a single Tavily search for *subtask* and return validated Findings.

    Results that are missing required fields are skipped with a warning rather
    than crashing the whole run.  Finding uses extra="forbid", so we build each
    instance with explicit keyword arguments — never **result unpacking —
    because Tavily's raw dicts include extra keys (score, raw_content, id, …)
    that are not part of the schema.
    """
    try:
        # ainvoke calls _arun internally; returns the same dict as invoke
        response: dict = await _tavily.ainvoke({"query": subtask})
    except Exception:
        logger.exception("Tavily search failed for subtask %r", subtask)
        return []

    findings: list[Finding] = []
    for result in response.get("results", []):
        content = result.get("content")
        url = result.get("url")
        title = result.get("title")

        if not all([content, url, title]):
            logger.warning(
                "Skipping result for subtask %r — missing required field(s): %s",
                subtask,
                {k: result.get(k) for k in ("content", "url", "title")},
            )
            continue

        findings.append(
            Finding(
                content=content,
                url=url,
                title=title,
                subtask=subtask,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def research_subtasks(plan: list[str]) -> list[Finding]:
    """Search all sub-questions in *plan* concurrently and return all Findings.

    Uses asyncio.gather so every subtask fires in parallel rather than
    sequentially.  The flattened list preserves the order of subtasks.
    """
    results: list[list[Finding]] = await asyncio.gather(
        *(_search_subtask(subtask) for subtask in plan)
    )
    # Flatten while preserving per-subtask order
    return [finding for subtask_findings in results for finding in subtask_findings]
