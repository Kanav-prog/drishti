"""Phase 3 ML runtime tests: anomaly, forecasting, explainability, registry, drift."""

from backend.ml.runtime import Phase3MLRuntime


def _runtime() -> Phase3MLRuntime:
    return Phase3MLRuntime()


def test_train_and_version_isolation_forest():
    rt = _runtime()
    rows = []
    for i in range(50):
        rows.append(
            {
                "delay": 8 + (i % 7),
                "speed": 55 + (i % 15),
                "density": 0.2 + ((i % 10) / 20),
                "time_of_day": i % 24,
                "route_id": f"r{i % 3}",
            }
        )

    out = rt.train_isolation_forest(rows)
    assert out["trained"] is True
    assert out["version"]["model_name"] == "isolation_forest"


def test_anomaly_score_output_shape():
    rt = _runtime()
    result = rt.score_anomaly(
        train_id="12001",
        features={
            "delay": 35,
            "speed": 44,
            "density": 0.83,
            "time_of_day": 3,
            "route_id": "r1",
        },
    )
    assert "combined_score" in result
    assert 0 <= result["combined_score"] <= 100


def test_forecast_prophet_or_fallback():
    rt = _runtime()
    series = [10, 12, 13, 14, 11, 15, 16, 17, 18, 17, 16, 19]
    out = rt.forecast_series(series=series, horizon=6, method="prophet")
    assert out["method"] == "prophet"
    assert len(out["values"]) == 6
    assert len(out["timestamps"]) == 6


def test_forecast_lstm_or_fallback():
    rt = _runtime()
    series = [18, 16, 15, 14, 16, 18, 20, 22, 21, 20, 19, 18]
    out = rt.forecast_series(series=series, horizon=5, method="lstm")
    assert out["method"] == "lstm"
    assert len(out["values"]) == 5


def test_explain_prediction_shap_or_fallback():
    rt = _runtime()
    feature_names = ["delay", "speed", "density"]
    train_matrix = [
        [10, 70, 0.3],
        [12, 65, 0.35],
        [14, 60, 0.5],
        [20, 50, 0.7],
        [25, 45, 0.9],
    ]
    row = [24, 43, 0.92]

    out = rt.explain_prediction("risk_regressor", feature_names, train_matrix, row)
    assert "backend" in out
    assert len(out["top_features"]) >= 1


def test_drift_observe_and_report():
    rt = _runtime()
    for i in range(220):
        rt.observe_for_drift(
            features={"delay": float(10 + (i % 5)), "density": float(0.3 + (i % 4) * 0.1)},
            prediction=float(0.2 + (i % 5) * 0.1),
        )

    report = rt.drift_report()
    assert "overall_health" in report
    assert "health_score" in report
