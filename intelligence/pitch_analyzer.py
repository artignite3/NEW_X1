"""
NEW_X1 — Intelligence Layer: Pitch & Venue Analyzer (PAF Score)
Calculates the Pitch Adjustment Factor (PAF) for cricket venues using historical
match data.

Categories:
  - BATTING: High avg 1st innings score (> 175 in T20), high boundary % (multiplier: 1.10 for batters)
  - BOWLING: Low avg score (< 145 in T20), high wickets per match (multiplier: 1.15 for bowlers)
  - SPIN FRIENDLY: High spin wicket ratio (multiplier: 1.15 for spinners)
  - NEUTRAL: Balanced conditions (multiplier: 1.0)
"""

from typing import Dict, Any

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


def get_venue_profile(venue_name: str, format_type: str = "t20") -> Dict[str, Any]:
    """
    Looks up pitch profile for a venue, with fallbacks based on format.
    """
    v_clean = venue_name.lower().strip()
    for key, profile in VENUE_PROFILES.items():
        if key in v_clean or v_clean in key:
            return profile

    # Default neutral profile
    return {
        "category": "NEUTRAL",
        "avg_1st_innings": 165 if format_type.lower() == "t20" else 265,
        "boundary_pct": 17.0,
        "batter_mult": 1.0,
        "pacer_mult": 1.0,
        "spinner_mult": 1.0,
        "description": "Standard sporting surface with balanced assistance for all skillsets."
    }


def adjust_player_score(
    predicted_score: float,
    player_role: str,
    venue_profile: Dict[str, Any]
) -> float:
    """
    Applies the venue PAF multiplier to a player's raw predicted performance score.
    """
    role = player_role.upper()
    multiplier = 1.0

    if "BAT" in role or "WK" in role:
        multiplier = venue_profile.get("batter_mult", 1.0)
    elif "BOWL" in role:
        # Check if spinner or pacer (default to pacer if unspecified)
        multiplier = max(venue_profile.get("pacer_mult", 1.0), venue_profile.get("spinner_mult", 1.0))
    elif "AR" in role:
        # Allrounders get a blended factor
        b_mult = venue_profile.get("batter_mult", 1.0)
        bw_mult = max(venue_profile.get("pacer_mult", 1.0), venue_profile.get("spinner_mult", 1.0))
        multiplier = (b_mult + bw_mult) / 2.0

    return round(predicted_score * multiplier, 2)


if __name__ == "__main__":
    profile = get_venue_profile("Chinnaswamy")
    print("Venue Profile:", profile)
    adjusted = adjust_player_score(60.0, "BAT", profile)
    print("Adjusted score for Batter (raw=60.0):", adjusted)
