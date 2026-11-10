# EduFeed / scraptool - FastAPI backend + static frontend in one container
# SnapDeploy builds this image for ARM64 and injects PORT / HOST at runtime.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8002

WORKDIR /app

# Install dependencies first so Docker can cache this layer
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Application code
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

WORKDIR /app/backend

# Educational note: SQLite lives inside the container filesystem, so data is
# reset whenever the container restarts/redeploys (see README).
EXPOSE 8002

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8002}"]
