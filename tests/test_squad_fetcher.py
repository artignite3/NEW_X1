"""Provider calls should be reserved for fixtures lacking usable squads."""

import unittest
from unittest.mock import patch

from data.future_matches import squad_fetcher
from model import team_generator


class SquadFetcherTests(unittest.TestCase):
    def setUp(self):
        self.matches = [
            {"match_id": 1, "date": "2026-10-12", "team1": "A", "team2": "B"},
            {"match_id": 2, "date": "2026-10-13", "team1": "C", "team2": "D"},
        ]
        self.prior = {"squads": {"1": {"ready": True}}, "fetched_at": "2026-10-10T00:00:00+00:00"}

    def run_fetcher(self, argv):
        with patch("sys.argv", argv), \
             patch.object(squad_fetcher, "load_matches", return_value={"matches": self.matches}), \
             patch.object(squad_fetcher, "load_squads", return_value=self.prior), \
             patch.object(team_generator, "has_usable_match_squads",
                          side_effect=lambda match, entry: bool(entry.get("ready"))), \
             patch.object(squad_fetcher, "refresh_match", return_value={"ready": True}) as refresh, \
             patch.object(squad_fetcher, "publish") as publish:
            squad_fetcher.main()
        return refresh, publish

    def test_default_refresh_skips_ready_fixture(self):
        refresh, publish = self.run_fetcher(["squad_fetcher.py"])
        self.assertEqual([call.args[0]["match_id"] for call in refresh.call_args_list], [2])
        self.assertIn("2", publish.call_args.args[0]["squads"])

    def test_explicit_id_can_refresh_ready_fixture(self):
        refresh, _ = self.run_fetcher(["squad_fetcher.py", "--ids", "1"])
        self.assertEqual([call.args[0]["match_id"] for call in refresh.call_args_list], [1])


if __name__ == "__main__":
    unittest.main()
