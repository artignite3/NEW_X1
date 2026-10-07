import json
import math

def numeric(stats, key):
    """Missing, null and nonfinite innings values represent zero."""
    try:
        value = float(stats.get(key) or 0)
        return value if math.isfinite(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


# Function to calculate batting points for Test matches
def calculate_batting_points_test(player_stats):
    points = 0
    runs_scored = numeric(player_stats, "Total Runs Scored")
    boundaries = numeric(player_stats, "Fours")
    sixes = numeric(player_stats, "Sixes")
    balls_faced = numeric(player_stats, "Balls Faced")
    balls_faced_inning1 = numeric(player_stats, "Innings 1 Balls Faced") or numeric(player_stats, "Balls Faced Inning 1")
    balls_faced_inning2 = numeric(player_stats, "Innings 2 Balls Faced") or numeric(player_stats, "Balls Faced Inning 2")
    balls_faced_inning3 = numeric(player_stats, "Innings 3 Balls Faced") or numeric(player_stats, "Balls Faced Inning 3")
    balls_faced_inning4 = numeric(player_stats, "Innings 4 Balls Faced") or numeric(player_stats, "Balls Faced Inning 4")
    inning1_not_out = numeric(player_stats, "How Out Inning 1 (not out)")
    inning2_not_out = numeric(player_stats, "How Out Inning 2 (not out)")
    inning1_not_played = numeric(player_stats, "How Out Inning 1 (Not Played)")
    inning2_not_played = numeric(player_stats, "How Out Inning 2 (Not Played)")
    inning3_not_out = numeric(player_stats, "How Out Inning 3 (not out)")
    inning4_not_out = numeric(player_stats, "How Out Inning 4 (not out)")
    inning3_not_played = numeric(player_stats, "How Out Inning 3 (Not Played)")
    inning4_not_played = numeric(player_stats, "How Out Inning 4 (Not Played)")
    inning1_runs = numeric(player_stats, "Innings 1 Runs")
    inning2_runs = numeric(player_stats, "Innings 2 Runs")
    inning3_runs = numeric(player_stats, "Innings 3 Runs")
    inning4_runs = numeric(player_stats, "Innings 4 Runs")
    
    
    
    # +1 point per run
    points += runs_scored * 1

    # +1 per boundary, +2 per six
    points += boundaries * 1
    points += sixes * 2

    # DOING CENTURY BONUS INNING BY INNING
    # removed double century case as it doesn't exist in the point system
    # +4  half-century, +8 for a century
    if inning1_runs >= 100:
        points += 8
    elif inning1_runs >= 50:
        points += 4
        
    if inning2_runs >= 100:
        points += 8
    elif inning2_runs >= 50:
        points += 4

    if inning3_runs >= 100:
        points += 8
    elif inning3_runs >= 50:
        points += 4
        
    if inning4_runs >= 100:
        points += 8
    elif inning4_runs >= 50:
        points += 4
        
    # DOING THIS DISMISSAL INNING BY INNING
    # TODO: MAKE THIS NOT FOR BOWLERS
    # currently done for all players as we dont have data if a player is bowler or not
    # Penalty: -4 points if dismissed for a duck (except tailenders)  
    if inning1_runs == 0 and (inning1_not_played==0 and inning1_not_out==0) and balls_faced_inning1 > 0:
        points -= 4
    if inning2_runs == 0 and (inning2_not_played==0 and inning2_not_out==0) and balls_faced_inning2 > 0:
        points -= 4
    if inning3_runs == 0 and (inning3_not_played==0 and inning3_not_out==0) and balls_faced_inning3 > 0:
        points -= 4
    if inning4_runs == 0 and (inning4_not_played==0 and inning4_not_out==0) and balls_faced_inning4 > 0:
        points -= 4


    # # Strike Rate Bonus (Min 50 balls faced)
    # if balls_faced >= 50:
    #     strike_rate = (runs_scored / balls_faced) * 100
    #     if strike_rate >= 100:
    #         points += 4
    #     elif strike_rate < 40:
    #         points -= 2

    return points

# Function to calculate bowling points for Test matches
def calculate_bowling_points_test(player_stats):
    points = 0
    wickets = numeric(player_stats, "Wickets")
    overs_bowled = numeric(player_stats, "Overs Bowled")
    inning1_wickets = numeric(player_stats, "Innings 1 Wickets")
    inning2_wickets = numeric(player_stats, "Innings 2 Wickets")
    inning3_wickets = numeric(player_stats, "Innings 3 Wickets")
    inning4_wickets = numeric(player_stats, "Innings 4 Wickets")
    
    
    # Bowled and LBW features to be made yet
    bowled_or_lbw = numeric(player_stats, "Bowled") + numeric(player_stats, "LBW")

    # +16 points per wicket, +8 for bowled/LBW dismissals
    points += wickets * 16
    points += bowled_or_lbw * 8

    # DOING WICKET BONUS INNING BY INNING
    # Bonus for 4 or >=5 wickets in a match
    if inning1_wickets >= 5:
        points += 8
    elif inning1_wickets == 4:
        points += 4
        
    if inning2_wickets >= 5:
        points += 8
    elif inning2_wickets == 4:
        points += 4
    
    if inning3_wickets >= 5:
        points += 8
    elif inning3_wickets == 4:
        points += 4
    
    if inning4_wickets >= 5:
        points += 8
    elif inning4_wickets == 4:
        points += 4

    # # Economy Rate Bonus (Min 10 overs bowled in an innings)
    # if overs_bowled >= 10:
    #     economy_rate = numeric(player_stats, "Economy Rate")
    #     if economy_rate < 2.5:
    #         points += 6
    #     elif 2.5 <= economy_rate <= 3.5:
    #         points += 4
    #     elif 3.5 < economy_rate <= 4.5:
    #         points += 2
    #     elif 4.5 < economy_rate <= 5.5:
    #         points -= 2
    #     elif economy_rate > 5.5:
            # points -= 4

    return points

# Function to calculate fielding points for Test matches
def calculate_fielding_points_test(player_stats):
    points = 0
    catches_taken = numeric(player_stats, "Catches Taken")
    stumped_outs = numeric(player_stats, "Stumped Outs Made")
    # run_outs_direct = numeric(player_stats, "Direct Hit Run Outs Made")
    # run_outs_indirect = numeric(player_stats, "Non-Direct Run Outs Made")
    run_outs = numeric(player_stats, "Run Outs Made")

    # +8 points per catch, +12 for stumping, +12 for direct run-out, +6 for indirect
    points += catches_taken * 8
    points += stumped_outs * 12
    # points += run_outs_direct * 12
    # points += run_outs_indirect * 6
    ## considering probability of direct hit is less so -1 than the avg of +12 and +6
    points += run_outs * 8  


    # Not there
    # if catches_taken >= 5:
    #     points += 8

    return points

# Wrapper function to calculate total fantasy points for Test matches
def calculate_fantasy_points_test(player_stats):
    batting_points = calculate_batting_points_test(player_stats)
    bowling_points = calculate_bowling_points_test(player_stats)
    fielding_points = calculate_fielding_points_test(player_stats)
    
    # Total points
    total_points = batting_points + bowling_points + fielding_points
    # assuming every player is playing
    total_points += 4
    return {
        "total_points": total_points,
        "batting_points": batting_points,
        "bowling_points": bowling_points,
        "fielding_points": fielding_points
    }

if __name__== '__main__':
    print(calculate_fantasy_points_test({
            "Team Name": "Northamptonshire",
            "Batting Innings": 2,
            "Bowling Innings": 1,
            "Total Runs Scored": 116.0,
            "Avg Runs Per Inning": 58.0,
            "Boundaries": 15.0,
            "Sixes": 2.0,
            "Average Sixes Per Inning": 1.0,
            "Fours": 13.0,
            "Average Fours Per Inning": 6.5,
            "Boundary% Per Inning": 4.237288135593221,
            "Boundary Rate Per Inning": 5.9,
            "Wickets": 0.0,
            "Avg Wickets Per Inning": 0.0,
            "Opposition Team": "Derbyshire",
            "Catches Taken": 0,
            "Stumped Outs Made": 0,
            "Run Outs Made": 0,
            "Match Date": "2024-09-09",
            "Match ID": "Northamptonshire-Derbyshire-2024-09-09-male-MDM",
            "Match Type": "MDM",
            "Venue": "County Ground, Northampton",
            "Event": "County Championship",
            "Match Winner": "Northamptonshire",
            "Balls Faced": 177.0,
            "Avg Balls Faced Per Inning": 88.5,
            "Avg Batting S/R Per Inning": 32.76836158192091,
            "Avg Runs/Ball Per Inning": 0.327683615819209,
            "Overs Bowled": 1.0,
            "Bowls Bowled": 6.0,
            "Average Bowls Bowled Per Inning": 6.0,
            "Avg Economy Rate per inning": 2.0,
            "Bowling Average": float('inf'),
            "Average Consecutive Dot Balls": 2.0,
            "Maiden Overs": 0.0,
            "Avg Bowling S/R Per Inning": float('inf'),
            "Runs Given": 2.0,
            "RunsGiven/Ball Per Inning": 0.3333333333333333,
            "Batting S/R AA(Above Average)": 12.41989931652881,
            "How Out Inning 1 (Not Played)": 0,
            "How Out Inning 1 (caught)": 0,
            "How Out Inning 1 (not out)": 0,
            "How Out Inning 1 (lbw)": 0,
            "How Out Inning 1 (bowled)": 0,
            "How Out Inning 1 (Run Out)": 0,
            "How Out Inning 1 (caught and bowled)": 0,
            "How Out Inning 1 (stumped)": 1,
            "How Out Inning 2 (Not Played)": 1,
            "How Out Inning 2 (caught)": 0,
            "How Out Inning 2 (not out)": 0,
            "How Out Inning 2 (lbw)": 0,
            "How Out Inning 2 (bowled)": 0,
            "How Out Inning 2 (Run Out)": 0,
            "How Out Inning 2 (caught and bowled)": 0,
            "How Out Inning 2 (stumped)": 0,
            "How Out Inning 3 (Not Played)": 0,
            "How Out Inning 3 (caught)": 0,
            "How Out Inning 3 (not out)": 0,
            "How Out Inning 3 (lbw)": 0,
            "How Out Inning 3 (bowled)": 1,
            "How Out Inning 3 (Run Out)": 0,
            "How Out Inning 3 (caught and bowled)": 0,
            "How Out Inning 3 (stumped)": 0,
            "How Out Inning 4 (Not Played)": 1,
            "How Out Inning 4 (caught)": 0,
            "How Out Inning 4 (not out)": 0,
            "How Out Inning 4 (lbw)": 0,
            "How Out Inning 4 (bowled)": 0,
            "How Out Inning 4 (Run Out)": 0,
            "How Out Inning 4 (caught and bowled)": 0,
            "How Out Inning 4 (stumped)": 0,
            "Innings 1 Runs": 90.0,
            "Innings 2 Runs": 0,
            "Innings 1 Wickets": 0,
            "Innings 2 Wickets": 0.0,
            "Innings 3 Runs": 26.0,
            "Innings 4 Runs": 0,
            "Innings 3 Wickets": 0,
            "Innings 4 Wickets": 0,
            "Innings 1 Balls Faced": 144.0,
            "Innings 2 Balls Faced": 0,
            "Innings 3 Balls Faced": 33.0,
            "Innings 4 Balls Faced": 0
            }))
