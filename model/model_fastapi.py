from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import pandas as pd
from pipeline import calculate_optimal_team, evaluate_team
from utils import load_player_fantasy_points, calculate_team_metrics
import os
import sys

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

sys.path.insert(0, PROJECT_ROOT)

from pipeline import calculate_optimal_team, evaluate_team

# # Path to the JSON file
T20_fantasy_points = "../data/processed/player_fantasy_points_t20.json"
ODI_fantasy_points = "../data/processed/player_fantasy_points_odi.json"
Test_fantasy_points = "../data/processed/player_fantasy_points_test.json"


app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allows your frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def home():
    return {"message": "API is running"}


@app.post("/generate_best_team")
def generate_best_team(request_data: dict):
    print("GENERATE_BEST_TEAM CALLED")

    # Extract data from request body
    player_info = request_data.get('player_info')
    date = request_data.get('date')
    format = request_data.get('format')
    use_ml = request_data.get('use_ml', False)  # Default to False for backward compatibility

    # Validation
    if not player_info:
        raise HTTPException(status_code=400, detail="Squad Not Found")
    if not date:
        raise HTTPException(status_code=400, detail="Please Enter the Date in YYYY-MM-DD Format")
    if not format:
        raise HTTPException(status_code=400, detail="Please Enter the correct format: ODI/Test/T20")

    if player_info and date and format:
        fantasy_points_data = None
        if format.upper() == "T20":
            fantasy_points_data = load_player_fantasy_points(T20_fantasy_points)
        elif format.upper() == "ODI":
            fantasy_points_data = load_player_fantasy_points(ODI_fantasy_points)
        elif format.upper() == "TEST":
            fantasy_points_data = load_player_fantasy_points(Test_fantasy_points)
        else:
            raise HTTPException(status_code=400, detail="Invalid format. Must be ODI/Test/T20")

        selected_players, stats_df, cov_matrix = calculate_optimal_team(
            player_info=player_info,
            num_matches=65,
            date_of_match=date,
            risk_aversion=0.1,
            solver='pulp',
            fantasy_points_data=fantasy_points_data,
            use_ml=use_ml
        )

        # Check if the player exists in the data
        if selected_players is None or stats_df is None or stats_df.empty:
            raise HTTPException(status_code=404, detail="Team is Not Selected Correctly")

        player_stats_json = stats_df.to_json(orient='records')
        cov_matrix_json = cov_matrix.to_json(orient='records')

        return {
            "best_team": selected_players,
            "player_stats": player_stats_json,
            "cov_matrix": cov_matrix_json
        }


@app.post("/team_evaluation")
def team_evaluation(request_data: dict):
    # Extract data from request body
    best_team = request_data.get('best_team')
    player_stats = request_data.get('player_stats')
    cov_matrix = request_data.get('cov_matrix')

    # Validation
    if not best_team:
        raise HTTPException(status_code=400, detail="Best Team not loaded correctly")
    if not player_stats:
        raise HTTPException(status_code=400, detail="Player Stats not loaded correctly")
    if not cov_matrix:
        raise HTTPException(status_code=400, detail="Player Covariance Matrix not loaded correctly")

    selected_players = best_team
    stats_df = pd.DataFrame(json.loads(player_stats))
    cov_matrix_df = pd.DataFrame(json.loads(cov_matrix))

    if selected_players and not stats_df.empty and not cov_matrix_df.empty:
        evaluation_tuple = evaluate_team(selected_players, stats_df, cov_matrix_df)
        if evaluation_tuple:
            return {
                "team_consistency_score": evaluation_tuple[0],
                "team_diversity_score": evaluation_tuple[1],
                "form_score": evaluation_tuple[2]
            }
        else:
            raise HTTPException(status_code=404, detail="Team Evaluation is not done correctly")
    else:
        raise HTTPException(status_code=400, detail="Players are not selected correctly or Player Stats are corrupted or Covariance Matrix is Corrupted")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=5002)