"""
DRISHTI HUD Protocol
Communication protocol for Head-Up Display in loco cabins
Standardized interface for alerting loco pilots in real-time
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Literal
from enum import Enum

# ============================================================================
# HUD MESSAGE TYPES & SEVERITY
# ============================================================================

class HUDSeverity(str, Enum):
    """HUD alert severity levels"""
    CRITICAL = "CRITICAL"      # IMMEDIATE ACTION REQUIRED (Red, beeping)
    HIGH = "HIGH"              # ACTION REQUIRED (Amber, alert)
    MEDIUM = "MEDIUM"          # CAUTION (Yellow, note)
    LOW = "LOW"                # INFORMATION (Green, text)
    ADVISORY = "ADVISORY"      # NOTE (Blue, no sound)


class HUDMessageType(str, Enum):
    """Types of HUD messages"""
    ACCIDENT_RISK = "ACCIDENT_RISK"              # Primary alert
    SPEED_ADVISORY = "SPEED_ADVISORY"            # Recommended speed change
    SIGNAL_CHANGE = "SIGNAL_CHANGE"              # Signal status update
    ADJACENT_TRAIN = "ADJACENT_TRAIN"            # Train proximity warning
    TRACK_CONDITION = "TRACK_CONDITION"          # Track/rail condition
    WEATHER_WARNING = "WEATHER_WARNING"          # Weather event
    MAINTENANCE_ALERT = "MAINTENANCE_ALERT"      # Track maintenance
    SPEED_LIMIT = "SPEED_LIMIT"                  # Speed restriction
    ROUTE_CHANGE = "ROUTE_CHANGE"                # Route modification
    SYSTEM_STATUS = "SYSTEM_STATUS"              # DRISHTI system info


# ============================================================================
# HUD DATA STRUCTURES
# ============================================================================

@dataclass
class HUDLocation:
    """Train location information"""
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    km_marker: float  # Kilometer marker on track
    track_section: str  # Section identifier
    junction_id: Optional[str] = None
    next_station: Optional[str] = None
    distance_to_next: Optional[float] = None  # km
    
    def to_dict(self):
        return asdict(self)


@dataclass
class HUDTrainState:
    """Current train dynamics"""
    train_id: str
    speed_kmph: float  # Current speed
    speed_limit_kmph: float  # Track speed limit
    acceleration: float  # m/s^2
    brake_status: str  # "engaged", "normal", "released"
    delay_minutes: int  # Schedule delay
    next_stop: str  # Next stop station
    eta_minutes: int  # ETA to next stop
    
    def to_dict(self):
        return asdict(self)


@dataclass
class HUDActionItem:
    """Recommended action for loco pilot"""
    action_id: str  # Unique ID
    action_type: str  # "reduce_speed", "change_track", "prepare_brake", etc.
    priority: Literal["immediate", "urgent", "soon", "note"]
    description: str  # Human-readable action
    target_value: Optional[float] = None  # e.g., target speed 20 kmph
    duration_sec: Optional[int] = None  # How long to maintain action
    
    def to_dict(self):
        return asdict(self)


@dataclass
class HUDAlertMessage:
    """Core HUD alert message sent to loco cabin display"""
    
    # Metadata (required)
    message_id: str  # Unique message ID (UUID)
    timestamp: str  # ISO 8601 timestamp
    severity: HUDSeverity  # CRITICAL, HIGH, MEDIUM, LOW, ADVISORY
    message_type: HUDMessageType  # Alert category
    
    # Train & Location (required)
    train_id: str
    location: HUDLocation
    train_state: HUDTrainState
    
    # Alert Details (required)
    alert_title: str  # Short title (e.g., "ACCIDENT RISK DETECTED")
    alert_description: str  # Detailed description
    confidence: float  # 0-1 confidence score
    primary_reason: str  # Why this alert (e.g., "Bayesian P=0.92")
    
    # Causal Explanation & Recommendations (optional with defaults)
    secondary_reasons: List[str] = None  # Additional factors
    actions: List[HUDActionItem] = None  # Actions to take
    time_to_event_sec: Optional[int] = None  # Seconds until predicted event
    
    # Sound/Visual Cues (optional)
    sound_type: Optional[str] = None  # "beep", "siren", "chime", "none"
    sound_duration_sec: Optional[int] = None
    flash_pattern: Optional[str] = None  # "continuous", "pulse", "flash"
    color: Optional[str] = None  # Hex color (#FF0000 for red, etc)
    
    # Audit Trail (optional)
    alert_id_from_audit: Optional[str] = None  # Link to audit log
    driver_acknowledged: bool = False
    driver_id: Optional[str] = None
    acknowledge_time: Optional[str] = None
    
    # Delivery Info (with defaults)
    protocol_version: str = "1.0"
    retry_count: int = 0
    delivery_attempts: int = 0
    
    def __post_init__(self):
        if self.secondary_reasons is None:
            self.secondary_reasons = []
        if self.actions is None:
            self.actions = []
    
    def to_json(self) -> str:
        """Serialize to JSON for transmission"""
        return json.dumps({
            'message_id': self.message_id,
            'timestamp': self.timestamp,
            'severity': self.severity.value,
            'message_type': self.message_type.value,
            'train_id': self.train_id,
            'location': self.location.to_dict(),
            'train_state': self.train_state.to_dict(),
            'alert_title': self.alert_title,
            'alert_description': self.alert_description,
            'confidence': self.confidence,
            'time_to_event_sec': self.time_to_event_sec,
            'primary_reason': self.primary_reason,
            'secondary_reasons': self.secondary_reasons,
            'actions': [a.to_dict() for a in self.actions],
            'sound_type': self.sound_type,
            'sound_duration_sec': self.sound_duration_sec,
            'flash_pattern': self.flash_pattern,
            'color': self.color,
            'alert_id_from_audit': self.alert_id_from_audit,
            'driver_acknowledged': self.driver_acknowledged,
            'driver_id': self.driver_id,
            'acknowledge_time': self.acknowledge_time,
            'protocol_version': self.protocol_version,
        })
    
    def to_display_string(self) -> str:
        """HUD display format (short)"""
        return f"[{self.severity}] {self.alert_title}\n{self.alert_description}"


# ============================================================================
# HUD ACKNOWLEDGMENT & FEEDBACK
# ============================================================================

@dataclass
class HUDDriverResponse:
    """Driver's response to HUD alert"""
    
    message_id: str  # Which alert they're responding to
    driver_id: str  # Loco pilot ID
    response_type: Literal["acknowledged", "dismissed", "action_taken"]
    action_taken: Optional[str] = None  # What action they took
    current_speed: Optional[float] = None  # Speed at acknowledgment
    comments: Optional[str] = None  # Driver comments
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_json(self) -> str:
        return json.dumps({
            'message_id': self.message_id,
            'driver_id': self.driver_id,
            'response_type': self.response_type,
            'action_taken': self.action_taken,
            'current_speed': self.current_speed,
            'comments': self.comments,
            'timestamp': self.timestamp,
        })


# ============================================================================
# HUD DISPLAY FORMATTER
# ============================================================================

class HUDDisplayFormatter:
    """Format HUD messages for different display types"""
    
    @staticmethod
    def format_for_text_display(msg: HUDAlertMessage, width: int = 40) -> str:
        """Format for text-based HUD (40x4 characters typical)"""
        lines = []
        
        # Line 1: Severity + Title (truncate to width)
        severity_short = msg.severity.value[:3]
        title = msg.alert_title[:width - 4]
        lines.append(f"[{severity_short}] {title}")
        
        # Line 2: Primary reason
        reason = msg.primary_reason[:width]
        lines.append(f"Confidence: {msg.confidence*100:.0f}%")
        
        # Line 3: Train info
        speed_info = f"Speed: {msg.train_state.speed_kmph:.0f}/{msg.train_state.speed_limit_kmph:.0f}"
        lines.append(speed_info)
        
        # Line 4: Action
        if msg.actions:
            action = msg.actions[0].description[:width]
            lines.append(f"Action: {action}")
        else:
            lines.append("No action required")
        
        return "\n".join(lines[:4])
    
    @staticmethod
    def format_for_graphical_display(msg: HUDAlertMessage) -> Dict:
        """Format for graphical HUD with gauges, indicators"""
        return {
            'severity_color': {
                'CRITICAL': '#FF0000',
                'HIGH': '#FF8800',
                'MEDIUM': '#FFFF00',
                'LOW': '#00DD00',
                'ADVISORY': '#0088FF'
            }[msg.severity.value],
            'alert_title': msg.alert_title,
            'alert_description': msg.alert_description,
            'confidence_percent': int(msg.confidence * 100),
            'speed_current': msg.train_state.speed_kmph,
            'speed_limit': msg.train_state.speed_limit_kmph,
            'speed_recommended': msg.actions[0].target_value if msg.actions else msg.train_state.speed_kmph,
            'delay_minutes': msg.train_state.delay_minutes,
            'location': msg.location.station_name,
            'sound_indicator': msg.sound_type is not None,
            'actions': [
                {
                    'description': a.description,
                    'priority': a.priority,
                    'target_value': a.target_value
                }
                for a in msg.actions
            ]
        }
    
    @staticmethod
    def format_for_audio(msg: HUDAlertMessage) -> Dict:
        """Format for audio output (text-to-speech + sound effects)"""
        return {
            'sound_effect': msg.sound_type,
            'duration_sec': msg.sound_duration_sec or 3,
            'speech_text': f"{msg.severity}, {msg.alert_title}. {msg.alert_description}",
            'priority': {
                'CRITICAL': 'interrupt',
                'HIGH': 'immediate',
                'MEDIUM': 'queue',
                'LOW': 'background',
                'ADVISORY': 'background'
            }[msg.severity.value]
        }


# ============================================================================
# HUD MOCK DISPLAY (for testing)
# ============================================================================

class MockHUDDisplay:
    """Mock HUD display for testing and development"""
    
    def __init__(self, name: str = "MockHUD"):
        self.name = name
        self.display_buffer = []
        self.acknowledged = False
    
    def display_alert(self, msg: HUDAlertMessage):
        """Show alert on mock display"""
        print(f"\n{'='*50}")
        print(f"[{self.name}] {msg.severity} ALERT")
        print(f"{'='*50}")
        print(f"Train: {msg.train_id} @ {msg.location.station_name}")
        print(f"Title: {msg.alert_title}")
        print(f"Desc: {msg.alert_description}")
        print(f"Confidence: {msg.confidence*100:.1f}%")
        print(f"Speed: {msg.train_state.speed_kmph:.0f}/{msg.train_state.speed_limit_kmph:.0f} kmph")
        
        if msg.actions:
            print("\nRecommended Actions:")
            for i, action in enumerate(msg.actions, 1):
                print(f"  {i}. {action.description}")
        
        if msg.sound_type:
            print(f"\n[SOUND] {msg.sound_type.upper()}")
        
        print(f"{'='*50}\n")
        
        self.display_buffer.append(msg)
    
    def simulate_acknowledgment(self, message_id: str, driver_id: str):
        """Simulate driver acknowledgement"""
        msg = next((m for m in self.display_buffer if m.message_id == message_id), None)
        if msg:
            msg.driver_acknowledged = True
            msg.driver_id = driver_id
            msg.acknowledge_time = datetime.now().isoformat()
            print(f"[ACK] Driver {driver_id} acknowledged message {message_id}")
            return msg
        return None


if __name__ == '__main__':
    # Example usage
    import uuid
    
    msg = HUDAlertMessage(
        message_id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        severity=HUDSeverity.CRITICAL,
        message_type=HUDMessageType.ACCIDENT_RISK,
        train_id="TRAIN_12345",
        location=HUDLocation(
            station_id="BAL",
            station_name="Balasore",
            latitude=21.4774,
            longitude=86.9479,
            km_marker=150.5,
            track_section="SEC_15"
        ),
        train_state=HUDTrainState(
            train_id="TRAIN_12345",
            speed_kmph=75.0,
            speed_limit_kmph=100.0,
            acceleration=0.2,
            brake_status="normal",
            delay_minutes=5,
            next_stop="Cuttack",
            eta_minutes=15
        ),
        alert_title="ACCIDENT RISK DETECTED",
        alert_description="Multiple ML methods detect critical conditions. Prepare for emergency stop.",
        confidence=0.92,
        time_to_event_sec=180,
        primary_reason="Bayesian P(accident)=0.92, IF anomaly, DBSCAN detected, Causal chain",
        secondary_reasons=["Signal status abnormal", "Track maintenance active"],
        actions=[
            HUDActionItem(
                action_id="1",
                action_type="reduce_speed",
                priority="immediate",
                description="Reduce speed to 20 kmph",
                target_value=20.0,
                duration_sec=300
            ),
            HUDActionItem(
                action_id="2",
                action_type="prepare_brake",
                priority="immediate",
                description="Prepare emergency brake",
                duration_sec=60
            )
        ],
        sound_type="siren",
        sound_duration_sec=3,
        flash_pattern="continuous",
        color="#FF0000"
    )
    
    # Display on mock HUD
    hud = MockHUDDisplay("Loco_Cabin_1")
    hud.display_alert(msg)
    
    # Simulate acknowledgment
    driver_response = HUDDriverResponse(
        message_id=msg.message_id,
        driver_id="Loco_Pilot_ML-12",
        response_type="action_taken",
        action_taken="Speed reduced to 20 kmph",
        current_speed=20.0,
        comments="Emergency stop prepared"
    )
    
    hud.simulate_acknowledgment(msg.message_id, driver_response.driver_id)
    print(f"Driver Response JSON:\n{driver_response.to_json()}")
