"""
Phase 5.D: Dual-Evidence Inference Engine
Purpose: Integrate Network Science + ML Evidence for high-confidence alerts
Combines: ML ensemble (behavioral) + Network centrality (structural) + Pattern matching

Author: DRISHTI Research - Phase 5.D
Date: March 31, 2026
"""

import asyncio
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

from backend.network.graph import IRNetworkGraph
from backend.network.crs_validator import CRSHistoricalAccidents
from backend.network.signatures import (
    PreAccidentSignatureLibrary,
    SignatureMatchingEngine,
    LiveStreamData,
    DualEvidenceRiskScorer
)

logger = logging.getLogger(__name__)


class DualEvidenceInferenceEngine:
    """
    Enhanced inference pipeline with dual-evidence validation
    
    ARCHITECTURE:
    Live Data → Feature Extract → ML Inference → Network Evidence → Dual Score → Alert
    
    EVIDENCE LAYERS:
    1. ML Evidence: Ensemble anomaly detection (behavioral risk)
    2. Network Evidence: Centrality + pre-accident patterns (structural risk)
    3. Dual Score: Combined confidence when both agree
    """
    
    def __init__(self, 
                 base_inference_engine,  # Existing ML engine
                 crs_data: Optional[Dict] = None):
        """
        Args:
            base_inference_engine: Existing UnifiedInferenceEngine
            crs_data: Historical CRS accidents (None = use mock)
        """
        self.base_engine = base_inference_engine
        
        # Initialize network science modules
        self._init_network_graph()
        self._init_crs_validator(crs_data)
        self._init_signature_matching()
        
        logger.info("✅ Dual-evidence inference engine initialized")
    
    def _init_network_graph(self):
        """Initialize IR network graph with centrality scoring"""
        self.graph = IRNetworkGraph()
        
        # Would populate with real IR network data
        # For now, this is ready for integration
        logger.info("Network graph initialized")
    
    def _init_crs_validator(self, crs_data: Optional[Dict]):
        """Initialize CRS historical accidents validator"""
        self.crs_validator = CRSHistoricalAccidents()
        
        if crs_data:
            self.crs_validator.load_from_corpus(crs_data)
            logger.info(f"CRS data loaded: {self.crs_validator.total_accidents} accidents")
        else:
            logger.info("CRS validator ready for data loading")
    
    def _init_signature_matching(self):
        """Initialize pre-accident pattern matching"""
        self.pattern_library = PreAccidentSignatureLibrary()
        
        # Build library from CRS data if available
        if self.crs_validator.total_accidents > 0:
            from backend.network.crs_validator import MOCK_CRS_ACCIDENTS
            self.pattern_library.build_from_crs_data(MOCK_CRS_ACCIDENTS)
        
        self.signature_engine = SignatureMatchingEngine(self.pattern_library)
        logger.info("Signature matching engine initialized")
    
    async def infer_train_dual_evidence(self,
                                       train_id: str,
                                       train_state: Dict,
                                       network_context: Optional[Dict] = None,
                                       all_trains: Optional[list] = None) -> Dict:
        """
        Full dual-evidence inference for a train
        
        Args:
            train_id: Train identifier
            train_state: Live train state (delay, speed, position, etc.)
            network_context: Network-wide metrics (density, delays, etc.)
            all_trains: All active trains (for density computation)
            
        Returns:
            {
                "alert_fired": bool,
                "base_alert": dict,  # ML-only alert (if any)
                "evidence": {
                    "type": "SINGLE|DUAL|DUAL+",
                    "ml_risk": float,
                    "network_risk": float,
                    "signature_matches": int,
                    "combined_score": float,
                    "confidence": float
                },
                "network_analysis": {
                    "junction": str,
                    "centrality": float,
                    "historic_accidents": int,
                    "matching_patterns": list
                }
            }
        """
        
        # Step 1: Get ML evidence from base engine
        ml_result = await self.base_engine.infer_train(
            train_id=train_id,
            train_state=train_state,
            all_trains=all_trains
        )
        
        ml_risk = 0.0
        if ml_result:
            # Extract risk score from ml_result
            ml_risk = ml_result.get("risk_score", 0) / 100.0  # Normalize to 0-1
        
        # Step 2: Compute network science evidence
        junction = train_state.get("station", "")
        centrality_score = self._get_centrality(junction)
        
        # Step 3: Match against historical patterns
        pattern_matches = self._match_patterns(train_state, network_context)
        
        # Step 4: Combine evidence
        dual_evidence = DualEvidenceRiskScorer.compute_dual_risk(
            ml_risk_score=ml_risk,
            centrality_score=centrality_score,
            signatures_matched_count=len(pattern_matches)
        )
        
        # Step 5: Determine if alert should fire
        alert_fires = False
        final_alert = None
        
        # DUAL+ evidence: Always fire (95% confidence)
        if dual_evidence["evidence_type"] == "DUAL+":
            alert_fires = True
        # DUAL evidence: Fire if score > threshold (85% confidence)
        elif dual_evidence["evidence_type"] == "DUAL" and dual_evidence["combined_risk_score"] > 0.7:
            alert_fires = True
        # SINGLE evidence: Use base ML alert only
        elif ml_result and ml_result.get("severity") in ["CRITICAL", "HIGH"]:
            alert_fires = True
            final_alert = ml_result
        
        # Get historic accident stats for this junction
        historic_accidents = self.crs_validator.get_accident_frequency(junction)
        
        return {
            "alert_fired": alert_fires,
            "base_ml_alert": ml_result,
            "final_alert": final_alert if final_alert else (
                self._create_dual_evidence_alert(
                    train_id=train_id,
                    train_state=train_state,
                    ml_alert=ml_result,
                    dual_evidence=dual_evidence,
                    junction_data={
                        "centrality": centrality_score,
                        "historic_accidents": historic_accidents,
                        "pattern_matches": pattern_matches,
                        "zone": train_state.get("zone", "unknown")
                    }
                ) if alert_fires else None
            ),
            "evidence": dual_evidence,
            "network_analysis": {
                "junction": junction,
                "centrality_score": centrality_score,
                "centrality_percentile": int(centrality_score * 100),
                "historic_accidents": historic_accidents.get("frequency", 0),
                "historic_deaths": historic_accidents.get("total_deaths", 0),
                "matching_patterns": len(pattern_matches),
                "pattern_details": pattern_matches[:3]  # Top 3
            }
        }
    
    def _get_centrality(self, station_code: str) -> float:
        """Get network centrality score for a station (0-1)"""
        try:
            centrality_scores = self.graph.compute_betweenness_centrality()
            return float(centrality_scores.get(station_code, 0.0))
        except Exception as e:
            logger.warning(f"Error computing centrality for {station_code}: {e}")
            return 0.0
    
    def _match_patterns(self, 
                       train_state: Dict, 
                       network_context: Optional[Dict]) -> list:
        """Match current conditions against pre-accident patterns"""
        if not network_context:
            return []
        
        try:
            live_data = LiveStreamData(
                timestamp=datetime.now(),
                section_code=train_state.get("station", ""),
                section_type=train_state.get("section_type", "Double-track"),
                time_of_day=train_state.get("time_of_day", "Unknown"),
                weather=network_context.get("weather", "Unknown"),
                trains_delayed=network_context.get("trains_delayed", 0),
                total_delay_accumulated_minutes=network_context.get("total_delay_minutes", 0),
                train_density=network_context.get("train_density", 0),
                avg_train_delay_minutes=network_context.get("avg_train_delay_minutes", 0),
                recent_signalling_events=network_context.get("signalling_events", 0)
            )
            
            section_type = train_state.get("section_type", "Double-track")
            centrality = self._get_centrality(train_state.get("station", ""))
            
            matches = self.signature_engine.match_live_data(
                live_data=live_data,
                section_type=section_type,
                centrality_score=centrality
            )
            
            # Return top matches with risk levels
            return [
                {
                    "pattern_id": m.pattern_id,
                    "match_score": m.match_score,
                    "risk_level": m.risk_level,
                    "historical_severity": m.historical_severity,
                    "probability": m.probability_of_major_accident
                }
                for m in matches[:5]  # Top 5
            ]
        
        except Exception as e:
            logger.warning(f"Error matching patterns: {e}")
            return []
    
    def _create_dual_evidence_alert(self,
                                    train_id: str,
                                    train_state: Dict,
                                    ml_alert: Optional[Dict],
                                    dual_evidence: Dict,
                                    junction_data: Dict) -> Dict:
        """Create alert enriched with dual-evidence information"""
        
        return {
            "alert_id": ml_alert.get("alert_id") if ml_alert else f"DUAL_{train_id}_{datetime.now().timestamp()}",
            "timestamp": datetime.utcnow().isoformat(),
            "train_id": train_id,
            "station": train_state.get("station", "unknown"),
            "zone": junction_data.get("zone", "unknown"),
            
            # Scores
            "risk_score": dual_evidence["combined_risk_score"] * 100,
            "severity": self._severity_from_score(dual_evidence["combined_risk_score"]),
            "confidence": dual_evidence["confidence"],
            
            # Evidence breakdown
            "evidence": {
                "type": dual_evidence["evidence_type"],
                "ml_risk": dual_evidence["ml_evidence"] * 100,
                "network_risk": dual_evidence["network_evidence"] * 100,
                "signature_matches": dual_evidence["signatures_matched"],
                "combined_score": dual_evidence["combined_risk_score"],
                "reasoning": dual_evidence["reasoning"]
            },
            
            # Network context
            "network_analysis": {
                "junction_centrality": junction_data["centrality"],
                "historic_accidents": junction_data["historic_accidents"].get("frequency", 0),
                "historic_deaths": junction_data["historic_accidents"].get("total_deaths", 0),
                "matching_patterns": junction_data["pattern_matches"]
            },
            
            # Base ML alert enrichment
            "base_ml_alert": ml_alert,
            
            # Recommended actions (enhanced)
            "actions": self._get_dual_evidence_actions(
                dual_evidence["evidence_type"],
                dual_evidence["combined_risk_score"],
                junction_data["centrality"]
            ),
            
            "acknowledged": False
        }
    
    def _severity_from_score(self, score: float) -> str:
        """Convert risk score to severity level"""
        if score >= 0.85:
            return "CRITICAL"
        elif score >= 0.7:
            return "HIGH"
        elif score >= 0.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _get_dual_evidence_actions(self, 
                                  evidence_type: str,
                                  risk_score: float,
                                  centrality: float) -> list:
        """Get recommended actions based on dual evidence"""
        actions = []
        
        # DUAL+ evidence (highest confidence)
        if evidence_type == "DUAL+":
            actions.append("IMMEDIATE_SPEED_RESTRICTION")
            actions.append("ALERT_ADJACENT_TRAINS")
            actions.append("NOTIFY_DISPATCH_CENTER")
        
        # DUAL evidence (high centrality junction)
        elif evidence_type == "DUAL":
            if centrality > 0.8:
                actions.append("SPEED_RESTRICTION")
                actions.append("ALERT_ADJACENT_TRAINS")
            else:
                actions.append("HUD_WARNING")
                actions.append("CREW_ALERT")
        
        # SINGLE evidence fallback
        else:
            actions.append("HUD_WARNING")
            if risk_score > 0.8:
                actions.append("CREW_ALERT")
        
        return actions


class DualEvidenceAlertGenerator:
    """Generate production-grade alerts with dual-evidence annotations"""
    
    @staticmethod
    def generate_with_evidence(dual_alert: Dict) -> str:
        """Generate human-readable alert message with reasoning"""
        
        evidence = dual_alert.get("evidence", {})
        network = dual_alert.get("network_analysis", {})
        
        message = f"""
🚨 DRISHTI DUAL-EVIDENCE ALERT
{'='*60}
Train ID: {dual_alert['train_id']} | Station: {dual_alert['station']}
Risk Score: {dual_alert['risk_score']:.0f}/100 | Severity: {dual_alert['severity']}

EVIDENCE ANALYSIS:
─────────────────
Evidence Type: {evidence.get('type') or evidence.get('evidence_type', 'UNKNOWN')}
  • ML Risk Score: {evidence.get('ml_risk', evidence.get('ml_evidence', 0)):.0f}% (behavioral analysis)
  • Network Risk Score: {evidence.get('network_risk', evidence.get('network_evidence', 0)):.0f}% (structural analysis)
  • Combined Risk: {evidence.get('combined_score', 0):.2f}
  • Confidence: {dual_alert['confidence']:.0%}

NETWORK CONTEXT:
────────────────
Junction: {dual_alert['station']} (Centrality: {network.get('junction_centrality', 0):.3f})
Historical Accidents: {network.get('historic_accidents', 0)}
Pre-accident Pattern Matches: {network.get('matching_patterns', 0)}

REASONING:
──────────
{evidence.get('reasoning', 'Unknown')}

RECOMMENDED ACTIONS:
───────────────────
{chr(10).join("  • " + a for a in dual_alert.get('actions', []))}

{'='*60}
"""
        return message.strip()


# Example usage pattern (for testing integration)
async def example_dual_evidence_inference():
    """Example of how to use dual-evidence engine"""
    from backend.inference.engine import UnifiedInferenceEngine
    
    # Initialize base ML engine
    base_engine = UnifiedInferenceEngine()
    
    # Wrap with dual-evidence layer
    dual_engine = DualEvidenceInferenceEngine(
        base_inference_engine=base_engine
    )
    
    # Example train state
    train_state = {
        "train_id": "12345",
        "station": "BLSR",  # Balasore
        "zone": "ER",
        "delay": 15,
        "speed": 45,
        "time_of_day": "Night",
        "section_type": "Double-track",
        "maintenance_active": False,
        "lat": 21.5,
        "lon": 86.93
    }
    
    # Network context
    network_context = {
        "trains_delayed": 8,
        "total_delay_minutes": 720,
        "train_density": 10,
        "avg_train_delay_minutes": 90,
        "weather": "Clear",
        "signalling_events": 0
    }
    
    # Run inference
    result = await dual_engine.infer_train_dual_evidence(
        train_id="12345",
        train_state=train_state,
        network_context=network_context
    )
    
    # Generate alert message
    if result["alert_fired"] and result["final_alert"]:
        message = DualEvidenceAlertGenerator.generate_with_evidence(result["final_alert"])
        print(message)
    
    return result
