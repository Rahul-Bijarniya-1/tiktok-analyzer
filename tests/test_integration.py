import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
import pandas as pd
from pathlib import Path

from src.scraper.tiktok_scraper import TikTokScraper
from src.analyzer.age_gender_predictor import OptimizedMiVOLOAnalyzer
from run import TikTokAnalyzerApp

class TestIntegration(unittest.TestCase):
    """Integration tests for the TikTok Analyzer"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.input_dir = Path(self.temp_dir) / "input"
        self.output_dir = Path(self.temp_dir) / "output"
        self.model_dir = Path(self.temp_dir) / "models"
        
        # Create directories
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
        self.model_dir.mkdir(exist_ok=True)
        
        # Create test input file
        self.create_test_input_file()
        
        # Set up environment variables
        self.original_env = os.environ.copy()
        os.environ["APIFY_API_KEY"] = "test_api_key"
        os.environ["AWS_REGION"] = "us-east-1"
        os.environ["S3_BUCKET"] = "test-bucket"
        
        # Patch for models directory
        self.patcher1 = patch('src.analyzer.age_gender_predictor.MODEL_DIR', new=self.model_dir)
        self.patcher2 = patch('config.settings.MODEL_DIR', new=self.model_dir)
        self.patcher3 = patch('config.settings.INPUT_DIR', new=self.input_dir)
        self.patcher4 = patch('config.settings.OUTPUT_DIR', new=self.output_dir)
        
        self.patcher1.start()
        self.patcher2.start()
        self.patcher3.start()
        self.patcher4.start()
    
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Restore environment variables
        os.environ.clear()
        os.environ.update(self.original_env)
        
        # Stop patchers
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        self.patcher4.stop()
    
    def create_test_input_file(self):
        """Create a test input CSV file with usernames"""
        test_data = {
            'username': ['test_user1', 'test_user2', 'test_user3']
        }
        df = pd.DataFrame(test_data)
        input_file = self.input_dir / "test_usernames.csv"
        df.to_csv(input_file, index=False)
    
    @patch('src.scraper.tiktok_scraper.TikTokScraper.scrape_user_thumbnails')
    @patch('src.analyzer.age_gender_predictor.OptimizedMiVOLOAnalyzer.process_thumbnails')
    @patch('src.analyzer.age_gender_predictor.download_with_gdown')
    @patch('src.analyzer.age_gender_predictor.OptimizedMiVOLOAnalyzer._initialize_models')
    def test_end_to_end_local(self, mock_init_models, mock_download, mock_process_thumbnails, mock_scrape):
        """Test the end-to-end process locally"""
        # Mock successful downloads
        mock_download.return_value = True
        
        # Create fake model files
        with open(self.model_dir / "yolov8x_person_face.pt", 'wb') as f:
            f.write(b'dummy model data')
        with open(self.model_dir / "mivolo_d1.pth.tar", 'wb') as f:
            f.write(b'dummy model data')
        
        # Mock the scraper to return thumbnail paths
        def mock_scrape_side_effect(username, limit=10):
            user_dir = self.input_dir / username
            user_dir.mkdir(exist_ok=True, parents=True)
            paths = [user_dir / f"thumbnail_{i}.jpg" for i in range(1, 4)]
            for path in paths:
                # Create empty file
                with open(path, 'wb') as f:
                    f.write(b'test image data')
            return paths
        
        mock_scrape.side_effect = mock_scrape_side_effect
        
        # Mock the analyzer to return age and gender
        def mock_process_side_effect(image_paths, username):
            age = 25.5
            gender = 'female'
            return age, gender
        
        mock_process_thumbnails.side_effect = mock_process_side_effect
        
        # Initialize the application
        app = TikTokAnalyzerApp(use_cloud=False)
        
        # Process a single username
        result = app.process_username('test_user1')
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertEqual(result['username'], 'test_user1')
        self.assertEqual(result['age'], 25.5)
        self.assertEqual(result['gender'], 'female')
        
        # Verify the output file was created
        output_file = self.output_dir / 'test_user1' / 'result.csv'
        self.assertTrue(output_file.exists())
        
        # Process file with multiple usernames
        input_file = self.input_dir / "test_usernames.csv"
        output_file = self.output_dir / "test_results.csv"
        
        results = app.process_file(input_file, output_file)
        
        # Verify results
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIn(result['username'], ['test_user1', 'test_user2', 'test_user3'])
            self.assertEqual(result['age'], 25.5)
            self.assertEqual(result['gender'], 'female')
        
        # Verify output file
        self.assertTrue(output_file.exists())
        df = pd.read_csv(output_file)
        self.assertEqual(len(df), 3)
        self.assertTrue(all(col in df.columns for col in ['username', 'age', 'gender']))
    
    @patch('src.scraper.tiktok_scraper.TikTokScraper.scrape_user_thumbnails')
    @patch('src.analyzer.age_gender_predictor.OptimizedMiVOLOAnalyzer.process_thumbnails')
    @patch('boto3.client')
    @patch('src.utils.helpers.upload_to_s3')
    @patch('src.analyzer.age_gender_predictor.download_with_gdown')
    @patch('src.analyzer.age_gender_predictor.OptimizedMiVOLOAnalyzer._initialize_models')
    def test_end_to_end_cloud(self, mock_init_models, mock_download, mock_upload, mock_boto, 
                              mock_process_thumbnails, mock_scrape):
        """Test the end-to-end process with cloud services"""
        # Mock successful downloads
        mock_download.return_value = True
        
        # Mock S3 upload
        mock_upload.return_value = True
        
        # Mock boto3 clients
        mock_s3 = MagicMock()
        mock_cloudwatch = MagicMock()
        mock_boto.side_effect = lambda service, **kwargs: {
            's3': mock_s3,
            'cloudwatch': mock_cloudwatch
        }.get(service, MagicMock())
        
        # Mock the scraper to return thumbnail paths
        mock_scrape.side_effect = lambda username, limit=10: [
            Path(f"/tmp/thumbnails/{username}/thumbnail_{i}.jpg") for i in range(1, 4)
        ]
        
        # Mock the analyzer to return age and gender
        mock_process_thumbnails.side_effect = lambda image_paths, username: (25.5, 'female')
        
        # Initialize the application with cloud mode
        app = TikTokAnalyzerApp(use_cloud=True)
        
        # Process a single username
        result = app.process_username('test_user1')
        
        # Verify the result
        self.assertIsNotNone(result)
        self.assertEqual(result['username'], 'test_user1')
        self.assertEqual(result['age'], 25.5)
        self.assertEqual(result['gender'], 'female')
        
        # Verify S3 upload was called
        mock_upload.assert_called()
        
        # Process file with multiple usernames
        input_file = self.input_dir / "test_usernames.csv"
        output_file = self.output_dir / "test_results.csv"
        
        results = app.process_file(input_file, output_file)
        
        # Verify results
        self.assertEqual(len(results), 3)
        
        # Verify CloudWatch metrics were reported
        self.assertTrue(mock_cloudwatch.put_metric_data.called)

if __name__ == "__main__":
    unittest.main()