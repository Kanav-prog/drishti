"""Data quality assurance layer for train telemetry."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """Represents a data quality problem."""

    issue_type: str  # "duplicate", "stale", "anomaly", "invalid_coordinates"
    severity: str  # "error", "warning", "info"
    message: str
    train_id: str
    timestamp: datetime


class DataQualityChecker:
    """Validates and gates train telemetry before persistence."""

    def __init__(
        self,
        freshness_threshold_minutes: int = 30,
        max_unrealistic_delay_minutes: int = 480,
        max_speed_kmh: float = 200.0,
    ):
        self.freshness_threshold = timedelta(minutes=freshness_threshold_minutes)
        self.max_delay = max_unrealistic_delay_minutes
        self.max_speed = max_speed_kmh
        self.recent_hashes: dict[str, str] = {}  # train_id -> hash of last state
        self.issues: list[QualityIssue] = []

    @staticmethod
    def _compute_state_hash(train_state: dict) -> str:
        """Compute hash of immutable train state fields."""
        key = f"{train_state['train_id']}|{train_state['current_station']}|{train_state['actual_delay_minutes']}"
        return hashlib.md5(key.encode()).hexdigest()

    def is_duplicate(self, train_state: dict) -> bool:
        """Check if this exact state was just seen."""
        state_hash = self._compute_state_hash(train_state)
        train_id = train_state["train_id"]

        if train_id in self.recent_hashes:
            if self.recent_hashes[train_id] == state_hash:
                logger.debug(f"[DQ] Duplicate state for {train_id}")
                self.issues.append(
                    QualityIssue(
                        issue_type="duplicate",
                        severity="warning",
                        message=f"Exact state seen in recent cycle",
                        train_id=train_id,
                        timestamp=datetime.now(timezone.utc),
                    )
                )
                return True

        self.recent_hashes[train_id] = state_hash
        return False

    def is_stale(self, train_state: dict) -> bool:
        """Check if telemetry is older than freshness threshold."""
        timestamp_str = train_state.get("timestamp", "")
        if not timestamp_str:
            return False

        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - ts
            if age > self.freshness_threshold:
                logger.debug(f"[DQ] Stale data for {train_state['train_id']}: {age.total_seconds():.0f}s old")
                self.issues.append(
                    QualityIssue(
                        issue_type="stale",
                        severity="warning",
                        message=f"Data {age.total_seconds():.0f}s old (threshold: {self.freshness_threshold.total_seconds():.0f}s)",
                        train_id=train_state.get("train_id", "unknown"),
                        timestamp=ts,
                    )
                )
                return True
        except ValueError:
            pass

        return False

    def is_anomalous(self, train_state: dict) -> bool:
        """Detect unrealistic train states."""
        train_id = train_state.get("train_id", "unknown")
        issues = []

        delay = train_state.get("actual_delay_minutes", 0)
        if delay < 0 or delay > self.max_delay:
            issues.append(f"unrealistic delay: {delay}min")

        speed = train_state.get("speed_kmh", 0)
        if speed < 0 or speed > self.max_speed:
            issues.append(f"unrealistic speed: {speed}kmh")

        lat = train_state.get("current_lat", 0)
        lon = train_state.get("current_lon", 0)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            issues.append(f"out-of-bounds coordinates: ({lat}, {lon})")

        if issues:
            msg = "; ".join(issues)
            logger.warning(f"[DQ] Anomaly for {train_id}: {msg}")
            self.issues.append(
                QualityIssue(
                    issue_type="anomaly",
                    severity="error",
                    message=msg,
                    train_id=train_id,
                    timestamp=datetime.now(timezone.utc),
                )
            )
            return True

        return False

    def validate(self, train_state: dict) -> tuple[bool, list[str]]:
        """Run all checks. Returns (is_valid, warnings)."""
        warnings = []

        if self.is_duplicate(train_state):
            warnings.append("duplicate_state")

        if self.is_stale(train_state):
            warnings.append("stale_data")

        if self.is_anomalous(train_state):
            return False, warnings + ["anomalous"]

        return True, warnings

    def get_issue_report(self) -> dict[str, Any]:
        """Summary of all quality issues detected."""
        by_type = {}
        for issue in self.issues:
            by_type.setdefault(issue.issue_type, []).append(
                {
                    "severity": issue.severity,
                    "message": issue.message,
                    "train_id": issue.train_id,
                    "timestamp": issue.timestamp.isoformat(),
                }
            )

        return {
            "total_issues": len(self.issues),
            "by_type": by_type,
            "recent_hashes_cached": len(self.recent_hashes),
        }

    def clear_recent_hashes(self):
        """Clear dedup cache (e.g., at end of cycle)."""
        self.recent_hashes.clear()
