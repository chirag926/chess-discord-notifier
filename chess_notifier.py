#!/usr/bin/env python3

import json
import os
from datetime import datetime

import requests


CLUB_NAME = "no-stress-chess-2"
CLUB_DISPLAY_NAME = "No Stress Chess"
OUR_TEAM_NAME = "no stress chess"

SEEN_FILE = "seen_games.json"
SEEN_MATCHES_FILE = "seen_matches.json"
SEEN_REGISTERED_FILE = "seen_registered_matches.json"

MAX_GAME_HISTORY = 1000
MAX_MATCH_HISTORY = 500
MAX_REGISTERED_HISTORY = 200

HEADERS = {
    "User-Agent": "NoStressChessDiscordNotifier/1.0"
}


def execute_api_request(url):

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()

        print("HTTP error:")
        print(response.status_code)
        print(response.text)

    except Exception as e:
        print("Request error:")
        print(e)

    return None



def fetch_club_matches():

    url = f"https://api.chess.com/pub/club/{CLUB_NAME}/matches"

    return execute_api_request(url)



def fetch_match(match_id):

    url = f"https://api.chess.com/pub/match/{match_id}"

    return execute_api_request(url)



def fetch_board(board_url):

    return execute_api_request(board_url)



def load_seen_games():

    if not os.path.exists(SEEN_FILE):
        return {}

    with open(SEEN_FILE, "r") as f:
        return json.load(f)



def save_seen_games(seen_games):

    with open(SEEN_FILE, "w") as f:
        json.dump(
            seen_games,
            f,
            indent=4
        )



def load_seen_matches():

    if not os.path.exists(SEEN_MATCHES_FILE):
        return {}

    with open(SEEN_MATCHES_FILE, "r") as f:
        return json.load(f)



def save_seen_matches(seen_matches):

    with open(SEEN_MATCHES_FILE, "w") as f:
        json.dump(
            seen_matches,
            f,
            indent=4
        )



def load_seen_registered_matches():

    if not os.path.exists(SEEN_REGISTERED_FILE):
        return {}

    with open(SEEN_REGISTERED_FILE, "r") as f:
        return json.load(f)



def save_seen_registered_matches(seen_registered_matches):

    with open(SEEN_REGISTERED_FILE, "w") as f:
        json.dump(
            seen_registered_matches,
            f,
            indent=4
        )



def cleanup_history(history, max_history):

    if len(history) <= max_history:
        return history

    sorted_history = sorted(
        history.items(),
        key=lambda x: x[1].get("date", ""),
        reverse=True
    )

    trimmed = dict(
        sorted_history[:max_history]
    )

    print(
        f"Cleanup: removed "
        f"{len(history) - max_history} old entries"
    )

    return trimmed



def determine_result(game):

    white = game.get("white")
    black = game.get("black")

    if not isinstance(white, dict):
        return None

    if not isinstance(black, dict):
        return None


    white_result = white.get("result")
    black_result = black.get("result")


    if white_result == "win":

        return {
            "winner": white["username"],
            "loser": black["username"],
            "draw": False
        }


    if black_result == "win":

        return {
            "winner": black["username"],
            "loser": white["username"],
            "draw": False
        }


    if (
        white_result
        and black_result
        and white_result == black_result
    ):

        return {
            "winner": None,
            "loser": None,
            "player1": white["username"],
            "player2": black["username"],
            "draw": True
        }


    return None



def process_match(match):

    match_id = match["@id"].split("/")[-1]

    data = fetch_match(match_id)

    if not data:
        return [], None


    print()
    print("MATCH:")
    print(data["name"])


    team1 = data["teams"]["team1"]
    team2 = data["teams"]["team2"]


    score = (
        f"{team1['name']}: {team1['score']}\n"
        f"{team2['name']}: {team2['score']}"
    )


    notifications = []

    processed_games = set()


    for team in ["team1", "team2"]:

        for player in data["teams"][team]["players"]:

            board_url = player.get("board")

            if not board_url:
                continue


            board = fetch_board(board_url)

            if not board:
                continue


            for game in board.get("games", []):

                game_id = game["url"].split("/")[-1]


                if game_id in processed_games:
                    continue


                result = determine_result(game)

                if not result:
                    continue


                processed_games.add(game_id)


                winner_team = ""


                if not result["draw"]:

                    winner_username = (
                        result["winner"].lower()
                    )


                    for check_team in [
                        "team1",
                        "team2"
                    ]:

                        for check_player in (
                            data["teams"][check_team]["players"]
                        ):

                            if (
                                check_player["username"].lower()
                                == winner_username
                            ):

                                winner_team = (
                                    data["teams"][check_team]["name"]
                                )


                notifications.append(
                    {
                        "game_id": game_id,
                        "winner": result.get("winner"),
                        "loser": result.get("loser"),
                        "player1": result.get("player1"),
                        "player2": result.get("player2"),
                        "draw": result.get("draw", False),
                        "winner_team": winner_team,
                        "match": data["name"],
                        "url": game["url"]
                    }
                )


    return notifications, score


def process_completed_match(match):

    match_id = match["@id"].split("/")[-1]

    data = fetch_match(match_id)

    if not data:
        return None


    team1 = data["teams"]["team1"]
    team2 = data["teams"]["team2"]


    if team1["result"] == "win":

        winner = team1["name"]

    elif team2["result"] == "win":

        winner = team2["name"]

    else:

        winner = None


    return {
        "match_id": match_id,
        "match": data["name"],
        "score": (
            f"{team1['name']}: {team1['score']}\n"
            f"{team2['name']}: {team2['score']}"
        ),
        "winner": winner
    }



def process_registered_match(match):

    match_id = match["@id"].split("/")[-1]

    data = fetch_match(match_id)

    if not data:
        return None


    team1 = data["teams"]["team1"]
    team2 = data["teams"]["team2"]


    if OUR_TEAM_NAME in team1["name"].lower():

        opponent = team2["name"]

    else:

        opponent = team1["name"]


    return {
        "match_id": match_id,
        "match": data["name"],
        "opponent": opponent,
        "description": data.get(
            "description",
            "Daily match"
        ),
        "start_time": data["start_time"],
        "url": data["url"]
    }



def send_game_update_notification(match_name, games, score):

    webhook_url = os.environ.get(
        "DISCORD_WEBHOOK_URL"
    )


    if not webhook_url:

        print(
            "DISCORD_WEBHOOK_URL not set. "
            "Skipping Discord notification."
        )

        return


    message = (
        f"♟️ **No Stress Chess Update**\n\n"
        f"⚔️ **Match:** {match_name}\n\n"
        f"📝 **Games completed since the last update:**\n\n"
    )


    for game in games:


        if game["draw"]:

            message += (
                f"• 🤝 **Draw:** "
                f"**{game['player1']}** vs "
                f"**{game['player2']}**\n"
                f"  🎮 {game['url']}\n\n"
            )


        else:

            if game["result"] == "win":

                emoji = "♟️"

            else:

                emoji = "😞"


            message += (
                f"• {emoji} **{game['winner']}** defeated "
                f"**{game['loser']}**\n"
                f"  🎮 {game['url']}\n\n"
            )


    message += (
        f"🏆 **Daily Club Match Score:**\n"
        f"{score}"
    )


    requests.post(
        webhook_url,
        json={"content": message},
        timeout=10
    )



def send_match_notification(match):

    webhook_url = os.environ.get(
        "DISCORD_WEBHOOK_URL"
    )


    if not webhook_url:

        return


    if match["winner"] is None:

        emoji = "🤝"
        result = "ended in a draw"


    elif OUR_TEAM_NAME in match["winner"].lower():

        emoji = "🎉"
        result = f"{match['winner']} won"


    else:

        emoji = "😞"
        result = f"{match['winner']} won"



    message = (
        f"⚔️ **No Stress Chess Match Completed**\n\n"
        f"🏟️ **Match:** {match['match']}\n\n"
        f"{emoji} {result}\n\n"
        f"🏆 **Final Score:**\n"
        f"{match['score']}"
    )


    requests.post(
        webhook_url,
        json={"content": message},
        timeout=10
    )



def send_registration_notification(match):

    webhook_url = os.environ.get(
        "DISCORD_WEBHOOK_URL"
    )


    if not webhook_url:

        return


    start_time = datetime.fromtimestamp(
        match["start_time"]
    ).strftime(
        "%A, %B %d, %Y %I:%M %p"
    )


    message = (
        f"📝 **New Daily Club Match Open**\n\n"
        f"♟️ **Match Name:** {match['match']}\n\n"
        f"⚔️ **Opponent:** {match['opponent']}\n\n"
        f"⏱️ **Time Control:** {match['description']}\n\n"
        f"🗓️ **Starts:** {start_time}\n\n"
        f"🔗 **Join Match**\n"
        f"{match['url']}"
    )


    requests.post(
        webhook_url,
        json={"content": message},
        timeout=10
    )



def main():

    print(datetime.now())
    print(
        f"Checking club: {CLUB_DISPLAY_NAME}"
    )


    seen_games = load_seen_games()
    seen_matches = load_seen_matches()
    seen_registered_matches = load_seen_registered_matches()


    original_seen_games = dict(seen_games)
    original_seen_matches = dict(seen_matches)
    original_seen_registered_matches = dict(
        seen_registered_matches
    )


    matches = fetch_club_matches()


    if not matches:

        print("No matches found")
        return



    game_notifications_sent = 0


    active_matches = matches.get(
        "in_progress",
        []
    )


    print(
        f"Active matches found: {len(active_matches)}"
    )


    for match in active_matches:


        notifications, score = process_match(match)


        unseen_games = []


        for notification in notifications:


            game_id = notification["game_id"]


            if game_id in seen_games:

                continue



            if notification["draw"]:

                unseen_games.append(
                    {
                        "draw": True,
                        "player1": notification["player1"],
                        "player2": notification["player2"],
                        "url": notification["url"]
                    }
                )


            else:


                our_team_won = (
                    notification["winner_team"].lower()
                    == OUR_TEAM_NAME
                )


                result = (
                    "win"
                    if our_team_won
                    else "loss"
                )


                unseen_games.append(
                    {
                        "draw": False,
                        "winner": notification["winner"],
                        "loser": notification["loser"],
                        "result": result,
                        "url": notification["url"]
                    }
                )



            seen_games[game_id] = {

                "winner": notification["winner"],
                "loser": notification["loser"],
                "match": notification["match"],
                "date": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )

            }



        if unseen_games:

            send_game_update_notification(
                notifications[0]["match"],
                unseen_games,
                score
            )


            game_notifications_sent += len(
                unseen_games
            )



    seen_games = cleanup_history(
        seen_games,
        MAX_GAME_HISTORY
    )


    seen_matches = cleanup_history(
        seen_matches,
        MAX_MATCH_HISTORY
    )


    seen_registered_matches = cleanup_history(
        seen_registered_matches,
        MAX_REGISTERED_HISTORY
    )



    print()

    print(
        f"New game notifications sent: "
        f"{game_notifications_sent}"
    )



    if seen_games != original_seen_games:

        save_seen_games(seen_games)

        print(
            "seen_games.json updated"
        )



    if seen_matches != original_seen_matches:

        save_seen_matches(seen_matches)

        print(
            "seen_matches.json updated"
        )



    if (
        seen_registered_matches
        != original_seen_registered_matches
    ):

        save_seen_registered_matches(
            seen_registered_matches
        )

        print(
            "seen_registered_matches.json updated"
        )



if __name__ == "__main__":

    main()
