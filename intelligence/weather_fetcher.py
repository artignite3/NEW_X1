"""
NEW_X1 — Intelligence Layer: Weather Fetcher
Uses Open-Meteo API (free, 10k calls/day, no API key required) to fetch
current or forecast weather for major cricket venues.

Conditions evaluated:
  - Overcast / High humidity: favors seam/swing bowlers
  - Extreme heat: fatigue impact on fast bowlers
  - High dew point in evening: favors 2nd innings batters
"""

import time
from datetime import date, timedelta
import statistics
import requests
from typing import Dict, Optional

# Weather responses cached for 30 minutes per venue (forecasts change slowly)
_WEATHER_CACHE: dict[str, tuple[float, Dict]] = {}
_WEATHER_TTL_SECONDS = 30 * 60

# Coordinates for major international and IPL cricket grounds
VENUE_COORDINATES = {
    # India
    "wankhede stadium": (18.9389, 72.8258),
    "m chinnaswamy stadium": (12.9788, 77.5996),
    "eden gardens": (22.5645, 88.3433),
    "narendra modi stadium": (23.0917, 72.5975),
    "feroz shah kotla": (28.6378, 77.2423),
    "arun jaitley stadium": (28.6378, 77.2423),
    "rajiv gandhi international stadium": (17.4065, 78.5505),
    "ma chidambaram stadium": (13.0628, 80.2793),
    "himachal pradesh cricket association stadium": (32.1976, 76.3259),
    "dharamsala": (32.1976, 76.3259),
    "punjab cricket association is bindra stadium": (30.6908, 76.7374),
    "mohali": (30.6908, 76.7374),
    # Australia
    "melbourne cricket ground": (-37.8200, 144.9834),
    "mcg": (-37.8200, 144.9834),
    "sydney cricket ground": (-33.8915, 151.2249),
    "scg": (-33.8915, 151.2249),
    "adelaide oval": (-34.9155, 138.5961),
    "the gabba": (-27.4858, 153.0381),
    "perth stadium": (-31.9512, 115.8890),
    "optus stadium": (-31.9512, 115.8890),
    # England
    "lord's": (51.5297, -0.1724),
    "the oval": (51.4837, -0.1150),
    "edgbaston": (52.4557, -1.9029),
    "headingley": (53.8177, -1.5818),
    "old trafford": (53.4566, -2.2873),
    "trent bridge": (52.9369, -1.1322),
    # UAE
    "dubai international cricket stadium": (25.0472, 55.2198),
    "sharjah cricket stadium": (25.3302, 55.4209),
    "sheikh zayed stadium": (24.4079, 54.5444),
}


# Cache for geocoded venue coordinates and fetched weather (TTL handled by caller)
_GEOCODE_CACHE: dict[str, tuple[float, float]] = {}


def _geocode_venue(venue_name: str) -> Optional[tuple[float, float]]:
    """Geocodes the city portion of a venue string via Open-Meteo geocoding (free, no key)."""
    if not venue_name:
        return None
    if venue_name.lower() in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[venue_name.lower()]

    # Venue strings usually look like "Ekana Cricket Stadium, Lucknow" — take the last part
    city = venue_name.split(",")[-1].strip()
    if not city:
        return None
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=5,
        )
        if r.status_code == 200:
            results = r.json().get("results") or []
            if results:
                coords = (float(results[0]["latitude"]), float(results[0]["longitude"]))
                _GEOCODE_CACHE[venue_name.lower()] = coords
                return coords
    except Exception as e:
        print(f"Geocoding error for '{venue_name}': {e}")
    return None


def get_venue_coords(venue_name: str) -> Optional[tuple[float, float]]:
    """Fuzzy lookup for venue latitude and longitude, with geocoding fallback."""
    v_clean = venue_name.lower().strip()
    if not v_clean or v_clean in {"neutral venue", "venue tbc"}:
        return None
    for name, coords in VENUE_COORDINATES.items():
        if name in v_clean or v_clean in name:
            return coords
    geocoded = _geocode_venue(venue_name)
    if geocoded:
        return geocoded
    return None


def fetch_venue_weather(venue_name: str, match_date: str | None = None) -> Dict:
    """Date-specific forecast, or explicit unavailability with neutral scoring."""
    requested = date.fromisoformat(match_date) if match_date else date.today()
    unavailable = {"available": False, "date": requested.isoformat(),
                   "seam_swing_advantage": False, "dew_risk": False,
                   "summary": "Weather unavailable; no weather adjustment applied"}
    if requested < date.today() or requested > date.today() + timedelta(days=15):
        return {**unavailable, "summary": "Date outside forecast window; no weather adjustment applied"}
    key = (venue_name.strip().lower(), requested.isoformat())
    cached = _WEATHER_CACHE.get(key)
    if cached and time.time() - cached[0] < _WEATHER_TTL_SECONDS:
        return cached[1]
    coords = get_venue_coords(venue_name)
    if not coords:
        return unavailable
    try:
        response = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": coords[0], "longitude": coords[1], "timezone": "auto",
            "start_date": requested.isoformat(), "end_date": requested.isoformat(),
            "hourly": "temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m,precipitation_probability",
        }, timeout=5)
        response.raise_for_status()
        hourly = response.json()["hourly"]
        def mean(name):
            values = [v for v in hourly[name][9:22] if v is not None]
            if not values:
                raise ValueError("Incomplete weather response")
            return round(statistics.mean(values), 1)
        temp, humidity, cloud = mean("temperature_2m"), mean("relative_humidity_2m"), mean("cloud_cover")
        seam = cloud >= 50 and humidity >= 65
        dew = temp <= 24 and humidity >= 70
        result = {"available": True, "date": requested.isoformat(), "source": "Open-Meteo",
                  "temperature_c": temp, "humidity_pct": humidity, "cloud_cover_pct": cloud,
                  "wind_speed_kmh": mean("wind_speed_10m"),
                  "precipitation_probability": mean("precipitation_probability"),
                  "seam_swing_advantage": seam, "dew_risk": dew,
                  "summary": f"{requested}: daytime/evening forecast; " + ("humid and overcast, favors seam" if seam else "balanced conditions")}
        _WEATHER_CACHE[key] = (time.time(), result)
        return result
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return unavailable


def weather_multiplier(role: str, bowling_style: str, weather: dict | None) -> float:
    if not weather or not weather.get("available"):
        return 1.0
    style = (bowling_style or "").lower()
    pace = any(word in style for word in ("fast", "medium", "pace"))
    spin = any(word in style for word in ("spin", "break", "orthodox", "chinaman"))
    factor = 1.0
    if role in ("BOWL", "AR"):
        if pace and weather.get("seam_swing_advantage"):
            factor *= 1.08
        if pace and weather.get("temperature_c", 0) >= 34:
            factor *= 0.95
        if spin and weather.get("dew_risk"):
            factor *= 0.95
    return (1 + factor) / 2 if role == "AR" else factor
