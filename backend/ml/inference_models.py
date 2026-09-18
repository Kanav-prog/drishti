"""
Phase 5.1: Model Loading & Device Management for Inference
Handles checkpoint loading, model initialization, and device placement.
"""

import torch
import torch.nn as nn
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import json
import logging
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class ModelCheckpoint:
    """Metadata for a loaded model checkpoint."""
    model_name: str
    architecture: str  # 'lstm', 'cnn1d', 'gat', 'hybrid'
    device: str
    checkpoint_path: Path
    loaded_at: str
    best_epoch: int
    best_auc: float
    total_parameters: int
    weights_size_mb: float


class DeviceManager:
    """Manage PyTorch device selection and placement."""
    
    @staticmethod
    def get_device(prefer_gpu: bool = False) -> torch.device:
        """
        Get appropriate device for inference.
        
        Args:
            prefer_gpu: Prefer GPU if available
            
        Returns:
            torch.device (cuda/cpu)
        """
        if prefer_gpu and torch.cuda.is_available():
            device = torch.device('cuda')
            logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            device = torch.device('cpu')
            logger.info("Using CPU for inference")
        
        return device
    
    @staticmethod
    def get_device_info() -> Dict[str, Any]:
        """Get detailed device information."""
        info = {
            'device': 'cuda' if torch.cuda.is_available() else 'cpu',
            'cuda_available': torch.cuda.is_available(),
        }
        
        if torch.cuda.is_available():
            info['gpu_name'] = torch.cuda.get_device_name(0)
            info['gpu_count'] = torch.cuda.device_count()
            props = torch.cuda.get_device_properties(0)
            info['gpu_memory_gb'] = props.total_memory / 1e9
            info['gpu_compute_capability'] = f"{props.major}.{props.minor}"
        
        return info


class ModelLoader:
    """Load trained models from Phase 4 checkpoints."""
    
    def __init__(self, checkpoint_dir: str, device: torch.device):
        """
        Initialize model loader.
        
        Args:
            checkpoint_dir: Directory containing ensemble checkpoints
            device: torch.device for loading models
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.device = device
        self.metadata = {}
        
        # Load ensemble metadata
        metadata_path = self.checkpoint_dir / "ensemble_metadata_phase4_complete.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
            logger.info(f"Loaded ensemble metadata: {metadata_path}")
        else:
            logger.warning(f"Ensemble metadata not found: {metadata_path}")
    
    def load_model(
        self,
        model_class: type,
        model_name: str,
        model_config: Dict[str, Any],
    ) -> Tuple[nn.Module, ModelCheckpoint]:
        """
        Load a single model from checkpoint.
        
        Args:
            model_class: Model class (e.g., LSTMTemporalClassifier)
            model_name: Name of model (e.g., 'lstm_model_1')
            model_config: Configuration dict for model initialization
            
        Returns:
            Tuple of (loaded_model, checkpoint_metadata)
        """
        checkpoint_path = self.checkpoint_dir / model_name / "model_best.pt"
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        
        # Separate architecture from model config
        clean_config = {k: v for k, v in model_config.items() if k != 'architecture'}
        
        # Initialize model architecture
        model = model_class(**clean_config)
        model = model.to(self.device)
        
        # Load weights
        checkpoint = torch.load(checkpoint_path, map_location=self.device)
        model.load_state_dict(checkpoint['model_state_dict'])
        
        # Set to inference mode
        model.eval()
        
        # Get checkpoint metadata
        model_histories = self.metadata.get('model_histories', {})
        model_history = model_histories.get(model_name, {})
        best_metrics = model_history.get('best_metrics', {})
        
        checkpoint_metadata = ModelCheckpoint(
            model_name=model_name,
            architecture=model_config.get('architecture', 'unknown'),
            device=str(self.device),
            checkpoint_path=checkpoint_path,
            loaded_at=str(Path(checkpoint_path).stat().st_mtime),
            best_epoch=best_metrics.get('epoch', -1),
            best_auc=best_metrics.get('val_auc', 0.0),
            total_parameters=sum(p.numel() for p in model.parameters()),
            weights_size_mb=checkpoint_path.stat().st_size / 1e6,
        )
        
        logger.info(f"Loaded {model_name} from {checkpoint_path}")
        logger.info(f"  Best AUC: {checkpoint_metadata.best_auc:.4f}")
        logger.info(f"  Parameters: {checkpoint_metadata.total_parameters:,}")
        logger.info(f"  Size: {checkpoint_metadata.weights_size_mb:.2f} MB")
        
        return model, checkpoint_metadata
    
    def get_ensemble_metrics(self) -> Dict[str, Any]:
        """Get ensemble-level metrics from metadata."""
        return self.metadata.get('ensemble_metrics', {})
    
    def get_model_rankings(self) -> list:
        """Get model performance rankings."""
        metrics = self.get_ensemble_metrics()
        return metrics.get('model_rankings', [])


class InferenceConfig:
    """Configuration for inference."""
    
    def __init__(
        self,
        checkpoint_dir: str = "./phase4_ensemble_checkpoints",
        device: Optional[torch.device] = None,
        prefer_gpu: bool = False,
        batch_size: int = 32,
        num_workers: int = 0,
        inference_timeout_sec: float = 5.0,
    ):
        """
        Initialize inference configuration.
        
        Args:
            checkpoint_dir: Path to Phase 4 checkpoints
            device: Explicit device or None for auto-detect
            prefer_gpu: Prefer GPU if available
            batch_size: Batch size for inference
            num_workers: Worker threads for data loading
            inference_timeout_sec: Timeout for single prediction
        """
        self.checkpoint_dir = checkpoint_dir
        self.device = device or DeviceManager.get_device(prefer_gpu=prefer_gpu)
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.inference_timeout_sec = inference_timeout_sec
        
        logger.info(f"InferenceConfig initialized:")
        logger.info(f"  Checkpoint dir: {checkpoint_dir}")
        logger.info(f"  Device: {self.device}")
        logger.info(f"  Batch size: {batch_size}")


class ModelCache:
    """Simple cache for loaded models with metadata."""
    
    def __init__(self, max_models: int = 10):
        """
        Initialize model cache.
        
        Args:
            max_models: Maximum number of models to cache
        """
        self.cache: Dict[str, Tuple[nn.Module, ModelCheckpoint]] = {}
        self.max_models = max_models
        self.access_times: Dict[str, float] = {}
    
    def get(self, model_name: str) -> Optional[Tuple[nn.Module, ModelCheckpoint]]:
        """Get model from cache."""
        if model_name in self.cache:
            self.access_times[model_name] = time.time()
            return self.cache[model_name]
        return None
    
    def put(self, model_name: str, model: nn.Module, metadata: ModelCheckpoint):
        """
        Add model to cache.
        
        Args:
            model_name: Model identifier
            model: Loaded model
            metadata: Checkpoint metadata
        """
        if len(self.cache) >= self.max_models:
            # Remove least recently used
            lru_model = min(self.access_times, key=self.access_times.get)
            del self.cache[lru_model]
            del self.access_times[lru_model]
            logger.debug(f"Evicted {lru_model} from cache")
        
        self.cache[model_name] = (model, metadata)
        self.access_times[model_name] = time.time()
        logger.debug(f"Cached {model_name}")
    
    def clear(self):
        """Clear cache."""
        self.cache.clear()
        self.access_times.clear()
    
    def size(self) -> int:
        """Get cache size."""
        return len(self.cache)


def benchmark_model_inference(
    model: nn.Module,
    input_tensor: torch.Tensor,
    num_runs: int = 100,
    device: torch.device = torch.device('cpu'),
) -> Dict[str, float]:
    """
    Benchmark inference latency for a model.
    
    Args:
        model: Model to benchmark
        input_tensor: Input tensor (will use its shape)
        num_runs: Number of runs for averaging
        device: Device to benchmark on
        
    Returns:
        Dict with latency statistics (ms)
    """
    model.eval()
    
    with torch.no_grad():
        # Warmup
        for _ in range(5):
            _ = model(input_tensor.to(device))
        
        # Measure
        times = []
        for _ in range(num_runs):
            start = time.time()
            _ = model(input_tensor.to(device))
            end = time.time()
            times.append((end - start) * 1000)  # Convert to ms
    
    import statistics
    times = sorted(times)
    
    return {
        'mean_ms': statistics.mean(times),
        'median_ms': statistics.median(times),
        'p99_ms': times[int(0.99 * len(times))],
        'p95_ms': times[int(0.95 * len(times))],
        'min_ms': min(times),
        'max_ms': max(times),
        'std_ms': statistics.stdev(times),
    }
