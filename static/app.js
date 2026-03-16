/* ============================================================
   FRONT OFFICE — Complete App with Theme, Sorting, Lineup Mgmt
   ============================================================ */

const API = '';
const STATE = {
  userTeamId: null,
  teamAbbr: '',
  teamCity: '',
  teamName: '',
  currentDate: '',
  season: 2026,
  phase: 'spring_training',
  calMonth: null,
  calYear: null,
  tradeOffer: [],
  tradeRequest: [],
  tradeTeamId: null,
  _rosterData: null,
  _lineupData: null,
  _rotationData: null,
  sortStates: {},
  teams: [],
};

// ============================================================
// THEME SYSTEM
// ============================================================
function initTheme() {
  const saved = localStorage.getItem('fo-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon();
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('fo-theme', next);
  updateThemeIcon();
  showToast(`Switched to ${next} mode`, 'info');
}

function updateThemeIcon() {
  const theme = document.documentElement.getAttribute('data-theme');
  const btn = document.querySelector('.theme-toggle');
  if (btn) btn.textContent = theme === 'dark' ? '☀' : '🌙';
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ============================================================
// GRADE SYSTEM
// ============================================================
const GRADES = [
  [80, 'A+'], [75, 'A'], [70, 'A-'], [65, 'B+'], [60, 'B'],
  [55, 'B-'], [50, 'C+'], [45, 'C'], [40, 'C-'], [35, 'D+'],
  [30, 'D'], [25, 'D-'], [20, 'F']
];
function toGrade(val) {
  for (const [min, g] of GRADES) { if (val >= min) return g; }
  return 'F';
}
function gradeClass(val) {
  if (val >= 65) return 'grade-elite';
  if (val >= 50) return 'grade-good';
  if (val >= 35) return 'grade-avg';
  return 'grade-below';
}
function gradeHtml(val) {
  return `<span class="grade ${gradeClass(val)}">${toGrade(val)}</span>`;
}
function ratingBar(val) {
  const pct = Math.max(0, Math.min(100, ((val - 20) / 60) * 100));
  const cls = val >= 65 ? 'rf-elite' : val >= 50 ? 'rf-good' : val >= 35 ? 'rf-avg' : 'rf-below';
  return `<span class="rating-bar"><span class="rating-fill ${cls}" style="width:${pct}%"></span></span><span class="mono" style="font-size:10px">${val}</span>`;
}

// ============================================================
// UTILITIES
// ============================================================
function fmt$(n) {
  if (!n && n !== 0) return '$0';
  if (Math.abs(n) >= 1e9) return '$' + (n / 1e9).toFixed(1) + 'B';
  if (Math.abs(n) >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
  if (Math.abs(n) >= 1e3) return '$' + (n / 1e3).toFixed(0) + 'K';
  return '$' + n.toLocaleString();
}
function fmtDate(s) {
  if (!s) return '';
  const d = new Date(s + 'T12:00:00');
  return d.toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'});
}
function fmtAvg(h, ab) { return ab > 0 ? (h / ab).toFixed(3).replace(/^0/, '') : '.000'; }
function fmtEra(er, ipOuts) { return ipOuts > 0 ? (9 * er / (ipOuts / 3)).toFixed(2) : '0.00'; }
function fmtIp(outs) { return Math.floor(outs / 3) + '.' + (outs % 3); }
async function api(path, opts) {
  try {
    const r = await fetch(API + path, opts);
    return await r.json();
  } catch (e) { console.error('API error:', path, e); return null; }
}
async function post(path, body) {
  return api(path, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
}

// ============================================================
// TABLE SORTING
// ============================================================
function makeSortable(tableId) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const headers = table.querySelectorAll('th.sortable');
  headers.forEach((th, idx) => {
    th.onclick = () => sortTable(tableId, idx);
  });
}

function sortTable(tableId, colIdx, type = 'auto') {
  const table = document.getElementById(tableId);
  if (!table) return;
  const tbody = table.querySelector('tbody');
  if (!tbody) return;

  const state = STATE.sortStates[tableId] = STATE.sortStates[tableId] || {};
  const wasAsc = state.col === colIdx && state.asc;
  state.col = colIdx;
  state.asc = !wasAsc;

  const rows = Array.from(tbody.querySelectorAll('tr'));
  rows.sort((a, b) => {
    const aVal = a.cells[colIdx]?.textContent.trim() || '';
    const bVal = b.cells[colIdx]?.textContent.trim() || '';

    let aNum = parseFloat(aVal);
    let bNum = parseFloat(bVal);
    let cmp = 0;

    if (!isNaN(aNum) && !isNaN(bNum)) {
      cmp = aNum - bNum;
    } else {
      cmp = aVal.localeCompare(bVal);
    }

    return state.asc ? cmp : -cmp;
  });

  // Update UI
  const headers = table.querySelectorAll('th');
  headers.forEach((h, i) => {
    h.classList.remove('sorted', 'asc', 'desc');
    if (i === colIdx) {
      h.classList.add('sorted');
      if (state.asc) h.classList.add('asc');
    }
  });

  tbody.innerHTML = '';
  rows.forEach(r => tbody.appendChild(r));
}

// ============================================================
// INTRO NARRATIVE
// ============================================================
const TEAMS = [
  { abbr: 'PIT', city: 'Pittsburgh', name: 'Pirates',
    owner: 'Marcus Whitfield', ownerDesc: 'Impatient heir who just took over from his father',
    pitch: 'A proud franchise in a two-decade spiral. The farm system has talent. Whitfield wants someone who thinks differently.',
    challenge: 'Small market, skeptical fanbase, thin ML roster, top-10 farm system ready to arrive.' },
  { abbr: 'KC', city: 'Kansas City', name: 'Royals',
    owner: 'Dennis Cavanaugh', ownerDesc: 'Self-made tech billionaire, first year of ownership',
    pitch: 'Cavanaugh made his fortune in AI and bought the Royals because he believes baseball is the ultimate optimization problem.',
    challenge: 'Mid-market, aging core, an owner who gives you rope but expects results by year 3.' },
  { abbr: 'CIN', city: 'Cincinnati', name: 'Reds',
    owner: 'Patricia Langford', ownerDesc: 'Lifelong fan, inherited the team, tired of losing',
    pitch: 'Great American Ball Park is a hitter\'s paradise. Langford wants bold moves and doesn\'t care if the old guard disapproves.',
    challenge: 'Competitive division, homer-friendly park, passionate fanbase, payroll needs creative management.' },
];

function playIntro() {
  const el = document.getElementById('intro-narrative');
  el.innerHTML = `
    <p><span class="dim">February 14, 2026</span></p>
    <p>The call comes on a Tuesday morning. An unknown number. You almost don't answer.</p>
    <p>On the other end is a voice you don't recognize, an owner you've only read about. <span class="hl">"I just fired my General Manager. I've been watching you. I think you're exactly what this franchise needs."</span></p>
    <p>You're not a traditional baseball executive. You never played pro ball. You're an <span class="gold">outsider with an edge</span>. You understand systems, data, and how to build from nothing. The old guard thinks you're a joke. The owner thinks you're the future.</p>
    <p>Three teams are interested. Three owners willing to bet on you.</p>
    <p><span class="hl">Choose your franchise.</span></p>
  `;
  const choices = document.getElementById('intro-choices');
  choices.style.display = 'flex';
  choices.innerHTML = TEAMS.map((t, i) => `
    <div class="team-choice" onclick="selectTeam(${i})" id="tc-${i}">
      <h3>${t.city} ${t.name}</h3>
      <p><strong>${t.owner}</strong> - ${t.ownerDesc}</p>
      <p>${t.pitch}</p>
      <p style="color:var(--accent);margin-top:3px;font-size:11px">${t.challenge}</p>
    </div>
  `).join('');
}

function selectTeam(i) {
  document.querySelectorAll('.team-choice').forEach(e => e.classList.remove('selected'));
  document.getElementById('tc-' + i).classList.add('selected');
  STATE._introTeam = i;
  const start = document.getElementById('intro-start');
  start.style.display = 'block';
  start.style.opacity = '0';
  start.style.animation = 'fadeIn 0.4s ease forwards';
}

async function startGame() {
  const t = TEAMS[STATE._introTeam];
  const teams = await api('/teams');
  const match = teams?.find(x => x.abbreviation === t.abbr);
  if (match) {
    STATE.userTeamId = match.id;
    STATE.teamAbbr = match.abbreviation;
    STATE.teamCity = match.city;
    STATE.teamName = match.name;
  }
  await post('/set-user-team', { team_id: STATE.userTeamId });
  document.getElementById('intro-screen').classList.remove('active');
  document.getElementById('app').classList.add('active');
  await loadState();
  showScreen('calendar');
}

// ============================================================
// GAME STATE
// ============================================================
async function loadState() {
  const s = await api('/game-state');
  if (!s) return;
  STATE.currentDate = s.current_date;
  STATE.season = s.season;
  STATE.phase = s.phase;
  if (s.user_team_id && !STATE.userTeamId) STATE.userTeamId = s.user_team_id;

  if (STATE.userTeamId) {
    const t = await api('/team/' + STATE.userTeamId);
    if (t?.team) {
      STATE.teamAbbr = t.team.abbreviation;
      STATE.teamCity = t.team.city;
      STATE.teamName = t.team.name;
    }
    document.getElementById('hdr-team').textContent = `${STATE.teamCity} ${STATE.teamName}`;
    document.getElementById('hdr-date').textContent = fmtDate(STATE.currentDate);
    document.getElementById('hdr-phase').textContent = STATE.phase.replace('_', ' ');

    const standings = await api('/standings');
    if (standings) {
      for (const teams of Object.values(standings)) {
        const us = teams.find(x => x.team_id === STATE.userTeamId);
        if (us) { document.getElementById('hdr-record').textContent = `${us.wins}-${us.losses}`; break; }
      }
    }
  }

  if (!STATE.calMonth) {
    const d = new Date(STATE.currentDate + 'T12:00:00');
    STATE.calMonth = d.getMonth();
    STATE.calYear = d.getFullYear();
  }

  const teams = await api('/teams');
  STATE.teams = teams || [];
}

// ============================================================
// GLOBAL SEARCH
// ============================================================
function openGlobalSearch() {
  document.getElementById('global-search-modal').style.display = 'flex';
  document.getElementById('global-search-input').focus();
}

let _globalSearchTimeout = null;
async function globalSearchChange() {
  clearTimeout(_globalSearchTimeout);
  _globalSearchTimeout = setTimeout(_doGlobalSearch, 200);
}
async function _doGlobalSearch() {
  const q = document.getElementById('global-search-input').value.trim();
  const results = document.getElementById('global-search-results');
  if (!q) {
    results.innerHTML = '<div class="empty-state">Start typing to search...</div>';
    return;
  }

  results.innerHTML = '<div class="loading"><span class="spinner"></span> Searching...</div>';

  const matches = await api('/players/search?q=' + encodeURIComponent(q) + '&limit=20') || [];

  let html = '';
  if (matches.length) {
    html += '<div style="padding: 8px 0; border-bottom: 1px solid var(--border); font-size: 10px; color: var(--text-muted); text-transform: uppercase;">PLAYERS</div>';
    matches.forEach(p => {
      const isPit = p.position === 'SP' || p.position === 'RP';
      const ovr = isPit
        ? Math.round((p.stuff_rating + p.control_rating + p.stamina_rating) / 3)
        : Math.round((p.contact_rating + p.power_rating + p.fielding_rating) / 3);
      html += `<div style="padding: 8px 0; border-bottom: 1px solid var(--border); cursor: pointer; display: flex; justify-content: space-between; align-items: center;" onclick="closeGlobalSearch(); showPlayer(${p.id})">
        <div>
          <div style="font-weight: 600;">${p.first_name} ${p.last_name}</div>
          <div style="font-size: 11px; color: var(--text-dim);">${p.position} | Age ${p.age} | ${p.abbreviation || 'FA'}</div>
        </div>
        <div>${gradeHtml(ovr)}</div>
      </div>`;
    });
  } else {
    html = '<div class="empty-state">No players found</div>';
  }

  results.innerHTML = html;
}
function closeGlobalSearch() {
  document.getElementById('global-search-modal').style.display = 'none';
  document.getElementById('global-search-input').value = '';
}

// ============================================================
// NAVIGATION
// ============================================================
function showScreen(name) {
  document.querySelectorAll('.content-screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const screen = document.getElementById('s-' + name);
  if (screen) screen.classList.add('active');
  const btn = document.querySelector(`.nav-btn[data-s="${name}"]`);
  if (btn) btn.classList.add('active');
  const loaders = {
    calendar: loadCalendar, roster: loadRoster, transactions: loadTransactions, lineup: loadLineup, depthchart: loadDepthChart, standings: loadStandings,
    schedule: loadSchedule, finances: loadFinances, trades: loadTrades, draft: loadDraft,
    freeagents: loadFA, findplayers: loadFindPlayers, leaders: loadLeaders, messages: loadMessages,
  };
  if (loaders[name]) loaders[name]();
}

// ============================================================
// SIM CONTROLS
// ============================================================
async function simDays(n) {
  const btns = document.querySelectorAll('.btn-sim');
  btns.forEach(b => { b.disabled = true; b.textContent = '...'; });
  const r = await post('/sim/advance', { days: n });
  await loadState();
  const ticker = document.getElementById('ticker');
  if (r) ticker.textContent = `Simulated ${n}d, ${r.games_played} games | ${fmtDate(r.new_date)}`;
  const active = document.querySelector('.content-screen.active');
  if (active) showScreen(active.id.replace('s-', ''));
  btns.forEach((b, i) => { b.disabled = false; b.textContent = i === 0 ? '▶ Day' : '▶▶ Week'; });
}

// ============================================================
// CALENDAR HUB
// ============================================================
async function loadCalendar() {
  const el = document.getElementById('s-calendar');
  const m = STATE.calMonth, y = STATE.calYear;
  const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  const games = await api(`/schedule?limit=162&team_id=${STATE.userTeamId}`);
  const monthGames = games?.filter(g => {
    const d = new Date(g.game_date + 'T12:00:00');
    return d.getMonth() === m && d.getFullYear() === y;
  }) || [];

  const byDay = {};
  monthGames.forEach(g => {
    const day = parseInt(g.game_date.split('-')[2]);
    byDay[day] = g;
  });

  const today = new Date(STATE.currentDate + 'T12:00:00');
  const todayDay = today.getMonth() === m && today.getFullYear() === y ? today.getDate() : -1;
  const firstDay = new Date(y, m, 1).getDay();
  const daysInMonth = new Date(y, m + 1, 0).getDate();

  let calHtml = `
    <div class="cal-header">
      <div class="cal-nav">
        <button onclick="navMonth(-1)">◀</button>
        <span class="cal-month-label">${monthNames[m]} ${y}</span>
        <button onclick="navMonth(1)">▶</button>
      </div>
      <div>
        <button class="btn btn-sm" onclick="navToday()">Today</button>
      </div>
    </div>
    <div class="cal-grid">
      ${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => `<div class="cal-day-header">${d}</div>`).join('')}
  `;

  for (let i = 0; i < firstDay; i++) calHtml += '<div class="cal-day empty"></div>';

  for (let day = 1; day <= daysInMonth; day++) {
    const g = byDay[day];
    const isToday = day === todayDay;
    const dateStr = `${y}-${String(m+1).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
    const isFuture = dateStr > STATE.currentDate;
    let cls = 'cal-day';
    if (isToday) cls += ' today';
    if (isFuture) cls += ' future';

    let content = `<div class="day-num ${isToday ? 'today-num' : ''}">${day}</div>`;
    if (g) {
      const isHome = g.home_team_id === STATE.userTeamId;
      const opp = isHome ? g.away_abbr : g.home_abbr;
      const ha = isHome ? 'vs' : '@';
      if (g.is_played) {
        const myScore = isHome ? g.home_score : g.away_score;
        const theirScore = isHome ? g.away_score : g.home_score;
        const won = myScore > theirScore;
        content += `<div class="cal-game" onclick="showBoxScore(${g.id})">
          <span class="ha">${ha}</span> <span class="opp">${opp}</span><br>
          <span class="${won ? 'win' : 'loss'}">${won ? 'W' : 'L'}</span>
          <span class="score">${myScore}-${theirScore}</span>
        </div>`;
      } else {
        content += `<div class="cal-game">
          <span class="ha">${ha}</span> <span class="opp">${opp}</span>
        </div>`;
      }
    } else {
      content += '<div class="cal-off">OFF</div>';
    }

    if (isFuture && !g) {
      calHtml += `<div class="${cls}">${content}</div>`;
    } else if (isFuture) {
      calHtml += `<div class="${cls}" onclick="simToDate('${dateStr}')" title="Sim to ${dateStr}">${content}</div>`;
    } else {
      calHtml += `<div class="${cls}">${content}</div>`;
    }
  }

  calHtml += '</div>';

  calHtml += '<div class="cal-sidebar">';

  const played = (games || []).filter(g => g.is_played).slice(-8).reverse();
  calHtml += '<div class="card"><h3>Recent Results</h3>';
  if (played.length) {
    calHtml += played.map(g => {
      const isHome = g.home_team_id === STATE.userTeamId;
      const myScore = isHome ? g.home_score : g.away_score;
      const theirScore = isHome ? g.away_score : g.home_score;
      const won = myScore > theirScore;
      const opp = isHome ? g.away_abbr : g.home_abbr;
      return `<div class="leader-row" style="cursor:pointer" onclick="showBoxScore(${g.id})">
        <span class="leader-rank mono" style="color:${won ? 'var(--green)' : 'var(--red)'}">${won ? 'W' : 'L'}</span>
        <span class="leader-name">${isHome ? 'vs' : '@'} ${opp}</span>
        <span class="leader-val">${myScore}-${theirScore}</span>
      </div>`;
    }).join('');
  } else {
    calHtml += '<div class="empty-state">Season hasn\'t started yet</div>';
  }
  calHtml += '</div>';

  const standings = await api('/standings');
  let divHtml = '<div class="card"><h3>Division</h3>';
  if (standings) {
    for (const [div, teams] of Object.entries(standings)) {
      if (teams.find(t => t.team_id === STATE.userTeamId)) {
        divHtml += `<table><tr><th class="text-col">Team</th><th class="r">W</th><th class="r">L</th><th class="r">GB</th></tr>`;
        teams.forEach(t => {
          divHtml += `<tr class="${t.team_id === STATE.userTeamId ? 'user-team' : ''}">
            <td class="text-col">${t.abbreviation}</td><td class="r">${t.wins}</td><td class="r">${t.losses}</td>
            <td class="r">${t.gb === 0 ? '-' : t.gb.toFixed(1)}</td></tr>`;
        });
        divHtml += '</table>';
        break;
      }
    }
  }
  divHtml += '</div>';
  calHtml += divHtml + '</div>';

  el.innerHTML = calHtml;
}

function navMonth(delta) {
  STATE.calMonth += delta;
  if (STATE.calMonth > 11) { STATE.calMonth = 0; STATE.calYear++; }
  if (STATE.calMonth < 0) { STATE.calMonth = 11; STATE.calYear--; }
  loadCalendar();
}

function navToday() {
  const d = new Date(STATE.currentDate + 'T12:00:00');
  STATE.calMonth = d.getMonth();
  STATE.calYear = d.getFullYear();
  loadCalendar();
}

async function simToDate(dateStr) {
  const cur = new Date(STATE.currentDate + 'T12:00:00');
  const target = new Date(dateStr + 'T12:00:00');
  const days = Math.ceil((target - cur) / 86400000);
  if (days > 0 && days <= 60) await simDays(days);
}

// ============================================================
// BOX SCORE MODAL
// ============================================================
async function showBoxScore(scheduleId) {
  const modal = document.getElementById('player-modal');
  const body = document.getElementById('player-modal-body');
  modal.style.display = 'flex';
  body.innerHTML = '<div class="loading"><span class="spinner"></span> Loading box score...</div>';

  const data = await api('/game/' + scheduleId + '/boxscore');
  if (!data || !data.game) { body.innerHTML = '<div class="empty-state">Box score not available</div>'; return; }

  const g = data.game;
  const result = data.result;
  const batting = data.batting || [];
  const pitching = data.pitching || [];

  let innings = [];
  try { innings = JSON.parse(result?.innings_json || '[[],[]]'); } catch(e) {}
  const awayInnings = innings[0] || [];
  const homeInnings = innings[1] || [];
  const numInnings = Math.max(awayInnings.length, homeInnings.length, 9);

  let ls = `<table class="linescore"><tr><th class="team-col"></th>`;
  for (let i = 1; i <= numInnings; i++) ls += `<th>${i}</th>`;
  ls += `<th class="total">R</th><th class="total">H</th></tr>`;

  const awayH = batting.filter(b => b.team_id !== g.home_team_id).reduce((s, b) => s + (b.hits || 0), 0);
  const homeH = batting.filter(b => b.team_id === g.home_team_id).reduce((s, b) => s + (b.hits || 0), 0);

  ls += `<tr><td class="team-col">${g.away_abbr}</td>`;
  for (let i = 0; i < numInnings; i++) ls += `<td>${awayInnings[i] ?? '-'}</td>`;
  ls += `<td class="total">${g.away_score}</td><td class="total">${awayH}</td></tr>`;

  ls += `<tr><td class="team-col">${g.home_abbr}</td>`;
  for (let i = 0; i < numInnings; i++) ls += `<td>${homeInnings[i] !== null && homeInnings[i] !== undefined ? homeInnings[i] : '-'}</td>`;
  ls += `<td class="total">${g.home_score}</td><td class="total">${homeH}</td></tr></table>`;

  function battingTable(teamId, abbr) {
    const b = batting.filter(x => x.team_id === teamId);
    if (!b.length) return '';
    return `<div class="section-title" style="margin:8px 0 4px">${abbr} Batting</div>
    <div class="table-wrap"><table>
      <tr><th class="text-col">Batter</th><th class="r">AB</th><th class="r">R</th><th class="r">H</th>
      <th class="r">2B</th><th class="r">3B</th><th class="r">HR</th><th class="r">RBI</th>
      <th class="r">BB</th><th class="r">SO</th><th class="r">AVG</th></tr>
      ${b.map(p => `<tr>
        <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.first_name} ${p.last_name}</td>
        <td class="r">${p.ab}</td><td class="r">${p.runs}</td><td class="r">${p.hits}</td>
        <td class="r">${p.doubles}</td><td class="r">${p.triples}</td><td class="r">${p.hr}</td>
        <td class="r">${p.rbi}</td><td class="r">${p.bb}</td><td class="r">${p.so}</td>
        <td class="r">${fmtAvg(p.hits, p.ab)}</td>
      </tr>`).join('')}
    </table></div>`;
  }

  function pitchingTable(teamId, abbr) {
    const p = pitching.filter(x => x.team_id === teamId);
    if (!p.length) return '';
    return `<div class="section-title" style="margin:8px 0 4px">${abbr} Pitching</div>
    <div class="table-wrap"><table>
      <tr><th class="text-col">Pitcher</th><th class="r">IP</th><th class="r">H</th><th class="r">R</th>
      <th class="r">ER</th><th class="r">BB</th><th class="r">SO</th><th class="r">HR</th>
      <th class="r">PC</th><th class="c">Dec</th></tr>
      ${p.map(x => `<tr>
        <td class="text-col clickable" onclick="showPlayer(${x.player_id})">${x.first_name} ${x.last_name}</td>
        <td class="r">${fmtIp(x.ip_outs)}</td><td class="r">${x.hits_allowed}</td><td class="r">${x.runs_allowed}</td>
        <td class="r">${x.er}</td><td class="r">${x.bb}</td><td class="r">${x.so}</td>
        <td class="r">${x.hr_allowed}</td><td class="r">${x.pitches}</td>
        <td class="c" style="color:${x.decision === 'W' ? 'var(--green)' : x.decision === 'L' ? 'var(--red)' : 'var(--text-dim)'}">${x.decision || ''}</td>
      </tr>`).join('')}
    </table></div>`;
  }

  body.innerHTML = `
    <div style="padding:12px 16px;background:var(--bg-2);border-bottom:1px solid var(--border)">
      <div style="font-family:'SF Mono',monospace;font-size:14px;font-weight:700">${g.away_city} ${g.away_name} @ ${g.home_city} ${g.home_name}</div>
      <div style="color:var(--text-dim);font-size:11px">${g.game_date} | Att: ${result?.attendance?.toLocaleString() || 'N/A'}</div>
    </div>
    <div class="modal-tabs">
      <button class="modal-tab active" onclick="switchBoxScoreTab(event, 'summary')">Summary</button>
      <button class="modal-tab" onclick="switchBoxScoreTab(event, 'playbyplay')">Play-by-Play</button>
    </div>
    <div id="boxscore-tab-summary" class="modal-body">
      ${ls}
      ${battingTable(g.away_team_id, g.away_abbr)}
      ${battingTable(g.home_team_id, g.home_abbr)}
      ${pitchingTable(g.away_team_id, g.away_abbr)}
      ${pitchingTable(g.home_team_id, g.home_abbr)}
    </div>
    <div id="boxscore-tab-playbyplay" class="modal-body" style="display:none">
      <div id="playbyplay-content"><div class="loading"><span class="spinner"></span> Loading play-by-play...</div></div>
    </div>
  `;

  // Load play-by-play when tab is switched
  window._currentBoxScoreId = scheduleId;
}

// ============================================================
// ROSTER
// ============================================================
async function loadRoster() {
  if (!STATE.userTeamId) return;
  const data = await api('/roster/' + STATE.userTeamId);
  STATE._rosterData = data;
  renderRosterTab('active');
}

function filterRosterTable() {
  const search = document.getElementById('roster-search')?.value.toLowerCase() || '';
  const pos = document.getElementById('roster-pos-filter')?.value || '';
  const tab = document.querySelector('#s-roster .tab-btn.active')?.dataset.tab || 'active';
  renderRosterTab(tab);
}

function renderRosterTab(tab) {
  document.querySelectorAll('#s-roster .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`#s-roster .tab-btn[data-tab="${tab}"]`)?.classList.add('active');

  const data = STATE._rosterData;
  if (!data) return;
  const players = tab === 'active' ? data.active : tab === 'minors' ? data.minors : data.injured;
  const el = document.getElementById('roster-body');
  const isPitcher = p => p.position === 'SP' || p.position === 'RP';

  const search = document.getElementById('roster-search')?.value.toLowerCase() || '';
  const posFilt = document.getElementById('roster-pos-filter')?.value || '';

  let filtered = players.filter(p => {
    const nameMatch = `${p.first_name} ${p.last_name}`.toLowerCase().includes(search);
    const posMatch = !posFilt || p.position === posFilt;
    return nameMatch && posMatch;
  });

  const pos = filtered.filter(p => !isPitcher(p));
  const pit = filtered.filter(p => isPitcher(p));

  let html = `<div style="margin-bottom:4px;font-size:11px;color:var(--text-muted)">
    Active: ${data.active_count}/26 | 40-Man: ${data.forty_man_count}/40 | IL: ${data.injured_count} | Payroll: ${fmt$(data.payroll)}
  </div>`;

  if (pos.length) {
    html += `<div class="section-title" style="margin:8px 0 4px">Position Players</div>
    <div class="table-wrap"><table id="roster-pos-table">
      <thead><tr><th class="text-col">Name</th><th class="c">Pos</th><th class="r">Age</th><th class="c">B/T</th>
      <th class="c">Con</th><th class="c">Pow</th><th class="c">Spd</th><th class="c">Fld</th><th class="c">Arm</th>
      <th class="r">Salary</th><th class="r">Yrs</th></tr></thead>
      <tbody>
      ${pos.map(p => `<tr>
        <td class="text-col clickable" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
        <td class="c">${p.position}</td><td class="r">${p.age}</td><td class="c">${p.bats}/${p.throws}</td>
        <td class="c">${gradeHtml(p.contact_rating)}</td><td class="c">${gradeHtml(p.power_rating)}</td>
        <td class="c">${gradeHtml(p.speed_rating)}</td><td class="c">${gradeHtml(p.fielding_rating)}</td>
        <td class="c">${gradeHtml(p.arm_rating)}</td>
        <td class="r mono">${p.annual_salary ? fmt$(p.annual_salary) : 'min'}</td>
        <td class="r">${p.years_remaining || '-'}</td>
      </tr>`).join('')}
      </tbody>
    </table></div>`;
    makeSortable('roster-pos-table');
  }

  if (pit.length) {
    html += `<div class="section-title" style="margin:12px 0 4px">Pitchers</div>
    <div class="table-wrap"><table id="roster-pit-table">
      <thead><tr><th class="text-col">Name</th><th class="c">Pos</th><th class="r">Age</th><th class="c">T</th>
      <th class="c">Stuff</th><th class="c">Ctrl</th><th class="c">Stam</th>
      <th class="r">Salary</th><th class="r">Yrs</th></tr></thead>
      <tbody>
      ${pit.map(p => `<tr>
        <td class="text-col clickable" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
        <td class="c">${p.position}</td><td class="r">${p.age}</td><td class="c">${p.throws}</td>
        <td class="c">${gradeHtml(p.stuff_rating)}</td><td class="c">${gradeHtml(p.control_rating)}</td>
        <td class="c">${gradeHtml(p.stamina_rating)}</td>
        <td class="r mono">${p.annual_salary ? fmt$(p.annual_salary) : 'min'}</td>
        <td class="r">${p.years_remaining || '-'}</td>
      </tr>`).join('')}
      </tbody>
    </table></div>`;
    makeSortable('roster-pit-table');
  }

  if (!players.length) html = '<div class="empty-state">No players in this category</div>';
  el.innerHTML = html;
}

// ============================================================
// LINEUP MANAGEMENT
// ============================================================
async function loadLineup() {
  if (!STATE.userTeamId) return;
  const lineup = await api(`/roster/${STATE.userTeamId}/lineup`);
  const rotation = await api(`/roster/${STATE.userTeamId}/rotation`);
  STATE._lineupData = lineup || { vs_rhp: { batting_order: [] }, vs_lhp: { batting_order: [] }, dh: { batting_order: [] }, no_dh: { batting_order: [] } };
  STATE._rotationData = rotation || { rotation: [], bullpen: [] };
  STATE._currentLineupConfig = 'vs_rhp';
  showLineupConfig('vs_rhp');
  showLineupTab('batting');
}

function showLineupConfig(config) {
  STATE._currentLineupConfig = config;
  document.querySelectorAll('#s-lineup .section-tabs:nth-of-type(1) .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`#s-lineup .section-tabs:nth-of-type(1) .tab-btn[data-tab="${config}"]`)?.classList.add('active');
  renderBattingLineup();
}

function showLineupTab(tab) {
  document.querySelectorAll('.lineup-tab').forEach(t => t.style.display = 'none');
  document.querySelectorAll('#s-lineup .section-tabs:nth-of-type(2) .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`#s-lineup .section-tabs:nth-of-type(2) .tab-btn[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`lineup-${tab}`).style.display = 'block';

  if (tab === 'batting') renderBattingLineup();
  else if (tab === 'rotation') renderRotation();
  else if (tab === 'bullpen') renderBullpen();
}

async function renderBattingLineup() {
  const el = document.getElementById('lineup-batting');
  if (!STATE.userTeamId) return;

  const roster = await api(`/roster/${STATE.userTeamId}`);
  if (!roster) return;

  const config = STATE._currentLineupConfig || 'vs_rhp';
  if (!STATE._lineupData[config]) {
    STATE._lineupData[config] = { batting_order: [] };
  }
  const order = STATE._lineupData[config]?.batting_order || [];

  let html = '<div class="lineup-container"><div class="lineup-table">';
  html += `<div style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: var(--bg-2); border-bottom: 1px solid var(--border); font-size: 11px; text-transform: uppercase; color: var(--text-muted);">Lineup: ${config.replace('_', ' ')} | Drag to reorder</div>`;

  if (order.length) {
    order.forEach((pid, idx) => {
      const p = roster.active.find(x => x.id === pid);
      if (p) {
        html += `<div class="lineup-slot" draggable="true" data-idx="${idx}" ondragstart="dragStart(event, ${idx})" ondragover="dragOver(event)" ondragleave="dragLeave(event)" ondrop="dragDrop(event, ${idx})">
          <div class="lineup-num">${idx + 1}</div>
          <div class="lineup-pos">${p.position}</div>
          <div class="lineup-name">${p.first_name} ${p.last_name}</div>
          <div class="lineup-stats">${p.contact_rating}/${p.power_rating}/${p.speed_rating}</div>
        </div>`;
      }
    });
  } else {
    html += '<div class="empty-state" style="padding: 20px;">No lineup configured. Drag players to set order.</div>';
  }

  html += '</div><div class="lineup-preview"><h3>Available Hitters</h3>';
  const hitters = roster.active.filter(p => p.position !== 'SP' && p.position !== 'RP');
  hitters.forEach(p => {
    const inLineup = order.includes(p.id);
    html += `<div style="padding: 4px 0; font-size: 11px; cursor: pointer; border-bottom: 1px solid var(--border); opacity: ${inLineup ? 0.5 : 1};" onclick="addToLineup(${p.id})">${p.first_name} ${p.last_name} (${p.position})${inLineup ? ' ✓' : ''}</div>`;
  });
  html += '</div></div>';

  el.innerHTML = html;
}

function addToLineup(playerId) {
  const config = STATE._currentLineupConfig || 'vs_rhp';
  if (!STATE._lineupData[config]) {
    STATE._lineupData[config] = { batting_order: [] };
  }
  if (!STATE._lineupData[config].batting_order.find(pid => pid === playerId)) {
    STATE._lineupData[config].batting_order.push(playerId);
    renderBattingLineup();
  }
}

async function renderRotation() {
  const el = document.getElementById('lineup-rotation');
  if (!STATE.userTeamId) return;

  const roster = await api(`/roster/${STATE.userTeamId}`);
  if (!roster) return;

  const rotation = STATE._rotationData?.rotation || [];
  let html = '<div style="background: var(--bg-1); border: 1px solid var(--border); padding: 12px;">';
  html += '<div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">Starting Pitchers</div>';

  rotation.forEach((pid, idx) => {
    const p = roster.active.find(x => x.id === pid);
    if (p) {
      html += `<div style="display: flex; align-items: center; padding: 6px; margin-bottom: 4px; background: var(--bg-2); border-radius: 2px;">
        <div style="width: 24px; font-weight: 600; color: var(--accent);">${idx + 1}</div>
        <div style="flex: 1;">${p.first_name} ${p.last_name}</div>
        <div style="font-size: 10px; color: var(--text-dim);">${p.stuff_rating}/${p.control_rating}/${p.stamina_rating}</div>
      </div>`;
    }
  });

  if (!rotation.length) {
    html += '<div class="empty-state">No rotation configured</div>';
  }

  html += '</div><div style="background: var(--bg-1); border: 1px solid var(--border); padding: 12px; margin-top: 12px;">';
  html += '<div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">Available Starters</div>';
  const pitchers = roster.active.filter(p => p.position === 'SP');
  pitchers.forEach(p => {
    html += `<div style="padding: 4px 0; font-size: 11px; cursor: pointer; border-bottom: 1px solid var(--border);" onclick="addToRotation(${p.id})">${p.first_name} ${p.last_name} (STF:${p.stuff_rating})</div>`;
  });
  html += '</div>';

  el.innerHTML = html;
}

function addToRotation(playerId) {
  if (!STATE._rotationData.rotation.find(pid => pid === playerId)) {
    STATE._rotationData.rotation.push(playerId);
    renderRotation();
  }
}

async function renderBullpen() {
  const el = document.getElementById('lineup-bullpen');
  if (!STATE.userTeamId) return;

  const roster = await api(`/roster/${STATE.userTeamId}`);
  if (!roster) return;

  const bullpen = STATE._rotationData?.bullpen || [];
  let html = '<div style="background: var(--bg-1); border: 1px solid var(--border); padding: 12px;">';
  html += '<div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">Relief Pitchers</div>';

  bullpen.forEach((p, idx) => {
    html += `<div style="display: flex; align-items: center; padding: 6px; margin-bottom: 4px; background: var(--bg-2); border-radius: 2px;">
      <div style="flex: 1;">${p.name || 'Unknown'}</div>
      <div style="font-size: 10px; color: var(--text-dim);">${p.role || 'RP'}</div>
    </div>`;
  });

  if (!bullpen.length) {
    html += '<div class="empty-state">No bullpen configured</div>';
  }

  html += '</div><div style="background: var(--bg-1); border: 1px solid var(--border); padding: 12px; margin-top: 12px;">';
  html += '<div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px;">Available Relievers</div>';
  const relievers = roster.active.filter(p => p.position === 'RP');
  relievers.forEach(p => {
    html += `<div style="padding: 4px 0; font-size: 11px; cursor: pointer; border-bottom: 1px solid var(--border);" onclick="addToBullpen(${p.id}, '${p.first_name} ${p.last_name}')">${p.first_name} ${p.last_name} (CTL:${p.control_rating})</div>`;
  });
  html += '</div>';

  el.innerHTML = html;
}

function addToBullpen(playerId, playerName) {
  if (!STATE._rotationData.bullpen.find(p => p.id === playerId)) {
    STATE._rotationData.bullpen.push({ id: playerId, name: playerName, role: 'RP' });
    renderBullpen();
  }
}

async function saveLineup() {
  if (!STATE.userTeamId) return;
  showToast('Saving lineup...', 'info');
  await post(`/roster/${STATE.userTeamId}/lineup`, STATE._lineupData);
  await post(`/roster/${STATE.userTeamId}/rotation`, STATE._rotationData);
  showToast('Lineup saved successfully', 'success');
}

let draggedIdx = null;
function dragStart(e, idx) {
  draggedIdx = idx;
  e.target.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
}
function dragOver(e) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  const slot = e.target.closest('.lineup-slot');
  if (slot) slot.classList.add('drag-over');
}
function dragLeave(e) {
  const slot = e.target.closest('.lineup-slot');
  if (slot) slot.classList.remove('drag-over');
}
function dragDrop(e, idx) {
  e.preventDefault();
  const slot = e.target.closest('.lineup-slot');
  if (slot) slot.classList.remove('drag-over');
  if (draggedIdx !== null && draggedIdx !== idx) {
    const config = STATE._currentLineupConfig || 'vs_rhp';
    if (!STATE._lineupData[config]) {
      STATE._lineupData[config] = { batting_order: [] };
    }
    const order = STATE._lineupData[config].batting_order;
    [order[draggedIdx], order[idx]] = [order[idx], order[draggedIdx]];
    renderBattingLineup();
  }
  draggedIdx = null;
}

// ============================================================
// FIND PLAYERS
// ============================================================
async function loadFindPlayers() {
  const teamSel = document.getElementById('find-team');
  if (teamSel) {
    teamSel.innerHTML = '<option value="">All Teams</option>' +
      (STATE.teams || []).map(t => `<option value="${t.id}">${t.abbreviation}</option>`).join('');
  }
}

let _searchTimeout = null;
async function searchPlayers() {
  clearTimeout(_searchTimeout);
  _searchTimeout = setTimeout(_doSearchPlayers, 250);
}
async function _doSearchPlayers() {
  const q = document.getElementById('find-search')?.value || '';
  const pos = document.getElementById('find-pos')?.value || '';
  const teamId = document.getElementById('find-team')?.value || '';
  const results = document.getElementById('find-results');

  if (!q && !pos && !teamId) {
    results.innerHTML = '<div class="empty-state">Search for players by name, position, or team</div>';
    return;
  }

  results.innerHTML = '<div class="loading"><span class="spinner"></span> Searching...</div>';

  let params = new URLSearchParams();
  if (q) params.set('q', q);
  if (pos) params.set('position', pos);
  if (teamId) params.set('team_id', teamId);
  params.set('limit', '50');

  const matches = await api('/players/search?' + params.toString());

  if (!matches?.length) {
    results.innerHTML = '<div class="empty-state">No players found</div>';
    return;
  }

  let html = `<div class="table-wrap"><table id="find-table">
    <thead><tr>
      <th class="text-col sortable">Name</th><th class="c sortable">Pos</th>
      <th class="r sortable">Age</th><th class="c">B/T</th>
      <th class="r sortable">OVR</th><th class="text-col">Team</th>
      <th class="r sortable">Salary</th><th class="c">Status</th>
    </tr></thead><tbody>`;
  matches.forEach(p => {
    const isPit = p.position === 'SP' || p.position === 'RP';
    const ovr = isPit
      ? Math.round((p.stuff_rating + p.control_rating + p.stamina_rating) / 3)
      : Math.round((p.contact_rating + p.power_rating + p.fielding_rating) / 3);
    html += `<tr onclick="showPlayer(${p.id})" style="cursor:pointer;">
      <td class="text-col">${p.first_name} ${p.last_name}</td>
      <td class="c">${p.position}</td><td class="r">${p.age}</td><td class="c">${p.bats}/${p.throws}</td>
      <td class="r">${gradeHtml(ovr)}</td>
      <td class="text-col">${p.abbreviation || 'FA'}</td>
      <td class="r mono">${p.annual_salary ? fmt$(p.annual_salary) : 'min'}</td>
      <td class="c" style="font-size:10px">${p.roster_status || ''}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  results.innerHTML = html;
  makeSortable('find-table');
}

// ============================================================
// PLAYER MODAL (TABS)
// ============================================================
async function showPlayer(pid) {
  const modal = document.getElementById('player-modal');
  const body = document.getElementById('player-modal-body');
  modal.style.display = 'flex';
  body.innerHTML = '<div class="loading"><span class="spinner"></span></div>';

  const d = await api('/player/' + pid);
  if (!d?.player) { body.innerHTML = '<div class="empty-state">Player not found</div>'; return; }
  const p = d.player;
  const isPit = p.position === 'SP' || p.position === 'RP';

  const ratings = isPit
    ? [['Stuff', p.stuff_rating], ['Control', p.control_rating], ['Stamina', p.stamina_rating]]
    : [['Contact', p.contact_rating], ['Power', p.power_rating], ['Speed', p.speed_rating], ['Fielding', p.fielding_rating], ['Arm', p.arm_rating]];

  const personality = [['Ego', p.ego], ['Lead', p.leadership], ['Work', p.work_ethic], ['Clutch', p.clutch], ['Dura', p.durability]];

  const gradesHtml = ratings.map(([l, v]) => `
    <div class="grade-box"><div class="grade-label">${l}</div>
    <div class="grade-value ${gradeClass(v)}">${toGrade(v)}</div>
    <div class="grade-num">${v}</div></div>`).join('');

  const persHtml = personality.map(([l, v]) => `
    <div class="grade-box"><div class="grade-label">${l}</div>
    <div class="grade-value ${gradeClass(v)}">${toGrade(v)}</div>
    <div class="grade-num">${v}</div></div>`).join('');

  let statsHtml = '';
  if (d.batting_stats?.length) {
    const s = d.batting_stats[0];
    statsHtml += `<div class="section-title" style="margin:12px 0 4px">${STATE.season} Stats</div>
    <div class="table-wrap"><table>
      <tr><th class="r">G</th><th class="r">AB</th><th class="r">R</th><th class="r">H</th><th class="r">2B</th>
      <th class="r">3B</th><th class="r">HR</th><th class="r">RBI</th><th class="r">BB</th><th class="r">SO</th>
      <th class="r">SB</th><th class="r">AVG</th><th class="r">OBP</th><th class="r">SLG</th></tr>
      <tr><td class="r">${s.games}</td><td class="r">${s.ab}</td><td class="r">${s.runs}</td><td class="r">${s.hits}</td>
      <td class="r">${s.doubles}</td><td class="r">${s.triples}</td><td class="r">${s.hr}</td><td class="r">${s.rbi}</td>
      <td class="r">${s.bb}</td><td class="r">${s.so}</td><td class="r">${s.sb}</td>
      <td class="r">${fmtAvg(s.hits, s.ab)}</td>
      <td class="r">${s.ab > 0 ? ((s.hits+s.bb+(s.hbp||0))/(s.ab+s.bb+(s.hbp||0)+(s.sf||0))).toFixed(3).replace(/^0/,'') : '.000'}</td>
      <td class="r">${s.ab > 0 ? ((s.hits+s.doubles+s.triples*2+s.hr*3)/s.ab).toFixed(3).replace(/^0/,'') : '.000'}</td></tr>
    </table></div>`;
  }
  if (d.pitching_stats?.length) {
    const s = d.pitching_stats[0];
    statsHtml += `<div class="section-title" style="margin:12px 0 4px">${STATE.season} Pitching</div>
    <div class="table-wrap"><table>
      <tr><th class="r">G</th><th class="r">GS</th><th class="r">W</th><th class="r">L</th><th class="r">SV</th>
      <th class="r">IP</th><th class="r">H</th><th class="r">ER</th><th class="r">BB</th><th class="r">SO</th>
      <th class="r">HR</th><th class="r">ERA</th><th class="r">WHIP</th></tr>
      <tr><td class="r">${s.games}</td><td class="r">${s.games_started}</td><td class="r">${s.wins}</td><td class="r">${s.losses}</td>
      <td class="r">${s.saves}</td><td class="r">${fmtIp(s.ip_outs)}</td><td class="r">${s.hits_allowed}</td>
      <td class="r">${s.er}</td><td class="r">${s.bb}</td><td class="r">${s.so}</td><td class="r">${s.hr_allowed}</td>
      <td class="r">${fmtEra(s.er, s.ip_outs)}</td>
      <td class="r">${s.ip_outs > 0 ? ((s.hits_allowed+s.bb)/(s.ip_outs/3)).toFixed(2) : '0.00'}</td></tr>
    </table></div>`;
  }

  body.innerHTML = `
    <div class="modal-header">
      <div>
        <div class="player-name">${p.first_name} ${p.last_name}</div>
        <div class="player-meta">${p.position} | Age ${p.age} | ${p.bats}/${p.throws} | ${p.birth_country || 'USA'}</div>
        <div class="player-meta">${p.abbreviation || ''} ${p.team_name || 'Free Agent'}</div>
      </div>
      <div class="player-contract">
        <div class="player-salary">${p.annual_salary ? fmt$(p.annual_salary) + '/yr' : 'Pre-Arb'}</div>
        <div class="player-contract-detail">${p.years_remaining ? p.years_remaining + ' yr remaining' : ''}</div>
        ${p.no_trade_clause ? '<div style="color:var(--red);font-size:10px">NO-TRADE CLAUSE</div>' : ''}
        <button class="btn btn-sm" style="margin-top: 6px;" onclick="compareWithPlayer(${p.id})">Compare</button>
      </div>
    </div>
    <div class="modal-tabs">
      <button class="modal-tab active" onclick="switchPlayerTab(event, 'overview')">Overview</button>
      <button class="modal-tab" onclick="switchPlayerTab(event, 'stats')">Stats</button>
      <button class="modal-tab" onclick="switchPlayerTab(event, 'scouting')">Scouting</button>
    </div>
    <div class="modal-body">
      <div id="player-tab-overview">
        <div class="section-title">${isPit ? 'Pitching' : 'Hitting'} Grades</div>
        <div class="grades-row">${gradesHtml}</div>
        <div class="section-title" style="margin-top:12px">Personality</div>
        <div class="grades-row">${persHtml}</div>
      </div>
      <div id="player-tab-stats" style="display:none">
        ${statsHtml || '<div class="empty-state">No stats available</div>'}
      </div>
      <div id="player-tab-scouting" style="display:none">
        <div id="scout-${p.id}" class="scouting-report" style="display:none"></div>
        <button class="btn btn-primary btn-sm" onclick="genScout(${p.id})">Generate Scout Report</button>
      </div>
    </div>
  `;
}

function switchPlayerTab(e, tab) {
  document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('[id^="player-tab-"]').forEach(t => t.style.display = 'none');
  e.target.classList.add('active');
  document.getElementById(`player-tab-${tab}`).style.display = 'block';
}

function switchBoxScoreTab(e, tab) {
  document.querySelectorAll('.modal-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('[id^="boxscore-tab-"]').forEach(t => t.style.display = 'none');
  e.target.classList.add('active');
  document.getElementById(`boxscore-tab-${tab}`).style.display = 'block';

  if (tab === 'playbyplay') {
    loadPlayByPlay(window._currentBoxScoreId);
  }
}

async function loadPlayByPlay(scheduleId) {
  const el = document.getElementById('playbyplay-content');
  el.innerHTML = '<div class="loading"><span class="spinner"></span> Loading play-by-play...</div>';

  const plays = await api(`/game/${scheduleId}/play-by-play`);
  if (!plays || plays.length === 0) {
    el.innerHTML = '<div class="empty-state">No play-by-play data available</div>';
    return;
  }

  let html = '<div class="playbyplay-container">';
  plays.forEach(play => {
    const isScoring = play.scoring || false;
    const isHomeRun = play.home_run || false;
    const isError = play.error || false;

    const bgColor = isHomeRun ? 'rgba(250,204,21,0.1)' : isScoring ? 'rgba(74,222,128,0.1)' : isError ? 'rgba(248,113,113,0.1)' : 'transparent';
    const borderColor = isHomeRun ? 'var(--orange)' : isScoring ? 'var(--green)' : isError ? 'var(--red)' : 'var(--border)';

    html += `<div style="padding: 12px; margin: 8px 0; border: 1px solid ${borderColor}; border-left: 3px solid ${borderColor}; background: ${bgColor}; border-radius: 2px;">
      <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px;">
        ${play.inning} | ${play.count || ''}
      </div>
      <div style="font-size: 12px; margin-bottom: 4px;">
        <strong>${play.batter || 'Unknown'}</strong> vs <strong>${play.pitcher || 'Unknown'}</strong>
      </div>
      <div style="font-size: 12px; margin-bottom: 6px; color: var(--text);">
        ${play.description || play.outcome || 'Play'}
      </div>
      <div style="font-size: 10px; color: var(--text-dim);">
        Score: ${play.away_score || 0}-${play.home_score || 0}
      </div>
    </div>`;
  });
  html += '</div>';
  el.innerHTML = html;
}

async function genScout(pid) {
  const el = document.getElementById('scout-' + pid);
  el.style.display = 'block';
  el.innerHTML = '<span class="spinner"></span> Scout evaluating player...';
  const r = await api('/player/' + pid + '/scouting-report-full');
  if (!r || r.error) { el.innerHTML = 'Scout report unavailable.'; return; }

  const pg = r.present_grades || {};
  const fg = r.future_grades || {};
  const margin = r.uncertainty_margin || 0;

  function gradePair(label, pres, fut) {
    const pCls = gradeClass(pres);
    const fCls = gradeClass(fut);
    return `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);font-size:11px">
      <span style="width:70px;color:var(--text-dim)">${label}</span>
      <span class="grade-pair"><span class="${pCls}" style="font-weight:700">${pres}</span><span style="color:var(--text-muted)">/</span><span class="${fCls}" style="font-weight:700">${fut}</span></span>
      <span style="color:var(--text-muted);font-size:9px">+/-${margin}</span>
    </div>`;
  }

  let gradesHtml = '<div class="scouting-grid"><div>';
  gradesHtml += '<div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;padding-bottom:4px;border-bottom:1px solid var(--accent)">Present / Future Grades (20-80)</div>';
  for (const [key, val] of Object.entries(pg)) {
    gradesHtml += gradePair(key.charAt(0).toUpperCase() + key.slice(1), val, fg[key] || val);
  }
  gradesHtml += '</div><div>';

  // OFP, ceiling, floor, risk
  gradesHtml += `<div class="card" style="padding:10px">
    <div style="text-align:center;margin-bottom:8px">
      <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px">Overall Future Potential</div>
      <div class="grade ${gradeClass(r.ofp)}" style="font-size:28px;width:auto">${r.ofp}</div>
    </div>
    <div style="font-size:11px;margin-top:8px">
      <div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="color:var(--green)">Ceiling</span><span>${r.ceiling || 'N/A'}</span></div>
      <div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="color:var(--red)">Floor</span><span>${r.floor || 'N/A'}</span></div>
      <div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="color:var(--text-dim)">Risk</span><span style="text-transform:capitalize">${r.risk_level || 'N/A'}</span></div>
      <div style="display:flex;justify-content:space-between"><span style="color:var(--text-dim)">ETA</span><span>${r.eta || 'N/A'}</span></div>
    </div>
  </div>`;
  gradesHtml += '</div></div>';

  // MLB comp
  let compHtml = '';
  if (r.mlb_comp) {
    const c = r.mlb_comp;
    compHtml = `<div style="background:var(--bg-2);border:1px solid var(--border);padding:10px;margin:12px 0;border-radius:2px">
      <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">MLB Comparison</div>
      <div style="font-size:14px;font-weight:700;color:var(--accent)">${c.name}</div>
      <div style="font-size:11px;color:var(--text-dim)">${c.position} | ${c.years}</div>
      <div style="font-size:11px;color:var(--text-dim);margin-top:2px">${c.peak_stats || ''}</div>
      <div style="font-size:12px;margin-top:6px;color:var(--text);line-height:1.5">${c.description || c.reasoning || ''}</div>
    </div>`;
  }

  // Makeup
  let makeupHtml = '';
  if (r.makeup) {
    const m = r.makeup;
    makeupHtml = `<div style="display:flex;gap:8px;margin:8px 0;flex-wrap:wrap">
      ${[['Work Ethic', m.work_ethic], ['Leadership', m.leadership], ['Clutch', m.clutch], ['Ego', m.ego]].map(([l, v]) =>
        `<div class="grade-box" style="min-width:60px"><div class="grade-label">${l}</div><div class="grade-value ${gradeClass(v)}" style="font-size:14px">${v}</div></div>`
      ).join('')}
    </div>`;
  }

  // Narrative
  const narrativeHtml = r.narrative
    ? `<div class="scouting-report" style="font-style:italic">"${r.narrative}"</div>`
    : '';

  el.innerHTML = gradesHtml + compHtml + makeupHtml + narrativeHtml +
    `<div style="font-size:9px;color:var(--text-muted);margin-top:8px;text-align:right">Scout confidence: ${r.scout_quality || 'N/A'}/100 | Margin: +/-${margin}</div>`;
}

function closeModal() {
  document.getElementById('player-modal').style.display = 'none';
  document.getElementById('global-search-modal').style.display = 'none';
}

function closeComparisonModal() {
  document.getElementById('comparison-modal').style.display = 'none';
}

// ============================================================
// PLAYER COMPARISON
// ============================================================
let comparisonTarget = null;

async function startComparison(pid) {
  comparisonTarget = pid;
  showToast('Click another player to compare', 'info');
}

async function compareWithPlayer(pid) {
  if (!comparisonTarget || comparisonTarget === pid) {
    showToast('Select two different players to compare', 'error');
    return;
  }

  const p1Data = await api('/player/' + comparisonTarget);
  const p2Data = await api('/player/' + pid);

  if (!p1Data?.player || !p2Data?.player) {
    showToast('Could not load player data', 'error');
    return;
  }

  const p1 = p1Data.player;
  const p2 = p2Data.player;

  const isPit1 = p1.position === 'SP' || p1.position === 'RP';
  const isPit2 = p2.position === 'SP' || p2.position === 'RP';

  let html = `<div class="comparison-header">
    <h2>Player Comparison</h2>
  </div>
  <div class="comparison-grid">
    <div class="comparison-column">
      <div class="comparison-player-info">
        <div class="comparison-name">${p1.first_name} ${p1.last_name}</div>
        <div class="comparison-meta">${p1.position} | Age ${p1.age} | ${p1.abbreviation || 'FA'}</div>
        <div class="comparison-meta" style="color: var(--accent);">${p1.annual_salary ? fmt$(p1.annual_salary) : 'Pre-Arb'}/yr</div>
      </div>
    </div>
    <div class="comparison-column-center">
      <div class="comparison-header-spacer"></div>
    </div>
    <div class="comparison-column">
      <div class="comparison-player-info">
        <div class="comparison-name">${p2.first_name} ${p2.last_name}</div>
        <div class="comparison-meta">${p2.position} | Age ${p2.age} | ${p2.abbreviation || 'FA'}</div>
        <div class="comparison-meta" style="color: var(--accent);">${p2.annual_salary ? fmt$(p2.annual_salary) : 'Pre-Arb'}/yr</div>
      </div>
    </div>
  </div>`;

  // Skills comparison
  const skills1 = isPit1
    ? [['Stuff', p1.stuff_rating], ['Control', p1.control_rating], ['Stamina', p1.stamina_rating]]
    : [['Contact', p1.contact_rating], ['Power', p1.power_rating], ['Speed', p1.speed_rating], ['Fielding', p1.fielding_rating]];

  const skills2 = isPit2
    ? [['Stuff', p2.stuff_rating], ['Control', p2.control_rating], ['Stamina', p2.stamina_rating]]
    : [['Contact', p2.contact_rating], ['Power', p2.power_rating], ['Speed', p2.speed_rating], ['Fielding', p2.fielding_rating]];

  html += `<div style="margin: 16px 0;"><div class="section-title">Skills</div>
    <div class="comparison-grid">`;

  const maxSkills = Math.max(skills1.length, skills2.length);
  for (let i = 0; i < maxSkills; i++) {
    const s1 = skills1[i];
    const s2 = skills2[i];
    const v1 = s1 ? s1[1] : 0;
    const v2 = s2 ? s2[1] : 0;
    const better = v1 > v2 ? 1 : v2 > v1 ? 2 : 0;

    html += `<div class="comparison-column">
      <div style="text-align: center; padding: 8px; background: var(--bg-2); margin-bottom: 4px;">
        <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">${s1 ? s1[0] : ''}</div>
        <div class="grade ${gradeClass(v1)}" style="font-size: 18px;${better === 1 ? 'color: var(--green); font-weight: 700;' : ''}">${toGrade(v1)}</div>
        <div style="font-size: 10px; color: var(--text-dim);">${v1}</div>
      </div>
    </div>
    <div class="comparison-column-center"></div>
    <div class="comparison-column">
      <div style="text-align: center; padding: 8px; background: var(--bg-2); margin-bottom: 4px;">
        <div style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">${s2 ? s2[0] : ''}</div>
        <div class="grade ${gradeClass(v2)}" style="font-size: 18px;${better === 2 ? 'color: var(--green); font-weight: 700;' : ''}">${toGrade(v2)}</div>
        <div style="font-size: 10px; color: var(--text-dim);">${v2}</div>
      </div>
    </div>`;
  }

  html += `</div></div>`;

  document.getElementById('comparison-body').innerHTML = html;
  document.getElementById('comparison-modal').style.display = 'flex';
  comparisonTarget = null;
}

// ============================================================
// STANDINGS
// ============================================================
async function loadStandings() {
  const standings = await api('/standings');
  if (!standings) return;
  for (const league of ['AL', 'NL']) {
    const el = document.getElementById('stnd-' + league.toLowerCase());
    const lName = league === 'AL' ? 'American League' : 'National League';
    let html = `<div class="section-title" style="margin-bottom:8px">${lName}</div>`;
    for (const div of ['East', 'Central', 'West']) {
      const key = `${league} ${div}`;
      const teams = standings[key];
      if (!teams) continue;
      html += `<div class="section-title" style="font-size:9px;margin:8px 0 2px;color:var(--text-muted)">${div}</div>
      <div class="table-wrap" style="margin-bottom:8px"><table id="stand-${league}-${div}">
        <thead><tr><th class="text-col">Team</th><th class="r">W</th><th class="r">L</th><th class="r">Pct</th>
        <th class="r">GB</th><th class="r separator">RS</th><th class="r">RA</th><th class="r">Diff</th></tr></thead>
        <tbody>
        ${teams.map(t => `<tr class="${t.team_id === STATE.userTeamId ? 'user-team' : ''}">
          <td class="text-col"><strong>${t.abbreviation}</strong> ${t.name}</td>
          <td class="r">${t.wins}</td><td class="r">${t.losses}</td><td class="r">${t.pct.toFixed(3)}</td>
          <td class="r">${t.gb === 0 ? '-' : t.gb.toFixed(1)}</td>
          <td class="r separator">${t.runs_scored}</td><td class="r">${t.runs_allowed}</td>
          <td class="r ${t.diff > 0 ? 'positive' : t.diff < 0 ? 'negative' : ''}">${t.diff > 0 ? '+' : ''}${t.diff}</td>
        </tr>`).join('')}
        </tbody>
      </table></div>`;
      makeSortable(`stand-${league}-${div}`);
    }
    el.innerHTML = html;
  }
}

// ============================================================
// SCHEDULE
// ============================================================
async function loadSchedule() {
  const el = document.getElementById('sched-body');
  el.innerHTML = '<div class="loading"><span class="spinner"></span></div>';
  const games = await api(`/schedule?limit=40${STATE.userTeamId ? '&team_id=' + STATE.userTeamId : ''}`);
  if (!games?.length) { el.innerHTML = '<div class="empty-state">No games found</div>'; return; }
  el.innerHTML = `<div class="table-wrap"><table id="sched-table">
    <thead><tr><th class="text-col">Date</th><th class="text-col">Away</th><th class="c"></th><th class="text-col">Home</th><th class="r">Score</th><th class="c"></th></tr></thead>
    <tbody>
    ${games.map(g => `<tr class="${g.home_team_id === STATE.userTeamId || g.away_team_id === STATE.userTeamId ? 'user-team' : ''}">
      <td class="text-col">${g.game_date}</td>
      <td class="text-col">${g.away_abbr}</td><td class="c" style="color:var(--text-muted)">@</td>
      <td class="text-col">${g.home_abbr}</td>
      <td class="r">${g.is_played ? g.away_score + '-' + g.home_score : '-'}</td>
      <td class="c">${g.is_played ? '<span class="clickable" onclick="showBoxScore(' + g.id + ')">Box</span>' : ''}</td>
    </tr>`).join('')}
    </tbody>
  </table></div>`;
  makeSortable('sched-table');
}

// ============================================================
// FINANCES
// ============================================================
async function loadFinances() {
  if (!STATE.userTeamId) return;
  const el = document.getElementById('fin-body');
  el.innerHTML = '<div class="loading"><span class="spinner"></span></div>';
  const [fin, team] = await Promise.all([
    api('/finances/' + STATE.userTeamId + '/details'),
    api('/finances/' + STATE.userTeamId),
  ]);
  if (!fin) { el.innerHTML = '<div class="empty-state">Financial data unavailable</div>'; return; }

  el.innerHTML = `<div class="fin-grid">
    <div class="card"><h3>Revenue</h3>
      <div class="fin-line"><span>Tickets</span><span>${fmt$(fin.ticket_revenue)}</span></div>
      <div class="fin-line"><span>Concessions</span><span>${fmt$(fin.concession_revenue)}</span></div>
      <div class="fin-line"><span>Broadcast</span><span>${fmt$(fin.broadcast_revenue)}</span></div>
      <div class="fin-line"><span>Merchandise</span><span>${fmt$(fin.merchandise_revenue)}</span></div>
      <div class="fin-line total"><span>Total Revenue</span><span class="positive">${fmt$(fin.total_revenue)}</span></div>
    </div>
    <div class="card"><h3>Expenses</h3>
      <div class="fin-line"><span>Payroll</span><span>${fmt$(fin.payroll)}</span></div>
      <div class="fin-line"><span>Farm System</span><span>${fmt$(fin.farm_expenses)}</span></div>
      <div class="fin-line"><span>Medical Staff</span><span>${fmt$(fin.medical_expenses)}</span></div>
      <div class="fin-line"><span>Scouting</span><span>${fmt$(fin.scouting_expenses)}</span></div>
      <div class="fin-line"><span>Stadium Ops</span><span>${fmt$(fin.stadium_expenses)}</span></div>
      <div class="fin-line"><span>Owner Dividends</span><span>${fmt$(fin.owner_dividends)}</span></div>
      <div class="fin-line total"><span>Total Expenses</span><span class="negative">${fmt$(fin.total_expenses)}</span></div>
    </div>
    <div class="card"><h3>Bottom Line</h3>
      <div class="fin-line total"><span>Profit/Loss</span><span class="${fin.profit >= 0 ? 'positive' : 'negative'}">${fmt$(fin.profit)}</span></div>
      <div class="fin-line"><span>Cash on Hand</span><span>${fmt$(team?.cash)}</span></div>
      <div class="fin-line"><span>Franchise Value</span><span>${fmt$(team?.franchise_value)}</span></div>
      <div class="fin-line"><span>Avg Attendance</span><span>${(fin.attendance_avg || 0).toLocaleString()}</span></div>
    </div>
    <div class="card"><h3>Budget Allocations</h3>
      <div class="slider-group">
        <label class="slider-label">Farm System</label>
        <input type="range" min="0" max="5000000" step="100000" value="${team?.farm_budget || 0}" oninput="updateBudgetDisplay(event)" onchange="updateBudget('farm', this.value)">
        <span class="slider-value">${fmt$(team?.farm_budget || 0)}</span>
      </div>
      <div class="slider-group">
        <label class="slider-label">Medical Staff</label>
        <input type="range" min="0" max="5000000" step="100000" value="${team?.medical_budget || 0}" oninput="updateBudgetDisplay(event)" onchange="updateBudget('medical', this.value)">
        <span class="slider-value">${fmt$(team?.medical_budget || 0)}</span>
      </div>
      <div class="slider-group">
        <label class="slider-label">Scouting</label>
        <input type="range" min="0" max="5000000" step="100000" value="${team?.scouting_budget || 0}" oninput="updateBudgetDisplay(event)" onchange="updateBudget('scouting', this.value)">
        <span class="slider-value">${fmt$(team?.scouting_budget || 0)}</span>
      </div>
    </div>
    <div class="card"><h3>Pricing Strategy</h3>
      <div class="slider-group">
        <label class="slider-label">Ticket Price</label>
        <input type="range" min="50" max="200" step="5" value="${team?.ticket_price_pct || 100}" oninput="updatePricingDisplay(event)" onchange="updateBudget('ticket_price', this.value)">
        <span class="slider-value">${team?.ticket_price_pct || 100}%</span>
      </div>
      <div class="slider-group">
        <label class="slider-label">Concession Price</label>
        <input type="range" min="50" max="200" step="5" value="${team?.concession_price_pct || 100}" oninput="updatePricingDisplay(event)" onchange="updateBudget('concession_price', this.value)">
        <span class="slider-value">${team?.concession_price_pct || 100}%</span>
      </div>
    </div>
  </div>`;
}

function updateBudgetDisplay(e) {
  const slider = e.target;
  const display = slider.parentElement.querySelector('.slider-value');
  if (display) display.textContent = fmt$(parseInt(slider.value));
}

function updatePricingDisplay(e) {
  const slider = e.target;
  const display = slider.parentElement.querySelector('.slider-value');
  if (display) display.textContent = slider.value + '%';
}

async function updateBudget(type, value) {
  if (!STATE.userTeamId) return;
  const numValue = parseInt(value);

  // Send to server
  try {
    // Handle pricing separately from budget
    if (type === 'ticket_price' || type === 'concession_price') {
      const payload = {};
      if (type === 'ticket_price') payload.ticket_price_pct = numValue;
      if (type === 'concession_price') payload.concession_price_pct = numValue;

      await post(`/finances/${STATE.userTeamId}/pricing`, payload);
      showToast('Pricing updated', 'success');
    } else {
      // Legacy budget endpoint
      await post(`/finances/${STATE.userTeamId}/budget`, {
        field: type,
        value: numValue
      });
      showToast('Budget updated', 'success');
    }
  } catch (err) {
    showToast('Error updating', 'error');
  }
}

// ============================================================
// TRADE CENTER
// ============================================================
async function loadTrades() {
  showTradeTab('trade');
  const teams = await api('/teams');
  const sel = document.getElementById('trade-sel');
  sel.innerHTML = '<option value="">Select team...</option>' +
    (teams || []).filter(t => t.id !== STATE.userTeamId)
      .map(t => `<option value="${t.id}">${t.abbreviation} ${t.city} ${t.name}</option>`).join('');

  if (STATE.userTeamId) {
    const r = await api('/roster/' + STATE.userTeamId);
    document.getElementById('trade-your').innerHTML = tradeRoster(r?.active || [], 'offer');
  }
  STATE.tradeOffer = []; STATE.tradeRequest = [];
  updateTradeSlots();
}

async function loadTradeTeam() {
  const tid = parseInt(document.getElementById('trade-sel').value);
  if (!tid) return;
  STATE.tradeTeamId = tid;
  const r = await api('/roster/' + tid);
  document.getElementById('trade-other').innerHTML = tradeRoster(r?.active || [], 'req');
}

function tradeRoster(players, action) {
  return `<table style="font-size:11px">
    ${players.map(p => `<tr style="cursor:pointer" onclick="toggleTrade(${p.id},'${p.first_name} ${p.last_name}','${p.position}','${action}')">
      <td class="text-col" style="font-size:11px">${p.first_name} ${p.last_name}</td>
      <td class="c">${p.position}</td><td class="r">${p.age}</td>
      <td class="r">${p.annual_salary ? fmt$(p.annual_salary) : 'min'}</td>
    </tr>`).join('')}
  </table>`;
}

function toggleTrade(id, name, pos, action) {
  const list = action === 'offer' ? STATE.tradeOffer : STATE.tradeRequest;
  const idx = list.findIndex(p => p.id === id);
  if (idx >= 0) list.splice(idx, 1); else list.push({ id, name, pos });
  updateTradeSlots();
}

function updateTradeSlots() {
  document.getElementById('trade-slot-offer').innerHTML = STATE.tradeOffer.length
    ? STATE.tradeOffer.map(p => `<span class="trade-chip" onclick="toggleTrade(${p.id},'${p.name}','${p.pos}','offer')">${p.name} (${p.pos}) x</span>`).join('')
    : 'Click players to offer...';
  document.getElementById('trade-slot-req').innerHTML = STATE.tradeRequest.length
    ? STATE.tradeRequest.map(p => `<span class="trade-chip" onclick="toggleTrade(${p.id},'${p.name}','${p.pos}','req')">${p.name} (${p.pos}) x</span>`).join('')
    : 'Click players to request...';
}

async function submitTrade() {
  if (!STATE.tradeOffer.length || !STATE.tradeRequest.length) {
    document.getElementById('trade-resp').innerHTML = '<span style="color:var(--red)">Select players on both sides.</span>';
    return;
  }
  document.getElementById('trade-resp').innerHTML = '<span class="spinner"></span> GM evaluating...';
  const r = await post('/trade/propose', {
    proposing_team_id: STATE.userTeamId, receiving_team_id: STATE.tradeTeamId,
    players_offered: STATE.tradeOffer.map(p => p.id),
    players_requested: STATE.tradeRequest.map(p => p.id), cash_included: 0,
  });
  if (!r) { document.getElementById('trade-resp').innerHTML = 'Error.'; return; }
  const ok = r.accept;
  document.getElementById('trade-resp').innerHTML = `
    <div style="text-align:center;margin-bottom:8px">
      <span style="font-size:18px">${ok ? '✓' : '✗'}</span>
      <strong style="color:${ok ? 'var(--green)' : 'var(--red)'}">${ok ? 'ACCEPTED' : 'REJECTED'}</strong>
    </div>
    <div style="color:var(--text-dim);font-size:12px">"${r.message_to_gm || r.reasoning || ''}"</div>
    ${r.counter_offer ? `<div style="color:var(--accent);font-size:11px;margin-top:6px">Counter: ${r.counter_offer}</div>` : ''}
    ${ok ? '<button class="btn btn-primary" style="margin-top:8px;width:100%" onclick="execTrade()">Execute</button>' : ''}`;
}

async function execTrade() {
  await post('/trade/execute', {
    proposing_team_id: STATE.userTeamId, receiving_team_id: STATE.tradeTeamId,
    players_offered: STATE.tradeOffer.map(p => p.id),
    players_requested: STATE.tradeRequest.map(p => p.id), cash_included: 0,
  });
  document.getElementById('trade-resp').innerHTML = '<span class="positive">Trade completed.</span>';
  STATE.tradeOffer = []; STATE.tradeRequest = [];
  loadTrades();
}

// ============================================================
// TRADING BLOCK
// ============================================================
function showTradeTab(tab) {
  document.querySelectorAll('.trade-tab').forEach(t => t.style.display = 'none');
  document.querySelectorAll('#s-trades .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`#s-trades .tab-btn[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`trade-tab-${tab}`).style.display = 'block';

  if (tab === 'block') loadTradingBlock();
}

async function loadTradingBlock() {
  if (!STATE.userTeamId) return;
  const blockEl = document.getElementById('trading-block-list');
  const offersEl = document.getElementById('trading-block-offers');

  blockEl.innerHTML = '<div class="loading"><span class="spinner"></span></div>';
  offersEl.innerHTML = '<div class="loading"><span class="spinner"></span></div>';

  const blockData = await api('/trading-block');
  const roster = await api(`/roster/${STATE.userTeamId}`);

  if (!blockData) {
    blockEl.innerHTML = '<div class="empty-state">No players on trading block</div>';
  } else {
    let html = '';
    (blockData.players || []).forEach(pid => {
      const p = roster.active?.find(x => x.id === pid);
      if (p) {
        html += `<div style="padding: 8px 12px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;">
          <div><strong>${p.first_name} ${p.last_name}</strong> <span style="color: var(--text-dim); font-size: 10px;">${p.position}</span></div>
          <button class="btn btn-sm btn-danger" onclick="removeFromTradingBlock(${p.id})">Remove</button>
        </div>`;
      }
    });
    blockEl.innerHTML = html || '<div class="empty-state">No players on trading block</div>';
  }

  if (!blockData?.offers || blockData.offers.length === 0) {
    offersEl.innerHTML = '<div class="empty-state">No trade offers yet</div>';
  } else {
    let html = '';
    blockData.offers.forEach((offer, idx) => {
      html += `<div style="padding: 8px 12px; border-bottom: 1px solid var(--border); background: var(--bg-2);">
        <div style="font-size: 11px; color: var(--accent); font-weight: 600; margin-bottom: 4px;">${offer.from_team || 'Unknown Team'}</div>
        <div style="font-size: 10px; color: var(--text-dim); margin-bottom: 6px;">For: ${offer.player_name || 'Unknown'}</div>
        <div style="font-size: 10px; margin-bottom: 6px;">${offer.message || ''}</div>
        <button class="btn btn-sm btn-primary" onclick="acceptTradingBlockOffer(${idx})">Accept</button>
        <button class="btn btn-sm btn-danger" onclick="rejectTradingBlockOffer(${idx})">Reject</button>
      </div>`;
    });
    offersEl.innerHTML = html;
  }
}

async function removeFromTradingBlock(playerId) {
  if (!STATE.userTeamId) return;
  await post(`/trading-block/remove/${playerId}`, {});
  showToast('Player removed from trading block', 'success');
  loadTradingBlock();
}

async function addToTradingBlock(playerId) {
  if (!STATE.userTeamId) return;
  await post(`/trading-block/add/${playerId}`, {});
  showToast('Player added to trading block', 'success');
}

async function acceptTradingBlockOffer(offerIdx) {
  showToast('Trade accepted', 'success');
  loadTradingBlock();
}

async function rejectTradingBlockOffer(offerIdx) {
  showToast('Trade rejected', 'info');
  loadTradingBlock();
}

// ============================================================
// FREE AGENTS
// ============================================================
async function loadFA() {
  const el = document.getElementById('fa-body');
  el.innerHTML = '<div class="loading"><span class="spinner"></span></div>';
  const fas = await api('/free-agents');
  if (!fas?.length) { el.innerHTML = '<div class="empty-state">No free agents available</div>'; return; }
  el.innerHTML = `<div class="table-wrap"><table id="fa-table">
    <thead><tr><th class="text-col">Name</th><th class="c">Pos</th><th class="r">Age</th><th class="c">B/T</th>
    <th class="c">Key</th><th class="r">Ask</th><th class="r">Yrs</th><th class="r">Teams</th><th></th></tr></thead>
    <tbody>
    ${fas.slice(0, 50).map(p => {
      const isPit = p.position === 'SP' || p.position === 'RP';
      const key = isPit ? `STF:${gradeHtml(p.stuff_rating)}` : `${gradeHtml(p.contact_rating)} ${gradeHtml(p.power_rating)}`;
      return `<tr>
        <td class="text-col clickable" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
        <td class="c">${p.position}</td><td class="r">${p.age}</td><td class="c">${p.bats}/${p.throws}</td>
        <td class="c">${key}</td><td class="r mono">${fmt$(p.asking_salary)}</td>
        <td class="r">${p.asking_years}</td><td class="r">${p.market_interest}</td>
        <td><button class="btn btn-sm btn-primary" onclick="signFA(${p.id},${p.asking_salary},${p.asking_years})">Sign</button></td>
      </tr>`;
    }).join('')}
    </tbody>
  </table></div>`;
  makeSortable('fa-table');
}

async function signFA(pid, sal, yrs) {
  if (!STATE.userTeamId) return;
  await post('/free-agents/sign', { player_id: pid, team_id: STATE.userTeamId, salary: sal, years: yrs });
  showToast('Player signed', 'success');
  loadFA();
}

// ============================================================
// LEADERS
// ============================================================
async function loadLeaders() {
  const cats = [
    { id: 'hr', stat: 'hr', label: 'Home Runs', bat: true },
    { id: 'avg', stat: 'hits', label: 'Batting Average', bat: true, fmt: p => fmtAvg(p.hits, p.ab) },
    { id: 'rbi', stat: 'rbi', label: 'RBI', bat: true },
    { id: 'wins', stat: 'wins', label: 'Wins', bat: false },
    { id: 'era', stat: 'so', label: 'Strikeouts (P)', bat: false },
    { id: 'sb', stat: 'sb', label: 'Stolen Bases', bat: true },
  ];
  for (const c of cats) {
    const url = c.bat ? `/leaders/batting?stat=${c.stat}&limit=10` : `/leaders/pitching?stat=${c.stat}&limit=10`;
    const data = await api(url) || [];
    document.getElementById('ldr-' + c.id).innerHTML = data.map((p, i) => {
      const val = c.fmt ? c.fmt(p) : (c.bat ? p[c.stat] : (c.stat === 'wins' ? p.wins : p.so));
      return `<div class="leader-row" onclick="showPlayer(${p.player_id || 0})">
        <span class="leader-rank">${i + 1}.</span>
        <span class="leader-name clickable">${p.first_name} ${p.last_name}</span>
        <span class="leader-team">${p.abbreviation}</span>
        <span class="leader-val">${val}</span>
      </div>`;
    }).join('') || '<div class="empty-state">No data yet</div>';
  }
}

// ============================================================
// MESSAGES
// ============================================================
async function loadMessages() {
  const el = document.getElementById('msg-body');
  const msgs = await api('/messages?unread_only=false') || [];
  const unreadCount = msgs.filter(m => !m.is_read).length;
  const badge = document.getElementById('msg-count');
  if (unreadCount > 0) {
    badge.textContent = unreadCount;
    badge.style.display = 'block';
  } else {
    badge.style.display = 'none';
  }
  if (!msgs.length) {
    el.innerHTML = '<div class="empty-state">Inbox empty. Messages from GMs, your owner, agents, and scouts will appear here.</div>';
    return;
  }
  el.innerHTML = msgs.map(m => `
    <div class="msg-item ${m.is_read ? '' : 'unread'}">
      <span class="msg-from">${m.sender_name}</span>
      <span class="msg-date">${m.game_date}</span>
      <div class="msg-body">${m.body}</div>
    </div>
  `).join('');
}

// ============================================================
// KEYBOARD SHORTCUTS
// ============================================================
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    openGlobalSearch();
  }
});

// ============================================================
// DEPTH CHART
// ============================================================
async function loadDepthChart() {
  const teamId = STATE.userTeamId;
  if (!teamId) return;

  const data = await api(`/team/${teamId}/depth-chart`);
  if (!data) {
    document.getElementById('depthchart-body').innerHTML = '<div class="empty-state">No depth chart data</div>';
    return;
  }

  // Create position group container
  let html = '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">';

  // Infield
  html += '<div style="grid-column: 1/2;"><h3 style="margin-top: 0;">Infield</h3>';
  const infield = ['C', '1B', '2B', '3B', 'SS'];
  for (const pos of infield) {
    html += renderDepthPosition(pos, data[pos] || []);
  }
  html += '</div>';

  // Outfield & DH
  html += '<div style="grid-column: 2/3;"><h3 style="margin-top: 0;">Outfield / DH</h3>';
  const outfield = ['LF', 'CF', 'RF', 'DH'];
  for (const pos of outfield) {
    html += renderDepthPosition(pos, data[pos] || []);
  }
  html += '</div>';

  html += '</div>';

  // Pitching
  html += '<div style="margin-top: 24px;"><h3>Pitching</h3>';
  html += '<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">';
  html += '<div><h4>Starters</h4>' + renderDepthPosition('SP', data['SP'] || []) + '</div>';
  html += '<div><h4>Relievers</h4>' + renderDepthPosition('RP', data['RP'] || []) + '</div>';
  html += '</div></div>';

  document.getElementById('depthchart-body').innerHTML = html;
}

function renderDepthPosition(pos, players) {
  let html = `<div style="margin-bottom: 16px; padding: 12px; border-left: 3px solid #666; background: var(--bg-secondary);">`;
  html += `<div style="font-weight: bold; margin-bottom: 8px; font-size: 14px;">${pos}</div>`;

  if (players.length === 0) {
    html += '<div style="font-size: 12px; color: var(--text-secondary);">No players</div>';
  } else {
    for (let i = 0; i < players.length; i++) {
      const p = players[i];
      const statusLabel = p.status === 'starter' ? '★' : p.status === 'backup' ? '▲' : '◆';
      const ratingClass = p.overall >= 65 ? 'grade-elite' : p.overall >= 50 ? 'grade-good' : 'grade-avg';
      html += `
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px; margin-bottom: 6px; padding: 4px 0; border-bottom: 1px solid var(--border);">
          <span style="flex: 1; cursor: pointer;" onclick="showPlayerModal(${p.player_id})">${statusLabel} ${p.name}</span>
          <span class="grade ${ratingClass}" style="font-size: 11px;">${p.overall}</span>
        </div>
      `;
    }
  }
  html += '</div>';
  return html;
}


// ============================================================
// COMMISSIONER MODE
// ============================================================
async function toggleCommissionerMode() {
  const result = await post('/settings/commissioner-mode', {});
  if (result?.success) {
    STATE.commissionerMode = result.commissioner_mode;
    updateCommissionerToggleUI();
    showToast(result.commissioner_mode ? 'Commissioner mode ENABLED' : 'Commissioner mode disabled', 'info');
  }
}

async function updateCommissionerToggleUI() {
  const mode = await api('/settings/commissioner-mode');
  STATE.commissionerMode = mode?.commissioner_mode || 0;
  const btn = document.getElementById('commissioner-toggle-btn');
  if (btn) {
    btn.textContent = STATE.commissionerMode ? 'ON' : 'OFF';
    btn.className = STATE.commissionerMode ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
  }
}

async function editPlayer(playerId) {
  if (!STATE.commissionerMode) {
    showToast('Commissioner mode is not enabled', 'warning');
    return;
  }

  const player = await api(`/player/${playerId}`);
  if (!player) return;

  const p = player.player;
  const html = `
    <div style="max-height: 500px; overflow-y: auto;">
      <h2>${p.first_name} ${p.last_name}</h2>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
        <div>
          <label>Contact Rating: <input type="number" id="edit-contact" value="${p.contact_rating}" min="20" max="80"></label>
        </div>
        <div>
          <label>Power Rating: <input type="number" id="edit-power" value="${p.power_rating}" min="20" max="80"></label>
        </div>
        <div>
          <label>Speed Rating: <input type="number" id="edit-speed" value="${p.speed_rating}" min="20" max="80"></label>
        </div>
        <div>
          <label>Fielding Rating: <input type="number" id="edit-fielding" value="${p.fielding_rating}" min="20" max="80"></label>
        </div>
        <div>
          <label>Arm Rating: <input type="number" id="edit-arm" value="${p.arm_rating}" min="20" max="80"></label>
        </div>
        <div>
          <label>Age: <input type="number" id="edit-age" value="${p.age}" min="18" max="45"></label>
        </div>
        ${p.position.includes('P') ? `
        <div>
          <label>Stuff Rating: <input type="number" id="edit-stuff" value="${p.stuff_rating}" min="20" max="80"></label>
        </div>
        <div>
          <label>Control Rating: <input type="number" id="edit-control" value="${p.control_rating}" min="20" max="80"></label>
        </div>
        <div>
          <label>Stamina Rating: <input type="number" id="edit-stamina" value="${p.stamina_rating}" min="20" max="80"></label>
        </div>
        ` : ''}
        <div>
          <label>Morale: <input type="number" id="edit-morale" value="${p.morale}" min="1" max="100"></label>
        </div>
      </div>
      <div style="margin-top: 16px; display: flex; gap: 8px;">
        <button class="btn btn-primary" onclick="savePlayerEdit(${playerId})">Save Changes</button>
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      </div>
    </div>
  `;

  document.getElementById('player-modal-body').innerHTML = html;
  document.getElementById('player-modal').style.display = 'block';
}

async function savePlayerEdit(playerId) {
  const updates = {};
  const fields = ['contact', 'power', 'speed', 'fielding', 'arm', 'stuff', 'control', 'stamina', 'age', 'morale'];

  for (const field of fields) {
    const el = document.getElementById(`edit-${field}`);
    if (el) {
      const val = parseInt(el.value);
      if (!isNaN(val)) {
        const fieldName = field.replace('contact', 'contact_rating').replace('power', 'power_rating')
          .replace('speed', 'speed_rating').replace('fielding', 'fielding_rating').replace('arm', 'arm_rating')
          .replace('stuff', 'stuff_rating').replace('control', 'control_rating').replace('stamina', 'stamina_rating');
        updates[fieldName] = val;
      }
    }
  }

  const result = await post(`/commissioner/edit-player/${playerId}`, updates);
  if (result?.success) {
    showToast('Player updated', 'success');
    closeModal();
  } else {
    showToast('Error updating player', 'error');
  }
}

async function editTeam(teamId) {
  if (!STATE.commissionerMode) {
    showToast('Commissioner mode is not enabled', 'warning');
    return;
  }

  const team = await api(`/team/${teamId}`);
  if (!team) return;

  const t = team.team;
  const html = `
    <div style="max-height: 500px; overflow-y: auto;">
      <h2>${t.city} ${t.name}</h2>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
        <div>
          <label>Cash: <input type="number" id="edit-cash" value="${t.cash}"></label>
        </div>
        <div>
          <label>Franchise Value: <input type="number" id="edit-franchise" value="${t.franchise_value}"></label>
        </div>
        <div>
          <label>Fan Loyalty: <input type="number" id="edit-loyalty" value="${t.fan_loyalty}" min="1" max="100"></label>
        </div>
        <div>
          <label>Farm System Budget: <input type="number" id="edit-farm" value="${t.farm_system_budget}"></label>
        </div>
        <div>
          <label>Medical Staff Budget: <input type="number" id="edit-medical" value="${t.medical_staff_budget}"></label>
        </div>
        <div>
          <label>Scouting Staff Budget: <input type="number" id="edit-scouting" value="${t.scouting_staff_budget}"></label>
        </div>
      </div>
      <div style="margin-top: 16px; display: flex; gap: 8px;">
        <button class="btn btn-primary" onclick="saveTeamEdit(${teamId})">Save Changes</button>
        <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
      </div>
    </div>
  `;

  document.getElementById('player-modal-body').innerHTML = html;
  document.getElementById('player-modal').style.display = 'block';
}

async function saveTeamEdit(teamId) {
  const updates = {
    cash: parseInt(document.getElementById('edit-cash').value) || 0,
    franchise_value: parseInt(document.getElementById('edit-franchise').value) || 0,
    fan_loyalty: parseInt(document.getElementById('edit-loyalty').value) || 50,
    farm_system_budget: parseInt(document.getElementById('edit-farm').value) || 0,
    medical_staff_budget: parseInt(document.getElementById('edit-medical').value) || 0,
    scouting_staff_budget: parseInt(document.getElementById('edit-scouting').value) || 0,
  };

  const result = await post(`/commissioner/edit-team/${teamId}`, updates);
  if (result?.success) {
    showToast('Team updated', 'success');
    closeModal();
  } else {
    showToast('Error updating team', 'error');
  }
}


// ============================================================
// SETTINGS & COLUMN PICKER
// ============================================================
function openSettingsModal() {
  document.getElementById('settings-modal').style.display = 'block';
  updateCommissionerToggleUI();
}

function closeSettingsModal() {
  document.getElementById('settings-modal').style.display = 'none';
}

let columnPickerType = null;
let selectedColumns = [];

async function openColumnPickerModal(tableType) {
  columnPickerType = tableType;
  const config = await api('/settings/stat-columns');

  const currentColumns = tableType === 'batting' ? (config?.batting || []) : (config?.pitching || []);
  selectedColumns = [...currentColumns];

  const allColumns = tableType === 'batting'
    ? ['name', 'pos', 'team', 'age', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'BB', 'SO', 'SB', 'CS', 'AVG', 'OBP', 'SLG', 'OPS']
    : ['name', 'pos', 'team', 'age', 'G', 'GS', 'W', 'L', 'SV', 'HLD', 'IP', 'H', 'ER', 'BB', 'SO', 'HR', 'ERA', 'WHIP', 'K/9', 'BB/9'];

  let html = '';
  for (const col of allColumns) {
    const checked = selectedColumns.includes(col) ? 'checked' : '';
    html += `<label style="display: block; margin: 8px 0;">
      <input type="checkbox" value="${col}" ${checked} onchange="updateSelectedColumns()"> ${col}
    </label>`;
  }

  document.getElementById('column-picker-title').textContent = `Select ${tableType === 'batting' ? 'Batting' : 'Pitching'} Columns`;
  document.getElementById('column-picker-body').innerHTML = html;
  document.getElementById('column-picker-modal').style.display = 'block';
}

function updateSelectedColumns() {
  const checkboxes = document.querySelectorAll('#column-picker-body input[type="checkbox"]');
  selectedColumns = [];
  for (const cb of checkboxes) {
    if (cb.checked) {
      selectedColumns.push(cb.value);
    }
  }
}

async function saveColumnConfig() {
  const updates = {};
  if (columnPickerType === 'batting') {
    updates.batting = selectedColumns;
  } else {
    updates.pitching = selectedColumns;
  }

  const result = await post('/settings/stat-columns', updates);
  if (result?.success) {
    showToast('Column settings saved', 'success');
    closeColumnPickerModal();
  }
}

function closeColumnPickerModal() {
  document.getElementById('column-picker-modal').style.display = 'none';
  columnPickerType = null;
  selectedColumns = [];
}


// ============================================================
// CSV EXPORT
// ============================================================
async function exportCSV(exportType, params = {}) {
  try {
    let url = '';
    let filename = '';

    switch (exportType) {
      case 'roster':
        url = `/export/roster/${STATE.userTeamId}`;
        filename = `roster.csv`;
        break;
      case 'batting-stats':
        url = `/export/batting-stats?season=${params.season || 2026}`;
        filename = `batting-stats-${params.season || 2026}.csv`;
        break;
      case 'pitching-stats':
        url = `/export/pitching-stats?season=${params.season || 2026}`;
        filename = `pitching-stats-${params.season || 2026}.csv`;
        break;
      case 'financials':
        url = `/export/financials/${STATE.userTeamId}`;
        filename = `financials.csv`;
        break;
      default:
        return;
    }

    // Trigger download
    const link = document.createElement('a');
    link.href = API + url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    showToast('CSV export started', 'success');
  } catch (e) {
    showToast('Error exporting CSV', 'error');
  }
}


// ============================================================
// DRAFT
// ============================================================
let _draftProspectsCache = [];
let _selectedProspect = null;

async function loadDraft() {
  if (!STATE.userTeamId) return;
  const statusEl = document.getElementById('draft-status');
  statusEl.innerHTML = '<span class="spinner" style="display: inline-block; width: 12px; height: 12px; border: 2px solid var(--accent); border-radius: 50%; border-right-color: transparent; animation: spin 0.6s linear infinite;"></span> Loading...';

  // Get draft status
  const draftStatus = await api(`/draft/status`);
  if (draftStatus) {
    const round = draftStatus.current_round || 1;
    const pick = draftStatus.current_pick || 1;
    statusEl.textContent = `Round ${round}, Pick ${pick}`;
  } else {
    statusEl.textContent = 'Draft status unavailable';
  }

  // Get available prospects
  const season = STATE.season;
  const allProspects = await api(`/draft/prospects/${season}`);
  _draftProspectsCache = allProspects ? allProspects.filter(p => !p.is_drafted) : [];

  filterDraftProspects();

  // Load already drafted players
  const drafted = await api(`/draft/results`);
  renderDraftedPlayers(drafted);
}

function filterDraftProspects() {
  const search = document.getElementById('draft-search')?.value.toLowerCase() || '';
  const pos = document.getElementById('draft-pos-filter')?.value || '';
  const sort = document.getElementById('draft-sort')?.value || 'rank';

  let filtered = _draftProspectsCache.filter(p => {
    const nameMatch = `${p.first_name} ${p.last_name}`.toLowerCase().includes(search);
    const posMatch = !pos || p.position === pos;
    return nameMatch && posMatch;
  });

  // Sort
  if (sort === 'rank') {
    filtered.sort((a, b) => a.overall_rank - b.overall_rank);
  } else if (sort === 'age') {
    filtered.sort((a, b) => a.age - b.age);
  } else if (sort === 'position') {
    filtered.sort((a, b) => a.position.localeCompare(b.position));
  }

  renderDraftProspectsList(filtered);
}

function renderDraftProspectsList(prospects) {
  const el = document.getElementById('draft-list');
  if (!prospects.length) {
    el.innerHTML = '<div class="empty-state" style="padding: 20px;">No prospects available</div>';
    return;
  }

  let html = '<div style="display: flex; flex-direction: column;">';
  prospects.forEach(p => {
    const isPitcher = p.position === 'SP' || p.position === 'RP';
    const mainRating = isPitcher ? (Math.round((p.stuff_floor + p.stuff_ceiling) / 2)) : (Math.round((p.contact_floor + p.contact_ceiling) / 2));
    html += `
      <div class="draft-prospect-item" onclick="selectProspect(${p.id})" style="padding: 8px 12px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.2s; ${_selectedProspect?.id === p.id ? 'background: var(--bg-selected);' : 'background: var(--bg-1);'} hover {background: var(--bg-3);}">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="flex: 1;">
            <div style="font-weight: 600;">${p.first_name} ${p.last_name}</div>
            <div style="font-size: 11px; color: var(--text-dim);">
              <span class="badge">${p.position}</span>
              Age ${p.age} | Rank ${p.overall_rank}
            </div>
          </div>
          <div style="text-align: right; font-weight: 600; color: var(--accent);">${mainRating}</div>
        </div>
      </div>
    `;
  });
  html += '</div>';
  el.innerHTML = html;
}

function selectProspect(prospectId) {
  _selectedProspect = _draftProspectsCache.find(p => p.id === prospectId);
  if (!_selectedProspect) return;

  const isPitcher = _selectedProspect.position === 'SP' || _selectedProspect.position === 'RP';

  const preview = document.getElementById('draft-preview');
  let html = `
    <div style="margin-bottom: 16px;">
      <div style="font-size: 16px; font-weight: 700; margin-bottom: 4px;">
        ${_selectedProspect.first_name} ${_selectedProspect.last_name}
      </div>
      <div style="display: flex; gap: 16px; font-size: 12px; color: var(--text-dim);">
        <span>${_selectedProspect.position}</span>
        <span>Age ${_selectedProspect.age}</span>
        <span>${_selectedProspect.bats}/${_selectedProspect.throws}</span>
        <span style="color: var(--accent); font-weight: 600;">Rank ${_selectedProspect.overall_rank}</span>
      </div>
    </div>
    <div style="border-top: 1px solid var(--border); padding-top: 12px;">
      <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; font-weight: 600;">Ratings Range (Floor-Ceiling)</div>
  `;

  if (isPitcher) {
    html += `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
        <div>Stuff: ${_selectedProspect.stuff_floor}-${_selectedProspect.stuff_ceiling}</div>
        <div>Control: ${_selectedProspect.control_floor}-${_selectedProspect.control_ceiling}</div>
      </div>
    `;
  } else {
    html += `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px;">
        <div>Contact: ${_selectedProspect.contact_floor}-${_selectedProspect.contact_ceiling}</div>
        <div>Power: ${_selectedProspect.power_floor}-${_selectedProspect.power_ceiling}</div>
        <div>Speed: ${_selectedProspect.speed_floor}-${_selectedProspect.speed_ceiling}</div>
        <div>Fielding: ${_selectedProspect.fielding_floor}-${_selectedProspect.fielding_ceiling}</div>
        <div>Arm: ${_selectedProspect.arm_floor}-${_selectedProspect.arm_ceiling}</div>
      </div>
    `;
  }

  if (_selectedProspect.scouting_report) {
    html += `
      <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 11px; line-height: 1.6;">
        <div style="color: var(--text-muted); margin-bottom: 4px;">Scouting Report</div>
        <div style="font-style: italic; color: var(--text-dim);">${_selectedProspect.scouting_report}</div>
      </div>
    `;
  }

  html += '</div>';
  preview.innerHTML = html;

  // Show draft button
  document.getElementById('draft-btn').style.display = 'block';

  // Update list selection
  filterDraftProspects();
}

async function draftSelectedProspect() {
  if (!_selectedProspect) return;

  const draftStatus = await api(`/draft/status`);
  if (!draftStatus || !draftStatus.current_round || !draftStatus.current_pick) {
    showToast('Draft status unavailable', 'error');
    return;
  }

  const btn = document.getElementById('draft-btn');
  btn.disabled = true;
  btn.textContent = 'DRAFTING...';

  const result = await post('/draft/pick', {
    team_id: STATE.userTeamId,
    prospect_id: _selectedProspect.id,
    round: draftStatus.current_round,
    pick: draftStatus.current_pick
  });

  btn.disabled = false;
  btn.textContent = 'DRAFT PLAYER';

  if (result?.success) {
    showToast(`Drafted ${result.name} - Round ${result.round}, Pick ${result.pick}`, 'success');
    _draftProspectsCache = _draftProspectsCache.filter(p => p.id !== _selectedProspect.id);
    _selectedProspect = null;
    loadDraft();
  } else {
    showToast(result?.error || 'Draft failed', 'error');
  }
}

function renderDraftedPlayers(drafted) {
  const el = document.getElementById('draft-results');
  if (!drafted || !drafted.length) {
    el.innerHTML = '<div class="empty-state" style="padding: 12px;">No picks yet</div>';
    return;
  }

  let html = '<div class="table-wrap"><table style="width: 100%; font-size: 11px;"><thead><tr><th style="text-align: left;">Round</th><th style="text-align: left;">Pick</th><th style="text-align: left;">Team</th><th style="text-align: left;">Player</th><th style="text-align: left;">Pos</th></tr></thead><tbody>';
  drafted.forEach(pick => {
    html += `<tr><td>${pick.round}</td><td>${pick.pick}</td><td>${pick.team_abbr}</td><td class="text-col clickable" onclick="showPlayer(${pick.player_id})">${pick.first_name} ${pick.last_name}</td><td>${pick.position}</td></tr>`;
  });
  html += '</tbody></table></div>';
  el.innerHTML = html;
}

// ============================================================
// TRANSACTIONS
// ============================================================
let _transactionsData = null;

async function loadTransactions() {
  if (!STATE.userTeamId) return;

  const data = await api(`/roster/${STATE.userTeamId}`);
  _transactionsData = data;

  const activeCount = data?.active?.length || 0;
  const fortyManCount = data?.forty_man_count || 0;
  document.getElementById('trans-active-count').textContent = activeCount;
  document.getElementById('trans-40man-count').textContent = fortyManCount;

  renderTransactionsList('active');
  renderTransactionsList('minors');
  renderTransactionsList('injured');
}

function filterTransactionsList(tab) {
  const search = document.getElementById(`trans-${tab}-search`)?.value.toLowerCase() || '';
  const pos = document.getElementById(`trans-${tab}-pos`)?.value || '';

  if (tab === 'active') {
    renderTransactionsList('active', search, pos);
  } else if (tab === 'minors') {
    renderTransactionsList('minors', search, pos);
  }
}

function renderTransactionsList(tab, search = '', pos = '') {
  if (!_transactionsData) return;

  const data = tab === 'active' ? _transactionsData.active : tab === 'minors' ? _transactionsData.minors : _transactionsData.injured;
  if (!data) return;

  let filtered = data.filter(p => {
    const nameMatch = `${p.first_name} ${p.last_name}`.toLowerCase().includes(search);
    const posMatch = !pos || p.position === pos;
    return nameMatch && posMatch;
  });

  const isPitcher = p => p.position === 'SP' || p.position === 'RP';
  const pitchers = filtered.filter(p => isPitcher(p));
  const hitters = filtered.filter(p => !isPitcher(p));
  const players = hitters.concat(pitchers);

  const el = document.getElementById(`trans-${tab}-list`);
  if (!players.length) {
    el.innerHTML = '<div class="empty-state" style="padding: 12px;">No players</div>';
    return;
  }

  let html = '<div style="display: flex; flex-direction: column;">';
  players.forEach(p => {
    const isPitch = isPitcher(p);
    const salary = p.annual_salary ? fmt$(p.annual_salary) : 'min';
    const mainRating = isPitch ? p.stuff_rating : p.contact_rating;

    let actions = '';
    if (tab === 'active') {
      actions = `
        <div style="display: flex; gap: 4px;">
          <button class="btn btn-sm" style="padding: 2px 6px; font-size: 10px;" onclick="showTransactionConfirm('il', ${p.id})">IL</button>
          <button class="btn btn-sm" style="padding: 2px 6px; font-size: 10px;" onclick="showTransactionConfirm('dfa', ${p.id})">DFA</button>
          ${data.length > 26 ? `<button class="btn btn-sm" style="padding: 2px 6px; font-size: 10px;" onclick="showTransactionConfirm('option', ${p.id})">Option</button>` : ''}
        </div>
      `;
    } else if (tab === 'minors') {
      actions = `<button class="btn btn-primary btn-sm" style="padding: 2px 6px; font-size: 10px;" onclick="callUpPlayer(${p.id})">Call Up</button>`;
    } else if (tab === 'injured') {
      actions = `<button class="btn btn-primary btn-sm" style="padding: 2px 6px; font-size: 10px;" onclick="activateFromIL(${p.id})">Activate</button>`;
    }

    html += `
      <div style="padding: 8px 12px; border-bottom: 1px solid var(--border); background: var(--bg-1); display: flex; justify-content: space-between; align-items: center;">
        <div style="flex: 1;">
          <div style="font-weight: 500; cursor: pointer;" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</div>
          <div style="font-size: 10px; color: var(--text-dim);">
            <span>${p.position}</span> | <span>Age ${p.age}</span> | <span>${salary}</span>
          </div>
        </div>
        <div style="text-align: right; margin-right: 12px; color: var(--accent); font-weight: 600;">${mainRating}</div>
        ${actions}
      </div>
    `;
  });
  html += '</div>';
  el.innerHTML = html;
}

function showTransactionConfirm(action, playerId) {
  const player = _transactionsData?.active?.find(p => p.id === playerId);
  if (!player) return;

  const messages = {
    'il': `Place ${player.first_name} ${player.last_name} on IL?`,
    'dfa': `Designate ${player.first_name} ${player.last_name} for assignment?`,
    'option': `Option ${player.first_name} ${player.last_name} to minors?`
  };

  if (confirm(messages[action])) {
    if (action === 'il') {
      placeOnIL(playerId);
    } else if (action === 'dfa') {
      dfaPlayer(playerId);
    } else if (action === 'option') {
      optionPlayer(playerId);
    }
  }
}

async function callUpPlayer(playerId) {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '...';

  const result = await post(`/roster/call-up/${playerId}`, {});

  btn.disabled = false;
  btn.textContent = 'Call Up';

  if (result?.success) {
    showToast(`Called up ${result.name}`, 'success');
    loadTransactions();
  } else {
    showToast(result?.error || 'Call-up failed', 'error');
  }
}

async function optionPlayer(playerId) {
  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '...';

  const result = await post(`/roster/option/${playerId}`, { level: 'minors_aaa' });

  btn.disabled = false;
  btn.textContent = 'Option';

  if (result?.success) {
    showToast(`Optioned ${result.name}`, 'success');
    loadTransactions();
  } else {
    showToast(result?.error || 'Option failed', 'error');
  }
}

async function dfaPlayer(playerId) {
  const player = _transactionsData?.active?.find(p => p.id === playerId);
  if (!player) return;

  const btn = event.target;
  btn.disabled = true;
  btn.textContent = '...';

  const result = await post(`/roster/dfa/${playerId}`, {});

  btn.disabled = false;
  btn.textContent = 'DFA';

  if (result?.success) {
    showToast(`DFA'd ${result.name}`, 'success');
    loadTransactions();
  } else {
    showToast(result?.error || 'DFA failed', 'error');
  }
}

async function placeOnIL(playerId) {
  const result = await post(`/roster/${STATE.userTeamId}/place-il`, { player_id: playerId, tier: '60' });

  if (result?.success) {
    showToast('Placed on IL', 'success');
    loadTransactions();
  } else {
    showToast(result?.error || 'IL placement failed', 'error');
  }
}

async function activateFromIL(playerId) {
  const result = await post(`/roster/${STATE.userTeamId}/activate`, { player_id: playerId });

  if (result?.success) {
    showToast('Activated from IL', 'success');
    loadTransactions();
  } else {
    showToast(result?.error || 'Activation failed', 'error');
  }
}

// ============================================================
// INIT
// ============================================================
async function init() {
  initTheme();
  try {
    const s = await api('/game-state');
    if (s?.user_team_id) {
      STATE.userTeamId = s.user_team_id;
      document.getElementById('intro-screen').classList.remove('active');
      document.getElementById('app').classList.add('active');
      await loadState();
      showScreen('calendar');
    } else {
      playIntro();
    }
  } catch (e) { playIntro(); }
}

init();
