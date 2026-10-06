#!/usr/bin/env python
# coding: utf-8

# In[1]:


csv_file_path = '../data/raw/T20_IT20_data.csv'
json_file_path = '../data/interim/T20_IT20_data.json'


# In[2]:


import pandas as pd
import json


# Load the data
data = pd.read_csv(csv_file_path)

# Initialize an empty dictionary to store the final JSON structure
json_data = {}

# Iterate over each row to populate the JSON structure
for _, row in data.iterrows():
    player_name = row['Player']  # Assuming 'Player' column has the player's name
    match_id = row['MatchID']
    innings_type = row.get("Innings Type", "")
    
    # Initialize the player structure if it does not exist
    if player_name not in json_data:
        json_data[player_name] = {}
    
    # Initialize the match structure if it does not exist for the player
    if match_id not in json_data[player_name]:
        json_data[player_name][match_id] = {
            "Team Name": row.get("Team", None),
            "Batting Innings": 0,
            "Bowling Innings": 0,
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
            "Catches Taken": 0,  # To be incremented if found
            "Stumped Outs Made": 0,  # To be incremented if found
            "Run Outs Made": 0,  # To be incremented if found  
            "Match Date": row.get("Date", None),
            "Match ID": match_id,
            "Match Type": row.get("Match Type", "ODI"),
            "Venue": row.get("Venue", None),
            "Event": row.get("Event", None),
            "Match Winner": "Not Available" if pd.isna(row.get("Match Winner")) else row.get("Match Winner"),
            "Balls Faced": 0 if pd.isna(row.get("Balls Faced")) else row.get("Balls Faced"),
            "Avg Balls Faced Per Inning": 0,
            "Avg Batting S/R Per Inning": 0,
            "Avg Runs/Ball Per Inning": 0,
            "Overs Bowled": 0,
            "Bowls Bowled": 0 if pd.isna(row.get("Balls Bowled")) else row.get("Balls Bowled"),
            "Average Bowls Bowled Per Inning": 0,
            "Avg Economy Rate per inning": 0,
            "Bowling Average": 0,
            "Average Consecutive Dot Balls": 0 if pd.isna(row.get("Avg Consecutive Dot Balls")) else row.get("Avg Consecutive Dot Balls"),
            "Maiden Overs": 0 if pd.isna(row.get("Maiden Overs")) else row.get("Maiden Overs"),
            "Avg Bowling S/R Per Inning": 0,
            "Runs Given": 0 if pd.isna(row.get("Runsgiven")) else row.get("Runsgiven"),
            "RunsGiven/Ball Per Inning": 0,
            "Batting S/R AA(Above Average)": 0,
            "How Out Inning 1 (Not Played)": 1,
            "How Out Inning 1 (caught)": 0,
            "How Out Inning 1 (not out)": 0,
            "How Out Inning 1 (lbw)": 0,
            "How Out Inning 1 (bowled)": 0,
            "How Out Inning 1 (Run Out)": 0,
            "How Out Inning 1 (caught and bowled)": 0,
            "How Out Inning 1 (stumped)": 0,
            "How Out Inning 1 (hit wicket)": 0,
            "How Out Inning 2 (Not Played)": 1,
            "How Out Inning 2 (caught)": 0,
            "How Out Inning 2 (not out)": 0,
            "How Out Inning 2 (lbw)": 0,
            "How Out Inning 2 (bowled)": 0,
            "How Out Inning 2 (Run Out)": 0,
            "How Out Inning 2 (caught and bowled)": 0,
            "How Out Inning 2 (stumped)": 0,
            "How Out Inning 2 (hit wicket)": 0,
            "How Out Inning 3 (Not Played)": 1,
            "How Out Inning 3 (caught)": 0,
            "How Out Inning 3 (not out)": 0,
            "How Out Inning 3 (lbw)": 0,
            "How Out Inning 3 (bowled)": 0,
            "How Out Inning 3 (Run Out)": 0,
            "How Out Inning 3 (caught and bowled)": 0,
            "How Out Inning 3 (stumped)": 0,
            "How Out Inning 3 (hit wicket)": 0,
            "How Out Inning 4 (Not Played)": 1,
            "How Out Inning 4 (caught)": 0,
            "How Out Inning 4 (not out)": 0,
            "How Out Inning 4 (lbw)": 0,
            "How Out Inning 4 (bowled)": 0,
            "How Out Inning 4 (Run Out)": 0,
            "How Out Inning 4 (caught and bowled)": 0,
            "How Out Inning 4 (stumped)": 0,
            "How Out Inning 4 (hit wicket)": 0,
            
        }
    else:
        # If the entry already exists, aggregate stats by adding new values to existing ones
        json_data[player_name][match_id]["Total Runs Scored"] += 0 if pd.isna(row.get("Score")) else row.get("Score")
        json_data[player_name][match_id]["Boundaries"] += (0 if pd.isna(row.get("Fours")) else row.get("Fours")) + (0 if pd.isna(row.get("Sixes")) else row.get("Sixes"))
        json_data[player_name][match_id]["Sixes"] += 0 if pd.isna(row.get("Sixes")) else row.get("Sixes")
        json_data[player_name][match_id]["Fours"] += 0 if pd.isna(row.get("Fours")) else row.get("Fours")
        json_data[player_name][match_id]["Balls Faced"] += 0 if pd.isna(row.get("Balls Faced")) else row.get("Balls Faced")
        json_data[player_name][match_id]["Wickets"] += 0 if pd.isna(row.get("Wickets")) else row.get("Wickets")
        json_data[player_name][match_id]["Bowled"] += 0 if pd.isna(row.get("Bowled")) else row.get("Bowled")
        json_data[player_name][match_id]["LBW"] += 0 if pd.isna(row.get("LBW")) else row.get("LBW")
        json_data[player_name][match_id]["Bowls Bowled"] += 0 if pd.isna(row.get("Balls Bowled")) else row.get("Balls Bowled")
        json_data[player_name][match_id]["Runs Given"] += 0 if pd.isna(row.get("Runsgiven")) else row.get("Runsgiven")
        json_data[player_name][match_id]["Average Consecutive Dot Balls"] += 0 if pd.isna(row.get("Avg Consecutive Dot Balls")) else row.get("Avg Consecutive Dot Balls")
        json_data[player_name][match_id]["Maiden Overs"] += 0 if pd.isna(row.get("Maiden Overs")) else row.get("Maiden Overs")
        
       
    

    
    # Increment the count based on the "Innings Type"
    if innings_type == "Batting":
        json_data[player_name][match_id]["Batting Innings"] += 1
    elif innings_type == "Bowling":
        json_data[player_name][match_id]["Bowling Innings"] += 1

# Calculate averages and derived statistics
for player in json_data:
    for match_id, stats in json_data[player].items():
        # Batting calculations
        batting_innings = stats["Batting Innings"]
        if batting_innings > 0:
            stats["Avg Runs Per Inning"] = stats["Total Runs Scored"] / batting_innings
            stats["Average Sixes Per Inning"] = stats["Sixes"] / batting_innings
            stats["Average Fours Per Inning"] = stats["Fours"] / batting_innings
            stats["Boundary% Per Inning"] = (stats["Boundaries"] * 100) / (stats["Balls Faced"] * batting_innings) if stats["Balls Faced"] > 0 else 0
            stats["Boundary Rate Per Inning"] = stats["Balls Faced"] / (stats["Boundaries"] * batting_innings) if stats["Boundaries"] > 0 else float('inf')
            stats["Avg Balls Faced Per Inning"] = stats["Balls Faced"] / batting_innings
            stats["Avg Batting S/R Per Inning"] = (stats["Total Runs Scored"] * 100) / (stats["Balls Faced"] * batting_innings) if stats["Balls Faced"] > 0 else 0
            stats["Avg Runs/Ball Per Inning"] = stats["Total Runs Scored"] / (stats["Balls Faced"] * batting_innings) if stats["Balls Faced"] > 0 else 0

        # Bowling calculations
        bowling_innings = stats["Bowling Innings"]
        if bowling_innings > 0:
            stats["Avg Wickets Per Inning"] = stats["Wickets"] / bowling_innings
            stats["Average Bowls Bowled Per Inning"] = stats["Bowls Bowled"] / bowling_innings
            stats["Overs Bowled"] = stats["Bowls Bowled"] / 6
            stats["Avg Economy Rate per inning"] = stats["Runs Given"] / (stats["Overs Bowled"] * bowling_innings) if stats["Overs Bowled"] > 0 else 0
            stats["Bowling Average"] = stats["Runs Given"] / (stats["Wickets"] * bowling_innings) if stats["Wickets"] > 0 else float('inf')
            stats["Avg Bowling S/R Per Inning"] = stats["Bowls Bowled"] / (stats["Wickets"] * bowling_innings) if stats["Wickets"] > 0 else float('inf')
            stats["RunsGiven/Ball Per Inning"] = stats["Runs Given"] / (stats["Bowls Bowled"] * bowling_innings) if stats["Bowls Bowled"] > 0 else 0
            stats["Average Consecutive Dot Balls"] = stats["Average Consecutive Dot Balls"]/bowling_innings


# Second pass: Update fielding stats based on "How Out" and "Fielder"
for _, row in data.iterrows():
    fielder_name = row.get("Fielder", "")
    match_id = row['MatchID']
    dismissal_type = row.get("How Out", "")

     # Check if fielder and dismissal_type are valid
    if fielder_name and isinstance(dismissal_type, str):
        # Ensure fielder exists in json_data
        if fielder_name in json_data and match_id in json_data[fielder_name]:
            if "caught" in dismissal_type.lower():
                json_data[fielder_name][match_id]["Catches Taken"] += 1
            elif "stumped" in dismissal_type.lower():
                json_data[fielder_name][match_id]["Stumped Outs Made"] += 1
            elif "run out" in dismissal_type.lower():
                json_data[fielder_name][match_id]["Run Outs Made"] += 1


# In[3]:


## Batting S/R ABOVE AVERAGE


# In[4]:


# data = json_data
# Create a dictionary to hold the match-wise Batting S/R
match_sr = {}

# Collect Batting S/R for each match ID
for player, matches in json_data.items():
    for match_id, stats in matches.items():
        if match_id not in match_sr:
            match_sr[match_id] = []
        match_sr[match_id].append(stats["Avg Batting S/R Per Inning"])

# Calculate mean Batting S/R for each match ID
match_avg_sr = {match_id: sum(sr_list) / len(sr_list) for match_id, sr_list in match_sr.items()}

# Add "Batting S/R Above Average" to the data
for player, matches in json_data.items():
    for match_id, stats in matches.items():
        match_id = str(match_id)
        avg_sr = match_avg_sr[match_id]
        stats["Batting S/R AA(Above Average)"] = stats["Avg Batting S/R Per Inning"] - avg_sr


# In[5]:


# Define the encoding mapping for "how out"
how_out_mapping = {
    "Not Played": 0,
    "caught": 1,
    "not out": 2,
    "lbw": 3,
    "bowled": 4,
    "Run Out": 5,
    "caught and bowled": 6,
    "stumped": 7,
    "hit wicket": 8
}

# Initialize one-hot encoding structure
def one_hot_encode_how_out(how_out):
    # Initialize a dictionary with all categories set to 0
    one_hot = {key: 0 for key in how_out_mapping.keys()}
    if how_out in how_out_mapping:  # Ensure valid category
        one_hot[how_out] = 1
    return one_hot

# Add one-hot encoding for 'how out' while considering the innings column
for _, row in data.iterrows():
    player_name = row['Player']
    match_id = row['MatchID']
    innings_type = row.get("Innings Type", "")
    innings_number = row.get("Innings", 1)  # Default to 1 if not available
    how_out = row.get("How Out", "Not Played")

    # Determine the inning (first or second) for batting
    if innings_type == "Batting":
        if(how_out!="Not Played"):
             json_data[player_name][match_id][f"How Out Inning {innings_number} (Not Played)"] = 0
        one_hot_encoded = one_hot_encode_how_out(how_out)
        json_data[player_name][match_id].update({f"How Out Inning {innings_number} ({key})": value for key, value in one_hot_encoded.items()})
      
# Save the updated JSON
json_output = json.dumps(json_data, indent=4)
with open(json_file_path, 'w') as json_file:
    json_file.write(json_output)


# In[6]:


## FOR TEST , innings wise update


# In[7]:


import json
import pandas as pd
import csv

# File paths
data = pd.read_csv(csv_file_path)
# Load the JSON data
with open(json_file_path, 'r') as json_file:
    player_data = json.load(json_file)

# Add new stats to the JSON data
for player, matches in player_data.items():
    for match_id, stats in matches.items():
        stats["Innings 1 Runs"] = 0
        stats["Innings 2 Runs"] = 0
        stats["Innings 1 Wickets"] = 0
        stats["Innings 2 Wickets"] = 0
        stats["Innings 3 Runs"] = 0
        stats["Innings 4 Runs"] = 0
        stats["Innings 3 Wickets"] = 0
        stats["Innings 4 Wickets"] = 0
        stats["Innings 1 Balls Faced"] = 0
        stats["Innings 2 Balls Faced"] = 0
        stats["Innings 3 Balls Faced"] = 0
        stats["Innings 4 Balls Faced"] = 0



# Update JSON data based on the CSV file
for _, row in data.iterrows():
    match_id = row["MatchID"]
    player_name = row["Player"]
    innings_no = int(row["Innings"]) 
    innings_type = row.get("Innings Type", "")
    runs = 0 if pd.isna(row.get("Score")) else row.get("Score")
    wickets = 0 if pd.isna(row.get("Wickets")) else row.get("Wickets")
    balls_faced= 0 if pd.isna(row.get("Balls Faced")) else row.get("Balls Faced")
    if player_name in player_data and match_id in player_data[player_name]:
        if innings_no == 1:
            player_data[player_name][match_id]["Innings 1 Runs"] += runs
            player_data[player_name][match_id]["Innings 1 Wickets"] += wickets
            player_data[player_name][match_id]["Innings 1 Balls Faced"] += balls_faced
        elif innings_no == 2:
            player_data[player_name][match_id]["Innings 2 Runs"] += runs
            player_data[player_name][match_id]["Innings 2 Wickets"] += wickets
            player_data[player_name][match_id]["Innings 2 Balls Faced"] += balls_faced
        elif innings_no == 3:
            player_data[player_name][match_id]["Innings 3 Runs"] += runs
            player_data[player_name][match_id]["Innings 3 Wickets"] += wickets
            player_data[player_name][match_id]["Innings 3 Balls Faced"] += balls_faced
        elif innings_no == 4:
            player_data[player_name][match_id]["Innings 4 Runs"] += runs
            player_data[player_name][match_id]["Innings 4 Wickets"] += wickets
            player_data[player_name][match_id]["Innings 4 Balls Faced"] += balls_faced

# Save updated JSON data back to the file
with open(json_file_path, 'w') as json_file:
    json.dump(player_data, json_file, indent=4)

print("JSON file updated successfully.")


# In[ ]:




