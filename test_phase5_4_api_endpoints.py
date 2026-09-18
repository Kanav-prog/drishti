"""
Phase 5.4 Test Suite: Inference API Endpoints

Tests the FastAPI inference endpoints:
- POST /api/inference/predict
- POST /api/inference/batch
- WS /ws/inference/stream
- GET /api/inference/models
- GET /api/inference/health
"""

import sys
import os
import numpy as np
import json
import pytest
from httpx import AsyncClient, Client
from fastapi.testclient import TestClient
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.main_app import app


# Initialize test client
client = TestClient(app)


def create_test_features():
    """Create synthetic test features (576, 15)."""
    return np.random.randn(576, 15).tolist()


def create_traditional_inputs():
    """Create traditional method inputs."""
    return {
        'bayesian_risk': 0.7,
        'anomaly_score': 75.0,
        'dbscan_anomaly': False,
        'causal_risk': 0.6,
    }


def test_health_check():
    """Test 1: Health check endpoint."""
    print("\n[TEST 1] Health check endpoint")
    print("-" * 50)
    
    try:
        response = client.get("/api/inference/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] in ['healthy', 'unhealthy']
        assert data['service'] == 'inference'
        
        print(f"[OK] Health check working")
        print(f"    - Status: {data['status']}")
        print(f"    - Service: {data['service']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_models_status():
    """Test 2: Get models status."""
    print("\n[TEST 2] Get models status endpoint")
    print("-" * 50)
    
    try:
        response = client.get("/api/inference/models")
        assert response.status_code == 200
        data = response.json()
        assert 'status' in data
        assert 'models_loaded' in data
        assert 'registered_models' in data
        assert 'inference_metrics' in data
        
        print(f"[OK] Models status retrieved")
        print(f"    - Status: {data['status']}")
        print(f"    - Models loaded: {data['models_loaded']}")
        print(f"    - Registered: {data['registered_models']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_predict_single_valid():
    """Test 3: Single prediction with valid input."""
    print("\n[TEST 3] Single prediction with valid input")
    print("-" * 50)
    
    try:
        features = create_test_features()
        traditional = create_traditional_inputs()
        
        payload = {
            'train_id': 'train_test_001',
            'features': features,
            **traditional,
            'auc_weights': {'lstm_model_2': 0.55},
        }
        
        response = client.post("/api/inference/predict", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data['train_id'] == 'train_test_001'
        assert 'alert_fires' in data
        assert 'severity' in data
        assert 'consensus_risk' in data
        assert 'methods_agreeing' in data
        assert 'neural_predictions' in data
        assert 'votes_breakdown' in data
        assert len(data['votes_breakdown']) == 5  # 5 methods
        
        print(f"[OK] Single prediction successful")
        print(f"    - Train ID: {data['train_id']}")
        print(f"    - Alert fires: {data['alert_fires']}")
        print(f"    - Severity: {data['severity']}")
        print(f"    - Methods agreeing: {data['methods_agreeing']}/5")
        print(f"    - Neural latency: {data['neural_latency_ms']:.2f} ms")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_predict_single_invalid_shape():
    """Test 4: Single prediction with invalid feature shape."""
    print("\n[TEST 4] Single prediction with invalid shape")
    print("-" * 50)
    
    try:
        features = np.random.randn(100, 10).tolist()  # Wrong shape
        traditional = create_traditional_inputs()
        
        payload = {
            'train_id': 'train_test_bad',
            'features': features,
            **traditional,
        }
        
        response = client.post("/api/inference/predict", json=payload)
        assert response.status_code == 422  # Validation error
        
        print(f"[OK] Invalid shape rejected")
        print(f"    - Status code: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_prediction_valid():
    """Test 5: Batch prediction with multiple samples."""
    print("\n[TEST 5] Batch prediction with multiple samples")
    print("-" * 50)
    
    try:
        train_ids = ['train_batch_001', 'train_batch_002', 'train_batch_003']
        features = [create_test_features() for _ in train_ids]
        
        payload = {
            'job_id': f'batch_test_{datetime.now().timestamp()}',
            'train_ids': train_ids,
            'features': features,
            'aggregation': 'mean',
            'auc_weights': {'lstm_model_2': 0.55},
        }
        
        response = client.post("/api/inference/batch", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert data['status'] == 'complete'
        assert data['num_samples'] == 3
        assert len(data['predictions']) == 3
        assert data['total_latency_ms'] > 0
        
        print(f"[OK] Batch prediction successful")
        print(f"    - Job ID: {data['job_id']}")
        print(f"    - Status: {data['status']}")
        print(f"    - Samples: {data['num_samples']}")
        print(f"    - Total latency: {data['total_latency_ms']:.2f} ms")
        print(f"    - Per-sample: {data['total_latency_ms']/data['num_samples']:.2f} ms")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_prediction_empty():
    """Test 6: Batch prediction with empty input."""
    print("\n[TEST 6] Batch prediction with empty input")
    print("-" * 50)
    
    try:
        payload = {
            'job_id': 'batch_empty',
            'train_ids': [],
            'features': [],
        }
        
        response = client.post("/api/inference/batch", json=payload)
        assert response.status_code == 422  # Validation error
        
        print(f"[OK] Empty batch rejected")
        print(f"    - Status code: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_prediction_invalid_shape():
    """Test 7: Batch prediction with invalid shapes."""
    print("\n[TEST 7] Batch prediction with invalid shapes")
    print("-" * 50)
    
    try:
        train_ids = ['train_bad_001', 'train_bad_002']
        features = [
            np.random.randn(576, 15).tolist(),
            np.random.randn(100, 10).tolist(),  # Wrong shape in second sample
        ]
        
        payload = {
            'train_ids': train_ids,
            'features': features,
        }
        
        response = client.post("/api/inference/batch", json=payload)
        assert response.status_code == 422  # Validation error
        
        print(f"[OK] Invalid shape in batch rejected")
        print(f"    - Status code: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_size_limit():
    """Test 8: Batch prediction size limit."""
    print("\n[TEST 8] Batch prediction size limit enforcement")
    print("-" * 50)
    
    try:
        # Try to create batch with 101 samples (exceeds limit of 100)
        train_ids = [f'train_{i}' for i in range(101)]
        features = [create_test_features() for _ in range(101)]
        
        payload = {
            'train_ids': train_ids,
            'features': features,
        }
        
        response = client.post("/api/inference/batch", json=payload)
        assert response.status_code == 422  # Pydantic validation error
        
        print(f"[OK] Batch size limit enforced")
        print(f"    - Status code: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_missing_required_fields():
    """Test 9: Predict endpoint with missing required fields."""
    print("\n[TEST 9] Predict endpoint with missing required fields")
    print("-" * 50)
    
    try:
        # Missing features
        payload = {
            'train_id': 'train_incomplete',
            'bayesian_risk': 0.7,
            # Missing other required fields
        }
        
        response = client.post("/api/inference/predict", json=payload)
        assert response.status_code == 422  # Validation error
        
        print(f"[OK] Missing fields rejected")
        print(f"    - Status code: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_invalid_risk_ranges():
    """Test 10: Predict endpoint with invalid risk ranges."""
    print("\n[TEST 10] Predict endpoint with invalid risk ranges")
    print("-" * 50)
    
    try:
        features = create_test_features()
        
        payload = {
            'train_id': 'train_bad_range',
            'features': features,
            'bayesian_risk': 1.5,  # Out of range (must be 0-1)
            'anomaly_score': 75.0,
            'dbscan_anomaly': False,
            'causal_risk': 0.6,
        }
        
        response = client.post("/api/inference/predict", json=payload)
        assert response.status_code == 422  # Validation error
        
        print(f"[OK] Invalid ranges rejected")
        print(f"    - Status code: {response.status_code}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 5.4 API tests."""
    print("\n" + "=" * 60)
    print("PHASE 5.4 TEST SUITE: INFERENCE API ENDPOINTS")
    print("=" * 60)
    
    tests = [
        ("Health Check", test_health_check),
        ("Models Status", test_models_status),
        ("Predict Valid", test_predict_single_valid),
        ("Predict Invalid Shape", test_predict_single_invalid_shape),
        ("Batch Valid", test_batch_prediction_valid),
        ("Batch Empty", test_batch_prediction_empty),
        ("Batch Invalid Shape", test_batch_prediction_invalid_shape),
        ("Batch Size Limit", test_batch_size_limit),
        ("Missing Fields", test_missing_required_fields),
        ("Invalid Ranges", test_invalid_risk_ranges),
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
