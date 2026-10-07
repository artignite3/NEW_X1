"""
NEW_X1 — M3: Independent squad validator
Re-checks a generated XI against the product contract, separate from the
solver that produced it. Runs on every /generate_best_team response and is
exercised adversarially in tests/test_squad_validator.py.

Validation is mode-aware:
  - "strict"        — full contract (role bounds, team spread, availability)
  - "relaxed_team"  — team-spread requirement dropped
  - "relaxed_roles" — role bounds dropped too
Hard invariants always apply: exactly 11 unique players drawn from the pool,
no INJURED/RESTED/SUSPENDED selection, captain and vice-captain in the XI.
"""

from typing import Dict, List, Optional

ROLE_BOUNDS = {"WK": (1, 5), "BAT": (1, 6), "BOWL": (2, 5), "AR": (0, 5)}
TEAM_BOUNDS = (1, 7)
BLOCKED_STATUSES = {"INJURED", "RESTED", "SUSPENDED"}
REQUIRED_SIZE = 11


def validate_squad(best_team: List[dict], pool: List[dict],
                   constraint_mode: str = "strict",
                   captain: Optional[str] = None,
                   vice_captain: Optional[str] = None) -> Dict:
    violations: List[str] = []

    if len(best_team) != REQUIRED_SIZE:
        violations.append(f"XI has {len(best_team)} players, expected {REQUIRED_SIZE}")

    keys = [p.get("fantasy_key") for p in best_team]
    if len(set(keys)) != len(keys):
        violations.append("duplicate player identities in the XI")

    pool_keys = {p.get("fantasy_key") or p.get("display_name") for p in pool}
    for p in best_team:
        identity = p.get("fantasy_key") or p.get("display_name")
        if identity not in pool_keys:
            violations.append(f"selected player not in the request pool: {p.get('display_name')}")
        if str(p.get("injury_status", "")).upper() in BLOCKED_STATUSES:
            violations.append(f"unavailable player selected: {p.get('display_name')} ({p.get('injury_status')})")

    if constraint_mode in ("strict", "relaxed_team"):
        role_counts: Dict[str, int] = {}
        for p in best_team:
            role_counts[p.get("role", "BAT")] = role_counts.get(p.get("role", "BAT"), 0) + 1
        for role, (low, high) in ROLE_BOUNDS.items():
            count = role_counts.get(role, 0)
            if count < low:
                violations.append(f"role {role}: {count} selected, minimum {low}")
            if count > high:
                violations.append(f"role {role}: {count} selected, maximum {high}")

    if constraint_mode == "strict":
        team_counts: Dict[str, int] = {}
        for p in best_team:
            team_counts[p.get("team", "?")] = team_counts.get(p.get("team", "?"), 0) + 1
        for team, count in team_counts.items():
            if count < TEAM_BOUNDS[0]:
                violations.append(f"team {team}: {count} selected, minimum {TEAM_BOUNDS[0]}")
            if count > TEAM_BOUNDS[1]:
                violations.append(f"team {team}: {count} selected, maximum {TEAM_BOUNDS[1]}")

    if captain and captain not in {p.get("display_name") for p in best_team}:
        violations.append(f"captain {captain} is not in the XI")
    if vice_captain and vice_captain not in {p.get("display_name") for p in best_team}:
        violations.append(f"vice-captain {vice_captain} is not in the XI")

    return {
        "valid": not violations,
        "constraint_mode": constraint_mode,
        "violations": violations,
        "role_counts": {
            role: sum(1 for p in best_team if p.get("role") == role)
            for role in ("WK", "BAT", "AR", "BOWL")
        },
    }
