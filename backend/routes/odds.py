# ============================================================
# routes/odds.py — ODDS BLUEPRINT
#
# This file defines the Flask Blueprint called odds_bp and
# exposes two API endpoints that the frontend can call to
# get live betting data from The Odds API.
#
# HOW IT FITS IN THE APP:
#   - odds_bp is imported and registered in app.py, which
#     makes these routes reachable by the browser.
#   - Game-level odds are fetched via fetch_nba_odds() from
#     data_fetcher.py (keeps HTTP logic out of route handlers).
#   - Player-prop odds are fetched inline here because the
#     event_id comes from the URL and must be interpolated
#     into the endpoint path at request time.
#
# ENDPOINTS PROVIDED:
#   GET /api/odds/games            → all current NBA game odds
#   GET /api/odds/props/<event_id> → player props for one game
# ============================================================

import os       # reads ODDS_API_KEY from the environment
import logging  # structured logging — avoids bare print() calls

import requests # makes HTTP requests to The Odds API

from flask import Blueprint, jsonify  # Blueprint groups routes; jsonify converts dicts to HTTP JSON responses

# Import the game-level fetcher from our data layer.
# data_fetcher.py centralises all outbound HTTP calls so that
# route handlers stay thin and focused on request/response logic.
from data_fetcher import fetch_nba_odds


# Module-level logger — messages show up as "routes.odds" in server output,
# making them easy to filter when debugging.
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# CREATE THE BLUEPRINT
#
# A Blueprint is Flask's way of grouping related routes into a
# reusable module.  It is registered on the main app in app.py
# via app.register_blueprint(odds_bp).
#
# name='odds'       → internal identifier used by url_for()
# __name__          → tells Flask where this file lives so it
#                     can resolve any template/static paths
# url_prefix        → every route in this blueprint is prefixed
#                     with /api/odds, so /games becomes /api/odds/games
# ------------------------------------------------------------------
odds_bp = Blueprint('odds', __name__, url_prefix='/api/odds')


# ------------------------------------------------------------------
# ROUTE: GET /api/odds/games
#
# PURPOSE:
#   Return a JSON array of all current NBA games with their
#   available odds (moneyline, spread, total) from The Odds API.
#
# HOW IT WORKS:
#   1. First checks that ODDS_API_KEY is present so we can
#      return a precise 500 (server misconfiguration) vs a 502
#      (upstream API failure) — the caller deserves to know
#      which kind of problem occurred.
#   2. Delegates the actual HTTP call to fetch_nba_odds() in
#      data_fetcher.py, which handles params, timeout, and errors.
#   3. If fetch_nba_odds() returns None (network / API failure),
#      this route responds with 502 (Bad Gateway) JSON error so
#      the frontend knows the data source is unavailable.
#   4. On success, the raw list from The Odds API is forwarded
#      as-is — no transformation needed at this stage.
#
# RESPONSE (success):
#   200 OK  — JSON array, each element is a game object with
#             bookmaker odds from The Odds API schema.
#
# RESPONSE (failure):
#   500 Internal Server Error — ODDS_API_KEY not configured
#   502 Bad Gateway           — network error or non-200 from API
# ------------------------------------------------------------------
@odds_bp.route('/games', methods=['GET'])
def get_games():
    # --- Guard: verify the API key exists before delegating ---
    # Checking here (in addition to inside fetch_nba_odds) lets us
    # return a 500 (our misconfiguration) rather than a 502 (upstream
    # failure), giving the client a more accurate picture of the fault.
    if not os.getenv('ODDS_API_KEY'):
        logger.error("GET /api/odds/games called but ODDS_API_KEY is not configured.")
        return jsonify({"error": "ODDS_API_KEY is not configured on the server."}), 500

    # Call the data layer; it handles the network request and
    # returns the parsed list, or None on any failure.
    odds_data = fetch_nba_odds()

    if odds_data is None:
        # fetch_nba_odds() already logged the specific cause.
        # We return 502 (upstream server error) because the problem
        # is with the external API, not our own code.
        return jsonify({"error": "Failed to fetch NBA odds. Check server logs for details."}), 502

    # Forward the raw JSON from The Odds API directly to the client.
    # jsonify wraps any list/dict in a proper HTTP JSON response.
    return jsonify(odds_data), 200


# ------------------------------------------------------------------
# ROUTE: GET /api/odds/props/<event_id>
#
# PURPOSE:
#   Return player-prop odds for a single NBA game identified by
#   its Odds API event ID.  Markets included: player points,
#   player rebounds, player assists.
#
# URL PARAMETER:
#   event_id (str) — The Odds API's unique identifier for a game.
#                    Obtain these IDs from the /api/odds/games
#                    endpoint above (each game object has an "id"
#                    field — pass that value here).
#
# HOW IT WORKS:
#   1. Reads ODDS_API_KEY from the environment (same key used by
#      fetch_nba_odds() in data_fetcher.py).
#   2. Builds the event-specific Odds API URL by interpolating
#      event_id into the path.
#   3. Makes a direct GET request with player-prop markets.
#   4. Returns JSON on success, or a clear error response on any
#      failure (missing key, bad event_id, network issue).
#
# WHY NOT USE data_fetcher.py HERE:
#   fetch_nba_odds() targets a fixed endpoint (all games).
#   This route's endpoint includes a dynamic event_id, so it
#   performs its own request inline rather than forcing
#   data_fetcher.py to accept parameters it doesn't need.
#
# RESPONSE (success):
#   200 OK  — JSON object from The Odds API with bookmaker
#             player-prop lines for the requested game.
#
# RESPONSE (failure):
#   500 Internal Server Error — API key missing from environment
#   502 Bad Gateway           — network error or non-200 from API
# ------------------------------------------------------------------
@odds_bp.route('/props/<string:event_id>', methods=['GET'])
def get_props(event_id):
    # --- 1. READ THE API KEY ---
    # Same key used by data_fetcher.py; stored in .env and loaded
    # at startup by load_dotenv() in app.py.
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        logger.error("GET /api/odds/props/%s called but ODDS_API_KEY is not configured.", event_id)
        return jsonify({"error": "ODDS_API_KEY is not configured on the server."}), 500

    # --- 2. BUILD THE EVENT-SPECIFIC ENDPOINT ---
    # The Odds API structures player-prop data under a per-event
    # path that embeds the event ID directly in the URL.
    url = (
        f"https://api.the-odds-api.com/v4/sports/basketball_nba"
        f"/events/{event_id}/odds"
    )

    # Query parameters:
    # regions=us              → US sportsbooks only
    # markets=player_points,… → the three player-prop market types
    # oddsFormat=american     → +/- American odds format
    # apiKey                  → authentication
    params = {
        "regions": "us",
        "markets": "player_points,player_rebounds,player_assists",
        "oddsFormat": "american",
        "apiKey": api_key,
    }

    # --- 3. MAKE THE REQUEST ---
    try:
        response = requests.get(url, params=params, timeout=10)
        # timeout=10 prevents hanging if The Odds API is slow.

    except requests.exceptions.RequestException as e:
        # Covers DNS failures, connection refused, timeouts, SSL errors.
        logger.error("Network error fetching props for event %s: %s", event_id, e)
        return jsonify({"error": "Network error while fetching player props."}), 502

    # --- 4. CHECK STATUS ---
    # 404 from The Odds API typically means the event_id is invalid
    # or the game is no longer listed.  We surface the status code
    # in the error message so the frontend can react appropriately.
    if response.status_code != 200:
        logger.error(
            "The Odds API returned %d for event %s: %s",
            response.status_code,
            event_id,
            response.text,
        )
        return jsonify({
            "error": f"The Odds API returned status {response.status_code}.",
            "event_id": event_id,
        }), 502

    # --- 5. RETURN THE PARSED RESPONSE ---
    # Forward the JSON from The Odds API directly to the caller.
    return jsonify(response.json()), 200
