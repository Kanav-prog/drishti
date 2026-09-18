"""
Phase 2.0: Extract 48-hour telemetry windows around CRS accidents

Responsibility: Link CRS accident timestamps to NTES train telemetry,
extract 48-hour windows (576 timesteps at 5-min intervals), validate completeness.

Usage:
    extractor = AccidentWindowExtractor()
    windows = extractor.extract_all_accident_windows()
    for accident_id, df in windows.items():
        print(f"{accident_id}: shape {df.shape}")  # (576, 3-7 columns)
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.data.crs_parser import CRSParser, AccidentRecord
from backend.db.session import SessionLocal
from backend.db.models import TrainTelemetry, Train

logger = logging.getLogger(__name__)


class AccidentWindowExtractor:
    """Extract 48-hour telemetry windows around CRS accidents"""
    
    WINDOW_HOURS = 48
    LOOKBACK_HOURS = 24
    TIMESTEP_MINUTES = 5
    WINDOW_SIZE = int((WINDOW_HOURS * 60) / TIMESTEP_MINUTES)  # Should be 576
    
    def __init__(self):
        """Initialize extractor with CRS corpus"""
        logger.info("Initializing AccidentWindowExtractor")
        self.parser = CRSParser()
        self.corpus = self.parser.get_corpus()
        logger.info(f"✓ Loaded {len(self.corpus)} CRS accidents")
        
        # Cache for DB session
        self.session = SessionLocal()
    
    def __del__(self):
        """Close DB session"""
        if hasattr(self, 'session'):
            self.session.close()
    
    def _parse_accident_datetime(self, accident: AccidentRecord) -> datetime:
        """
        Extract precise datetime from accident record.
        
        CRS data provides date (YYYY-MM-DD) and time_of_day (NIGHT/DAY).
        Narrative has precise time (HH:MM).
        
        Fallback: 
        - NIGHT (22:00-05:00): Use 02:30 (common accident hour)
        - DAY (06:00-21:00): Use 14:00 (day operations)
        """
        try:
            # Try to parse date
            date_str = accident.date  # format: YYYY-MM-DD
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Extract time from narrative if available
            # Looking for patterns like "02:47", "03:15"
            if accident.narrative_text:
                import re
                time_match = re.search(r'(\d{1,2}):(\d{2})', accident.narrative_text)
                if time_match:
                    hour, minute = int(time_match.group(1)), int(time_match.group(2))
                    dt = dt.replace(hour=hour, minute=minute)
                    logger.debug(f"{accident.accident_id}: Extracted time {hour:02d}:{minute:02d} from narrative")
                    return dt
            
            # Fallback to time_of_day
            if accident.time_of_day == "NIGHT":
                dt = dt.replace(hour=2, minute=30)
            else:
                dt = dt.replace(hour=14, minute=0)
            
            logger.debug(f"{accident.accident_id}: Used fallback time ({accident.time_of_day})")
            return dt
            
        except Exception as e:
            logger.error(f"Failed to parse datetime for {accident.accident_id}: {e}")
            raise
    
    def _query_telemetry_window(
        self,
        accident: AccidentRecord,
        train_ids: List[str]
    ) -> Optional[pd.DataFrame]:
        """
        Query database for 48-hour telemetry window before accident.
        
        Args:
            accident: CRS accident record
            train_ids: List of train IDs involved in accident
            
        Returns:
            DataFrame with telemetry or None if insufficient data
        """
        try:
            # Parse accident time
            accident_time = self._parse_accident_datetime(accident)
            window_start = accident_time - timedelta(hours=self.LOOKBACK_HOURS)
            window_end = accident_time
            
            logger.debug(f"Querying {accident.accident_id}: {window_start} → {window_end}")
            
            # Query telemetry for window
            query = self.session.query(TrainTelemetry).filter(
                TrainTelemetry.train_id.in_(train_ids),
                TrainTelemetry.timestamp_utc >= window_start,
                TrainTelemetry.timestamp_utc <= window_end
            ).order_by(TrainTelemetry.timestamp_utc)
            
            rows = query.all()
            
            if not rows:
                logger.warning(f"{accident.accident_id}: No telemetry found in window")
                return None
            
            # Convert to DataFrame
            data = []
            for row in rows:
                data.append({
                    'timestamp_utc': row.timestamp_utc,
                    'train_id': row.train_id,
                    'station_code': row.station_code,
                    'delay_minutes': row.delay_minutes,
                    'speed_kmh': row.speed_kmh,
                    'latitude': row.latitude,
                    'longitude': row.longitude
                })
            
            df = pd.DataFrame(data)
            df = df.sort_values('timestamp_utc').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Failed to query telemetry for {accident.accident_id}: {e}")
            return None
    
    def _resample_to_regular_intervals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Resample telemetry to regular 5-minute intervals.
        
        Handles gaps:
        - delay_minutes: Forward-fill (assume held constant)
        - speed_kmh: Linear interpolation
        - station_code: Forward-fill
        
        Args:
            df: DataFrame with potentially irregular timestamps
            
        Returns:
            DataFrame with regular 5-min intervals, 576 rows
        """
        # Set timestamp as index
        df = df.set_index('timestamp_utc').sort_index()
        
        # Create regular 5-minute frequency
        start_time = df.index[0]
        end_time = df.index[-1]
        regular_idx = pd.date_range(start=start_time, end=end_time, freq='5min')
        
        # Reindex to regular intervals
        df = df.reindex(regular_idx)
        
        # Interpolation strategy
        df['delay_minutes'] = df['delay_minutes'].fillna(method='ffill')
        df['speed_kmh'] = df['speed_kmh'].interpolate(method='linear')
        df['station_code'] = df['station_code'].fillna(method='ffill')
        df['train_id'] = df['train_id'].fillna(method='ffill')
        df['latitude'] = df['latitude'].interpolate(method='linear')
        df['longitude'] = df['longitude'].interpolate(method='linear')
        
        # Fill any remaining NaNs
        df = df.fillna(method='bfill').fillna(method='ffill')
        
        # Reset index
        df = df.reset_index()
        df = df.rename(columns={'index': 'timestamp_utc'})
        
        return df
    
    def _validate_window_completeness(
        self,
        df: pd.DataFrame,
        accident_id: str
    ) -> Tuple[bool, Dict]:
        """
        Validate telemetry window quality.
        
        Returns: (is_valid, metrics_dict)
        """
        metrics = {
            'accident_id': accident_id,
            'rows': len(df),
            'expected_rows': self.WINDOW_SIZE,
            'completeness_pct': 100 * len(df) / self.WINDOW_SIZE if self.WINDOW_SIZE > 0 else 0,
            'missing_values': df.isna().sum().to_dict(),
            'delay_stats': {
                'mean': float(df['delay_minutes'].mean()),
                'std': float(df['delay_minutes'].std()),
                'min': float(df['delay_minutes'].min()),
                'max': float(df['delay_minutes'].max())
            }
        }
        
        # Validation rules
        is_valid = True
        reasons = []
        
        # Need at least 450/576 timesteps (95% complete)
        if metrics['completeness_pct'] < 95:
            is_valid = False
            reasons.append(f"Completeness {metrics['completeness_pct']:.1f}% < 95%")
        
        # Can't have more than 10% missing per key field
        if metrics['missing_values'].get('delay_minutes', 0) > 0.1 * self.WINDOW_SIZE:
            is_valid = False
            reasons.append("Too many missing delay values")
        
        metrics['is_valid'] = is_valid
        metrics['validation_reasons'] = reasons
        
        return is_valid, metrics
    
    def extract_window_for_accident(self, accident: AccidentRecord) -> Optional[Tuple[pd.DataFrame, Dict]]:
        """
        Extract complete 48-hour window for single accident.
        
        Returns: (DataFrame, metrics) or None if fails validation
        """
        logger.info(f"\n--- Extracting window for {accident.accident_id} ---")
        
        # Get train IDs
        if not accident.train_ids:
            logger.warning(f"{accident.accident_id}: No train IDs specified")
            return None
        
        train_ids = accident.train_ids if isinstance(accident.train_ids, list) else [accident.train_ids]
        logger.info(f"Trains: {train_ids}")
        
        # Query telemetry
        df = self._query_telemetry_window(accident, train_ids)
        if df is None or len(df) < 10:
            logger.warning(f"{accident.accident_id}: Insufficient telemetry data (<10 rows)")
            return None
        
        logger.info(f"Retrieved {len(df)} raw telemetry rows")
        
        # Resample to regular intervals
        df = self._resample_to_regular_intervals(df)
        logger.info(f"Resampled to {len(df)} regular 5-min intervals")
        
        # Validate
        is_valid, metrics = self._validate_window_completeness(df, accident.accident_id)
        
        if not is_valid:
            logger.warning(f"❌ Validation failed: {metrics['validation_reasons']}")
            return None
        
        logger.info(f"✓ Validation passed: {metrics['completeness_pct']:.1f}% complete")
        logger.info(f"  Delay: mean={metrics['delay_stats']['mean']:.1f}m, "
                   f"std={metrics['delay_stats']['std']:.1f}m")
        
        return df, metrics
    
    def extract_all_accident_windows(self) -> Dict[str, Tuple[pd.DataFrame, Dict]]:
        """
        Extract windows for all CRS accidents.
        
        Returns: {accident_id: (DataFrame, metrics)}
        """
        logger.info(f"\n{'='*70}")
        logger.info("EXTRACTING 48-HOUR WINDOWS FOR ALL CRS ACCIDENTS")
        logger.info(f"{'='*70}")
        
        windows = {}
        successful = 0
        failed = 0
        
        for accident in self.corpus:
            result = self.extract_window_for_accident(accident)
            
            if result is not None:
                df, metrics = result
                windows[accident.accident_id] = (df, metrics)
                successful += 1
            else:
                failed += 1
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Summary: {successful} successful, {failed} failed")
        logger.info(f"{'='*70}\n")
        
        return windows


def main():
    """Development/testing"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    extractor = AccidentWindowExtractor()
    windows = extractor.extract_all_accident_windows()
    
    # Summary
    print(f"\nExtracted {len(windows)} windows:")
    for accident_id, (df, metrics) in windows.items():
        print(f"  {accident_id}: {len(df)} rows, {metrics['completeness_pct']:.1f}% complete")


if __name__ == "__main__":
    main()
