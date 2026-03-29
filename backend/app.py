# ============================================================
# app.py — THE MAIN ENTRY POINT FOR THE ENTIRE APPLICATION
# Run this file and your website becomes accessible in a browser.
# ============================================================

# --- IMPORTS ---
from flask import Flask, jsonify  # web framework — handles URLs and pages; jsonify for JSON responses
from extensions import db  # database connection
from dotenv import load_dotenv  # read secret keys from the .env file
import os  # reading environment variables

# --- LOAD SECRET KEYS ---
# NEVER pushed to GitHub — each person has their own copy locally
load_dotenv()

# --- CREATE THE FLASK APP ---
# creates the main app object
# template_folder → finds HTML files
# static_folder → finds our CSS/JS files
import pathlib
BASE_DIR = pathlib.Path(__file__).parent.parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / 'frontend' / 'templates'),
    static_folder=str(BASE_DIR / 'frontend' / 'static')
)

# --- DATABASE CONFIGURATION ---
# tells Flask to use a simple SQLite database file called nba.db
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nba.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# This is a secret key Flask uses for security (sessions, etc.)
# It reads from your .env file — add SECRET_KEY=anyrandomstring to your .env
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key')

# --- CONNECT THE DATABASE TO THE APP ---
# db was created in extensions.py — here we attach it to our app
db.init_app(app)

# --- LOAD ALL ROUTES ---
# Routes are the URLs of our app (e.g. /player, /search, /screener)
# They are defined in separate files inside the /backend/routes/ folder
# import here when you create new routes
from routes.player import bp as player_bp
from routes.analytics import bp as analytics_bp
# odds_bp adds the /api/odds/games and /api/odds/props/<event_id> endpoints,
# which fetch live NBA betting data (game lines and player props) from
# The Odds API.  See backend/routes/odds.py and backend/data_fetcher.py.
from routes.odds import odds_bp
# screener_bp adds GET /api/screener/props — the prop screener endpoint
# that filters stored PlayerProp rows by odds/stat, calculates hit rates
# using analytics.py, and returns a ranked JSON list to the frontend.
# See backend/routes/screener.py.
from routes.screener import screener_bp
app.register_blueprint(player_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(odds_bp)
app.register_blueprint(screener_bp)

# ------------------------------------------------------------------
# ADMIN ROUTE: POST /api/admin/fetch-props
#
# PURPOSE:
#   Manual trigger to pull fresh player-prop odds from The Odds API
#   and store them in the PlayerProp table (models.py).
#
# HOW IT FITS IN:
#   Calls fetch_and_store_props() from data_fetcher.py, which handles
#   all API calls and database writes.  Returns the summary dict
#   { games_processed, props_stored, errors } as JSON.
#
# After this route runs, the screener endpoint
# (GET /api/screener/props) will have fresh data to work with.
# ------------------------------------------------------------------
@app.route('/api/admin/fetch-props', methods=['POST'])
def admin_fetch_props():
    from data_fetcher import fetch_and_store_props
    summary = fetch_and_store_props()
    return jsonify(summary)

# --- CREATE DATABASE TABLES ---
# This creates the actual database tables based on models.py
with app.app_context():
    db.create_all()
    print("Database tables created (or already exist)")

# --- START SERVER ---
# only runs when you execute this file directly
if __name__ == '__main__':
    print("Starting NBA Prop Analytics app...")
    print("Open your browser and go to the URL Replit gives you")
    app.run(debug=True, host='0.0.0.0', port=5000)