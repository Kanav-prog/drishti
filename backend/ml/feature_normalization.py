"""
Phase 2.1 (Extended): Feature normalization and dataset loading

Standardizes features for neural network training.
Provides loaders compatible with PyTorch and TensorFlow.
"""

import logging
import json
import numpy as np
import pickle
from pathlib import Path
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from typing import Dict, Tuple, Optional, List
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


class FeatureNormalizer:
    """Normalize features to standard ranges for ML training"""
    
    def __init__(self):
        """Initialize scalers"""
        self.feature_scalers = {}
        self.fit_params = {}
    
    def fit(self, X: np.ndarray, feature_names: list):
        """Fit scalers on training data"""
        logger.info("Fitting feature normalization parameters...")
        
        assert X.shape[2] == len(feature_names), "Feature count mismatch"
        
        # Flatten to 2D (samples*timesteps, features)
        X_flat = X.reshape(-1, X.shape[2])
        
        # Standardize delay/trend features (center 0, std 1)
        delay_features = ['delay_minutes', 'delay_trend', 'delay_acceleration', 'delay_jitter']
        for feat in delay_features:
            if feat in feature_names:
                idx = feature_names.index(feat)
                scaler = StandardScaler()
                scaler.fit(X_flat[:, idx:idx+1])
                self.feature_scalers[feat] = scaler
                self.fit_params[feat] = {
                    'mean': float(scaler.mean_[0]),
                    'std': float(scaler.scale_[0])
                }
        
        # Min-max scale speed (0-1)
        if 'speed_kmh' in feature_names:
            idx = feature_names.index('speed_kmh')
            scaler = MinMaxScaler(feature_range=(0, 1))
            scaler.fit(X_flat[:, idx:idx+1])
            self.feature_scalers['speed_kmh'] = scaler
            self.fit_params['speed_kmh'] = {
                'min': float(scaler.data_min_[0]),
                'max': float(scaler.data_max_[0])
            }
        
        # No scaling for binary/categorical (already 0-1 or 0-1 encoded)
        categorical_features = ['maintenance_active', 'signal_state_encoded', 'track_state_encoded',
                               'embedding_similarity', 'time_of_day_encode']
        for feat in categorical_features:
            self.fit_params[feat] = {'min': 0, 'max': 1}
        
        logger.info(f"✓ Fitted normalizers for {len(self.feature_scalers)} features")
        return self
    
    def transform(self, X: np.ndarray, feature_names: list) -> np.ndarray:
        """Apply normalization"""
        X_norm = X.copy()
        
        # Reshape for scaling
        original_shape = X.shape
        X_flat = X.reshape(-1, X.shape[2])
        X_norm_flat = X_flat.copy()
        
        # Apply scalers
        for feat, scaler in self.feature_scalers.items():
            if feat in feature_names:
                idx = feature_names.index(feat)
                X_norm_flat[:, idx:idx+1] = scaler.transform(X_flat[:, idx:idx+1])
        
        # Reshape back
        X_norm = X_norm_flat.reshape(original_shape)
        
        return X_norm
    
    def save_config(self, output_path: str):
        """Save normalization config to JSON"""
        with open(output_path, 'w') as f:
            json.dump(self.fit_params, f, indent=2)
        logger.info(f"✓ Saved normalizer config to {output_path}")
    
    def load_config(self, config_path: str):
        """Load normalization config"""
        with open(config_path, 'r') as f:
            self.fit_params = json.load(f)
        logger.info(f"✓ Loaded normalizer config from {config_path}")


class TimeSeriesDatasetLoader:
    """Load dataset from HDF5 or NumPy format"""
    
    @staticmethod
    def load_from_npz(
        npz_path: str,
        split: str = 'train',
        normalize: bool = False
    ) -> Tuple[np.ndarray, np.ndarray, list]:
        """
        Load from NumPy compressed format.
        
        Args:
            npz_path: Path to .npz file
            split: 'train', 'val', 'test', or 'all'
            normalize: Apply standardization if True
            
        Returns:
            (X, y, feature_names)
        """
        logger.info(f"Loading from {npz_path} (split={split})")
        
        with np.load(npz_path, allow_pickle=True) as data:
            X = data['X']
            y = data['y']
            feature_names = list(data['feature_names'])
            
            train_idx = data['train_idx']
            val_idx = data['val_idx']
            test_idx = data['test_idx']
        
        # Select split
        if split == 'train':
            idx = train_idx
        elif split == 'val':
            idx = val_idx
        elif split == 'test':
            idx = test_idx
        else:
            idx = np.arange(len(X))
        
        X_split = X[idx]
        y_split = y[idx]
        
        logger.info(f"✓ Loaded {split}: X shape {X_split.shape}, y shape {y_split.shape}")
        
        # Normalize if requested
        if normalize:
            logger.info("Applying normalization...")
            normalizer = FeatureNormalizer()
            normalizer.fit(X_split, feature_names)
            X_split = normalizer.transform(X_split, feature_names)
        
        return X_split, y_split, feature_names
    
    @staticmethod
    def load_from_h5(
        h5_path: str,
        split: str = 'train',
        normalize: bool = False
    ) -> Tuple[np.ndarray, np.ndarray, list]:
        """
        Load from HDF5 format.
        
        Returns:
            (X, y, feature_names)
        """
        try:
            import h5py
        except ImportError:
            raise ImportError("h5py required for HDF5 loading")
        
        logger.info(f"Loading from {h5_path} (split={split})")
        
        with h5py.File(h5_path, 'r') as f:
            X = f['X'][:]
            y = f['y'][:]
            feature_names = list(f['feature_names'][:])
            
            train_idx = f['train_idx'][:]
            val_idx = f['val_idx'][:]
            test_idx = f['test_idx'][:]
            
            # Decode feature names if bytes
            feature_names = [f.decode() if isinstance(f, bytes) else f for f in feature_names]
        
        # Select split
        if split == 'train':
            idx = train_idx
        elif split == 'val':
            idx = val_idx
        elif split == 'test':
            idx = test_idx
        else:
            idx = np.arange(len(X))
        
        X_split = X[idx]
        y_split = y[idx]
        
        logger.info(f"✓ Loaded {split}: X shape {X_split.shape}, y shape {y_split.shape}")
        
        # Normalize if requested
        if normalize:
            logger.info("Applying normalization...")
            normalizer = FeatureNormalizer()
            normalizer.fit(X_split, feature_names)
            X_split = normalizer.transform(X_split, feature_names)
        
        return X_split, y_split, feature_names
    
    @staticmethod
    def get_pytorch_loader(
        X: np.ndarray,
        y: np.ndarray,
        batch_size: int = 32,
        shuffle: bool = True
    ):
        """
        Create PyTorch DataLoader (requires torch).
        
        With stratified batching (preserve class balance).
        """
        try:
            import torch
            from torch.utils.data import DataLoader, TensorDataset
        except ImportError:
            raise ImportError("PyTorch required for PyTorch loader")
        
        # Convert to tensors
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.LongTensor(y)
        
        # Create dataset
        dataset = TensorDataset(X_tensor, y_tensor)
        
        # Create loader with stratified sampler if shuffling
        if shuffle:
            from torch.utils.data import WeightedRandomSampler
            
            # Compute class weights (inverse of class frequency)
            class_counts = np.bincount(y)
            weights = 1.0 / class_counts[y]
            sampler = WeightedRandomSampler(
                weights=weights,
                num_samples=len(y),
                replacement=True
            )
            
            loader = DataLoader(dataset, batch_size=batch_size, sampler=sampler)
        else:
            loader = DataLoader(dataset, batch_size=batch_size, shuffle=False)
        
        return loader
    
    @staticmethod
    def get_kfold_pytorch_loaders(
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int = 5,
        batch_size: int = 32,
        seed: int = 42
    ) -> List[Tuple]:
        """
        Create K-fold stratified PyTorch DataLoaders.
        
        Args:
            X (np.ndarray): Feature matrix (n_samples, timesteps, features)
            y (np.ndarray): Labels (n_samples,), binary
            n_folds (int): Number of folds. Default: 5
            batch_size (int): Batch size. Default: 32
            seed (int): Random seed. Default: 42
        
        Returns:
            list: List of (train_loader, val_loader) tuples, one per fold
        """
        try:
            import torch
            from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
        except ImportError:
            raise ImportError("PyTorch required for PyTorch K-fold loaders")
        
        from backend.data.kfold_split_manager import KFoldSplitManager
        
        # Generate splits
        manager = KFoldSplitManager(n_splits=n_folds, stratified=True, shuffle=True, seed=seed)
        manager.generate_splits(X, y)
        
        # Create loaders
        fold_loaders = []
        
        for fold_id, (train_idx, val_idx) in enumerate(manager.splits):
            # Fold data
            X_train_fold = X[train_idx]
            y_train_fold = y[train_idx]
            X_val_fold = X[val_idx]
            y_val_fold = y[val_idx]
            
            # Convert to tensors
            X_train_t = torch.FloatTensor(X_train_fold)
            y_train_t = torch.LongTensor(y_train_fold)
            X_val_t = torch.FloatTensor(X_val_fold)
            y_val_t = torch.LongTensor(y_val_fold)
            
            # Datasets
            train_dataset = TensorDataset(X_train_t, y_train_t)
            val_dataset = TensorDataset(X_val_t, y_val_t)
            
            # Train loader with weighted sampling (balance classes)
            class_counts = np.bincount(y_train_fold)
            weights = 1.0 / class_counts[y_train_fold]
            sampler = WeightedRandomSampler(
                weights=weights,
                num_samples=len(y_train_fold),
                replacement=True
            )
            
            train_loader = DataLoader(train_dataset, batch_size=batch_size, sampler=sampler)
            val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
            
            fold_loaders.append((train_loader, val_loader))
            
            logger.info(f"K-fold {fold_id}: train {len(train_loader.dataset)}, "
                       f"val {len(val_loader.dataset)}, "
                       f"fold pos ratio: {y_train_fold.mean():.4f}")
        
        return fold_loaders, manager
    
    @staticmethod
    def create_tensorflow_dataset(
        X: np.ndarray,
        y: np.ndarray,
        batch_size: int = 32,
        shuffle: bool = True
    ):
        """
        Create TensorFlow Dataset (requires tensorflow).
        """
        try:
            import tensorflow as tf
        except ImportError:
            raise ImportError("TensorFlow required for TensorFlow dataset")
        
        # Create dataset
        dataset = tf.data.Dataset.from_tensor_slices((X, y))
        
        if shuffle:
            dataset = dataset.shuffle(buffer_size=1000)
        
        dataset = dataset.batch(batch_size)
        dataset = dataset.prefetch(tf.data.AUTOTUNE)
        
        return dataset


def main():
    """Testing"""
    logging.basicConfig(level=logging.INFO)
    
    print("Feature Normalizer & Dataset Loader ready")
    print(f"Supports: NumPy, HDF5, PyTorch, TensorFlow")


if __name__ == "__main__":
    main()
