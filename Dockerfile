# skilly backend - Python FastAPI + Supabase Postgres + Gemini
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg2 and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Requirements first for cache
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and Dataset (backend expects ../Dataset/data.json)
COPY backend/ ./backend/
COPY Dataset/ ./Dataset/
# Also copy dataset lowercase fallback if exists
COPY dataset/ ./dataset/ 2>/dev/null || true

# Copy .env if present (otherwise use env vars)
COPY backend/.env ./backend/.env 2>/dev/null || true

WORKDIR /app/backend

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
