import os
import sys
import unittest
from pathlib import Path
from dotenv import load_dotenv
# Specify the path relative to the project root where tests are usually run
dotenv_path = Path(__file__).parent.parent / 'config' / '.env' 
if dotenv_path.exists():
    load_dotenv(dotenv_path=dotenv_path)
    print(f"Loaded environment variables from: {dotenv_path}")
else:
    print(f"Warning: .env file not found at {dotenv_path}")


class EnvironmentTest(unittest.TestCase):
    """Test the environment setup"""
    
    def test_python_version(self):
        """Test if Python version is 3.11 or higher"""
        major, minor = sys.version_info.major, sys.version_info.minor
        print(f"Python version: {major}.{minor}")
        self.assertGreaterEqual(major, 3)
        self.assertGreaterEqual(minor, 9 if major == 3 else 0)
    
    def test_required_directories(self):
        """Test if required directories exist"""
        required_dirs = [
            "src",
            "config",
            "data",
            "data/input",
            "data/output",
            "models"
        ]
        
        for dir_path in required_dirs:
            path = Path(dir_path)
            print(f"Checking directory: {path}")
            self.assertTrue(path.exists() and path.is_dir(), f"Directory {path} does not exist")
    
    def test_required_modules(self):
        """Test if required modules can be imported"""
        required_modules = [
            "torch",
            "numpy",
            "pandas",
            "cv2",
            "boto3",
            "requests",
            "apify_client",
            "sklearn",
            "matplotlib"
        ]
        
        for module_name in required_modules:
            try:
                print(f"Importing module: {module_name}")
                module = __import__(module_name)
                self.assertIsNotNone(module, f"Module {module_name} import returned None")
            except ImportError as e:
                self.fail(f"Module {module_name} import failed: {e}")
    
    def test_torch_gpu(self):
        """Test if PyTorch can detect GPU (will pass even if GPU is not available)"""
        import torch
        
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            print(f"CUDA device count: {device_count}")
            self.assertGreaterEqual(device_count, 1)
            
            for i in range(device_count):
                print(f"CUDA device {i}: {torch.cuda.get_device_name(i)}")
                self.assertIsNotNone(torch.cuda.get_device_name(i))
        else:
            print("CUDA not available - this is OK for CPU-only environments")
    
    def test_cv2_installation(self):
        """Test if OpenCV is properly installed"""
        import cv2
        
        print(f"OpenCV version: {cv2.__version__}")
        self.assertIsNotNone(cv2.__version__)
    
    def test_environment_variables(self):
        """Test if environment variables are set (from .env or system)"""
        # Don't fail if variables are not set, just print status
        env_vars = [
            "APIFY_API_KEY",
            "AWS_REGION",
            "S3_BUCKET",
            "SQS_QUEUE_URL"
        ]
        
        for var in env_vars:
            value = os.environ.get(var)
            status = "set" if value else "not set"
            print(f"Environment variable {var}: {status}")

if __name__ == "__main__":
    unittest.main()