"""
Persistent Model Loader
Load on startup, train if missing
"""

from __future__ import annotations

import logging
import pickle
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class PersistentModelLoader:
    """Load trained models from artifacts or train fresh"""

    def __init__(self, artifact_dir: str = "models"):
        self.artifact_dir = Path(artifact_dir)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.isolation_forest: Optional[object] = None
        self.training_timestamp: Optional[datetime] = None

    def load_or_train_isolation_forest(self):
        """Load IF model or train fresh"""
        from sklearn.ensemble import IsolationForest
        
        artifact_path = self.artifact_dir / "isolation_forest_latest.pkl"

        # Try load
        if artifact_path.exists():
            file_age = (datetime.now() - datetime.fromtimestamp(artifact_path.stat().st_mtime)).days
            if file_age < 7:
                logger.info(f"[MODEL] Loading Isolation Forest ({file_age} days old)")
                try:
                    with open(artifact_path, "rb") as f:
                        self.isolation_forest = pickle.load(f)
                    self.training_timestamp = datetime.now(timezone.utc)
                    return self.isolation_forest
                except Exception as e:
                    logger.warning(f"[MODEL] Failed to load: {e}")

        # Train fresh
        logger.info("[MODEL] No recent model. Training Isolation Forest from CRS data...")
        
        try:
            from backend.data.crs_loader import CRSLoader
            from backend.features.engineering import FeatureEngineer
            
            crs_loader = CRSLoader()
            accidents = crs_loader.load()

            if not accidents:
                logger.warning("[MODEL] No CRS data found. Using synthetic baseline.")
                return self._create_synthetic_model()

            # Extract features
            feature_engineer = FeatureEngineer()
            features_list = [
                list(
                    feature_engineer.engineer_all_features(
                        acc, accidents, delay_minutes=getattr(acc, "pre_accident_delays_minutes", 0)
                    ).values()
                )
                for acc in accidents
            ]

            X = np.array(features_list)

            # Train
            model = IsolationForest(contamination=0.02, random_state=42, n_estimators=100)
            model.fit(X)

            # Save
            with open(artifact_path, "wb") as f:
                pickle.dump(model, f)

            logger.info(f"[MODEL] Trained and saved Isolation Forest ({len(accidents)} samples)")
            self.isolation_forest = model
            self.training_timestamp = datetime.now(timezone.utc)

            return model
            
        except Exception as e:
            logger.error(f"[MODEL] Training error: {e}")
            return self._create_synthetic_model()

    def _create_synthetic_model(self):
        """Fallback: train on synthetic data"""
        from sklearn.ensemble import IsolationForest
        
        logger.warning("[MODEL] Creating synthetic training data")

        # Generate synthetic normal + anomalous data
        normal = np.random.normal(0, 1, (500, 20))
        anomalies = np.random.uniform(-10, 10, (10, 20))
        X = np.vstack([normal, anomalies])

        model = IsolationForest(contamination=0.02, random_state=42)
        model.fit(X)

        return model

    def model_is_fresh(self, max_age_days: int = 7) -> bool:
        """Check if current model needs retraining"""
        if not self.training_timestamp:
            return False

        age = (datetime.now(timezone.utc) - self.training_timestamp).days
        return age < max_age_days


# Global loader
model_loader = PersistentModelLoader()
