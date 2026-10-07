"""M1 — Ingestion idempotency gate.

Two guarantees:
  1. Running ingestion twice over an UNCHANGED source produces byte-identical
     outputs and manifests (the second run is a no-op).
  2. A corrected archive member updates ONLY that match's player records;
     every other player's history stays byte-identical.
"""

import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import data_processing.cricsheet_ingestor as ingestor


def cricsheet_match(team_a, team_b, date_str, runs_a, runs_b, fmt="T20"):
    """Minimal valid cricsheet-style match dict."""
    def innings(team, runs):
        bowler_team = team_b if team == team_a else team_a
        overs = []
        if runs:
            overs.append({"over": 0, "deliveries": [{
                "over": 0, "ball": 1, "batter": f"{team} Opener",
                "bowler": f"{bowler_team} Pacer",
                "non_striker": f"{team} Partner",
                "runs": {"batter": runs, "extras": 0, "total": runs},
                "wickets": [{"player_out": f"{bowler_team} Opener",
                             "kind": "bowled"}],
            }]})
        return {"team": team, "overs": overs}

    squads = {
        team_a: [f"{team_a} Opener", f"{team_a} Partner", f"{team_a} Pacer"],
        team_b: [f"{team_b} Opener", f"{team_b} Partner", f"{team_b} Pacer"],
    }

    return {
        "info": {
            "dates": [date_str], "gender": "male", "match_type": fmt,
            "teams": [team_a, team_b], "venue": "Test Ground, Testville",
            "players": squads,
            "outcome": {"winner": team_a, "type": "runs"},
        },
        "innings": [innings(team_a, runs_a), innings(team_b, runs_b)],
    }


class IngestionIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "data" / "processed").mkdir(parents=True)
        (self.base / "data" / "raw").mkdir(parents=True)
        self._write_zip(runs_a=120, runs_b=118)
        self._patch = mock.patch.multiple(
            ingestor, BASE_DIR=self.base, ARCHIVES={"t20": "t20s"},
        )
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self.tmp.cleanup()

    def _write_zip(self, runs_a, runs_b):
        archive_path = self.base / "data" / "raw" / "t20s_json.zip"
        matches = [
            ("m1", cricsheet_match("Alpha", "Beta", "2024-06-01", runs_a, runs_b)),
            ("m2", cricsheet_match("Gamma", "Delta", "2024-06-02", 140, 130)),
        ]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, match in matches:
                zf.writestr(f"{name}.json", json.dumps(match))
        archive_path.write_bytes(buf.getvalue())

    def _run(self):
        ingestor.ingest_format("t20")
        out = (self.base / "data" / "processed" / "player_fantasy_points_t20.json").read_bytes()
        man = (self.base / "data" / "processed" / "ingestion_t20.json").read_bytes()
        return out, man

    def test_second_unchanged_run_is_byte_identical(self):
        first_out, first_man = self._run()
        second_out, second_man = self._run()
        self.assertEqual(first_out, second_out, "fantasy output changed on a no-op rerun")
        self.assertEqual(first_man, second_man, "manifest changed on a no-op rerun")

    def test_corrected_match_updates_only_its_players(self):
        first_out, _ = self._run()
        first_state = json.loads(first_out)

        # correction: Alpha scores 30 more runs in match m1
        self._write_zip(runs_a=150, runs_b=118)
        second_out, _ = self._run()
        second_state = json.loads(second_out)

        for player, history in second_state.items():
            for key, record in history.items():
                old = first_state.get(player, {}).get(key)
                if record.get("source_id") == "m1":
                    continue  # affected match may change
                self.assertEqual(record, old,
                                 f"unaffected record changed: {player}/{key}")

        # and the correction actually landed: an m1 record carries the new 150 runs
        m1_runs = [r.get("total_runs") for h in second_state.values()
                   for r in h.values() if r.get("source_id") == "m1"]
        self.assertIn(150.0, m1_runs)
        self.assertNotIn(120.0, m1_runs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
