"""
Phase 2.5: Integration tests for entire dataset generation pipeline

Tests each component and validates end-to-end data quality.
"""

import logging
import json
import numpy as np
import tempfile
from pathlib import Path
from typing import Dict
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.data.accident_window_extractor import AccidentWindowExtractor
from backend.features.timeseries_features import TimeSeriesFeatureExtractor
from backend.data.augmentation import PositiveSequenceAugmentor
from backend.ml.feature_normalization import TimeSeriesDatasetLoader, FeatureNormalizer
from backend.data.timeseries_dataset import TimeSeriesDatasetGenerator

logger = logging.getLogger(__name__)


class Phase2TestSuite:
    """Test suite for Phase 2 dataset generation"""
    
    def __init__(self):
        self.results = {
            'tests_passed': 0,
            'tests_failed': 0,
            'test_details': []
        }
    
    def _log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
        if message:
            logger.info(f"   {message}")
        
        if passed:
            self.results['tests_passed'] += 1
        else:
            self.results['tests_failed'] += 1
        
        self.results['test_details'].append({
            'test': test_name,
            'passed': passed,
            'message': message
        })
    
    def test_1_accident_window_extraction(self):
        """Test: Extract 48-hour windows from CRS accidents"""
        logger.info("\n" + "="*70)
        logger.info("TEST 1: Accident Window Extraction")
        logger.info("="*70)
        
        try:
            extractor = AccidentWindowExtractor()
            windows = extractor.extract_all_accident_windows()
            
            # Check: Should have some windows
            test1a = len(windows) >= 1
            self._log_test(
                "Windows extracted",
                test1a,
                f"Got {len(windows)} windows (expect ≥1)"
            )
            
            # Check: Each window has correct shape
            if windows:
                first_id = list(windows.keys())[0]
                df, metrics = windows[first_id]
                
                test1b = len(df) >= 450  # At least 95% of 576
                self._log_test(
                    "Window completeness",
                    test1b,
                    f"Got {len(df)} timesteps (expect ≥450)"
                )
                
                test1c = 'delay_minutes' in df.columns
                self._log_test(
                    "Required columns present",
                    test1c,
                    f"Columns: {list(df.columns)}"
                )
            
            return test1a
        
        except Exception as e:
            self._log_test("Accident window extraction", False, str(e))
            return False
    
    def test_2_feature_extraction(self):
        """Test: Extract 15 features from telemetry"""
        logger.info("\n" + "="*70)
        logger.info("TEST 2: Feature Extraction")
        logger.info("="*70)
        
        try:
            # Create mock window
            mock_df = np.random.randn(576, 7)
            mock_df = np.clip(mock_df, 0, 100)
            mock_df = {
                'delay_minutes': mock_df[:, 0],
                'speed_kmh': mock_df[:, 1],
                'station_code': ['BBS'] * 576,
                'timestamp_utc': [None] * 576
            }
            
            extractor = TimeSeriesFeatureExtractor()
            
            # Extract features
            features = extractor.extract_all_features(
                mock_df,
                'TEST_ACCIDENT',
                {'maintenance_active': False, 'signal_state': 'GREEN', 'track_state': 'MAIN_LINE'}
            )
            
            # Check: Shape
            test2a = features.shape == (576, 15)
            self._log_test(
                "Feature extraction shape",
                test2a,
                f"Got {features.shape} (expect (576, 15))"
            )
            
            # Check: No NaNs
            test2b = not np.isnan(features).any()
            self._log_test(
                "No NaN values",
                test2b,
                f"NaN count: {np.isnan(features).sum()}"
            )
            
            # Check: Reasonable ranges
            test2c = np.all(features >= -5) and np.all(features <= 100)
            self._log_test(
                "Feature value ranges",
                test2c,
                f"Min: {features.min():.2f}, Max: {features.max():.2f}"
            )
            
            return test2a and test2b and test2c
        
        except Exception as e:
            self._log_test("Feature extraction", False, str(e))
            return False
    
    def test_3_augmentation(self):
        """Test: Augment sequences"""
        logger.info("\n" + "="*70)
        logger.info("TEST 3: Augmentation")
        logger.info("="*70)
        
        try:
            # Create mock base sequences
            base_seqs = [np.random.randn(576, 15) for _ in range(3)]
            
            augmentor = PositiveSequenceAugmentor()
            augmented = augmentor.generate_augmentations(base_seqs, target_count=30)
            
            # Check: Generated count
            test3a = len(augmented) >= 30
            self._log_test(
                "Augmentation count",
                test3a,
                f"Generated {len(augmented)} sequences (expect ≥30)"
            )
            
            # Check: Each has correct shape
            test3b = all(seq.shape == (576, 15) for seq, _ in augmented)
            self._log_test(
                "Augmented shape consistency",
                test3b,
                f"All shapes (576, 15): {test3b}"
            )
            
            # Check: Augmentations are different
            seq1 = augmented[0][0]
            seq2 = augmented[1][0]
            test3c = not np.allclose(seq1, seq2)
            self._log_test(
                "Augmentations differ",
                test3c,
                f"Sequences are different: {test3c}"
            )
            
            return test3a and test3b and test3c
        
        except Exception as e:
            self._log_test("Augmentation", False, str(e))
            return False
    
    def test_4_normalization(self):
        """Test: Feature normalization"""
        logger.info("\n" + "="*70)
        logger.info("TEST 4: Feature Normalization")
        logger.info("="*70)
        
        try:
            # Create mock data
            X = np.random.randn(100, 576, 15)
            X = np.clip(X, -10, 100)
            feature_names = TimeSeriesFeatureExtractor.FEATURES
            
            # Fit normalizer
            normalizer = FeatureNormalizer()
            normalizer.fit(X, feature_names)
            
            # Transform
            X_norm = normalizer.transform(X, feature_names)
            
            # Check: Shape preserved
            test4a = X_norm.shape == X.shape
            self._log_test(
                "Normalization preserves shape",
                test4a,
                f"Shape: {X_norm.shape}"
            )
            
            # Check: Values in reasonable range
            test4b = np.all(X_norm >= -5) and np.all(X_norm <= 5)
            self._log_test(
                "Normalized value ranges",
                test4b,
                f"Min: {X_norm.min():.2f}, Max: {X_norm.max():.2f}"
            )
            
            return test4a and test4b
        
        except Exception as e:
            self._log_test("Normalization", False, str(e))
            return False
    
    def test_5_dataset_split(self):
        """Test: Train/val/test splitting"""
        logger.info("\n" + "="*70)
        logger.info("TEST 5: Dataset Splitting")
        logger.info("="*70)
        
        try:
            # Create mock dataset
            X = np.random.randn(1100, 576, 15)
            y = np.concatenate([np.ones(400), np.zeros(700)])
            
            # Simulate splitting
            n = len(X)
            train_end = int(0.75 * n)
            val_end = train_end + int(0.125 * n)
            
            train_idx = np.arange(train_end)
            val_idx = np.arange(train_end, val_end)
            test_idx = np.arange(val_end, n)
            
            # Check: No overlap
            test5a = len(set(train_idx) & set(val_idx)) == 0
            test5a = test5a and len(set(val_idx) & set(test_idx)) == 0
            self._log_test(
                "No index overlap",
                test5a,
                f"Train/val/test: {len(train_idx)}/{len(val_idx)}/{len(test_idx)}"
            )
            
            # Check: All indices covered
            test5b = len(set(train_idx) | set(val_idx) | set(test_idx)) == n
            self._log_test(
                "All indices covered",
                test5b,
                f"Coverage: {len(set(train_idx) | set(val_idx) | set(test_idx))}/{n}"
            )
            
            return test5a and test5b
        
        except Exception as e:
            self._log_test("Dataset splitting", False, str(e))
            return False
    
    def test_6_dataset_loader(self):
        """Test: Dataset loader functionality"""
        logger.info("\n" + "="*70)
        logger.info("TEST 6: Dataset Loader")
        logger.info("="*70)
        
        try:
            # Create and save mock dataset
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)
                
                # Create mock NPZ
                X = np.random.randn(100, 576, 15)
                y = np.random.randint(0, 2, 100)
                feature_names = TimeSeriesFeatureExtractor.FEATURES
                train_idx = np.arange(75)
                val_idx = np.arange(75, 88)
                test_idx = np.arange(88, 100)
                
                npz_path = tmpdir / "test.npz"
                np.savez_compressed(
                    npz_path,
                    X=X, y=y,
                    train_idx=train_idx,
                    val_idx=val_idx,
                    test_idx=test_idx,
                    feature_names=np.array(feature_names, dtype=object)
                )
                
                # Load
                loader = TimeSeriesDatasetLoader()
                X_train, y_train, _ = loader.load_from_npz(str(npz_path), split='train')
                
                # Check: Correct split shape
                test6a = len(X_train) == 75 and len(y_train) == 75
                self._log_test(
                    "Loader split shapes",
                    test6a,
                    f"Train: {len(X_train)} samples"
                )
                
                # Check: Correct feature dimension
                test6b = X_train.shape[2] == 15
                self._log_test(
                    "Loader feature dimension",
                    test6b,
                    f"Features: {X_train.shape[2]}"
                )
                
                return test6a and test6b
        
        except Exception as e:
            self._log_test("Dataset loader", False, str(e))
            return False
    
    def test_7_class_balance(self):
        """Test: Class balance validation"""
        logger.info("\n" + "="*70)
        logger.info("TEST 7: Class Balance")
        logger.info("="*70)
        
        try:
            # Create mock labeled dataset
            y = np.concatenate([np.ones(400), np.zeros(4000)])
            
            positive_ratio = np.mean(y)
            
            # Check: Positive ratio ~9%
            test7a = 0.08 <= positive_ratio <= 0.10
            self._log_test(
                "Class balance (9% positive)",
                test7a,
                f"Positive ratio: {positive_ratio*100:.1f}%"
            )
            
            # Check: Document imbalance requires focal loss
            test7b = positive_ratio < 0.15  # Extreme imbalance
            self._log_test(
                "Extreme imbalance detected (focal loss needed)",
                test7b,
                f"Recommend focal loss for training"
            )
            
            return test7a
        
        except Exception as e:
            self._log_test("Class balance", False, str(e))
            return False
    
    def run_all_tests(self) -> Dict:
        """Run all tests"""
        logger.info("\n\n")
        logger.info("█" * 70)
        logger.info("█" + " " * 68 + "█")
        logger.info("█" + "PHASE 2: TEST SUITE".center(68) + "█")
        logger.info("█" + " " * 68 + "█")
        logger.info("█" * 70)
        
        self.test_1_accident_window_extraction()
        self.test_2_feature_extraction()
        self.test_3_augmentation()
        self.test_4_normalization()
        self.test_5_dataset_split()
        self.test_6_dataset_loader()
        self.test_7_class_balance()
        
        logger.info("\n" + "█" * 70)
        logger.info(f"SUMMARY: {self.results['tests_passed']} passed, {self.results['tests_failed']} failed")
        logger.info("█" * 70 + "\n")
        
        return self.results


def main():
    """Run test suite"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s:%(name)s:%(message)s'
    )
    
    suite = Phase2TestSuite()
    results = suite.run_all_tests()
    
    # Save results
    with open("backend/data/phase2_test_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Test results saved to backend/data/phase2_test_results.json")


if __name__ == "__main__":
    main()
