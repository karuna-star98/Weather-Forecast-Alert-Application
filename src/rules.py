"""Alert / rule engine.

Each rule is a small, testable function:  (ctx, thresholds) -> Alert | None.
`ctx` is built once from the hourly/daily DataFrames, so rules never touch
raw JSON.  Add a new rule = write one function + append it to RULES.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Callable, Optional

import pandas as pd

from .config import Thresholds
from .weather_codes import STORM_CODES

SEV_ORDER = {"info": 1, "warn": 2, "critical": 3}
SEV_POINTS = {"info": 5, "warn": 15, "critical": 30}


@dataclass
class Alert:
    code: str
    label: str
    severity: str          # info | warn | critical
    message: str           # human readable, includes the numbers
    advice: str            # what to do
    when: str = ""         # time window text
    value: Optional[float] = None
    threshold: Optional[float] = None
    category: str = "general"

    def to_dict(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------- context
def build_context(hourly: pd.DataFrame, daily: pd.DataFrame, now: pd.Timestamp,
                  aqi: Optional[dict] = None) -> dict:
    """Roll the series up into the few numbers the rules need."""
    up = hourly[hourly["ts"] >= now.floor("h")].reset_index(drop=True)
    n12, n24, n48 = up.head(12), up.head(24), up.head(48)
    today = now.strftime("%Y-%m-%d")
    d = daily[daily["date"] >= today].reset_index(drop=True)
    return {"now": now, "next12": n12, "next24": n24, "next48": n48, "daily": d, "aqi": aqi}


def _hr(ts: pd.Timestamp) -> str:
    return ts.strftime("%a %H:%M")


# ------------------------------------------------------------------------- rules
def rule_rain_soon(c, t: Thresholds):
    df = c["next12"]
    if df.empty or df["precip_prob"].isna().all():
        return None
    row = df.loc[df["precip_prob"].idxmax()]
    if row["precip_prob"] >= t.rain_prob:
        return Alert("RAIN_SOON", "Rain likely in next 12h", "warn",
                     f"Rain probability peaks at {row['precip_prob']:.0f}% around {_hr(row['ts'])}.",
                     "Carry an umbrella; avoid outdoor events or cover open loads.",
                     f"next 12h (peak {_hr(row['ts'])})", float(row["precip_prob"]), t.rain_prob, "rain")


def rule_heavy_rain(c, t: Thresholds):
    d = c["daily"].head(3)
    d = d[d["rain_mm"].fillna(0) >= t.heavy_rain_day_mm]
    if not d.empty:
        r = d.iloc[0]
        sev = "critical" if r["rain_mm"] >= 2 * t.heavy_rain_day_mm else "warn"
        return Alert("HEAVY_RAIN", "Heavy rainfall expected", sev,
                     f"{r['rain_mm']:.0f} mm of rain forecast on {r['date']}.",
                     "Risk of waterlogging: reschedule transport, protect stock, avoid low-lying roads.",
                     r["date"], float(r["rain_mm"]), t.heavy_rain_day_mm, "rain")


def rule_heat_wave(c, t: Thresholds):
    d = c["daily"].head(3)
    hot = d[d["tmax_c"].fillna(-99) >= t.heat_c]
    if not hot.empty:
        r = hot.iloc[0]
        sev = "critical" if r["tmax_c"] >= t.heat_c + 4 else "warn"
        return Alert("HEAT_WAVE", f"Max temperature ≥ {t.heat_c:.0f}°C", sev,
                     f"High of {r['tmax_c']:.1f}°C forecast on {r['date']}.",
                     "Stay hydrated, avoid outdoor work 12:00-16:00, check on children and elderly.",
                     r["date"], float(r["tmax_c"]), t.heat_c, "heat")


def rule_feels_like(c, t: Thresholds):
    df = c["next24"]
    if df.empty or df["feels_c"].isna().all():
        return None
    row = df.loc[df["feels_c"].idxmax()]
    if row["feels_c"] >= t.feels_like_c:
        return Alert("HEAT_INDEX", "Dangerous 'feels-like' temperature", "critical",
                     f"Feels like {row['feels_c']:.1f}°C around {_hr(row['ts'])} (humidity {row['humidity']:.0f}%).",
                     "Heat-stroke risk: limit exertion and take cooling breaks.",
                     _hr(row["ts"]), float(row["feels_c"]), t.feels_like_c, "heat")


def rule_humidity(c, t: Thresholds):
    df = c["next24"]
    m = df[(df["humidity"] >= t.humidity_pct) & (df["temp_c"] >= t.humid_min_temp_c)]
    if len(m) >= 3:
        return Alert("HUMID_HOT", "Hot and very humid", "warn",
                     f"{len(m)} hours with humidity ≥ {t.humidity_pct:.0f}% and temp ≥ {t.humid_min_temp_c:.0f}°C.",
                     "Heat stress is higher than the thermometer shows; schedule breaks.",
                     "next 24h", float(m['humidity'].max()), t.humidity_pct, "humidity")


def rule_wind(c, t: Thresholds):
    df = c["next24"]
    if df.empty or df["wind_gust_ms"].isna().all():
        return None
    row = df.loc[df["wind_gust_ms"].idxmax()]
    g = row["wind_gust_ms"]
    if g >= t.wind_gust_ms:
        sev = "critical" if g >= 1.6 * t.wind_gust_ms else "warn"
        return Alert("WIND_HIGH", f"Wind gusts ≥ {t.wind_gust_ms:.0f} m/s", sev,
                     f"Gusts up to {g:.1f} m/s ({g*3.6:.0f} km/h) around {_hr(row['ts'])}.",
                     "Secure loose objects, avoid cranes/scaffolding/two-wheelers, expect delays.",
                     f"peak {_hr(row['ts'])}", float(g), t.wind_gust_ms, "wind")


def rule_storm(c, t: Thresholds):
    df = c["next48"]
    s = df[df["weather_code"].isin(STORM_CODES)]
    if not s.empty:
        return Alert("THUNDERSTORM", "Thunderstorm expected", "critical",
                     f"Thunderstorm conditions from {_hr(s.iloc[0]['ts'])} ({len(s)} h).",
                     "Stay indoors, unplug sensitive equipment, avoid open fields and tall trees.",
                     f"from {_hr(s.iloc[0]['ts'])}", float(len(s)), 1, "storm")


def rule_uv(c, t: Thresholds):
    d = c["daily"].head(2)
    d = d[d["uv_max"].fillna(0) >= t.uv_index]
    if not d.empty:
        r = d.iloc[0]
        return Alert("UV_HIGH", f"UV index ≥ {t.uv_index:.0f}", "warn",
                     f"UV index reaches {r['uv_max']:.1f} on {r['date']}.",
                     "Use SPF 30+, hat and sunglasses; avoid direct sun at midday.",
                     r["date"], float(r["uv_max"]), t.uv_index, "uv")


def rule_fog(c, t: Thresholds):
    df = c["next24"]
    f = df[df["visibility_km"].fillna(99) < t.fog_visibility_km]
    if not f.empty:
        r = f.loc[f["visibility_km"].idxmin()]
        return Alert("FOG", "Dense fog / low visibility", "warn",
                     f"Visibility down to {r['visibility_km']:.2f} km around {_hr(r['ts'])}.",
                     "Drive slowly with fog lights; expect flight/rail delays.",
                     _hr(r["ts"]), float(r["visibility_km"]), t.fog_visibility_km, "fog")


def rule_cold(c, t: Thresholds):
    d = c["daily"].head(3)
    d = d[d["tmin_c"].fillna(99) <= t.cold_c]
    if not d.empty:
        r = d.iloc[0]
        return Alert("COLD", f"Min temperature ≤ {t.cold_c:.0f}°C", "warn",
                     f"Low of {r['tmin_c']:.1f}°C on {r['date']}.",
                     "Protect crops from frost, dress in layers, check heating.",
                     r["date"], float(r["tmin_c"]), t.cold_c, "cold")


def rule_aqi(c, t: Thresholds):
    a = c.get("aqi")
    if a and a.get("us_aqi") is not None and a["us_aqi"] >= t.aqi_unhealthy:
        sev = "critical" if a["us_aqi"] >= 300 else "warn"
        return Alert("AQI_POOR", "Unhealthy air quality", sev,
                     f"US AQI is {a['us_aqi']:.0f} (PM2.5 {a.get('pm2_5')} µg/m³).",
                     "Wear an N95 outdoors; sensitive groups should stay indoors.",
                     "now", float(a["us_aqi"]), t.aqi_unhealthy, "air")


RULES: list[Callable] = [rule_storm, rule_heavy_rain, rule_heat_wave, rule_feels_like, rule_wind,
                         rule_rain_soon, rule_humidity, rule_uv, rule_fog, rule_cold, rule_aqi]


def evaluate(hourly: pd.DataFrame, daily: pd.DataFrame, thresholds: Optional[Thresholds] = None,
             now: Optional[pd.Timestamp] = None, aqi: Optional[dict] = None) -> list[Alert]:
    """Run every rule; return alerts sorted by severity (critical first)."""
    t = thresholds or Thresholds()
    now = now if now is not None else pd.Timestamp.now()
    ctx = build_context(hourly, daily, now, aqi)
    fired: list[Alert] = []
    for rule in RULES:
        try:
            a = rule(ctx, t)
        except Exception:      # a bad data point must never crash the engine
            a = None
        if a:
            fired.append(a)
    return sorted(fired, key=lambda a: -SEV_ORDER[a.severity])


def risk_score(alerts: list[Alert]) -> dict:
    """0-100 composite risk + level label (new feature beyond the basic brief)."""
    score = min(100, sum(SEV_POINTS[a.severity] for a in alerts))
    level = ("SEVERE" if score >= 70 else "HIGH" if score >= 45 else
             "MODERATE" if score >= 20 else "LOW")
    return {"score": score, "level": level}
