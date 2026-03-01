# ─────────────────────────────────────────────────────────────────────────────
# Legal Agentic PageIndex RAG — Hugging Face Spaces Docker image
#
# Architecture inside the container:
#   FastAPI backend  → http://localhost:8000  (internal only)
#   Streamlit frontend → http://0.0.0.0:7860  (exposed by HF Spaces)
#
# HF Spaces only exposes one port (7860). Streamlit runs on 7860 and calls
# the FastAPI backend on localhost:8000 internally — no external URL needed.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── System dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# ── Create non-root user (required by Hugging Face Spaces) ───────────────────
RUN useradd -m -u 1000 appuser

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy source code ──────────────────────────────────────────────────────────
COPY --chown=appuser:appuser . .

# ── Create data and log directories ──────────────────────────────────────────
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app/data /app/logs

# ── Supervisor config (manages both processes) ────────────────────────────────
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# ── Streamlit config ──────────────────────────────────────────────────────────
RUN mkdir -p /app/.streamlit
COPY .streamlit/config.toml /app/.streamlit/config.toml

# ── Switch to non-root user ───────────────────────────────────────────────────
USER appuser

# ── Expose Streamlit port (HF Spaces requirement) ────────────────────────────
EXPOSE 7860

# ── Start both services via supervisor ───────────────────────────────────────
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
