"""
Causal DAG Discovery & Inference using pgmpy

Build directed acyclic graphs for Indian Railways operations.
Provides the structural model and Conditional Probability Tables (CPTs)
for true exact Bayesian inference.
"""

from typing import Dict, List, Tuple
import logging
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete import TabularCPD
import itertools

logger = logging.getLogger(__name__)


class CausalDAGBuilder:
    """Build causal DAGs and true Probabilistic Graphical Models using pgmpy"""
    
    def __init__(self, accident_corpus: List = None):
        """
        Initialize with parsed CRS accidents (corpus not strictly needed for manual DAG).
        """
        self.corpus = accident_corpus
        self.model = None
        self.nodes = [
            "maintenance_skip", 
            "signal_failure", 
            "track_mismatch", 
            "delay_cascade", 
            "train_bunching", 
            "high_centrality_junction", 
            "night_shift", 
            "accident"
        ]
        
        logger.info("Initialized pgmpy CausalDAGBuilder")
    
    def build_manual_dag(self) -> DiscreteBayesianNetwork:
        """
        Construct a true causal Bayesian Network based on domain expertise + accident analysis.
        This defines the DAG structure and the exact CPDS.
        """
        # Node states: 0 = False, 1 = True
        
        # 1. Define Edges structure
        edges = [
            ("maintenance_skip", "signal_failure"),
            ("maintenance_skip", "delay_cascade"),
            ("signal_failure", "track_mismatch"),
            ("track_mismatch", "train_bunching"),
            ("delay_cascade", "train_bunching"),
            ("high_centrality_junction", "train_bunching"),
            ("night_shift", "train_bunching"),
            ("night_shift", "signal_failure"),
            ("train_bunching", "accident"),
            ("track_mismatch", "accident")
        ]
        
        self.model = DiscreteBayesianNetwork(edges)
        
        # 2. Define Priors (base probabilities for root nodes)
        
        # P(maintenance_skip) = 5%
        cpd_maint = TabularCPD(variable='maintenance_skip', variable_card=2, values=[[0.95], [0.05]])
        
        # P(night_shift) = 30%
        cpd_night = TabularCPD(variable='night_shift', variable_card=2, values=[[0.70], [0.30]])
        
        # P(high_centrality_junction) = 10%
        cpd_cent = TabularCPD(variable='high_centrality_junction', variable_card=2, values=[[0.90], [0.10]])
        
        # 3. Define conditional probabilities
        
        # P(signal_failure | maintenance_skip, night_shift)
        # evidence order: [maintenance_skip=0/1, night_shift=0/1]
        # values[1] (prob of failure=1) = [m=0/n=0, m=0/n=1, m=1/n=0, m=1/n=1]
        sf_1 = [0.001, 0.005, 0.15, 0.25]
        sf_0 = [1 - x for x in sf_1]
        cpd_sig = TabularCPD(
            variable='signal_failure', variable_card=2,
            values=[sf_0, sf_1],
            evidence=['maintenance_skip', 'night_shift'],
            evidence_card=[2, 2]
        )
        
        # P(delay_cascade | maintenance_skip)
        # values[1] = [m=0, m=1]
        dc_1 = [0.05, 0.35]
        dc_0 = [1 - x for x in dc_1]
        cpd_delay = TabularCPD(
            variable='delay_cascade', variable_card=2,
            values=[dc_0, dc_1],
            evidence=['maintenance_skip'],
            evidence_card=[2]
        )
        
        # P(track_mismatch | signal_failure)
        # values[1] = [s=0, s=1]
        tm_1 = [0.0001, 0.20]
        tm_0 = [1 - x for x in tm_1]
        cpd_track = TabularCPD(
            variable='track_mismatch', variable_card=2,
            values=[tm_0, tm_1],
            evidence=['signal_failure'],
            evidence_card=[2]
        )
        
        # P(train_bunching | delay_cascade, track_mismatch, high_centrality_junction, night_shift)
        # Construct dynamically via noisy-OR-like logic
        parents = ['delay_cascade', 'track_mismatch', 'high_centrality_junction', 'night_shift']
        tb_1_probs = []
        for combo in itertools.product([0, 1], repeat=4):
            delay, track, cent, night = combo
            p = 0.01  # base bunching chance
            if delay: p += 0.30
            if track: p += 0.40
            if cent:  p += 0.15
            if night: p += 0.05
            p = min(0.95, p) # Cap
            tb_1_probs.append(p)
            
        tb_0_probs = [1 - p for p in tb_1_probs]
        cpd_bunching = TabularCPD(
            variable='train_bunching', variable_card=2,
            values=[tb_0_probs, tb_1_probs],
            evidence=parents,
            evidence_card=[2, 2, 2, 2]
        )
        
        # P(accident | train_bunching, track_mismatch)
        # values[1] = [b=0/t=0, b=0/t=1, b=1/t=0, b=1/t=1]
        acc_1 = [0.0001, 0.05, 0.02, 0.85]  # Highest risk: track mismatch AND bunching (e.g. Balasore)
        acc_0 = [1 - x for x in acc_1]
        cpd_acc = TabularCPD(
            variable='accident', variable_card=2,
            values=[acc_0, acc_1],
            evidence=['train_bunching', 'track_mismatch'],
            evidence_card=[2, 2]
        )
        
        # Add all CPDs to the model
        self.model.add_cpds(cpd_maint, cpd_night, cpd_cent, cpd_sig, cpd_delay, cpd_track, cpd_bunching, cpd_acc)
        
        return self.model
    
    def validate_dag(self) -> bool:
        """Validate Bayesian Network mathematically"""
        if self.model is None:
            self.build_manual_dag()
        try:
            is_valid = self.model.check_model()
            logger.info("DAG validation passed")
            return is_valid
        except Exception as e:
            logger.error(f"DAG validation failed: {e}")
            return False

    def get_pgmpy_model(self) -> DiscreteBayesianNetwork:
        if self.model is None:
            self.build_manual_dag()
        return self.model

    def estimate_p_accident_given_state(self, state: Dict) -> float:
        from pgmpy.inference import VariableElimination
        infer = VariableElimination(self.get_pgmpy_model())
        evidence = {}
        for k, v in state.items():
            if k in self.model.nodes():
                evidence[k] = 1 if v else 0
        try:
            res = infer.query(['accident'], evidence=evidence, joint=False)
            return float(res['accident'].values[1])
        except:
            return 0.001

def main():
    """Development/testing to view CPDs"""
    logging.basicConfig(level=logging.INFO)
    builder = CausalDAGBuilder()
    model = builder.build_manual_dag()
    builder.validate_dag()
    print("\nModel constructed successfully.")
    print(f"Nodes: {model.nodes()}")
    print(f"Edges: {model.edges()}")

if __name__ == "__main__":
    main()
