"""
Hybrid Ensemble Classifier combining LSTM + CNN1D + GAT.
Phase 3.4: Multi-stream architecture with learned attention fusion.
"""

import torch
import torch.nn as nn
import logging
from typing import Optional, Tuple, Dict
from .lstm_classifier import LSTMTemporalClassifier
from .cnn1d_classifier import CNN1DTemporalClassifier
from .gat_classifier import GATTemporalGraphClassifier

logger = logging.getLogger(__name__)


class HybridTemporalGraphClassifier(nn.Module):
    """
    Hybrid multi-stream neural network combining temporal and graph models.
    
    Architecture:
        Input time-series: (batch, 576, 15)
        ↓
        ├─ Stream 1: LSTM
        |  └→ Temporal features (batch, 64)
        |
        ├─ Stream 2: CNN1D  
        |  └→ Convolutional features (batch, 64)
        |
        └─ Stream 3: GAT (optional)
           └→ Graph-aware features (batch, 64)
        
        ↓ Fusion (learned attention weights)
        
        ├─ Attention weights: α, β, γ (sum to 1)
        └─ Fused: α*LSTM + β*CNN + γ*GAT → (batch, 64)
        
        ↓ Classification
        
        FC: 64 → 32 → 1
        
    Total parameters: ~300-400K (trainable)
    """
    
    def __init__(
        self,
        input_size: int = 15,
        embedding_dim: int = 384,
        lstm_hidden_size: int = 128,
        cnn_out_channels: list = None,
        gat_hidden_size: int = 64,
        fusion_hidden: int = 64,
        fusion_method: str = "attention",
        dropout: float = 0.2,
        use_gat: bool = False,
    ):
        """
        Initialize hybrid classifier.
        
        Args:
            input_size (int): Input features. Default: 15
            embedding_dim (int): Station embedding dim. Default: 384
            lstm_hidden_size (int): LSTM hidden size. Default: 128
            cnn_out_channels (list): CNN output channels. Default: [32, 64]
            gat_hidden_size (int): GAT hidden size. Default: 64
            fusion_hidden (int): Fusion layer hidden size. Default: 64
            fusion_method (str): 'attention', 'concat', or 'weighted'. Default: 'attention'
            dropout (float): Dropout probability. Default: 0.2
            use_gat (bool): Include GAT stream. Default: False
        """
        super(HybridTemporalGraphClassifier, self).__init__()
        
        if cnn_out_channels is None:
            cnn_out_channels = [32, 64]
        
        self.input_size = input_size
        self.embedding_dim = embedding_dim
        self.lstm_hidden_size = lstm_hidden_size
        self.fusion_method = fusion_method
        self.use_gat = use_gat
        
        # Stream 1: LSTM
        self.lstm = LSTMTemporalClassifier(
            input_size=input_size,
            hidden_size=lstm_hidden_size,
            num_layers=2,
            dropout=dropout,
            embedding_dim=32,
            bidirectional=False
        )
        lstm_output_size = lstm_hidden_size
        
        # Stream 2: CNN1D
        self.cnn1d = CNN1DTemporalClassifier(
            input_size=input_size,
            out_channels=cnn_out_channels,
            kernel_size=3,
            dropout=dropout
        )
        cnn_output_size = cnn_out_channels[-1]
        
        # Stream 3: GAT (optional)
        if use_gat:
            self.gat = GATTemporalGraphClassifier(
                temporal_input_size=input_size,
                temporal_hidden_size=gat_hidden_size,
                embedding_dim=embedding_dim,
                attention_hidden=64,
                num_attention_heads=4,
                dropout=dropout
            )
            gat_output_size = 64
            n_streams = 3
        else:
            self.gat = None
            gat_output_size = 0
            n_streams = 2
        
        self.n_streams = n_streams
        
        # Stream projections to common dimension
        self.lstm_projection = nn.Linear(lstm_output_size, fusion_hidden)
        self.cnn_projection = nn.Linear(cnn_output_size, fusion_hidden)
        if use_gat:
            self.gat_projection = nn.Linear(gat_output_size, fusion_hidden)
        
        # Fusion mechanism
        if fusion_method == "attention":
            # Learned attention weights
            self.fusion_weights = nn.Linear(fusion_hidden * n_streams, n_streams)
            self.attention_activation = nn.Softmax(dim=1)
        elif fusion_method == "concat":
            # Concatenation instead of weighted fusion
            pass
        elif fusion_method == "weighted":
            # Fixed or learnable weights
            self.stream_weights = nn.Parameter(torch.ones(n_streams) / n_streams)
        else:
            raise ValueError(f"Unknown fusion method: {fusion_method}")
        
        self.fusion_method = fusion_method
        
        # Classification head
        if fusion_method == "concat":
            classifier_input = fusion_hidden * n_streams
        else:
            classifier_input = fusion_hidden
        
        self.classifier = nn.Sequential(
            nn.Linear(classifier_input, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )
        
        logger.info(f"Hybrid Classifier initialized:")
        logger.info(f"  Streams: LSTM ({lstm_output_size}D) + CNN ({cnn_output_size}D)"
                   f"{f' + GAT ({gat_output_size}D)' if use_gat else ''}")
        logger.info(f"  Projection: {n_streams} streams → {fusion_hidden}D each")
        logger.info(f"  Fusion method: {fusion_method}")
        logger.info(f"  Classification: {classifier_input}D → 32D → 1")
        
        total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        logger.info(f"  Total parameters: {total_params:,}")
    
    def forward(
        self,
        time_series: torch.Tensor,
        station_embedding: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict]:
        """
        Forward pass combining all streams.
        
        Args:
            time_series (torch.Tensor): Time-series, shape (batch, 576, 15)
            station_embedding (torch.Tensor): Station embeddings, shape (batch, 384),
                                            only used if GAT is enabled
        
        Returns:
            tuple: (logits, debug_info)
                   logits: shape (batch, 1)
                   debug_info: dict with stream outputs and fusion weights
        """
        debug_info = {}
        
        # Extract features from each stream
        # Stream 1: LSTM representation
        lstm_repr = self.lstm.get_sequence_representation(time_series)  # (batch, lstm_hidden)
        lstm_proj = self.lstm_projection(lstm_repr)  # (batch, fusion_hidden)
        debug_info['lstm_repr'] = lstm_proj
        
        # Stream 2: CNN representation
        cnn_repr = self.cnn1d.get_sequence_representation(time_series)  # (batch, cnn_out)
        cnn_proj = self.cnn_projection(cnn_repr)  # (batch, fusion_hidden)
        debug_info['cnn_repr'] = cnn_proj
        
        # Stream 3: GAT representation (optional)
        if self.use_gat and self.gat is not None:
            if station_embedding is None:
                logger.warning("GAT enabled but no station_embedding provided, skipping GAT")
            else:
                # GAT returns logits (batch, 1), we need to map to feature representation
                # For now, use GAT internal representation instead of final logits
                gat_time_features = self.gat._extract_temporal(time_series)  # (batch, gat_hidden)
                gat_proj = self.gat_projection(gat_time_features)  # (batch, fusion_hidden)
                debug_info['gat_repr'] = gat_proj
        
        # Fusion
        if self.fusion_method == "attention":
            # Concatenate representations
            if self.use_gat and self.gat is not None and 'gat_repr' in debug_info:
                stacked = torch.cat([lstm_proj, cnn_proj, debug_info['gat_repr']], dim=1)
                n_streams = 3
            else:
                stacked = torch.cat([lstm_proj, cnn_proj], dim=1)
                n_streams = 2
            
            # Compute attention weights
            fusion_logits = self.fusion_weights(stacked)  # (batch, n_streams)
            fusion_weights = self.attention_activation(fusion_logits)  # (batch, n_streams)
            debug_info['fusion_weights'] = fusion_weights
            
            # Apply weights
            if n_streams == 3:
                fused = (
                    fusion_weights[:, 0:1] * lstm_proj +
                    fusion_weights[:, 1:2] * cnn_proj +
                    fusion_weights[:, 2:3] * debug_info['gat_repr']
                )
            else:
                fused = (
                    fusion_weights[:, 0:1] * lstm_proj +
                    fusion_weights[:, 1:2] * cnn_proj
                )
        
        elif self.fusion_method == "concat":
            if self.use_gat and self.gat is not None and 'gat_repr' in debug_info:
                fused = torch.cat([lstm_proj, cnn_proj, debug_info['gat_repr']], dim=1)
            else:
                fused = torch.cat([lstm_proj, cnn_proj], dim=1)
        
        elif self.fusion_method == "weighted":
            weights = torch.softmax(self.stream_weights, dim=0)
            if self.use_gat and self.gat is not None and 'gat_repr' in debug_info:
                fused = (
                    weights[0] * lstm_proj +
                    weights[1] * cnn_proj +
                    weights[2] * debug_info['gat_repr']
                )
            else:
                fused = weights[0] * lstm_proj + weights[1] * cnn_proj
        
        # Classification
        logits = self.classifier(fused)  # (batch, 1)
        
        debug_info['logits'] = logits
        
        return logits, debug_info
    
    def get_stream_outputs(self, time_series: torch.Tensor) -> Dict:
        """
        Get individual stream outputs for analysis.
        
        Args:
            time_series (torch.Tensor): Time-series, shape (batch, 576, 15)
        
        Returns:
            dict: Per-stream logits
        """
        lstm_repr = self.lstm.get_sequence_representation(time_series)
        lstm_logits = torch.sigmoid(lstm_repr.mean())  # Dummy for now
        
        cnn_repr = self.cnn1d.get_sequence_representation(time_series)
        cnn_logits = torch.sigmoid(cnn_repr.mean())  # Dummy for now
        
        return {
            'lstm': lstm_logits,
            'cnn': cnn_logits,
        }


def test_hybrid_classifier():
    """Test hybrid classifier."""
    logging.basicConfig(level=logging.INFO)
    
    batch_size = 32
    sequence_length = 576
    input_size = 15
    embedding_dim = 384
    
    print("\n" + "="*60)
    print("Testing Hybrid Model (2-stream: LSTM + CNN)")
    print("="*60)
    
    model = HybridTemporalGraphClassifier(
        input_size=input_size,
        embedding_dim=embedding_dim,
        lstm_hidden_size=128,
        cnn_out_channels=[32, 64],
        fusion_method="attention",
        use_gat=False,
    )
    
    time_series = torch.randn(batch_size, sequence_length, input_size)
    logits, debug_info = model(time_series)
    
    print(f"\n✓ Forward pass successful (2-stream)")
    print(f"  Output shape: {logits.shape}")
    print(f"  Fusion weights: {debug_info['fusion_weights'][0].detach().numpy()}")
    
    # Test backprop
    loss = logits.mean()
    loss.backward()
    print(f"✓ Gradients computed")
    
    print("\n" + "="*60)
    print("Testing Hybrid Model (3-stream: LSTM + CNN + GAT)")
    print("="*60)
    
    model_3stream = HybridTemporalGraphClassifier(
        input_size=input_size,
        embedding_dim=embedding_dim,
        lstm_hidden_size=128,
        cnn_out_channels=[32, 64],
        fusion_method="attention",
        use_gat=True,
    )
    
    station_embedding = torch.randn(batch_size, embedding_dim)
    logits_3stream, debug_info_3stream = model_3stream(time_series, station_embedding=station_embedding)
    
    print(f"\n✓ Forward pass successful (3-stream)")
    print(f"  Output shape: {logits_3stream.shape}")
    print(f"  Fusion weights: {debug_info_3stream['fusion_weights'][0].detach().numpy()}")
    
    # Test backprop
    loss_3stream = logits_3stream.mean()
    loss_3stream.backward()
    print(f"✓ Gradients computed")
    
    print("\n" + "="*60)
    print("Parameter Summary")
    print("="*60)
    params_2stream = sum(p.numel() for p in model.parameters())
    params_3stream = sum(p.numel() for p in model_3stream.parameters())
    print(f"2-stream model: {params_2stream:,} parameters")
    print(f"3-stream model: {params_3stream:,} parameters")


if __name__ == "__main__":
    test_hybrid_classifier()
