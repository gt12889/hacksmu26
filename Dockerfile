# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 — build the Vite/React frontend
# ──────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 — Python runtime (FastAPI + DSP pipeline)
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

RUN apt-get update && apt-get install -y --no-install-recommends \
        libsndfile1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-backend.txt ./
RUN pip install --upgrade pip \
 && pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-backend.txt

COPY api/ ./api/
COPY pipeline/ ./pipeline/
COPY models/ ./models/
COPY data/outputs/demo/ ./data/outputs/demo/

COPY --from=frontend-build /build/dist ./frontend/dist

RUN mkdir -p data/uploads data/outputs \
 && chmod -R 777 data

EXPOSE 7860
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
