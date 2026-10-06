"""
ML Prediction Service for Fantasy Cricket Points
Supports multiple algorithms (XGBoost, CatBoost, LightGBM) for different formats
"""

import pandas as pd
import json
import os
from datetime import datetime
import re
import itertools
from typing import Dict, List, Tuple, Optional, Union
import warnings
warnings.filterwarnings('ignore')
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)
import numpy as np
# Try to import ML libraries, with fallbacks
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: XGBoost not available")

try:
    from catboost import CatBoostRegressor
    CATBOOST_AVAILABLE = True
except ImportError:
    CATBOOST_AVAILABLE = False
    print("Warning: CatBoost not available")

try:
    from lightgbm import LGBMRegressor
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False
    print("Warning: LightGBM not available")

from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import LabelEncoder
import joblib
from utils import get_past_match_performance  # Import the utility function

# Feature definitions (keeping from original)
past_features = [
    "total_runs",
    "avg_runs_per_inning",
    "boundaries",
    "sixes",
    "average_sixes_per_inning",
    "fours",
    "average_fours_per_inning",
    "boundary_percent_per_inning",
    "wickets",
    "avg_wickets_per_inning",
    "catches_taken",
    "stumped_outs_made",
    "run_outs_made",
    "balls_faced",
    "avg_balls_faced_per_inning",
    "avg_batting_sr_per_inning",
    "avg_runs_ball_per_inning",
    "overs_bowled",
    "bowls_bowled",
    "average_bowls_bowled_per_inning",
    "avg_economy_rate_per_inning",
    "average_consecutive_dot_balls",
    "runs_given",
    "runs_given_ball_per_inning",
    "batting_sr_aa",
]

bowling_features = [
    "wickets",
    "avg_wickets_per_inning",
    "avg_runs_ball_per_inning",
    "overs_bowled",
    "bowls_bowled",
    "average_bowls_bowled_per_inning",
    "avg_economy_rate_per_inning",
    "runs_given",
    "runs_given_ball_per_inning",
]

batting_features = [
    "total_runs",
    "avg_runs_per_inning",
    "boundaries",
    "sixes",
    "average_sixes_per_inning",
    "fours",
    "average_fours_per_inning",
    "boundary_percent_per_inning",
    "balls_faced",
    "avg_balls_faced_per_inning",
    "avg_batting_sr_per_inning",
    "avg_runs_ball_per_inning",
    "average_consecutive_dot_balls",
    "batting_sr_aa",
]

# Aggregate columns for stats
agg_cols = [
    "Batting", "Bowling", "Games", "Won", "Drawn", "Win %", "Innings Batted",
    "Runs", "Singles", "Fours", "Sixes", "Dot Balls", "Balls Faced", "Outs",
    "Bowled Outs", "LBW Outs", "Hitwicket Outs", "Caught Outs", "Stumped Outs",
    "Run Outs", "Caught and Bowled Outs", "Dot Ball %", "Strike Turnover %",
    "Batting S/R", "Batting S/R MeanAD", "Batting Avg", "Mean Score",
    "Score MeanAD", "Scoring Consistency", "Boundary %", "Runs/Ball",
    "Mean Balls Faced", "Balls Faced MeanAD", "Survival Consistency",
    "Avg First Boundary Ball", "Dismissal Rate", "Boundary Rate",
    "Innings Bowled", "Runsgiven", "Singlesgiven", "Foursgiven", "Sixesgiven",
    "Wickets", "Balls Bowled", "Extras", "No Balls", "Wides", "Dot Balls Bowled",
    "Bowleds", "LBWs", "Hitwickets", "Caughts", "Stumpeds", "Caught and Bowleds",
    "Catches", "Runouts", "Stumpings", "Economy Rate", "Economy Rate MeanAD",
    "Dot Ball Bowled %", "Boundary Given %", "Bowling Avg", "Bowling Avg MeanAD",
    "Bowling S/R", "Bowling S/R MeanAD", "Runsgiven/Ball", "Boundary Given Rate",
    "Strike Turnovergiven %", "Avg Consecutive Dot Balls", "Runs Rate",
    "Runsgiven/Wicket", "Runs AA", "Runs/Ball AA", "Runsgiven AA", "Runsgiven/Ball AA",
]


class MLPredictionService:
    """Service for ML-based fantasy points prediction"""

    def __init__(self, model_dir: str="."):
        """
        Initialize the ML prediction service

        Args:
            model_dir: Directory where trained models are stored
        """
        self.model_dir = model_dir
        self.models = {}  # Format -> {target: model}
        self.label_encoders = {}  # Format -> {column: encoder}
        self.feature_lists = {
            'batting': batting_features,
            'bowling': bowling_features,
            'fielding': ["catches_taken", "stumped_outs_made", "run_outs_made"]  # Fielding-specific features
        }

        # Try to load pre-trained models
        self._load_models()

    def _load_models(self):
        """Load pre-trained models for all formats and targets"""
        formats = ['t20', 'odi', 'test']
        targets = ['batting', 'bowling', 'fielding']
        algorithms = ['xgboost', 'catboost', 'lightgbm']
        
        for fmt in formats:
            self.models[fmt] = {}
            self.label_encoders[fmt] = {}

            for target in targets:
                model_loaded = False
                # Try different algorithms in order of preference
                for algo in algorithms:
                    model_path = os.path.join(
                        self.model_dir,
                        f"{algo}_model_{target}_{fmt}.joblib"
                    )
                    encoder_path = os.path.join(
                        self.model_dir,
                        f"{algo}_label_encoders_{target}_{fmt}.joblib"
                    )

                    if os.path.exists(model_path):
                        try:
                            self.models[fmt][target] = joblib.load(model_path)
                            # Try to load encoder if it exists, but don't require it
                            if os.path.exists(encoder_path):
                                try:
                                    self.label_encoders[fmt][target] = joblib.load(encoder_path)
                                except Exception:
                                    # If encoder loading fails, continue without it
                                    self.label_encoders[fmt][target] = {}
                            else:
                                # No encoder file found, use empty dict
                                self.label_encoders[fmt][target] = {}
                            model_loaded = True
                            print(f"Loaded {algo} model for {target} ({fmt})")
                            break
                        except Exception as e:
                            print(f"Error loading {algo} model for {target} ({fmt}): {e}")

                if not model_loaded:
                    print(f"No pre-trained model found for {target} ({fmt})")                
        
    def _extract_features_from_match(self, match_stats: Dict, feature_type: str='combined') -> Dict:
        """
        Extract features from a single match's statistics

        Args:
            match_stats: Dictionary containing match statistics
            feature_type: Type of features to extract ('batting', 'bowling', 'fielding', or 'combined')

        Returns:
            Dictionary of features
        """
        features = {}

        # Determine which feature set to use based on feature_type
        if feature_type == 'batting':
            selected_features = batting_features
        elif feature_type == 'bowling':
            selected_features = bowling_features
        elif feature_type == 'fielding':
            selected_features = self.feature_lists['fielding']
        else:  # 'combined' or any other value
            selected_features = batting_features + bowling_features

        for feature in selected_features:
            if feature in match_stats:
                value = match_stats[feature]
                # Try to convert string values to numeric when possible
                try:
                    features[feature] = float(value)
                except:
                    features[feature] = 0.0
                else:
                    features[feature] = value
            else:
                # Default value for missing features
                features[feature] = 0

        return features

    def _prepare_player_features(self, player_matches: List[Tuple[str, Dict]],
                                num_matches: int=10, feature_type: str='combined') -> pd.DataFrame:
        """
        Prepare features for a player based on their recent matches

        Args:
            player_matches: List of (match_id, match_stats) tuples, sorted chronologically
            num_matches: Number of recent matches to consider
            feature_type: Type of features to extract ('batting', 'bowling', 'fielding', or 'combined')

        Returns:
            DataFrame with features for ML prediction
        """
        if not player_matches:
            # Return empty DataFrame with expected columns
            if feature_type == 'batting':
                expected_cols = batting_features
            elif feature_type == 'bowling':
                expected_cols = bowling_features
            elif feature_type == 'fielding':
                expected_cols = self.feature_lists['fielding']
            else:  # 'combined'
                expected_cols = list(dict.fromkeys(batting_features + bowling_features))  # Remove duplicates
            return pd.DataFrame(columns=expected_cols)

        # Get recent matches
        recent_matches = player_matches[-num_matches:] if len(player_matches) >= num_matches else player_matches

        # If we don't have enough matches, pad with the earliest match
        if len(recent_matches) < num_matches and recent_matches:
            padding = [recent_matches[0]] * (num_matches - len(recent_matches))
            recent_matches = padding + recent_matches

        # Extract features for each match
        feature_rows = []
        for match_id, match_stats in recent_matches:
            features = self._extract_features_from_match(match_stats, feature_type)
            feature_rows.append(features)

        # Create DataFrame
        if feature_rows:
            df = pd.DataFrame(feature_rows)
            # Ensure all expected columns are present
            if feature_type == 'batting':
                expected_cols = batting_features
            elif feature_type == 'bowling':
                expected_cols = bowling_features
            elif feature_type == 'fielding':
                expected_cols = self.feature_lists['fielding']
            else:  # 'combined'
                expected_cols = list(dict.fromkeys(batting_features + bowling_features))  # Remove duplicates

            for col in expected_cols:
                if col not in df.columns:
                    df[col] = 0
            return df[expected_cols]
        else:
            if feature_type == 'batting':
                expected_cols = batting_features
            elif feature_type == 'bowling':
                expected_cols = bowling_features
            elif feature_type == 'fielding':
                expected_cols = self.feature_lists['fielding']
            else:  # 'combined'
                expected_cols = list(dict.fromkeys(batting_features + bowling_features))  # Remove duplicates
            return pd.DataFrame(columns=expected_cols)

    def prepare_training_data(self, fantasy_points_data, format_type):
        """
        Convert raw fantasy points data into training datasets

        Args:
            fantasy_points_data: Dictionary with player match data
            format_type: 't20', 'odi', or 'test'

        Returns:
            X_batting, y_batting, X_bowling, y_bowling, X_fielding, y_fielding
        """
        # Import required modules if not already imported
        import pandas as pd
        import numpy as np

        # Initialize lists to collect training samples
        batting_samples, bowling_samples, fielding_samples = [], [], []
        batting_targets, bowling_targets, fielding_targets = [], [], []

        # Process each player's match history
        for player_name, matches in fantasy_points_data.items():
            for match_key, match_stats in matches:
                # Get target values (actual fantasy points from this match)
                batting_target = match_stats.get('batting_points', 0)
                bowling_target = match_stats.get('bowling_points', 0)
                fielding_target = match_stats.get('fielding_points', 0)

                # Extract features for each target type using appropriate feature sets
                batting_features = self._extract_features_from_match(match_stats, 'batting')
                bowling_features = self._extract_features_from_match(match_stats, 'bowling')
                fielding_features = self._extract_features_from_match(match_stats, 'fielding')

                # Add to appropriate lists
                batting_samples.append(batting_features)
                batting_targets.append(batting_target)

                bowling_samples.append(bowling_features)
                bowling_targets.append(bowling_target)

                fielding_samples.append(fielding_features)
                fielding_targets.append(fielding_target)

        # Convert to DataFrames
        X_batting = pd.DataFrame(batting_samples) if batting_samples else pd.DataFrame()
        y_batting = np.array(batting_targets) if batting_targets else np.array([])
        X_bowling = pd.DataFrame(bowling_samples) if bowling_samples else pd.DataFrame()
        y_bowling = np.array(bowling_targets) if bowling_targets else np.array([])
        X_fielding = pd.DataFrame(fielding_samples) if fielding_samples else pd.DataFrame()
        y_fielding = np.array(fielding_targets) if fielding_targets else np.array([])

        return X_batting, y_batting, X_bowling, y_bowling, X_fielding, y_fielding

    def predict_player_points(self, player_name: str, fantasy_points_data: Dict,
                            format_type: str='t20', num_matches: int=10,
                            date_of_match: Optional[str]=None) -> Dict[str, float]:
        """
        Predict fantasy points for a player using ML models

        Args:
            player_name: Name of the player
            fantasy_points_data: Historical fantasy points data
            format_type: Game format ('t20', 'odi', 'test')
            num_matches: Number of recent matches to consider for features
            date_of_match: Optional cutoff date (YYYY-MM-DD)

        Returns:
            Dictionary with predicted points for batting, bowling, fielding
        """
        format_type = format_type.lower()

        # Get player's historical data
        player_data = fantasy_points_data.get(player_name, {})
        if not player_data:
            return {'batting': 0.0, 'bowling': 0.0, 'fielding': 0.0}

        # Convert to list and sort by date
        matches_data = list(player_data.items()) if isinstance(player_data, dict) else player_data

        # Filter by date if specified
        if date_of_match:
            try:
                cutoff_date = datetime.strptime(date_of_match, '%Y-%m-%d')
                filtered_matches = []
                for match_id, match_stats in matches_data:
                    match_date_str = re.search(r'(\d{4}-\d{2}-\d{2})', match_id)
                    if match_date_str:
                        match_date = datetime.strptime(match_date_str.group(1), '%Y-%m-%d')
                        if match_date <= cutoff_date:
                            filtered_matches.append((match_id, match_stats))
                matches_data = filtered_matches
            except Exception as e:
                print(f"Error filtering by date: {e}")

        # Sort by date (oldest first)
        try:
            matches_data.sort(
                key=lambda x: datetime.strptime(
                    "-".join(x[0].split("-")[-5:-2]), "%Y-%m-%d"
                ) if re.search(r'(\d{4}-\d{2}-\d{2})', x[0]) else datetime.min
            )
        except Exception as e:
            print(f"Error sorting matches by date: {e}")

        # Prepare features
        features_df = self._prepare_player_features(matches_data, num_matches)

        if features_df.empty or len(features_df) == 0:
            return {'batting': 0.0, 'bowling': 0.0, 'fielding': 0.0}

        # Use the most recent match's features for prediction
        # (alternatively, we could average features across matches)
        latest_features = features_df.iloc[-1:].copy()

        # Handle label encoding if needed
        if format_type in self.label_encoders:
            for col in latest_features.columns:
                if col in self.label_encoders[format_type]:
                    try:
                        latest_features[col] = self.label_encoders[format_type][col].transform(
                            latest_features[col].astype(str)
                        )
                    except Exception:
                        # If encoding fails, keep original value
                        pass

        # Make predictions
        predictions = {'batting': 0.0, 'bowling': 0.0, 'fielding': 0.0}

        format_models = self.models.get(format_type, {})

        # Predict batting points
        if 'batting' in format_models and format_models['batting'] is not None:
            try:
                # Use only batting features for batting model
                batting_features_only = latest_features[batting_features] if all(f in latest_features.columns for f in batting_features) else latest_features
                pred = format_models['batting'].predict(batting_features_only)[0]
                predictions['batting'] = max(0, float(pred))  # Ensure non-negative
            except Exception as e:
                print(f"Error predicting batting points: {e}")

        # Predict bowling points
        if 'bowling' in format_models and format_models['bowling'] is not None:
            try:
                # Use only bowling features for bowling model
                bowling_features_only = latest_features[bowling_features] if all(f in latest_features.columns for f in bowling_features) else latest_features
                pred = format_models['bowling'].predict(bowling_features_only)[0]
                predictions['bowling'] = max(0, float(pred))  # Ensure non-negative
            except Exception as e:
                print(f"Error predicting bowling points: {e}")

        # Predict fielding points
        if 'fielding' in format_models and format_models['fielding'] is not None:
            try:
                # Use all features for fielding model (or whatever was used during training)
                fielding_features_only = latest_features
                pred = format_models['fielding'].predict(fielding_features_only)[0]
                predictions['fielding'] = max(0, float(pred))  # Ensure non-negative
            except Exception as e:
                print(f"Error predicting fielding points: {e}")

        return predictions


# Global instance for easy access
import os
ml_service = MLPredictionService(model_dir=os.path.dirname(os.path.abspath(__file__)))


def compute_player_stats_ml(fantasy_points: Dict, players: List[str],
                           num_matches: int=65, date_of_match: str=None,
                           key: str='total_points', use_ml: bool=True) -> pd.DataFrame:
    """
    Compute player statistics using ML predictions (fallback to statistical if ML fails)

    Args:
        fantasy_points: Historical fantasy points data
        players: List of player names
        num_matches: Number of past matches to consider
        date_of_match: Optional cutoff date
        key: Key for points data in match info
        use_ml: Whether to use ML predictions (True) or statistical (False)

    Returns:
        DataFrame with player statistics (mean_points, variance)
    """
    if not use_ml:
        # Fall back to original statistical method
        from heuristic_solver import compute_player_stats
        return compute_player_stats(fantasy_points, players, num_matches, date_of_match, key)

    stats_list = []
    for player in players:
        try:
            # Get ML predictions
            predictions = ml_service.predict_player_points(
                player, fantasy_points,
                format_type='t20',  # TODO: Determine format from context
                num_matches=min(num_matches, 10),  # Use recent matches for features
                date_of_match=date_of_match
            )

            # Use predicted points as mean
            mean_points = predictions['batting'] + predictions['bowling'] + predictions['fielding']

            # For variance, we could use prediction uncertainty or historical variance
            # For now, use a small fixed variance or compute from recent historical points
            matches, points = get_past_match_performance(
                player, fantasy_points, min(num_matches, 20), key, date_of_match
            )
            if points and len(points) > 1:
                variance_points = np.var(points)
            else:
                variance_points = 1.0  # Default variance

            stats_list.append({
                'player': player,
                'mean_points': mean_points,
                'variance': variance_points
            })
        except Exception as e:
            print(f"Error computing ML stats for {player}: {e}")
            # Fall back to statistical method for this player
            matches, points = get_past_match_performance(
                player, fantasy_points, num_matches, key, date_of_match
            )
            if points:
                mean_points = np.mean(points)
                variance_points = np.var(points)
            else:
                mean_points = 0.0
                variance_points = 0.0

            stats_list.append({
                'player': player,
                'mean_points': mean_points,
                'variance': variance_points
            })

    return pd.DataFrame(stats_list)


# Backward compatibility functions
def train_models_for_format(format_type: str, fantasy_points_data: Dict,
                            model_dir: str="."):
    """
    Train ML models for a specific format

    Args:
        format_type: Game format ('t20', 'odi', 'test')
        fantasy_points_data: Historical fantasy points data
        model_dir: Directory to save trained models
    """
    print(f"Training models for {format_type} format...")

    # Prepare training data
    # Create an instance of MLPredictionService to access helper methods
    ml_service_instance = MLPredictionService()
    X_batting, y_batting, X_bowling, y_bowling, X_fielding, y_fielding = \
        ml_service_instance.prepare_training_data(fantasy_points_data, format_type)

    # Define models to train
    algorithms = ['xgboost', 'catboost', 'lightgbm']
    targets = ['batting', 'bowling', 'fielding']
    results = []
    # Feature lists (should match those used in prediction)
    feature_lists = {
        'batting': batting_features,
        'bowling': bowling_features,
        'fielding': []  # Will be determined from data
    }

    # Train models for each target
    for target in targets:
        print(f"  Training {target} models...")

        # Select appropriate dataset
        if target == 'batting':
            X, y = X_batting, y_batting
        elif target == 'bowling':
            X, y = X_bowling, y_bowling
        else:  # fielding
            X, y = X_fielding, y_fielding
            # For fielding, use all available features if list is empty
            if not feature_lists[target]:
                feature_lists[target] = list(X.columns)

        # Ensure we have the right features
        X = X[feature_lists[target]]
        # Force all features to numeric
        for col in X.columns:
            X[col] = pd.to_numeric(X[col], errors="coerce")

    # Replace NaN generated during conversion
        X = X.fillna(0)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.2,
            random_state=42
        )
        
        print(f"\n{target.upper()} feature dtypes:")
        print(X.dtypes)

        # Train each algorithm
        for algo in algorithms:
            model_path = os.path.join(model_dir, f"{algo}_model_{target}_{format_type}.joblib")
            encoder_path = os.path.join(model_dir, f"{algo}_label_encoders_{target}_{format_type}.joblib")

            try:
                model = None
                if algo == 'xgboost' and XGBOOST_AVAILABLE:
                    model = xgb.XGBRegressor(
                        n_estimators=100,
                        max_depth=6,
                        learning_rate=0.1,
                        random_state=42
                    )
                elif algo == 'catboost' and CATBOOST_AVAILABLE:
                    model = CatBoostRegressor(
                        iterations=100,
                        depth=6,
                        learning_rate=0.1,
                        random_seed=42,
                        verbose=False
                    )
                elif algo == 'lightgbm' and LIGHTGBM_AVAILABLE:
                    model = LGBMRegressor(
                        n_estimators=100,
                        max_depth=6,
                        learning_rate=0.1,
                        random_state=42
                    )

                if model is not None:
                    # Train the model
                    model.fit(X_train, y_train)
                    preds = model.predict(X_test)
                    
                    mae = mean_absolute_error(y_test, preds)
                    mse = mean_squared_error(y_test, preds)
                    rmse = np.sqrt(mse)
                    r2 = r2_score(y_test, preds)
                    
                    print(f"\n    {algo.upper()} RESULTS")
                    print(f"      MAE  : {mae:.4f}")
                    print(f"      MSE  : {mse:.4f}")
                    print(f"      RMSE : {rmse:.4f}")
                    print(f"      R2   : {r2:.4f}")
                    
                    results.append({
                        "Format": format_type,
                        "Target": target,
                        "Model": algo,
                        "MAE": mae,
                        "MSE": mse,
                        "RMSE": rmse,
                        "R2": r2
                    })
                    
                    # Save model and encoders (if any)
                    joblib.dump(model, model_path)
                    # Note: Label encoders would be saved if categorical features exist
                    print(f"    Saved {algo} model for {target} ({format_type})")
                else:
                    print(f"    Skipping {algo} - not available")

            except Exception as e:
                print(f"    Error training {algo} for {target}: {e}")

        print(f"Completed training for {format_type} format")
        
        metrics_df = pd.DataFrame(results)

        metrics_path = os.path.join(
            model_dir,
            f"metrics_{format_type}.csv"
        )

        metrics_df.to_csv(metrics_path, index=False)

        print("\n======================")
        print(f"Metrics saved to:")
        print(metrics_path)
        print("======================")

        print(metrics_df)        


def predict_with_ml(player_name: str, fantasy_points_data: Dict,
                   format_type: str='t20') -> Dict[str, float]:
    """
    Simple interface for ML prediction

    Args:
        player_name: Name of the player
        fantasy_points_data: Historical fantasy points data
        format_type: Game format

    Returns:
        Dictionary with predicted points
    """
    return ml_service.predict_player_points(
        player_name, fantasy_points_data, format_type
    )
