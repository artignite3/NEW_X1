"""
NEW_X1 — Intelligence Layer: Pitch & Venue Analyzer (PAF Score).
Date-safe historical reports take priority when sufficient evidence exists.
They are descriptive and apply neutral multipliers. The curated T20 priors
remain a labelled fallback; unsupported venue/format combinations are neutral.
"""

from typing import Dict, Any

from intelligence.venue_history import report as historical_report

# Curated pitch baseline profiles for prominent venues
VENUE_PROFILES = {
    # T20 Baselines: High-scoring batting paradises
    "m chinnaswamy stadium": {
        "category": "BATTING",
        "avg_1st_innings": 185,
        "boundary_pct": 21.5,
        "batter_mult": 1.12,
        "pacer_mult": 0.90,
        "spinner_mult": 0.88,
        "description": "Short boundaries and fast outfield; heavily favors aggressive top-order batters."
    },
    "wankhede stadium": {
        "category": "BATTING",
        "avg_1st_innings": 180,
        "boundary_pct": 19.8,
        "batter_mult": 1.10,
        "pacer_mult": 0.95,
        "spinner_mult": 0.92,
        "description": "True bounce and carry with evening dew; batting first or second favors strokeplay."
    },
    "eden gardens": {
        "category": "NEUTRAL",
        "avg_1st_innings": 168,
        "boundary_pct": 18.2,
        "batter_mult": 1.02,
        "pacer_mult": 1.02,
        "spinner_mult": 1.05,
        "description": "Balanced pitch offering pace off the wicket and grip for spinners in the middle overs."
    },
    "ma chidambaram stadium": {
        "category": "SPIN FRIENDLY",
        "avg_1st_innings": 158,
        "boundary_pct": 15.1,
        "batter_mult": 0.92,
        "pacer_mult": 0.95,
        "spinner_mult": 1.20,
        "description": "Dry and slow surface; heavy turn and grip for wrist and finger spinners."
    },
    "chepauk": {
        "category": "SPIN FRIENDLY",
        "avg_1st_innings": 158,
        "boundary_pct": 15.1,
        "batter_mult": 0.92,
        "pacer_mult": 0.95,
        "spinner_mult": 1.20,
        "description": "Dry and abrasive; prime conditions for spin bowlers."
    },
    "the gabba": {
        "category": "BOWLING",
        "avg_1st_innings": 162,
        "boundary_pct": 16.5,
        "batter_mult": 0.95,
        "pacer_mult": 1.18,
        "spinner_mult": 0.90,
        "description": "Extra bounce and pace; seam bowlers get steep lift and seam movement."
    },
    "melbourne cricket ground": {
        "category": "NEUTRAL",
        "avg_1st_innings": 160,
        "boundary_pct": 15.8,
        "batter_mult": 0.98,
        "pacer_mult": 1.05,
        "spinner_mult": 1.02,
        "description": "Large square boundaries; two-paced with reward for disciplined bowling."
    },
    "dubai international cricket stadium": {
        "category": "NEUTRAL",
        "avg_1st_innings": 156,
        "boundary_pct": 15.4,
        "batter_mult": 0.98,
        "pacer_mult": 1.04,
        "spinner_mult": 1.06,
        "description": "Ring of fire venue; ring-fenced bounce, assists cutters and seam in early overs."
    },
}


def get_venue_profile(venue_name: str, format_type: str = "t20", *,
                      as_of: str | None = None, gender: str = "male") -> Dict[str, Any]:
    """
    Return a format-scoped prior without presenting curated numbers as statistics.
    """
    v_clean = venue_name.lower().strip()
    if not v_clean:
        v_clean = "unknown venue"
    fmt = format_type.lower()
    if as_of:
        empirical = historical_report(venue_name, fmt, as_of, gender)
        if empirical is not None:
            return empirical
    if fmt == "t20":
        for key, profile in VENUE_PROFILES.items():
            if key in v_clean or v_clean in key:
                return {**profile, "avg_1st_innings": None, "boundary_pct": None,
                        "source": "curated_prior", "format": fmt, "sample_size": None}

    # Default neutral profile
    return {
        "category": "NEUTRAL",
        "avg_1st_innings": None,
        "boundary_pct": None,
        "source": "unavailable",
        "format": fmt,
        "sample_size": None,
        "batter_mult": 1.0,
        "pacer_mult": 1.0,
        "spinner_mult": 1.0,
        "description": "No validated venue profile for this format; neutral adjustments applied."
    }


def pitch_multiplier(role: str, bowling_style: str, profile: Dict[str, Any]) -> float:
    """Unknown bowling types receive a neutral bowling multiplier."""
    style = (bowling_style or "").lower()
    bowling = 1.0
    if any(word in style for word in ("spin", "break", "orthodox", "chinaman")):
        bowling = profile.get("spinner_mult", 1.0)
    elif any(word in style for word in ("fast", "medium", "pace")):
        bowling = profile.get("pacer_mult", 1.0)
    batting = profile.get("batter_mult", 1.0)
    if role in ("BAT", "WK"):
        return batting
    if role == "AR":
        return (batting + bowling) / 2
    return bowling


def adjust_player_score(predicted_score, player_role, venue_profile, bowling_style=""):
    return round(predicted_score * pitch_multiplier(player_role.upper(), bowling_style, venue_profile), 2)


if __name__ == "__main__":
    profile = get_venue_profile("Chinnaswamy")
    print("Venue Profile:", profile)
    adjusted = adjust_player_score(60.0, "BAT", profile)
    print("Adjusted score for Batter (raw=60.0):", adjusted)
