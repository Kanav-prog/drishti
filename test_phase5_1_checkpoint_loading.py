#!/usr/bin/env python3
"""
Phase 5.1 Test: Checkpoint Loading & Model Initialization
Verify that Phase 4 models can be loaded and run inference.
"""

import sys
import os
import numpy as np
import torch
import json
from pathlib import Path

# Add workspace to path
workspace_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, workspace_root)


def test_device_manager():
    """Test device selection."""
    from backend.ml.inference_models import DeviceManager
    
    print("\n" + "="*70)
    print("TEST 1: Device Manager")
    print("="*70)
    
    device = DeviceManager.get_device(prefer_gpu=False)
    print(f"✓ Device selected: {device}")
    
    device_info = DeviceManager.get_device_info()
    print(f"✓ Device info: {device_info}")
    
    assert device is not None
    print("✓ Device manager test PASSED")


def test_model_loader():
    """Test loading models from Phase 4 checkpoints."""
    from backend.ml.inference_models import ModelLoader, DeviceManager
    from backend.ml.models.lstm_classifier import LSTMTemporalClassifier
    
    print("\n" + "="*70)
    print("TEST 2: Model Loader")
    print("="*70)
    
    checkpoint_dir = "./phase4_ensemble_checkpoints"
    device = DeviceManager.get_device(prefer_gpu=False)
    
    loader = ModelLoader(checkpoint_dir, device)
    print(f"✓ ModelLoader initialized")
    
    # Get metadata
    metrics = loader.get_ensemble_metrics()
    print(f"✓ Ensemble metrics loaded: {len(metrics)} keys")
    print(f"  - Models trained: {metrics['num_models']}")
    print(f"  - Mean AUC: {metrics['avg_val_auc']:.4f}")
    print(f"  - Best model: {metrics['best_model']} ({metrics['best_auc']:.4f})")
    
    # Get rankings
    rankings = loader.get_model_rankings()
    print(f"✓ Model rankings: {len(rankings)} models")
    for ranking in rankings:
        print(f"  {ranking['rank']}. {ranking['model'].upper()}: AUC={ranking['val_auc']:.4f}")
    
    # Try loading first model (lstm_model_2 with AUC=0.55)
    model_name = rankings[0]['model']
    
    # Use architecture matching the actual checkpoint
    # lstm_model_2: 1 LSTM layer, hidden_size 64, embedding_dim 32
    # lstm_model_1: 2 LSTM layers, hidden_size 128, embedding_dim 32
    if model_name == 'lstm_model_2':
        config = {
            'input_size': 15,
            'hidden_size': 64,
            'num_layers': 1,
            'embedding_dim': 32,
            'architecture': 'lstm',
        }
    else:  # lstm_model_1
        config = {
            'input_size': 15,
            'hidden_size': 128,
            'num_layers': 2,
            'embedding_dim': 32,
            'architecture': 'lstm',
        }
    
    model, metadata = loader.load_model(LSTMTemporalClassifier, model_name, config)
    print(f"✓ Loaded model: {model_name}")
    print(f"  - Best AUC: {metadata.best_auc:.4f}")
    print(f"  - Parameters: {metadata.total_parameters:,}")
    print(f"  - Size: {metadata.weights_size_mb:.2f} MB")
    
    assert model is not None
    assert metadata.best_auc > 0
    print("✓ Model loader test PASSED")


def test_ensemble_inference_creation():
    """Test creating ensemble inference engine."""
    from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
    
    print("\n" + "="*70)
    print("TEST 3: Ensemble Inference Engine Creation")
    print("="*70)
    
    engine = create_ensemble_inference_from_checkpoint(
        checkpoint_dir="./phase4_ensemble_checkpoints",
        prefer_gpu=False,
    )
    
    print(f"✓ EnsembleInference engine created")
    
    models = engine.list_models()
    print(f"✓ Models loaded: {len(models)}")
    for model_name in models:
        print(f"  - {model_name}")
    
    model_info = engine.get_model_info()
    for name, info in model_info.items():
        print(f"✓ {name}:")
        print(f"  - Architecture: {info['architecture']}")
        print(f"  - Best AUC: {info['best_auc']:.4f}")
        print(f"  - Parameters: {info['parameters']:,}")
    
    assert len(models) > 0
    print("✓ Ensemble inference creation test PASSED")


def test_batch_inference():
    """Test batch inference."""
    from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
    
    print("\n" + "="*70)
    print("TEST 4: Batch Inference")
    print("="*70)
    
    engine = create_ensemble_inference_from_checkpoint(
        checkpoint_dir="./phase4_ensemble_checkpoints",
        prefer_gpu=False,
    )
    
    # Create dummy batch
    batch_size = 4
    seq_len = 576
    n_features = 15
    
    features = np.random.randn(batch_size, seq_len, n_features).astype(np.float32)
    print(f"✓ Created dummy batch: shape={features.shape}")
    
    # Run inference
    print(f"Running batch inference...")
    batch_result = engine.predict_batch(features)
    
    print(f"✓ Batch inference complete")
    print(f"  - Batch ID: {batch_result.batch_id}")
    print(f"  - Batch size: {batch_result.batch_size}")
    print(f"  - Models run: {len(batch_result.predictions)}")
    print(f"  - Preprocessing: {batch_result.preprocessing_time_ms:.2f} ms")
    print(f"  - Inference: {batch_result.inference_time_ms:.2f} ms")
    print(f"  - Total latency: {batch_result.total_latency_ms:.2f} ms")
    
    # Check predictions
    for model_name, pred_result in batch_result.predictions.items():
        print(f"\n  {model_name}:")
        print(f"    - Logits shape: {pred_result.logits.shape}")
        print(f"    - Probs shape: {pred_result.probabilities.shape}")
        print(f"    - Probs range: [{pred_result.probabilities.min():.4f}, {pred_result.probabilities.max():.4f}]")
        print(f"    - Latency: {pred_result.latency_ms:.2f} ms")
        
        # Verify shapes and ranges
        assert pred_result.logits.shape == (batch_size,), f"Wrong logits shape: {pred_result.logits.shape}"
        assert pred_result.probabilities.shape == (batch_size,), f"Wrong probs shape: {pred_result.probabilities.shape}"
        assert 0 <= pred_result.probabilities.min() <= 1, "Probabilities out of range"
        assert 0 <= pred_result.probabilities.max() <= 1, "Probabilities out of range"
    
    # Test ensemble aggregation
    ensemble_pred = engine.get_ensemble_prediction(batch_result, aggregation="mean")
    print(f"\n✓ Ensemble aggregation (mean):")
    print(f"  - Shape: {ensemble_pred.shape}")
    print(f"  - Range: [{ensemble_pred.min():.4f}, {ensemble_pred.max():.4f}]")
    
    assert ensemble_pred.shape == (batch_size,)
    assert 0 <= ensemble_pred.min() <= 1
    assert 0 <= ensemble_pred.max() <= 1
    
    print("✓ Batch inference test PASSED")


def test_single_inference():
    """Test single sample inference."""
    from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
    
    print("\n" + "="*70)
    print("TEST 5: Single Sample Inference")
    print("="*70)
    
    engine = create_ensemble_inference_from_checkpoint(
        checkpoint_dir="./phase4_ensemble_checkpoints",
        prefer_gpu=False,
    )
    
    # Create dummy sample
    seq_len = 576
    n_features = 15
    features = np.random.randn(seq_len, n_features).astype(np.float32)
    print(f"✓ Created dummy sample: shape={features.shape}")
    
    # Run inference
    predictions = engine.predict_single(features)
    
    print(f"✓ Single inference complete")
    print(f"  - Models run: {len(predictions)}")
    
    for model_name, prob in predictions.items():
        print(f"  - {model_name}: {prob:.4f}")
        assert 0 <= prob <= 1, f"Probability out of range: {prob}"
    
    print("✓ Single inference test PASSED")


def test_model_warmup():
    """Test model warmup."""
    from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
    
    print("\n" + "="*70)
    print("TEST 6: Model Warmup")
    print("="*70)
    
    engine = create_ensemble_inference_from_checkpoint(
        checkpoint_dir="./phase4_ensemble_checkpoints",
        prefer_gpu=False,
    )
    
    print("Running warmup...")
    engine.warmup(sample_size=32, seq_len=576, n_features=15)
    print("✓ Warmup complete")


def test_inference_statistics():
    """Test inference statistics tracking."""
    from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
    
    print("\n" + "="*70)
    print("TEST 7: Inference Statistics")
    print("="*70)
    
    engine = create_ensemble_inference_from_checkpoint(
        checkpoint_dir="./phase4_ensemble_checkpoints",
        prefer_gpu=False,
    )
    
    # Run several batches
    for i in range(3):
        features = np.random.randn(8, 576, 15).astype(np.float32)
        _ = engine.predict_batch(features, batch_id=f"batch_{i}")
    
    # Get statistics
    stats = engine.get_statistics()
    
    print(f"✓ Statistics collected:")
    for model_name, stat in stats.items():
        print(f"  {model_name}:")
        print(f"    - Predictions: {stat['predictions']}")
        print(f"    - Mean latency: {stat['mean_latency_ms']:.2f} ms")
        print(f"    - Total latency: {stat['total_latency_ms']:.2f} ms")
    
    print("✓ Statistics test PASSED")


def test_model_status():
    """Test model status report."""
    from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
    
    print("\n" + "="*70)
    print("TEST 8: Model Status Report")
    print("="*70)
    
    engine = create_ensemble_inference_from_checkpoint(
        checkpoint_dir="./phase4_ensemble_checkpoints",
        prefer_gpu=False,
    )
    
    status = engine.get_model_status()
    
    print(f"✓ Engine status:")
    print(f"  - Device: {status['device']}")
    print(f"  - Models loaded: {status['num_models_loaded']}")
    print(f"  - Device info: {status['device_info']}")
    
    print("✓ Status report test PASSED")


def main():
    """Run all Phase 5.1 tests."""
    print("\n" + "="*70)
    print("PHASE 5.1: CHECKPOINT LOADING & MODEL INITIALIZATION - TEST SUITE")
    print("="*70)
    
    tests = [
        ("Device Manager", test_device_manager),
        ("Model Loader", test_model_loader),
        ("Ensemble Inference Creation", test_ensemble_inference_creation),
        ("Batch Inference", test_batch_inference),
        ("Single Inference", test_single_inference),
        ("Model Warmup", test_model_warmup),
        ("Inference Statistics", test_inference_statistics),
        ("Model Status", test_model_status),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n✗ {test_name} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n[OK] Phase 5.1 tests PASSED!")
        return 0
    else:
        print(f"\n[FAIL] {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

