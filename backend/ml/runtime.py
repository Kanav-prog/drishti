"""Unified Phase 3 ML runtime: anomaly, forecast, explainability, versioning, drift."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backend.ml.anomaly_detector import AnomalyDetector
from backend.ml.drift_detector import DriftDetector
from backend.ml.forecasting import TimeSeriesForecaster
from backend.ml.model_registry import ModelRegistry


class Phase3MLRuntime:
    def __init__(self) -> None:
        self.anomaly = AnomalyDetector(contamination=0.02)
        self.drift = DriftDetector()
        self.forecaster = TimeSeriesForecaster()
        self.registry = ModelRegistry()

        self._isolation_trained = False

    def train_isolation_forest(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        df = pd.DataFrame(rows)
        required = {"delay", "speed", "density", "time_of_day", "route_id"}
        if not required.issubset(df.columns):
            missing = sorted(required - set(df.columns))
            raise ValueError(f"Missing required columns: {missing}")

        self.anomaly.train_isolation_forest(df)
        self.anomaly.train_statistical_profiles(df)
        self._isolation_trained = True

        metrics = {
            "samples": float(len(df)),
            "feature_delay_mean": float(df["delay"].mean()),
        }
        params = {
            "contamination": self.anomaly.contamination,
            "features": ["delay", "speed", "density", "time_of_day"],
        }

        artifact_dir = Path("models")
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / "isolation_forest_train_summary.json"
        artifact_path.write_text(json.dumps({"metrics": metrics, "params": params}, indent=2), encoding="utf-8")

        version = self.registry.register_model(
            model_name="isolation_forest",
            metrics={k: float(v) for k, v in metrics.items()},
            params=params,
            artifact_path=str(artifact_path),
        )
        return {
            "trained": True,
            "version": asdict(version),
            "metrics": metrics,
        }

    def score_anomaly(self, train_id: str, features: dict[str, Any], all_trains: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if not self._isolation_trained:
            # Bootstrap with synthetic baseline if explicit training not done yet.
            synth = pd.DataFrame(
                {
                    "route_id": ["baseline"] * 300,
                    "delay": np.random.normal(12, 6, 300),
                    "speed": np.random.normal(68, 10, 300),
                    "density": np.random.uniform(0.2, 0.8, 300),
                    "time_of_day": np.random.randint(0, 24, 300),
                }
            )
            self.anomaly.train_isolation_forest(synth)
            self.anomaly.train_statistical_profiles(synth)
            self._isolation_trained = True

        score = self.anomaly.get_anomaly_score(train_id=train_id, features=features, all_trains=all_trains)
        return asdict(score)

    def forecast_series(self, series: list[float], horizon: int, method: str) -> dict[str, Any]:
        out = self.forecaster.forecast(series=series, horizon=horizon, method=method)  # type: ignore[arg-type]

        # Track forecast outputs as target stream for drift monitoring.
        for value in out.values:
            self.drift.add_observation({"forecast_value": value}, prediction=value)

        return asdict(out)

    def explain_prediction(self, model_type: str, feature_names: list[str], train_matrix: list[list[float]], row: list[float]) -> dict[str, Any]:
        X = np.asarray(train_matrix, dtype=float)
        sample = np.asarray(row, dtype=float)
        if X.ndim != 2:
            raise ValueError("train_matrix must be 2D")
        if sample.shape[0] != X.shape[1]:
            raise ValueError("row shape mismatch")

        # SHAP (if available) on a tree surrogate.
        try:
            from sklearn.ensemble import RandomForestRegressor
            import shap  # type: ignore

            y = X[:, 0] if X.shape[1] == 1 else X.mean(axis=1)
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X, y)

            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(sample.reshape(1, -1))
            values = shap_values[0].tolist() if hasattr(shap_values, "tolist") else list(shap_values[0])
            base_value = float(explainer.expected_value)
            backend = "shap"
        except Exception:
            # Deterministic fallback: z-score style contribution proxy.
            mu = X.mean(axis=0)
            sigma = X.std(axis=0)
            sigma = np.where(sigma == 0, 1.0, sigma)
            values = ((sample - mu) / sigma).tolist()
            base_value = float(np.mean(X))
            backend = "zscore-fallback"

        pairs = []
        abs_sum = float(np.sum(np.abs(values))) or 1.0
        for name, val in zip(feature_names, values):
            pairs.append(
                {
                    "feature": name,
                    "value": float(val),
                    "direction": "increases_risk" if val >= 0 else "decreases_risk",
                    "importance_pct": float(abs(val) / abs_sum * 100),
                }
            )

        pairs.sort(key=lambda p: abs(p["value"]), reverse=True)

        return {
            "model_type": model_type,
            "backend": backend,
            "base_value": base_value,
            "top_features": pairs[:8],
            "explanation_id": hashlib.md5(json.dumps(pairs[:8]).encode("utf-8")).hexdigest(),
        }

    def observe_for_drift(self, features: dict[str, float], prediction: float) -> None:
        self.drift.add_observation(features, prediction)

    def drift_report(self) -> dict[str, Any]:
        return asdict(self.drift.get_health_report())

    def list_model_versions(self, model_name: str | None = None) -> list[dict[str, Any]]:
        return [asdict(v) for v in self.registry.list_versions(model_name=model_name)]
