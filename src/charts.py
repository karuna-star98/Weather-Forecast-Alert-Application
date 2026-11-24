"""Matplotlib visualisation: a one-page 'operations dashboard' + multi-city comparison."""
from __future__ import annotations
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless-safe
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd

NAVY, BLUE, ORANGE, RED, GREEN, GREY = "#0B1F3A", "#2F80ED", "#F2994A", "#EB5757", "#27AE60", "#8A94A6"
SEV_COLOR = {"info": BLUE, "warn": ORANGE, "critical": RED}
RISK_COLOR = {"LOW": GREEN, "MODERATE": "#F2C94C", "HIGH": ORANGE, "SEVERE": RED}


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=NAVY)
    ax.grid(alpha=.25); ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)


def dashboard_chart(s, path: Path, hours: int = 48) -> Path:
    t = s.thresholds
    h = s.hourly[s.hourly["ts"] >= s.now.floor("h")].head(hours)
    d = s.daily
    fig = plt.figure(figsize=(16, 10), facecolor="white")
    gs = fig.add_gridspec(3, 2, height_ratios=[0.55, 1, 1], hspace=.5, wspace=.18,
                          left=.05, right=.97, top=.95, bottom=.06)

    # --- header banner
    ax = fig.add_subplot(gs[0, :]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, color=NAVY, transform=ax.transAxes, clip_on=False))
    c = s.current
    ax.text(.015, .70, f"{s.city}  |  Weather Forecast & Alert Dashboard", color="white", fontsize=18, fontweight="bold")
    ax.text(.015, .38, f"{s.now:%A, %d %b %Y %H:%M}   •   mode: {s.mode}" + (f" ({s.scenario})" if s.scenario else ""),
            color="#B8C4D9", fontsize=10)
    ax.text(.015, .10, f"Now: {s.condition}  {c.get('temp_c', '-')}°C (feels {c.get('feels_c', '-')}°C)  •  "
            f"Humidity {c.get('humidity', '-')}%  •  Wind {c.get('wind_ms', '-')} m/s  •  "
            f"Comfort {s.comfort}/100" + (f"  •  AQI {s.aqi['us_aqi']}" if s.aqi else ""), color="white", fontsize=10.5)
    col = RISK_COLOR[s.risk["level"]]
    ax.text(.985, .62, f"RISK {s.risk['score']}/100", color=col, fontsize=20, fontweight="bold", ha="right")
    ax.text(.985, .25, f"{s.risk['level']}  •  {len(s.alerts)} active alert(s)", color="white", fontsize=11, ha="right")

    fmt = mdates.DateFormatter("%a %H:%M")
    # --- temperature
    ax = fig.add_subplot(gs[1, 0]); _style(ax, f"Temperature — next {hours} h (°C)")
    ax.plot(h["ts"], h["temp_c"], color=RED, lw=2, label="Temperature")
    ax.plot(h["ts"], h["feels_c"], color=ORANGE, lw=1.4, ls="--", label="Feels like")
    if h["temp_c"].max() > t.heat_c - 6: ax.axhline(t.heat_c, color=RED, ls=":", lw=1, label=f"Heat limit {t.heat_c:.0f}°C")
    ax.xaxis.set_major_formatter(fmt); ax.legend(fontsize=8, frameon=False)
    # --- rain
    ax = fig.add_subplot(gs[1, 1]); _style(ax, "Rain probability (%) & precipitation (mm)")
    ax.bar(h["ts"], h["precip_prob"], width=.035, color=BLUE, alpha=.55, label="Probability %")
    ax.axhline(t.rain_prob, color=BLUE, ls=":", lw=1); ax.set_ylim(0, 105)
    ax2 = ax.twinx(); ax2.plot(h["ts"], h["precip_mm"], color=NAVY, lw=1.8, label="mm/h")
    ax2.spines[["top"]].set_visible(False); ax2.tick_params(labelsize=8)
    ax.xaxis.set_major_formatter(fmt)
    ax.legend(*[sum(z, []) for z in zip(ax.get_legend_handles_labels(), ax2.get_legend_handles_labels())], fontsize=8, frameon=False, loc="upper right")
    # --- wind
    ax = fig.add_subplot(gs[2, 0]); _style(ax, "Wind speed & gusts (m/s)")
    ax.fill_between(h["ts"], h["wind_ms"], color=GREEN, alpha=.25); ax.plot(h["ts"], h["wind_ms"], color=GREEN, lw=1.6, label="Wind")
    ax.plot(h["ts"], h["wind_gust_ms"], color=ORANGE, lw=1.4, label="Gusts")
    ax.axhline(t.wind_gust_ms, color=RED, ls=":", lw=1, label=f"Gust limit {t.wind_gust_ms:.0f}")
    ax.xaxis.set_major_formatter(fmt); ax.legend(fontsize=8, frameon=False)
    # --- 7 day
    ax = fig.add_subplot(gs[2, 1]); _style(ax, f"{len(d)}-day outlook — temperature range (°C) & rain (mm)")
    x = pd.to_datetime(d["date"])
    ax.fill_between(x, d["tmin_c"], d["tmax_c"], color=ORANGE, alpha=.25)
    ax.plot(x, d["tmax_c"], color=RED, marker="o", lw=2, label="Max"); ax.plot(x, d["tmin_c"], color=BLUE, marker="o", lw=2, label="Min")
    if d["tmax_c"].max() > t.heat_c - 6: ax.axhline(t.heat_c, color=RED, ls=":", lw=1)
    ax3 = ax.twinx(); ax3.bar(x, d["rain_mm"], width=.4, color=BLUE, alpha=.35, label="Rain mm")
    ax3.spines[["top"]].set_visible(False); ax3.tick_params(labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d")); ax.legend(fontsize=8, frameon=False, loc="upper left")

    fig.text(.05, .015, "Source: " + ("Open-Meteo" if s.mode == "live" else "Virtual simulator (offline demo data)") +
             "  •  Weather Forecast & Alert Application", fontsize=8, color=GREY)
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130); plt.close(fig)
    return path


def alerts_chart(s, path: Path) -> Path:
    """Horizontal severity chart of fired alerts (nice screenshot for README)."""
    fig, ax = plt.subplots(figsize=(10, max(2.5, .7 * len(s.alerts) + 1.2)))
    if not s.alerts:
        ax.text(.5, .5, "✓ No active alerts", ha="center", va="center", fontsize=16, color=GREEN)
        ax.axis("off")
    else:
        labels = [a.label for a in s.alerts][::-1]
        vals = [{"info": 1, "warn": 2, "critical": 3}[a.severity] for a in s.alerts][::-1]
        ax.barh(labels, vals, color=[SEV_COLOR[a.severity] for a in s.alerts][::-1])
        ax.set_xticks([1, 2, 3]); ax.set_xticklabels(["INFO", "WARN", "CRITICAL"])
        ax.set_title(f"{s.city} — active alerts", loc="left", fontweight="bold", color=NAVY)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130); plt.close(fig); return path


def comparison_chart(snaps: list, path: Path) -> Path:
    """Multi-city comparison: today's max temp, rain, gusts and risk score."""
    names = [s.city.split(",")[0] for s in snaps]
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.8))
    data = [("Max temp next 24h (°C)", [s.summary["temp_max"] for s in snaps], RED),
            ("Rain next 24h (mm)", [s.summary["rain_total_mm"] for s in snaps], BLUE),
            ("Peak gust (m/s)", [s.summary["gust_max"] for s in snaps], ORANGE),
            ("Risk score (0-100)", [s.risk["score"] for s in snaps], None)]
    for ax, (title, vals, col) in zip(axes, data):
        colors = col or [RISK_COLOR[s.risk["level"]] for s in snaps]
        ax.barh(names, vals, color=colors); _style(ax, title)
        for i, v in enumerate(vals): ax.text(v, i, f" {v}", va="center", fontsize=8)
    fig.suptitle("Multi-city weather risk comparison", x=.01, ha="left", fontsize=14, fontweight="bold", color=NAVY)
    fig.tight_layout(); path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130); plt.close(fig); return path
