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
    for name, coords in VENUE_COORDINATES.items():
        if name in v_clean or v_clean in name:
            return coords
    geocoded = _geocode_venue(venue_name)
    if geocoded:
        return geocoded
    # Default fallback: central coordinates (e.g. Mumbai)
    return 19.0760, 72.8777


def fetch_venue_weather(venue_name: str) -> Dict[str, any]:
    """
    Fetches real-time / daily weather from Open-Meteo API.
    Returns:
      {
        "temperature": 28.5,
        "humidity": 75,
        "precipitation_probability": 10,
        "cloud_cover": 60,
        "wind_speed": 14.2,
        "seam_swing_advantage": True,
        "dew_risk": True,
        "summary": "Humid and overcast (Advantage: Swing Bowlers)"
      }
    """
    coords = get_venue_coords(venue_name)
    if not coords:
        return {"summary": "Weather unavailable"}

    cache_key = venue_name.lower().strip()
    cached = _WEATHER_CACHE.get(cache_key)
    if cached and (time.time() - cached[0]) < _WEATHER_TTL_SECONDS:
        return cached[1]

    lat, lon = coords
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"current=temperature_2m,relative_humidity_2m,precipitation,cloud_cover,wind_speed_10m&"
        f"timezone=auto"
    )

    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json().get("current", {})
            temp = data.get("temperature_2m", 25.0)
            humidity = data.get("relative_humidity_2m", 50)
            cloud = data.get("cloud_cover", 0)
            wind = data.get("wind_speed_10m", 10.0)

            # Analyze cricket condition implications
            seam_swing = (cloud >= 50 and humidity >= 65)
            dew_risk = (temp <= 24 and humidity >= 70)

            summary_parts = []
            if seam_swing:
                summary_parts.append("Overcast & humid — favors seam/swing bowlers")
            elif temp >= 34:
                summary_parts.append("High heat — pace fatigue factor elevated")
            else:
                summary_parts.append("Clear & balanced conditions")

            if dew_risk:
                summary_parts.append("Evening dew risk high (2nd innings batting advantage)")

            result = {
                "temperature_c": temp,
                "humidity_pct": humidity,
                "cloud_cover_pct": cloud,
                "wind_speed_kmh": wind,
                "seam_swing_advantage": seam_swing,
                "dew_risk": dew_risk,
                "summary": "; ".join(summary_parts)
            }
            _WEATHER_CACHE[cache_key] = (time.time(), result)
            return result
    except Exception as e:
        print(f"Weather API error: {e}")

    return {
        "temperature_c": 26.0,
        "humidity_pct": 55,
        "cloud_cover_pct": 20,
        "wind_speed_kmh": 12.0,
        "seam_swing_advantage": False,
        "dew_risk": False,
        "summary": "Typical playing conditions"
    }


if __name__ == "__main__":
    w = fetch_venue_weather("Wankhede Stadium")
    print("Wankhede Stadium Weather:", w)
