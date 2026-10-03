# 1. Build the React UI
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. The FastAPI backend serves the API, the videos and the built UI (same layout as the repo: backend/ beside frontend/dist)
# bookworm = ffmpeg 5.1: ffmpeg 7 (trixie) decodes every scene input ahead of x264, ~135 MB per scene;
# a 30 s render peaked at 930 MB and was OOM-killed in the 1 GB Railway box, 5.1 peaks at 530 MB
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-noto-core && rm -rf /var/lib/apt/lists/*
# Hugging Face Spaces run as uid 1000; own the app dir so backend/out/ is writable
RUN useradd -m -u 1000 user
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN mkdir -p out && chown -R user:user /app
USER user
EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
