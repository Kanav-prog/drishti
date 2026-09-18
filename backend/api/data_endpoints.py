"""Database-backed train state and telemetry APIs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.db.models import Station, Train, TrainTelemetry
from backend.db.session import get_db

router = APIRouter(prefix="/api/data", tags=["data"])


@router.get("/trains/current")
async def get_current_trains(
    zone: Optional[str] = Query(None),
    min_delay: int = Query(0),
    max_results: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Get current state of all trains (latest telemetry per train)."""
    query = db.query(Train).filter(Train.is_active.is_(True))

    if zone:
        query = query.filter(Train.origin_station_code.ilike(f"{zone[:2]}%"))

    trains = query.limit(max_results).all()

    result = []
    for train in trains:
        latest_telemetry = (
            db.query(TrainTelemetry)
            .filter(TrainTelemetry.train_pk == train.id)
            .order_by(TrainTelemetry.timestamp_utc.desc())
            .first()
        )

        if latest_telemetry and latest_telemetry.delay_minutes >= min_delay:
            result.append(
                {
                    "train_id": train.train_id,
                    "train_name": train.train_name,
                    "current_station": train.current_station_code,
                    "route": train.route,
                    "delay_minutes": latest_telemetry.delay_minutes,
                    "speed_kmh": latest_telemetry.speed_kmh,
                    "latitude": latest_telemetry.latitude,
                    "longitude": latest_telemetry.longitude,
                    "timestamp": latest_telemetry.timestamp_utc.isoformat(),
                    "source": latest_telemetry.source,
                    "stress_level": "CRITICAL" if latest_telemetry.delay_minutes > 120 else ("HIGH" if latest_telemetry.delay_minutes > 60 else "STABLE"),
                }
            )

    # Return as direct array (compatible with frontend)
    return result


@router.get("/trains/{train_id}/history")
async def get_train_history(
    train_id: str,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Get historical telemetry for a single train."""
    train = db.query(Train).filter(Train.train_id == train_id).first()
    if not train:
        raise HTTPException(status_code=404, detail=f"Train {train_id} not found")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    telemetry = (
        db.query(TrainTelemetry)
        .filter(
            TrainTelemetry.train_pk == train.id,
            TrainTelemetry.timestamp_utc >= cutoff,
        )
        .order_by(TrainTelemetry.timestamp_utc.asc())
        .all()
    )

    return {
        "train_id": train.train_id,
        "train_name": train.train_name,
        "route": train.route,
        "hours": hours,
        "record_count": len(telemetry),
        "telemetry": [
            {
                "timestamp": t.timestamp_utc.isoformat(),
                "station": t.station_code,
                "delay_minutes": t.delay_minutes,
                "speed_kmh": t.speed_kmh,
                "latitude": t.latitude,
                "longitude": t.longitude,
                "source": t.source,
            }
            for t in telemetry
        ],
    }


@router.get("/stations/current")
async def get_stations_occupancy(
    zone: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get current occupancy at all major stations."""
    query = db.query(Station)

    if zone:
        query = query.filter(Station.zone == zone.upper())

    stations = query.all()
    result = []

    for station in stations:
        current_trains = (
            db.query(TrainTelemetry)
            .filter(
                TrainTelemetry.station_code == station.code,
                TrainTelemetry.timestamp_utc
                >= datetime.now(timezone.utc) - timedelta(minutes=5),
            )
            .all()
        )

        if current_trains:
            avg_delay = sum(t.delay_minutes for t in current_trains) / len(current_trains)
            max_delay = max(t.delay_minutes for t in current_trains)
            result.append(
                {
                    "station_code": station.code,
                    "station_name": station.name,
                    "zone": station.zone,
                    "latitude": station.latitude,
                    "longitude": station.longitude,
                    "trains_now": len(current_trains),
                    "avg_delay_minutes": round(avg_delay, 1),
                    "max_delay_minutes": max_delay,
                    "stress_level": (
                        "CRITICAL"
                        if max_delay > 120
                        else "HIGH"
                        if max_delay > 60
                        else "MEDIUM"
                        if max_delay > 30
                        else "LOW"
                    ),
                }
            )

    return {"stations": result, "count": len(result)}


@router.get("/zones/health")
async def get_zone_health(db: Session = Depends(get_db)):
    """Get operational health by railway zone."""
    zones = {}

    all_telemetry = (
        db.query(TrainTelemetry)
        .filter(TrainTelemetry.timestamp_utc >= datetime.now(timezone.utc) - timedelta(minutes=30))
        .all()
    )

    for telemetry in all_telemetry:
        station = db.query(Station).filter(Station.code == telemetry.station_code).first()
        if station:
            zone = station.zone
            if zone not in zones:
                zones[zone] = {"trains": [], "delays": []}
            zones[zone]["trains"].append(telemetry.train_id)
            zones[zone]["delays"].append(telemetry.delay_minutes)

    result = {}
    for zone, data in zones.items():
        trains = set(data["trains"])
        delays = data["delays"]
        avg_delay = sum(delays) / len(delays) if delays else 0
        max_delay = max(delays) if delays else 0

        health_score = max(0, 100 - (avg_delay / 2))

        result[zone] = {
            "trains_active": len(trains),
            "avg_delay_minutes": round(avg_delay, 1),
            "max_delay_minutes": max_delay,
            "health_score": round(health_score, 1),
            "status": (
                "CRITICAL" if health_score < 30 else "STRESSED" if health_score < 60 else "HEALTHY"
            ),
        }

    return {"zones": result}


@router.get("/telemetry/stats")
async def get_telemetry_stats(
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Get global statistics on ingested telemetry."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    total_records = (
        db.query(TrainTelemetry).filter(TrainTelemetry.timestamp_utc >= cutoff).count()
    )

    unique_trains = (
        db.query(TrainTelemetry.train_id)
        .filter(TrainTelemetry.timestamp_utc >= cutoff)
        .distinct()
        .count()
    )

    unique_stations = (
        db.query(TrainTelemetry.station_code)
        .filter(TrainTelemetry.timestamp_utc >= cutoff)
        .distinct()
        .count()
    )

    delays = db.query(TrainTelemetry.delay_minutes).filter(TrainTelemetry.timestamp_utc >= cutoff).all()

    delay_values = [d[0] for d in delays if d[0] is not None]
    avg_delay = sum(delay_values) / len(delay_values) if delay_values else 0
    max_delay = max(delay_values) if delay_values else 0

    sources = (
        db.query(TrainTelemetry.source)
        .filter(TrainTelemetry.timestamp_utc >= cutoff)
        .distinct()
        .all()
    )

    return {
        "hours": hours,
        "total_records": total_records,
        "unique_trains": unique_trains,
        "unique_stations": unique_stations,
        "avg_delay_minutes": round(avg_delay, 1),
        "max_delay_minutes": max_delay,
        "data_sources": [s[0] for s in sources],
    }
