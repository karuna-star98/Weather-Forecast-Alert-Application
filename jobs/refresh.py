"""Scheduled refresh job.  Run manually or from cron / Task Scheduler:

    python -m jobs.refresh            # every 2-3 hours is typical
    # crontab:  0 */3 * * *  cd /path/to/project && .venv/bin/python -m jobs.refresh
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import notifier, storage
from src.config import default_mode
from src.providers import WeatherAPIError
from src.service import build_snapshot


def refresh_all(notify: bool = False) -> None:
    storage.init_db()
    locs = storage.list_locations()
    if not locs:
        print("No saved locations yet. Run:  python main.py --city Delhi --simulate"); return
    for loc in locs:
        try:
            s = build_snapshot(loc["name"], mode=default_mode())
            sent = notifier.dispatch(s.location_id, s.city, s.alerts, dry_run=not (notify and s.mode == "live"))
            print(f"[ok] {s.city}: {len(s.alerts)} alert(s), {len(sent)} notification(s)")
        except WeatherAPIError as exc:
            print(f"[fail] {loc['name']}: {exc}")


if __name__ == "__main__":
    refresh_all(notify="--notify" in sys.argv)
