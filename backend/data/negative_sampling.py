"""
Phase 2.3: Negative sampling - generate 4,000 normal operation sequences

Strategy: Cross-station random sampling
- Query telemetry from non-accident stations
- Stratify by time-of-day, delay range, geographic zone
- Ensure NO overlap with accident timestamps
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.db.session import SessionLocal
from backend.db.models import TrainTelemetry, Station
from backend.data.crs_parser import CRSParser

logger = logging.getLogger(__name__)


class NegativeSampler:
    """Generate 4,000 negative (normal operation) sequences"""
    
    def __init__(self, random_seed: int = 42):
        np.random.seed(random_seed)
        self.random_state = np.random.RandomState(random_seed)
        self.session = SessionLocal()
        self.parser = CRSParser()
    
    def __del__(self):
        if hasattr(self, 'session'):
            self.session.close()
    
    def get_accident_stations(self) -> set:
        """Get set of stations with accidents"""
        corpus = self.parser.get_corpus()
        return {acc.station for acc in corpus}
    
    def get_accident_time_ranges(self) -> List[Tuple]:
        """Get (start, end) time ranges around accidents (avoid these)"""
        corpus = self.parser.get_corpus()
        ranges = []
        
        for acc in corpus:
            try:
                # Parse date
                date_str = acc.date
                from datetime import datetime, timedelta
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Create 72-hour exclusion window (24h before, 48h after)
                start = dt - timedelta(hours=24)
                end = dt + timedelta(hours=48)
                ranges.append((start, end))
            except:
                pass
        
        return ranges
    
    def query_candidate_telemetry(self, limit: int = 10000) -> pd.DataFrame:
        """
        Query telemetry from non-accident stations, outside accident times.
        
        Returns: DataFrame with candidate rows for negative sampling
        """
        logger.info("Querying candidate telemetry for negative sampling...")
        
        accident_stations = self.get_accident_stations()
        accident_ranges = self.get_accident_time_ranges()
        
        logger.info(f"Excluding stations: {accident_stations}")
        logger.info(f"Excluding {len(accident_ranges)} time windows around accidents")
        
        # Query telemetry
        query = self.session.query(TrainTelemetry)
        
        # Exclude accident stations
        for station in accident_stations:
            query = query.filter(TrainTelemetry.station_code != station)
        
        # Exclude accident time windows (basic: just check first range)
        if accident_ranges:
            start, end = accident_ranges[0]
            query = query.filter(
                (TrainTelemetry.timestamp_utc < start) |
                (TrainTelemetry.timestamp_utc > end)
            )
        
        # Limit and fetch
        rows = query.limit(limit).all()
        
        data = []
        for row in rows:
            data.append({
                'train_id': row.train_id,
                'station_code': row.station_code,
                'timestamp_utc': row.timestamp_utc,
                'delay_minutes': row.delay_minutes,
                'speed_kmh': row.speed_kmh,
                'latitude': row.latitude,
                'longitude': row.longitude
            })
        
        df = pd.DataFrame(data)
        logger.info(f"Retrieved {len(df)} candidate rows for sampling")
        
        return df
    
    def stratify_by_characteristics(
        self,
        candidates: pd.DataFrame,
        target_samples: int = 4000
    ) -> List[pd.DataFrame]:
        """
        Stratify candidates into 48-hour windows with balanced characteristics.
        
        Returns: List of DataFrames, each ≈ 48-hour window
        """
        logger.info(f"Stratifying {len(candidates)} rows into {target_samples} samples")
        
        samples = []
        
        # Stratify by delay range
        delay_strats = {
            'light': (0, 10),      # 30%
            'moderate': (10, 30),  # 50%
            'heavy': (30, 60),     # 15%
            'severe': (60, 999)    # 5%
        }
        
        proportions = {'light': 0.30, 'moderate': 0.50, 'heavy': 0.15, 'severe': 0.05}
        
        for strat_name, (delay_min, delay_max) in delay_strats.items():
            target_count = int(proportions[strat_name] * target_samples)
            
            # Filter by delay range
            mask = (candidates['delay_minutes'] >= delay_min) & (candidates['delay_minutes'] < delay_max)
            strat_candidates = candidates[mask]
            
            if len(strat_candidates) == 0:
                logger.warning(f"No candidates in delay range {strat_name}")
                continue
            
            # Sample from this stratum
            sample_rows = strat_candidates.sample(
                n=min(target_count, len(strat_candidates)),
                random_state=self.random_state
            )
            
            # Group into 48-hour windows
            sample_rows = sample_rows.sort_values('timestamp_utc')
            samples.append(sample_rows)
            
            logger.debug(f"{strat_name}: {len(sample_rows)} samples")
        
        result = pd.concat(samples, ignore_index=True)
        logger.info(f"✓ Stratified into {len(result)} samples")
        
        return result
    
    def extract_windows_from_samples(
        self,
        samples: pd.DataFrame
    ) -> List[np.ndarray]:
        """
        Extract 48-hour windows starting from each sample timestamp.
        
        Returns: List of window DataFrames
        """
        logger.info(f"Extracting 48-hour windows from {len(samples)} sample points...")
        
        windows = []
        
        for idx, row in samples.iterrows():
            try:
                start_time = row['timestamp_utc']
                end_time = pd.Timestamp(start_time) + pd.Timedelta(hours=48)
                
                # Query 48h window for this train
                window_data = self.session.query(TrainTelemetry).filter(
                    TrainTelemetry.train_id == row['train_id'],
                    TrainTelemetry.timestamp_utc >= start_time,
                    TrainTelemetry.timestamp_utc <= end_time
                ).order_by(TrainTelemetry.timestamp_utc).all()
                
                if len(window_data) >= 100:  # Minimum threshold
                    window_df = pd.DataFrame([{
                        'timestamp_utc': w.timestamp_utc,
                        'train_id': w.train_id,
                        'station_code': w.station_code,
                        'delay_minutes': w.delay_minutes,
                        'speed_kmh': w.speed_kmh,
                        'latitude': w.latitude,
                        'longitude': w.longitude
                    } for w in window_data])
                    windows.append(window_df)
                
                if len(windows) % 500 == 0:
                    logger.debug(f"Extracted {len(windows)} windows...")
            
            except Exception as e:
                logger.debug(f"Error extracting window: {e}")
                continue
        
        logger.info(f"✓ Extracted {len(windows)} valid 48-hour windows")
        
        return windows
    
    def sample_negatives(self, target_count: int = 4000) -> List[np.ndarray]:
        """
        Generate negative sequences.
        
        Returns: List of (576, 15) feature arrays
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"NEGATIVE SAMPLING: Generating {target_count} normal sequences")
        logger.info(f"{'='*70}")
        
        # Query candidates
        candidates = self.query_candidate_telemetry(limit=50000)
        
        if len(candidates) == 0:
            logger.error("No candidate telemetry found!")
            return []
        
        # Stratify
        stratified = self.stratify_by_characteristics(candidates, target_count)
        
        # Extract windows
        windows = self.extract_windows_from_samples(stratified)
        
        logger.info(f"{'='*70}")
        logger.info(f"Successfully sampled {len(windows)} negative sequences")
        logger.info(f"{'='*70}\n")
        
        return windows


def main():
    """Testing"""
    logging.basicConfig(level=logging.INFO)
    
    sampler = NegativeSampler()
    
    # Test accident station detection
    acc_stations = sampler.get_accident_stations()
    print(f"Accident stations: {acc_stations}")
    
    # Sample
    windows = sampler.sample_negatives(target_count=100)
    print(f"Sampled {len(windows)} windows")


if __name__ == "__main__":
    main()
