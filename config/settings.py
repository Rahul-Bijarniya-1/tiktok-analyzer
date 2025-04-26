# Configuration settings for the TikTok Analyzer project

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
MODEL_DIR = BASE_DIR / "models"

# Create directories if they don't exist
for dir_path in [DATA_DIR, INPUT_DIR, OUTPUT_DIR, MODEL_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)

# Environment variables with defaults
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
S3_BUCKET = os.getenv("S3_BUCKET", "tiktok-analyzer-data")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "")

# GPU settings
USE_GPU = os.getenv("USE_GPU", "True").lower() in ("true", "1", "t")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "16"))

# MiVOLO model settings
YOLO_MODEL_PATH = MODEL_DIR / "yolov8x_person_face.pt"
MIVOLO_MODEL_PATH = MODEL_DIR / "mivolo_d1.pth.tar"

# URL for model downloads
YOLO_MODEL_URL = "https://drive.google.com/uc?id=1CGNCkZQNj5WkP3rLpENWAOgrBQkUWRdw"
MIVOLO_MODEL_URL = "https://drive.google.com/uc?id=11i8pKctxz3wVkDBlWKvhYIh7kpVFXSZ4"

# Scraper settings
THUMBNAILS_PER_USER = int(os.getenv("THUMBNAILS_PER_USER", "10"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))  # seconds

# Cloud settings
EC2_INSTANCE_TYPE = os.getenv("EC2_INSTANCE_TYPE", "t2.micro")
EC2_AMI_ID = os.getenv("EC2_AMI_ID", "ami-0f1dcc636b69a6438")  # Deep Learning AMI
EC2_KEY_NAME = os.getenv("EC2_KEY_NAME", "tiktok-analyzer-key")