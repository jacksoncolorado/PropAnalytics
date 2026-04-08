# ============================================================
# routes/screener.py — PROP SCREENER BLUEPRINT
#
# Exposes a single endpoint that lets the frontend (or any API
# consumer) filter the PlayerProp table by odds range and prop
# type, then score each result with a historical hit rate and
# trend direction.
#
# HOW IT FITS IN THE APP:
#   1. fetch_and_store_props() in data_fetcher.py populates the
#      PlayerProp table with data from The Odds API.
#   2. This screener READS those PlayerProp rows, combines them
#      with GameLog-based analytics (hit_rate / combo_hit_rate /
#      trend from analytics.py), and returns a ranked JSON list.
#   3. screener_bp is imported and registered in app.py.
#
# ENDPOINT:
#   GET /api/screener/props — returns filtered, ranked props
# ============================================================

import logging

from flask import Blueprint, jsonify, request  # request gives us query params

from datetime import datetime, timezone
from models import PlayerProp, Player, Game
from analytics import hit_rate, combo_hit_rate, trend # analytics functions


# Module-level logger — messages show as "routes.screener" in server output.
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# COMBO PROP MAPPING
#
# The Odds API uses market keys like "player_points_rebounds_assists"
# for combo props.  To calculate a combo hit rate we need to know
# which individual stats to sum.  This dict maps each combo market
# key (with the "player_" prefix and possible "_alternate" suffix
# stripped) to the list of base GameLog stat columns.
#
# Used by _parse_stat_columns() below to decide whether to call
# hit_rate() (single stat) or combo_hit_rate() (multi stat).
# ------------------------------------------------------------------
COMBO_PROP_MAP = {
    "points_rebounds_assists": ["points", "rebounds", "assists"],
    "points_rebounds":         ["points", "rebounds"],
    "points_assists":          ["points", "assists"],
    "rebounds_assists":        ["rebounds", "assists"],
}

# Single-stat props map to exactly one GameLog column.
SINGLE_STAT_MAP = {
    "points":    "points",
    "rebounds":  "rebounds",
    "assists":   "assists",
    "threes":    "threes",
    "blocks":    "blocks",
    "steals":    "steals",
    "turnovers": "turnovers",
}


# ------------------------------------------------------------------
# _parse_stat_columns(prop_type)
#
# PURPOSE:
#   Given a full Odds API prop_type string (e.g. "player_points" or
#   "player_points_rebounds_assists_alternate"), determine whether
#   it is a single stat or a combo, and return the corresponding
#   GameLog column name(s).
#
# RETURNS:
#   ("single", "points")                              — for single stats
#   ("combo", ["points", "rebounds", "assists"])       — for combo stats
#   (None, None)                                      — if unrecognized
#
# HOW IT FITS IN:
#   Called by the GET /api/screener/props handler below for each
#   PlayerProp row to decide which analytics function to invoke.
# ------------------------------------------------------------------
def _parse_stat_columns(prop_type: str):
    """Parse a prop_type market key into a stat mode and column name(s)."""

    # Strip the "player_" prefix and "_alternate" suffix to get the
    # core stat descriptor (e.g. "points_rebounds_assists").
    core = prop_type
    if core.startswith("player_"):
        core = core[len("player_"):]
    if core.endswith("_alternate"):
        core = core[: -len("_alternate")]

    # Check combo map first (longer keys match first to avoid false
    # positives against single-stat keys).
    if core in COMBO_PROP_MAP:
        return "combo", COMBO_PROP_MAP[core]

    # Check single-stat map.
    if core in SINGLE_STAT_MAP:
        return "single", SINGLE_STAT_MAP[core]

    # Unrecognized prop type (e.g. "player_double_double").
    # We cannot compute a hit rate for these, so we return None.
    return None, None


# ------------------------------------------------------------------
# CREATE THE BLUEPRINT
#
# Registered in app.py via app.register_blueprint(screener_bp).
# The url_prefix means every route here starts with /api/screener.
# ------------------------------------------------------------------
screener_bp = Blueprint('screener', __name__, url_prefix='/api/screener')


# ------------------------------------------------------------------
# ROUTE: GET /api/screener/props
#
# PURPOSE:
#   The main prop-screener endpoint.  Lets the frontend filter
#   stored player props by odds range and prop type, calculates a
#   historical hit rate for each, filters by minimum hit rate,
#   attaches a trend direction, and returns a sorted JSON array.
#
# QUERY PARAMETERS:
#   min_odds     (int,   default -300) — minimum American odds
#   max_odds     (int,   default  300) — maximum American odds
#   min_hit_rate (float, default 0.0)  — minimum hit rate (0.0–1.0)
#   sample_size  (int,   default 20)   — games to look back
#   stat         (str,   optional)     — filter by prop_type
#   side         (str,   default "over") — "over" or "under"
#
# RESPONSE (success — 200):
#   JSON array sorted by hit_rate descending, each element:
#   {
#     "player_name": "LeBron James",
#     "prop_type":   "player_points",
#     "line_value":  25.5,
#     "over_odds":   -110,
#     "under_odds":  -110,
#     "bookmaker":   "draftkings",
#     "is_alternate": false,
#     "hit_rate":     0.70,
#     "hit_rate_pct": "70.0%",
#     "trend":        "up",
#     "games_used":   20
#   }
#
# RESPONSE (error — 400):
#   JSON { "error": "..." }
# ------------------------------------------------------------------
def _get_game_time(game_id):
    if not game_id:
        return None
    game = Game.query.get(game_id)
    if not game or not game.game_date:
        return None
    return game.game_date.strftime("%-I:%M %p")

@screener_bp.route('/props', methods=['GET'])
def get_screener_props():
    # --- 1. PARSE QUERY PARAMETERS ---
    # request.args gives us the URL query string as a dict-like object.
    # We cast each to the correct type with sensible defaults.
    try:
        min_odds = int(request.args.get('min_odds', -300))
        max_odds = int(request.args.get('max_odds', 300))
        min_hit_rate_val = float(request.args.get('min_hit_rate', 0.0))
        sample_size = int(request.args.get('sample_size', 20))
    except (ValueError, TypeError) as e:
        return jsonify({"error": f"Invalid query parameter: {e}"}), 400

    stat_filter = request.args.get('stat')  # optional — may be None
    side = request.args.get('side', 'over')  # "over" or "under"

    if side not in ('over', 'under'):
        return jsonify({"error": "side must be 'over' or 'under'."}), 400

    # --- 2. QUERY PLAYER PROPS FROM THE DATABASE ---
    # Start with a base query on the PlayerProp table (defined in models.py,
    # populated by fetch_and_store_props() in data_fetcher.py).
    query = PlayerProp.query

    # Filter by the odds column that matches the requested side.
    # "over" → filter on over_odds;  "under" → filter on under_odds.
    if side == 'over':
        query = query.filter(
            PlayerProp.over_odds.isnot(None),
            PlayerProp.over_odds >= min_odds,
            PlayerProp.over_odds <= max_odds,
        )
    else:
        query = query.filter(
            PlayerProp.under_odds.isnot(None),
            PlayerProp.under_odds >= min_odds,
            PlayerProp.under_odds <= max_odds,
        )

    # Optionally filter by prop_type if the caller specified a stat.
    if stat_filter:
        query = query.filter(PlayerProp.prop_type == stat_filter)

    props = query.all()
    logger.info("Screener query returned %d raw props.", len(props))

    # --- 3. SCORE EACH PROP WITH HIT RATE + TREND ---
    results = []
    for prop in props:
        # Look up the player name for the response JSON.
        player = Player.query.get(prop.player_id)
        player_name = player.name if player else "Unknown"

        # Determine whether this prop is single-stat or combo-stat
        # so we know which analytics function to call.
        mode, stat_cols = _parse_stat_columns(prop.prop_type)

        if mode == "single":
            # --- Single-stat hit rate ---
            # Call hit_rate() from analytics.py with the stat column
            # name and the prop's line_value.
            try:
                hr = hit_rate(prop.player_id, stat_cols, prop.line_value, sample_size)
            except ValueError:
                continue  # skip if stat is somehow invalid
        elif mode == "combo":
            # --- Combo hit rate ---
            # Call combo_hit_rate() from analytics.py with the list
            # of stat columns to sum before checking against the line.
            hr = combo_hit_rate(prop.player_id, stat_cols, prop.line_value, sample_size)
        else:
            # Unrecognized prop type (e.g. player_double_double).
            # We cannot compute a hit rate, so skip this prop.
            continue

        # Skip props with no game data or below the minimum hit rate.
        if hr["hit_rate"] is None:
            continue
        if hr["hit_rate"] < min_hit_rate_val:
            continue

        # --- Get trend direction ---
        # trend() from analytics.py returns a dict with "direction"
        # ("up", "down", "flat", or "N/A").  For combo props we use
        # the first stat in the list for the trend signal.
        trend_stat = stat_cols if mode == "single" else stat_cols[0]
        try:
            tr = trend(prop.player_id, trend_stat, sample_size)
            trend_direction = tr.get("direction", "N/A")
        except ValueError:
            trend_direction = "N/A"

        # --- Build the result object ---
        # This is the JSON shape the frontend expects from the screener.
        results.append({
            "player_name":  player_name,
            "prop_type":    prop.prop_type,
            "line_value":   prop.line_value,
            "over_odds":    prop.over_odds,
            "under_odds":   prop.under_odds,
            "bookmaker":    prop.bookmaker,
            "is_alternate": prop.is_alternate,
            "hit_rate":     hr["hit_rate"],
            "hit_rate_pct": hr["hit_rate_pct"],
            "trend":        trend_direction,
            "games_used":   hr["games_used"],
            "fetched_at":   prop.fetched_at.strftime("%-I:%M %p") if prop.fetched_at else None,
            "game_time":    _get_game_time(prop.game_id),
        })

    # --- 4. SORT BY HIT RATE DESCENDING ---
    # Best props (highest hit rate) come first in the list.
    results.sort(key=lambda r: r["hit_rate"], reverse=True)

    logger.info("Screener returning %d scored props (after min_hit_rate filter).", len(results))
    latest_fetch = None
    if results:
        fetched_times = [r["fetched_at"] for r in results if r["fetched_at"]]
        if fetched_times:
            latest_fetch = fetched_times[0]

    return jsonify({
        "results": results,
        "fetched_at": latest_fetch
    }), 200
