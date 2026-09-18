"""
Phase 5: End-to-End Inference Pipeline
Core engine for real-time and batch inference with Phase 4 trained models.
"""

import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
import time
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Result of a single model prediction."""
    model_name: str
    logits: np.ndarray  # Raw logits (batch_size,) or (batch_size, 1)
    probabilities: np.ndarray  # Sigmoid probabilities (batch_size,)
    latency_ms: float  # Time for inference
    device: str


@dataclass
class EnsembleInferenceBatch:
    """Batch inference results from all models."""
    batch_id: str
    batch_size: int
    predictions: Dict[str, PredictionResult]  # model_name -> PredictionResult
    total_latency_ms: float
    preprocessing_time_ms: float
    inference_time_ms: float
    postprocessing_time_ms: float
    timestamp: str


class EnsembleInference:
    """
    Main inference engine for Phase 5.
    
    Manages loading and caching of Phase 4 trained models,
    provides batch and single-sample inference interfaces.
    """
    
    def __init__(
        self,
        checkpoint_dir: str = "./phase4_ensemble_checkpoints",
        device: torch.device = torch.device('cpu'),
        use_cache: bool = True,
        cache_size: int = 10,
    ):
        """
        Initialize ensemble inference engine.
        
        Args:
            checkpoint_dir: Directory with Phase 4 checkpoints
            device: Device for inference (cpu/cuda)
            use_cache: Enable model caching
            cache_size: Max cached models
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.device = device
        self.use_cache = use_cache
        self.cache_size = cache_size
        
        # Model storage
        self.models: Dict[str, nn.Module] = {}
        self.model_metadata: Dict[str, Any] = {}
        self.model_configs: Dict[str, Dict[str, Any]] = {}
        
        # Statistics
        self.stats = defaultdict(lambda: {
            'predictions': 0,
            'total_latency_ms': 0,
            'mean_latency_ms': 0,
        })
        
        logger.info(f"EnsembleInference initialized on {device}")
    
    def register_model(
        self,
        model_name: str,
        model: nn.Module,
        model_config: Dict[str, Any],
        metadata: Dict[str, Any],
    ):
        """
        Register a loaded model for inference.
        
        Args:
            model_name: Unique model identifier
            model: Loaded PyTorch model
            model_config: Configuration dict used to train model
            metadata: Checkpoint metadata
        """
        model.eval()
        model = model.to(self.device)
        
        self.models[model_name] = model
        self.model_configs[model_name] = model_config
        self.model_metadata[model_name] = metadata
        
        logger.info(f"Registered model: {model_name}")
        logger.info(f"  Architecture: {model_config.get('architecture', 'unknown')}")
        logger.info(f"  Best AUC: {metadata.get('best_auc', 'N/A')}")
    
    def list_models(self) -> List[str]:
        """Get list of registered models."""
        return list(self.models.keys())
    
    def get_model_info(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed info on all registered models."""
        info = {}
        for name in self.models:
            info[name] = {
                'architecture': self.model_configs[name].get('architecture', 'unknown'),
                'best_auc': self.model_metadata[name].get('best_auc', 0.0),
                'parameters': sum(p.numel() for p in self.models[name].parameters()),
                'device': str(self.device),
                'cached': name in self.models,
            }
        return info
    
    def _preprocess_batch(
        self,
        features: np.ndarray,
        normalizer: Optional[Any] = None,
    ) -> torch.Tensor:
        """
        Preprocess feature batch for inference.
        
        Args:
            features: (batch_size, seq_len, n_features) numpy array
            normalizer: Optional feature normalization function
            
        Returns:
            Preprocessed torch tensor on device
        """
        # Apply normalization if provided
        if normalizer is not None:
            features = normalizer(features)
        
        # Convert to torch tensor
        tensor = torch.from_numpy(features).float()
        tensor = tensor.to(self.device)
        
        return tensor
    
    def _forward_batch(
        self,
        model_name: str,
        features_tensor: torch.Tensor,
    ) -> PredictionResult:
        """
        Run batch forward pass through a single model.
        
        Args:
            model_name: Model to use
            features_tensor: Preprocessed features on device
            
        Returns:
            PredictionResult with latencies
        """
        if model_name not in self.models:
            raise ValueError(f"Unknown model: {model_name}")
        
        model = self.models[model_name]
        
        # Inference
        start_time = time.time()
        with torch.no_grad():
            logits = model(features_tensor)
        latency_ms = (time.time() - start_time) * 1000
        
        # Convert outputs
        logits_np = logits.cpu().detach().numpy()
        
        # Handle shape: could be (batch_size,) or (batch_size, 1)
        if logits_np.ndim > 1:
            logits_np = logits_np.squeeze(-1)
        
        # Sigmoid for probabilities
        probabilities = 1.0 / (1.0 + np.exp(-logits_np))
        
        return PredictionResult(
            model_name=model_name,
            logits=logits_np,
            probabilities=probabilities,
            latency_ms=latency_ms,
            device=str(self.device),
        )
    
    def predict_batch(
        self,
        features: np.ndarray,
        model_names: Optional[List[str]] = None,
        normalizer: Optional[Any] = None,
        batch_id: str = "default",
    ) -> EnsembleInferenceBatch:
        """
        Run inference on batch through all (or specified) models.
        
        Args:
            features: (batch_size, seq_len, n_features) numpy array
            model_names: Models to use (None = all)
            normalizer: Optional feature normalizer
            batch_id: Identifier for batch
            
        Returns:
            EnsembleInferenceBatch with all predictions
        """
        if model_names is None:
            model_names = self.list_models()
        
        if not model_names:
            raise ValueError("No models registered")
        
        batch_size = features.shape[0]
        
        # Preprocess
        start_preprocessing = time.time()
        features_tensor = self._preprocess_batch(features, normalizer)
        preprocessing_time_ms = (time.time() - start_preprocessing) * 1000
        
        # Inference
        start_inference = time.time()
        predictions = {}
        for model_name in model_names:
            if model_name not in self.models:
                logger.warning(f"Model '{model_name}' not found, skipping")
                continue
            
            result = self._forward_batch(model_name, features_tensor)
            predictions[model_name] = result
        
        inference_time_ms = (time.time() - start_inference) * 1000
        
        # Postprocessing (compute stats)
        start_postprocessing = time.time()
        total_latency = sum(r.latency_ms for r in predictions.values())
        postprocessing_time_ms = (time.time() - start_postprocessing) * 1000
        
        # Update statistics
        for model_name in predictions:
            self.stats[model_name]['predictions'] += batch_size
            self.stats[model_name]['total_latency_ms'] += predictions[model_name].latency_ms
            self.stats[model_name]['mean_latency_ms'] = (
                self.stats[model_name]['total_latency_ms'] /
                self.stats[model_name]['predictions']
            )
        
        batch_result = EnsembleInferenceBatch(
            batch_id=batch_id,
            batch_size=batch_size,
            predictions=predictions,
            total_latency_ms=total_latency,
            preprocessing_time_ms=preprocessing_time_ms,
            inference_time_ms=inference_time_ms,
            postprocessing_time_ms=postprocessing_time_ms,
            timestamp=str(np.datetime64('now')),
        )
        
        logger.debug(f"Batch {batch_id}: {batch_size} samples, "
                    f"total_latency={total_latency:.2f}ms, "
                    f"models={len(predictions)}")
        
        return batch_result
    
    def predict_single(
        self,
        features: np.ndarray,
        model_names: Optional[List[str]] = None,
        normalizer: Optional[Any] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Run inference on single sample through all models.
        
        Args:
            features: (seq_len, n_features) numpy array
            model_names: Models to use (None = all)
            normalizer: Optional feature normalizer
            
        Returns:
            Dict mapping model_name -> probabilities (array of 1 element)
        """
        # Add batch dimension
        features_batched = np.expand_dims(features, axis=0)
        
        # Run batch inference
        batch_result = self.predict_batch(
            features_batched,
            model_names=model_names,
            normalizer=normalizer,
            batch_id="single",
        )
        
        # Extract single probabilities
        return {
            name: result.probabilities[0]
            for name, result in batch_result.predictions.items()
        }
    
    def get_ensemble_prediction(
        self,
        batch_result: EnsembleInferenceBatch,
        aggregation: str = "mean",
    ) -> np.ndarray:
        """
        Combine predictions from multiple models.
        
        Args:
            batch_result: EnsembleInferenceBatch from predict_batch
            aggregation: 'mean', 'median', 'max', 'min'
            
        Returns:
            Aggregated predictions (batch_size,)
        """
        if not batch_result.predictions:
            raise ValueError("No predictions available")
        
        # Stack all probabilities
        all_probs = np.stack([
            result.probabilities
            for result in batch_result.predictions.values()
        ], axis=0)  # Shape: (num_models, batch_size)
        
        # Aggregate across models
        if aggregation == "mean":
            ensemble_pred = np.mean(all_probs, axis=0)
        elif aggregation == "median":
            ensemble_pred = np.median(all_probs, axis=0)
        elif aggregation == "max":
            ensemble_pred = np.max(all_probs, axis=0)
        elif aggregation == "min":
            ensemble_pred = np.min(all_probs, axis=0)
        else:
            raise ValueError(f"Unknown aggregation: {aggregation}")
        
        return ensemble_pred
    
    def get_statistics(self) -> Dict[str, Dict[str, Union[int, float]]]:
        """Get inference statistics per model."""
        return dict(self.stats)
    
    def reset_statistics(self):
        """Reset inference statistics."""
        self.stats.clear()
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all models and engine."""
        return {
            'device': str(self.device),
            'num_models_loaded': len(self.models),
            'models': self.list_models(),
            'model_info': self.get_model_info(),
            'statistics': self.get_statistics(),
            'device_info': self._get_device_info(),
        }
    
    def _get_device_info(self) -> Dict[str, Any]:
        """Get device information."""
        info = {
            'device_type': str(self.device).split(':')[0],
            'cuda_available': torch.cuda.is_available(),
        }
        
        if torch.cuda.is_available() and 'cuda' in str(self.device):
            info['gpu_name'] = torch.cuda.get_device_name(0)
            info['gpu_memory_gb'] = torch.cuda.get_device_properties(0).total_memory / 1e9
        
        return info
    
    def warmup(self, sample_size: int = 32, seq_len: int = 576, n_features: int = 15):
        """
        Warm up models with dummy data.
        Helps with CUDA kernel compilation and JIT optimization.
        
        Args:
            sample_size: Batch size for warmup
            seq_len: Sequence length
            n_features: Number of features
        """
        logger.info("Warming up models...")
        
        dummy_input = np.random.randn(sample_size, seq_len, n_features).astype(np.float32)
        
        try:
            _ = self.predict_batch(dummy_input)
            logger.info("Warmup complete")
        except Exception as e:
            logger.warning(f"Warmup failed: {e}")


def create_ensemble_inference_from_checkpoint(
    checkpoint_dir: str = "./phase4_ensemble_checkpoints",
    device: Optional[torch.device] = None,
    prefer_gpu: bool = False,
) -> EnsembleInference:
    """
    Factory function to create EnsembleInference from Phase 4 checkpoint.
    
    Args:
        checkpoint_dir: Path to ensemble checkpoints
        device: Explicit device or None for auto-detect
        prefer_gpu: Prefer GPU if available
        
    Returns:
        Initialized EnsembleInference engine
    """
    from backend.ml.inference_models import DeviceManager, ModelLoader
    from backend.ml.models.lstm_classifier import LSTMTemporalClassifier
    from backend.ml.models.cnn1d_classifier import CNN1DTemporalClassifier
    
    # Setup device
    if device is None:
        device = DeviceManager.get_device(prefer_gpu=prefer_gpu)
    
    # Initialize
    engine = EnsembleInference(checkpoint_dir=checkpoint_dir, device=device)
    loader = ModelLoader(checkpoint_dir, device)
    
    # Get model rankings from metadata
    rankings = loader.get_model_rankings()
    
    logger.info(f"Loading models from {checkpoint_dir}...")
    
    # Load models (with error handling for missing architectures)
    model_architectures = {
        'lstm': LSTMTemporalClassifier,
        'cnn1d': CNN1DTemporalClassifier,
    }
    
    for ranking in rankings:
        model_name = ranking['model']
        model_auc = ranking['val_auc']
        
        try:
            # Determine architecture from model name
            architecture = 'lstm' if 'lstm' in model_name.lower() else 'cnn1d'
            
            if architecture not in model_architectures:
                logger.warning(f"Architecture '{architecture}' not available, skipping {model_name}")
                continue
            
            model_class = model_architectures[architecture]
            
            # Default config (will be adjusted based on actual checkpoint)
            config = {
                'architecture': architecture,
                'input_size': 15,
                'hidden_size': 64,  # Smaller default
                'num_layers': 1,    # Single layer default
            }
            
            # Load
            model, metadata = loader.load_model(model_class, model_name, config)
            
            # Register
            engine.register_model(
                model_name,
                model,
                config,
                {
                    'best_auc': model_auc,
                    'best_epoch': metadata.best_epoch,
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to load {model_name}: {e}")
            continue
    
    if not engine.list_models():
        logger.warning("No models loaded successfully!")
    else:
        logger.info(f"Successfully loaded {len(engine.list_models())} models")
    
    return engine
