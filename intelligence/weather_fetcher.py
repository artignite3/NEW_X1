"""
NEW_X1 — Intelligence Layer: Weather Fetcher
Uses Open-Meteo API (free, 10k calls/day, no API key required) to fetch
current or forecast weather for major cricket venues.

Conditions evaluated:
  - Overcast / High humidity: favors seam/swing bowlers
  - Extreme heat: fatigue impact on fast bowlers
  - High dew point in evening: favors 2nd innings batters
"""

import requests
from typing import Dict, Optional

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


def get_venue_coords(venue_name: str) -> Optional[tuple[float, float]]:
    """Fuzzy lookup for venue latitude and longitude."""
    v_clean = venue_name.lower().strip()
    for name, coords in VENUE_COORDINATES.items():
        if name in v_clean or v_clean in name:
            return coords
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

            return {
                "temperature_c": temp,
                "humidity_pct": humidity,
                "cloud_cover_pct": cloud,
                "wind_speed_kmh": wind,
                "seam_swing_advantage": seam_swing,
                "dew_risk": dew_risk,
                "summary": "; ".join(summary_parts)
            }
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
