import os
import json
import requests
from dotenv import load_dotenv
import time

load_dotenv()

RAPID_API_KEY = os.getenv("RAPID_API_KEY")

_HERE = os.path.dirname(os.path.abspath(__file__))
MATCHES_PATH = os.path.join(_HERE, "upcoming_matches.json")
SQUADS_PATH = os.path.join(_HERE, "upcoming_squads.json")
SERIES_SQUAD_CACHE = {}
PLAYER_CACHE = {}

HEADERS = {
    "X-RapidAPI-Key": RAPID_API_KEY,
    "X-RapidAPI-Host": "cricbuzz-cricket.p.rapidapi.com"
}

def get_series_squads(series_id):

    if series_id in SERIES_SQUAD_CACHE:
        return SERIES_SQUAD_CACHE[series_id]

    try:

        url = (
            f"https://cricbuzz-cricket.p.rapidapi.com/"
            f"series/v1/{series_id}/squads"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        SERIES_SQUAD_CACHE[series_id] = data

        return data

    except Exception as e:

        print(
            f"Squad list error: {e}"
        )

        return None
def get_squad_players(
    series_id,
    squad_id
):

    key = (
        str(series_id),
        str(squad_id)
    )

    if key in PLAYER_CACHE:
        return PLAYER_CACHE[key]

    try:

        url = (
            f"https://cricbuzz-cricket.p.rapidapi.com/"
            f"series/v1/{series_id}/squads/{squad_id}"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        PLAYER_CACHE[key] = data

        return data

    except Exception as e:

        print(
            f"Player fetch error: {e}"
        )

        return None

    try:

        url = (
            f"https://cricbuzz-cricket.p.rapidapi.com/"
            f"series/v1/{series_id}/squads/{squad_id}"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()

        return response.json()

    except Exception as e:

        print(
            f"Player fetch error: {e}"
        )

        return None
    
def normalize_role(role):

    role = str(role).lower()

    if "wk" in role:
        return "WK"

    if "allround" in role:
        return "AR"

    if "bowler" in role:
        return "BOWL"

    return "BAT"
    
def main():
    # Optional: restrict to specific match ids to conserve RapidAPI quota, e.g.
    #   python squad_fetcher.py --ids 148404,148405
    import argparse

    parser = argparse.ArgumentParser(description="Fetch squads for upcoming matches")
    parser.add_argument(
        "--ids",
        default="",
        help="Comma-separated match_ids to fetch (default: all matches in upcoming_matches.json)",
    )
    args = parser.parse_args()

    id_filter = {i.strip() for i in args.ids.split(",") if i.strip()}

    with open(MATCHES_PATH, "r", encoding="utf-8") as f:
        matches_data = json.load(f)

    matches_to_process = [
        m for m in matches_data["matches"]
        if not id_filter or str(m.get("match_id")) in id_filter
    ]

    squads_out = {
        "fetched_at": "",
        "squads": {}
    }

    # Merge with the existing squads file instead of replacing it — a partial
    # quota-limited run must never wipe squads fetched for other matches.
    if os.path.exists(SQUADS_PATH):
        try:
            with open(SQUADS_PATH, "r", encoding="utf-8") as f:
                squads_out["squads"] = json.load(f).get("squads", {})
        except (json.JSONDecodeError, OSError):
            pass

    for match in matches_to_process:

        series_id = match.get(
            "series_id"
        )

        match_id = match.get(
            "match_id"
        )

        squads_json = get_series_squads(
            series_id
        )

        if (
            not squads_json
            or "squads" not in squads_json
        ):

            squads_out["squads"][
                str(match_id)
            ] = {

                "match_id": match_id,

                "series": match["series"],

                "team1": {
                    "team_name": match["team1"],
                    "players": []
                },

                "team2": {
                    "team_name": match["team2"],
                    "players": []
                }
            }

            continue

        all_squads = []

        for squad in squads_json[
            "squads"
        ]:

            if squad.get("isHeader"):
                continue

            squad_id = squad.get(
                "squadId"
            )

            if not squad_id:
                continue

            players_json = (
                get_squad_players(
                    series_id,
                    squad_id
                )
            )

            players = []

            if players_json:

                for player in players_json.get(
                    "player",
                    []
                ):

                    if player.get(
                        "isHeader"
                    ):
                        continue

                    players.append({

                        "player_id":
                            str(
                                player.get(
                                    "id",
                                    ""
                                )
                            ),

                        "player_name":
                            player.get(
                                "name",
                                ""
                            ),

                        "role":
                            normalize_role(
                                player.get(
                                    "role",
                                    ""
                                )
                            ),

                        "batting_style":
                            player.get(
                                "battingStyle",
                                "Unknown"
                            ),

                        "bowling_style":
                            player.get(
                                "bowlingStyle",
                                "Unknown"
                            ),

                        "is_confirmed":
                            True,

                        "injury_status":
                            "UNKNOWN",

                        "squad_source":
                            "cricbuzz"
                    })

            all_squads.append({

                "team_name":
                    squad.get(
                        "squadType",
                        ""
                    ),

                "team_id":
                    squad.get(
                        "teamId"
                    ),

                "players":
                    players
            })

        squads_out["squads"][
            str(match_id)
        ] = {

            "match_id":
                match_id,

            "series":
                match["series"],

            "series_id":
                series_id,

            "format":
                match["match_type"],

            "team1":
                match["team1"],

            "team2":
                match["team2"],

            "available_squads":
                all_squads
        }

        print(
            f"{match['team1']} vs "
            f"{match['team2']} -> "
            f"{len(all_squads)} squads"
        )
        squads_out["fetched_at"] = __import__("datetime").datetime.now().isoformat()
        with open(
            SQUADS_PATH,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                squads_out,
                f,
                indent=2,
                ensure_ascii=False
            )

        print(
            f"Saved {len(squads_out['squads'])} matches"
        )


if __name__ == "__main__":
    main()