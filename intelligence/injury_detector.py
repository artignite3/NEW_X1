"""
NEW_X1 — Intelligence Layer: Injury, Availability & Playing Probability Engine

Analyzes player availability and injury news via Google News RSS + Local Ollama / Rule Heuristics.

Provides:
  1. Injury Status & Multiplier
  2. Playing XI Selection Probability Adjustment
  3. 80% Confidence Interval (Z=1.28) for score ranges
  4. Captaincy Upside Score (Mean + 0.30 * Std)
"""

import json
import re
from typing import Dict, Any, Optional

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

# ── Multiplier Tables ────────────────────────────────────────────────────────
INJURY_MULTIPLIERS = {
    "FIT":       1.00,
    "UNKNOWN":   0.90,
    "DOUBTFUL":  0.45,
    "INJURED":   0.05,
    "RESTED":    0.00,
    "SUSPENDED": 0.00,
}

PLAYING_PROB_ADJUSTMENTS = {
    "FIT":       1.10,
    "UNKNOWN":   1.00,
    "DOUBTFUL":  0.40,
    "INJURED":   0.00,
    "RESTED":    0.00,
    "SUSPENDED": 0.00,
}

CI_Z_SCORE = 1.28               # 80% Confidence Interval
CAPTAIN_VARIANCE_WEIGHT = 0.30  # Ceil boost for boom/bust captains

RSS_URL = "https://news.google.com/rss/search?q=cricket+injury+squad+update&hl=en"


def fetch_injury_feed(limit: int = 20) -> list[str]:
    """Fetches titles from cricket injury Google News RSS."""
    if not HAS_FEEDPARSER:
        return []
    try:
        feed = feedparser.parse(RSS_URL)
        return [entry.title for entry in feed.entries[:limit]]
    except Exception as e:
        print(f"[WARN] RSS fetch error: {e}")
        return []


def classify_headline_with_llm(headline: str, model: str = "llama3.2:3b") -> Dict[str, Any]:
    """Uses Ollama or keyword heuristics to extract player and status."""
    lower = headline.lower()

    # Fast heuristic check first
    rule_status = None
    if any(w in lower for w in ["ruled out", "fracture", "surgery", "torn", "injured"]):
        rule_status = "INJURED"
    elif any(w in lower for w in ["doubtful", "niggle", "uncertain", "unlikely to play", "fitness test"]):
        rule_status = "DOUBTFUL"
    elif "rested" in lower:
        rule_status = "RESTED"
    elif "suspended" in lower or "banned" in lower:
        rule_status = "SUSPENDED"
    elif any(w in lower for w in ["passed fit", "returns", "fit to play", "cleared"]):
        rule_status = "FIT"

    if HAS_OLLAMA:
        prompt = f"""
Analyze this cricket news headline:
"{headline}"

Extract the player's name and availability status.
Status must be one of: [FIT, DOUBTFUL, INJURED, RESTED, SUSPENDED, UNKNOWN]

Output ONLY JSON:
{{"player": "Player Name", "status": "STATUS"}}
If no player or status found:
{{"player": null, "status": "UNKNOWN"}}
"""
        try:
            resp = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1}
            )
            match = re.search(r"\{.*?\}", resp["message"]["content"], re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                if parsed.get("player") and parsed.get("status") in INJURY_MULTIPLIERS:
                    return parsed
        except Exception:
            pass

    return {"player": None, "status": rule_status or "UNKNOWN"}


def get_active_injury_reports() -> Dict[str, Dict[str, Any]]:
    """
    Returns active injury status per player:
    {
      "Player Name": {
         "status": "DOUBTFUL",
         "multiplier": 0.45,
         "headline": "...",
         "playing_prob_factor": 0.40
      }
    }
    """
    headlines = fetch_injury_feed()
    reports = {}

    for h in headlines:
        extracted = classify_headline_with_llm(h)
        player = extracted.get("player")
        status = extracted.get("status", "UNKNOWN").upper()

        if player and status in INJURY_MULTIPLIERS and status != "UNKNOWN":
            reports[player] = {
                "status": status,
                "multiplier": INJURY_MULTIPLIERS.get(status, 0.90),
                "playing_prob_factor": PLAYING_PROB_ADJUSTMENTS.get(status, 1.00),
                "headline": h
            }

    return reports


def calculate_player_injury_adjustments(
    base_score: float,
    status: str = "FIT",
    career_matches: int = 25,
    player_std: float = 18.0
) -> Dict[str, Any]:
    """
    Applies comprehensive injury and availability adjustment:
      1. Injury multiplier
      2. Playing probability adjustment
      3. 80% Confidence Interval bounds (Low, High)
      4. Captain ceiling score
    """
    status_upper = status.upper() if status else "FIT"
    inj_mult = INJURY_MULTIPLIERS.get(status_upper, 0.90)
    prob_adj = PLAYING_PROB_ADJUSTMENTS.get(status_upper, 1.00)

    # Experience base probability: career_matches / 20 (capped at 1.0)
    exp_factor = min(career_matches / 20.0, 1.0)
    effective_playing_prob = min(prob_adj * exp_factor, 1.0)

    # Final adjusted score
    final_score = round(base_score * inj_mult * effective_playing_prob, 1)

    # 80% Confidence Interval: [score - 1.28*std, score + 1.28*std]
    ci_margin = round(CI_Z_SCORE * (player_std * inj_mult), 1)
    score_low = max(0.0, round(final_score - ci_margin, 1))
    score_high = round(final_score + ci_margin, 1)

    # Captain upside ceiling (rewards high variance boom players)
    captain_ceiling = round(final_score + (CAPTAIN_VARIANCE_WEIGHT * player_std * inj_mult), 1)

    return {
        "status": status_upper,
        "injury_multiplier": inj_mult,
        "playing_probability": round(effective_playing_prob * 100, 1),
        "final_score": final_score,
        "score_ci_low": score_low,
        "score_ci_high": score_high,
        "captain_upside": captain_ceiling
    }


if __name__ == "__main__":
    print("Testing Injury & Availability Engine...")
    result = calculate_player_injury_adjustments(base_score=60.0, status="DOUBTFUL", career_matches=30, player_std=20.0)
    print("Doubtful Player Adjustment:", result)
    fit_result = calculate_player_injury_adjustments(base_score=60.0, status="FIT", career_matches=30, player_std=20.0)
    print("Fit Player Adjustment:", fit_result)
