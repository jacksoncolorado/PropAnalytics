// screener.js — Prop Screener form & results
// Replaces placeholder divs in #screener with real inputs,
// calls GET /api/screener/props on submit, renders result cards.

document.addEventListener('DOMContentLoaded', function () {

  var inputStyle = 'min-height:48px;padding:0 14px;border:1px solid rgba(148,163,184,0.22);border-radius:14px;background:#1a2432;color:#e7eef8;font:inherit;width:100%;';
  var selectStyle = inputStyle;

  // Prop Type → <select>
  var propTypeDiv = document.getElementById('propType');
  if (propTypeDiv) {
    var select = document.createElement('select');
    select.id = 'propTypeSelect';
    select.style.cssText = selectStyle;
    [
      { value: '', text: 'All Types' },
      { value: 'player_points', text: 'Points' },
      { value: 'player_points_alternate', text: 'Points Alternate' },
      { value: 'player_rebounds', text: 'Rebounds' },
      { value: 'player_rebounds_alternate', text: 'Rebounds Alternate' },
      { value: 'player_assists', text: 'Assists' },
      { value: 'player_assists_alternate', text: 'Assists Alternate' },
      { value: 'player_threes', text: 'Threes' },
      { value: 'player_threes_alternate', text: 'Threes Alternate' },
      { value: 'player_blocks', text: 'Blocks' },
      { value: 'player_blocks_alternate', text: 'Blocks Alternate' },
      { value: 'player_steals', text: 'Steals' },
      { value: 'player_steals_alternate', text: 'Steals Alternate' },
      { value: 'player_turnovers', text: 'Turnovers' },
      { value: 'player_points_rebounds_assists', text: 'PTS+REB+AST' },
      { value: 'player_points_rebounds_assists_alternate', text: 'PTS+REB+AST Alternate' },
      { value: 'player_points_rebounds', text: 'PTS+REB' },
      { value: 'player_points_assists', text: 'PTS+AST' },
      { value: 'player_rebounds_assists', text: 'REB+AST' },
    ].forEach(function (opt) {
      var o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.text;
      select.appendChild(o);
    });
    propTypeDiv.replaceWith(select);
  }

  // Min Odds → <input type="number">
  var minOddsDiv = document.getElementById('minOdds');
  if (minOddsDiv) {
    var input = document.createElement('input');
    input.type = 'number'; input.id = 'minOddsInput'; input.placeholder = '-200';
    input.style.cssText = inputStyle;
    minOddsDiv.replaceWith(input);
  }

  // Max Odds → <input type="number">
  var maxOddsDiv = document.getElementById('maxOdds');
  if (maxOddsDiv) {
    var input = document.createElement('input');
    input.type = 'number'; input.id = 'maxOddsInput'; input.placeholder = '+200';
    input.style.cssText = inputStyle;
    maxOddsDiv.replaceWith(input);
  }

  // Min Hit % → <input type="number" min=0 max=100>
  var minHitDiv = document.getElementById('minHit');
  if (minHitDiv) {
    var input = document.createElement('input');
    input.type = 'number'; input.id = 'minHitInput'; input.min = '0'; input.max = '100'; input.placeholder = '0';
    input.style.cssText = inputStyle;
    minHitDiv.replaceWith(input);
  }

  // Max Hit % — backend does not currently support max_hit_rate filtering,
  // so we hide this placeholder rather than showing a non-functional control.
  var maxHitDiv = document.getElementById('maxHit');
  if (maxHitDiv) {
    maxHitDiv.parentElement.style.display = 'none';
  }

  // Sample Size → <select> with 5/10/15/20
  var sampleSizeDiv = document.getElementById('sampleSize');
  if (sampleSizeDiv) {
    var select = document.createElement('select');
    select.id = 'sampleSizeSelect';
    select.style.cssText = selectStyle;
    [5, 10, 15, 20].forEach(function (n) {
      var o = document.createElement('option');
      o.value = n;
      o.textContent = n + ' games';
      if (n === 10) o.selected = true;
      select.appendChild(o);
    });
    sampleSizeDiv.replaceWith(select);
  }

  // Replace placeholder button with real submit
  var placeholderBtn = document.querySelector('.placeholder-button');
  if (placeholderBtn) {
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.id = 'screenerSubmit';
    btn.textContent = 'Run Screener';
    btn.style.cssText = 'min-height:50px;padding:0 28px;border:none;border-radius:15px;background:linear-gradient(135deg,#2563eb,#60a5fa);color:#fff;font-weight:800;font-size:0.95rem;cursor:pointer;text-transform:uppercase;letter-spacing:0.05em;';
    placeholderBtn.replaceWith(btn);
  }

  // Submit handler
  var submitBtn = document.getElementById('screenerSubmit');
  if (submitBtn) {
    submitBtn.addEventListener('click', function () {
      var propType = document.getElementById('propTypeSelect');
      var minOdds = document.getElementById('minOddsInput');
      var maxOdds = document.getElementById('maxOddsInput');
      var minHit = document.getElementById('minHitInput');
      var sampleSize = document.getElementById('sampleSizeSelect');

      var params = new URLSearchParams();
      if (propType && propType.value) params.set('stat', propType.value);
      if (minOdds && minOdds.value) params.set('min_odds', minOdds.value);
      if (maxOdds && maxOdds.value) params.set('max_odds', maxOdds.value);
      if (minHit && minHit.value) params.set('min_hit_rate', (parseFloat(minHit.value) / 100).toString());
      if (sampleSize && sampleSize.value) params.set('sample_size', sampleSize.value);

      // Inject sort controls above results if not already there
      var existingSort = document.getElementById('screenerSortBar');
      if (!existingSort) {
        var sortBar = document.createElement('div');
        sortBar.id = 'screenerSortBar';
        sortBar.style.cssText = 'display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;';
        sortBar.innerHTML =
          '<span style="color:#98a7bb;font-size:0.78rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;align-self:center;">Sort:</span>' +
          '<button onclick="sortResults(\'hit_rate\',\'desc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Hit Rate ↓</button>' +
          '<button onclick="sortResults(\'hit_rate\',\'asc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Hit Rate ↑</button>' +
          '<button onclick="sortResults(\'odds\',\'desc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Best Odds ↓</button>' +
          '<button onclick="sortResults(\'odds\',\'asc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Best Odds ↑</button>' +
          '<button onclick="sortResults(\'game_time\',\'asc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Soonest Game</button>';
        var resultsSection = document.getElementById('results');
        if (resultsSection) resultsSection.insertBefore(sortBar, resultsSection.firstChild);
      }
      var resultsGrid = document.querySelector('.results-grid');
      if (resultsGrid) {
        resultsGrid.innerHTML = '<p style="color:#98a7bb;padding:18px;">Loading...</p>';
      }

      fetch('/api/screener/props?' + params.toString())
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (!resultsGrid) return;

          // Show timestamp above results
          var tsEl = document.getElementById('screenerTimestamp');
          if (!tsEl) {
            tsEl = document.createElement('p');
            tsEl.id = 'screenerTimestamp';
            tsEl.style.cssText = 'color:#98a7bb;font-size:0.82rem;margin-bottom:12px;';
            resultsGrid.parentElement.insertBefore(tsEl, resultsGrid);
          }
          tsEl.textContent = data.fetched_at ? 'Odds pulled at ' + data.fetched_at : '';

          var results = data.results || [];
          window._screenerData = results;

          if (!results || results.length === 0) {
            resultsGrid.innerHTML = '<div class="empty-state"><p>No props match your filters. Try adjusting your criteria.</p></div>';
            return;
          }

          resultsGrid.innerHTML = '';
          results.forEach(function (prop) {
            var card = document.createElement('div');
            card.className = 'result-card';

            var PROP_LABELS = {
              'player_points': 'Points',
              'player_points_alternate': 'Points Alt',
              'player_rebounds': 'Rebounds',
              'player_rebounds_alternate': 'Rebounds Alt',
              'player_assists': 'Assists',
              'player_assists_alternate': 'Assists Alt',
              'player_threes': 'Threes',
              'player_threes_alternate': 'Threes Alt',
              'player_blocks': 'Blocks',
              'player_blocks_alternate': 'Blocks Alt',
              'player_steals': 'Steals',
              'player_steals_alternate': 'Steals Alt',
              'player_turnovers': 'Turnovers',
              'player_points_rebounds_assists': 'PTS+REB+AST',
              'player_points_rebounds_assists_alternate': 'PTS+REB+AST Alt',
              'player_points_rebounds': 'PTS+REB',
              'player_points_rebounds_alternate': 'PTS+REB Alt',
              'player_points_assists': 'PTS+AST',
              'player_points_assists_alternate': 'PTS+AST Alt',
              'player_rebounds_assists': 'REB+AST',
              'player_rebounds_assists_alternate': 'REB+AST Alt',
            };
            var displayType = PROP_LABELS[prop.prop_type] || prop.prop_type;

            var hitPct = prop.hit_rate_pct || 'N/A';
            var oddsDisplay = prop.over_odds !== null && prop.over_odds !== undefined
              ? (prop.over_odds > 0 ? '+' + prop.over_odds : prop.over_odds)
              : 'N/A';

            card.innerHTML =
              '<div class="pill-row">' +
                '<span class="pill">' + displayType + '</span>' +
                '<span class="odds">' + oddsDisplay + '</span>' +
              '</div>' +
              '<h3>' + (prop.player_name || 'Unknown') + '</h3>' +
              '<div class="meta">' +
                '<div class="meta-box"><strong>' + (prop.line_value !== undefined ? prop.line_value : '—') + '</strong><span>line</span></div>' +
                '<div class="meta-box"><strong>' + hitPct + '</strong><span>hit rate</span></div>' +
                '<div class="meta-box"><strong>' + oddsDisplay + '</strong><span>over odds</span></div>' +
              '</div>';

            resultsGrid.appendChild(card);
          });
        })
        .catch(function (err) {
          if (resultsGrid) {
            resultsGrid.innerHTML = '<div class="empty-state"><p>Error loading results. Please try again.</p></div>';
          }
          console.error('Screener fetch error:', err);
        });
    });
  }
  window.sortResults = function(field, dir) {
    var data = window._screenerData;
    if (!data) return;
    data.sort(function(a, b) {
      var aVal, bVal;
      if (field === 'hit_rate') {
        aVal = a.hit_rate || 0;
        bVal = b.hit_rate || 0;
      } else if (field === 'odds') {
        aVal = a.over_odds || 0;
        bVal = b.over_odds || 0;
      } else if (field === 'game_time') {
        aVal = a.game_time || '';
        bVal = b.game_time || '';
      }
      if (dir === 'asc') return aVal > bVal ? 1 : -1;
      return aVal < bVal ? 1 : -1;
    });
    var resultsGrid = document.querySelector('.results-grid');
    if (!resultsGrid) return;
    resultsGrid.innerHTML = '';
    data.forEach(function(prop) {
      var card = document.createElement('div');
      card.className = 'result-card';
      var PROP_LABELS = {
        'player_points':'Points','player_points_alternate':'Points Alt',
        'player_rebounds':'Rebounds','player_rebounds_alternate':'Rebounds Alt',
        'player_assists':'Assists','player_assists_alternate':'Assists Alt',
        'player_threes':'Threes','player_threes_alternate':'Threes Alt',
        'player_blocks':'Blocks','player_blocks_alternate':'Blocks Alt',
        'player_steals':'Steals','player_steals_alternate':'Steals Alt',
        'player_turnovers':'Turnovers',
        'player_points_rebounds_assists':'PTS+REB+AST',
        'player_points_rebounds_assists_alternate':'PTS+REB+AST Alt',
        'player_points_rebounds':'PTS+REB','player_points_rebounds_alternate':'PTS+REB Alt',
        'player_points_assists':'PTS+AST','player_points_assists_alternate':'PTS+AST Alt',
        'player_rebounds_assists':'REB+AST','player_rebounds_assists_alternate':'REB+AST Alt',
      };
      var displayType = PROP_LABELS[prop.prop_type] || prop.prop_type;
      var hitPct = prop.hit_rate_pct || 'N/A';
      var oddsDisplay = prop.over_odds !== null && prop.over_odds !== undefined
        ? (prop.over_odds > 0 ? '+' + prop.over_odds : prop.over_odds) : 'N/A';
      card.innerHTML =
        '<div class="pill-row"><span class="pill">' + displayType + '</span><span class="odds">' + oddsDisplay + '</span></div>' +
        '<h3>' + (prop.player_name || 'Unknown') + '</h3>' +
        '<div class="meta">' +
          '<div class="meta-box"><strong>' + (prop.line_value !== undefined ? prop.line_value : '—') + '</strong><span>line</span></div>' +
          '<div class="meta-box"><strong>' + hitPct + '</strong><span>hit rate</span></div>' +
          '<div class="meta-box"><strong>' + oddsDisplay + '</strong><span>over odds</span></div>' +
        '</div>';
      resultsGrid.appendChild(card);
    });
  };
});
