"""
Phase 5.3 Test Suite: Neural Ensemble Voting Integration

Validates:
1. Neural voting with AUC weighting
2. Integration with traditional voting (4 methods → 5 methods)
3. Enhanced consensus computation
4. Alert generation with neural boost
5. Integrated pipeline end-to-end
"""

import sys
import os
import numpy as np
import json
from datetime import datetime
import uuid
from typing import Dict

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.ml.ensemble import EnsembleVoter, AlertSeverity
from backend.ml.inference_engine import create_ensemble_inference_from_checkpoint
from backend.ml.batch_and_realtime_inference import InferencePipeline
from backend.ml.neural_ensemble_voting import (
    NeuralEnsembleVoter,
    NeuralPredictionInput,
    IntegratedInferencePipeline,
)


def create_test_neural_input(
    models_probs: Dict[str, float] = None,
    models_aucs: Dict[str, float] = None,
) -> NeuralPredictionInput:
    """Create test neural input."""
    from typing import Dict
    
    if models_probs is None:
        models_probs = {
            'lstm_model_2': 0.65,  # Moderate accident probability
            'lstm_model_1_fallback': 0.58,
        }
    
    if models_aucs is None:
        models_aucs = {
            'lstm_model_2': 0.55,  # Phase 4 AUC
            'lstm_model_1_fallback': 0.50,
        }
    
    return NeuralPredictionInput(
        ensemble_probabilities=models_probs,
        model_auc_scores=models_aucs,
        confidence=0.75,
    )


def test_neural_voting_basic():
    """Test 1: Basic neural voting with AUC weighting."""
    print("\n[TEST 1] Basic neural voting with AUC weighting")
    print("-" * 50)
    
    try:
        # Create voter
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter, neural_threshold=0.5)
        
        # Create neural input
        neural_input = create_test_neural_input()
        
        # Vote
        neural_vote = neural_voter.vote_neural_ensemble(neural_input)
        
        # Validate
        assert neural_vote['method_name'] == 'neural_ensemble'
        assert neural_vote['score'] > 0
        assert neural_vote['threshold'] == 50.0
        assert 'model_breakdown' in neural_vote
        
        print(f"[OK] Neural voting successful")
        print(f"    - Score: {neural_vote['score']:.2f}")
        print(f"    - Votes danger: {neural_vote['votes_danger']}")
        print(f"    - Confidence: {neural_vote['confidence']:.2f}")
        print(f"    - Models: {list(neural_vote['model_breakdown'].keys())}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auc_weighting():
    """Test 2: AUC weighting in neural voting."""
    print("\n[TEST 2] AUC weighting in neural voting")
    print("-" * 50)
    
    try:
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter, neural_threshold=0.5)
        
        # Create two scenarios: high AUC vs low AUC with multiple models
        neural_input_high_auc = NeuralPredictionInput(
            ensemble_probabilities={'model_high': 0.7, 'model_mid': 0.5},
            model_auc_scores={'model_high': 0.9, 'model_mid': 0.6},  # Higher AUCs
            confidence=0.75,
        )
        
        neural_input_low_auc = NeuralPredictionInput(
            ensemble_probabilities={'model_low': 0.7, 'model_mid': 0.5},  # Same probs
            model_auc_scores={'model_low': 0.5, 'model_mid': 0.5},   # Lower AUCs
            confidence=0.75,
        )
        
        vote_high_auc = neural_voter.vote_neural_ensemble(neural_input_high_auc)
        vote_low_auc = neural_voter.vote_neural_ensemble(neural_input_low_auc)
        
        # High AUC weights should produce higher score
        assert vote_high_auc['score'] >= vote_low_auc['score']
        
        print(f"[OK] AUC weighting working")
        print(f"    - High AUC (0.9): {vote_high_auc['score']:.2f}")
        print(f"    - Low AUC (0.5): {vote_low_auc['score']:.2f}")
        print(f"    - Difference: {vote_high_auc['score'] - vote_low_auc['score']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_enhanced_consensus():
    """Test 3: Enhanced consensus with 5 methods."""
    print("\n[TEST 3] Enhanced consensus computation with 5 methods")
    print("-" * 50)
    
    try:
        from backend.ml.ensemble import MethodVote
        
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter)
        
        # Create 4 traditional votes
        traditional_votes = [
            MethodVote(
                method_name="bayesian",
                score=70.0,
                threshold=70.0,
                votes_danger=True,
                confidence=0.85,
                explanation="Test vote 1"
            ),
            MethodVote(
                method_name="isolation_forest",
                score=50.0,
                threshold=80.0,
                votes_danger=False,
                confidence=0.80,
                explanation="Test vote 2"
            ),
            MethodVote(
                method_name="dbscan",
                score=90.0,
                threshold=50.0,
                votes_danger=True,
                confidence=0.85,
                explanation="Test vote 3"
            ),
            MethodVote(
                method_name="causal_dag",
                score=40.0,
                threshold=75.0,
                votes_danger=False,
                confidence=0.80,
                explanation="Test vote 4"
            ),
        ]
        
        # Neural vote
        neural_vote = {
            'score': 65.0,
            'votes_danger': True,
            'confidence': 0.75,
        }
        
        # Compute consensus
        n_danger, consensus_risk, neural_weight = neural_voter.compute_enhanced_consensus(
            traditional_votes, neural_vote
        )
        
        # Validate
        assert n_danger == 3  # 3 votes danger (bayesian, dbscan, neural)
        assert 50 < consensus_risk < 70  # Average of 5 scores
        assert neural_weight == 0.75
        
        print(f"[OK] Enhanced consensus computed")
        print(f"    - Methods voting danger: {n_danger}/5")
        print(f"    - Consensus risk: {consensus_risk:.2f}")
        print(f"    - Neural confidence: {neural_weight:.2f}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_voting_round_enhanced_no_alert():
    """Test 4: Enhanced voting round with <2 methods agreeing (no alert)."""
    print("\n[TEST 4] Enhanced voting round with <2 methods (no alert)")
    print("-" * 50)
    
    try:
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter, neural_threshold=0.5)
        
        # Low risk scenario (< 2 methods agree)
        neural_input = NeuralPredictionInput(
            ensemble_probabilities={'lstm_model_2': 0.3},
            model_auc_scores={'lstm_model_2': 0.55},
            confidence=0.75,
        )
        
        alert = neural_voter.voting_round_enhanced(
            train_id="train_test_no_alert",
            bayesian_risk=0.2,       # Low
            anomaly_score=30.0,      # Low
            dbscan_anomaly=False,    # Normal
            causal_risk=0.1,         # Low
            neural_input=neural_input,
            timestamp=datetime.now().isoformat(),
            alert_id=str(uuid.uuid4()),
        )
        
        # Validate
        assert alert.fires == False
        assert alert.severity == AlertSeverity.LOW
        assert alert.methods_agreeing < 2
        
        print(f"[OK] No-alert scenario working")
        print(f"    - Fires: {alert.fires}")
        print(f"    - Severity: {alert.severity.value}")
        print(f"    - Methods agreeing: {alert.methods_agreeing}/5")
        print(f"    - Consensus risk: {alert.consensus_risk:.2f}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_voting_round_enhanced_alert():
    """Test 5: Enhanced voting round with 3+ methods (HIGH alert)."""
    print("\n[TEST 5] Enhanced voting round with 3+ methods (HIGH alert)")
    print("-" * 50)
    
    try:
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter, neural_threshold=0.5)
        
        # High risk scenario (3+ methods agree)
        neural_input = NeuralPredictionInput(
            ensemble_probabilities={'lstm_model_2': 0.72},
            model_auc_scores={'lstm_model_2': 0.55},
            confidence=0.80,
        )
        
        alert = neural_voter.voting_round_enhanced(
            train_id="train_test_alert",
            bayesian_risk=0.8,       # High
            anomaly_score=85.0,      # High
            dbscan_anomaly=True,     # Anomalous
            causal_risk=0.4,         # Moderate
            neural_input=neural_input,
            timestamp=datetime.now().isoformat(),
            alert_id=str(uuid.uuid4()),
        )
        
        # Validate
        assert alert.fires == True
        assert alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        assert alert.methods_agreeing >= 3
        assert len(alert.votes) == 5  # Now 5 methods
        
        print(f"[OK] Alert firing scenario working")
        print(f"    - Fires: {alert.fires}")
        print(f"    - Severity: {alert.severity.value}")
        print(f"    - Methods agreeing: {alert.methods_agreeing}/5")
        print(f"    - Consensus risk: {alert.consensus_risk:.2f}")
        print(f"    - Actions: {len(alert.actions)} recommended")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_voting_round_enhanced_critical():
    """Test 6: Enhanced voting round with 4+ methods (CRITICAL alert)."""
    print("\n[TEST 6] Enhanced voting round with 4+ methods (CRITICAL)")
    print("-" * 50)
    
    try:
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter, neural_threshold=0.5)
        
        # Critical risk scenario (4+ methods agree)
        neural_input = NeuralPredictionInput(
            ensemble_probabilities={'lstm_model_2': 0.85},
            model_auc_scores={'lstm_model_2': 0.55},
            confidence=0.85,
        )
        
        alert = neural_voter.voting_round_enhanced(
            train_id="train_critical",
            bayesian_risk=0.9,       # Very high
            anomaly_score=95.0,      # Very high
            dbscan_anomaly=True,     # Anomalous
            causal_risk=0.85,        # Very high
            neural_input=neural_input,
            timestamp=datetime.now().isoformat(),
            alert_id=str(uuid.uuid4()),
        )
        
        # Validate
        assert alert.fires == True
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.methods_agreeing >= 4
        
        print(f"[OK] CRITICAL alert scenario working")
        print(f"    - Fires: {alert.fires}")
        print(f"    - Severity: {alert.severity.value}")
        print(f"    - Methods agreeing: {alert.methods_agreeing}/5")
        print(f"    - Consensus risk: {alert.consensus_risk:.2f}")
        print(f"    - Actions: {alert.actions}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model_auc_extraction():
    """Test 7: AUC weight extraction from checkpoint metadata."""
    print("\n[TEST 7] AUC weight extraction from metadata")
    print("-" * 50)
    
    try:
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter)
        
        # Mock checkpoint metadata
        metadata = {
            'models': [
                {'name': 'lstm_model_1', 'best_auc': 0.516},
                {'name': 'lstm_model_2', 'best_auc': 0.550},
                {'name': 'cnn_model', 'best_auc': 0.495},
            ],
        }
        
        # Extract weights
        weights = neural_voter.get_model_auc_weights(metadata)
        
        # Validate
        assert 'lstm_model_1' in weights
        assert 'lstm_model_2' in weights
        assert weights['lstm_model_2'] == 0.550
        
        print(f"[OK] AUC extraction working")
        print(f"    - Models: {list(weights.keys())}")
        print(f"    - Weights: {weights}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integrated_pipeline_structure():
    """Test 8: IntegratedInferencePipeline initialization."""
    print("\n[TEST 8] Integrated pipeline structure")
    print("-" * 50)
    
    try:
        # Create ensemble infrastructure
        ensemble = create_ensemble_inference_from_checkpoint()
        batch_realtime_pipeline = InferencePipeline(ensemble_inference=ensemble)
        
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter)
        
        # Create integrated pipeline
        integrated = IntegratedInferencePipeline(
            batch_realtime_pipeline=batch_realtime_pipeline,
            neural_voter=neural_voter,
            ensemble_voter=base_voter,
        )
        
        # Validate
        assert integrated.batch_realtime_pipeline is not None
        assert integrated.neural_voter is not None
        assert integrated.ensemble_voter is not None
        
        print(f"[OK] Integrated pipeline initialized")
        print(f"    - Has batch/realtime pipeline: True")
        print(f"    - Has neural voter: True")
        print(f"    - Has ensemble voter: True")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integrated_pipeline_end_to_end():
    """Test 9: End-to-end integrated pipeline."""
    print("\n[TEST 9] End-to-end integrated pipeline")
    print("-" * 50)
    
    try:
        # Setup
        ensemble = create_ensemble_inference_from_checkpoint()
        batch_realtime_pipeline = InferencePipeline(ensemble_inference=ensemble)
        
        base_voter = EnsembleVoter()
        neural_voter = NeuralEnsembleVoter(base_voter, neural_threshold=0.5)
        
        integrated = IntegratedInferencePipeline(
            batch_realtime_pipeline=batch_realtime_pipeline,
            neural_voter=neural_voter,
            ensemble_voter=base_voter,
        )
        
        # Create test feature
        features = np.random.randn(576, 15).astype(np.float32)
        auc_weights = {'lstm_model_2': 0.55}
        
        # Run prediction
        result = integrated.predict_with_voting(
            features=features,
            train_id="train_e2e_test",
            bayesian_risk=0.7,
            anomaly_score=75.0,
            dbscan_anomaly=False,
            causal_risk=0.6,
            auc_weights=auc_weights,
            timestamp=datetime.now().isoformat(),
            alert_id=str(uuid.uuid4()),
        )
        
        # Validate
        assert 'train_id' in result
        assert 'voting_result' in result
        assert 'neural_predictions' in result
        assert 'votes_breakdown' in result
        assert len(result['votes_breakdown']) == 5  # 5 methods
        
        print(f"[OK] End-to-end prediction successful")
        print(f"    - Train ID: {result['train_id']}")
        print(f"    - Alert fires: {result['voting_result']['fires']}")
        print(f"    - Methods agreeing: {result['voting_result']['methods_agreeing']}/5")
        print(f"    - Neural latency: {result['neural_latency_ms']:.2f} ms")
        print(f"    - Severity: {result['voting_result']['severity']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all Phase 5.3 tests."""
    print("\n" + "=" * 60)
    print("PHASE 5.3 TEST SUITE: NEURAL ENSEMBLE VOTING")
    print("=" * 60)
    
    tests = [
        ("Neural Voting Basic", test_neural_voting_basic),
        ("AUC Weighting", test_auc_weighting),
        ("Enhanced Consensus", test_enhanced_consensus),
        ("Voting Round (No Alert)", test_voting_round_enhanced_no_alert),
        ("Voting Round (Alert)", test_voting_round_enhanced_alert),
        ("Voting Round (CRITICAL)", test_voting_round_enhanced_critical),
        ("AUC Extraction", test_model_auc_extraction),
        ("Integrated Pipeline Structure", test_integrated_pipeline_structure),
        ("End-to-End Pipeline", test_integrated_pipeline_end_to_end),
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
