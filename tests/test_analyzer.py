import os
import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
import cv2
import numpy as np
import torch
from pathlib import Path

from src.analyzer.age_gender_predictor import OptimizedMiVOLOAnalyzer

class TestOptimizedMiVOLOAnalyzer(unittest.TestCase):
    """Test the OptimizedMiVOLOAnalyzer class"""
    
    def setUp(self):
        """Set up test environment"""
        # Create temporary directory for models and images
        self.temp_dir = tempfile.mkdtemp()
        self.model_dir = Path(self.temp_dir) / "models"
        self.model_dir.mkdir(exist_ok=True)
        
        # Create test images directory
        self.images_dir = Path(self.temp_dir) / "images"
        self.images_dir.mkdir(exist_ok=True)
        
        # Create test images (blank images with simple shapes for testing)
        self.create_test_images()
        
        # Mock model paths to prevent actual downloads
        self.patcher1 = patch('src.analyzer.age_gender_predictor.YOLO_MODEL_PATH', 
                              new=self.model_dir / "yolov8x_person_face.pt")
        self.patcher2 = patch('src.analyzer.age_gender_predictor.MIVOLO_MODEL_PATH', 
                              new=self.model_dir / "mivolo_d1.pth.tar")
        self.patcher1.start()
        self.patcher2.start()
    
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
        
        # Stop patchers
        self.patcher1.stop()
        self.patcher2.stop()
    
    def create_test_images(self, count=3):
        """Create test images with faces for testing"""
        for i in range(1, count+1):
            img_path = self.images_dir / f"test_image_{i}.jpg"
            
            # Create a blank image (500x500)
            img = np.zeros((500, 500, 3), dtype=np.uint8)
            
            # Draw a face-like shape (circle)
            cv2.circle(img, (250, 250), 100, (255, 255, 255), -1)
            
            # Add eyes (two small circles)
            cv2.circle(img, (200, 220), 20, (0, 0, 0), -1)
            cv2.circle(img, (300, 220), 20, (0, 0, 0), -1)
            
            # Add mouth (curved line)
            cv2.ellipse(img, (250, 300), (60, 30), 0, 0, 180, (0, 0, 0), 5)
            
            # Save image
            cv2.imwrite(str(img_path), img)
    
    @patch('src.analyzer.age_gender_predictor.download_with_gdown')
    @patch('src.analyzer.age_gender_predictor.OptimizedMiVOLOAnalyzer._initialize_models')
    def test_init_and_setup_device(self, mock_init_models, mock_download):
        """Test initialization and device setup"""
        # Mock successful downloads
        mock_download.return_value = True
        
        # Create fake model files to prevent download attempts
        with open(self.model_dir / "yolov8x_person_face.pt", 'wb') as f:
            f.write(b'dummy model data')
        with open(self.model_dir / "mivolo_d1.pth.tar", 'wb') as f:
            f.write(b'dummy model data')
        
        # Initialize analyzer
        analyzer = OptimizedMiVOLOAnalyzer(model_dir=self.model_dir, batch_size=2)
        
        # Check device (CPU or GPU)
        expected_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.assertEqual(analyzer.device, expected_device)
        
        # Check batch size
        self.assertEqual(analyzer.batch_size, 2)
        
        # Check model directory
        self.assertEqual(analyzer.model_dir, self.model_dir)
        
        # Verify model initialization was called
        mock_init_models.assert_called_once()
    
    @patch('src.analyzer.age_gender_predictor.download_with_gdown')
    @patch('torch.cuda.is_available')
    @patch('torch.cuda.get_device_name')
    @patch('torch.cuda.get_device_properties')
    @patch('src.analyzer.age_gender_predictor.OptimizedMiVOLOAnalyzer._initialize_models')
    def test_setup_device_gpu(self, mock_init_models, mock_device_props, mock_device_name, 
                            mock_cuda_available, mock_download):
        """Test device setup with GPU"""
        # Mock successful downloads
        mock_download.return_value = True
        
        # Mock GPU availability
        mock_cuda_available.return_value = True
        
        # Mock device name and properties
        mock_device_name.return_value = "NVIDIA Test GPU"
        
        # Create a mock for device properties
        device_props_mock = MagicMock()
        device_props_mock.total_memory = 8 * 1e9  # 8GB
        mock_device_props.return_value = device_props_mock
        
        # Initialize analyzer
        analyzer = OptimizedMiVOLOAnalyzer(model_dir=self.model_dir)
        
        # Check device
        self.assertEqual(analyzer.device, torch.device("cuda"))
    
    @patch('src.analyzer.age_gender_predictor.download_with_gdown')
    @patch('torch.cuda.is_available')
    @patch('src.analyzer.age_gender_predictor.OptimizedMiVOLOAnalyzer._initialize_models')
    def test_setup_device_cpu(self, mock_init_models, mock_cuda_available, mock_download):
        """Test device setup with CPU"""
        # Mock successful downloads
        mock_download.return_value = True
        
        # Mock GPU availability
        mock_cuda_available.return_value = False
        
        # Initialize analyzer
        analyzer = OptimizedMiVOLOAnalyzer(model_dir=self.model_dir)
        
        # Check device
        self.assertEqual(analyzer.device, torch.device("cpu"))
    
    @patch('src.analyzer.age_gender_predictor.download_with_gdown')
    def test_download_models(self, mock_download):
        """Test downloading models"""
        # Mock successful downloads
        mock_download.return_value = True
        
        # Testing download_models directly is challenging due to imports,
        # so we'll just verify the method exists and calls work correctly
        mock_download.side_effect = lambda url, path: True
        
        # Create a minimal subclass to test protected method
        class TestableAnalyzer(OptimizedMiVOLOAnalyzer):
            def _initialize_models(self):
                pass  # Override to do nothing
        
        # Initialize analyzer
        analyzer = TestableAnalyzer(model_dir=self.model_dir)
        
        # Verify download_with_gdown was called twice (once for each model)
        self.assertEqual(mock_download.call_count, 2)
    
    @patch('src.analyzer.age_gender_predictor.download_with_gdown')
    @patch('src.analyzer.age_gender_predictor.OptimizedMiVOLOAnalyzer._initialize_models')
    def test_results_management(self, mock_init_models, mock_download):
        """Test results management methods"""
        # Mock successful downloads
        mock_download.return_value = True
        
        # Initialize analyzer
        analyzer = OptimizedMiVOLOAnalyzer(model_dir=self.model_dir)
        
        # Test initial empty results
        self.assertEqual(analyzer.get_results(), [])
        
        # Add some test results
        test_results = [
            {'username': 'user1', 'age': 25.5, 'gender': 'male'},
            {'username': 'user2', 'age': 32.1, 'gender': 'female'}
        ]
        analyzer.results = test_results
        
        # Test get_results
        self.assertEqual(analyzer.get_results(), test_results)
        
        # Test clear_results
        analyzer.clear_results()
        self.assertEqual(analyzer.get_results(), [])

if __name__ == "__main__":
    unittest.main()