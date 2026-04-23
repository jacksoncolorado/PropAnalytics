# ============================================================
# app.py — THE MAIN ENTRY POINT FOR THE ENTIRE APPLICATION
# Run this file and your website becomes accessible in a browser.
# ============================================================

# --- IMPORTS ---
from flask import Flask, jsonify
from extensions import db
from dotenv import load_dotenv
import os

# --- LOAD SECRET KEYS ---
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- CREATE THE FLASK APP ---
import pathlib
BASE_DIR = pathlib.Path(__file__).parent.parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / 'frontend' / 'templates'),
    static_folder=str(BASE_DIR / 'frontend' / 'static')
)

# --- DATABASE CONFIGURATION ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nba.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key')

# --- CONNECT THE DATABASE TO THE APP ---
db.init_app(app)

# --- LOAD ALL ROUTES ---
from routes.player import bp as player_bp
from routes.analytics import bp as analytics_bp
from routes.odds import odds_bp
from routes.screener import screener_bp
from routes.game import bp as game_bp

app.register_blueprint(player_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(odds_bp)
app.register_blueprint(screener_bp)
app.register_blueprint(game_bp)

# --- ADMIN ROUTES ---
@app.route('/api/admin/fetch-props', methods=['POST'])
def admin_fetch_props():
    from data_fetcher import fetch_and_store_props
    return jsonify(fetch_and_store_props())

@app.route('/api/admin/fetch-gamelogs', methods=['POST'])
def admin_fetch_gamelogs():
    from data_fetcher import fetch_and_store_gamelogs
    return jsonify(fetch_and_store_gamelogs())

@app.route('/api/admin/backfill-player-meta', methods=['POST'])
def backfill_player_meta_route():
    from data_fetcher import backfill_player_meta
    return jsonify(backfill_player_meta())

# --- CREATE DATABASE TABLES ---
with app.app_context():
    db.create_all()
    print("Database tables created (or already exist)")

# --- AUTO-INIT ON STARTUP ---
def _startup_init():
    from datetime import date
    from models import PlayerProp, Player, GameLog, Game
    from data_fetcher import fetch_and_store_props, fetch_and_store_gamelogs, backfill_player_meta

    with app.app_context():
        # 1. Check if props exist for today
        today = date.today()
        recent_prop = PlayerProp.query.order_by(PlayerProp.fetched_at.desc()).first()
        props_are_fresh = (
            recent_prop and
            recent_prop.fetched_at and
            recent_prop.fetched_at.date() == today
        )

        if not props_are_fresh:
            print("No props for today — fetching from Odds API...")
            props_summary = fetch_and_store_props()
            print(f"Props: {props_summary['props_stored']} stored, {len(props_summary['errors'])} errors")
        else:
            print("Props already fresh for today — skipping fetch.")

        # 2. Check if gamelogs exist
        log_count = GameLog.query.count()
        from datetime import timedelta
        latest_log = GameLog.query.join(Game).order_by(Game.game_date.desc()).first()
        stale = (not latest_log) or (date.today() - latest_log.game.game_date.date() > timedelta(days=2))
        if stale:
            print("No game logs found — fetching from nba_api (this takes a few minutes)...")
            logs_summary = fetch_and_store_gamelogs()
            print(f"Gamelogs: {logs_summary['players_updated']} players updated")
        else:
            print(f"Game logs exist ({log_count} rows) — skipping fetch.")

        # 3. Check if player metadata needs backfill
        missing_meta = Player.query.filter(
            (Player.team == None) | (Player.nba_player_id == None)
        ).count()
        if missing_meta > 0:
            print(f"{missing_meta} players missing metadata — running backfill...")
            meta_summary = backfill_player_meta()
            print(f"Backfill: {meta_summary['players_updated']} updated")
        else:
            print("Player metadata complete — skipping backfill.")

        print("Startup init complete. App is ready.")

import threading
import os
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    init_thread = threading.Thread(target=_startup_init, daemon=True)
    init_thread.start()

# --- START SERVER ---
if __name__ == '__main__':
    print("Starting NBA Prop Analytics...")
    print("Data will auto-fetch in the background if needed.")
    print("Open your browser and go to the URL Replit gives you")
    app.run(debug=False, host='0.0.0.0', port=5000)