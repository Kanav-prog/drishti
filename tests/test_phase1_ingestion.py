"""Tests for Phase 1 data ingestion pipeline."""

from pathlib import Path

import pytest

from backend.data.phase1_ingestion import Phase1IngestionPipeline


@pytest.mark.asyncio
async def test_phase1_pipeline_run_once_has_expected_shape(tmp_path: Path):
    pipeline = Phase1IngestionPipeline()

    snapshot = await pipeline.run_once()

    assert snapshot["phase"] == 1
    assert snapshot["pipeline"] == "data_ingestion"
    assert "timestamp_utc" in snapshot
    assert isinstance(snapshot["results"], list)
    assert len(snapshot["results"]) == 2

    names = {item["source"] for item in snapshot["results"]}
    assert names == {"ntes", "crs_cleaned"}


@pytest.mark.asyncio
async def test_phase1_pipeline_counts_are_non_negative():
    pipeline = Phase1IngestionPipeline()

    snapshot = await pipeline.run_once()

    for result in snapshot["results"]:
        assert result["records_received"] >= 0
        assert result["records_valid"] >= 0
        assert result["records_invalid"] >= 0
        assert result["records_valid"] + result["records_invalid"] == result["records_received"]


@pytest.mark.asyncio
async def test_phase1_pipeline_persists_snapshot(tmp_path: Path):
    pipeline = Phase1IngestionPipeline()
    snapshot = await pipeline.run_once()

    output_path = tmp_path / "phase1_snapshot.json"
    written = pipeline.persist_snapshot(snapshot, output_path)

    assert written.exists()
    assert written.read_text(encoding="utf-8").strip().startswith("{")
