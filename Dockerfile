# ── Build stage ────────────────────────────────────────────────────────────
# Use 3.11-slim: stable, well-tested with weasyprint's C extensions.
# (Local dev may run 3.14 but Docker images stick to a supported LTS release.)
FROM python:3.11-slim

# ── System dependencies ─────────────────────────────────────────────────────
# WeasyPrint needs Pango/Cairo/GDK-PixBuf for PDF rendering.
# libffi-dev is required by some cffi-based packages in requirements.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    # fontconfig is needed so WeasyPrint can find system fonts
    fontconfig \
    # clean up apt cache to keep the image small
 && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ──────────────────────────────────────────────────────
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────────────────────
# Copy everything except what .dockerignore excludes
COPY . .

# Ensure the reports directory exists inside the image
# (it will be overridden by the bind-mount in docker-compose,
#  but this prevents startup errors if run without compose)
RUN mkdir -p reports

# ── Runtime ──────────────────────────────────────────────────────────────────
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
