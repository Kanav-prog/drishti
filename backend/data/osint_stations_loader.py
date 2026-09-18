"""
Phase 1: Real Railway Stations Graph Builder (7000+ nodes)
Source: GitHub raw CSV
"""

from __future__ import annotations

import logging
import urllib.request
import io
import csv
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
import networkx as nx

logger = logging.getLogger(__name__)

STATIONS_CSV_URL = "https://raw.githubusercontent.com/DeekshithRajBasa/Train-time-delay-prediction-using-machine-learning/master/stations.csv"


@dataclass(frozen=True)
class Station:
    """Railway station node"""
    code: str
    name: str
    zone: str = "Unknown"
    state: str = "Unknown"
    lat: float = 0.0
    lon: float = 0.0


class RealRailwayGraph:
    """Build 7000+ node railway network from OSINT data"""

    def __init__(self, use_cache: bool = True):
        self.stations: Dict[str, Station] = {}
        self.graph: nx.DiGraph = nx.DiGraph()
        self.cache_path = Path("backend/data/stations_cache.pkl")
        self.use_cache = use_cache

    def build_from_github(self) -> nx.DiGraph:
        """Download and build graph from GitHub stations CSV"""
        
        logger.info("[OSINT] Downloading stations from GitHub...")
        
        try:
            # Download CSV
            with urllib.request.urlopen(STATIONS_CSV_URL) as response:
                csv_content = response.read().decode('utf-8')
            
            # Parse CSV
            reader = csv.DictReader(io.StringIO(csv_content))
            for row in reader:
                code = row.get('Code', '').strip()
                name = row.get('Station Name', '').strip()
                
                if code and name:
                    station = Station(
                        code=code,
                        name=name,
                        zone=self._extract_zone(code),
                        state=self._extract_state(name),
                    )
                    self.stations[code] = station
                    self.graph.add_node(code, station_name=name, zone=station.zone)
            
            logger.info(f"✅ Loaded {len(self.stations)} stations into graph")
            return self.graph
            
        except Exception as e:
            logger.error(f"❌ Failed to download: {e}")
            logger.info("Falling back to embedded stations...")
            return self._build_embedded_graph()

    def _extract_zone(self, code: str) -> str:
        """Map station code → zone"""
        # Simplified zone mapping (IR zones)
        zone_map = {
            'N': 'NR', 'C': 'CR', 'E': 'ER', 'W': 'WR',
            'S': 'SR', 'M': 'NR', 'D': 'DCR', 'F': 'NFR',
            'H': 'NR', 'A': 'NER', 'K': 'KR', 'T': 'TR',
        }
        first_char = code[0].upper() if code else 'U'
        return zone_map.get(first_char, 'Other')

    def _extract_state(self, name: str) -> str:
        """Extract state from station name (simple heuristic)"""
        state_suffixes = {
            'Delhi': 'DL', 'Mumbai': 'MH', 'Bangalore': 'KA',
            'Kolkata': 'WB', 'Chennai': 'TN', 'Hyderabad': 'TG',
            'Pune': 'MH', 'Jaipur': 'RJ', 'Lucknow': 'UP',
        }
        for city, state in state_suffixes.items():
            if city in name:
                return state
        return 'XX'

    def _build_embedded_graph(self) -> nx.DiGraph:
        """Fallback: embedded stations (when download fails)"""
        embedded = [
            Station('NDLS', 'New Delhi', 'NR', 'DL'),
            Station('BPL', 'Bhopal Junction', 'WCR', 'MP'),
            Station('HWH', 'Howrah Junction', 'ER', 'WB'),
            Station('CST', 'Mumbai', 'CR', 'MH'),
            Station('MAS', 'Chennai Central', 'SR', 'TN'),
        ]
        for station in embedded:
            self.stations[station.code] = station
            self.graph.add_node(station.code, station_name=station.name, zone=station.zone)
        
        logger.info(f"⚠️  Using embedded graph ({len(embedded)} stations)")
        return self.graph

    def calculate_centrality(self) -> Dict[str, float]:
        """Identify accident-prone junctions (high centrality)"""
        if self.graph.number_of_edges() == 0:
            logger.warning("Graph has no edges - centrality will be zero for all nodes")
        
        centrality = nx.betweenness_centrality(self.graph)
        
        # Top 20 highest-centrality stations (likely accident hotspots)
        top_20 = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:20]
        
        logger.info(f"🔴 TOP 20 HIGH-CENTRALITY STATIONS (accident hotspots):")
        for code, score in top_20:
            station = self.stations.get(code)
            print(f"  {code:6} {station.name if station else 'Unknown':30} Centrality: {score:.4f}")
        
        return centrality

    def get_zone_composition(self) -> Dict[str, int]:
        """Station count by zone"""
        zones = {}
        for station in self.stations.values():
            zones[station.zone] = zones.get(station.zone, 0) + 1
        
        logger.info("📊 ZONE COMPOSITION:")
        for zone, count in sorted(zones.items(), key=lambda x: x[1], reverse=True):
            print(f"  {zone:6} {count:5} stations")
        
        return zones


if __name__ == "__main__":
    logger.basicConfig(level=logging.INFO)
    
    builder = RealRailwayGraph()
    graph = builder.build_from_github()
    
    print(f"\n✅ Graph built: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")
    
    centrality = builder.calculate_centrality()
    zones = builder.get_zone_composition()
    
    print(f"\n📈 Total: {len(builder.stations)} stations across {len(zones)} zones")
