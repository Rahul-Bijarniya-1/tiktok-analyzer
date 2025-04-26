import os
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import pandas as pd # Add pandas import

from src.scraper.tiktok_scraper import TikTokScraper
from config.settings import APIFY_API_KEY

class MockResponse:
    """Mock HTTP response"""
    def __init__(self, status_code=200, content=b"test"):
        self.status_code = status_code
        self.content = content
    
    def raise_for_status(self):
        if self.status_code != 200:
            raise Exception(f"HTTP Error: {self.status_code}")

class MockDatasetItem:
    """Mock Apify dataset item"""
    def __init__(self, thumbnail_url):
        self.data = {
            "videoMeta": {
                "originalCoverUrl": thumbnail_url
            }
        }
    
    def __getitem__(self, key):
        return self.data[key]
    
    def __contains__(self, key):
        return key in self.data

class TestTikTokScraper(unittest.TestCase):
    """Test the TikTok scraper"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for thumbnails
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    @patch('src.scraper.tiktok_scraper.ApifyClient')
    def test_init(self, mock_apify_client):
        """Test initialization"""
        # Test initialization with default API key
        scraper = TikTokScraper()
        self.assertEqual(scraper.api_key, APIFY_API_KEY)
        mock_apify_client.assert_called_with(APIFY_API_KEY)
        
        # Test initialization with custom API key
        custom_key = "custom_api_key"
        scraper = TikTokScraper(api_key=custom_key)
        self.assertEqual(scraper.api_key, custom_key)
        mock_apify_client.assert_called_with(custom_key)
    
    @patch('src.scraper.tiktok_scraper.ApifyClient')
    @patch('src.scraper.tiktok_scraper.download_file')
    def test_scrape_user_thumbnails(self, mock_download, mock_apify_client):
        """Test scraping user thumbnails"""
        # Get the mock client instance returned by the patched ApifyClient constructor
        mock_client_instance = mock_apify_client.return_value

        # Configure the mock actor and its call method directly on the instance
        mock_actor = MagicMock()
        mock_client_instance.actor.return_value = mock_actor
        mock_actor.call.return_value = {"defaultDatasetId": "test_dataset_id"}

        # Configure the mock dataset directly on the instance
        mock_dataset = MagicMock()
        mock_client_instance.dataset.return_value = mock_dataset
        mock_items = [
            MockDatasetItem("https://example.com/thumbnail1.jpg"),
            MockDatasetItem("https://example.com/thumbnail2.jpg"),
            MockDatasetItem("https://example.com/thumbnail3.jpg")
        ]
        mock_dataset.iterate_items.return_value = mock_items

        # Mock download_file to succeed
        mock_download.return_value = True

        # Initialize scraper inside the test where patching is active
        # This will now use the configured mock_client_instance via the patch
        scraper = TikTokScraper(output_dir=self.temp_dir)

        # Test scraping
        username = "test_user"
        limit = 3
        thumbnails = scraper.scrape_user_thumbnails(username, limit)
        
        # Verify calls using the correct mock instance
        mock_client_instance.actor.assert_called_with("0FXVyOXXEmdGcV88a")
        mock_actor.call.assert_called_once()
        mock_client_instance.dataset.assert_called_with("test_dataset_id")
        mock_dataset.iterate_items.assert_called_once()
        
        # Verify downloads
        self.assertEqual(len(thumbnails), 3)
        self.assertEqual(mock_download.call_count, 3)
        
        # Verify thumbnail paths
        user_dir = Path(self.temp_dir) / username
        for i, path in enumerate(thumbnails, 1):
            expected_path = user_dir / f"thumbnail_{i}.jpg"
            self.assertEqual(path, expected_path)
    
    @patch('src.scraper.tiktok_scraper.TikTokScraper.scrape_user_thumbnails')
    def test_process_username_list(self, mock_scrape):
        """Test processing a list of usernames from a CSV file"""
        # Initialize scraper inside the test
        scraper = TikTokScraper(output_dir=self.temp_dir)

        # Define path to the test usernames file
        csv_path = Path(__file__).parent.parent / 'data' / 'input' / 'test_usernames.csv'
        
        # Ensure the file exists before running the test
        if not csv_path.exists():
            self.skipTest(f"Test username file not found: {csv_path}")
            
        # Read usernames from CSV
        try:
            # Try utf-16 encoding
            df = pd.read_csv(csv_path, encoding='utf-16') 
            # Assuming the column containing usernames is named 'username'
            usernames = df['username'].tolist() 
            if not usernames:
                 self.skipTest(f"No usernames found in {csv_path}")
        except Exception as e:
            self.fail(f"Failed to read or process {csv_path}: {e}")

        # Mock the scrape_user_thumbnails method
        def mock_scrape_side_effect(username, limit):
            user_dir = Path(self.temp_dir) / username
            user_dir.mkdir(exist_ok=True, parents=True)
            paths = [user_dir / f"thumbnail_{i}.jpg" for i in range(1, limit+1)]
            for path in paths:
                # Create empty file
                with open(path, 'wb') as f:
                    f.write(b'')
            return paths
        
        mock_scrape.side_effect = mock_scrape_side_effect
        
        # Test processing username list
        limit = 2 # Keep limit or adjust as needed
        results = scraper.process_username_list(usernames, limit)
        
        # Verify calls - should match the number of usernames in the file
        self.assertEqual(mock_scrape.call_count, len(usernames))
        
        # Verify results
        self.assertEqual(len(results), len(usernames))
        for username in usernames:
            self.assertIn(username, results)
            self.assertEqual(len(results[username]), limit)

if __name__ == "__main__":
    unittest.main()