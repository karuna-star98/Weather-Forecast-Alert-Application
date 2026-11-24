"""FastAPI service.  Run:  uvicorn api.app:app --reload   (docs at /docs)

Endpoints
  GET  /health
  GET  /locations                       saved locations
  POST /locations?city=Pune             add + fetch a location
  GET  /snapshot?city=Pune              full live computation (current, summary, alerts, risk)
  GET  /forecast/hourly?location_id=1&hours=24
  GET  /forecast/daily?location_id=1&days=7
  GET  /alerts?location_id=1            evaluated from stored data
  GET  /alerts/history                  notification log
  POST /refresh                         re-fetch every saved location (+ notify)
  GET  /compare?cities=Delhi,Mumbai     multi-city risk comparison
"""
from __future__ import annotations
import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from src import notifier, storage
from src.config import Thresholds, default_mode
from src.providers import WeatherAPIError
from src.rules import evaluate, risk_score
from src.service import build_snapshot
from src.simulator import SCENARIOS


def records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe list (NaN -> None, timestamps -> ISO strings)."""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%dT%H:%M")
    return out.astype(object).where(out.notna(), None).to_dict("records")


def snap_json(s) -> dict:
    return {"location": {"id": s.location_id, "name": s.city, "lat": s.lat, "lon": s.lon, "tz": s.tz},
            "mode": s.mode, "scenario": s.scenario, "warning": s.warning, "generated": str(s.now),
            "condition": s.condition, "current": s.current, "aqi": s.aqi, "summary": s.summary,
            "best_outdoor_window": s.window, "comfort": s.comfort, "risk": s.risk,
            "alerts": [a.to_dict() for a in s.alerts]}


def refresh_all(notify: bool = False) -> list[dict]:
    results = []
    for loc in storage.list_locations():
        try:
            s = build_snapshot(loc["name"], mode=default_mode())
            sent = notifier.dispatch(s.location_id, s.city, s.alerts, dry_run=not (notify and s.mode == "live"))
            results.append({"location": s.city, "alerts": len(s.alerts), "notified": len(sent)})
        except WeatherAPIError as exc:
            results.append({"location": loc["name"], "error": str(exc)})
    return results


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage.init_db()
    task = None
    minutes = float(os.getenv("AUTO_REFRESH_MINUTES", 0) or 0)
    if minutes > 0:                                   # optional background scheduler
        async def loop():
            while True:
                await asyncio.sleep(minutes * 60)
                await asyncio.to_thread(refresh_all, True)
        task = asyncio.create_task(loop())
    yield
    if task:
        task.cancel()


app = FastAPI(title="Weather Forecast & Alert API", version="2.0.0",
              description="Real-time & forecast weather with rule-based risk alerts.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "mode": default_mode(), "scenarios": SCENARIOS}


@app.get("/locations")
def locations():
    return storage.list_locations()


@app.post("/locations")
def add_location(city: str = Query(..., min_length=2)):
    try:
        return snap_json(build_snapshot(city))
    except WeatherAPIError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.get("/snapshot")
def snapshot(city: str = Query(..., min_length=2), mode: str | None = None, scenario: str = "auto", days: int = 7):
    try:
        return snap_json(build_snapshot(city, mode=mode, scenario=scenario, days=days))
    except WeatherAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


def _series(location_id: int) -> dict:
    if not storage.get_location(location_id):
        raise HTTPException(status_code=404, detail="Unknown location_id")
    return storage.load_series(location_id)


@app.get("/forecast/hourly")
def hourly(location_id: int, hours: int = Query(24, ge=1, le=168)):
    h = _series(location_id)["hourly"]
    return records(h[h["ts"] >= pd.Timestamp.now().floor("h")].head(hours))


@app.get("/forecast/daily")
def daily(location_id: int, days: int = Query(7, ge=1, le=16)):
    d = _series(location_id)["daily"]
    return records(d[d["date"] >= pd.Timestamp.now().strftime("%Y-%m-%d")].head(days))


@app.get("/alerts")
def alerts(location_id: int):
    data = _series(location_id)
    a = evaluate(data["hourly"], data["daily"], Thresholds.from_env(), pd.Timestamp.now())
    return {"location_id": location_id, "risk": risk_score(a), "alerts": [x.to_dict() for x in a]}


@app.get("/alerts/history")
def history(location_id: int | None = None, limit: int = Query(50, le=500)):
    return storage.alert_history(location_id, limit)


@app.post("/refresh")
def refresh(notify: bool = False):
    return refresh_all(notify)


@app.get("/compare")
def compare(cities: str, scenario: str = "auto"):
    out = []
    for c in [x.strip() for x in cities.split(",") if x.strip()][:10]:
        try:
            s = build_snapshot(c, scenario=scenario, persist=False)
            out.append({"city": s.city, "risk": s.risk, "summary": s.summary, "alerts": [a.code for a in s.alerts]})
        except WeatherAPIError as exc:
            out.append({"city": c, "error": str(exc)})
    return sorted(out, key=lambda r: -r.get("risk", {}).get("score", -1))
