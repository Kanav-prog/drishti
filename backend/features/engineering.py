"""
Feature Engineering: 6 → 20+ features
All features tied to accident hypotheses
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Any

import numpy as np

logger = logging.getLogger(__name__)

# Indian national holidays (sample)
INDIAN_HOLIDAYS = {
    "2023-01-26",  # Republic Day
    "2023-03-07",  # Maha Shivaratri
    "2023-03-30",  # Good Friday
    "2023-04-04",  # Eid ul-Fitr
    "2023-04-14",  # Ambedkar Jayanti
    "2023-05-23",  # Buddha Purnima
    "2023-08-15",  # Independence Day
    "2023-08-30",  # Janmashtami
    "2023-09-19",  # Milad un-Nabi
    "2023-10-02",  # Gandhi Jayanti
    "2023-10-24",  # Dussehra
    "2023-11-14",  # Diwali
    "2023-12-25",  # Christmas
}


class FeatureEngineer:
    """Engineers 20+ features from raw data"""

    def __init__(self, network_graph=None):
        self.network_graph = network_graph
        self.accident_cache: Dict[str, List] = {}

    def extract_temporal_features(self, date: str) -> Dict[str, Any]:
        """5 temporal features"""
        try:
            dt = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except:
            dt = datetime.now()

        return {
            "hour_of_day": float(dt.hour),
            "day_of_week": float(dt.weekday()),
            "is_weekend": float(dt.weekday() in [5, 6]),
            "month": float(dt.month),
            "is_monsoon": float(6 <= dt.month <= 9),
            "is_holiday": float(date.split("T")[0] in INDIAN_HOLIDAYS if "T" in date else False),
        }

    def extract_spatial_features(self, station_code: str) -> Dict[str, Any]:
        """4 spatial topology features"""
        if not self.network_graph or station_code not in self.network_graph.nodes:
            return {
                "centrality": 0.3,
                "degree": 2.0,
                "avg_neighbor_centrality": 0.3,
                "distance_to_hub": 3.0,
            }

        node = self.network_graph.nodes[station_code]
        neighbors = list(self.network_graph.neighbors(station_code))

        return {
            "centrality": float(node.get("centrality", 0.3)),
            "degree": float(len(neighbors)),
            "avg_neighbor_centrality": float(
                np.mean(
                    [
                        self.network_graph.nodes[n].get("centrality", 0.3)
                        for n in neighbors
                    ]
                )
                if neighbors
                else 0.3
            ),
            "distance_to_hub": 3.0,
        }

    def extract_historical_features(
        self, station_code: str, all_accidents: List
    ) -> Dict[str, Any]:
        """6 historical accident features"""

        # Filter accidents at this station
        acc_at_station = [a for a in all_accidents if a.station_code == station_code]

        if not acc_at_station:
            return {
                "accident_frequency": 0.0,
                "deaths_on_record": 0.0,
                "injuries_on_record": 0.0,
                "years_since_last_accident": 50.0,
                "peak_accident_month": 6.0,
                "common_cause_signal_failure": 0.0,
            }

        # Compute features
        deaths = sum(a.deaths for a in acc_at_station)
        injuries = sum(a.injuries for a in acc_at_station)

        # Years since last accident
        try:
            latest_date = max(a.date for a in acc_at_station)
            dt_latest = datetime.fromisoformat(latest_date.replace("Z", "+00:00"))
            years_since = (datetime.now(dt_latest.tzinfo) - dt_latest).days / 365.25
        except:
            years_since = 50.0

        # Most common cause
        causes = {}
        for acc in acc_at_station:
            cause = getattr(acc, "primary_cause", "unknown")
            causes[cause] = causes.get(cause, 0) + 1
        top_cause = max(causes, key=causes.get) if causes else "unknown"

        # Peak accident month
        try:
            months = [int(a.date.split("-")[1]) for a in acc_at_station]
            peak_month = float(np.median(months)) if months else 6.0
        except:
            peak_month = 6.0

        return {
            "accident_frequency": float(len(acc_at_station)),
            "deaths_on_record": float(deaths),
            "injuries_on_record": float(injuries),
            "years_since_last_accident": float(years_since),
            "peak_accident_month": peak_month,
            "common_cause_signal_failure": float(top_cause == "signal_failure"),
        }

    def extract_operational_features(
        self,
        delay_minutes: int,
        weather_condition: str,
        temperature_celsius: float,
        rainfall_mm: float,
    ) -> Dict[str, Any]:
        """5 operational features"""
        return {
            "delay_minutes": float(delay_minutes),
            "delay_hours": float(delay_minutes / 60.0),
            "is_heavy_rain": float(rainfall_mm > 50),
            "is_extreme_heat": float(temperature_celsius > 40),
            "weather_severity": float(
                (
                    (1.0 if rainfall_mm > 50 else 0.5 if rainfall_mm > 10 else 0)
                    + (1.0 if temperature_celsius > 40 else 0.5 if temperature_celsius > 35 else 0)
                )
            ),
        }

    def engineer_all_features(
        self,
        accident,
        all_accidents: List,
        delay_minutes: int = 0,
        weather_condition: str = "Unknown",
        temperature: float = 25.0,
        rainfall: float = 0.0,
    ) -> Dict[str, float]:
        """Create feature vector with 20+ features"""
        features = {}

        # Temporal features (6)
        temporal = self.extract_temporal_features(accident.date)
        features.update({f"temporal_{k}": v for k, v in temporal.items()})

        # Spatial features (4)
        spatial = self.extract_spatial_features(accident.station_code)
        features.update({f"spatial_{k}": v for k, v in spatial.items()})

        # Historical features (6)
        historical = self.extract_historical_features(accident.station_code, all_accidents)
        features.update({f"historical_{k}": v for k, v in historical.items()})

        # Operational features (5)
        operational = self.extract_operational_features(
            delay_minutes, weather_condition, temperature, rainfall
        )
        features.update({f"operational_{k}": v for k, v in operational.items()})

        # Static accident metadata
        features["deaths"] = float(accident.deaths)
        features["injuries"] = float(accident.injuries)

        return features


# Global engineer
feature_engineer = FeatureEngineer()
