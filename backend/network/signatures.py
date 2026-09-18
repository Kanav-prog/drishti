"""
Pre-Accident Signature Matching
Purpose: Extract and match 48-72 hour patterns before major accidents
Data: From CRS parser, patterns are compared against live stream data
Strategy: When live data matches historical pre-accident patterns + high centrality = ELEVATED RISK

Author: DRISHTI Research - Phase 5.C Network Science
Date: March 31, 2026
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PatternSignature:
    """Fingerprint of conditions 48-72 hours before major accident"""
    signature_id: str
    time_of_day: str
    section_type: str
    weather: str
    
    # Delay/congestion metrics (KEY indicators)
    trains_delayed_count: int
    accumulated_delay_minutes: int
    avg_delay_per_train_minutes: float
    
    # Systemic stress
    network_density_level: str  # LOW, MEDIUM, HIGH
    
    # What happened (for post-analysis)
    accident_severity: int  # deaths
    primary_cause: str
    confidence_score: float = 0.0  # 0-1, how well this pattern predicts accidents


@dataclass
class LiveStreamData:
    """Current network state for pattern matching"""
    timestamp: datetime
    section_code: str
    section_type: str
    time_of_day: str
    weather: str
    trains_delayed: int
    total_delay_accumulated_minutes: int
    train_density: int  # trains per hour on this section
    avg_train_delay_minutes: float
    recent_signalling_events: int  # signal issues in last 1 hour


@dataclass
class SignatureMatch:
    """Result of matching live data against historical pattern"""
    pattern_id: str
    match_score: float  # 0-1, higher = more similar to accident precursor
    matching_indicators: List[str]
    non_matching_indicators: List[str]
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    reasoning: str
    historical_severity: int  # deaths in matching historical pattern
    probability_of_major_accident: float  # Bayesian estimate


class PreAccidentSignatureLibrary:
    """Manage collection of pre-accident patterns"""
    
    def __init__(self):
        self.patterns: Dict[str, PatternSignature] = {}
        self.patterns_by_section: Dict[str, List[PatternSignature]] = defaultdict(list)
        self.patterns_by_cause: Dict[str, List[PatternSignature]] = defaultdict(list)
        self.high_severity_patterns: List[PatternSignature] = []
        
        logger.info("Pre-accident signature library initialized")
    
    def add_pattern(self, pattern: PatternSignature):
        """Add extracted historical pattern to library"""
        self.patterns[pattern.signature_id] = pattern
        self.patterns_by_section[pattern.section_type].append(pattern)
        self.patterns_by_cause[pattern.primary_cause].append(pattern)
        
        if pattern.accident_severity > 100:  # Catastrophic
            self.high_severity_patterns.append(pattern)
        
        logger.debug(f"Added pattern {pattern.signature_id}: {pattern.primary_cause}")
    
    def build_from_crs_data(self, crs_accidents: List[Dict]):
        """Build library from CRS accident records"""
        for i, accident in enumerate(crs_accidents):
            pattern = PatternSignature(
                signature_id=f"PAT_{accident['location_code']}_{accident['date'].replace('-','')}",
                time_of_day=accident.get("time_of_day", "Unknown"),
                section_type=accident.get("section_type", "Unknown"),
                weather=accident.get("weather", "Unknown"),
                trains_delayed_count=accident.get("pre_accident_delay_trains", 0),
                accumulated_delay_minutes=accident.get("pre_accident_delays_minutes", 0),
                avg_delay_per_train_minutes=(
                    accident.get("pre_accident_delays_minutes", 0) / 
                    max(accident.get("pre_accident_delay_trains", 1), 1)
                ),
                network_density_level="HIGH" if accident.get("pre_accident_delay_trains", 0) > 5 else "MEDIUM",
                accident_severity=accident.get("deaths", 0),
                primary_cause=accident.get("primary_cause", "Unknown"),
                confidence_score=0.7 if accident.get("deaths", 0) > 100 else 0.5  # Higher for catastrophic
            )
            self.add_pattern(pattern)
    
    def get_patterns_for_section(self, section_type: str) -> List[PatternSignature]:
        """Get patterns specific to this section type (e.g., 'Double-track')"""
        return self.patterns_by_section.get(section_type, [])
    
    def get_catastrophic_patterns(self) -> List[PatternSignature]:
        """Get only patterns that led to 100+ deaths (high severity)"""
        return self.high_severity_patterns


class SignatureMatchingEngine:
    """Match live data against historical pre-accident patterns"""
    
    def __init__(self, pattern_library: PreAccidentSignatureLibrary):
        self.library = pattern_library
        self.match_weights = {
            "time_of_day": 0.15,
            "section_type": 0.20,
            "weather": 0.10,
            "trains_delayed": 0.20,
            "accumulated_delay": 0.15,
            "density": 0.20
        }
        logger.info("Signature matching engine initialized")
    
    def match_live_data(
        self, 
        live_data: LiveStreamData, 
        section_type: str,
        centrality_score: float = 0.0
    ) -> List[SignatureMatch]:
        """
        Match live network state against historical patterns
        
        Returns: Ranked list of matching historical patterns (most similar first)
        """
        # Get patterns for this section type
        candidate_patterns = self.library.get_patterns_for_section(section_type)
        if not candidate_patterns:
            return []  # No historical data for this section
        
        matches = []
        for pattern in candidate_patterns:
            match = self._compute_match(live_data, pattern, centrality_score)
            if match.match_score > 0.3:  # Only significant matches
                matches.append(match)
        
        # Sort by match score (descending)
        matches.sort(key=lambda m: m.match_score, reverse=True)
        
        return matches
    
    def _compute_match(
        self, 
        live: LiveStreamData, 
        pattern: PatternSignature,
        centrality_score: float
    ) -> SignatureMatch:
        """Compute similarity between live data and historical pattern"""
        
        matching_indicators = []
        non_matching_indicators = []
        score_components = {}
        
        # 1. TIME OF DAY (15% weight)
        time_match = 1.0 if live.time_of_day == pattern.time_of_day else 0.3
        score_components["time_of_day"] = time_match * self.match_weights["time_of_day"]
        (matching_indicators if time_match > 0.5 else non_matching_indicators).append(
            f"Time: {live.time_of_day}"
        )
        
        # 2. SECTION TYPE (20% weight)
        section_match = 1.0 if live.section_type == pattern.section_type else 0.2
        score_components["section_type"] = section_match * self.match_weights["section_type"]
        matching_indicators.append(f"Section: {live.section_type}")
        
        # 3. WEATHER (10% weight) 
        weather_match = 1.0 if live.weather == pattern.weather else 0.4
        score_components["weather"] = weather_match * self.match_weights["weather"]
        (matching_indicators if weather_match > 0.5 else non_matching_indicators).append(
            f"Weather: {live.weather}"
        )
        
        # 4. TRAINS DELAYED (20% weight) - KEY INDICATOR
        delayed_diff = abs(live.trains_delayed - pattern.trains_delayed_count) / max(
            live.trains_delayed, pattern.trains_delayed_count, 1
        )
        trains_match = max(0, 1.0 - delayed_diff)
        score_components["trains_delayed"] = trains_match * self.match_weights["trains_delayed"]
        matching_indicators.append(
            f"Trains delayed: {live.trains_delayed} (pattern: {pattern.trains_delayed_count})"
        )
        
        # 5. ACCUMULATED DELAY (15% weight) - KEY INDICATOR
        delay_diff = abs(
            live.total_delay_accumulated_minutes - pattern.accumulated_delay_minutes
        ) / max(live.total_delay_accumulated_minutes, pattern.accumulated_delay_minutes, 1)
        delay_match = max(0, 1.0 - delay_diff)
        score_components["accumulated_delay"] = delay_match * self.match_weights["accumulated_delay"]
        matching_indicators.append(
            f"Accumulated delay: {live.total_delay_accumulated_minutes}m (pattern: {pattern.accumulated_delay_minutes}m)"
        )
        
        # 6. NETWORK DENSITY (20% weight)
        density_ratio = live.train_density / 10.0  # Normalize to [0,1]
        density_ratio = min(density_ratio, 1.0)
        score_components["density"] = density_ratio * self.match_weights["density"]
        
        density_level = (
            "HIGH" if live.train_density > 15 else 
            "MEDIUM" if live.train_density > 8 else "LOW"
        )
        matching_indicators.append(f"Network density: {density_level}")
        
        # COMPOSITE SCORE (0-1)
        composite_score = sum(score_components.values())
        
        # CENTRALITY BOOST: If this location is high-centrality + matches pattern = higher risk
        centrality_boost = centrality_score * 0.3 if centrality_score > 0.6 else 0
        final_score = min(composite_score + centrality_boost, 1.0)
        
        # RISK ASSESSMENT
        risk_level = self._assess_risk(final_score, pattern.accident_severity)
        
        # BAYESIAN PROBABILITY
        prob = self._estimate_accident_probability(
            final_score, pattern.confidence_score, pattern.accident_severity
        )
        
        reasoning = (
            f"Pattern match score: {final_score:.2f}. "
            f"Historical pattern: {pattern.primary_cause} → {pattern.accident_severity} deaths. "
            f"Current network: {len(matching_indicators)} matching indicators."
        )
        
        return SignatureMatch(
            pattern_id=pattern.signature_id,
            match_score=final_score,
            matching_indicators=matching_indicators,
            non_matching_indicators=non_matching_indicators,
            risk_level=risk_level,
            reasoning=reasoning,
            historical_severity=pattern.accident_severity,
            probability_of_major_accident=prob
        )
    
    def _assess_risk(self, match_score: float, historical_severity: int) -> str:
        """Convert match score to risk level"""
        if match_score >= 0.8 and historical_severity > 100:
            return "CRITICAL"
        elif match_score >= 0.7:
            return "HIGH"
        elif match_score >= 0.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _estimate_accident_probability(
        self, 
        match_score: float, 
        pattern_confidence: float,
        historical_severity: int
    ) -> float:
        """
        Bayesian-style probability estimate
        P(accident | observed_state) ∝ match_score × pattern_confidence × severity_weight
        """
        severity_weight = 1.0 if historical_severity > 100 else 0.6
        return min(match_score * pattern_confidence * severity_weight, 1.0)


class DualEvidenceRiskScorer:
    """
    Combine Network Science Evidence + ML Evidence
    
    NETWORK EVIDENCE: High centrality + pre-accident patterns = structural risk
    ML EVIDENCE: Ensemble anomaly detection = behavioral risk
    """
    
    @staticmethod
    def compute_dual_risk(
        ml_risk_score: float,  # From ensemble (0-1)
        centrality_score: float,  # From graph (0-1)
        signature_match: Optional[SignatureMatch] = None,
        signatures_matched_count: int = 0
    ) -> Dict:
        """
        Combine independent evidence streams
        
        ML + Network + Signature = DUAL+ evidence
        ML + Network = DUAL evidence
        ML alone = SINGLE evidence
        """
        
        network_risk = centrality_score  # High centrality = structural danger
        signature_risk = (
            signature_match.match_score if signature_match else 0.0
        )
        
        # DUAL EVIDENCE: Both ML and Network Science agree
        if ml_risk_score > 0.6 and network_risk > 0.6:
            combined_score = (ml_risk_score + network_risk) / 2.0  # Equal weight
            evidence_type = "DUAL"
        else:
            # Single stream or low-risk: take max
            combined_score = max(ml_risk_score, network_risk)
            evidence_type = "SINGLE"
        
        # SIGNATURE BOOST: If we've matched historical pre-accident patterns
        if signatures_matched_count >= 2:
            combined_score = min(combined_score * 1.3, 1.0)  # Boost to 1.3x
            evidence_type = "DUAL+"
        
        return {
            "combined_risk_score": min(combined_score, 1.0),
            "evidence_type": evidence_type,  # SINGLE, DUAL, DUAL+
            "ml_evidence": ml_risk_score,
            "network_evidence": network_risk,
            "signature_evidence": signature_risk,
            "signatures_matched": signatures_matched_count,
            "confidence": 0.95 if evidence_type == "DUAL+" else (
                0.85 if evidence_type == "DUAL" else 0.65
            ),
            "reasoning": f"{evidence_type}-evidence alert. "
                        f"ML risk: {ml_risk_score:.2f}, "
                        f"Network centrality: {network_risk:.2f}, "
                        f"Signature matches: {signatures_matched_count}"
        }
