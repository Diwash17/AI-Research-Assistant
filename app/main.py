# app/main.py
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes import router, REPORTS_DIR

STATIC_DIR = "static"

# Ensure the reports directory exists before mounting
os.makedirs(REPORTS_DIR, exist_ok=True)

app = FastAPI(
    title="AI Research Assistant",
    version="1.0.0",
    description="Multi-agent research pipeline: plan → search → dedup → write → review",
)

# Serve generated reports (markdown + PDF) as static files
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")

# API routes
app.include_router(router)

# Serve the frontend at /
@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))
