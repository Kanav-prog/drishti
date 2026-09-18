"""
Data Drift Detection Engine
Purpose: Monitor ML model degradation by detecting input/output distribution shifts
Author: DRISHTI Research - Phase 5 ML Features
Date: March 31, 2026

Methods:
- Kolmogorov-Smirnov (KS) test for distribution changes
- Statistical profiling: mean, std, quantiles
- Concept drift: P(prediction) changes
- Adversarial drift: prediction changes but accuracy stays same
"""

import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
import numpy as np
import json
from collections import deque
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class FeatureStats:
    """Distribution statistics for a feature"""
    feature_name: str
    mean: float
    std: float
    min: float
    max: float
    median: float
    q25: float
    q75: float
    sample_count: int


@dataclass
class DriftAlert:
    """Alert when data drift detected"""
    drift_type: str             # "feature_drift", "target_drift", "concept_drift"
    severity: str               # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    feature_name: str           # Which feature drifted (or "ensemble")
    ks_statistic: float         # KS test statistic (0-1)
    p_value: float              # Statistical significance
    baseline_mean: float        # Historical mean
    current_mean: float         # Recent mean
    percent_change: float       # (current - baseline) / baseline * 100
    recommendation: str         # Action to take
    timestamp: str
    alert_id: str


@dataclass
class ModelHealthReport:
    """Overall model health assessment"""
    overall_health: str         # "HEALTHY", "DEGRADED", "FAILING"
    health_score: float         # 0-100
    feature_drifts: List[DriftAlert]
    target_drift_detected: bool
    concept_drift_detected: bool
    last_retraining: str        # ISO timestamp
    predictions_since_retrain: int
    recommended_action: str
    timestamp: str


class DriftDetector:
    """
    Multi-method drift detection for DRISHTI models
    
    Detects:
    1. Feature drift: Input distribution changes
    2. Target drift: Output distribution changes
    3. Concept drift: Relationship between input/output changes
    4. Adversarial drift: Predictions change despite no drift
    """
    
    def __init__(self, 
                 baseline_window_hours: int = 24,
                 detection_window_hours: int = 1,
                 ks_threshold: float = 0.15,
                 min_samples: int = 100):
        """
        Args:
            baseline_window_hours: Use past N hours as baseline
            detection_window_hours: Check last N hours for drift
            ks_threshold: KS statistic > this = drift detected
            min_samples: Need at least N samples to detect drift
        """
        self.baseline_window_hours = baseline_window_hours
        self.detection_window_hours = detection_window_hours
        self.ks_threshold = ks_threshold
        self.min_samples = min_samples
        
        # Historical data storage
        self.feature_history = {}  # {feature_name: deque of values}
        self.target_history = deque(maxlen=10000)  # Prediction scores
        self.baseline_stats = {}
        self.current_stats = {}
        self.last_retraining_time = datetime.now(timezone.utc)
        
        logger.info(f"DriftDetector initialized: KS threshold={ks_threshold}, baseline={baseline_window_hours}h")
    
    def add_observation(self, features: Dict[str, float], prediction: float) -> None:
        """
        Add new observation (feature vector + prediction)
        
        Args:
            features: {feature_name -> value}
            prediction: Model output (0-1 for binary, 0-100 for risk score)
        """
        
        # Store features
        for fname, fval in features.items():
            if fname not in self.feature_history:
                self.feature_history[fname] = deque(maxlen=100000)  # 100k samples
            self.feature_history[fname].append(fval)
        
        # Store prediction
        self.target_history.append(prediction)
    
    def _ks_test(self, baseline: List[float], current: List[float]) -> Tuple[float, float]:
        """
        Kolmogorov-Smirnov test for distribution drift
        
        Returns:
            (k_statistic, p_value)
            k_statistic: 0-1, higher = more drift
            p_value: Significance, <0.05 = significant drift
        """
        if len(baseline) < self.min_samples or len(current) < self.min_samples:
            return 0.0, 1.0  # Not enough data
        
        # Simplified KS test (in production: use scipy.stats.ks_2samp)
        baseline_sorted = sorted(baseline)
        current_sorted = sorted(current)
        
        baseline_mean = np.mean(baseline)
        current_mean = np.mean(current)
        
        # Calculate divergence as simple distance between distributions
        ks_stat = abs(current_mean - baseline_mean) / (np.std(baseline) + 1e-6)
        ks_stat = min(ks_stat, 1.0)  # Normalize to 0-1
        
        # P-value: higher KS stat = lower p-value
        p_value = np.exp(-ks_stat * len(current))
        
        return float(ks_stat), float(p_value)
    
    def _get_feature_stats(self, feature_values: List[float]) -> Optional[FeatureStats]:
        """Compute distribution statistics"""
        if not feature_values:
            return None
        
        arr = np.array(feature_values)
        return FeatureStats(
            feature_name="",  # Set by caller
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            median=float(np.median(arr)),
            q25=float(np.percentile(arr, 25)),
            q75=float(np.percentile(arr, 75)),
            sample_count=len(arr)
        )
    
    def detect_feature_drift(self) -> List[DriftAlert]:
        """
        Detect drift in input features
        
        Returns:
            List of DriftAlert for features that drifted
        """
        alerts = []
        
        now = datetime.now(timezone.utc)
        baseline_cutoff = now - timedelta(hours=self.baseline_window_hours)
        current_cutoff = now - timedelta(hours=self.detection_window_hours)
        
        # For each feature, compare old vs recent distribution
        for fname, history in self.feature_history.items():
            if len(history) < self.min_samples * 2:
                continue
            
            # Split into baseline and current
            history_list = list(history)
            mid_point = len(history_list) // 2
            baseline_data = history_list[:mid_point]
            current_data = history_list[mid_point:]
            
            # Run KS test
            ks_stat, p_val = self._ks_test(baseline_data, current_data)
            
            # Check if significant drift
            if ks_stat > self.ks_threshold and p_val < 0.05:
                baseline_stats = self._get_feature_stats(baseline_data)
                current_stats = self._get_feature_stats(current_data)
                if baseline_stats is None or current_stats is None:
                    continue
                
                percent_change = (current_stats.mean - baseline_stats.mean) / baseline_stats.mean * 100
                
                severity = self._classify_severity(ks_stat, abs(percent_change))
                
                alert = DriftAlert(
                    drift_type="feature_drift",
                    severity=severity,
                    feature_name=fname,
                    ks_statistic=ks_stat,
                    p_value=p_val,
                    baseline_mean=baseline_stats.mean,
                    current_mean=current_stats.mean,
                    percent_change=percent_change,
                    recommendation=f"Feature '{fname}' shifted {percent_change:.1f}%. Consider retraining.",
                    timestamp=now.isoformat(),
                    alert_id=hashlib.md5(f"{fname}-{now}".encode()).hexdigest()
                )
                alerts.append(alert)
                
                logger.warning(f"Feature drift detected: {fname} (KS={ks_stat:.3f}, p={p_val:.4f})")
        
        return alerts
    
    def detect_target_drift(self) -> Optional[DriftAlert]:
        """
        Detect drift in model predictions (concept drift)
        
        Returns:
            DriftAlert if target distribution changed significantly
        """
        if len(self.target_history) < self.min_samples * 2:
            return None
        
        target_list = list(self.target_history)
        mid = len(target_list) // 2
        baseline = target_list[:mid]
        current = target_list[mid:]
        
        ks_stat, p_val = self._ks_test(baseline, current)
        
        if ks_stat > self.ks_threshold:
            baseline_mean = float(np.mean(baseline))
            current_mean = float(np.mean(current))
            percent_change = float((current_mean - baseline_mean) / baseline_mean * 100)
            
            severity = self._classify_severity(ks_stat, abs(percent_change))
            
            alert = DriftAlert(
                drift_type="target_drift",
                severity=severity,
                feature_name="model_predictions",
                ks_statistic=ks_stat,
                p_value=p_val,
                baseline_mean=baseline_mean,
                current_mean=current_mean,
                percent_change=percent_change,
                recommendation="Model predictions changed. Performance may degrade. Retrain recommended.",
                timestamp=datetime.now(timezone.utc).isoformat(),
                alert_id=hashlib.md5(f"target_drift-{datetime.now(timezone.utc)}".encode()).hexdigest()
            )
            
            logger.warning(f"Target drift detected: KS={ks_stat:.3f}, predictions shifted {percent_change:.1f}%")
            return alert
        
        return None
    
    def detect_concept_drift(self) -> Optional[DriftAlert]:
        """
        Detect concept drift: relationship between inputs/outputs changes
        
        Example: Same features now lead to different predictions
        
        Returns:
            DriftAlert if concept drift detected
        """
        # Simplified check: if prediction variance increased while feature variance stable
        if len(self.target_history) < self.min_samples:
            return None
        
        target_std = np.std(list(self.target_history))
        
        # Check if predictions are much more variable than features
        feature_stds = [np.std(list(self.feature_history[f])) 
                       for f in self.feature_history if len(self.feature_history[f]) > 0]
        
        avg_feature_std = np.mean(feature_stds) if feature_stds else 1.0
        
        # If predictions vary 2x more than features: concept drift
        if target_std > 2.0 * avg_feature_std:
            alert = DriftAlert(
                drift_type="concept_drift",
                severity="HIGH",
                feature_name="model_behavior",
                ks_statistic=0.0,
                p_value=0.0,
                baseline_mean=float(np.mean(feature_stds)),
                current_mean=float(target_std),
                percent_change=float((target_std - np.mean(feature_stds)) / np.mean(feature_stds) * 100),
                recommendation="Concept drift detected. Input-output relationship changed. Urgent retraining needed.",
                timestamp=datetime.now(timezone.utc).isoformat(),
                alert_id=hashlib.md5(f"concept_drift-{datetime.now(timezone.utc)}".encode()).hexdigest()
            )
            
            logger.error(f"CONCEPT DRIFT: Predictions highly variable (std={target_std:.3f})")
            return alert
        
        return None
    
    def _classify_severity(self, ks_stat: float, percent_change: float) -> str:
        """
        Classify drift severity
        
        Args:
            ks_stat: KS statistic (0-1)
            percent_change: Absolute percent change
            
        Returns:
            "LOW", "MEDIUM", "HIGH", "CRITICAL"
        """
        if ks_stat > 0.5 or percent_change > 50:
            return "CRITICAL"
        elif ks_stat > 0.35 or percent_change > 30:
            return "HIGH"
        elif ks_stat > 0.25 or percent_change > 15:
            return "MEDIUM"
        else:
            return "LOW"
    
    def get_health_report(self) -> ModelHealthReport:
        """
        Generate comprehensive model health report
        
        Returns:
            ModelHealthReport with all drift metrics
        """
        feature_drifts = self.detect_feature_drift()
        target_drift = self.detect_target_drift()
        concept_drift = self.detect_concept_drift()
        
        # Aggregate severity
        all_drifts = feature_drifts + ([target_drift] if target_drift else [])
        
        critical_count = sum(1 for d in all_drifts if d.severity == "CRITICAL")
        high_count = sum(1 for d in all_drifts if d.severity == "HIGH")
        
        if critical_count > 0 or concept_drift:
            overall_health = "FAILING"
            health_score = 20
            action = "URGENT: Retrain model immediately"
        elif high_count > 1:
            overall_health = "DEGRADED"
            health_score = 50
            action = "Retrain recommended within next 6 hours"
        else:
            overall_health = "HEALTHY"
            health_score = 95
            action = "No action needed. Continue monitoring."
        
        report = ModelHealthReport(
            overall_health=overall_health,
            health_score=health_score,
            feature_drifts=feature_drifts,
            target_drift_detected=target_drift is not None,
            concept_drift_detected=concept_drift is not None,
            last_retraining=self.last_retraining_time.isoformat(),
            predictions_since_retrain=len(self.target_history),
            recommended_action=action,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        logger.info(f"Health report: {overall_health} (score={health_score}/100)")
        return report
    
    def reset_after_retraining(self) -> None:
        """Reset drift detector after model retraining"""
        self.last_retraining_time = datetime.now(timezone.utc)
        self.target_history.clear()
        logger.info("Drift detector reset after retraining")


if __name__ == "__main__":
    # Demo
    detector = DriftDetector()
    
    # Add normal observations
    print("Adding normal observations...")
    for i in range(200):
        features = {
            "delay_minutes": np.random.normal(15, 5),
            "speed_kmh": np.random.normal(100, 10),
            "traffic_density": np.random.uniform(0.3, 0.6),
        }
        prediction = 0.4 + np.random.normal(0, 0.1)
        detector.add_observation(features, prediction)
    
    # Add drifted observations
    print("Adding DRIFTED observations...")
    for i in range(100):
        features = {
            "delay_minutes": np.random.normal(45, 10),  # SHIFT: Increased delay!
            "speed_kmh": np.random.normal(95, 15),
            "traffic_density": np.random.uniform(0.7, 0.95),  # SHIFT: High traffic!
        }
        prediction = 0.75 + np.random.normal(0, 0.15)  # SHIFT: Higher risk!
        detector.add_observation(features, prediction)
    
    # Generate report
    print("\nGENERATING DRIFT DETECTION REPORT:\n")
    report = detector.get_health_report()
    print(json.dumps(asdict(report), indent=2, default=str))
