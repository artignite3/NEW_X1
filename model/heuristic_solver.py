import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json
import re
import datetime
import pulp
from scipy.stats import entropy
from typing import List, Dict, Tuple, Union

# Ensure model directory is on sys.path for internal imports
MODEL_DIR = Path(__file__).resolve().parent
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

try:
    from utils import get_past_match_performance
except ImportError:
    try:
        from model.utils import get_past_match_performance
    except ImportError:
        get_past_match_performance = None

try:
    from model import compute_player_stats_ml
except ImportError:
    try:
        from model.model import compute_player_stats_ml
    except ImportError:
        compute_player_stats_ml = None


def load_player_fantasy_points_for_optimization(json_file: str) -> Dict:
    """
    Loads and sorts player fantasy points data chronologically.

    Logic:
    1. Reads JSON file containing player match data
    2. For each player's matches, extracts dates using regex
    3. Sorts matches chronologically using datetime parsing
    4. Returns reconstructed dictionary with sorted matches

    Args:
        json_file (str): Path to JSON file with player fantasy points

    Returns:
        Dict: Player data with chronologically sorted matches
    """
    with open(json_file, "r") as file:
        data = json.load(file)
        sorted_data = {}
        for player, matches in data.items():
            match_list = list(matches.items())
            match_list_sorted = sorted(
                match_list,
                key=lambda x: datetime.datetime.strptime(
                    re.search(r'(\d{4}-\d{2}-\d{2})', x[0]).group(1),
                    '%Y-%m-%d'
                ) if re.search(r'(\d{4}-\d{2}-\d{2})', x[0]) else datetime.datetime.min
            )
            sorted_data[player] = dict(match_list_sorted)
    return sorted_data

def compute_player_stats(fantasy_points: Dict, players: List[str],
                        num_matches: int = 65, date_of_match: str = None,
                        key: str = 'total_points', use_ml: bool = False) -> pd.DataFrame:
    """
    Computes mean and variance of fantasy points for each player.
    Can use ML predictions or traditional statistical approach.

    Logic:
    1. For each player, retrieves last N matches performance
    2. Calculates mean and variance of points (statistical) OR
       Gets ML predictions for expected points
    3. Handles missing data by computing stats on available matches

    Args:
        fantasy_points (Dict): Historical fantasy points data
        players (List[str]): List of player names
        num_matches (int): Number of past matches to consider
        date_of_match (str): Optional cutoff date
        key (str): Key for points data in match info
        use_ml (bool): Whether to use ML predictions (True) or statistical (False)

    Returns:
        pd.DataFrame: DataFrame with player statistics (mean_points, variance)
    """
    if use_ml:
        # Use ML-based predictions
        return compute_player_stats_ml(
            fantasy_points, players, num_matches, date_of_match, key, use_ml=True
        )
    else:
        # Use traditional statistical approach
        stats_list = []
        for player in players:
            matches, points = get_past_match_performance(
                player, fantasy_points, num_matches, key, date_of_match
            )
            if points:
                mean_points = np.mean(points)
                variance_points = np.var(points)
                stats_list.append({
                    'player': player,
                    'mean_points': mean_points,
                    'variance': variance_points
                })
            else:
                stats_list.append({
                    'player': player,
                    'mean_points': 0.0,
                    'variance': 0.0
                })

        return pd.DataFrame(stats_list)

def compute_covariance_matrix(fantasy_points: Dict, players: List[str],
                            num_matches: int = 65,
                            date_of_match: str = None) -> pd.DataFrame:
    """
    Computes covariance matrix of fantasy points for players.

    Logic:
    1. For each player, retrieves last N matches performance
    2. Builds matrix of points for each match pair
    3. Computes covariance matrix
    4. Ensures matrix is symmetric and positive semidefinite

    Args:
        fantasy_points (Dict): Historical fantasy points data
        players (List[str]): List of player names
        num_matches (int): Number of past matches to consider
        date_of_match (str): Optional cutoff date

    Returns:
        pd.DataFrame: Covariance matrix (players x players)
    """
    # Get performance data for all players
    player_data = {}
    max_length = 0

    for player in players:
        matches, points = get_past_match_performance(
            player, fantasy_points, num_matches, 'total_points', date_of_match
        )
        player_data[player] = points
        max_length = max(max_length, len(points))

    # Pad shorter sequences with the last available value or 0
    for player in players:
        points = player_data[player]
        if len(points) < max_length:
            if points:
                # Pad with last available value
                points.extend([points[-1]] * (max_length - len(points)))
            else:
                # Pad with zeros if no data
                points.extend([0] * (max_length - len(points)))
        player_data[player] = points

    # Create DataFrame where rows are matches and columns are players
    df = pd.DataFrame(player_data)

    # Compute covariance matrix
    cov_matrix = df.cov()

    # Handle NaN values (if a player has zero variance)
    cov_matrix = cov_matrix.fillna(0)

    # Ensure symmetry
    cov_matrix = (cov_matrix + cov_matrix.T) / 2

    # Ensure the covariance matrix is positive semidefinite
    # Small values on the diagonal can help with numerical stability
    min_eigenvalue = np.min(np.real(np.linalg.eigvals(cov_matrix.values)))
    if min_eigenvalue < 0:
        # Add a small value to the diagonal to make it positive semidefinite
        cov_matrix.values.flat[::len(cov_matrix) + 1] += (-min_eigenvalue + 1e-8)

    return cov_matrix

def optimize_team_sharpe(
    player_stats,
    cov_matrix,
    risk_aversion=0.05,
    max_players=11,
    min_players_per_team=1,
    max_players_per_team=7,
    **kwargs
):
    """
    Binary team selection using PuLP with role and team constraints.

    Objective:
        maximize expected_points - λ * variance

    Role constraints:

        WK:   1 ≤ selected ≤ 5
        BAT:  1 ≤ selected ≤ 6
        BOWL: 2 ≤ selected ≤ 5
        AR:   0 ≤ selected ≤ 5
        Total = 11
        Per team: min_players_per_team ≤ selected ≤ max_players_per_team
    """

    n = len(player_stats)
    players  = player_stats["player"].tolist()
    mu       = player_stats["mean_points"].values
    variances = np.diag(cov_matrix)

    # ── Role index lists ─────────────────────────────────────────────
    roles = player_stats.get("role", pd.Series(["BAT"] * n, name="role"))
    if isinstance(roles, pd.Series):
        roles = roles.tolist()

    wk_idx   = [i for i, r in enumerate(roles) if str(r).upper() in ("WK",  "WICKETKEEPER")]
    bat_idx  = [i for i, r in enumerate(roles) if str(r).upper() in ("BAT", "BATTER")]
    bowl_idx = [i for i, r in enumerate(roles) if str(r).upper() in ("BOWL","BOWLER")]
    ar_idx   = [i for i, r in enumerate(roles) if str(r).upper() in ("AR",  "ALLROUNDER", "ALL-ROUNDER")]

    # ── Team index lists ─────────────────────────────────────────────
    team_col = "team" if "team" in player_stats.columns else None
    team_indices = {}
    if team_col:
        for team in player_stats[team_col].unique():
            team_indices[team] = [
                i for i, t in enumerate(player_stats[team_col].tolist()) if t == team
            ]

    # ── Debug top scores ─────────────────────────────────────────────
    scores = [(players[i], mu[i] - risk_aversion * variances[i]) for i in range(n)]
    scores.sort(key=lambda x: x[1], reverse=True)
    print("\n===== TOP OBJECTIVE SCORES =====")
    for player, score in scores[:15]:
        print(player, round(score, 2))
    print("===============================\n")

    # ── PuLP model ───────────────────────────────────────────────────
    lp = pulp.LpProblem("NEW_X1_Optimization", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)}

    # Objective
    lp += pulp.lpSum((mu[i] - risk_aversion * variances[i]) * x[i] for i in range(n))

    # Total players
    lp += pulp.lpSum(x[i] for i in range(n)) == max_players

    # Role constraints (only if role data available)
    if wk_idx:
        lp += pulp.lpSum(x[i] for i in wk_idx)   >= 1
        lp += pulp.lpSum(x[i] for i in wk_idx)   <= 5
    if bat_idx:
        lp += pulp.lpSum(x[i] for i in bat_idx)  >= 1
        lp += pulp.lpSum(x[i] for i in bat_idx)  <= 6
    if bowl_idx:
        lp += pulp.lpSum(x[i] for i in bowl_idx) >= 2
        lp += pulp.lpSum(x[i] for i in bowl_idx) <= 5
    if ar_idx:
        lp += pulp.lpSum(x[i] for i in ar_idx)   <= 5

    # Per-team constraints
    for team, idx in team_indices.items():
        lp += pulp.lpSum(x[i] for i in idx) >= min_players_per_team
        lp += pulp.lpSum(x[i] for i in idx) <= max_players_per_team

    # Solve
    lp.solve(pulp.PULP_CBC_CMD(msg=False))

    selected_players = [players[i] for i in range(n) if pulp.value(x[i]) > 0.5]
    objective_value  = pulp.value(lp.objective)

    return selected_players, objective_value

def optimize_team_advanced(player_stats: pd.DataFrame,
                          cov_matrix: pd.DataFrame,
                          risk_aversion: float = 0.05,
                          diversity_weight: float = 0.1,
                          form_weight: float = 0.1,
                          max_players: int = 11,
                          team_constraints: Dict[str, int] = None) -> Tuple[List[str], Dict]:
    """
    Advanced team optimization with multiple objectives

    Args:
        player_stats: DataFrame with player statistics
        cov_matrix: Covariance matrix of player performances
        risk_aversion: Risk aversion parameter
        diversity_weight: Weight for diversity objective
        form_weight: Weight for form objective
        max_players: Maximum number of players in team
        team_constraints: Dict mapping team names to min/max players allowed

    Returns:
        Tuple of (selected_players_list, metrics_dict)
    """
    # For now, delegate to Sharpe optimization
    # In a full implementation, this would balance multiple objectives
    selected_players, sharpe = optimize_team_sharpe(
        player_stats, cov_matrix, risk_aversion, max_players, min_players_per_team=2, max_players_per_team=9
    )

    # Calculate additional metrics
    metrics = {
        'sharpe_ratio': sharpe,
        'expected_points': player_stats[
            player_stats['player'].isin(selected_players)
        ]['mean_points'].sum() if len(selected_players) > 0 else 0,
        'diversity_score': 0.0,  # Placeholder
        'form_score': 0.0       # Placeholder
    }
    print("Selected:", len(selected_players))
    print(selected_players)
    return selected_players, metrics

def optimize_team_advanced_test(player_stats: pd.DataFrame,
                               cov_matrix: pd.DataFrame,
                               risk_aversion: float = 0.05,
                               max_players: int = 11) -> Tuple[List[str], float]:
    """
    Test optimization function

    Args:
        player_stats: DataFrame with player statistics
        cov_matrix: Covariance matrix of player performances
        risk_aversion: Risk aversion parameter
        max_players: Maximum number of players in team

    Returns:
        Tuple of (selected_players_list, expected_points)
    """
    selected_players, _ = optimize_team_sharpe(
        player_stats, cov_matrix, risk_aversion, max_players, min_players_per_team=1
    )

    expected_points = player_stats[
        player_stats['player'].isin(selected_players)
    ]['mean_points'].sum() if len(selected_players) > 0 else 0

    return selected_players, expected_points