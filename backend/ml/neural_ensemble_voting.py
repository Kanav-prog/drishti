"""
Phase 5.3: Neural Ensemble Voting Integration
Extends EnsembleVoter with Deep Learning predictions from Phase 5.2.

Combines:
- Bayesian Risk (statistical)
- Isolation Forest (statistical)
- DBSCAN Trajectories (geometric)
- Causal DAG (causal inference)
- Neural Ensemble (deep learning) ← NEW

Strategy: Weight neural predictions by Phase 4 AUC scores
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import logging
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class NeuralPredictionInput:
    """Input for neural voting method."""
    ensemble_probabilities: Dict[str, float]  # {"lstm_model_2": 0.55, ...}
    model_auc_scores: Dict[str, float]        # {"lstm_model_2": 0.55, ...}
    confidence: float = 0.75                  # How confident in neural predictions


class NeuralEnsembleVoter:
    """
    Extended EnsembleVoter that integrates neural predictions.
    
    Enhances the 4-method voting with a 5th method: Deep learning ensemble.
    Neural method uses AUC-weighted voting from Phase 5.1/5.2 models.
    """

    def __init__(self,
                 base_voter,
                 neural_threshold: float = 0.5,
                 auc_weight_factor: float = 1.0,
                 min_methods_agreeing: int = 2):
        """
        Initialize neural-enhanced voter.
        
        Args:
            base_voter: Original EnsembleVoter instance
            neural_threshold: P(accident) > this → danger vote
            auc_weight_factor: Scale factor for AUC weighting
            min_methods_agreeing: Minimum methods for alert (2-3 of 5)
        """
        self.base_voter = base_voter
        self.neural_threshold = neural_threshold
        self.auc_weight_factor = auc_weight_factor
        self.min_methods_agreeing = min_methods_agreeing
        
        logger.info(
            f"NeuralEnsembleVoter initialized: "
            f"threshold={neural_threshold}, "
            f"min_methods={min_methods_agreeing}"
        )

    def vote_neural_ensemble(
        self,
        neural_input: 'NeuralPredictionInput',
    ) -> Dict:
        """
        Neural ensemble vote using AUC-weighted aggregation.
        
        Strategy:
        1. Weight each model's prediction by its AUC score
        2. Aggregate weighted predictions
        3. Compare to threshold for danger vote
        
        Args:
            neural_input: Neural predictions + AUC scores
            
        Returns:
            Dict with neural vote details
        """
        # Validate inputs
        probs = neural_input.ensemble_probabilities
        aucs = neural_input.model_auc_scores
        
        if not probs or not aucs:
            logger.warning("Empty neural predictions")
            return {
                'method_name': 'neural_ensemble',
                'score': 50.0,
                'threshold': self.neural_threshold * 100,
                'votes_danger': False,
                'confidence': 0.0,
                'explanation': 'No neural models available',
                'model_breakdown': {},
            }

        # Compute AUC-weighted average
        weighted_sum = 0.0
        auc_sum = 0.0
        model_breakdown = {}

        for model_name, prob in probs.items():
            # Get AUC (default to 0.5 if missing)
            auc = aucs.get(model_name, 0.5)
            
            # Weight by AUC
            weight = auc * self.auc_weight_factor
            weighted_sum += prob * weight
            auc_sum += weight
            
            model_breakdown[model_name] = {
                'probability': float(prob),
                'auc': float(auc),
                'weighted_contribution': float(prob * weight),
            }

        # Avoid division by zero
        if auc_sum > 0:
            neural_ensemble_score = weighted_sum / auc_sum
        else:
            neural_ensemble_score = np.mean(list(probs.values()))

        # Normalize to 0-100
        neural_score_norm = neural_ensemble_score * 100

        # Decision
        votes_danger = neural_ensemble_score > self.neural_threshold

        # Explanation
        explanation = f"Neural Ensemble (AUC-weighted): {neural_ensemble_score:.3f}"
        if votes_danger:
            explanation += f" > threshold {self.neural_threshold}"

        return {
            'method_name': 'neural_ensemble',
            'score': neural_score_norm,
            'threshold': self.neural_threshold * 100,
            'votes_danger': votes_danger,
            'confidence': neural_input.confidence,
            'explanation': explanation,
            'model_breakdown': model_breakdown,
            'raw_score': neural_ensemble_score,
        }

    def compute_enhanced_consensus(
        self,
        traditional_votes: List,
        neural_vote: Dict,
    ) -> Tuple[int, float, float]:
        """
        Compute consensus with neural predictions included.
        
        Args:
            traditional_votes: List of 4 MethodVote objects
            neural_vote: Dict from vote_neural_ensemble()
            
        Returns:
            (n_danger_votes, consensus_risk, neural_weight)
        """
        # Count danger votes
        n_danger_from_traditional = sum(1 for v in traditional_votes if v.votes_danger)
        n_danger_from_neural = 1 if neural_vote['votes_danger'] else 0
        n_danger_votes = n_danger_from_traditional + n_danger_from_neural

        # Consensus risk (average of all 5 methods)
        traditional_scores = [v.score for v in traditional_votes]
        all_scores = traditional_scores + [neural_vote['score']]
        consensus_risk = np.mean(all_scores)

        # Neural weight (confidence-based)
        neural_weight = neural_vote.get('confidence', 0.75)

        return n_danger_votes, consensus_risk, neural_weight

    def voting_round_enhanced(
        self,
        train_id: str,
        bayesian_risk: float,
        anomaly_score: float,
        dbscan_anomaly: bool,
        causal_risk: float,
        neural_input: NeuralPredictionInput,
        timestamp: str,
        alert_id: str,
    ):
        """
        Enhanced voting round with neural predictions.
        
        Args:
            train_id: Train identifier
            bayesian_risk: P(accident) (0-1)
            anomaly_score: Isolation Forest score (0-100)
            dbscan_anomaly: DBSCAN outlier flag
            causal_risk: Causal DAG risk (0-1)
            neural_input: Neural predictions + AUC weights
            timestamp: ISO timestamp
            alert_id: UUID for this alert
            
        Returns:
            Enhanced EnsembleAlert with 5 votes
        """
        # Get traditional votes
        vote_bayesian = self.base_voter.vote_bayesian(bayesian_risk, confidence=0.85)
        vote_if = self.base_voter.vote_isolation_forest(anomaly_score)
        vote_dbscan = self.base_voter.vote_trajectory_clustering(dbscan_anomaly)
        vote_dag = self.base_voter.vote_causal_dag(causal_risk, confidence=0.80)

        traditional_votes = [vote_bayesian, vote_if, vote_dbscan, vote_dag]

        # Get neural vote
        neural_vote_dict = self.vote_neural_ensemble(neural_input)

        # Convert neural dict to MethodVote for consistency
        from backend.ml.ensemble import MethodVote, EnsembleAlert, AlertSeverity
        
        vote_neural = MethodVote(
            method_name="neural_ensemble",
            score=neural_vote_dict['score'],
            threshold=neural_vote_dict['threshold'],
            votes_danger=neural_vote_dict['votes_danger'],
            confidence=neural_vote_dict['confidence'],
            explanation=neural_vote_dict['explanation']
        )

        all_votes = traditional_votes + [vote_neural]

        # Compute consensus
        n_danger_votes, consensus_risk, neural_weight = self.compute_enhanced_consensus(
            traditional_votes, neural_vote_dict
        )

        # Decision logic: still need 2+ methods, but now out of 5
        # Adjust: 2+ out of 4 traditional, OR 4+ out of 5 total (majority)
        n_danger_traditional = sum(1 for v in traditional_votes if v.votes_danger)
        
        fires = (n_danger_traditional >= 2) or (n_danger_votes >= 3)

        # Determine severity with neural boost
        if n_danger_votes >= 4:
            severity = AlertSeverity.CRITICAL
        elif n_danger_votes == 3 and consensus_risk > 75:
            severity = AlertSeverity.HIGH
        elif n_danger_votes >= 2:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        # Actions
        actions = []
        if fires:
            if severity == AlertSeverity.CRITICAL:
                actions = [
                    "EMERGENCY_ALERT_TO_LOCO_PILOT",
                    "ALERT_ADJACENT_TRAINS",
                    "NOTIFY_SIGNALLING_CENTER",
                    "LOG_IMMUTABLE_AUDIT"
                ]
            elif severity == AlertSeverity.HIGH:
                actions = [
                    "WARNING_TO_LOCO_PILOT",
                    "NOTIFY_SECTION_CONTROLLER",
                    "LOG_AUDIT"
                ]
            else:
                actions = [
                    "CAUTION_FLAG",
                    "LOG_AUDIT"
                ]

        # Build explanation
        explanations = [f"Method: {v.explanation}" for v in all_votes]
        consensus_msg = f"{n_danger_votes}/5 methods voting danger (risk={consensus_risk:.1f})"
        
        if fires:
            explanation = f"🚨 ALERT FIRED: {consensus_msg}\n"
            explanation += f"   Neural boost: {neural_weight:.2f}\n"
            explanation += "\n".join(explanations)
        else:
            explanation = f"✓ No alert: {consensus_msg}\n"
            explanation += f"   Neural boost: {neural_weight:.2f}\n"
            explanation += "\n".join(explanations)

        # Create alert object
        alert = EnsembleAlert(
            train_id=train_id,
            alert_id=alert_id,
            timestamp=timestamp,
            severity=severity,
            consensus_risk=consensus_risk,
            certainty=n_danger_votes / 5.0,  # Out of 5 methods now
            methods_agreeing=n_danger_votes,
            votes=all_votes,
            explanation=explanation,
            actions=actions,
            fires=fires
        )

        return alert

    def get_model_auc_weights(self, checkpoint_metadata: Dict) -> Dict[str, float]:
        """
        Extract AUC weights from Phase 4 checkpoint metadata.
        
        Args:
            checkpoint_metadata: Dict from ensemble_metadata_phase4_complete.json
            
        Returns:
            Dict mapping model names to AUC scores
        """
        auc_weights = {}

        # Extract from 'models' list if present
        if 'models' in checkpoint_metadata:
            for model_info in checkpoint_metadata['models']:
                name = model_info.get('name')
                auc = model_info.get('best_auc', 0.5)
                if name:
                    auc_weights[name] = auc

        # Extract from 'metrics' if models not present
        elif 'metrics' in checkpoint_metadata:
            metrics = checkpoint_metadata['metrics']
            if 'model_aucs' in metrics:
                auc_weights = metrics['model_aucs']

        logger.info(f"Extracted AUC weights: {auc_weights}")
        return auc_weights


class IntegratedInferencePipeline:
    """
    Unified pipeline integrating Phase 5.2 (batch/realtime inference)
    with Phase 5.3 (neural ensemble voting).
    
    Handles:
    1. Batch/real-time feature processing → neural predictions
    2. AUC-weighted neural voting
    3. Multi-method consensus with alert generation
    """

    def __init__(
        self,
        batch_realtime_pipeline,
        neural_voter: NeuralEnsembleVoter,
        ensemble_voter,
    ):
        """
        Initialize integrated pipeline.
        
        Args:
            batch_realtime_pipeline: Phase 5.2 InferencePipeline
            neural_voter: NeuralEnsembleVoter instance
            ensemble_voter: Original EnsembleVoter from Phase 5.0
        """
        self.batch_realtime_pipeline = batch_realtime_pipeline
        self.neural_voter = neural_voter
        self.ensemble_voter = ensemble_voter

        logger.info("IntegratedInferencePipeline initialized")

    def predict_with_voting(
        self,
        features: np.ndarray,
        train_id: str,
        bayesian_risk: float,
        anomaly_score: float,
        dbscan_anomaly: bool,
        causal_risk: float,
        auc_weights: Dict[str, float],
        timestamp: str,
        alert_id: str,
    ) -> Dict:
        """
        Run end-to-end prediction with neural voting.
        
        Args:
            features: (seq_len, n_features) or (batch, seq_len, n_features)
            train_id: Train identifier
            bayesian_risk, anomaly_score, dbscan_anomaly, causal_risk: Traditional method outputs
            auc_weights: Model AUC scores
            timestamp: ISO timestamp
            alert_id: UUID for alert
            
        Returns:
            Dict with neural predictions and voting results
        """
        # Step 1: Get neural predictions
        neural_result = self.batch_realtime_pipeline.stream_predict(
            features,
            train_id=train_id,
        )

        if neural_result['status'] != 'success':
            logger.error(f"Neural prediction failed: {neural_result.get('error')}")
            neural_predictions = {'fallback_model': 0.5}
        else:
            neural_predictions = neural_result.get('predictions', {})

        # Step 2: Create neural input
        neural_input = NeuralPredictionInput(
            ensemble_probabilities=neural_predictions,
            model_auc_scores=auc_weights,
            confidence=0.75,
        )

        # Step 3: Run enhanced voting
        alert = self.neural_voter.voting_round_enhanced(
            train_id=train_id,
            bayesian_risk=bayesian_risk,
            anomaly_score=anomaly_score,
            dbscan_anomaly=dbscan_anomaly,
            causal_risk=causal_risk,
            neural_input=neural_input,
            timestamp=timestamp,
            alert_id=alert_id,
        )

        # Step 4: Compile results
        return {
            'train_id': train_id,
            'timestamp': timestamp,
            'alert_id': alert_id,
            'neural_predictions': neural_predictions,
            'neural_latency_ms': neural_result.get('latency_ms', 0),
            'voting_result': {
                'fires': alert.fires,
                'severity': alert.severity.value,
                'consensus_risk': alert.consensus_risk,
                'methods_agreeing': alert.methods_agreeing,
                'explanation': alert.explanation,
                'actions': alert.actions,
            },
            'votes_breakdown': [
                {
                    'method': v.method_name,
                    'score': v.score,
                    'votes_danger': v.votes_danger,
                    'confidence': v.confidence,
                }
                for v in alert.votes
            ],
        }
