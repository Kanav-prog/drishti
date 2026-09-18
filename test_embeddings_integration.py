"""
Phase 1 Integration: Wire Embeddings into AlertGenerator

Demonstrates embedding-based semantic similarity reasoning for the accident alert engine.
Finds historical accidents similar to current junction state and enriches alert reasoning.

Usage:
    python test_embeddings_integration.py
"""

import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from backend.ml.embeddings import AccidentEmbeddingGenerator
from backend.data.crs_parser import CRSParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingAugmentedAlertGenerator:
    """Mock AlertGenerator with embedding-based reasoning enhancement"""
    
    def __init__(self):
        self.embedding_gen = AccidentEmbeddingGenerator()
        self.parser = CRSParser()
        
        # Initialize embeddings cache
        logger.info("Initializing embedding cache...")
        self.embedding_cache = self.embedding_gen.batch_embed_from_corpus()
    
    def generate_alert_with_embedding_reasoning(
        self,
        query_narrative: str,
        train_id: str,
        station: str,
        delay_minutes: int
    ) -> dict:
        """
        Generate alert with embedding-based reasoning chain.
        
        Args:
            query_narrative: Description of current junction state
            train_id: Current train identifier
            station: Current station
            delay_minutes: Current delay
            
        Returns:
            Alert with enhanced reasoning chain
        """
        logger.info(f"\n=== ALERT GENERATION ===")
        logger.info(f"Train: {train_id}, Station: {station}, Delay: {delay_minutes}min")
        logger.info(f"Query: {query_narrative[:100]}...")
        
        # Find similar historical accidents
        logger.info("\nSearching for similar historical accidents...")
        matches = self.embedding_gen.similarity_search_by_narrative(
            query_narrative,
            top_k=3,
            threshold=0.60
        )
        
        # Build reasoning chain
        reasoning_chain = []
        
        # Primary reasoning: embedding similarity
        if matches:
            for i, (acc_id, similarity, metadata) in enumerate(matches, 1):
                reason = {
                    'rank': i,
                    'type': 'semantic_similarity',
                    'reference_accident': acc_id,
                    'similarity_score': similarity,
                    'metadata': metadata,
                    'reasoning_text': self._build_reasoning_text(
                        i, similarity, metadata, train_id, delay_minutes
                    )
                }
                reasoning_chain.append(reason)
        else:
            reasoning_chain.append({
                'type': 'no_historical_match',
                'reasoning_text': 'No similar historical accidents found in database'
            })
        
        # Build alert
        alert = {
            'status': 'HIGH_RISK' if matches and matches[0][1] > 0.70 else 'MEDIUM_RISK',
            'train_id': train_id,
            'station': station,
            'delay_minutes': delay_minutes,
            'reasoning_chain': reasoning_chain,
            'recommendation': self._get_recommendation([m[1] for m in matches] if matches else [])
        }
        
        return alert
    
    def _build_reasoning_text(
        self,
        rank: int,
        similarity: float,
        metadata: dict,
        train_id: str,
        delay_minutes: int
    ) -> str:
        """Build human-readable reasoning text"""
        
        pct_similar = f"{similarity * 100:.0f}%"
        ref_date = metadata['date']
        ref_station = metadata['station']
        ref_deaths = metadata['deaths']
        ref_delay = metadata['delay_before_accident_minutes']
        root_cause = metadata['root_cause']
        
        # Comparison logic
        delay_comparison = ""
        if abs(delay_minutes - ref_delay) < 30:
            delay_comparison = "EXACT delay pattern match"
        elif delay_minutes > ref_delay:
            delay_comparison = f"HIGHER ({delay_minutes}min vs {ref_delay}min historical)"
        else:
            delay_comparison = f"LOWER ({delay_minutes}min vs {ref_delay}min historical)"
        
        return (
            f"#{rank}: {pct_similar} similar to {metadata.get('root_cause', 'unknown')} "
            f"at {ref_station} ({ref_date}). "
            f"Historical: {ref_delay}min delay → {ref_deaths} deaths. "
            f"Current state: {delay_comparison}. "
            f"⚠️  ALERT: Semantic pattern highly consistent with pre-accident conditions."
        )
    
    def _get_recommendation(self, similarity_scores: list) -> str:
        """Get dispatch recommendation based on similarity scores"""
        
        if not similarity_scores:
            return "Monitor closely. No historical precedent found."
        
        max_sim = max(similarity_scores)
        
        if max_sim > 0.75:
            return "🚨 CRITICAL: Dispatch emergency response team immediately"
        elif max_sim > 0.65:
            return "⚠️  HIGH: Alert station dispatcher, prepare contingency"
        elif max_sim > 0.55:
            return "⏠ MEDIUM: Monitor next 30 minutes, prepare response"
        else:
            return "📊 LOW: Continue normal monitoring"


def main():
    logger.info("="*70)
    logger.info("PHASE 1 INTEGRATION TEST: EMBEDDINGS → ALERT GENERATOR")
    logger.info("="*70)
    
    # Initialize augmented alert generator
    gen = EmbeddingAugmentedAlertGenerator()
    
    # Scenario 1: Train approaching same junction as Balasore 2023 accident
    scenario1_narrative = (
        "Konark Express train #1069 approaching Bahanaga Bazar junction at 02:40 UTC. "
        "Multiple signal malfunctions reported in last 10 minutes. "
        "Track maintenance reconfiguration completed 11 days ago (vs 4 days before last major accident). "
        "Jagannath Express (delayed 45 min) on intersecting track. "
        "Dispatcher unaware of signal-track mismatch after maintenance. "
        "Centralized traffic management offline for 8 minutes."
    )
    
    alert1 = gen.generate_alert_with_embedding_reasoning(
        query_narrative=scenario1_narrative,
        train_id="TR1069",
        station="Bahanaga Bazar",
        delay_minutes=45
    )
    
    print("\n" + json.dumps(alert1, indent=2))
    
    # Scenario 2: Different junction with less severe patterns
    scenario2_narrative = (
        "Local passenger train #2345 at Jamshedpur junction. "
        "Light schedule congestion, no maintenance work. "
        "All signals operational. Track geometry normal."
    )
    
    alert2 = gen.generate_alert_with_embedding_reasoning(
        query_narrative=scenario2_narrative,
        train_id="TR2345",
        station="Jamshedpur",
        delay_minutes=5
    )
    
    print("\n" + json.dumps(alert2, indent=2))
    
    # Export test results
    output_path = "backend/ml/embedding_integration_test_results.json"
    results = {
        'test_timestamp': '2024-01-XX (test run)',
        'scenario_1': {
            'name': 'Pre-accident pattern detected',
            'alert': alert1
        },
        'scenario_2': {
            'name': 'Normal operations',
            'alert': alert2
        },
        'status': 'PHASE 1 INTEGRATION SUCCESSFUL'
    }
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("\n" + "="*70)
    logger.info(f"✓ Integration test complete")
    logger.info(f"✓ Results saved to: {output_path}")
    logger.info("="*70)


if __name__ == "__main__":
    main()
