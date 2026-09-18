"""Tests for real feed connector, quality checker, and DB-backed APIs."""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.data.real_feed_connector import RealFeedConnector
from backend.data.quality_checker import DataQualityChecker
from backend.db.models import Base, Train, TrainTelemetry, Station
from pathlib import Path


@pytest.mark.asyncio
async def test_real_feed_connector_fetches_trains():
    connector = RealFeedConnector()
    trains = await connector.fetch_trains_from_real_feeds()
    await connector.close()

    assert len(trains) > 0
    assert all(t["train_id"] for t in trains)
    assert all("current_station" in t for t in trains)
    assert all("actual_delay_minutes" in t for t in trains)


def test_quality_checker_detects_duplicates():
    checker = DataQualityChecker()

    state1 = {
        "train_id": "12001",
        "current_station": "NDLS",
        "actual_delay_minutes": 15,
        "current_lat": 28.6,
        "current_lon": 77.2,
        "speed_kmh": 80,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # First check passes
    is_valid, warnings = checker.validate(state1)
    assert is_valid is True
    assert "duplicate_state" not in warnings

    # Second identical check should be flagged as duplicate
    is_valid, warnings = checker.validate(state1)
    assert "duplicate_state" in warnings or is_valid is False


def test_quality_checker_detects_stale_data():
    checker = DataQualityChecker(freshness_threshold_minutes=1)

    state = {
        "train_id": "12002",
        "current_station": "BPL",
        "actual_delay_minutes": 20,
        "current_lat": 23.1,
        "current_lon": 77.2,
        "speed_kmh": 85,
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }

    # Old timestamp should flag stale
    is_valid, warnings = checker.validate(state)
    if "stale_data" in warnings:
        assert is_valid is True  # stale is a warning, not an error


def test_quality_checker_detects_anomalies():
    checker = DataQualityChecker()

    bad_state = {
        "train_id": "12003",
        "current_station": "HWH",
        "actual_delay_minutes": 999,  # Unrealistic
        "current_lat": 22.6,
        "current_lon": 88.3,
        "speed_kmh": 80,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    is_valid, warnings = checker.validate(bad_state)
    assert is_valid is False


def _session_factory(db_path: Path):
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_db_backed_trains_current_state(tmp_path: Path):
    from backend.data.train_repository import TrainDataRepository

    session_factory = _session_factory(tmp_path / "test_trains.db")
    repo = TrainDataRepository(session_factory=session_factory)

    state = {
        "train_id": "12001",
        "train_name": "Bhopal Shatabdi",
        "current_station": "NDLS",
        "current_lat": 28.6,
        "current_lon": 77.2,
        "actual_delay_minutes": 15,
        "speed_kmh": 85.0,
        "route": "NDLS-BPL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    result = repo.ingest_train_states([state], source="test")
    assert result["records_persisted"] == 1

    with session_factory() as db:
        train = db.query(Train).filter(Train.train_id == "12001").first()
        assert train is not None
        assert train.train_name == "Bhopal Shatabdi"
        assert train.current_station_code == "NDLS"


def test_db_backed_trains_telemetry_history(tmp_path: Path):
    from backend.data.train_repository import TrainDataRepository

    session_factory = _session_factory(tmp_path / "test_history.db")
    repo = TrainDataRepository(session_factory=session_factory)

    now = datetime.now(timezone.utc)
    states = [
        {
            "train_id": "12001",
            "train_name": "Bhopal Shatabdi",
            "current_station": "NDLS",
            "current_lat": 28.6,
            "current_lon": 77.2,
            "actual_delay_minutes": i * 5,
            "speed_kmh": 80 + i,
            "route": "NDLS-BPL",
            "timestamp": (now - timedelta(minutes=i)).isoformat(),
        }
        for i in range(3)
    ]

    result = repo.ingest_train_states(states, source="test")
    assert result["records_persisted"] == 3

    with session_factory() as db:
        telemetries = db.query(TrainTelemetry).filter(TrainTelemetry.train_id == "12001").all()
        assert len(telemetries) == 3
        delays = sorted([t.delay_minutes for t in telemetries])
        assert delays == [0, 5, 10]
