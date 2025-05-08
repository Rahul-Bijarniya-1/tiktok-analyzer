# Use a base CUDA image (e.g., CUDA 11.8 on Ubuntu 22.04)
FROM nvidia/cuda:11.8.0-base-ubuntu22.04

# Set working directory
WORKDIR /app

# Avoid interactive prompts and set Python env variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Install system dependencies including Python 3.10
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
      software-properties-common \
      python3.10 \
      python3.10-dev \
      python3.10-distutils \
      python3-pip \
      git \
      libsm6 \
      libxext6 \
      libxrender-dev \
      ffmpeg \
      curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install pip for Python 3.10
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.10

# Make python3.10 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.10 1

# Upgrade pip and install PyTorch/Torchvision compatible with Python 3.10 and CUDA 11.8
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.10 -m pip install --upgrade pip && \
    python3.10 -m pip install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cu118

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install remaining dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.10 -m pip install -r requirements.txt

# Install MiVOLO dependencies and clone repo
RUN --mount=type=cache,target=/root/.cache/pip \
    python3.10 -m pip install huggingface_hub ultralytics==8.1.0 timm==0.8.13.dev0 lapx>=0.5.2 && \
    git clone https://github.com/WildChlamydia/MiVOLO.git && \
    cd MiVOLO && python3.10 -m pip install .

# Create necessary directories
RUN mkdir -p /app/data/input /app/data/output /app/models

# Copy source code
COPY . .

# Copy the verification script
COPY docker/verify_install.py .

# Verify Python, PyTorch & CUDA using the script
RUN python3.10 --version && python3.10 docker/verify_install.py

# Default command
CMD ["python3.10", "run.py", "--mode=file", "--cloud"]