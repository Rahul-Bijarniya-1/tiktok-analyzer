# Use a base CUDA image (e.g., CUDA 11.8 on Ubuntu 22.04)
# Check NVIDIA's NGC catalog or Docker Hub for the latest appropriate tags
FROM nvidia/cuda:11.8.0-base-ubuntu22.04

# Set working directory
WORKDIR /app

# Avoid interactive prompts and set Python env variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Install system dependencies including Python 3.11 and pip
# Added: software-properties-common, python3.11, python3.11-dev (for potential C extensions), python3-pip, git
# Kept: libsm6, libxext6, libxrender-dev, ffmpeg
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      software-properties-common \
      python3.11 \
      python3.11-dev \
      python3-pip \
      git \
      libsm6 \
      libxext6 \
      libxrender-dev \
      ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip for Python 3.11 and install PyTorch/Torchvision compatible with Python 3.11 and CUDA 11.8
# Check https://pytorch.org/get-started/locally/ for the latest command if needed
# Using PyTorch 2.1.2 as an example, adjust if necessary
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.11 -m pip install --no-cache-dir --upgrade pip && \
    python3.11 -m pip install --no-cache-dir \
      torch==2.1.2 \
      torchvision==0.16.2 \
      torchaudio==2.1.2 \
      --index-url https://download.pytorch.org/whl/cu118

# Copy requirements first for better layer caching
COPY requirements.txt .

# Use BuildKit cache mount to speed up pip installs for remaining dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.11 -m pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/data/input /app/data/output /app/models

# Copy source code
COPY . .

# Copy the verification script (adjust path if needed, e.g., docker/verify_install.py)
COPY docker/verify_install.py .

# Verify Python, PyTorch & CUDA using the script
RUN python3.11 --version && python3.11 docker/verify_install.py

# Default command (using python3.11)
CMD ["python3.11", "run.py", "--mode=file", "--cloud"]