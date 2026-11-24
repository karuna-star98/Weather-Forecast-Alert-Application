# 4️⃣ Implementation Plan (10 phases)

| Phase | What to do | Why | Expected output | Beginner mistake |
|---|---|---|---|---|
| 1 Setup | Install Python 3.10+, VS Code, Git | Reproducible environment | `python --version` works | Forgetting "Add to PATH" |
| 2 Folders | Create structure (below) | Clean GitHub repo | Folder tree | Putting everything in one file |
| 3 API key setup | Open-Meteo needs none; `.env` for optional tokens | Keep secrets out of code | `.env` + `.env.example` | Committing `.env` |
| 4 Fetching | `src/providers.py` (geocode + forecast) | Get real data | Raw JSON | No timeout / error handling |
| 5 Parsing | `normalize()` → DataFrames | One consistent schema | Hourly & daily tables | Mixing units (km/h vs m/s) |
| 6 Forecast analysis | `src/analysis.py` | Summaries, comfort, best window | Next-24h summary | Using past hours as "forecast" |
| 7 Alert logic | `src/rules.py` | Turn data into warnings | Alert list + risk score | Hard-coding thresholds |
| 8 Visualisation | `src/charts.py`, Streamlit | Communicate trends | PNG dashboard / web UI | Unlabelled axes |
| 9 Reports | `src/report.py` | Proof & sharing | CSV/TXT/HTML/JSON | Overwriting files each run |
| 10 GitHub | Commit, push, README, screenshots | Portfolio proof | Public repo | Uploading `.env`/venv |

# 5️⃣ Folder structure explained
| Folder/file | Purpose |
|---|---|
| `src/` | All reusable logic (providers, rules, analysis, storage, notifier, charts, report, service) |
| `api/` | FastAPI app |
| `dashboard/` | Streamlit UI |
| `jobs/` | Scheduled refresh job |
| `db/` | SQL schema (the `.db` file is git-ignored) |
| `data/` | Static/sample data |
| `outputs/` | CSVs + charts produced by runs |
| `reports/` | TXT/HTML/JSON reports |
| `images/` | Screenshots for README |
| `docs/` | Guides & interview prep |
| `tests/` | Pytest tests |
| `main.py` | CLI entry point |
| `.env.example` | Template of settings (no secrets) |
| `.gitignore` | Stops secrets/junk from being committed |

# 6️⃣ Installation guide
**Python:** download 3.10+ from python.org (tick *Add Python to PATH* on Windows). Check: `python --version`.

**Windows**
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
**Mac / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
**Libraries:** requests, pandas, numpy, matplotlib, python-dotenv, tzdata (core) · fastapi, uvicorn (API) · streamlit, plotly (UI) · pytest, httpx (tests).

**Storing keys safely**
1. Put real values only in `.env` (read via `python-dotenv` / `os.getenv`).
2. `.env` is listed in `.gitignore` → Git never tracks it.
3. Commit only `.env.example` (blank values).
4. If you ever leak a key: **revoke/rotate it immediately** — deleting the commit is not enough.
5. Check before pushing: `git status` must not list `.env`.
