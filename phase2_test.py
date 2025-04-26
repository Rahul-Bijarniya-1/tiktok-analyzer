import unittest
import torch
import os
from src.analyzer.age_gender_predictor import OptimizedMiVOLOAnalyzer

class GPUOptimizationTest(unittest.TestCase):
    @unittest.skipIf(not torch.cuda.is_available(), "No GPU available")
    def test_gpu_usage(self):
        """Test if the optimizer properly uses GPU"""
        analyzer = OptimizedMiVOLOAnalyzer(batch_size=4)
        
        # Verify device setting
        self.assertEqual(analyzer.device.type, "cuda")
        
        # Test if models are on correct device
        self.assertEqual(next(analyzer.age_gender_model.parameters()).device.type, "cuda")
        
        # Check if CUDA memory is being allocated
        initial_memory = torch.cuda.memory_allocated()
        # Run a simple forward pass
        # ... test code ...
        after_memory = torch.cuda.memory_allocated()
        
        # Ensure memory was used (models were loaded to GPU)
        self.assertGreater(after_memory, initial_memory)
        
    def test_batch_processing(self):
        """Test if batch processing works correctly"""
        # Create test images
        # ... test code ...
        
        analyzer = OptimizedMiVOLOAnalyzer(batch_size=2)
        analyzer.process_batch([...], "test_user")
        
        # Assert batch processing results
        # ... assertions ...

if __name__ == "__main__":
    unittest.main()
