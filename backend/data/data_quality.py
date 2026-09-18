"""Data quality layer for train telemetry validation and anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import logging
from typing import Sequence

from backend.data.ntes_live_real import TrainState

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Quality assessment for a single telemetry record."""

    is_valid: bool
    overall_score: float  # 0-1, higher is better
    issues: list[str]  # What failed/warning
    source_quality: float  # Inherited from data source
    freshness_hours: float  # Age of data
    is_duplicate: bool  # Already seen?


class DataQualityMonitor:
    """Validates + scores train telemetry before persistence."""

    def __init__(self, max_age_hours: float = 2.0, max_jump_km: float = 100.0):
        self.max_age_hours = max_age_hours
        self.max_jump_km = max_jump_km
        self.seen_events = {}  # (train_id, source, timestamp_bucket) → count for dedup

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        """Parse ISO timestamp safely."""
        if not value:
            return datetime.now(timezone.utc)
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            logger.warning(f"Invalid timestamp: {value}, using now()")
            return datetime.now(timezone.utc)

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two geo points in km."""
        from math import radians, cos, sin, asin, sqrt

        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        km = 6371 * c
        return km

    def validate_train_state(
        self, state: TrainState, previous_state: TrainState | None = None
    ) -> QualityScore:
        """Comprehensive validation of a train telemetry record."""
        issues = []
        score_deltas = []

        # 1. Required fields
        if not state.train_id or not state.train_id.strip():
            issues.append("Missing train_id")
            score_deltas.append(-1.0)  # Fatal

        if not state.current_station or not state.current_station.strip():
            issues.append("Missing current_station")
            score_deltas.append(-0.5)

        # 2. Coordinate bounds
        if not (-90 <= state.current_lat <= 90):
            issues.append(f"Latitude out of range: {state.current_lat}")
            score_deltas.append(-0.8)

        if not (-180 <= state.current_lon <= 180):
            issues.append(f"Longitude out of range: {state.current_lon}")
            score_deltas.append(-0.8)

        # 3. Delay bounds (0-8 hours = 480 min)
        if not (0 <= state.actual_delay_minutes <= 480):
            issues.append(f"Delay out of range: {state.actual_delay_minutes}min")
            score_deltas.append(-0.8)  # Critical

        # 4. Speed bounds (0-160 km/h typical for trains)
        if not (0 <= state.speed_kmh <= 160):
            issues.append(f"Speed out of range: {state.speed_kmh} km/h")
            score_deltas.append(-0.4)

        # 5. Freshness check
        ts = self._parse_timestamp(state.timestamp)
        now = datetime.now(timezone.utc)
        age_hours = (now - ts).total_seconds() / 3600.0
        freshness_score = max(0, 1 - age_hours / self.max_age_hours)
        
        if age_hours > self.max_age_hours:
            issues.append(f"Data stale: {age_hours:.1f}h old")
            score_deltas.append(freshness_score - 1.0)

        # 6. Impossible jump check
        is_jump = False
        if previous_state:
            distance_km = self._haversine_distance(
                previous_state.current_lat, previous_state.current_lon,
                state.current_lat, state.current_lon,
            )
            prev_ts = self._parse_timestamp(previous_state.timestamp)
            elapsed_minutes = (ts - prev_ts).total_seconds() / 60.0
            
            if elapsed_minutes >= 1:  # At least 1 minute apart
                max_possible_km = (elapsed_minutes / 60.0) * 150  # 150 km/h max speed
                if distance_km > max_possible_km:
                    is_jump = True
                    issues.append(f"Impossible jump: {distance_km:.0f}km in {elapsed_minutes:.0f}min")
                    score_deltas.append(-0.9)

        # 7. Duplicate detection (same train, same source, same time bucket)
        dedup_key = (state.train_id, getattr(state, "source", "unknown"), ts.minute // 5)
        if dedup_key in self.seen_events:
            issues.append("Duplicate event (same train, source, time-bucket)")
            score_deltas.append(-0.3)
        else:
            self.seen_events[dedup_key] = 1

        # Compute overall score
        base_score = getattr(state, "source_quality_score", 0.5)
        delta = sum(score_deltas) if score_deltas else 0
        overall_score = max(0, min(1, base_score + delta * 0.1))

        # Invalid if: missing required field, out-of-bounds coordinate, impossible jump, or stale data
        critical_issues = [d for d in score_deltas if d <= -0.7]
        out_of_bounds = [d for d in score_deltas if d <= -0.6 and d > -0.7]  # Delay, coords, speed
        is_valid = len(critical_issues) == 0 and len(out_of_bounds) == 0

        return QualityScore(
            is_valid=is_valid,
            overall_score=overall_score,
            issues=issues,
            source_quality=base_score,
            freshness_hours=age_hours,
            is_duplicate="Duplicate event" in " ".join(issues),
        )

    def filter_and_score(self, states: Sequence[TrainState]) -> list[tuple[TrainState, QualityScore]]:
        """Validate + score all states, tracking previous for jump detection."""
        results = []
        state_by_train = {}

        for state in states:
            previous = state_by_train.get(state.train_id)
            score = self.validate_train_state(state, previous)
            results.append((state, score))
            state_by_train[state.train_id] = state

            if score.issues:
                logger.debug(f"[QA] {state.train_id}: {'; '.join(score.issues[:2])} (score={score.overall_score:.2f})")

        return results
