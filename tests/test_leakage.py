"""M1 — Leakage perturbation gate.

Property under test: editing any match's outcome, venue or opponent must not
alter the feature row (or the model-ready request row) of ANY earlier match.
Features may only depend on information with available_date before the row's
match, and same-day matches must not see each other.

If any assertion here fails, every model trained on the affected features is
contaminated and must be retrained after the fix.
"""

import sys
import unittest
from unittest import mock
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_processing.feature_engineering import RAW_STATS, add_ts_features, add_context_features
from model.predict_model import build_request_features


def corpus(n_matches=12, players=("Alice", "Bob", "Carol", "Dave")):
    """A synthetic history: 4 players across 3 venues/opponents, dated July 2025."""
    venues = ["Ground A, Alpha", "Ground B, Beta", "Ground C, Gamma"]
    opponents = ["Opponent X", "Opponent Y", "Opponent Z"]
    rng = np.random.RandomState(42)
    rows = []
    for i in range(n_matches):
        date = pd.Timestamp("2025-07-01") + pd.Timedelta(days=i)
        venue, opponent = venues[i % 3], opponents[i % 3]
        for p_i, player in enumerate(players):
            score = float(rng.randint(0, 80))
            rows.append({
                "player": player, "match_key": f"M{i:02d}-{player}",
                "match_date": date, "available_date": date,
                "venue": venue, "opponent": opponent,
                "total_points": score,
                **{c: float(rng.randint(0, 20)) for c in RAW_STATS},
            })
    return pd.DataFrame(rows).sort_values(["player", "match_date"]).reset_index(drop=True)


def feature_frame(df):
    return add_context_features(add_ts_features(df.copy()))


class LeakagePerturbationTests(unittest.TestCase):
    def assert_earlier_rows_identical(self, before, after, cutoff_date, msg):
        """Every feature column of every row strictly before cutoff must match."""
        cols = [c for c in before.columns]
        earlier_b = before[before.match_date < pd.Timestamp(cutoff_date)]
        earlier_a = after[after.match_date < pd.Timestamp(cutoff_date)]
        self.assertEqual(len(earlier_b), len(earlier_a), msg)
        try:
            pd.testing.assert_frame_equal(earlier_b[cols], earlier_a[cols])
        except AssertionError as e:
            self.fail(f"{msg}: earlier rows changed -> {e}")

    def test_01_outcome_edit_cannot_touch_earlier_rows(self):
        """Edit the final match's score: all earlier feature rows stay identical."""
        raw = corpus()
        before = feature_frame(raw)
        last_date = raw.match_date.max()
        changed = raw.copy()
        mask = changed.match_date.eq(last_date)
        self.assertTrue(mask.any())
        changed.loc[mask, "total_points"] = 99999.0
        changed.loc[mask, RAW_STATS] = 777.0
        after = feature_frame(changed)
        self.assert_earlier_rows_identical(before, after, last_date,
                                           "score edit on final match leaked backwards")

    def test_02_mid_series_edit_only_shifts_later_rows(self):
        """Edit match #6's outcome: rows from matches #1-#5 identical, #7+ may change."""
        raw = corpus()
        before = feature_frame(raw)
        target = pd.Timestamp("2025-07-06")
        changed = raw.copy()
        changed.loc[changed.match_date.eq(target), "total_points"] = 12345.0
        after = feature_frame(changed)
        self.assert_earlier_rows_identical(before, after, target,
                                           "mid-series edit leaked backwards")

    def test_03_venue_and_opponent_edit_cannot_touch_earlier_rows(self):
        raw = corpus()
        before = feature_frame(raw)
        last_date = raw.match_date.max()
        changed = raw.copy()
        changed.loc[changed.match_date.eq(last_date), "venue"] = "Ground Z, Omega"
        changed.loc[changed.match_date.eq(last_date), "opponent"] = "Opponent W"
        after = feature_frame(changed)
        self.assert_earlier_rows_identical(before, after, last_date,
                                           "venue/opponent edit leaked backwards")

    def test_04_same_day_rows_do_not_see_each_other(self):
        """Two matches on the same date must not feed each other's context."""
        raw = corpus(n_matches=3)
        twin = raw.copy()
        # duplicate the first date's matches with wildly different outcomes
        twin_first = twin[twin.match_date.eq(pd.Timestamp("2025-07-01"))].copy()
        twin_first["match_key"] = twin_first["match_key"] + "-twin"
        twin_first["total_points"] = 500.0
        combined = pd.concat([twin, twin_first], ignore_index=True)
        result = feature_frame(combined)
        same_day = result[result.match_date.eq(pd.Timestamp("2025-07-01"))]
        # venue_avg_pts for same-day rows must not include the twin's 500 points
        self.assertTrue((same_day["venue_avg_pts"] < 100).all(),
                        "same-day matches saw each other's outcomes")

    def test_05_request_features_invariant_to_later_matches(self):
        """Model-ready rows for date D must not change when a later match changes."""
        raw = corpus()
        cols = ["total_points_lag1", "venue_avg_pts"]
        date = "2025-07-08"
        clean = feature_frame(raw)
        changed = raw.copy()
        late = changed.match_date.gt(pd.Timestamp(date))
        self.assertTrue(late.any())
        changed.loc[late, "total_points"] = 99999.0
        tainted = feature_frame(changed)

        with mock.patch("model.predict_model._load_features_dataset", return_value=clean):
            before_rows = build_request_features(["Alice"], "t20", date, cols, "Ground A, Alpha")
        with mock.patch("model.predict_model._load_features_dataset", return_value=tainted):
            after_rows = build_request_features(["Alice"], "t20", date, cols, "Ground A, Alpha")
        self.assertIn("Alice", before_rows)
        pd.testing.assert_frame_equal(before_rows["Alice"], after_rows["Alice"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
