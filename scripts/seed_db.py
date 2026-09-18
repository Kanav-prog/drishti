"""Database seeding script for DRISHTI — Populates stations and initial train metadata."""
import os
import sys
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from backend.db.models import Station, Train
from backend.db.session import SessionLocal, engine

# Data copied from scripts/generate_graph.py
NODES = [
    ("NDLS",   "New Delhi",          "NR",  28.6431,  77.2197),
    ("DLI",    "Delhi Junction",     "NR",  28.5921,  77.2270),
    ("LKO",    "Lucknow",            "NR",  26.8390,  80.9333),
    ("CNB",    "Kanpur Central",     "NR",  26.4499,  80.3319),
    ("ALD",    "Prayagraj Jn",       "NR",  25.4246,  81.8410),
    ("JHS",    "Jhansi Jn",          "NR",  25.4464,  78.5953),
    ("FZD",    "Firozabad",          "NR",  27.1506,  78.3717),
    ("HRN",    "Hazrat Nizamuddin",  "NR",  28.5633,  77.2522),
    ("AGC",    "Agra Cantt",         "NR",  27.1767,  78.0059),
    ("GWL",    "Gwalior",            "NR",  26.2183,  78.1749),
    ("HWH",    "Howrah Jn",          "ER",  22.5958,  88.3017),
    ("ASN",    "Asansol Jn",         "ER",  23.6850,  86.9768),
    ("BLSR",   "Balasore",           "ER",  21.4942,  86.9289),
    ("BBS",    "Bhubaneswar",        "ER",  20.2500,  85.8300),
    ("CT",     "Cuttack",            "ER",  20.4628,  85.8830),
    ("KGP",    "Kharagpur Jn",       "ER",  22.3396,  87.3204),
    ("BOMBAY", "Mumbai Central",     "WR",  18.9719,  72.8188),
    ("DADAR",  "Dadar",              "WR",  18.9819,  72.8288),
    ("BRC",    "Vadodara Jn",        "WR",  22.3143,  73.1939),
    ("ADI",    "Ahmedabad Jn",       "WR",  23.0225,  72.5714),
    ("RATLAM", "Ratlam Jn",          "WR",  23.3304,  75.0394),
    ("PUNE",   "Pune Jn",            "CR",  18.5204,  73.8567),
    ("NGP",    "Nagpur",             "CR",  21.1460,  79.0882),
    ("BPL",    "Bhopal Jn",          "CR",  23.1815,  77.4104),
    ("JBP",    "Jabalpur",           "CR",  23.1815,  79.9864),
    ("ET",     "Itarsi Jn",          "CR",  22.1879,  77.6889),
    ("BINA",   "Bina Jn",            "CR",  23.6069,  78.8242),
    ("MAS",    "Chennai Central",    "SR",  13.0288,  80.1859),
    ("SBC",    "Bangalore City",     "SR",  12.9565,  77.5960),
    ("MYSORE", "Mysuru Jn",          "SR",  12.2958,  76.6394),
    ("SALEM",  "Salem Jn",           "SR",  11.6643,  78.1461),
    ("ED",     "Erode Jn",           "SR",  11.3410,  77.7172),
    ("SC",     "Secunderabad",       "SCR", 17.4337,  78.5016),
    ("BZA",    "Vijayawada Jn",      "SCR", 16.5062,  80.6480),
    ("VSKP",   "Visakhapatnam",      "SCR", 17.6907,  83.2179),
    ("GNT",    "Guntur Jn",          "SCR", 16.2963,  80.4376),
    ("RJY",    "Rajahmundry",        "SCR", 16.9891,  81.7866),
    ("TATA",   "Tatanagar Jn",       "SER", 22.7720,  86.2081),
    ("ROU",    "Rourkela",           "SER", 22.2511,  84.8582),
    ("BSP",    "Bilaspur Jn",        "SER", 22.0797,  82.1409),
    ("JP",     "Jaipur Jn",          "NWR", 26.9124,  75.7873),
    ("AII",    "Ajmer Jn",           "NWR", 26.4552,  74.6290),
    ("JU",     "Jodhpur Jn",         "NWR", 26.2389,  73.0243),
    ("GKP",    "Gorakhpur Jn",       "NER", 26.7604,  83.3732),
    ("LJN",    "Lucknow NE",         "NER", 26.8578,  80.9204),
    ("GHY",    "Guwahati",           "NFR", 26.1445,  91.7362),
    ("DBRG",   "Dibrugarh",          "NFR", 27.4848,  95.0088),
    ("PNBE",   "Patna Jn",           "ECR", 25.6022,  85.1376),
    ("MGS",    "Mughal Sarai",       "ECR", 25.2819,  83.1199),
    ("DHN",    "Dhanbad Jn",         "ECR", 23.7957,  86.4304),
    ("PURI",   "Puri",               "ECoR",19.8104,  85.8300),
]

# Popular trains to simulate
TRAINS = [
    ("12001", "Shatabdi Express", "NDLS-BPL", "NDLS", "BPL", "NDLS"),
    ("12951", "Mumbai Rajdhani", "NDLS-BOMBAY", "NDLS", "BOMBAY", "NDLS"),
    ("12301", "Howrah Rajdhani", "NDLS-HWH", "NDLS", "HWH", "NDLS"),
    ("22691", "Bangalore Rajdhani", "NDLS-SBC", "NDLS", "SBC", "NDLS"),
    ("12622", "Tamil Nadu Express", "NDLS-MAS", "NDLS", "MAS", "NDLS"),
    ("12801", "Purushottam Express", "NDLS-PURI", "NDLS", "PURI", "NDLS"),
    ("12275", "Duronto Express", "NDLS-NGP", "NDLS", "NGP", "NDLS"),
    ("12559", "Shiv Ganga Express", "NDLS-BSB", "NDLS", "BSB", "NDLS"),
    ("12423", "Dibrugarh Rajdhani", "NDLS-DBRG", "NDLS", "DBRG", "NDLS"),
    ("20503", "NE Rajdhani", "NDLS-GHY", "NDLS", "GHY", "NDLS"),
]

def seed_database():
    db = SessionLocal()
    print("🌱 Starting database seeding...")

    try:
        # 1. Seed Stations
        print(f"📡 Seeding {len(NODES)} stations...")
        for code, name, zone, lat, lng in NODES:
            existing = db.query(Station).filter(Station.code == code).first()
            if not existing:
                station = Station(
                    code=code,
                    name=name,
                    zone=zone,
                    latitude=lat,
                    longitude=lng
                )
                db.add(station)
        
        db.commit()
        print("✅ Stations seeded.")

        # 2. Seed Trains
        print(f"🚄 Seeding {len(TRAINS)} trains...")
        for tid, tname, route, origin, dest, current in TRAINS:
            existing = db.query(Train).filter(Train.train_id == tid).first()
            if not existing:
                train = Train(
                    train_id=tid,
                    train_name=tname,
                    route=route,
                    origin_station_code=origin,
                    destination_station_code=dest,
                    current_station_code=current,
                    source="telemetry_producer",
                    is_active=True
                )
                db.add(train)
        
        db.commit()
        print("✅ Trains seeded.")
        print("🎉 Database successfully initialized for DRISHTI.")

    except Exception as e:
        print(f"❌ Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
