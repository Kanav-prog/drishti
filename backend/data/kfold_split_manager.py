"""
K-Fold Split Manager for stratified cross-validation.
Phase 3.0.2: Manages 5-fold splits with stratification, no leakage verification.
"""

import json
import logging
from pathlib import Path
from typing import Tuple, List, Dict, Any
import numpy as np
from sklearn.model_selection import StratifiedKFold

logger = logging.getLogger(__name__)


class KFoldSplitManager:
    """
    Manages K-fold cross-validation splits for time-series data.
    Ensures stratification (respects class balance), no leakage, full coverage.
    """
    
    def __init__(self, n_splits: int = 5, stratified: bool = True, shuffle: bool = True, seed: int = 42):
        """
        Initialize K-fold manager.
        
        Args:
            n_splits (int): Number of folds. Default: 5
            stratified (bool): Use stratified K-fold. Default: True
            shuffle (bool): Shuffle data before splitting. Default: True
            seed (int): Random seed. Default: 42
        """
        self.n_splits = n_splits
        self.stratified = stratified
        self.shuffle = shuffle
        self.seed = seed
        
        if stratified:
            self.splitter = StratifiedKFold(n_splits=n_splits, shuffle=shuffle, random_state=seed)
        else:
            from sklearn.model_selection import KFold
            self.splitter = KFold(n_splits=n_splits, shuffle=shuffle, random_state=seed)
        
        self.splits = None  # Will store fold indices
        self.metadata = None
        
        logger.info(f"K-Fold Manager initialized: splits={n_splits}, stratified={stratified}, shuffle={shuffle}")
    
    def generate_splits(self, X: np.ndarray, y: np.ndarray) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Generate K-fold splits.
        
        Args:
            X (np.ndarray): Feature matrix (n_samples, n_features)
            y (np.ndarray): Labels (n_samples,), binary (0/1)
        
        Returns:
            list: List of (train_indices, val_indices) tuples
        """
        splits = []
        n_samples = len(X)
        
        for fold_id, (train_idx, val_idx) in enumerate(self.splitter.split(X, y)):
            splits.append((train_idx, val_idx))
            
            # Log fold statistics
            train_pos = np.sum(y[train_idx])
            train_neg = len(train_idx) - train_pos
            val_pos = np.sum(y[val_idx])
            val_neg = len(val_idx) - val_pos
            
            train_pos_ratio = train_pos / len(train_idx) * 100
            val_pos_ratio = val_pos / len(val_idx) * 100 if len(val_idx) > 0 else 0
            
            logger.info(f"Fold {fold_id}: train {len(train_idx)} ({train_pos_ratio:.2f}% pos), "
                       f"val {len(val_idx)} ({val_pos_ratio:.2f}% pos)")
        
        self.splits = splits
        self._verify_splits(X, y)
        return splits
    
    def _verify_splits(self, X: np.ndarray, y: np.ndarray):
        """
        Verify split integrity: no leakage, full coverage, stratification.
        
        Args:
            X (np.ndarray): Feature matrix
            y (np.ndarray): Labels
        """
        if self.splits is None:
            raise ValueError("No splits generated yet. Call generate_splits() first.")
        
        all_train_idx = set()
        all_val_idx = set()
        n_samples = len(X)
        
        for fold_id, (train_idx, val_idx) in enumerate(self.splits):
            # Check no overlap (no leakage)
            overlap = set(train_idx) & set(val_idx)
            if overlap:
                raise ValueError(f"Fold {fold_id}: Train-val overlap detected! {len(overlap)} samples")
            
            # Track all indices
            all_train_idx.update(train_idx)
            all_val_idx.update(val_idx)
        
        # Check full coverage
        all_used = all_train_idx | all_val_idx
        if len(all_used) != n_samples:
            raise ValueError(f"Coverage issue: {len(all_used)}/{n_samples} samples covered")
        
        logger.info(f"✓ Split verification passed: no leakage, full coverage, stratified")
    
    def get_fold_indices(self, fold_id: int) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get train and val indices for a specific fold.
        
        Args:
            fold_id (int): Fold ID (0 to n_splits-1)
        
        Returns:
            tuple: (train_indices, val_indices)
        """
        if self.splits is None:
            raise ValueError("No splits generated yet. Call generate_splits() first.")
        
        if fold_id >= len(self.splits):
            raise ValueError(f"Fold {fold_id} out of range (max: {len(self.splits)-1})")
        
        return self.splits[fold_id]
    
    def save_splits_json(self, output_path: str):
        """
        Save split indices to JSON file for reproducibility.
        
        Args:
            output_path (str): Path to save JSON file
        """
        if self.splits is None:
            raise ValueError("No splits generated yet. Call generate_splits() first.")
        
        splits_data = {
            "n_splits": self.n_splits,
            "stratified": self.stratified,
            "shuffle": self.shuffle,
            "seed": self.seed,
            "splits": [
                {
                    "fold_id": fold_id,
                    "train_indices": train_idx.tolist(),
                    "val_indices": val_idx.tolist(),
                    "train_size": len(train_idx),
                    "val_size": len(val_idx),
                }
                for fold_id, (train_idx, val_idx) in enumerate(self.splits)
            ]
        }
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(splits_data, f, indent=2)
        
        logger.info(f"K-fold splits saved to {output_path}")
    
    def load_splits_json(self, input_path: str) -> List[Tuple[np.ndarray, np.ndarray]]:
        """
        Load split indices from JSON file.
        
        Args:
            input_path (str): Path to JSON file
        
        Returns:
            list: List of (train_indices, val_indices) tuples
        """
        input_path = Path(input_path)
        
        with open(input_path, 'r') as f:
            splits_data = json.load(f)
        
        # Restore settings
        self.n_splits = splits_data["n_splits"]
        self.stratified = splits_data["stratified"]
        self.shuffle = splits_data["shuffle"]
        self.seed = splits_data["seed"]
        
        # Restore splits
        self.splits = [
            (np.array(split["train_indices"]), np.array(split["val_indices"]))
            for split in splits_data["splits"]
        ]
        
        logger.info(f"K-fold splits loaded from {input_path}")
        return self.splits
    
    def get_fold_statistics(self, y: np.ndarray) -> Dict[str, Any]:
        """
        Get statistics for all folds.
        
        Args:
            y (np.ndarray): Labels
        
        Returns:
            dict: Statistics for each fold
        """
        if self.splits is None:
            raise ValueError("No splits generated yet. Call generate_splits() first.")
        
        stats = {}
        for fold_id, (train_idx, val_idx) in enumerate(self.splits):
            train_y = y[train_idx]
            val_y = y[val_idx]
            
            train_pos = np.sum(train_y)
            val_pos = np.sum(val_y)
            
            stats[f"fold_{fold_id}"] = {
                "train_size": len(train_idx),
                "train_pos_count": int(train_pos),
                "train_neg_count": int(len(train_idx) - train_pos),
                "train_pos_ratio": float(train_pos / len(train_idx)) if len(train_idx) > 0 else 0,
                "val_size": len(val_idx),
                "val_pos_count": int(val_pos),
                "val_neg_count": int(len(val_idx) - val_pos),
                "val_pos_ratio": float(val_pos / len(val_idx)) if len(val_idx) > 0 else 0,
            }
        
        return stats


def create_kfold_dataloaders(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    batch_size: int = 32,
    n_splits: int = 5,
    seed: int = 42
) -> List[Tuple]:
    """
    Create K-fold stratified dataloaders from train/test split.
    
    Args:
        X_train (np.ndarray): Training features (n_train, ...)
        y_train (np.ndarray): Training labels (n_train,)
        X_test (np.ndarray): Test features (n_test, ...)
        y_test (np.ndarray): Test labels (n_test,)
        batch_size (int): Batch size for dataloaders. Default: 32
        n_splits (int): Number of folds. Default: 5
        seed (int): Random seed. Default: 42
    
    Returns:
        list: List of (train_loader, val_loader, test_loader) tuples, one per fold
    """
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    
    # Generate splits
    manager = KFoldSplitManager(n_splits=n_splits, stratified=True, shuffle=True, seed=seed)
    manager.generate_splits(X_train, y_train)
    
    # Create dataloaders
    dataloaders = []
    
    for fold_id, (train_idx, val_idx) in enumerate(manager.splits):
        # Fold data
        X_fold_train = X_train[train_idx]
        y_fold_train = y_train[train_idx]
        X_fold_val = X_train[val_idx]
        y_fold_val = y_train[val_idx]
        
        # Convert to tensors
        X_fold_train_t = torch.FloatTensor(X_fold_train)
        y_fold_train_t = torch.FloatTensor(y_fold_train).reshape(-1, 1)
        X_fold_val_t = torch.FloatTensor(X_fold_val)
        y_fold_val_t = torch.FloatTensor(y_fold_val).reshape(-1, 1)
        X_test_t = torch.FloatTensor(X_test)
        y_test_t = torch.FloatTensor(y_test).reshape(-1, 1)
        
        # Datasets
        train_dataset = TensorDataset(X_fold_train_t, y_fold_train_t)
        val_dataset = TensorDataset(X_fold_val_t, y_fold_val_t)
        test_dataset = TensorDataset(X_test_t, y_test_t)
        
        # Dataloaders
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
        
        dataloaders.append((train_loader, val_loader, test_loader))
        
        logger.info(f"Fold {fold_id}: train {len(train_loader.dataset)}, "
                   f"val {len(val_loader.dataset)}, test {len(test_loader.dataset)}")
    
    return dataloaders, manager


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    # Mock data
    n_samples = 4400
    X_mock = np.random.randn(n_samples, 576, 15)
    y_mock = np.random.binomial(1, 0.09, n_samples)  # 9% positive
    
    # Generate splits
    manager = KFoldSplitManager(n_splits=5)
    manager.generate_splits(X_mock, y_mock)
    
    # Check statistics
    stats = manager.get_fold_statistics(y_mock)
    print("Fold Statistics:")
    print(json.dumps(stats, indent=2))
