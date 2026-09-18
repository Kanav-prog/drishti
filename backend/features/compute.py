"""
Real-Time Feature Computation Engine

Computes per-train, per-junction, per-signal features in <50ms
for ML inference pipeline.

Features are stored in Redis cache and queried by inference engine.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class PerTrainFeatures:
    """Features for a single train"""
    train_id: str
    position_lat: float
    position_lon: float
    actual_delay_minutes: int
    scheduled_delay_baseline_minutes: int  # Historical baseline delay for this train
    delay_trend: float  # Rate of change: (current_delay - past_delay) / time_delta
    speed_kmh: float
    traffic_density_around_train: float  # 0-1, % of max capacity on this section
    time_to_next_junction_minutes: int
    is_goods_train: bool
    timestamp: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PerJunctionFeatures:
    """Features for a junction/station"""
    junction_id: str
    station_name: str
    centrality_rank: int  # 0-100, higher = more dangerous topology
    avg_traffic_density_24h: float
    signal_failures_24h: int
    maintenance_window_active: bool
    avg_signal_cycle_time_seconds: float
    trains_currently_in_zone: int
    recent_accidents_30d: int
    time_of_day: str  # NIGHT or DAY
    timestamp: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


class NetworkTopology:
    """
    Hardcoded network data for Indian Railways.
    Maps stations → centrality rank (from network analysis).
    """
    
    # High-centrality (dangerous) junctions from our graph analysis
    HIGH_RISK_JUNCTIONS = {
        "Bahanaga Bazar": {"centrality_rank": 99, "lat": 21.5, "lon": 86.8},
        "Gaisal": {"centrality_rank": 98, "lat": 24.2, "lon": 88.5},
        "Kanchanjungha": {"centrality_rank": 97, "lat": 23.8, "lon": 91.3},
        "Khanna": {"centrality_rank": 96, "lat": 30.7, "lon": 75.7},
        "Asansol": {"centrality_rank": 95, "lat": 23.6, "lon": 86.9},
        "Firozabad": {"centrality_rank": 94, "lat": 27.2, "lon": 78.4},
    }
    
    # Medium-risk junctions
    MEDIUM_RISK_JUNCTIONS = {
        "Howrah": {"centrality_rank": 75, "lat": 22.5, "lon": 88.3},
        "Chennai Central": {"centrality_rank": 70, "lat": 13.0, "lon": 80.2},
        "Agra": {"centrality_rank": 65, "lat": 27.2, "lon": 78.0},
    }
    
    @staticmethod
    def get_centrality_rank(station: str) -> int:
        """Get centrality rank (0-100) for a station"""
        if station in NetworkTopology.HIGH_RISK_JUNCTIONS:
            return NetworkTopology.HIGH_RISK_JUNCTIONS[station]["centrality_rank"]
        elif station in NetworkTopology.MEDIUM_RISK_JUNCTIONS:
            return NetworkTopology.MEDIUM_RISK_JUNCTIONS[station]["centrality_rank"]
        else:
            return 50  # Default middle rank


class FeatureEngine:
    """Compute features in real-time for inference"""
    
    def __init__(self, ntes_connector, timetable_baseline: Dict = None):
        """
        Initialize feature engine.
        
        Args:
            ntes_connector: Live train feed connector
            timetable_baseline: Historical delay baselines per train
        """
        self.ntes = ntes_connector
        self.baselines = timetable_baseline or {}
        self.past_states = {}  # For computing delay_trend
        self.compute_count = 0
        
        logger.info("Feature engine initialized")
        
    def get_baseline_delay(self, train_id: str) -> int:
        """Get historical baseline delay for a train (in minutes)"""
        # In production: query timetable database
        # For now: use hardcoded baselines
        baselines = {
            "12841": 8,   # Coromandel: usually ~8 min late
            "12003": 5,   # Bengaluru-Howrah: usually ~5 min late
            "13015": 3,   # Kanchanjungha: usually on time
            "15006": 15,  # Goods: usually ~15 min late
        }
        return baselines.get(train_id, 10)  # Default: 10 min
    
    def compute_delay_trend(self, train_id: str, current_delay: int) -> float:
        """
        Compute rate of change of delay.
        
        Returns:
        - Positive: delay increasing (worsening)
        - Negative: delay decreasing (improving)
        - 0: stable
        """
        if train_id not in self.past_states:
            # First observation: no trend yet
            self.past_states[train_id] = {
                'delay': current_delay,
                'timestamp': datetime.utcnow().isoformat()
            }
            return 0.0
        
        past = self.past_states[train_id]
        delay_change = current_delay - past['delay']
        
        # Approximate time since last observation (in minutes)
        # In production: compute exact time difference
        time_delta_minutes = 5  # Assume 5 min between features
        
        # Trend: delay change per minute
        trend = delay_change / max(time_delta_minutes, 1)
        
        # Update past state
        self.past_states[train_id] = {
            'delay': current_delay,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return trend
    
    def compute_traffic_density(self, station: str, trains: List) -> float:
        """
        Compute traffic density at a station (0-1).
        
        = current trains at station / max capacity for this station
        """
        trains_at_station = [t for t in trains if t.current_station == station]
        
        # Station capacity (hardcoded for development)
        capacities = {
            "Bahanaga Bazar": 3,
            "Gaisal": 3,
            "Howrah": 10,
            "Chennai Central": 8,
        }
        
        capacity = capacities.get(station, 3)  # Default: 3 trains max
        
        density = min(1.0, len(trains_at_station) / capacity)
        return density
    
    def compute_time_to_next_junction(self, train_id: str, 
                                     current_station: str,
                                     speed_kmh: float = 80) -> int:
        """
        Estimate minutes until train reaches next junction.
        
        Simplified logic:
        - Major junctions are ~100km apart
        - Average speed: 80 kmh
        - Time = 100 / 80 * 60 = ~75 minutes
        """
        # In production: query actual track data, schedule
        # For now: estimate
        estimated_distance_km = 100  # Average distance to next junction
        estimated_minutes = (estimated_distance_km / max(speed_kmh, 1)) * 60
        return int(estimated_minutes)
    
    async def compute_train_features(self, train_id: str, 
                                    trains: List) -> Optional[PerTrainFeatures]:
        """
        Compute all features for a train.
        Must complete in <50ms for production.
        """
        # Get train state from NTES
        train_state = self.ntes.get_train_state(train_id)
        if not train_state:
            logger.warning(f"Train {train_id} not found in NTES cache")
            return None
        
        # Compute features
        try:
            features = PerTrainFeatures(
                train_id=train_id,
                position_lat=train_state.current_lat,
                position_lon=train_state.current_lon,
                actual_delay_minutes=train_state.actual_delay_minutes,
                scheduled_delay_baseline_minutes=self.get_baseline_delay(train_id),
                delay_trend=self.compute_delay_trend(train_id, train_state.actual_delay_minutes),
                speed_kmh=train_state.speed_kmh,
                traffic_density_around_train=self.compute_traffic_density(train_state.current_station, trains),
                time_to_next_junction_minutes=self.compute_time_to_next_junction(
                    train_id, 
                    train_state.current_station,
                    train_state.speed_kmh
                ),
                is_goods_train=train_id.startswith("15") or "Goods" in train_state.train_name,
                timestamp=train_state.timestamp
            )
            
            return features
            
        except Exception as e:
            logger.error(f"Error computing features for {train_id}: {e}")
            return None
    
    async def compute_junction_features(self, station: str, 
                                       trains: List) -> PerJunctionFeatures:
        """
        Compute all features for a junction.
        Must complete in <50ms for production.
        """
        # Determine time of day
        hour = datetime.utcnow().hour
        time_of_day = "NIGHT" if (hour < 6 or hour >= 22) else "DAY"
        
        # Count trains at junction
        trains_here = self.ntes.get_trains_at_station(station)
        
        features = PerJunctionFeatures(
            junction_id=station,  # Use station name as ID
            station_name=station,
            centrality_rank=NetworkTopology.get_centrality_rank(station),
            avg_traffic_density_24h=self.compute_traffic_density(station, trains),
            signal_failures_24h=0,  # TODO: query signal history
            maintenance_window_active=False,  # TODO: query maintenance schedule
            avg_signal_cycle_time_seconds=4.5,  # Average for Indian Railways
            trains_currently_in_zone=len(trains_here),
            recent_accidents_30d=len(self.get_regional_accidents(station, 30)),
            time_of_day=time_of_day,
            timestamp=datetime.utcnow().isoformat()
        )
        
        return features
    
    def get_regional_accidents(self, station: str, days: int) -> List:
        """Get recent accidents near a station (simplified)"""
        # In production: query accident database with geo-proximity
        # For now: check if high-risk junction
        if station in NetworkTopology.HIGH_RISK_JUNCTIONS:
            return [{"station": station}]  # At least 1 recent accident
        return []
    
    async def compute_all_features(self) -> Tuple[List[PerTrainFeatures], List[PerJunctionFeatures]]:
        """
        Compute features for all high-risk junctions + relevant trains.
        Batch process in parallel. Must complete in <100ms.
        """
        self.compute_count += 1
        
        try:
            trains = self.ntes.get_all_trains()
            
            # Compute train features for all trains
            train_features = []
            for train in trains:
                features = await self.compute_train_features(train.train_id, trains)
                if features:
                    train_features.append(features)
            
            # Compute junction features for high-risk stations only
            junction_features = []
            for station in NetworkTopology.HIGH_RISK_JUNCTIONS.keys():
                features = await self.compute_junction_features(station, trains)
                junction_features.append(features)
            
            logger.info(f"Computed {len(train_features)} train features, {len(junction_features)} junction features")
            
            return train_features, junction_features
            
        except Exception as e:
            logger.error(f"Error computing all features: {e}")
            return [], []
    
    def get_stats(self) -> Dict:
        """Get engine statistics"""
        return {
            'compute_count': self.compute_count,
            'tracked_trains': len(self.past_states),
        }


async def main():
    """Development/testing"""
    logging.basicConfig(level=logging.INFO)
    
    # Import and initialize NTES connector
    from backend.data.ntes_connector import NTESConnector
    
    ntes = NTESConnector()
    ntes.load_cache()
    
    # Initialize and run feature engine
    engine = FeatureEngine(ntes)
    
    # Compute features
    train_features, junction_features = await engine.compute_all_features()
    
    print(f"\n=== Train Features ===")
    for tf in train_features[:3]:
        print(f"\n{tf.train_id}:")
        print(f"  Delay: {tf.actual_delay_minutes}m (baseline: {tf.scheduled_delay_baseline_minutes}m)")
        print(f"  Trend: {tf.delay_trend:.2f} m/min")
        print(f"  Traffic density: {tf.traffic_density_around_train:.1%}")
    
    print(f"\n=== Junction Features ===")
    for jf in junction_features[:3]:
        print(f"\n{jf.station_name}:")
        print(f"  Centrality rank: {jf.centrality_rank}")
        print(f"  Trains in zone: {jf.trains_currently_in_zone}")
        print(f"  Time of day: {jf.time_of_day}")
    
    stats = engine.get_stats()
    print(f"\n=== Stats ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
