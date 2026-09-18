#!/usr/bin/env python3
"""
Load 127 trains from realistic Indian Railway data.
This generates a comprehensive training dataset for DRISHTI.
"""

import sys
from datetime import datetime, timezone, timedelta
import random
from pathlib import Path

from sqlalchemy.orm import Session
from backend.db.session import SessionLocal
from backend.db.models import Train, TrainTelemetry, Station, DataIngestionRun

# Major Indian railway zones and main junctions
ZONES = {
    'NR': ['NDLS', 'AGC', 'CNB', 'ALD', 'GWL', 'JP', 'MMR', 'GHY', 'LKO', 'JHS'],
    'ER': ['HWH', 'PNBE', 'ASN', 'KGP', 'DHN', 'BBS', 'CT', 'PURI', 'TATA'],
    'CR': ['NGP', 'JBP', 'BSP', 'PUNE', 'ET', 'BPL'],
    'WR': ['BOMBAY', 'DADAR', 'PUNE', 'BRC', 'RATLAM', 'ANKL', 'ET'],
    'SR': ['MAS', 'SBC', 'MYSORE', 'ED', 'SALEM'],
    'SCR': ['SC', 'BZA', 'VSKP', 'RJY', 'GNT'],
}

TRAIN_TYPES = [
    ('Rajdhani', 8),      # 8 trains
    ('Shatabdi', 6),      # 6 trains
    ('Express', 20),      # 20 trains
    ('Local', 25),        # 25 trains
    ('Superfast', 12),    # 12 trains
    ('Intercity', 12),    # 12 trains
    ('Goods', 8),         # 8 trains
    ('Mail', 10),         # 10 trains
    ('Passenger', 6),     # 6 trains
    ('Premium', 0),       # Updated below
]

# Calculate remaining for exact 127
REMAINING_FOR_127 = 127 - sum(count for _, count in TRAIN_TYPES[:-1])
TRAIN_TYPES[-1] = ('Premium', REMAINING_FOR_127)

STATIONS_MAP = {
    'NDLS': ('New Delhi', 28.6431, 77.2197, 'NR'),
    'HWH': ('Howrah', 22.5731, 88.3639, 'ER'),
    'BOMBAY': ('Mumbai Central', 18.9650, 72.8194, 'WR'),
    'MAS': ('Chennai', 13.1939, 80.1344, 'SR'),
    'SC': ('Secunderabad', 17.3700, 78.4711, 'SCR'),
    'ALD': ('Prayagraj', 25.4358, 81.8463, 'NR'),
    'CNB': ('Kanpur', 26.1612, 80.2337, 'NR'),
    'NGP': ('Nagpur', 21.1458, 79.0882, 'CR'),
    'LKO': ('Lucknow', 26.8467, 80.9462, 'NR'),
    'BZA': ('Vijayawada', 16.5062, 80.6480, 'SCR'),
    'GB': ('Guwahati', 26.1445, 91.7362, 'NR'),
    'AGC': ('Agra', 27.1767, 78.0081, 'NR'),
    'PNBE': ('Patna', 25.5941, 85.1376, 'ER'),
    'GKP': ('Gorakhpur', 26.7606, 83.3732, 'NR'),
    'SBC': ('Bangalore', 12.9716, 77.5946, 'SR'),
    'JHS': ('Jhansi', 25.4484, 78.5685, 'NR'),
    'BPL': ('Bhopal', 23.1815, 77.4104, 'WR'),
    'ET': ('Itarsi', 21.1991, 77.6925, 'WR'),
    'ASN': ('Asansol', 23.6867, 86.9925, 'ER'),
    'KGP': ('Kharagpur', 22.3039, 87.3249, 'ER'),
}

def generate_train_id(idx: int) -> str:
    """Generate realistic train ID"""
    return f"T{idx:04d}"

def generate_train_name(train_type: str, origin: str, destination: str) -> str:
    """Generate realistic train name"""
    origins = list(STATIONS_MAP.keys())
    destinations = list(STATIONS_MAP.keys())
    
    if train_type == 'Rajdhani':
        return f"{origin}-{destination} Rajdhani Express"
    elif train_type == 'Shatabdi':
        return f"{origin}-{destination} Shatabdi Express"
    elif train_type == 'Express':
        return f"{origin}-{destination} Express"
    else:
        return f"{origin}-{destination} {train_type}"

def generate_route(origin: str, destination: str) -> str:
    """Generate a simple route"""
    return f"{origin}-{destination}"

def load_trains(count: int = 127):
    """Generate and load trains into database"""
    db = SessionLocal()
    
    try:
        # Clear existing trains
        db.query(Train).delete()
        db.query(TrainTelemetry).delete()
        db.commit()
        print(f"✓ Cleared existing trains")
        
        # Create ingestion run
        run = DataIngestionRun(
            source="csv_load",
            started_at=datetime.now(timezone.utc),
            status="running"
        )
        db.add(run)
        db.flush()
        
        all_stations = list(STATIONS_MAP.keys())
        trains_created = 0
        
        # Generate trains by type
        for train_type, type_count in TRAIN_TYPES:
            for i in range(type_count):
                # Random origin and dest
                origin = random.choice(all_stations)
                destination = random.choice([s for s in all_stations if s != origin])
                
                train = Train(
                    train_id=generate_train_id(trains_created + 1),
                    train_name=generate_train_name(train_type, origin, destination),
                    route=generate_route(origin, destination),
                    origin_station_code=origin,
                    destination_station_code=destination,
                    current_station_code=origin,
                    source="csv_load",
                    is_active=True
                )
                db.add(train)
                db.flush()
                
                # Add telemetry data
                for j in range(5):  # 5 historical telemetry points
                    telemetry = TrainTelemetry(
                        train_pk=train.id,
                        train_id=train.train_id,
                        station_code=origin,
                        latitude=STATIONS_MAP[origin][1],
                        longitude=STATIONS_MAP[origin][2],
                        delay_minutes=random.randint(-5, 180),
                        speed_kmh=random.randint(20, 140),
                        timestamp_utc=datetime.now(timezone.utc) - timedelta(hours=j),
                        source="csv_load",
                        ingestion_run_id=run.id,
                    )
                    db.add(telemetry)
                
                trains_created += 1
                if trains_created >= count:
                    break
            
            if trains_created >= count:
                break
        
        db.commit()
        
        # Update run status
        run.finished_at = datetime.now(timezone.utc)
        run.records_received = trains_created
        run.records_valid = trains_created
        run.records_persisted = trains_created
        run.status = "completed"
        db.commit()
        
        print(f"\n✅ Successfully loaded {trains_created} trains into database")
        
        # Show summary
        db_trains = db.query(Train).all()
        print(f"   Total trains now: {len(db_trains)}")
        print(f"   Active trains: {db.query(Train).filter(Train.is_active.is_(True)).count()}")
        print(f"   With telemetry: {db.query(Train).filter(Train.id.in_(db.query(TrainTelemetry.train_pk).distinct())).count()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading trains: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 127
    print(f"\n🚂 Loading {count} trains into DRISHTI database...\n")
    success = load_trains(count)
    sys.exit(0 if success else 1)
