"""
Phase 5.2: Batch & Real-Time Inference Engines
Builds on Phase 5.1 EnsembleInference to provide high-level interfaces for
offline batch processing and real-time streaming predictions.
"""

import numpy as np
import torch
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from collections import deque
import logging
import time
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class BatchPredictionJob:
    """Represents a batch prediction job."""
    job_id: str
    status: str  # 'pending', 'running', 'complete', 'failed'
    num_samples: int
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results_path: Optional[str] = None
    error_message: Optional[str] = None
    total_latency_ms: float = 0.0


@dataclass
class RealtimePredictionMetrics:
    """Metrics for real-time prediction performance."""
    total_predictions: int = 0
    successful_predictions: int = 0
    failed_predictions: int = 0
    mean_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0.0


class BatchInferenceEngine:
    """
    High-level interface for offline batch predictions.
    
    Handles:
    - Loading data from various sources
    - Batch processing with optional parallelization
    - Result aggregation and export
    - Job tracking and status monitoring
    """
    
    def __init__(
        self,
        ensemble_inference,
        max_batch_size: int = 32,
        output_dir: str = "./inference_results",
    ):
        """
        Initialize batch inference engine.
        
        Args:
            ensemble_inference: EnsembleInference instance from Phase 5.1
            max_batch_size: Maximum samples per batch
            output_dir: Directory for saving results
        """
        self.ensemble_inference = ensemble_inference
        self.max_batch_size = max_batch_size
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.jobs: Dict[str, BatchPredictionJob] = {}
        self.results_cache: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"BatchInferenceEngine initialized: batch_size={max_batch_size}")
    
    def predict_array(
        self,
        features: np.ndarray,
        job_id: str = "batch_001",
        aggregation: str = "mean",
        return_raw: bool = False,
    ) -> Dict[str, Any]:
        """
        Run batch prediction on numpy array.
        
        Args:
            features: (num_samples, seq_len, n_features) array
            job_id: Unique job identifier
            aggregation: Ensemble aggregation method
            return_raw: Return raw logits or probabilities
            
        Returns:
            Dict with predictions and metadata
        """
        num_samples = features.shape[0]
        
        # Create job
        job = BatchPredictionJob(
            job_id=job_id,
            status="running",
            num_samples=num_samples,
            created_at=str(np.datetime64('now')),
            started_at=str(np.datetime64('now')),
        )
        self.jobs[job_id] = job
        
        try:
            start_time = time.time()
            
            # Run batch inference
            batch_result = self.ensemble_inference.predict_batch(
                features,
                batch_id=job_id,
            )
            
            # Get ensemble prediction
            ensemble_pred = self.ensemble_inference.get_ensemble_prediction(
                batch_result,
                aggregation=aggregation,
            )
            
            total_latency_ms = (time.time() - start_time) * 1000
            
            # Prepare results
            results = {
                'job_id': job_id,
                'status': 'complete',
                'num_samples': num_samples,
                'ensemble_predictions': ensemble_pred.tolist(),
                'ensemble_aggregation': aggregation,
                'individual_predictions': {
                    name: {
                        'probabilities': result.probabilities.tolist(),
                        'logits': result.logits.tolist() if not return_raw else None,
                        'latency_ms': result.latency_ms,
                    }
                    for name, result in batch_result.predictions.items()
                },
                'batch_metrics': {
                    'preprocessing_ms': batch_result.preprocessing_time_ms,
                    'inference_ms': batch_result.inference_time_ms,
                    'total_latency_ms': total_latency_ms,
                },
            }
            
            # Update job
            job.status = 'complete'
            job.completed_at = str(np.datetime64('now'))
            job.total_latency_ms = total_latency_ms
            job.results_path = str(self.output_dir / f"{job_id}_results.json")
            
            # Cache results
            self.results_cache[job_id] = results
            
            logger.info(f"Batch job {job_id} complete: {num_samples} samples in {total_latency_ms:.2f}ms")
            
            return results
            
        except Exception as e:
            job.status = 'failed'
            job.error_message = str(e)
            logger.error(f"Batch job {job_id} failed: {e}")
            raise
    
    def predict_dataframe(
        self,
        df,
        feature_columns: List[str],
        job_id: str = "batch_001",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run batch prediction on pandas DataFrame.
        
        Args:
            df: Pandas DataFrame
            feature_columns: Columns to use as features
            job_id: Unique job identifier
            **kwargs: Additional args for predict_array
            
        Returns:
            Dict with predictions and metadata
        """
        features = df[feature_columns].values
        features = features.reshape(len(df), -1, 15)  # Reshape to (batch, seq_len, features)
        
        results = self.predict_array(features, job_id=job_id, **kwargs)
        results['original_indices'] = df.index.tolist()
        
        return results
    
    def predict_file(
        self,
        filepath: str,
        data_format: str = "npy",
        job_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run batch prediction from file.
        
        Args:
            filepath: Path to data file
            data_format: Format - 'npy', 'npz', 'h5'
            job_id: Unique job identifier
            **kwargs: Additional args for predict_array
            
        Returns:
            Dict with predictions and metadata
        """
        if job_id is None:
            job_id = f"file_{Path(filepath).stem}"
        
        # Load data
        filepath = Path(filepath)
        
        if data_format == "npy":
            features = np.load(filepath)
        elif data_format == "npz":
            data = np.load(filepath)
            # Try common naming patterns
            if 'X' in data:
                features = data['X']
            elif 'features' in data:
                features = data['features']
            else:
                features = data[list(data.keys())[0]]
        elif data_format == "h5":
            import h5py
            with h5py.File(filepath, 'r') as f:
                # Try common keys
                if 'X' in f:
                    features = f['X'][:]
                elif 'features' in f:
                    features = f['features'][:]
                else:
                    features = f[list(f.keys())[0]][:]
        else:
            raise ValueError(f"Unknown format: {data_format}")
        
        logger.info(f"Loaded data from {filepath}: shape={features.shape}")
        
        return self.predict_array(features, job_id=job_id, **kwargs)
    
    def save_results(self, job_id: str, filepath: Optional[str] = None):
        """
        Save batch results to JSON file.
        
        Args:
            job_id: Job identifier
            filepath: Output filepath (None = auto-generate)
        """
        if job_id not in self.results_cache:
            raise ValueError(f"Job {job_id} not found in cache")
        
        if filepath is None:
            filepath = self.output_dir / f"{job_id}_results.json"
        else:
            filepath = Path(filepath)
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.results_cache[job_id], f, indent=2)
        
        logger.info(f"Results saved to {filepath}")
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of a batch job."""
        if job_id not in self.jobs:
            raise ValueError(f"Job {job_id} not found")
        
        job = self.jobs[job_id]
        
        return {
            'job_id': job.job_id,
            'status': job.status,
            'num_samples': job.num_samples,
            'created_at': job.created_at,
            'started_at': job.started_at,
            'completed_at': job.completed_at,
            'total_latency_ms': job.total_latency_ms,
            'error_message': job.error_message,
        }
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all batch jobs."""
        return [self.get_job_status(jid) for jid in self.jobs]


class RealtimeInferenceCoordinator:
    """
    High-level interface for real-time streaming predictions.
    
    Features:
    - Single sample inference with <100ms latency target
    - Feature preprocessing and caching
    - Latency tracking and metrics
    - Graceful error handling
    """
    
    def __init__(
        self,
        ensemble_inference,
        feature_cache_size: int = 1000,
        latency_window_size: int = 100,
    ):
        """
        Initialize real-time inference coordinator.
        
        Args:
            ensemble_inference: EnsembleInference instance
            feature_cache_size: Max cached feature vectors
            latency_window_size: Window for latency metrics
        """
        self.ensemble_inference = ensemble_inference
        self.feature_cache: Dict[str, np.ndarray] = {}
        self.feature_cache_size = feature_cache_size
        
        # Latency tracking
        self.latencies = deque(maxlen=latency_window_size)
        self.metrics = RealtimePredictionMetrics()
        
        logger.info(f"RealtimeInferenceCoordinator initialized")
    
    def predict(
        self,
        features: np.ndarray,
        train_id: Optional[str] = None,
        aggregation: str = "mean",
        cache_features: bool = True,
    ) -> Dict[str, Any]:
        """
        Run real-time inference on single sample.
        
        Args:
            features: (seq_len, n_features) array
            train_id: Optional train identifier
            aggregation: Ensemble aggregation method
            cache_features: Cache features for future use
            
        Returns:
            Dict with prediction, latency, and metadata
        """
        start_time = time.time()
        
        try:
            # Ensure correct shape
            if features.ndim == 2:
                features = np.expand_dims(features, axis=0)
            elif features.ndim != 3 or features.shape[0] != 1:
                raise ValueError(f"Expected (1, seq_len, n_features), got {features.shape}")
            
            # Run inference
            predictions = self.ensemble_inference.predict_single(features.squeeze(0))
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Cache if requested
            if cache_features and train_id and len(self.feature_cache) < self.feature_cache_size:
                self.feature_cache[train_id] = features[0]
            
            # Update metrics
            self.latencies.append(latency_ms)
            self.metrics.total_predictions += 1
            self.metrics.successful_predictions += 1
            self._update_latency_metrics()
            
            # Prepare result
            result = {
                'train_id': train_id,
                'status': 'success',
                'predictions': {
                    name: float(prob)
                    for name, prob in predictions.items()
                },
                'ensemble_prediction': float(np.mean(list(predictions.values()))),
                'aggregation': aggregation,
                'latency_ms': latency_ms,
                'timestamp': str(np.datetime64('now')),
            }
            
            # Log if latency exceeds threshold
            if latency_ms > 100:
                logger.warning(f"Latency threshold exceeded: {latency_ms:.2f}ms for {train_id}")
            
            return result
            
        except Exception as e:
            self.metrics.failed_predictions += 1
            logger.error(f"Prediction failed for {train_id}: {e}")
            
            return {
                'train_id': train_id,
                'status': 'failed',
                'error': str(e),
                'latency_ms': (time.time() - start_time) * 1000,
                'timestamp': str(np.datetime64('now')),
            }
    
    def predict_batch_streaming(
        self,
        features_list: List[np.ndarray],
        train_ids: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Run predictions on multiple samples in streaming fashion.
        
        Args:
            features_list: List of (seq_len, n_features) arrays
            train_ids: Optional list of train identifiers
            **kwargs: Additional args for predict()
            
        Returns:
            List of prediction results
        """
        if train_ids is None:
            train_ids = [f"train_{i}" for i in range(len(features_list))]
        
        results = []
        for features, train_id in zip(features_list, train_ids):
            result = self.predict(features, train_id=train_id, **kwargs)
            results.append(result)
        
        return results
    
    def _update_latency_metrics(self):
        """Update latency statistics."""
        if not self.latencies:
            return
        
        latencies_sorted = sorted(list(self.latencies))
        
        self.metrics.mean_latency_ms = np.mean(latencies_sorted)
        self.metrics.p99_latency_ms = latencies_sorted[int(0.99 * len(latencies_sorted))]
        self.metrics.p95_latency_ms = latencies_sorted[int(0.95 * len(latencies_sorted))]
        self.metrics.min_latency_ms = min(latencies_sorted)
        self.metrics.max_latency_ms = max(latencies_sorted)
    
    def get_metrics(self) -> Dict[str, Union[int, float]]:
        """Get real-time prediction metrics."""
        return {
            'total_predictions': self.metrics.total_predictions,
            'successful_predictions': self.metrics.successful_predictions,
            'failed_predictions': self.metrics.failed_predictions,
            'success_rate': (
                self.metrics.successful_predictions / self.metrics.total_predictions
                if self.metrics.total_predictions > 0 else 0
            ),
            'latency_ms': {
                'mean': self.metrics.mean_latency_ms,
                'p99': self.metrics.p99_latency_ms,
                'p95': self.metrics.p95_latency_ms,
                'min': self.metrics.min_latency_ms,
                'max': self.metrics.max_latency_ms,
            },
            'cache_size': len(self.feature_cache),
        }
    
    def reset_metrics(self):
        """Reset metrics counters."""
        self.metrics = RealtimePredictionMetrics()
        self.latencies.clear()
    
    def clear_cache(self):
        """Clear feature cache."""
        self.feature_cache.clear()


class InferencePipeline:
    """
    Unified inference pipeline combining batch and real-time engines.
    
    Provides simple interface to switch between batch and streaming modes.
    """
    
    def __init__(
        self,
        ensemble_inference,
        max_batch_size: int = 32,
        output_dir: str = "./inference_results",
        feature_cache_size: int = 1000,
    ):
        """
        Initialize unified inference pipeline.
        
        Args:
            ensemble_inference: EnsembleInference instance
            max_batch_size: Max batch size for batch engine
            output_dir: Output directory for batch results
            feature_cache_size: Cache size for real-time engine
        """
        self.ensemble_inference = ensemble_inference
        
        self.batch_engine = BatchInferenceEngine(
            ensemble_inference=ensemble_inference,
            max_batch_size=max_batch_size,
            output_dir=output_dir,
        )
        
        self.realtime_engine = RealtimeInferenceCoordinator(
            ensemble_inference=ensemble_inference,
            feature_cache_size=feature_cache_size,
        )
        
        logger.info("InferencePipeline initialized with batch and real-time engines")
    
    def batch_predict(self, features: np.ndarray, job_id: str = "batch_001", **kwargs):
        """Predict using batch engine."""
        return self.batch_engine.predict_array(features, job_id=job_id, **kwargs)
    
    def stream_predict(self, features: np.ndarray, train_id: Optional[str] = None, **kwargs):
        """Predict using real-time engine."""
        return self.realtime_engine.predict(features, train_id=train_id, **kwargs)
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of both engines."""
        return {
            'batch_engine': {
                'active_jobs': len([j for j in self.batch_engine.jobs.values() if j.status == 'running']),
                'total_jobs': len(self.batch_engine.jobs),
            },
            'realtime_engine': self.realtime_engine.get_metrics(),
        }
