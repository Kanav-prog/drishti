# ─────────────────────────────────────────────────────────────────────────────
# DRISHTI API — Multi-Stage Production Dockerfile
# Stage 1: Build (install deps with cache mount)
# Stage 2: Runtime (minimal image, non-root, no dev deps)
#
# Build: docker build -t drishti-api .
# Run:   docker run -p 8000:8000 --env-file .env drishti-api
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: Dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools (needed for some scientific packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies (cached separately from code)
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Metadata
LABEL org.opencontainers.image.title="DRISHTI API"
LABEL org.opencontainers.image.description="India's Railway Cascade Intelligence System — Backend API"
LABEL org.opencontainers.image.source="https://github.com/404Avinash/drishti"

WORKDIR /app

# Install only runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY backend/        ./backend/
COPY scripts/        ./scripts/
COPY data/           ./data/
COPY models/         ./models/
# Cascade logic needs the graph definition
COPY frontend/public/network_graph.json ./frontend/public/network_graph.json
COPY crs_corpus.json ./
COPY requirements.txt ./

# Create non-root user (security best practice)
RUN useradd --uid 1000 --no-create-home --shell /bin/false drishti \
    && chown -R drishti:drishti /app
USER drishti

# Health check — hits the /api/health endpoint
HEALTHCHECK \
    --interval=30s \
    --timeout=10s \
    --start-period=15s \
    --retries=3 \
    CMD curl -sf http://localhost:${PORT:-8000}/api/health || exit 1

EXPOSE 8000

# Use exec form to handle signals properly (SIGTERM for graceful shutdown)
CMD python -m uvicorn backend.api.server:app \
    --host 0.0.0.0 \
    --port ${PORT:-8000} \
    --workers ${UVICORN_WORKERS:-1} \
    --log-level ${LOG_LEVEL:-info} \
    --access-log \
    --no-server-header
