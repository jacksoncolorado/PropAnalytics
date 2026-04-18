# ============================================================
# analytics.py — CORE ANALYTICS ENGINE
#
# Three main capabilities:
#   1. hit_rate()       — how often a player has cleared a single-stat prop line
#   2. combo_hit_rate() — how often a player has cleared a multi-stat combo line
#   3. trend()          — whether a player's stats are trending up or down
#
# All three work from GameLog records already stored in the database.
# They look at the last N games (default 20) rather than a full season.
#
# CONSUMED BY:
#   routes/analytics.py (analytics_bp)   — exposes hit_rate / prop_report via API
#   routes/screener.py  (screener_bp)    — calls hit_rate / combo_hit_rate to
#                                          score every prop returned by the screener
#
# DATA SOURCE:
#   GameLog rows in models.py, populated externally (e.g. via nba_api ingestion).
# ============================================================

from models import GameLog, Player, Game
from sqlalchemy import desc


# ---------------------------------------------------------------------------
# INTERNAL HELPER
# ---------------------------------------------------------------------------

def _get_game_logs(player_id: int, stat: str, n_games: int = 20) -> list[float]:
    """
    Fetch the most recent n_games stat values for a player, ordered oldest-first.

    HOW IT FITS IN:
      This is the single data-access function that every public analytics
      function calls.  It reads one stat column from the GameLog table
      defined in models.py.  The stat name must exactly match a column
      on GameLog (e.g. 'points', 'threes', 'steals').

    PARAMETERS:
      player_id : int   — primary key of the Player in the database
      stat      : str   — must be one of the valid stat column names
      n_games   : int   — how many recent games to look back (default 20)

    RETURNS:
      list[float] — stat values ordered oldest → newest.  Empty list if
                     the player has no game logs in the database.

    RAISES:
      ValueError — if stat is not in the valid set
    """
    # All seven stat columns that exist on the GameLog model in models.py.
    # Points, rebounds, assists were the original three; threes, blocks,
    # steals, turnovers were added to support the expanded Odds API markets.
    valid_stats = {'points', 'rebounds', 'assists', 'threes', 'blocks', 'steals', 'turnovers'}
    if stat not in valid_stats:
        raise ValueError(f"stat must be one of {valid_stats}, got '{stat}'")

    # Query the most recent n_games GameLog rows for this player.
    # order_by(desc(GameLog.id)) gives us newest-first; we reverse below
    # so the caller gets oldest-first (easier for trend analysis).
    logs = (
        GameLog.query
        .join(Game, GameLog.game_id == Game.id)
        .filter(GameLog.player_id == player_id)
        .order_by(desc(Game.game_date))
        .limit(n_games)
        .all()
    )

    if not logs:
        return []

    # Pull out the single stat column as a float and reverse to
    # oldest-first order for consistent downstream processing.
    values = [float(getattr(log, stat)) for log in logs]
    values.reverse()
    return values


# ---------------------------------------------------------------------------
# HIT RATE (single stat)
# ---------------------------------------------------------------------------

def hit_rate(player_id: int, stat: str, line: float, n_games: int = 20) -> dict:
    """
    Calculate how often a player has exceeded a single-stat prop line.

    HOW IT FITS IN:
      Called by:
        - GET /api/analytics/hit-rate/… in routes/analytics.py
        - GET /api/screener/props      in routes/screener.py (for non-combo props)
      The "line" value typically comes from a PlayerProp.line_value in models.py.

    Parameters
    ----------
    player_id : int
        Primary key of the player in the database.
    stat : str
        One of the valid GameLog stat columns (e.g. 'points', 'threes').
    line : float
        The prop line to test against (e.g. 25.5).
    n_games : int
        How many recent games to look back (default 20).

    Returns
    -------
    dict with keys:
        player_id   : int
        stat        : str
        line        : float
        games_used  : int   — how many games were actually found
        hits        : int   — games where stat > line
        misses      : int
        hit_rate    : float — hits / games_used (0.0–1.0), or None if no data
        hit_rate_pct: str   — e.g. "70.0%" or "N/A"
        values      : list[float] — raw game values (oldest → newest)
    """
    values = _get_game_logs(player_id, stat, n_games)

    if not values:
        return {
            "player_id": player_id,
            "stat": stat,
            "line": line,
            "games_used": 0,
            "hits": 0,
            "misses": 0,
            "hit_rate": None,
            "hit_rate_pct": "N/A",
            "values": [],
        }

    hits = sum(1 for v in values if v > line)
    misses = len(values) - hits
    rate = hits / len(values)

    return {
        "player_id": player_id,
        "stat": stat,
        "line": line,
        "games_used": len(values),
        "hits": hits,
        "misses": misses,
        "hit_rate": round(rate, 4),
        "hit_rate_pct": f"{rate * 100:.1f}%",
        "values": values,
    }


# ---------------------------------------------------------------------------
# HIT RATE (combo / multi-stat)
# ---------------------------------------------------------------------------

def combo_hit_rate(player_id: int, stats: list, line: float, n_games: int = 20) -> dict:
    """
    Calculate how often a player has exceeded a COMBINED multi-stat prop line.

    HOW IT FITS IN:
      Called by GET /api/screener/props in routes/screener.py for combo
      props like "player_points_rebounds_assists".  The screener detects
      combo props by checking if the prop_type maps to multiple stat
      columns, then calls this function instead of hit_rate().

    LOGIC:
      1. Fetch game logs for each stat separately using _get_game_logs().
      2. Align them by index (same game position in the list).
      3. Sum the values per game to get a combined total.
      4. Count how many combined totals exceed the line — same math as
         hit_rate() uses for a single stat.

    EXAMPLE:
      combo_hit_rate(42, ['points', 'rebounds', 'assists'], 35.5)
      → sums pts + reb + ast per game, checks how many times > 35.5

    Parameters
    ----------
    player_id : int
        Primary key of the player in the database.
    stats : list[str]
        List of stat names to combine, e.g. ['points', 'rebounds', 'assists'].
        Each must be a valid GameLog stat column.
    line : float
        The combined prop line to test against (e.g. 35.5 for PRA).
    n_games : int
        How many recent games to look back (default 20).

    Returns
    -------
    dict — same shape as hit_rate(), but with:
        stat set to "+".join(stats), e.g. "points+rebounds+assists"
        values containing the per-game summed totals
    """
    # --- 1. FETCH LOGS FOR EACH STAT ---
    # _get_game_logs returns oldest-first lists, all the same length
    # (limited to n_games).  If any stat returns empty, we have no data.
    all_stat_values = []
    for s in stats:
        vals = _get_game_logs(player_id, s, n_games)
        all_stat_values.append(vals)

    # Build a friendly label like "points+rebounds+assists" for display
    # and for the screener to echo back to the frontend.
    combined_stat_name = "+".join(stats)

    # --- 2. HANDLE MISSING DATA ---
    # If any individual stat returns no logs, we cannot compute a
    # meaningful combined value.
    if not all_stat_values or any(len(v) == 0 for v in all_stat_values):
        return {
            "player_id": player_id,
            "stat": combined_stat_name,
            "line": line,
            "games_used": 0,
            "hits": 0,
            "misses": 0,
            "hit_rate": None,
            "hit_rate_pct": "N/A",
            "values": [],
        }

    # --- 3. SUM VALUES PER GAME ---
    # Use the shortest list length in case different stats have
    # different numbers of logged games.
    min_len = min(len(v) for v in all_stat_values)
    combined_values = []
    for i in range(min_len):
        game_total = sum(v[i] for v in all_stat_values)
        combined_values.append(game_total)

    # --- 4. COMPUTE HIT RATE (same formula as hit_rate()) ---
    hits = sum(1 for v in combined_values if v > line)
    misses = len(combined_values) - hits
    rate = hits / len(combined_values)

    return {
        "player_id": player_id,
        "stat": combined_stat_name,
        "line": line,
        "games_used": len(combined_values),
        "hits": hits,
        "misses": misses,
        "hit_rate": round(rate, 4),
        "hit_rate_pct": f"{rate * 100:.1f}%",
        "values": combined_values,
    }


# ---------------------------------------------------------------------------
# TREND ANALYSIS
# ---------------------------------------------------------------------------

def trend(player_id: int, stat: str, n_games: int = 20) -> dict:
    """
    Compare a player's recent performance against their earlier performance
    to detect upward or downward trends.

    The window is split in half: older half vs newer half.
    If n_games is odd the extra game goes to the newer half.

    HOW IT FITS IN:
      Called by:
        - GET /api/analytics/prop-report/… in routes/analytics.py
        - GET /api/screener/props          in routes/screener.py
          (to attach a "trend" direction to each screener result)

    Parameters
    ----------
    player_id : int
    stat : str  — one of the valid GameLog stat columns
    n_games : int — default 20

    Returns
    -------
    dict with keys:
        player_id       : int
        stat            : str
        games_used      : int
        avg_early       : float — average in older half of games
        avg_recent      : float — average in newer half of games
        avg_overall     : float — average across all games
        delta           : float — avg_recent - avg_early (positive = trending up)
        direction       : str   — 'up', 'down', or 'flat'
        early_values    : list[float]
        recent_values   : list[float]
    """
    values = _get_game_logs(player_id, stat, n_games)

    if not values:
        return {
            "player_id": player_id,
            "stat": stat,
            "games_used": 0,
            "avg_early": None,
            "avg_recent": None,
            "avg_overall": None,
            "delta": None,
            "direction": "N/A",
            "early_values": [],
            "recent_values": [],
        }

    mid = len(values) // 2
    early = values[:mid]
    recent = values[mid:]

    avg_early = sum(early) / len(early) if early else 0.0
    avg_recent = sum(recent) / len(recent) if recent else 0.0
    avg_overall = sum(values) / len(values)
    delta = avg_recent - avg_early

    if abs(delta) < 0.5:
        direction = "flat"
    elif delta > 0:
        direction = "up"
    else:
        direction = "down"

    return {
        "player_id": player_id,
        "stat": stat,
        "games_used": len(values),
        "avg_early": round(avg_early, 2),
        "avg_recent": round(avg_recent, 2),
        "avg_overall": round(avg_overall, 2),
        "delta": round(delta, 2),
        "direction": direction,
        "early_values": early,
        "recent_values": recent,
    }


# ---------------------------------------------------------------------------
# COMBINED REPORT
# ---------------------------------------------------------------------------

def prop_report(player_id: int, stat: str, line: float, n_games: int = 20) -> dict:
    """
    One-call convenience wrapper that returns both hit rate and trend data
    together, plus a short plain-English summary.

    HOW IT FITS IN:
      Called by GET /api/analytics/prop-report/… in routes/analytics.py.

    Returns
    -------
    dict with keys:
        player_id   : int
        stat        : str
        line        : float
        hit_rate    : dict  — full hit_rate() result
        trend       : dict  — full trend() result
        summary     : str   — plain-English interpretation
    """
    hr = hit_rate(player_id, stat, line, n_games)
    tr = trend(player_id, stat, n_games)

    if hr["games_used"] == 0:
        summary = "No game log data available for this player."
    else:
        summary = (
            f"Over the last {hr['games_used']} games, this player has gone "
            f"over {line} {stat} in {hr['hits']} of them ({hr['hit_rate_pct']}). "
            f"Their {stat} average is {tr['avg_overall']} and the trend is "
            f"{tr['direction']} ({'+' if (tr['delta'] or 0) >= 0 else ''}"
            f"{tr['delta']} vs earlier stretch)."
        )

    return {
        "player_id": player_id,
        "stat": stat,
        "line": line,
        "hit_rate": hr,
        "trend": tr,
        "summary": summary,
    }
