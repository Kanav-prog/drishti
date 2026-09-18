"""Tests for backend hardening: auth, sanitization, and migrations."""

from backend.api.schemas import BayesianInferRequest, sanitize_text
from backend.db.migrations import run_migrations
from backend.security.auth import hash_password, verify_password


def test_password_hash_and_verify_roundtrip():
    plain = "Str0ngPassw0rd!"
    hashed = hash_password(plain)

    assert hashed != plain
    assert "$" in hashed
    assert verify_password(plain, hashed)
    assert not verify_password("wrong-password", hashed)


def test_sanitize_text_removes_risky_chars():
    raw = " admin<script>alert(1)</script> "
    cleaned = sanitize_text(raw)

    assert "<" not in cleaned
    assert ">" not in cleaned
    assert "script" in cleaned.lower()


def test_bayesian_schema_validation_accepts_valid_payload():
    payload = {
        "delay_minutes": 35,
        "time_of_day": "day",
        "signal_cycle_time": 5.5,
        "maintenance_active": False,
        "centrality_rank": 72,
        "traffic_density": 0.66,
    }
    validated = BayesianInferRequest(**payload)

    assert validated.time_of_day == "DAY"
    assert validated.centrality_rank == 72


def test_migrations_runner_is_idempotent():
    # Should not raise even when called repeatedly.
    run_migrations()
    run_migrations()
    assert True
