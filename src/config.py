"""Central configuration: paths, mode, and alert thresholds (env-overridable)."""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path

try:  # .env is optional
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("WEATHER_DB", ROOT / "db" / "weather.db"))
SCHEMA_PATH = ROOT / "db" / "schema.sql"
OUTPUT_DIR = ROOT / "outputs"
REPORT_DIR = ROOT / "reports"
DATA_DIR = ROOT / "data"


def default_mode() -> str:
    return os.getenv("WEATHER_MODE", "simulate").lower()


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


@dataclass
class Thresholds:
    """All alert limits in one place. Units: °C, %, m/s, mm, km."""
    rain_prob: float = 60.0         # % chance in next 12 h
    heavy_rain_day_mm: float = 50.0  # mm in one day
    heat_c: float = 40.0            # daily max
    feels_like_c: float = 45.0      # heat-index style "feels like"
    humidity_pct: float = 85.0      # combined with warm temp
    humid_min_temp_c: float = 30.0
    wind_gust_ms: float = 15.0      # ~54 km/h
    uv_index: float = 8.0
    fog_visibility_km: float = 1.0
    cold_c: float = 5.0             # daily min
    aqi_unhealthy: float = 150.0    # US AQI

    @classmethod
    def from_env(cls) -> "Thresholds":
        return cls(
            rain_prob=_f("THRESH_RAIN_PROB", 60),
            heat_c=_f("THRESH_HEAT_C", 40),
            wind_gust_ms=_f("THRESH_WIND_GUST_MS", 15),
        )
