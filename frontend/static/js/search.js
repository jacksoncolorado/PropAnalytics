// search.js — Today's Games section
// Fetches GET /api/odds/games and replaces placeholder game cards
// with real data showing teams, tip-off time, and event links.

document.addEventListener('DOMContentLoaded', function () {

  var gamesGrid = document.querySelector('.games-grid');
  var statusNote = document.querySelector('.status-note');

  if (!gamesGrid) return;
  var NBA_TEAM_IDS = {
    'Atlanta Hawks': 1610612737, 'Boston Celtics': 1610612738,
    'Brooklyn Nets': 1610612751, 'Charlotte Hornets': 1610612766,
    'Chicago Bulls': 1610612741, 'Cleveland Cavaliers': 1610612739,
    'Dallas Mavericks': 1610612742, 'Denver Nuggets': 1610612743,
    'Detroit Pistons': 1610612765, 'Golden State Warriors': 1610612744,
    'Houston Rockets': 1610612745, 'Indiana Pacers': 1610612754,
    'LA Clippers': 1610612746, 'Los Angeles Lakers': 1610612747,
    'Memphis Grizzlies': 1610612763, 'Miami Heat': 1610612748,
    'Milwaukee Bucks': 1610612749, 'Minnesota Timberwolves': 1610612750,
    'New Orleans Pelicans': 1610612740, 'New York Knicks': 1610612752,
    'Oklahoma City Thunder': 1610612760, 'Orlando Magic': 1610612753,
    'Philadelphia 76ers': 1610612755, 'Phoenix Suns': 1610612756,
    'Portland Trail Blazers': 1610612757, 'Sacramento Kings': 1610612758,
    'San Antonio Spurs': 1610612759, 'Toronto Raptors': 1610612761,
    'Utah Jazz': 1610612762, 'Washington Wizards': 1610612764
  };

  function teamLogoUrl(teamName) {
    var id = NBA_TEAM_IDS[teamName];
    return id ? 'https://cdn.nba.com/logos/nba/' + id + '/global/L/logo.svg' : null;
  }
  fetch('/api/odds/games')
    .then(function (res) {
      if (!res.ok) throw new Error('API returned status ' + res.status);
      return res.json();
    })
    .then(function (games) {
      gamesGrid.innerHTML = '';

      if (!games || games.length === 0) {
        gamesGrid.innerHTML = '<div class="empty-state"><p>No games scheduled for today.</p></div>';
        if (statusNote) statusNote.textContent = 'No games found from The Odds API.';
        return;
      }
      // Filter to today only (local date)
      var todayStr = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD
      games = games.filter(function(game) {
        if (!game.commence_time) return false;
        var gameDate = new Date(game.commence_time).toLocaleDateString('en-CA');
        return gameDate === todayStr;
      });

      if (games.length === 0) {
        gamesGrid.innerHTML = '<div class="empty-state"><p>No games scheduled for today.</p></div>';
        if (statusNote) statusNote.textContent = 'No games today.';
        return;
      }
      games.forEach(function (game) {
        var article = document.createElement('article');
        article.className = 'game-card';

        var timeStr = 'TBD';
        if (game.commence_time) {
          try {
            var d = new Date(game.commence_time);
            timeStr = d.toLocaleTimeString('en-US', {
              hour: 'numeric',
              minute: '2-digit',
              hour12: true
            });
          } catch (e) {
            timeStr = 'TBD';
          }
        }

        var link = document.createElement('a');
        link.href = '/game/' + (game.id || '');
        link.style.cssText = 'text-decoration:none;color:inherit;';

        var awayLogo = teamLogoUrl(game.away_team);
        var homeLogo = teamLogoUrl(game.home_team);

        var awayLogoHtml = awayLogo
          ? '<img src="' + awayLogo + '" style="width:32px;height:32px;object-fit:contain;" onerror="this.style.display=\'none\'">'
          : '<span style="width:32px;display:inline-block;"></span>';
        var homeLogoHtml = homeLogo
          ? '<img src="' + homeLogo + '" style="width:32px;height:32px;object-fit:contain;" onerror="this.style.display=\'none\'">'
          : '<span style="width:32px;display:inline-block;"></span>';

        article.innerHTML =
          '<time>' + timeStr + '</time>' +
          '<div style="display:flex;align-items:center;gap:10px;margin:6px 0;">' +
            awayLogoHtml +
            '<span style="font-weight:700;">' + (game.away_team || 'TBD') + '</span>' +
            '<span style="color:var(--muted);font-size:0.85rem;">@</span>' +
            homeLogoHtml +
            '<span style="font-weight:700;">' + (game.home_team || 'TBD') + '</span>' +
          '</div>' +
          '<span class="pill">view props</span>';

        link.appendChild(article);
        gamesGrid.appendChild(link);
      });

      if (statusNote) {
        statusNote.textContent = games.length + ' game' + (games.length !== 1 ? 's' : '') + ' found for today.';
      }
    })
    .catch(function (err) {
      gamesGrid.innerHTML = '<div class="empty-state"><p>Could not load today\'s games. Check your API key.</p></div>';
      if (statusNote) statusNote.textContent = 'Error loading games.';
      console.error('Games fetch error:', err);
    });
});
