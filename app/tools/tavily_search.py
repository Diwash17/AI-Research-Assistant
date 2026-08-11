# app/tools/tavily_search.py
"""
Centralised Tavily search tool factory.

All Tavily configuration lives here — max_results, search_depth, API key
injection — mirroring the pattern used by app.config.get_llm() for the LLM.
Agents import `get_tavily_tool()` rather than constructing TavilySearch
directly, so search behaviour can be tuned in one place.
"""
from langchain_tavily import TavilySearch

# ---------------------------------------------------------------------------
# Configuration constants — tune here, not in agent code
# ---------------------------------------------------------------------------

TAVILY_MAX_RESULTS: int = 3
TAVILY_SEARCH_DEPTH: str = "basic"  # "basic" | "advanced" (advanced uses 2x credits)

# Lazy singleton — created on first call so import-time env loading order
# doesn't matter.  TAVILY_API_KEY is picked up automatically from the
# environment (loaded by app.config at startup via python-dotenv).
_tavily_tool: TavilySearch | None = None


def get_tavily_tool() -> TavilySearch:
    """Return the shared TavilySearch instance, creating it on first call."""
    global _tavily_tool
    if _tavily_tool is None:
        _tavily_tool = TavilySearch(
            max_results=TAVILY_MAX_RESULTS,
            search_depth=TAVILY_SEARCH_DEPTH,
        )
    return _tavily_tool
