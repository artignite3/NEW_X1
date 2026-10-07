"""
NEW_X1 — Intelligence Layer: Team Analyst Report Orchestrator
Bridges the generation cache (feature rows + player entries), the SHAP
driver extractor, and the Ollama analyst (llm_inference).

Produced report shape:
  {
    "generated_with": "ollama" | "heuristic",
    "team_report": "<paragraph>",
    "players": [{"display_name", "role", "selected", "explanation",
                 "drivers": [{"feature", "label", "impact"}]}],
    "context": {"pitch_category", "weather_summary", "venue", "date", "format"}
  }
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List

from intelligence.shap_explainer import pretty_feature
from model import llm_inference


def generate_team_report(cached: dict, drivers_by_player: Dict[str, List[dict]]) -> dict:
    players = cached["players"]                 # fantasy_key -> entry
    selected_keys = cached["selected"]
    pitch_category = cached.get("pitch_category", "NEUTRAL")
    weather_summary = cached.get("weather_summary", "Typical playing conditions")

    # LLM narration is reserved for the selected XI — the bench gets driver
    # chips only (11 calls instead of 31 keeps CPU-only Ollama responsive).
    jobs = [(k, players[k], True) for k in selected_keys if k in players]

    explanations: Dict[str, str] = {}
    used_ollama = []

    def run(job):
        key, p, is_sel = job
        drivers = drivers_by_player.get(key, [])
        top3 = [(d["feature"], d["impact"]) for d in drivers]
        labels = [f"{pretty_feature(d['feature'])} ({d['impact']:+.1f} pts)" for d in drivers]
        text, used = llm_inference.generate_player_explanation(
            player_name=p["display_name"],
            role=p["role"],
            predicted_score=p["adjusted_score"],
            shap_top3=top3,
            pitch_type=pitch_category,
            weather_summary=weather_summary,
            is_selected=is_sel,
            driver_labels=labels if drivers else None,
            return_source=True,
        )
        return key, text, used

    # Ollama calls are I/O bound — parallelize across players (4 workers keeps
    # a CPU-only llama3.2:3b responsive). Heuristic fallback is instant anyway.
    if jobs:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(run, j) for j in jobs]
            for fut in as_completed(futures):
                key, text, used = fut.result()
                explanations[key] = text
                used_ollama.append(used)

    # Team-level summary from the selected XI
    expected_total = sum(players[k]["adjusted_score"] for k in selected_keys if k in players)
    team_lines = []
    for key in selected_keys:
        p = players[key]
        team_lines.append(f"{p['display_name']} ({p['role']}, {p['team']}) — {p['adjusted_score']:.0f} pts")
    team_report, summary_used_ollama = llm_inference.generate_team_summary(
        team_lines=team_lines,
        pitch_type=pitch_category,
        weather_summary=weather_summary,
        expected_total=expected_total,
        captain=_captain_of(players, selected_keys),
        return_source=True,
    )

    player_reports = []
    for key, p in players.items():
        player_reports.append({
            "display_name": p["display_name"],
            "role": p["role"],
            "team": p["team"],
            "selected": key in set(selected_keys),
            "adjusted_score": p["adjusted_score"],
            "explanation": explanations.get(key, ""),
            "drivers": [
                {"feature": d["feature"], "label": pretty_feature(d["feature"]), "impact": d["impact"]}
                for d in drivers_by_player.get(key, [])
            ],
        })

    # Selected players first, then bench; each group sorted by projected score
    player_reports.sort(key=lambda r: (not r["selected"], -r["adjusted_score"]))

    covered = sum(bool(drivers_by_player.get(k)) for k in selected_keys)
    return {
        "generated_with": "ollama" if summary_used_ollama and all(used_ollama) else "heuristic",
        "attribution": {"method": "weighted_base_shap" if cached["fmt"] != "t20" else "catboost_shap",
                        "available": covered > 0, "covered_selected": covered,
                        "selected_count": len(selected_keys)},
        "team_report": team_report,
        "players": player_reports,
        "context": {
            "venue": cached.get("venue"),
            "date": cached.get("date"),
            "format": cached.get("fmt"),
            "constraint_mode": cached.get("constraint_mode", "strict"),
            "pitch_category": pitch_category,
            "weather_summary": weather_summary,
            "expected_total_points": round(expected_total, 1),
        },
    }


def _captain_of(players: Dict[str, dict], selected_keys: List[str]) -> str:
    best_key, best_upside = None, -1.0
    for key in selected_keys:
        upside = players.get(key, {}).get("captain_upside", 0.0)
        if upside > best_upside:
            best_key, best_upside = key, upside
    return players.get(best_key, {}).get("display_name", "") if best_key else ""
