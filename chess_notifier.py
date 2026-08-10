#!/usr/bin/env python3

import json
import os
from datetime import datetime

import requests


# ============================================================
# CONFIGURATION
# ============================================================

# Chess.com club information
CLUB_NAME = "no-stress-chess-2"
CLUB_DISPLAY_NAME = "No Stress Chess"

# Used to determine whether our team won or lost a game/match
OUR_TEAM_NAME = "no stress chess"

# Files used to remember games and matches we've already
# processed so we don't send duplicate Discord notifications.
SEEN_FILE = "seen_games.json"
SEEN_MATCHES_FILE = "seen_matches.json"

# Maximum number of old entries to keep in the JSON files.
MAX_GAME_HISTORY = 1000
MAX_MATCH_HISTORY = 500

# User-Agent sent with Chess.com API requests.
HEADERS = {
    "User-Agent": "NoStressChessDiscordNotifier/1.0"
}


# ============================================================
# CHESS.COM API FUNCTIONS
# ============================================================

def execute_api_request(url):

    """
    Make a GET request to the Chess.com API.

    Returns:
        Parsed JSON data if the request succeeds.
        None if the request fails.
    """

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

    """
    Get the club's current matches from Chess.com.

    Chess.com separates these into categories such as:
        - in_progress
        - finished
    """

    url = (
        f"https://api.chess.com/pub/club/"
        f"{CLUB_NAME}/matches"
    )

    return execute_api_request(url)


def fetch_match(match_id):

    """
    Get detailed information about a specific match.
    """

    url = (
        f"https://api.chess.com/pub/match/"
        f"{match_id}"
    )

    return execute_api_request(url)


def fetch_board(board_url):

    """
    Fetch the individual board/game information for a player
    in a daily match.
    """

    return execute_api_request(board_url)


# ============================================================
# SEEN GAME / MATCH FILE FUNCTIONS
# ============================================================

def load_seen_games():

    """
    Load the list of games that have already been processed.

    If the file doesn't exist yet, start with an empty dictionary.
    """

    if not os.path.exists(SEEN_FILE):

        return {}

    with open(SEEN_FILE, "r") as f:

        return json.load(f)


def save_seen_games(seen_games):

    """
    Save processed game information to seen_games.json.
    """

    with open(SEEN_FILE, "w") as f:

        json.dump(
            seen_games,
            f,
            indent=4
        )


def load_seen_matches():

    """
    Load the list of matches for which we've already sent
    a match-completed notification.

    If the file doesn't exist yet, start with an empty dictionary.
    """

    if not os.path.exists(SEEN_MATCHES_FILE):

        return {}

    with open(SEEN_MATCHES_FILE, "r") as f:

        return json.load(f)


def save_seen_matches(seen_matches):

    """
    Save processed match information to seen_matches.json.
    """

    with open(SEEN_MATCHES_FILE, "w") as f:

        json.dump(
            seen_matches,
            f,
            indent=4
        )


def cleanup_history(history, max_history):

    """
    Keep only the newest entries in a history dictionary.

    This prevents seen_games.json and seen_matches.json from
    growing indefinitely.
    """

    if len(history) <= max_history:

        return history

    # Sort newest entries first based on the saved date.
    sorted_history = sorted(
        history.items(),
        key=lambda x: x[1].get("date", ""),
        reverse=True
    )

    # Keep only the newest max_history entries.
    trimmed = dict(
        sorted_history[:max_history]
    )

    print(
        f"Cleanup: removed "
        f"{len(history) - max_history} old entries"
    )

    return trimmed


# ============================================================
# GAME RESULT PROCESSING
# ============================================================

def determine_result(game):

    """
    Determine whether a completed game was:
        - a win for White
        - a win for Black
        - a draw
        - or still unfinished

    Returns a dictionary describing the result, or None if
    the game does not have a completed result yet.
    """

    white = game.get("white")
    black = game.get("black")

    # Make sure the expected player information exists.
    if not isinstance(white, dict):

        return None

    if not isinstance(black, dict):

        return None

    white_result = white.get("result")
    black_result = black.get("result")

    # White won.
    if white_result == "win":

        return {
            "winner": white["username"],
            "loser": black["username"],
            "draw": False
        }

    # Black won.
    if black_result == "win":

        return {
            "winner": black["username"],
            "loser": white["username"],
            "draw": False
        }

    # Both players have the same non-empty result.
    # This is how we identify a draw.
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

    # No completed result yet.
    return None


# ============================================================
# MATCH / GAME DISCOVERY
# ============================================================

def process_match(match):

    """
    Examine all boards/games belonging to a match.

    This function does NOT determine whether a game is new.
    It simply finds completed games and returns information
    about them.

    Returns:
        notifications = list of completed games
        score = current/final match score
    """

    match_id = match["@id"].split("/")[-1]

    data = fetch_match(match_id)

    if not data:

        return [], None

    print()
    print("MATCH:")
    print(data["name"])

    team1 = data["teams"]["team1"]
    team2 = data["teams"]["team2"]

    # Current score of the match.
    score = (
        f"{team1['name']}: {team1['score']}\n"
        f"{team2['name']}: {team2['score']}"
    )

    notifications = []

    # A player can potentially point to a board we've already
    # inspected, so keep track of boards we've processed.
    processed_games = set()
    processed_boards = set()

    # Examine both teams.
    for team in ["team1", "team2"]:

        for player in data["teams"][team]["players"]:

            board_url = player.get("board")

            # Some players may not have a board URL.
            if not board_url:

                continue

            # Don't fetch the same board twice.
            if board_url in processed_boards:

                continue

            processed_boards.add(board_url)

            board = fetch_board(board_url)

            if not board:

                continue

            # Examine every game on this board.
            for game in board.get("games", []):

                game_id = game["url"].split("/")[-1]

                # Don't process the same game twice if it appears
                # in more than one place.
                if game_id in processed_games:

                    continue

                result = determine_result(game)

                # Ignore games that haven't finished yet.
                if not result:

                    continue

                processed_games.add(game_id)

                # Determine which team the winner belongs to.
                winner_team = ""

                if not result["draw"]:

                    winner_username = result["winner"].lower()

                    for check_team in ["team1", "team2"]:

                        for check_player in data["teams"][check_team]["players"]:

                            if (
                                check_player["username"].lower()
                                == winner_username
                            ):

                                winner_team = (
                                    data["teams"][check_team]["name"]
                                )

                # Store the completed game's information.
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

    """
    Get the final result of a completed match.

    Returns information needed to send the match-completed
    Discord notification.
    """

    match_id = match["@id"].split("/")[-1]

    data = fetch_match(match_id)

    if not data:

        return None

    team1 = data["teams"]["team1"]
    team2 = data["teams"]["team2"]

    # Determine which team won the overall match.
    if team1["result"] == "win":

        winner = team1["name"]

    elif team2["result"] == "win":

        winner = team2["name"]

    else:

        # Neither team won, so the match was a draw.
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


# ============================================================
# DISCORD NOTIFICATIONS
# ============================================================

def send_game_update_notification(match_name, games, score):

    """
    Send a Discord notification for one or more newly completed
    games.

    This notification is separate from the match-completed
    notification.
    """

    webhook_url = os.environ.get(
        "DISCORD_WEBHOOK_URL"
    )

    if not webhook_url:

        return

    message = (
        f"♟️ **No Stress Chess Update**\n\n"
        f"⚔️ **Match:** {match_name}\n\n"
        f"📝 **Games completed since the last update:**\n\n"
    )

    for game in games:

        # Draw notification.
        if game["draw"]:

            message += (
                f"🤝 **Draw:** "
                f"**{game['player1']}** vs "
                f"**{game['player2']}**\n\n"
                f"🎮 {game['url']}\n\n"
            )

        # Win/loss notification.
        else:

            # 🎉 if our team won.
            # 😞 if our team lost.
            emoji = (
                "🎉"
                if game["result"] == "win"
                else "😞"
            )

            message += (
                f"{emoji} **{game['winner']}** defeated "
                f"**{game['loser']}**\n\n"
                f"🎮 {game['url']}\n\n"
            )

    # Include the current match score at the bottom.
    message += (
        f"🏆 **Daily Club Match Score:**\n"
        f"{score}\n"
    )

    requests.post(
        webhook_url,
        json={"content": message},
        timeout=10
    )


def send_match_notification(match):

    """
    Send a Discord notification when an entire match has finished.

    This is intentionally separate from individual game
    notifications.
    """

    webhook_url = os.environ.get(
        "DISCORD_WEBHOOK_URL"
    )

    if not webhook_url:

        return False

    # Overall match was a draw.
    if match["winner"] is None:

        emoji = "🤝"
        result = "ended in a draw"

    # Our team won the overall match.
    elif OUR_TEAM_NAME in match["winner"].lower():

        emoji = "🎉"
        result = f"{match['winner']} won"

    # Opposing team won the overall match.
    else:

        emoji = "😞"
        result = f"{match['winner']} won"

    message = (
        f"⚔️ **No Stress Chess Match Completed**\n\n"
        f"🏟️ **Match:** {match['match']}\n\n"
        f"{emoji} {result}\n\n"
        f"🏆 **Final Score:**\n"
        f"{match['score']}\n"
    )

    response = requests.post(
        webhook_url,
        json={"content": message},
        timeout=10
    )

    # Discord returns HTTP 204 when the webhook succeeds.
    return response.status_code == 204


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():

    print(datetime.now())

    print(
        f"Checking club: {CLUB_DISPLAY_NAME}"
    )

    # Load our history files.
    seen_games = load_seen_games()
    seen_matches = load_seen_matches()

    # Keep copies so we can determine whether anything changed
    # before deciding whether to write the files back to disk.
    original_seen_games = dict(seen_games)
    original_seen_matches = dict(seen_matches)

    # Get the club's matches from Chess.com.
    matches = fetch_club_matches()

    if not matches:

        print("No matches found")

        return

    game_notifications_sent = 0
    match_notifications_sent = 0


    # ========================================================
    # GAME NOTIFICATION HANDLER
    # ========================================================

    def handle_game_notifications(match):

        """
        Find all completed games in a match and determine which
        ones are new.

        A game is considered "new" if its ID is not already in
        seen_games.json.

        New games are:
            1. Added to seen_games
            2. Included in a Discord notification

        This function is used for BOTH active and finished
        matches.
        """

        nonlocal game_notifications_sent

        notifications, score = process_match(match)

        unseen_games = []

        for notification in notifications:

            game_id = notification["game_id"]

            # If we've already processed this game, don't send
            # another notification.
            if game_id in seen_games:

                continue

            # ------------------------------------------------
            # Draw
            # ------------------------------------------------

            if notification["draw"]:

                unseen_games.append(
                    {
                        "draw": True,
                        "player1": notification["player1"],
                        "player2": notification["player2"],
                        "url": notification["url"]
                    }
                )

            # ------------------------------------------------
            # Win / Loss
            # ------------------------------------------------

            else:

                # Check whether the winning player belongs to
                # our team.
                our_team_won = (
                    OUR_TEAM_NAME
                    in notification["winner_team"].lower()
                )

                unseen_games.append(
                    {
                        "draw": False,
                        "winner": notification["winner"],
                        "loser": notification["loser"],
                        "result": (
                            "win"
                            if our_team_won
                            else "loss"
                        ),
                        "url": notification["url"]
                    }
                )

            # IMPORTANT:
            #
            # Mark the game as seen immediately after adding it
            # to the notification list.
            #
            # This prevents the same game from being sent again
            # on the next GitHub Actions run.
            seen_games[game_id] = {
                "winner": notification["winner"],
                "loser": notification["loser"],
                "match": notification["match"],
                "date": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            }

        # If we found any games that weren't previously seen,
        # send them together in one Discord message.
        if unseen_games:

            send_game_update_notification(
                notifications[0]["match"],
                unseen_games,
                score
            )

            game_notifications_sent += len(unseen_games)


    # ========================================================
    # ACTIVE / IN-PROGRESS MATCHES
    # ========================================================

    active_matches = matches.get(
        "in_progress",
        []
    )

    print(
        f"Active matches found: {len(active_matches)}"
    )

    for match in active_matches:

        match_id = match["@id"].split("/")[-1]

        # Fetch the full match to verify its current status.
        actual_match = fetch_match(match_id)

        # Occasionally Chess.com can return a match in the
        # "in_progress" list even though its detailed status
        # has already changed to "finished".
        if (
            actual_match
            and actual_match.get("status") == "finished"
        ):

            print(
                f"Found finished match inside active list: {match_id}"
            )

            # ------------------------------------------------
            # IMPORTANT ORDER:
            #
            # Process games FIRST.
            #
            # Then process the overall match.
            # ------------------------------------------------

            handle_game_notifications(match)

            # Only send the match-completed notification if we
            # haven't already sent it.
            if match_id not in seen_matches:

                completed_match = process_completed_match(match)

                if completed_match:

                    if send_match_notification(completed_match):

                        match_notifications_sent += 1

                        seen_matches[match_id] = {
                            "match": completed_match["match"],
                            "date": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        }

            continue

        # Normal active match:
        #
        # Look for games that have finished since the previous
        # GitHub Actions run.
        handle_game_notifications(match)


    # ========================================================
    # FINISHED MATCHES
    # ========================================================

    finished_matches = matches.get(
        "finished",
        []
    )

    print(
        f"Finished matches found: {len(finished_matches)}"
    )

    for match in finished_matches:

        match_id = match["@id"].split("/")[-1]

        # ----------------------------------------------------
        # IMPORTANT FIX
        # ----------------------------------------------------
        #
        # We MUST process the games even if the match itself
        # has already been recorded in seen_matches.json.
        #
        # Why?
        #
        # A match can finish before our script has had a chance
        # to record its final games in seen_games.json.
        #
        # Previously, this code checked:
        #
        #     if match_id in seen_matches:
        #         continue
        #
        # BEFORE processing the games.
        #
        # That meant a match could have its match notification
        # sent while its individual game notifications were
        # completely skipped.
        #
        # Now games are processed FIRST.
        # ----------------------------------------------------

        handle_game_notifications(match)

        # ----------------------------------------------------
        # MATCH NOTIFICATION
        # ----------------------------------------------------
        #
        # Game processing and match processing are independent.
        #
        # Even if this match has already been recorded in
        # seen_matches.json, we still want the game processing
        # above to happen.
        #
        # But we don't want to send the overall match notification
        # twice.
        # ----------------------------------------------------

        if match_id in seen_matches:

            continue

        completed_match = process_completed_match(match)

        if completed_match:

            if send_match_notification(completed_match):

                match_notifications_sent += 1

                seen_matches[match_id] = {
                    "match": completed_match["match"],
                    "date": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                }


    # ========================================================
    # CLEAN UP HISTORY FILES
    # ========================================================

    # Keep only the most recent game records.
    seen_games = cleanup_history(
        seen_games,
        MAX_GAME_HISTORY
    )

    # Keep only the most recent match records.
    seen_matches = cleanup_history(
        seen_matches,
        MAX_MATCH_HISTORY
    )


    # ========================================================
    # OUTPUT SUMMARY
    # ========================================================

    print()

    print(
        f"New game notifications sent: {game_notifications_sent}"
    )

    print(
        f"New match notifications sent: {match_notifications_sent}"
    )


    # ========================================================
    # SAVE CHANGED FILES
    # ========================================================

    # Only rewrite seen_games.json if something actually changed.
    if seen_games != original_seen_games:

        save_seen_games(seen_games)

        print(
            "seen_games.json updated"
        )

    # Only rewrite seen_matches.json if something actually changed.
    if seen_matches != original_seen_matches:

        save_seen_matches(seen_matches)

        print(
            "seen_matches.json updated"
        )


# ============================================================
# PROGRAM ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()

