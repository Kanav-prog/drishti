"""
DRISHTI Signalling System Integration
Connects alert distribution to Indian Railways signalling infrastructure
Implements automated mitigation through signal control and track management
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class SignalStatus(str, Enum):
    """Railway signal states per Indian Railway standards"""
    RED = "RED"              # Stop - do not proceed
    YELLOW = "YELLOW"        # Caution - prepare to stop
    GREEN = "GREEN"          # Proceed - line clear
    OFF = "OFF"              # Maintenance/offline


class TrackOccupancy(str, Enum):
    """Track section occupancy status"""
    CLEAR = "CLEAR"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    MAINTENANCE = "MAINTENANCE"


class SignallingCommand(str, Enum):
    """Automatic mitigation commands"""
    SET_SIGNAL_RED = "SET_SIGNAL_RED"              # Stop this train
    SET_SIGNAL_YELLOW = "SET_SIGNAL_YELLOW"        # Warn adjacent
    LOWER_SPEED_RESTRICTION = "LOWER_SPEED_RESTRICTION"  # Reduce allowed speed
    DIVERT_TRAIN = "DIVERT_TRAIN"                  # Send to alternate route
    ALERT_AHEAD_TRAIN = "ALERT_AHEAD_TRAIN"        # Warn train ahead
    EMERGENCY_BRAKE_CALL = "EMERGENCY_BRAKE_CALL"  # Lineside emergency brake
    RESERVE_SIDINGS = "RESERVE_SIDINGS"            # Clear escape routes


@dataclass
class SignallingStation:
    """Railway signalling station configuration"""
    station_id: str
    station_name: str
    location_km: float              # KM marker on line
    line_code: str                  # Branch line identifier
    signals_controlled: List[str]   # Signal IDs managed by this station
    interlocked_stations: List[str] # Nearby stations (for coordination)
    track_sections: List[str]       # Track sections under control
    scada_endpoint: Optional[str] = None  # SCADA system URL
    api_key: Optional[str] = None        # Authentication token


@dataclass
class SignalControl:
    """Individual signal state and configuration"""
    signal_id: str
    station_id: str
    signal_type: str               # Home, Distant, Shunt, etc.
    current_status: SignalStatus
    next_status: SignalStatus      # Pending change
    km_marker: float
    protects_train: Optional[str] = None  # Train ID if protecting specific train
    aspect_time: Optional[int] = None     # Time signal has been at current aspect (sec)
    maintenance_mode: bool = False


@dataclass
class TrackSection:
    """Railway track section configuration and state"""
    section_id: str
    station_from: str
    station_to: str
    km_marker_start: float
    km_marker_end: float
    occupancy_status: TrackOccupancy
    occupied_by_trains: List[str] = None  # Train IDs on this section
    normal_speed_kmph: int = 100
    reduced_speed_kmph: int = 80
    current_speed_restriction: int = 100   # Active speed limit
    emergency_brake_active: bool = False


@dataclass
class SignallingAction:
    """Request to change signalling infrastructure state"""
    action_id: str
    timestamp: str
    severity: str                  # CRITICAL, HIGH, MEDIUM, LOW
    source_alert_id: str
    source_train_id: str
    command: SignallingCommand
    station_id: str
    signal_ids: List[str]
    reason: str                    # Why this action
    duration_sec: Optional[int] = None  # How long to maintain (None=indefinite)
    reversible: bool = True        # Can be undone
    status: str = "pending"        # pending, executing, completed, failed


@dataclass
class SignallingResponse:
    """Response from signalling system to action"""
    action_id: str
    status: str                    # "success", "partial", "failed"
    timestamp: str
    messages: List[str]           # Execution messages
    affected_trains: List[str]    # Trains impacted
    metrics: Dict = None          # Performance metrics


class SignallingController:
    """
    Controls Indian Railways signalling infrastructure
    Executes automatically mitigations based on DRISHTI alerts
    """
    
    def __init__(self):
        self.stations: Dict[str, SignallingStation] = {}
        self.signals: Dict[str, SignalControl] = {}
        self.track_sections: Dict[str, TrackSection] = {}
        self.action_history: List[SignallingAction] = []
        self.response_history: List[SignallingResponse] = []
        self.active_restrictions: Dict[str, int] = {}  # train_id -> speed limit
    
    def register_station(self, station: SignallingStation) -> bool:
        """Register a signalling station"""
        if station.station_id in self.stations:
            logger.warning(f"Station {station.station_id} already registered")
            return False
        
        self.stations[station.station_id] = station
        logger.info(f"[SIGNALLING] Registered station {station.station_name} ({station.station_id})")
        
        return True
    
    def register_signal(self, signal: SignalControl) -> bool:
        """Register a signal for monitoring/control"""
        if signal.signal_id in self.signals:
            logger.warning(f"Signal {signal.signal_id} already registered")
            return False
        
        self.signals[signal.signal_id] = signal
        logger.info(f"[SIGNALLING] Registered signal {signal.signal_id} at {signal.km_marker}km")
        
        return True
    
    def register_track_section(self, section: TrackSection) -> bool:
        """Register a track section for occupancy tracking"""
        if section.section_id in self.track_sections:
            logger.warning(f"Section {section.section_id} already registered")
            return False
        
        section.occupied_by_trains = []
        self.track_sections[section.section_id] = section
        logger.info(f"[SIGNALLING] Registered track section {section.section_id}")
        
        return True
    
    def execute_alert_mitigation(self, alert_severity: str, train_id: str, 
                                 location_km: float, reason: str) -> SignallingAction:
        """
        Execute signalling mitigation for DRISHTI alert
        
        Args:
            alert_severity: "CRITICAL", "HIGH", "MEDIUM", "LOW"
            train_id: Affected train
            location_km: Current train location
            reason: Alert reason for audit
        
        Returns:
            SignallingAction with execution status
        """
        
        action_id = str(uuid.uuid4())
        logger.info(f"[MITIGATION] Severity={alert_severity}, Train={train_id}, Location={location_km}km")
        
        # Determine mitigation based on severity
        if alert_severity == "CRITICAL":
            action = self._execute_critical_mitigation(
                action_id, train_id, location_km, reason
            )
        elif alert_severity == "HIGH":
            action = self._execute_high_mitigation(
                action_id, train_id, location_km, reason
            )
        elif alert_severity == "MEDIUM":
            action = self._execute_medium_mitigation(
                action_id, train_id, location_km, reason
            )
        else:
            action = self._execute_low_mitigation(
                action_id, train_id, location_km, reason
            )
        
        # Log action
        self.action_history.append(action)
        
        # Execute signals
        response = self._execute_signalling_commands(action)
        self.response_history.append(response)
        
        logger.info(f"[MITIGATION] Action {action_id}: {response.status}")
        
        return action
    
    def _execute_critical_mitigation(self, action_id: str, train_id: str, 
                                     location_km: float, reason: str) -> SignallingAction:
        """CRITICAL: Full emergency stop - all available measures"""
        
        # Find all signals for this train
        signal_ids = self._find_signals_for_train(train_id)
        
        action = SignallingAction(
            action_id=action_id,
            timestamp=datetime.now().isoformat(),
            severity="CRITICAL",
            source_alert_id=str(uuid.uuid4()),  # Link to alert
            source_train_id=train_id,
            command=SignallingCommand.SET_SIGNAL_RED,
            station_id=self._find_station_for_location(location_km),
            signal_ids=signal_ids,
            reason=f"CRITICAL: {reason}",
            duration_sec=None,  # Indefinite until manually cleared
            reversible=True,
            status="executing"
        )
        
        # Set all signals to RED (stop)
        for signal_id in signal_ids:
            if signal_id in self.signals:
                self.signals[signal_id].next_status = SignalStatus.RED
                logger.warning(f"[SIGNAL] {signal_id} -> RED (CRITICAL)")
        
        # Set emergency speed restriction
        self.active_restrictions[train_id] = 0  # Stop
        logger.warning(f"[SPEED] Train {train_id}: 0 kmph (EMERGENCY STOP)")
        
        # Alert adjacent trains
        self._alert_surrounding_trains(train_id, location_km)
        
        # Call lineside emergency brake
        self._trigger_emergency_brake(location_km)
        
        action.status = "completed"
        return action
    
    def _execute_high_mitigation(self, action_id: str, train_id: str, 
                                 location_km: float, reason: str) -> SignallingAction:
        """HIGH: Controlled stop - warn surrounding trains"""
        
        signal_ids = self._find_signals_for_train(train_id)
        
        action = SignallingAction(
            action_id=action_id,
            timestamp=datetime.now().isoformat(),
            severity="HIGH",
            source_alert_id=str(uuid.uuid4()),
            source_train_id=train_id,
            command=SignallingCommand.LOWER_SPEED_RESTRICTION,
            station_id=self._find_station_for_location(location_km),
            signal_ids=signal_ids,
            reason=f"HIGH: {reason}",
            duration_sec=600,  # 10 minutes
            reversible=True,
            status="executing"
        )
        
        # Set signals to YELLOW (caution)
        for signal_id in signal_ids:
            if signal_id in self.signals:
                self.signals[signal_id].next_status = SignalStatus.YELLOW
                logger.warning(f"[SIGNAL] {signal_id} -> YELLOW (HIGH)")
        
        # Reduce speed to 30 kmph
        self.active_restrictions[train_id] = 30
        logger.warning(f"[SPEED] Train {train_id}: 30 kmph (HIGH ALERT)")
        
        # Alert ahead train
        self._alert_next_train(train_id, location_km)
        
        action.status = "completed"
        return action
    
    def _execute_medium_mitigation(self, action_id: str, train_id: str, 
                                   location_km: float, reason: str) -> SignallingAction:
        """MEDIUM: Precautionary speed reduction"""
        
        action = SignallingAction(
            action_id=action_id,
            timestamp=datetime.now().isoformat(),
            severity="MEDIUM",
            source_alert_id=str(uuid.uuid4()),
            source_train_id=train_id,
            command=SignallingCommand.LOWER_SPEED_RESTRICTION,
            station_id=self._find_station_for_location(location_km),
            signal_ids=[],
            reason=f"MEDIUM: {reason}",
            duration_sec=300,  # 5 minutes
            reversible=True,
            status="executing"
        )
        
        # Reduce speed to 50 kmph
        self.active_restrictions[train_id] = 50
        logger.info(f"[SPEED] Train {train_id}: 50 kmph (MEDIUM)")
        
        action.status = "completed"
        return action
    
    def _execute_low_mitigation(self, action_id: str, train_id: str, 
                                location_km: float, reason: str) -> SignallingAction:
        """LOW: Advisory - no action, monitoring only"""
        
        action = SignallingAction(
            action_id=action_id,
            timestamp=datetime.now().isoformat(),
            severity="LOW",
            source_alert_id=str(uuid.uuid4()),
            source_train_id=train_id,
            command=SignallingCommand.ALERT_AHEAD_TRAIN,
            station_id=self._find_station_for_location(location_km),
            signal_ids=[],
            reason=f"LOW: {reason}",
            duration_sec=60,  # 1 minute advisory
            reversible=True,
            status="completed"
        )
        
        # No speed restriction, just monitoring
        logger.info(f"[ADVISORY] Train {train_id}: Monitoring (LOW)")
        
        return action
    
    def _execute_signalling_commands(self, action: SignallingAction) -> SignallingResponse:
        """Execute actual signalling commands (mock implementation)"""
        
        response = SignallingResponse(
            action_id=action.action_id,
            status="success",
            timestamp=datetime.now().isoformat(),
            messages=[],
            affected_trains=[action.source_train_id],
            metrics={}
        )
        
        try:
            # In production: Call SCADA/signalling API
            # For now: Mock implementation
            
            if action.command == SignallingCommand.SET_SIGNAL_RED:
                response.messages.append(f"Set {len(action.signal_ids)} signals to RED")
                response.metrics['signals_changed'] = len(action.signal_ids)
                response.metrics['trains_stopped'] = 1
            
            elif action.command == SignallingCommand.SET_SIGNAL_YELLOW:
                response.messages.append(f"Set {len(action.signal_ids)} signals to YELLOW")
                response.metrics['signals_changed'] = len(action.signal_ids)
            
            elif action.command == SignallingCommand.LOWER_SPEED_RESTRICTION:
                response.messages.append(f"Speed restriction applied to {action.source_train_id}")
                response.metrics['speed_restriction_kmph'] = self.active_restrictions.get(
                    action.source_train_id, 100)
            
            else:
                response.messages.append(f"Executed {action.command}")
            
            logger.info(f"[EXECUTION] {action.action_id}: {response.status}")
            
        except Exception as e:
            response.status = "failed"
            response.messages.append(f"Execution failed: {str(e)}")
            logger.error(f"[EXECUTION] Action {action.action_id} failed: {e}")
        
        return response
    
    def update_track_occupancy(self, section_id: str, train_id: str, 
                               occupancy: TrackOccupancy) -> bool:
        """Update track section occupancy"""
        if section_id not in self.track_sections:
            logger.warning(f"Section {section_id} not found")
            return False
        
        section = self.track_sections[section_id]
        section.occupancy_status = occupancy
        
        if occupancy == TrackOccupancy.OCCUPIED:
            if train_id not in section.occupied_by_trains:
                section.occupied_by_trains.append(train_id)
        elif occupancy == TrackOccupancy.CLEAR:
            if train_id in section.occupied_by_trains:
                section.occupied_by_trains.remove(train_id)
        
        logger.info(f"[TRACK] {section_id}: {occupancy} (trains: {len(section.occupied_by_trains)})")
        return True
    
    def clear_restrictions(self, train_id: str) -> bool:
        """Clear speed restrictions for train"""
        if train_id in self.active_restrictions:
            del self.active_restrictions[train_id]
            logger.info(f"[CLEAR] Speed restriction removed for {train_id}")
            return True
        return False
    
    def get_signal_status(self, signal_id: str) -> Optional[Dict]:
        """Get current signal status"""
        if signal_id not in self.signals:
            return None
        
        signal = self.signals[signal_id]
        return {
            'signal_id': signal.signal_id,
            'current_status': signal.current_status.value,
            'next_status': signal.next_status.value,
            'km_marker': signal.km_marker,
            'protects_train': signal.protects_train,
            'maintenance_mode': signal.maintenance_mode
        }
    
    def get_track_status(self, section_id: str) -> Optional[Dict]:
        """Get current track section status"""
        if section_id not in self.track_sections:
            return None
        
        section = self.track_sections[section_id]
        return {
            'section_id': section.section_id,
            'occupancy': section.occupancy_status.value,
            'occupied_trains': section.occupied_by_trains,
            'speed_restriction': section.current_speed_restriction,
            'normal_speed': section.normal_speed_kmph,
            'emergency_brake': section.emergency_brake_active
        }
    
    def get_speed_restriction(self, train_id: str) -> int:
        """Get current speed restriction for train (kmph)"""
        return self.active_restrictions.get(train_id, 100)  # Default 100 kmph
    
    def get_system_status(self) -> Dict:
        """Get overall signalling system status"""
        return {
            'timestamp': datetime.now().isoformat(),
            'stations_registered': len(self.stations),
            'signals_registered': len(self.signals),
            'track_sections_registered': len(self.track_sections),
            'active_speed_restrictions': len(self.active_restrictions),
            'actions_executed': len(self.action_history),
            'last_action': self.action_history[-1].action_id if self.action_history else None,
            'signals_at_red': sum(1 for s in self.signals.values() if s.current_status == SignalStatus.RED),
            'signals_at_yellow': sum(1 for s in self.signals.values() if s.current_status == SignalStatus.YELLOW)
        }
    
    # Helper methods
    
    def _find_signals_for_train(self, train_id: str) -> List[str]:
        """Find all signals protecting a specific train"""
        signal_ids = []
        for sig_id, signal in self.signals.items():
            if signal.protects_train == train_id:
                signal_ids.append(sig_id)
        return signal_ids
    
    def _find_station_for_location(self, km_marker: float) -> str:
        """Find nearest station for location"""
        nearest_station = None
        nearest_distance = float('inf')
        
        for station_id, station in self.stations.items():
            distance = abs(station.location_km - km_marker)
            if distance < nearest_distance:
                nearest_distance = distance
                nearest_station = station_id
        
        return nearest_station or "UNKNOWN"
    
    def _alert_surrounding_trains(self, train_id: str, location_km: float) -> None:
        """Alert trains in adjacent sections"""
        logger.warning(f"[ALERT] Surrounding trains alerted (location: {location_km}km)")
    
    def _alert_next_train(self, train_id: str, location_km: float) -> None:
        """Alert train ahead on same line"""
        logger.warning(f"[ALERT] Next train alerted ({train_id} context)")
    
    def _trigger_emergency_brake(self, location_km: float) -> None:
        """Trigger lineside emergency brake"""
        logger.critical(f"[EMERGENCY] Lineside brake triggered at {location_km}km")


if __name__ == '__main__':
    # Example usage
    controller = SignallingController()
    
    # Register stations
    controller.register_station(SignallingStation(
        station_id="BAL",
        station_name="Balasore",
        location_km=150.5,
        line_code="SEC_15",
        signals_controlled=["BAL_HOME_1", "BAL_HOME_2"],
        interlocked_stations=["CUT", "BBD"],
        track_sections=["SEC_15_A", "SEC_15_B"]
    ))
    
    # Register signals
    controller.register_signal(SignalControl(
        signal_id="BAL_HOME_1",
        station_id="BAL",
        signal_type="Home",
        current_status=SignalStatus.GREEN,
        next_status=SignalStatus.GREEN,
        km_marker=150.5,
        protects_train="TRAIN_12345"
    ))
    
    # Register track sections
    controller.register_track_section(TrackSection(
        section_id="SEC_15_A",
        station_from="BAL",
        station_to="CUT",
        km_marker_start=150.5,
        km_marker_end=165.0,
        occupancy_status=TrackOccupancy.OCCUPIED,
        normal_speed_kmph=100,
        reduced_speed_kmph=80
    ))
    
    print("\n" + "="*80)
    print("SIGNALLING SYSTEM INTEGRATION TEST")
    print("="*80)
    
    # Simulate CRITICAL alert
    print("\n[TEST] CRITICAL Alert Mitigation")
    action = controller.execute_alert_mitigation(
        alert_severity="CRITICAL",
        train_id="TRAIN_12345",
        location_km=150.5,
        reason="Bayesian P=0.92, Multiple ML methods predict accident risk"
    )
    
    print(f"Action: {action.action_id}")
    print(f"Command: {action.command}")
    print(f"Status: {action.status}")
    print(f"Speed Restriction: {controller.get_speed_restriction('TRAIN_12345')} kmph")
    
    # Show system status
    status = controller.get_system_status()
    print(f"\n[SYSTEM] {status['signals_at_red']} signals at RED")
    print(f"[SYSTEM] {status['active_speed_restrictions']} active restrictions")
