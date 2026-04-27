# Optimized Statistical NBA Tool

A Flask-based web application that helps NBA fans evaluate single-game player prop bets by combining live betting odds with historical performance data. The app pulls current player props from The Odds API, fetches recent game logs from the public NBA Stats endpoints, and computes a hit rate (how often a player has cleared a given prop line over their last N games) plus a short-term trend direction. Results are surfaced through three pages: a homepage prop screener with filterable results, a per-game view showing all props for both teams, and a per-player detail page with charts of recent stat lines.

> **Note for the grader:** The live deployment URL may be inactive at the time of grading. Replit free deployments sleep when not accessed and the Odds API key may have rotated. The instructions below cover everything needed to run the project locally from a clean clone.

---

## Local Setup

### 1. Prerequisites

- **Python 3.11 or newer** (`python3 --version` to check)
- **pip** (bundled with modern Python installs)
- **git**

### 2. Clone the repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### 3. Install dependencies

From the project root:

```bash
pip install -r requirements.txt
```

This installs Flask, Flask-SQLAlchemy, the `nba_api` client, `requests`, and `python-dotenv`.

### 4. Obtain API keys

The app uses two upstream data sources. Only one of them requires a key.

| Source | Used for | Key required? | Where to obtain |
|---|---|---|---|
| **NBA Stats API** (via `nba_api` package) | Player metadata and historical game logs | **No** — uses the public `stats.nba.com` endpoints | n/a |
| **The Odds API** | Live game odds and player-prop lines | **Yes** | Sign up for a free account at <https://the-odds-api.com> — the free tier returns 500 requests/month, which is sufficient for grading |

### 5. Configure environment variables

Create a file named `.env` in the project root with the following contents:

```env
ODDS_API_KEY=your_odds_api_key_here
SECRET_KEY=any_random_string_for_flask_sessions
```

Replace `your_odds_api_key_here` with the key issued to you by The Odds API. `SECRET_KEY` can be any non-trivial string — it is only used for Flask session signing in development.

### 6. Start the application

```bash
cd backend
python app.py
```

The server will listen on `http://localhost:5000`. On first launch it will:

1. Create the SQLite database file at `backend/instance/nba.db`.
2. Automatically fetch today's games, player props, and game logs in the background. The first launch can take 60–90 seconds while the initial data populates.

You should see log lines like `Database tables created (or already exist)` followed by `Startup init complete. App is ready.` when it is finished.

### 7. Manually trigger a data refresh (optional)

If you want to force a re-fetch (for example, the day after first launch), the app exposes three admin endpoints. With the server running, in a second terminal:

```bash
curl -X POST http://localhost:5000/api/admin/fetch-props        # refresh today's prop lines
curl -X POST http://localhost:5000/api/admin/fetch-gamelogs     # refresh recent game logs
curl -X POST http://localhost:5000/api/admin/backfill-player-meta  # fill in missing player names/teams/positions
```

Each call returns a JSON summary of how many rows were inserted or updated.

### 8. Use the application

Open <http://localhost:5000> in any modern browser (Chrome or Firefox recommended). From the homepage you can:

- Filter today's player props by prop type, odds range, and minimum hit rate using the **Prop Screener**.
- Click any of the **Today's Games** cards to see all available props for that matchup.
- Use the **Select Team / Select Player** dropdowns in the header to jump directly to a player's detail page with their recent game logs and trend chart.

---

## Project Layout

```
.
├── backend/
│   ├── app.py              # Flask app factory, route registration, admin endpoints
│   ├── models.py           # SQLAlchemy models: Player, Game, PlayerProp, GameLog
│   ├── analytics.py        # hit_rate, combo_hit_rate, trend functions
│   ├── data_fetcher.py     # Outbound calls to The Odds API and nba_api
│   ├── routes/             # Blueprints: home, game, player, odds, screener, analytics
│   └── instance/nba.db     # SQLite database (auto-created on first run)
├── frontend/
│   ├── templates/          # Jinja2 templates (base, index, game, player)
│   └── static/             # CSS and JS assets
├── requirements.txt
└── README.md
```

---

## Troubleshooting

- **`ODDS_API_KEY` not set warning:** Confirm the `.env` file is in the project root (not inside `backend/`) and that the variable name is spelled exactly `ODDS_API_KEY`.
- **`502 The Odds API returned status 401`:** The supplied API key is invalid or has hit its monthly request quota. Generate a new key from <https://the-odds-api.com>.
- **Player page shows id number with placeholder team/position:** Run the `backfill-player-meta` admin endpoint shown in step 7. Some players require a second metadata fetch after their first prop appears.
- **No games shown on the homepage:** The NBA regular season runs October through April with playoffs continuing into June. During the offseason The Odds API will return an empty list and the app will display a "no games today" message — this is expected behavior, not an error.
