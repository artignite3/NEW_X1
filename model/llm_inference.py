"""
NEW_X1 — Intelligence Layer: Explainability (SHAP + Ollama Llama 3.2 3B)
Synthesizes natural language analyst explanations via local Ollama.

Zero API cost, zero rate limits, runs completely offline on CPU.
Configuration is read from .env (OLLAMA_BASE_URL, OLLAMA_MODEL).
"""

import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
import time
from typing import List, Tuple

try:
    import httpx
    import ollama
    # Hard timeout: a hung/unreachable Ollama must never stall API responses.
    # Use 127.0.0.1 — 'localhost' can resolve to ::1 and hang on TCP connect.
    _raw_host = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    _host = _raw_host.replace("localhost", "127.0.0.1")
    _client = ollama.Client(
        host=_host,
        timeout=httpx.Timeout(60.0, connect=3.0),
    )
    HAS_OLLAMA = True
except ImportError:
    _client = None
    HAS_OLLAMA = False

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

# Availability probe cache — avoids re-stalling on every explanation call
_avail_cache: tuple[float, bool] = (0.0, False)
_AVAIL_TTL = 60.0


def ollama_available() -> bool:
    """True when the Ollama server is reachable and the model is pulled."""
    global _avail_cache
    now = time.time()
    if now - _avail_cache[0] < _AVAIL_TTL:
        return _avail_cache[1]
    ok = False
    if HAS_OLLAMA:
        try:
            models = _client.list()
            names = [m.get("model", "") for m in models.get("models", [])]
            ok = any(OLLAMA_MODEL in n for n in names) 
        except Exception:
            ok = False
    _avail_cache = (now, ok)
    return ok


def generate_player_explanation(
    player_name: str,
    role: str,
    predicted_score: float,
    shap_top3: List[Tuple[str, float]],
    pitch_type: str = "Neutral",
    weather_summary: str = "Clear conditions",
    is_selected: bool = True,
    driver_labels: List[str] = None,
    return_source: bool = False,
) -> str | tuple[str, bool]:
    """
    Synthesizes a 2-sentence expert analyst explanation for player selection/exclusion.
    Falls back to a high-quality heuristic when Ollama is offline.
    """
    status_word = "selected for the optimal XI" if is_selected else "left out of the optimal XI"

    if driver_labels:
        reasons_text = ", ".join(driver_labels)
    elif shap_top3:
        reasons_text = ", ".join(f"{feat.replace('_', ' ')}: {val:+.1f} pts" for feat, val in shap_top3)
    else:
        reasons_text = "feature attribution is unavailable for this prediction"

    if not ollama_available():
        if is_selected:
            result = (
                f"{player_name} is selected with {predicted_score:.1f} projected performance points. "
                f"Key drivers: {reasons_text}, under {pitch_type.lower()} conditions ({weather_summary.lower()})."
            )
        else:
            result = (f"{player_name} misses out — {reasons_text} did not offset a lower projected score "
                      f"({predicted_score:.1f}) for this {pitch_type.lower()} venue.")
        return (result, False) if return_source else result

    prompt = f"""You are a senior cricket performance analyst.
Write exactly a 2-sentence explanation for why {player_name} ({role}) was {status_word}.

Context:
- Projected Score: {predicted_score:.1f}
- Key analytical drivers: {reasons_text}
- Venue pitch profile: {pitch_type}
- Weather: {weather_summary}

Be concise, confident, analytical, and mention at least one key stat/driver.
Reply with ONLY the two sentences.
"""
    try:
        resp = _client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.2},
        )
        result = resp["message"]["content"].strip()
        return (result, True) if return_source else result
    except Exception:
        if is_selected:
            result = (
                f"{player_name} is selected with {predicted_score:.1f} projected performance points. "
                f"Key drivers: {reasons_text}."
            )
        else:
            result = (f"{player_name} misses out — projected {predicted_score:.1f} points "
                      f"was not enough for this {pitch_type.lower()} venue.")
        return (result, False) if return_source else result


def generate_team_summary(
    team_lines: List[str],
    pitch_type: str,
    weather_summary: str,
    expected_total: float,
    captain: str,
    return_source: bool = False,
) -> str | tuple[str, bool]:
    """Generates the closing paragraph summarizing the whole XI selection."""
    team_text = "\n".join(team_lines)

    if not ollama_available():
        result = (
            f"The selected XI projects {expected_total:.0f} combined performance points at "
            f"a {pitch_type.lower()} venue ({weather_summary.lower()}). "
            f"{captain} has the highest calculated captaincy upside."
        )
        return (result, False) if return_source else result

    prompt = f"""You are a senior cricket performance analyst presenting the Optimal XI.
Write exactly one short paragraph (3-4 sentences) summarizing why this team was chosen.

Selected XI (player, role, projected points):
{team_text}

Venue: {pitch_type} pitch. Weather: {weather_summary}.
Projected total: {expected_total:.0f} points. Recommended captain: {captain}.

Mention the venue/weather influence and the captain choice. Reply with ONLY the paragraph.
"""
    try:
        resp = _client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3},
        )
        result = resp["message"]["content"].strip()
        return (result, True) if return_source else result
    except Exception:
        result = (
            f"The optimizer projects {expected_total:.0f} combined points from this XI at a "
            f"{pitch_type.lower()} venue. {captain} is the recommended captaincy pick."
        )
        return (result, False) if return_source else result


if __name__ == "__main__":
    top3 = [("avg_runs_per_inning_roll3_mean", 14.5), ("venue_avg_pts", 8.2), ("avg_economy_rate_per_inning", -2.1)]
    print("Sample Analyst Explanation:\n", generate_player_explanation(
        "Virat Kohli", "BAT", 78.4, top3, "Batting Pitch", "Humid and overcast", True))
