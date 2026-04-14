from flask import Blueprint, render_template

from analytics import prop_report
from models import Game, PlayerProp


bp = Blueprint('game', __name__)


GAME_MARKETS = {
    "points": {
        "prop_type": "player_points",
        "label": "Points",
        "stat": "points",
        "accent": "#60a5fa",
        "description": "Scoring lines for both sides with recent hit rates and stat history.",
    },
    "rebounds": {
        "prop_type": "player_rebounds",
        "label": "Rebounds",
        "stat": "rebounds",
        "accent": "#38bdf8",
        "description": "Glass-cleaning props prioritized to one featured line per player.",
    },
    "assists": {
        "prop_type": "player_assists",
        "label": "Assists",
        "stat": "assists",
        "accent": "#22c55e",
        "description": "Playmaking props with trend context pulled from recent game logs.",
    },
    "threes": {
        "prop_type": "player_threes",
        "label": "3-Pointers",
        "stat": "threes",
        "accent": "#f59e0b",
        "description": "Perimeter-volume props surfaced in the same card layout as the core stats.",
    },
    "steals": {
        "prop_type": "player_steals",
        "label": "Steals",
        "stat": "steals",
        "accent": "#f97316",
        "description": "Defensive activity props with the same matchup card treatment.",
    },
    "blocks": {
        "prop_type": "player_blocks",
        "label": "Blocks",
        "stat": "blocks",
        "accent": "#a3e635",
        "description": "Rim-protection props, ready to expand as game logs fill in.",
    },
}

MARKET_BY_PROP_TYPE = {
    market["prop_type"]: {"key": key, **market}
    for key, market in GAME_MARKETS.items()
}

PREFERRED_BOOKMAKERS = {
    "draftkings": 0,
    "fanduel": 1,
    "betmgm": 2,
    "espnbet": 3,
    "caesars": 4,
}

TREND_LABELS = {
    "up": ("trend-up", "Trending up"),
    "down": ("trend-down", "Cooling off"),
    "flat": ("trend-flat", "Holding steady"),
    "N/A": ("trend-na", "No trend data"),
}


def _format_game_time(game_date):
    if not game_date:
        return "Tipoff pending"
    return game_date.strftime("%b %d, %I:%M %p").replace(" 0", " ")


def _format_odds(value):
    if value is None:
        return "N/A"
    return f"+{value}" if value > 0 else str(value)


def _format_bookmaker(bookmaker):
    if not bookmaker:
        return "Sportsbook"
    return bookmaker.replace("_", " ").title()


def _slugify_player(name):
    if not name:
        return "unknown-player"
    return "-".join(name.strip().split())


def _team_rank(team_name, game):
    if game and team_name == game.away_team:
        return 0
    if game and team_name == game.home_team:
        return 1
    return 2


def _priority(prop):
    preferred_rank = PREFERRED_BOOKMAKERS.get(
        (prop.bookmaker or "").lower(),
        len(PREFERRED_BOOKMAKERS),
    )
    over_distance = abs(abs(prop.over_odds) - 110) if prop.over_odds is not None else 999
    under_distance = abs(abs(prop.under_odds) - 110) if prop.under_odds is not None else 999
    return (
        1 if prop.is_alternate else 0,
        preferred_rank,
        over_distance + under_distance,
        abs(prop.line_value or 0),
        prop.id,
    )


def _select_featured_props(game_id):
    props = (
        PlayerProp.query
        .filter(
            PlayerProp.game_id == game_id,
            PlayerProp.prop_type.in_(list(MARKET_BY_PROP_TYPE.keys())),
        )
        .all()
    )

    featured = {}
    for prop in props:
        key = (prop.player_id, prop.prop_type)
        current = featured.get(key)
        if current is None or _priority(prop) < _priority(current):
            featured[key] = prop

    return list(featured.values())


def _build_card_subtitle(team_name, position, bookmaker_label):
    parts = []
    if team_name and team_name != "Team pending":
        parts.append(team_name)
    if position:
        parts.append(position)
    if bookmaker_label:
        parts.append(bookmaker_label)
    return " | ".join(parts) if parts else "Matchup data pending"


def _build_tabs(game):
    tabs = []
    featured_props = []
    unique_players = set()
    unique_books = set()
    analytics_ready = 0

    if game:
        featured_props = _select_featured_props(game.id)

    cards_by_tab = {key: [] for key in GAME_MARKETS}

    for prop in featured_props:
        market = MARKET_BY_PROP_TYPE.get(prop.prop_type)
        if not market:
            continue

        player = prop.player
        player_name = player.name if player else "Unknown Player"
        team_name = player.team if player and player.team else "Team pending"
        position = player.position if player and player.position else None
        unique_players.add(player_name)

        if prop.bookmaker:
            unique_books.add(prop.bookmaker.lower())

        report = prop_report(prop.player_id, market["stat"], prop.line_value, 10)
        hit_data = report.get("hit_rate", {})
        trend_data = report.get("trend", {})

        if hit_data.get("games_used"):
            analytics_ready += 1

        trend_direction = trend_data.get("direction") or "N/A"
        trend_class, trend_label = TREND_LABELS.get(
            trend_direction,
            TREND_LABELS["N/A"],
        )

        cards_by_tab[market["key"]].append({
            "player_name": player_name,
            "player_slug": _slugify_player(player_name),
            "team_rank": _team_rank(team_name, game),
            "subtitle": _build_card_subtitle(
                team_name,
                position,
                _format_bookmaker(prop.bookmaker),
            ),
            "line_value": prop.line_value,
            "line_label": f"{prop.line_value:.1f}" if prop.line_value is not None else "N/A",
            "over_odds_label": _format_odds(prop.over_odds),
            "under_odds_label": _format_odds(prop.under_odds),
            "hit_rate_pct": hit_data.get("hit_rate_pct", "N/A"),
            "games_used": hit_data.get("games_used", 0),
            "games_label": (
                f"Last {hit_data.get('games_used', 0)} logged games"
                if hit_data.get("games_used")
                else "No recent game logs yet"
            ),
            "chart_values": hit_data.get("values", []),
            "trend_class": trend_class,
            "trend_label": trend_label,
            "line_type": "Alt Line" if prop.is_alternate else "Main Line",
            "chart_accent": market["accent"],
        })

    for key, market in GAME_MARKETS.items():
        cards = cards_by_tab[key]
        cards.sort(key=lambda card: (card["team_rank"], card["player_name"]))
        tabs.append({
            "key": key,
            "label": market["label"],
            "description": market["description"],
            "cards": cards,
        })

    return {
        "tabs": tabs,
        "total_cards": sum(len(tab["cards"]) for tab in tabs),
        "player_count": len(unique_players),
        "markets_ready": sum(1 for tab in tabs if tab["cards"]),
        "bookmaker_count": len(unique_books),
        "analytics_ready": analytics_ready,
    }


@bp.route('/game/<string:event_id>')
def game_page(event_id):
    game = Game.query.filter_by(odds_event_id=event_id).first()
    tab_context = _build_tabs(game)

    matchup_title = (
        f"{game.away_team} @ {game.home_team}"
        if game else
        "Live Game Detail"
    )

    hero_copy = (
        "Browse tonight's featured player props by stat category."
        if tab_context["total_cards"] else
        "This matchup page is ready. Prop cards will appear here when game data is available."
    )

    status_text = (
        "Analytics Ready"
        if tab_context["total_cards"] else
        "Props Coming Soon"
    )

    summary_cards = [
        {
            "label": "Players",
            "value": tab_context["player_count"],
            "subtext": "featured on the page",
        },
        {
            "label": "Props",
            "value": tab_context["total_cards"],
            "subtext": "lines shown",
        },
        {
            "label": "Markets",
            "value": tab_context["markets_ready"],
            "subtext": "categories with data",
        },
        {
            "label": "Books",
            "value": tab_context["bookmaker_count"],
            "subtext": "sportsbooks represented",
        },
    ]

    return render_template(
        'game.html',
        event_id=event_id,
        tabs=tab_context["tabs"],
        matchup_title=matchup_title,
        hero_copy=hero_copy,
        tipoff_text=_format_game_time(game.game_date) if game else "Looking for tipoff...",
        status_text=status_text,
        summary_cards=summary_cards,
        has_db_cards_attr='1' if tab_context["total_cards"] > 0 else '0',
        has_db_game_attr='1' if game is not None else '0',
    )
