# app/main.py
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router, REPORTS_DIR

# Ensure the reports directory exists before mounting
os.makedirs(REPORTS_DIR, exist_ok=True)

app = FastAPI(
    title="AI Research Assistant",
    version="1.0.0",
    description="Multi-agent research pipeline: plan → search → dedup → write → review",
)

# Serve generated reports (markdown + PDF) as static files
# GET /reports/<filename> will stream the file directly
app.mount("/reports", StaticFiles(directory=REPORTS_DIR), name="reports")

# API routes
app.include_router(router)
