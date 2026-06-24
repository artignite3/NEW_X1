#!/usr/bin/env python3
"""
Script to create all_player_stats.csv from available JSON data.
This creates the expected input file for the player_roles.ipynb notebook.
"""

import json
import os
import csv
from collections import defaultdict

def process_json_file(filepath, match_type):
    """Process a JSON file and extract player stats."""
    print(f"Processing {filepath}...")

    with open(filepath, 'r') as f:
        data = json.load(f)

    # Dictionary to store aggregated stats per player
    # {player_name: {runs: total, wickets: total, stumpings: total, matches: count}}
    player_stats = defaultdict(lambda: {'runs': 0, 'wickets': 0, 'stumpings': 0, 'matches': 0})

    for player_name, matches in data.items():
        if not isinstance(matches, dict):
            continue

        for match_key, match_data in matches.items():
            if not isinstance(match_data, dict):
                continue

            # Extract runs (try different possible field names)
            runs = 0
            for field in ['Total Runs Scored', 'total_runs', 'Runs']:
                if field in match_data:
                    try:
                        runs = float(match_data[field])
                        break
                    except (ValueError, TypeError):
                        pass

            # Extract wickets (try different possible field names)
            wickets = 0
            for field in ['Wickets', 'total_wickets', 'Wkts']:
                if field in match_data:
                    try:
                        wickets = float(match_data[field])
                        break
                    except (ValueError, TypeError):
                        pass

            # Extract stumpings (try different possible field names)
            stumpings = 0
            for field in ['Stumped Outs Made', 'stumpings', 'St']:
                if field in match_data:
                    try:
                        stumpings = float(match_data[field])
                        break
                    except (ValueError, TypeError):
                        pass

            # Only count if we have meaningful data
            if runs > 0 or wickets > 0 or stumpings > 0:
                player_stats[player_name]['runs'] += runs
                player_stats[player_name]['wickets'] += wickets
                player_stats[player_name]['stumpings'] += stumpings
                player_stats[player_name]['matches'] += 1

    return player_stats

def main():
    """Main function to create the CSV file."""
    print("Creating all_player_stats.csv from JSON data...")

    # Define the JSON files to process
    json_files = [
        ('data/interim/T20_data.json', 'T20'),
        ('data/interim/ODI_ODM_data.json', 'ODI'),
        ('data/interim/Test_MDM_data.json', 'Test')
    ]

    # Aggregate stats from all files
    all_player_stats = defaultdict(lambda: {'runs': 0, 'wickets': 0, 'stumpings': 0, 'matches': 0})

    for json_file, match_type in json_files:
        if os.path.exists(json_file):
            stats = process_json_file(json_file, match_type)
            for player_name, player_data in stats.items():
                all_player_stats[player_name]['runs'] += player_data['runs']
                all_player_stats[player_name]['wickets'] += player_data['wickets']
                all_player_stats[player_name]['stumpings'] += player_data['stumpings']
                all_player_stats[player_name]['matches'] += player_data['matches']
        else:
            print(f"Warning: {json_file} not found")

    # Write to CSV file
    output_file = 'data/interim/all_player_stats.csv'
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', newline='') as csvfile:
        fieldnames = ['player_name', 'runs', 'wickets', 'stumpings', 'matches']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for player_name, stats in all_player_stats.items():
            writer.writerow({
                'player_name': player_name,
                'runs': int(stats['runs']),
                'wickets': int(stats['wickets']),
                'stumpings': int(stats['stumpings']),
                'matches': int(stats['matches'])
            })

    print(f"Created {output_file} with {len(all_player_stats)} players")

    # Show some sample data
    print("\nSample data:")
    count = 0
    for player_name, stats in all_player_stats.items():
        if count < 5:
            print(f"{player_name}: {stats}")
            count += 1
        else:
            break

if __name__ == "__main__":
    main()