#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import csv
import json


# In[2]:


ODI_ODM_data = pd.read_csv("../data/raw/ODI_ODM_data.csv")
Test_MDM_data = pd.read_csv("../data/raw/Test_MDM_data.csv")
T20_data = pd.read_csv("../data/raw/T20_IT20_data.csv")
csv_file_path = '../data/interim/combined_data.csv'  # Replace with your CSV file path
combined_squad_path = '../data/processed/combined_squad.json'
datewise_squad_path = '../data/processed/datewise_squad.json'


# In[3]:


# combined data already saved 


# In[4]:


# combined_data = pd.concat([ODI_ODM_data,Test_MDM_data,T20_data], axis=0, ignore_index=True)


# In[5]:


# combined_data.to_csv(csv_file_path)


# In[6]:


##FOR Model UI


# In[3]:


# Initialize an empty dictionary to store the data
data = {}
combined_data = pd.read_csv(csv_file_path)
# Read the CSV file
for _, row in combined_data.iterrows():
    match_id = row['MatchID']
    team = row['Team']
    opposition_team_name = row['Opposition']
    player = row['Player']
    fielder = row['Fielder']
    inning_type = row["Innings Type"]
    # Initialize the structure for the date and event if not already in data
    if match_id not in data:
        data[match_id] = {}
        
    if team not in data[match_id]:
        data[match_id][team] = []
    if opposition_team_name not in data[match_id]:
        data[match_id][opposition_team_name] = []
     

    # Add the player to the respective team list only
    if player not in data[match_id][team]:
        data[match_id][team].append(player)

    # Add the fielder to the opposition team as a player, if not already present
    if inning_type=="Batting" and not pd.isna(fielder) and fielder not in data[match_id][opposition_team_name]:
        data[match_id][opposition_team_name].append(fielder)
    # Add the fielder to the opposition team as a player, if not already present
    if inning_type=="Bowling" and not pd.isna(fielder) and fielder not in data[match_id][team]:
        data[match_id][team].append(fielder)


        

# Convert the dictionary to JSON and print/save to file
json_output = json.dumps(data, indent=4)

# Alternatively, save the JSON to a file
with open(combined_squad_path, 'w') as outfile:
    outfile.write(json_output)


# In[8]:


## FOR FRONTEND


# In[9]:


##without second squad generation


# In[10]:


# import csv
# import json

# # Initialize an empty dictionary to store the data
# data = {}

# # Read the CSV file
# csv_file_path = '/Users/ayush_arya/Downloads/Inter_IIT_Tech_13/dream11-inter-iit/data/Match_Level_players/combined_data.csv'  # Replace with your CSV file path
# with open(csv_file_path, 'r') as csvfile:
#     reader = csv.DictReader(csvfile)
    
#     for row in reader:
#         date = row['Date']
#         event = row['Event']
#         match_id = row['MatchID']
#         team = row['Team']
#         opposition_team_name = row['Opposition']
#         venue = row['Venue']
#         player = row['Player']
#         fielder = row['Fielder']  # Add fielder from the row
#         match_type = row["Match Type"]

#         # Create the key in the format "Team_VS_OppositionTeamName_Venue"
#         key = f"{team}_VS_{opposition_team_name}_{venue}"
#         swapped_key = f"{opposition_team_name}_VS_{team}_{venue}"

#         # Initialize the structure for the date and event if not already in data
#         if date not in data:
#             data[date] = {}
        
#         if event not in data[date]:
#             data[date][event] = {}
        
#         # Check if swapped key already exists, otherwise use the original key
#         if swapped_key in data[date][event]:
#             key = swapped_key  # If swapped key exists, use it
#         elif key not in data[date][event]:
#             # If neither key exists, create the key using the original key
#             data[date][event][key] = {}
            
            
#         data[date][event][key]['Venue'] = venue
#         if match_type in ["MDM", "Test"]:
#             data[date][event][key]['Format'] =  "Test"
#         elif match_type in ["ODM", "ODI"]:
#             data[date][event][key]['Format'] =  "ODI"
#         elif match_type == "T20":
#             data[date][event][key]['Format'] =  "T20"
            
            

#         # Use f-strings for the team keys
#         team_key = f"{team}"
#         opposition_team_key = f"{opposition_team_name}"

#         # Initialize the team and opposition team arrays if they don't exist
#         if team_key not in data[date][event][key]:
#             data[date][event][key][team_key] = []
#         if opposition_team_key not in data[date][event][key]:
#             data[date][event][key][opposition_team_key] = []

#         # Add the player to the respective team list only
#         if player not in data[date][event][key][team_key]:
#             data[date][event][key][team_key].append(player)

#         # Add the fielder to the opposition team as a player, if not already present
#         if fielder and fielder not in data[date][event][key][opposition_team_key]:
#             data[date][event][key][opposition_team_key].append(fielder)

# # Convert the dictionary to JSON and print/save to file
# json_output = json.dumps(data, indent=4)

# # Alternatively, save the JSON to a file
# with open('/Users/ayush_arya/Downloads/Inter_IIT_Tech_13/dream11-inter-iit/data/Match_Level_players/Final_datewise_squad.json', 'w') as outfile:
#     outfile.write(json_output)


# In[11]:


#with second squad generation


# In[4]:


import csv
import json
from collections import defaultdict
from datetime import datetime
from tqdm import tqdm

# Function to Extract Gender from MatchID
def extract_gender_from_match_id(match_id):
    # Implement logic to extract gender from match_id
    # Adjust this according to your actual MatchID format
    match_id = match_id.lower()
    if "female" in match_id:
        return 'female'
    else:
        return 'male'

# Step 1: Read and Group CSV Data by MatchID
matches_dict = defaultdict(lambda: {
    'rows': [],
    'date': '',
    'event': '',
    'match_type': '',
    'gender': ''
})

with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        match_id = row['MatchID']
        # Extract gender from MatchID
        gender = extract_gender_from_match_id(match_id)
        matches_dict[match_id]['rows'].append(row)
        matches_dict[match_id]['date'] = row['Date']
        matches_dict[match_id]['event'] = row['Event']
        matches_dict[match_id]['match_type'] = row['Match Type']
        matches_dict[match_id]['gender'] = gender  # Store gender

# Step 2: Convert Grouped Data into a Sorted List of Matches
matches = []
for match_id, match_info in tqdm(matches_dict.items()):
    date_str = match_info['date']
    event = match_info['event']
    match_type = match_info['match_type']
    gender = match_info['gender']
    venue = match_info['rows'][0]['Venue']  # Assuming venue is the same for all rows in a match

    teams = set()
    for row in match_info['rows']:
        teams.add(row['Team'])
        teams.add(row['Opposition'])
    teams = list(teams)

    if len(teams) != 2:
        # Handle cases where teams are not properly identified
        continue

    team1, team2 = teams
    # Initialize player sets with gender information
    team1_players = set()
    team2_players = set()

    for row in match_info['rows']:
        team = row['Team']
        opposition = row['Opposition']
        player = row['Player']
        fielder = row['Fielder']
        inning_type = row['Innings Type']

        if team == team1:
            team1_players.add(player)
            if inning_type == "Batting" and fielder:
                team2_players.add(fielder)
            elif inning_type == "Bowling" and fielder:
                team1_players.add(fielder)
        elif team == team2:
            team2_players.add(player)
            if inning_type == "Batting" and fielder:
                team1_players.add(fielder)
            elif inning_type == "Bowling" and fielder:
                team2_players.add(fielder)

    match_entry = {
        'date': datetime.strptime(date_str, '%Y-%m-%d'),
        'event': event,
        'match_id': match_id,
        'match_type': match_type,
        'gender': gender,  # Include gender
        'venue': venue,
        'team1': team1,
        'team2': team2,
        'team1_players': list(team1_players),
        'team2_players': list(team2_players)
    }
    matches.append(match_entry)

# Step 3: Sort Matches Chronologically
matches.sort(key=lambda x: x['date'])

# Step 4: Initialize Data Structures for Tracking Past Squads
# Include gender in the data structure
team_past_matches = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # team_past_matches[team][match_type][gender] = list of squads

# Step 5: Process Each Match to Build JSON with Second Squads
data = defaultdict(lambda: defaultdict(dict))

for match in tqdm(matches):
    date_str = match['date'].strftime('%Y-%m-%d')
    event = match['event']
    match_type = match['match_type']
    gender = match['gender']
    venue = match['venue']
    team1 = match['team1']
    team2 = match['team2']
    squad1 = match['team1_players']
    squad2 = match['team2_players']

    # Create Match Keys
    key1 = f"{team1}_VS_{team2}_{venue}"
    key2 = f"{team2}_VS_{team1}_{venue}"

    # Determine the correct key based on existing data
    if key1 not in data[date_str][event]:
        key = key1
    else:
        key = key2

    if key not in data[date_str][event]:
        data[date_str][event][key] = {}

    if match_type in ["MDM", "Test"]:
        data[date_str][event][key]['Format'] = "Test"
    elif match_type in ["ODM", "ODI"]:
        data[date_str][event][key]['Format'] = "ODI"
    elif match_type == "T20":
        data[date_str][event][key]['Format'] = "T20"
    else:
        data[date_str][event][key]['Format'] = match_type  # Use match_type as is if it doesn't match known types

    # Assign Current Squads
    data[date_str][event][key][team1] = squad1
    data[date_str][event][key][team2] = squad2

    # Function to Generate Second Squad
    def generate_second_squad(team, current_squad, match_type, gender):
        past_squads = team_past_matches[team][match_type][gender][-10:]  # Get last 10 squads
        past_players = set()
        for past_squad in past_squads:
            past_players.update(past_squad)
        # Second squad is past players minus current squad
        second_squad = list(past_players - set(current_squad))
        return second_squad

    # Generate Second Squads for Both Teams
    second_squad1 = generate_second_squad(team1, squad1, match_type, gender)
    second_squad2 = generate_second_squad(team2, squad2, match_type, gender)

    data[date_str][event][key][f"{team1}_Second_Squad"] = second_squad1
    data[date_str][event][key][f"{team2}_Second_Squad"] = second_squad2

    # Update Past Matches with Current Squads
    team_past_matches[team1][match_type][gender].append(set(squad1))
    team_past_matches[team2][match_type][gender].append(set(squad2))

# Step 6: Convert to Regular Dictionary and Save JSON
# Convert defaultdicts to regular dicts for JSON serialization
def convert_defaultdict_to_dict(d):
    if isinstance(d, defaultdict):
        d = {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        d = [convert_defaultdict_to_dict(i) for i in d]
    elif isinstance(d, dict):
        d = {k: convert_defaultdict_to_dict(v) for k, v in d.items()}
    return d

final_data = convert_defaultdict_to_dict(data)

# Save to JSON file
with open(datewise_squad_path, 'w', encoding='utf-8') as outfile:
    json.dump(final_data, outfile, indent=4)


# In[ ]:




