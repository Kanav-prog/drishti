"""
Bayesian Network for Real-Time Risk Propagation using pgmpy

Models Indian Railways as a probabilistic graphical model.
Uses Exact Bayesian Inference (Variable Elimination) to answer: 
P(accident | current observations) = ?
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
from pgmpy.inference import VariableElimination

logger = logging.getLogger(__name__)


@dataclass
class BayesianPrediction:
    """Result of exact Bayesian inference"""
    p_accident: float  # Probability of accident (0-1)
    p_collision: float  # Component: collision risk
    p_derailment: float  # Component: derailment risk
    confidence: float  # Confidence interval (varies by observed evidence)
    time_to_accident_minutes: int  # Heuristic estimation of timeframe


class BayesianRiskNetwork:
    """Real-time Exact Bayesian inference for accident risk"""
    
    def __init__(self, causal_dag_builder):
        """
        Initialize Bayesian network inference.
        
        Args:
            causal_dag_builder: Instantiated CausalDAGBuilder with pgmpy model
        """
        self.causal_dag_builder = causal_dag_builder
        self.model = causal_dag_builder.get_pgmpy_model()
        
        # Use exact inference (Variable Elimination)
        self.inference = VariableElimination(self.model)
        self.update_count = 0
        
        logger.info(f"Initialized pgmpy VariableElimination Bayesian network inference")
    
    def update_belief(self, observations: Dict) -> BayesianPrediction:
        """
        Update beliefs given new evidence via Exact Inference.
        """
        self.update_count += 1
        
        try:
            # Convert observations to dictionary of known evidence (0 or 1)
            causal_state = self._observations_to_causal_state(observations)
            evidence = {k: (1 if v else 0) for k, v in causal_state.items()}
            
            # 1. Exact Inference: Query P(accident | evidence)
            result = self.inference.query(variables=['accident'], evidence=evidence, joint=False)
            
            # Extract probability that accident = 1 (True)
            p_accident = float(result['accident'].values[1])
            
            # Decompose into specific accident types (heuristics)
            p_collision = p_accident * 0.7  
            p_derailment = p_accident * 0.3  
            
            # Confidence based on amount of known evidence vs unknown
            confidence = self._compute_confidence(evidence)
            
            # Estimate time to accident
            time_to_accident = self._estimate_time_to_accident(observations)
            
            prediction = BayesianPrediction(
                p_accident=p_accident,
                p_collision=p_collision,
                p_derailment=p_derailment,
                confidence=confidence,
                time_to_accident_minutes=time_to_accident
            )
            
            logger.debug(f"Update #{self.update_count}: P(accident)={p_accident:.3f}, confidence={confidence:.2f}")
            
            return prediction
            
        except Exception as e:
            logger.error(f"Exact Bayesian update failed: {e}")
            return BayesianPrediction(0.001, 0.0007, 0.0003, 0.0, 0)
    
    def _observations_to_causal_state(self, obs: Dict) -> Dict:
        """
        Convert numerical observations to discrete causal evidence states.
        Only returns keys for which we have direct evidence!
        """
        state = {}
        
        if 'maintenance_active' in obs:
            state['maintenance_skip'] = obs['maintenance_active']
            
        if 'signal_cycle_time' in obs:
            state['signal_failure'] = obs.get('signal_cycle_time', 4.0) > 6.0
            
        if 'delay_minutes' in obs:
            state['delay_cascade'] = obs.get('delay_minutes', 0) > 30
            
        if 'centrality_rank' in obs:
            state['high_centrality_junction'] = obs.get('centrality_rank', 50) > 75
            
        if 'time_of_day' in obs:
            state['night_shift'] = obs.get('time_of_day', '') == 'NIGHT'
            
        # We explicitly DO NOT infer track_mismatch or train_bunching here.
        # We let the PGM mathematically infer their hidden probabilities based on the network structure!
        
        return state
    
    def _compute_confidence(self, evidence: Dict) -> float:
        """
        Confidence increases with the proportion of the graph we actually observe.
        """
        num_evidence = len(evidence)
        total_nodes = len(self.model.nodes()) - 1  # Exclude target
        return min(1.0, num_evidence / max(1, total_nodes))
    
    def _estimate_time_to_accident(self, obs: Dict) -> int:
        """Estimate minutes until potential accident."""
        time_to_accident = 120  
        delay = obs.get('delay_minutes', 0)
        traffic_density = obs.get('traffic_density', 0.0)
        
        if traffic_density > 0.8 and delay > 40:
            time_to_accident = 15
        elif traffic_density > 0.6 and delay > 30:
            time_to_accident = 30
        elif delay > 40:
            time_to_accident = 45
            
        return max(0, time_to_accident)
    
    def explain_prediction(self, prediction: BayesianPrediction, observations: Dict) -> Dict:
        """
        Create human-readable explanation for a prediction.
        Identifies mathematically which hidden factors are likely active.
        """
        state = self._observations_to_causal_state(observations)
        evidence = {k: (1 if v else 0) for k, v in state.items()}
        
        active_factors = [k for k, v in evidence.items() if v == 1]
        
        # Marginal inference on unobserved intermediate causes
        unobserved = [n for n in self.model.nodes() if n not in evidence and n != 'accident']
        inferred_hidden_dangers = []
        
        if unobserved:
            try:
                marginals = self.inference.query(variables=unobserved, evidence=evidence, joint=False)
                for node in unobserved:
                    # If the PGM thinks this hidden node has > 50% chance of being active
                    if marginals[node].values[1] > 0.50:
                        inferred_hidden_dangers.append(f"{node} ({(marginals[node].values[1]*100):.1f}%)")
            except Exception as e:
                logger.warning(f"Secondary inference failed: {e}")
        
        return {
            'risk_level': self._risk_level_text(prediction.p_accident),
            'p_accident': round(prediction.p_accident, 3),
            'confidence': round(prediction.confidence, 2),
            'time_to_accident_minutes': prediction.time_to_accident_minutes,
            'active_observed_factors': active_factors,
            'inferred_hidden_dangers': inferred_hidden_dangers,
        }
    
    def _risk_level_text(self, p_accident: float) -> str:
        """Text interpretation of risk"""
        if p_accident < 0.1:
            return "LOW"
        elif p_accident < 0.3:
            return "MEDIUM"
        elif p_accident < 0.6:
            return "HIGH"
        else:
            return "CRITICAL"


def main():
    """Development/testing of the true PGM Inference"""
    logging.basicConfig(level=logging.INFO)
    
    from backend.ml.causal_dag import CausalDAGBuilder
    dag_builder = CausalDAGBuilder()
    
    bayesian = BayesianRiskNetwork(dag_builder)
    
    print("\n=== True pgmpy Exact Inference ===")
    
    test_cases = [
        {
            "name": "Normal train operations",
            "obs": {
                'maintenance_active': False,
                'delay_minutes': 5,
                'signal_cycle_time': 4.0,
                'traffic_density': 0.3,
                'time_of_day': 'DAY',
                'centrality_rank': 40,
            }
        },
        {
            "name": "High delay, night shift",
            "obs": {
                'maintenance_active': False,
                'delay_minutes': 45,
                'signal_cycle_time': 4.5,
                'traffic_density': 0.8,
                'time_of_day': 'NIGHT',
                'centrality_rank': 80,
            }
        },
        {
            "name": "Balasore-like conditions",
            "obs": {
                'maintenance_active': True,
                'delay_minutes': 45,
                'signal_cycle_time': 7.5,
                'traffic_density': 0.9,
                'time_of_day': 'NIGHT',
                'centrality_rank': 99,
            }
        },
    ]
    
    for test in test_cases:
        print(f"\n--- {test['name']} ---")
        import time
        t0 = time.time()
        pred = bayesian.update_belief(test['obs'])
        t1 = time.time()
        
        explanation = bayesian.explain_prediction(pred, test['obs'])
        
        print(f"P(accident) = {pred.p_accident:.4f}")
        print(f"Risk level: {explanation['risk_level']}")
        print(f"Confidence (evidence ratio): {explanation['confidence']:.2f}")
        print(f"Observed issues: {explanation['active_observed_factors']}")
        print(f"Inferred hidden dangers: {explanation['inferred_hidden_dangers']}")
        print(f"Inference latency: {(t1-t0)*1000:.1f} ms")


if __name__ == "__main__":
    main()
