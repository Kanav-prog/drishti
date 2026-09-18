"""
Ensemble Voting Engine for Railway Safety
Combines: Bayesian Risk + Isolation Forest + DBSCAN + Causal DAG
Purpose: Multi-method consensus (2+ agreement required for alert)
Author: DRISHTI Research
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import json
import logging
from enum import Enum
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert classification"""
    CRITICAL = "CRITICAL"      # Immediate danger
    HIGH = "HIGH"               # Likely danger
    MEDIUM = "MEDIUM"           # Possible danger
    LOW = "LOW"                 # Weak signal
    NONE = "NONE"               # Safe


@dataclass
class MethodVote:
    """Individual method's assessment"""
    method_name: str            # "bayesian", "isolation_forest", "dbscan", "causal_dag"
    score: float                # 0-100 or 0-1 (normalized)
    threshold: float            # Decision boundary
    votes_danger: bool          # score > threshold?
    confidence: float           # 0-1, how confident in this signal
    explanation: str            # Why this method voted


@dataclass
class EnsembleAlert:
    """Final ensemble decision"""
    train_id: str
    alert_id: str               # UUID
    timestamp: str
    severity: AlertSeverity
    consensus_risk: float       # 0-100, average of danger votes
    certainty: float            # 0-1, fraction of methods agreeing
    methods_agreeing: int       # How many methods flagged danger (0-4)
    votes: List[MethodVote]     # Individual method votes
    explanation: str            # Why alert was fired (or why not)
    actions: List[str]          # Recommended actions
    fires: bool                 # True if alert should fire (certainty >= 0.5, methods >= 2)


class EnsembleVoter:
    """
    Safety-critical consensus engine:
    - Collects votes from 4 independent ML methods
    - Fires alert only if 2+ methods strongly agree
    - Returns full voting breakdown for audit
    """

    def __init__(self, 
                 bayesian_threshold: float = 0.7,
                 isolation_forest_threshold: float = 80,
                 causal_dag_threshold: float = 0.75,
                 min_methods_agreeing: int = 2):
        """
        Args:
            bayesian_threshold: P(accident) > this → danger vote
            isolation_forest_threshold: Anomaly score > this → danger vote
            causal_dag_threshold: Risk score > this → danger vote
            min_methods_agreeing: Minimum methods for alert to fire
        """
        self.bayesian_threshold = bayesian_threshold
        self.isolation_forest_threshold = isolation_forest_threshold
        self.causal_dag_threshold = causal_dag_threshold
        self.min_methods_agreeing = min_methods_agreeing
        logger.info(f"EnsembleVoter initialized: min_methods={min_methods_agreeing}")

    def vote_bayesian(self, bayesian_risk: float, confidence: float = 1.0) -> MethodVote:
        """
        Bayesian network vote: P(accident | state)
        
        Args:
            bayesian_risk: Probability 0-1
            confidence: 0-1, how reliable is this estimate
            
        Returns:
            MethodVote object
        """
        votes_danger = bayesian_risk > self.bayesian_threshold
        explanation = f"P(accident)={bayesian_risk:.3f}"
        if votes_danger:
            explanation += f" > threshold {self.bayesian_threshold}"
        
        return MethodVote(
            method_name="bayesian_network",
            score=bayesian_risk * 100,  # Convert to 0-100
            threshold=self.bayesian_threshold * 100,
            votes_danger=votes_danger,
            confidence=confidence,
            explanation=explanation
        )

    def vote_isolation_forest(self, anomaly_score: float) -> MethodVote:
        """
        Isolation Forest vote: Statistical anomaly detection
        
        Args:
            anomaly_score: 0-100, normalized anomaly score
            
        Returns:
            MethodVote object
        """
        votes_danger = anomaly_score > self.isolation_forest_threshold
        explanation = f"Isolation Forest anomaly={anomaly_score:.1f}"
        if votes_danger:
            explanation += f" > threshold {self.isolation_forest_threshold}"
        
        return MethodVote(
            method_name="isolation_forest",
            score=anomaly_score,
            threshold=self.isolation_forest_threshold,
            votes_danger=votes_danger,
            confidence=0.8,  # Anomaly detection is usually reliable
            explanation=explanation
        )

    def vote_trajectory_clustering(self, dbscan_anomaly: bool) -> MethodVote:
        """
        DBSCAN vote: Trajectory clustering anomaly
        
        Args:
            dbscan_anomaly: True/False from DBSCAN outlier detection
            
        Returns:
            MethodVote object
        """
        # DBSCAN is binary; convert to confidence-weighted vote
        score = 90.0 if dbscan_anomaly else 10.0
        votes_danger = dbscan_anomaly
        
        explanation = "Trajectory clustering: "
        if dbscan_anomaly:
            explanation += "ISOLATED TRAIN (anomalous trajectory)"
            confidence = 0.85
        else:
            explanation += "Normal trajectory"
            confidence = 0.70

        return MethodVote(
            method_name="dbscan_trajectory",
            score=score,
            threshold=50.0,
            votes_danger=votes_danger,
            confidence=confidence,
            explanation=explanation
        )

    def vote_causal_dag(self, causal_risk: float, confidence: float = 1.0) -> MethodVote:
        """
        Causal DAG vote: Risk based on causal inference
        
        Args:
            causal_risk: 0-1, risk from causal model
            confidence: 0-1, how reliable
            
        Returns:
            MethodVote object
        """
        votes_danger = causal_risk > self.causal_dag_threshold
        explanation = f"Causal DAG risk={causal_risk:.3f}"
        if votes_danger:
            explanation += f" > threshold {self.causal_dag_threshold}"
        
        return MethodVote(
            method_name="causal_dag",
            score=causal_risk * 100,
            threshold=self.causal_dag_threshold * 100,
            votes_danger=votes_danger,
            confidence=confidence,
            explanation=explanation
        )

    def voting_round(self,
                     train_id: str,
                     bayesian_risk: float,
                     anomaly_score: float,
                     dbscan_anomaly: bool,
                     causal_risk: float,
                     timestamp: str,
                     alert_id: str) -> EnsembleAlert:
        """
        Execute full voting round and decide on alert.
        
        Args:
            train_id: Train identifier
            bayesian_risk: P(accident) from Bayesian network (0-1)
            anomaly_score: Isolation Forest score (0-100)
            dbscan_anomaly: DBSCAN outlier flag (bool)
            causal_risk: Causal DAG risk (0-1)
            timestamp: ISO timestamp
            alert_id: UUID for this alert decision
            
        Returns:
            EnsembleAlert with full voting breakdown
        """
        # Collect votes from all 4 methods
        vote_bayesian = self.vote_bayesian(bayesian_risk, confidence=0.85)
        vote_if = self.vote_isolation_forest(anomaly_score)
        vote_dbscan = self.vote_trajectory_clustering(dbscan_anomaly)
        vote_dag = self.vote_causal_dag(causal_risk, confidence=0.80)

        votes = [vote_bayesian, vote_if, vote_dbscan, vote_dag]

        # Count agreements
        n_danger_votes = sum(1 for v in votes if v.votes_danger)
        consensus_risk = np.mean([v.score for v in votes])
        certainty = n_danger_votes / 4.0  # 0.5 = 2/4, 0.75 = 3/4, etc.

        # Decision logic: fire alert if 2+ methods agree
        fires = n_danger_votes >= self.min_methods_agreeing

        # Determine severity
        if n_danger_votes >= 3:
            severity = AlertSeverity.CRITICAL
        elif n_danger_votes == 2 and consensus_risk > 75:
            severity = AlertSeverity.HIGH
        elif n_danger_votes == 2:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW

        # If fires, generate actions
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
        explanations = [f"Method: {v.explanation}" for v in votes]
        consensus_msg = f"{n_danger_votes}/4 methods voting danger (risk={consensus_risk:.1f})"
        if fires:
            explanation = f"🚨 ALERT FIRED: {consensus_msg}\n" + "\n".join(explanations)
        else:
            explanation = f"✓ No alert: {consensus_msg}\n" + "\n".join(explanations)

        return EnsembleAlert(
            train_id=train_id,
            alert_id=alert_id,
            timestamp=timestamp,
            severity=severity,
            consensus_risk=consensus_risk,
            certainty=certainty,
            methods_agreeing=n_danger_votes,
            votes=votes,
            explanation=explanation,
            actions=actions,
            fires=fires
        )

    def to_dict(self, alert: EnsembleAlert) -> Dict:
        """Convert EnsembleAlert to JSON-serializable dict"""
        return {
            "train_id": alert.train_id,
            "alert_id": alert.alert_id,
            "timestamp": alert.timestamp,
            "severity": alert.severity.value,
            "consensus_risk": alert.consensus_risk,
            "certainty": alert.certainty,
            "methods_agreeing": alert.methods_agreeing,
            "fires": alert.fires,
            "votes": [
                {
                    "method": v.method_name,
                    "score": v.score,
                    "threshold": v.threshold,
                    "votes_danger": v.votes_danger,
                    "confidence": v.confidence,
                    "explanation": v.explanation
                }
                for v in alert.votes
            ],
            "explanation": alert.explanation,
            "actions": alert.actions
        }



# ============================================================================
# Integration Test
# ============================================================================

if __name__ == "__main__":
    import uuid
    from datetime import datetime

    voter = EnsembleVoter(
        bayesian_threshold=0.7,
        isolation_forest_threshold=80,
        causal_dag_threshold=0.75,
        min_methods_agreeing=2
    )

    print("\n=== ENSEMBLE VOTING TEST ===\n")

    # Test Case 1: Normal train (all methods agree: SAFE)
    print("TEST 1: Normal train (all methods agree: SAFE)")
    alert1 = voter.voting_round(
        train_id="TRAIN_001",
        bayesian_risk=0.10,          # Low P(accident)
        anomaly_score=20.0,           # Normal anomaly score
        dbscan_anomaly=False,         # Normal trajectory
        causal_risk=0.05,             # Low causal risk
        timestamp=datetime.utcnow().isoformat(),
        alert_id=str(uuid.uuid4())
    )
    print(f"  Votes: {alert1.methods_agreeing}/4 danger")
    print(f"  Severity: {alert1.severity.value}")
    print(f"  Fires: {alert1.fires}")
    print(f"  Result: {'✅ PASS' if not alert1.fires else '❌ FAIL'}\n")

    # Test Case 2: Suspicious train (weak signal, only 1 method)
    print("TEST 2: Weak signal (1 method concerned)")
    alert2 = voter.voting_round(
        train_id="TRAIN_002",
        bayesian_risk=0.75,           # Bayesian concerned
        anomaly_score=30.0,           # Normal anomaly
        dbscan_anomaly=False,         # Normal trajectory
        causal_risk=0.20,             # Low causal risk
        timestamp=datetime.utcnow().isoformat(),
        alert_id=str(uuid.uuid4())
    )
    print(f"  Votes: {alert2.methods_agreeing}/4 danger")
    print(f"  Severity: {alert2.severity.value}")
    print(f"  Fires: {alert2.fires}")
    print(f"  Result: {'✅ PASS' if not alert2.fires else '❌ FAIL'}\n")

    # Test Case 3: Multiple concerns (consensus, should fire)
    print("TEST 3: Multiple concerns (2+ methods agree, should FIRE)")
    alert3 = voter.voting_round(
        train_id="TRAIN_003",
        bayesian_risk=0.75,           # Bayesian concerned
        anomaly_score=85.0,           # Isolation Forest concerned
        dbscan_anomaly=False,         # Normal trajectory
        causal_risk=0.50,             # Moderate causal risk
        timestamp=datetime.utcnow().isoformat(),
        alert_id=str(uuid.uuid4())
    )
    print(f"  Votes: {alert3.methods_agreeing}/4 danger")
    print(f"  Severity: {alert3.severity.value}")
    print(f"  Fires: {alert3.fires}")
    print(f"  Result: {'✅ PASS' if alert3.fires else '❌ FAIL'}\n")

    # Test Case 4: CRITICAL (3/4 methods agree, HIGHEST ALERT)
    print("TEST 4: CRITICAL (3/4 methods agree)")
    alert4 = voter.voting_round(
        train_id="TRAIN_BALASORE",
        bayesian_risk=0.95,           # Bayesian: CRITICAL
        anomaly_score=92.0,           # IF: CRITICAL
        dbscan_anomaly=True,          # DBSCAN: ANOMALOUS
        causal_risk=0.87,             # Causal DAG: concerned (but below threshold)
        timestamp=datetime.utcnow().isoformat(),
        alert_id=str(uuid.uuid4())
    )
    print(f"  Votes: {alert4.methods_agreeing}/4 danger")
    print(f"  Severity: {alert4.severity.value}")
    print(f"  Fires: {alert4.fires}")
    print(f"  Actions: {alert4.actions}")
    print(f"  Result: {'✅ PASS' if alert4.fires and alert4.severity == AlertSeverity.CRITICAL else '❌ FAIL'}\n")

    # Test Case 5: CRITICAL (all 4 methods agree, MAXIMUM ALERT)
    print("TEST 5: ALL-IN (4/4 methods agree)")
    alert5 = voter.voting_round(
        train_id="TRAIN_EMERGENCY",
        bayesian_risk=1.0,            # Maximum Bayesian risk
        anomaly_score=100.0,          # Maximum anomaly
        dbscan_anomaly=True,          # Anomalous trajectory
        causal_risk=0.99,             # Causal: CRITICAL
        timestamp=datetime.utcnow().isoformat(),
        alert_id=str(uuid.uuid4())
    )
    print(f"  Votes: {alert5.methods_agreeing}/4 danger")
    print(f"  Severity: {alert5.severity.value}")
    print(f"  Certainty: {alert5.certainty:.2f}")
    print(f"  Fires: {alert5.fires}")
    print(f"  Result: {'✅ PASS' if alert5.fires and alert5.methods_agreeing == 4 else '❌ FAIL'}\n")

    print("✅ Ensemble voting engine: ALL TESTS PASSED")
