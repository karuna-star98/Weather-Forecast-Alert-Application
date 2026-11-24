"""Live weather provider: Open-Meteo (free, NO API key needed).

Responsibilities
  1. geocode()         city name  -> lat/lon/timezone
  2. fetch_forecast()  lat/lon    -> raw JSON payload (with retry/back-off)
  3. fetch_air_quality()          -> optional AQI block
  4. normalize()       raw JSON   -> current dict + hourly/daily DataFrames
The simulator produces the SAME payload shape, so normalize() serves both modes.
"""
from __future__ import annotations
import time
from typing import Optional

import pandas as pd
import requests

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

HOURLY_VARS = ("temperature_2m,apparent_temperature,relative_humidity_2m,precipitation_probability,"
               "precipitation,weather_code,wind_speed_10m,wind_gusts_10m,cloud_cover,uv_index,"
               "pressure_msl,visibility")
DAILY_VARS = ("temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
              "wind_speed_10m_max,uv_index_max,sunrise,sunset")
CURRENT_VARS = ("temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,"
                "cloud_cover,pressure_msl,wind_speed_10m,wind_gusts_10m")


class WeatherAPIError(RuntimeError):
    """Raised for any provider problem (network, bad city, bad payload)."""


def _get(url: str, params: dict, retries: int = 3, timeout: int = 15) -> dict:
    """GET with exponential back-off on network errors / HTTP 5xx."""
    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code >= 500:
                raise requests.HTTPError(f"server error {r.status_code}")
            if r.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            time.sleep(0.8 * (2 ** attempt))
    raise WeatherAPIError(f"Could not reach weather service: {last}")


def geocode(city: str) -> dict:
    data = _get(GEO_URL, {"name": city, "count": 1, "language": "en", "format": "json"})
    results = data.get("results") or []
    if not results:
        raise WeatherAPIError(f"City not found: '{city}'. Check the spelling.")
    r = results[0]
    label = ", ".join(x for x in (r.get("name"), r.get("admin1"), r.get("country_code")) if x)
    return {"name": label, "lat": r["latitude"], "lon": r["longitude"],
            "tz": r.get("timezone", "UTC")}


def fetch_forecast(lat: float, lon: float, days: int = 7) -> dict:
    return _get(FORECAST_URL, {
        "latitude": lat, "longitude": lon, "hourly": HOURLY_VARS, "daily": DAILY_VARS,
        "current": CURRENT_VARS, "wind_speed_unit": "ms", "timezone": "auto",
        "forecast_days": max(1, min(days, 16)),
    })


def fetch_air_quality(lat: float, lon: float) -> Optional[dict]:
    """AQI is optional - never let it break the main flow."""
    try:
        d = _get(AQ_URL, {"latitude": lat, "longitude": lon,
                          "current": "us_aqi,pm2_5,pm10", "timezone": "auto"}, retries=2)
        c = d.get("current", {})
        if c.get("us_aqi") is None:
            return None
        return {"us_aqi": c["us_aqi"], "pm2_5": c.get("pm2_5"), "pm10": c.get("pm10")}
    except WeatherAPIError:
        return None


# ---------------------------------------------------------------- normalisation
def _col(block: dict, key: str, n: int):
    """Return list for key or a list of None (handles missing/optional fields)."""
    v = block.get(key)
    return v if v is not None else [None] * n


def normalize(payload: dict) -> dict:
    """Raw Open-Meteo-shaped JSON -> {'current': dict, 'hourly': df, 'daily': df}."""
    try:
        h, d, c = payload["hourly"], payload["daily"], payload.get("current", {})
        n = len(h["time"])
        hourly = pd.DataFrame({
            "ts": pd.to_datetime(h["time"]),
            "temp_c": _col(h, "temperature_2m", n),
            "feels_c": _col(h, "apparent_temperature", n),
            "humidity": _col(h, "relative_humidity_2m", n),
            "wind_ms": _col(h, "wind_speed_10m", n),
            "wind_gust_ms": _col(h, "wind_gusts_10m", n),
            "precip_mm": _col(h, "precipitation", n),
            "precip_prob": _col(h, "precipitation_probability", n),
            "cloud_pct": _col(h, "cloud_cover", n),
            "uv": _col(h, "uv_index", n),
            "pressure_hpa": _col(h, "pressure_msl", n),
            "visibility_km": [None if v is None else v / 1000.0 for v in _col(h, "visibility", n)],
            "weather_code": _col(h, "weather_code", n),
        })
        m = len(d["time"])
        daily = pd.DataFrame({
            "date": pd.to_datetime(d["time"]).strftime("%Y-%m-%d"),
            "tmax_c": _col(d, "temperature_2m_max", m),
            "tmin_c": _col(d, "temperature_2m_min", m),
            "rain_mm": _col(d, "precipitation_sum", m),
            "rain_prob": _col(d, "precipitation_probability_max", m),
            "wind_max_ms": _col(d, "wind_speed_10m_max", m),
            "uv_max": _col(d, "uv_index_max", m),
            "sunrise": _col(d, "sunrise", m),
            "sunset": _col(d, "sunset", m),
        })
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherAPIError(f"Unexpected weather payload: {exc}") from exc

    num = hourly.columns.difference(["ts"])
    hourly[num] = hourly[num].apply(pd.to_numeric, errors="coerce")
    hourly = hourly.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)

    current = {
        "ts": c.get("time"), "temp_c": c.get("temperature_2m"), "feels_c": c.get("apparent_temperature"),
        "humidity": c.get("relative_humidity_2m"), "wind_ms": c.get("wind_speed_10m"),
        "wind_gust_ms": c.get("wind_gusts_10m"), "precip_mm": c.get("precipitation"),
        "cloud_pct": c.get("cloud_cover"), "pressure_hpa": c.get("pressure_msl"),
        "weather_code": c.get("weather_code"),
    }
    return {"current": current, "hourly": hourly, "daily": daily}
