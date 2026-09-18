"""
Integration tests for new data pipeline
Tests all new connectors, cleaning, features, and model loading
"""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path

# Import all new systems
from backend.data.ntes_live import NTESLiveConnector
from backend.data.crs_loader import CRSLoader
from backend.data.weather_connector import WeatherConnector
from backend.data.cleaning import DataCleaner, TrainDataCleaner
from backend.features.engineering import FeatureEngineer
from backend.features.store import FeatureStore
from backend.ml.model_loader import PersistentModelLoader
from backend.ml.drift_retraining import DriftMonitoredRetrainer
from backend.ml.ab_test import ABTestingEngine


class TestNTESLiveConnector:
    """Test live NTES train fetching"""

    @pytest.mark.asyncio
    async def test_fetch_live_trains(self):
        """Fetch live trains with fallback"""
        connector = NTESLiveConnector()
        trains = await connector.fetch_live_trains()
        
        assert len(trains) > 0, "No trains fetched"
        assert all(t.train_id for t in trains), "Train IDs missing"
        assert all(0 <= t.actual_delay_minutes <= 480 for t in trains), "Invalid delays"
        assert all(-90 <= t.current_lat <= 90 for t in trains), "Invalid latitudes"
        assert all(-180 <= t.current_lon <= 180 for t in trains), "Invalid longitudes"
        
        await connector.close()

    @pytest.mark.asyncio
    async def test_validate_train_state(self):
        """Validate train state logic"""
        connector = NTESLiveConnector()
        trains = await connector.fetch_live_trains()
        
        valid_trains = []
        for train in trains:
            is_valid = await connector.validate_train_state(train)
            if is_valid:
                valid_trains.append(train)
        
        assert len(valid_trains) > 0, "No valid trains after validation"
        await connector.close()


class TestCRSLoader:
    """Test CRS accident corpus loading"""

    def test_load_corpus(self):
        """Load accident corpus"""
        loader = CRSLoader()
        accidents = loader.load()
        
        # Accept embedded corpus (3+ records) or full corpus (40+ records)
        # Full corpus requires backend/data/accidents.csv from data.gov.in
        assert len(accidents) >= 3, f"Expected >= 3 accidents, got {len(accidents)}"
        assert all(a.date for a in accidents), "Some accidents missing dates"
        assert all(a.station_code for a in accidents), "Some accidents missing station codes"
        assert all(a.deaths >= 0 for a in accidents), "Negative deaths found"

    def test_corpus_data_quality(self):
        """Check data quality of corpus"""
        loader = CRSLoader()
        accidents = loader.load()
        
        # All should have proper structure
        for acc in accidents[:5]:  # Sample first 5
            assert hasattr(acc, 'date')
            assert hasattr(acc, 'station_code')
            assert hasattr(acc, 'deaths')
            assert hasattr(acc, 'injuries')
            assert hasattr(acc, 'primary_cause')


class TestWeatherConnector:
    """Test weather data fetching"""

    @pytest.mark.asyncio
    async def test_fetch_weather(self):
        """Fetch weather with fallback chain"""
        connector = WeatherConnector()
        
        # Test for known station
        weather = await connector.get_weather("BLSR", datetime(2023, 6, 2))
        
        assert weather is not None, "Weather fetch failed"
        assert weather.temperature_celsius > 0, "Invalid temperature"
        assert 0 <= weather.humidity_percent <= 100, "Invalid humidity"
        assert weather.rainfall_mm >= 0, "Invalid rainfall"
        assert weather.weather_condition, "Missing weather condition"
        
        await connector.close()

    @pytest.mark.asyncio
    async def test_weather_fallback(self):
        """Test weather fallback for unknown station"""
        connector = WeatherConnector()
        
        # Unknown station should return statistical weather
        weather = await connector.get_weather("XXX_UNKNOWN", datetime(2023, 6, 2))
        
        assert weather is not None, "Fallback weather failed"
        assert weather.temperature_celsius > 0
        
        await connector.close()


class TestDataCleaning:
    """Test data cleaning pipeline"""

    def test_deduplicate_accidents(self):
        """Test deduplication"""
        loader = CRSLoader()
        cleaner = DataCleaner()
        
        accidents = loader.load()
        before = len(accidents)
        
        deduped = cleaner.deduplicate_accidents(accidents)
        after = len(deduped)
        
        # After dedup, count should be <= before
        assert after <= before, f"Dedup increased count: {before} -> {after}"

    def test_normalize_timestamps(self):
        """Test timestamp normalization"""
        loader = CRSLoader()
        cleaner = DataCleaner()
        
        accidents = loader.load()
        normalized = cleaner.normalize_timestamps(accidents)
        
        # All dates should parse as ISO format
        for acc in normalized:
            try:
                datetime.fromisoformat(acc.date.replace("Z", "+00:00"))
            except ValueError:
                pytest.fail(f"Invalid ISO date: {acc.date}")

    def test_impute_weather(self):
        """Test weather imputation"""
        loader = CRSLoader()
        cleaner = DataCleaner()
        
        accidents = loader.load()
        
        for acc in accidents:
            imputed = cleaner.impute_weather(acc)
            assert imputed.weather and imputed.weather != "Unknown"

    def test_train_data_cleaner_validation(self):
        """Test train data validation"""
        connector = NTESLiveConnector()
        cleaner = TrainDataCleaner()
        
        # Create sample trains (would come from NTES in prod)
        trains = connector.REAL_TRAINS[:3]  # Sample 3 trains
        train_objs = [
            type('Train', (), {
                'train_id': t[0],
                'current_station': t[2],
                'current_lat': t[4],
                'current_lon': t[5],
                'actual_delay_minutes': 30,
            })()
            for t in trains
        ]
        
        valid, invalid = cleaner.validate_and_clean(train_objs)
        assert len(valid) > 0
        assert invalid == 0


class TestFeatureEngineering:
    """Test feature extraction"""

    def test_temporal_features(self):
        """Test temporal feature extraction"""
        engineer = FeatureEngineer()
        
        features = engineer.extract_temporal_features("2023-06-02")
        
        assert features is not None
        assert "hour_of_day" in features
        assert "day_of_week" in features
        assert "is_monsoon" in features
        assert "is_holiday" in features
        assert 0 <= features["day_of_week"] <= 6
        assert 0 <= features["hour_of_day"] <= 23

    def test_spatial_features(self):
        """Test spatial feature extraction"""
        engineer = FeatureEngineer()
        
        features = engineer.extract_spatial_features("BLSR")
        
        assert features is not None
        assert "centrality" in features
        assert "degree" in features
        assert features["centrality"] >= 0

    def test_historical_features(self):
        """Test historical accident features"""
        loader = CRSLoader()
        engineer = FeatureEngineer()
        
        accidents = loader.load()
        features = engineer.extract_historical_features("BLSR", accidents)
        
        assert features is not None
        assert "accident_frequency" in features
        assert "deaths_on_record" in features
        assert "years_since_last_accident" in features

    def test_engineer_all_features(self):
        """Test complete feature engineering"""
        loader = CRSLoader()
        engineer = FeatureEngineer()
        
        accidents = loader.load()
        if accidents:
            features = engineer.engineer_all_features(
                accidents[0],
                accidents,
                delay_minutes=45,
                weather_condition="Rainy",
                temperature=35.0,
                rainfall=20.0,
            )
            
            # Should have 20+ features
            assert len(features) >= 20, f"Only {len(features)} features extracted"
            # Should have death-related features
            assert any("death" in k.lower() for k in features.keys())


class TestFeatureStore:
    """Test Redis feature cache"""

    @pytest.mark.skipif(True, reason="Requires Redis server running locally")
    def test_cache_features(self):
        """Test feature caching (requires Redis)"""
        store = FeatureStore()
        
        test_features = {
            "delay_minutes": 45.0,
            "temperature": 35.0,
            "is_monsoon": 1.0,
        }
        
        # Cache features (uses Redis if available, fallback in-memory)
        store.cache_features("TRAIN_12001", test_features, ttl_hours=1)
        
        # Retrieve (should work with fallback)
        cached = store.get_features("TRAIN_12001")
        assert cached is not None, "Failed to retrieve cached features"
        assert cached.get("delay_minutes") == 45.0

    @pytest.mark.skipif(True, reason="Requires Redis server running locally")
    def test_delete_features(self):
        """Test feature deletion (requires Redis)"""
        store = FeatureStore()
        
        test_features = {"test": 1.0}
        store.cache_features("TEST_KEY", test_features)
        
        # Verify it was cached
        cached = store.get_features("TEST_KEY")
        assert cached is not None, "Failed to cache test features"
        
        # Delete features
        deleted = store.delete_features("TEST_KEY")
        assert deleted, "Delete operation failed"
        
        # Verify deletion
        cached_after = store.get_features("TEST_KEY")
        assert cached_after is None, "Features should be deleted"


class TestPersistentModelLoader:
    """Test model loading and training"""

    def test_load_or_train(self):
        """Test model loading/training"""
        loader = PersistentModelLoader(artifact_dir="/tmp/test_models")
        
        model = loader.load_or_train_isolation_forest()
        
        assert model is not None, "Model loading failed"
        assert hasattr(model, 'score_samples'), "Model missing score_samples method"

    def test_model_is_fresh(self):
        """Test freshness check"""
        loader = PersistentModelLoader()
        
        # After loading, should be fresh
        loader.load_or_train_isolation_forest()
        fresh = loader.model_is_fresh(max_age_days=7)
        
        # Should be fresh since just loaded
        assert fresh, "Model should be fresh after loading"


class TestDriftDetection:
    """Test drift detection system"""

    def test_drift_report_generation(self):
        """Test drift report generation"""
        retrainer = DriftMonitoredRetrainer()
        
        report = retrainer.compute_drift()
        
        assert report is not None
        assert hasattr(report, 'ks_statistic')
        assert hasattr(report, 'p_value')
        assert hasattr(report, 'drift_detected')
        assert 0 <= report.p_value <= 1


class TestABTestingEngine:
    """Test A/B testing framework"""

    def test_run_shadow_test(self):
        """Test A/B test execution"""
        engine = ABTestingEngine()
        
        result = engine.run_shadow_test(
            prediction_id="TEST_001",
            old_model_score=0.8,
            new_model_score=0.85,
            actual_outcome=True,
        )
        
        assert result is not None
        assert result.test_id == "TEST_001"
        assert result.winner in ["old", "new", "tie"]

    def test_get_test_stats(self):
        """Test statistics computation"""
        engine = ABTestingEngine()
        
        # Run multiple tests
        for i in range(50):
            engine.run_shadow_test(
                prediction_id=f"TEST_{i}",
                old_model_score=0.7 if i % 2 == 0 else 0.8,
                new_model_score=0.75,
                actual_outcome=True if i % 3 == 0 else False,
            )
        
        stats = engine.get_test_stats()
        
        assert stats["total_tests"] == 50
        assert 0 <= stats["new_model_win_rate"] <= 1
        assert stats["recommendation"]
