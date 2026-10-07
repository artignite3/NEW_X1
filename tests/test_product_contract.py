"""Fixed-data regression checks for the audited product defects."""
import unittest
import os
from copy import deepcopy
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from model.name_resolver import PlayerNameResolver
from model import team_generator as generator
from model.model_fastapi import app
from intelligence.pitch_analyzer import get_venue_profile


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 8, 12, tzinfo=tz)


class ProductContractTests(unittest.TestCase):
    def test_exact_name_must_have_requested_gender_history(self):
        resolver = PlayerNameResolver({"Same Name": {"fixture-female-game": {}}})
        self.assertEqual(resolver.resolve("Same Name", "male"), (None, None))
        self.assertEqual(resolver.resolve("Same Name", "female"), ("Same Name", "exact"))

    def test_pitch_priors_do_not_claim_measured_statistics_or_cross_formats(self):
        t20 = get_venue_profile("Wankhede Stadium", "t20")
        self.assertEqual(t20["source"], "curated_prior")
        self.assertIsNone(t20["avg_1st_innings"])
        for fmt in ("odi", "test"):
            profile = get_venue_profile("Wankhede Stadium", fmt)
            self.assertEqual(profile["source"], "unavailable")
            self.assertIsNone(profile["avg_1st_innings"])
            self.assertEqual(profile["batter_mult"], 1.)

    def generate(self, mode="prediction", relaxed=False):
        roles = ["WK"] + ["BAT"] * 4 + ["AR"] * 2 + ["BOWL"] * 4
        if relaxed:
            roles = ["BAT"] * 11
        pool = [{"display_name": f"Player {i}", "team": "Alpha" if i < 6 else "Beta",
                 "role": role, "injury_status": "UNKNOWN"} for i, role in enumerate(roles)]
        resolver = MagicMock()
        resolver.resolve.side_effect = lambda name, **kwargs: (name, "exact")
        with patch.object(generator, "datetime", FixedClock), \
             patch.object(generator, "pool_from_custom_teams", return_value=deepcopy(pool)), \
             patch.object(generator, "get_fantasy", return_value={}), \
             patch.object(generator, "get_resolver", return_value=resolver), \
             patch.object(generator, "get_league_prior", return_value=(30., 10.)), \
             patch.object(generator, "canonical_venue", side_effect=lambda name: name):
            return generator.generate_best_team({"team1": "Alpha", "team2": "Beta", "format": "t20",
                "date": "2026-10-12" if mode == "prediction" else "2026-10-06", "mode": mode,
                "use_ml": False, "use_intelligence": False, "allow_relaxation": relaxed})

    def test_prediction_and_retrospective_modes_survive_strict_solver(self):
        for mode in ("prediction", "retrospective"):
            result = self.generate(mode)
            self.assertEqual(result["request"]["mode"], mode)
            self.assertEqual(result["summary"]["constraint_mode"], "strict")
            self.assertTrue(result["validation"]["valid"])
            for player in result["best_team"]:
                self.assertIsNone(player["playing_probability"])
                self.assertEqual(player["selection_status"], "unconfirmed")

    def test_relaxation_does_not_overwrite_prediction_mode(self):
        result = self.generate(relaxed=True)
        self.assertEqual(result["request"]["mode"], "prediction")
        self.assertEqual(result["summary"]["constraint_mode"], "relaxed_roles")

    def test_active_api_rejects_invalid_requests_before_generation(self):
        with patch.dict(os.environ, {"APP_ENV": "test", "SUPABASE_URL": "", "SUPABASE_PUBLISHABLE_KEY": ""}), \
             TestClient(app) as client, patch("model.model_fastapi.generate_best_team") as generate:
            for body in ({}, {"team1": "Alpha"}, {"team1": "Alpha", "team2": "alpha"},
                         {"match_id": True}, {"match_id": "x", "date": "2026-02-30"},
                         {"match_id": "x", "format": "T10"}, {"match_id": "x", "risk_aversion": 1.}):
                with self.subTest(body=body):
                    self.assertEqual(client.post("/generate_best_team", json=body).status_code, 422)
            self.assertEqual(client.post("/explain_team", json={"explain_token": "bad"}).status_code, 422)
            generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
