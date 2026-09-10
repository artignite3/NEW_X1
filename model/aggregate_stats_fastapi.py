from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
import requests
import pandas as pd

# ── Local LLM via Ollama ──────────────────────────────────────────────────────
def call_llm(prompt: str, model: str = "llama3.2:3b") -> str:
    """
    Call local Ollama LLM.
    Requires: ollama serve  +  ollama pull llama3.2:3b
    Falls back to a rule-based summary if Ollama is not running.
    """
    try:
        import ollama as _ollama
        resp = _ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp["message"]["content"]
    except Exception as e:
        return f"[LLM unavailable — start Ollama with 'ollama serve'] Error: {e}"
# ─────────────────────────────────────────────────────────────────────────────

# Path to the JSON file
T20_aggregate_points = "../data/processed/T20_data_aggregate_data.json"
ODI_ODM_aggregate_points = "../data/processed/ODI_ODM_data_aggregate_data.json"
Test_MDM_aggregate_points = "../data/processed/Test_MDM_data_aggregate_data.json"

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allows your frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Load the data from your JSON file
with open(T20_aggregate_points, "r") as file:
    player_T20_data = json.load(file)

with open(ODI_ODM_aggregate_points, "r") as file:
    player_ODI_data = json.load(file)

with open(Test_MDM_aggregate_points, "r") as file:
    player_Test_data = json.load(file)


@app.post("/aggregate_stats")
def get_player_stats(request_data: dict):
    # Extract data from request body
    Players = request_data.get('Players')
    Format = request_data.get('Format')

    # Validation
    if not Players:
        raise HTTPException(status_code=400, detail="Player name is required")
    if not Format:
        raise HTTPException(status_code=400, detail="Format is required")

    player_names = Players
    format = Format.upper()

    stats = {}
    for player_name in player_names:
        stats[player_name] = {}
        stats[player_name][format] = "Not available"

        # Check if the player name is valid
        if player_name:
            # Check if the player exists in the data
            player_stats = []
            if format == "ODI":
                player_stats = player_ODI_data.get(player_name)
            elif format == "T20":
                player_stats = player_T20_data.get(player_name)
            elif format == "TEST":
                player_stats = player_Test_data.get(player_name)
            else:
                raise HTTPException(status_code=400, detail="Invalid format. Must be ODI/T20/TEST")

            if player_stats is not None:
                stats[player_name] = player_stats
            # else remains "Not available"

    # Check if we got any valid stats
    has_valid_data = any(
        stats[player][format] != "Not available"
        for player in player_names
        if format in stats[player]
    )

    if not has_valid_data and player_names:
        raise HTTPException(status_code=404, detail="No data found for the specified players and format")

    # Process infinite values
    for player, player_stats in stats.items():
        if player_stats != "Not available" and isinstance(player_stats, dict):
            for key, value in player_stats.items():
                if value == float("inf"):
                    player_stats[key] = "Infinity"

    return stats


@app.post("/analyze_player")
def analyze_player(request_data: dict):
    # Extract data from request body
    best_team = request_data.get('best_team')
    Player = request_data.get('Player')
    format = request_data.get('format')

    # Validation
    if not best_team:
        raise HTTPException(status_code=400, detail="Best Team not found")
    if not Player:
        raise HTTPException(status_code=400, detail="Player name not found")
    if not format:
        raise HTTPException(status_code=400, detail="Please enter format as ODI/Test/T20")

    selected_players = best_team
    player_name = Player
    format_lower = format.lower()

    player_aggregate_stats = None
    if format_lower == "t20":
        player_aggregate_stats = player_T20_data.get(player_name, {})
    elif format_lower == "odi":
        player_aggregate_stats = player_ODI_data.get(player_name, {})
    elif format_lower == "test":
        player_aggregate_stats = player_Test_data.get(player_name, {})
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Must be ODI/Test/T20")

    if not player_aggregate_stats:
        raise HTTPException(status_code=400, detail=f"No aggregate statistics found for {player_name}")

    selection_status = "selected" if player_name in selected_players else "not selected"

    prompt = f"""
Based on the following statistics, explain why {player_name} was {selection_status} for the optimal fantasy cricket team:

Key Aggregate Statistics:
Batting Statistics:
- Batting Style: {player_aggregate_stats.get('Batting', 'N/A')}
- Total Runs: {player_aggregate_stats.get('Runs', 'N/A')}
- Batting Average: {player_aggregate_stats.get('Batting Avg', 'N/A')}
- Strike Rate: {player_aggregate_stats.get('Batting S/R', 'N/A')}
- Boundary Percentage: {player_aggregate_stats.get('Boundary %', 'N/A')}
- Mean Score: {player_aggregate_stats.get('Mean Score', 'N/A')}
- Dismissal Rate: {player_aggregate_stats.get('Dismissal Rate', 'N/A')}

Bowling Statistics:
- Bowling Style: {player_aggregate_stats.get('Bowling', 'N/A')}
- Wickets: {player_aggregate_stats.get('Wickets', 'N/A')}
- Economy Rate: {player_aggregate_stats.get('Economy Rate', 'N/A')}
- Bowling Average: {player_aggregate_stats.get('Bowling Avg', 'N/A')}
- Bowling Strike Rate: {player_aggregate_stats.get('Bowling S/R', 'N/A')}
- Dot Ball Bowled %: {player_aggregate_stats.get('Dot Ball Bowled %', 'N/A')}
- Boundary Given %: {player_aggregate_stats.get('Boundary Given %', 'N/A')}

Fielding Statistics:
- Catches: {player_aggregate_stats.get('Catches', 'N/A')}
- Runouts: {player_aggregate_stats.get('Runouts', 'N/A')}
- Stumpings: {player_aggregate_stats.get('Stumpings', 'N/A')}

A negative value for an aggregate statistic means that value does not exist and is not be to considered in the analysis.

Please provide a concise and brief analysis of why this player was {selection_status}, considering only their overall cricket statistics. Output the best statistics of the player. Be crisp.
"""

    analysis = call_llm(prompt)
    return {"analysis": analysis}



@app.post("/analyze_team")
def analyze_team(request_data: dict):
    # Extract data from request body
    best_team = request_data.get('best_team')
    player_stats = request_data.get('player_stats')
    format = request_data.get('format')

    # Validation
    if not best_team:
        raise HTTPException(status_code=400, detail="Best Team not found")
    if not player_stats:
        raise HTTPException(status_code=400, detail="Player Stats not loaded correctly")
    if not format:
        raise HTTPException(status_code=400, detail="Please enter format as ODI/Test/T20")

    selected_players = best_team
    stats_df_json = player_stats
    stats_df = pd.DataFrame(json.loads(stats_df_json))
    format_lower = format.lower()

    aggregate_stats = None
    if format_lower == "t20":
        aggregate_stats = player_T20_data
    elif format_lower == "odi":
        aggregate_stats = player_ODI_data
    elif format_lower == "test":
        aggregate_stats = player_Test_data
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Must be ODI/Test/T20")

    team_stats = []
    for player in selected_players:
        player_fantasy_stats = stats_df[stats_df['player'] == player].to_dict('records')[0]
        player_aggregate_stats = aggregate_stats.get(player, {})

        # Create player stat summary
        player_summary = {
            'name': player,
            'batting_style': player_aggregate_stats.get('Batting', 'N/A'),
            'bowling_style': player_aggregate_stats.get('Bowling', 'N/A'),
            'mean_fantasy_points': player_fantasy_stats.get('mean_points', 'N/A'),
            'batting_stats': {
                'average': player_aggregate_stats.get('Batting Avg', 'N/A'),
                'strike_rate': player_aggregate_stats.get('Batting S/R', 'N/A'),
                'consistency': player_aggregate_stats.get('Scoring Consistency', 'N/A'),
                'runs': player_aggregate_stats.get('Runs', 'N/A')
            },
            'bowling_stats': {
                'wickets': player_aggregate_stats.get('Wickets', 'N/A'),
                'economy': player_aggregate_stats.get('Economy Rate', 'N/A'),
                'average': player_aggregate_stats.get('Bowling Avg', 'N/A'),
                'strike_rate': player_aggregate_stats.get('Bowling S/R', 'N/A')
            },
            'fielding_stats': {
                'catches': player_aggregate_stats.get('Catches', 'N/A'),
                'runouts': player_aggregate_stats.get('Runouts', 'N/A'),
                'stumpings': player_aggregate_stats.get('Stumpings', 'N/A')
            },
            'overall_stats': {
                'games': player_aggregate_stats.get('Games', 'N/A'),
                'win_percentage': player_aggregate_stats.get('Win %', 'N/A')
            }
        }
        team_stats.append(player_summary)

    # Calculate team aggregate statistics
    team_summary = {
        'total_mean_points': sum(p.get('mean_fantasy_points', 0) for p in team_stats),
        'batting_styles': [p['batting_style'] for p in team_stats],
        'bowling_styles': [p['bowling_style'] for p in team_stats if p['bowling_style'] != 'N/A'],
        'avg_win_percentage': sum(float(p['overall_stats']['win_percentage']) for p in team_stats if p['overall_stats']['win_percentage'] != 'N/A') / len(team_stats),
        'total_experience': sum(int(p['overall_stats']['games']) for p in team_stats if p['overall_stats']['games'] != 'N/A')
    }

    # Create prompt for LLM
    prompt = f"""
        As a cricket analytics expert, provide a detailed analysis of why this team selection represents the optimal combination of players. Here's the team composition and their statistics:

        Team Overview:
        - Total Mean Fantasy Points: {team_summary['total_mean_points']:.2f}
        - Average Win Percentage: {team_summary['avg_win_percentage']:.2f}%
        - Total Combined Experience: {team_summary['total_experience']} matches
        - Batting Styles Distribution: {', '.join(str(team_summary['batting_styles']))}
        - Bowling Styles Distribution: {', '.join(str(team_summary['bowling_styles']))}

        Detailed Player Analysis:

        """

    # Add individual player details to prompt
    for player in team_stats:
        prompt += f"""
            {player['name']}:
            - Fantasy Points: {player['mean_fantasy_points']}
            - Role: {player['bowling_style']} bowler, {player['batting_style']} batsman
            - Batting: Avg {player['batting_stats']['average']}, SR {player['batting_stats']['strike_rate']}, Consistency {player['batting_stats']['consistency']}
            - Bowling: {player['bowling_stats']['wickets']} wickets, Econ {player['bowling_stats']['economy']}, Avg {player['bowling_stats']['average']}
            - Fielding: {player['fielding_stats']['catches']} catches, {player['fielding_stats']['runouts']} runouts
            - Experience: {player['overall_stats']['games']} games, {player['overall_stats']['win_percentage']}% wins
            """

    prompt += """
        Please provide a comprehensive analysis of this team selection, addressing:
        1. Overall team balance and composition
        2. Batting lineup strength and depth
        3. Bowling attack variety and effectiveness
        4. Fielding capabilities
        5. Experience and win-rate contribution
        6. Key player roles and their specific importance
        7. How the players complement each other
        8. Any potential weaknesses or risks
        9. Why this combination maximizes fantasy points while maintaining team balance

        Focus on why this specific combination of players forms the optimal team, considering both individual strengths and team synergy."""

    analysis = call_llm(prompt)
    return {"team analysis": analysis}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=3002)