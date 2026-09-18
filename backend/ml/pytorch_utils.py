"""
PyTorch utilities for device management, seeding, and configuration.
Phase 3.0.1: Environment setup for temporal + graph models.
"""

import os
import random
import numpy as np
import torch
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manages PyTorch device selection, memory, and capabilities."""
    
    def __init__(self):
        self.device = None
        self.device_info = None
        self.is_cuda_available = False
        self.cuda_device_count = 0
    
    def detect_cuda_device(self) -> str:
        """
        Detect and return the best available device.
        
        Returns:
            str: 'cuda' if GPU available, else 'cpu'
        """
        self.is_cuda_available = torch.cuda.is_available()
        self.cuda_device_count = torch.cuda.device_count() if self.is_cuda_available else 0
        
        if self.is_cuda_available:
            self.device = torch.device("cuda")
            logger.info(f"CUDA detected: {self.cuda_device_count} device(s)")
            return "cuda"
        else:
            self.device = torch.device("cpu")
            logger.warning("CUDA not available, using CPU (slower training)")
            return "cpu"
    
    def get_device(self) -> torch.device:
        """
        Get the current device. Detects if not already done.
        
        Returns:
            torch.device: Current device
        """
        if self.device is None:
            self.detect_cuda_device()
        return self.device
    
    def get_device_info(self) -> Dict[str, Any]:
        """
        Get detailed device information.
        
        Returns:
            dict: Device specs (name, compute capability, memory, etc.)
        """
        if self.device_info is not None:
            return self.device_info
        
        info = {
            "device_type": "cuda" if self.is_cuda_available else "cpu",
            "cuda_available": self.is_cuda_available,
            "cuda_device_count": self.cuda_device_count,
        }
        
        if self.is_cuda_available:
            device_idx = torch.cuda.current_device()
            info["cuda_device_name"] = torch.cuda.get_device_name(device_idx)
            info["cuda_compute_capability"] = torch.cuda.get_device_capability(device_idx)
            
            # Memory info
            total_mem = torch.cuda.get_device_properties(device_idx).total_memory / 1e9
            reserved_mem = torch.cuda.memory_reserved(device_idx) / 1e9
            allocated_mem = torch.cuda.memory_allocated(device_idx) / 1e9
            
            info["cuda_total_memory_gb"] = round(total_mem, 2)
            info["cuda_reserved_memory_gb"] = round(reserved_mem, 2)
            info["cuda_allocated_memory_gb"] = round(allocated_mem, 2)
        
        self.device_info = info
        return info
    
    def print_device_info(self):
        """Pretty-print device information to logger."""
        info = self.get_device_info()
        if info["cuda_available"]:
            logger.info(f"GPU Device: {info['cuda_device_name']}")
            logger.info(f"Compute Capability: {info['cuda_compute_capability']}")
            logger.info(f"Total Memory: {info['cuda_total_memory_gb']} GB")
        else:
            logger.info("Using CPU (no CUDA available)")


class SeedManager:
    """Manages random seed for reproducibility across PyTorch, NumPy, and Python random."""
    
    @staticmethod
    def set_seed(seed: int = 42):
        """
        Set seed for all random number generators.
        
        Args:
            seed (int): Seed value. Default: 42
        """
        # Python random
        random.seed(seed)
        
        # NumPy
        np.random.seed(seed)
        
        # PyTorch
        torch.manual_seed(seed)
        
        # CUDA determinism
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            # Note: May impact performance slightly
            torch.backends.cudnn.deterministic = True
            torch.backends.cudnn.benchmark = False
        
        logger.info(f"Random seed set to {seed} (Python, NumPy, PyTorch, CUDA)")
    
    @staticmethod
    def get_seed_state() -> Dict[str, Any]:
        """
        Get current state of all random generators.
        
        Returns:
            dict: State information for reproducibility verification
        """
        return {
            "python_random_sample": random.random(),
            "numpy_random_sample": np.random.random(),
            "torch_random_sample": torch.rand(1).item(),
        }


class MemoryManager:
    """Manages GPU memory optimization and monitoring."""
    
    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """
        Get current memory usage.
        
        Returns:
            dict: Memory stats (allocated, reserved, free, percent)
        """
        if not torch.cuda.is_available():
            return {
                "device": "cpu",
                "memory_gb": None,
                "memory_percent": None
            }
        
        allocated = torch.cuda.memory_allocated() / 1e9
        reserved = torch.cuda.memory_reserved() / 1e9
        total = torch.cuda.get_device_properties(0).total_memory / 1e9
        free = total - allocated
        percent_used = (allocated / total) * 100
        
        return {
            "device": "cuda",
            "allocated_gb": round(allocated, 2),
            "reserved_gb": round(reserved, 2),
            "total_gb": round(total, 2),
            "free_gb": round(free, 2),
            "percent_used": round(percent_used, 2)
        }
    
    @staticmethod
    def log_memory_usage():
        """Log current memory usage to logger."""
        stats = MemoryManager.get_memory_usage()
        if stats["device"] == "cuda":
            logger.info(f"GPU Memory: {stats['allocated_gb']}/{stats['total_gb']} GB "
                       f"({stats['percent_used']}% used)")
        else:
            logger.info("Using CPU (no CUDA memory to report)")
    
    @staticmethod
    def clear_cache():
        """Clear GPU cache."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("GPU cache cleared")


class PyTorchConfig:
    """Central configuration for PyTorch models."""
    
    # Device settings
    DEVICE = "auto"  # 'auto' for auto-detect, 'cuda', or 'cpu'
    SEED = 42
    
    # Training defaults
    DEFAULT_BATCH_SIZE = 32
    DEFAULT_LEARNING_RATE = 1e-3
    DEFAULT_EPOCHS = 50
    DEFAULT_OPTIMIZER = "adam"
    DEFAULT_SCHEDULER = "reduce_on_plateau"
    
    # Focal loss hyperparameters
    FOCAL_LOSS_ALPHA = 0.25
    FOCAL_LOSS_GAMMA = 2.0
    
    # K-fold settings
    KFOLD_SPLITS = 5
    KFOLD_STRATIFIED = True
    KFOLD_SHUFFLE = True
    
    # Model architecture defaults
    LSTM_HIDDEN_SIZE = 128
    LSTM_NUM_LAYERS = 2
    LSTM_DROPOUT = 0.3
    
    CNN1D_OUT_CHANNELS = [32, 64]
    CNN1D_KERNEL_SIZE = 3
    CNN1D_DROPOUT = 0.2
    
    GAT_NUM_LAYERS = 2
    GAT_NUM_HEADS = 4
    GAT_OUT_CHANNELS = 64
    GAT_DROPOUT = 0.2
    
    # Training hyperparameters
    EARLY_STOPPING_PATIENCE = 10
    GRADIENT_CLIP_VALUE = 1.0
    WEIGHT_DECAY = 1e-5
    
    # Data settings
    FEATURE_DIM = 15
    SEQUENCE_LENGTH = 576
    NUM_SENSORS = 7000  # Railway stations/junctions


def get_device_manager() -> DeviceManager:
    """Factory function to get a configured DeviceManager."""
    manager = DeviceManager()
    manager.detect_cuda_device()
    return manager


def setup_pytorch_environment(seed: int = 42, verbose: bool = True) -> Tuple[torch.device, Dict[str, Any]]:
    """
    Complete PyTorch environment setup in one call.
    
    Args:
        seed (int): Random seed. Default: 42
        verbose (bool): Print setup info. Default: True
    
    Returns:
        tuple: (device, device_info_dict)
    """
    # Set seeds
    SeedManager.set_seed(seed)
    
    # Detect device
    device_mgr = get_device_manager()
    device = device_mgr.get_device()
    
    if verbose:
        device_mgr.print_device_info()
        MemoryManager.log_memory_usage()
    
    info = device_mgr.get_device_info()
    return device, info


if __name__ == "__main__":
    # Test setup
    logging.basicConfig(level=logging.INFO)
    device, info = setup_pytorch_environment(verbose=True)
    print(f"\nSetup complete. Device: {device}")
    print(f"Memory: {MemoryManager.get_memory_usage()}")
