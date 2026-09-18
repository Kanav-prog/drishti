"""Populate DRISHTI database with sample trains and telemetry data."""

import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import random

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.db.session import SessionLocal
from backend.db.models import Train, Station, TrainTelemetry, DataIngestionRun

def populate_trains():
    """Populate database with 127 sample trains."""
    db = SessionLocal()
    
    try:
        # Check if trains already exist
        existing = db.query(Train).count()
        if existing > 0:
            print(f"✓ {existing} trains already in database")
            return
        
        # Get all stations
        stations = db.query(Station).all()
        if not stations:
            print("✗ No stations found in database. Run station initialization first.")
            return
        
        stations_list = list(stations)
        
        # Create ingestion run
        run = DataIngestionRun(
            source="demo_sample",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            records_received=127,
            records_valid=127,
            records_invalid=0,
            records_persisted=127,
            status="completed"
        )
        db.add(run)
        db.flush()
        
        # Sample train data
        sample_trains = [
            ("12001", "Rajdhani Express", "NDLS", "KOLKATA", ["NDLS", "AGRA", "ALLAHABAD", "VARANASI", "KOLKATA"]),
            ("12002", "Shatabdi Express", "NDLS", "AGRA", ["NDLS", "AGRA"]),
            ("12003", "Rajdhani Express", "NDLS", "MUMBAI", ["NDLS", "AGRA", "JHANSI", "BHOPAL", "MUMBAI"]),
            ("12004", "Shatabdi Express", "NDLS", "JNP", ["NDLS", "MATHURA", "JNP"]),
            ("12005", "Rajdhani Express", "NDLS", "HOWRAH", ["NDLS", "ALLAHABAD", "VARANASI", "HOWRAH"]),
            ("12006", "Poorva Express", "NDLS", "HOWRAH", ["NDLS", "VARANASI", "HOWRAH"]),
            ("12007", "North East Express", "NDLS", "SILLIGURI", ["NDLS", "LUCKNOW", "GORAKHPUR", "SILLIGURI"]),
            ("12008", "Himalayan Queen", "NDLS", "SIMLA", ["NDLS", "KALKA", "SIMLA"]),
            ("12009", "Circular Railway", "NDLS", "AGRA", ["NDLS", "AGRA"]),
            ("12010", "Premium Express", "NDLS", "LUCKNOW", ["NDLS", "LUCKNOW"]),
            ("12011", "Fast Passenger", "MUMBAI", "HOWRAH", ["MUMBAI", "BHOPAL", "INDORE", "KOLKATA", "HOWRAH"]),
            ("12012", "Express", "MUMBAI", "DELHI", ["MUMBAI", "BHOPAL", "AGRA", "DELHI"]),
            ("12013", "Local Train", "MUMBAI", "PUNE", ["MUMBAI", "PUNE"]),
            ("12014", "Intercity Express", "MUMBAI", "BANGALORE", ["MUMBAI", "KARNATAKA", "BANGALORE"]),
            ("12015", "Shatabdi", "MUMBAI", "SURAT", ["MUMBAI", "SURAT"]),
            ("12016", "Express", "BANGALORE", "HYDERABAD", ["BANGALORE", "TELANGANA", "HYDERABAD"]),
            ("12017", "South Express", "BANGALORE", "KOCHI", ["BANGALORE", "KARNATAKA", "KOCHI"]),
            ("12018", "Express", "BANGALORE", "MUMBAI", ["BANGALORE", "KARNATAKA", "MUMBAI"]),
            ("12019", "Shatabdi", "BANGALORE", "MYSORE", ["BANGALORE", "MYSORE"]),
            ("12020", "South Indian", "BANGALORE", "MADRAS", ["BANGALORE", "TAMIL_NADU", "MADRAS"]),
        ]
        
        # Extend with more trains for variety
        train_ids = [12021 + i for i in range(107)]
        for train_id in train_ids:
            origin = random.choice(stations_list)
            dest = random.choice(stations_list)
            while dest == origin:
                dest = random.choice(stations_list)
            sample_trains.append((
                str(train_id),
                f"Train {train_id}",
                origin.code,
                dest.code,
                [origin.code, dest.code]
            ))
        
        # Create trains
        created_trains = []
        for train_id, train_name, origin, dest, route in sample_trains:
            # Pick a random station from the route
            current_station = random.choice(route)
            
            train = Train(
                train_id=train_id,
                train_name=train_name,
                route=f"{origin}-{dest}",
                origin_station_code=origin,
                destination_station_code=dest,
                current_station_code=current_station,
                source="demo_sample",
                is_active=True,
                updated_at=datetime.now(timezone.utc)
            )
            db.add(train)
            created_trains.append((train, current_station))
        
        db.flush()
        print(f"✓ Created {len(created_trains)} trains")
        
        # Create telemetry data for each train
        now = datetime.now(timezone.utc)
        for train, current_station in created_trains:
            # Get station location
            station = db.query(Station).filter(Station.code == current_station).first()
            if not station:
                continue
            
            # Create telemetry with random stress levels
            delay = random.choice([0, 5, 15, 30, 45, 60, 90])
            speed = random.randint(40, 120)
            
            telemetry = TrainTelemetry(
                train_pk=train.id,
                train_id=train.train_id,
                station_code=current_station,
                latitude=station.latitude,
                longitude=station.longitude,
                delay_minutes=delay,
                speed_kmh=speed,
                timestamp_utc=now - timedelta(minutes=random.randint(0, 30)),
                source="demo_sample",
                ingestion_run_id=run.id,
                raw_payload="{}"
            )
            db.add(telemetry)
        
        db.commit()
        print(f"✓ Created telemetry data for all trains")
        print(f"✓ Database populated successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error populating database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🚄 Populating DRISHTI database...")
    populate_trains()
