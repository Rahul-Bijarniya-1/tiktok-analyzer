import os
import sys
import unittest

class EnvironmentTest(unittest.TestCase):
    def test_environment(self):
        """Test if environment is set up properly"""
        # Check Python version
        self.assertGreaterEqual(sys.version_info.major, 3)
        self.assertGreaterEqual(sys.version_info.minor, 8)
        
        # Check if required directories exist
        self.assertTrue(os.path.exists("src"))
        self.assertTrue(os.path.exists("config"))
        
        # Test if required packages can be imported
        try:
            import torch
            self.assertTrue(hasattr(torch, '__version__'))
            print(f"PyTorch version: {torch.__version__}")
            
            # Check if CUDA is available (will be false locally, but code should run)
            print(f"CUDA available: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                print(f"CUDA device: {torch.cuda.get_device_name(0)}")
        except ImportError:
            self.fail("PyTorch not installed")

if __name__ == "__main__":
    unittest.main()
