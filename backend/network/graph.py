"""
Indian Railways Network Graph Construction
Purpose: Build accurate network topology of all 7000+ IR junctions
Data: station coordinates, track types, section data
Output: Betweenness centrality-ranked junctions

Author: DRISHTI Research - Phase 5.C Network Science
Date: March 31, 2026
"""

import networkx as nx
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Station:
    """Indian Railways station node"""
    code: str              # e.g., "BLSR" for Balasore
    name: str              # Full name
    zone: str              # Railway zone (ER, WR, etc.)
    latitude: float
    longitude: float
    station_type: str      # Junction, Terminal, Yard, etc.
    platforms: int
    
    @property
    def node_id(self):
        return self.code


@dataclass
class Track:
    """Track segment between stations"""
    from_station: str
    to_station: str
    distance_km: float
    track_type: str        # "double", "single", "loop"
    speed_limit_kmh: int
    electrified: bool
    estimated_trains_per_day: int


class IRNetworkGraph:
    """Build and analyze Indian Railways network"""
    
    def __init__(self):
        self.graph = nx.Graph()
        self.stations: Dict[str, Station] = {}
        self.centrality_scores: Dict[str, float] = {}
        self.centrality_ranks: Dict[str, int] = {}
        
        logger.info("IRNetworkGraph initialized")
    
    def add_station(self, station: Station):
        """Add station to network"""
        self.stations[station.code] = station
        self.graph.add_node(
            station.code,
            name=station.name,
            zone=station.zone,
            lat=station.latitude,
            lon=station.longitude,
            type=station.station_type
        )
    
    def add_track(self, track: Track):
        """Add bidirectional track with weights"""
        weight = self._compute_edge_weight(track)
        
        self.graph.add_edge(
            track.from_station,
            track.to_station,
            weight=weight,
            distance=track.distance_km,
            track_type=track.track_type,
            speed_limit=track.speed_limit_kmh,
            traffic=track.estimated_trains_per_day
        )
    
    def _compute_edge_weight(self, track: Track) -> float:
        """
        Edge weight = how "central" this track is to network flow
        Higher traffic + single track = higher weight (more bottleneck)
        """
        base_weight = 1.0 / (track.distance_km + 0.1)  # Inverse distance
        
        # Single track is bottleneck
        if track.track_type == "single":
            base_weight *= 2.0
        
        # High traffic increases weight
        weight = base_weight * (1 + track.estimated_trains_per_day / 100)
        
        return weight
    
    def compute_betweenness_centrality(self) -> Dict[str, float]:
        """
        Compute betweenness centrality for all nodes
        High value = junction trains MUST pass through
        High value = structural danger point
        """
        self.centrality_scores = nx.betweenness_centrality(
            self.graph,
            weight='weight',
            normalized=True
        )
        
        # Create rankings (0-100)
        sorted_nodes = sorted(
            self.centrality_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        self.centrality_ranks = {
            node: int(100 * (1 - idx / len(sorted_nodes)))
            for idx, (node, _) in enumerate(sorted_nodes)
        }
        
        logger.info(f"Centrality computed for {len(self.centrality_scores)} nodes")
        
        return self.centrality_scores
    
    def get_top_critical_junctions(self, n: int = 100) -> List[Dict]:
        """Get top N high-centrality junctions"""
        if not self.centrality_scores:
            self.compute_betweenness_centrality()
        
        sorted_nodes = sorted(
            self.centrality_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:n]
        
        critical_junctions = []
        for idx, (node_id, centrality) in enumerate(sorted_nodes):
            station = self.stations.get(node_id)
            if not station:
                continue
            
            critical_junctions.append({
                "rank": idx + 1,
                "station_code": node_id,
                "station_name": station.name,
                "zone": station.zone,
                "centrality_score": float(centrality),
                "centrality_percentile": float(self.centrality_ranks.get(node_id, 0)),
                "latitude": station.latitude,
                "longitude": station.longitude,
                "reasoning": self._explain_criticality(node_id)
            })
        
        return critical_junctions
    
    def _explain_criticality(self, node_id: str) -> str:
        """Explain WHY this junction is critical"""
        if node_id not in self.graph:
            return "Station not in network"
        
        neighbors = list(self.graph.neighbors(node_id))
        degree = len(neighbors)
        
        return (
            f"Betweenness centrality: trains must pass through here. "
            f"Connected to {degree} other junctions. "
            f"Network bottleneck for multiple routes."
        )
    
    def get_network_stats(self) -> Dict:
        """Overall network health metrics"""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "network_density": nx.density(self.graph),
            "avg_degree": sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes(),
            "connected_components": nx.number_connected_components(self.graph),
            "is_connected": nx.is_connected(self.graph)
        }
    
    def export_graph(self) -> Dict:
        """Export for visualization (D3.js)"""
        nodes = []
        for node_id, station in self.stations.items():
            centrality = self.centrality_scores.get(node_id, 0.0)
            rank = self.centrality_ranks.get(node_id, 0)
            
            nodes.append({
                "id": node_id,
                "name": station.name,
                "zone": station.zone,
                "centrality": float(centrality),
                "rank": int(rank),
                "lat": station.latitude,
                "lon": station.longitude,
                "size": max(5, int(centrality * 100))  # For visualization
            })
        
        edges = []
        for from_node, to_node, data in self.graph.edges(data=True):
            edges.append({
                "source": from_node,
                "target": to_node,
                "weight": float(data.get('weight', 1.0)),
                "distance": float(data.get('distance', 0))
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": self.get_network_stats()
        }


# Mock data for Indian Railways (representative sample)
MOCK_IR_STATIONS = [
    # Core high-traffic junctions (real places)
    Station("BLSR", "Balasore", "ER", 21.5189, 86.9259, "Junction", 4),
    Station("BBS", "Bhubaneswar", "ER", 20.2471, 85.8404, "Junction", 6),
    Station("CSTM", "Mumbai Central", "WR", 18.9598, 72.8194, "Terminal", 17),
    Station("VT", "Victoria Terminus", "WR", 18.9641, 72.8327, "Terminal", 16),
    Station("BCT", "Mumbai Beach", "WR", 18.9641, 72.8327, "Junction", 8),
    Station("NDLS", "New Delhi", "NR", 28.6428, 77.2197, "Terminal", 16),
    Station("DLI", "Delhi", "NR", 28.6353, 77.2245, "Junction", 10),
    Station("KJM", "Krishnarajapuram", "SR", 13.0833, 77.6333, "Junction", 4),
    Station("BZA", "Vijayawada", "SR", 16.5062, 80.6480, "Junction", 6),
    Station("SBC", "Bangalore City", "SR", 12.9352, 77.5700, "Terminal", 10),
    
    # Additional critical nodes
    Station("LKO", "Lucknow", "NR", 26.8467, 80.9462, "Junction", 5),
    Station("CNB", "Kanpur Central", "NR", 26.4499, 80.3319, "Junction", 5),
    Station("JMP", "Jamshedpur", "ER", 22.8046, 84.8304, "Junction", 3),
    Station("ASN", "Asansol", "ER", 23.6837, 86.9850, "Junction", 4),
    Station("HWH", "Howrah", "ER", 22.5958, 88.2636, "Terminal", 15),
    Station("SDAH", "Sealdah", "ER", 22.5505, 88.3629, "Terminal", 10),
]

MOCK_IR_TRACKS = [
    # High-traffic corridors
    Track("BLSR", "BBS", 180, "double", 100, True, 25),
    Track("BBS", "CSTM", 850, "double", 90, True, 35),
    Track("CSTM", "VT", 8, "single", 40, False, 5),
    Track("VT", "BCT", 5, "single", 30, False, 3),
    Track("NDLS", "DLI", 15, "double", 60, True, 40),
    Track("DLI", "CNB", 420, "double", 100, True, 30),
    Track("CNB", "LKO", 250, "double", 90, True, 20),
    Track("LKO", "JMP", 600, "double", 80, True, 15),
    Track("JMP", "ASN", 120, "single", 60, False, 8),
    Track("ASN", "HWH", 300, "double", 80, True, 20),
    Track("HWH", "SDAH", 10, "single", 40, False, 5),
    Track("SBC", "KJM", 50, "double", 80, True, 25),
    Track("KJM", "BZA", 400, "double", 100, True, 30),
]


def create_mock_ir_network() -> IRNetworkGraph:
    """Create mock IR network for testing"""
    network = IRNetworkGraph()
    
    for station in MOCK_IR_STATIONS:
        network.add_station(station)
    
    for track in MOCK_IR_TRACKS:
        network.add_track(track)
    
    network.compute_betweenness_centrality()
    
    return network
