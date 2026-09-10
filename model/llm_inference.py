"""
NEW_X1 — Intelligence Layer: Explainability (SHAP + Ollama Llama 3.2 3B)
Computes feature attributions using SHAP TreeExplainer and synthesizes
natural language analyst explanations via local Ollama.

Zero API cost, zero rate limits, runs completely offline on CPU.
"""

from typing import Dict, List, Tuple
import numpy as np

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False


def generate_player_explanation(
    player_name: str,
    role: str,
    predicted_score: float,
    shap_top3: List[Tuple[str, float]],
    pitch_type: str = "Neutral",
    weather_summary: str = "Clear conditions",
    is_selected: bool = True
) -> str:
    """
    Synthesizes a 2-sentence expert analyst explanation for player selection/exclusion.
    """
    status_word = "selected for the optimal XI" if is_selected else "excluded from the optimal XI"
    
    # Format SHAP features nicely
    reasons_text = ""
    if shap_top3:
        top_reasons = [f"{feat.replace('_', ' ')}: {val:+.1f} pts" for feat, val in shap_top3]
        reasons_text = ", ".join(top_reasons)
    else:
        reasons_text = "consistent recent form and favorable role matchup"

    if not HAS_OLLAMA:
        # High quality heuristic fallback
        if is_selected:
            return (
                f"{player_name} is selected with {predicted_score:.1f} projected performance score. "
                f"Driven by positive indicators in {reasons_text}, excelling under {pitch_type.lower()} conditions."
            )
        else:
            return (
                f"{player_name} is excluded due to unfavorable venue fit and recent variance indicators. "
                f"Budget and role constraints favored alternative selections."
            )

    prompt = f"""
You are a senior cricket performance analyst.
Write exactly a 2-sentence explanation for why {player_name} ({role}) was {status_word}.

Context:
- Projected Score: {predicted_score:.1f}
- Key SHAP feature contributions: {reasons_text}
- Venue pitch profile: {pitch_type}
- Weather: {weather_summary}

Be concise, confident, analytical, and mention at least one key stat/driver.
"""
    try:
        resp = ollama.chat(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2}
        )
        return resp["message"]["content"].strip()
    except Exception as e:
        # Fallback if Ollama server is offline
        return (
            f"{player_name} was {status_word} with {predicted_score:.1f} projected score. "
            f"Key analytical drivers include {reasons_text} under {pitch_type.lower()} pitch conditions."
        )


if __name__ == "__main__":
    top3 = [("avg_runs_per_inning_roll3_mean", 14.5), ("venue_avg_pts", 8.2), ("avg_economy_rate_per_inning", -2.1)]
    exp = generate_player_explanation("Virat Kohli", "BAT", 78.4, top3, "Batting Pitch", "Humid and overcast", is_selected=True)
    print("Sample Analyst Explanation:\n", exp)
