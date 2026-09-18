"""Tests for DB-backed data APIs."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.server import app
from backend.db.models import Base, DataIngestionRun, Station, Train, TrainTelemetry
from backend.db.session import engine, SessionLocal


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Drop all tables and recreate them for a clean DB
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    # Clean up after test
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    """Create a test client with live DB."""
    return TestClient(app)


def test_data_endpoints_get_current_trains(client, db_session):
    """Test /api/data/trains/current endpoint."""
    now = datetime.now(timezone.utc)

    station = Station(
        code="NDLS",
        name="New Delhi",
        latitude=28.6,
        longitude=77.2,
        zone="NR",
        updated_at=now,
    )
    db_session.add(station)
    db_session.flush()

    train = Train(
        train_id="12001",
        train_name="Bhopal Shatabdi",
        route="NDLS-BPL",
        origin_station_code="NDLS",
        destination_station_code="BPL",
        current_station_code="NDLS",
        source="ntes_live",
        is_active=True,
        updated_at=now,
    )
    db_session.add(train)
    db_session.flush()

    run = DataIngestionRun(
        source="ntes_live",
        started_at=now,
        finished_at=now,
        records_received=1,
        records_valid=1,
        records_invalid=0,
        records_persisted=1,
        status="success",
    )
    db_session.add(run)
    db_session.flush()

    telemetry = TrainTelemetry(
        train_pk=train.id,
        train_id="12001",
        station_code="NDLS",
        latitude=28.6,
        longitude=77.2,
        delay_minutes=15,
        speed_kmh=85.0,
        timestamp_utc=now,
        source="ntes_live",
        ingestion_run_id=run.id,
        raw_payload="{}",
    )
    db_session.add(telemetry)
    db_session.commit()

    resp = client.get("/api/data/trains/current")
    assert resp.status_code == 200
    body = resp.json()
    assert "trains" in body
    assert len(body["trains"]) >= 1
    assert body["trains"][0]["train_id"] == "12001"
    assert body["trains"][0]["delay_minutes"] == 15


def test_data_endpoints_get_train_history(client, db_session):
    """Test /api/data/trains/{train_id}/history endpoint."""
    now = datetime.now(timezone.utc)

    train = Train(
        train_id="12301",
        train_name="Howrah Rajdhani",
        route="HWH-NDLS",
        origin_station_code="HWH",
        destination_station_code="NDLS",
        current_station_code="HWH",
        source="ntes_live",
        is_active=True,
        updated_at=now,
    )
    db_session.add(train)
    db_session.flush()

    run = DataIngestionRun(
        source="ntes_live",
        started_at=now,
        finished_at=now,
        records_received=2,
        records_valid=2,
        records_invalid=0,
        records_persisted=2,
        status="success",
    )
    db_session.add(run)
    db_session.flush()

    for i in range(2):
        telemetry = TrainTelemetry(
            train_pk=train.id,
            train_id="12301",
            station_code="HWH",
            latitude=22.6,
            longitude=88.3,
            delay_minutes=10 + i * 5,
            speed_kmh=80.0 + i * 5,
            timestamp_utc=now,
            source="ntes_live",
            ingestion_run_id=run.id,
            raw_payload="{}",
        )
        db_session.add(telemetry)
    db_session.commit()

    resp = client.get("/api/data/trains/12301/history?hours=24")
    assert resp.status_code == 200
    body = resp.json()
    assert body["train_id"] == "12301"
    assert len(body["telemetry"]) >= 2


def test_data_endpoints_get_zone_health(client, db_session):
    """Test /api/data/zones/health endpoint."""
    now = datetime.now(timezone.utc)

    station = Station(
        code="NDLS",
        name="New Delhi",
        latitude=28.6,
        longitude=77.2,
        zone="NR",
        updated_at=now,
    )
    db_session.add(station)
    db_session.flush()

    train = Train(
        train_id="12001",
        train_name="Train A",
        route="NDLS-BPL",
        origin_station_code="NDLS",
        destination_station_code="BPL",
        current_station_code="NDLS",
        source="ntes_live",
        is_active=True,
        updated_at=now,
    )
    db_session.add(train)
    db_session.flush()

    run = DataIngestionRun(
        source="ntes_live",
        started_at=now,
        finished_at=now,
        records_received=1,
        records_valid=1,
        records_invalid=0,
        records_persisted=1,
        status="success",
    )
    db_session.add(run)
    db_session.flush()

    telemetry = TrainTelemetry(
        train_pk=train.id,
        train_id="12001",
        station_code="NDLS",
        latitude=28.6,
        longitude=77.2,
        delay_minutes=20,
        speed_kmh=85.0,
        timestamp_utc=now,
        source="ntes_live",
        ingestion_run_id=run.id,
        raw_payload="{}",
    )
    db_session.add(telemetry)
    db_session.commit()

    resp = client.get("/api/data/zones/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "zones" in body
