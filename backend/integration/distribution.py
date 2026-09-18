"""
DRISHTI Integrated Alert Distribution System
Connects: Alert Engine → HUD Protocol → Notification Gateway → Railway Systems
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

from backend.alerts.engine import DrishtiAlert, AuditLog
from backend.hud.protocol import (
    HUDAlertMessage, HUDSeverity, HUDMessageType, HUDLocation, HUDTrainState,
    HUDActionItem, HUDDisplayFormatter, MockHUDDisplay, HUDDriverResponse
)
from backend.notifications.gateway import NotificationRouter, NotificationMessage

logger = logging.getLogger(__name__)


class AlertDistributionSystem:
    """
    Integrates alert generation, HUD delivery, and notifications
    Single point for distributing alert to all railway systems
    """
    
    def __init__(self, audit_log: AuditLog = None):
        self.audit_log = audit_log or AuditLog()
        self.notification_router = NotificationRouter()
        self.hud_displays = {}  # train_id -> MockHUDDisplay
        self.distribution_log = []
    
    def distribute_alert(self, drishti_alert: DrishtiAlert, train_data: Dict) -> Dict:
        """
        Main entry point: Take a DrishtiAlert and distribute to all systems
        
        Args:
            drishti_alert: Alert from inference engine
            train_data: Current train state/location data
        
        Returns:
            Distribution summary with HUD message and notifications sent
        """
        logger.info(f"[DISTRIBUTION] Processing alert for train {drishti_alert.train_id}")
        
        # Step 1: Convert to HUD message
        hud_msg = self._convert_to_hud_message(drishti_alert, train_data)
        
        # Step 2: Display on HUD in loco cabin
        hud_delivery = self._deliver_to_hud(hud_msg)
        
        # Step 3: Send notifications to personnel
        notifications = self._send_notifications(drishti_alert, hud_msg)
        
        # Step 4: Log distribution
        distribution_record = {
            'timestamp': datetime.now().isoformat(),
            'alert_id': str(drishti_alert.alert_id),
            'train_id': drishti_alert.train_id,
            'severity': drishti_alert.severity,
            'hud_delivered': hud_delivery['success'],
            'notifications_sent': len(notifications),
            'hud_message_id': hud_msg.message_id,
            'status': 'distributed'
        }
        self.distribution_log.append(distribution_record)
        
        return {
            'alert_id': str(drishti_alert.alert_id),
            'hud_message': hud_msg,
            'hud_delivery': hud_delivery,
            'notifications': notifications,
            'distribution_record': distribution_record
        }
    
    def _convert_to_hud_message(self, drishti_alert: DrishtiAlert, train_data: Dict) -> HUDAlertMessage:
        """Convert DrishtiAlert to HUD protocol message"""
        
        # Map severity
        severity_map = {
            'CRITICAL': HUDSeverity.CRITICAL,
            'HIGH': HUDSeverity.HIGH,
            'MEDIUM': HUDSeverity.MEDIUM,
            'LOW': HUDSeverity.LOW
        }
        hud_severity = severity_map.get(drishti_alert.severity, HUDSeverity.ADVISORY)
        
        # Create location
        location = HUDLocation(
            station_id=train_data.get('current_station', 'UNKNOWN'),
            station_name=train_data.get('current_station_name', 'Unknown Station'),
            latitude=train_data.get('latitude', 0.0),
            longitude=train_data.get('longitude', 0.0),
            km_marker=train_data.get('km_marker', 0.0),
            track_section=train_data.get('track_section', 'UNKNOWN'),
            junction_id=train_data.get('junction_id'),
            next_station=train_data.get('next_station'),
            distance_to_next=train_data.get('distance_to_next')
        )
        
        # Create train state
        train_state = HUDTrainState(
            train_id=drishti_alert.train_id,
            speed_kmph=train_data.get('speed', 60.0),
            speed_limit_kmph=train_data.get('speed_limit', 100.0),
            acceleration=train_data.get('acceleration', 0.0),
            brake_status=train_data.get('brake_status', 'normal'),
            delay_minutes=train_data.get('delay_minutes', 0),
            next_stop=train_data.get('next_station', 'Unknown'),
            eta_minutes=train_data.get('eta_minutes', 30)
        )
        
        # Create actions
        actions = []
        for action in drishti_alert.actions:
            actions.append(HUDActionItem(
                action_id=str(uuid.uuid4()),
                action_type=self._map_action_to_type(action),
                priority=self._map_severity_to_priority(drishti_alert.severity),
                description=action,
                target_value=self._get_action_target_value(action),
                duration_sec=300 if 'speed' in action.lower() else 60
            ))
        
        # Sound and visual cues based on severity
        sound_map = {
            'CRITICAL': 'siren',
            'HIGH': 'alarm',
            'MEDIUM': 'chime',
            'LOW': 'beep',
            'ADVISORY': None
        }
        
        # Create HUD message
        hud_msg = HUDAlertMessage(
            message_id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            severity=hud_severity,
            message_type=HUDMessageType.ACCIDENT_RISK,
            train_id=drishti_alert.train_id,
            location=location,
            train_state=train_state,
            alert_title=f"[{drishti_alert.severity}] ACCIDENT RISK",
            alert_description=drishti_alert.explanation.primary,
            confidence=drishti_alert.risk_score / 100.0,
            time_to_event_sec=self._estimate_time_to_event(drishti_alert),
            primary_reason=drishti_alert.explanation.primary,
            secondary_reasons=drishti_alert.explanation.secondary_factors or [],
            actions=actions,
            sound_type=sound_map[drishti_alert.severity],
            sound_duration_sec=3 if drishti_alert.severity in ['CRITICAL', 'HIGH'] else 1,
            flash_pattern='continuous' if drishti_alert.severity == 'CRITICAL' else 'pulse',
            color=self._get_color_for_severity(drishti_alert.severity),
            alert_id_from_audit=str(drishti_alert.alert_id)
        )
        
        return hud_msg
    
    def _deliver_to_hud(self, hud_msg: HUDAlertMessage) -> Dict:
        """Display message on loco cabin HUD"""
        try:
            # Get or create display for this train
            if hud_msg.train_id not in self.hud_displays:
                self.hud_displays[hud_msg.train_id] = MockHUDDisplay(name=f"Loco_{hud_msg.train_id}")
            
            display = self.hud_displays[hud_msg.train_id]
            display.display_alert(hud_msg)
            
            logger.info(f"[HUD] Message displayed on train {hud_msg.train_id}")
            
            return {
                'success': True,
                'message_id': hud_msg.message_id,
                'train_id': hud_msg.train_id,
                'display_type': 'MockHUD',
                'timestamp': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"[HUD] Delivery failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _send_notifications(self, drishti_alert: DrishtiAlert, hud_msg: HUDAlertMessage) -> List[NotificationMessage]:
        """Send notifications through router"""
        
        messages = self.notification_router.route_alert(
            severity=drishti_alert.severity,
            train_id=drishti_alert.train_id,
            station=hud_msg.location.station_name,
            alert_title=hud_msg.alert_title,
            alert_body=hud_msg.alert_description,
            details={
                'confidence': hud_msg.confidence,
                'methods': drishti_alert.explanation.methods_voting,
                'actions': drishti_alert.actions,
                'alert_id': str(drishti_alert.alert_id),
                'hud_message_id': hud_msg.message_id
            }
        )
        
        logger.info(f"[NOTIFICATIONS] Sent {len(messages)} notifications for alert {drishti_alert.alert_id}")
        
        return messages
    
    def record_driver_acknowledgment(self, hud_message_id: str, driver_response: HUDDriverResponse) -> bool:
        """Record driver acknowledgment in audit log"""
        try:
            # Update HUD message
            for train_displays in self.hud_displays.values():
                for msg in train_displays.display_buffer:
                    if msg.message_id == hud_message_id:
                        msg.driver_acknowledged = True
                        msg.driver_id = driver_response.driver_id
                        msg.acknowledge_time = driver_response.timestamp
                        logger.info(f"[ACK] Driver {driver_response.driver_id} acknowledged message")
                        return True
            
            logger.warning(f"[ACK] Message not found: {hud_message_id}")
            return False
        
        except Exception as e:
            logger.error(f"[ACK] Recording acknowledgment failed: {e}")
            return False
    
    def get_status(self) -> Dict:
        """Get system status"""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_distributions': len(self.distribution_log),
            'notification_status': self.notification_router.get_delivery_status(),
            'hud_displays_active': len(self.hud_displays),
            'recent_distributions': self.distribution_log[-5:]  # Last 5
        }
    
    # Helper methods
    
    @staticmethod
    def _map_action_to_type(action: str) -> str:
        """Map action description to action type"""
        action_lower = action.lower()
        if 'speed' in action_lower or 'reduce' in action_lower:
            return 'reduce_speed'
        elif 'brake' in action_lower or 'emergency' in action_lower:
            return 'prepare_brake'
        elif 'track' in action_lower or 'change' in action_lower:
            return 'change_track'
        elif 'alert' in action_lower or 'notify' in action_lower:
            return 'alert_personnel'
        else:
            return 'other'
    
    @staticmethod
    def _map_severity_to_priority(severity: str) -> str:
        """Map alert severity to action priority"""
        severity_map = {
            'CRITICAL': 'immediate',
            'HIGH': 'urgent',
            'MEDIUM': 'soon',
            'LOW': 'note'
        }
        return severity_map.get(severity, 'note')
    
    @staticmethod
    def _get_action_target_value(action: str) -> Optional[float]:
        """Extract numeric target from action description"""
        import re
        match = re.search(r'(\d+)\s*(?:kmph|km/h)', action, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None
    
    @staticmethod
    def _estimate_time_to_event(alert: DrishtiAlert) -> int:
        """Estimate seconds until predicted event"""
        # Based on delay and current position
        # Conservative estimate: 3 minutes for CRITICAL, 5 for HIGH, etc.
        time_map = {
            'CRITICAL': 180,
            'HIGH': 300,
            'MEDIUM': 600,
            'LOW': None
        }
        return time_map.get(alert.severity)
    
    @staticmethod
    def _get_color_for_severity(severity: str) -> str:
        """Get HEX color for severity level"""
        color_map = {
            'CRITICAL': '#FF0000',  # Red
            'HIGH': '#FF8800',      # Orange
            'MEDIUM': '#FFFF00',    # Yellow
            'LOW': '#00DD00'        # Green
        }
        return color_map.get(severity, '#FFFFFF')


if __name__ == '__main__':
    # Example usage
    from backend.alerts.engine import AlertExplanation, CryptographicSignature
    
    # Create a mock alert
    alert = DrishtiAlert(
        alert_id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        train_id="TRAIN_12345",
        station="Balasore",
        severity="CRITICAL",
        risk_score=92.0,
        certainty=0.92,
        methods_agreeing=4,
        bayesian_risk=92.0,
        anomaly_score=88.0,
        causal_risk=90.0,
        trajectory_anomaly=True,
        explanation=AlertExplanation(
            primary="Bayesian P(accident)=0.92, Causal chain triggered, IF + DBSCAN anomalies detected",
            secondary_factors=[
                "Signal status abnormal",
                "Track maintenance active",
                "High traffic density"
            ],
            methods_voting={'bayesian': True, 'if': True, 'causal': True, 'dbscan': True},
            confidence_percent=92
        ),
        actions=[
            "EMERGENCY_ALERT_TO_LOCO_PILOT",
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
    
    # Mock train data
    train_data = {
        'current_station': 'BAL',
        'current_station_name': 'Balasore',
        'latitude': 21.4774,
        'longitude': 86.9479,
        'km_marker': 150.5,
        'track_section': 'SEC_15',
        'speed': 75.0,
        'speed_limit': 100.0,
        'acceleration': 0.2,
        'brake_status': 'normal',
        'delay_minutes': 5,
        'next_station': 'Cuttack',
        'eta_minutes': 15
    }
    
    # Distribute alert
    system = AlertDistributionSystem()
    result = system.distribute_alert(alert, train_data)
    
    print("\n" + "="*70)
    print("ALERT DISTRIBUTION RESULT")
    print("="*70)
    print(f"HUD Delivery: {'SUCCESS' if result['hud_delivery']['success'] else 'FAILED'}")
    print(f"Notifications Sent: {result['distribution_record']['notifications_sent']}")
    print(f"Distribution Status: {result['distribution_record']['status']}")
    print(f"\nSystem Status: {system.get_status()}")
