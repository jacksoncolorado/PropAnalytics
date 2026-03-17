from .extensions import db
from datetime import datetime

class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    game_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20)) # e.g., 'Scheduled', 'Live', 'Final'
    
    # Relationships
    logs = db.relationship('GameLog', backref='game', lazy=True)
    props = db.relationship('PlayerProp', backref='game', lazy=True)

class Player(db.Model):
    __tablename__ = 'players'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    team = db.Column(db.String(50))
    position = db.Column(db.String(20))
    
    # Relationships
    logs = db.relationship('GameLog', backref='player', lazy=True)
    props = db.relationship('PlayerProp', backref='player', lazy=True)

class PlayerProp(db.Model):
    __tablename__ = 'player_props'
    
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    
    prop_type = db.Column(db.String(50))  # e.g., 'Points', 'Rebounds'
    line_value = db.Column(db.Float)      # e.g., 22.5
    odds = db.Column(db.Integer)          # e.g., -110
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class GameLog(db.Model):
    __tablename__ = 'game_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id'), nullable=False)
    
    # Stat columns
    points = db.Column(db.Integer, default=0)
    rebounds = db.Column(db.Integer, default=0)
    assists = db.Column(db.Integer, default=0)
    minutes_played = db.Column(db.Integer)
    
    def __repr__(self):
        return f"<GameLog Player:{self.player_id} Game:{self.game_id}>"
