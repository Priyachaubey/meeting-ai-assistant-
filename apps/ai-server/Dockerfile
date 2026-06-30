# ═══════════════════════════════════════════════════════════════════════════
# ConvoPilot AI Server – Phase 4 Dockerfile
# Self-hosted ML engine with GPU/CPU support
# ═══════════════════════════════════════════════════════════════════════════
#
# Build args:
#   BASE_IMAGE: "nvidia/cuda:12.4.1-runtime-ubuntu22.04" for GPU
#               "python:3.12-slim" for CPU-only (default)
#
# Usage:
#   CPU:  docker build -t convopilot-ai-server .
#   GPU:  docker build --build-arg BASE_IMAGE=nvidia/cuda:12.4.1-runtime-ubuntu22.04 \
#         --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu124 \
#         -t convopilot-ai-server:gpu .
# ═══════════════════════════════════════════════════════════════════════════

ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/models/huggingface
ENV TRANSFORMERS_CACHE=/models/huggingface
ENV AI_SERVER_PORT=8001

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra tesseract-ocr-spa \
    tesseract-ocr-deu tesseract-ocr-ita tesseract-ocr-por tesseract-ocr-rus \
    tesseract-ocr-chi-sim tesseract-ocr-jpn tesseract-ocr-kor tesseract-ocr-ara \
    tesseract-ocr-hin \
    libsndfile1 ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch – torch index is configurable for CPU/GPU
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url ${TORCH_INDEX}
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Model storage volume
RUN mkdir -p /models/huggingface
VOLUME ["/models"]

# Health check (start period allows model loading)
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001

# Single worker – ML models loaded in-process
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
