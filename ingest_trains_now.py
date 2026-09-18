#!/usr/bin/env python
"""Quick script to ingest trains from real feed into database."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.data.phase1_ingestion import Phase1IngestionPipeline
from backend.data.real_feed_connector import RealFeedConnector
from backend.data.quality_checker import DataQualityChecker
from backend.data.train_repository import TrainDataRepository


async def main():
    """Run one ingestion cycle to populate trains."""
    print("\n🚂 DRISHTI Live Train Ingestion")
    print("=" * 60)

    # Initialize pipeline
    real_feed = RealFeedConnector()
    quality_check = DataQualityChecker()
    repo = TrainDataRepository()

    pipeline = Phase1IngestionPipeline(
        real_feed_connector=real_feed,
        quality_checker=quality_check,
        train_repository=repo,
        use_real_feeds=True,
        persist_to_db=True,
    )

    print("\n📡 Fetching trains from real feeds...")
    result = await pipeline.ingest_ntes_once()

    print(f"\n✅ Ingestion Complete!")
    print(f"   Received: {result.records_received}")
    print(f"   Valid:    {result.records_valid}")
    print(f"   Invalid:  {result.records_invalid}")
    print(f"   Persisted: {result.records_persisted}")

    # Show some trains
    from backend.db.session import SessionLocal
    from backend.db.models import Train, TrainTelemetry
    
    db = SessionLocal()
    trains = db.query(Train).limit(10).all()
    telemetry = db.query(TrainTelemetry).limit(10).all()
    
    print(f"\n🚂 Trains in DB: {len(trains)}")
    for t in trains:
        print(f"   • {t.train_id} - {t.train_name} @ {t.current_station_code} ({t.source})")

    print(f"\n📊 Telemetry records: {len(telemetry)}")
    for tel in telemetry[:5]:
        print(f"   • Train {tel.train_id} @ {tel.station_code}: {tel.delay_minutes}min delay, {tel.speed_kmh}km/h")

    db.close()
    await real_feed.close()


if __name__ == "__main__":
    asyncio.run(main())
