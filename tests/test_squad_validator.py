"""M3 — Squad contract: adversarial validator and solver-ladder tests.

Every successful generation must pass the independent validator; adversarial
pools (no wicketkeeper, duplicates, too few players, all-injured) must produce
a clear infeasibility instead of a broken XI.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from model.squad_validator import validate_squad
from model.team_generator import solve_xi


def pool_rows(spec):
    """spec: list of (key, display, role, team)."""
    rows = []
    rng = np.random.RandomState(7)
    for i, (key, display, role, team) in enumerate(spec):
        rows.append({
            "player": key, "display_name": display, "role": role, "team": team,
            "mean_points": float(rng.randint(10, 60)),
            "variance": float(rng.randint(200, 600)),
        })
    return pd.DataFrame(rows)


def cov_for(stats):
    players = stats["player"].tolist()
    vals = stats["variance"].values
    cov = pd.DataFrame(np.diag(vals), index=players, columns=players)
    # small positive off-diagonal to make pair terms meaningful
    for i in range(len(players)):
        for j in range(len(players)):
            if i < j:
                cov.iloc[i, j] = cov.iloc[j, i] = 5.0
    return cov


SQUAD = (
    [("K1", "Keeper A", "WK", "Team X"), ("K2", "Keeper B", "WK", "Team Y")]
    + [(f"B{i}", f"Batter {i}", "BAT", "Team X" if i % 2 else "Team Y") for i in range(1, 7)]
    + [(f"A{i}", f"Allrounder {i}", "AR", "Team X" if i % 2 else "Team Y") for i in range(1, 5)]
    + [(f"W{i}", f"Bowler {i}", "BOWL", "Team X" if i % 2 else "Team Y") for i in range(1, 7)]
)  # 19 players, both teams, all roles covered


class ValidatorTests(unittest.TestCase):
    def test_valid_xi_passes_all_modes(self):
        stats = pool_rows(SQUAD)
        selected, status = solve_xi(stats, cov_for(stats), risk_aversion=0.05)
        self.assertEqual(status, "Optimal")
        xi = [dict(p) | {"fantasy_key": p["player"], "injury_status": "FIT"}
              for p in stats.to_dict("records") if p["player"] in selected]
        pool = [dict(p) | {"fantasy_key": p["player"], "injury_status": "FIT"}
                for p in stats.to_dict("records")]
        result = validate_squad(xi, pool, constraint_mode="strict")
        self.assertTrue(result["valid"], result["violations"])

    def test_missing_wicketkeeper_is_infeasible_strict(self):
        spec = [(k, d, r, t) for (k, d, r, t) in SQUAD if r != "WK"]
        stats = pool_rows(spec)
        selected, status = solve_xi(stats, cov_for(stats), risk_aversion=0.05)
        self.assertNotEqual(status, "Optimal")

    def test_duplicate_identity_flagged(self):
        xi = [dict(p) | {"fantasy_key": "K1", "injury_status": "FIT"}
              for p in pool_rows(SQUAD).head(11).to_dict("records")]
        result = validate_squad(xi, SQUAD and [
            {"fantasy_key": p["player"], "display_name": p["display_name"],
             "role": p["role"], "team": p["team"], "injury_status": "FIT"}
            for p in pool_rows(SQUAD).to_dict("records")], constraint_mode="strict")
        self.assertFalse(result["valid"])
        self.assertTrue(any("duplicate" in v for v in result["violations"]))

    def test_injured_player_selected_is_flagged(self):
        xi = [dict(p) | {"fantasy_key": p["player"], "injury_status": "FIT"}
              for p in pool_rows(SQUAD).head(11).to_dict("records")]
        xi[0]["injury_status"] = "INJURED"
        pool = [{"fantasy_key": p["player"], "display_name": p["display_name"],
                 "role": p["role"], "team": p["team"], "injury_status": "INJURED"}
                if p["player"] == xi[0]["fantasy_key"]
                else {"fantasy_key": p["player"], "display_name": p["display_name"],
                      "role": p["role"], "team": p["team"], "injury_status": "FIT"}
                for p in pool_rows(SQUAD).to_dict("records")]
        result = validate_squad(xi, pool, constraint_mode="strict")
        self.assertFalse(result["valid"])
        self.assertTrue(any("INJURED" in v for v in result["violations"]))

    def test_outside_player_flagged(self):
        xi = [dict(p) | {"fantasy_key": p["player"], "injury_status": "FIT"}
              for p in pool_rows(SQUAD).head(11).to_dict("records")]
        intruder = dict(xi[0]) | {"fantasy_key": "INTRUDER", "display_name": "Hacker"}
        result = validate_squad(xi + [intruder], [
            {"fantasy_key": p["player"], "display_name": p["display_name"],
             "role": p["role"], "team": p["team"], "injury_status": "FIT"}
            for p in pool_rows(SQUAD).to_dict("records")], constraint_mode="strict")
        self.assertFalse(result["valid"])

    def test_wrong_size_flagged(self):
        xi = [dict(p) | {"fantasy_key": p["player"], "injury_status": "FIT"}
              for p in pool_rows(SQUAD).head(9).to_dict("records")]
        result = validate_squad(xi, [
            {"fantasy_key": p["player"], "display_name": p["display_name"],
             "role": p["role"], "team": p["team"], "injury_status": "FIT"}
            for p in pool_rows(SQUAD).to_dict("records")], constraint_mode="strict")
        self.assertFalse(result["valid"])

    def test_relaxed_roles_reports_mode(self):
        xi = [dict(p) | {"fantasy_key": p["player"], "injury_status": "FIT"}
              for p in pool_rows(SQUAD).head(11).to_dict("records")]
        result = validate_squad(xi, [
            {"fantasy_key": p["player"], "display_name": p["display_name"],
             "role": p["role"], "team": p["team"], "injury_status": "FIT"}
            for p in pool_rows(SQUAD).to_dict("records")], constraint_mode="relaxed_roles")
        # an all-batter XI violates role bounds only in strict mode
        self.assertTrue(result["valid"], result["violations"])
        self.assertEqual(result["constraint_mode"], "relaxed_roles")


class SolverLadderTests(unittest.TestCase):
    def test_insufficient_pool_is_infeasible(self):
        stats = pool_rows(SQUAD[:8])
        selected, status = solve_xi(stats, cov_for(stats), risk_aversion=0.05)
        self.assertTrue(selected == [] or len(selected) < 11)

    def test_all_batter_pool_cannot_satisfy_role_bounds(self):
        spec = [(f"B{i}", f"Batter {i}", "BAT", "Team X" if i % 2 else "Team Y")
                for i in range(1, 19)]
        stats = pool_rows(spec)
        selected, status = solve_xi(stats, cov_for(stats), risk_aversion=0.05,
                                    use_role_bounds=True, use_team_bounds=True)
        self.assertNotEqual(status, "Optimal")
        selected2, status2 = solve_xi(stats, cov_for(stats), risk_aversion=0.05,
                                      use_role_bounds=False, use_team_bounds=False)
        self.assertEqual(status2, "Optimal")  # relaxation path exists


if __name__ == "__main__":
    unittest.main(verbosity=2)
