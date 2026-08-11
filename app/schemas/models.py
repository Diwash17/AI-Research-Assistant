"""
Pydantic models and typed structures for the research agent pipeline.

Pydantic v2 is in use (pydantic==2.13.4).
- Finding is a BaseModel for structured validation of individual research results.
- ResearchState is a TypedDict — LangGraph expects TypedDict-based state schemas
  so that its reducers and graph nodes can annotate fields without Pydantic overhead.
"""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, ConfigDict


class Finding(BaseModel):
    """A single research finding retrieved by a researcher node."""

    model_config = ConfigDict(
        # Forbid extra fields so stray keys from API responses surface as errors
        # rather than being silently ignored.
        extra="forbid",
        # Produce clean JSON-serialisable output when calling .model_dump().
        populate_by_name=True,
    )

    content: str
    url: str
    title: str
    subtask: str


class ResearchState(TypedDict, total=False):
    """
    Shared state passed between LangGraph nodes throughout the pipeline.

    Using TypedDict (not BaseModel) because LangGraph's StateGraph requires a
    TypedDict-based schema so it can introspect field annotations for its
    reducer system.  total=False means every key is optional at construction
    time, which matches how LangGraph builds the initial state incrementally.

    Fields
    ------
    topic           : The research question / subject being investigated.
    plan            : Ordered list of subtask strings produced by the planner.
    raw_findings    : Unfiltered findings collected across all researcher runs.
    deduped_findings: Findings after the deduplication node has run.
    report_draft    : Markdown report text produced (and optionally revised) by
                      the writer node.
    review_feedback : Natural-language critique from the reviewer node, or None
                      if the draft was accepted without changes.
    revision_count  : How many writer→reviewer cycles have completed.
    citations       : Mapping of citation index (1-based int) to source URL,
                      populated when the writer inlines references.
    """

    topic: str
    plan: list[str]
    raw_findings: list[Finding]
    deduped_findings: list[Finding]
    report_draft: str
    review_feedback: str | None
    revision_count: int
    citations: dict[int, str]
