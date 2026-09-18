"""
Training Harness for Phase 3 Temporal Models.
Phase 3.5.1: Complete training pipeline with early stopping, scheduling, checkpointing.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau
import logging
import json
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from collections import defaultdict
import numpy as np
from sklearn.metrics import roc_auc_score, confusion_matrix, f1_score, precision_score, recall_score

logger = logging.getLogger(__name__)


class TemporalModelTrainer:
    """
    Training harness for temporal models with full PyTorch integration.
    
    Features:
    - Epoch-based training and validation
    - Early stopping with patience
    - Learning rate scheduling
    - Model checkpointing (save best model)
    - Comprehensive metrics logging
    - Gradient clipping for stability
    """
    
    def __init__(
        self,
        model: nn.Module,
        train_loader,
        val_loader,
        device: torch.device,
        loss_fn: nn.Module,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        scheduler_factor: float = 0.1,
        scheduler_patience: int = 5,
        scheduler_min_lr: float = 1e-6,
        early_stopping_patience: int = 10,
        gradient_clip_value: float = 1.0,
        checkpoint_dir: Optional[str] = None,
    ):
        """
        Initialize trainer.
        
        Args:
            model (nn.Module): PyTorch model to train
            train_loader: Training dataloader
            val_loader: Validation dataloader
            device (torch.device): CPU or CUDA
            loss_fn (nn.Module): Loss function (e.g., FocalLoss)
            learning_rate (float): Initial LR. Default: 1e-3
            weight_decay (float): L2 regularization. Default: 1e-5
            scheduler_factor (float): LR reduction factor. Default: 0.1
            scheduler_patience (int): Patience for LR reduction. Default: 5
            scheduler_min_lr (float): Minimum LR. Default: 1e-6
            early_stopping_patience (int): Patience before stopping. Default: 10
            gradient_clip_value (float): Max gradient norm. Default: 1.0
            checkpoint_dir (str): Where to save checkpoints. Default: None
        """
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.loss_fn = loss_fn
        self.gradient_clip_value = gradient_clip_value
        self.checkpoint_dir = Path(checkpoint_dir) if checkpoint_dir else Path("./checkpoints")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Optimizer
        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        # Learning rate scheduler
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='max',  # Maximize validation AUC
            factor=scheduler_factor,
            patience=scheduler_patience,
            min_lr=scheduler_min_lr
        )
        
        # Early stopping
        self.early_stopping_patience = early_stopping_patience
        self.best_val_auc = 0.0
        self.patience_counter = 0
        self.should_stop = False
        
        # History tracking
        self.history = {
            'train_loss': [],
            'train_auc': [],
            'val_loss': [],
            'val_auc': [],
            'val_sensitivity': [],
            'val_specificity': [],
            'learning_rates': [],
        }
        
        logger.info(f"Trainer initialized:")
        logger.info(f"  Device: {device}")
        logger.info(f"  Optimizer: Adam (lr={learning_rate}, decay={weight_decay})")
        logger.info(f"  Scheduler: ReduceLROnPlateau (factor={scheduler_factor}, "
                   f"patience={scheduler_patience})")
        logger.info(f"  Early stopping patience: {early_stopping_patience}")
        logger.info(f"  Gradient clip value: {gradient_clip_value}")
    
    def train_epoch(self) -> Tuple[float, float]:
        """
        Train for one epoch.
        
        Returns:
            tuple: (avg_loss, avg_auc)
        """
        self.model.train()
        total_loss = 0.0
        all_targets = []
        all_predictions = []
        
        for batch_idx, (x, y) in enumerate(self.train_loader):
            x = x.to(self.device)
            y = y.to(self.device).float()
            
            # Forward pass
            self.optimizer.zero_grad()
            
            # Handle both hybrid models and simple models
            if isinstance(self.model, torch.nn.Module):
                # Check if model returns tuple (hybrid) or tensor
                output = self.model(x)
                if isinstance(output, tuple):
                    logits = output[0]
                else:
                    logits = output
            
            logits = logits.squeeze(-1)
            
            # Compute loss
            loss = self.loss_fn(logits, y)
            
            # Backward pass
            loss.backward()
            
            # Gradient clipping
            if self.gradient_clip_value is not None:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.gradient_clip_value)
            
            # Optimization step
            self.optimizer.step()
            
            # Tracking
            total_loss += loss.item()
            all_targets.append(y.cpu().detach().numpy())
            all_predictions.append(torch.sigmoid(logits).cpu().detach().numpy())
            
            if (batch_idx + 1) % 50 == 0 or (batch_idx + 1) == len(self.train_loader):
                logger.info(f"  Batch {batch_idx + 1}/{len(self.train_loader)}: loss={loss.item():.6f}")
        
        # Compute metrics
        avg_loss = total_loss / len(self.train_loader)
        all_targets = np.concatenate(all_targets, axis=0)
        all_predictions = np.concatenate(all_predictions, axis=0)
        
        # AUC only if we have both classes
        if len(np.unique(all_targets)) == 2:
            avg_auc = roc_auc_score(all_targets, all_predictions)
        else:
            avg_auc = 0.0
        
        return avg_loss, avg_auc
    
    def validate_epoch(self) -> Dict[str, float]:
        """
        Validate for one epoch.
        
        Returns:
            dict: Validation metrics
        """
        self.model.eval()
        total_loss = 0.0
        all_targets = []
        all_predictions = []
        
        with torch.no_grad():
            for x, y in self.val_loader:
                x = x.to(self.device)
                y = y.to(self.device).float()
                
                # Forward pass
                output = self.model(x)
                if isinstance(output, tuple):
                    logits = output[0]
                else:
                    logits = output
                
                logits = logits.squeeze(-1)
                
                # Compute loss
                loss = self.loss_fn(logits, y)
                
                total_loss += loss.item()
                all_targets.append(y.cpu().numpy())
                all_predictions.append(torch.sigmoid(logits).cpu().numpy())
        
        # Compute metrics
        avg_loss = total_loss / len(self.val_loader)
        all_targets = np.concatenate(all_targets, axis=0)
        all_predictions = np.concatenate(all_predictions, axis=0)
        
        # AUC
        if len(np.unique(all_targets)) == 2:
            auc = roc_auc_score(all_targets, all_predictions)
        else:
            auc = 0.0
        
        # Confusion matrix metrics
        y_pred_binary = (all_predictions > 0.5).astype(int)
        cm = confusion_matrix(all_targets, y_pred_binary)
        
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
            f1 = f1_score(all_targets, y_pred_binary, zero_division=0)
            precision = precision_score(all_targets, y_pred_binary, zero_division=0)
            recall = recall_score(all_targets, y_pred_binary, zero_division=0)
        else:
            sensitivity = specificity = f1 = precision = recall = 0
        
        metrics = {
            'loss': avg_loss,
            'auc': auc,
            'sensitivity': sensitivity,
            'specificity': specificity,
            'f1': f1,
            'precision': precision,
            'recall': recall,
        }
        
        return metrics
    
    def train_full(
        self,
        epochs: int = 50,
        verbose: bool = True,
    ) -> Tuple[nn.Module, Dict]:
        """
        Complete training loop with early stopping.
        
        Args:
            epochs (int): Maximum epochs. Default: 50
            verbose (bool): Print progress. Default: True
        
        Returns:
            tuple: (trained_model, history_dict)
        """
        logger.info(f"\nStarting training for {epochs} epochs...")
        logger.info(f"=" * 60)
        
        for epoch in range(1, epochs + 1):
            # Train
            train_loss, train_auc = self.train_epoch()
            
            # Validate
            val_metrics = self.validate_epoch()
            val_loss = val_metrics['loss']
            val_auc = val_metrics['auc']
            val_sensitivity = val_metrics['sensitivity']
            val_specificity = val_metrics['specificity']
            
            # Learning rate scheduling
            self.scheduler.step(val_auc)
            current_lr = self.optimizer.param_groups[0]['lr']
            
            # History
            self.history['train_loss'].append(train_loss)
            self.history['train_auc'].append(train_auc)
            self.history['val_loss'].append(val_loss)
            self.history['val_auc'].append(val_auc)
            self.history['val_sensitivity'].append(val_sensitivity)
            self.history['val_specificity'].append(val_specificity)
            self.history['learning_rates'].append(current_lr)
            
            # Logging
            if verbose or epoch % 5 == 0 or epoch == 1:
                logger.info(f"Epoch {epoch:3d}/{epochs} | "
                           f"Train: loss={train_loss:.6f}, auc={train_auc:.4f} | "
                           f"Val: loss={val_loss:.6f}, auc={val_auc:.4f} "
                           f"(sens={val_sensitivity:.4f}, spec={val_specificity:.4f}) | "
                           f"LR={current_lr:.2e}")
            
            # Early stopping logic
            if val_auc > self.best_val_auc:
                self.best_val_auc = val_auc
                self.patience_counter = 0
                
                # Save best model
                self.save_checkpoint(epoch, val_auc, 'best')
                logger.info(f"  >> New best AUC: {val_auc:.4f} (saved)")
            else:
                self.patience_counter += 1
                
                if self.patience_counter >= self.early_stopping_patience:
                    logger.info(f"Early stopping triggered (patience={self.early_stopping_patience})")
                    self.should_stop = True
                    break
        
        logger.info(f"=" * 60)
        logger.info(f"Training complete!")
        logger.info(f"Best validation AUC: {self.best_val_auc:.4f}")
        
        # Load best model before returning
        self.load_checkpoint('best')
        
        return self.model, self.history
    
    def save_checkpoint(self, epoch: int, val_auc: float, tag: str = ''):
        """Save model checkpoint."""
        if not self.checkpoint_dir.exists():
            self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        if tag:
            path = self.checkpoint_dir / f"model_{tag}.pt"
        else:
            path = self.checkpoint_dir / f"model_epoch{epoch:03d}.pt"
        
        torch.save({
            'epoch': epoch,
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'val_auc': val_auc,
        }, path)
        
        logger.info(f"  Checkpoint saved: {path}")
    
    def load_checkpoint(self, tag: str = 'best'):
        """Load model checkpoint."""
        if tag:
            path = self.checkpoint_dir / f"model_{tag}.pt"
        else:
            path = self.checkpoint_dir / f"model_{tag}.pt"
        
        if path.exists():
            checkpoint = torch.load(path, map_location=self.device)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            logger.info(f"Loaded checkpoint: {path}")
        else:
            logger.warning(f"Checkpoint not found: {path}")
    
    def save_history(self, output_path: str):
        """Save training history to JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.history, f, indent=2)
        
        logger.info(f"Training history saved to {output_path}")
    
    def get_best_metrics(self) -> Dict:
        """Get best validation metrics achieved."""
        best_epoch = np.argmax(self.history['val_auc'])
        
        return {
            'epoch': best_epoch + 1,
            'val_auc': float(self.history['val_auc'][best_epoch]),
            'val_loss': float(self.history['val_loss'][best_epoch]),
            'val_sensitivity': float(self.history['val_sensitivity'][best_epoch]),
            'val_specificity': float(self.history['val_specificity'][best_epoch]),
            'train_auc_at_best': float(self.history['train_auc'][best_epoch]),
        }


class EnsembleTrainer:
    """
    Phase 4: Ensemble Training Coordination
    
    Orchestrates training of multiple temporal models:
    - LSTM, CNN1D, Attention, GAT classifiers
    - Tracks per-model performance metrics
    - Coordinates checkpointing across ensemble
    - Provides ensemble-level analysis and comparison
    - Supports both sequential and parallel training modes
    
    Architecture:
        EnsembleTrainer (coordinator)
        ├── TemporalModelTrainer (LSTM)
        ├── TemporalModelTrainer (CNN1D)
        ├── TemporalModelTrainer (Attention)
        └── TemporalModelTrainer (GAT)
    """
    
    def __init__(
        self,
        device: torch.device = torch.device('cpu'),
        ensemble_checkpoint_dir: str = "./ensemble_checkpoints",
        registry_path: Optional[str] = None,
    ):
        """
        Initialize ensemble trainer.
        
        Args:
            device: torch.device for training
            ensemble_checkpoint_dir: Directory for ensemble-level checkpoints
            registry_path: Path to model registry JSON
        """
        self.device = device
        self.ensemble_checkpoint_dir = Path(ensemble_checkpoint_dir)
        self.registry_path = Path(registry_path) if registry_path else None
        
        self.model_trainers: Dict[str, TemporalModelTrainer] = {}
        self.model_histories: Dict[str, Dict] = {}
        self.ensemble_metrics: Dict = {
            'models_trained': [],
            'avg_val_auc': 0.0,
            'best_model': None,
            'worst_model': None,
            'variance_auc': 0.0,
            'timestamp': None,
        }
        
        self.ensemble_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"EnsembleTrainer initialized: {ensemble_checkpoint_dir}")
    
    def add_model_trainer(
        self,
        model_name: str,
        trainer: TemporalModelTrainer,
    ):
        """
        Register a model trainer in the ensemble.
        
        Args:
            model_name: Identifier for model (e.g., 'lstm', 'cnn1d', 'gat')
            trainer: TemporalModelTrainer instance for this model
        """
        self.model_trainers[model_name] = trainer
        logger.info(f"Added model to ensemble: {model_name}")
    
    def train_model(
        self,
        model_name: str,
        epochs: int = 5,
        verbose: bool = True,
    ) -> Tuple[nn.Module, Dict]:
        """
        Train a single model in the ensemble.
        
        Args:
            model_name: Model identifier (must be registered via add_model_trainer)
            epochs: Number of epochs
            verbose: Print epoch-level metrics
            
        Returns:
            Tuple of (trained_model, training_history)
        """
        if model_name not in self.model_trainers:
            raise ValueError(f"Model '{model_name}' not registered. Available: {list(self.model_trainers.keys())}")
        
        trainer = self.model_trainers[model_name]
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Training model: {model_name.upper()}")
        logger.info(f"{'='*70}")
        
        trained_model, history = trainer.train_full(epochs=epochs, verbose=verbose)
        
        self.model_histories[model_name] = {
            'history': history,
            'best_metrics': trainer.get_best_metrics(),
        }
        
        logger.info(f"✓ {model_name} training complete")
        logger.info(f"  Best AUC: {trainer.get_best_metrics()['val_auc']:.4f}")
        
        return trained_model, history
    
    def train_ensemble(
        self,
        epochs: int = 5,
        verbose: bool = True,
        model_names: Optional[List[str]] = None,
    ) -> Dict[str, Tuple[nn.Module, Dict]]:
        """
        Train all models in ensemble sequentially.
        
        Args:
            epochs: Number of epochs per model
            verbose: Print metrics
            model_names: Specific models to train (None = all)
            
        Returns:
            Dict mapping model_name -> (trained_model, history)
        """
        if not self.model_trainers:
            raise ValueError("No models registered in ensemble")
        
        if model_names is None:
            model_names = list(self.model_trainers.keys())
        
        results = {}
        
        logger.info(f"\n{'='*70}")
        logger.info(f"ENSEMBLE TRAINING: {len(model_names)} models")
        logger.info(f"{'='*70}\n")
        
        for model_name in model_names:
            if model_name not in self.model_trainers:
                logger.warning(f"Model '{model_name}' not found, skipping")
                continue
            
            model, history = self.train_model(model_name, epochs=epochs, verbose=verbose)
            results[model_name] = (model, history)
        
        # Compute ensemble statistics
        self._compute_ensemble_metrics()
        
        logger.info(f"\n{'='*70}")
        logger.info("ENSEMBLE TRAINING COMPLETE")
        logger.info(f"{'='*70}\n")
        self._print_ensemble_summary()
        
        return results
    
    def _compute_ensemble_metrics(self):
        """Compute ensemble-level statistics across all trained models."""
        if not self.model_histories:
            logger.warning("No model histories to compute ensemble metrics")
            return
        
        val_aucs = []
        for model_name, model_data in self.model_histories.items():
            auc = model_data['best_metrics']['val_auc']
            val_aucs.append((model_name, auc))
        
        val_aucs_sorted = sorted(val_aucs, key=lambda x: x[1], reverse=True)
        best_model, best_auc = val_aucs_sorted[0]
        worst_model, worst_auc = val_aucs_sorted[-1]
        mean_auc = np.mean([auc for _, auc in val_aucs])
        var_auc = np.var([auc for _, auc in val_aucs])
        
        self.ensemble_metrics = {
            'models_trained': list(self.model_histories.keys()),
            'num_models': len(self.model_histories),
            'avg_val_auc': float(mean_auc),
            'best_model': best_model,
            'best_auc': float(best_auc),
            'worst_model': worst_model,
            'worst_auc': float(worst_auc),
            'variance_auc': float(var_auc),
            'std_auc': float(np.std([auc for _, auc in val_aucs])),
            'timestamp': str(np.datetime64('now')),
            'model_rankings': [
                {'rank': i+1, 'model': model, 'val_auc': float(auc)}
                for i, (model, auc) in enumerate(val_aucs_sorted)
            ]
        }
        
        logger.info("\nEnsemble Metrics Computed:")
        logger.info(f"  Num models: {self.ensemble_metrics['num_models']}")
        logger.info(f"  Mean AUC: {self.ensemble_metrics['avg_val_auc']:.4f}")
        logger.info(f"  Std AUC: {self.ensemble_metrics['std_auc']:.4f}")
        logger.info(f"  Best: {best_model} ({best_auc:.4f})")
        logger.info(f"  Worst: {worst_model} ({worst_auc:.4f})")
    
    def _print_ensemble_summary(self):
        """Print formatted ensemble performance summary."""
        if not self.ensemble_metrics.get('model_rankings'):
            return
        
        print("\n" + "="*70)
        print("ENSEMBLE PERFORMANCE SUMMARY")
        print("="*70)
        print(f"\nModels trained: {len(self.ensemble_metrics['models_trained'])}")
        print(f"Mean Val AUC: {self.ensemble_metrics['avg_val_auc']:.4f} +/- {self.ensemble_metrics['std_auc']:.4f}")
        print(f"\nModel Rankings (by Val AUC):")
        print("-" * 70)
        
        for ranking in self.ensemble_metrics['model_rankings']:
            model_name = ranking['model']
            auc = ranking['val_auc']
            status = "[BEST]" if ranking['rank'] == 1 else ""
            print(f"  {ranking['rank']}. {model_name.upper():12} > AUC: {auc:.4f}  {status}")
        
        print("-" * 70)
        print()
    
    def save_ensemble_checkpoint(self, tag: str = ""):
        """
        Save checkpoints for all models in ensemble.
        
        Args:
            tag: Optional tag for checkpoint (e.g., "phase4_complete")
        """
        # Convert numpy types to native Python types for JSON serialization
        def convert_for_json(obj):
            """Convert numpy types to native Python types."""
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_for_json(v) for v in obj]
            return obj
        
        checkpoint_data = {
            'ensemble_metrics': convert_for_json(self.ensemble_metrics),
            'model_histories': convert_for_json(self.model_histories),
            'num_models': len(self.model_trainers),
            'models': {},
        }
        
        # Reference each model's best checkpoint
        for model_name, trainer in self.model_trainers.items():
            checkpoint_path = trainer.checkpoint_dir / "model_best.pt"
            checkpoint_data['models'][model_name] = str(checkpoint_path)
            logger.info(f"Referenced checkpoint for {model_name}: {checkpoint_path}")
        
        # Save ensemble metadata
        metadata_path = self.ensemble_checkpoint_dir / f"ensemble_metadata_{tag}.json"
        with open(metadata_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        logger.info(f"Ensemble checkpoint saved: {metadata_path}")
        return metadata_path
    
    def load_ensemble_checkpoint(self, checkpoint_dir: str):
        """
        Load ensemble checkpoint from directory.
        
        Args:
            checkpoint_dir: Directory containing ensemble checkpoint files
        """
        checkpoint_path = Path(checkpoint_dir)
        metadata_files = list(checkpoint_path.glob("ensemble_metadata_*.json"))
        
        if not metadata_files:
            logger.warning(f"No ensemble metadata found in {checkpoint_dir}")
            return
        
        metadata_path = metadata_files[-1]  # Load most recent
        
        with open(metadata_path, 'r') as f:
            checkpoint_data = json.load(f)
        
        self.ensemble_metrics = checkpoint_data['ensemble_metrics']
        self.model_histories = checkpoint_data['model_histories']
        
        logger.info(f"Ensemble checkpoint loaded: {metadata_path}")
        logger.info(f"  Models: {checkpoint_data['num_models']}")
        logger.info(f"  Mean Val AUC: {self.ensemble_metrics['avg_val_auc']:.4f}")
    
    def get_ensemble_metrics(self) -> Dict:
        """Get ensemble-level metrics."""
        return self.ensemble_metrics
    
    def get_model_comparison(self) -> Dict:
        """
        Get detailed comparison of all models in ensemble.
        
        Returns:
            Dict with per-model metrics and comparisons
        """
        comparison = {
            'num_models': len(self.model_histories),
            'models': {}
        }
        
        for model_name, model_data in self.model_histories.items():
            best_metrics = model_data['best_metrics']
            comparison['models'][model_name] = {
                'best_epoch': best_metrics['epoch'],
                'val_auc': best_metrics['val_auc'],
                'val_loss': best_metrics['val_loss'],
                'val_sensitivity': best_metrics['val_sensitivity'],
                'val_specificity': best_metrics['val_specificity'],
                'train_auc_at_best': best_metrics['train_auc_at_best'],
            }
        
        # Add statistics
        aucs = [m['val_auc'] for m in comparison['models'].values()]
        comparison['ensemble_stats'] = {
            'mean_auc': float(np.mean(aucs)),
            'std_auc': float(np.std(aucs)),
            'min_auc': float(np.min(aucs)),
            'max_auc': float(np.max(aucs)),
        }
        
        return comparison
    
    def export_ensemble_report(self, output_path: str = "ensemble_report.json"):
        """
        Export detailed ensemble training report.
        
        Args:
            output_path: Path for JSON report
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert numpy types to native Python types for JSON serialization
        def convert_for_json(obj):
            """Convert numpy types to native Python types."""
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_for_json(v) for v in obj]
            return obj
        
        report = {
            'ensemble_metrics': convert_for_json(self.ensemble_metrics),
            'model_comparison': convert_for_json(self.get_model_comparison()),
            'model_histories': convert_for_json(self.model_histories),
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Ensemble report exported: {output_path}")


def test_trainer():
    """Quick test of trainer."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    from backend.ml.models.lstm_classifier import LSTMTemporalClassifier
    from backend.ml.losses import FocalLoss
    
    # Mock data
    batch_size = 32
    seq_len = 576
    n_features = 15
    n_samples = 128
    
    X_train = torch.randn(n_samples, seq_len, n_features)
    y_train = torch.randint(0, 2, (n_samples,)).float()
    
    X_val = torch.randn(n_samples, seq_len, n_features)
    y_val = torch.randint(0, 2, (n_samples,)).float()
    
    # DataLoaders
    train_dataset = torch.utils.data.TensorDataset(X_train, y_train)
    val_dataset = torch.utils.data.TensorDataset(X_val, y_val)
    
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # Model and trainer
    device = torch.device('cpu')
    model = LSTMTemporalClassifier(input_size=n_features)
    loss_fn = FocalLoss(alpha=0.25, gamma=2.0)
    
    trainer = TemporalModelTrainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        loss_fn=loss_fn,
        learning_rate=1e-3,
        early_stopping_patience=3,
        checkpoint_dir="./test_checkpoints"
    )
    
    # Train
    print("\n" + "="*60)
    print("Testing TemporalModelTrainer (5 epochs)")
    print("="*60)
    
    trained_model, history = trainer.train_full(epochs=5, verbose=True)
    
    print(f"\n[OK] Training complete")
    print(f"  Best metrics: {trainer.get_best_metrics()}")


def test_ensemble_trainer():
    """Test Phase 4 ensemble trainer with multiple models."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    from backend.ml.models.lstm_classifier import LSTMTemporalClassifier
    from backend.ml.losses import FocalLoss
    
    print("\n" + "="*70)
    print("PHASE 4: ENSEMBLE TRAINING COORDINATION TEST")
    print("="*70 + "\n")
    
    # Mock data for all models
    batch_size = 32
    seq_len = 576
    n_features = 15
    n_samples = 100
    
    X_train = torch.randn(n_samples, seq_len, n_features)
    y_train = torch.randint(0, 2, (n_samples,)).float()
    
    X_val = torch.randn(n_samples, seq_len, n_features)
    y_val = torch.randint(0, 2, (n_samples,)).float()
    
    # DataLoaders
    train_dataset = torch.utils.data.TensorDataset(X_train, y_train)
    val_dataset = torch.utils.data.TensorDataset(X_val, y_val)
    
    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    device = torch.device('cpu')
    loss_fn = FocalLoss(alpha=0.25, gamma=2.0)
    
    # Initialize ensemble trainer
    ensemble = EnsembleTrainer(
        device=device,
        ensemble_checkpoint_dir="./phase4_ensemble_checkpoints"
    )
    
    # Train multiple models in ensemble
    model_configs = [
        {
            'name': 'lstm_model_1',
            'config': {'input_size': 15, 'hidden_size': 128, 'num_layers': 2},
        },
        {
            'name': 'lstm_model_2',
            'config': {'input_size': 15, 'hidden_size': 64, 'num_layers': 1},
        },
    ]
    
    print(f"Creating {len(model_configs)} models for ensemble training...\n")
    
    for model_cfg in model_configs:
        model = LSTMTemporalClassifier(**model_cfg['config'])
        
        trainer = TemporalModelTrainer(
            model=model,
            train_loader=train_loader,
            val_loader=val_loader,
            device=device,
            loss_fn=loss_fn,
            learning_rate=1e-3,
            early_stopping_patience=3,
            checkpoint_dir=f"./phase4_ensemble_checkpoints/{model_cfg['name']}"
        )
        
        ensemble.add_model_trainer(model_cfg['name'], trainer)
        logger.info(f"Added {model_cfg['name']} to ensemble")
    
    # Train all models in ensemble
    print("\n" + "="*70)
    print("Starting ensemble training (2 models x 5 epochs)...")
    print("="*70 + "\n")
    
    results = ensemble.train_ensemble(epochs=5, verbose=False)
    
    # Get ensemble metrics
    print("\n" + "="*70)
    print("ENSEMBLE ANALYSIS")
    print("="*70 + "\n")
    
    ensemble_metrics = ensemble.get_ensemble_metrics()
    print(f"Models trained: {ensemble_metrics['num_models']}")
    print(f"Mean Val AUC: {ensemble_metrics['avg_val_auc']:.4f} ± {ensemble_metrics['std_auc']:.4f}")
    print(f"Best model: {ensemble_metrics['best_model']} ({ensemble_metrics['best_auc']:.4f})")
    print(f"Worst model: {ensemble_metrics['worst_model']} ({ensemble_metrics['worst_auc']:.4f})")
    
    # Print detailed comparison
    comparison = ensemble.get_model_comparison()
    print(f"\nDetailed Model Comparison:")
    print("-" * 70)
    for model_name, metrics in comparison['models'].items():
        print(f"\n{model_name}:")
        print(f"  Best epoch: {metrics['best_epoch']}")
        print(f"  Val AUC: {metrics['val_auc']:.4f}")
        print(f"  Val Sensitivity: {metrics['val_sensitivity']:.4f}")
        print(f"  Val Specificity: {metrics['val_specificity']:.4f}")
    
    # Save ensemble checkpoint
    print("\n" + "="*70)
    print("Saving ensemble checkpoint...")
    checkpoint_path = ensemble.save_ensemble_checkpoint(tag="phase4_complete")
    print(f"Checkpoint saved: {checkpoint_path}")
    
    # Export report
    report_path = "phase4_ensemble_report.json"
    ensemble.export_ensemble_report(report_path)
    print(f"Report exported: {report_path}")
    
    print("\n" + "="*70)
    print("[OK] Phase 4 ensemble training complete!")
    print("="*70 + "\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "ensemble":
        test_ensemble_trainer()
    else:
        test_trainer()
