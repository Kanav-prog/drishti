"""
Drift Detection → Auto-Retraining
Background job monitors model drift
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DriftReport:
    """Drift detection result"""
    timestamp: str
    ks_statistic: float
    p_value: float
    drift_detected: bool
    recommendation: str


class DriftMonitoredRetrainer:
    """Background job: monitor drift, retrain if needed"""

    def __init__(self, recheck_interval_hours: int = 24):
        self.recheck_interval_hours = recheck_interval_hours
        self.baseline_predictions: Optional[List[float]] = None
        self.last_check = None

    async def monitor_and_retrain_loop(self):
        """Background task: check drift daily"""
        while True:
            try:
                # Wait for interval
                await asyncio.sleep(self.recheck_interval_hours * 3600)

                drift_report = self.compute_drift()

                if drift_report.drift_detected:
                    logger.warning(
                        f"[DRIFT] Detected! p-value={drift_report.p_value:.4f}. Retraining..."
                    )

                    new_model = await self._retrain_model()
                    if new_model:
                        from backend.ml.model_loader import model_loader
                        model_loader.isolation_forest = new_model
                        logger.info("[REPLAY] Model replaced with retrained version")
                else:
                    logger.info(
                        f"[DRIFT] No drift detected. p-value={drift_report.p_value:.4f}"
                    )

            except Exception as e:
                logger.error(f"[DRIFT] Monitor loop error: {e}")
                await asyncio.sleep(60)

    def compute_drift(self) -> DriftReport:
        """Compare recent predictions vs baseline using KS-test"""
        try:
            baseline = self.baseline_predictions or self._compute_baseline()
            recent = self._get_recent_predictions()

            if not baseline or not recent:
                return DriftReport(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    ks_statistic=0.0,
                    p_value=1.0,
                    drift_detected=False,
                    recommendation="No data for drift test",
                )

            # KS-test
            try:
                from scipy.stats import ks_2samp
                ks_stat, p_value = ks_2samp(baseline, recent)
            except:
                ks_stat = 0.0
                p_value = 1.0

            drift_detected = p_value < 0.05

            return DriftReport(
                timestamp=datetime.now(timezone.utc).isoformat(),
                ks_statistic=float(ks_stat),
                p_value=float(p_value),
                drift_detected=drift_detected,
                recommendation="Retrain" if drift_detected else "Keep current model",
            )

        except Exception as e:
            logger.error(f"[DRIFT] Compute error: {e}")
            return DriftReport(
                timestamp=datetime.now(timezone.utc).isoformat(),
                ks_statistic=0.0,
                p_value=1.0,
                drift_detected=False,
                recommendation=f"Error: {e}",
            )

    def _compute_baseline(self) -> List[float]:
        """Compute baseline anomaly scores from CRS data"""
        try:
            from backend.data.crs_loader import CRSLoader
            from backend.features.engineering import FeatureEngineer
            from backend.ml.model_loader import model_loader
            
            crs_loader = CRSLoader()
            accidents = crs_loader.load()
            feature_engineer = FeatureEngineer()

            features_list = [
                np.array(
                    list(
                        feature_engineer.engineer_all_features(
                            acc, accidents
                        ).values()
                    )
                )
                for acc in accidents[:100]
            ]

            if model_loader.isolation_forest and features_list:
                scores = model_loader.isolation_forest.score_samples(
                    np.array(features_list)
                )
                self.baseline_predictions = scores.tolist()
                return scores.tolist()

        except Exception as e:
            logger.warning(f"[DRIFT] Baseline computation error: {e}")

        return []

    def _get_recent_predictions(self) -> List[float]:
        """Get recent prediction scores (simulated)"""
        return (np.random.normal(-0.5, 0.5, 50)).tolist()

    async def _retrain_model(self):
        """Retrain model on latest data"""
        try:
            from backend.data.crs_loader import CRSLoader
            from backend.features.engineering import FeatureEngineer
            from sklearn.ensemble import IsolationForest
            
            crs_loader = CRSLoader()
            accidents = crs_loader.load()

            if not accidents:
                logger.warning("[RETRAIN] No CRS data available")
                return None

            feature_engineer = FeatureEngineer()
            features_list = [
                np.array(
                    list(
                        feature_engineer.engineer_all_features(
                            acc, accidents
                        ).values()
                    )
                )
                for acc in accidents
            ]

            X = np.array(features_list)
            new_model = IsolationForest(contamination=0.02, random_state=42)
            new_model.fit(X)

            logger.info(f"[RETRAIN] Model trained on {len(accidents)} samples")
            return new_model

        except Exception as e:
            logger.error(f"[RETRAIN] Error: {e}")
            return None


# Global retrainer
drift_retrainer = DriftMonitoredRetrainer()
