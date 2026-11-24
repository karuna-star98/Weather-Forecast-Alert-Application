# 1️⃣ Project Explanation, Tech Stack & Architecture

## What is a Weather Forecast & Alert Application?
**Simple:** an app that checks the weather for your city and *warns you automatically* when something important is coming — rain, extreme heat, strong wind, storms, fog or bad air.

**Technical:** a pipeline that **ingests** weather JSON from a public API, **normalises** it into tables (hourly + daily), evaluates **business rules** (thresholds) on the series, scores overall risk, and **serves/notifies** the result through CLI, REST API, dashboard, e-mail/Telegram.

## Problem it solves
People check weather manually and react late. This system turns raw numbers into **actionable, timed advice**.

| User | Benefit |
|---|---|
| Travellers | Know storms/fog before leaving; best outdoor window |
| Farmers | Irrigation/spray timing, frost & heat warnings |
| Logistics | Reroute/delay on rain, wind, fog → fewer delays |
| Event planners | Pick safe dates; trigger backup plans |
| Businesses | Protect stock/assets; staff-safety rules |

## How weather apps fetch live data
1. App sends an HTTPS **GET** request: `https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&hourly=...`
2. The server replies with **JSON** (lists of timestamps + values).
3. App parses JSON → DataFrame → applies rules. (`requests` handles HTTP, `json`/`pandas` handle data.)

## How alerts are generated
`rule = condition on data + severity + message`. Example: *"if max gust in next 24 h ≥ 15 m/s → WIND_HIGH (warn)"*.
Each fired alert carries: **what** (label), **numbers** (message), **when**, and **what to do** (advice). Severity points feed the 0–100 risk score.

## Workflow
```
User enters city → geocode → weather API fetch → JSON parse/normalise → forecast analysis
→ alert condition check → display output → save report (CSV/TXT/HTML/PNG) → notify (de-duplicated)
```

# 2️⃣ Tech Stack Options
| | Option A – Easy | Option B – Intermediate | Option C – Advanced (**this project includes B + parts of C**) |
|---|---|---|---|
| Tools | Python, requests, json, datetime | + Pandas, Matplotlib, Streamlit, SQLite | + FastAPI, scheduler, Telegram/SMTP, Docker, pytest, Next.js |
| Difficulty | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Output | Terminal weather + simple alerts | CSV/charts + web dashboard | REST API + live dashboard + push notifications + container |

**Best for students:** Option B as the base (CLI + Pandas + charts + Streamlit), then add FastAPI/notifications as "stretch" — exactly what this repo does. Open-Meteo is chosen because it needs **no API key**, so nothing sensitive can leak.

# 3️⃣ Architecture
**Input:** city name · (optional API/notification keys in `.env`) · alert thresholds (`--heat --rain --wind`, sliders, env).

**Processing:** API request → JSON parse → temperature/humidity analysis → rain/storm checks → alert generation → risk score.

**Output:** current weather · forecast summary · alert messages · saved reports/charts.

```
┌────────┐   ┌──────────┐   ┌───────────┐   ┌─────────────┐   ┌──────────────┐
│ INPUT  │──►│ PROVIDER │──►│ NORMALISE │──►│ RULE ENGINE │──►│   OUTPUTS    │
│ city   │   │ Open-Meteo│  │ DataFrames│   │ 11 rules    │   │ CLI/API/UI   │
│ limits │   │ / Simulator│ │ + SQLite  │   │ risk score  │   │ reports/notify│
└────────┘   └──────────┘   └───────────┘   └─────────────┘   └──────────────┘
```
**Data flow:** `service.build_snapshot()` is the single orchestration point; CLI, API and dashboard all call it, so logic is never duplicated. Providers are swappable because the simulator emits the *same JSON shape* as Open-Meteo.
