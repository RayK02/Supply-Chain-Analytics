(function () {
  'use strict';

  var KEY = 'pocketTerminal_v5';
  var PRESTIGE_BASE = 250000;
  var OFFLINE_CAP_SECONDS = 8 * 60 * 60;
  var mode = '1';
  var lastTick = Date.now();
  var toastTimer = null;
  var goldenHideTimer = null;

  var upgrades = [
    { id: 'worker', icon: '👷', name: 'Dock Worker', power: 1, base: 15 },
    { id: 'forklift', icon: '🏎️', name: 'Forklift', power: 7, base: 120 },
    { id: 'truck', icon: '🚚', name: 'Yard Truck', power: 38, base: 1050 },
    { id: 'crane', icon: '🏗️', name: 'Gantry Crane', power: 180, base: 9200 },
    { id: 'rail', icon: '🚆', name: 'Rail Link', power: 850, base: 78000 },
    { id: 'auto', icon: '🤖', name: 'Automated Hub', power: 4200, base: 650000 }
  ];

  function freshState() {
    return {
      credits: 0,
      lifetime: 0,
      runCredits: 0,
      taps: 0,
      tokens: 0,
      prestiges: 0,
      levels: {},
      lastSeen: Date.now(),
      doubleUntil: 0,
      rushReady: 0,
      radar: false,
      goldenAt: 0
    };
  }

  function byId(id) { return document.getElementById(id); }

  function loadState() {
    var state = freshState();
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) {
        var parsed = JSON.parse(raw);
        Object.keys(state).forEach(function (key) {
          if (Object.prototype.hasOwnProperty.call(parsed, key)) state[key] = parsed[key];
        });
        state.levels = parsed.levels && typeof parsed.levels === 'object' ? parsed.levels : {};
      }
    } catch (e) {}
    return state;
  }

  var state = loadState();

  function saveState() {
    state.lastSeen = Date.now();
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }

  function formatNumber(value) {
    var n = Math.max(0, Number(value) || 0);
    if (n < 1000) return n < 100 ? String(Math.floor(n * 10) / 10) : String(Math.floor(n));
    var units = ['K', 'M', 'B', 'T', 'Qa', 'Qi'];
    var index = -1;
    while (n >= 1000 && index < units.length - 1) {
      n /= 1000;
      index += 1;
    }
    var text = n >= 100 ? n.toFixed(0) : n >= 10 ? n.toFixed(1) : n.toFixed(2);
    return text + units[index];
  }

  function totalLevels() {
    var total = 0;
    Object.keys(state.levels).forEach(function (key) { total += Number(state.levels[key]) || 0; });
    return total;
  }

  function milestoneMultiplier() {
    var levels = totalLevels();
    var mult = 1;
    if (levels >= 25) mult *= 2;
    if (levels >= 75) mult *= 2;
    if (levels >= 150) mult *= 2;
    if (levels >= 300) mult *= 2;
    return mult;
  }

  function passiveTokenMultiplier() { return 1 + state.tokens * 0.2; }
  function tapTokenMultiplier() { return 1 + state.tokens * 0.1; }

  function baseProduction() {
    var total = 0;
    upgrades.forEach(function (upgrade) {
      total += (Number(state.levels[upgrade.id]) || 0) * upgrade.power;
    });
    return total * milestoneMultiplier() * passiveTokenMultiplier();
  }

  function production() {
    return baseProduction() * (Date.now() < state.doubleUntil ? 2 : 1);
  }

  function tapValue() {
    return Math.max(1, (1 + Math.sqrt(totalLevels()) * 1.25) * milestoneMultiplier() * tapTokenMultiplier());
  }

  function oneCost(upgrade, level) {
    return Math.ceil(upgrade.base * Math.pow(1.15, level));
  }

  function multiCost(upgrade, count) {
    var level = Number(state.levels[upgrade.id]) || 0;
    var total = 0;
    var i;
    for (i = 0; i < count; i += 1) total += oneCost(upgrade, level + i);
    return total;
  }

  function maxAffordable(upgrade) {
    var level = Number(state.levels[upgrade.id]) || 0;
    var spent = 0;
    var count = 0;
    while (count < 500) {
      var next = oneCost(upgrade, level + count);
      if (spent + next > state.credits) break;
      spent += next;
      count += 1;
    }
    return count;
  }

  function earn(amount) {
    if (!isFinite(amount) || amount <= 0) return;
    state.credits += amount;
    state.lifetime += amount;
    state.runCredits += amount;
  }

  function vibrate() {
    try { if (navigator.vibrate) navigator.vibrate(12); } catch (e) {}
  }

  function showToast(title, text) {
    byId('toastTitle').textContent = title;
    byId('toastText').textContent = text || '';
    byId('toast').classList.add('is-visible');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { byId('toast').classList.remove('is-visible'); }, 2200);
  }

  function currentMilestoneTarget() {
    var levels = totalLevels();
    var targets = [25, 75, 150, 300];
    var i;
    for (i = 0; i < targets.length; i += 1) if (levels < targets[i]) return targets[i];
    return 300;
  }

  function terminalTier() {
    var levels = totalLevels();
    if (levels < 25) return 'Tiny freight yard';
    if (levels < 75) return 'Regional terminal';
    if (levels < 150) return 'Intermodal hub';
    if (levels < 300) return 'National gateway';
    return 'Autonomous mega terminal';
  }

  function prestigeGain() {
    return Math.floor(Math.sqrt(state.runCredits / PRESTIGE_BASE));
  }

  function renderUpgrades() {
    var list = byId('upgradeList');
    list.textContent = '';

    upgrades.forEach(function (upgrade) {
      var level = Number(state.levels[upgrade.id]) || 0;
      var count = mode === 'max' ? Math.max(1, maxAffordable(upgrade)) : Number(mode);
      var cost = multiCost(upgrade, count);
      var affordable = mode === 'max' ? maxAffordable(upgrade) : count;

      var row = document.createElement('article');
      row.className = 'upgrade';

      var icon = document.createElement('div');
      icon.className = 'upgrade-icon';
      icon.textContent = upgrade.icon;

      var info = document.createElement('div');
      var title = document.createElement('h3');
      title.textContent = upgrade.name + ' · Lv ' + level;
      var copy = document.createElement('p');
      copy.textContent = '+' + formatNumber(upgrade.power * milestoneMultiplier() * passiveTokenMultiplier()) + ' / s each';
      info.appendChild(title);
      info.appendChild(copy);

      var buy = document.createElement('button');
      buy.type = 'button';
      buy.className = 'buy-button';
      buy.disabled = affordable < 1 || state.credits < cost;
      var buyLabel = mode === 'max' ? 'MAX +' + affordable : 'BUY x' + count;
      buy.textContent = buyLabel + ' · ' + formatNumber(cost);
      buy.addEventListener('click', function () { buyUpgrade(upgrade); });

      row.appendChild(icon);
      row.appendChild(info);
      row.appendChild(buy);
      list.appendChild(row);
    });
  }

  function buyUpgrade(upgrade) {
    var count = mode === 'max' ? maxAffordable(upgrade) : Number(mode);
    if (count < 1) return;
    var cost = multiCost(upgrade, count);
    if (state.credits < cost) return;
    state.credits -= cost;
    state.levels[upgrade.id] = (Number(state.levels[upgrade.id]) || 0) + count;
    vibrate();
    render();
    saveState();
  }

  function render() {
    var prod = production();
    var levels = totalLevels();
    var target = currentMilestoneTarget();
    var gain = prestigeGain();
    var remainingDouble = Math.max(0, Math.ceil((state.doubleUntil - Date.now()) / 1000));
    var rushRemaining = Math.max(0, Math.ceil((state.rushReady - Date.now()) / 1000));
    var doublePrice = Math.max(250, prod * 30 + 250);

    byId('cash').textContent = formatNumber(state.credits);
    byId('rate').textContent = '+' + formatNumber(prod) + ' / s';
    byId('tapValue').textContent = '+' + formatNumber(tapValue());
    byId('yardTier').textContent = terminalTier();

    byId('milestoneText').textContent = levels + ' / ' + target + ' upgrades';
    byId('milestoneProgress').max = target;
    byId('milestoneProgress').value = Math.min(levels, target);
    byId('milestoneBonus').textContent = levels >= 300 ? 'All expansion milestones unlocked' : 'Next bonus: x2 output';

    byId('assetTruck').classList.toggle('is-on', (Number(state.levels.truck) || 0) > 0);
    byId('assetCrane').classList.toggle('is-on', (Number(state.levels.crane) || 0) > 0);
    byId('assetTrain').classList.toggle('is-on', (Number(state.levels.rail) || 0) > 0);

    byId('doubleShift').textContent = remainingDouble > 0 ? 'ACTIVE · ' + remainingDouble + 's' : 'Activate · ' + formatNumber(doublePrice);
    byId('doubleShift').disabled = remainingDouble > 0 || state.credits < doublePrice;

    byId('rushOrder').textContent = rushRemaining > 0 ? 'Cooldown · ' + rushRemaining + 's' : 'Complete rush order · +' + formatNumber(prod * 60);
    byId('rushOrder').disabled = rushRemaining > 0 || prod <= 0;

    byId('radarButton').textContent = state.radar ? 'Radar online' : 'Install radar · 25K';
    byId('radarButton').disabled = state.radar || state.credits < 25000;

    byId('tokens').textContent = state.tokens;
    byId('lifetime').textContent = formatNumber(state.lifetime);
    byId('tapCount').textContent = formatNumber(state.taps);
    byId('prestigeCount').textContent = state.prestiges;
    byId('runCredits').textContent = formatNumber(state.runCredits);
    byId('prestigeProgress').max = PRESTIGE_BASE;
    byId('prestigeProgress').value = Math.min(state.runCredits, PRESTIGE_BASE);
    byId('prestigeText').textContent = gain > 0 ? 'Reset now for ' + gain + ' token' + (gain === 1 ? '' : 's') : formatNumber(state.runCredits) + ' / ' + formatNumber(PRESTIGE_BASE) + ' run credits';
    byId('prestigeButton').disabled = gain < 1;
    byId('prestigeButton').textContent = gain < 1 ? 'Prestige locked' : 'Expand network · +' + gain + ' ◆';

    renderUpgrades();
  }

  function maybeSpawnGoldenCargo() {
    if (!state.radar || Date.now() < state.goldenAt || !byId('goldenCargo').hidden) return;
    state.goldenAt = Date.now() + 30000 + Math.random() * 50000;
    byId('goldenCargo').hidden = false;
    if (goldenHideTimer) clearTimeout(goldenHideTimer);
    goldenHideTimer = setTimeout(function () { byId('goldenCargo').hidden = true; }, 9000);
  }

  byId('tapCargo').addEventListener('pointerdown', function () {
    earn(tapValue());
    state.taps += 1;
    vibrate();
    render();
  });

  byId('buyMode').querySelectorAll('button').forEach(function (button) {
    button.addEventListener('click', function () {
      byId('buyMode').querySelectorAll('button').forEach(function (item) { item.classList.remove('is-active'); });
      button.classList.add('is-active');
      mode = button.getAttribute('data-mode');
      renderUpgrades();
    });
  });

  document.querySelectorAll('.bottom-nav button').forEach(function (button) {
    button.addEventListener('click', function () {
      document.querySelectorAll('.bottom-nav button').forEach(function (item) { item.classList.remove('is-active'); });
      document.querySelectorAll('.tab').forEach(function (tab) { tab.classList.remove('is-active'); });
      button.classList.add('is-active');
      byId('tab-' + button.getAttribute('data-tab')).classList.add('is-active');
      render();
    });
  });

  byId('doubleShift').addEventListener('click', function () {
    var price = Math.max(250, production() * 30 + 250);
    if (state.credits < price || Date.now() < state.doubleUntil) return;
    state.credits -= price;
    state.doubleUntil = Date.now() + 60000;
    showToast('Double Shift active', 'Passive income is doubled for 60 seconds.');
    render();
    saveState();
  });

  byId('rushOrder').addEventListener('click', function () {
    if (Date.now() < state.rushReady || production() <= 0) return;
    var reward = production() * 60;
    earn(reward);
    state.rushReady = Date.now() + 30000;
    showToast('Rush order complete', '+' + formatNumber(reward) + ' credits');
    render();
    saveState();
  });

  byId('radarButton').addEventListener('click', function () {
    if (state.radar || state.credits < 25000) return;
    state.credits -= 25000;
    state.radar = true;
    state.goldenAt = Date.now() + 15000 + Math.random() * 25000;
    showToast('Radar online', 'Golden cargo can now appear.');
    render();
    saveState();
  });

  byId('goldenCargo').addEventListener('click', function () {
    var reward = Math.max(250, production() * 120 + tapValue() * 50);
    earn(reward);
    byId('goldenCargo').hidden = true;
    showToast('Golden cargo!', '+' + formatNumber(reward) + ' credits');
    render();
    saveState();
  });

  byId('prestigeButton').addEventListener('click', function () {
    var gain = prestigeGain();
    if (gain < 1) return;
    if (!window.confirm('Reset this terminal for ' + gain + ' Logistics Token' + (gain === 1 ? '' : 's') + '?')) return;
    var keepTokens = state.tokens + gain;
    var keepPrestiges = state.prestiges + 1;
    var keepLifetime = state.lifetime;
    state = freshState();
    state.tokens = keepTokens;
    state.prestiges = keepPrestiges;
    state.lifetime = keepLifetime;
    showToast('Network expanded', 'Permanent production bonuses increased.');
    render();
    saveState();
  });

  byId('resetSave').addEventListener('click', function () {
    if (!window.confirm('Delete the complete Pocket Terminal save?')) return;
    try { localStorage.removeItem(KEY); } catch (e) {}
    state = freshState();
    render();
    saveState();
  });

  byId('collectOffline').addEventListener('click', function () {
    byId('offlineModal').classList.remove('is-visible');
    byId('offlineModal').setAttribute('aria-hidden', 'true');
    saveState();
  });

  (function applyOfflineIncome() {
    var now = Date.now();
    var awaySeconds = Math.min(OFFLINE_CAP_SECONDS, Math.max(0, (now - (Number(state.lastSeen) || now)) / 1000));
    if (awaySeconds > 20 && baseProduction() > 0) {
      var reward = baseProduction() * awaySeconds * 0.75;
      earn(reward);
      byId('offlineText').textContent = 'Your terminal worked for ' + Math.floor(awaySeconds / 60) + ' minutes and earned ' + formatNumber(reward) + ' credits.';
      byId('offlineModal').classList.add('is-visible');
      byId('offlineModal').setAttribute('aria-hidden', 'false');
    }
  }());

  setInterval(function () {
    var now = Date.now();
    var delta = Math.min(1, Math.max(0, (now - lastTick) / 1000));
    lastTick = now;
    earn(production() * delta);
    maybeSpawnGoldenCargo();
    render();
  }, 500);

  setInterval(saveState, 5000);
  document.addEventListener('visibilitychange', function () { if (document.hidden) saveState(); });
  window.addEventListener('pagehide', saveState);

  render();
}());
