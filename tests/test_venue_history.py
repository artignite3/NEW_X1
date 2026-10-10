"""Venue evidence must be date-safe, transparent, and recoverable."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from intelligence import venue_history as history
from intelligence.build_venue_history import build, match_record
from intelligence.pitch_analyzer import get_venue_profile


def record(match_id, day, venue, fmt="t20", runs=120, balls=120, gender="male"):
    return {"id": match_id, "date": day, "available_date": day, "venue": venue, "format": fmt,
            "gender": gender, "team_type": "international",
            "first": {"runs": runs, "balls": balls, "wickets": 6, "boundaries": 15}, "style": {}, "defended": None}


class VenueHistoryTests(unittest.TestCase):
    def test_checksum_and_last_good_recovery(self):
        snapshot = history.make_snapshot([record("one", "2020-01-01", "One Ground")])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "venue_history.json").write_text("{broken", encoding="utf-8")
            (root / "venue_history.json.last_good").write_text(json.dumps(snapshot), encoding="utf-8")
            with patch.object(history, "data_root", return_value=root), patch.object(history, "PROJECT_ROOT", root):
                result, path = history.load_snapshot()
            self.assertEqual(result["matches"][0]["id"], "one")
            self.assertTrue(path.endswith(".last_good"))
        snapshot["matches"][0]["first"]["runs"] = 999
        with self.assertRaises(ValueError):
            history.validate_snapshot(snapshot)

    def test_cross_format_normalization_and_future_exclusion(self):
        matches = [record(f"base-t20-{i}", f"2020-01-{i+1:02d}", "Other T20", runs=120) for i in range(25)]
        matches += [record(f"base-odi-{i}", f"2020-01-{i+1:02d}", "Other ODI", fmt="odi", runs=200, balls=300) for i in range(25)]
        for i in range(10):
            fmt = "t20" if i % 2 == 0 else "odi"
            matches.append(record(f"venue-{i}", f"2021-02-{i+1:02d}", "Example Ground, Town", fmt,
                                  runs=180 if fmt == "t20" else 300, balls=120 if fmt == "t20" else 300))
        matches.append(record("future", "2022-01-01", "Example Ground, Town", runs=1000))
        in_progress = record("unfinished-test", "2021-02-26", "Example Ground, Town", fmt="test", runs=1000)
        in_progress["available_date"] = "2021-03-03"
        matches.append(in_progress)
        snapshot = history.make_snapshot(matches)
        with patch.object(history, "load_snapshot", return_value=(snapshot, "fixture.json")):
            result = history.report("Example Ground", "t20", "2021-03-01")
            self.assertEqual(result["source"], "historical")
            self.assertEqual(result["category"], "BATTING")
            self.assertEqual(result["sample_size"], 10)
            self.assertEqual(result["last5"]["same_format_matches"], 2)
            self.assertEqual(result["last10"]["avg_1st_innings"], 180)
            self.assertEqual(result["batter_mult"], 1.0)
            self.assertNotIn("future", result["match_ids"])
            self.assertNotIn("unfinished-test", result["match_ids"])
            self.assertIsNone(history.report("Example Ground", "t20", "2021-02-03"))

    def test_city_collision_and_gender_are_not_conflated(self):
        rows = [record("a", "2020-01-01", "National Stadium, City A"),
                record("b", "2020-01-02", "National Stadium, City B"),
                record("c", "2020-01-03", "National Stadium, City A", gender="female")]
        self.assertEqual(history._identity(rows, "National Stadium"), [])
        self.assertEqual([m["id"] for m in history._identity(rows, "National Stadium, City B")], ["b"])
        self.assertEqual(get_venue_profile("Unknown", "odi")["source"], "unavailable")

    def test_delivery_extraction_counts_legal_balls_and_style(self):
        delivery = {"batter": "A", "bowler": "B", "runs": {"batter": 1, "extras": 0, "total": 1}}
        overs = [{"over": n, "deliveries": [delivery.copy() for _ in range(6)]} for n in range(16)]
        data = {"info": {"match_type": "T20", "venue": "Sample Ground", "dates": ["2020-01-01"],
                         "gender": "male", "team_type": "international", "outcome": {}},
                "innings": [{"team": "A", "overs": overs}]}
        parsed = match_record(data, "t20:sample", {("2020-01-01", "sample ground", "B"): "pace"})
        self.assertEqual(parsed["first"]["balls"], 96)
        self.assertEqual(parsed["first"]["runs"], 96)
        self.assertEqual(parsed["style"]["powerplay"]["pace"], [36, 36, 0])

    def test_refresh_without_style_csv_keeps_validated_previous_style(self):
        delivery = {"batter": "A", "bowler": "B", "runs": {"batter": 1, "extras": 0, "total": 1}}
        fixture = {"info": {"match_type": "T20", "venue": "Sample Ground", "dates": ["2020-01-01"],
                            "gender": "male", "team_type": "international", "outcome": {}},
                   "innings": [{"team": "A", "overs": [{"over": n, "deliveries": [delivery] * 6} for n in range(16)]}]}
        with tempfile.TemporaryDirectory() as folder:
            raw = Path(folder) / "raw"
            raw.mkdir()
            for name in ("t20s_json.zip", "odis_json.zip", "tests_json.zip"):
                with zipfile.ZipFile(raw / name, "w") as archive:
                    if name.startswith("t20"):
                        archive.writestr("match.json", json.dumps(fixture))
            previous = record("t20:match", "2020-01-01", "Sample Ground")
            previous["style"] = {"powerplay": {"pace": [36, 36, 0]}}
            output = Path(folder) / "venue_history.json"
            output.write_text(json.dumps(history.make_snapshot([previous])), encoding="utf-8")
            self.assertEqual(build(raw, output)["matches"], 1)
            refreshed = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(refreshed["matches"][0]["style"], previous["style"])


if __name__ == "__main__":
    unittest.main()
