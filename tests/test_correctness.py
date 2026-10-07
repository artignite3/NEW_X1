"""Regression coverage for the failures discovered in the project audit."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data_processing"))
from data_processing.feature_engineering import RAW_STATS, add_ts_features, add_context_features
from data_processing.cricsheet_ingestor import match_records
from model.calculator_test import calculate_fantasy_points_test
from model.team_generator import solve_xi, build_covariance_matrix, player_history, infer_role_from_history
from model.predict_model import build_request_features, validate_model_metadata
from intelligence.weather_fetcher import weather_multiplier, fetch_venue_weather
from intelligence.pitch_analyzer import pitch_multiplier


def raw_rows():
    rows = []
    for player in ("Alice", "Bob"):
        for i, score in enumerate((10, 20, 30)):
            rows.append({"player": player, "match_key": f"{player}-{i}",
                         "match_date": pd.Timestamp(f"2025-07-0{i+1}"),
                         "available_date": pd.Timestamp(f"2025-07-0{i+1}"),
                         "venue": "Ground", "opponent": "Opponent", "total_points": score,
                         **{c: float(score) for c in RAW_STATS}})
    return pd.DataFrame(rows).sort_values(["player", "match_date"]).reset_index(drop=True)


class CorrectnessTests(unittest.TestCase):
    def test_null_test_innings(self):
        for key in ("Innings 3 Runs", "Innings 4 Wickets", "Total Runs Scored", "Bowled"):
            self.assertEqual(calculate_fantasy_points_test({key: None})["total_points"], 4)
        self.assertEqual(calculate_fantasy_points_test({"Innings 3 Runs": float("nan")})["total_points"], 4)

    def test_shifted_features_and_context_do_not_see_future_or_same_day(self):
        raw = raw_rows()
        before = add_context_features(add_ts_features(raw))
        changed = raw.copy()
        changed.loc[changed.match_date.eq(pd.Timestamp("2025-07-03")), "total_points"] = 99999
        after = add_context_features(add_ts_features(changed))
        cols = [c for c in before if c.startswith("total_points_") or c.endswith("avg_pts")]
        pd.testing.assert_frame_equal(before[cols], after[cols])
        self.assertEqual(before.loc[before.match_date.eq(pd.Timestamp("2025-07-02")), "venue_avg_pts"].tolist(), [10, 10])
        self.assertFalse(any(c.startswith("career_") for c in before))

    def test_unfinished_test_does_not_enter_venue_context(self):
        raw = raw_rows()
        raw.loc[raw.match_date.eq(pd.Timestamp("2025-07-01")), "available_date"] = pd.Timestamp("2025-07-05")
        result = add_context_features(add_ts_features(raw))
        self.assertEqual(result.loc[result.match_date.eq(pd.Timestamp("2025-07-03")), "venue_avg_pts"].tolist(), [20, 20])

    def test_prediction_includes_latest_completed_match(self):
        dataset = add_context_features(add_ts_features(raw_rows()))
        with patch("model.predict_model._load_features_dataset", return_value=dataset):
            rows = build_request_features(["Alice"], "t20", "2025-07-04", ["total_points_lag1", "venue_avg_pts"], "Ground")
            self.assertEqual(rows["Alice"].iloc[0].total_points_lag1, 30)
            self.assertEqual(rows["Alice"].iloc[0].venue_avg_pts, 20)

    def test_history_excludes_match_until_completed(self):
        data = {"P": {"2025-07-01-Test": {"total_points": 50, "available_date": "2025-07-05"}}}
        self.assertEqual(player_history(data, "P", "2025-07-04"), [])
        self.assertEqual(len(player_history(data, "P", "2025-07-06")), 1)

    def test_obsolete_models_are_refused(self):
        with self.assertRaises(FileNotFoundError):
            validate_model_metadata({"cutoff": "2025-06-30", "feature_cols": ["career_Mean_Score"]})

    def test_wicketkeeper_and_team_constraints(self):
        roles = ["WK"] + ["BAT"] * 4 + ["BOWL"] * 5 + ["AR"] * 2
        frame = pd.DataFrame({"player": [str(i) for i in range(12)], "role": roles,
                              "team": ["A"] * 6 + ["B"] * 6, "mean_points": [10] * 12, "variance": [1] * 12})
        cov = pd.DataFrame(np.eye(12))
        selected, status = solve_xi(frame, cov)
        self.assertEqual(status, "Optimal")
        self.assertEqual(len(selected), 11)
        self.assertIn("0", selected)
        frame["role"] = frame.role.replace("WK", "BAT")
        self.assertEqual(solve_xi(frame, cov), ([], "Infeasible"))
        self.assertEqual(infer_role_from_history([{"stumped_outs_made": 1}]), "WK")

    def test_covariance_aligns_matches_and_is_psd(self):
        covariance = build_covariance_matrix({"A": {"m1": 1, "m2": 3}, "B": {"m3": 1, "m4": 3}}, ["A", "B"], {"A": 1, "B": 1})
        self.assertEqual(covariance.loc["A", "B"], 0)
        self.assertGreaterEqual(np.linalg.eigvalsh(covariance).min(), -1e-9)

    def test_weather_and_pitch_respect_bowling_style(self):
        weather = {"available": True, "seam_swing_advantage": True}
        self.assertGreater(weather_multiplier("BOWL", "Right arm fast", weather), 1)
        self.assertEqual(weather_multiplier("BOWL", "Legbreak", weather), 1)
        profile = {"pacer_mult": .9, "spinner_mult": 1.2}
        self.assertEqual(pitch_multiplier("BOWL", "Legbreak", profile), 1.2)
        self.assertEqual(pitch_multiplier("BOWL", "", profile), 1)
        with patch("intelligence.weather_fetcher.get_venue_coords", return_value=None):
            self.assertFalse(fetch_venue_weather("Unknown")["available"])

    def test_ingestion_counts_all_innings_and_fielders(self):
        delivery = {"batter": "A", "non_striker": "B", "bowler": "C", "runs": {"batter": 4, "total": 4}}
        wicket = {"batter": "B", "non_striker": "A", "bowler": "C", "runs": {"batter": 0, "total": 0},
                  "wickets": [{"kind": "stumped", "player_out": "B", "fielders": [{"name": "D"}]}]}
        match = {"info": {"dates": ["2025-07-01", "2025-07-04"], "teams": ["One", "Two"],
                          "players": {"One": ["A", "B"], "Two": ["C", "D"]}, "match_type": "Test", "gender": "male"},
                 "innings": [{"team": "One", "overs": [{"deliveries": [delivery, wicket]}]},
                             {"team": "One", "overs": [{"deliveries": [delivery]}]}]}
        key, records = match_records(match, "123", "test")
        self.assertEqual(records["A"]["total_runs"], 8)
        self.assertEqual(records["C"]["wickets"], 1)
        self.assertEqual(records["D"]["stumped_outs_made"], 1)
        self.assertEqual(records["A"]["available_date"], "2025-07-04")

    def test_incremental_matches_full_rebuild_with_backfill(self):
        import incremental_feature_append as incremental
        raw = raw_rows()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with patch.object(incremental, "DATA_PROCESSED", directory), patch.object(incremental, "flatten_json", return_value=raw):
                incremental.incremental_update("t20", Path("unused"))
            update = raw.copy()
            update.loc[update.match_key.eq("Alice-1"), "total_points"] = 90
            with patch.object(incremental, "DATA_PROCESSED", directory), patch.object(incremental, "flatten_json", return_value=update):
                incremental.incremental_update("t20", Path("unused"))
            actual = pd.read_parquet(directory / "features_t20.parquet")
            expected = add_context_features(add_ts_features(update))
            pd.testing.assert_frame_equal(actual, expected, check_dtype=False)


if __name__ == "__main__":
    unittest.main()
