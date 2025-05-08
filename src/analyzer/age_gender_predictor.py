# MiVOLO age/gender prediction

import os
import cv2
import torch
import numpy as np
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union
from collections import defaultdict, Counter
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA

# Force PyTorch to load full weights
os.environ['TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD'] = '1'

from src.utils.helpers import download_with_gdown
from config.settings import (
    MODEL_DIR, 
    YOLO_MODEL_PATH, 
    MIVOLO_MODEL_PATH, 
    YOLO_MODEL_URL, 
    MIVOLO_MODEL_URL,
    BATCH_SIZE
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OptimizedMiVOLOAnalyzer:
    """Optimized MiVOLO analyzer with batch processing for GPU efficiency"""
    
    def __init__(self, model_dir: Optional[Union[str, Path]] = None, batch_size: int = BATCH_SIZE):
        """Initialize the optimized MiVOLO analyzer
        
        Args:
            model_dir: Directory to store models (default: from settings)
            batch_size: Batch size for processing (default: from settings)
        """
        self.model_dir = Path(model_dir) if model_dir else MODEL_DIR
        self.model_dir.mkdir(exist_ok=True, parents=True)
        
        self.batch_size = batch_size
        self.results = []
        
        # Configure device
        self.device = self._setup_device()
        logger.info(f"Using device: {self.device}")
        
        # Download models
        self._download_models()
        
        # Initialize models
        self._initialize_models()
    
    def _setup_device(self) -> torch.device:
        """Set up device with proper error handling"""
        if torch.cuda.is_available():
            # Set up for the best GPU performance
            torch.backends.cudnn.benchmark = True
            device = torch.device("cuda")
            logger.info(f"GPU available: {torch.cuda.get_device_name(0)}")
            # Check memory
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(f"GPU memory: {gpu_memory:.2f} GB")
            return device
        else:
            logger.warning("CUDA not available. Using CPU instead.")
            return torch.device("cpu")
    
    def _download_models(self) -> None:
        """Download required models if they don't exist"""
        # Check and download YOLOv8 detector model
        yolo_path = self.model_dir / "yolov8x_person_face.pt"
        if not yolo_path.exists():
            logger.info("Downloading YOLOv8 face and person detector model...")
            download_success = download_with_gdown(YOLO_MODEL_URL, yolo_path)
            if not download_success:
                raise RuntimeError("Failed to download YOLOv8 model")
        
        # Check and download MiVOLO age and gender model
        mivolo_path = self.model_dir / "mivolo_d1.pth.tar"
        if not mivolo_path.exists():
            logger.info("Downloading MiVOLO age and gender model...")
            download_success = download_with_gdown(MIVOLO_MODEL_URL, mivolo_path)
            if not download_success:
                raise RuntimeError("Failed to download MiVOLO model")
        
        # Verify MiVOLO is already installed (should be from Dockerfile)
        try:
            import mivolo
            logger.info("MiVOLO package already installed")
        except ImportError:
            logger.error("MiVOLO package not found. It should have been installed during Docker build.")
            raise ImportError("MiVOLO package not installed. Please rebuild the Docker image.")
    
    def _initialize_models(self) -> None:
        """Initialize models with memory optimization"""
        try:
            # Import here to ensure dependencies are installed
            from mivolo.model.yolo_detector import Detector
            from mivolo.model.mi_volo import MiVOLO
            
            # Initialize detector with memory optimization
            self.detector = Detector(
                weights=str(self.model_dir / "yolov8x_person_face.pt"),
                device=self.device,
                verbose=False,
                conf_thresh=0.4,
                iou_thresh=0.7
            )
            
            # Initialize age_gender model with optimizations
            self.age_gender_model = MiVOLO(
                str(self.model_dir / "mivolo_d1.pth.tar"),
                device=self.device,
                half=True,  # Use FP16 for better performance
                use_persons=True,
                disable_faces=False,
                verbose=False
            )
            
            # Set model to evaluation mode for inference
            #self.detector.model.eval()
            #self.age_gender_model.eval()
            
            logger.info("Models initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing models: {str(e)}")
            raise
    
    def process_thumbnails(self, image_paths: List[Path], username: str) -> Tuple[Optional[float], Optional[str]]:
        """Process all thumbnails for a specific username and identify the content creator
        
        Args:
            image_paths: List of paths to thumbnail images
            username: TikTok username
        
        Returns:
            Tuple of (average age, most common gender) for identified creator
        """
        if not image_paths:
            logger.warning(f"No images provided for {username}")
            return None, None
        
        logger.info(f"Processing {len(image_paths)} thumbnails for {username}")
        
        # Store all face data for clustering
        all_face_data = []
        
        # Process images in batches for better GPU utilization
        for i in range(0, len(image_paths), self.batch_size):
            batch_paths = image_paths[i:i+self.batch_size]
            logger.info(f"Processing batch {i//self.batch_size + 1}/{len(image_paths)//self.batch_size + 1} for {username}")
            
            # Process each image in the batch
            for img_path in batch_paths:
                try:
                    # Load the image
                    image = cv2.imread(str(img_path))
                    if image is None:
                        logger.warning(f"Failed to load image: {img_path}")
                        continue
                    
                    # Detect faces and persons using YOLOv8
                    with torch.no_grad():
                        detected_objects = self.detector.predict(image)
                    
                    if detected_objects.n_faces == 0:
                        logger.info(f"No faces found in {img_path.name}")
                        continue
                    
                    logger.info(f"Processing {img_path.name}: found {detected_objects.n_faces} faces")
                    
                    # Process each detected face and person with MiVOLO for age/gender prediction
                    with torch.no_grad():
                        self.age_gender_model.predict(image, detected_objects)
                    
                    # Extract features for clustering
                    for face_ind in detected_objects.get_bboxes_inds("face"):
                        x1, y1, x2, y2 = detected_objects.get_bbox_by_ind(face_ind).cpu().numpy()
                        face_crop = image[y1:y2, x1:x2]
                        
                        # Resize to common size for feature extraction
                        face_resized = cv2.resize(face_crop, (64, 64))
                        gray_face = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY)
                        face_features = gray_face.flatten() / 255.0
                        
                        # Get age and gender prediction from MiVOLO
                        age = detected_objects.ages[face_ind]
                        gender = detected_objects.genders[face_ind]
                        gender_score = detected_objects.gender_scores[face_ind]
                        
                        if age is None or gender is None:
                            continue
                        
                        # Store face data
                        face_data = {
                            'img_path': img_path,
                            'face_ind': face_ind,
                            'face_box': [x1, y1, x2, y2],
                            'face_feature': face_features,
                            'age': age,
                            'gender': gender,
                            'confidence': gender_score if gender_score is not None else 0.5
                        }
                        
                        all_face_data.append(face_data)
                
                except Exception as e:
                    logger.error(f"Error processing {img_path}: {str(e)}")
        
        # Identify the content creator
        if all_face_data:
            avg_age, most_common_gender = self._identify_creator(all_face_data, username)
            return avg_age, most_common_gender
        else:
            logger.warning(f"No faces found in thumbnails for {username}")
            return None, None
    
    def _identify_creator(self, all_face_data: List[Dict], username: str) -> Tuple[float, str]:
        """Identify the likely content creator across thumbnails using clustering
        
        Args:
            all_face_data: List of face data dictionaries
            username: TikTok username
        
        Returns:
            Tuple of (average age, most common gender) for identified creator
        """
        logger.info(f"Analyzing {len(all_face_data)} faces to identify content creator for {username}...")
        
        # Extract features for clustering
        features = np.array([face['face_feature'] for face in all_face_data])
        
        # Reduce dimensionality for better clustering
        if len(features) > 10:  # Need enough samples for PCA
            pca = PCA(n_components=min(100, len(features)-1))
            features = pca.fit_transform(features)
        
        # Cluster faces - try to identify unique individuals
        clustering = DBSCAN(eps=20, min_samples=1).fit(features)
        labels = clustering.labels_
        
        # Count occurrences of each label
        label_counts = Counter(labels)
        
        # Find the most common person (likely the creator)
        most_common_label = label_counts.most_common(1)[0][0]
        creator_indices = [i for i, label in enumerate(labels) if label == most_common_label]
        
        logger.info(f"Identified {len(label_counts)} unique individuals")
        logger.info(f"Most frequent individual (likely creator) appears in {len(creator_indices)} thumbnails")
        
        # Process creator data
        creator_ages = [all_face_data[i]['age'] for i in creator_indices]
        creator_genders = [all_face_data[i]['gender'] for i in creator_indices]
        
        # Calculate final estimates
        avg_age = sum(creator_ages) / len(creator_ages)
        gender_counts = Counter(creator_genders)
        most_common_gender = gender_counts.most_common(1)[0][0]
        
        # Store result
        result = {
            'username': username,
            'age': round(avg_age, 1),
            'gender': most_common_gender,
            'appearances': len(creator_indices),
            'total_faces': len(all_face_data)
        }
        self.results.append(result)
        
        logger.info(f"Analysis complete for {username}")
        logger.info(f"Content Creator Summary:")
        logger.info(f"  - Estimated Age: {avg_age:.1f}")
        logger.info(f"  - Estimated Gender: {most_common_gender}")
        
        return avg_age, most_common_gender
    
    def get_results(self) -> List[Dict]:
        """Get the current results
        
        Returns:
            List of result dictionaries
        """
        return self.results
    
    def clear_results(self) -> None:
        """Clear the current results"""
        self.results = []