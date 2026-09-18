"""Tests for data quality monitoring, real NTES connector, and DB-backed APIs."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.data.data_quality import DataQualityMonitor, QualityScore
from backend.data.ntes_live_real import NTESLiveConnector, TrainState
from backend.data.train_repository import TrainDataRepository
from backend.db.models import Base, Train, TrainTelemetry


def _session_factory(db_path: Path):
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


# ─────────────────────────────────────────────────────────────────────────────
# Data Quality Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_data_quality_monitor_accepts_valid_train():
    monitor = DataQualityMonitor()
    now = datetime.now(timezone.utc).isoformat()

    state = TrainState(
        train_id="12001",
        train_name="Bhopal Shatabdi",
        current_station="NDLS",
        current_lat=28.6,
        current_lon=77.2,
        actual_delay_minutes=15,
        speed_kmh=85.0,
        route="NDLS-BPL",
        timestamp=now,
        source_quality_score=0.85,
    )

    score = monitor.validate_train_state(state)
    assert score.is_valid
    assert score.overall_score >= 0.7
    assert len(score.issues) == 0


def test_data_quality_monitor_rejects_impossible_jump():
    from datetime import timedelta
    monitor = DataQualityMonitor(max_jump_km=50.0)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    later_iso = (now + timedelta(minutes=1)).isoformat()

    prev_state = TrainState(
        train_id="12001",
        train_name="Train A",
        current_station="NDLS",
        current_lat=28.6,
        current_lon=77.2,
        actual_delay_minutes=10,
        speed_kmh=80.0,
        route="NDLS-BPL",
        timestamp=now_iso,
    )

    later_state = TrainState(
        train_id="12001",
        train_name="Train A",
        current_station="BPL",
        current_lat=23.2,
        current_lon=75.9,
        actual_delay_minutes=15,
        speed_kmh=80.0,
        route="NDLS-BPL",
        timestamp=later_iso,
    )

    score = monitor.validate_train_state(later_state, prev_state)
    assert not score.is_valid
    assert any("Impossible jump" in issue for issue in score.issues)


def test_data_quality_monitor_flags_stale_data():
    monitor = DataQualityMonitor(max_age_hours=1.0)

    old_time = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)).isoformat()

    state = TrainState(
        train_id="12001",
        train_name="Train A",
        current_station="NDLS",
        current_lat=28.6,
        current_lon=77.2,
        actual_delay_minutes=10,
        speed_kmh=80.0,
        route="NDLS-BPL",
        timestamp=old_time,
    )

    score = monitor.validate_train_state(state)
    assert score.freshness_hours > 1.0
    assert any("stale" in issue.lower() for issue in score.issues)


def test_data_quality_monitor_detects_duplicates():
    monitor = DataQualityMonitor()
    now = datetime.now(timezone.utc).isoformat()

    state = TrainState(
        train_id="12001",
        train_name="Train A",
        current_station="NDLS",
        current_lat=28.6,
        current_lon=77.2,
        actual_delay_minutes=10,
        speed_kmh=80.0,
        route="NDLS-BPL",
        timestamp=now,
    )

    # First occurrence
    score1 = monitor.validate_train_state(state)
    assert not score1.is_duplicate

    # Second occurrence (same train, same time bucket)
    score2 = monitor.validate_train_state(state)
    assert score2.is_duplicate


# ─────────────────────────────────────────────────────────────────────────────
# Real NTES Connector Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ntes_live_connector_fetches_trains():
    connector = NTESLiveConnector()
    trains = await connector.fetch_live_trains()
    await connector.close()

    assert len(trains) > 0
    for train in trains:
        assert train.train_id
        assert train.train_name
        assert -90 <= train.current_lat <= 90
        assert -180 <= train.current_lon <= 180
        assert 0 <= train.source_quality_score <= 1


@pytest.mark.asyncio
async def test_ntes_live_connector_validate_train_state():
    connector = NTESLiveConnector()

    valid_state = TrainState(
        train_id="12001",
        train_name="Train A",
        current_station="NDLS",
        current_lat=28.6,
        current_lon=77.2,
        actual_delay_minutes=15,
        speed_kmh=80.0,
        route="NDLS-BPL",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    assert await connector.validate_train_state(valid_state)

    invalid_state = TrainState(
        train_id="",
        train_name="Bad Train",
        current_station="NDLS",
        current_lat=28.6,
        current_lon=77.2,
        actual_delay_minutes=15,
        speed_kmh=80.0,
        route="",
        timestamp="",
    )

    assert not await connector.validate_train_state(invalid_state)

    await connector.close()


# ─────────────────────────────────────────────────────────────────────────────
# End-to-End Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_repository_with_quality_scoring_integration(tmp_path: Path):
    """Test full pipeline: fetch → score → persist."""
    session_factory = _session_factory(tmp_path / "quality_integration.db")
    quality_monitor = DataQualityMonitor()
    repository = TrainDataRepository(session_factory=session_factory, quality_monitor=quality_monitor)

    now = datetime.now(timezone.utc).isoformat()
    states = [
        TrainState(
            train_id="12001",
            train_name="Valid Train",
            current_station="NDLS",
            current_lat=28.6,
            current_lon=77.2,
            actual_delay_minutes=15,
            speed_kmh=85.0,
            route="NDLS-BPL",
            timestamp=now,
            source_quality_score=0.85,
        ),
        TrainState(
            train_id="",  # Invalid
            train_name="Bad Train",
            current_station="HWH",
            current_lat=22.6,
            current_lon=88.3,
            actual_delay_minutes=20,
            speed_kmh=75.0,
            route="HWH-NDLS",
            timestamp=now,
        ),
        TrainState(
            train_id="12301",
            train_name="Another Train",
            current_station="BPL",
            current_lat=23.2,
            current_lon=75.9,
            actual_delay_minutes=600,  # Out of range
            speed_kmh=85.0,
            route="BPL-NDLS",
            timestamp=now,
            source_quality_score=0.70,
        ),
    ]

    result = repository.ingest_train_states(states, source="ntes_live")

    assert result["records_received"] == 3
    assert result["records_valid"] == 1
    assert result["records_invalid"] == 2
    assert result["records_persisted"] == 1

    with session_factory() as db:
        assert db.query(Train).count() == 1
        assert db.query(TrainTelemetry).count() == 1
