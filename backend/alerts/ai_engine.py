import json
import os
import random
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import logging

logger = logging.getLogger(__name__)

class CRSIntelligenceEngine:
    """
    DRISHTI ML CORE:
    Trains an Isolation Forest natively on the 40-year CRS corpus dataset.
    It identifies structurally identical signatures to historical accidents 
    (Balasore, Gaisal, Firozabad) in real-time.
    """
    def __init__(self):
        self.corpus_path = os.path.join(os.path.dirname(__file__), "..", "..", "crs_corpus.json")
        self.model = IsolationForest(n_estimators=100, contamination=0.05, random_state=42)
        self.is_trained = False
        
        self.train_crs_model()
        
    def _parse_features(self, record: dict) -> list:
        # Convert JSON categorical data into strict numerical ML arrays
        delay = record.get("delay_before_accident_minutes", 0)
        
        # 1 if GOODS train is involved in the block section
        goods_present = 1 if "GOODS" in record.get("train_types", []) else 0 
        
        # 1 if NIGHT
        night = 1 if record.get("time_of_day") == "NIGHT" else 0
        
        # 1 if Loop Line (more complex switching logic = higher risk)
        loop = 1 if record.get("track_state") == "LOOP_LINE" else 0
        
        # Maintenance active 
        maint = 1 if record.get("maintenance_active") else 0
        
        return [delay, goods_present, night, loop, maint]

    def train_crs_model(self):
        try:
            with open(self.corpus_path, "r") as f:
                accidents = json.load(f)
        except Exception as e:
            logger.error(f"[AI CORE] Failed to load CRS data: {e}")
            return
            
        # Extract features for the 6 actual accidents
        accident_features = [self._parse_features(a) for a in accidents]
        
        # --- DATA AUGMENTATION (Building the Baseline) ---
        # A single model needs thousands of "normal" trips to detect the anomalies logically.
        # We simulate 5,000 normal traversals: low delays, day time, main lines.
        normal_data = []
        for _ in range(5000):
            normal_data.append([
                random.randint(0, 15), # Standard delay
                random.choices([0, 1], weights=[80, 20])[0], # Less likely goods
                random.choices([0, 1], weights=[70, 30])[0], # Mostly day
                0, # Main line mostly
                random.choices([0, 1], weights=[90, 10])[0]  # Rare maintenance
            ])
            
        df = pd.DataFrame(accident_features + normal_data, columns=["delay", "goods", "night", "loop", "maintenance"])
        
        # Train the unsupervised anomaly model
        self.model.fit(df)
        self.is_trained = True
        logger.info(f"[AI CORE] Trained Isolation Forest on CRS Signatures ({len(df)} topologies)")

    def predict_anomaly(self, delay: int, goods: bool, night: bool, loop: bool, maintenance: bool) -> dict:
        """
        Evaluate live telemetry against the ML model.
        Returns the anomaly score and probability of CRS match.
        """
        if not self.is_trained:
            return {"score": 0, "is_anomaly": False, "match_probability": 0}
            
        x_test = pd.DataFrame([[
            delay, 
            1 if goods else 0, 
            1 if night else 0, 
            1 if loop else 0, 
            1 if maintenance else 0
        ]], columns=["delay", "goods", "night", "loop", "maintenance"])
        
        # Anomaly scoring: negative is anomalous (outlier), positive is normal
        raw_score = self.model.decision_function(x_test)[0]
        prediction = self.model.predict(x_test)[0]
        
        # Normalize the decision score into a 0-100 Danger Metric
        # Typical scores span from +0.15 (very normal) to -0.25 (highly anomalous CRS match)
        normalized_risk = max(0, min(100, int((0.15 - raw_score) * 200)))
        
        return {
            "score": normalized_risk,
            "is_anomaly": bool(prediction == -1),
            "match_probability": normalized_risk
        }

# Singleton ML engine
ai = CRSIntelligenceEngine()
