# ── Stage 1: Base with system dependencies ────────────────────────────────
FROM python:3.11-slim AS base

# Install Tesseract OCR and supporting libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Stage 2: Python dependencies ─────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Stage 3: Application code ─────────────────────────────────────────────
COPY . .

# Create non-root user for security
RUN useradd -m -u 1001 bankguard \
    && chown -R bankguard:bankguard /app
USER bankguard

# Expose ports
EXPOSE 8000 7860

# ── Start script ──────────────────────────────────────────────────────────
COPY start.sh /start.sh
USER root
RUN chmod +x /start.sh
USER bankguard

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["/start.sh"]
