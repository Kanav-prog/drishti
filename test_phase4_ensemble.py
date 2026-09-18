#!/usr/bin/env python3
"""
Phase 4 Ensemble Training Coordination - Test Runner
Demonstrates multi-model ensemble training with performance comparison.
"""

import sys
import os

# Add workspace root to path
workspace_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, workspace_root)

if __name__ == "__main__":
    from backend.ml.training_harness import test_ensemble_trainer
    
    print("\n" + "="*70)
    print("PHASE 4: ENSEMBLE TRAINING COORDINATION")
    print("="*70 + "\n")
    
    test_ensemble_trainer()
