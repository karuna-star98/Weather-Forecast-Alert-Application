"""SQLite persistence: locations, raw payloads, normalised series, alert log."""
from __future__ import annotations
import datetime as dt
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import DB_PATH, SCHEMA_PATH


@contextmanager
def connect(db: Path | str = DB_PATH):
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db(db: Path | str = DB_PATH) -> None:
    with connect(db) as con:
        con.executescript(Path(SCHEMA_PATH).read_text(encoding="utf-8"))


def upsert_location(loc: dict, db: Path | str = DB_PATH) -> int:
    init_db(db)
    with connect(db) as con:
        con.execute("INSERT OR IGNORE INTO locations(name,lat,lon,tz) VALUES (?,?,?,?)",
                    (loc["name"], loc["lat"], loc["lon"], loc["tz"]))
        row = con.execute("SELECT id FROM locations WHERE lat=? AND lon=?",
                          (loc["lat"], loc["lon"])).fetchone()
        return int(row["id"])


def list_locations(db: Path | str = DB_PATH) -> list[dict]:
    init_db(db)
    with connect(db) as con:
        return [dict(r) for r in con.execute("SELECT * FROM locations ORDER BY name")]


def get_location(loc_id: int, db: Path | str = DB_PATH) -> Optional[dict]:
    init_db(db)
    with connect(db) as con:
        r = con.execute("SELECT * FROM locations WHERE id=?", (loc_id,)).fetchone()
        return dict(r) if r else None


def persist_raw(loc_id: int, payload: dict, provider: str, db: Path | str = DB_PATH) -> None:
    with connect(db) as con:
        con.execute("INSERT INTO weather_raw(location_id,fetched_at,scope,provider,payload) VALUES (?,?,?,?,?)",
                    (loc_id, dt.datetime.now(dt.timezone.utc).isoformat(), "full", provider, json.dumps(payload)))


def save_series(loc_id: int, norm: dict, db: Path | str = DB_PATH) -> None:
    """Upsert current, hourly and daily rows (INSERT OR REPLACE = idempotent refresh)."""
    h, d, c = norm["hourly"].copy(), norm["daily"].copy(), norm["current"]
    h["ts"] = h["ts"].dt.strftime("%Y-%m-%dT%H:%M")
    h = h.astype(object).where(h.notna(), None)
    d = d.astype(object).where(d.notna(), None)
    hcols = ["ts", "temp_c", "feels_c", "humidity", "wind_ms", "wind_gust_ms", "precip_mm", "precip_prob",
             "cloud_pct", "uv", "pressure_hpa", "visibility_km", "weather_code"]
    dcols = ["date", "tmax_c", "tmin_c", "rain_mm", "rain_prob", "wind_max_ms", "uv_max", "sunrise", "sunset"]
    with connect(db) as con:
        con.executemany(
            "INSERT OR REPLACE INTO weather_hourly(location_id,%s) VALUES (?,%s)" % (",".join(hcols), ",".join("?" * len(hcols))),
            [(loc_id, *row) for row in h[hcols].itertuples(index=False, name=None)])
        con.executemany(
            "INSERT OR REPLACE INTO weather_daily(location_id,%s) VALUES (?,%s)" % (",".join(dcols), ",".join("?" * len(dcols))),
            [(loc_id, *row) for row in d[dcols].itertuples(index=False, name=None)])
        con.execute("INSERT OR REPLACE INTO weather_current VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (loc_id, c.get("ts"), c.get("temp_c"), c.get("feels_c"), c.get("humidity"), c.get("wind_ms"),
                     c.get("wind_gust_ms"), c.get("precip_mm"), c.get("cloud_pct"), c.get("pressure_hpa"),
                     c.get("weather_code")))


def load_series(loc_id: int, db: Path | str = DB_PATH) -> dict:
    """Read stored series back into DataFrames (used by the API)."""
    init_db(db)
    with connect(db) as con:
        h = pd.read_sql_query("SELECT * FROM weather_hourly WHERE location_id=? ORDER BY ts", con, params=(loc_id,))
        d = pd.read_sql_query("SELECT * FROM weather_daily WHERE location_id=? ORDER BY date", con, params=(loc_id,))
        c = con.execute("SELECT * FROM weather_current WHERE location_id=?", (loc_id,)).fetchone()
    if not h.empty:
        h["ts"] = pd.to_datetime(h["ts"])
    return {"hourly": h.drop(columns="location_id", errors="ignore"),
            "daily": d.drop(columns="location_id", errors="ignore"),
            "current": dict(c) if c else {}}


# ------------------------------------------------------------------ alert log
def recently_sent(loc_id: int, code: str, hours: int = 12, db: Path | str = DB_PATH) -> bool:
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    with connect(db) as con:
        return con.execute("SELECT 1 FROM alert_log WHERE location_id=? AND code=? AND sent_at>=?",
                           (loc_id, code, cutoff)).fetchone() is not None


def log_alert(loc_id: int, alert: dict, channel: str, db: Path | str = DB_PATH) -> None:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with connect(db) as con:
        con.execute("INSERT INTO alert_log(location_id,code,severity,message,channel,sent_at) VALUES (?,?,?,?,?,?)",
                    (loc_id, alert["code"], alert["severity"], alert["message"], channel, now))


def alert_history(loc_id: Optional[int] = None, limit: int = 50, db: Path | str = DB_PATH) -> list[dict]:
    init_db(db)
    with connect(db) as con:
        q = "SELECT a.*, l.name AS location FROM alert_log a LEFT JOIN locations l ON l.id=a.location_id"
        args: tuple = ()
        if loc_id:
            q += " WHERE a.location_id=?"; args = (loc_id,)
        return [dict(r) for r in con.execute(q + " ORDER BY a.id DESC LIMIT ?", (*args, limit))]
