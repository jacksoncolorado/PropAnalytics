document.addEventListener('DOMContentLoaded', function () {

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

  var submitBtn = document.getElementById('screenerSubmit');
  if (!submitBtn) return;

  submitBtn.addEventListener('click', function () {
    var propType = document.getElementById('propTypeSelect');
    var minOdds = document.getElementById('minOddsInput');
    var maxOdds = document.getElementById('maxOddsInput');
    var minHit = document.getElementById('minHitSelect');
    var sampleSize = document.getElementById('sampleSizeSelect');

    var params = new URLSearchParams();
    if (propType && propType.value) params.set('stat', propType.value);
    if (minOdds && minOdds.value) params.set('min_odds', minOdds.value);
    if (maxOdds && maxOdds.value) params.set('max_odds', maxOdds.value);
    if (minHit && minHit.value && minHit.value !== '0') {
      params.set('min_hit_rate', (parseFloat(minHit.value) / 100).toString());
    }
    if (sampleSize && sampleSize.value) params.set('sample_size', sampleSize.value);

    var resultsEl = document.getElementById('results');
    var sortBar = document.getElementById('sortBar');

    if (resultsEl) resultsEl.innerHTML = '<p style="color:#98a7bb;padding:18px;">Loading...</p>';

    fetch('/api/screener/props?' + params.toString())
      .then(function(res){ return res.json(); })
      .then(function(data){
        var tsEl = document.getElementById('screenerTimestamp');
        if (tsEl) tsEl.textContent = data.fetched_at ? 'Odds pulled at ' + data.fetched_at : '';

        var results = data.results || [];
        window._screenerData = results;

        if (!resultsEl) return;

        if (!results.length) {
          resultsEl.innerHTML = '<div class="empty-state"><p>No props match your filters. Try adjusting your criteria.</p></div>';
          if (sortBar) sortBar.style.display = 'none';
          return;
        }

        // Show sort bar
        if (sortBar) {
          sortBar.style.display = 'flex';
          sortBar.style.cssText = 'display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap;';
          sortBar.innerHTML =
            '<span style="color:#98a7bb;font-size:0.78rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;align-self:center;">Sort:</span>' +
            '<button onclick="screenerSort(\'hit_rate\',\'desc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Hit Rate ↓</button>' +
            '<button onclick="screenerSort(\'hit_rate\',\'asc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Hit Rate ↑</button>' +
            '<button onclick="screenerSort(\'odds\',\'desc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Best Odds ↓</button>' +
            '<button onclick="screenerSort(\'odds\',\'asc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Best Odds ↑</button>' +
            '<button onclick="screenerSort(\'game_time\',\'asc\')" style="padding:6px 14px;border-radius:999px;border:1px solid rgba(148,163,184,0.22);background:#1a2432;color:#dbeafe;font-size:0.82rem;cursor:pointer;">Soonest Game</button>';
        }

        renderGrouped(results, resultsEl);
      })
      .catch(function(err){
        if (resultsEl) resultsEl.innerHTML = '<div class="empty-state"><p>Error loading results. Please try again.</p></div>';
        console.error('Screener fetch error:', err);
      });
  });

  function renderGrouped(results, container, sortField, sortDir) {
    // Deduplicate — keep only best odds per player+stat (no alt spam)
    var best = {};
    results.forEach(function(prop) {
      var statCore = (prop.prop_type||'').replace('player_','').replace('_alternate','');
      var key = (prop.player_name||'') + '|' + statCore;
      var existing = best[key];
      if (!existing) { best[key] = prop; return; }
      // Keep whichever has better hit rate; tie-break on higher odds
      var existingHr = existing.hit_rate || 0;
      var newHr = prop.hit_rate || 0;
      if (newHr > existingHr) { best[key] = prop; return; }
      if (newHr === existingHr) {
        var existingOdds = existing.over_odds || -9999;
        var newOdds = prop.over_odds || -9999;
        if (newOdds > existingOdds) best[key] = prop;
      }
    });

    var deduped = Object.values(best);

    // Group by player
    var byPlayer = {};
    deduped.forEach(function(prop) {
      var name = prop.player_name || 'Unknown';
      if (!byPlayer[name]) byPlayer[name] = [];
      byPlayer[name].push(prop);
    });

    container.innerHTML = '';

    var playerNames = Object.keys(byPlayer);

    if (sortField === 'hit_rate') {
      playerNames.sort(function(a, b) {
        var aHr = byPlayer[a][0] ? (byPlayer[a][0].hit_rate||0) : 0;
        var bHr = byPlayer[b][0] ? (byPlayer[b][0].hit_rate||0) : 0;
        return sortDir === 'asc' ? aHr - bHr : bHr - aHr;
      });
    } else if (sortField === 'odds') {
      playerNames.sort(function(a, b) {
        var aOdds = byPlayer[a][0] ? (byPlayer[a][0].over_odds||0) : 0;
        var bOdds = byPlayer[b][0] ? (byPlayer[b][0].over_odds||0) : 0;
        return sortDir === 'asc' ? aOdds - bOdds : bOdds - aOdds;
      });
    } else if (sortField === 'game_time') {
      playerNames.sort(function(a, b) {
        var aT = byPlayer[a][0] ? (byPlayer[a][0].game_time||'') : '';
        var bT = byPlayer[b][0] ? (byPlayer[b][0].game_time||'') : '';
        return aT > bT ? 1 : -1;
      });
    } else {
      playerNames.sort();
    }

    playerNames.forEach(function(playerName) {
      var props = byPlayer[playerName];
      // Sort props within player by hit rate desc
      props.sort(function(a,b){ return (b.hit_rate||0) - (a.hit_rate||0); });

      var bestHr = props[0] ? Math.round((props[0].hit_rate||0)*100) : 0;
      var dotColor = bestHr >= 60 ? '#4ade80' : bestHr >= 45 ? '#facc15' : '#f87171';

      var wrap = document.createElement('div');
      wrap.style.cssText = 'border:1px solid rgba(148,163,184,0.22);border-radius:14px;overflow:hidden;margin-bottom:8px;';

      var header = document.createElement('div');
      header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:14px 18px;cursor:pointer;background:rgba(22,31,44,0.88);user-select:none;';
      header.innerHTML =
        '<div style="display:flex;align-items:center;gap:10px;">' +
          '<div style="width:10px;height:10px;border-radius:50%;background:' + dotColor + ';flex-shrink:0;"></div>' +
        '<a href="/player/' + playerName.replace(/\s+/g,'-') + '" onclick="event.stopPropagation()" style="font-weight:700;color:var(--ink);text-decoration:none;">' + playerName + '</a>' +
          '<span style="color:#98a7bb;font-size:0.82rem;">' + props.length + ' prop' + (props.length>1?'s':'') + ' match</span>' +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:10px;">' +
          '<span style="font-size:0.82rem;color:#98a7bb;">best: <span style="color:' + dotColor + ';font-weight:700;">' + bestHr + '%</span></span>' +
          '<span style="color:#98a7bb;font-size:0.8rem;" class="chev">▼</span>' +
        '</div>';

      var body = document.createElement('div');
      body.style.cssText = 'display:none;background:rgba(14,20,30,0.7);border-top:1px solid rgba(148,163,184,0.12);';

      props.forEach(function(prop) {
        var label = PROP_LABELS[prop.prop_type] || prop.prop_type;
        var hr = Math.round((prop.hit_rate||0)*100);
        var hrColor = hr >= 60 ? '#4ade80' : hr >= 45 ? '#facc15' : '#f87171';
        var odds = prop.over_odds !== null && prop.over_odds !== undefined
          ? (prop.over_odds > 0 ? '+'+prop.over_odds : prop.over_odds) : 'N/A';

        var row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:12px 18px;border-bottom:1px solid rgba(148,163,184,0.08);';
        row.innerHTML =
          '<div style="display:flex;align-items:center;gap:12px;">' +
            '<span style="font-size:0.82rem;padding:3px 8px;border-radius:6px;background:rgba(96,165,250,0.15);color:#dbeafe;">' + label + '</span>' +
            '<span style="font-size:0.82rem;color:#98a7bb;font-family:monospace;">line ' + (prop.line_value||'—') + '</span>' +
          '</div>' +
          '<div style="display:flex;align-items:center;gap:16px;">' +
            '<span style="font-weight:700;color:' + hrColor + ';font-family:monospace;">' + hr + '%</span>' +
            '<span style="color:#7dd3fc;font-family:monospace;font-weight:700;">' + odds + '</span>' +
            '<span style="color:#98a7bb;font-size:0.78rem;">' + (prop.hit_rate_pct ? prop.games_used + ' games' : '') + '</span>' +
          '</div>';
        body.appendChild(row);
      });

      header.addEventListener('click', function(e) {
        if (e.target.tagName === 'A') return;
        var open = body.style.display !== 'none';
        body.style.display = open ? 'none' : 'block';
        header.querySelector('.chev').textContent = open ? '▼' : '▲';
      });
      wrap.appendChild(header);
      wrap.appendChild(body);
      container.appendChild(wrap);
    });
  }

  window.screenerSort = function(field, dir) {
    var data = window._screenerData;
    if (!data) return;
    var resultsEl = document.getElementById('results');
    if (!resultsEl) return;
    renderGrouped(data, resultsEl, field, dir);
  };

});