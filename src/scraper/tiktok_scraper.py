# TikTok scraper functionality

import os
import logging
import requests
import time
from pathlib import Path
from typing import List, Dict, Optional, Union
from apify_client import ApifyClient

from src.utils.helpers import retry_with_backoff, download_file
from config.settings import (
    APIFY_API_KEY, 
    THUMBNAILS_PER_USER, 
    MAX_RETRIES, 
    RETRY_DELAY
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TikTokScraper:
    """Scraper class to download TikTok video thumbnails for a given username"""
    
    def __init__(self, api_key: Optional[str] = None, output_dir: Optional[Union[str, Path]] = None):
        """Initialize the TikTok scraper
        
        Args:
            api_key: Apify API key (default: from settings)
            output_dir: Directory to save thumbnails (default: "thumbnails")
        """
        self.api_key = api_key or APIFY_API_KEY
        self.output_dir = Path(output_dir) if output_dir else Path("thumbnails")
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Initialize the ApifyClient
        self.client = ApifyClient(self.api_key)
        
        logger.info(f"TikTok scraper initialized with output directory: {self.output_dir}")
    
    @retry_with_backoff(max_retries=MAX_RETRIES, initial_delay=RETRY_DELAY)
    def scrape_user_thumbnails(self, username: str, limit: int = THUMBNAILS_PER_USER) -> List[Path]:
        """Scrape thumbnails for a given TikTok username
        
        Args:
            username: TikTok username to scrape
            limit: Maximum number of thumbnails to download
        
        Returns:
            List of paths to downloaded thumbnail images
        """
        logger.info(f"Scraping thumbnails for user: {username}, limit: {limit}")
        
        # Create user-specific directory
        user_dir = self.output_dir / username
        user_dir.mkdir(exist_ok=True, parents=True)
        
        # Prepare the Actor input
        run_input = {
            "profiles": [username],
            "profileScrapeSections": ["videos"],
            "profileSorting": "latest",
            "resultsPerPage": limit,  # Request more to ensure we get enough
            "excludePinnedPosts": False,
            "shouldDownloadVideos": False,
            "shouldDownloadCovers": True,
            "shouldDownloadSubtitles": False,
            "shouldDownloadSlideshowImages": False,
            "shouldDownloadAvatars": False,
        }
        
        # Run the Apify Actor and wait for it to finish
        logger.info(f"Starting Apify Actor to scrape {username}...")
        run = self.client.actor("0FXVyOXXEmdGcV88a").call(run_input=run_input)
        
        if not run:
            logger.error(f"Apify Actor run failed for {username}")
            return []
        
        # Download thumbnails
        downloaded_paths = []
        thumbnail_count = 0
        
        # Fetch and process results from the dataset
        logger.info("Fetching results from Apify dataset...")
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            # Check if we've already downloaded enough thumbnails
            if thumbnail_count >= limit:
                break
            
            # Extract originalCoverUrl from videoMeta
            if "videoMeta" in item and "originalCoverUrl" in item["videoMeta"]:
                thumbnail_url = item["videoMeta"]["originalCoverUrl"]
                
                try:
                    logger.info(f"Downloading thumbnail {thumbnail_count+1}/{limit}...")
                    thumbnail_path = user_dir / f"thumbnail_{thumbnail_count+1}.jpg"
                    
                    # Download the thumbnail
                    success = download_file(thumbnail_url, thumbnail_path)
                    
                    if success:
                        logger.info(f"Downloaded thumbnail {thumbnail_count+1} for {username}")
                        downloaded_paths.append(thumbnail_path)
                        thumbnail_count += 1
                    else:
                        logger.warning(f"Failed to download thumbnail {thumbnail_count+1} for {username}")
                        
                except Exception as e:
                    logger.error(f"Error downloading thumbnail: {str(e)}")
        
        logger.info(f"Downloaded {len(downloaded_paths)}/{limit} thumbnails for {username}")
        return downloaded_paths
    
    def process_username_list(self, usernames: List[str], limit_per_user: int = THUMBNAILS_PER_USER) -> Dict[str, List[Path]]:
        """Process a list of usernames and download thumbnails for each
        
        Args:
            usernames: List of TikTok usernames
            limit_per_user: Maximum number of thumbnails per user
        
        Returns:
            Dictionary mapping usernames to lists of thumbnail paths
        """
        results = {}
        
        for username in usernames:
            logger.info(f"Processing username: {username}")
            thumbnails = self.scrape_user_thumbnails(username, limit_per_user)
            results[username] = thumbnails
            
            # Add a delay between users to avoid rate limiting
            if username != usernames[-1]:
                time.sleep(2)
        
        return results
