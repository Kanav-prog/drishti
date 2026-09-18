"""
1D-CNN Temporal Classifier for accident prediction.
Phase 3.2.2: CNN-based model for local temporal pattern extraction.
"""

import torch
import torch.nn as nn
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class CNN1DTemporalClassifier(nn.Module):
    """
    1D Convolutional Neural Network for time-series accident prediction.
    
    Architecture:
        Input: (batch, 576 timesteps, 15 features)
        ↓
        Transpose: (batch, 15 features, 576 timesteps)  [CNN expects (batch, channels, length)]
        ↓
        Conv1d: 15 → 32 channels, kernel=3, stride=1, padding=1
        ↓
        ReLU + MaxPool1d(2) → (batch, 32, 288)
        ↓
        Conv1d: 32 → 64 channels, kernel=3, stride=1, padding=1
        ↓
        ReLU + MaxPool1d(2) → (batch, 64, 144)
        ↓
        GlobalAvgPool1d → (batch, 64)
        ↓
        FC: 64 → 32 → 1
    
    Total parameters: ~8K (much smaller than LSTM, faster training)
    """
    
    def __init__(
        self,
        input_size: int = 15,
        out_channels: List[int] = None,
        kernel_size: int = 3,
        stride: int = 1,
        padding: int = 1,
        pool_size: int = 2,
        dropout: float = 0.2,
    ):
        """
        Initialize 1D-CNN classifier.
        
        Args:
            input_size (int): Number of features (channels). Default: 15
            out_channels (list): Output channels for each conv block. 
                                Default: [32, 64]
            kernel_size (int): Convolution kernel size. Default: 3
            stride (int): Convolution stride. Default: 1
            padding (int): Convolution padding. Default: 1
            pool_size (int): Max pooling size. Default: 2
            dropout (float): Dropout probability. Default: 0.2
        """
        super(CNN1DTemporalClassifier, self).__init__()
        
        if out_channels is None:
            out_channels = [32, 64]
        
        self.input_size = input_size
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.dropout = dropout
        
        # Build convolutional blocks
        conv_blocks = []
        in_channels = input_size
        
        for i, out_ch in enumerate(out_channels):
            # Conv1d block: Conv → BatchNorm → ReLU → Dropout → MaxPool
            conv_block = nn.Sequential(
                nn.Conv1d(
                    in_channels=in_channels,
                    out_channels=out_ch,
                    kernel_size=kernel_size,
                    stride=stride,
                    padding=padding,
                    bias=True
                ),
                nn.BatchNorm1d(out_ch),
                nn.ReLU(inplace=True),
                nn.Dropout(dropout),
                nn.MaxPool1d(kernel_size=pool_size, stride=pool_size)
            )
            conv_blocks.append(conv_block)
            in_channels = out_ch
        
        self.conv_layers = nn.Sequential(*conv_blocks)
        
        # Global average pooling
        self.global_avg_pool = nn.AdaptiveAvgPool1d(1)
        
        # Fully connected layers
        fc_input_size = out_channels[-1]  # Last channel dimension
        self.fc_layers = nn.Sequential(
            nn.Linear(fc_input_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )
        
        logger.info(f"1D-CNN Classifier initialized:")
        logger.info(f"  Input: {input_size} features × 576 timesteps")
        logger.info(f"  Convolution: {len(out_channels)} blocks, "
                   f"channels: {input_size} → {' → '.join(map(str, out_channels))}")
        logger.info(f"  Kernel: {kernel_size}, Stride: {stride}, Padding: {padding}")
        logger.info(f"  Pooling: size={pool_size}")
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
        # Transpose from (batch, timesteps, features) to (batch, features, timesteps)
        # This is required for Conv1d which expects (batch, channels, length)
        x = x.transpose(1, 2)  # (batch, 15, 576)
        
        # Convolutional layers
        x = self.conv_layers(x)  # (batch, out_channels[-1], reduced_length)
        
        # Global average pooling: (batch, out_channels[-1], reduced_length) → (batch, out_channels[-1])
        x = self.global_avg_pool(x).squeeze(-1)
        
        # Fully connected layers
        logits = self.fc_layers(x)  # (batch, 1)
        
        return logits
    
    def get_sequence_representation(self, x: torch.Tensor) -> torch.Tensor:
        """
        Get sequence representation (after global avg pool).
        
        Args:
            x (torch.Tensor): Input tensor, shape (batch_size, sequence_length, input_size)
        
        Returns:
            torch.Tensor: Representations, shape (batch_size, out_channels[-1])
        """
        x = x.transpose(1, 2)  # (batch, features, timesteps)
        x = self.conv_layers(x)
        x = self.global_avg_pool(x).squeeze(-1)  # (batch, out_channels[-1])
        return x


def test_cnn1d_classifier():
    """Test 1D-CNN classifier."""
    logging.basicConfig(level=logging.INFO)
    
    batch_size = 32
    sequence_length = 576
    input_size = 15
    
    # Create model
    model = CNN1DTemporalClassifier(
        input_size=input_size,
        out_channels=[32, 64],
        kernel_size=3,
        dropout=0.2
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
    
    # Compare parameter count with LSTM
    print(f"\nParameter comparison:")
    print(f"  1D-CNN: {sum(p.numel() for p in model.parameters()):,} parameters")


if __name__ == "__main__":
    test_cnn1d_classifier()
