# ============================================================
# extensions.py — SHARED TOOLS / EXTENSIONS
# This file creates shared objects that the whole app can use.
# ============================================================

from flask_sqlalchemy import SQLAlchemy
# SQLAlchemy is the tool that lets us talk to the database
# Create the database object — it gets connected to the app in app.py
db = SQLAlchemy()