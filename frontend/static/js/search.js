// search.js — Today's Games section
// Fetches GET /api/odds/games and replaces placeholder game cards
// with real data showing teams, tip-off time, and event links.

document.addEventListener('DOMContentLoaded', function () {

  var gamesGrid = document.querySelector('.games-grid');
  var statusNote = document.querySelector('.status-note');

  if (!gamesGrid) return;

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

        article.innerHTML =
          '<time>' + timeStr + '</time>' +
          '<h3>' + (game.away_team || 'TBD') + ' @ ' + (game.home_team || 'TBD') + '</h3>' +
          '<p>' + (game.sport_title || 'NBA') + '</p>' +
          '<span class="pill">live odds</span>';

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
