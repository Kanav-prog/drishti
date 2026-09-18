"""
A/B Testing Framework
New model runs in shadow, compared vs old
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ABTestResult:
    """A/B test comparison"""
    test_id: str
    old_model_score: float
    new_model_score: float
    actual_outcome: Optional[bool]
    timestamp: str
    winner: str


class ABTestingEngine:
    """A/B testing for model deployments"""

    def __init__(self):
        self.results: List[ABTestResult] = []
        self.new_model_wins = 0
        self.old_model_wins = 0
        self.ties = 0

    def run_shadow_test(
        self,
        prediction_id: str,
        old_model_score: float,
        new_model_score: float,
        actual_outcome: Optional[bool] = None,
    ) -> ABTestResult:
        """Log both old + new model predictions"""
        timestamp = datetime.now(timezone.utc).isoformat()

        # Determine winner
        if actual_outcome is not None:
            old_error = abs(old_model_score - float(actual_outcome))
            new_error = abs(new_model_score - float(actual_outcome))

            if old_error < new_error:
                winner = "old"
                self.old_model_wins += 1
            elif new_error < old_error:
                winner = "new"
                self.new_model_wins += 1
            else:
                winner = "tie"
                self.ties += 1
        else:
            winner = "unknown"

        result = ABTestResult(
            test_id=prediction_id,
            old_model_score=old_model_score,
            new_model_score=new_model_score,
            actual_outcome=actual_outcome,
            timestamp=timestamp,
            winner=winner,
        )

        self.results.append(result)
        return result

    def get_test_stats(self) -> Dict:
        """Compute A/B test statistics"""
        total = self.new_model_wins + self.old_model_wins + self.ties

        return {
            "total_tests": total,
            "new_model_wins": self.new_model_wins,
            "old_model_wins": self.old_model_wins,
            "ties": self.ties,
            "new_model_win_rate": (
                self.new_model_wins / total if total > 0 else 0
            ),
            "recommendation": self._get_recommendation(),
        }

    def _get_recommendation(self) -> str:
        """Should we deploy new model?"""
        total = self.new_model_wins + self.old_model_wins

        if total < 30:
            return "Need more test data (30+ comparisons)"

        new_rate = self.new_model_wins / total if total > 0 else 0

        if new_rate > 0.65:
            return "✅ Deploy new model (wins >65%)"
        elif new_rate > 0.50:
            return "⚠️ Continue testing (marginal improvement)"
        else:
            return "❌ Keep old model (performs worse)"

    def clear_results(self):
        """Reset for next test cycle"""
        self.results = []
        self.new_model_wins = 0
        self.old_model_wins = 0
        self.ties = 0


# Global A/B tester
ab_tester = ABTestingEngine()
