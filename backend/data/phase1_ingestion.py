"""Phase 1 ingestion pipeline for NTES and CRS data sources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from backend.data.crs_parser import CRSParser
from backend.data.ntes_connector import NTESConnector
from backend.data.crs_loader import CRSLoader
from backend.data.ntes_live import NTESLiveConnector
from backend.data.train_repository import TrainDataRepository
from backend.data.cleaning import DataCleaner
from backend.data.real_feed_connector import RealFeedConnector
from backend.data.quality_checker import DataQualityChecker

@dataclass
class IngestionResult:
    """Normalized ingestion result returned by each source."""

    source: str
    timestamp_utc: str
    records_received: int
    records_valid: int
    records_invalid: int
    records_persisted: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "timestamp_utc": self.timestamp_utc,
            "records_received": self.records_received,
            "records_valid": self.records_valid,
            "records_invalid": self.records_invalid,
            "records_persisted": self.records_persisted,
        }


class Phase1IngestionPipeline:
    """Coordinates ingestion for Phase 1 data sources."""

    def __init__(
        self,
        ntes_connector: NTESConnector | None = None,
        crs_parser: CRSParser | None = None,
        train_repository: TrainDataRepository | None = None,
        real_feed_connector: RealFeedConnector | None = None,
        quality_checker: DataQualityChecker | None = None,
        persist_to_db: bool = True,
        use_real_feeds: bool = True,
    ) -> None:
        self.ntes_connector = ntes_connector or NTESConnector()
        self.crs_parser = crs_parser or CRSParser()
        self.train_repository = train_repository or TrainDataRepository()
        self.real_feed_connector = real_feed_connector or RealFeedConnector()
        self.quality_checker = quality_checker or DataQualityChecker()
        self.persist_to_db = persist_to_db
        self.use_real_feeds = use_real_feeds

    @staticmethod
    def _now_utc_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def ingest_ntes_once(self) -> IngestionResult:
        """Poll NTES/real feeds with quality gating."""
        if self.use_real_feeds:
            trains_raw = await self.real_feed_connector.fetch_trains_from_real_feeds()
        else:
            live_connector = NTESLiveConnector()
            trains_raw = [
                {
                    "train_id": t.train_id,
                    "train_name": t.train_name,
                    "current_station": t.current_station,
                    "current_lat": t.current_lat,
                    "current_lon": t.current_lon,
                    "actual_delay_minutes": t.actual_delay_minutes,
                    "speed_kmh": t.speed_kmh,
                    "route": t.route,
                    "timestamp": t.timestamp,
                    "source": "ntes_live",
                }
                for t in await live_connector.fetch_live_trains()
            ]
            await live_connector.close()

        received = len(trains_raw)
        valid_states = []
        invalid = 0

        for train in trains_raw:
            is_valid, warnings = self.quality_checker.validate(train)
            if not is_valid:
                invalid += 1
            else:
                valid_states.append(train)

        persisted = 0
        if self.persist_to_db and valid_states:
            summary = self.train_repository.ingest_train_states(
                valid_states,
                source="ntes_real_feeds" if self.use_real_feeds else "ntes_live",
            )
            persisted = summary["records_persisted"]

        self.quality_checker.clear_recent_hashes()

        return IngestionResult(
            source="ntes",
            timestamp_utc=self._now_utc_iso(),
            records_received=received,
            records_valid=len(valid_states),
            records_invalid=invalid,
            records_persisted=persisted,
        )

    async def _ingest_crs_cleaned(self) -> IngestionResult:
        """Load CRS with full cleaning and quality pipeline."""
        loader = CRSLoader()
        cleaner = DataCleaner()
        
        # Load raw records from corpus
        records = loader.load()
        received = len(records)
        
        # Apply full cleaning pipeline
        # 1. Deduplicate
        records = cleaner.deduplicate_accidents(records)
        
        # 2. Normalize timestamps
        records = cleaner.normalize_timestamps(records)
        
        # 3. Impute missing values
        records = [cleaner.impute_weather(r) for r in records]
        records = [cleaner.impute_time_of_day(r) for r in records]
        
        valid = len(records)
        
        return IngestionResult(
            source="crs_cleaned",
            timestamp_utc=self._now_utc_iso(),
            records_received=received,
            records_valid=valid,
            records_invalid=max(0, received - valid),
            records_persisted=0,
        )

    async def run_once(self) -> dict[str, Any]:
        """Run one ingestion cycle for all Phase 1 sources."""
        ntes_result, crs_result = await asyncio.gather(
            self.ingest_ntes_once(),
            self._ingest_crs_cleaned(),
        )

        return {
            "phase": 1,
            "pipeline": "data_ingestion",
            "timestamp_utc": self._now_utc_iso(),
            "results": [ntes_result.to_dict(), crs_result.to_dict()],
        }

    @staticmethod
    def persist_snapshot(snapshot: dict[str, Any], output_path: str | Path) -> Path:
        """Persist one ingestion snapshot as JSON."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        return output


async def _main() -> None:
    pipeline = Phase1IngestionPipeline()
    snapshot = await pipeline.run_once()
    out = Phase1IngestionPipeline.persist_snapshot(snapshot, "data/phase1_ingestion_snapshot.json")
    print(f"Phase 1 ingestion completed. Snapshot written to: {out}")


if __name__ == "__main__":
    asyncio.run(_main())
