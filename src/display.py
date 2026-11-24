"""Pretty terminal output using plain ANSI colours (no extra dependency)."""
from __future__ import annotations
import os
import sys

from . import analysis

_USE = sys.stdout.isatty() and os.getenv("NO_COLOR") is None
C = {"r": "\033[91m", "y": "\033[93m", "g": "\033[92m", "b": "\033[94m", "c": "\033[96m", "bold": "\033[1m", "dim": "\033[2m", "x": "\033[0m"}
SEV = {"info": "b", "warn": "y", "critical": "r"}
RISK = {"LOW": "g", "MODERATE": "y", "HIGH": "y", "SEVERE": "r"}


def col(text: str, k: str) -> str:
    return f"{C[k]}{text}{C['x']}" if _USE else text


def _bar(v: float, width: int = 20) -> str:
    n = int(round(width * v / 100))
    return "█" * n + "░" * (width - n)


def banner(title: str) -> None:
    print(col("=" * 70, "c")); print(col(f"  {title}", "bold")); print(col("=" * 70, "c"))


def show_snapshot(s) -> None:
    c = s.current
    banner(f"{s.emoji}  {s.city}  —  Weather Forecast & Alert Application")
    print(f"  {s.now:%A %d %b %Y, %H:%M}  |  mode: {s.mode}" + (f" ({s.scenario})" if s.scenario else ""))
    if s.warning:
        print(col(f"  ! {s.warning}", "y"))
    print(col("\n  CURRENT WEATHER", "bold"))
    print(f"   Condition   : {s.condition}")
    print(f"   Temperature : {c.get('temp_c')}°C  (feels like {c.get('feels_c')}°C)")
    print(f"   Humidity    : {c.get('humidity')}%      Cloud: {c.get('cloud_pct')}%")
    print(f"   Wind        : {c.get('wind_ms')} m/s (gusts {c.get('wind_gust_ms')} m/s)")
    print(f"   Pressure    : {c.get('pressure_hpa')} hPa   Rain now: {c.get('precip_mm')} mm")
    if s.aqi:
        print(f"   Air quality : US AQI {s.aqi['us_aqi']}  (PM2.5 {s.aqi['pm2_5']} µg/m³)")
    print(f"   Comfort     : {_bar(s.comfort)} {s.comfort}/100")
    sm = s.summary
    print(col("\n  NEXT 24 HOURS", "bold"))
    print(f"   Temperature : {sm['temp_min']}–{sm['temp_max']}°C (avg {sm['temp_avg']}), hottest at {sm['hottest_time']}")
    print(f"   Rain        : {sm['rain_total_mm']} mm total, peak probability {sm['rain_prob_peak']}%")
    print(f"   Wind gust   : up to {sm['gust_max']} m/s    Max UV: {sm['uv_max']}")
    if s.window:
        print(col(f"   Best outdoor window: {s.window['start']} → {s.window['end']} ({s.window['hours']} h)", "g"))
    print(col("\n  FORECAST", "bold"))
    print("   " + analysis.daily_table(s.daily).to_string(index=False).replace("\n", "\n   "))
    lvl = s.risk["level"]
    print(col(f"\n  RISK SCORE  {_bar(s.risk['score'])} {s.risk['score']}/100 — {lvl}", RISK[lvl]))
    print(col(f"\n  ALERTS ({len(s.alerts)})", "bold"))
    if not s.alerts:
        print(col("   ✓ No alerts. Conditions are within safe limits.", "g"))
    for a in s.alerts:
        print(col(f"   [{a.severity.upper():8}] {a.label}", SEV[a.severity]))
        print(f"              {a.message}")
        print(col(f"              → {a.advice}", "dim"))


def show_sent(sent: list, dry_run: bool) -> None:
    tag = "DRY-RUN (simulation)" if dry_run else "LIVE"
    print(col(f"\n  NOTIFICATIONS — {tag}", "bold"))
    if not sent:
        print("   Nothing new to send (already notified in the last 12 h, or below min severity).")
    for a in sent:
        print(f"   → {a['code']:13} via {', '.join(a['channels'])}")
