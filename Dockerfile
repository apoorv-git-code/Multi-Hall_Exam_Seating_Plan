# syntax=docker/dockerfile:1
# Exam Seating Allocation: FastAPI backend + built React dashboard in one image.
#   docker build -t exam-seating .
#   docker run --rm -p 8000:8000 exam-seating        -> http://localhost:8000

# ---- Stage 1: build the frontend ------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: runtime (Python only, no Node) ---------------------------------------
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements-web.txt ./
RUN pip install -r requirements-web.txt

# Run as an unprivileged user.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

COPY server.py ./
COPY src/ ./src/
COPY config/ ./config/
COPY data/sample/ ./data/sample/
COPY --from=frontend /build/dist ./frontend/dist

# Tunables (see README_WEB.md). Set COOKIE_SECURE=1 when served over HTTPS.
ENV SESSION_TTL_SECONDS=7200 \
    MAX_SESSIONS=200 \
    MAX_CONCURRENT_JOBS=4 \
    COOKIE_SECURE=0

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

# IMPORTANT: exactly one worker. Sessions live in this process's memory, so several
# workers would each hold different sessions and users would randomly lose their data.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
