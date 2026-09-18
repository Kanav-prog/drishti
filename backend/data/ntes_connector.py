"""
NTES Live Data Connector

Polls Indian Railways NTES system for real-time train data.
Handles: scraping, validation, reconciliation, caching.

NTES = National Train Enquiry System (live IR data)
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging
import asyncio
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class TrainState:
    """Real-time state of a train from NTES"""
    train_id: str
    train_name: str
    current_station: str
    current_lat: float
    current_lon: float
    actual_delay_minutes: int
    scheduled_delay_baseline_minutes: int = 0
    speed_kmh: float = 0.0
    route: str = ""
    timestamp: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


class NTESConnector:
    """Polls live NTES feed every 5 minutes"""
    
    def __init__(self, poll_interval_seconds: int = 300, cache_file: str = "ntes_cache.json"):
        """
        Initialize NTES connector.
        
        Args:
            poll_interval_seconds: How often to poll NTES (default 5 min)
            cache_file: Where to store cached train states
        """
        self.poll_interval = poll_interval_seconds
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, TrainState] = {}
        self.poll_count = 0
        self.errors = 0
        
        logger.info(f"NTES Connector initialized (poll every {poll_interval_seconds}s)")
        
    def load_hardcoded_trains(self) -> List[TrainState]:
        """
        Load hardcoded train data for development/testing.
        In production, replace with actual NTES API calls.
        """
        # Simulated major trains from Indian Railways
        trains = [
            TrainState(
                train_id="12841",
                train_name="Coromandel Express",
                current_station="Bahanaga Bazar",
                current_lat=21.5,
                current_lon=86.8,
                actual_delay_minutes=45,
                route="Howrah-Chennai"
            ),
            TrainState(
                train_id="12003",
                train_name="Bengaluru-Howrah Express",
                current_station="Gaisal",
                current_lat=24.2,
                current_lon=88.5,
                actual_delay_minutes=32,
                route="Howrah-Chennai"
            ),
            TrainState(
                train_id="13015",
                train_name="Kanchanjungha Express",
                current_station="Agartala",
                current_lat=23.8,
                current_lon=91.3,
                actual_delay_minutes=28,
                route="Howrah-Chennai"
            ),
            TrainState(
                train_id="15006",
                train_name="Goods Train",
                current_station="Bahanaga Bazar Loop",
                current_lat=21.5,
                current_lon=86.8,
                actual_delay_minutes=60,
                route="Cross-track"
            ),
        ]
        
        # Add timestamps
        now = datetime.now(timezone.utc).isoformat()
        for train in trains:
            train.timestamp = now
            
        return trains
    
    async def poll_ntes(self) -> List[TrainState]:
        """
        Poll NTES for train states.
        In production: query actual NTES API
        For now: return simulated data
        
        TODO: 
        1. Query https://enquiry.indianrail.gov.in/ntes/ API
        2. Parse response into TrainState objects
        3. Validate schema
        4. Reconcile with timetable
        5. Cache results
        """
        self.poll_count += 1
        
        try:
            # Development: use hardcoded data
            trains = self.load_hardcoded_trains()
            
            # Simulate some variation (delays increase over time)
            for train in trains:
                train.actual_delay_minutes += (self.poll_count % 5)
            
            # Cache results
            for train in trains:
                self.cache[train.train_id] = train
            
            logger.info(f"Poll #{self.poll_count}: {len(trains)} trains updated")
            return trains
            
        except Exception as e:
            self.errors += 1
            logger.error(f"NTES poll failed: {e}")
            return []
    
    def validate_train_state(self, state: TrainState) -> bool:
        """
        Validate train state against schema.
        
        Checks:
        - train_id not empty
        - delay is numeric and reasonable (<480 min = 8 hours)
        - coordinates are within India bounds
        """
        # Check required fields
        if not state.train_id or len(state.train_id) == 0:
            logger.warning(f"Invalid train_id: {state.train_id}")
            return False
        
        # Check delay is reasonable
        if not (-60 <= state.actual_delay_minutes <= 480):
            logger.warning(f"Delay out of range: {state.actual_delay_minutes}")
            return False
        
        # Check coordinates are in India bounds
        if not (8 <= state.current_lat <= 35 and 68 <= state.current_lon <= 97):
            logger.warning(f"Coordinates out of India: ({state.current_lat}, {state.current_lon})")
            return False
        
        return True
    
    async def reconcile_with_timetable(self, state: TrainState) -> Dict:
        """
        Reconcile actual train position with timetable.
        
        Returns:
        {
            'is_valid': bool,
            'expected_station': str,
            'expected_time': str,
            'reconciliation_score': float (0-1)
        }
        
        TODO:
        1. Fetch expected station from timetable for this time
        2. Check if current_station matches expected (±30 min window)
        3. Flag if mismatch exceeds threshold
        """
        # For now: return placeholder
        return {
            'is_valid': True,
            'expected_station': state.current_station,
            'expected_time': state.timestamp,
            'reconciliation_score': 1.0
        }
    
    def save_cache(self):
        """Save train cache to disk"""
        try:
            data = {train_id: state.to_dict() for train_id, state in self.cache.items()}
            self.cache_file.write_text(json.dumps(data, indent=2))
            logger.debug(f"Saved {len(self.cache)} trains to cache")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def load_cache(self):
        """Load train cache from disk"""
        try:
            if self.cache_file.exists():
                data = json.loads(self.cache_file.read_text())
                self.cache = {
                    train_id: TrainState(**state) 
                    for train_id, state in data.items()
                }
                logger.debug(f"Loaded {len(self.cache)} trains from cache")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
    
    async def run_polling_loop(self):
        """
        Main polling loop: fetch data every poll_interval seconds
        """
        logger.info("Starting NTES polling loop...")
        
        while True:
            try:
                trains = await self.poll_ntes()
                
                # Validate each train
                valid_count = 0
                for train in trains:
                    if self.validate_train_state(train):
                        valid_count += 1
                
                logger.info(f"Validated: {valid_count}/{len(trains)} trains")
                
                # Save cache
                self.save_cache()
                
                # Sleep until next poll
                await asyncio.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Polling loop interrupted")
                break
            except Exception as e:
                logger.error(f"Polling loop error: {e}")
                await asyncio.sleep(self.poll_interval)
    
    def get_train_state(self, train_id: str) -> Optional[TrainState]:
        """Get cached state of a specific train"""
        return self.cache.get(train_id)
    
    def get_all_trains(self) -> List[TrainState]:
        """Get all cached train states"""
        return list(self.cache.values())
    
    def get_trains_at_station(self, station: str) -> List[TrainState]:
        """Get all trains currently at a specific station"""
        return [t for t in self.cache.values() if t.current_station == station]
    
    def get_stats(self) -> Dict:
        """Get connector statistics"""
        return {
            'polls_count': self.poll_count,
            'errors': self.errors,
            'success_rate': 1.0 - (self.errors / max(1, self.poll_count)),
            'trains_cached': len(self.cache),
            'cache_file': str(self.cache_file)
        }


async def main():
    """Main entry point for development"""
    logging.basicConfig(level=logging.INFO)
    
    connector = NTESConnector(poll_interval_seconds=5)
    connector.load_cache()
    
    # Run a few polls
    for i in range(3):
        trains = await connector.poll_ntes()
        print(f"\n=== Poll {connector.poll_count} ===")
        for train in trains:
            print(f"  {train.train_id}: {train.current_station} (delay: {train.actual_delay_minutes}m)")
        
        if i < 2:
            await asyncio.sleep(connector.poll_interval)
    
    stats = connector.get_stats()
    print(f"\n=== Stats ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
