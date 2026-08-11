# app/graph/workflow.py
"""
LangGraph workflow — wires all agents into a DAG.

Pipeline flow:
    plan → research → dedup → write → review
                                 ↑         |
                                 └─────────┘  (conditional: needs_revision)
                                              exits to END when approved / threshold / max revisions
"""
from __future__ import annotations

import asyncio
import logging

from langgraph.graph import END, StateGraph

from app.agents.dedup import dedup_findings
from app.agents.planner import plan_research
from app.agents.researcher import research_subtasks
from app.agents.reviewer import MAX_REVISIONS, REVISION_THRESHOLD, review_report
from app.agents.writer import write_report
from app.graph.state import ResearchState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Node functions — each receives the full state dict and returns a partial
# update dict that LangGraph merges back into state.
# ---------------------------------------------------------------------------


def node_plan(state: ResearchState) -> dict:
    """Planner: topic → list of subtask sub-questions."""
    logger.info("[plan] topic=%r", state["topic"])
    plan = plan_research(state["topic"])
    logger.info("[plan] produced %d subtasks", len(plan))
    return {"plan": plan}


def node_research(state: ResearchState) -> dict:
    """Researcher: subtask list → raw findings (runs async searches concurrently)."""
    logger.info("[research] running %d subtasks", len(state.get("plan", [])))
    findings = asyncio.run(research_subtasks(state["plan"]))
    logger.info("[research] collected %d raw findings", len(findings))
    return {"raw_findings": findings}


def node_dedup(state: ResearchState) -> dict:
    """Dedup: raw findings → deduplicated findings via embedding similarity."""
    raw = state.get("raw_findings", [])
    logger.info("[dedup] deduplicating %d findings", len(raw))
    deduped = dedup_findings(raw)
    logger.info("[dedup] kept %d findings (dropped %d)", len(deduped), len(raw) - len(deduped))
    return {"deduped_findings": deduped}


def node_write(state: ResearchState) -> dict:
    """Writer: findings → report draft + citations dict."""
    revision_count = state.get("revision_count", 0)
    feedback = state.get("review_feedback")

    logger.info("[write] revision_count=%d, has_feedback=%s", revision_count, feedback is not None)

    report, citations = write_report(
        topic=state["topic"],
        findings=state["deduped_findings"],
        review_feedback=feedback,
    )
    logger.info("[write] report length=%d chars", len(report))
    return {
        "report_draft": report,
        "citations": citations,
        # Clear feedback after it has been consumed by the writer
        "review_feedback": None,
    }


def node_review(state: ResearchState) -> dict:
    """Reviewer: score the draft, check plan coverage, decide if revision needed."""
    revision_count = state.get("revision_count", 0)

    logger.info("[review] revision_count=%d / max=%d", revision_count, MAX_REVISIONS)

    result, needs_revision = review_report(
        topic=state["topic"],
        plan=state.get("plan", []),
        findings=state["deduped_findings"],
        report=state["report_draft"],
        revision_count=revision_count,
    )

    logger.info(
        "[review] score=%.1f approved=%s needs_revision=%s issues=%d",
        result.score,
        result.approved,
        needs_revision,
        len(result.issues),
    )

    # Build a plain-text feedback string for the writer if revision is needed
    feedback: str | None = None
    if needs_revision and result.revision_instructions:
        feedback = "\n".join(
            f"{i+1}. {instr}" for i, instr in enumerate(result.revision_instructions)
        )

    return {
        "review_feedback": feedback,
        "revision_count": revision_count + 1,
    }


# ---------------------------------------------------------------------------
# Conditional edge — routes after the review node
# ---------------------------------------------------------------------------


def route_after_review(state: ResearchState) -> str:
    """Return 'write' if another revision cycle should run, else END."""
    revision_count = state.get("revision_count", 0)
    feedback = state.get("review_feedback")

    # feedback is set only when needs_revision=True (see node_review above)
    if feedback and revision_count <= MAX_REVISIONS:
        logger.info("[route] → write (revision %d)", revision_count)
        return "write"

    logger.info("[route] → END (revision_count=%d, feedback=%s)", revision_count, feedback)
    return END


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Construct and compile the research pipeline graph."""
    graph = StateGraph(ResearchState)

    # Register nodes
    graph.add_node("plan", node_plan)
    graph.add_node("research", node_research)
    graph.add_node("dedup", node_dedup)
    graph.add_node("write", node_write)
    graph.add_node("review", node_review)

    # Linear edges
    graph.set_entry_point("plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "dedup")
    graph.add_edge("dedup", "write")
    graph.add_edge("write", "review")

    # Conditional edge: review → write (revision) or END (accept)
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {
            "write": "write",
            END: END,
        },
    )

    return graph.compile()


# Module-level compiled graph — import this in routes.py
research_graph = build_graph()
