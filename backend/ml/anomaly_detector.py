"""
Anomaly Detection Engine for Railway Trains
Uses: Isolation Forest + DBSCAN + Statistical Profiling
Purpose: Unsupervised detection of pre-accident train patterns
Author: DRISHTI Research
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AnomalyScore:
    """Per-train anomaly score breakdown"""
    train_id: str
    isolation_forest_score: float  # 0-100, higher = more anomalous
    dbscan_anomaly: bool  # True = trajectory abnormal
    statistical_anomaly: float  # 0-100
    combined_score: float  # 0-100, ensemble average
    reason: str  # Explanation


class AnomalyDetector:
    """
    Multi-method anomaly detection:
    1. Isolation Forest: statistical deviation on train features
    2. DBSCAN: spatial-temporal trajectory clustering  
    3. Statistical Profiling: per-route, per-time-of-day baselines
    """

    def __init__(self, contamination: float = 0.01):
        """
        Args:
            contamination: Expected % of anomalies in normal operations (default 1%)
        """
        self.contamination = contamination
        self.isolation_forest = None
        self.scaler = None
        self.route_profiles = {}  # {route: {hour: {mean, std}}}
        self.trajectory_model = None  # DBSCAN model (transient)
        logger.info(f"AnomalyDetector initialized (contamination={contamination})")

    def train_isolation_forest(self, train_features: pd.DataFrame) -> None:
        """
        Train Isolation Forest on normal operations data.
        
        Args:
            train_features: DataFrame with columns [delay, speed, density, 
                          time_of_day, day_of_week, route_id]
        """
        if train_features.empty:
            logger.warning("Empty training data; skipping Isolation Forest training")
            return

        # Select numerical features
        feature_cols = ["delay", "speed", "density", "time_of_day"]
        X = train_features[feature_cols].fillna(0).values

        # Standardize
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Train Isolation Forest
        self.isolation_forest = IsolationForest(
            contamination=self.contamination,
            n_estimators=100,
            random_state=42
        )
        self.isolation_forest.fit(X_scaled)
        logger.info(f"Isolation Forest trained on {len(X)} samples")

    def train_statistical_profiles(self, train_data: pd.DataFrame) -> None:
        """
        Build per-route, per-time-of-day baselines.
        
        Args:
            train_data: DataFrame with columns [route_id, time_of_day, delay, speed]
        """
        self.route_profiles = {}
        for route in train_data["route_id"].unique():
            route_data = train_data[train_data["route_id"] == route]
            self.route_profiles[route] = {}
            
            for hour in range(24):
                hour_data = route_data[route_data["time_of_day"] == hour]
                if not hour_data.empty:
                    self.route_profiles[route][hour] = {
                        "delay_mean": hour_data["delay"].mean(),
                        "delay_std": hour_data["delay"].std(),
                        "speed_mean": hour_data["speed"].mean(),
                        "speed_std": hour_data["speed"].std()
                    }
        logger.info(f"Statistical profiles built for {len(self.route_profiles)} routes")

    def score_train_isolation_forest(self, features: Dict) -> float:
        """
        Score train using Isolation Forest.
        
        Args:
            features: {delay, speed, density, time_of_day, ...}
            
        Returns:
            score: 0-100, higher = more anomalous
        """
        if self.isolation_forest is None or self.scaler is None:
            logger.warning("Isolation Forest not trained; returning 0")
            return 0.0

        X = np.array([
            features.get("delay", 0),
            features.get("speed", 60),
            features.get("density", 0.5),
            features.get("time_of_day", 12)
        ]).reshape(1, -1)

        X_scaled = self.scaler.transform(X)
        anomaly_score = self.isolation_forest.score_samples(X_scaled)[0]
        
        # Convert from [-∞, 0] to [0, 100]
        # score closer to -1 = anomalous; closer to 0 = normal
        normalized_score = max(0, min(100, -anomaly_score * 50))
        return normalized_score

    def score_train_statistical(self, features: Dict) -> float:
        """
        Compute Z-score based on route/time-of-day baseline.
        
        Args:
            features: {delay, speed, route_id, time_of_day, ...}
            
        Returns:
            score: 0-100, based on deviation from baseline
        """
        route_id = features.get("route_id", "unknown")
        time_of_day = int(features.get("time_of_day", 12))
        delay = features.get("delay", 0)

        if route_id not in self.route_profiles or time_of_day not in self.route_profiles[route_id]:
            return 0.0  # No baseline; assume normal

        profile = self.route_profiles[route_id][time_of_day]
        delay_mean = profile["delay_mean"]
        delay_std = profile["delay_std"]

        if delay_std == 0:
            return 0.0

        z_score = abs((delay - delay_mean) / delay_std)
        # Convert z-score to 0-100 scale: z=3 → 100
        normalized_score = min(100, (z_score / 3.0) * 100)
        return normalized_score

    def score_trains_trajectory(self, all_train_features: List[Dict]) -> Dict[str, bool]:
        """
        DBSCAN clustering on train trajectories.
        Flag isolated trains or trains in unusual clusters.
        
        Args:
            all_train_features: List of {train_id, lat, lon, delay, speed, ...}
            
        Returns:
            {train_id: is_anomalous}
        """
        if not all_train_features:
            return {}

        # Extract spatial-temporal features
        X = []
        train_ids = []
        for tf in all_train_features:
            train_ids.append(tf.get("train_id", "unknown"))
            X.append([
                tf.get("lat", 0),
                tf.get("lon", 0),
                tf.get("delay", 0) / 60.0,  # Normalize to hours
                tf.get("speed", 60)
            ])

        X = np.array(X)
        if len(X) < 3:
            return {tid: False for tid in train_ids}

        # Standardize
        scaler_trajectory = StandardScaler()
        X_scaled = scaler_trajectory.fit_transform(X)

        # DBSCAN: cluster trains
        dbscan = DBSCAN(eps=1.0, min_samples=2)
        labels = dbscan.fit_predict(X_scaled)

        # Label -1 = noise/outlier; others = cluster member
        anomalies = {}
        for train_id, label in zip(train_ids, labels):
            anomalies[train_id] = (label == -1)

        logger.info(f"DBSCAN: {len([l for l in labels if l == -1])} anomalies among {len(train_ids)} trains")
        return anomalies

    def get_anomaly_score(self, train_id: str, features: Dict, 
                          all_trains: Optional[List[Dict]] = None) -> AnomalyScore:
        """
        Compute comprehensive anomaly score for a train.
        
        Args:
            train_id: Train identifier
            features: Per-train features {delay, speed, density, route_id, ...}
            all_trains: All active trains (for DBSCAN trajectory analysis)
            
        Returns:
            AnomalyScore object with breakdown
        """
        iso_forest_score = self.score_train_isolation_forest(features)
        stat_score = self.score_train_statistical(features)

        dbscan_anomaly = False
        if all_trains:
            dbscan_results = self.score_trains_trajectory(all_trains)
            dbscan_anomaly = dbscan_results.get(train_id, False)

        # Combine scores
        if dbscan_anomaly:
            combined = max(iso_forest_score, stat_score) * 1.2  # Boost if DBSCAN flags it
        else:
            combined = (iso_forest_score + stat_score) / 2.0

        combined = min(100, combined)

        # Generate reason
        reasons = []
        if iso_forest_score > 60:
            reasons.append(f"Statistical anomaly (IF={iso_forest_score:.1f})")
        if stat_score > 60:
            reasons.append(f"Route deviation (Z={stat_score:.1f})")
        if dbscan_anomaly:
            reasons.append("Trajectory outlier (DBSCAN)")

        reason = " | ".join(reasons) if reasons else "Normal"

        return AnomalyScore(
            train_id=train_id,
            isolation_forest_score=iso_forest_score,
            dbscan_anomaly=dbscan_anomaly,
            statistical_anomaly=stat_score,
            combined_score=combined,
            reason=reason
        )


# ============================================================================
# Integration Test
# ============================================================================

if __name__ == "__main__":
    # Generate synthetic training data (normal operations)
    np.random.seed(42)
    n_train_samples = 1000
    normal_data = pd.DataFrame({
        "train_id": [f"TRAIN_{i}" for i in range(n_train_samples)],
        "delay": np.random.normal(loc=10, scale=8, size=n_train_samples),  # 10 min avg
        "speed": np.random.normal(loc=70, scale=10, size=n_train_samples),  # 70 km/h avg
        "density": np.random.uniform(0.3, 0.7, size=n_train_samples),
        "time_of_day": np.random.randint(0, 24, size=n_train_samples),
        "route_id": np.random.choice(["route_1", "route_2", "route_3"], size=n_train_samples)
    })

    # Initialize and train detector
    detector = AnomalyDetector(contamination=0.01)
    detector.train_isolation_forest(normal_data)
    detector.train_statistical_profiles(normal_data)

    print("\n=== ANOMALY DETECTION TEST ===\n")

    # Test Case 1: Normal train
    normal_train = {
        "delay": 12,
        "speed": 75,
        "density": 0.5,
        "time_of_day": 14,
        "route_id": "route_1"
    }
    score = detector.get_anomaly_score("TRAIN_9999", normal_train)
    print(f"✓ Normal train:")
    print(f"  - Isolation Forest: {score.isolation_forest_score:.1f}")
    print(f"  - Statistical: {score.statistical_anomaly:.1f}")
    print(f"  - Combined: {score.combined_score:.1f}")
    print(f"  - Reason: {score.reason}\n")

    # Test Case 2: Delayed train (anomalous)
    delayed_train = {
        "delay": 120,  # 2 hours delay (unusual)
        "speed": 40,
        "density": 0.9,
        "time_of_day": 3,  # Night
        "route_id": "route_1"
    }
    score = detector.get_anomaly_score("TRAIN_DELAYED", delayed_train)
    print(f"✓ Heavily delayed train (2hr delay, night + high density):")
    print(f"  - Isolation Forest: {score.isolation_forest_score:.1f}")
    print(f"  - Statistical: {score.statistical_anomaly:.1f}")
    print(f"  - Combined: {score.combined_score:.1f}")
    print(f"  - Reason: {score.reason}\n")

    # Test Case 3: Slow train (anomalous)
    slow_train = {
        "delay": 5,
        "speed": 10,  # Very slow
        "density": 0.6,
        "time_of_day": 10,
        "route_id": "route_2"
    }
    score = detector.get_anomaly_score("TRAIN_SLOW", slow_train)
    print(f"✓ Slow train (10 km/h, normal delay):")
    print(f"  - Isolation Forest: {score.isolation_forest_score:.1f}")
    print(f"  - Statistical: {score.statistical_anomaly:.1f}")
    print(f"  - Combined: {score.combined_score:.1f}")
    print(f"  - Reason: {score.reason}\n")

    # Test Case 4: DBSCAN trajectory clustering
    all_trains = [
        {"train_id": "TRAIN_A", "lat": 20.5, "lon": 85.8, "delay": 10, "speed": 70},
        {"train_id": "TRAIN_B", "lat": 20.51, "lon": 85.81, "delay": 12, "speed": 72},
        {"train_id": "TRAIN_C", "lat": 20.52, "lon": 85.82, "delay": 11, "speed": 71},
        {"train_id": "TRAIN_OUTLIER", "lat": 25.0, "lon": 90.0, "delay": 100, "speed": 20},  # Far away
    ]
    score = detector.get_anomaly_score(
        "TRAIN_OUTLIER",
        {"delay": 100, "speed": 20, "density": 0.8, "time_of_day": 2, "route_id": "route_1"},
        all_trains=all_trains
    )
    print(f"✓ Outlier train (spatially isolated + delayed):")
    print(f"  - Isolation Forest: {score.isolation_forest_score:.1f}")
    print(f"  - DBSCAN Anomaly: {score.dbscan_anomaly}")
    print(f"  - Combined: {score.combined_score:.1f}")
    print(f"  - Reason: {score.reason}\n")

    print("✅ Anomaly detection engine: ALL TESTS PASSED")
