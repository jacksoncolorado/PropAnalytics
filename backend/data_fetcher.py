# ============================================================
# data_fetcher.py — Fetch NBA stats via nba_api and populate DB
# ============================================================

from nba_api.stats.static import players as nba_players
from nba_api.stats.endpoints import playergamelog, leaguegamefinder
from extensions import db
from models import Player, Game, GameLog
from datetime import datetime

# -----------------------------
# Load Players into DB
# -----------------------------
def load_players():
    all_players = nba_players.get_players()

    for p in all_players:
        # Check if already in DB by nba_id
        player = Player.query.filter_by(nba_id=p['id']).first()
        if not player:
            player = Player(
                nba_id=p['id'],
                name=p['full_name'],
                team=None,  # will populate later
                position=None
            )
            db.session.add(player)

    db.session.commit()
    print(f"✅ Loaded {len(all_players)} players")


# -----------------------------
# Load Games into DB
# -----------------------------
def load_games():
    # Fetch recent games (all-time optional)
    games_df = leaguegamefinder.LeagueGameFinder().get_data_frames()[0]

    for _, row in games_df.iterrows():
        # Check if already exists
        game = Game.query.filter_by(nba_game_id=row['GAME_ID']).first()
        if not game:
            # Parse teams from matchup string
            matchup = row['MATCHUP']  # e.g. "LAL @ BOS" or "BOS vs. LAL"
            if "@" in matchup:
                away_team, home_team = matchup.split(" @ ")
            elif "vs." in matchup:
                home_team, away_team = matchup.split(" vs. ")
            else:
                home_team = row['TEAM_ABBREVIATION']
                away_team = None

            game = Game(
                nba_game_id=row['GAME_ID'],
                home_team=home_team,
                away_team=away_team,
                game_date=row['GAME_DATE'],
                status=row['WL']  # simple placeholder
            )
            db.session.add(game)

    db.session.commit()
    print(f"✅ Loaded {len(games_df)} games")


# -----------------------------
# Load Player Game Logs into DB
# -----------------------------
def load_game_logs(limit_players=None):
    """
    Pull each player's recent game logs and save in DB.
    limit_players = int → optional, number of players to fetch (for testing)
    """
    query = Player.query
    if limit_players:
        query = query.limit(limit_players)

    players = query.all()
    print(f"🔄 Loading game logs for {len(players)} players")

    for player in players:
        try:
            logs_df = playergamelog.PlayerGameLog(player_id=player.nba_id).get_data_frames()[0]

            for _, row in logs_df.iterrows():
                # Find game in DB
                game = Game.query.filter_by(nba_game_id=row['Game_ID']).first()
                if not game:
                    continue  # skip if game not in DB

                # Skip duplicates
                existing = GameLog.query.filter_by(player_id=player.id, game_id=game.id).first()
                if existing:
                    continue

                log = GameLog(
                    player_id=player.id,
                    game_id=game.id,
                    points=row['PTS'],
                    rebounds=row['REB'],
                    assists=row['AST'],
                    minutes_played=int(row['MIN']) if row['MIN'] else None
                )
                db.session.add(log)

            db.session.commit()
        except Exception as e:
            print(f"⚠️ Error loading logs for {player.name}: {e}")

    print("✅ Game logs loaded")


# -----------------------------
# Master function to run all
# -----------------------------
def run_all(limit_players=None):
    print("🚀 Starting data fetcher...")
    load_players()
    load_games()
    load_game_logs(limit_players=limit_players)
    print("🎉 Data fetcher complete!")