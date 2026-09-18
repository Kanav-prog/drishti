"""
Graph Attention Network (GAT) Classifier for accident prediction.
Phase 3.3.2: GAT-based model using simplified station graph.
"""

import torch
import torch.nn as nn
import logging
from typing import Optional, Tuple
import warnings

logger = logging.getLogger(__name__)

# Try to import torch_geometric, but provide fallback
try:
    import torch_geometric
    from torch_geometric.nn import GATConv, global_mean_pool
    HAS_TORCH_GEO = True
except ImportError:
    HAS_TORCH_GEO = False
    if HAS_TORCH_GEO is False:
        logger.warning("torch_geometric not installed. GAT will use fallback implementation.")


class GATTemporalGraphClassifier(nn.Module):
    """
    Graph Attention Network for accident prediction with time-series features.
    
    Simplified approach: Uses station embeddings + adjacency matrix directly
    without full PyTorch Geometric (avoids expensive 7K node graph computation).
    
    Architecture:
        Input: Time-series (batch, 576, 15) + station graph structure
        ↓
        LSTM/CNN stream: Extract temporal features (batch, temporal_embed_dim)
        ↓
        Station embedding: Use embeddings from Phase 1 or learned
        ↓
        Attention fusion: Combine temporal + station context
        ↓
        Output: (batch, 1) binary logits
    
    Design rationale:
        - Full graph (7K nodes): Too expensive for training
        - Station-focused approach: Model relevant context stations only
        - Practical: Can run on CPU without excessive computation
    """
    
    def __init__(
        self,
        temporal_input_size: int = 15,
        temporal_hidden_size: int = 64,
        embedding_dim: int = 384,
        attention_hidden: int = 64,
        num_attention_heads: int = 4,
        dropout: float = 0.2,
    ):
        """
        Initialize GAT classifier.
        
        Args:
            temporal_input_size (int): Input features. Default: 15
            temporal_hidden_size (int): Temporal embedding dim. Default: 64
            embedding_dim (int): Station embedding dim. Default: 384
            attention_hidden (int): Attention layer hidden size. Default: 64
            num_attention_heads (int): Multi-head attention heads. Default: 4
            dropout (float): Dropout probability. Default: 0.2
        """
        super(GATTemporalGraphClassifier, self).__init__()
        
        self.temporal_input_size = temporal_input_size
        self.temporal_hidden_size = temporal_hidden_size
        self.embedding_dim = embedding_dim
        self.attention_hidden = attention_hidden
        self.num_attention_heads = num_attention_heads
        
        # Stream 1: Temporal feature extraction (simplified LSTM)
        self.temporal_lstm = nn.LSTM(
            input_size=temporal_input_size,
            hidden_size=temporal_hidden_size,
            num_layers=1,
            batch_first=True,
            dropout=0
        )
        
        # Stream 2: Station embedding projection
        self.embedding_projection = nn.Sequential(
            nn.Linear(embedding_dim, attention_hidden),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        # Stream 3: Multi-head attention fusion
        self.attention = nn.MultiheadAttention(
            embed_dim=attention_hidden,
            num_heads=num_attention_heads,
            dropout=dropout,
            batch_first=True
        )
        
        # Temporal projection for attention
        self.temporal_projection = nn.Sequential(
            nn.Linear(temporal_hidden_size, attention_hidden),
            nn.ReLU()
        )
        
        # Final classification layers
        self.classifier = nn.Sequential(
            nn.Linear(attention_hidden * 2, 64),  # Temporal + attention dim
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )
        
        logger.info(f"GAT Classifier initialized (simplified):")
        logger.info(f"  Temporal stream: LSTM {temporal_input_size} → {temporal_hidden_size}")
        logger.info(f"  Embedding stream: Linear {embedding_dim} → {attention_hidden}")
        logger.info(f"  Attention: {num_attention_heads} heads, {attention_hidden} dim")
        logger.info(f"  Output: Binary classification (1)")
        
        total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        logger.info(f"  Total parameters: {total_params:,}")
    
    def forward(
        self,
        time_series: torch.Tensor,
        station_embedding: Optional[torch.Tensor] = None,
        station_context: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            time_series (torch.Tensor): Time-series features, shape (batch, 576, 15)
            station_embedding (torch.Tensor): Optional station embeddings, 
                                            shape (batch, embedding_dim)
            station_context (torch.Tensor): Optional context from adjacent stations,
                                           shape (batch, n_context, embedding_dim)
        
        Returns:
            torch.Tensor: Logits, shape (batch, 1)
        """
        batch_size = time_series.shape[0]
        device = time_series.device
        
        # Stream 1: Extract temporal features
        lstm_out, (lstm_hidden, _) = self.temporal_lstm(time_series)
        temporal_features = lstm_hidden[-1]  # (batch, temporal_hidden_size)
        
        # Project temporal features for attention
        temporal_proj = self.temporal_projection(temporal_features)  # (batch, attention_hidden)
        
        # Stream 2 & 3: Graph attention fusion
        if station_embedding is not None:
            # Project station embedding
            station_proj = self.embedding_projection(station_embedding)  # (batch, attention_hidden)
            
            # Create query-key-value for attention
            # Use temporal as query, station as both key and value
            query = temporal_proj.unsqueeze(1)  # (batch, 1, attention_hidden)
            key_value = station_proj.unsqueeze(1)  # (batch, 1, attention_hidden)
            
            # Multi-head attention
            attn_out, attn_weights = self.attention(
                query=query,
                key=key_value,
                value=key_value
            )
            attn_out = attn_out.squeeze(1)  # (batch, attention_hidden)
        else:
            # No station embedding available, use temporal only
            attn_out = temporal_proj
        
        # Combine streams
        combined = torch.cat([temporal_proj, attn_out], dim=1)  # (batch, 2*attention_hidden)
        
        # Classification
        logits = self.classifier(combined)  # (batch, 1)
        
        return logits
    
    def get_attention_weights(
        self,
        time_series: torch.Tensor,
        station_embedding: torch.Tensor,
    ) -> torch.Tensor:
        """
        Get attention weights for interpretability.
        
        Args:
            time_series (torch.Tensor): Time-series, shape (batch, 576, 15)
            station_embedding (torch.Tensor): Station embeddings, shape (batch, embedding_dim)
        
        Returns:
            torch.Tensor: Attention weights, shape (batch, num_heads)
        """
        # Compute attention manually for interpretability
        temporal_features = self._extract_temporal(time_series)
        temporal_proj = self.temporal_projection(temporal_features)
        station_proj = self.embedding_projection(station_embedding)
        
        query = temporal_proj.unsqueeze(1)
        key_value = station_proj.unsqueeze(1)
        
        _, attn_weights = self.attention(query, key_value, key_value)
        
        return attn_weights
    
    def _extract_temporal(self, time_series: torch.Tensor) -> torch.Tensor:
        """Helper: Extract temporal features."""
        _, (lstm_hidden, _) = self.temporal_lstm(time_series)
        return lstm_hidden[-1]


class GATSimplified(nn.Module):
    """
    Ultra-simplified GAT variant: just attention over embeddings.
    
    Useful as baseline before full GAT implementation.
    """
    
    def __init__(self, embedding_dim: int = 384, hidden_dim: int = 64):
        super(GATSimplified, self).__init__()
        
        self.attention_layers = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
        
        self.classifier = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
        
        logger.info("Simplified GAT initialized")
    
    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            embeddings (torch.Tensor): Station embeddings, shape (batch, embedding_dim)
        
        Returns:
            torch.Tensor: Logits, shape (batch, 1)
        """
        # Compute attention weights
        attn_weights = torch.softmax(self.attention_layers(embeddings), dim=0)
        
        # Attention-weighted embedding
        weighted = embeddings * attn_weights
        
        # Classify
        return self.classifier(weighted)


def test_gat_classifier():
    """Test GAT classifier."""
    logging.basicConfig(level=logging.INFO)
    
    batch_size = 32
    sequence_length = 576
    input_size = 15
    embedding_dim = 384
    
    # Test 1: Basic forward pass
    model = GATTemporalGraphClassifier(
        temporal_input_size=input_size,
        temporal_hidden_size=64,
        embedding_dim=embedding_dim,
        attention_hidden=64,
        num_attention_heads=4,
    )
    
    time_series = torch.randn(batch_size, sequence_length, input_size)
    station_embedding = torch.randn(batch_size, embedding_dim)
    
    logits = model(time_series, station_embedding=station_embedding)
    
    print(f"\n✓ Forward pass successful")
    print(f"  Input (time-series): {time_series.shape}")
    print(f"  Input (embedding): {station_embedding.shape}")
    print(f"  Output: {logits.shape}")
    
    # Test 2: Gradients
    loss = logits.mean()
    loss.backward()
    print(f"✓ Gradients computed successfully")
    
    # Test 3: Simplified variant
    model_simple = GATSimplified(embedding_dim=embedding_dim)
    logits_simple = model_simple(station_embedding)
    print(f"✓ Simplified GAT works: {logits_simple.shape}")


if __name__ == "__main__":
    test_gat_classifier()
