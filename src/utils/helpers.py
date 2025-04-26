# Utility functions for TikTok Analyzer

import os
import time
import logging
import csv
import boto3
import requests
from pathlib import Path
from botocore.exceptions import ClientError
from typing import List, Dict, Optional, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_directories(paths: List[Path]) -> None:
    """Create directories if they don't exist"""
    for path in paths:
        path.mkdir(exist_ok=True, parents=True)
        logger.debug(f"Directory created or verified: {path}")

def download_file(url: str, dest_path: Path, timeout: int = 60) -> bool:
    """Download a file from URL to destination path with retry logic"""
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading {url} to {dest_path}")
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            # Get file size for progress reporting
            total_size = int(response.headers.get('content-length', 0))
            
            # Ensure directory exists
            dest_path.parent.mkdir(exist_ok=True, parents=True)
            
            # Download with basic progress reporting
            with open(dest_path, 'wb') as f:
                downloaded = 0
                chunk_size = 8192
                
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Print progress every ~10%
                        if total_size > 0 and downloaded % (total_size // 10) < chunk_size:
                            percent = downloaded / total_size * 100
                            logger.info(f"Download progress: {percent:.1f}%")
            
            logger.info(f"Download complete: {dest_path}")
            return True
            
        except (requests.RequestException, IOError) as e:
            logger.warning(f"Download attempt {attempt+1}/{max_retries} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logger.error(f"Failed to download {url} after {max_retries} attempts")
                return False

def download_with_gdown(drive_url: str, dest_path: Path) -> bool:
    """Download a file from Google Drive using gdown"""
    try:
        import gdown
    except ImportError:
        logger.info("Installing gdown for Google Drive downloads...")
        os.system("pip install gdown -q")
        import gdown
    
    try:
        logger.info(f"Downloading from Google Drive to {dest_path}")
        dest_path.parent.mkdir(exist_ok=True, parents=True)
        gdown.download(drive_url, str(dest_path), quiet=False)
        return os.path.exists(dest_path)
    except Exception as e:
        logger.error(f"Failed to download with gdown: {str(e)}")
        return False

def upload_to_s3(file_path: Path, bucket: str, object_name: Optional[str] = None) -> bool:
    """Upload a file to an S3 bucket"""
    if object_name is None:
        object_name = file_path.name
    
    try:
        s3_client = boto3.client('s3')
        s3_client.upload_file(str(file_path), bucket, object_name)
        logger.info(f"Uploaded {file_path} to s3://{bucket}/{object_name}")
        return True
    except ClientError as e:
        logger.error(f"Error uploading to S3: {str(e)}")
        return False

def download_from_s3(bucket: str, object_name: str, file_path: Path) -> bool:
    """Download a file from an S3 bucket"""
    try:
        file_path.parent.mkdir(exist_ok=True, parents=True)
        s3_client = boto3.client('s3')
        s3_client.download_file(bucket, object_name, str(file_path))
        logger.info(f"Downloaded s3://{bucket}/{object_name} to {file_path}")
        return True
    except ClientError as e:
        logger.error(f"Error downloading from S3: {str(e)}")
        return False

def read_csv(file_path: Path, encoding: str = 'utf-8') -> List[Dict]:
    """Read a CSV file and return a list of dictionaries"""
    encodings_to_try = [encoding, 'utf-8-sig', 'latin-1', 'utf-16']
    
    for enc in encodings_to_try:
        try:
            data = []
            with open(file_path, 'r', newline='', encoding=enc) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            logger.info(f"Read {len(data)} rows from {file_path} using {enc} encoding")
            return data
        except UnicodeDecodeError:
            logger.debug(f"Failed to read {file_path} with {enc} encoding, trying next...")
        except Exception as e:
            logger.error(f"Error reading CSV: {str(e)}")
            return []
    
    logger.error(f"Failed to read {file_path} with any encoding: {encodings_to_try}")
    return []

def write_csv(data: List[Dict], file_path: Path, fieldnames: Optional[List[str]] = None, encoding: str = 'utf-8') -> bool:
    """Write a list of dictionaries to a CSV file"""
    try:
        file_path.parent.mkdir(exist_ok=True, parents=True)
        
        if not fieldnames and data:
            fieldnames = list(data[0].keys())
        
        with open(file_path, 'w', newline='', encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
            
        logger.info(f"Wrote {len(data)} rows to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing CSV: {str(e)}")
        return False

def retry_with_backoff(max_retries: int = 3, initial_delay: int = 1, 
                       max_delay: int = 60, backoff_factor: int = 2, 
                       exceptions: tuple = (Exception,)):
    """
    Decorator factory for retrying a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts.
        initial_delay: Initial delay between retries in seconds.
        max_delay: Maximum delay between retries in seconds.
        backoff_factor: Factor by which the delay increases after each retry.
        exceptions: Tuple of exception types to catch and retry on.
    """
    def decorator(func):
        """The actual decorator that takes the function."""
        def wrapper(*args, **kwargs):
            """The wrapper function that implements the retry logic."""
            delay = initial_delay
            
            for attempt in range(max_retries + 1): # +1 to include initial try
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"Function {func.__name__} failed after {attempt} attempts: {str(e)}")
                        raise
                    
                    wait_time = min(delay, max_delay)
                    logger.warning(f"Attempt {attempt+1}/{max_retries+1} failed for {func.__name__}, retrying in {wait_time}s: {str(e)}")
                    time.sleep(wait_time)
                    delay = min(delay * backoff_factor, max_delay) # Apply backoff, capped by max_delay
                    
        return wrapper
    return decorator
