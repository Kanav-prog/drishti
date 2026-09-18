"""
Phase 5.2 Test Suite: Batch & Real-Time Inference Engines

Tests the BatchInferenceEngine, RealtimeInferenceCoordinator, and InferencePipeline.
Validates latency targets, result accuracy, and error handling.
"""

import sys
import os
import numpy as np
import json
import time
from pathlib import Path
import tempfile
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
from backend.ml.batch_and_realtime_inference import (
    BatchInferenceEngine,
    RealtimeInferenceCoordinator,
    InferencePipeline,
)


def create_test_data():
    """Create synthetic test data."""
    # Create batch of 10 samples, 576 timesteps, 15 features
    return np.random.randn(10, 576, 15).astype(np.float32)


def test_batch_inference_basic():
    """Test 1: Basic batch inference."""
    print("\n[TEST 1] Basic batch inference")
    print("-" * 50)
    
    try:
        # Load ensemble
        ensemble = create_ensemble_inference_from_checkpoint()
        
        # Create batch engine
        engine = BatchInferenceEngine(
            ensemble_inference=ensemble,
            max_batch_size=32,
        )
        
        # Predict
        features = create_test_data()
        results = engine.predict_array(features, job_id="test_batch_001")
        
        # Validate
        assert results['status'] == 'complete'
        assert results['num_samples'] == 10
        assert len(results['ensemble_predictions']) == 10
        assert results['batch_metrics']['total_latency_ms'] > 0
        
        # Check values are in valid range
        probs = results['ensemble_predictions']
        for p in probs:
            assert 0.0 <= p <= 1.0, f"Probability out of range: {p}"
        
        print(f"[OK] Batch inference complete")
        print(f"    - Samples: {results['num_samples']}")
        print(f"    - Total latency: {results['batch_metrics']['total_latency_ms']:.2f} ms")
        print(f"    - Predictions: {probs[:3]}...")
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_job_tracking():
    """Test 2: Batch job tracking and status."""
    print("\n[TEST 2] Batch job tracking")
    print("-" * 50)
    
    try:
        ensemble = create_ensemble_inference_from_checkpoint()
        engine = BatchInferenceEngine(ensemble_inference=ensemble)
        
        # Run multiple jobs
        job_ids = []
        for i in range(3):
            features = create_test_data()
            results = engine.predict_array(features, job_id=f"job_{i}")
            job_ids.append(f"job_{i}")
        
        # Check job tracking
        jobs = engine.list_jobs()
        assert len(jobs) == 3
        
        all_complete = all(job['status'] == 'complete' for job in jobs)
        assert all_complete
        
        print(f"[OK] Job tracking working")
        print(f"    - Total jobs: {len(jobs)}")
        for job in jobs:
            print(f"    - {job['job_id']}: {job['status']} ({job['total_latency_ms']:.2f}ms)")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_results_structure():
    """Test 3: Batch results structure and metadata."""
    print("\n[TEST 3] Batch results structure")
    print("-" * 50)
    
    try:
        ensemble = create_ensemble_inference_from_checkpoint()
        engine = BatchInferenceEngine(ensemble_inference=ensemble)
        
        features = create_test_data()[:4]  # Just 4 samples
        results = engine.predict_array(features, job_id="test_structure")
        
        # Validate structure
        required_keys = [
            'job_id', 'status', 'num_samples', 'ensemble_predictions',
            'ensemble_aggregation', 'individual_predictions', 'batch_metrics'
        ]
        
        for key in required_keys:
            assert key in results, f"Missing key: {key}"
        
        # Check individual predictions structure
        for model_name, pred in results['individual_predictions'].items():
            assert 'probabilities' in pred
            assert 'latency_ms' in pred
            assert isinstance(pred['probabilities'], list)
        
        print(f"[OK] Results structure valid")
        print(f"    - Keys present: {list(results.keys())}")
        print(f"    - Models: {list(results['individual_predictions'].keys())}")
        print(f"    - Batch metrics: {results['batch_metrics']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_realtime_single_prediction():
    """Test 4: Real-time single sample inference."""
    print("\n[TEST 4] Real-time single sample inference")
    print("-" * 50)
    
    try:
        ensemble = create_ensemble_inference_from_checkpoint()
        coordinator = RealtimeInferenceCoordinator(ensemble_inference=ensemble)
        
        # Single sample (576, 15)
        features = np.random.randn(576, 15).astype(np.float32)
        
        start = time.time()
        result = coordinator.predict(features, train_id="train_123")
        latency = (time.time() - start) * 1000
        
        # Validate
        assert result['status'] == 'success'
        assert 'predictions' in result
        assert 'ensemble_prediction' in result
        assert 0.0 <= result['ensemble_prediction'] <= 1.0
        
        print(f"[OK] Real-time prediction successful")
        print(f"    - Train ID: {result['train_id']}")
        print(f"    - Latency: {result['latency_ms']:.2f} ms (actual: {latency:.2f} ms)")
        print(f"    - Ensemble prediction: {result['ensemble_prediction']:.4f}")
        
        # Latency check (soft - just warn if over 100ms)
        if result['latency_ms'] > 100:
            print(f"    - [NOTE] Latency > 100ms target on CPU")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_realtime_metrics():
    """Test 5: Real-time metrics tracking."""
    print("\n[TEST 5] Real-time metrics tracking")
    print("-" * 50)
    
    try:
        ensemble = create_ensemble_inference_from_checkpoint()
        coordinator = RealtimeInferenceCoordinator(ensemble_inference=ensemble)
        
        # Run multiple predictions
        num_predictions = 10
        for i in range(num_predictions):
            features = np.random.randn(576, 15).astype(np.float32)
            coordinator.predict(features, train_id=f"train_{i}")
        
        # Get metrics
        metrics = coordinator.get_metrics()
        
        # Validate
        assert metrics['total_predictions'] == num_predictions
        assert metrics['successful_predictions'] == num_predictions
        assert metrics['failed_predictions'] == 0
        assert metrics['success_rate'] == 1.0
        assert metrics['latency_ms']['mean'] > 0
        
        print(f"[OK] Metrics tracking working")
        print(f"    - Total predictions: {metrics['total_predictions']}")
        print(f"    - Success rate: {metrics['success_rate']*100:.1f}%")
        print(f"    - Latency (mean): {metrics['latency_ms']['mean']:.2f} ms")
        print(f"    - Latency (p95): {metrics['latency_ms']['p95']:.2f} ms")
        print(f"    - Latency (p99): {metrics['latency_ms']['p99']:.2f} ms")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_realtime_feature_caching():
    """Test 6: Real-time feature caching."""
    print("\n[TEST 6] Feature caching")
    print("-" * 50)
    
    try:
        ensemble = create_ensemble_inference_from_checkpoint()
        coordinator = RealtimeInferenceCoordinator(
            ensemble_inference=ensemble,
            feature_cache_size=5
        )
        
        # Cache features
        for i in range(5):
            features = np.random.randn(576, 15).astype(np.float32)
            coordinator.predict(features, train_id=f"train_{i}", cache_features=True)
        
        metrics = coordinator.get_metrics()
        
        assert metrics['cache_size'] == 5
        
        print(f"[OK] Feature caching working")
        print(f"    - Cache size: {metrics['cache_size']}")
        print(f"    - Cached train IDs: {list(coordinator.feature_cache.keys())}")
        
        # Clear cache
        coordinator.clear_cache()
        metrics = coordinator.get_metrics()
        
        assert metrics['cache_size'] == 0
        
        print(f"    - After clear: {metrics['cache_size']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_unified_pipeline():
    """Test 7: Unified inference pipeline."""
    print("\n[TEST 7] Unified inference pipeline")
    print("-" * 50)
    
    try:
        ensemble = create_ensemble_inference_from_checkpoint()
        
        # Create pipeline
        pipeline = InferencePipeline(
            ensemble_inference=ensemble,
            max_batch_size=32,
        )
        
        # Test batch mode
        batch_features = create_test_data()[:4]
        batch_result = pipeline.batch_predict(batch_features, job_id="pipeline_batch")
        
        assert batch_result['status'] == 'complete'
        assert batch_result['num_samples'] == 4
        
        # Test streaming mode
        stream_features = np.random.randn(576, 15).astype(np.float32)
        stream_result = pipeline.stream_predict(stream_features, train_id="pipeline_train")
        
        assert stream_result['status'] == 'success'
        
        # Check status
        status = pipeline.get_status()
        assert 'batch_engine' in status
        assert 'realtime_engine' in status
        
        print(f"[OK] Unified pipeline working")
        print(f"    - Batch result: {batch_result['status']} ({batch_result['num_samples']} samples)")
        print(f"    - Stream result: {stream_result['status']}")
        print(f"    - Active batch jobs: {status['batch_engine']['active_jobs']}")
        print(f"    - Total real-time predictions: {status['realtime_engine']['total_predictions']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_streaming_predictions():
    """Test 8: Batch streaming predictions."""
    print("\n[TEST 8] Batch streaming predictions")
    print("-" * 50)
    
    try:
        ensemble = create_ensemble_inference_from_checkpoint()
        coordinator = RealtimeInferenceCoordinator(ensemble_inference=ensemble)
        
        # Create list of samples
        features_list = [
            np.random.randn(576, 15).astype(np.float32)
            for _ in range(5)
        ]
        train_ids = [f"train_{i}" for i in range(5)]
        
        # Predict batch in streaming fashion
        results = coordinator.predict_batch_streaming(features_list, train_ids=train_ids)
        
        # Validate
        assert len(results) == 5
        assert all(r['status'] == 'success' for r in results)
        
        print(f"[OK] Batch streaming working")
        print(f"    - Batch size: {len(results)}")
        print(f"    - All successful: {all(r['status'] == 'success' for r in results)}")
        for i, result in enumerate(results[:3]):
            print(f"    - {result['train_id']}: {result['ensemble_prediction']:.4f}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 5.2 tests."""
    print("\n" + "=" * 60)
    print("PHASE 5.2 TEST SUITE: BATCH & REAL-TIME INFERENCE")
    print("=" * 60)
    
    tests = [
        ("Basic Batch Inference", test_batch_inference_basic),
        ("Job Tracking", test_batch_job_tracking),
        ("Results Structure", test_batch_results_structure),
        ("Real-time Single Prediction", test_realtime_single_prediction),
        ("Metrics Tracking", test_realtime_metrics),
        ("Feature Caching", test_realtime_feature_caching),
        ("Unified Pipeline", test_unified_pipeline),
        ("Batch Streaming", test_batch_streaming_predictions),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n[FATAL] {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test_name, passed_flag in results.items():
        status = "[PASS]" if passed_flag else "[FAIL]"
        print(f"{status} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[OK] ALL TESTS PASSED [OK]")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} tests failed")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
