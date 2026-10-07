"""Fixed-data failure cases for feed recovery and ensemble explanations."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from data.future_matches.fixture_store import load, publish, validate_feed
from data.future_matches import squad_store
from data_processing.safe_publish import last_good, promote
from intelligence.shap_explainer import top_shap_features_ensemble


def fixture(day="2026-10-12", match_id="fixed-1"):
    return {"match_id": match_id, "team1": "Alpha", "team2": "Beta", "date": day,
            "match_type": "T20", "venue": "Test Ground"}


def feed(matches):
    return {"source": "fixed-test-feed", "fetched_at": "2026-10-07T12:00:00+05:30", "matches": matches}


class FeedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.primary = Path(self.temp.name) / "matches.json"
        self.backup = Path(self.temp.name) / "matches.last_good.json"
        self.addCleanup(self.temp.cleanup)

    def test_corrupt_primary_uses_last_verified_snapshot(self):
        publish(feed([fixture()]), self.primary, self.backup)
        publish(feed([fixture("2026-10-13", "fixed-2")]), self.primary, self.backup)
        self.primary.write_text("{corrupt", encoding="utf-8")
        result = load(self.primary, self.backup, today=__import__("datetime").date(2026, 10, 7))
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["source"], "fixed-test-feed")
        self.assertEqual(result["matches"][0]["match_id"], "fixed-1")
        self.assertIsNotNone(result["warning"])

    def test_bad_update_cannot_replace_healthy_feed(self):
        original = feed([fixture()])
        publish(original, self.primary, self.backup)
        before = self.primary.read_bytes()
        with self.assertRaises(ValueError):
            publish(feed([{"match_id": "bad"}]), self.primary, self.backup)
        self.assertEqual(before, self.primary.read_bytes())

    def test_empty_refresh_cannot_erase_future_fixture(self):
        publish(feed([fixture()]), self.primary, self.backup)
        before = self.primary.read_bytes()
        with patch("data.future_matches.fixture_store.date") as mocked_date:
            mocked_date.today.return_value = __import__("datetime").date(2026, 10, 7)
            mocked_date.fromisoformat.side_effect = __import__("datetime").date.fromisoformat
            with self.assertRaises(ValueError):
                publish(feed([]), self.primary, self.backup)
        self.assertEqual(self.primary.read_bytes(), before)

    def test_expired_backup_never_masquerades_as_future_data(self):
        publish(feed([fixture("2026-10-08")]), self.primary, self.backup)
        publish(feed([fixture("2026-10-09", "new")]), self.primary, self.backup)
        self.primary.unlink()
        result = load(self.primary, self.backup, today=__import__("datetime").date(2026, 10, 10))
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["matches"], [])

    def test_both_missing_is_explicit(self):
        result = load(self.primary, self.backup, today=__import__("datetime").date(2026, 10, 7))
        self.assertEqual(result["matches"], [])
        self.assertIn("No valid fixture feed", result["warning"])

    def test_duplicate_or_bad_format_fails(self):
        for matches in ([fixture(), fixture()], [{**fixture(), "match_type": "T10"}]):
            with self.assertRaises(ValueError):
                validate_feed(feed(matches))

    def test_squad_snapshot_recovers_but_empty_update_cannot_erase_it(self):
        primary = Path(self.temp.name) / "squads.json"
        backup = Path(self.temp.name) / "squads.last_good.json"
        first = {"fetched_at": "2026-10-07T12:00:00", "squads": {"fixed-1": {"available_squads": []}}}
        squad_store.publish(first, primary, backup)
        with self.assertRaises(ValueError):
            squad_store.publish({**first, "squads": {}}, primary, backup)
        squad_store.publish({**first, "squads": {"fixed-2": {}}}, primary, backup)
        primary.write_text("{broken", encoding="utf-8")
        result = squad_store.load(primary, backup)
        self.assertEqual(list(result["squads"]), ["fixed-1"])
        self.assertTrue(result["fallback_used"])

    def test_safe_promotion_keeps_last_verified_data(self):
        destination = Path(self.temp.name) / "history.json"
        destination.write_text('{"Alice": {}}', encoding="utf-8")
        prepared = Path(self.temp.name) / "new.tmp"
        prepared.write_text('{"Bob": {}}', encoding="utf-8")
        def valid(path):
            if not json.loads(path.read_text(encoding="utf-8")):
                raise ValueError("empty")
        promote(prepared, destination, validate=valid)
        self.assertEqual(json.loads(last_good(destination).read_text())["Alice"], {})
        destination.write_text("{broken", encoding="utf-8")
        prepared.write_text('{"Cara": {}}', encoding="utf-8")
        promote(prepared, destination, validate=valid)
        self.assertIn("Alice", json.loads(last_good(destination).read_text()))

    def test_fantasy_history_uses_only_valid_backup(self):
        from model import team_generator
        primary = Path(self.temp.name) / "player_fantasy_points_t20.json"
        backup = last_good(primary)
        primary.write_text("{broken", encoding="utf-8")
        backup.write_text('{"Fixed Player": {"match-1": {}}}', encoding="utf-8")
        with patch.object(team_generator, "DATA_PROCESSED", Path(self.temp.name)):
            team_generator._DATA_STAMPS.pop("t20", None)
            self.assertIn("Fixed Player", team_generator.get_fantasy("t20"))
            self.assertEqual(team_generator._FANTASY_SOURCES["t20"], "last_good")
            backup.unlink()
            with self.assertRaises(FileNotFoundError):
                team_generator.get_fantasy("t20")
        team_generator._DATA_STAMPS.pop("t20", None)

    def test_model_bundle_uses_compatible_backup_only(self):
        import joblib
        from model import predict_model
        from model.data_contract import FEATURE_SCHEMA_VERSION, TRAIN_CUTOFF
        primary = Path(self.temp.name) / "tribe_odi.pkl"
        primary.write_bytes(b"broken")
        backup = last_good(primary)
        joblib.dump({"feature_schema_version": FEATURE_SCHEMA_VERSION, "cutoff": TRAIN_CUTOFF,
                     "feature_cols": ["fixed_feature"]}, backup)
        with patch.object(predict_model, "MODEL_ARTIFACTS", Path(self.temp.name)):
            predict_model._MODEL_CACHE.pop("odi", None)
            self.assertEqual(predict_model.get_model("odi")[2], ["fixed_feature"])
            self.assertEqual(predict_model._MODEL_SOURCES["odi"], "last_good")
            joblib.dump({"feature_schema_version": 1, "cutoff": TRAIN_CUTOFF,
                         "feature_cols": ["career_leak"]}, backup)
            with self.assertRaises(FileNotFoundError):
                predict_model.get_model("odi")
        predict_model._MODEL_CACHE.pop("odi", None)
        predict_model._MODEL_STAMPS.pop("odi", None)

    def test_feature_table_falls_back_to_schema_v2_snapshot(self):
        from model import predict_model
        from model.data_contract import FEATURE_SCHEMA_VERSION
        primary = Path(self.temp.name) / "features_test.parquet"
        primary.write_bytes(b"broken parquet")
        pd.DataFrame({"feature_schema_version": [FEATURE_SCHEMA_VERSION],
                      "match_date": [pd.Timestamp("2026-01-01")],
                      "available_date": [pd.Timestamp("2026-01-02")],
                      "player": ["Fixed Player"]}).to_parquet(last_good(primary))
        with patch.object(predict_model, "DATA_PROCESSED", Path(self.temp.name)):
            predict_model._DF_CACHE.pop("test", None)
            df = predict_model._load_features_dataset("test")
            self.assertEqual(df.iloc[0]["player"], "Fixed Player")
            self.assertEqual(predict_model._DF_SOURCES["test"], "last_good")
        predict_model._DF_CACHE.pop("test", None)
        predict_model._DF_STAMPS.pop("test", None)

    def test_switching_formats_evicts_large_data_caches(self):
        from model import predict_model, team_generator
        from model.data_contract import FEATURE_SCHEMA_VERSION
        folder = Path(self.temp.name)
        for fmt in ("t20", "odi"):
            (folder / f"player_fantasy_points_{fmt}.json").write_text(
                json.dumps({f"fixed-{fmt}": {"match-1": {}}}), encoding="utf-8")
            pd.DataFrame({"feature_schema_version": [FEATURE_SCHEMA_VERSION],
                          "match_date": [pd.Timestamp("2026-01-01")],
                          "available_date": [pd.Timestamp("2026-01-02")],
                          "player": [f"fixed-{fmt}"]}).to_parquet(folder / f"features_{fmt}.parquet")
        with patch.object(team_generator, "DATA_PROCESSED", folder), patch.object(predict_model, "DATA_PROCESSED", folder):
            for fmt in ("t20", "odi"):
                team_generator.get_fantasy(fmt)
                predict_model._load_features_dataset(fmt)
            self.assertEqual(list(team_generator._FANTASY_CACHE), ["odi"])
            self.assertEqual(list(predict_model._DF_CACHE), ["odi"])
        for fmt in ("t20", "odi"):
            team_generator._FANTASY_CACHE.pop(fmt, None)
            team_generator._DATA_STAMPS.pop(fmt, None)
            predict_model._DF_CACHE.pop(fmt, None)
            predict_model._DF_STAMPS.pop(fmt, None)


class EnsembleAttributionTests(unittest.TestCase):
    def test_all_model_weights_and_unrounded_values_are_used(self):
        class Meta:
            coef_ = np.array([0.5, 0.25, 0.25])
        bundle = {"meta_model": Meta(), "base_model_names": ["catboost", "xgboost", "lightgbm"],
                  "base_models": {n: object() for n in ("catboost", "xgboost", "lightgbm")}}
        vectors = {"catboost": np.array([2., 0.04, 0.]),
                   "xgboost": np.array([0., 1., -2.]),
                   "lightgbm": np.array([0., 0.08, 4.])}
        with patch("intelligence.shap_explainer._raw_shap_values", side_effect=lambda model, row, cols, kind: vectors[kind]):
            drivers = top_shap_features_ensemble(bundle, pd.DataFrame([[0, 0, 0]], columns=["a", "b", "c"]), ["a", "b", "c"])
        self.assertEqual(drivers, [{"feature": "a", "impact": 1.0}, {"feature": "c", "impact": 0.5}, {"feature": "b", "impact": 0.29}])

    def test_partial_attribution_is_not_reported_as_ensemble(self):
        class Meta:
            coef_ = np.array([0.5, 0.5])
        bundle = {"meta_model": Meta(), "base_model_names": ["catboost", "xgboost"],
                  "base_models": {"catboost": object(), "xgboost": object()}}
        def values(model, row, cols, kind):
            if kind == "xgboost":
                raise RuntimeError("explainer unavailable")
            return np.array([3.])
        with patch("intelligence.shap_explainer._raw_shap_values", side_effect=values):
            self.assertEqual(top_shap_features_ensemble(bundle, pd.DataFrame([[0]], columns=["a"]), ["a"]), [])

    def test_ollama_failure_reports_heuristic_fallback(self):
        from intelligence.llm_analyst import generate_team_report
        cached = {"fmt": "t20", "players": {"fixed": {"display_name": "Fixed Player", "role": "BAT",
                  "team": "Alpha", "adjusted_score": 42., "captain_upside": 45.}},
                  "selected": ["fixed"], "venue": "Fixed Ground", "date": "2026-10-12"}
        client = MagicMock()
        client.chat.side_effect = RuntimeError("model failed")
        with patch("model.llm_inference.ollama_available", return_value=True), patch("model.llm_inference._client", client):
            report = generate_team_report(cached, {"fixed": []})
        self.assertEqual(report["generated_with"], "heuristic")
        self.assertFalse(report["attribution"]["available"])


class OptimizerBoundednessTests(unittest.TestCase):
    def test_series_squads_for_other_teams_do_not_mark_fixture_available(self):
        from model.team_generator import has_usable_match_squads
        match = fixture()
        eleven = [{"player_name": f"Player {i}"} for i in range(11)]
        wrong = {"available_squads": [{"team_name": "Gamma Squad", "players": eleven},
                                      {"team_name": "Beta Squad", "players": eleven}]}
        self.assertFalse(has_usable_match_squads(match, wrong))
        correct = {"available_squads": [{"team_name": "Alpha Squad", "players": eleven[:6]},
                                        {"team_name": "Beta Squad", "players": eleven[6:]}]}
        self.assertTrue(has_usable_match_squads(match, correct))

    def test_dense_fixed_pool_still_solves_strictly(self):
        from model.team_generator import solve_xi
        roles = ["WK"] * 5 + ["BAT"] * 20 + ["AR"] * 8 + ["BOWL"] * 20
        names = [f"fixed-player-{i}" for i in range(len(roles))]
        stats = pd.DataFrame({"player": names, "mean_points": [60 - i / 4 for i in range(len(roles))],
                              "variance": [10.] * len(roles), "role": roles,
                              "team": ["Alpha" if i % 2 else "Beta" for i in range(len(roles))]})
        covariance = pd.DataFrame(np.full((len(roles), len(roles)), 0.5), index=names, columns=names)
        np.fill_diagonal(covariance.values, 10.)
        selected, status = solve_xi(stats, covariance)
        self.assertEqual(status, "Optimal")
        self.assertEqual(len(selected), 11)
        self.assertEqual(len(set(selected)), 11)


if __name__ == "__main__":
    unittest.main()
