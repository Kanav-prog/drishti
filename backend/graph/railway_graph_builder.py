"""
Railway Network Graph Builder for GAT model.
Phase 3.3.1: Constructs PyTorch Geometric graph from station data.
"""

import torch
import numpy as np
import pandas as pd
import logging
from pathlib import Path
from typing import Optional, Dict, Tuple
from scipy.spatial.distance import cdist

logger = logging.getLogger(__name__)


class RailwayGraphBuilder:
    """
    Builds railway network graph for Graph Attention Network (GAT).
    
    Graph structure:
        - Nodes: Railway stations (7,000)
        - Node features: Station embeddings (384-dim from Phase 1) + coordinates (2-dim)
        - Edges: Connect geographically adjacent stations
        - Edge weights: Inverse distance (closer = stronger signal)
    """
    
    def __init__(
        self,
        stations_csv: str = "data/railway_stations_7000.csv",
        embeddings_json: Optional[str] = None,
        max_distance_km: float = 50.0,
        max_neighbors: int = 10,
    ):
        """
        Initialize graph builder.
        
        Args:
            stations_csv (str): Path to stations CSV file
            embeddings_json (str): Path to embeddings JSON (optional)
            max_distance_km (float): Maximum distance to connect stations
            max_neighbors (int): Maximum neighbors per station
        """
        self.stations_csv = Path(stations_csv)
        self.embeddings_json = Path(embeddings_json) if embeddings_json else None
        self.max_distance_km = max_distance_km
        self.max_neighbors = max_neighbors
        
        self.stations_df = None
        self.embeddings_dict = None
        self.node_features = None
        self.edge_index = None
        self.edge_attr = None
        self.data = None
        
        logger.info(f"RailwayGraphBuilder initialized")
        logger.info(f"  Stations CSV: {self.stations_csv}")
        logger.info(f"  Max distance: {max_distance_km} km")
        logger.info(f"  Max neighbors: {max_neighbors}")
    
    def load_stations(self) -> pd.DataFrame:
        """Load stations from CSV."""
        if not self.stations_csv.exists():
            raise FileNotFoundError(f"Stations CSV not found: {self.stations_csv}")
        
        self.stations_df = pd.read_csv(self.stations_csv)
        n_stations = len(self.stations_df)
        
        logger.info(f"✓ Loaded {n_stations} stations from {self.stations_csv}")
        logger.info(f"  Columns: {self.stations_df.columns.tolist()}")
        
        return self.stations_df
    
    def load_embeddings(self) -> Dict[int, np.ndarray]:
        """Load embeddings from JSON (optional)."""
        if self.embeddings_json is None:
            logger.info("No embeddings JSON provided, will use coordinate-only features")
            return {}
        
        if not self.embeddings_json.exists():
            logger.warning(f"Embeddings JSON not found: {self.embeddings_json}, "
                          "using coordinate-only features")
            return {}
        
        import json
        try:
            with open(self.embeddings_json, 'r') as f:
                data = json.load(f)
                # Assuming JSON structure: {"station_id": [embedding_values]}
                self.embeddings_dict = {
                    int(k): np.array(v) for k, v in data.items()
                }
                logger.info(f"✓ Loaded embeddings for {len(self.embeddings_dict)} stations")
                return self.embeddings_dict
        except Exception as e:
            logger.error(f"Error loading embeddings: {e}")
            return {}
    
    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance between two points in km.
        
        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates
        
        Returns:
            float: Distance in kilometers
        """
        R = 6371  # Earth radius in km
        
        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        delta_lat = np.radians(lat2 - lat1)
        delta_lon = np.radians(lon2 - lon1)
        
        a = np.sin(delta_lat / 2) ** 2 + \
            np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(delta_lon / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(a))
        
        return R * c
    
    def build_node_features(self) -> np.ndarray:
        """
        Build node feature matrix.
        
        Combines embeddings (384-dim) + coordinates (2-dim) = 386-dim total
        Or coordinates only (2-dim) if embeddings not available.
        """
        if self.stations_df is None:
            raise ValueError("Load stations first with load_stations()")
        
        n_stations = len(self.stations_df)
        
        # Start with coordinates
        coords = self.stations_df[['latitude', 'longitude']].values  # (7000, 2)
        
        # Normalize coordinates to [0, 1] range for consistent scaling
        lat_min, lat_max = coords[:, 0].min(), coords[:, 0].max()
        lon_min, lon_max = coords[:, 1].min(), coords[:, 1].max()
        
        coords_normalized = np.zeros_like(coords, dtype=np.float32)
        coords_normalized[:, 0] = (coords[:, 0] - lat_min) / (lat_max - lat_min)
        coords_normalized[:, 1] = (coords[:, 1] - lon_min) / (lon_max - lon_min)
        
        # Combine with embeddings if available
        if self.embeddings_dict and len(self.embeddings_dict) > 0:
            # Create embedding matrix
            embeddings = np.zeros((n_stations, 384), dtype=np.float32)
            for idx, station_id in enumerate(self.stations_df['station_id'].values):
                if station_id in self.embeddings_dict:
                    embeddings[idx] = self.embeddings_dict[station_id]
            
            # Concatenate: (7000, 384) + (7000, 2) = (7000, 386)
            node_features = np.concatenate([embeddings, coords_normalized], axis=1)
            logger.info(f"✓ Built node features: {node_features.shape} (embeddings + coords)")
        else:
            # Use coordinates only
            node_features = coords_normalized
            logger.info(f"✓ Built node features: {node_features.shape} (coordinates only)")
        
        self.node_features = torch.FloatTensor(node_features)
        return node_features
    
    def build_adjacency(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Build graph adjacency based on geographic proximity.
        
        Returns:
            tuple: (edge_index, edge_weights) where:
                   edge_index: shape (2, num_edges) for PyTorch Geometric
                   edge_weights: shape (num_edges,) inverse distance weights
        """
        if self.stations_df is None:
            raise ValueError("Load stations first with load_stations()")
        
        coords = self.stations_df[['latitude', 'longitude']].values
        n_stations = len(coords)
        
        # Compute pairwise distances using Haversine
        logger.info("Computing pairwise distances (this may take a moment)...")
        
        distances = np.zeros((n_stations, n_stations))
        for i in range(n_stations):
            for j in range(i, n_stations):
                dist = self.haversine_distance(
                    coords[i, 0], coords[i, 1],
                    coords[j, 0], coords[j, 1]
                )
                distances[i, j] = dist
                distances[j, i] = dist
        
        logger.info(f"✓ Computed distances")
        logger.info(f"  Min distance: {distances[distances > 0].min():.2f} km")
        logger.info(f"  Max distance: {distances.max():.2f} km")
        logger.info(f"  Mean distance: {distances[distances > 0].mean():.2f} km")
        
        # Build edges: keep only nearby stations
        edges = []
        weights = []
        
        for i in range(n_stations):
            # Find neighbors within max_distance and limit to max_neighbors
            neighbors_mask = (distances[i] > 0) & (distances[i] <= self.max_distance_km)
            neighbor_indices = np.where(neighbors_mask)[0]
            neighbor_distances = distances[i, neighbor_indices]
            
            # Sort by distance and keep top max_neighbors
            if len(neighbor_indices) > 0:
                top_k = min(self.max_neighbors, len(neighbor_indices))
                top_indices = np.argsort(neighbor_distances)[:top_k]
                
                for idx_in_neighbors in top_indices:
                    j = neighbor_indices[idx_in_neighbors]
                    dist = distances[i, j]
                    
                    # Add edge (i, j) only if i < j to avoid duplicates
                    if i < j:
                        edges.append([i, j])
                        # Weight: inverse distance (closer = higher weight)
                        weight = 1.0 / (1.0 + dist)
                        weights.append(weight)
        
        edges = np.array(edges, dtype=np.int64).T if edges else np.zeros((2, 0), dtype=np.int64)
        weights = np.array(weights, dtype=np.float32) if weights else np.zeros(0, dtype=np.float32)
        
        logger.info(f"✓ Built adjacency")
        logger.info(f"  Number of edges: {edges.shape[1] if edges.size > 0 else 0}")
        logger.info(f"  Edge density: {(edges.shape[1] / (n_stations * (n_stations - 1) / 2) * 100):.4f}%"
                   f" (if edges exist)")
        
        self.edge_index = torch.LongTensor(edges)
        self.edge_attr = torch.FloatTensor(weights).reshape(-1, 1) if weights.size > 0 else None
        
        return edges, weights
    
    def build_full_graph(self):
        """Build complete graph structure."""
        # Load data
        self.load_stations()
        self.load_embeddings()
        
        # Build features and adjacency
        self.build_node_features()
        self.build_adjacency()
        
        # Create PyTorch Geometric Data object
        try:
            from torch_geometric.data import Data
            
            self.data = Data(
                x=self.node_features,
                edge_index=self.edge_index,
                edge_attr=self.edge_attr
            )
            
            logger.info(f"✓ Built PyTorch Geometric Data object")
            logger.info(f"  Node features: {self.data.x.shape}")
            logger.info(f"  Edge index: {self.data.edge_index.shape}")
            if self.data.edge_attr is not None:
                logger.info(f"  Edge attributes: {self.data.edge_attr.shape}")
            
            return self.data
        
        except ImportError:
            logger.warning("torch_geometric not installed, returning data as tensors")
            return {
                'x': self.node_features,
                'edge_index': self.edge_index,
                'edge_attr': self.edge_attr
            }
    
    def verify_connectivity(self) -> Dict:
        """Verify graph connectivity."""
        if self.edge_index is None or self.edge_index.shape[1] == 0:
            logger.warning("Graph has no edges!")
            return {"connected_components": -1, "avg_degree": 0}
        
        n_nodes = self.node_features.shape[0]
        n_edges = self.edge_index.shape[1]
        
        # Compute degree
        degree = torch.zeros(n_nodes)
        degree.scatter_add_(0, self.edge_index[0], torch.ones(n_edges))
        degree.scatter_add_(0, self.edge_index[1], torch.ones(n_edges))
        
        stats = {
            "n_nodes": n_nodes,
            "n_edges": n_edges,
            "min_degree": int(degree.min().item()),
            "max_degree": int(degree.max().item()),
            "avg_degree": float(degree.mean().item()),
            "isolated_nodes": int((degree == 0).sum().item()),
        }
        
        logger.info(f"✓ Graph connectivity check:")
        logger.info(f"  Nodes: {stats['n_nodes']}")
        logger.info(f"  Edges: {stats['n_edges']}")
        logger.info(f"  Degree - Min: {stats['min_degree']}, Max: {stats['max_degree']}, "
                   f"Avg: {stats['avg_degree']:.2f}")
        logger.info(f"  Isolated nodes: {stats['isolated_nodes']}")
        
        return stats
    
    def compute_stats(self) -> Dict:
        """Compute graph statistics."""
        if self.node_features is None:
            raise ValueError("Build graph first with build_full_graph()")
        
        stats = {
            "n_nodes": self.node_features.shape[0],
            "n_features": self.node_features.shape[1],
            "n_edges": self.edge_index.shape[1] if self.edge_index is not None else 0,
        }
        
        if self.edge_attr is not None:
            stats["edge_weight_min"] = float(self.edge_attr.min().item())
            stats["edge_weight_max"] = float(self.edge_attr.max().item())
            stats["edge_weight_mean"] = float(self.edge_attr.mean().item())
        
        logger.info(f"Graph stats: {stats}")
        return stats


def main():
    """Test graph builder."""
    logging.basicConfig(level=logging.INFO)
    
    builder = RailwayGraphBuilder(
        stations_csv="data/railway_stations_7000.csv",
        embeddings_json=None,  # Won't use embeddings for now
        max_distance_km=50.0,
        max_neighbors=10
    )
    
    # Build graph
    graph_data = builder.build_full_graph()
    
    # Verify
    builder.verify_connectivity()
    builder.compute_stats()
    
    print(f"\n✓ Graph build complete")


if __name__ == "__main__":
    main()
