"""Time-series forecasting using Prophet/LSTM with robust fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import numpy as np


@dataclass(slots=True)
class ForecastOutput:
    method: str
    backend: str
    horizon: int
    timestamps: list[str]
    values: list[float]


class TimeSeriesForecaster:
    """Forecast delay/risk series using prophet or lstm where available."""

    def _future_timestamps(self, horizon: int, freq_minutes: int) -> list[str]:
        start = datetime.now(timezone.utc)
        return [(start + timedelta(minutes=freq_minutes * (i + 1))).isoformat() for i in range(horizon)]

    def forecast(self, series: list[float], horizon: int, method: Literal["prophet", "lstm"]) -> ForecastOutput:
        if len(series) < 8:
            raise ValueError("Need at least 8 points for forecasting")
        if horizon < 1 or horizon > 256:
            raise ValueError("Horizon must be between 1 and 256")

        if method == "prophet":
            return self._forecast_prophet(series, horizon)
        return self._forecast_lstm(series, horizon)

    def _forecast_prophet(self, series: list[float], horizon: int) -> ForecastOutput:
        # Try modern package name first.
        try:
            from prophet import Prophet  # type: ignore
            import pandas as pd  # type: ignore

            df = pd.DataFrame(
                {
                    "ds": [datetime.now(timezone.utc) + timedelta(minutes=5 * i) for i in range(len(series))],
                    "y": series,
                }
            )
            model = Prophet(daily_seasonality=True, weekly_seasonality=True)
            model.fit(df)
            future = model.make_future_dataframe(periods=horizon, freq="5min")
            forecast = model.predict(future).tail(horizon)
            values = [float(v) for v in forecast["yhat"].tolist()]
            times = [str(t) for t in forecast["ds"].tolist()]
            return ForecastOutput("prophet", "prophet", horizon, times, values)
        except Exception:
            # Fallback: linear trend extrapolation when Prophet isn't available.
            arr = np.asarray(series, dtype=float)
            x = np.arange(len(arr), dtype=float)
            coeff = np.polyfit(x, arr, 1)
            preds = [float(coeff[0] * (len(arr) + i) + coeff[1]) for i in range(1, horizon + 1)]
            return ForecastOutput(
                "prophet",
                "linear-fallback",
                horizon,
                self._future_timestamps(horizon, 5),
                preds,
            )

    def _forecast_lstm(self, series: list[float], horizon: int) -> ForecastOutput:
        try:
            import tensorflow as tf  # type: ignore

            arr = np.asarray(series, dtype=float)
            mean = float(arr.mean())
            std = float(arr.std() or 1.0)
            norm = (arr - mean) / std

            window = min(16, len(norm) - 1)
            xs = []
            ys = []
            for i in range(len(norm) - window):
                xs.append(norm[i : i + window])
                ys.append(norm[i + window])
            x_train = np.array(xs).reshape((-1, window, 1))
            y_train = np.array(ys)

            model = tf.keras.Sequential(
                [
                    tf.keras.layers.Input(shape=(window, 1)),
                    tf.keras.layers.LSTM(16),
                    tf.keras.layers.Dense(1),
                ]
            )
            model.compile(optimizer="adam", loss="mse")
            model.fit(x_train, y_train, epochs=8, verbose=0)

            current = norm[-window:].reshape((1, window, 1))
            preds = []
            for _ in range(horizon):
                next_val = float(model.predict(current, verbose=0)[0][0])
                preds.append(next_val)
                tail = current.reshape((window,)).tolist()[1:] + [next_val]
                current = np.array(tail).reshape((1, window, 1))

            denorm = [float(v * std + mean) for v in preds]
            return ForecastOutput("lstm", "tensorflow", horizon, self._future_timestamps(horizon, 5), denorm)
        except Exception:
            # Fallback: autoregressive-style smoothing.
            arr = np.asarray(series, dtype=float)
            alpha = 0.4
            level = arr[0]
            for v in arr[1:]:
                level = alpha * v + (1 - alpha) * level
            preds = [float(level) for _ in range(horizon)]
            return ForecastOutput("lstm", "exp-smoothing-fallback", horizon, self._future_timestamps(horizon, 5), preds)
