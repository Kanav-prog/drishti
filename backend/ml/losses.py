"""
Custom loss functions for Phase 3 neural models.
Phase 3.1.1: Focal Loss from scratch (RetinaNet formulation)
Phase 3.1.2: NT-Xent Loss for contrastive learning (optional)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class FocalLoss(nn.Module):
    """
    Focal Loss for handling class imbalance.
    
    Reference: Lin et al., "Focal Loss for Dense Object Detection" (RetinaNet)
    URL: https://arxiv.org/abs/1708.02002
    
    Formula:
        FL(p_t) = -α_t * (1 - p_t)^γ * log(p_t)
    
    where:
        - p_t: model's estimated probability for positive class
        - α_t: weighting factor (balance positive/negative)
        - γ: focusing parameter (emphasize hard examples)
        - (1 - p_t)^γ: modulating factor (down-weight easy examples)
    
    Hyperparameters (from RetinaNet):
        - alpha=0.25: Positive class weight
        - gamma=2.0: Focusing parameter
    """
    
    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        reduction: str = 'mean',
        pos_weight: Optional[float] = None
    ):
        """
        Initialize Focal Loss.
        
        Args:
            alpha (float): Weighting factor for positive class (0-1).
                          Default: 0.25 (4x more weight on negatives)
            gamma (float): Focusing parameter. Default: 2.0
                          Higher gamma = more focus on hard examples
            reduction (str): 'mean', 'sum', or 'none'. Default: 'mean'
            pos_weight (float): Optional additional positive class weight.
                               If provided, alpha *= pos_weight
        """
        super(FocalLoss, self).__init__()
        
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
        
        if pos_weight is not None:
            self.alpha = alpha * pos_weight
            logger.info(f"Focal loss with pos_weight: alpha={self.alpha:.4f}")
        
        logger.info(f"Focal Loss initialized: alpha={self.alpha:.4f}, gamma={self.gamma:.2f}, "
                   f"reduction={reduction}")
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute focal loss.
        
        Args:
            inputs (torch.Tensor): Model predictions (logits), shape (batch_size,) or (batch_size, 1)
            targets (torch.Tensor): Binary targets (0/1), shape (batch_size,) or (batch_size, 1)
        
        Returns:
            torch.Tensor: Focal loss value(s)
        """
        # Ensure correct shapes
        if inputs.dim() > 1:
            inputs = inputs.squeeze(-1)
        if targets.dim() > 1:
            targets = targets.squeeze(-1)
        
        # Validate shapes match
        assert inputs.shape == targets.shape, \
            f"Shape mismatch: inputs {inputs.shape} vs targets {targets.shape}"
        
        device = inputs.device
        targets = targets.float().to(device)
        
        # Compute sigmoid (convert logits to probabilities)
        p = torch.sigmoid(inputs)
        
        # Compute p_t (probability of true class)
        # If target=1, p_t = p; if target=0, p_t = 1-p
        p_t = p * targets + (1 - p) * (1 - targets)
        
        # Avoid log(0)
        p_t = torch.clamp(p_t, min=1e-7, max=1 - 1e-7)
        
        # Focal loss: -α * (1-p_t)^γ * log(p_t)
        focal_weight = (1 - p_t) ** self.gamma
        log_p = torch.log(p_t)
        
        # Apply alpha weighting based on class
        # For positive class (target=1): use alpha
        # For negative class (target=0): use 1-alpha
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        
        # Focal loss
        loss = -alpha_t * focal_weight * log_p
        
        # Reduction
        if self.reduction == 'mean':
            return loss.mean()
        elif self.reduction == 'sum':
            return loss.sum()
        elif self.reduction == 'none':
            return loss
        else:
            raise ValueError(f"Unknown reduction: {self.reduction}")
    
    def __repr__(self) -> str:
        return (f"FocalLoss(alpha={self.alpha:.4f}, gamma={self.gamma:.2f}, "
                f"reduction='{self.reduction}')")


class FocalLossWithLogits(nn.Module):
    """
    Variant of Focal Loss using BCEWithLogitsLoss as base.
    
    More numerically stable than computing sigmoid manually.
    """
    
    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        reduction: str = 'mean',
        pos_weight: Optional[float] = None
    ):
        """Initialize with same signature as FocalLoss."""
        super(FocalLossWithLogits, self).__init__()
        
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction
        
        if pos_weight is not None:
            self.alpha = alpha * pos_weight
        
        # Use BCEWithLogitsLoss for numerical stability
        self.bce = nn.BCEWithLogitsLoss(reduction='none')
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute focal loss using BCEWithLogitsLoss.
        
        Args:
            inputs (torch.Tensor): Logits, shape (batch_size,) or (batch_size, 1)
            targets (torch.Tensor): Binary targets, shape (batch_size,) or (batch_size, 1)
        
        Returns:
            torch.Tensor: Focal loss
        """
        # Ensure correct shapes
        if inputs.dim() > 1:
            inputs = inputs.squeeze(-1)
        if targets.dim() > 1:
            targets = targets.squeeze(-1)
        
        targets = targets.float()
        
        # Compute sigmoid for focal weight computation
        p = torch.sigmoid(inputs)
        
        # Compute CE loss
        ce_loss = self.bce(inputs, targets)
        
        # Compute focal weight
        p_t = p * targets + (1 - p) * (1 - targets)
        focal_weight = (1 - p_t) ** self.gamma
        
        # Apply alpha weighting
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)
        
        # Focal loss
        focal_loss = alpha_t * focal_weight * ce_loss
        
        # Reduction
        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        elif self.reduction == 'none':
            return focal_loss
        else:
            raise ValueError(f"Unknown reduction: {self.reduction}")


class NTXentLoss(nn.Module):
    """
    Normalized Temperature-scaled Cross Entropy Loss.
    
    For contrastive learning (SimCLR formulation).
    Used for self-supervised pre-training or contrastive representation learning.
    
    Reference: Chen et al., "A Simple Framework for Contrastive Learning of Visual Representations"
    URL: https://arxiv.org/abs/2002.05709
    """
    
    def __init__(self, temperature: float = 0.07, reduction: str = 'mean'):
        """
        Initialize NT-Xent loss.
        
        Args:
            temperature (float): Temperature scaling parameter. Default: 0.07
                                Lower = sharper contrast, higher = smoother
            reduction (str): 'mean' or 'sum'. Default: 'mean'
        """
        super(NTXentLoss, self).__init__()
        
        self.temperature = temperature
        self.reduction = reduction
        logger.info(f"NT-Xent Loss initialized: temperature={temperature:.4f}")
    
    def forward(
        self,
        z_i: torch.Tensor,
        z_j: torch.Tensor,
        normalize: bool = True
    ) -> torch.Tensor:
        """
        Compute NT-Xent loss.
        
        Args:
            z_i (torch.Tensor): Embeddings from one augmentation, shape (batch_size, embed_dim)
            z_j (torch.Tensor): Embeddings from another augmentation, same shape
            normalize (bool): Normalize embeddings to unit norm. Default: True
        
        Returns:
            torch.Tensor: Contrastive loss
        """
        batch_size = z_i.shape[0]
        
        # L2 normalize if requested
        if normalize:
            z_i = F.normalize(z_i, dim=1)
            z_j = F.normalize(z_j, dim=1)
        
        # Concatenate representations
        z = torch.cat([z_i, z_j], dim=0)  # (2B, embed_dim)
        
        # Compute similarity matrix
        similarity_matrix = torch.mm(z, z.t())  # (2B, 2B)
        
        # Mask: remove self-similarity and create correct pairs
        mask = torch.eye(2 * batch_size, dtype=torch.bool, device=z.device)
        similarity_matrix.masked_fill_(mask, -9e15)
        
        # Positive pairs mask (diagonal blocks within batch)
        pos_mask = torch.zeros(2 * batch_size, 2 * batch_size, dtype=torch.bool, device=z.device)
        for i in range(batch_size):
            pos_mask[i, batch_size + i] = True
            pos_mask[batch_size + i, i] = True
        
        # Scale by temperature
        sim_scaled = similarity_matrix / self.temperature
        
        # Compute NT-Xent loss
        # For each sample, compute cross-entropy loss
        loss = 0.0
        for i in range(2 * batch_size):
            # Positive similarity (pair)
            pos_sim = similarity_matrix[i][pos_mask[i]].unsqueeze(0)
            
            # All similarities
            all_sim = sim_scaled[i].unsqueeze(0)
            
            # Log-sum-exp
            pos_term = torch.logsumexp(pos_sim / self.temperature, dim=1)
            all_term = torch.logsumexp(all_sim, dim=1)
            
            loss += all_term - pos_term
        
        # Average
        if self.reduction == 'mean':
            loss = loss / (2 * batch_size)
        
        return loss


class WeightedCrossEntropyLoss(nn.Module):
    """
    Binary cross-entropy with class weights.
    
    Useful as baseline comparison to focal loss.
    """
    
    def __init__(self, pos_weight: float = 11.0, reduction: str = 'mean'):
        """
        Initialize.
        
        Args:
            pos_weight (float): Weight for positive class. Default: 11.0
            reduction (str): 'mean' or 'sum'. Default: 'mean'
        """
        super(WeightedCrossEntropyLoss, self).__init__()
        
        self.pos_weight = torch.tensor(pos_weight)
        self.reduction = reduction
        logger.info(f"Weighted CE Loss: pos_weight={pos_weight:.4f}")
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Compute weighted cross-entropy loss.
        
        Args:
            inputs (torch.Tensor): Logits, shape (batch_size,) or (batch_size, 1)
            targets (torch.Tensor): Binary targets, shape (batch_size,) or (batch_size, 1)
        
        Returns:
            torch.Tensor: Loss
        """
        if inputs.dim() > 1:
            inputs = inputs.squeeze(-1)
        if targets.dim() > 1:
            targets = targets.squeeze(-1)
        
        bce_loss = F.binary_cross_entropy_with_logits(
            inputs, targets.float(), reduction='none'
        )
        
        # Apply class weights
        weights = targets * self.pos_weight.to(targets.device) + (1 - targets)
        weighted_loss = weights * bce_loss
        
        if self.reduction == 'mean':
            return weighted_loss.mean()
        elif self.reduction == 'sum':
            return weighted_loss.sum()
        else:
            return weighted_loss


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    # Mock data
    batch_size = 32
    logits = torch.randn(batch_size, requires_grad=True)
    targets = torch.randint(0, 2, (batch_size,)).float()
    
    # Test Focal Loss
    fl = FocalLoss(alpha=0.25, gamma=2.0)
    loss_fl = fl(logits, targets)
    print(f"Focal Loss: {loss_fl.item():.6f}")
    
    # Test variant
    logits2 = torch.randn(batch_size, requires_grad=True)
    fl_logits = FocalLossWithLogits(alpha=0.25, gamma=2.0)
    loss_fl_logits = fl_logits(logits2, targets)
    print(f"Focal Loss (Logits variant): {loss_fl_logits.item():.6f}")
    
    # Test Weighted CE (baseline)
    logits3 = torch.randn(batch_size, requires_grad=True)
    wce = WeightedCrossEntropyLoss(pos_weight=11.0)
    loss_wce = wce(logits3, targets)
    print(f"Weighted CE Loss: {loss_wce.item():.6f}")
    
    # Verify gradient flow
    loss_fl.backward()
    print(f"✓ Focal Loss gradients computed successfully")
