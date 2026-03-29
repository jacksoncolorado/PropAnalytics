# ============================================================
# data_fetcher.py — EXTERNAL DATA RETRIEVAL LAYER
#
# This module is responsible for making HTTP requests to
# third-party APIs on behalf of the Flask application.
# It sits between the raw API providers and our route
# handlers: routes call functions here, and functions here
# call the outside world.
#
# Currently implemented:
#   - fetch_nba_odds()  → The Odds API (game-level markets)
#
# The route that consumes fetch_nba_odds() lives in:
#   backend/routes/odds.py  (odds_bp blueprint)
# ============================================================

import os       # used to read environment variables (e.g. ODDS_API_KEY)
import requests # used to make HTTP GET requests to external APIs


# ------------------------------------------------------------------
# fetch_nba_odds()
#
# PURPOSE:
#   Retrieve current NBA game odds from The Odds API for three
#   standard betting markets: moneyline (h2h), point spread
#   (spreads), and game total (totals).
#
# HOW IT FITS IN THE APP:
#   Called by GET /api/odds/games inside routes/odds.py.
#   That route simply passes whatever this function returns
#   straight to the frontend as JSON, so the return value
#   must be JSON-serialisable (a list of game dicts) or None.
#
# RETURNS:
#   list  — parsed JSON from The Odds API on success.
#           Each element is a dict describing one game and its
#           bookmaker odds.
#   None  — on any failure (network error, bad status code,
#           missing API key).  The caller is responsible for
#           turning None into a user-facing error response.
#
# ENVIRONMENT VARIABLES REQUIRED:
#   ODDS_API_KEY  — your key from https://the-odds-api.com
#                   Set this in your .env file; it is loaded
#                   automatically by load_dotenv() in app.py
#                   before this function is ever called.
# ------------------------------------------------------------------
def fetch_nba_odds():
    # --- 1. READ THE API KEY ---
    # os.getenv returns None (not an exception) if the variable
    # is missing, so we check for it explicitly before making
    # any network call.
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        print("[data_fetcher] ERROR: ODDS_API_KEY is not set in the environment.")
        return None

    # --- 2. BUILD THE REQUEST ---
    # The Odds API endpoint for NBA game-level markets.
    # See: https://the-odds-api.com/liveapi/guides/v4/
    base_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"

    # Query parameters sent alongside the URL.
    # regions=us        → only US sportsbooks (DraftKings, FanDuel, etc.)
    # markets=h2h,...   → h2h=moneyline, spreads=point spread, totals=over/under
    # oddsFormat=american → odds expressed as +110 / -110, not decimals
    # apiKey            → authenticates the request
    params = {
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "apiKey": api_key,
    }

    # --- 3. MAKE THE REQUEST ---
    try:
        response = requests.get(base_url, params=params, timeout=10)
        # timeout=10 prevents the app from hanging forever if
        # The Odds API is slow or unreachable.

    except requests.exceptions.RequestException as e:
        # Catches every network-level failure: DNS errors,
        # connection refused, timeout, SSL errors, etc.
        print(f"[data_fetcher] Network error while fetching NBA odds: {e}")
        return None

    # --- 4. CHECK THE HTTP STATUS CODE ---
    # 200 = success; anything else (401 bad key, 429 rate limit,
    # 500 server error) means we cannot use the response body.
    if response.status_code != 200:
        print(
            f"[data_fetcher] The Odds API returned status {response.status_code}: "
            f"{response.text}"
        )
        return None

    # --- 5. PARSE AND RETURN THE JSON ---
    # response.json() converts the raw response body into a
    # Python list/dict that Flask can later serialise back to
    # JSON for the frontend.
    return response.json()
