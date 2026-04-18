# ============================================================
# routes/player.py — PLAYER PAGE & PLAYER DATA ROUTES
#
# Routes:
#   GET /              → home page (index.html)
#   GET /player/<name> → player detail page (player.html)
#   GET /api/player/<player_name>          → season averages JSON
#   GET /api/player/<int:player_id>/gamelogs → last 15 game logs JSON
#   GET /api/player/<int:player_id>/props    → props + hit rates JSON
# ============================================================

from flask import Blueprint, render_template, jsonify
from models import Player, GameLog, PlayerProp, Game
from sqlalchemy import desc
from extensions import db
from datetime import datetime, date, timezone

bp = Blueprint('player', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/api/player/<player_name>')
def get_player(player_name):
    player = Player.query.filter(
        Player.name.ilike(player_name.replace("-", " "))
    ).first()

    if not player:
        return jsonify({
            "name": player_name,
            "points_per_game": 0,
            "rebounds_per_game": 0,
            "assists_per_game": 0,
            "message": "Player not found in database"
        })

    logs = GameLog.query.filter_by(player_id=player.id).all()

    if not logs:
        return jsonify({
            "name": player.name,
            "points_per_game": 0,
            "rebounds_per_game": 0,
            "assists_per_game": 0,
            "message": "No game log data available yet"
        })

    total_games = len(logs)
    ppg = round(sum(log.points for log in logs) / total_games, 1)
    rpg = round(sum(log.rebounds for log in logs) / total_games, 1)
    apg = round(sum(log.assists for log in logs) / total_games, 1)

    return jsonify({
        "name": player.name,
        "team": player.team,
        "position": player.position,
        "nba_player_id": player.nba_player_id,
        "nba_team_id": player.nba_team_id,
        "points_per_game": ppg,
        "rebounds_per_game": rpg,
        "assists_per_game": apg,
    })


@bp.route('/player/<player_name>')
def player_page(player_name):
    """Render the player detail page, passing player_id for JS API calls."""
    player = Player.query.filter(
        Player.name.ilike(player_name.replace("-", " "))
    ).first()

    player_id = player.id if player else None

    display_name = player.name if player else player_name.replace("-", " ").title()

    return render_template(
        'player.html',
        player_name=display_name,
        player_id=player_id,
    )


@bp.route('/api/player/<int:player_id>/gamelogs')
def get_player_gamelogs(player_id):
    """Return the 15 most recent GameLog rows ordered by game date desc."""
    player = Player.query.get(player_id)
    if not player:
        return jsonify({"error": "Player not found"}), 404

    logs = (
        GameLog.query
        .join(Game, GameLog.game_id == Game.id)
        .filter(GameLog.player_id == player_id)
        .order_by(desc(Game.game_date))
        .limit(15)
        .all()
    )

    results = []
    for log in logs:
        game = log.game
        date_str = game.game_date.strftime("%Y-%m-%d") if game and game.game_date else "N/A"
        opponent = f"{game.away_team} @ {game.home_team}" if game else "N/A"

        results.append({
            "date": date_str,
            "opponent": opponent,
            "points": log.points,
            "rebounds": log.rebounds,
            "assists": log.assists,
            "threes": log.threes,
            "blocks": log.blocks,
            "steals": log.steals,
            "turnovers": log.turnovers,
            "minutes_played": log.minutes_played,
        })

    return jsonify(results)


@bp.route('/api/player/<int:player_id>/props')
def get_player_props(player_id):
    """Return all PlayerProp rows for a player, enriched with hit_rate data."""
    from analytics import hit_rate

    player = Player.query.get(player_id)
    if not player:
        return jsonify({"error": "Player not found"}), 404

    props = PlayerProp.query.filter_by(player_id=player_id).all()
    valid_stats = {'points', 'rebounds', 'assists', 'threes', 'blocks', 'steals', 'turnovers'}

    results = []
    for prop in props:
        stat_name = prop.prop_type.replace("player_", "").replace("_alternate", "")

        hr_data = None
        if stat_name in valid_stats:
            try:
                hr_data = hit_rate(player_id, stat_name, prop.line_value)
            except ValueError:
                hr_data = None

        results.append({
            "prop_type": prop.prop_type,
            "line_value": prop.line_value,
            "over_odds": prop.over_odds,
            "under_odds": prop.under_odds,
            "hit_rate": hr_data,
        })

    return jsonify(results)

@bp.route('/api/players/today')
def get_players_today():
    """Return players with props today grouped by team, for header dropdowns."""
    from data_fetcher import fetch_nba_odds
    from datetime import date

    # Get today's teams from the Odds API
    odds_data = fetch_nba_odds()
    today_str = date.today().isoformat()
    today_teams = set()

    if odds_data:
        from datetime import datetime, timezone, timedelta
        mountain_offset = timedelta(hours=-6)  # MDT (Mountain Daylight Time)
        now_mountain = datetime.now(timezone.utc) + mountain_offset
        today_mountain = now_mountain.date()
        for game in odds_data:
            commence = game.get('commence_time', '')
            if not commence:
                continue
            try:
                game_dt_utc = datetime.strptime(commence[:19], '%Y-%m-%dT%H:%M:%S')
                game_dt_mountain = game_dt_utc + mountain_offset
                if game_dt_mountain.date() == today_mountain:
                    today_teams.add(game.get('home_team'))
                    today_teams.add(game.get('away_team'))
            except ValueError:
                continue

    # Filter players to only those on today's teams
    props_today = PlayerProp.query.all()
    player_ids = list(set(p.player_id for p in props_today))
    players = Player.query.filter(Player.id.in_(player_ids)).all()

    teams = {}
    for player in players:
        team = player.team or 'Unknown'
        if team not in today_teams:
            continue
        if team not in teams:
            teams[team] = []
        teams[team].append({
            'id': player.id,
            'name': player.name,
        })

    for team in teams:
        teams[team].sort(key=lambda p: p['name'])

    result = sorted([
        {'team': team, 'players': players_list}
        for team, players_list in teams.items()
    ], key=lambda t: t['team'])

    return jsonify(result)