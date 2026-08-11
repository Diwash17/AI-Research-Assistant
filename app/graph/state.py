# app/graph/state.py
"""
LangGraph state definition for the research pipeline.

We re-export ResearchState from app.schemas.models so the graph module
has a single import point. LangGraph's StateGraph requires a TypedDict — 
ResearchState is already defined as one.
"""
from app.schemas.models import Finding, ResearchState

__all__ = ["ResearchState", "Finding"]
