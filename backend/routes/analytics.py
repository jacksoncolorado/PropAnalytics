from flask import Blueprint, jsonify
from analytics import hit_rate, prop_report

bp = Blueprint('analytics', __name__)

@bp.route('/api/analytics/hit-rate/<int:player_id>/<stat>/<float:line>')
def get_hit_rate(player_id, stat, line):
    try:
        result = hit_rate(player_id, stat, line)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@bp.route('/api/analytics/prop-report/<int:player_id>/<stat>/<float:line>')
def get_prop_report(player_id, stat, line):
    try:
        result = prop_report(player_id, stat, line)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
