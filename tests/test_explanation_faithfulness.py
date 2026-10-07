"""Self-contained explanation checks: no fixtures, dates, model artifacts or LLM server."""
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
from intelligence.llm_analyst import generate_team_report
from intelligence.shap_explainer import top_shap_features_ensemble


class ExplanationFaithfulnessTests(unittest.TestCase):
    def setUp(self):
        self.offline = patch("model.llm_inference.ollama_available", return_value=False)
        self.offline.start()
        self.addCleanup(self.offline.stop)
        self.cached = {"fmt": "t20", "date": "fixed-test-date", "venue": "Test Ground",
            "pitch_category": "NEUTRAL", "weather_summary": "Weather unavailable",
            "selected": ["p1", "p2"], "constraint_mode": "strict",
            "players": {
                "p1": {"display_name": "Alpha Player", "role": "BAT", "team": "Alpha",
                       "adjusted_score": 42., "captain_upside": 45.},
                "p2": {"display_name": "Beta Player", "role": "BOWL", "team": "Beta",
                       "adjusted_score": 34.5, "captain_upside": 35.},
                "p3": {"display_name": "Bench Player", "role": "AR", "team": "Alpha",
                       "adjusted_score": 20., "captain_upside": 22.}}}
        self.drivers = {"p1": [{"feature": "total_runs_roll3_mean", "impact": 4.2}],
                        "p2": [{"feature": "wickets_roll3_mean", "impact": 2.5}]}
        self.report = generate_team_report(self.cached, self.drivers)

    def test_driver_chips_are_exactly_the_supplied_attributions(self):
        keys = {p["display_name"]: key for key, p in self.cached["players"].items()}
        for player in self.report["players"]:
            expected = self.drivers.get(keys[player["display_name"]], [])
            actual = [{"feature": d["feature"], "impact": d["impact"]} for d in player["drivers"]]
            self.assertEqual(actual, expected)

    def test_only_pool_players_are_reported(self):
        self.assertEqual({p["display_name"] for p in self.report["players"]},
                         {p["display_name"] for p in self.cached["players"].values()})

    def test_projected_total_excludes_bench(self):
        self.assertEqual(self.report["context"]["expected_total_points"], 76.5)

    def test_selected_player_explanations_quote_real_scores(self):
        for player in self.report["players"]:
            if player["selected"]:
                self.assertIn(f"{player['adjusted_score']:.1f}", player["explanation"])
        self.assertEqual(self.report["generated_with"], "heuristic")

    def test_repeated_explanations_are_deterministic(self):
        self.assertEqual(generate_team_report(self.cached, self.drivers), self.report)

    def test_ensemble_weights_match_exact_expected_values(self):
        class Meta:
            coef_ = np.array([0.5, 0.25, 0.25])
        names = ["catboost", "xgboost", "lightgbm"]
        bundle = {"meta_model": Meta(), "base_model_names": names,
                  "base_models": {n: object() for n in names}}
        vectors = {"catboost": np.array([2., -1.]), "xgboost": np.array([4., 1.]),
                   "lightgbm": np.array([0., 3.])}
        with patch("intelligence.shap_explainer._raw_shap_values",
                   side_effect=lambda model, row, cols, kind: vectors[kind]):
            actual = top_shap_features_ensemble(bundle, pd.DataFrame([[0., 0.]], columns=["a", "b"]), ["a", "b"])
        self.assertEqual(actual, [{"feature": "a", "impact": 2.}, {"feature": "b", "impact": 0.5}])


if __name__ == "__main__":
    unittest.main()
