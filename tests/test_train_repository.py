from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.data.ntes_live import TrainState
from backend.data.train_repository import TrainDataRepository
from backend.db.models import Base, DataIngestionRun, Station, Train, TrainTelemetry


def _session_factory(db_path: Path):
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_ingest_train_states_persists_train_station_and_telemetry(tmp_path: Path):
    session_factory = _session_factory(tmp_path / "tracking.db")
    repository = TrainDataRepository(session_factory=session_factory)

    now = datetime.now(timezone.utc).isoformat()
    states = [
        TrainState(
            train_id="12001",
            train_name="Bhopal Shatabdi",
            current_station="NDLS",
            current_lat=28.6431,
            current_lon=77.2197,
            actual_delay_minutes=12,
            speed_kmh=84.5,
            route="NDLS-BPL",
            timestamp=now,
        ),
        TrainState(
            train_id="12301",
            train_name="Howrah Rajdhani",
            current_station="HWH",
            current_lat=22.5958,
            current_lon=88.3017,
            actual_delay_minutes=25,
            speed_kmh=77.3,
            route="HWH-NDLS",
            timestamp=now,
        ),
    ]

    result = repository.ingest_train_states(states, source="ntes_live")

    assert result["records_received"] == 2
    assert result["records_valid"] == 2
    assert result["records_invalid"] == 0
    assert result["records_persisted"] == 2

    with session_factory() as db:
        assert db.query(Station).count() == 2
        assert db.query(Train).count() == 2
        assert db.query(TrainTelemetry).count() == 2

        run = db.query(DataIngestionRun).order_by(DataIngestionRun.id.desc()).first()
        assert run is not None
        assert run.status == "success"
        assert run.records_persisted == 2


def test_ingest_train_states_rejects_invalid_records(tmp_path: Path):
    session_factory = _session_factory(tmp_path / "tracking_invalid.db")
    repository = TrainDataRepository(session_factory=session_factory)

    states = [
        TrainState(
            train_id="",
            train_name="Bad Train",
            current_station="NDLS",
            current_lat=28.0,
            current_lon=77.0,
            actual_delay_minutes=15,
            speed_kmh=70.0,
            route="NDLS-BPL",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        TrainState(
            train_id="12002",
            train_name="Valid Train",
            current_station="BPL",
            current_lat=23.1,
            current_lon=77.2,
            actual_delay_minutes=8,
            speed_kmh=90.0,
            route="BPL-NDLS",
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
    ]

    result = repository.ingest_train_states(states, source="ntes_live")

    assert result["records_received"] == 2
    assert result["records_valid"] == 1
    assert result["records_invalid"] == 1
    assert result["records_persisted"] == 1

    with session_factory() as db:
        assert db.query(TrainTelemetry).count() == 1
