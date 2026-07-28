#!/usr/bin/env python3

import json
import os
from datetime import datetime

import requests


CLUB_NAME = "no-stress-chess-2"
CLUB_DISPLAY_NAME = "No Stress Chess"
OUR_TEAM_NAME = "no stress chess"

SEEN_FILE = "seen_games.json"
MAX_HISTORY = 1000

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


def cleanup_history(seen_games):
    if len(seen_games) <= MAX_HISTORY:
        return seen_games

    sorted_games = sorted(
        seen_games.items(),
        key=lambda x: x[1]["date"],
        reverse=True
    )

    trimmed = dict(sorted_games[:MAX_HISTORY])

    print(
        f"Cleanup: removed {len(seen_games) - MAX_HISTORY} old games"
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
        return []

    print()
    print("MATCH:")
    print(data["name"])

    team1 = data["teams"]["team1"]
    team2 = data["teams"]["team2"]

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
                            "score": (
                                f"{team1['name']}: {team1['score']}\n"
                                f"{team2['name']}: {team2['score']}"
                            ),
                            "url": game["url"]
                        }
                    )

    return notifications


def send_notification(notification):

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print(
            "DISCORD_WEBHOOK_URL not set. "
            "Skipping Discord notification."
        )
        return

    our_team_won = (
        OUR_TEAM_NAME in notification["winner_team"].lower()
    )

    result_emoji = "🎉" if our_team_won else "♟️"

    message = (
        f"♟️ **No Stress Chess Update**\n\n"
        f"🏟️ **Match:** {notification['match']}\n\n"
        f"{result_emoji} **{notification['winner']}** defeated "
        f"**{notification['loser']}**!\n\n"
        f"🏆 **Match Score:**\n"
        f"{notification['score']}\n\n"
        f"🎮 **Game:**\n"
        f"{notification['url']}"
    )

    payload = {
        "content": message
    }

    response = requests.post(
        webhook_url,
        json=payload,
        timeout=10
    )

    if response.status_code != 204:
        print("Discord error:")
        print(response.status_code)
        print(response.text)


def main():

    print(datetime.now())
    print(f"Checking club: {CLUB_DISPLAY_NAME}")

    seen_games = load_seen_games()

    print(f"Games already seen: {len(seen_games)}")

    original_seen_games = dict(seen_games)

    seen_games = cleanup_history(seen_games)

    matches = fetch_club_matches()

    if not matches:
        print("No matches found")
        return

    active_matches = matches.get(
        "in_progress",
        []
    )

    print(
        f"Active matches found: {len(active_matches)}"
    )

    sent_notifications = 0

    for match in active_matches:

        notifications = process_match(match)

        for notification in notifications:

            game_id = notification["game_id"]

            if game_id in seen_games:
                continue

            send_notification(notification)

            sent_notifications += 1

            seen_games[game_id] = {
                "winner": notification["winner"],
                "loser": notification["loser"],
                "winner_team": notification["winner_team"],
                "match": notification["match"],
                "date": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }

    seen_games = cleanup_history(seen_games)

    print()
    print(f"New notifications sent: {sent_notifications}")

    if seen_games != original_seen_games:
        save_seen_games(seen_games)
        print("seen_games.json updated")
    else:
        print("No changes to seen_games.json")


if __name__ == "__main__":
    main()
