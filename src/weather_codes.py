"""WMO weather-code lookup (used by Open-Meteo) -> human text + emoji."""

WMO = {
    0: ("Clear sky", "☀️"), 1: ("Mainly clear", "🌤️"), 2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"), 45: ("Fog", "🌫️"), 48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"), 53: ("Drizzle", "🌦️"), 55: ("Dense drizzle", "🌦️"),
    61: ("Light rain", "🌧️"), 63: ("Moderate rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
    71: ("Light snow", "🌨️"), 73: ("Snow", "🌨️"), 75: ("Heavy snow", "❄️"),
    80: ("Rain showers", "🌦️"), 81: ("Heavy showers", "🌧️"), 82: ("Violent showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm + hail", "⛈️"), 99: ("Severe thunderstorm", "⛈️"),
}
STORM_CODES = {95, 96, 99}


def describe(code) -> str:
    try:
        return WMO.get(int(code), ("Unknown", "❓"))[0]
    except (TypeError, ValueError):
        return "Unknown"


def icon(code) -> str:
    try:
        return WMO.get(int(code), ("Unknown", "❓"))[1]
    except (TypeError, ValueError):
        return "❓"
