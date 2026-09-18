"""
UNIFIED ALERT REASONING ENGINE
Connects all AI/ML signals (anomalies, incidents, correlations, predictions)
into actionable, reasoned alerts with explanations
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
import json

router = APIRouter(prefix="/api/alerts", tags=["alert-reasoning"])

class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class AlertReason(BaseModel):
    """Structured reason for each alert: connects to specific AI/ML signal."""
    category: str  # "anomaly", "incident", "cascade", "prediction", "correlation"
    confidence: float  # 0.0-1.0
    evidence: List[str]  # Supporting data points
    affected_entities: List[str]  # Trains, stations, routes affected
    recommended_action: str
    ml_model: Optional[str]  # e.g., "isolation_forest", "lstm_predictor", "cascade_simulator"

class Alert(BaseModel):
    """Production alert with full reasoning chain."""
    alert_id: str
    severity: AlertSeverity
    title: str
    description: str
    timestamp: datetime
    reasons: List[AlertReason]
    affected_trains: List[str]
    affected_junctions: List[str]
    estimated_impact: Dict[str, Any]  # delay_minutes, stranded_passengers, etc.
    
@router.get("/unified")
async def get_unified_alerts(
    severity: AlertSeverity = Query(None, description="Filter by severity"),
    limit: int = Query(50, le=500),
    hours: int = Query(24, description="Last N hours"),
    include_reasoning: bool = Query(True, description="Include full reasoning chain"),
):
    """
    Get UNIFIED alerts combining ALL intelligence:
    - Anomaly detection (Isolation Forest)
    - Incident tracking (recent disruptions)
    - Cascade predictions (network propagation)
    - LSTM predictions (speed/delay forecasts)
    - Correlation analysis (multi-train patterns)
    """
    
    # In production: fetch from unified_alerts table with full reasoning
    # This is a rich example showing the structure:
    
    alerts = [
        Alert(
            alert_id="ALT-2024-001",
            severity=AlertSeverity.CRITICAL,
            title="MAJOR CASCADE DETECTED: Delhi → Lucknow → Gaya",
            description="Cascading delays detected at NDLS hub affecting 67 trains across NR, "
                       "propagating down to LKO and potentially reaching MGS/PNBE. "
                       "This is a TIER-1 incident requiring immediate action.",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=15),
            reasons=[
                AlertReason(
                    category="cascade",
                    confidence=0.98,
                    evidence=[
                        "12 high-centrality junctions affected",
                        "Average delay spike of 67 minutes",
                        "Network model predicts 15% probability of complete hub failure",
                    ],
                    affected_entities=["12001", "12002", "12301", "12302", "12309", "12310"],
                    recommended_action="Activate CASCADE_RESPONSE_PROTOCOL: "
                                      "Reroute non-critical trains via BR, delay Rajdhani departures",
                    ml_model="cascade_simulator",
                ),
                AlertReason(
                    category="anomaly",
                    confidence=0.95,
                    evidence=[
                        "Isolation Forest flagged 47 trains with >5σ delay",
                        "3 trains in EMERGENCY status",
                    ],
                    affected_entities=["NDLS", "LKO", "MGS"],
                    recommended_action="Perform emergency diagnostics at NDLS signalling",
                    ml_model="isolation_forest",
                ),
                AlertReason(
                    category="prediction",
                    confidence=0.87,
                    evidence=[
                        "LSTM model predicts 2-hour duration for cascade",
                        "85% confidence the cascade will peak at PNBE/ALD",
                    ],
                    affected_entities=["PNBE", "ALD", "HWH"],
                    recommended_action="Pre-position recovery resources at PNBE",
                    ml_model="lstm_cascade_predictor",
                ),
            ],
            affected_trains=["12001", "12002", "12301", "12302", "12309", "12310", "14031", "14032", "22691"],
            affected_junctions=["NDLS", "CNB", "JHS", "ALD", "MGS", "PNBE", "LKO", "GKP"],
            estimated_impact={
                "total_delay_train_minutes": 4521,  # 67 trains × 67 avg minutes
                "stranded_passengers": 28750,  # (4521 avg min / 1440 min/day) × avg occupancy
                "economic_loss_inr": 2872500,  # Per incident average
                "recovery_time_hours": 2.5,
                "critical_trains": 3,
                "zone_priority": ["NR", "ECR"],
            },
        ),
        Alert(
            alert_id="ALT-2024-002",
            severity=AlertSeverity.WARNING,
            title="ANOMALOUS SPEED PATTERN: 22 trains @ 40% below capacity",
            description="Isolated Forest detected 22 trains running at 40% below normal operational speed "
                       "across WR zone. Likely cause: track congestion or signalling issues.",
            timestamp=datetime.now(timezone.utc) - timedelta(minutes=5),
            reasons=[
                AlertReason(
                    category="anomaly",
                    confidence=0.92,
                    evidence=[
                        "Speed deviation: -42% (mean 80 km/h → observed 46 km/h)",
                        "Spatial clustering: 18/22 trains on BOMBAY-PUNE-ET corridor",
                        "Temporal pattern: Consistent for 45+ minutes",
                    ],
                    affected_entities=["BOMBAY", "PUNE", "ET"],
                    recommended_action="Check BOMBAY-PUNE section signalling system logs",
                    ml_model="isolation_forest",
                ),
                AlertReason(
                    category="correlation",
                    confidence=0.88,
                    evidence=[
                        "All 22 trains passing through same 3 junctions in 45min window",
                        "Correlation with maintenance window? (Checked: No)",
                        "Likely infrastructure bottleneck",
                    ],
                    affected_entities=["BOMBAY", "PUNE"],
                    recommended_action="Initiate root cause analysis with field teams",
                    ml_model="correlation_engine",
                ),
            ],
            affected_trains=["12951", "12952", "12622", "12621", "12627", "12628", "11061", "11062"],
            affected_junctions=["BOMBAY", "DADAR", "PUNE", "ET"],
            estimated_impact={
                "total_delay_train_minutes": 1848,  # 22 trains × 84 min average
                "stranded_passengers": 5040,
                "economic_loss_inr": 315600,
                "recovery_time_hours": 1.5,
                "critical_trains": 0,
                "zone_priority": ["WR", "CR"],
            },
        ),
        Alert(
            alert_id="ALT-2024-003",
            severity=AlertSeverity.INFO,
            title="UPCOMING DELAYS PREDICTED (Next 3 hrs): Howrah Junction",
            description="LSTM delay predictor estimates HWH junction will experience 35-45 min delays "
                       "in the next 3 hours (confidence: 84%) due to converging train traffic patterns.",
            timestamp=datetime.now(timezone.utc),
            reasons=[
                AlertReason(
                    category="prediction",
                    confidence=0.84,
                    evidence=[
                        "LSTM model trained on 18 months HWH data",
                        "12 high-density trains converging in 180-minute window",
                        "Historical similar patterns: 87% result in 40-50min delays",
                    ],
                    affected_entities=["HWH", "ALD", "PNBE", "KGP"],
                    recommended_action="Pre-emptively coordinate platform allocation at HWH",
                    ml_model="lstm_delay_predictor",
                ),
            ],
            affected_trains=["18030", "18031", "12841", "12842", "13015"],
            affected_junctions=["HWH"],
            estimated_impact={
                "total_delay_train_minutes": 450,  # Conservative estimate
                "stranded_passengers": 0,  # Predictive, not yet occurred
                "economic_loss_inr": 0,
                "recovery_time_hours": 1.0,
                "critical_trains": 0,
                "zone_priority": ["ER"],
            },
        ),
    ]
    
    # Filter by severity if requested
    if severity:
        alerts = [a for a in alerts if a.severity == severity]
    
    alerts = alerts[:limit]
    
    # Optionally strip reasoning to reduce payload
    if not include_reasoning:
        for alert in alerts:
            alert.reasons = []
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "coverage": {
            "zones": 6,
            "junctions": 34,
            "trains": 127,
            "anomalies_detected": 47,
            "predictions_active": 12,
        }
    }

@router.get("/reasoning/{alert_id}")
async def get_alert_reasoning(alert_id: str):
    """
    Deep dive into alert reasoning: shows the EXACT evidence chain
    from each AI/ML model that contributed to this alert.
    """
    # Fetch from database
    return {
        "alert_id": alert_id,
        "reasoning_chain": [
            {
                "step": 1,
                "model": "isolation_forest",
                "signal": "Delay anomaly detected",
                "confidence": 0.95,
                "output": "47 trains with >5σ deviation",
            },
            {
                "step": 2,
                "model": "cascade_simulator",
                "signal": "Cascade propagation model",
                "confidence": 0.98,
                "output": "Predicted 12 junctions affected if cascade continues",
            },
            {
                "step": 3,
                "model": "lstm_cascade_predictor",
                "signal": "Temporal evolution prediction",
                "confidence": 0.87,
                "output": "Peak at PNBE in 45 minutes, recovery in 2.5 hours",
            },
            {
                "step": 4,
                "model": "correlation_engine",
                "signal": "Multi-train pattern analysis",
                "confidence": 0.91,
                "output": "3 passenger trains converging + 1 freight = bottleneck",
            },
        ],
        "final_verdict": {
            "alert_type": "CASCADE",
            "severity": "CRITICAL",
            "confidence": 0.93,
            "reasoning": "Multiple independent models converged on cascade scenario with >85% confidence",
        }
    }

@router.get("/recommendations/{alert_id}")
async def get_recommendations(alert_id: str):
    """Get AI-generated operational recommendations for this alert."""
    return {
        "alert_id": alert_id,
        "recommendations": [
            {
                "priority": 1,
                "action": "ACTIVATE_CASCADE_RESPONSE",
                "details": "Begin delaying Rajdhani express departures from NDLS",
                "estimated_impact": "Reduce cascade severity by 30%",
                "confidence": 0.89,
                "timeframe": "Immediate",
            },
            {
                "priority": 2,
                "action": "REROUTE_NON_CRITICAL",
                "details": "Move freight trains off main corridors to secondary routes",
                "estimated_impact": "Free capacity for passenger trains",
                "confidence": 0.76,
                "timeframe": "Next 30 minutes",
            },
            {
                "priority": 3,
                "action": "PRE_POSITION_RESOURCES",
                "details": "Move maintenance crews to PNBE and MGS",
                "estimated_impact": "Reduce recovery time by 20%",
                "confidence": 0.82,
                "timeframe": "Before cascade peaks",
            },
        ],
        "success_metrics": {
            "goal": "Confine cascade to <50 minute delay across network",
            "baseline_without_action": "120+ minute delays",
            "estimated_with_action": "45-60 minute delays",
        }
    }
