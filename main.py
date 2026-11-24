#!/usr/bin/env python3
"""Weather Forecast & Alert Application — command line entry point.

Examples
  python main.py --city Delhi --simulate                    # offline demo
  python main.py --city Mumbai --simulate --scenario monsoon
  python main.py --city London                              # live Open-Meteo (no key)
  python main.py --cities Delhi,Mumbai,Kolkata --simulate   # multi-city comparison
  python main.py --serve                                    # FastAPI on :8000
  python main.py --dashboard                                # Streamlit dashboard
"""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

from src import charts, display, notifier, report, simulator
from src.config import OUTPUT_DIR, Thresholds, default_mode
from src.providers import WeatherAPIError
from src.service import build_snapshot


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Weather Forecast & Alert Application")
    p.add_argument("--city", default="Delhi", help="City name (default: Delhi)")
    p.add_argument("--cities", help="Comma-separated list for multi-city comparison")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--simulate", action="store_true", help="Use offline virtual simulation")
    mode.add_argument("--live", action="store_true", help="Use the real Open-Meteo API")
    p.add_argument("--scenario", default="auto", choices=simulator.SCENARIOS, help="Simulation scenario")
    p.add_argument("--days", type=int, default=7, help="Forecast days (1-16)")
    p.add_argument("--heat", type=float, help="Heat alert threshold °C")
    p.add_argument("--rain", type=float, help="Rain probability threshold %%")
    p.add_argument("--wind", type=float, help="Wind gust threshold m/s")
    p.add_argument("--notify", action="store_true", help="Send alerts via Telegram/Email (live mode only)")
    p.add_argument("--no-save", action="store_true", help="Do not write CSV/report/chart files")
    p.add_argument("--no-fallback", action="store_true", help="Fail instead of falling back to simulation")
    p.add_argument("--serve", action="store_true", help="Start the FastAPI server")
    p.add_argument("--dashboard", action="store_true", help="Start the Streamlit dashboard")
    p.add_argument("--list-cities", action="store_true", help="List built-in simulation cities")
    return p.parse_args(argv)


def thresholds_from(args) -> Thresholds:
    t = Thresholds.from_env()
    if args.heat is not None: t.heat_c = args.heat
    if args.rain is not None: t.rain_prob = args.rain
    if args.wind is not None: t.wind_gust_ms = args.wind
    return t


def run_city(city: str, args, mode: str):
    s = build_snapshot(city, mode=mode, scenario=args.scenario, days=args.days,
                       thresholds=thresholds_from(args), fallback=not args.no_fallback)
    display.show_snapshot(s)
    dry = s.mode != "live" or not args.notify
    sent = notifier.dispatch(s.location_id, s.city, s.alerts, dry_run=dry)
    display.show_sent(sent, dry)
    if not args.no_save:
        chart = charts.dashboard_chart(s, OUTPUT_DIR / "charts" / f"{report.slug(s.city)}_dashboard.png")
        charts.alerts_chart(s, OUTPUT_DIR / "charts" / f"{report.slug(s.city)}_alerts.png")
        paths = report.save_all(s, chart)
        print(display.col("\n  SAVED FILES", "bold"))
        for k, v in {"chart": chart, **paths}.items():
            print(f"   {k:11}: {Path(v).relative_to(Path(__file__).parent)}")
    return s


def main(argv=None) -> int:
    args = parse_args(argv)
    root = Path(__file__).parent
    if args.list_cities:
        print("Built-in simulation cities:", ", ".join(simulator.known_cities())); return 0
    if args.serve:
        return subprocess.call([sys.executable, "-m", "uvicorn", "api.app:app", "--reload", "--port", "8000"], cwd=root)
    if args.dashboard:
        return subprocess.call([sys.executable, "-m", "streamlit", "run", "dashboard/streamlit_app.py"], cwd=root)

    mode = "simulate" if args.simulate else "live" if args.live else default_mode()
    try:
        if args.cities:
            snaps = [run_city(c.strip(), args, mode) for c in args.cities.split(",") if c.strip()]
            if len(snaps) > 1 and not args.no_save:
                p = charts.comparison_chart(snaps, OUTPUT_DIR / "charts" / "city_comparison.png")
                print(display.col(f"\n  Comparison chart: {p.relative_to(root)}", "g"))
        else:
            run_city(args.city, args, mode)
    except WeatherAPIError as exc:
        print(display.col(f"\n  ERROR: {exc}", "r"))
        print("  Tip: run with --simulate to work offline.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
