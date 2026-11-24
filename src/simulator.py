"""Virtual weather simulator (works 100% offline).

Generates a realistic Open-Meteo-shaped payload for a city so the *whole*
pipeline (parse -> analyse -> alert -> report -> chart) can be demonstrated
without internet or API keys.  Output is deterministic per (city, scenario, day)
so screenshots and tests are reproducible.

Scenarios: auto | normal | heatwave | monsoon | storm | fog | cold
"""
from __future__ import annotations
import math
import zlib
import datetime as dt
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np

SCENARIOS = ["auto", "normal", "heatwave", "monsoon", "storm", "fog", "cold"]

# name: lat, lon, tz, mean_temp, diurnal_amp, humidity_base, rain_day_prob, wind, uv_peak, default_scenario
CITY_PROFILES = {
    "Delhi":     (28.61, 77.21, "Asia/Kolkata", 31, 7.0, 40, 0.15, 3.0, 9.0, "heatwave"),
    "Mumbai":    (19.08, 72.88, "Asia/Kolkata", 29, 3.0, 75, 0.50, 5.0, 8.0, "monsoon"),
    "Bhusawal":  (21.05, 75.78, "Asia/Kolkata", 32, 7.0, 35, 0.12, 3.0, 9.0, "heatwave"),
    "Chennai":   (13.08, 80.27, "Asia/Kolkata", 31, 3.5, 70, 0.30, 4.5, 9.0, "normal"),
    "Kolkata":   (22.57, 88.36, "Asia/Kolkata", 30, 4.0, 72, 0.40, 3.5, 8.0, "storm"),
    "Bengaluru": (12.97, 77.59, "Asia/Kolkata", 25, 5.0, 60, 0.35, 3.5, 8.0, "normal"),
    "Hyderabad": (17.39, 78.49, "Asia/Kolkata", 29, 6.0, 50, 0.25, 3.5, 9.0, "normal"),
    "Pune":      (18.52, 73.86, "Asia/Kolkata", 27, 7.0, 55, 0.30, 3.5, 9.0, "normal"),
    "Jaipur":    (26.91, 75.79, "Asia/Kolkata", 30, 8.0, 35, 0.10, 3.5, 9.0, "heatwave"),
    "Shimla":    (31.10, 77.17, "Asia/Kolkata", 12, 6.0, 60, 0.30, 3.0, 7.0, "fog"),
    "Dubai":     (25.20, 55.27, "Asia/Dubai", 33, 6.0, 45, 0.02, 4.0, 10.0, "heatwave"),
    "London":    (51.51, -0.13, "Europe/London", 11, 4.0, 75, 0.45, 5.0, 3.0, "normal"),
}
_LOOKUP = {k.lower(): k for k in CITY_PROFILES}


def known_cities() -> list[str]:
    return list(CITY_PROFILES)


def _tz(name: str):
    try:
        return ZoneInfo(name)
    except Exception:  # tzdata missing -> fall back to UTC
        return dt.timezone.utc


def sim_geocode(city: str) -> dict:
    """Resolve a city offline. Unknown names get stable pseudo-coordinates."""
    key = _LOOKUP.get(city.strip().lower())
    if key:
        lat, lon, tz = CITY_PROFILES[key][:3]
        return {"name": key, "lat": lat, "lon": lon, "tz": tz}
    h = zlib.crc32(city.strip().lower().encode())
    return {"name": city.strip().title(), "lat": round(8 + (h % 2800) / 100, 2),
            "lon": round(70 + ((h >> 8) % 1800) / 100, 2), "tz": "Asia/Kolkata"}


def _profile(city: str):
    key = _LOOKUP.get(city.strip().lower())
    if key:
        return CITY_PROFILES[key]
    h = zlib.crc32(city.strip().lower().encode())
    return (0, 0, "Asia/Kolkata", 24 + h % 12, 5 + h % 4, 40 + h % 40, 0.15 + (h % 30) / 100,
            3 + (h % 3), 8.0, "normal")


def simulate_forecast(city: str, scenario: str = "auto", days: int = 7,
                      now: Optional[dt.datetime] = None) -> dict:
    """Return an Open-Meteo-shaped payload (units: C, %, m/s, mm, m)."""
    lat, lon, tzname, mean, amp, hum0, p_rain, wind0, uv_peak, default_sc = _profile(city)
    sc = default_sc if scenario in (None, "auto") else scenario
    tz = _tz(tzname)
    now = (now or dt.datetime.now(tz)).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    start = now.replace(hour=0)
    n = days * 24
    seed = zlib.crc32(f"{city.lower()}|{sc}|{start.date()}".encode())
    rng = np.random.default_rng(seed)

    # ---- scenario knobs -----------------------------------------------------
    t_shift, rain_boost, wind_boost, fog, storm_day = 0.0, 0.0, 0.0, False, -1
    if sc == "heatwave": t_shift = 5.0; p_rain *= 0.3
    elif sc == "monsoon": t_shift = -2.0; rain_boost = 0.45; hum0 = max(hum0, 85); wind_boost = 2.0
    elif sc == "storm": rain_boost = 0.25; wind_boost = 6.0; storm_day = 1
    elif sc == "fog": fog = True; t_shift = -3.0; hum0 = max(hum0, 85)
    elif sc == "cold": t_shift = -(mean - 3)

    # ---- day-level weather: offset + rain events ----------------------------------
    day_off = np.cumsum(rng.normal(0, 0.9, days)) - 0.5
    rain_events = np.zeros(n); storm_hours = np.zeros(n, bool)
    for d in range(days):
        pr = min(0.95, p_rain + rain_boost)
        if sc == "monsoon" and d < 4: pr = 0.95  # make the demo clearly rainy
        if rng.random() < pr or d == storm_day:
            s = d * 24 + int(rng.integers(12, 20) if sc != "monsoon" else rng.integers(2, 16))
            length = int(rng.integers(3, 8))
            inten = float(rng.uniform(1.5, 6.0) * (2.5 if sc in ("monsoon", "storm") else 1))
            for k in range(length):
                if s + k < n: rain_events[s + k] = inten * (1 - abs(k - length / 2) / length) + rng.uniform(0, .5)
            if sc == "storm" and d == storm_day:
                for k in range(length):
                    if s + k < n: storm_hours[s + k] = True

    hours = np.arange(n); hod = hours % 24; dayi = hours // 24
    temp = (mean + t_shift + day_off[dayi] + amp * np.sin(2 * math.pi * (hod - 9) / 24)
            + rng.normal(0, 0.4, n) - 0.35 * rain_events)
    # smooth rain-probability ramp before/after events
    ev = (rain_events > 0.2).astype(float)
    ramp = np.convolve(ev, np.array([.15, .3, .5, .8, 1, .7, .4, .2]), mode="same")
    prob = np.clip(8 + 100 * p_rain * .6 + 85 * np.clip(ramp, 0, 1) + rng.normal(0, 4, n), 0, 100)
    prob = np.where(rain_events > 0.2, np.maximum(prob, 88), prob)
    hum = np.clip(hum0 - 2.0 * (temp - mean - t_shift) + 12 * np.clip(ramp, 0, 1) + rng.normal(0, 3, n), 12, 100)
    cloud = np.clip(25 + 60 * np.clip(ramp, 0, 1) + rng.normal(0, 10, n) + (20 if sc == "monsoon" else 0), 0, 100)
    wind = np.clip(wind0 + wind_boost * 0.4 + 1.5 * np.sin(2 * math.pi * (hod - 10) / 24) + rng.normal(0, .6, n), .3, None)
    gust = wind * rng.uniform(1.3, 1.7, n)
    if sc == "storm":
        gust = np.where(storm_hours, np.maximum(gust, rng.uniform(16, 24, n)), gust)
        wind = np.where(storm_hours, np.maximum(wind, 10), wind)
    daylight = np.clip(np.sin(math.pi * (hod - 6) / 12), 0, None)
    uv = np.round(uv_peak * daylight * (1 - .6 * cloud / 100), 1)
    pressure = 1010 - (6 if sc in ("monsoon", "storm") else 0) - 2 * np.clip(ramp, 0, 1) + rng.normal(0, .8, n)
    vis = np.clip(24000 - 2500 * rain_events + rng.normal(0, 800, n), 1500, 30000)
    if fog:
        vis = np.where((hod >= 2) & (hod <= 8), rng.uniform(250, 800, n), vis)
    rain_mm = np.round(rain_events, 1)

    ah = hum / 100 * 6.105 * np.exp(17.27 * temp / (237.7 + temp))   # apparent temperature
    feels = temp + 0.33 * ah - 0.70 * wind - 4.0

    code = np.zeros(n, int)
    code = np.where(cloud > 40, 1, code); code = np.where(cloud > 60, 2, code); code = np.where(cloud > 85, 3, code)
    code = np.where(rain_mm > 0.2, 61, code); code = np.where(rain_mm > 2.5, 63, code)
    code = np.where(rain_mm > 6, 65, code); code = np.where(storm_hours, 95, code)
    code = np.where(vis < 1000, 45, code)

    times = [(start + dt.timedelta(hours=int(i))).strftime("%Y-%m-%dT%H:%M") for i in hours]
    r1 = lambda a, k=1: [round(float(x), k) for x in a]
    hourly = {"time": times, "temperature_2m": r1(temp), "apparent_temperature": r1(feels),
              "relative_humidity_2m": [int(round(x)) for x in hum],
              "precipitation_probability": [int(round(x)) for x in prob], "precipitation": r1(rain_mm),
              "weather_code": [int(x) for x in code], "wind_speed_10m": r1(wind), "wind_gusts_10m": r1(gust),
              "cloud_cover": [int(round(x)) for x in cloud], "uv_index": r1(uv),
              "pressure_msl": r1(pressure), "visibility": [int(x) for x in vis]}

    daily = {k: [] for k in ["time", "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
                              "precipitation_probability_max", "wind_speed_10m_max", "uv_index_max",
                              "sunrise", "sunset"]}
    for d in range(days):
        sl = slice(d * 24, d * 24 + 24); day = (start + dt.timedelta(days=d)).date()
        daily["time"].append(str(day))
        daily["temperature_2m_max"].append(round(float(temp[sl].max()), 1))
        daily["temperature_2m_min"].append(round(float(temp[sl].min()), 1))
        daily["precipitation_sum"].append(round(float(rain_mm[sl].sum()), 1))
        daily["precipitation_probability_max"].append(int(prob[sl].max()))
        daily["wind_speed_10m_max"].append(round(float(wind[sl].max()), 1))
        daily["uv_index_max"].append(round(float(uv[sl].max()), 1))
        daily["sunrise"].append(f"{day}T06:05"); daily["sunset"].append(f"{day}T18:40")

    i = int(np.clip((now - start).total_seconds() // 3600, 0, n - 1))
    current = {"time": times[i], "temperature_2m": hourly["temperature_2m"][i],
               "apparent_temperature": hourly["apparent_temperature"][i],
               "relative_humidity_2m": hourly["relative_humidity_2m"][i],
               "precipitation": hourly["precipitation"][i], "weather_code": hourly["weather_code"][i],
               "cloud_cover": hourly["cloud_cover"][i], "pressure_msl": hourly["pressure_msl"][i],
               "wind_speed_10m": hourly["wind_speed_10m"][i], "wind_gusts_10m": hourly["wind_gusts_10m"][i]}
    return {"latitude": lat, "longitude": lon, "timezone": tzname, "current": current,
            "hourly": hourly, "daily": daily, "_simulated": True, "_scenario": sc}


def simulate_air_quality(city: str, scenario: str = "auto") -> dict:
    """Plausible AQI per city (Delhi-type cities worse)."""
    h = zlib.crc32(city.lower().encode())
    base = {"delhi": 210, "kolkata": 120, "mumbai": 95, "jaipur": 140, "bhusawal": 110}.get(city.lower(), 60 + h % 50)
    aqi = int(base + (h % 25) - (40 if scenario in ("monsoon", "storm") else 0))
    aqi = max(15, aqi)
    return {"us_aqi": aqi, "pm2_5": round(aqi * 0.42, 1), "pm10": round(aqi * 0.8, 1)}
