"""Pandas analytics: summaries, outdoor-window finder, comfort index."""
from __future__ import annotations
from typing import Optional
import pandas as pd


def upcoming(hourly: pd.DataFrame, now: pd.Timestamp, hours: int = 24) -> pd.DataFrame:
    return hourly[hourly["ts"] >= now.floor("h")].head(hours).reset_index(drop=True)


def summarize_next(hourly: pd.DataFrame, now: pd.Timestamp, hours: int = 24) -> dict:
    df = upcoming(hourly, now, hours)
    if df.empty:
        return {}
    hot = df.loc[df["temp_c"].idxmax()]
    return {
        "hours": len(df),
        "temp_min": round(df["temp_c"].min(), 1), "temp_max": round(df["temp_c"].max(), 1),
        "temp_avg": round(df["temp_c"].mean(), 1),
        "hottest_time": hot["ts"].strftime("%a %H:%M"),
        "rain_total_mm": round(df["precip_mm"].fillna(0).sum(), 1),
        "rain_prob_peak": int(df["precip_prob"].max()) if df["precip_prob"].notna().any() else 0,
        "gust_max": round(df["wind_gust_ms"].max(), 1),
        "humidity_avg": round(df["humidity"].mean()),
        "uv_max": round(df["uv"].max(), 1),
    }


def comfort_score(temp_c: float, humidity: float, wind_ms: float, rain_prob: float) -> int:
    """0-100: 100 = pleasant (22-26°C, ~50% RH, calm, dry)."""
    s = 100.0
    s -= abs(temp_c - 24) * 3.0
    s -= max(0, humidity - 65) * 0.6 + max(0, 35 - humidity) * 0.3
    s -= max(0, wind_ms - 6) * 3
    s -= rain_prob * 0.3
    return int(max(0, min(100, round(s))))


def best_outdoor_window(hourly: pd.DataFrame, now: pd.Timestamp, hours: int = 36,
                        max_rain_prob: float = 30, temp_range=(12, 35), max_gust: float = 10,
                        max_uv: float = 7) -> Optional[dict]:
    """Longest run of consecutive 'good' daylight hours in the next `hours` (new feature)."""
    df = upcoming(hourly, now, hours)
    if df.empty:
        return None
    day = df["ts"].dt.hour.between(6, 19)
    good = (day & (df["precip_prob"].fillna(0) <= max_rain_prob)
            & df["temp_c"].between(*temp_range) & (df["wind_gust_ms"].fillna(0) <= max_gust)
            & (df["uv"].fillna(0) <= max_uv))
    best = (0, 0, 0); i = 0
    while i < len(df):
        if good.iloc[i]:
            j = i
            while j + 1 < len(df) and good.iloc[j + 1]:
                j += 1
            if j - i + 1 > best[0]:
                best = (j - i + 1, i, j)
            i = j + 1
        else:
            i += 1
    if best[0] < 2:
        return None
    a, b = df.loc[best[1], "ts"], df.loc[best[2], "ts"] + pd.Timedelta(hours=1)
    return {"start": a.strftime("%a %H:%M"), "end": b.strftime("%a %H:%M"), "hours": best[0]}


def daily_table(daily: pd.DataFrame) -> pd.DataFrame:
    out = daily.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%a %d %b")
    return out[["date", "tmax_c", "tmin_c", "rain_mm", "rain_prob", "wind_max_ms", "uv_max"]]
