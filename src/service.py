"""Orchestrator: city -> provider -> normalise -> persist -> analyse -> alerts.

Both the CLI, the FastAPI app and the Streamlit dashboard call build_snapshot(),
so the business logic lives in exactly one place.
"""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

from . import analysis, providers, simulator, storage
from .config import DB_PATH, Thresholds, default_mode
from .rules import Alert, evaluate, risk_score
from .weather_codes import describe, icon


@dataclass
class Snapshot:
    city: str
    lat: float
    lon: float
    tz: str
    mode: str                      # 'live' | 'simulate' | 'simulate (fallback)'
    scenario: Optional[str]
    now: pd.Timestamp
    current: dict
    hourly: pd.DataFrame
    daily: pd.DataFrame
    aqi: Optional[dict]
    alerts: list[Alert]
    risk: dict
    summary: dict
    window: Optional[dict]
    comfort: int
    location_id: Optional[int] = None
    warning: str = ""
    thresholds: Thresholds = field(default_factory=Thresholds)

    @property
    def condition(self) -> str:
        return describe(self.current.get("weather_code"))

    @property
    def emoji(self) -> str:
        return icon(self.current.get("weather_code"))


def _now_local(tzname: str) -> pd.Timestamp:
    try:
        return pd.Timestamp(dt.datetime.now(ZoneInfo(tzname)).replace(tzinfo=None))
    except Exception:
        return pd.Timestamp.now()


def build_snapshot(city: str, mode: Optional[str] = None, scenario: str = "auto", days: int = 7,
                   thresholds: Optional[Thresholds] = None, persist: bool = True, db=DB_PATH,
                   fallback: bool = True, now: Optional[pd.Timestamp] = None) -> Snapshot:
    mode = (mode or default_mode()).lower()
    thresholds = thresholds or Thresholds.from_env()
    warning, used, sc = "", mode, None

    if mode == "live":
        try:
            loc = providers.geocode(city)
            payload = providers.fetch_forecast(loc["lat"], loc["lon"], days)
            aqi = providers.fetch_air_quality(loc["lat"], loc["lon"])
            loc["tz"] = payload.get("timezone", loc["tz"])
        except providers.WeatherAPIError as exc:
            if not fallback:
                raise
            warning = f"Live API unavailable ({exc}). Showing SIMULATED data instead."
            used = "simulate (fallback)"
    if used != "live":
        loc = simulator.sim_geocode(city)
        payload = simulator.simulate_forecast(city, scenario, days, now=now.to_pydatetime() if now is not None else None)
        aqi = simulator.simulate_air_quality(city, payload["_scenario"])
        sc = payload["_scenario"]

    norm = providers.normalize(payload)
    now = now if now is not None else _now_local(loc["tz"])
    loc_id = None
    if persist:
        loc_id = storage.upsert_location(loc, db)
        storage.persist_raw(loc_id, payload, "open-meteo" if used == "live" else "simulator", db)
        storage.save_series(loc_id, norm, db)

    h, d = norm["hourly"], norm["daily"]
    alerts = evaluate(h, d, thresholds, now, aqi)
    cur = norm["current"]
    up = analysis.upcoming(h, now, 1)
    rp = float(up["precip_prob"].iloc[0]) if len(up) and pd.notna(up["precip_prob"].iloc[0]) else 0.0
    comfort = analysis.comfort_score(cur.get("temp_c") or 25, cur.get("humidity") or 50,
                                     cur.get("wind_ms") or 0, rp)
    return Snapshot(city=loc["name"], lat=loc["lat"], lon=loc["lon"], tz=loc["tz"], mode=used, scenario=sc,
                    now=now, current=cur, hourly=h, daily=d, aqi=aqi, alerts=alerts, risk=risk_score(alerts),
                    summary=analysis.summarize_next(h, now, 24), window=analysis.best_outdoor_window(h, now),
                    comfort=comfort, location_id=loc_id, warning=warning, thresholds=thresholds)
