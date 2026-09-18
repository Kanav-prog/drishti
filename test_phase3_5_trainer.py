#!/usr/bin/env python3
"""
Quick runner for Phase 3.5 ML Training Harness tests.
Properly handles module imports and path configuration.
"""

import sys
import os

# Add workspace root to path
workspace_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, workspace_root)

if __name__ == "__main__":
    from backend.ml.training_harness import test_trainer
    
    print("\n" + "="*70)
    print("PHASE 3.5: ML TRAINING HARNESS - QUICK TEST")
    print("="*70 + "\n")
    
    test_trainer()
    
    print("\n" + "="*70)
    print("[OK] Phase 3.5 trainer test completed successfully!")
    print("="*70)
