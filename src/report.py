"""Report generation: CSV (hourly/daily/alerts), TXT, JSON and a standalone HTML report."""
from __future__ import annotations
import base64
import datetime as dt
import html
import json
import re
from pathlib import Path

from . import analysis
from .config import OUTPUT_DIR, REPORT_DIR


def slug(city: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", city.lower()).strip("_")


def text_report(s) -> str:
    c, sm = s.current, s.summary
    L = ["=" * 66, f" WEATHER FORECAST & ALERT REPORT - {s.city}", "=" * 66,
         f" Generated : {s.now:%Y-%m-%d %H:%M} ({s.tz})   Mode: {s.mode}" + (f" / {s.scenario}" if s.scenario else ""),
         f" Risk      : {s.risk['score']}/100 ({s.risk['level']})   Comfort: {s.comfort}/100", "",
         "CURRENT WEATHER", "-" * 66,
         f" {s.condition}, {c.get('temp_c')}°C (feels {c.get('feels_c')}°C), humidity {c.get('humidity')}%,"
         f" wind {c.get('wind_ms')} m/s (gust {c.get('wind_gust_ms')}), pressure {c.get('pressure_hpa')} hPa"]
    if s.aqi:
        L.append(f" Air quality: US AQI {s.aqi['us_aqi']} (PM2.5 {s.aqi['pm2_5']}, PM10 {s.aqi['pm10']})")
    L += ["", "NEXT 24 HOURS", "-" * 66,
          f" Temp {sm['temp_min']}-{sm['temp_max']}°C (avg {sm['temp_avg']}), hottest {sm['hottest_time']}",
          f" Rain {sm['rain_total_mm']} mm, peak probability {sm['rain_prob_peak']}%",
          f" Peak gust {sm['gust_max']} m/s, avg humidity {sm['humidity_avg']}%, max UV {sm['uv_max']}"]
    if s.window:
        L.append(f" Best outdoor window: {s.window['start']} -> {s.window['end']} ({s.window['hours']} h)")
    L += ["", "DAILY FORECAST", "-" * 66, analysis.daily_table(s.daily).to_string(index=False), "",
          f"ALERTS ({len(s.alerts)})", "-" * 66]
    if not s.alerts:
        L.append(" ✓ No alerts - conditions are within safe limits.")
    for a in s.alerts:
        L += [f" [{a.severity.upper():8}] {a.label}", f"            {a.message}", f"            -> {a.advice}"]
    L += ["", "Data source: " + ("Open-Meteo" if s.mode == "live" else "Virtual simulator (not real weather)")]
    return "\n".join(L)


def html_report(s, chart_png: Path | None = None) -> str:
    col = {"info": "#2F80ED", "warn": "#F2994A", "critical": "#EB5757"}
    img = ""
    if chart_png and Path(chart_png).exists():
        b64 = base64.b64encode(Path(chart_png).read_bytes()).decode()
        img = f'<img alt="dashboard" style="width:100%;border-radius:10px" src="data:image/png;base64,{b64}">'
    cards = "".join(
        f'<div class="a" style="border-left:6px solid {col[a.severity]}"><b>{html.escape(a.label)}</b> '
        f'<span class="tag" style="background:{col[a.severity]}">{a.severity.upper()}</span>'
        f'<div>{html.escape(a.message)}</div><small>→ {html.escape(a.advice)}</small></div>' for a in s.alerts
    ) or '<div class="a" style="border-left:6px solid #27AE60">✓ No active alerts</div>'
    rows = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>"
                   for r in analysis.daily_table(s.daily).itertuples(index=False))
    c = s.current
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(s.city)} weather report</title>
<style>body{{font-family:Segoe UI,Arial,sans-serif;background:#F4F6FA;margin:0;color:#0B1F3A}}
header{{background:#0B1F3A;color:#fff;padding:22px 32px}}main{{max-width:1100px;margin:auto;padding:24px}}
.kpi{{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0}}.k{{background:#fff;padding:14px 20px;border-radius:12px;box-shadow:0 1px 4px #0002;min-width:140px}}
.k b{{font-size:24px;display:block}}.a{{background:#fff;padding:12px 16px;margin:10px 0;border-radius:8px;box-shadow:0 1px 3px #0002}}
.tag{{color:#fff;font-size:11px;padding:2px 8px;border-radius:10px;margin-left:6px}}
table{{border-collapse:collapse;width:100%;background:#fff}}td,th{{padding:8px 12px;border-bottom:1px solid #E3E8F0;text-align:right}}th:first-child,td:first-child{{text-align:left}}
th{{background:#EAF0FA}}</style></head><body><header><h1 style="margin:0">{html.escape(s.city)} — Weather Forecast &amp; Alert Report</h1>
<div>{s.now:%A %d %b %Y %H:%M} · mode: {s.mode}</div></header><main>
<div class="kpi"><div class="k">{s.emoji} {s.condition}<b>{c.get('temp_c')}°C</b>feels {c.get('feels_c')}°C</div>
<div class="k">Humidity<b>{c.get('humidity')}%</b></div><div class="k">Wind<b>{c.get('wind_ms')} m/s</b></div>
<div class="k">Risk<b>{s.risk['score']}/100</b>{s.risk['level']}</div><div class="k">Comfort<b>{s.comfort}/100</b></div></div>
<h2>Alerts</h2>{cards}<h2>Dashboard</h2>{img}<h2>Daily forecast</h2>
<table><tr><th>Date</th><th>Max °C</th><th>Min °C</th><th>Rain mm</th><th>Rain %</th><th>Wind m/s</th><th>UV</th></tr>{rows}</table>
<p><small>Source: {'Open-Meteo' if s.mode == 'live' else 'Virtual simulator (offline demo data)'}</small></p></main></body></html>"""


def save_all(s, chart_png: Path | None = None, out_dir: Path = OUTPUT_DIR, report_dir: Path = REPORT_DIR) -> dict:
    """Write every artefact for a snapshot and return the paths."""
    out_dir, report_dir = Path(out_dir), Path(report_dir)
    out_dir.mkdir(parents=True, exist_ok=True); report_dir.mkdir(parents=True, exist_ok=True)
    base = f"{slug(s.city)}_{s.now:%Y%m%d_%H%M}"
    paths = {
        "hourly_csv": out_dir / f"{base}_hourly.csv", "daily_csv": out_dir / f"{base}_daily.csv",
        "alerts_csv": out_dir / f"{base}_alerts.csv", "txt": report_dir / f"{base}_report.txt",
        "html": report_dir / f"{base}_report.html", "json": report_dir / f"{base}_summary.json",
    }
    s.hourly.to_csv(paths["hourly_csv"], index=False)
    s.daily.to_csv(paths["daily_csv"], index=False)
    import pandas as pd
    pd.DataFrame([a.to_dict() for a in s.alerts]).to_csv(paths["alerts_csv"], index=False)
    paths["txt"].write_text(text_report(s), encoding="utf-8")
    paths["html"].write_text(html_report(s, chart_png), encoding="utf-8")
    paths["json"].write_text(json.dumps({
        "city": s.city, "generated": str(s.now), "mode": s.mode, "risk": s.risk, "comfort": s.comfort,
        "current": s.current, "summary": s.summary, "best_outdoor_window": s.window, "aqi": s.aqi,
        "alerts": [a.to_dict() for a in s.alerts]}, indent=2, default=str), encoding="utf-8")
    return paths
