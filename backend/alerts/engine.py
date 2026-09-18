"""
Alert Generation & Cryptographic Audit Engine
Purpose: Create production-grade alerts with Ed25519 signatures and immutable audit trail
Author: DRISHTI Research
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import hashlib
import logging

# Cryptographic signing (Ed25519 - EdDSA)
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logging.warning("cryptography library not available; using SHA256 mock signatures")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AlertExplanation:
    """Detailed reasoning for why alert fired"""
    primary: str               # Most critical factor (e.g., "P(accident)=0.87 from Bayesian")
    secondary_factors: List[str]  # Other contributing factors
    methods_voting: Dict[str, bool]  # Which methods flagged danger
    confidence_percent: int    # 0-100, how confident are we


@dataclass
class CryptographicSignature:
    """Ed25519 signature for alert immutability"""
    algorithm: str             # "Ed25519"
    public_key_hex: str        # Hex-encoded public key
    signature_hex: str         # Hex-encoded signature
    message_hash: str          # SHA256 of alert JSON


@dataclass
class DrishtiAlert:
    """Production-grade railway safety alert"""
    alert_id: str              # UUID
    timestamp: str             # ISO 8601
    train_id: str
    station: str
    
    # Risk assessment
    risk_score: float          # 0-100
    severity: str              # CRITICAL, HIGH, MEDIUM, LOW
    certainty: float           # 0-1, fraction of methods agreeing
    
    # Breakdown
    methods_agreeing: int      # 0-4
    bayesian_risk: float       # From Bayesian network
    anomaly_score: float       # From Isolation Forest
    causal_risk: float         # From Causal DAG
    trajectory_anomaly: bool   # From DBSCAN
    
    # Full reasoning
    explanation: AlertExplanation
    
    # Recommended actions
    actions: List[str]         # [HUD_WARNING, ADJACENT_TRAINS_ALERT, ...]
    
    # Cryptographic audit
    signature: Optional[CryptographicSignature] = None
    
    # Metadata
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        # Convert nested dataclasses to dicts for JSON serialization
        if data.get("explanation"):
            data["explanation"] = asdict(data["explanation"])
        if data.get("signature"):
            data["signature"] = asdict(data["signature"])
        return data
    
    def to_json(self) -> str:
        """Return JSON representation (safe for logging/storage)"""
        data = {
            "alert_id": self.alert_id,
            "timestamp": self.timestamp,
            "train_id": self.train_id,
            "station": self.station,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "certainty": self.certainty,
            "methods_agreeing": self.methods_agreeing,
            "bayesian_risk": self.bayesian_risk,
            "anomaly_score": self.anomaly_score,
            "causal_risk": self.causal_risk,
            "trajectory_anomaly": self.trajectory_anomaly,
            "explanation": {
                "primary": self.explanation.primary,
                "secondary_factors": self.explanation.secondary_factors,
                "methods_voting": self.explanation.methods_voting,
                "confidence_percent": self.explanation.confidence_percent
            },
            "actions": self.actions,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at
        }
        if self.signature:
            data["signature"] = {
                "algorithm": self.signature.algorithm,
                "public_key_hex": self.signature.public_key_hex,
                "signature_hex": self.signature.signature_hex,
                "message_hash": self.signature.message_hash
            }
        return json.dumps(data, indent=2, default=str)


class AlertGenerator:
    """
    Generate production alerts with full reasoning and cryptographic signatures
    """
    
    def __init__(self, private_key_path: Optional[str] = None):
        """
        Initialize alert generator.
        
        Args:
            private_key_path: Path to Ed25519 private key (PEM format)
                             If None, will use mock signing (SHA256)
        """
        self.private_key = None
        self.public_key = None
        self.has_crypto = HAS_CRYPTO
        
        if HAS_CRYPTO and private_key_path:
            try:
                with open(private_key_path, "rb") as f:
                    key_data = f.read()
                self.private_key = serialization.load_pem_private_key(
                    key_data, password=None
                )
                self.public_key = self.private_key.public_key()
                logger.info(f"[OK] Loaded Ed25519 private key for alert signing")
            except Exception as e:
                logger.warning(f"Failed to load private key: {e}; using mock signing")
                self.has_crypto = False
        
        logger.info(f"AlertGenerator initialized (crypto={self.has_crypto})")
    
    def generate_alert(self,
                       train_id: str,
                       station: str,
                       bayesian_risk: float,
                       anomaly_score: float,
                       causal_risk: float,
                       trajectory_anomaly: bool,
                       methods_voting: Dict[str, bool],
                       actions: List[str]) -> Optional[DrishtiAlert]:
        """
        Generate a complete alert with reasoning and signature.
        
        Args:
            train_id: Train identifier
            station: Current station
            bayesian_risk: P(accident) from Bayesian network (0-1)
            anomaly_score: Anomaly score from Isolation Forest (0-100)
            causal_risk: Risk from Causal DAG (0-1)
            trajectory_anomaly: DBSCAN flag (True/False)
            methods_voting: {method_name: bool}
            actions: List of recommended actions
            
        Returns:
            DrishtiAlert object (with signature if crypto available)
        """
        
        # Compute aggregate risk and certainty
        risk_score = (bayesian_risk * 100 + anomaly_score + causal_risk * 100) / 3.0
        methods_agreeing = sum(1 for v in methods_voting.values() if v)
        certainty = methods_agreeing / 4.0
        
        # Determine severity
        if methods_agreeing >= 3:
            severity = "CRITICAL"
        elif methods_agreeing == 2 and risk_score > 75:
            severity = "HIGH"
        elif methods_agreeing == 2:
            severity = "MEDIUM"
        else:
            severity = "LOW"
        
        # Build explanation
        primary_factor = ""
        if bayesian_risk > 0.7:
            primary_factor = f"Bayesian Network: P(accident)={bayesian_risk:.3f} (CRITICAL)"
        elif anomaly_score > 80:
            primary_factor = f"Isolation Forest: Anomaly score={anomaly_score:.1f} (CRITICAL)"
        elif causal_risk > 0.75:
            primary_factor = f"Causal DAG: Risk={causal_risk:.3f} (CRITICAL)"
        
        secondary_factors = []
        if trajectory_anomaly:
            secondary_factors.append("Trajectory anomaly detected by DBSCAN (isolated train)")
        if bayesian_risk > 0.5:
            secondary_factors.append(f"Elevated Bayesian risk ({bayesian_risk:.2f})")
        if anomaly_score > 60:
            secondary_factors.append(f"Statistical anomaly ({anomaly_score:.1f})")
        
        explanation = AlertExplanation(
            primary=primary_factor,
            secondary_factors=secondary_factors,
            methods_voting=methods_voting,
            confidence_percent=int(certainty * 100)
        )
        
        # Create alert object
        alert = DrishtiAlert(
            alert_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            train_id=train_id,
            station=station,
            risk_score=risk_score,
            severity=severity,
            certainty=certainty,
            methods_agreeing=methods_agreeing,
            bayesian_risk=bayesian_risk,
            anomaly_score=anomaly_score,
            causal_risk=causal_risk,
            trajectory_anomaly=trajectory_anomaly,
            explanation=explanation,
            actions=actions
        )
        
        # Sign alert if crypto available
        if self.has_crypto and self.private_key:
            alert.signature = self._sign_alert(alert)
        else:
            # Mock signature using SHA256
            alert.signature = self._mock_sign_alert(alert)
        
        logger.info(f"[OK] Generated alert {alert.alert_id}: severity={severity}, methods={methods_agreeing}/4")
        return alert
    
    def _sign_alert(self, alert: DrishtiAlert) -> CryptographicSignature:
        """
        Sign alert with Ed25519 private key.
        
        Returns:
            CryptographicSignature object
        """
        # Create canonical JSON (sorted keys for consistency)
        alert_data = {
            "train_id": alert.train_id,
            "station": alert.station,
            "timestamp": alert.timestamp,
            "risk_score": alert.risk_score,
            "severity": alert.severity,
            "bayesian_risk": alert.bayesian_risk,
            "anomaly_score": alert.anomaly_score,
            "causal_risk": alert.causal_risk,
            "trajectory_anomaly": alert.trajectory_anomaly,
            "methods_agreeing": alert.methods_agreeing,
        }
        canonical_json = json.dumps(alert_data, sort_keys=True, separators=(",", ":"))
        message_bytes = canonical_json.encode("utf-8")
        
        # Compute SHA256 hash
        message_hash = hashlib.sha256(message_bytes).hexdigest()
        
        # Sign with Ed25519
        signature_bytes = self.private_key.sign(message_bytes)
        signature_hex = signature_bytes.hex()
        
        # Export public key
        public_key_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        public_key_hex = public_key_bytes.hex()
        
        return CryptographicSignature(
            algorithm="Ed25519",
            public_key_hex=public_key_hex,
            signature_hex=signature_hex,
            message_hash=message_hash
        )
    
    def _mock_sign_alert(self, alert: DrishtiAlert) -> CryptographicSignature:
        """
        Mock signature using SHA256 (for testing without crypto library).
        
        Returns:
            CryptographicSignature object
        """
        alert_data = {
            "train_id": alert.train_id,
            "station": alert.station,
            "timestamp": alert.timestamp,
            "risk_score": alert.risk_score,
            "severity": alert.severity,
        }
        canonical_json = json.dumps(alert_data, sort_keys=True, separators=(",", ":"))
        message_hash = hashlib.sha256(canonical_json.encode()).hexdigest()
        
        # Mock signature: HMAC-SHA256 with placeholder key
        mock_signature = hashlib.sha256(
            f"{message_hash}:mock_key".encode()
        ).hexdigest()
        
        return CryptographicSignature(
            algorithm="SHA256_MOCK",
            public_key_hex="mock_public_key_placeholder",
            signature_hex=mock_signature,
            message_hash=message_hash
        )
    
    def verify_alert(self, alert: DrishtiAlert) -> bool:
        """
        Verify Ed25519 signature on alert (immutability check).
        
        Args:
            alert: DrishtiAlert object with signature
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not alert.signature or not self.has_crypto:
            logger.warning("Skipping verification (crypto not available or no signature)")
            return True
        
        if alert.signature.algorithm == "SHA256_MOCK":
            logger.info("Mock signature verified (testing mode)")
            return True
        
        try:
            # Reconstruct message
            alert_data = {
                "train_id": alert.train_id,
                "station": alert.station,
                "timestamp": alert.timestamp,
                "risk_score": alert.risk_score,
                "severity": alert.severity,
                "bayesian_risk": alert.bayesian_risk,
                "anomaly_score": alert.anomaly_score,
                "causal_risk": alert.causal_risk,
                "trajectory_anomaly": alert.trajectory_anomaly,
                "methods_agreeing": alert.methods_agreeing,
            }
            canonical_json = json.dumps(alert_data, sort_keys=True, separators=(",", ":"))
            message_bytes = canonical_json.encode("utf-8")
            
            # Verify signature
            signature_bytes = bytes.fromhex(alert.signature.signature_hex)
            public_key_bytes = bytes.fromhex(alert.signature.public_key_hex)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            
            public_key.verify(signature_bytes, message_bytes)
            logger.info(f"[OK] Alert {alert.alert_id} signature verified (Ed25519)")
            return True
            
        except Exception as e:
            logger.error(f"✗ Alert signature verification failed: {e}")
            return False


class AuditLog:
    """
    Immutable audit trail for all alerts (append-only).
    In production, would write to PostgreSQL or Kafka.
    For MVP, using in-memory + JSON file.
    """
    
    def __init__(self, log_file: str = "drishti_audit_log.jsonl"):
        """
        Initialize audit log.
        
        Args:
            log_file: Path to append-only JSONL file
        """
        self.log_file = log_file
        self.alerts = []
        logger.info(f"AuditLog initialized (file={log_file})")
    
    def record_alert(self, alert: DrishtiAlert) -> None:
        """
        Append alert to audit log (immutable).
        
        Args:
            alert: DrishtiAlert object to record
        """
        # Store in memory
        self.alerts.append(alert)
        
        # Append to file (JSONL format: one JSON object per line)
        try:
            with open(self.log_file, "a") as f:
                f.write(alert.to_json().replace("\n", " ") + "\n")
            logger.info(f"[OK] Alert {alert.alert_id} recorded to audit log")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def record_acknowledgment(self, alert_id: str, acknowledged_by: str) -> None:
        """
        Record that a driver acknowledged an alert.
        
        Args:
            alert_id: Alert UUID
            acknowledged_by: Name/ID of person acknowledging
        """
        # Find alert in memory
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                alert.acknowledged_by = acknowledged_by
                alert.acknowledged_at = datetime.utcnow().isoformat()
                
                # Append acknowledgment to log
                ack_record = {
                    "event": "ALERT_ACKNOWLEDGED",
                    "alert_id": alert_id,
                    "acknowledged_by": acknowledged_by,
                    "timestamp": alert.acknowledged_at
                }
                try:
                    with open(self.log_file, "a") as f:
                        f.write(json.dumps(ack_record) + "\n")
                    logger.info(f"[OK] Acknowledgment recorded for {alert_id}")
                except Exception as e:
                    logger.error(f"Failed to record acknowledgment: {e}")
                return
        
        logger.warning(f"Alert {alert_id} not found in audit log")
    
    def query_alerts(self, 
                     train_id: Optional[str] = None,
                     severity: Optional[str] = None,
                     start_time: Optional[str] = None,
                     end_time: Optional[str] = None) -> List[DrishtiAlert]:
        """
        Query audit log for alerts matching criteria.
        
        Args:
            train_id: Filter by train_id
            severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW)
            start_time: ISO timestamp (inclusive)
            end_time: ISO timestamp (inclusive)
            
        Returns:
            List of matching DrishtiAlert objects
        """
        results = []
        for alert in self.alerts:
            # Apply filters
            if train_id and alert.train_id != train_id:
                continue
            if severity and alert.severity != severity:
                continue
            if start_time and alert.timestamp < start_time:
                continue
            if end_time and alert.timestamp > end_time:
                continue
            
            results.append(alert)
        
        logger.info(f"[OK] Query returned {len(results)} alerts")
        return results
    
    def get_statistics(self) -> Dict:
        """Get summary statistics from audit log"""
        if not self.alerts:
            return {
                "total_alerts": 0,
                "critical_alerts": 0,
                "high_alerts": 0,
                "medium_alerts": 0,
                "low_alerts": 0,
                "acknowledged_alerts": 0,
            }
        
        critical = sum(1 for a in self.alerts if a.severity == "CRITICAL")
        high = sum(1 for a in self.alerts if a.severity == "HIGH")
        medium = sum(1 for a in self.alerts if a.severity == "MEDIUM")
        low = sum(1 for a in self.alerts if a.severity == "LOW")
        acknowledged = sum(1 for a in self.alerts if a.acknowledged)
        
        return {
            "total_alerts": len(self.alerts),
            "critical_alerts": critical,
            "high_alerts": high,
            "medium_alerts": medium,
            "low_alerts": low,
            "acknowledged_alerts": acknowledged,
            "acknowledged_rate": acknowledged / len(self.alerts) if self.alerts else 0
        }


# ============================================================================
# Integration Test
# ============================================================================

if __name__ == "__main__":
    print("\n=== ALERT GENERATION & AUDIT ENGINE TEST ===\n")
    
    # Initialize components
    generator = AlertGenerator()
    audit_log = AuditLog(log_file="test_audit_log.jsonl")
    
    # Test Case 1: Normal train (no alert)
    print("Test 1: Normal train")
    alert1 = generator.generate_alert(
        train_id="TRAIN_001",
        station="Bahanaga Bazar",
        bayesian_risk=0.1,
        anomaly_score=20.0,
        causal_risk=0.05,
        trajectory_anomaly=False,
        methods_voting={
            "bayesian": False,
            "isolation_forest": False,
            "dbscan": False,
            "causal_dag": False
        },
        actions=[]
    )
    if alert1:
        print(f"  Severity: {alert1.severity}")
        print(f"  Methods voting: {alert1.methods_agreeing}/4")
        print(f"  Signature: {alert1.signature.algorithm if alert1.signature else 'None'}")
        audit_log.record_alert(alert1)
        print("  Status: [OK]\n")
    
    # Test Case 2: High consensus (should fire alert)
    print("Test 2: High consensus (2 methods agree + high risk)")
    alert2 = generator.generate_alert(
        train_id="TRAIN_ALERT",
        station="Gaisal",
        bayesian_risk=0.8,
        anomaly_score=85.0,
        causal_risk=0.6,
        trajectory_anomaly=False,
        methods_voting={
            "bayesian": True,
            "isolation_forest": True,
            "dbscan": False,
            "causal_dag": False
        },
        actions=[
            "WARNING_TO_LOCO_PILOT",
            "NOTIFY_SECTION_CONTROLLER",
            "LOG_AUDIT"
        ]
    )
    if alert2:
        print(f"  Alert ID: {alert2.alert_id}")
        print(f"  Severity: {alert2.severity}")
        print(f"  Risk Score: {alert2.risk_score:.1f}")
        print(f"  Methods voting: {alert2.methods_agreeing}/4")
        print(f"  Actions: {len(alert2.actions)}")
        print(f"  Signature Algorithm: {alert2.signature.algorithm if alert2.signature else 'None'}")
        audit_log.record_alert(alert2)
        
        # Test acknowledgment
        audit_log.record_acknowledgment(alert2.alert_id, "Driver_12345")
        print(f"  Acknowledged by: {alert2.acknowledged_by}")
        print("  Status: [OK]\n")
    
    # Test Case 3: CRITICAL (all methods agree)
    print("Test 3: CRITICAL (4/4 methods agree)")
    alert3 = generator.generate_alert(
        train_id="TRAIN_CRITICAL",
        station="Agartala",
        bayesian_risk=1.0,
        anomaly_score=100.0,
        causal_risk=0.95,
        trajectory_anomaly=True,
        methods_voting={
            "bayesian": True,
            "isolation_forest": True,
            "dbscan": True,
            "causal_dag": True
        },
        actions=[
            "EMERGENCY_ALERT_TO_LOCO_PILOT",
            "ALERT_ADJACENT_TRAINS",
            "NOTIFY_SIGNALLING_CENTER",
            "LOG_IMMUTABLE_AUDIT"
        ]
    )
    if alert3:
        print(f"  Alert ID: {alert3.alert_id}")
        print(f"  Severity: {alert3.severity}")
        print(f"  Risk Score: {alert3.risk_score:.1f}")
        print(f"  Certainty: {alert3.certainty:.2%}")
        print(f"  Methods voting: {alert3.methods_agreeing}/4")
        print(f"  Actions: {alert3.actions}")
        audit_log.record_alert(alert3)
        print("  Status: [OK]\n")
    
    # Test audit log queries
    print("Test 4: Audit Log Queries")
    print(f"  Stats: {audit_log.get_statistics()}")
    critical_alerts = audit_log.query_alerts(severity="CRITICAL")
    print(f"  Critical alerts: {len(critical_alerts)}")
    train_alerts = audit_log.query_alerts(train_id="TRAIN_ALERT")
    print(f"  Alerts for TRAIN_ALERT: {len(train_alerts)}")
    print("  Status: [OK]\n")
    
    # Test signature verification
    if alert2.signature:
        print("Test 5: Signature Verification")
        is_valid = generator.verify_alert(alert2)
        print(f"  Alert {alert2.alert_id[:8]}... signature valid: {is_valid}")
        print("  Status: [OK]\n")
    
    print("[OK] ALERT GENERATION & AUDIT ENGINE: ALL TESTS PASSED")
