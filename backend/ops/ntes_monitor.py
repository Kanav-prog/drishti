"""
DRISHTI Layer 2: The Pulse
Live Operations Intelligence Engine

Connects NTES real-time feed to structural network model.
- Watch top 100 critical junctions (from Layer 1)
- Track real-time delays and propagation
- Score cascade risk in real-time
- Zone health intelligence

This layer turns static graph into live operations dashboard.

Author: DRISHTI - Operations Intelligence
Date: March 31, 2026
"""

import logging
from typing import Dict, List, Tuple, Set, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


@dataclass
class TrainState:
    """Current state of a single train from NTES"""
    train_id: str
    train_name: str
    current_station: str
    scheduled_departure: datetime
    actual_departure: Optional[datetime] = None
    delay_minutes: int = 0
    status: str = "Running"  # Running, Delayed, Cancelled, Completed
    next_stations: List[str] = field(default_factory=list)
    passengers_aboard: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class JunctionState:
    """Real-time state of a critical junction"""
    code: str
    name: str
    centrality_score: float
    
    # Live metrics
    trains_currently_at: List[str] = field(default_factory=list)  # Train IDs
    trains_delayed_here: int = 0
    average_delay_minutes: float = 0.0
    max_delay_minutes: int = 0
    
    # Stress indicators
    stress_level: float = 0.0  # 0-100
    stress_trend: str = "stable"  # stable, rising, falling
    anomaly_count: int = 0  # Deviations from historical baseline
    
    # Cascade risk
    cascade_risk_score: float = 0.0  # 0-100
    trains_will_be_affected_next_2h: List[str] = field(default_factory=list)
    
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ZoneHealth:
    """Health score for one railway zone"""
    zone_code: str
    zone_name: str
    
    # Metrics
    total_trains_in_zone: int = 0
    trains_delayed: int = 0
    delay_percentage: float = 0.0
    
    trains_bunched: int = 0  # Multiple trains dangerously close (cascade risk)
    problematic_junctions: List[str] = field(default_factory=list)  # High-stress junctions
    
    # Overall health
    health_score: float = 100.0  # 0-100 (100 = healthy, 0 = crisis)
    status: str = "Healthy"  # Healthy, Stressed, Critical
    
    trend: str = "stable"  # stable, improving, degrading
    last_updated: datetime = field(default_factory=datetime.now)


class NTESMonitor:
    """
    Monitor NTES live feed.
    In production: connects to enquiry.indianrail.gov.in API
    For demo: uses historical replay data
    """
    
    def __init__(self):
        self.trains: Dict[str, TrainState] = {}
        self.junctions: Dict[str, JunctionState] = {}
        self.zones: Dict[str, ZoneHealth] = {}
        
        # Configuration
        self.top_100_nodes: List[str] = []  # From Layer 1
        self.delay_threshold_minutes = 15  # Alert if delay > this
        self.cascade_threshold_trains = 3  # Alert if 3+ trains affected downstream
        
    def set_top_nodes(self, nodes: List[str]):
        """Set which junctions to monitor (from Layer 1)"""
        self.top_100_nodes = nodes
        for node in nodes:
            self.junctions[node] = JunctionState(
                code=node,
                name=node,
                centrality_score=0.0
            )
        logger.info(f"✓ Monitoring {len(nodes)} critical junctions")
    
    def update_train(self, train: TrainState):
        """Update single train state (from NTES feed)"""
        self.trains[train.train_id] = train
        
        # Update junction state if train is at a critical junction
        if train.current_station in self.top_100_nodes:
            junction = self.junctions[train.current_station]
            
            if train.train_id not in junction.trains_currently_at:
                junction.trains_currently_at.append(train.train_id)
            
            # Update delay metrics
            if train.delay_minutes > 0:
                junction.trains_delayed_here += 1
                junction.max_delay_minutes = max(junction.max_delay_minutes, train.delay_minutes)
    
    def compute_stress(self, junction_code: str) -> float:
        """
        Compute real-time stress at a junction (0-100)
        
        Factors:
        - Number of delayed trains
        - Magnitude of delays
        - Historical baseline deviation
        - Cascade potential
        """
        if junction_code not in self.junctions:
            return 0.0
        
        junction = self.junctions[junction_code]
        
        # Factor 1: Delay concentration (40%)
        delayed_count = junction.trains_delayed_here
        delayed_score = min(100, delayed_count * 20)  # Each train adds 20 points
        
        # Factor 2: Delay magnitude (35%)
        max_delay = junction.max_delay_minutes
        delay_magnitude_score = min(100, max_delay / 2)  # 50min delay = 100 score
        
        # Factor 3: Bunching/cascade potential (25%)
        # (High train concentration + delays = cascade risk)
        trains_at_junction = len(junction.trains_currently_at)
        cascade_score = min(100, trains_at_junction * 10)  # Each train adds 10 points
        
        # Weighted combination
        stress = (
            delayed_score * 0.4 +
            delay_magnitude_score * 0.35 +
            cascade_score * 0.25
        )
        
        return min(100, stress)
    
    def get_cascade_forecast(self, from_station: str, affected_trains: List[str], 
                            network_graph=None) -> Dict:
        """
        Forecast cascade impact: if stress at from_station compounds,
        which trains and junctions get affected downstream?
        
        Args:
            from_station: Junction where delay is happening
            affected_trains: Trains currently delayed there
            network_graph: NetworkX graph for path computation
        
        Returns:
            Forecast of downstream impact
        """
        if not network_graph or from_station not in network_graph:
            return {"error": "Network graph not available"}
        
        # Get all downstream neighbors
        downstream = list(network_graph.neighbors(from_station))
        
        # Estimate impact time (assumes ~1-2 hours for cascade to propagate)
        impact_timeline = {
            "T+30min": [],
            "T+1h": [],
            "T+2h": []
        }
        
        # Find trains that will be affected
        for train_id in affected_trains:
            if train_id in self.trains:
                train = self.trains[train_id]
                # Check if train's next stops are downstream
                for station in train.next_stations[:3]:  # Check next 3 stops
                    if station in downstream:
                        impact_timeline["T+30min"].append(
                            f"{train_id} at {station}"
                        )
        
        return {
            "cascade_risk": "HIGH" if len(impact_timeline["T+30min"]) > 2 else "MODERATE",
            "timeline": impact_timeline,
            "downstream_junctions": downstream,
            "forecast_confidence": 0.75
        }
    
    def compute_zone_health(self, zone_code: str) -> ZoneHealth:
        """Compute health score for a zone"""
        # Find all trains in zone
        zone_trains = [
            t for t in self.trains.values()
            if t.train_id.startswith(zone_code) or zone_code in t.train_id
        ]
        
        if not zone_trains:
            return ZoneHealth(zone_code=zone_code, zone_name=zone_code)
        
        # Metrics
        total = len(zone_trains)
        delayed = sum(1 for t in zone_trains if t.delay_minutes > self.delay_threshold_minutes)
        delay_pct = (delayed / total * 100) if total > 0 else 0
        
        # Bunching (dangerous clustering)
        bunched = sum(1 for t in zone_trains if t.delay_minutes > 45)
        
        # Find problematic junctions in zone
        problematic = [
            code for code in self.top_100_nodes
            if code in self.junctions and self.compute_stress(code) > 50
        ]
        
        # Health score formula
        # 100 = no delays
        # 75 = <10% delayed
        # 50 = 10-25% delayed
        # 25 = >40% delayed
        # 0 = crisis (>60% delayed + bunching)
        
        health = 100 - (delay_pct * 0.8) - (bunched * 3)
        health = max(0, min(100, health))
        
        # Determine status
        if health >= 75:
            status = "Healthy"
            trend = "stable"
        elif health >= 50:
            status = "Stressed"
            trend = "rising" if delay_pct > 15 else "stable"
        else:
            status = "Critical"
            trend = "degrading"
        
        return ZoneHealth(
            zone_code=zone_code,
            zone_name=zone_code,
            total_trains_in_zone=total,
            trains_delayed=delayed,
            delay_percentage=delay_pct,
            trains_bunched=bunched,
            problematic_junctions=problematic,
            health_score=health,
            status=status,
            trend=trend,
            last_updated=datetime.now()
        )
    
    def get_top_stress_junctions(self, n: int = 10) -> List[Dict]:
        """Get most stressed junctions right now"""
        junction_stresses = []
        
        for code, junction in self.junctions.items():
            stress = self.compute_stress(code)
            junction_stresses.append({
                "code": code,
                "name": junction.name,
                "centrality": junction.centrality_score,
                "stress_level": stress,
                "trains_delayed": junction.trains_delayed_here,
                "max_delay": junction.max_delay_minutes,
                "cascade_risk": "HIGH" if len(junction.trains_will_be_affected_next_2h) > 2 else "MEDIUM"
            })
        
        return sorted(junction_stresses, key=lambda x: x["stress_level"], reverse=True)[:n]
    
    def get_national_health(self) -> Dict:
        """Get overall national railway health"""
        all_trains = list(self.trains.values())
        if not all_trains:
            return {"error": "No train data available"}
        
        delayed = sum(1 for t in all_trains if t.delay_minutes > self.delay_threshold_minutes)
        avg_delay = sum(t.delay_minutes for t in all_trains) / len(all_trains) if all_trains else 0
        
        critical_zones = [
            z for z in self.zones.values()
            if z.status == "Critical"
        ]
        
        national_stress = (delayed / len(all_trains) * 100) if all_trains else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_trains": len(all_trains),
            "trains_delayed": delayed,
            "delay_percentage": round(delayed / len(all_trains) * 100, 1),
            "average_delay_minutes": round(avg_delay, 1),
            "critical_zones": len(critical_zones),
            "critical_zone_codes": [z.zone_code for z in critical_zones],
            "national_stress_level": round(national_stress, 1),
            "status": "CRISIS" if national_stress > 50 else "CRITICAL" if national_stress > 30 else "STRESSED" if national_stress > 15 else "HEALTHY"
        }
    
    def export_realtime_snapshot(self) -> Dict:
        """Export current state for dashboard/API"""
        
        # Top stressed junctions
        top_stress = self.get_top_stress_junctions(10)
        
        # Zone health
        zones_health = []
        for zone_code in set(t.train_id.split("_")[0] if "_" in t.train_id else "" 
                            for t in self.trains.values()):
            if zone_code:
                zones_health.append(asdict(self.compute_zone_health(zone_code)))
        
        return {
            "timestamp": datetime.now().isoformat(),
            "national_health": self.get_national_health(),
            "top_stressed_junctions": top_stress,
            "zone_health": zones_health,
            "critical_alerts": [
                j for j in top_stress
                if j["cascade_risk"] == "HIGH"
            ]
        }


# Demo: Show Layer 2 in action
if __name__ == "__main__":
    print("\n" + "="*70)
    print("DRISHTI LAYER 2: THE PULSE - Live Operations Demo")
    print("="*70)
    
    # Initialize monitor
    monitor = NTESMonitor()
    
    # Set top 100 nodes (from Layer 1)
    demo_nodes = ["ITARSI", "JABALPUR", "BPL", "NAGPUR", "INDORE", 
                  "AHMEDABAD", "PUNE", "BUI", "ALD", "LKO"]
    monitor.set_top_nodes(demo_nodes)
    
    print("\n[1] Simulating NTES live feed...")
    
    # Create demo train states
    demo_trains = [
        TrainState(
            train_id="DEMO_001",
            train_name="Coromandel Express",
            current_station="BPL",
            scheduled_departure=datetime.now() + timedelta(hours=1),
            actual_departure=None,
            delay_minutes=45,
            status="Delayed",
            next_stations=["ITARSI", "JABALPUR", "NAGPUR"]
        ),
        TrainState(
            train_id="DEMO_002", 
            train_name="Radhani Express",
            current_station="ITARSI",
            scheduled_departure=datetime.now() + timedelta(minutes=30),
            actual_departure=None,
            delay_minutes=32,
            status="Delayed",
            next_stations=["JABALPUR", "NAGPUR"]
        ),
        TrainState(
            train_id="DEMO_003",
            train_name="Shatabdi Express",
            current_station="ITARSI",
            scheduled_departure=datetime.now(),
            actual_departure=None,
            delay_minutes=28,
            status="Delayed",
            next_stations=["NAGPUR", "INDORE"]
        )
    ]
    
    for train in demo_trains:
        monitor.update_train(train)
    
    print(f"✓ Loaded {len(demo_trains)} sample trains")
    
    print("\n[2] Computing stress levels at junctions...")
    top_stress = monitor.get_top_stress_junctions(5)
    for j in top_stress:
        print(f"   {j['code']:10s} - Stress: {j['stress_level']:5.1f} | Delayed: {j['trains_delayed']:2d} | Cascade: {j['cascade_risk']}")
    
    print("\n[3] National health snapshot...")
    national = monitor.get_national_health()
    print(f"   Status: {national['status']}")
    print(f"   Trains Delayed: {national['trains_delayed']}/{national['total_trains']}")
    print(f"   Average Delay: {national['average_delay_minutes']:.1f} min")
    print(f"   National Stress: {national['national_stress_level']:.1f}%")
    
    print("\n[4] Zone health scores...")
    for train in demo_trains:
        zone = monitor.compute_zone_health("DEMO")
        print(f"   Zone: {zone.zone_code} | Health: {zone.health_score:.0f} | Status: {zone.status} | Delayed: {zone.trains_delayed}/{zone.total_trains_in_zone}")
    
    print("\n" + "="*70)
    print("✅ Layer 2 (The Pulse) - Real-time ops monitor ready")
    print("="*70)
