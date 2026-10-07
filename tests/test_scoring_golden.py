"""M1 — Golden scoring tests: hand-verified fantasy-points examples.

Every expected value below was computed BY HAND from the scoring contract
(SCORING_SPEC_VERSION = 1) and then checked against the implementation.
If an expectation disagrees with the code, the spec or the code is wrong —
investigate; never update the expectation to make the test pass.

SCORING SPEC v1 (as implemented in model/calculator_{t20,odi,test}.py):

T20 (+4 participation)
  Batting:  +1/run, +1/four, +2/six; 30 runs +4, 50 +8, 100 +16;
            duck -2 (batted: balls>0 and dismissed-in-inning flags set);
            SR bonus at >=10 balls: >170 +6, (150,170] +4, [130,150] +2 — note SR exactly 150 takes the LOWER bracket (strict upper-tier boundary),
            60-70 -2, 50-60 -4, <50 -6 (gap 70-130 neutral)
  Bowling:  +25/wicket, +8/bowled-or-lbw; 3 wkts +4, 4 +8, >=5 +16;
            +12/maiden; economy at >=2 overs: <5 +6, 5-5.99 +4, 6-7 +2,
            10-11 -2, 11-12 -4, >12 -6 (gap 7-10 neutral)
  Fielding: +8/catch, +12/stumping, +8/run-out; 3+ catches +4

ODI (+4 participation)
  Batting:  +1/run, +1/four, +2/six; 50 +4, 100 +8; duck -3;
            SR bonus at >=20 balls: >140 +6, 120-140 +4, 100-120 +2,
            40-50 -2, 30-40 -4, <30 -6 (gap 50-100 neutral)
  Bowling:  +25/wicket, +8/bowled-or-lbw; 4 wkts +4, >=5 +8;
            +4/maiden; economy at >=5 overs: <2.5 +6, 2.5-3.5 +4,
            3.5-4.5 +2, 7-8 -2, 8-9 -4, >9 -6 (gap 4.5-7 neutral)

Test (+4 participation)
  Batting:  +1/run, +1/four, +2/six; PER-INNINGS 50 +4, 100 +8 (4 innings);
            PER-INNINGS duck -4 (needs per-innings balls faced and
            dismissal/not-out/not-played flags)
  Bowling:  +16/wicket, +8/bowled-or-lbw; PER-INNINGS 4 wkts +4, >=5 +8;
            no economy bonus
  Fielding: +8/catch, +12/stumping, +8/run-out (no multi-catch bonus)
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.calculator_t20 import calculate_fantasy_points_t20
from model.calculate_odi import calculate_fantasy_points_odi
from model.calculator_test import calculate_fantasy_points_test

SCORING_SPEC_VERSION = 1


def t20_batter(runs, balls, fours=0, sixes=0, caught_inning=None, not_out_innings=()):
    stats = {
        "Total Runs Scored": runs, "Balls Faced": balls,
        "Fours": fours, "Sixes": sixes,
        "Avg Batting S/R Per Inning": (runs / balls * 100) if balls else 0.0,
    }
    for inning in (1, 2):
        stats[f"How Out Inning {inning} (Not Played)"] = 0
        stats[f"How Out Inning {inning} (not out)"] = 0
        stats[f"How Out Inning {inning} (caught)"] = 0
    if caught_inning:
        stats[f"How Out Inning {caught_inning} (caught)"] = 1
    for inning in not_out_innings:
        stats[f"How Out Inning {inning} (not out)"] = 1
    return stats


def bowler(wickets, overs, runs_conceded, maidens=0, bowled=0, lbw=0):
    return {
        "Wickets": wickets, "Overs Bowled": overs, "Maiden Overs": maidens,
        "Avg Economy Rate per inning": (runs_conceded / overs) if overs else 0.0,
        "Bowled": bowled, "LBW": lbw,
    }


class TestT20Scoring(unittest.TestCase):
    def test_01_pure_batter_mid_innings(self):
        # 45 runs + 4 fours(4) + 2 sixes(4) + 30-run bonus(4) + SR 160.7 -> +4 + 4
        result = calculate_fantasy_points_t20(t20_batter(45, 28, 4, 2, caught_inning=2))
        self.assertEqual(result["batting_points"], 61)
        self.assertEqual(result["total_points"], 65)

    def test_02_five_wicket_haul(self):
        # 5w(125) + 3 bowled/lbw(24) + haul(16) + maiden(12) + econ 6.0(2) + 4
        result = calculate_fantasy_points_t20(bowler(5, 4, 24, maidens=1, bowled=2, lbw=1))
        self.assertEqual(result["bowling_points"], 179)
        self.assertEqual(result["total_points"], 183)

    def test_03_wicketkeeper(self):
        # 2 catches(16) + 1 stumping(12) + 4
        result = calculate_fantasy_points_t20({
            "Catches Taken": 2, "Stumped Outs Made": 1, "Run Outs Made": 0,
        })
        self.assertEqual(result["fielding_points"], 28)
        self.assertEqual(result["total_points"], 32)

    def test_04_golden_duck(self):
        # batted 2 balls, caught: duck(-2) + 4
        result = calculate_fantasy_points_t20(t20_batter(0, 2, caught_inning=2))
        self.assertEqual(result["batting_points"], -2)
        self.assertEqual(result["total_points"], 2)

    def test_05_did_not_bat_or_bowl(self):
        # Not Played in both innings: no duck penalty, participation only
        stats = t20_batter(0, 0)
        stats["How Out Inning 1 (Not Played)"] = 1
        stats["How Out Inning 2 (Not Played)"] = 1
        result = calculate_fantasy_points_t20(stats)
        self.assertEqual(result["total_points"], 4)

    def test_06_economy_neutral_gap(self):
        # 1 wicket(25) + econ 9.5 sits in the 7-10 neutral gap(0) + 4
        result = calculate_fantasy_points_t20(bowler(1, 4, 38))
        self.assertEqual(result["bowling_points"], 25)
        self.assertEqual(result["total_points"], 29)

    def test_07_half_century_sr_tier(self):
        # 60 runs + 50 bonus(8) + SR 166.7 -> +4 + 4  (zero boundaries)
        result = calculate_fantasy_points_t20(t20_batter(60, 36, caught_inning=1))
        self.assertEqual(result["total_points"], 76)


class TestODIScoring(unittest.TestCase):
    def test_08_century(self):
        # 102 runs + 8 fours(8) + 3 sixes(6) + century(8) + SR 92.7 gap(0) + 4
        result = calculate_fantasy_points_odi(t20_batter(102, 110, 8, 3))
        self.assertEqual(result["batting_points"], 124)
        self.assertEqual(result["total_points"], 128)

    def test_09_four_wicket_haul(self):
        # 4w(100) + 1 lbw(8) + haul(4) + maiden(4) + econ 4.5(2) + 4
        result = calculate_fantasy_points_odi(bowler(4, 10, 45, maidens=1, lbw=1))
        self.assertEqual(result["bowling_points"], 118)
        self.assertEqual(result["total_points"], 122)

    def test_10_duck_penalty_is_three(self):
        result = calculate_fantasy_points_odi(t20_batter(0, 5, caught_inning=1))
        self.assertEqual(result["total_points"], 1)


class TestTestScoring(unittest.TestCase):
    def test_11_two_innings_batter(self):
        # 115 runs + 10 fours + 4 sixes(8) + per-innings 50s(4+4) + 4
        stats = {
            "Total Runs Scored": 115, "Fours": 10, "Sixes": 4,
            "Innings 1 Runs": 60, "Innings 2 Runs": 55,
            "Innings 1 Balls Faced": 90, "Innings 2 Balls Faced": 80,
        }
        result = calculate_fantasy_points_test(stats)
        self.assertEqual(result["batting_points"], 141)
        self.assertEqual(result["total_points"], 145)

    def test_12_ten_wicket_match(self):
        # 10w(160) + 3 bowled(24) + in1 4wkts(4) + in2 6wkts(8) + 4
        stats = {
            "Wickets": 10, "Bowled": 3, "LBW": 0,
            "Innings 1 Wickets": 4, "Innings 2 Wickets": 6,
        }
        result = calculate_fantasy_points_test(stats)
        self.assertEqual(result["bowling_points"], 196)
        self.assertEqual(result["total_points"], 200)

    def test_13_none_values_are_zero(self):
        # Nulls and missing keys must not crash or fabricate points (issue: NoneType)
        stats = {"Wickets": None, "Overs Bowled": None, "Catches Taken": None}
        result = calculate_fantasy_points_test(stats)
        self.assertEqual(result["total_points"], 4)

    def test_14_per_innings_duck(self):
        # Inning-1 duck with per-innings balls faced: -4 + 4
        stats = {
            "Innings 1 Runs": 0, "Innings 1 Balls Faced": 8,
            "Innings 1 Balls Faced Inning 1": 8,
        }
        result = calculate_fantasy_points_test(stats)
        self.assertEqual(result["batting_points"], -4)
        self.assertEqual(result["total_points"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
