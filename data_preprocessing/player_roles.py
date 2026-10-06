#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import os

# Load data
print("Loading interim data...")
# Check if the all_player_stats.csv exists in interim
interim_files = [f for f in os.listdir('../data/interim/') if 'stats' in f.lower() or f.endswith('.csv')]
if interim_files:
    stats_file = os.path.join('../data/interim/', interim_files[0])
    print(f"Found stats file: {stats_file}")
else:
    # If no stats file, try to create aggregated data from the JSON files
    print("Warning: No player stats CSV found in interim. Will need to process JSON data.")
    stats_file = None

print("Loading people data...")
people_path = '../data/interim/people.csv'
if os.path.exists(people_path):
    df_people = pd.read_csv(people_path)
else:
    # Try the people.csv in interim
    people_path = '../data/interim/people.csv'
    if os.path.exists(people_path):
        df_people = pd.read_csv(people_path)
    else:
        raise FileNotFoundError("people.csv not found in either raw/additional_data/ or interim/")

print("\nInterim data columns:")
if stats_file and os.path.exists(stats_file):
    df_stats = pd.read_csv(stats_file, encoding="latin1")
    print(df_stats.columns.tolist())
else:
    print("[No stats file loaded]")
print("\nPeople data columns:")
print(df_people.columns.tolist())

# Show first few rows of each
print("\nInterim data head:")
if stats_file and os.path.exists(stats_file):
    print(df_stats.head())
else:
    print("[No stats data]")
print("\nPeople data head:")
print(df_people.head())


# In[2]:


# Check if 'role' column exists in people.csv
if 'role' in df_people.columns:
    print("\n'role' column found in people.csv. Extracting directly.")
    role_from_people = df_people.set_index('name')['role'].to_dict()
else:
    print("\n'role' column NOT found in people.csv. Deriving from historical match stats.")
    role_from_people = {}

# Extract batting_style and bowling_style from people.csv if columns exist
batting_style_from_people = {}
bowling_style_from_people = {}

if 'batting_style' in df_people.columns:
    batting_style_from_people = df_people.set_index('name')['batting_style'].to_dict()
else:
    print("'batting_style' column not found in people.csv. Setting to 'Unknown' for all.")

if 'bowling_style' in df_people.columns:
    bowling_style_from_people = df_people.set_index('name')['bowling_style'].to_dict()
else:
    print("'bowling_style' column not found in people.csv. Setting to 'Unknown' for all.")

# Now derive role from stats if needed
if 'role' not in df_people.columns:
    print("\nDeriving role from historical stats...")
    if stats_file and os.path.exists(stats_file):
        # We need to know the column names for runs, wickets, stumpings
        # Let's assume common names, but we'll check what we have
        cols = df_stats.columns.tolist()
        # Try to find likely column names
        run_col = None
        wicket_col = None
        stump_col = None
        for col in cols:
            col_lower = col.lower()
            if 'run' in col_lower:
                run_col = col
            if 'wicket' in col_lower:
                wicket_col = col
            if 'stump' in col_lower:
                stump_col = col

        if not run_col or not wicket_col or not stump_col:
            print("Warning: Could not automatically detect runs/wickets/stumpings columns.")
            print("Using first three numeric columns as fallback.")
            # Get numeric columns
            numeric_cols = df_stats.select_dtypes(include=['number']).columns.tolist()
            if len(numeric_cols) >= 3:
                run_col = numeric_cols[0]
                wicket_col = numeric_cols[1]
                stump_col = numeric_cols[2]
            else:
                raise ValueError("Not enough numeric columns to derive roles")

        print(f"Using columns: runs='{run_col}', wickets='{wicket_col}', stumpings='{stump_col}'")

        # Aggregate per player
        player_agg = df_stats.groupby('player_name').agg(
            total_runs=(run_col, 'sum'),
            total_wickets=(wicket_col, 'sum'),
            total_stumpings=(stump_col, 'sum'),
            matches_played=(run_col, 'count')  # using runs column as proxy for presence
        ).reset_index()

        # Classify role based on user feedback
        def classify_role(row):
            # WK: at least 5 stumpings
            if row['total_stumpings'] >= 5:
                return 'WK'
            # BAT: matches > 200 AND runs >= 5000 AND wickets < 150
            elif row['matches_played'] > 200 and row['total_runs'] >= 5000 and row['total_wickets'] < 150:
                return 'BAT'
            # AR: matches > 200 AND runs > 4000 AND wickets > 200
            elif row['matches_played'] > 200 and row['total_runs'] > 4000 and row['total_wickets'] > 200:
                return 'AR'
            # BOWL: matches > 200 AND wickets > 200 AND runs < 2500
            elif row['matches_played'] > 200 and row['total_wickets'] > 200 and row['total_runs'] < 2500:
                return 'BOWL'
            else:
                return 'IDK'  # Unknown/Other

        player_agg['role'] = player_agg.apply(classify_role, axis=1)
        role_from_stats = player_agg.set_index('player_name')['role'].to_dict()
        print("Role derivation complete.")
    else:
        print("No stats data available for role derivation")
        role_from_stats = {}
else:
    role_from_stats = {}


# In[3]:


# Build player_roles dictionary
import difflib

# Get unique player names from the interim stats
if stats_file and os.path.exists(stats_file):
    player_names_stats = df_stats['player_name'].unique()
    print(f"\nLoaded {len(player_names_stats)} unique players from stats data")
else:
    print("\nWarning: No stats data available. Cannot build player roles from historical data.")
    # Try to get player names from people.csv as fallback
    player_names_stats = df_people['name'].unique() if 'name' in df_people.columns else []
    print(f"Using {len(player_names_stats)} player names from people.csv as fallback")

# Get player names from people.csv
if 'name' in df_people.columns:
    player_names_people = df_people['name'].unique()
else:
    print("Warning: 'name' column not found in people.csv. Cannot match players.")
    player_names_people = []

# We'll create a dictionary for the final result
player_roles = {}

print(f"\nMatching {len(player_names_stats)} players from stats data to {len(player_names_people)} people.")

matched_count = 0
for name in player_names_stats:
    # Try exact match first
    if 'name' in df_people.columns:
        exact_match = df_people[df_people['name'] == name]
        if not exact_match.empty:
            person = exact_match.iloc[0]
            player_id = person.get('identifier', '') if 'identifier' in person else ''
            role = person.get('role', '') if 'role' in person else ''
            batting_style = person.get('batting_style', '') if 'batting_style' in person else ''
            bowling_style = person.get('bowling_style', '') if 'bowling_style' in person else ''
            matched_count += 1
        else:
            # Fuzzy match
            if len(player_names_people) > 0:
                matches = difflib.get_close_matches(name, player_names_people, n=1, cutoff=0.85)
                if matches:
                    matched_name = matches[0]
                    person = df_people[df_people['name'] == matched_name].iloc[0]
                    player_id = person.get('identifier', '') if 'identifier' in person else ''
                    role = person.get('role', '') if 'role' in person else ''
                    batting_style = person.get('batting_style', '') if 'batting_style' in person else ''
                    bowling_style = person.get('bowling_style', '') if 'bowling_style' in person else ''
                    matched_count += 1
                else:
                    player_id = ''
                    role = ''
                    batting_style = ''
                    bowling_style = ''
            else:
                player_id = ''
                role = ''
                batting_style = ''
                bowling_style = ''
    else:
        # No name column in people.csv
        player_id = ''
        role = ''
        batting_style = ''
        bowling_style = ''

    # If role is empty (i.e., not found in people.csv or people.csv has no role), then derive from stats
    if not role and role_from_stats:
        role = role_from_stats.get(name, 'BAT')
    elif not role:
        role = 'BAT'  # default

    # For styles, if empty from people.csv, use Unknown
    if not batting_style:
        batting_style = batting_style_from_people.get(name, 'Unknown')
    if not bowling_style:
        bowling_style = bowling_style_from_people.get(name, 'Unknown')

    player_roles[name] = {
        'player_id': player_id,
        "role": role,
        'batting_style': batting_style,
        'bowling_style': bowling_style
    }

print(f"Matched {matched_count} players via exact or fuzzy name matching.")
print(f"Built roles for {len(player_roles)} players.")

# Role distribution
role_counts = {'BAT': 0, 'BOWL': 0, 'AR': 0, 'WK': 0}
for data in player_roles.values():
    role = data['role']
    if role in role_counts:
        role_counts[role] += 1
    else:
        # In case we have unexpected role values, count them as BAT for simplicity
        role_counts['BAT'] += 1

print(f"Role distribution: BAT={role_counts['BAT']}, BOWL={role_counts['BOWL']}, AR={role_counts['AR']}, WK={role_counts['WK']}")

# Save to file
output_path = '../data/processed/player_roles.json'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
import json
with open(output_path, 'w') as f:
    json.dump(player_roles, f, indent=2)
print(f"Saved player roles to {output_path}")


# In[4]:


# Validate
print("\n=== Validation ===")

# Load the saved file to verify
import json
if os.path.exists('../data/processed/player_roles.json'):
    with open('../data/processed/player_roles.json', 'r') as f:
        player_roles = json.load(f)
    print(f"Loaded {len(player_roles)} player roles from file")
else:
    print("Error: player_roles.json not found")
    player_roles = {}

# Convert back to DataFrame for easy analysis
player_list = []
for name, data in player_roles.items():
    player_list.append({
        'player_name': name,
        'player_id': data['player_id'],
        'role': data['role'],
        'batting_style': data['batting_style'],
        'bowling_style': data['bowling_style']
    })

df_roles = pd.DataFrame(player_list)

# We need to merge with stats to get matches_played etc. for validation
print("\nMerging with interim stats for validation...")
if stats_file and os.path.exists(stats_file):
    df_validation = df_stats.groupby('player_name').agg(
        total_runs=('runs', 'sum'),
        total_wickets=('wickets', 'sum'),
        total_stumpings=('stumpings', 'sum'),
        matches_played=('runs', 'count')
    ).reset_index()
    
    df_validation = df_validation.merge(df_roles, left_on='player_name', right_on='player_name', how='left')
    
    # Fill missing roles with BAT
    df_validation['role'] = df_validation['role'].fillna('BAT')
    
    # # Show top 20 players by matches_played
    # print("\nTop 20 players by matches played:")
    # top_20 = df_validation.nlargest(20, 'matches_played')[['player_name', 'matches_played', 'role', 'total_runs', 'total_wickets', 'total_stumpings']]
    # print(top_20.to_string(index=False))
    
    # Flag any player with role=BAT who has >20 wickets (possible misclassification)
    print("\nChecking for BAT players with >20 wickets (possible misclassification):")
    bat_wicket_players = df_validation[(df_validation['role'] == 'BAT') & (df_validation['total_wickets'] > 20)]
    if not bat_wicket_players.empty:
        print("Found {} BAT players with >20 wickets:".format(len(bat_wicket_players)))
        print(bat_wicket_players[['player_name', 'total_wickets', 'role']].to_string(index=False))
    else:
        print("No BAT players with >20 wickets found.")
    
    # Flag any player with role=BOWL who has >500 runs (possible misclassification)
    print("\nChecking for BOWL players with >500 runs (possible misclassification):")
    bowl_run_players = df_validation[(df_validation['role'] == 'BOWL') & (df_validation['total_runs'] > 500)]
    if not bowl_run_players.empty:
        print("Found {} BOWL players with >500 runs:".format(len(bowl_run_players)))
        print(bowl_run_players[['player_name', 'total_runs', 'role']].to_string(index=False))
    else:
        print("No BOWL players with >500 runs found.")
    
    # Also check for extreme cases
    print("\nAdditional checks:")
    print("BAT players with >50 wickets:", len(df_validation[(df_validation['role'] == 'BAT') & (df_validation['total_wickets'] > 50)]))
    print("BOWL players with >1000 runs:", len(df_validation[(df_validation['role'] == 'BOWL') & (df_validation['total_runs'] > 1000)]))
    print("AR players with <10 wickets and <500 runs:", len(df_validation[(df_validation['role'] == 'AR') & (df_validation['total_wickets'] < 10) & (df_validation['total_runs'] < 500)]))
    print("WK players with 0 stumpings:", len(df_validation[(df_validation['role'] == 'WK') & (df_validation['total_stumpings'] == 0)]))
else:
    print("Cannot validate - no stats data available")


# In[ ]:





# In[ ]:




