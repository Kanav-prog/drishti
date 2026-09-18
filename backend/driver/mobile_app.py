"""
DRISHTI Phase 4.4: Driver Mobile App Backend
Provides real-time push notifications and train status to drivers in loco cabin
Connects to FastAPI server with WebSocket for live updates
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Set
import json
from fastapi import WebSocket, WebSocketDisconnect
import asyncio


class DriverAlertType(Enum):
    """Types of alerts sent to driver mobile app"""
    CRITICAL_ACCIDENT_RISK = "CRITICAL_ACCIDENT_RISK"
    HIGH_ALERT = "HIGH_ALERT"
    MEDIUM_ALERT = "MEDIUM_ALERT"
    LOW_ADVISORY = "LOW_ADVISORY"
    SIGNAL_CHANGE = "SIGNAL_CHANGE"
    SPEED_RESTRICTION = "SPEED_RESTRICTION"
    TRACK_OCCUPANCY = "TRACK_OCCUPANCY"
    ACKNOWLEDGMENT_REQUIRED = "ACKNOWLEDGMENT_REQUIRED"
    CLEARANCE_NOTIFICATION = "CLEARANCE_NOTIFICATION"


class DriverAckStatus(Enum):
    """Driver acknowledgment status for alerts"""
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISMISSED = "DISMISSED"
    OVERRIDDEN = "OVERRIDDEN"


@dataclass
class MobileDriver:
    """Driver profile for mobile app"""
    driver_id: str
    name: str
    emp_code: str
    phone: str
    email: str
    train_id: str
    is_active: bool = True
    mobile_app_version: str = "1.0"
    device_type: str = "android"  # android or ios
    registration_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DriverAlert:
    """Alert sent to driver mobile app"""
    alert_id: str
    driver_id: str
    train_id: str
    alert_type: DriverAlertType
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    title: str
    message: str
    location_km: float
    current_speed_kmph: int
    recommended_speed_kmph: int
    duration_minutes: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ack_status: DriverAckStatus = DriverAckStatus.PENDING
    ack_timestamp: Optional[datetime] = None
    sound_enabled: bool = True
    vibration_enabled: bool = True


@dataclass
class TrainStatusSnapshot:
    """Current train status for mobile dashboard"""
    train_id: str
    driver_id: str
    current_location_km: float
    current_speed_kmph: int
    max_speed_kmph: int
    restricted_speed_kmph: Optional[int] = None
    next_station_km: float = 0.0
    next_station_name: str = ""
    eta_minutes: int = 0
    active_alerts: int = 0
    pending_acks: int = 0
    signal_status: str = "GREEN"  # RED, YELLOW, GREEN, OFF
    track_status: str = "CLEAR"  # CLEAR, OCCUPIED, RESERVED, MAINTENANCE
    last_update: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DriverAcknowledgment:
    """Driver acknowledgment of alert"""
    ack_id: str
    alert_id: str
    driver_id: str
    train_id: str
    ack_type: str  # "acknowledged" or "dismissed"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    app_version: str = "1.0"
    device_info: str = ""


class DriverMobileAppBackend:
    """Backend service for driver mobile app"""
    
    def __init__(self, pipeline=None):
        """
        Initialize mobile app backend
        Args:
            pipeline: DrishtiPipeline instance for getting alerts
        """
        self.pipeline = pipeline
        self.registered_drivers: Dict[str, MobileDriver] = {}
        self.active_websockets: Dict[str, Set[WebSocket]] = {}  # train_id -> set of websockets
        self.driver_alerts: Dict[str, List[DriverAlert]] = {}  # train_id -> list of alerts
        self.acknowledgments: Dict[str, DriverAcknowledgment] = {}  # ack_id -> ack
        self.driver_sessions: Dict[str, Dict] = {}  # driver_id -> session info
        
    def register_driver(self, driver_profile: MobileDriver) -> bool:
        """Register driver for mobile app access"""
        if driver_profile.driver_id in self.registered_drivers:
            return False
        
        self.registered_drivers[driver_profile.driver_id] = driver_profile
        self.driver_alerts[driver_profile.train_id] = []
        
        if driver_profile.train_id not in self.active_websockets:
            self.active_websockets[driver_profile.train_id] = set()
        
        # Log session
        self.driver_sessions[driver_profile.driver_id] = {
            'login_time': datetime.utcnow(),
            'train_id': driver_profile.train_id,
            'device_type': driver_profile.device_type,
            'app_version': driver_profile.mobile_app_version
        }
        
        return True
    
    def get_driver_profile(self, driver_id: str) -> Optional[MobileDriver]:
        """Get driver profile"""
        return self.registered_drivers.get(driver_id)
    
    def get_train_status(self, train_id: str=None) -> Optional[TrainStatusSnapshot]:
        """Get current train status for driver dashboard"""
        # This would fetch from pipeline's train tracking
        # For now, return mock data
        return TrainStatusSnapshot(
            train_id=train_id or "TRAIN_12345",
            driver_id="DRV_001",
            current_location_km=150.5,
            current_speed_kmph=45,
            max_speed_kmph=100,
            restricted_speed_kmph=30,
            next_station_km=160.0,
            next_station_name="Balasore Junction",
            eta_minutes=15,
            active_alerts=1,
            pending_acks=1,
            signal_status="YELLOW",
            track_status="CLEAR"
        )
    
    def create_driver_alert(self, drishti_alert, train_id: str, driver_id: str) -> DriverAlert:
        """
        Convert Drishti alert to driver mobile alert
        Customized for driver consumption
        """
        severity_map = {
            "CRITICAL": (DriverAlertType.CRITICAL_ACCIDENT_RISK, "EMERGENCY - STOP IMMEDIATELY"),
            "HIGH": (DriverAlertType.HIGH_ALERT, "HIGH ALERT - REDUCE SPEED"),
            "MEDIUM": (DriverAlertType.MEDIUM_ALERT, "MEDIUM ALERT - PROCEED CAUTIOUSLY"),
            "LOW": (DriverAlertType.LOW_ADVISORY, "ADVISORY - FOR INFORMATION")
        }
        
        alert_type, title = severity_map.get(
            drishti_alert['severity'],
            (DriverAlertType.LOW_ADVISORY, "Information")
        )
        
        speed_map = {
            "CRITICAL": 0,
            "HIGH": 30,
            "MEDIUM": 50,
            "LOW": 100
        }
        
        driver_alert = DriverAlert(
            alert_id=drishti_alert['alert_id'],
            driver_id=driver_id,
            train_id=train_id,
            alert_type=alert_type,
            severity=drishti_alert['severity'],
            title=title,
            message=drishti_alert.get('reason', 'Safety hazard detected'),
            location_km=drishti_alert.get('location_km', 0),
            current_speed_kmph=drishti_alert.get('current_speed', 0),
            recommended_speed_kmph=speed_map.get(drishti_alert['severity'], 100),
            duration_minutes={"CRITICAL": 0, "HIGH": 10, "MEDIUM": 5, "LOW": 1}.get(
                drishti_alert['severity'], 1
            ),
            sound_enabled=drishti_alert['severity'] in ["CRITICAL", "HIGH"],
            vibration_enabled=True
        )
        
        # Store in driver alert history
        if train_id not in self.driver_alerts:
            self.driver_alerts[train_id] = []
        self.driver_alerts[train_id].append(driver_alert)
        
        return driver_alert
    
    def acknowledge_driver_alert(
        self,
        alert_id: str,
        driver_id: str,
        train_id: str,
        ack_type: str = "acknowledged"
    ) -> DriverAcknowledgment:
        """
        Process driver acknowledgment of alert
        ack_type: "acknowledged" or "dismissed"
        """
        ack = DriverAcknowledgment(
            ack_id=f"ACK_{alert_id}_{driver_id}",
            alert_id=alert_id,
            driver_id=driver_id,
            train_id=train_id,
            ack_type=ack_type,
            device_info=self.driver_sessions.get(driver_id, {}).get('device_type', 'unknown')
        )
        
        # Update alert status
        if train_id in self.driver_alerts:
            for alert in self.driver_alerts[train_id]:
                if alert.alert_id == alert_id:
                    alert.ack_status = (
                        DriverAckStatus.ACKNOWLEDGED if ack_type == "acknowledged"
                        else DriverAckStatus.DISMISSED
                    )
                    alert.ack_timestamp = datetime.utcnow()
                    break
        
        self.acknowledgments[ack.ack_id] = ack
        return ack
    
    async def broadcast_to_train_drivers(self, train_id: str, message: Dict):
        """
        Broadcast message to all drivers on same train (multi-driver trains)
        via WebSocket
        """
        if train_id not in self.active_websockets:
            return
        
        message_json = json.dumps(message)
        
        disconnected = set()
        for websocket in self.active_websockets[train_id]:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                disconnected.add(websocket)
        
        # Clean up disconnected clients
        self.active_websockets[train_id] -= disconnected
    
    async def register_websocket(self, train_id: str, websocket: WebSocket):
        """Register WebSocket connection for real-time updates"""
        await websocket.accept()
        
        if train_id not in self.active_websockets:
            self.active_websockets[train_id] = set()
        
        self.active_websockets[train_id].add(websocket)
    
    def get_driver_alert_history(self, train_id: str, limit: int = 50) -> List[Dict]:
        """Get recent alert history for driver"""
        if train_id not in self.driver_alerts:
            return []
        
        alerts = self.driver_alerts[train_id][-limit:]
        return [
            {
                'alert_id': a.alert_id,
                'type': a.alert_type.value,
                'severity': a.severity,
                'title': a.title,
                'message': a.message,
                'location_km': a.location_km,
                'speed_kmph': a.recommended_speed_kmph,
                'timestamp': a.timestamp.isoformat(),
                'ack_status': a.ack_status.value,
                'ack_timestamp': a.ack_timestamp.isoformat() if a.ack_timestamp else None
            }
            for a in alerts
        ]
    
    def get_driver_stats(self, driver_id: str) -> Dict:
        """Get driver performance stats"""
        driver = self.registered_drivers.get(driver_id)
        if not driver:
            return {}
        
        train_id = driver.train_id
        alerts = self.driver_alerts.get(train_id, [])
        
        # Count acknowledgments by type
        acks = [a for a in alerts if a.ack_status == DriverAckStatus.ACKNOWLEDGED]
        dismisses = [a for a in alerts if a.ack_status == DriverAckStatus.DISMISSED]
        pending = [a for a in alerts if a.ack_status == DriverAckStatus.PENDING]
        
        # Calculate response time
        ack_times = []
        for alert in acks:
            if alert.ack_timestamp:
                time_diff = (alert.ack_timestamp - alert.timestamp).total_seconds()
                ack_times.append(time_diff)
        
        avg_response_time = sum(ack_times) / len(ack_times) if ack_times else 0
        
        return {
            'driver_id': driver_id,
            'driver_name': driver.name,
            'train_id': train_id,
            'total_alerts_received': len(alerts),
            'acknowledged': len(acks),
            'dismissed': len(dismisses),
            'pending': len(pending),
            'avg_ack_time_seconds': avg_response_time,
            'ack_rate_percent': (len(acks) / len(alerts) * 100) if alerts else 0,
            'mobile_app_version': driver.mobile_app_version,
            'device_type': driver.device_type
        }
    
    def get_system_status(self) -> Dict:
        """Get mobile app backend system status"""
        total_drivers = len(self.registered_drivers)
        active_trains = len(self.active_websockets)
        active_connections = sum(len(ws_set) for ws_set in self.active_websockets.values())
        total_alerts_sent = sum(len(alerts) for alerts in self.driver_alerts.values())
        
        by_severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for alerts in self.driver_alerts.values():
            for alert in alerts:
                by_severity[alert.severity] += 1
        
        return {
            'registered_drivers': total_drivers,
            'active_trains': active_trains,
            'active_websocket_connections': active_connections,
            'total_alerts_sent': total_alerts_sent,
            'alerts_by_severity': by_severity,
            'total_acknowledgments': len(self.acknowledgments),
            'system_ready': total_drivers > 0 and active_connections > 0
        }


# FastAPI Integration
class MobileAppAPI:
    """REST API endpoints for driver mobile app"""
    
    def __init__(self, backend: DriverMobileAppBackend):
        self.backend = backend
    
    async def register_driver_endpoint(self, driver_data: Dict) -> Dict:
        """POST /api/driver/register"""
        driver = MobileDriver(
            driver_id=driver_data['driver_id'],
            name=driver_data['name'],
            emp_code=driver_data['emp_code'],
            phone=driver_data['phone'],
            email=driver_data['email'],
            train_id=driver_data['train_id'],
            device_type=driver_data.get('device_type', 'android'),
            mobile_app_version=driver_data.get('app_version', '1.0')
        )
        
        success = self.backend.register_driver(driver)
        return {
            'success': success,
            'driver_id': driver.driver_id,
            'message': 'Driver registered successfully' if success else 'Driver already registered'
        }
    
    async def get_train_status_endpoint(self, train_id: str) -> Dict:
        """GET /api/train/{train_id}/status"""
        status = self.backend.get_train_status(train_id)
        if status:
            return asdict(status)
        return {'error': 'Train not found'}
    
    async def get_alerts_endpoint(self, train_id: str) -> Dict:
        """GET /api/train/{train_id}/alerts"""
        history = self.backend.get_driver_alert_history(train_id)
        return {
            'train_id': train_id,
            'alert_count': len(history),
            'alerts': history
        }
    
    async def acknowledge_alert_endpoint(self, ack_data: Dict) -> Dict:
        """POST /api/alert/acknowledge"""
        ack = self.backend.acknowledge_driver_alert(
            alert_id=ack_data['alert_id'],
            driver_id=ack_data['driver_id'],
            train_id=ack_data['train_id'],
            ack_type=ack_data.get('ack_type', 'acknowledged')
        )
        
        return {
            'success': True,
            'ack_id': ack.ack_id,
            'alert_id': ack.alert_id,
            'ack_type': ack.ack_type,
            'timestamp': ack.timestamp.isoformat()
        }
    
    async def get_driver_stats_endpoint(self, driver_id: str) -> Dict:
        """GET /api/driver/{driver_id}/stats"""
        stats = self.backend.get_driver_stats(driver_id)
        return stats or {'error': 'Driver not found'}
    
    async def get_system_status_endpoint(self) -> Dict:
        """GET /api/system/status"""
        return self.backend.get_system_status()


if __name__ == "__main__":
    # Test the mobile app backend
    backend = DriverMobileAppBackend()
    
    # Register test driver
    driver1 = MobileDriver(
        driver_id="DRV_001",
        name="Raj Kumar",
        emp_code="EMP_12345",
        phone="+91-9876543210",
        email="raj@ir.gov.in",
        train_id="TRAIN_12345"
    )
    backend.register_driver(driver1)
    
    # Create test alert
    test_alert = {
        'alert_id': 'ALERT_001',
        'severity': 'CRITICAL',
        'reason': 'Obstacle detected on track',
        'location_km': 150.5,
        'current_speed': 80
    }
    
    driver_alert = backend.create_driver_alert(test_alert, "TRAIN_12345", "DRV_001")
    print(f"[✓] Driver Alert Created: {driver_alert.title}")
    
    # Acknowledge alert
    ack = backend.acknowledge_driver_alert(
        "ALERT_001",
        "DRV_001",
        "TRAIN_12345",
        "acknowledged"
    )
    print(f"[✓] Alert Acknowledged: {ack.ack_type}")
    
    # Get stats
    stats = backend.get_driver_stats("DRV_001")
    print(f"[✓] Driver Stats: {stats['total_alerts_received']} alerts, {stats['ack_rate_percent']:.1f}% ack rate")
    
    # System status
    status = backend.get_system_status()
    print(f"[✓] System Status: {status['registered_drivers']} drivers, Ready: {status['system_ready']}")
