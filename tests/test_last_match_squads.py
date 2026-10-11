"""Last-match squad estimates must be complete, same-format, and pre-fixture."""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from model import team_generator as generator
from model.model_fastapi import app


def history(team, gender, day, source_id, count=11, available=None):
    return {
        f"{team}-{source_id}-{i}": {
            f"{source_id}-{i}": {
                "team": team,
                "gender": gender,
                "match_date": day,
                "available_date": available or day,
                "source_id": source_id,
            }
        }
        for i in range(count)
    }


class LastMatchSquadTests(unittest.TestCase):
    def setUp(self):
        generator._historical_team_index.cache_clear()

    def tearDown(self):
        generator._historical_team_index.cache_clear()

    def test_uses_latest_complete_match_available_before_fixture(self):
        fantasy = {
            **history("Alpha", "male", "2026-10-01", "old"),
            **history("Alpha", "male", "2026-10-10", "short", count=10),
            **history("Alpha", "male", "2026-10-11", "late", available="2026-10-14"),
            **history("Alpha", "female", "2026-10-12", "wrong-gender"),
            **history("Alpha", "male", "2026-10-13", "same-day"),
        }
        with patch.object(generator, "get_fantasy", return_value=fantasy), \
             patch.object(generator, "_fantasy_history_stamp", return_value=("fixture",)):
            squad = generator.last_completed_team_squad("Alpha", "t20", "2026-10-13")
        self.assertEqual(squad["date"], "2026-10-01")
        self.assertEqual(len(squad["players"]), 11)

    def test_requires_both_complete_teams(self):
        fantasy = {**history("Alpha", "male", "2026-10-01", "a"),
                   **history("Beta", "male", "2026-10-01", "b", count=10)}
        match = {"team1": "Alpha", "team2": "Beta", "date": "2026-10-13"}
        with patch.object(generator, "get_fantasy", return_value=fantasy), \
             patch.object(generator, "_fantasy_history_stamp", return_value=("incomplete",)):
            self.assertIsNone(generator.last_match_squads_for_fixture(match, "t20"))

    def test_fixture_pool_marks_historical_players_unconfirmed(self):
        match = {"match_id": 7, "team1": "Alpha", "team2": "Beta", "date": "2026-10-13",
                 "match_type": "T20", "venue": "Example Ground"}
        historical = {"team1": {"date": "2026-10-01", "players": [f"A{i}" for i in range(11)]},
                      "team2": {"date": "2026-10-02", "players": [f"B{i}" for i in range(11)]}}
        with patch.object(generator, "get_squads_json", return_value={}), \
             patch.object(generator, "get_match_info", return_value=match), \
             patch.object(generator, "last_match_squads_for_fixture", return_value=historical):
            pool, meta = generator.pool_from_match_squads(7, "t20")
        self.assertEqual(len(pool), 22)
        self.assertEqual(meta["squad_source"], "last_match")
        self.assertEqual(meta["squad_match_dates"], {"Alpha": "2026-10-01", "Beta": "2026-10-02"})
        self.assertTrue(all(p["source"] == "last_completed_match" and p["injury_status"] == "UNKNOWN"
                            for p in pool))

    def test_fixture_feed_exposes_provisional_source_and_dates(self):
        match = {"match_id": 7, "team1": "Alpha", "team2": "Beta", "date": "2026-10-13",
                 "match_type": "T20", "venue": "Example Ground"}
        historical = {"team1": {"date": "2026-10-01", "players": [f"A{i}" for i in range(11)]},
                      "team2": {"date": "2026-10-02", "players": [f"B{i}" for i in range(11)]}}
        feed = {"matches": [match], "source": "test", "fetched_at": "2026-10-10T00:00:00+00:00",
                "fallback_used": False, "warning": None}
        with patch("data.future_matches.fixture_store.load", return_value=feed), \
             patch.object(generator, "get_squads_json", return_value={}), \
             patch("model.model_fastapi.last_match_squads_for_fixture", return_value=historical):
            response = TestClient(app).get("/matches")
        self.assertEqual(response.status_code, 200)
        item = response.json()["matches"][0]
        self.assertTrue(item["has_squad"])
        self.assertEqual(item["squad_source"], "last_match")
        self.assertEqual(item["squad_match_dates"], {"Alpha": "2026-10-01", "Beta": "2026-10-02"})


if __name__ == "__main__":
    unittest.main()
