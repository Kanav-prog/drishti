"""
Real-time Alert Generation Pipeline
Connects ML inference → Alert generation → Distribution
"""

import json
import logging
from typing import Dict, Optional
from datetime import datetime

from backend.inference.ml_integration import MLInference, get_ml_inference
from backend.alerts.engine import AlertGenerator, DrishtiAlert

logger = logging.getLogger(__name__)


class RealTimeAlertDispatcher:
    """
    Connects ML model inference to alert generation and distribution.
    Real-time inference for live train streams.
    """
    
    def __init__(self, ml_inference: Optional[MLInference] = None):
        self.ml_inference = ml_inference or get_ml_inference()
        self.alert_generator = AlertGenerator()
        
        self.alerts_generated = []
        self.alerts_by_severity = {'CRITICAL': [], 'HIGH': [], 'MEDIUM': [], 'LOW': []}
        
        logger.info("[OK] Real-time alert dispatcher initialized")
    
    def process_train_stream(self, train_data: Dict) -> Optional[DrishtiAlert]:
        """
        Process a live train and generate alert if needed.
        
        Args:
            train_data: {
                'train_id': str,
                'zone': str,
                'station': str,
                'delay_minutes': float,
                'speed_kmph': float,
                'is_heavy_train': bool,
                'weather': str,
            }
        
        Returns:
            DrishtiAlert if generated, None otherwise
        """
        
        train_id = train_data.get('train_id', 'UNKNOWN')
        
        try:
            # Step 1: Run ML inference
            risk_assessment = self.ml_inference.compute_train_risk(train_data)
            
            # Step 2: Check if alert is needed
            if not self._should_generate_alert(risk_assessment):
                logger.debug(f"[SKIP] No alert needed for {train_id}")
                return None
            
            # Step 3: Generate alert
            alert = self.alert_generator.generate_alert(
                train_id=train_id,
                station=train_data.get('station', 'UNKNOWN'),
                bayesian_risk=risk_assessment['bayesian_risk'],
                anomaly_score=risk_assessment['anomaly_score'],
                causal_risk=risk_assessment['causal_risk'],
                trajectory_anomaly=risk_assessment['trajectory_anomaly'],
                methods_voting=risk_assessment['methods_voting'],
                actions=risk_assessment['recommended_actions']
            )
            
            if alert:
                # Log alert
                self.alerts_generated.append(alert)
                self.alerts_by_severity[alert.severity].append(alert)
                
                logger.warning(f"[ALERT] {alert.severity} alert generated for {train_id} "
                              f"at {train_data.get('station', '?')}: "
                              f"risk={alert.risk_score:.1f}, "
                              f"methods={alert.methods_agreeing}/4")
                
                return alert
        
        except Exception as e:
            logger.error(f"Error processing train {train_id}: {e}")
        
        return None
    
    def _should_generate_alert(self, risk_assessment: Dict) -> bool:
        """Determine if the risk warrants an alert"""
        
        bayesian_risk = risk_assessment['bayesian_risk']
        anomaly_score = risk_assessment['anomaly_score']
        causal_risk = risk_assessment['causal_risk']
        trajectory_anomaly = risk_assessment['trajectory_anomaly']
        methods_flagging = risk_assessment['methods_flagging']
        
        # Alert criteria:
        # 1. Any risk > 0.7 threshold
        if bayesian_risk > 0.7 or anomaly_score > 85 or causal_risk > 0.7:
            return True
        
        # 2. Multiple methods flagging (ensemble voting)
        if methods_flagging >= 2:
            # Confirm with secondary high risk
            if bayesian_risk > 0.4 or anomaly_score > 70:
                return True
        
        # 3. Trajectory anomaly + any moderate risk
        if trajectory_anomaly and (bayesian_risk > 0.3 or anomaly_score > 60):
            return True
        
        return False
    
    def get_alert_summary(self) -> Dict:
        """Get summary of generated alerts"""
        return {
            'total_alerts': len(self.alerts_generated),
            'critical': len(self.alerts_by_severity['CRITICAL']),
            'high': len(self.alerts_by_severity['HIGH']),
            'medium': len(self.alerts_by_severity['MEDIUM']),
            'low': len(self.alerts_by_severity['LOW']),
            'summary': f"{len(self.alerts_by_severity['CRITICAL'])} CRITICAL, "
                      f"{len(self.alerts_by_severity['HIGH'])} HIGH, "
                      f"{len(self.alerts_by_severity['MEDIUM'])} MEDIUM"
        }
    
    def save_alerts_to_file(self, filepath: str = "generated_alerts.jsonl") -> int:
        """Save all generated alerts to JSONL file (one JSON per line)"""
        try:
            with open(filepath, 'w') as f:
                for alert in self.alerts_generated:
                    f.write(alert.to_json() + '\n')
            
            count = len(self.alerts_generated)
            logger.info(f"[OK] Saved {count} alerts to {filepath}")
            return count
        
        except Exception as e:
            logger.error(f"Failed to save alerts: {e}")
            return 0


# Global dispatcher instance
_dispatcher = None


def initialize_alert_dispatcher(ml_inference: Optional[MLInference] = None) -> RealTimeAlertDispatcher:
    """Initialize global alert dispatcher"""
    global _dispatcher
    
    _dispatcher = RealTimeAlertDispatcher(ml_inference)
    logger.info("[OK] Alert dispatcher ready")
    return _dispatcher


def get_alert_dispatcher() -> RealTimeAlertDispatcher:
    """Get global alert dispatcher"""
    global _dispatcher
    
    if _dispatcher is None:
        initialize_alert_dispatcher()
    
    return _dispatcher


def generate_alert_for_train(train_data: Dict) -> Optional[DrishtiAlert]:
    """Generate alert for a train (convenience wrapper)"""
    return get_alert_dispatcher().process_train_stream(train_data)
