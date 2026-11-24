"""Unit tests.  Run:  pytest -q"""
import datetime as dt
import tempfile
from pathlib import Path

import pandas as pd

from src import analysis, notifier, report, storage
from src.config import Thresholds
from src.providers import normalize
from src.rules import evaluate, risk_score
from src.service import build_snapshot
from src.simulator import simulate_forecast

NOW = dt.datetime(2026, 11, 23, 10, 0)
TS = pd.Timestamp(NOW)


def _codes(city, scenario):
    n = normalize(simulate_forecast(city, scenario, now=NOW))
    return {a.code for a in evaluate(n["hourly"], n["daily"], Thresholds(), TS)}


def _frames(temp=25, prob=10, gust=5, tmax=30, rain=0, vis=20, code=0):
    """Hand-made 48h / 3-day data so rules can be tested in isolation."""
    h = pd.DataFrame({"ts": pd.date_range("2026-11-23 10:00", periods=48, freq="h"), "temp_c": temp, "feels_c": temp,
                      "humidity": 50.0, "wind_ms": 3.0, "wind_gust_ms": gust, "precip_mm": 0.0, "precip_prob": prob,
                      "cloud_pct": 20.0, "uv": 3.0, "pressure_hpa": 1010.0, "visibility_km": vis, "weather_code": code})
    d = pd.DataFrame({"date": ["2026-11-23", "2026-11-24", "2026-11-25"], "tmax_c": tmax, "tmin_c": 18.0,
                      "rain_mm": rain, "rain_prob": prob, "wind_max_ms": 5.0, "uv_max": 5.0,
                      "sunrise": "x", "sunset": "y"})
    return h, d


def test_simulation_is_deterministic():
    assert simulate_forecast("Delhi", now=NOW) == simulate_forecast("Delhi", now=NOW)


def test_normalize_shapes_and_units():
    n = normalize(simulate_forecast("Mumbai", days=7, now=NOW))
    assert len(n["hourly"]) == 168 and len(n["daily"]) == 7
    assert n["hourly"]["temp_c"].notna().all()
    assert n["hourly"]["visibility_km"].max() < 40          # metres were converted to km


def test_calm_weather_no_alerts():
    h, d = _frames()
    assert evaluate(h, d, Thresholds(), TS) == []


def test_heat_wave_is_critical_when_4_above_limit():
    h, d = _frames(tmax=45)
    a = {x.code: x for x in evaluate(h, d, Thresholds(), TS)}
    assert a["HEAT_WAVE"].severity == "critical"


def test_rain_wind_fog_storm_rules():
    h, d = _frames(prob=80, gust=20, vis=0.4, code=95)
    codes = {x.code for x in evaluate(h, d, Thresholds(), TS)}
    assert {"RAIN_SOON", "WIND_HIGH", "FOG", "THUNDERSTORM"} <= codes


def test_custom_threshold_changes_result():
    h, d = _frames(tmax=36)
    assert "HEAT_WAVE" not in {x.code for x in evaluate(h, d, Thresholds(), TS)}
    assert "HEAT_WAVE" in {x.code for x in evaluate(h, d, Thresholds(heat_c=35), TS)}


def test_missing_data_never_crashes():
    h, d = _frames()
    h[["precip_prob", "wind_gust_ms", "feels_c"]] = None
    evaluate(h, d, Thresholds(), TS)


def test_scenarios_fire_expected_alerts():
    assert "HEAT_WAVE" in _codes("Delhi", "heatwave")
    assert {"RAIN_SOON", "HEAVY_RAIN"} & _codes("Mumbai", "monsoon")
    assert "THUNDERSTORM" in _codes("Kolkata", "storm")
    assert "FOG" in _codes("Shimla", "fog")


def test_risk_score_levels():
    assert risk_score([])["level"] == "LOW"
    h, d = _frames(tmax=46, prob=90, gust=30, code=95)
    assert risk_score(evaluate(h, d, Thresholds(), TS))["level"] in ("HIGH", "SEVERE")


def test_best_outdoor_window_and_none_case():
    h, _ = _frames()
    w = analysis.best_outdoor_window(h, TS)
    assert w and w["hours"] >= 2
    h2, _ = _frames(prob=90)
    assert analysis.best_outdoor_window(h2, TS) is None


def test_storage_roundtrip_and_debounce():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "t.db"
        s = build_snapshot("Delhi", mode="simulate", db=db, now=TS)
        back = storage.load_series(s.location_id, db)
        assert len(back["hourly"]) == 168 and len(back["daily"]) == 7
        first = notifier.dispatch(s.location_id, s.city, s.alerts, dry_run=True, db=db)
        again = notifier.dispatch(s.location_id, s.city, s.alerts, dry_run=True, db=db)
        assert first and again == []                         # second run is de-duplicated
        assert storage.alert_history(db=db)


def test_reports_are_written():
    with tempfile.TemporaryDirectory() as tmp:
        s = build_snapshot("Kolkata", mode="simulate", persist=False, now=TS)
        paths = report.save_all(s, None, Path(tmp) / "o", Path(tmp) / "r")
        assert all(p.exists() and p.stat().st_size > 0 for p in paths.values())
        assert "ALERTS" in paths["txt"].read_text(encoding="utf-8")


def test_live_failure_falls_back_to_simulation(monkeypatch=None):
    from src import providers
    def boom(*a, **k): raise providers.WeatherAPIError("offline")
    orig = providers.geocode; providers.geocode = boom
    try:
        s = build_snapshot("Delhi", mode="live", persist=False, now=TS)
        assert s.mode == "simulate (fallback)" and s.warning
    finally:
        providers.geocode = orig


def test_live_path_with_mocked_http():
    """Exercise the live code path without internet by faking the HTTP layer."""
    from src import providers
    sim = simulate_forecast("London", "normal", now=NOW)

    def fake_get(url, params, **kw):
        if "geocoding" in url:
            return {"results": [{"name": "London", "admin1": "England", "country_code": "GB",
                                 "latitude": 51.5, "longitude": -0.12, "timezone": "Europe/London"}]}
        if "air-quality" in url:
            return {"current": {"us_aqi": 42, "pm2_5": 9.0, "pm10": 14.0}}
        return sim
    orig = providers._get; providers._get = fake_get
    try:
        s = build_snapshot("London", mode="live", persist=False, now=TS)
        assert s.mode == "live" and s.city == "London, England, GB" and s.aqi["us_aqi"] == 42
    finally:
        providers._get = orig
