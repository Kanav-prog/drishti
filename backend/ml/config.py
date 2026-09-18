"""
PyTorch Configuration for Phase 3 Models.
Centralizes hyperparameters, device settings, and training defaults.
"""

import os
from pathlib import Path
from typing import Dict, Any


class PyTorchConfig:
    """Central configuration for PyTorch models and training."""
    
    # ===== Device Settings =====
    DEVICE = "auto"  # 'auto' for auto-detect, 'cuda', or 'cpu'
    SEED = 42
    
    # ===== Training Defaults =====
    DEFAULT_BATCH_SIZE = 32
    DEFAULT_LEARNING_RATE = 1e-3
    DEFAULT_EPOCHS = 50
    DEFAULT_OPTIMIZER = "adam"
    DEFAULT_SCHEDULER = "reduce_on_plateau"
    
    # ===== Loss Function Hyperparameters =====
    FOCAL_LOSS_ALPHA = 0.25  # Balance factor for positive class
    FOCAL_LOSS_GAMMA = 2.0   # Focusing parameter (higher = harder examples)
    
    # Class weights (inverse frequency)
    CLASS_WEIGHT_NEGATIVE = 1.0  # Majority class
    CLASS_WEIGHT_POSITIVE = 11.0  # Minority class (9% → ~11x weight)
    
    # ===== K-Fold Settings =====
    KFOLD_SPLITS = 5
    KFOLD_STRATIFIED = True
    KFOLD_SHUFFLE = True
    
    # ===== LSTM Configuration =====
    LSTM_HIDDEN_SIZE = 128
    LSTM_NUM_LAYERS = 2
    LSTM_DROPOUT = 0.3
    LSTM_BIDIRECTIONAL = False
    
    # ===== 1D-CNN Configuration =====
    CNN1D_OUT_CHANNELS = [32, 64]  # Channels: 15 → 32 → 64
    CNN1D_KERNEL_SIZE = 3
    CNN1D_STRIDE = 1
    CNN1D_PADDING = 1
    CNN1D_DROPOUT = 0.2
    CNN1D_POOL_SIZE = 2
    
    # ===== GAT (Graph Attention Network) Configuration =====
    GAT_NUM_LAYERS = 2
    GAT_NUM_HEADS = 4
    GAT_OUT_CHANNELS = 64
    GAT_DROPOUT = 0.2
    GAT_ATTENTION_DROPOUT = 0.2
    GAT_EDGE_DIM = 1  # One-dimensional edge weights
    
    # ===== Hybrid Model Fusion =====
    HYBRID_FUSION_METHOD = "attention"  # 'concat', 'attention', or 'weighted'
    HYBRID_ATTENTION_HIDDEN = 64
    
    # ===== Training Hyperparameters =====
    EARLY_STOPPING_PATIENCE = 10
    EARLY_STOPPING_MIN_DELTA = 1e-4
    
    GRADIENT_CLIP_VALUE = 1.0
    GRADIENT_CLIP_NORM = None
    
    WEIGHT_DECAY = 1e-5
    MOMENTUM = 0.9  # For SGD optimizer
    
    # Learning rate scheduler
    SCHEDULER_FACTOR = 0.1  # Reduce LR by this factor
    SCHEDULER_PATIENCE = 5  # Patience for reduction
    SCHEDULER_MIN_LR = 1e-6
    
    # ===== Data Settings =====
    FEATURE_DIM = 15  # Number of features per timestep
    SEQUENCE_LENGTH = 576  # 48 hours × 12 samples/hour
    NUM_SENSORS = 7000  # Railway stations/junctions
    INPUT_EMBEDDING_DIM = 384  # From Phase 1 embeddings
    
    # ===== Model Ensemble Settings =====
    ENSEMBLE_VOTING_THRESHOLD = 2  # Require 2+ models to agree
    ENSEMBLE_USE_WEIGHTS = True  # Weight by individual model performance
    
    # ===== Inference Settings =====
    INFERENCE_BATCH_SIZE = 64
    INFERENCE_DEVICE = "auto"
    INFERENCE_CONFIDENCE_THRESHOLD = 0.5
    
    # Alert severity mapping
    ALERT_SEVERITY_MAPPING = {
        "confidence": [0.0, 0.5, 0.7, 1.0],
        "severity": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    }
    
    # ===== Validation Thresholds (Target Metrics) =====
    TARGET_AUC = 0.85
    TARGET_SENSITIVITY = 0.80  # Recall for positive class
    TARGET_SPECIFICITY = 0.90  # Recall for negative class
    TARGET_INFERENCE_LATENCY_MS = 100
    
    # ===== Paths =====
    MODELS_DIR = Path(__file__).parent / "models"
    RESULTS_DIR = Path(__file__).parent.parent / "data" / "phase3_results"
    LOGS_DIR = Path(__file__).parent.parent / "logs" / "phase3"
    CHECKPOINTS_DIR = RESULTS_DIR / "checkpoints"
    
    # ===== Logging =====
    LOG_LEVEL = "INFO"
    LOG_INTERVAL = 10  # Log metrics every N batches
    
    # ===== Reproducibility =====
    CUDNN_DETERMINISTIC = True
    CUDNN_BENCHMARK = False  # Set to False for reproducibility
    
    @classmethod
    def get_all_config(cls) -> Dict[str, Any]:
        """Get all configuration as dictionary."""
        return {k: getattr(cls, k) for k in dir(cls) 
                if not k.startswith('_') and k.isupper()}
    
    @classmethod
    def print_config(cls):
        """Print configuration."""
        config = cls.get_all_config()
        print("\n" + "=" * 60)
        print("PyTorch Configuration")
        print("=" * 60)
        
        for key, value in sorted(config.items()):
            if not callable(value):
                print(f"{key:40s} = {value}")
        
        print("=" * 60 + "\n")


class DataConfig:
    """Configuration for data loading and preprocessing."""
    
    # Dataset paths
    DATASET_H5_PATH = "backend/data/timeseries_dataset.h5"
    DATASET_NPZ_PATH = "backend/data/timeseries_dataset.npz"
    METADATA_PATH = "backend/data/dataset_metadata.json"
    
    # Dataset statistics (from Phase 2)
    TOTAL_SEQUENCES = 4400
    NUM_POSITIVE = 400
    NUM_NEGATIVE = 4000
    POSITIVE_RATIO = 0.0909  # ~9%
    
    # Split ratios
    TRAIN_RATIO = 0.75  # 3,300 samples
    VAL_RATIO = 0.125   # 550 samples
    TEST_RATIO = 0.125  # 550 samples
    
    # Feature names
    FEATURE_NAMES = [
        "delay_minutes",
        "speed_kmh",
        "delay_trend",
        "delay_acceleration",
        "delay_jitter",
        "maintenance_active",
        "signal_state_encoded",
        "track_state_encoded",
        "embedding_similarity",
        "time_of_day_encode",
        "hour_of_day",
        "station_centrality",
        "adjacent_train_delay",
        "junction_density",
        "grid_position_normalized",
    ]


class ModelPaths:
    """Model save/load paths."""
    
    BASE_DIR = Path(__file__).parent.parent.parent / "models"
    PHASE3_DIR = BASE_DIR / "phase3"
    
    @staticmethod
    def get_model_path(name: str, fold_id: int = None) -> Path:
        """Get model save path."""
        if fold_id is not None:
            return ModelPaths.PHASE3_DIR / f"{name}_fold{fold_id}.pt"
        return ModelPaths.PHASE3_DIR / f"{name}.pt"
    
    @staticmethod
    def get_checkpoint_path(name: str, fold_id: int = None, epoch: int = None) -> Path:
        """Get checkpoint path."""
        if epoch is not None and fold_id is not None:
            return ModelPaths.PHASE3_DIR / f"{name}_fold{fold_id}_epoch{epoch}.pt"
        elif fold_id is not None:
            return ModelPaths.PHASE3_DIR / f"{name}_fold{fold_id}_best.pt"
        return ModelPaths.PHASE3_DIR / f"{name}_best.pt"


# Export main config
__all__ = ["PyTorchConfig", "DataConfig", "ModelPaths"]


if __name__ == "__main__":
    PyTorchConfig.print_config()
