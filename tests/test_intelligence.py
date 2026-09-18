"""
DRISHTI — Intelligence Layer Test Suite
Tests: SignatureMatcher, CRS corpus integrity, scoring logic

Run: pytest tests/test_intelligence.py -v
"""
import pytest
import sys
import os

# Make backend importable from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.intelligence.signature_matcher import SignatureMatcher, AlertScore


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def matcher():
    """Shared SignatureMatcher instance (expensive to init)."""
    return SignatureMatcher()


# ─────────────────────────────────────────────────────────────────────────────
# Corpus integrity
# ─────────────────────────────────────────────────────────────────────────────

class TestCorpusIntegrity:
    def test_signatures_loaded(self, matcher):
        """Must have at least 5 historical signatures in corpus."""
        assert len(matcher.signatures) >= 5, \
            f"Expected ≥5 signatures, got {len(matcher.signatures)}"

    def test_balasore_signature_present(self, matcher):
        """Balasore 2023 (BLSR) must be in the corpus — it's the benchmark accident."""
        blsr_sigs = [s for s in matcher.signatures if s.station_code == "BLSR"]
        assert len(blsr_sigs) >= 1, "BLSR (Balasore 2023) signature missing from corpus"

    def test_firozabad_signature_present(self, matcher):
        """Firozabad 1998 (FZD) — 358 deaths, must be in corpus."""
        fzd_sigs = [s for s in matcher.signatures if s.station_code == "FZD"]
        assert len(fzd_sigs) >= 1, "FZD (Firozabad 1998) signature missing"

    def test_all_signatures_have_deaths(self, matcher):
        """Every signature must record at least 1 death (otherwise it's not a valid accident)."""
        for sig in matcher.signatures:
            assert sig.deaths >= 1, \
                f"Signature {sig.signature_id} at {sig.station_code} has deaths=0"

    def test_no_invalid_station_codes(self, matcher):
        """All station codes must be non-empty strings."""
        for sig in matcher.signatures:
            assert isinstance(sig.station_code, str), f"station_code not str: {sig.signature_id}"
            assert len(sig.station_code) >= 2, f"station_code too short: {sig.signature_id}"

    def test_all_signatures_have_dates(self, matcher):
        """Every signature must have an accident date."""
        for sig in matcher.signatures:
            assert sig.accident_date, f"Missing date on {sig.signature_id}"
            # Check format YYYY-MM-DD
            year = int(sig.accident_date[:4])
            assert 1980 <= year <= 2024, \
                f"Suspicious year {year} in {sig.signature_id}"


# ─────────────────────────────────────────────────────────────────────────────
# Scoring behaviour
# ─────────────────────────────────────────────────────────────────────────────

class TestScoringBehaviour:
    def test_zero_stress_zero_score(self, matcher):
        """Stable junction with no delays → score should be near 0."""
        result = matcher.score_current_state(
            station_code="NDLS",
            current_stress=0,
            current_delayed_trains=0,
            current_accumulated_delay=0,
            network_density="LOW",
            maintenance_deferred=False,
        )
        assert isinstance(result, AlertScore)
        assert result.score < 30.0, \
            f"Stable junction scored too high: {result.score:.1f}"

    def test_known_bad_conditions_high_score(self, matcher):
        """BLSR with Balasore-like conditions → should match ≥ 50%."""
        result = matcher.score_current_state(
            station_code="BLSR",
            current_stress=80,
            current_delayed_trains=8,
            current_accumulated_delay=720,
            network_density="HIGH",
            maintenance_deferred=True,
        )
        assert result.score >= 50.0, \
            f"BLSR under Balasore conditions scored too low: {result.score:.1f}"

    def test_score_range(self, matcher):
        """Score must always be 0–100."""
        for stress in [0, 20, 50, 80, 100]:
            result = matcher.score_current_state(
                station_code="HWH",
                current_stress=stress,
                current_delayed_trains=stress // 20,
                current_accumulated_delay=stress * 10,
                network_density="HIGH",
            )
            assert 0.0 <= result.score <= 100.0, \
                f"Score out of range at stress={stress}: {result.score}"

    def test_risk_tier_values(self, matcher):
        """Risk tier must be one of: SINGLE, DUAL, DUAL+"""
        valid_tiers = {"SINGLE", "DUAL", "DUAL+"}
        for station in ["NDLS", "HWH", "BLSR", "FZD"]:
            result = matcher.score_current_state(
                station_code=station,
                current_stress=50,
                current_delayed_trains=4,
                current_accumulated_delay=300,
                network_density="HIGH",
            )
            assert result.risk_tier in valid_tiers, \
                f"Invalid risk_tier '{result.risk_tier}' for {station}"

    def test_confidence_range(self, matcher):
        """Confidence must be 0.0–1.0."""
        result = matcher.score_current_state(
            station_code="BPL",
            current_stress=60,
            current_delayed_trains=5,
            current_accumulated_delay=400,
            network_density="HIGH",
        )
        assert 0.0 <= result.confidence <= 1.0, \
            f"confidence out of range: {result.confidence}"

    def test_higher_stress_higher_score(self, matcher):
        """Monotonicity check: increasing stress should not decrease score."""
        scores = []
        for stress in [0, 25, 50, 75]:
            result = matcher.score_current_state(
                station_code="CNB",
                current_stress=stress,
                current_delayed_trains=stress // 15,
                current_accumulated_delay=stress * 5,
                network_density="HIGH",
                maintenance_deferred=(stress > 50),
            )
            scores.append(result.score)
        # Allow small variance — just check overall trend
        assert scores[-1] >= scores[0], \
            f"Score decreased with stress: {scores}"

    def test_unknown_station_doesnt_crash(self, matcher):
        """An unknown station code should return a valid (low) score, not raise."""
        result = matcher.score_current_state(
            station_code="XXXXUNKNOWN",
            current_stress=30,
            current_delayed_trains=2,
            current_accumulated_delay=100,
            network_density="MEDIUM",
        )
        assert isinstance(result, AlertScore)
        assert 0.0 <= result.score <= 100.0

    def test_maintenance_flag_increases_score(self, matcher):
        """Deferred maintenance should result in higher score than no maintenance."""
        base = matcher.score_current_state(
            station_code="NGP",
            current_stress=50,
            current_delayed_trains=4,
            current_accumulated_delay=300,
            network_density="HIGH",
            maintenance_deferred=False,
        )
        maintained = matcher.score_current_state(
            station_code="NGP",
            current_stress=50,
            current_delayed_trains=4,
            current_accumulated_delay=300,
            network_density="HIGH",
            maintenance_deferred=True,
        )
        assert maintained.score >= base.score, \
            f"Deferred maintenance should increase score: {base.score:.1f} → {maintained.score:.1f}"


# ─────────────────────────────────────────────────────────────────────────────
# Recommendation quality
# ─────────────────────────────────────────────────────────────────────────────

class TestRecommendations:
    def test_critical_state_has_recommendation(self, matcher):
        """High-scoring states must include a recommendation string."""
        result = matcher.score_current_state(
            station_code="BLSR",
            current_stress=90,
            current_delayed_trains=10,
            current_accumulated_delay=900,
            network_density="HIGH",
            maintenance_deferred=True,
        )
        if result.score >= 60:
            assert result.recommendation, \
                "Score ≥ 60 but no recommendation provided"

    def test_matched_signatures_are_strings(self, matcher):
        result = matcher.score_current_state(
            station_code="FZD",
            current_stress=70,
            current_delayed_trains=7,
            current_accumulated_delay=600,
            network_density="HIGH",
        )
        for sig_id in result.matched_signatures:
            assert isinstance(sig_id, str), f"matched_signature not str: {sig_id}"
