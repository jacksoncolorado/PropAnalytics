# ============================================================
# data_fetcher.py — EXTERNAL DATA RETRIEVAL LAYER
#
# This module is responsible for making HTTP requests to
# third-party APIs on behalf of the Flask application.
# It sits between the raw API providers and our route
# handlers / database: routes call functions here, and
# functions here call the outside world and (optionally)
# write results into the database defined in models.py.
#
# FUNCTIONS:
#   fetch_nba_odds()            → returns raw NBA game odds JSON
#                                 (consumed by routes/odds.py)
#   fetch_and_store_props()     → pulls player-prop odds from the API,
#                                 stores them as PlayerProp rows in the
#                                 database, and returns a summary dict
#                                 (consumed by POST /api/admin/fetch-props
#                                 in app.py)
#   fetch_and_store_gamelogs()  → pulls recent box-score stats from nba_api
#                                 for every Player in the database, writes
#                                 GameLog rows, and returns a summary dict
#                                 (consumed by POST /api/admin/fetch-gamelogs
#                                 in app.py)
#
# ENVIRONMENT VARIABLES REQUIRED:
#   ODDS_API_KEY — your key from https://the-odds-api.com
# ============================================================

import os       # used to read environment variables (e.g. ODDS_API_KEY)
import logging  # standard Python logger — used instead of print so log
                # level and output destination can be controlled globally
from datetime import datetime  # used to set fetched_at on PlayerProp rows

import requests  # used to make HTTP GET requests to external APIs

from extensions import db          # SQLAlchemy instance — used for db.session
from models import Game, Player, PlayerProp, GameLog  # database models we read/write


# Module-level logger.  The name mirrors the module so log messages are
# easily traceable: look for "data_fetcher" in your server output.
logger = logging.getLogger(__name__)


# ============================================================
# PROP MARKET GROUP DEFINITIONS
#
# The Odds API limits the number of markets per request.
# We split the full set of player-prop markets into four groups
# (A–D) and make one API call per group per game.  This keeps
# each call focused and conserves API credits.
#
# These lists are used by fetch_and_store_props() below.
# ============================================================

# Group A — standard single-stat over/under props.
# These map 1-to-1 to the stat columns on GameLog in models.py
# (except player_double_double, which is a derived stat).
MARKET_GROUP_A = (
    "player_points,player_rebounds,player_assists,"
    "player_threes,player_blocks,player_steals,"
    "player_turnovers,player_double_double"
)

# Group B — combo props that combine multiple stats.
# e.g. "player_points_rebounds_assists" = PRA (points + rebounds + assists).
# The screener in routes/screener.py detects these via the COMBO_PROP_MAP
# and calls combo_hit_rate() from analytics.py instead of hit_rate().
MARKET_GROUP_B = (
    "player_points_rebounds_assists,player_points_rebounds,"
    "player_points_assists,player_rebounds_assists"
)

# Group C — alternate lines for single-stat props.
# Same stats as Group A but with wider line choices and different odds.
# fetch_and_store_props() sets is_alternate=True on these PlayerProp rows.
MARKET_GROUP_C = (
    "player_points_alternate,player_rebounds_alternate,"
    "player_assists_alternate,player_threes_alternate,"
    "player_blocks_alternate,player_steals_alternate,"
    "player_turnovers_alternate"
)

# Group D — alternate lines for combo props.
# Same combos as Group B but with alternate lines.
MARKET_GROUP_D = (
    "player_points_rebounds_assists_alternate,"
    "player_points_rebounds_alternate,"
    "player_points_assists_alternate,"
    "player_rebounds_assists_alternate"
)

# All four groups collected so we can iterate over them easily.
MARKET_GROUPS = [MARKET_GROUP_A, MARKET_GROUP_B, MARKET_GROUP_C, MARKET_GROUP_D]


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
# ------------------------------------------------------------------
def fetch_nba_odds():
    # --- 1. READ THE API KEY ---
    # os.getenv returns None (not an exception) if the variable
    # is missing, so we check for it explicitly before making
    # any network call.
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        logger.error("ODDS_API_KEY is not set in the environment.")
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
        logger.error("Network error while fetching NBA odds: %s", e)
        return None

    # --- 4. CHECK THE HTTP STATUS CODE ---
    # 200 = success; anything else (401 bad key, 429 rate limit,
    # 500 server error) means we cannot use the response body.
    if response.status_code != 200:
        logger.error(
            "The Odds API returned status %d: %s",
            response.status_code,
            response.text,
        )
        return None

    # --- 5. PARSE AND RETURN THE JSON ---
    # response.json() converts the raw response body into a
    # Python list/dict that Flask can later serialise back to
    # JSON for the frontend.
    return response.json()


# ------------------------------------------------------------------
# _fetch_event_props()   (internal helper)
#
# PURPOSE:
#   Fetch player-prop odds for a single NBA game (identified by
#   its Odds API event_id) for one market group.
#
# HOW IT FITS IN:
#   Called by fetch_and_store_props() below — once for each of
#   the four MARKET_GROUPS per game.  Keeps the main function
#   readable and separates HTTP concerns from DB concerns.
#
# RETURNS:
#   dict  — parsed JSON on success (the event object with
#           bookmaker prop data).
#   None  — on any failure.
# ------------------------------------------------------------------
def _fetch_event_props(event_id: str, markets: str, api_key: str) -> dict | None:
    """Fetch prop odds for one event and one market group."""

    url = (
        f"https://api.the-odds-api.com/v4/sports/basketball_nba"
        f"/events/{event_id}/odds"
    )

    params = {
        "regions": "us",
        "markets": markets,
        "oddsFormat": "american",
        "apiKey": api_key,
    }

    try:
        response = requests.get(url, params=params, timeout=15)
    except requests.exceptions.RequestException as e:
        logger.error(
            "Network error fetching props for event %s, markets [%s]: %s",
            event_id, markets[:40], e,
        )
        return None

    if response.status_code != 200:
        logger.error(
            "Odds API returned %d for event %s, markets [%s]: %s",
            response.status_code, event_id, markets[:40], response.text[:200],
        )
        return None

    return response.json()


# ------------------------------------------------------------------
# fetch_and_store_props()
#
# PURPOSE:
#   The main prop-ingestion pipeline.  Pulls every player-prop
#   line for today's NBA games from The Odds API and writes them
#   into the PlayerProp table (models.py).
#
# HOW IT FITS IN THE APP:
#   Called by POST /api/admin/fetch-props in app.py.
#   That route is the manual trigger a developer or admin uses
#   to refresh the odds data.  After this function returns, the
#   screener endpoint (GET /api/screener/props in routes/screener.py)
#   can query the freshly-stored PlayerProp rows.
#
# HIGH-LEVEL FLOW:
#   1. Hit the games endpoint (h2h only) to get today's games.
#   2. For each game, upsert a Game row using odds_event_id.
#   3. For each game, make 4 API calls (one per market group).
#   4. For each bookmaker → market → outcome pair, upsert a
#      PlayerProp row (auto-creating the Player if needed).
#   5. Commit after each game is fully processed.
#   6. Return a summary dict { games_processed, props_stored, errors }.
#
# MUST RUN INSIDE FLASK APP CONTEXT:
#   This function uses db.session (from extensions.py) and queries
#   SQLAlchemy models, so it must be called from within
#   app.app_context().  The POST route in app.py handles that
#   automatically because Flask routes run inside the context.
#
# RETURNS:
#   dict with keys:
#     games_processed : int — number of games we iterated over
#     props_stored    : int — total PlayerProp rows inserted
#     errors          : list[str] — human-readable error messages
# ------------------------------------------------------------------
def fetch_and_store_props() -> dict:
    # --- 1. VALIDATE THE API KEY ---
    api_key = os.getenv('ODDS_API_KEY')
    if not api_key:
        logger.error("ODDS_API_KEY is not set — cannot fetch props.")
        return {"games_processed": 0, "props_stored": 0, "errors": ["ODDS_API_KEY not set"]}

    errors = []       # accumulate non-fatal error messages
    games_processed = 0
    props_stored = 0

    # --- 2. FETCH TODAY'S NBA GAMES ---
    # We request only h2h (moneyline) because we just need the game list.
    # The actual player-prop markets come from the per-event calls below.
    games_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
    games_params = {
        "regions": "us",
        "markets": "h2h",
        "oddsFormat": "american",
        "apiKey": api_key,
    }

    try:
        games_resp = requests.get(games_url, params=games_params, timeout=15)
    except requests.exceptions.RequestException as e:
        msg = f"Network error fetching games list: {e}"
        logger.error(msg)
        return {"games_processed": 0, "props_stored": 0, "errors": [msg]}

    if games_resp.status_code != 200:
        msg = f"Games endpoint returned {games_resp.status_code}: {games_resp.text[:200]}"
        logger.error(msg)
        return {"games_processed": 0, "props_stored": 0, "errors": [msg]}

    games_data = games_resp.json()
    logger.info("Found %d NBA games from The Odds API.", len(games_data))

    # --- 3. PROCESS EACH GAME ---
    for game_obj in games_data:
        event_id = game_obj.get("id")
        home_team = game_obj.get("home_team", "Unknown")
        away_team = game_obj.get("away_team", "Unknown")

        # --- 3a. UPSERT THE GAME ROW ---
        # Look up by odds_event_id to avoid creating duplicate Game rows
        # for the same real-world game.  If found, update mutable fields
        # (team names may change in API responses, e.g. due to formatting).
        # If not found, create a new Game row.
        game_record = Game.query.filter_by(odds_event_id=event_id).first()
        if game_record:
            # Update existing Game record with latest data from the API
            # so we don't leave stale metadata in the database.
            game_record.home_team = home_team
            game_record.away_team = away_team
        else:
            game_record = Game(
                home_team=home_team,
                away_team=away_team,
                odds_event_id=event_id,
                game_date=datetime.utcnow(),
            )
            db.session.add(game_record)
        # Flush so game_record.id is available for PlayerProp FK below.
        db.session.flush()

        game_props_count = 0  # props stored for this game

        # --- 3b. FETCH PROPS FOR EACH MARKET GROUP ---
        # Each group is a comma-separated string of market keys.
        # We make one API call per group (4 calls per game).
        for group in MARKET_GROUPS:
            event_data = _fetch_event_props(event_id, group, api_key)
            if event_data is None:
                errors.append(f"Failed to fetch group [{group[:30]}…] for event {event_id}")
                continue

            # --- 3c. EXTRACT BOOKMAKER → MARKET → OUTCOMES ---
            # The Odds API response structure:
            #   { "bookmakers": [ { "key": "draftkings", "markets": [ { "key": "player_points", "outcomes": [...] } ] } ] }
            bookmakers = event_data.get("bookmakers", [])
            for bookmaker_obj in bookmakers:
                bookmaker_key = bookmaker_obj.get("key", "unknown")

                for market_obj in bookmaker_obj.get("markets", []):
                    market_key = market_obj.get("key", "")  # e.g. "player_points"

                    # Determine if this is an alternate-line prop.
                    # The Odds API appends "_alternate" to the market key for alt lines.
                    is_alt = "alternate" in market_key

                    # --- 3d. PAIR OVER/UNDER OUTCOMES ---
                    # The Odds API returns outcomes as a flat list.  For player props
                    # each outcome has a "description" (player name), a "name" (Over/Under),
                    # a "price" (American odds), and a "point" (the line value).
                    # We need to group by (player_name, line_value) to pair the Over and Under.
                    outcomes = market_obj.get("outcomes", [])

                    # Build a lookup: (player_name, point) → {over_odds, under_odds}
                    paired = {}
                    for outcome in outcomes:
                        player_name = outcome.get("description", "")
                        point = outcome.get("point")       # the line value (float)
                        price = outcome.get("price")       # American odds (int)
                        side = outcome.get("name", "")     # "Over" or "Under"

                        if not player_name or point is None or price is None:
                            continue

                        pair_key = (player_name, point)
                        if pair_key not in paired:
                            paired[pair_key] = {"over_odds": None, "under_odds": None}

                        if side == "Over":
                            paired[pair_key]["over_odds"] = price
                        elif side == "Under":
                            paired[pair_key]["under_odds"] = price

                    # --- 3e. WRITE PLAYER PROP ROWS ---
                    for (player_name, point), odds_pair in paired.items():

                        # Look up the player by name.  If not found, auto-create a
                        # minimal Player row so we can store the prop.  Team/position
                        # will be NULL until filled by another data source.
                        player = Player.query.filter_by(name=player_name).first()
                        if not player:
                            player = Player(name=player_name)
                            db.session.add(player)
                            db.session.flush()  # get player.id

                        # Delete any existing prop for the same combination to
                        # avoid duplicates when the pipeline is run multiple times.
                        PlayerProp.query.filter_by(
                            player_id=player.id,
                            game_id=game_record.id,
                            prop_type=market_key,
                            bookmaker=bookmaker_key,
                            line_value=point,
                        ).delete()

                        # Create the new PlayerProp row with fresh data.
                        prop = PlayerProp(
                            player_id=player.id,
                            game_id=game_record.id,
                            prop_type=market_key,
                            line_value=point,
                            over_odds=odds_pair["over_odds"],
                            under_odds=odds_pair["under_odds"],
                            is_alternate=is_alt,
                            bookmaker=bookmaker_key,
                            fetched_at=datetime.utcnow(),
                        )
                        db.session.add(prop)
                        game_props_count += 1

        # --- 3f. COMMIT AFTER EACH GAME ---
        # Committing per-game means a failure on game N+1 doesn't
        # roll back the props already stored for games 1 through N.
        try:
            db.session.commit()
            games_processed += 1
            props_stored += game_props_count
            logger.info(
                "Committed %d props for %s vs %s (event %s).",
                game_props_count, away_team, home_team, event_id,
            )
        except Exception as e:
            db.session.rollback()
            msg = f"DB commit failed for event {event_id}: {e}"
            logger.error(msg)
            errors.append(msg)

    # --- 4. RETURN SUMMARY ---
    # The POST /api/admin/fetch-props route in app.py returns this
    # dict directly as JSON to the caller.
    logger.info(
        "fetch_and_store_props complete: %d games, %d props, %d errors.",
        games_processed, props_stored, len(errors),
    )
    return {
        "games_processed": games_processed,
        "props_stored": props_stored,
        "errors": errors,
    }


# ------------------------------------------------------------------
# fetch_and_store_gamelogs()
#
# Pulls recent box-score stats from nba_api for every Player in the
# DB and writes GameLog rows. Called by POST /api/admin/fetch-gamelogs.
# Returns { players_updated, players_skipped, errors }.
# ------------------------------------------------------------------
def fetch_and_store_gamelogs() -> dict:
    import time
    from nba_api.stats.endpoints import commonallplayers, playergamelog

    errors = []
    players_updated = 0
    players_skipped = 0

    # Determine the current NBA season string dynamically.
    # NBA seasons span two calendar years (e.g. "2024-25").
    # If we're before October, the current season started the previous year.
    now = datetime.utcnow()
    season_start_year = now.year if now.month >= 10 else now.year - 1
    season_str = f"{season_start_year}-{str(season_start_year + 1)[-2:]}"
    logger.info("Using NBA season: %s", season_str)

    try:
        all_players_response = commonallplayers.CommonAllPlayers(
            is_only_current_season=1
        )
        all_players_df = all_players_response.get_data_frames()[0]
    except Exception as e:
        msg = f"Failed to fetch CommonAllPlayers from nba_api: {e}"
        logger.error(msg)
        return {"players_updated": 0, "players_skipped": 0, "errors": [msg]}

    nba_name_to_id = {}
    for _, row in all_players_df.iterrows():
        display_name = row.get("DISPLAY_FIRST_LAST", "")
        person_id = row.get("PERSON_ID")
        if display_name and person_id:
            nba_name_to_id[display_name.lower()] = int(person_id)

    logger.info("Built nba_api name lookup with %d players.", len(nba_name_to_id))

    db_players = Player.query.all()
    logger.info("Found %d players in our database to process.", len(db_players))

    for player in db_players:
        nba_id = nba_name_to_id.get(player.name.lower())
        if nba_id is None:
            logger.warning("Could not find '%s' in nba_api — skipping.", player.name)
            players_skipped += 1
            continue

        try:
            time.sleep(0.6)
            gamelog_response = playergamelog.PlayerGameLog(
                player_id=nba_id,
                season=season_str,
            )
            gamelog_df = gamelog_response.get_data_frames()[0]
        except Exception as e:
            msg = f"Failed to fetch game log for '{player.name}' (nba_id={nba_id}): {e}"
            logger.error(msg)
            errors.append(msg)
            continue

        if gamelog_df.empty:
            logger.info("No %s game logs for '%s' — skipping.", season_str, player.name)
            players_skipped += 1
            continue

        recent_games = gamelog_df.head(15)

        games_written = 0
        for _, game_row in recent_games.iterrows():
            matchup = game_row.get("MATCHUP", "")
            game_date_str = game_row.get("GAME_DATE", "")

            if " vs. " in matchup:
                parts = matchup.split(" vs. ")
                home_team = parts[0].strip()
                away_team = parts[1].strip()
            elif " @ " in matchup:
                parts = matchup.split(" @ ")
                away_team = parts[0].strip()
                home_team = parts[1].strip()
            else:
                home_team = matchup
                away_team = "UNK"

            try:
                game_date = datetime.strptime(game_date_str, "%b %d, %Y")
            except (ValueError, TypeError):
                game_date = datetime.utcnow()

            game_record = Game.query.filter(
                Game.home_team == home_team,
                Game.away_team == away_team,
                db.func.date(Game.game_date) == game_date.date(),
            ).first()

            if not game_record:
                game_record = Game(
                    home_team=home_team,
                    away_team=away_team,
                    game_date=game_date,
                )
                db.session.add(game_record)
                db.session.flush()

            min_played_raw = game_row.get("MIN", 0)
            try:
                if isinstance(min_played_raw, str) and ":" in min_played_raw:
                    minutes_played = int(min_played_raw.split(":")[0])
                else:
                    minutes_played = int(float(min_played_raw))
            except (ValueError, TypeError):
                minutes_played = 0

            existing_log = GameLog.query.filter_by(
                player_id=player.id,
                game_id=game_record.id,
            ).first()

            stat_vals = {
                "points": int(game_row.get("PTS", 0)),
                "rebounds": int(game_row.get("REB", 0)),
                "assists": int(game_row.get("AST", 0)),
                "threes": int(game_row.get("FG3M", 0)),
                "blocks": int(game_row.get("BLK", 0)),
                "steals": int(game_row.get("STL", 0)),
                "turnovers": int(game_row.get("TOV", 0)),
                "minutes_played": minutes_played,
            }

            if existing_log:
                for k, v in stat_vals.items():
                    setattr(existing_log, k, v)
            else:
                new_log = GameLog(
                    player_id=player.id,
                    game_id=game_record.id,
                    **stat_vals,
                )
                db.session.add(new_log)

            games_written += 1

        if games_written > 0:
            players_updated += 1
            logger.info(
                "Wrote %d game logs for '%s' (nba_id=%d).",
                games_written, player.name, nba_id,
            )

    # --- 4. COMMIT ALL CHANGES ---
    try:
        db.session.commit()
        logger.info(
            "fetch_and_store_gamelogs complete: %d updated, %d skipped, %d errors.",
            players_updated, players_skipped, len(errors),
        )
    except Exception as e:
        db.session.rollback()
        msg = f"DB commit failed during game log ingestion: {e}"
        logger.error(msg)
        errors.append(msg)

    # --- 5. RETURN SUMMARY ---
    # POST /api/admin/fetch-gamelogs in app.py returns this dict as JSON.
    return {
        "players_updated": players_updated,
        "players_skipped": players_skipped,
        "errors": errors,
    }

# ------------------------------------------------------------------
# DATA FETCHER FUNCTION: backfill_player_meta()
#
# PURPOSE:
#   Populate missing player metadata (team and position) for existing
#   Player records in the database using nba_api.
#
# HOW IT FITS IN:
#   This function is called by the admin route:
#     POST /api/admin/backfill-player-meta
#
#   It iterates over all Player rows and:
#     1. Skips players that already have both team and position
#     2. Uses nba_api static lookup to find a matching NBA player ID
#     3. Calls CommonPlayerInfo to retrieve detailed metadata
#     4. Updates the Player table with team and position
#
# WHY THIS IS NEEDED:
#   Player records created during prop ingestion often only contain
#   names. The Odds API does not reliably provide team or position,
#   so this function enriches the database after the fact.
#
# OUTPUT:
#   Returns a summary dict:
#     {
#       status,
#       players_checked,
#       players_updated,
#       players_skipped,
#       errors
#     }
#
# After this function runs, player pages will display team and
# position correctly instead of placeholders.
# ------------------------------------------------------------------
def backfill_player_meta():
    from models import Player, db
    from nba_api.stats.static import players as nba_players
    from nba_api.stats.endpoints import commonplayerinfo
    import time

    updated = 0
    checked = 0
    skipped = 0
    errors = []

    all_players = Player.query.all()

    for player in all_players:
        checked += 1

        if player.team and player.position:
            skipped += 1
            continue

        try:
            matches = nba_players.find_players_by_full_name(player.name)

            if not matches:
                errors.append(f"No static match for {player.name}")
                continue

            nba_match = matches[0]
            nba_player_id = nba_match["id"]

            info = commonplayerinfo.CommonPlayerInfo(player_id=nba_player_id)
            df = info.get_data_frames()[0]

            if df.empty:
                errors.append(f"No CommonPlayerInfo rows for {player.name}")
                continue

            row = df.iloc[0]

            team_name = row.get("TEAM_NAME")
            position = row.get("POSITION")

            if team_name:
                player.team = str(team_name)

            if position:
                player.position = str(position)

            updated += 1

            # Avoid rate limiting from NBA stats endpoints
            time.sleep(0.6)

        except Exception as e:
            errors.append(f"{player.name}: {str(e)}")

    db.session.commit()

    return {
        "status": "success",
        "players_checked": checked,
        "players_updated": updated,
        "players_skipped": skipped,
        "errors": errors[:25]
    }
