"""
Phase 2.1: Extract 15 engineered features from telemetry windows

Features:
- Raw (2): delay_minutes, speed_kmh
- Derived (3): delay_trend, acceleration, jitter
- Semantic (4): embedding (384-dim) + maintenance signal + signal_state + track_state
- Control (6): time_of_day, station_code, train_bunching, centrality, zone, historical_departure_delay

Goal: Create rich feature matrix (576, 15) enabling LSTM/1D-CNN to learn multimodal patterns
"""

import logging
import pandas as pd
import numpy as np
from typing import Tuple, Dict, List, Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.data.crs_parser import CRSParser
from backend.ml.embeddings import AccidentEmbeddingGenerator

logger = logging.getLogger(__name__)


class TimeSeriesFeatureExtractor:
    """Extract and engineer 15 features from 48-hour telemetry windows"""
    
    # Feature specification
    FEATURES = [
        # Raw telemetry (2)
        'delay_minutes',
        'speed_kmh',
        # Derived signals (3)
        'delay_trend',           # Rate of change of delay (min/5min)
        'delay_acceleration',    # 2nd derivative of delay
        'delay_jitter',          # Volatility/std of delay
        # Semantic features (3)
        'maintenance_active',    # Binary: 0/1
        'signal_state_encoded',  # Categorical: GREEN/YELLOW/RED/ERROR/RED_OVERSHOT
        'track_state_encoded',   # Categorical: MAIN/LOOP/SIDING
        # Embedding (would be 384, but we'll encode as single score for now)
        'embedding_similarity',  # Similarity to historical accidents (0-1)
        # Contextual (4)
        'time_of_day_encode',    # Binary: DAY/NIGHT
        'hour_of_day',           # 0-23
        'station_centrality',    # Junction importance (0-1)
        'adjacent_train_delay',  # Delay on intersecting track
    ]
    
    NUM_FEATURES = len(FEATURES)
    
    def __init__(self):
        """Initialize with CRS parser for embeddings"""
        logger.info("Initializing TimeSeriesFeatureExtractor")
        self.parser = CRSParser()
        
        # Load embeddings
        try:
            self.embedding_gen = AccidentEmbeddingGenerator()
            self.embedding_gen.batch_embed_from_corpus()
            self.embeddings_available = True
            logger.info("✓ Embeddings loaded")
        except Exception as e:
            logger.warning(f"Embeddings not available: {e}")
            self.embeddings_available = False
    
    def extract_raw_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract raw telemetry features"""
        features = pd.DataFrame()
        
        # Handle both dict and DataFrame inputs
        if isinstance(df, dict):
            features['delay_minutes'] = pd.Series(df.get('delay_minutes', [0])).fillna(0)
            features['speed_kmh'] = pd.Series(df.get('speed_kmh', [0])).fillna(0)
        else:
            features['delay_minutes'] = df.get('delay_minutes', pd.Series([0])).fillna(0)
            features['speed_kmh'] = df.get('speed_kmh', pd.Series([0])).fillna(0)
        
        return features
    
    def extract_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute derived temporal features"""
        features = pd.DataFrame()
        
        # Handle both dict and DataFrame inputs
        if isinstance(df, dict):
            delay = np.array(df.get('delay_minutes', [])) if isinstance(df.get('delay_minutes'), list) else df.get('delay_minutes', 0)
        else:
            delay = df['delay_minutes'].values if 'delay_minutes' in df.columns else np.zeros(len(df))
        
        if np.isscalar(delay):
            delay = np.array([delay] * 576)
        
        # Trend: rate of change of delay
        delay_diff = np.diff(delay, prepend=delay[0])  # Handle first element
        features['delay_trend'] = delay_diff
        
        # Acceleration: 2nd derivative (rate of trend change)
        trend_diff = np.diff(delay_diff, prepend=delay_diff[0])
        features['delay_acceleration'] = trend_diff
        
        # Jitter: rolling standard deviation (volatility)
        window = 12  # ~1 hour at 5-min intervals
        features['delay_jitter'] = delay.copy()
        for i in range(len(delay)):
            start = max(0, i - window)
            features.loc[i, 'delay_jitter'] = np.std(delay[start:i+1])
        
        return features
    
    def extract_semantic_features(
        self,
        df: pd.DataFrame,
        accident_metadata: Dict
    ) -> pd.DataFrame:
        """Extract semantic/categorical features"""
        features = pd.DataFrame()
        
        # Maintenance active (constant across window)
        maintenance = float(accident_metadata.get('maintenance_active', False))
        features['maintenance_active'] = maintenance
        
        # Signal state (categorical encoding)
        signal_state_map = {
            'GREEN': 0.2,
            'YELLOW': 0.5,
            'RED': 0.8,
            'ERROR': 0.9,
            'RED_OVERSHOT': 1.0
        }
        signal_state = accident_metadata.get('signal_state', 'GREEN')
        features['signal_state_encoded'] = signal_state_map.get(signal_state, 0.2)
        
        # Track state (categorical encoding)
        track_state_map = {
            'MAIN_LINE': 0.3,
            'LOOP_LINE': 0.6,
            'SIDING': 0.9
        }
        track_state = accident_metadata.get('track_state', 'MAIN_LINE')
        features['track_state_encoded'] = track_state_map.get(track_state, 0.3)
        
        return features
    
    def extract_embedding_features(
        self,
        accident_id: str
    ) -> np.ndarray:
        """
        Get embedding similarity for accident.
        
        Returns: Scalar similarity score (0-1) to average of corpus
        """
        if not self.embeddings_available:
            logger.warning(f"Embeddings not available for {accident_id}")
            return 0.5  # Default neutral score
        
        try:
            cache = self.embedding_gen.embedding_cache
            if accident_id not in cache:
                logger.debug(f"{accident_id} not in embedding cache")
                return 0.5
            
            # Get embedding for this accident
            query_emb = cache[accident_id]['embedding']
            
            # Average similarity to all other accidents
            similarities = []
            for other_id, data in cache.items():
                if other_id != accident_id:
                    sim = np.dot(query_emb, data['embedding'])
                    similarities.append(sim)
            
            if similarities:
                avg_sim = np.mean(similarities)
                return float(avg_sim)
            else:
                return 0.5
        
        except Exception as e:
            logger.warning(f"Error computing embedding similarity: {e}")
            return 0.5
    
    def extract_contextual_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract contextual/temporal features"""
        features = pd.DataFrame()
        
        # Determine number of rows
        if isinstance(df, dict):
            n_rows = len(df.get('timestamp_utc', []))
            if n_rows == 0:
                n_rows = 576  # Default
            timestamps = df.get('timestamp_utc', [None] * n_rows)
        else:
            n_rows = len(df)
            timestamps = df.get('timestamp_utc', [None] * n_rows) if 'timestamp_utc' in df else [None] * n_rows
        
        # Handle timestamps
        if timestamps and timestamps[0] is not None:
            timestamps = pd.to_datetime(timestamps)
            hours = timestamps.dt.hour
        else:
            hours = np.zeros(n_rows)
        
        # Time of day encoding
        # NIGHT: 22:00-05:00, DAY: 06:00-21:00
        time_of_day = np.where((hours >= 22) | (hours <= 5), 0, 1)
        features['time_of_day_encode'] = time_of_day
        
        # Hour of day (0-23)
        features['hour_of_day'] = hours.values / 24.0 if hasattr(hours, 'values') else hours / 24.0
        
        # Station centrality (mock: based on zone if available)
        centrality = 0.6  # Placeholder
        features['station_centrality'] = centrality
        
        # Adjacent train delay (mock: second train mean delay)
        if isinstance(df, dict):
            mean_delay = np.mean(df.get('delay_minutes', [0]))
        else:
            mean_delay = df.get('delay_minutes', pd.Series([0])).mean() if 'delay_minutes' in df else 0
        
        adjacent_delay = mean_delay * 0.8 / 100.0  # Normalize
        features['adjacent_train_delay'] = adjacent_delay
        
        return features
    
    def extract_all_features(
        self,
        df: pd.DataFrame,
        accident_id: str,
        accident_metadata: Dict
    ) -> np.ndarray:
        """
        Extract all 15 features for telemetry window.
        
        Args:
            df: Telemetry DataFrame or dict (576 rows, ~7 columns)
            accident_id: For embedding lookup
            accident_metadata: From CRS accident
            
        Returns:
            Feature matrix (576, 15)
        """
        logger.debug(f"Extracting 15 features for {accident_id}")
        
        # Convert dict to DataFrame if needed
        if isinstance(df, dict):
            df = pd.DataFrame(df)
        
        # Extract each feature group
        raw_feats = self.extract_raw_features(df)
        derived_feats = self.extract_derived_features(df)
        semantic_feats = self.extract_semantic_features(df, accident_metadata)
        
        # Embedding score (scalar, repeated 576 times)
        emb_score = self.extract_embedding_features(accident_id)
        embedding_feats = pd.DataFrame({
            'embedding_similarity': [emb_score] * len(df)
        })
        
        # Contextual features
        contextual_feats = self.extract_contextual_features(df)
        
        # Combine all
        all_feats = pd.concat(
            [raw_feats, derived_feats, semantic_feats, embedding_feats, contextual_feats],
            axis=1
        )
        
        # Reorder to match FEATURES spec
        all_feats = all_feats[self.FEATURES]
        
        # Validate
        assert all_feats.shape[0] == len(df), "Feature rows mismatch"
        assert all_feats.shape[1] == self.NUM_FEATURES, f"Expected {self.NUM_FEATURES} features, got {all_feats.shape[1]}"
        assert not all_feats.isna().any().any(), "NaN values in features"
        
        return all_feats.values


def main():
    """Development/testing"""
    logging.basicConfig(level=logging.INFO)
    
    extractor = TimeSeriesFeatureExtractor()
    
    print(f"Feature list ({extractor.NUM_FEATURES} total):")
    for i, feat in enumerate(extractor.FEATURES, 1):
        print(f"  {i:2d}. {feat}")
    
    print(f"\n✓ Ready to extract features from telemetry windows")


if __name__ == "__main__":
    main()
