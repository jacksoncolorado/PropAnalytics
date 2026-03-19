# ============================================================
# app.py — THE MAIN ENTRY POINT FOR THE ENTIRE APPLICATION
# Run this file and your website becomes accessible in a browser.
# ============================================================

# --- IMPORTS ---
from flask import Flask  # web framework — handles URLs and pages
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
from routes.player import bp as player_bp# Register the route blueprints (blueprints are just grouped sets of routes)
app.register_blueprint(player_bp)
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