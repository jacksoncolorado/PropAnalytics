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
      { value: 'player_rebounds', text: 'Rebounds' },
      { value: 'player_assists', text: 'Assists' },
      { value: 'player_threes', text: 'Threes' }
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

      var resultsGrid = document.querySelector('.results-grid');
      if (resultsGrid) {
        resultsGrid.innerHTML = '<p style="color:#98a7bb;padding:18px;">Loading...</p>';
      }

      fetch('/api/screener/props?' + params.toString())
        .then(function (res) { return res.json(); })
        .then(function (data) {
          if (!resultsGrid) return;

          if (!data || data.length === 0) {
            resultsGrid.innerHTML = '<div class="empty-state"><p>No props match your filters. Try adjusting your criteria.</p></div>';
            return;
          }

          resultsGrid.innerHTML = '';
          data.forEach(function (prop) {
            var card = document.createElement('div');
            card.className = 'result-card';

            var displayType = (prop.prop_type || '')
              .replace('player_', '')
              .replace(/_/g, ' ')
              .replace(/\b\w/g, function (c) { return c.toUpperCase(); });

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
});
