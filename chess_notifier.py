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
        key=lambda x: x[1]["date"],
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

    if isinstance(game.get("white"), dict):

        white = game["white"]
        black = game["black"]

        if white.get("result") == "win":
            return white["username"], black["username"]

        if black.get("result") == "win":
            return black["username"], white["username"]

    return None, None


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

    print(
        f"Score: {team1['name']} {team1['score']} - "
        f"{team2['name']} {team2['score']}"
    )

    notifications = []

    for team in ["team1", "team2"]:

        team_name = data["teams"][team]["name"]

        for player in data["teams"][team]["players"]:

            board_url = player.get("board")

            if not board_url:
                continue

            board = fetch_board(board_url)

            if not board:
                continue

            for game in board.get("games", []):

                winner, loser = determine_result(game)

                if winner and loser:

                    game_id = game["url"].split("/")[-1]

                    notifications.append(
                        {
                            "game_id": game_id,
                            "winner": winner,
                            "loser": loser,
                            "winner_team": team_name,
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

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

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

        if game["result"] == "win":
            emoji = "🎉"

        else:
            emoji = "😞"

        message += (
            f"• {emoji} **{game['winner']}** defeated "
            f"**{game['loser']}**\n"
            f"  🎮 {game['url']}\n\n"
        )

    message += (
        f"🏆 **Current Match Score:**\n"
        f"{score}"
    )

    requests.post(
        webhook_url,
        json={"content": message},
        timeout=10
    )


def send_match_notification(match):

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print(
            "DISCORD_WEBHOOK_URL not set. "
            "Skipping Discord notification."
        )
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

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print(
            "DISCORD_WEBHOOK_URL not set. "
            "Skipping Discord notification."
        )
        return

    start_time = datetime.fromtimestamp(
        match["start_time"]
    ).strftime(
        "%A, %B %-d, %Y %-I:%M %p"
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
    print(f"Checking club: {CLUB_DISPLAY_NAME}")

    seen_games = load_seen_games()
    seen_matches = load_seen_matches()
    seen_registered_matches = load_seen_registered_matches()

    original_seen_games = dict(seen_games)
    original_seen_matches = dict(seen_matches)
    original_seen_registered_matches = dict(
        seen_registered_matches
    )

    print(
        f"Games already seen: {len(seen_games)}"
    )

    print(
        f"Completed matches already seen: "
        f"{len(seen_matches)}"
    )

    print(
        f"Registered matches already seen: "
        f"{len(seen_registered_matches)}"
    )

    matches = fetch_club_matches()

    if not matches:
        print("No matches found")
        return


    game_notifications_sent = 0
    match_notifications_sent = 0
    registration_notifications_sent = 0


    #
    # REGISTERED MATCHES
    #

    registered_matches = matches.get(
        "registered",
        []
    )

    print(
        f"Registered matches found: "
        f"{len(registered_matches)}"
    )

    for match in registered_matches:

        match_id = match["@id"].split("/")[-1]

        if match_id in seen_registered_matches:
            continue

        registered_match = process_registered_match(match)

        if registered_match:

            print()
            print("NEW REGISTERED MATCH:")
            print(
                registered_match["match"]
            )
            print(
                registered_match["opponent"]
            )

            send_registration_notification(
                registered_match
            )

            registration_notifications_sent += 1

            seen_registered_matches[match_id] = {
                "match": registered_match["match"],
                "date": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }


    #
    # FINISHED MATCHES
    #

    finished_matches = matches.get(
        "finished",
        []
    )

    print(
        f"Finished matches found: "
        f"{len(finished_matches)}"
    )

    for match in finished_matches:

        match_id = match["@id"].split("/")[-1]

        if match_id in seen_matches:
            continue

        completed_match = process_completed_match(match)

        if completed_match:

            print()
            print("NEW COMPLETED MATCH:")
            print(
                completed_match["match"]
            )
            print(
                completed_match["score"]
            )

            send_match_notification(
                completed_match
            )

            match_notifications_sent += 1

            seen_matches[match_id] = {
                "match": completed_match["match"],
                "date": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }


    #
    # ACTIVE MATCHES
    #

    active_matches = matches.get(
        "in_progress",
        []
    )

    print(
        f"Active matches found: "
        f"{len(active_matches)}"
    )

    for match in active_matches:

        notifications, score = process_match(match)

        unseen_games = []

        for notification in notifications:

            game_id = notification["game_id"]

            if game_id in seen_games:
                continue

            our_team_won = (
                OUR_TEAM_NAME
                in notification["winner_team"].lower()
            )

            result = (
                "win"
                if our_team_won
                else "loss"
            )

            unseen_games.append(
                {
                    "winner": notification["winner"],
                    "loser": notification["loser"],
                    "result": result,
                    "url": notification["url"]
                }
            )

            seen_games[game_id] = {
                "winner": notification["winner"],
                "loser": notification["loser"],
                "winner_team": notification["winner_team"],
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


    #
    # CLEANUP HISTORY
    #

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
        f"New registration notifications sent: "
        f"{registration_notifications_sent}"
    )

    print(
        f"New game notifications sent: "
        f"{game_notifications_sent}"
    )

    print(
        f"New match notifications sent: "
        f"{match_notifications_sent}"
    )


    if seen_games != original_seen_games:

        save_seen_games(
            seen_games
        )

        print(
            "seen_games.json updated"
        )


    if seen_matches != original_seen_matches:

        save_seen_matches(
            seen_matches
        )

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


    if (
        seen_games == original_seen_games
        and seen_matches == original_seen_matches
        and seen_registered_matches
        == original_seen_registered_matches
    ):

        print(
            "No JSON changes"
        )


if __name__ == "__main__":

    main()
