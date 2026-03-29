# ============================================================
# models.py — DATABASE SCHEMA DEFINITIONS
#
# Every table the app uses is defined here as a SQLAlchemy model.
# Flask-SQLAlchemy reads these classes and creates the
# corresponding SQLite tables when db.create_all() runs in app.py.
#
# MODELS:
#   Game       — one NBA game (home vs away), linked to odds_event_id
#                so we can match The Odds API events to our records.
#   Player     — one NBA player (name, team, position).
#   PlayerProp — one betting prop line from a bookmaker for a player
#                in a specific game.  Populated by
#                fetch_and_store_props() in data_fetcher.py.
#   GameLog    — one row of actual box-score stats for a player in a
#                game.  Used by hit_rate() / combo_hit_rate() in
#                analytics.py to calculate how often a player clears
#                a prop line.
# ============================================================

from extensions import db
from datetime import datetime


class Game(db.Model):
    """
    Represents a single NBA game.

    The odds_event_id column is the bridge between our internal game
    records and The Odds API: when fetch_and_store_props() in
    data_fetcher.py pulls games from the API, it stores the API's
    event ID here so we can look up (or create) the correct Game row
    without duplicating entries.
    """
    __tablename__ = 'games'

    id = db.Column(db.Integer, primary_key=True)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    game_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20))

    # --- ODDS API LINK ---
    # The Odds API assigns every game a unique event ID string
    # (e.g. "a1b2c3d4e5f6...").  We store it here so that
    # fetch_and_store_props() in data_fetcher.py can match incoming
    # API data to the correct Game row and avoid creating duplicates.
    # Nullable because games loaded from other sources (e.g. nba_api)
    # may not have an Odds API event ID.
    odds_event_id = db.Column(db.String(100), nullable=True)

    # --- RELATIONSHIPS ---
    # One game has many box-score logs and many prop lines.
    logs = db.relationship('GameLog', backref='game', lazy=True)
    props = db.relationship('PlayerProp', backref='game', lazy=True)


class Player(db.Model):
    """
    Represents an NBA player.

    Players can be created automatically by fetch_and_store_props()
    in data_fetcher.py when a player name from the API doesn't match
    any existing record.  In that case only the name is set; team and
    position remain NULL until filled in by another data source.
    """
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team = db.Column(db.String(50))
    position = db.Column(db.String(20))

    # --- RELATIONSHIPS ---
    # One player has many box-score logs and many prop lines.
    logs = db.relationship('GameLog', backref='player', lazy=True)
    props = db.relationship('PlayerProp', backref='player', lazy=True)


class PlayerProp(db.Model):
    """
    One betting prop line from a single bookmaker for a player in a game.

    POPULATED BY:
      fetch_and_store_props() in data_fetcher.py — it loops through
      every bookmaker → market → outcome pair returned by The Odds API
      and creates one PlayerProp row per unique (player, game, prop_type,
      bookmaker, line_value) combination.

    CONSUMED BY:
      GET /api/screener/props in routes/screener.py — it queries this
      table, filters by odds range / prop_type, and then calls
      hit_rate() or combo_hit_rate() from analytics.py to score each
      prop before returning results to the frontend.
    """
    __tablename__ = 'player_props'

    id = db.Column(db.Integer, primary_key=True)

    # --- FOREIGN KEYS ---
    # Link this prop to exactly one player and one game.
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)

    # --- PROP DETAILS ---
    # prop_type stores the full Odds API market key, e.g.
    # "player_points", "player_points_alternate",
    # "player_points_rebounds_assists".  The screener uses this to
    # decide whether to call hit_rate() or combo_hit_rate().
    prop_type = db.Column(db.String(100))

    # line_value is the number the player must exceed, e.g. 25.5.
    # The screener passes this to hit_rate() / combo_hit_rate() as
    # the "line" argument.
    line_value = db.Column(db.Float)

    # over_odds / under_odds are American-format odds (e.g. -110, +120).
    # The screener filters on whichever side (over or under) the user
    # selected, using the min_odds / max_odds query parameters.
    over_odds = db.Column(db.Integer)
    under_odds = db.Column(db.Integer)

    # is_alternate is True when prop_type contains "alternate"
    # (e.g. "player_points_alternate").  Alternate lines typically
    # have wider odds and more line choices than standard props.
    # Set automatically by fetch_and_store_props() in data_fetcher.py.
    is_alternate = db.Column(db.Boolean, default=False)

    # bookmaker stores which sportsbook offered this line, e.g.
    # "draftkings", "fanduel".  Each bookmaker may offer different
    # lines/odds for the same prop, so we store them separately.
    bookmaker = db.Column(db.String(50))

    # fetched_at records when this row was pulled from the API.
    # Useful for showing how stale the data is or for pruning old props.
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)


class GameLog(db.Model):
    """
    One row of actual box-score stats for a player in a game.

    POPULATED BY:
      External data ingestion (e.g. nba_api) — not yet implemented
      in this codebase, but the table is ready.

    CONSUMED BY:
      _get_game_logs() in analytics.py — it reads stat columns from
      this table to supply values for hit_rate(), combo_hit_rate(),
      and trend().  The screener endpoint in routes/screener.py
      ultimately depends on this data to calculate hit rates.
    """
    __tablename__ = 'game_logs'

    id = db.Column(db.Integer, primary_key=True)

    # --- FOREIGN KEYS ---
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)

    # --- CORE STAT COLUMNS ---
    # These three are the original stats the app tracked.
    # hit_rate() and trend() in analytics.py read these via
    # getattr(log, stat) where stat is a string like "points".
    points = db.Column(db.Integer, default=0)
    rebounds = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)

    # --- EXPANDED STAT COLUMNS ---
    # Added to support the full set of Odds API prop markets.
    # threes   → "player_threes" / "player_threes_alternate" props
    # blocks   → "player_blocks" / "player_blocks_alternate" props
    # steals   → "player_steals" / "player_steals_alternate" props
    # turnovers→ "player_turnovers" / "player_turnovers_alternate" props
    # All default to 0 so existing rows remain valid after migration.
    threes = db.Column(db.Integer, default=0)
    blocks = db.Column(db.Integer, default=0)
    steals = db.Column(db.Integer, default=0)
    turnovers = db.Column(db.Integer, default=0)

    # minutes_played is metadata — not used for prop analysis but
    # useful for filtering out garbage-time or DNP entries.
    minutes_played = db.Column(db.Integer)

    def __repr__(self):
        return f"<GameLog Player:{self.player_id} Game:{self.game_id}>"
