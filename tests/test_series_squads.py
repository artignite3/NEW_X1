"""A series roster can cover later fixtures without crossing teams or formats."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from model import team_generator as generator
from model.model_fastapi import app


def block(team, fmt="T20I"):
    return {"team_name": f"{team} {fmt} Squad",
            "players": [{"player_name": f"{team} Player {i}", "role": "BAT"}
                        for i in range(11)]}


class SeriesSquadTests(unittest.TestCase):
    def setUp(self):
        self.match = {"match_id": 30, "series_id": 42, "match_type": "T20",
                      "team1": "Alpha", "team2": "Beta", "date": "2026-10-14", "venue": "Ground"}
        self.squads = {
            "10": {"series_id": 42, "format": "T20", "available_squads": [block("Alpha"), block("Gamma")]},
            "20": {"series_id": 42, "format": "T20", "available_squads": [block("Delta"), block("Beta")]},
        }

    def test_combines_two_saved_matches_in_same_series(self):
        entry, source, ids = generator.resolve_match_squad_entry(self.match, self.squads)
        self.assertEqual(source, "series_squad")
        self.assertEqual(ids, ["10", "20"])
        self.assertTrue(generator.has_usable_match_squads(self.match, entry))
        with patch.object(generator, "get_squads_json", return_value=self.squads), \
             patch.object(generator, "get_match_info", return_value=self.match):
            pool, meta = generator.pool_from_match_squads(30, "t20")
        self.assertEqual(len(pool), 22)
        self.assertEqual(meta["squad_source"], "series_squad")

    def test_does_not_use_another_series_or_format(self):
        wrong_series = {k: {**v, "series_id": 43} for k, v in self.squads.items()}
        wrong_format = {k: {**v, "format": "ODI", "available_squads": [block("Alpha", "ODI"), block("Beta", "ODI")]}
                        for k, v in self.squads.items()}
        self.assertEqual(generator.resolve_match_squad_entry(self.match, wrong_series)[1], "pending")
        self.assertEqual(generator.resolve_match_squad_entry(self.match, wrong_format)[1], "pending")

    def test_api_exposes_provisional_series_source(self):
        feed = {"matches": [self.match], "source": "test", "fetched_at": "2026-10-11T00:00:00+00:00",
                "fallback_used": False, "warning": None}
        with patch("data.future_matches.fixture_store.load", return_value=feed), \
             patch.object(generator, "get_squads_json", return_value=self.squads):
            response = TestClient(app).get("/matches")
        item = response.json()["matches"][0]
        self.assertTrue(item["has_squad"])
        self.assertEqual(item["squad_source"], "series_squad")
        self.assertEqual(item["squad_source_match_ids"], ["10", "20"])


if __name__ == "__main__":
    unittest.main()
