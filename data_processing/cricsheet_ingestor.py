import sys
import os
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

# Add paths to sys for legacy modules
BASE_DIR = Path(__file__).resolve().parent.parent
PREPROC_DIR = BASE_DIR / "data_preprocessing"
if str(PREPROC_DIR) not in sys.path:
    sys.path.insert(0, str(PREPROC_DIR))
    sys.path.insert(0, str(BASE_DIR / "model"))

import cricketstats as cks
from Data_Extracter import data_extracter
from Aggregate_Points import aggregate_points_json
from Testing import process_match_data

def format_csv_to_json(csv_path, json_out_path):
    print(f"Formatting {csv_path} to JSON...")
    if not os.path.exists(csv_path):
        print(f"Skip: {csv_path} not found.")
        return
        
    data = pd.read_csv(csv_path)
    json_data = {}

    for _, row in data.iterrows():
        player_name = row['Player']
        match_id = row['MatchID']
        
        if player_name not in json_data:
            json_data[player_name] = {}
        
        if match_id not in json_data[player_name]:
            json_data[player_name][match_id] = {
                "Team Name": row.get("Team", None),
                "Batting Innings": 0, "Bowling Innings": 0,
                "Total Runs Scored": 0 if pd.isna(row.get("Score")) else row.get("Score"),
                "Avg Runs Per Inning": 0,
                "Boundaries": (0 if pd.isna(row.get("Fours")) else row.get("Fours")) + (0 if pd.isna(row.get("Sixes")) else row.get("Sixes")),
                "Sixes": 0 if pd.isna(row.get("Sixes")) else row.get("Sixes"),
                "Average Sixes Per Inning": 0,
                "Fours": 0 if pd.isna(row.get("Fours")) else row.get("Fours"),
                "Average Fours Per Inning": 0,
                "Boundary% Per Inning": 0,
                "Boundary Rate Per Inning": 0,
                "Wickets": 0 if pd.isna(row.get("Wickets")) else row.get("Wickets"),
                "Bowled": 0 if pd.isna(row.get("Bowled")) else row.get("Bowled"),
                "LBW": 0 if pd.isna(row.get("LBW")) else row.get("LBW"),
                "Avg Wickets Per Inning": 0,
                "Opposition Team": row.get("Opposition", None),
                "Catches Taken": 0, "Stumped Outs Made": 0, "Run Outs Made": 0,  
                "Match Date": row.get("Date", None),
                "Match ID": match_id,
                "Match Type": row.get("Match Type", "ODI"),
                "Venue": row.get("Venue", None),
                "Overs Bowled": 0 if pd.isna(row.get("Overs")) else row.get("Overs"),
                "Runs Given": 0 if pd.isna(row.get("Runs")) else row.get("Runs"),
                "Maidens": 0 if pd.isna(row.get("Maidens")) else row.get("Maidens"),
                "Bowls Bowled": 0, "Bowling Average": 0, "Avg Bowling S/R Per Inning": 0,
                "RunsGiven/Ball Per Inning": 0, "Average Consecutive Dot Balls": 0,
                "Average Bowls Bowled Per Inning": 0, "Avg Economy Rate per inning": 0,
                "Dot Balls": 0 if pd.isna(row.get("Dots")) else row.get("Dots"),
                "Balls Faced": 0 if pd.isna(row.get("Balls")) else row.get("Balls"),
                "Avg Balls Faced Per Inning": 0, "Avg Batting S/R Per Inning": 0,
                "Avg Runs/Ball Per Inning": 0,
                "How Out": row.get("How Out", None),
                "Fielder": row.get("Fielder", None)
            }
            
        # Specific updates based on Innings Type
        innings_type = row.get("Innings Type", "")
        if pd.notna(innings_type):
            if "Batting" in innings_type:
                json_data[player_name][match_id]["Batting Innings"] += 1
            if "Bowling" in innings_type:
                json_data[player_name][match_id]["Bowling Innings"] += 1

    # Derived Stats
    for player in json_data:
        for match_id, stats in json_data[player].items():
            b_inns = stats["Batting Innings"]
            if b_inns > 0:
                stats["Avg Runs Per Inning"] = stats["Total Runs Scored"] / b_inns
                stats["Average Sixes Per Inning"] = stats["Sixes"] / b_inns
                stats["Average Fours Per Inning"] = stats["Fours"] / b_inns
                stats["Boundary% Per Inning"] = (stats["Boundaries"] * 100) / (stats["Balls Faced"] * b_inns) if stats["Balls Faced"] > 0 else 0
                stats["Avg Batting S/R Per Inning"] = (stats["Total Runs Scored"] * 100) / (stats["Balls Faced"] * b_inns) if stats["Balls Faced"] > 0 else 0
            
            bow_inns = stats["Bowling Innings"]
            if bow_inns > 0:
                stats["Avg Wickets Per Inning"] = stats["Wickets"] / bow_inns
                stats["Avg Economy Rate per inning"] = stats["Runs Given"] / (stats["Overs Bowled"] * bow_inns) if stats["Overs Bowled"] > 0 else 0

    # Fielding stats
    for _, row in data.iterrows():
        fielder = row.get("Fielder", "")
        match_id = row['MatchID']
        how_out = str(row.get("How Out", ""))
        if fielder and fielder in json_data and match_id in json_data[fielder]:
            if "caught" in how_out.lower():
                json_data[fielder][match_id]["Catches Taken"] += 1
            elif "stumped" in how_out.lower():
                json_data[fielder][match_id]["Stumped Outs Made"] += 1
            elif "run out" in how_out.lower():
                json_data[fielder][match_id]["Run Outs Made"] += 1

    with open(json_out_path, 'w') as f:
        json.dump(json_data, f)
    print(f"Saved {json_out_path}")

def run_pipeline():
    today = datetime.today()
    from_date = (2010, 1, 1)
    to_date = (today.year, today.month, today.day)
    
    formats = [
        (["T20", "IT20"], "T20_IT20_data"),
        (["ODI", "ODM"], "ODI_ODM_data"),
        (["Test", "MDM"], "Test_MDM_data")
    ]
    
    for matchtype, prefix in formats:
        print(f"\n--- Extracting {prefix} ---")
        try:
            # Dynamically set database to format-specific zip
            zip_name = "t20s_json.zip" if "T20" in prefix else "odis_json.zip" if "ODI" in prefix else "tests_json.zip"
            zip_path = str(BASE_DIR / "data" / "raw" / zip_name)
            
            import Data_Extracter
            Data_Extracter.database = zip_path
            import Aggregate_Points
            Aggregate_Points.database = zip_path
            
            import os
            print(f"Setting database to {zip_path}, exists: {os.path.exists(zip_path)}")
            
            data_extracter(matchtype, from_date, to_date)
            aggregate_points_json(matchtype, from_date, to_date)
            
            csv_in = str(BASE_DIR / "data" / "raw" / f"{prefix}.csv")
            json_interim = str(BASE_DIR / "data" / "interim" / f"{prefix}.json")
            agg_in = str(BASE_DIR / "data" / "processed" / f"{prefix}_aggregate_data.json")
            
            format_csv_to_json(csv_in, json_interim)
            
            # Map legacy prefix to model expected suffixes
            if "T20" in prefix: out_name = "player_fantasy_points_t20.json"
            elif "ODI" in prefix: out_name = "player_fantasy_points_odi.json"
            else: out_name = "player_fantasy_points_test.json"
            
            out_path = str(BASE_DIR / "data" / "processed" / out_name)
            
            print(f"Calculating Fantasy Points for {prefix}...")
            process_match_data(json_interim, agg_in, out_path)
            
        except Exception as e:
            print(f"Error processing {prefix}: {e}")

if __name__ == "__main__":
    run_pipeline()
