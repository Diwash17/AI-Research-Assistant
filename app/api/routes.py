# app/api/routes.py
import logging
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.export.markdown_builder import _slugify, save_markdown
from app.export.pdf_exporter import markdown_to_pdf
from app.graph.workflow import research_graph

logger = logging.getLogger(__name__)

router = APIRouter()

# Directory where reports are written — must match main.py StaticFiles mount
REPORTS_DIR = "reports"


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    topic: str


class ResearchResponse(BaseModel):
    report_id: str
    markdown_url: str
    pdf_url: str
    summary: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.post("/research", response_model=ResearchResponse)
def run_research(request: ResearchRequest):
    """Run the full multi-agent research pipeline for the given topic.

    Uses a plain `def` (not `async def`) because the graph's research node
    calls asyncio.run() internally, which would raise a RuntimeError if
    invoked inside an already-running event loop (FastAPI's async context).
    """
    topic = request.topic.strip()
    if not topic:
        return JSONResponse(status_code=422, content={"detail": "topic must not be empty"})

    # --- run the pipeline ---
    try:
        state = research_graph.invoke({
            "topic": topic,
            "revision_count": 0,
        })
    except Exception as exc:
        logger.exception("Pipeline failed for topic %r", topic)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Research pipeline failed: {exc}"},
        )

    report: str = state.get("report_draft", "")

    # --- export ---
    try:
        md_path = save_markdown(report, topic, output_dir=REPORTS_DIR)
        pdf_path = markdown_to_pdf(md_path)
    except Exception as exc:
        logger.exception("Export failed for topic %r", topic)
        return JSONResponse(
            status_code=500,
            content={"detail": f"Export failed: {exc}"},
        )

    # Build URL-friendly paths (just the filename portion)
    md_filename = Path(md_path).name
    pdf_filename = Path(pdf_path).name
    slug = _slugify(topic)

    return ResearchResponse(
        report_id=slug,
        markdown_url=f"/reports/{md_filename}",
        pdf_url=f"/reports/{pdf_filename}",
        summary=report[:300].strip(),
    )
