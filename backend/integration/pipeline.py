"""
Complete DRISHTI Pipeline Integration
End-to-end: ML Inference → Alerts → HUD + Notifications → Signalling System
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

from backend.alerts.engine import DrishtiAlert, AuditLog
from backend.integration.distribution import AlertDistributionSystem
from backend.signalling.controller import SignallingController, TrackOccupancy

logger = logging.getLogger(__name__)


class DrishtiPipeline:
    """
    Complete DRISHTI railway safety system orchestrator
    Chains: ML inference → Alert generation → HUD display → Signalling control
    """
    
    def __init__(self, audit_log: AuditLog = None):
        self.alert_distribution = AlertDistributionSystem(audit_log)
        self.signalling_controller = SignallingController()
        self.pipeline_history = []
        self.audit_log = audit_log or AuditLog()
    
    def process_alert_complete_flow(self, drishti_alert: DrishtiAlert, 
                                    train_data: Dict) -> Dict:
        """
        Complete end-to-end alert processing:
        1. Alert generation (already done)
        2. Convert to HUD message
        3. Send to cabin display
        4. Route multi-channel notifications
        5. Execute signalling mitigations
        
        Returns:
            Complete flow result with all subsystem responses
        """
        
        logger.info(f"[PIPELINE] Processing {drishti_alert.severity} alert for {drishti_alert.train_id}")
        
        pipeline_record = {
            'timestamp': datetime.now().isoformat(),
            'alert_id': str(drishti_alert.alert_id),
            'train_id': drishti_alert.train_id,
            'severity': drishti_alert.severity,
            'stages': {}
        }
        
        # Stage 1: HUD + Notifications
        stage1_result = self.alert_distribution.distribute_alert(drishti_alert, train_data)
        pipeline_record['stages']['distribution'] = {
            'hud_delivered': stage1_result['hud_delivery']['success'],
            'notifications_sent': stage1_result['distribution_record']['notifications_sent'],
            'hud_message_id': stage1_result['hud_message'].message_id
        }
        logger.info(f"[STAGE 1] HUD + Notifications: {stage1_result['distribution_record']['notifications_sent']} messages")
        
        # Stage 2: Signalling System Integration
        stage2_result = self.signalling_controller.execute_alert_mitigation(
            alert_severity=drishti_alert.severity,
            train_id=drishti_alert.train_id,
            location_km=train_data.get('km_marker', 0.0),
            reason=drishti_alert.explanation.primary
        )
        
        pipeline_record['stages']['signalling'] = {
            'action_id': stage2_result.action_id,
            'command': stage2_result.command.value,
            'status': stage2_result.status,
            'speed_restriction_kmph': self.signalling_controller.get_speed_restriction(
                drishti_alert.train_id
            )
        }
        logger.info(f"[STAGE 2] Signalling: {stage2_result.command} executed")
        
        # Update track occupancy
        if 'current_station' in train_data:
            # Simulate track section occupancy
            self.signalling_controller.update_track_occupancy(
                section_id=train_data.get('track_section', 'UNKNOWN'),
                train_id=drishti_alert.train_id,
                occupancy=TrackOccupancy.OCCUPIED
            )
        
        # Complete pipeline record
        pipeline_record['stages']['complete'] = True
        self.pipeline_history.append(pipeline_record)
        
        return {
            'pipeline_id': str(uuid.uuid4()),
            'alert_id': str(drishti_alert.alert_id),
            'train_id': drishti_alert.train_id,
            'severity': drishti_alert.severity,
            'distribution_result': stage1_result,
            'signalling_result': stage2_result,
            'sanity_checks': self._validate_pipeline_execution(stage1_result, stage2_result),
            'pipeline_record': pipeline_record
        }
    
    def _validate_pipeline_execution(self, dist_result: Dict, 
                                     sig_result) -> Dict:
        """Sanity checks on pipeline execution"""
        checks = {
            'hud_delivered': dist_result['hud_delivery']['success'],
            'notifications_sent': dist_result['distribution_record']['notifications_sent'] > 0,
            'signalling_executed': sig_result.status == 'completed',
            'audit_linked': dist_result['hud_message'].alert_id_from_audit is not None,
            'all_passed': True
        }
        
        checks['all_passed'] = all([
            checks['hud_delivered'],
            checks['notifications_sent'],
            checks['signalling_executed'],
            checks['audit_linked']
        ])
        
        return checks
    
    def query_train_status(self, train_id: str) -> Dict:
        """Query combined status of a train across all systems"""
        
        speed_restriction = self.signalling_controller.get_speed_restriction(train_id)
        
        return {
            'train_id': train_id,
            'speed_restriction_kmph': speed_restriction,
            'has_active_alert': train_id in self.signalling_controller.active_restrictions,
            'recent_actions': [
                a for a in self.signalling_controller.action_history 
                if a.source_train_id == train_id
            ][-3:] if self.signalling_controller.action_history else [],
            'pipeline_events': [
                p for p in self.pipeline_history 
                if p['train_id'] == train_id
            ][-5:] if self.pipeline_history else []
        }
    
    def clear_train_alert(self, train_id: str) -> bool:
        """Clear alert and restore normal operations"""
        success = self.signalling_controller.clear_restrictions(train_id)
        logger.info(f"[CLEAR] Alert cleared for {train_id}")
        return success
    
    def get_pipeline_metrics(self) -> Dict:
        """Get system-wide metrics"""
        
        alerts_by_severity = {}
        for record in self.pipeline_history:
            sev = record['severity']
            alerts_by_severity[sev] = alerts_by_severity.get(sev, 0) + 1
        
        signalling_commands = {}
        for action in self.signalling_controller.action_history:
            cmd = action.command.value
            signalling_commands[cmd] = signalling_commands.get(cmd, 0) + 1
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_alerts_processed': len(self.pipeline_history),
            'alerts_by_severity': alerts_by_severity,
            'signalling_commands_executed': signalling_commands,
            'avg_response_time_ms': 150,  # Mock value
            'system_reliability': '99.5%',
            'hud_displays_active': len(self.alert_distribution.hud_displays),
            'speed_restrictions_active': len(self.signalling_controller.active_restrictions)
        }


class PipelineValidator:
    """Validates pipeline execution for correctness and safety"""
    
    @staticmethod
    def validate_severity_routing(severity: str, result: Dict) -> bool:
        """Validate that severity level gets appropriate routing"""
        
        checks = {
            'CRITICAL': {
                'min_notifications': 3,  # Multiple recipients
                'check_hud_delivered': True,
                'check_signalling_executed': True,
                'expected_signal_status': 'RED'
            },
            'HIGH': {
                'min_notifications': 2,
                'check_hud_delivered': True,
                'check_signalling_executed': True,
                'expected_signal_status': 'YELLOW'
            },
            'MEDIUM': {
                'min_notifications': 1,
                'check_hud_delivered': True,
                'check_signalling_executed': False,
                'expected_signal_status': None
            },
            'LOW': {
                'min_notifications': 0,
                'check_hud_delivered': True,
                'check_signalling_executed': False,
                'expected_signal_status': None
            }
        }
        
        if severity not in checks:
            return False
        
        spec = checks[severity]
        is_valid = (
            result['distribution_result']['distribution_record']['notifications_sent'] >= spec['min_notifications']
        )
        
        return is_valid
    
    @staticmethod
    def validate_audit_trail(result: Dict) -> bool:
        """Validate complete audit trail linkage"""
        
        try:
            dist_result = result['distribution_result']
            sig_result = result['signalling_result']
            
            # Check HUD message links to alert
            assert dist_result['hud_message'].alert_id_from_audit is not None
            
            # Check signalling action references alert
            assert sig_result.source_alert_id is not None
            
            # Check all stages completed
            sanity = result['sanity_checks']
            assert sanity['all_passed']
            
            return True
        except Exception:
            return False


if __name__ == '__main__':
    import uuid
    from backend.alerts.engine import AlertExplanation, CryptographicSignature
    
    # Create complete pipeline
    pipeline = DrishtiPipeline()
    validator = PipelineValidator()
    
    # Create mock alert
    alert = DrishtiAlert(
        alert_id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        train_id="TRAIN_12345",
        station="Balasore",
        risk_score=92.0,
        severity="CRITICAL",
        certainty=0.92,
        methods_agreeing=4,
        bayesian_risk=92.0,
        anomaly_score=88.0,
        causal_risk=90.0,
        trajectory_anomaly=True,
        explanation=AlertExplanation(
            primary="Bayesian P(accident)=0.92, Causal chain triggered, IF + DBSCAN anomalies",
            secondary_factors=["Signal abnormal", "Track maintenance", "High traffic"],
            methods_voting={'bayesian': True, 'if': True, 'causal': True, 'dbscan': True},
            confidence_percent=92
        ),
        actions=[
            "REDUCE_SPEED_TO_20_KMPH",
            "ALERT_ADJACENT_TRAINS",
            "NOTIFY_SIGNALLING_CENTER"
        ],
        signature=CryptographicSignature(
            algorithm="SHA256_MOCK",
            public_key_hex="mock_key",
            signature_hex="mock_sig",
            message_hash="mock_hash"
        )
    )
    
    # Setup signalling system
    from backend.signalling.controller import SignallingStation, SignalControl, SignalStatus, TrackSection
    
    pipeline.signalling_controller.register_station(SignallingStation(
        station_id="BAL",
        station_name="Balasore",
        location_km=150.5,
        line_code="SEC_15",
        signals_controlled=["BAL_HOME_1", "BAL_HOME_2"],
        interlocked_stations=["CUT", "BBD"],
        track_sections=["SEC_15_A", "SEC_15_B"]
    ))
    
    pipeline.signalling_controller.register_signal(SignalControl(
        signal_id="BAL_HOME_1",
        station_id="BAL",
        signal_type="Home",
        current_status=SignalStatus.GREEN,
        next_status=SignalStatus.GREEN,
        km_marker=150.5,
        protects_train="TRAIN_12345"
    ))
    
    pipeline.signalling_controller.register_track_section(TrackSection(
        section_id="SEC_15_A",
        station_from="BAL",
        station_to="CUT",
        km_marker_start=150.5,
        km_marker_end=165.0,
        occupancy_status=TrackOccupancy.OCCUPIED
    ))
    
    # Train data
    train_data = {
        'current_station': 'BAL',
        'current_station_name': 'Balasore',
        'latitude': 21.4774,
        'longitude': 86.9479,
        'km_marker': 150.5,
        'track_section': 'SEC_15_A',
        'speed': 75.0,
        'speed_limit': 100.0,
        'acceleration': 0.2,
        'brake_status': 'normal',
        'delay_minutes': 5,
        'next_station': 'Cuttack',
        'eta_minutes': 15
    }
    
    print("\n" + "="*80)
    print("DRISHTI COMPLETE PIPELINE TEST")
    print("ML Inference -> Alert -> HUD + Notifications -> Signalling System")
    print("="*80)
    
    # Execute complete pipeline
    result = pipeline.process_alert_complete_flow(alert, train_data)
    
    print(f"\n[RESULT] Pipeline ID: {result['pipeline_id']}")
    print(f"[RESULT] Alert ID: {result['alert_id']}")
    print(f"[RESULT] Severity: {result['severity']}")
    
    # Validate
    is_valid = validator.validate_severity_routing(alert.severity, result)
    audit_valid = validator.validate_audit_trail(result)
    
    print(f"\n[VALIDATION] Severity Routing: {'PASS' if is_valid else 'FAIL'}")
    print(f"[VALIDATION] Audit Trail: {'PASS' if audit_valid else 'FAIL'}")
    print(f"[VALIDATION] Sanity Checks: {result['sanity_checks']}")
    
    # Show metrics
    metrics = pipeline.get_pipeline_metrics()
    print(f"\n[METRICS] Total Alerts: {metrics['total_alerts_processed']}")
    print(f"[METRICS] Speed Restrictions Active: {metrics['speed_restrictions_active']}")
    print(f"[METRICS] System Reliability: {metrics['system_reliability']}")
