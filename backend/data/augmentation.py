"""
Phase 2.2: Augmentation strategy - expand 6 CRS accidents → 400 positive sequences

Techniques:
1. Noise injection: Gaussian σ=(0.01-0.05) on delay/speed
2. Scaling: Delay magnitude ×0.9, ×1.1, ×1.2 (severity variation)
3. Time-shift: Shift pattern ±1-3 hours (onset variation)
4. Concatenation: Stack overlapping windows (sequential dependency)
5. Interleaving: Mix patterns from multiple accidents

Target: 67 variants per base accident (6 × 67 = 402 ≈ 400)
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Tuple, Dict
from copy import deepcopy

logger = logging.getLogger(__name__)


class PositiveSequenceAugmentor:
    """Augment 6 base accident sequences into 400 synthetic variants"""
    
    def __init__(self, random_seed: int = 42):
        """Initialize with deterministic randomness for reproducibility"""
        np.random.seed(random_seed)
        self.random_state = np.random.RandomState(random_seed)
    
    def augment_with_noise(
        self,
        sequence: np.ndarray,
        noise_level: float = 0.02,
        columns_to_noise: List[int] = None
    ) -> np.ndarray:
        """Add Gaussian noise to specific columns"""
        if columns_to_noise is None:
            columns_to_noise = [0, 1]  # delay_minutes, speed_kmh
        
        seq = sequence.copy()
        for col_idx in columns_to_noise:
            if col_idx < seq.shape[1]:
                noise = self.random_state.normal(0, noise_level, seq.shape[0])
                seq[:, col_idx] = np.maximum(seq[:, col_idx] + noise, 0)
        
        return seq
    
    def augment_with_scaling(
        self,
        sequence: np.ndarray,
        scale_factor: float,
        columns_to_scale: List[int] = None
    ) -> np.ndarray:
        """Scale delay/speed columns by factor"""
        if columns_to_scale is None:
            columns_to_scale = [0, 1]  # delay, speed
        
        seq = sequence.copy()
        for col_idx in columns_to_scale:
            if col_idx < seq.shape[1]:
                seq[:, col_idx] = np.maximum(seq[:, col_idx] * scale_factor, 0)
        
        return seq
    
    def augment_with_timeshift(
        self,
        sequence: np.ndarray,
        shift_steps: int,
        wrap: bool = False
    ) -> np.ndarray:
        """Shift sequence temporally (rotate indices)"""
        seq = sequence.copy()
        if wrap:
            # Circular shift (keep dimensionality)
            seq = np.roll(seq, shift_steps, axis=0)
        else:
            # Linear shift with zero-padding (changes temporal alignment)
            if shift_steps > 0:
                seq = np.vstack([np.zeros((shift_steps, seq.shape[1])), seq[:-shift_steps]])
            elif shift_steps < 0:
                seq = np.vstack([seq[-shift_steps:], np.zeros((-shift_steps, seq.shape[1]))])
        
        return seq
    
    def augment_with_concatenation(
        self,
        sequences: List[np.ndarray]
    ) -> np.ndarray:
        """Concatenate 2-3 overlapping windows"""
        # Take first and third sequence, overlap middle section
        if len(sequences) < 2:
            return sequences[0]
        
        seq1 = sequences[0]
        seq2 = sequences[1]
        
        # Overlap: last 25% of seq1 + first 75% of seq2
        overlap_size = seq1.shape[0] // 4
        
        spliced = np.vstack([
            seq1[:-overlap_size],
            seq2[overlap_size:]
        ])
        
        # Truncate/pad to original length
        if spliced.shape[0] > seq1.shape[0]:
            spliced = spliced[:seq1.shape[0]]
        elif spliced.shape[0] < seq1.shape[0]:
            padding = np.zeros((seq1.shape[0] - spliced.shape[0], seq1.shape[1]))
            spliced = np.vstack([spliced, padding])
        
        return spliced
    
    def augment_with_interleaving(
        self,
        sequences: List[np.ndarray],
        blend_factor: float = 0.3
    ) -> np.ndarray:
        """Blend patterns from 2 sequences (weighted mix)"""
        if len(sequences) < 2:
            return sequences[0]
        
        seq1 = sequences[0]
        seq2 = sequences[1]
        
        # Ensure same shape
        if seq1.shape != seq2.shape:
            seq2 = seq2[:seq1.shape[0]]
        
        # Weighted blend: (1-α)×seq1 + α×seq2
        blended = (1 - blend_factor) * seq1 + blend_factor * seq2
        
        return blended
    
    def generate_augmentations(
        self,
        base_sequences: List[np.ndarray],
        target_count: int = 400
    ) -> List[Tuple[np.ndarray, str]]:
        """
        Generate augmented sequences.
        
        Args:
            base_sequences: List of base sequences
            target_count: Total target sequences
            
        Returns:
            List of (augmented_sequence, augmentation_type)
        """
        logger.info(f"Generating {target_count} augmentations from {len(base_sequences)} base sequences")
        
        per_base = target_count // len(base_sequences)
        augmented = []
        
        for base_idx, base_seq in enumerate(base_sequences):
            logger.debug(f"Augmenting base sequence {base_idx + 1}/{len(base_sequences)} ({per_base} variants)")
            
            # Fixed plan: distribute augmentations across techniques
            noise_count = int(0.60 * per_base)
            scale_count = int(0.20 * per_base)
            shift_count = int(0.10 * per_base)
            concat_count = int(0.05 * per_base)
            interleave_count = per_base - (noise_count + scale_count + shift_count + concat_count)
            
            # Noise augmentations
            for i in range(noise_count):
                noise_level = self.random_state.uniform(0.01, 0.05)
                aug_seq = self.augment_with_noise(base_seq, noise_level=noise_level)
                augmented.append((aug_seq, f"noise_σ={noise_level:.3f}"))
            
            # Scaling augmentations
            for i in range(scale_count):
                scale = self.random_state.choice([0.9, 1.1, 1.2])
                aug_seq = self.augment_with_scaling(base_seq, scale_factor=scale)
                augmented.append((aug_seq, f"scale_×{scale}"))
            
            # Time-shift augmentations
            for i in range(shift_count):
                shift = self.random_state.randint(-12, 12)  # ±1 hour
                aug_seq = self.augment_with_timeshift(base_seq, shift_steps=shift)
                augmented.append((aug_seq, f"shift_{shift:+d}steps"))
            
            # Concatenation (mix with other base)
            for i in range(concat_count):
                other_idx = self.random_state.randint(0, len(base_sequences))
                aug_seq = self.augment_with_concatenation([base_seq, base_sequences[other_idx]])
                augmented.append((aug_seq, f"concat_with_base{other_idx}"))
            
            # Interleaving (blend with other base)
            for i in range(interleave_count):
                other_idx = self.random_state.randint(0, len(base_sequences))
                blend = self.random_state.uniform(0.1, 0.5)
                aug_seq = self.augment_with_interleaving(
                    [base_seq, base_sequences[other_idx]],
                    blend_factor=blend
                )
                augmented.append((aug_seq, f"interleave_α={blend:.2f}"))
        
        logger.info(f"✓ Generated {len(augmented)} augmented sequences")
        logger.info(f"  - Noise: {noise_count * len(base_sequences)}")
        logger.info(f"  - Scaling: {scale_count * len(base_sequences)}")
        logger.info(f"  - Time-shift: {shift_count * len(base_sequences)}")
        logger.info(f"  - Concatenation: {concat_count * len(base_sequences)}")
        logger.info(f"  - Interleaving: {interleave_count * len(base_sequences)}")
        
        return augmented


def main():
    """Testing"""
    logging.basicConfig(level=logging.INFO)
    
    # Create mock base sequences
    np.random.seed(42)
    base_seqs = [
        np.random.randn(576, 15) for _ in range(6)
    ]
    
    augmentor = PositiveSequenceAugmentor()
    augmented = augmentor.generate_augmentations(base_seqs, target_count=402)
    
    print(f"\n✓ Generated {len(augmented)} sequences")
    print(f"First augmentation type: {augmented[0][1]}")
    print(f"Shape: {augmented[0][0].shape}")


if __name__ == "__main__":
    main()
