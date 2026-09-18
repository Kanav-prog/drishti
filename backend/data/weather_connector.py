"""
Weather Data Connector
Historical + forecast weather via free APIs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class WeatherRecord:
    """Weather data for a location + date"""
    date: str
    temperature_celsius: float
    humidity_percent: float
    rainfall_mm: float
    wind_speed_kmh: float
    visibility_km: float
    weather_condition: str  # Clear, Rain, Fog, Cloudy, etc.


class WeatherConnector:
    """Multi-source weather connector with fallback"""

    # Station coordinates (lat, lon)
    STATION_COORDS = {
        "BLSR": (21.5, 86.8),
        "FZD": (27.4, 78.0),
        "BPL": (23.1, 77.4),
        "NDLS": (28.6, 77.2),
        "HWH": (22.5, 88.3),
        "MAS": (13.0, 80.2),
        "BOMBAY": (18.9, 72.8),
        "NGP": (21.1, 79.0),
    }

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=5.0)

    async def get_weather(
        self, station_code: str, date: datetime
    ) -> WeatherRecord:
        """Get weather: openmeteo → wttr.in → statistical"""

        coords = self.STATION_COORDS.get(station_code)
        if not coords:
            logger.warning(f"Unknown station: {station_code}")
            return self._generate_statistical_weather(station_code, date)

        # Try openmeteo (free, no key needed)
        weather = await self._fetch_openmeteo(coords, date)
        if weather:
            logger.debug(f"[WEATHER] {station_code} from openmeteo: {weather.weather_condition}")
            return weather

        # Fallback: wttr.in (simple)
        weather = await self._fetch_wttr_in(coords, date)
        if weather:
            logger.debug(f"[WEATHER] {station_code} from wttr.in: {weather.weather_condition}")
            return weather

        # Final fallback: statistical
        logger.debug(f"[WEATHER] {station_code} statistical (fallback)")
        return self._generate_statistical_weather(station_code, date)

    async def _fetch_openmeteo(
        self, coords: tuple, date: datetime
    ) -> Optional[WeatherRecord]:
        """Fetch from openmeteo.com (free, no auth)"""
        try:
            lat, lon = coords
            date_str = date.strftime("%Y-%m-%d")

            # openmeteo historical API (free)
            url = (
                f"https://archive-api.open-meteo.com/v1/archive?"
                f"latitude={lat}&longitude={lon}&"
                f"start_date={date_str}&end_date={date_str}&"
                f"hourly=temperature_2m,relative_humidity_2m,precipitation,weather_code"
            )

            resp = await self.client.get(url)
            if resp.status_code != 200:
                return None

            data = resp.json()
            hourly = data.get("hourly", {})

            if not hourly.get("temperature_2m"):
                return None

            # Average over the day
            temps = hourly["temperature_2m"]
            humidity = hourly.get("relative_humidity_2m", [50] * len(temps))
            precip = hourly.get("precipitation", [0] * len(temps))

            temp = np.mean(temps) if temps else 25.0
            humidity_pct = np.mean(humidity) if humidity else 60.0
            rainfall = sum(precip) if precip else 0.0

            condition = "Clear" if rainfall < 5 else "Rainy"

            return WeatherRecord(
                date=date_str,
                temperature_celsius=float(temp),
                humidity_percent=float(humidity_pct),
                rainfall_mm=float(rainfall),
                wind_speed_kmh=15.0,
                visibility_km=10.0,
                weather_condition=condition,
            )
        except Exception as e:
            logger.debug(f"[WEATHER] openmeteo failed: {e}")
            return None

    async def _fetch_wttr_in(
        self, coords: tuple, date: datetime
    ) -> Optional[WeatherRecord]:
        """Fallback: wttr.in (simple JSON endpoint)"""
        try:
            lat, lon = coords
            url = f"https://wttr.in/{lat},{lon}?format=j1"

            resp = await self.client.get(url)
            if resp.status_code != 200:
                return None

            data = resp.json()
            current = data.get("current_condition", [{}])[0]

            return WeatherRecord(
                date=date.strftime("%Y-%m-%d"),
                temperature_celsius=float(current.get("temp_C", 25)),
                humidity_percent=float(current.get("humidity", 60)),
                rainfall_mm=float(current.get("precipMM", 0)),
                wind_speed_kmh=float(current.get("windspeedKmph", 15)),
                visibility_km=float(current.get("visibility", 10)),
                weather_condition=current.get("weatherDesc", [{}])[0].get("value", "Clear"),
            )
        except Exception as e:
            logger.debug(f"[WEATHER] wttr.in failed: {e}")
            return None

    def _generate_statistical_weather(
        self, station_code: str, date: datetime
    ) -> WeatherRecord:
        """Statistical fallback based on station + month"""
        month = date.month

        # India meteorological patterns
        if 6 <= month <= 9:  # Monsoon
            temp = 28.0
            rainfall = np.random.uniform(20, 100)
            condition = "Rainy" if np.random.random() > 0.3 else "Cloudy"
        elif 3 <= month <= 5:  # Summer
            temp = 38.0
            rainfall = np.random.uniform(0, 10)
            condition = "Clear"
        else:  # Winter
            temp = 22.0
            rainfall = np.random.uniform(0, 5)
            condition = "Clear"

        return WeatherRecord(
            date=date.strftime("%Y-%m-%d"),
            temperature_celsius=temp,
            humidity_percent=60.0,
            rainfall_mm=rainfall,
            wind_speed_kmh=15.0,
            visibility_km=10.0,
            weather_condition=condition,
        )

    async def close(self):
        """Cleanup"""
        await self.client.aclose()
