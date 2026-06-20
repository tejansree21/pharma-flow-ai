# ─────────────────────────────────────────────────────────────────────────────
# PharmaFlow AI — API Dockerfile
# Multi-stage build: lean production image (~450MB)
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for Prophet / XGBoost / SciPy compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ cmake libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps into a prefix for clean copy
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="PharmaFlow AI" \
      version="4.0.0" \
      description="PharmaFlow AI — FastAPI backend"

WORKDIR /app

# Runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY src/ ./src/
COPY data/ ./data/
COPY models/ ./models/

# Create non-root user for security
RUN useradd -m -u 1001 pharma && chown -R pharma:pharma /app
USER pharma

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

# Production: 2 workers, no reload
CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
