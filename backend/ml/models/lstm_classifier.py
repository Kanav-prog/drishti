"""
LSTM Temporal Classifier for accident prediction.
Phase 3.2.1: LSTM-based model capturing temporal dependencies.
"""

import torch
import torch.nn as nn
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class LSTMTemporalClassifier(nn.Module):
    """
    LSTM-based classifier for time-series accident prediction.
    
    Architecture:
        Input: (batch, 576 timesteps, 15 features)
        ↓
        Embedding: 15 features → 32 dims (optional, improves gradient flow)
        ↓
        LSTM: 32 → 128 hidden (2 layers, dropout=0.3)
        ↓
        Take last hidden state: (batch, 128)
        ↓
        FC: 128 → 64 → 1 (sigmoid output)
    
    Total parameters: ~120K (trainable)
    """
    
    def __init__(
        self,
        input_size: int = 15,
        hidden_size: int = 128,
        num_layers: int = 2,
        dropout: float = 0.3,
        embedding_dim: Optional[int] = 32,
        bidirectional: bool = False,
    ):
        """
        Initialize LSTM classifier.
        
        Args:
            input_size (int): Number of features per timestep. Default: 15
            hidden_size (int): LSTM hidden size. Default: 128
            num_layers (int): Number of LSTM layers. Default: 2
            dropout (float): Dropout probability. Default: 0.3
            embedding_dim (int): Optional feature embedding dimension. Default: 32
            bidirectional (bool): Use bidirectional LSTM. Default: False
        """
        super(LSTMTemporalClassifier, self).__init__()
        
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.dropout = dropout
        self.embedding_dim = embedding_dim
        self.bidirectional = bidirectional
        
        # Feature embedding (optional)
        if embedding_dim is not None:
            self.embedding = nn.Linear(input_size, embedding_dim)
            lstm_input_size = embedding_dim
        else:
            self.embedding = None
            lstm_input_size = input_size
        
        # LSTM
        self.lstm = nn.LSTM(
            input_size=lstm_input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )
        
        # Calculate LSTM output size
        lstm_output_size = hidden_size * (2 if bidirectional else 1)
        
        # Fully connected layers
        self.fc_layers = nn.Sequential(
            nn.Linear(lstm_output_size, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1)
        )
        
        logger.info(f"LSTM Classifier initialized:")
        logger.info(f"  Input: {input_size} features × 576 timesteps")
        logger.info(f"  Embedding: {embedding_dim if embedding_dim else 'None'}")
        logger.info(f"  LSTM: {num_layers} layers, {hidden_size} hidden, "
                   f"bidirectional={bidirectional}")
        logger.info(f"  Output: 1 (binary classification)")
        
        # Count parameters
        total_params = sum(p.numel() for p in self.parameters() if p.requires_grad)
        logger.info(f"  Total parameters: {total_params:,}")
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Args:
            x (torch.Tensor): Input tensor, shape (batch_size, sequence_length, input_size)
                            e.g., (32, 576, 15)
        
        Returns:
            torch.Tensor: Logits, shape (batch_size, 1)
        """
        batch_size = x.shape[0]
        
        # Embedding (optional)
        if self.embedding is not None:
            x = self.embedding(x)  # (batch, 576, embedding_dim)
        
        # LSTM
        lstm_out, (hidden, cell) = self.lstm(x)
        # lstm_out: (batch, 576, hidden_size * num_directions)
        # hidden: (num_layers * num_directions, batch, hidden_size)
        
        # Take last hidden state
        if self.bidirectional:
            # Concatenate forward and backward last states
            hidden = hidden.view(self.num_layers, 2, batch_size, self.hidden_size)
            last_hidden = hidden[-1]  # (2, batch, hidden_size)
            last_hidden = last_hidden.transpose(0, 1)  # (batch, 2, hidden_size)
            last_hidden = last_hidden.reshape(batch_size, -1)  # (batch, 2*hidden_size)
        else:
            last_hidden = hidden[-1]  # (batch, hidden_size)
        
        # Fully connected
        logits = self.fc_layers(last_hidden)  # (batch, 1)
        
        return logits
    
    def get_sequence_representation(self, x: torch.Tensor) -> torch.Tensor:
        """
        Get sequence representation (for visualization, clustering, etc.).
        
        Args:
            x (torch.Tensor): Input tensor, shape (batch_size, sequence_length, input_size)
        
        Returns:
            torch.Tensor: Representations, shape (batch_size, hidden_size)
        """
        batch_size = x.shape[0]
        
        if self.embedding is not None:
            x = self.embedding(x)
        
        lstm_out, (hidden, cell) = self.lstm(x)
        
        if self.bidirectional:
            hidden = hidden.view(self.num_layers, 2, batch_size, self.hidden_size)
            last_hidden = hidden[-1]
            last_hidden = last_hidden.transpose(0, 1)
            last_hidden = last_hidden.reshape(batch_size, -1)
        else:
            last_hidden = hidden[-1]
        
        return last_hidden


def test_lstm_classifier():
    """Test LSTM classifier."""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    batch_size = 32
    sequence_length = 576
    input_size = 15
    
    # Create model
    model = LSTMTemporalClassifier(
        input_size=input_size,
        hidden_size=128,
        num_layers=2,
        dropout=0.3,
        embedding_dim=32
    )
    
    # Forward pass
    x = torch.randn(batch_size, sequence_length, input_size)
    logits = model(x)
    
    print(f"\n✓ Forward pass successful")
    print(f"  Input shape: {x.shape}")
    print(f"  Output shape: {logits.shape}")
    
    # Get representation
    repr = model.get_sequence_representation(x)
    print(f"  Representation shape: {repr.shape}")
    
    # Test backprop
    loss = logits.mean()
    loss.backward()
    print(f"✓ Gradients computed successfully")


if __name__ == "__main__":
    test_lstm_classifier()
