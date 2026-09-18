"""
Data Quality Pipeline
Deduplication, outlier removal, imputation
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import List, Tuple

import numpy as np
from datetime import datetime

from backend.data.crs_loader import AccidentRecord
from backend.data.ntes_live import TrainState

logger = logging.getLogger(__name__)


class DataCleaner:
    """Production data cleaning pipeline"""

    def deduplicate_accidents(self, accidents: List[AccidentRecord]) -> List[AccidentRecord]:
        """Remove duplicate accident records"""
        seen = {}
        unique = []
        duplicates_removed = 0

        for acc in accidents:
            # Signature: (date, station, deaths)
            sig = (acc.date, acc.station_code, acc.deaths)

            if sig not in seen:
                seen[sig] = acc
                unique.append(acc)
            else:
                # Merge if new record has more info
                existing = seen[sig]
                if len(acc.secondary_causes) > len(existing.secondary_causes):
                    seen[sig] = acc
                    unique[-1] = acc
                duplicates_removed += 1

        logger.info(f"Deduplicated: removed {duplicates_removed} duplicate accidents")
        return unique

    def remove_outlier_delays(self, trains: List[TrainState]) -> Tuple[List[TrainState], int]:
        """Remove unrealistic delay values"""
        valid = []
        outliers = 0

        for train in trains:
            # Rules: 0 <= delay <= 480 (8 hours, beyond = likely cancelled)
            if 0 <= train.actual_delay_minutes <= 480:
                valid.append(train)
            else:
                outliers += 1
                logger.debug(
                    f"Outlier removed: {train.train_id} delay={train.actual_delay_minutes}min"
                )

        logger.info(f"Removed {outliers} outlier delays")
        return valid, outliers

    def impute_weather(self, accident: AccidentRecord, fallback_weather: str = "Unknown") -> AccidentRecord:
        """Fill missing weather field"""
        if not accident.weather or accident.weather == "Unknown":
            # Use monsoon-based fallback
            month = int(accident.date.split("-")[1])
            accident.weather = "Rainy" if 6 <= month <= 9 else "Clear"
        return accident

    def impute_time_of_day(
        self, accident: AccidentRecord, fallback_time: str = "Night"
    ) -> AccidentRecord:
        """Fill missing time_of_day (statistically higher accident rate at night)"""
        if not accident.time_of_day or accident.time_of_day == "Unknown":
            accident.time_of_day = fallback_time
        return accident

    def normalize_timestamps(self, accidents: List[AccidentRecord]) -> List[AccidentRecord]:
        """Normalize all dates to ISO format UTC"""
        normalized = []
        for acc in accidents:
            try:
                # Parse and normalize to ISO
                dt = datetime.fromisoformat(acc.date.replace("Z", "+00:00"))
                acc.date = dt.isoformat()
                normalized.append(acc)
            except ValueError as e:
                logger.warning(f"Failed to parse date {acc.date}: {e}")
                # Skip record with invalid date
        return normalized

    def validate_and_clean_batch(
        self, accidents: List[AccidentRecord]
    ) -> Tuple[List[AccidentRecord], int]:
        """Run full cleaning pipeline"""
        logger.info(f"Starting data cleaning: {len(accidents)} records")

        # Step 1: Deduplicate
        accidents = self.deduplicate_accidents(accidents)

        # Step 2: Normalize timestamps
        accidents = self.normalize_timestamps(accidents)

        # Step 3: Impute missing values
        accidents = [self.impute_weather(a) for a in accidents]
        accidents = [self.impute_time_of_day(a) for a in accidents]

        # Step 4: Basic validation (must have: date, station, deaths)
        before_validation = len(accidents)
        accidents = [
            a for a in accidents
            if a.date and a.station_code and a.deaths >= 0
        ]
        invalid_removed = before_validation - len(accidents)

        logger.info(
            f"Cleaning complete: {len(accidents)} valid records "
            f"({invalid_removed} invalid removed)"
        )

        return accidents, invalid_removed


class TrainDataCleaner:
    """Clean live train data"""

    def validate_and_clean(self, trains: List[TrainState]) -> Tuple[List[TrainState], int]:
        """Validate train records"""
        valid = []
        invalid = 0

        for train in trains:
            if self._is_valid(train):
                valid.append(train)
            else:
                invalid += 1

        logger.info(f"Train validation: {len(valid)} valid, {invalid} invalid")
        return valid, invalid

    def _is_valid(self, train: TrainState) -> bool:
        """Validation rules"""
        return (
            train.train_id
            and train.current_station
            and 0 <= train.actual_delay_minutes <= 480
            and -90 <= train.current_lat <= 90
            and -180 <= train.current_lon <= 180
        )


# Global cleaner instances
accident_cleaner = DataCleaner()
train_cleaner = TrainDataCleaner()
