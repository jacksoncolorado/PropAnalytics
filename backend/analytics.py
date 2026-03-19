# ============================================================
# analytics.py — CORE ANALYTICS ENGINE
#
# Two main capabilities:
#   1. hit_rate()   — how often a player has cleared a prop line
#   2. trend()      — whether their stats are trending up or down
#
# Both work from GameLog records already stored in the database.
# Statistics include the last 20 games rather than the season.
# 
# ============================================================

from models import GameLog, Player
from sqlalchemy import desc


# ---------------------------------------------------------------------------
# INTERNAL HELPER
# ---------------------------------------------------------------------------

def _get_game_logs(player_id: int, stat: str, n_games: int = 20) -> list[float]:
    """
    Fetch the most recent n_games stat values for a player, ordered oldest-first.

    stat must be one of: 'points', 'rebounds', 'assists'
    Returns a list of numeric values (floats).  Empty list if no data.
    """
    valid_stats = {'points', 'rebounds', 'assists'}
    if stat not in valid_stats:
        raise ValueError(f"stat must be one of {valid_stats}, got '{stat}'")

    logs = (
        GameLog.query
        .filter_by(player_id=player_id)
        .order_by(desc(GameLog.id))
        .limit(n_games)
        .all()
    )

    if not logs:
        return []

    values = [float(getattr(log, stat)) for log in logs]
    values.reverse()
    return values


# ---------------------------------------------------------------------------
# HIT RATE
# ---------------------------------------------------------------------------

def hit_rate(player_id: int, stat: str, line: float, n_games: int = 20) -> dict:
    """
    Calculate how often a player has exceeded a prop line.

    Parameters
    ----------
    player_id : int
        Primary key of the player in the database.
    stat : str
        One of 'points', 'rebounds', 'assists'.
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
# TREND ANALYSIS
# ---------------------------------------------------------------------------

def trend(player_id: int, stat: str, n_games: int = 20) -> dict:
    """
    Compare a player's recent performance against their earlier performance
    to detect upward or downward trends.

    The window is split in half: older half vs newer half.
    If n_games is odd the extra game goes to the newer half.

    Parameters
    ----------
    player_id : int
    stat : str  — one of 'points', 'rebounds', 'assists'
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
