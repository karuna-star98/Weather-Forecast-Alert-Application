# 1️⃣4️⃣ Interview Preparation

### 1. Explain your project.
**HR version (30 s):** "I built a weather forecast and alert application in Python. You enter a city, it fetches live weather, analyses the next hours and days, and automatically warns about rain, extreme heat, wind, storms or poor air quality. It also saves reports and shows a dashboard."
**Technical version:** "It's a pipeline: Open-Meteo API → `requests` with retry → JSON normalised into Pandas DataFrames and SQLite → a rule engine of 11 testable rules → risk score → exposed through a CLI, a FastAPI service and a Streamlit dashboard, with Telegram/Email notifications de-duplicated for 12 hours. Because I had no weather stations, I added a deterministic simulator that outputs the same JSON shape, so everything runs offline and is testable."

### 2. What problem does it solve?
It replaces manual weather checking with automatic, explainable, timed warnings — useful for travellers, farmers, logistics and event teams.

### 3. Which technologies did you use and why?
Python (ecosystem), `requests` (HTTP), Pandas (time-series handling), SQLite (zero-setup storage), FastAPI (typed, auto-documented REST), Streamlit/Plotly (fast dashboards), Matplotlib (report charts), pytest (testing).

### 4. How do you fetch data?
HTTPS GET to Open-Meteo with latitude/longitude and the variables I need; JSON comes back; I convert units (m/s, km, °C) and load it into DataFrames. Retries with exponential back-off handle 5xx/timeouts.

### 5. What is JSON and why is it used?
A lightweight text format of key-value pairs and lists, language-independent, so any API can send structured data any client can parse.

### 6. How does the alert system work?
Each rule is a function `(context, thresholds) → Alert | None`. I roll hourly/daily data into a context (next 12 h, 24 h, 3 days), evaluate every rule, sort by severity, and compute a 0–100 risk score. Thresholds are configurable via CLI, env or UI.

### 7. How did you handle errors?
Timeouts, retries with back-off, clear `WeatherAPIError` messages (bad city, no internet), tolerance for missing values (`None/NaN`), a try/except guard around every rule, and automatic fallback to simulation.

### 8. What outputs does it generate?
Terminal report, CSV (hourly/daily/alerts), TXT/HTML/JSON reports, PNG dashboards, a SQLite history and alert log.

### 9. How would you improve it?
Radar map layer, multi-provider ensemble, SMS/WhatsApp, geofencing, calendar integration, caching with Redis, ML nowcasting, authentication and rate-limiting on the API, CI/CD with GitHub Actions.

### 10. Explain it to a non-technical person.
"I made a program that watches the weather for a city and warns you — like 'heavy rain at 6 pm, take an umbrella' — so you can plan ahead."

### Bonus questions
- **How do you avoid alert spam?** De-duplicate per (location, rule) for 12 h using the `alert_log` table.
- **How do you keep API keys safe?** `.env` + `.gitignore`, commit `.env.example`, rotate if leaked. (Open-Meteo needs no key.)
- **Why a simulator?** Testing, offline demos, reproducibility, forcing rare conditions (storm) on demand.
- **How do you test rules?** Hand-built DataFrames (calm → no alerts; extreme → specific alerts) plus golden scenario tests.
- **Timezones/units?** Request `timezone=auto`, use m/s, mm, °C, km everywhere; convert at the boundary.
