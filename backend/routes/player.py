# ============================================================
# routes/player_routes.py — PLAYER PAGE ROUTES
# For example: /player/lebron-james loads the player page for LeBron.
# ============================================================

from flask import Blueprint, render_template, jsonify
# Blueprint = a way to group related routes together
# render_template = loads an HTML file and sends it to the browser
# jsonify = converts Python data (dicts/lists) into JSON for the frontend JS to use

# Create a blueprint called 'player' — this groups all player-related routes
bp = Blueprint('player', __name__)

# --- HOME PAGE ROUTE ---
@bp.route('/')
def index():
    # render_template looks in frontend/templates/ for index.html
    return render_template('index.html')

# --- PLAYER SEARCH ROUTE ---
# When the frontend JS calls /api/player/<name>, return that player's stats as JSON
# <player_name> is a variable — whatever the user types becomes the player_name
@bp.route('/api/player/<player_name>')
def get_player(player_name):
    # TODO: Replace this placeholder with a real nba_api call
    # For now this just returns fake data so the app runs without errors
    placeholder_data = {
        "name": player_name,
        "points_per_game": 0,
        "rebounds_per_game": 0,
        "assists_per_game": 0,
        "message": "Real stats coming soon — connect nba_api here"
    }
    # jsonify converts the Python dictionary above into a JSON response
    return jsonify(placeholder_data)

# --- PLAYER DETAIL PAGE ROUTE ---
# When someone visits /player/lebron-james, load the player detail HTML page
@bp.route('/player/<player_name>')
def player_page(player_name):
    # Pass the player_name into the HTML template so it can display it
    return render_template('player.html', player_name=player_name)