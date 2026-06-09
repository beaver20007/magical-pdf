# Extract API — Docling + EasyOCR (CPU). Target: Render / Fly / Cloud Run.
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/data/huggingface \
    OCR_DOCS_DATA_DIR=/data

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src ./src
COPY scripts/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8765

ENTRYPOINT ["/entrypoint.sh"]
