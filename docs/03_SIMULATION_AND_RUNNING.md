# 8️⃣ Virtual Simulation
No professional weather station? No problem — `src/simulator.py` creates a **realistic virtual weather feed**.

- **City-wise representation:** each city has a climate profile (mean temp, daily swing, humidity, rain chance, wind, UV) — Bhusawal/Delhi hot & dry, Mumbai humid & rainy, Shimla cold & foggy, etc. Unknown cities get stable pseudo-coordinates.
- **Same shape as the real API:** the simulator returns an Open-Meteo-style JSON, so *the same parser, rules, charts and reports* run in both modes.
- **Deterministic:** same city + scenario + day ⇒ same numbers (reproducible screenshots & tests).
- **Scenarios:** `normal, heatwave, monsoon, storm, fog, cold, auto` — force an alert on demand.
- **Thresholds checked:** rain probability ≥ 60 %, daily rain ≥ 50 mm, max temp ≥ 40 °C, feels-like ≥ 45 °C, hot + humid, gust ≥ 15 m/s, UV ≥ 8, visibility < 1 km, min temp ≤ 5 °C, AQI ≥ 150, thunderstorm codes.
- **Alert creation:** every fired rule → `Alert(code, label, severity, message, advice, when)`; severities add up to the risk score.
- **Reports:** CSV (hourly/daily/alerts), TXT, HTML (charts embedded), JSON, PNG charts.
- **In real life:** only the provider changes (`--live`). Add a scheduler (`jobs/refresh.py` every 2–3 h) and Telegram/Email and it becomes a monitoring service.

**Screenshots to capture:** project folder · terminal in simulate mode · current-weather block · forecast table · alerts block · generated CSV · dashboard PNG · Streamlit dashboard · GitHub repo page.
**Outputs to upload:** `outputs/*.csv`, `outputs/charts/*.png`, `reports/*.html|txt|json`, `images/*`.
**Never upload:** `.env`, API/bot tokens, SMTP passwords, `.venv`, `db/*.db` (can contain raw payloads/alert logs), personal chat IDs/emails.

# 9️⃣ How to Run
```bash
python main.py --city Delhi --simulate                      # simulation mode
python main.py --city Mumbai --simulate --scenario monsoon  # pick a scenario
python main.py --city London --live                         # API mode (internet)
python main.py --serve                                      # API mode as a service → /docs
python main.py --dashboard                                  # Streamlit dashboard
```
**Expected terminal output:** banner → CURRENT WEATHER → NEXT 24 HOURS → FORECAST table → RISK SCORE bar → ALERTS list → NOTIFICATIONS (dry-run) → SAVED FILES. See `docs/sample_terminal_output.txt`.

**Generated files:** `outputs/<city>_<time>_{hourly,daily,alerts}.csv`, `outputs/charts/<city>_dashboard.png`, `reports/<city>_<time>_report.{txt,html}` and `_summary.json`.
If the live API is unreachable the app prints a warning and **falls back to simulation** (use `--no-fallback` to disable).

# 1️⃣0️⃣ GitHub Upload Steps
```bash
git init
git add .
git status                      # confirm .env is NOT listed
git commit -m "feat: initial weather forecast & alert application"
git branch -M main
git remote add origin https://github.com/<username>/Weather-Forecast-Alert-Application.git
git push -u origin main
```
1. github.com → **New repository** → name below → *Public* → **don't** add README (you have one).
2. Run the commands above.
3. Commit messages: `feat:` new feature · `fix:` bug · `docs:` docs · `test:` tests · `chore:` setup.

| | |
|---|---|
| **Repo name** | `Weather-Forecast-Alert-Application` |
| **Description** | Python weather forecast & rule-based alert system with FastAPI, Streamlit dashboard, Open-Meteo integration, offline simulation and Telegram/Email notifications |
| **Topics** | `python` `weather` `weather-api` `open-meteo` `fastapi` `streamlit` `pandas` `matplotlib` `alert-system` `automation` `data-visualization` `api-integration` `sqlite` |

Rules: never upload API keys · use `.env.example` not `.env` · keep `.gitignore`. Add screenshots to `images/` and outputs to `outputs/` + `reports/` and commit them.

# 1️⃣2️⃣ Proof-Building Strategy (6 days)
| Day | Work | Commit message | Screenshot |
|---|---|---|---|
| 1 | Setup, folders, venv, `.gitignore`, `.env.example`, config | `chore: project skeleton and config` | Folder tree |
| 2 | `providers.py` (geocode + forecast), error handling | `feat: open-meteo integration with retry` | Raw JSON / first fetch |
| 3 | `normalize()`, `simulator.py`, `storage.py` | `feat: normalisation, simulator, sqlite storage` | DataFrame head |
| 4 | `rules.py`, risk score, notifier, tests | `feat: alert engine, risk score, notifications` + `test: rule tests` | Alert output |
| 5 | `charts.py`, `report.py`, Streamlit, FastAPI | `feat: charts, reports, dashboard, api` | Dashboard PNG, UI, CSV |
| 6 | README, docs, screenshots, tidy | `docs: readme, guides, screenshots` | GitHub repo page |

# 1️⃣3️⃣ Screenshots / Outputs checklist
1. Project folder (VS Code explorer)  2. Simulation terminal run  3. Current weather block  4. Forecast table  5. Alert messages  6. CSV opened in Excel  7. `*_dashboard.png` chart  8. Streamlit dashboard  9. FastAPI `/docs` page  10. GitHub repo preview.
Save into `images/` with clear names (`01_folder.png`, `02_terminal_simulation.png`, ...).
