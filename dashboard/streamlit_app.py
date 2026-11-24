"""Streamlit operations dashboard.   Run:  streamlit run dashboard/streamlit_app.py"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src import analysis, notifier, report, simulator
from src.config import Thresholds
from src.providers import WeatherAPIError
from src.service import build_snapshot

st.set_page_config(page_title="Weather Forecast & Alert", page_icon="⛅", layout="wide")

NAVY, BLUE, ORANGE, RED, GREEN = "#0B1F3A", "#2F80ED", "#F2994A", "#EB5757", "#27AE60"
SEV = {"info": BLUE, "warn": ORANGE, "critical": RED}
RISK = {"LOW": GREEN, "MODERATE": "#F2C94C", "HIGH": ORANGE, "SEVERE": RED}

st.markdown(f"""<style>
.block-container{{padding-top:1.2rem}}
.hero{{background:linear-gradient(120deg,{NAVY},#16407A);padding:20px 26px;border-radius:14px;margin-bottom:14px}}
.hero h1{{margin:0;font-size:1.7rem;color:#FFFFFF !important}}
.hero small, .hero b{{color:#DCE6F7 !important}}
/* Every card sets its OWN text colours so it is readable in light AND dark themes */
.kpi{{background:#FFFFFF;border:1px solid #E3E8F0;border-radius:12px;padding:12px 16px;box-shadow:0 1px 3px #0001;
      transition:transform .15s, box-shadow .15s}}
.kpi:hover{{transform:translateY(-3px);box-shadow:0 6px 16px #0B1F3A26}}
.kpi .l{{font-size:.78rem;color:#5A6780 !important;text-transform:uppercase;letter-spacing:.04em}}
.kpi .v{{font-size:1.6rem;font-weight:700;color:{NAVY} !important}}
.kpi small{{color:#5A6780 !important}}
.alert{{background:#FFFFFF;border:1px solid #E3E8F0;border-radius:10px;padding:12px 16px;margin-bottom:10px;
        color:#1B2B45 !important;transition:transform .15s, box-shadow .15s}}
.alert:hover{{transform:translateX(4px);box-shadow:0 4px 14px #0B1F3A22}}
.alert b{{color:{NAVY} !important;font-size:1.02rem}}
.alert small{{color:#44546F !important}}
.tag{{color:#FFFFFF !important;font-size:.7rem;padding:2px 8px;border-radius:10px;margin-left:8px;font-weight:600}}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=600, show_spinner="Fetching weather…")
def load(city, mode, scenario, days, heat, rain, wind):
    t = Thresholds(heat_c=heat, rain_prob=rain, wind_gust_ms=wind)
    return build_snapshot(city, mode=mode, scenario=scenario, days=days, thresholds=t, persist=False)


def kpi(col, label, value, sub=""):
    col.markdown(f'<div class="kpi"><div class="l">{label}</div><div class="v">{value}</div><small>{sub}</small></div>',
                 unsafe_allow_html=True)


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ Controls")
    mode = "live" if st.radio("Data source", ["Simulation (offline)", "Live (Open-Meteo)"]).startswith("Live") else "simulate"
    preset = st.selectbox("City", simulator.known_cities() + ["Custom…"])
    city = st.text_input("Type a city", "Pune") if preset == "Custom…" else preset
    scenario = st.selectbox("Simulation scenario", simulator.SCENARIOS, disabled=(mode == "live"))
    days = st.slider("Forecast days", 3, 16 if mode == "live" else 7, 7)
    st.subheader("Alert thresholds")
    heat = st.slider("Heat (°C)", 30, 50, 40)
    rain = st.slider("Rain probability (%)", 20, 100, 60)
    wind = st.slider("Wind gust (m/s)", 5, 30, 15)
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
    notify_clicked = st.button("🔔 Send test notification (dry-run)")

try:
    s = load(city, mode, scenario, days, float(heat), float(rain), float(wind))
except WeatherAPIError as exc:
    st.error(str(exc)); st.stop()

if notify_clicked:
    top = s.alerts[0] if s.alerts else None
    st.toast(notifier.format_message(s.city, top.to_dict()) if top else "No alerts to send for this city.", icon="🔔")

c = s.current
st.markdown(f'<div class="hero"><h1>{s.emoji} {s.city}</h1><small>{s.now:%A, %d %b %Y %H:%M} · {s.condition} · '
            f'mode: <b>{s.mode}</b>{" (" + s.scenario + ")" if s.scenario else ""}</small></div>', unsafe_allow_html=True)
if s.warning:
    st.warning(s.warning)

cols = st.columns(6)
kpi(cols[0], "Temperature", f"{c.get('temp_c')}°C", f"feels {c.get('feels_c')}°C")
kpi(cols[1], "Humidity", f"{c.get('humidity')}%", f"cloud {c.get('cloud_pct')}%")
kpi(cols[2], "Wind", f"{c.get('wind_ms')} m/s", f"gusts {c.get('wind_gust_ms')}")
kpi(cols[3], "Air quality", f"{s.aqi['us_aqi']}" if s.aqi else "n/a", "US AQI")
kpi(cols[4], "Comfort", f"{s.comfort}/100", "pleasantness")
cols[5].markdown(f'<div class="kpi"><div class="l">Risk score</div><div class="v" style="color:{RISK[s.risk["level"]]}">'
                 f'{s.risk["score"]}/100</div><small>{s.risk["level"]}</small></div>', unsafe_allow_html=True)

st.subheader(f"🚨 Alerts ({len(s.alerts)})")
if not s.alerts:
    st.success("No active alerts — conditions are within safe limits.")
else:
    levels = st.multiselect("Filter by severity", ["critical", "warn", "info"], default=["critical", "warn", "info"])
    for a in [x for x in s.alerts if x.severity in levels]:
        st.markdown(f'<div class="alert" style="border-left:6px solid {SEV[a.severity]}"><b>{a.label}</b>'
                    f'<span class="tag" style="background:{SEV[a.severity]}">{a.severity.upper()}</span><br>{a.message}'
                    f'<br><small>→ {a.advice}</small></div>', unsafe_allow_html=True)
if s.window:
    st.info(f"🕒 Best outdoor window: **{s.window['start']} → {s.window['end']}** ({s.window['hours']} h)")

h = s.hourly[s.hourly["ts"] >= s.now.floor("h")].head(48)
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Next 48 h", "📅 Daily outlook", "🗺️ Map", "🏙️ Compare cities", "📥 Data & export"])

with tab1:
    f1 = go.Figure()
    f1.add_scatter(x=h["ts"], y=h["temp_c"], name="Temperature", line=dict(color=RED, width=3))
    f1.add_scatter(x=h["ts"], y=h["feels_c"], name="Feels like", line=dict(color=ORANGE, dash="dash"))
    f1.add_hline(y=heat, line_dash="dot", line_color=RED, annotation_text="heat limit")
    f1.update_layout(title="Temperature (°C)", height=320, margin=dict(t=40, b=10))
    st.plotly_chart(f1, use_container_width=True)
    left, right = st.columns(2)
    f2 = make_subplots(specs=[[{"secondary_y": True}]])
    f2.add_bar(x=h["ts"], y=h["precip_prob"], name="Probability %", marker_color=BLUE, opacity=.5)
    f2.add_scatter(x=h["ts"], y=h["precip_mm"], name="mm/h", line=dict(color=NAVY), secondary_y=True)
    f2.add_hline(y=rain, line_dash="dot", line_color=BLUE)
    f2.update_layout(title="Rain", height=300, margin=dict(t=40, b=10))
    left.plotly_chart(f2, use_container_width=True)
    f3 = go.Figure()
    f3.add_scatter(x=h["ts"], y=h["wind_ms"], name="Wind", fill="tozeroy", line=dict(color=GREEN))
    f3.add_scatter(x=h["ts"], y=h["wind_gust_ms"], name="Gusts", line=dict(color=ORANGE))
    f3.add_hline(y=wind, line_dash="dot", line_color=RED)
    f3.update_layout(title="Wind (m/s)", height=300, margin=dict(t=40, b=10))
    right.plotly_chart(f3, use_container_width=True)

with tab2:
    d = s.daily
    f4 = make_subplots(specs=[[{"secondary_y": True}]])
    f4.add_bar(x=d["date"], y=d["rain_mm"], name="Rain mm", marker_color=BLUE, opacity=.35, secondary_y=True)
    f4.add_scatter(x=d["date"], y=d["tmax_c"], name="Max °C", line=dict(color=RED, width=3), mode="lines+markers")
    f4.add_scatter(x=d["date"], y=d["tmin_c"], name="Min °C", line=dict(color=BLUE, width=3), mode="lines+markers", fill="tonexty")
    f4.update_layout(height=380, margin=dict(t=20))
    st.plotly_chart(f4, use_container_width=True)
    st.dataframe(analysis.daily_table(s.daily), use_container_width=True, hide_index=True)

with tab3:
    st.map(pd.DataFrame({"lat": [s.lat], "lon": [s.lon]}), zoom=6)
    st.caption(f"{s.city}: {s.lat:.2f}, {s.lon:.2f} · timezone {s.tz}")

with tab4:
    picks = st.multiselect("Cities to compare", simulator.known_cities(), default=["Delhi", "Mumbai", "Kolkata", "Shimla"])
    if picks:
        snaps = [load(p, mode, scenario, 7, float(heat), float(rain), float(wind)) for p in picks]
        df = pd.DataFrame([{"City": x.city, "Risk": x.risk["score"], "Level": x.risk["level"], "Max temp °C": x.summary["temp_max"],
                            "Rain mm (24h)": x.summary["rain_total_mm"], "Peak gust m/s": x.summary["gust_max"],
                            "Alerts": ", ".join(a.code for a in x.alerts) or "—"} for x in snaps]).sort_values("Risk", ascending=False)
        st.plotly_chart(go.Figure(go.Bar(x=df["City"], y=df["Risk"], marker_color=[RISK[l] for l in df["Level"]])).update_layout(
            title="Risk score by city", height=320), use_container_width=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

with tab5:
    st.dataframe(s.hourly, use_container_width=True, height=300)
    b1, b2, b3 = st.columns(3)
    b1.download_button("⬇️ Hourly CSV", s.hourly.to_csv(index=False), f"{report.slug(s.city)}_hourly.csv", "text/csv")
    b2.download_button("⬇️ Text report", report.text_report(s), f"{report.slug(s.city)}_report.txt")
    b3.download_button("⬇️ HTML report", report.html_report(s), f"{report.slug(s.city)}_report.html", "text/html")

st.caption("Source: " + ("Open-Meteo (live)" if s.mode == "live" else "Virtual simulator — demo data, not real weather"))
