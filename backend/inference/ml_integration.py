"""
ML Model Integration & Real-time Inference
Loads trained ML model state and computes risk scores for live trains
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class MLModelLoader:
    """Load and access trained ML model state"""
    
    def __init__(self, model_path: str = "ml_model_state.json"):
        self.model_path = Path(model_path)
        self.model_state = None
        self.zone_base_rates = {}
        self.prediction_windows = {}
        self.feature_importance = {}
        self.model_performance = {}
        
        self.load_model()
    
    def load_model(self) -> bool:
        """Load ML model state from JSON file"""
        try:
            if not self.model_path.exists():
                logger.warning(f"Model file not found: {self.model_path}")
                return False
            
            with open(self.model_path, 'r') as f:
                self.model_state = json.load(f)
            
            # Extract components
            self.zone_base_rates = self.model_state.get('zone_base_rates', {})
            self.prediction_windows = self.model_state.get('prediction_windows', {})
            self.feature_importance = self.model_state.get('feature_importance', {})
            self.model_performance = self.model_state.get('model_performance', {})
            
            logger.info(f"[OK] ML model loaded: {len(self.zone_base_rates)} zones, "
                       f"{len(self.prediction_windows)} patterns, "
                       f"accuracy={self.model_performance.get('retrospective_accuracy', 'N/A')}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to load ML model: {e}")
            return False
    
    def get_zone_risk(self, zone_code: str) -> float:
        """Get base accident risk for a zone (0-1)"""
        if zone_code not in self.zone_base_rates:
            logger.warning(f"Zone not in model: {zone_code}")
            return 0.05  # Default low risk
        
        return self.zone_base_rates[zone_code].get('adjusted_rate', 0.05)
    
    def get_prediction_window(self, signature_type: str) -> Optional[Dict]:
        """Get prediction window for a signature type"""
        return self.prediction_windows.get(signature_type)


class MLInference:
    """Real-time ML inference for train risk assessment"""
    
    def __init__(self, model_loader: Optional[MLModelLoader] = None):
        self.model = model_loader or MLModelLoader()
        self.recent_inferences = {}  # Cache recent results
    
    def compute_train_risk(self, train_data: Dict) -> Dict:
        """
        Compute complete risk assessment for a train.
        
        Args:
            train_data: {
                'train_id': str,
                'zone': str,
                'station': str,
                'delay_minutes': float,
                'speed_kmph': float,
                'is_heavy_train': bool,
                'weather': str,  # 'Clear', 'Rain', 'Fog'
            }
        
        Returns:
            {
                'bayesian_risk': float (0-1),
                'anomaly_score': float (0-100),
                'causal_risk': float (0-1),
                'trajectory_anomaly': bool,
                'methods_voting': {method_name: bool},
                'recommended_actions': [str],
                'inference_timestamp': str,
            }
        """
        
        train_id = train_data.get('train_id', 'UNKNOWN')
        zone = train_data.get('zone', 'UNKNOWN')
        delay_minutes = train_data.get('delay_minutes', 0)
        speed_kmph = train_data.get('speed_kmph', 100)
        weather = train_data.get('weather', 'Clear')
        is_heavy_train = train_data.get('is_heavy_train', False)
        
        # Method 1: Bayesian Network (Zone-based base rates)
        bayesian_risk = self._compute_bayesian_risk(zone, delay_minutes, weather)
        
        # Method 2: Isolation Forest / Anomaly Detection
        anomaly_score = self._compute_anomaly_score(
            speed_kmph, delay_minutes, is_heavy_train, weather
        )
        
        # Method 3: Causal DAG (depends on zone + weather + delay)
        causal_risk = self._compute_causal_risk(zone, weather, delay_minutes)
        
        # Method 4: Trajectory/DBSCAN (isolated train detection)
        trajectory_anomaly = self._detect_trajectory_anomaly(
            speed_kmph, delay_minutes, is_heavy_train
        )
        
        # Voting: Which methods flag danger?
        methods_voting = {
            'bayesian_network': bayesian_risk > 0.4,
            'isolation_forest': anomaly_score > 65,
            'causal_dag': causal_risk > 0.4,
            'trajectory_dbscan': trajectory_anomaly
        }
        
        methods_flagging = sum(1 for v in methods_voting.values() if v)
        
        # Recommended actions
        actions = self._determine_actions(
            zone, bayesian_risk, anomaly_score, methods_flagging, weather
        )
        
        result = {
            'train_id': train_id,
            'zone': zone,
            'bayesian_risk': bayesian_risk,
            'anomaly_score': anomaly_score,
            'causal_risk': causal_risk,
            'trajectory_anomaly': trajectory_anomaly,
            'methods_voting': methods_voting,
            'methods_flagging': methods_flagging,
            'recommended_actions': actions,
            'inference_timestamp': datetime.utcnow().isoformat(),
        }
        
        # Cache result
        self.recent_inferences[train_id] = result
        
        return result
    
    def _compute_bayesian_risk(self, zone: str, delay_minutes: float, weather: str) -> float:
        """Bayesian Network: Zone base rate adjusted by delay and weather"""
        # Get base rate from model
        base_rate = self.model.get_zone_risk(zone)
        
        # Adjust by delay (trains with large delays are more at risk)
        delay_factor = 1.0
        if delay_minutes > 60:
            delay_factor = 1.2  # 20% increase for heavily delayed trains
        elif delay_minutes > 30:
            delay_factor = 1.1
        
        # Adjust by weather (rain/fog increase risk)
        weather_factor = 1.0
        if weather in ['Rain', 'Heavy Rain']:
            weather_factor = 1.3
        elif weather == 'Fog':
            weather_factor = 1.25
        
        # Combined risk (cap at 1.0)
        adjusted_risk = min(base_rate * delay_factor * weather_factor, 1.0)
        
        logger.debug(f"Bayesian risk for {zone}: base={base_rate:.2f}, "
                    f"delay_factor={delay_factor}, weather={weather_factor}, "
                    f"adjusted={adjusted_risk:.3f}")
        
        return adjusted_risk
    
    def _compute_anomaly_score(self, speed_kmph: float, delay_minutes: float, 
                              is_heavy_train: bool, weather: str) -> float:
        """Isolation Forest: Detect unusual speed/delay/train combinations"""
        
        # Normal parameters (tuned from historical data)
        normal_speed = 80  # Average running speed
        normal_delay = 15  # Average delay
        
        # Compute deviations
        speed_deviation = abs(speed_kmph - normal_speed) / normal_speed
        delay_deviation = abs(delay_minutes - normal_delay) / max(normal_delay, 1)
        
        # Heavy trains are expected to run slower/get delayed more
        if is_heavy_train:
            normal_speed = 60
            normal_delay = 30
            speed_deviation = abs(speed_kmph - normal_speed) / normal_speed
            delay_deviation = abs(delay_minutes - normal_delay) / max(normal_delay, 1)
        
        # Combine deviations into anomaly score (0-100)
        anomaly_score = (speed_deviation + delay_deviation) * 50
        
        # Rain/fog slightly increases anomaly threshold (harder to measure)
        if weather in ['Rain', 'Heavy Rain', 'Fog']:
            anomaly_score *= 1.1
        
        # Cap at 100
        anomaly_score = min(anomaly_score, 100)
        
        logger.debug(f"Anomaly score: speed_dev={speed_deviation:.2f}, "
                    f"delay_dev={delay_deviation:.2f}, score={anomaly_score:.1f}")
        
        return anomaly_score
    
    def _compute_causal_risk(self, zone: str, weather: str, delay_minutes: float) -> float:
        """Causal DAG: Zone maintenance issues cause accidents"""
        
        # Get zone health metrics from base rates
        zone_rate = self.model.get_zone_risk(zone)
        
        # Causal factors:
        # - Maintenance backlog (from zone_base_rates shortfall_factor)
        zone_data = self.model.zone_base_rates.get(zone, {})
        shortfall_factor = zone_data.get('shortfall_factor', 1.0)
        spad_factor = zone_data.get('spad_factor', 1.0)
        
        # High shortfall → high causal risk
        causal_risk = (shortfall_factor - 1.0) * 0.15  # 0-15% from shortfall
        causal_risk += (spad_factor - 1.0) * 0.10     # 0-10% from SPAD
        
        # Weather and delay compound the risk
        if weather in ['Rain', 'Heavy Rain']:
            causal_risk += 0.15
        elif weather == 'Fog':
            causal_risk += 0.10
        
        if delay_minutes > 60:
            causal_risk += 0.10
        
        # Cap at 1.0
        causal_risk = min(causal_risk, 1.0)
        
        logger.debug(f"Causal risk for {zone}: shortfall={shortfall_factor:.2f}, "
                    f"spad={spad_factor:.2f}, causal={causal_risk:.3f}")
        
        return causal_risk
    
    def _detect_trajectory_anomaly(self, speed_kmph: float, delay_minutes: float, 
                                   is_heavy_train: bool) -> bool:
        """DBSCAN: Detect isolated/unusual train trajectories"""
        
        # Flags for trajectory anomaly:
        # 1. Extremely low speed (near stopped)
        # 2. Massive delay (> 2 hours)
        # 3. Heavy train with high speed
        
        flags = []
        
        if speed_kmph < 10:  # Train nearly stopped
            flags.append('stopped')
        
        if delay_minutes > 120:  # > 2 hours delay
            flags.append('severe_delay')
        
        if is_heavy_train and speed_kmph > 100:  # Heavy train running too fast
            flags.append('heavy_fast')
        
        trajectory_anomaly = len(flags) >= 1
        
        if trajectory_anomaly:
            logger.debug(f"Trajectory anomaly detected: {flags}")
        
        return trajectory_anomaly
    
    def _determine_actions(self, zone: str, bayesian_risk: float, anomaly_score: float,
                          methods_flagging: int, weather: str) -> list:
        """Determine recommended actions based on risk assessment"""
        
        actions = []
        
        # High Bayesian risk
        if bayesian_risk > 0.6:
            actions.append('HUD_CRITICAL_WARNING')
            actions.append('ALERT_DISPATCH_CONTROL')
        elif bayesian_risk > 0.4:
            actions.append('HUD_WARNING')
        
        # High anomaly (unusual patterns)
        if anomaly_score > 80:
            actions.append('SPEED_RESTRICTION')
            actions.append('ADJACENT_TRAINS_ALERT')
        
        # Multiple methods flagging danger
        if methods_flagging >= 3:
            actions.append('EMERGENCY_INSPECTION')
            actions.append('SLOW_ZONE_ACTIVATION')
        
        # Weather-specific actions
        if weather == 'Fog':
            actions.append('HEADLIGHT_FULL')
            actions.append('SPEED_REDUCTION_FOG')
        elif weather == 'Heavy Rain':
            actions.append('TRACK_INSPECTION_ALERT')
            actions.append('DRAINAGE_CHECK')
        
        # High-risk zones get extra care
        if zone in ['ER', 'CR', 'ECoR']:  # Known high-accident zones
            if bayesian_risk > 0.3:
                actions.append('ENHANCED_MONITORING')
        
        return actions


# Convenience functions for easy access

_model_loader = None
_ml_inference = None


def initialize_ml_inference(model_path: str = "ml_model_state.json") -> MLInference:
    """Initialize global ML inference engine"""
    global _model_loader, _ml_inference
    
    _model_loader = MLModelLoader(model_path)
    _ml_inference = MLInference(_model_loader)
    
    logger.info("[OK] ML inference engine initialized")
    return _ml_inference


def get_ml_inference() -> MLInference:
    """Get global ML inference engine"""
    global _ml_inference
    
    if _ml_inference is None:
        initialize_ml_inference()
    
    return _ml_inference


def compute_risk_for_train(train_data: Dict) -> Dict:
    """Compute risk for a train (convenience wrapper)"""
    return get_ml_inference().compute_train_risk(train_data)
