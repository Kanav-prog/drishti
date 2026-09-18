"""Persistence layer for train-state ingestion and telemetry history."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from typing import Any, Sequence, Union

from sqlalchemy.orm import Session

from backend.data.ntes_live import TrainState
from backend.db.models import Base, DataIngestionRun, Station, Train, TrainTelemetry
from backend.db.session import SessionLocal


class TrainDataRepository:
    """Stores real-time train states into normalized relational tables."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    @staticmethod
    def _parse_route(route: str) -> tuple[str, str]:
        if not route or "-" not in route:
            return "", ""
        origin, destination = route.split("-", 1)
        return origin.strip().upper(), destination.strip().upper()

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _zone_from_station(station_code: str) -> str:
        code = (station_code or "").upper()
        zone_prefix = {
            "ND": "NR",
            "DL": "NR",
            "HW": "ER",
            "HO": "ER",
            "MM": "CR",
            "MU": "CR",
            "SE": "SER",
            "SC": "SCR",
            "MA": "SR",
            "CH": "SR",
        }
        if len(code) >= 2:
            return zone_prefix.get(code[:2], "UNKNOWN")
        return "UNKNOWN"

    def _upsert_station(self, db: Session, state: TrainState) -> Station:
        station_code = (state.current_station or "").strip().upper()
        station = db.query(Station).filter(Station.code == station_code).first()
        if station is None:
            station = Station(
                code=station_code,
                name=station_code,
                latitude=state.current_lat,
                longitude=state.current_lon,
                zone=self._zone_from_station(station_code),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(station)
            db.flush()
            return station

        station.latitude = state.current_lat
        station.longitude = state.current_lon
        station.updated_at = datetime.now(timezone.utc)
        return station

    def _upsert_train(self, db: Session, state: TrainState, source: str) -> Train:
        train = db.query(Train).filter(Train.train_id == state.train_id).first()
        origin, destination = self._parse_route(state.route)

        if train is None:
            train = Train(
                train_id=state.train_id,
                train_name=state.train_name,
                route=state.route or "",
                origin_station_code=origin,
                destination_station_code=destination,
                current_station_code=state.current_station.upper(),
                source=source,
                is_active=True,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(train)
            db.flush()
            return train

        train.train_name = state.train_name
        train.route = state.route or ""
        train.origin_station_code = origin
        train.destination_station_code = destination
        train.current_station_code = state.current_station.upper()
        train.source = source
        train.is_active = True
        train.updated_at = datetime.now(timezone.utc)
        return train

    @staticmethod
    def _is_valid_state(state: TrainState) -> bool:
        return (
            bool(state.train_id)
            and bool(state.current_station)
            and 0 <= state.actual_delay_minutes <= 480
            and -90.0 <= state.current_lat <= 90.0
            and -180.0 <= state.current_lon <= 180.0
        )

    def ingest_train_states(self, train_states: Sequence[Union[TrainState, dict]], source: str = "ntes_live") -> dict[str, int]:
        started_at = datetime.now(timezone.utc)
        received = len(train_states)

        # Convert dicts to TrainState objects
        converted_states = []
        for state in train_states:
            if isinstance(state, dict):
                ts = TrainState(
                    train_id=state.get("train_id", ""),
                    train_name=state.get("train_name", ""),
                    current_station=state.get("current_station", ""),
                    current_lat=float(state.get("current_lat", 0)),
                    current_lon=float(state.get("current_lon", 0)),
                    actual_delay_minutes=int(state.get("actual_delay_minutes", 0)),
                    speed_kmh=float(state.get("speed_kmh", 0.0)),
                    route=state.get("route", ""),
                    timestamp=state.get("timestamp", ""),
                )
            else:
                ts = state
            converted_states.append(ts)

        with self.session_factory() as db:
            Base.metadata.create_all(bind=db.get_bind())

            run = DataIngestionRun(
                source=source,
                started_at=started_at,
                status="running",
            )
            db.add(run)
            db.flush()

            valid = 0
            invalid = 0
            persisted = 0

            for state in converted_states:
                if not self._is_valid_state(state):
                    invalid += 1
                    continue

                valid += 1
                station = self._upsert_station(db, state)
                train = self._upsert_train(db, state, source)

                telemetry = TrainTelemetry(
                    train_pk=train.id,
                    train_id=train.train_id,
                    station_code=station.code,
                    latitude=state.current_lat,
                    longitude=state.current_lon,
                    delay_minutes=int(state.actual_delay_minutes),
                    speed_kmh=float(state.speed_kmh or 0.0),
                    timestamp_utc=self._parse_timestamp(state.timestamp),
                    source=source,
                    ingestion_run_id=run.id,
                    raw_payload=json.dumps(asdict(state)),
                )
                db.add(telemetry)
                persisted += 1

            run.finished_at = datetime.now(timezone.utc)
            run.records_received = received
            run.records_valid = valid
            run.records_invalid = invalid
            run.records_persisted = persisted
            run.status = "success"
            db.commit()

        return {
            "records_received": received,
            "records_valid": valid,
            "records_invalid": invalid,
            "records_persisted": persisted,
        }
