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
  statsPage: {
    type: 'batters',
    sort: 'hr',
    order: 'desc',
    page: 1,
    minPA: 0
  }
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
  if (btn) btn.textContent = theme === 'dark' ? '\u2600' : '\uD83C\uDF19';
  const sidebarBtn = document.getElementById('sidebar-theme-btn');
  if (sidebarBtn) sidebarBtn.textContent = theme === 'dark' ? '\u2600' : '\u263E';
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

    // Update sidebar elements
    const sidebarTeam = document.getElementById('sidebar-team-name');
    if (sidebarTeam) sidebarTeam.textContent = `${STATE.teamCity} ${STATE.teamName}`;
    const sidebarPhase = document.getElementById('sidebar-phase');
    if (sidebarPhase) sidebarPhase.textContent = STATE.phase.replace('_', ' ');

    const standings = await api('/standings');
    if (standings) {
      for (const teams of Object.values(standings)) {
        const us = teams.find(x => x.team_id === STATE.userTeamId);
        if (us) {
          document.getElementById('hdr-record').textContent = `${us.wins}-${us.losses}`;
          const sidebarRecord = document.getElementById('sidebar-record');
          if (sidebarRecord) sidebarRecord.textContent = `${us.wins}-${us.losses}`;
          break;
        }
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
const PAGE_TITLES = {
  calendar: 'Dashboard', roster: 'Roster', transactions: 'Transactions',
  lineup: 'Lineup', depthchart: 'Depth Chart', standings: 'Standings',
  schedule: 'Schedule', playoffs: 'Playoffs', finances: 'Finances',
  trades: 'Trade Center', draft: 'Draft', freeagents: 'Free Agents',
  findplayers: 'Find Players', leaders: 'Leaders', messages: 'Messages',
  gameday: 'Game Day',
};

function showScreen(name) {
  document.querySelectorAll('.content-screen').forEach(s => s.classList.remove('active'));
  // Update both old nav-btn and new sidebar nav-item
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  const screen = document.getElementById('s-' + name);
  if (screen) screen.classList.add('active');
  const btn = document.querySelector(`.nav-btn[data-s="${name}"]`);
  if (btn) btn.classList.add('active');
  const navItem = document.querySelector(`.nav-item[data-s="${name}"]`);
  if (navItem) navItem.classList.add('active');
  // Update page title in top bar
  const titleEl = document.getElementById('page-title');
  if (titleEl) titleEl.textContent = PAGE_TITLES[name] || name;
  const loaders = {
    calendar: loadCalendar, roster: loadRoster, transactions: loadTransactions, lineup: loadLineup, depthchart: loadDepthChart, standings: loadStandings,
    schedule: loadSchedule, playoffs: loadPlayoffs, finances: loadFinances, trades: loadTrades, draft: loadDraft,
    freeagents: loadFA, findplayers: loadFindPlayers, leaders: loadLeaders, messages: loadMessages,
    gameday: loadGameDay,
  };
  if (loaders[name]) loaders[name]();
}

// ============================================================
// SIM CONTROLS
// ============================================================
async function simDays(n) {
  // Disable both old and new sim buttons
  const oldBtns = document.querySelectorAll('.btn-sim');
  const dayBtn = document.getElementById('sim-day-btn');
  const weekBtn = document.getElementById('sim-week-btn');
  oldBtns.forEach(b => { b.disabled = true; b.textContent = '...'; });
  if (dayBtn) { dayBtn.disabled = true; dayBtn.textContent = 'Simulating...'; }
  if (weekBtn) { weekBtn.disabled = true; }
  const r = await post('/sim/advance', { days: n });
  await loadState();
  const ticker = document.getElementById('ticker');
  if (r) {
    const stGames = r.spring_training ? r.spring_training.length : 0;
    const regGames = r.games_played || 0;
    if (stGames > 0 && regGames === 0) {
      ticker.textContent = `Simulated ${n}d, ${stGames} spring training games | ${fmtDate(r.new_date)}`;
    } else if (stGames > 0) {
      ticker.textContent = `Simulated ${n}d, ${regGames} games + ${stGames} ST games | ${fmtDate(r.new_date)}`;
    } else {
      ticker.textContent = `Simulated ${n}d, ${regGames} games | ${fmtDate(r.new_date)}`;
    }
    // Show roster trim notification on Opening Day
    if (r.offseason) {
      const trim = r.offseason.find(e => e.type === 'opening_day_roster_trim');
      if (trim && trim.teams_trimmed && trim.teams_trimmed.length > 0) {
        showToast(`Opening Day: ${trim.teams_trimmed.length} teams trimmed rosters to 26`, 'info');
      }
      // All-Star Game result
      const asg = r.offseason.find(e => e.type === 'all_star_game');
      if (asg && !asg.error) {
        showToast(`All-Star Game: AL ${asg.al_score}, NL ${asg.nl_score}`, 'info');
      }
    }
  }
  // After advancing the date, reset calendar to show current month
  const d = new Date(STATE.currentDate + 'T12:00:00');
  STATE.calMonth = d.getMonth();
  STATE.calYear = d.getFullYear();
  const active = document.querySelector('.content-screen.active');
  if (active) showScreen(active.id.replace('s-', ''));
  oldBtns.forEach((b, i) => { b.disabled = false; b.textContent = i === 0 ? '\u25B6 Day' : '\u25B6\u25B6 Week'; });
  if (dayBtn) { dayBtn.disabled = false; dayBtn.textContent = '\u25B6 Sim Day'; }
  if (weekBtn) { weekBtn.disabled = false; weekBtn.textContent = '\u25B6\u25B6 Week'; }
}

// ============================================================
// CALENDAR HUB
// ============================================================
async function loadCalendar() {
  const el = document.getElementById('s-calendar');

  // Sync calendar month/year with current game date to ensure we always show the current month
  // This is especially important after simulating days
  const d = new Date(STATE.currentDate + 'T12:00:00');
  const currentMonth = d.getMonth();
  const currentYear = d.getFullYear();

  // If calMonth/calYear haven't been set yet, initialize them
  // Otherwise, if they differ from current date, update them (user navigated and sim advanced)
  if (STATE.calMonth === null || STATE.calYear === null) {
    STATE.calMonth = currentMonth;
    STATE.calYear = currentYear;
  }

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

  // Compute dashboard stats
  const allPlayed = (games || []).filter(g => g.is_played);
  let wins = 0, losses = 0;
  allPlayed.forEach(g => {
    const isHome = g.home_team_id === STATE.userTeamId;
    const myScore = isHome ? g.home_score : g.away_score;
    const theirScore = isHome ? g.away_score : g.home_score;
    if (myScore > theirScore) wins++; else losses++;
  });

  // Last 10 streak
  const last10 = allPlayed.slice(-10);
  let l10w = 0, l10l = 0;
  last10.forEach(g => {
    const isHome = g.home_team_id === STATE.userTeamId;
    const myScore = isHome ? g.home_score : g.away_score;
    const theirScore = isHome ? g.away_score : g.home_score;
    if (myScore > theirScore) l10w++; else l10l++;
  });

  // Compute current streak
  let streakCount = 0, streakType = '';
  if (allPlayed.length) {
    const lastGame = allPlayed[allPlayed.length - 1];
    const lastIsHome = lastGame.home_team_id === STATE.userTeamId;
    const lastWon = (lastIsHome ? lastGame.home_score : lastGame.away_score) > (lastIsHome ? lastGame.away_score : lastGame.home_score);
    streakType = lastWon ? 'W' : 'L';
    for (let si = allPlayed.length - 1; si >= 0; si--) {
      const sg = allPlayed[si];
      const sHome = sg.home_team_id === STATE.userTeamId;
      const sWon = (sHome ? sg.home_score : sg.away_score) > (sHome ? sg.away_score : sg.home_score);
      if ((sWon && streakType === 'W') || (!sWon && streakType === 'L')) streakCount++;
      else break;
    }
  }
  const streakStr = streakCount > 0 ? `${streakType}${streakCount}` : '-';

  // Next game
  const upcoming = (games || []).filter(g => !g.is_played);
  let nextGameHtml = '<span style="color:var(--text-tertiary)">Off day</span>';
  let nextGameSub = '';
  if (upcoming.length) {
    const ng = upcoming[0];
    const isHome = ng.home_team_id === STATE.userTeamId;
    const opp = isHome ? ng.away_abbr : ng.home_abbr;
    nextGameHtml = `${isHome ? 'vs' : '@'} <strong>${opp}</strong>`;
    nextGameSub = ng.game_date;
  }

  let calHtml = `
    <div class="dashboard-grid" style="grid-column: 1 / -1;">
      <div class="dash-stat-card">
        <div class="dash-stat-label">Record</div>
        <div class="dash-stat-value">${wins}-${losses}</div>
        <div class="dash-stat-sub">${wins + losses > 0 ? (wins / (wins + losses) * 100).toFixed(1) + '% win rate' : 'Season not started'}</div>
      </div>
      <div class="dash-stat-card">
        <div class="dash-stat-label">Last 10</div>
        <div class="dash-stat-value">${l10w}-${l10l}</div>
        <div class="dash-stat-sub">${last10.length > 0 ? (l10w >= 7 ? 'Hot streak' : l10w >= 5 ? 'Solid' : l10w >= 3 ? 'Cold stretch' : 'Struggling') : 'No games yet'}</div>
      </div>
      <div class="dash-stat-card">
        <div class="dash-stat-label">Streak</div>
        <div class="dash-stat-value ${streakType === 'W' ? 'streak-win' : streakType === 'L' ? 'streak-loss' : ''}">${streakStr}</div>
        <div class="dash-stat-sub">${streakCount >= 5 ? (streakType === 'W' ? 'On fire!' : 'Skid') : streakCount >= 3 ? (streakType === 'W' ? 'Rolling' : 'Rough patch') : 'Game by game'}</div>
      </div>
      <div class="dash-stat-card">
        <div class="dash-stat-label">Next Game</div>
        <div class="dash-stat-value" style="font-size: 20px;">${nextGameHtml}</div>
        <div class="dash-stat-sub">${nextGameSub}</div>
      </div>
      <div class="dash-stat-card">
        <div class="dash-stat-label">Season</div>
        <div class="dash-stat-value" style="font-size: 20px;">${STATE.season}</div>
        <div class="dash-stat-sub" style="text-transform: capitalize;">${STATE.phase.replace('_', ' ')}</div>
      </div>
    </div>
    <div style="grid-column: 1 / -1; display: flex; gap: 16px; margin-bottom: 8px;">
      <div class="card" style="flex:1">
        <h3>Recent Results</h3>
        ${(() => {
          const recent = (games || []).filter(g => g.is_played).sort((a, b) => b.game_date > a.game_date ? 1 : -1).slice(0, 5);
          if (!recent.length) return '<div style="color:var(--text-tertiary);font-size:12px">No games played yet</div>';
          return recent.map(g => {
            const isHome = g.home_team_id === STATE.userTeamId;
            const won = isHome ? g.home_score > g.away_score : g.away_score > g.home_score;
            const opp = isHome ? (g.away_abbr || '???') : (g.home_abbr || '???');
            const myScore = isHome ? g.home_score : g.away_score;
            const theirScore = isHome ? g.away_score : g.home_score;
            const prefix = isHome ? 'vs' : '@';
            return `<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;border-bottom:1px solid var(--border-light);font-size:12px;cursor:pointer" onclick="showBoxScore(${g.id})">
              <span><span class="${won ? 'win' : 'loss'}" style="font-weight:700;width:14px;display:inline-block">${won ? 'W' : 'L'}</span> <span style="color:var(--text-secondary)">${prefix}</span> <strong>${opp}</strong></span>
              <span class="mono" style="font-weight:600">${myScore}-${theirScore}</span>
            </div>`;
          }).join('');
        })()}
      </div>
      <div class="card" style="flex:1">
        <h3>Run Differential</h3>
        ${(() => {
          const played = (games || []).filter(g => g.is_played);
          let rs = 0, ra = 0;
          played.forEach(g => {
            if (g.home_team_id === STATE.userTeamId) { rs += g.home_score; ra += g.away_score; }
            else { rs += g.away_score; ra += g.home_score; }
          });
          const diff = rs - ra;
          return `<div class="dash-stat-value" style="font-size:28px;color:${diff >= 0 ? 'var(--green)' : 'var(--red)'}">
            ${diff >= 0 ? '+' : ''}${diff}
          </div>
          <div class="dash-stat-sub mono">${rs} RS / ${ra} RA</div>`;
        })()}
      </div>
    </div>
    <div class="cal-header">
      <div class="cal-nav">
        <button onclick="navMonth(-1)">\u25C0</button>
        <span class="cal-month-label">${monthNames[m]} ${y}</span>
        <button onclick="navMonth(1)">\u25B6</button>
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
    const b = batting.filter(x => x.team_id === teamId).sort((a, b) => (a.batting_order || 99) - (b.batting_order || 99));
    if (!b.length) return '';
    const totals = b.reduce((t, p) => ({
      ab: t.ab + (p.ab||0), r: t.r + (p.runs||0), h: t.h + (p.hits||0),
      d: t.d + (p.doubles||0), tr: t.tr + (p.triples||0), hr: t.hr + (p.hr||0),
      rbi: t.rbi + (p.rbi||0), bb: t.bb + (p.bb||0), so: t.so + (p.so||0)
    }), {ab:0,r:0,h:0,d:0,tr:0,hr:0,rbi:0,bb:0,so:0});
    return `<div class="section-title" style="margin:12px 0 4px">${abbr} Batting</div>
    <div class="table-wrap"><table>
      <tr><th style="width:24px" class="c">#</th><th class="text-col">Batter</th><th class="c" style="width:32px">POS</th><th class="r">AB</th><th class="r">R</th><th class="r">H</th>
      <th class="r">2B</th><th class="r">3B</th><th class="r">HR</th><th class="r">RBI</th>
      <th class="r">BB</th><th class="r">SO</th><th class="r">AVG</th></tr>
      ${b.map(p => {
        const hrStyle = p.hr > 0 ? 'font-weight:700;color:var(--gold,var(--accent))' : '';
        const multiHit = p.hits >= 3 ? 'font-weight:700' : '';
        return `<tr${p.hr > 0 ? ' style="background:var(--gold-soft,var(--accent-soft))"' : ''}>
        <td class="c mono" style="font-size:11px;color:var(--text-dim)">${p.batting_order || ''}</td>
        <td class="text-col clickable" style="${multiHit}" onclick="showPlayer(${p.player_id})">${p.first_name} ${p.last_name}</td>
        <td class="c" style="font-size:11px;color:var(--text-dim)">${p.position_played || p.position || ''}</td>
        <td class="r mono">${p.ab}</td><td class="r mono">${p.runs}</td><td class="r mono" style="${multiHit}">${p.hits}</td>
        <td class="r mono">${p.doubles}</td><td class="r mono">${p.triples}</td><td class="r mono" style="${hrStyle}">${p.hr}</td>
        <td class="r mono">${p.rbi}</td><td class="r mono">${p.bb}</td><td class="r mono">${p.so}</td>
        <td class="r mono">${fmtAvg(p.hits, p.ab)}</td>
      </tr>`;}).join('')}
      <tr style="font-weight:700;border-top:2px solid var(--border)">
        <td></td><td class="text-col">Totals</td><td></td>
        <td class="r mono">${totals.ab}</td><td class="r mono">${totals.r}</td><td class="r mono">${totals.h}</td>
        <td class="r mono">${totals.d}</td><td class="r mono">${totals.tr}</td><td class="r mono">${totals.hr}</td>
        <td class="r mono">${totals.rbi}</td><td class="r mono">${totals.bb}</td><td class="r mono">${totals.so}</td>
        <td class="r mono">${fmtAvg(totals.h, totals.ab)}</td>
      </tr>
    </table></div>`;
  }

  function pitchingTable(teamId, abbr) {
    const p = pitching.filter(x => x.team_id === teamId).sort((a, b) => (a.pitch_order || 99) - (b.pitch_order || 99));
    if (!p.length) return '';
    const decColor = d => d === 'W' ? 'var(--green)' : d === 'L' ? 'var(--red)' : d === 'S' ? 'var(--gold,var(--accent))' : d === 'H' ? 'var(--accent)' : d === 'BS' ? 'var(--red)' : 'var(--text-dim)';
    const decLabel = d => d === 'W' ? 'W' : d === 'L' ? 'L' : d === 'S' ? 'SV' : d === 'H' ? 'HLD' : d === 'BS' ? 'BS' : '';
    return `<div class="section-title" style="margin:12px 0 4px">${abbr} Pitching</div>
    <div class="table-wrap"><table>
      <tr><th class="text-col">Pitcher</th><th class="r">IP</th><th class="r">H</th><th class="r">R</th>
      <th class="r">ER</th><th class="r">BB</th><th class="r">SO</th><th class="r">HR</th>
      <th class="r">PC</th><th class="c">Dec</th></tr>
      ${p.map(x => `<tr>
        <td class="text-col clickable" onclick="showPlayer(${x.player_id})">${x.first_name} ${x.last_name}</td>
        <td class="r mono">${fmtIp(x.ip_outs)}</td><td class="r mono">${x.hits_allowed}</td><td class="r mono">${x.runs_allowed}</td>
        <td class="r mono">${x.er}</td><td class="r mono">${x.bb}</td><td class="r mono">${x.so}</td>
        <td class="r mono">${x.hr_allowed}</td><td class="r mono">${x.pitches}</td>
        <td class="c" style="font-weight:700;color:${decColor(x.decision)}">${decLabel(x.decision)}</td>
      </tr>`).join('')}
    </table></div>`;
  }

  body.innerHTML = `
    <div style="padding:12px 16px;background:var(--bg-2);border-bottom:1px solid var(--border)">
      <div style="font-family:'Bitter',Georgia,serif;font-size:16px;font-weight:700;letter-spacing:0.5px">${g.away_city} ${g.away_name} @ ${g.home_city} ${g.home_name}</div>
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

  const activeStatus = data.active_count > 26 ? 'over' : data.active_count >= 25 ? 'warn' : 'ok';
  const fortyStatus = data.forty_man_count > 40 ? 'over' : data.forty_man_count >= 39 ? 'warn' : 'ok';
  const payrollVal = data.payroll || 0;
  const payrollStatus = payrollVal > 230e6 ? 'over' : payrollVal > 200e6 ? 'warn' : 'ok';

  let html = `<div class="roster-summary-bar">
    <div class="roster-summary-item roster-status-${activeStatus}">
      <span class="roster-summary-dot"></span>
      <span>${data.active_count}/26 Active</span>
    </div>
    <div class="roster-summary-item roster-status-${fortyStatus}">
      <span class="roster-summary-dot"></span>
      <span>${data.forty_man_count}/40 40-Man</span>
    </div>
    <div class="roster-summary-item">
      <span>IL: ${data.injured_count}</span>
    </div>
    <div class="roster-summary-item roster-status-${payrollStatus}">
      <span class="roster-summary-dot"></span>
      <span>${fmt$(payrollVal)} Payroll</span>
    </div>
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
  const hitters = roster.active.filter(p => p.position !== 'SP' && p.position !== 'RP');

  let html = `
    <div style="display: grid; grid-template-columns: 1fr 250px; gap: 12px; padding: 12px;">
      <div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(100%, 1fr)); gap: 0; border: 1px solid var(--border); border-radius: 4px; overflow: hidden;">
          <table style="width: 100%; border-collapse: collapse;">
            <thead style="background: var(--bg-2); border-bottom: 2px solid var(--border);">
              <tr style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">
                <th style="width: 30px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">#</th>
                <th style="width: 30px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Pos</th>
                <th style="padding: 8px; text-align: left; border-right: 1px solid var(--border);">Player Name</th>
                <th style="width: 35px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">B/T</th>
                <th style="width: 40px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Con</th>
                <th style="width: 40px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Pow</th>
                <th style="width: 40px; padding: 8px; text-align: center;">Spd</th>
              </tr>
            </thead>
            <tbody>`;

  if (order.length) {
    order.forEach((pid, idx) => {
      const p = hitters.find(x => x.id === pid);
      if (p) {
        const con = p.contact_rating || 50;
        const pow = p.power_rating || 50;
        const spd = p.speed_rating || 50;
        html += `
          <tr draggable="true" data-idx="${idx}" ondragstart="dragStart(event, ${idx})" ondragover="dragOver(event)" ondragleave="dragLeave(event)" ondrop="dragDrop(event, ${idx})"
              style="border-bottom: 1px solid var(--border); cursor: move; font-size: 12px; background: var(--bg-1);">
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border); font-weight: 600; color: var(--accent);">${idx + 1}</td>
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border); font-size: 11px;">${p.position}</td>
            <td style="padding: 8px; border-right: 1px solid var(--border); cursor: pointer; text-decoration: underline; text-decoration-color: transparent;" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border); font-size: 11px;">${p.bats || '?'}/${p.throws || '?'}</td>
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border);">${gradeHtml(con)}</td>
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border);">${gradeHtml(pow)}</td>
            <td style="padding: 8px; text-align: center;">${gradeHtml(spd)}</td>
          </tr>`;
      }
    });
  } else {
    html += `<tr><td colspan="7" style="padding: 20px; text-align: center; color: var(--text-dim);">No lineup configured. Click Auto-Generate or add players from Bench.</td></tr>`;
  }

  html += `
            </tbody>
          </table>
        </div>
      </div>
      <div style="border: 1px solid var(--border); border-radius: 4px; padding: 12px; background: var(--bg-1); max-height: 400px; overflow-y: auto;">
        <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; font-weight: 600;">Bench</div>`;

  const inLineup = new Set(order);
  const bench = hitters.filter(p => !inLineup.has(p.id));

  if (bench.length) {
    bench.forEach(p => {
      const con = p.contact_rating || 50;
      const pow = p.power_rating || 50;
      html += `
        <div style="padding: 6px; margin-bottom: 4px; background: var(--bg-2); border-radius: 2px; font-size: 11px; cursor: pointer; border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;" onclick="addToLineup(${p.id})">
          <span onclick="event.stopPropagation(); showPlayer(${p.id}); event.stopPropagation();" style="text-decoration: underline; text-decoration-color: transparent; flex: 1;">${p.first_name.charAt(0)} ${p.last_name}</span>
          <span style="font-size: 10px; color: var(--text-dim);">${p.position}</span>
        </div>`;
    });
  } else {
    html += `<div style="font-size: 11px; color: var(--text-dim); text-align: center;">All hitters in lineup</div>`;
  }

  html += `
      </div>
    </div>`;

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
  const starters = roster.active.filter(p => p.position === 'SP');

  let html = `
    <div style="display: grid; grid-template-columns: 1fr 250px; gap: 12px; padding: 12px;">
      <div>
        <div style="border: 1px solid var(--border); border-radius: 4px; overflow: hidden;">
          <div style="background: var(--bg-2); padding: 12px; border-bottom: 1px solid var(--border); font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Starting Rotation</div>
          <table style="width: 100%; border-collapse: collapse;">
            <thead style="background: var(--bg-1); border-bottom: 1px solid var(--border);">
              <tr style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">
                <th style="width: 50px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Role</th>
                <th style="padding: 8px; text-align: left; border-right: 1px solid var(--border);">Pitcher</th>
                <th style="width: 40px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Stuff</th>
                <th style="width: 40px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Ctrl</th>
                <th style="width: 40px; padding: 8px; text-align: center;">Stm</th>
              </tr>
            </thead>
            <tbody>`;

  if (rotation.length) {
    rotation.forEach((entry, idx) => {
      const pid = entry.player_id || entry;
      const p = starters.find(x => x.id === pid);
      if (p) {
        const stuff = p.stuff_rating || 20;
        const ctrl = p.control_rating || 20;
        const stm = p.stamina_rating || 20;
        const roleDisplay = entry.role || `#${idx + 1}`;
        html += `
          <tr style="border-bottom: 1px solid var(--border); font-size: 12px; background: var(--bg-1);">
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border); font-weight: 600; color: var(--accent);">${roleDisplay}</td>
            <td style="padding: 8px; border-right: 1px solid var(--border); cursor: pointer; text-decoration: underline; text-decoration-color: transparent;" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border);">${gradeHtml(stuff)}</td>
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border);">${gradeHtml(ctrl)}</td>
            <td style="padding: 8px; text-align: center;">${gradeHtml(stm)}</td>
          </tr>`;
      }
    });
  } else {
    html += `<tr><td colspan="5" style="padding: 20px; text-align: center; color: var(--text-dim);">No rotation configured. Click Auto-Generate or add starters from Available.</td></tr>`;
  }

  html += `
            </tbody>
          </table>
        </div>
      </div>
      <div style="border: 1px solid var(--border); border-radius: 4px; padding: 12px; background: var(--bg-1); max-height: 400px; overflow-y: auto;">
        <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; font-weight: 600;">Available Starters</div>`;

  const inRotation = new Set(rotation.map(r => r.player_id || r));
  const available = starters.filter(p => !inRotation.has(p.id));

  if (available.length) {
    available.forEach(p => {
      const stuff = p.stuff_rating || 20;
      html += `
        <div style="padding: 6px; margin-bottom: 4px; background: var(--bg-2); border-radius: 2px; font-size: 11px; cursor: pointer; border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;" onclick="addToRotation(${p.id})">
          <span onclick="event.stopPropagation(); showPlayer(${p.id});" style="text-decoration: underline; text-decoration-color: transparent; flex: 1;">${p.first_name} ${p.last_name}</span>
          <span style="font-size: 10px; color: var(--text-dim);">${gradeHtml(stuff)}</span>
        </div>`;
    });
  } else {
    html += `<div style="font-size: 11px; color: var(--text-dim); text-align: center;">No available starters</div>`;
  }

  html += `
      </div>
    </div>`;

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
  const relievers = roster.active.filter(p => p.position === 'RP');

  let html = `
    <div style="display: grid; grid-template-columns: 1fr 250px; gap: 12px; padding: 12px;">
      <div>
        <div style="border: 1px solid var(--border); border-radius: 4px; overflow: hidden;">
          <div style="background: var(--bg-2); padding: 12px; border-bottom: 1px solid var(--border); font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Bullpen</div>
          <table style="width: 100%; border-collapse: collapse;">
            <thead style="background: var(--bg-1); border-bottom: 1px solid var(--border);">
              <tr style="font-size: 11px; text-transform: uppercase; color: var(--text-muted);">
                <th style="width: 50px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Role</th>
                <th style="padding: 8px; text-align: left; border-right: 1px solid var(--border);">Reliever</th>
                <th style="width: 40px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Stuff</th>
                <th style="width: 40px; padding: 8px; text-align: center; border-right: 1px solid var(--border);">Ctrl</th>
                <th style="width: 50px; padding: 8px; text-align: center;">OVR</th>
              </tr>
            </thead>
            <tbody>`;

  if (bullpen.length) {
    bullpen.forEach((entry) => {
      const pid = entry.player_id || entry.id;
      const p = relievers.find(x => x.id === pid);
      if (p) {
        const stuff = p.stuff_rating || 20;
        const ctrl = p.control_rating || 20;
        const ovr = Math.round((stuff + ctrl) / 2);
        const roleDisplay = entry.role || 'RP';
        const roleColor = roleDisplay === 'CL' ? '#ff6b6b' : roleDisplay === 'SU' ? '#ffd43b' : 'inherit';
        html += `
          <tr style="border-bottom: 1px solid var(--border); font-size: 12px; background: var(--bg-1);">
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border); font-weight: 600; color: ${roleColor};">${roleDisplay}</td>
            <td style="padding: 8px; border-right: 1px solid var(--border); cursor: pointer; text-decoration: underline; text-decoration-color: transparent;" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border);">${gradeHtml(stuff)}</td>
            <td style="padding: 8px; text-align: center; border-right: 1px solid var(--border);">${gradeHtml(ctrl)}</td>
            <td style="padding: 8px; text-align: center;">${gradeHtml(ovr)}</td>
          </tr>`;
      }
    });
  } else {
    html += `<tr><td colspan="5" style="padding: 20px; text-align: center; color: var(--text-dim);">No bullpen configured. Click Auto-Generate or add relievers from Available.</td></tr>`;
  }

  html += `
            </tbody>
          </table>
        </div>
      </div>
      <div style="border: 1px solid var(--border); border-radius: 4px; padding: 12px; background: var(--bg-1); max-height: 400px; overflow-y: auto;">
        <div style="font-size: 11px; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; font-weight: 600;">Available Relievers</div>`;

  const inBullpen = new Set(bullpen.map(b => b.player_id || b.id));
  const available = relievers.filter(p => !inBullpen.has(p.id));

  if (available.length) {
    available.forEach(p => {
      const stuff = p.stuff_rating || 20;
      const ctrl = p.control_rating || 20;
      const ovr = Math.round((stuff + ctrl) / 2);
      html += `
        <div style="padding: 6px; margin-bottom: 4px; background: var(--bg-2); border-radius: 2px; font-size: 11px; cursor: pointer; border: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;" onclick="addToBullpen(${p.id}, '${p.first_name} ${p.last_name}')">
          <span onclick="event.stopPropagation(); showPlayer(${p.id});" style="text-decoration: underline; text-decoration-color: transparent; flex: 1;">${p.first_name} ${p.last_name}</span>
          <span style="font-size: 10px; color: var(--text-dim);">${gradeHtml(ovr)}</span>
        </div>`;
    });
  } else {
    html += `<div style="font-size: 11px; color: var(--text-dim); text-align: center;">No available relievers</div>`;
  }

  html += `
      </div>
    </div>`;

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

async function autoGenerateLineup() {
  if (!STATE.userTeamId) return;
  showToast('Generating optimal lineup...', 'info');
  const result = await post(`/roster/${STATE.userTeamId}/auto-lineup`, {});
  if (result?.success) {
    // Update local state with generated data
    STATE._lineupData = result.lineup_data;
    STATE._rotationData = result.rotation_data;
    showToast('Lineup generated! Review and save.', 'success');
    // Re-render all tabs
    const currentTab = document.querySelector('#s-lineup .section-tabs:nth-of-type(2) .tab-btn.active');
    if (currentTab?.dataset?.tab === 'batting') {
      renderBattingLineup();
    } else if (currentTab?.dataset?.tab === 'rotation') {
      renderRotation();
    } else if (currentTab?.dataset?.tab === 'bullpen') {
      renderBullpen();
    } else {
      renderBattingLineup();
    }
  } else {
    showToast(result?.error || 'Error generating lineup', 'error');
  }
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

  // Add stats filters UI below the search bar
  const resultsContainer = document.getElementById('find-results');
  if (resultsContainer && resultsContainer.innerHTML === '') {
    resultsContainer.innerHTML = `
      <div style="margin: 12px 0; padding: 12px; background: var(--bg-secondary); border-radius: 4px;">
        <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">
          <label style="margin-right: 16px;">
            Min PA/IP: <input type="number" id="find-min-pa" value="0" min="0" max="500" style="width: 50px;" onchange="searchPlayers()">
          </label>
        </div>
        <div style="font-size: 12px; color: var(--text-secondary);">Enter search terms above or select position/team to browse stats.</div>
      </div>
      <div class="empty-state">Search for players by name, position, or team</div>
    `;
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
  const minPA = parseInt(document.getElementById('find-min-pa')?.value || '0');
  const results = document.getElementById('find-results');

  // If text search, use the search endpoint
  if (q) {
    results.innerHTML = '<div class="loading"><span class="spinner"></span> Searching...</div>';
    let params = new URLSearchParams();
    params.set('q', q);
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
    return;
  }

  // If position/team selected, browse stats
  if (pos || teamId || minPA > 0) {
    STATE.statsPage.minPA = minPA;
    STATE.statsPage.sort = 'hr';
    STATE.statsPage.order = 'desc';
    STATE.statsPage.type = (pos === 'SP' || pos === 'RP') ? 'pitchers' : 'batters';
    await displayStatsBrowser(pos || undefined, teamId || undefined, minPA);
    return;
  }

  results.innerHTML = '<div class="empty-state">Search for players by name, position, or team</div>';
}

async function displayStatsBrowser(position, teamId, minPA) {
  const results = document.getElementById('find-results');
  results.innerHTML = '<div class="loading"><span class="spinner"></span> Loading stats...</div>';

  const isBatter = !position || (position !== 'SP' && position !== 'RP');
  const endpoint = isBatter ? '/stats/all-batters' : '/stats/all-pitchers';

  let params = new URLSearchParams();
  params.set('season', '2026');
  params.set('sort', STATE.statsPage.sort);
  params.set('order', STATE.statsPage.order);
  params.set('limit', '100');
  if (minPA > 0) params.set(isBatter ? 'min_pa' : 'min_ip', minPA.toString());
  if (position) params.set('position', position);
  if (teamId) params.set('team_id', teamId);

  const stats = await api(endpoint + '?' + params.toString());

  if (!stats?.length) {
    results.innerHTML = '<div class="empty-state">No stats found</div>';
    return;
  }

  if (isBatter) {
    displayBatterStats(stats);
  } else {
    displayPitcherStats(stats);
  }
}

function displayBatterStats(stats) {
  const results = document.getElementById('find-results');

  let html = `<div class="table-wrap"><table id="stats-table" style="font-size: 12px;">
    <thead><tr>
      <th class="text-col" onclick="reloadStats('batters', 'first_name')" style="cursor:pointer;">Name</th>
      <th class="c" onclick="reloadStats('batters', 'position')" style="cursor:pointer;">Pos</th>
      <th class="r" onclick="reloadStats('batters', 'games')" style="cursor:pointer;">G</th>
      <th class="r" onclick="reloadStats('batters', 'ab')" style="cursor:pointer;">AB</th>
      <th class="r" onclick="reloadStats('batters', 'runs')" style="cursor:pointer;">R</th>
      <th class="r" onclick="reloadStats('batters', 'hits')" style="cursor:pointer;">H</th>
      <th class="r" onclick="reloadStats('batters', 'doubles')" style="cursor:pointer;">2B</th>
      <th class="r" onclick="reloadStats('batters', 'triples')" style="cursor:pointer;">3B</th>
      <th class="r" onclick="reloadStats('batters', 'hr')" style="cursor:pointer;">HR</th>
      <th class="r" onclick="reloadStats('batters', 'rbi')" style="cursor:pointer;">RBI</th>
      <th class="r" onclick="reloadStats('batters', 'bb')" style="cursor:pointer;">BB</th>
      <th class="r" onclick="reloadStats('batters', 'so')" style="cursor:pointer;">SO</th>
      <th class="r" onclick="reloadStats('batters', 'sb')" style="cursor:pointer;">SB</th>
      <th class="r" onclick="reloadStats('batters', 'avg')" style="cursor:pointer;">AVG</th>
      <th class="r" onclick="reloadStats('batters', 'obp')" style="cursor:pointer;">OBP</th>
      <th class="r" onclick="reloadStats('batters', 'slg')" style="cursor:pointer;">SLG</th>
      <th class="r" onclick="reloadStats('batters', 'ops')" style="cursor:pointer;">OPS</th>
      <th class="c" onclick="reloadStats('batters', 'contact_rating')" style="cursor:pointer;">CON</th>
      <th class="c" onclick="reloadStats('batters', 'power_rating')" style="cursor:pointer;">POW</th>
      <th class="c" onclick="reloadStats('batters', 'speed_rating')" style="cursor:pointer;">SPD</th>
      <th class="text-col">Team</th>
    </tr></thead><tbody>`;

  stats.forEach(s => {
    const ops = (parseFloat(s.obp) + parseFloat(s.slg)).toFixed(3);
    html += `<tr onclick="showPlayer(${s.id})" style="cursor:pointer;">
      <td class="text-col">${s.first_name} ${s.last_name}</td>
      <td class="c">${s.position}</td>
      <td class="r">${s.games}</td>
      <td class="r">${s.ab}</td>
      <td class="r">${s.runs}</td>
      <td class="r">${s.hits}</td>
      <td class="r">${s.doubles}</td>
      <td class="r">${s.triples}</td>
      <td class="r">${s.hr}</td>
      <td class="r">${s.rbi}</td>
      <td class="r">${s.bb}</td>
      <td class="r">${s.so}</td>
      <td class="r">${s.sb}</td>
      <td class="r mono">${(s.avg || 0).toFixed(3).replace(/^0/, '')}</td>
      <td class="r mono">${(s.obp || 0).toFixed(3).replace(/^0/, '')}</td>
      <td class="r mono">${(s.slg || 0).toFixed(3).replace(/^0/, '')}</td>
      <td class="r mono">${ops.replace(/^0/, '')}</td>
      <td class="c">${gradeHtml(s.contact_rating)}</td>
      <td class="c">${gradeHtml(s.power_rating)}</td>
      <td class="c">${gradeHtml(s.speed_rating)}</td>
      <td class="text-col">${s.abbreviation}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  results.innerHTML = html;
}

function displayPitcherStats(stats) {
  const results = document.getElementById('find-results');

  let html = `<div class="table-wrap"><table id="stats-table" style="font-size: 12px;">
    <thead><tr>
      <th class="text-col" onclick="reloadStats('pitchers', 'first_name')" style="cursor:pointer;">Name</th>
      <th class="c" onclick="reloadStats('pitchers', 'position')" style="cursor:pointer;">Pos</th>
      <th class="r" onclick="reloadStats('pitchers', 'games')" style="cursor:pointer;">G</th>
      <th class="r" onclick="reloadStats('pitchers', 'games_started')" style="cursor:pointer;">GS</th>
      <th class="r" onclick="reloadStats('pitchers', 'wins')" style="cursor:pointer;">W</th>
      <th class="r" onclick="reloadStats('pitchers', 'losses')" style="cursor:pointer;">L</th>
      <th class="r" onclick="reloadStats('pitchers', 'saves')" style="cursor:pointer;">SV</th>
      <th class="r" onclick="reloadStats('pitchers', 'ip_outs')" style="cursor:pointer;">IP</th>
      <th class="r" onclick="reloadStats('pitchers', 'hits_allowed')" style="cursor:pointer;">H</th>
      <th class="r" onclick="reloadStats('pitchers', 'er')" style="cursor:pointer;">ER</th>
      <th class="r" onclick="reloadStats('pitchers', 'bb')" style="cursor:pointer;">BB</th>
      <th class="r" onclick="reloadStats('pitchers', 'so')" style="cursor:pointer;">SO</th>
      <th class="r" onclick="reloadStats('pitchers', 'hr_allowed')" style="cursor:pointer;">HR</th>
      <th class="r" onclick="reloadStats('pitchers', 'era')" style="cursor:pointer;">ERA</th>
      <th class="r" onclick="reloadStats('pitchers', 'whip')" style="cursor:pointer;">WHIP</th>
      <th class="r" onclick="reloadStats('pitchers', 'k9')" style="cursor:pointer;">K/9</th>
      <th class="r" onclick="reloadStats('pitchers', 'bb9')" style="cursor:pointer;">BB/9</th>
      <th class="r" onclick="reloadStats('pitchers', 'k_bb')" style="cursor:pointer;">K/BB</th>
      <th class="c" onclick="reloadStats('pitchers', 'stuff_rating')" style="cursor:pointer;">STF</th>
      <th class="c" onclick="reloadStats('pitchers', 'control_rating')" style="cursor:pointer;">CTL</th>
      <th class="c" onclick="reloadStats('pitchers', 'stamina_rating')" style="cursor:pointer;">STA</th>
      <th class="text-col">Team</th>
    </tr></thead><tbody>`;

  stats.forEach(s => {
    const ip = Math.floor(s.ip_outs / 3) + '.' + (s.ip_outs % 3);
    html += `<tr onclick="showPlayer(${s.id})" style="cursor:pointer;">
      <td class="text-col">${s.first_name} ${s.last_name}</td>
      <td class="c">${s.position}</td>
      <td class="r">${s.games}</td>
      <td class="r">${s.games_started}</td>
      <td class="r">${s.wins}</td>
      <td class="r">${s.losses}</td>
      <td class="r">${s.saves}</td>
      <td class="r mono">${ip}</td>
      <td class="r">${s.hits_allowed}</td>
      <td class="r">${s.er}</td>
      <td class="r">${s.bb}</td>
      <td class="r">${s.so}</td>
      <td class="r">${s.hr_allowed}</td>
      <td class="r mono">${(s.era || 0).toFixed(2)}</td>
      <td class="r mono">${(s.whip || 0).toFixed(2)}</td>
      <td class="r mono">${(s.k9 || 0).toFixed(2)}</td>
      <td class="r mono">${(s.bb9 || 0).toFixed(2)}</td>
      <td class="r mono">${(s.k_bb || 0).toFixed(2)}</td>
      <td class="c">${gradeHtml(s.stuff_rating)}</td>
      <td class="c">${gradeHtml(s.control_rating)}</td>
      <td class="c">${gradeHtml(s.stamina_rating)}</td>
      <td class="text-col">${s.abbreviation}</td>
    </tr>`;
  });
  html += '</tbody></table></div>';
  results.innerHTML = html;
}

async function reloadStats(type, sortField) {
  const pos = document.getElementById('find-pos')?.value || '';
  const teamId = document.getElementById('find-team')?.value || '';
  const minPA = parseInt(document.getElementById('find-min-pa')?.value || '0');

  // Toggle sort direction if same field
  if (STATE.statsPage.sort === sortField) {
    STATE.statsPage.order = STATE.statsPage.order === 'asc' ? 'desc' : 'asc';
  } else {
    STATE.statsPage.sort = sortField;
    STATE.statsPage.order = 'desc';
  }

  await displayStatsBrowser(pos || undefined, teamId || undefined, minPA);
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
    <div class="grade-box-lg"><div class="grade-label">${l}</div>
    <div class="grade-value-lg ${gradeClass(v)}">${toGrade(v)}</div>
    <div class="grade-num">${v}</div></div>`).join('');

  const persHtml = personality.map(([l, v]) => `
    <div class="grade-box"><div class="grade-label">${l}</div>
    <div class="grade-value ${gradeClass(v)}">${toGrade(v)}</div>
    <div class="grade-num">${v}</div></div>`).join('');

  // Build mini current-season stat line for the overview tab
  let miniStatHtml = '';
  if (d.batting_stats?.length) {
    const cur = d.batting_stats[d.batting_stats.length - 1];
    if (cur && cur.ab > 0) {
      const avg = fmtAvg(cur.hits, cur.ab);
      const obp = ((cur.hits+cur.bb+(cur.hbp||0))/(cur.ab+cur.bb+(cur.hbp||0)+(cur.sf||0))).toFixed(3).replace(/^0/,'');
      const slg = ((cur.hits+cur.doubles+cur.triples*2+cur.hr*3)/cur.ab).toFixed(3).replace(/^0/,'');
      miniStatHtml = `<div class="mini-stat-line">
        <span class="mini-stat">${cur.games} G</span>
        <span class="mini-stat">${avg} AVG</span>
        <span class="mini-stat">${cur.hr} HR</span>
        <span class="mini-stat">${cur.rbi} RBI</span>
        <span class="mini-stat">${obp} OBP</span>
        <span class="mini-stat">${slg} SLG</span>
      </div>`;
    }
  }
  if (d.pitching_stats?.length && !miniStatHtml) {
    const cur = d.pitching_stats[d.pitching_stats.length - 1];
    if (cur) {
      const era = fmtEra(cur.er, cur.ip_outs);
      const whip = cur.ip_outs > 0 ? ((cur.hits_allowed+cur.bb)/(cur.ip_outs/3)).toFixed(2) : '0.00';
      miniStatHtml = `<div class="mini-stat-line">
        <span class="mini-stat">${cur.games} G</span>
        <span class="mini-stat">${cur.wins}-${cur.losses} W-L</span>
        <span class="mini-stat">${era} ERA</span>
        <span class="mini-stat">${fmtIp(cur.ip_outs)} IP</span>
        <span class="mini-stat">${cur.so} K</span>
        <span class="mini-stat">${whip} WHIP</span>
      </div>`;
    }
  }

  let statsHtml = '';
  if (d.batting_stats?.length) {
    statsHtml += `<div class="section-title" style="margin:12px 0 4px">Batting Stats</div>`;
    statsHtml += `<div class="table-wrap"><table>
      <tr><th>Season</th><th class="r">G</th><th class="r">AB</th><th class="r">R</th><th class="r">H</th><th class="r">2B</th>
      <th class="r">3B</th><th class="r">HR</th><th class="r">RBI</th><th class="r">BB</th><th class="r">SO</th>
      <th class="r">SB</th><th class="r">AVG</th><th class="r">OBP</th><th class="r">SLG</th></tr>`;
    d.batting_stats.forEach(s => {
      const obp = s.ab > 0 ? ((s.hits+s.bb+(s.hbp||0))/(s.ab+s.bb+(s.hbp||0)+(s.sf||0))).toFixed(3).replace(/^0/,'') : '.000';
      const slg = s.ab > 0 ? ((s.hits+s.doubles+s.triples*2+s.hr*3)/s.ab).toFixed(3).replace(/^0/,'') : '.000';
      statsHtml += `<tr><td>${s.season}</td><td class="r">${s.games}</td><td class="r">${s.ab}</td><td class="r">${s.runs}</td><td class="r">${s.hits}</td>
      <td class="r">${s.doubles}</td><td class="r">${s.triples}</td><td class="r">${s.hr}</td><td class="r">${s.rbi}</td>
      <td class="r">${s.bb}</td><td class="r">${s.so}</td><td class="r">${s.sb}</td>
      <td class="r">${fmtAvg(s.hits, s.ab)}</td>
      <td class="r">${obp}</td>
      <td class="r">${slg}</td></tr>`;
    });
    // Career totals row
    if (d.batting_stats.length > 1) {
      const ct = d.batting_stats.reduce((a, s) => ({
        games: a.games + s.games, ab: a.ab + s.ab, runs: a.runs + s.runs, hits: a.hits + s.hits,
        doubles: a.doubles + s.doubles, triples: a.triples + s.triples, hr: a.hr + s.hr, rbi: a.rbi + s.rbi,
        bb: a.bb + s.bb, so: a.so + s.so, sb: a.sb + s.sb, hbp: (a.hbp||0) + (s.hbp||0), sf: (a.sf||0) + (s.sf||0)
      }), {games:0,ab:0,runs:0,hits:0,doubles:0,triples:0,hr:0,rbi:0,bb:0,so:0,sb:0,hbp:0,sf:0});
      const cobp = ct.ab > 0 ? ((ct.hits+ct.bb+ct.hbp)/(ct.ab+ct.bb+ct.hbp+ct.sf)).toFixed(3).replace(/^0/,'') : '.000';
      const cslg = ct.ab > 0 ? ((ct.hits+ct.doubles+ct.triples*2+ct.hr*3)/ct.ab).toFixed(3).replace(/^0/,'') : '.000';
      statsHtml += `<tr style="font-weight:700;border-top:2px solid var(--border)"><td>Career</td><td class="r">${ct.games}</td><td class="r">${ct.ab}</td><td class="r">${ct.runs}</td><td class="r">${ct.hits}</td>
      <td class="r">${ct.doubles}</td><td class="r">${ct.triples}</td><td class="r">${ct.hr}</td><td class="r">${ct.rbi}</td>
      <td class="r">${ct.bb}</td><td class="r">${ct.so}</td><td class="r">${ct.sb}</td>
      <td class="r">${fmtAvg(ct.hits, ct.ab)}</td><td class="r">${cobp}</td><td class="r">${cslg}</td></tr>`;
    }
    statsHtml += `</table></div>`;
  }
  if (d.pitching_stats?.length) {
    statsHtml += `<div class="section-title" style="margin:12px 0 4px">Pitching Stats</div>`;
    statsHtml += `<div class="table-wrap"><table>
      <tr><th>Season</th><th class="r">G</th><th class="r">GS</th><th class="r">W</th><th class="r">L</th><th class="r">SV</th>
      <th class="r">IP</th><th class="r">H</th><th class="r">ER</th><th class="r">BB</th><th class="r">SO</th>
      <th class="r">HR</th><th class="r">ERA</th><th class="r">WHIP</th></tr>`;
    d.pitching_stats.forEach(s => {
      const era = fmtEra(s.er, s.ip_outs);
      const whip = s.ip_outs > 0 ? ((s.hits_allowed+s.bb)/(s.ip_outs/3)).toFixed(2) : '0.00';
      statsHtml += `<tr><td>${s.season}</td><td class="r">${s.games}</td><td class="r">${s.games_started}</td><td class="r">${s.wins}</td><td class="r">${s.losses}</td>
      <td class="r">${s.saves}</td><td class="r">${fmtIp(s.ip_outs)}</td><td class="r">${s.hits_allowed}</td>
      <td class="r">${s.er}</td><td class="r">${s.bb}</td><td class="r">${s.so}</td><td class="r">${s.hr_allowed}</td>
      <td class="r">${era}</td>
      <td class="r">${whip}</td></tr>`;
    });
    // Career totals row
    if (d.pitching_stats.length > 1) {
      const ct = d.pitching_stats.reduce((a, s) => ({
        games: a.games + s.games, games_started: a.games_started + s.games_started,
        wins: a.wins + s.wins, losses: a.losses + s.losses, saves: a.saves + s.saves,
        ip_outs: a.ip_outs + s.ip_outs, hits_allowed: a.hits_allowed + s.hits_allowed,
        er: a.er + s.er, bb: a.bb + s.bb, so: a.so + s.so, hr_allowed: a.hr_allowed + s.hr_allowed
      }), {games:0,games_started:0,wins:0,losses:0,saves:0,ip_outs:0,hits_allowed:0,er:0,bb:0,so:0,hr_allowed:0});
      const cera = fmtEra(ct.er, ct.ip_outs);
      const cwhip = ct.ip_outs > 0 ? ((ct.hits_allowed+ct.bb)/(ct.ip_outs/3)).toFixed(2) : '0.00';
      statsHtml += `<tr style="font-weight:700;border-top:2px solid var(--border)"><td>Career</td><td class="r">${ct.games}</td><td class="r">${ct.games_started}</td><td class="r">${ct.wins}</td><td class="r">${ct.losses}</td>
      <td class="r">${ct.saves}</td><td class="r">${fmtIp(ct.ip_outs)}</td><td class="r">${ct.hits_allowed}</td>
      <td class="r">${ct.er}</td><td class="r">${ct.bb}</td><td class="r">${ct.so}</td><td class="r">${ct.hr_allowed}</td>
      <td class="r">${cera}</td><td class="r">${cwhip}</td></tr>`;
    }
    statsHtml += `</table></div>`;
  }

  // Determine which action buttons to show
  const isUserTeam = p.team_id === STATE.userTeamId;
  const isFreeAgent = !p.team_id;
  const isActive = p.roster_status === 'active';
  const isMinors = p.roster_status && p.roster_status.includes('minors');
  const isIL = p.roster_status && p.roster_status.includes('il_');
  const hasOptionYears = p.option_years_remaining && p.option_years_remaining > 0;
  const onFortyMan = p.on_forty_man;

  let actionBarHtml = '';
  if (isUserTeam || isFreeAgent) {
    actionBarHtml = '<div class="player-action-bar" style="display:flex;gap:4px;margin-top:8px;flex-wrap:wrap;border-top:1px solid var(--border);padding-top:8px">';

    if (isUserTeam && isActive) {
      // Active roster actions
      if (hasOptionYears) {
        actionBarHtml += `<button class="btn btn-sm" onclick="showOptionMenu(${p.id})">Option to Minors</button>`;
      }
      actionBarHtml += `<button class="btn btn-sm" onclick="showILMenu(${p.id})">Place on IL</button>`;
      actionBarHtml += `<button class="btn btn-sm" onclick="confirmDFA(${p.id})">DFA</button>`;
      actionBarHtml += `<button class="btn btn-sm" onclick="confirmRelease(${p.id})">Release</button>`;
      actionBarHtml += `<button class="btn btn-sm" onclick="showExtendModal(${p.id})">Extend Contract</button>`;
      actionBarHtml += `<button class="btn btn-sm" onclick="confirmAddToBlock(${p.id})">Add to Trading Block</button>`;
    } else if (isUserTeam && isMinors) {
      // Minor league actions
      actionBarHtml += `<button class="btn btn-sm" onclick="confirmCallUp(${p.id})">Call Up</button>`;
      actionBarHtml += `<button class="btn btn-sm" onclick="confirmRelease(${p.id})">Release</button>`;
      if (!onFortyMan) {
        actionBarHtml += `<button class="btn btn-sm" onclick="confirmAddToFortyMan(${p.id})">Add to 40-Man</button>`;
      }
    } else if (isUserTeam && isIL) {
      // IL actions
      actionBarHtml += `<button class="btn btn-sm" onclick="confirmActivateFromIL(${p.id})">Activate from IL</button>`;
    }

    if (isFreeAgent) {
      // Free agent actions
      actionBarHtml += `<button class="btn btn-primary btn-sm" onclick="showSignPlayerModal(${p.id})">Sign Player</button>`;
    }

    actionBarHtml += '</div>';
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
        <div style="font-size:10px;margin-top:2px;color:var(--text-dim)">${
          p.service_years < 3 ? '<span style="color:var(--blue)">Pre-Arbitration</span>' :
          p.service_years < 6 ? '<span style="color:var(--orange)">Arb-Eligible (Yr ' + Math.min(Math.floor(p.service_years) - 2, 4) + ')</span>' :
          '<span style="color:var(--green)">FA-Eligible</span>'
        } | ${(p.service_years || 0).toFixed(1)} service yrs</div>
        ${p.no_trade_clause ? '<div style="color:var(--red);font-size:10px">NO-TRADE CLAUSE</div>' : ''}
        <button class="btn btn-sm" style="margin-top: 6px;" onclick="compareWithPlayer(${p.id})">Compare</button>
      </div>
    </div>
    ${actionBarHtml}
    <div class="modal-tabs">
      <button class="modal-tab active" onclick="switchPlayerTab(event, 'overview')">Overview</button>
      <button class="modal-tab" onclick="switchPlayerTab(event, 'stats')">Stats</button>
      <button class="modal-tab" onclick="switchPlayerTab(event, 'scouting')">Scouting</button>
    </div>
    <div class="modal-body">
      <div id="player-tab-overview">
        ${p.is_injured ? `<div style="background:var(--red);color:white;padding:8px 12px;border-radius:4px;margin-bottom:12px;font-size:12px">
          <strong>INJURED</strong> - ${p.injury_type || 'Unknown injury'} (${p.injury_days_remaining || '?'} days remaining)
        </div>` : ''}
        <div class="section-title">${isPit ? 'Pitching' : 'Hitting'} Grades</div>
        <div class="grades-row">${gradesHtml}</div>
        ${miniStatHtml ? `<div class="section-title" style="margin-top:12px">${STATE.season} Season</div>${miniStatHtml}` : ''}
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

// ============================================================
// PLAYER ACTION BUTTONS
// ============================================================
function confirmDFA(pid) {
  document.getElementById('action-confirm-panel')?.remove();

  const bar = document.querySelector('.player-action-bar');
  if (!bar) return;

  const panel = document.createElement('div');
  panel.id = 'action-confirm-panel';
  panel.style.cssText = 'background:var(--bg-2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-top:8px';
  panel.innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Designate this player for assignment?</div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" style="background:var(--red);color:white" onclick="execDFA(${pid})">Confirm DFA</button>
      <button class="btn btn-sm" onclick="document.getElementById('action-confirm-panel').remove()">Cancel</button>
    </div>
  `;
  bar.after(panel);
}

async function execDFA(pid) {
  const r = await api(`/roster/dfa/${pid}`, { method: 'POST' });
  if (r?.success) {
    showToast('Player designated for assignment', 'success');
    closeModal();
    loadRoster();
  } else {
    showToast(r?.error || 'Error designating player', 'error');
  }
}

function showOptionMenu(pid) {
  document.getElementById('action-confirm-panel')?.remove();

  const bar = document.querySelector('.player-action-bar');
  if (!bar) return;

  const panel = document.createElement('div');
  panel.id = 'action-confirm-panel';
  panel.style.cssText = 'background:var(--bg-2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-top:8px';
  panel.innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Select assignment level:</div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" onclick="optionPlayer(${pid}, 'minors_aaa'); document.getElementById('action-confirm-panel').remove()">AAA</button>
      <button class="btn btn-sm" onclick="optionPlayer(${pid}, 'minors_aa'); document.getElementById('action-confirm-panel').remove()">AA</button>
      <button class="btn btn-sm" onclick="optionPlayer(${pid}, 'minors_low'); document.getElementById('action-confirm-panel').remove()">Low-A</button>
      <button class="btn btn-sm" onclick="document.getElementById('action-confirm-panel').remove()">Cancel</button>
    </div>
  `;
  bar.after(panel);
}

async function optionPlayer(pid, level) {
  const r = await api(`/roster/option/${pid}?level=${level}`, { method: 'POST' });
  if (r?.success) {
    showToast(`Player optioned to ${level}`, 'success');
    closeModal();
    loadRoster();
  } else {
    showToast(r?.error || 'Error optioning player', 'error');
  }
}

function showILMenu(pid) {
  document.getElementById('action-confirm-panel')?.remove();

  const bar = document.querySelector('.player-action-bar');
  if (!bar) return;

  const panel = document.createElement('div');
  panel.id = 'action-confirm-panel';
  panel.style.cssText = 'background:var(--bg-2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-top:8px';
  panel.innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Select IL tier:</div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" onclick="placeOnIL(${pid}, '10'); document.getElementById('action-confirm-panel').remove()">10-Day IL</button>
      <button class="btn btn-sm" onclick="placeOnIL(${pid}, '15'); document.getElementById('action-confirm-panel').remove()">15-Day IL</button>
      <button class="btn btn-sm" onclick="placeOnIL(${pid}, '60'); document.getElementById('action-confirm-panel').remove()">60-Day IL</button>
      <button class="btn btn-sm" onclick="document.getElementById('action-confirm-panel').remove()">Cancel</button>
    </div>
  `;
  bar.after(panel);
}

async function placeOnIL(pid, tier) {
  const r = await api(`/roster/${STATE.userTeamId}/place-il`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_id: pid, tier })
  });
  if (r?.success) {
    showToast(`Player placed on ${tier}-day IL`, 'success');
    closeModal();
    loadRoster();
  } else {
    showToast(r?.error || 'Error placing player on IL', 'error');
  }
}

function confirmRelease(pid) {
  document.getElementById('action-confirm-panel')?.remove();

  const bar = document.querySelector('.player-action-bar');
  if (!bar) return;

  const panel = document.createElement('div');
  panel.id = 'action-confirm-panel';
  panel.style.cssText = 'background:var(--bg-2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-top:8px';
  panel.innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Release this player? They will become a free agent.</div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" style="background:var(--red);color:white" onclick="execRelease(${pid})">Confirm Release</button>
      <button class="btn btn-sm" onclick="document.getElementById('action-confirm-panel').remove()">Cancel</button>
    </div>
  `;
  bar.after(panel);
}

async function execRelease(pid) {
  const r = await api(`/roster/release/${pid}`, { method: 'POST' });
  if (r?.success) {
    showToast('Player released', 'success');
    closeModal();
    loadRoster();
  } else {
    showToast(r?.error || 'Error releasing player', 'error');
  }
}

function confirmCallUp(pid) {
  document.getElementById('action-confirm-panel')?.remove();

  const bar = document.querySelector('.player-action-bar');
  if (!bar) return;

  const panel = document.createElement('div');
  panel.id = 'action-confirm-panel';
  panel.style.cssText = 'background:var(--bg-2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-top:8px';
  panel.innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Call up this player to the active roster?</div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" style="background:var(--green);color:white" onclick="execCallUp(${pid})">Confirm Call Up</button>
      <button class="btn btn-sm" onclick="document.getElementById('action-confirm-panel').remove()">Cancel</button>
    </div>
  `;
  bar.after(panel);
}

async function execCallUp(pid) {
  const r = await api(`/roster/call-up/${pid}`, { method: 'POST' });
  if (r?.success) {
    showToast('Player called up', 'success');
    closeModal();
    loadRoster();
  } else {
    showToast(r?.error || 'Error calling up player', 'error');
  }
}

function confirmActivateFromIL(pid) {
  document.getElementById('action-confirm-panel')?.remove();

  const bar = document.querySelector('.player-action-bar');
  if (!bar) return;

  const panel = document.createElement('div');
  panel.id = 'action-confirm-panel';
  panel.style.cssText = 'background:var(--bg-2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-top:8px';
  panel.innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Activate this player from the injured list?</div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" style="background:var(--green);color:white" onclick="execActivateFromIL(${pid})">Confirm Activation</button>
      <button class="btn btn-sm" onclick="document.getElementById('action-confirm-panel').remove()">Cancel</button>
    </div>
  `;
  bar.after(panel);
}

async function execActivateFromIL(pid) {
  const r = await api(`/roster/${STATE.userTeamId}/activate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_id: pid })
  });
  if (r?.success) {
    showToast('Player activated from IL', 'success');
    closeModal();
    loadRoster();
  } else {
    showToast(r?.error || 'Error activating player', 'error');
  }
}

function confirmAddToFortyMan(pid) {
  document.getElementById('action-confirm-panel')?.remove();

  const bar = document.querySelector('.player-action-bar');
  if (!bar) return;

  const panel = document.createElement('div');
  panel.id = 'action-confirm-panel';
  panel.style.cssText = 'background:var(--bg-2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-top:8px';
  panel.innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Add this player to the 40-man roster?</div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" style="background:var(--blue);color:white" onclick="execAddToFortyMan(${pid})">Confirm Add</button>
      <button class="btn btn-sm" onclick="document.getElementById('action-confirm-panel').remove()">Cancel</button>
    </div>
  `;
  bar.after(panel);
}

async function execAddToFortyMan(pid) {
  const r = await api(`/roster/forty-man/add/${pid}`, { method: 'POST' });
  if (r?.success) {
    showToast('Player added to 40-man roster', 'success');
    closeModal();
    loadRoster();
  } else {
    showToast(r?.error || 'Error adding player to 40-man', 'error');
  }
}

function showSignPlayerModal(pid) {
  // Create a sign player modal for free agents
  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.style.display = 'flex';
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

  modal.innerHTML = `
    <div class="modal-content" style="max-width:400px">
      <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
      <div style="font-weight:700;margin-bottom:16px;font-size:16px">Sign Player</div>
      <div id="sign-current" style="margin-bottom:16px"></div>
      <div style="margin-bottom:12px">
        <label style="font-size:12px;color:var(--text-muted);text-transform:uppercase">Years</label>
        <input type="number" id="sign-years" min="1" max="10" value="1" style="width:100%;padding:8px;margin-top:4px;background:var(--bg-2);border:1px solid var(--border);color:var(--text);border-radius:2px">
      </div>
      <div style="margin-bottom:12px">
        <label style="font-size:12px;color:var(--text-muted);text-transform:uppercase">Annual Salary</label>
        <input type="number" id="sign-salary" value="5000000" style="width:100%;padding:8px;margin-top:4px;background:var(--bg-2);border:1px solid var(--border);color:var(--text);border-radius:2px">
      </div>
      <button class="btn btn-primary" style="width:100%;margin-top:16px" onclick="submitSignPlayer(${pid})">Offer Contract</button>
    </div>
  `;
  document.body.appendChild(modal);

  // Load player info
  api('/player/' + pid).then(d => {
    if (d?.player) {
      const p = d.player;
      document.getElementById('sign-current').innerHTML = `
        <div style="padding:12px;background:var(--bg-2);border-radius:2px">
          <div style="font-weight:700">${p.first_name} ${p.last_name}</div>
          <div style="font-size:11px;color:var(--text-muted)">${p.position} | Age ${p.age}</div>
        </div>
      `;
    }
  });
}

async function submitSignPlayer(pid) {
  const years = parseInt(document.getElementById('sign-years').value);
  const salary = parseInt(document.getElementById('sign-salary').value);

  if (isNaN(years) || isNaN(salary) || years < 1 || salary < 0) {
    showToast('Invalid contract terms', 'error');
    return;
  }

  const r = await api('/free-agency/sign', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_id: pid, team_id: STATE.userTeamId, years, annual_salary: salary })
  });

  if (r?.success) {
    showToast('Player signed', 'success');
    document.querySelector('.modal').remove();
    closeModal();
    loadRoster();
  } else {
    showToast(r?.error || 'Error signing player', 'error');
  }
}

function showExtendModal(pid) {
  const modal = document.getElementById('player-modal');
  const extModal = document.createElement('div');
  extModal.id = 'extend-modal';
  extModal.className = 'modal';
  extModal.style.display = 'flex';
  extModal.onclick = (e) => { if (e.target === extModal) extModal.remove(); };

  extModal.innerHTML = `
    <div class="modal-content" style="max-width:450px">
      <button class="modal-close" onclick="document.getElementById('extend-modal').remove()">&times;</button>
      <div style="font-weight:700;margin-bottom:16px;font-size:16px">Extend Contract</div>
      <div id="extend-current"></div>

      <div style="margin-top:16px">
        <label style="font-size:12px;color:var(--text-muted);text-transform:uppercase">Annual Salary</label>
        <div style="display:flex;gap:8px;margin-top:4px">
          <input type="range" id="extend-salary-slider" min="500000" max="30000000" step="100000" value="5000000" style="flex:1;cursor:pointer" onchange="updateExtendSalaryDisplay()">
          <div style="display:flex;flex-direction:column;justify-content:center;align-items:flex-end;min-width:130px">
            <input type="number" id="extend-salary" min="500000" max="30000000" step="100000" value="5000000" style="width:100%;padding:6px;background:var(--bg-2);border:1px solid var(--border);color:var(--text);border-radius:2px" onchange="updateExtendSalarySlider()">
            <div id="extend-salary-display" style="font-size:11px;color:var(--accent);font-weight:600;margin-top:4px">$5.0M</div>
          </div>
        </div>
      </div>

      <div style="margin-top:12px">
        <label style="font-size:12px;color:var(--text-muted);text-transform:uppercase">Years (1-10)</label>
        <select id="extend-years" style="width:100%;padding:8px;margin-top:4px;background:var(--bg-2);border:1px solid var(--border);color:var(--text);border-radius:2px">
          ${[1,2,3,4,5,6,7,8,9,10].map(y => `<option value="${y}" ${y === 3 ? 'selected' : ''}>${y}</option>`).join('')}
        </select>
      </div>

      <div style="margin-top:12px;display:flex;align-items:center;gap:8px">
        <input type="checkbox" id="extend-notrade" style="width:18px;height:18px;cursor:pointer">
        <label style="font-size:12px;color:var(--text-muted);cursor:pointer;margin:0" for="extend-notrade">Include No-Trade Clause</label>
      </div>

      <div style="margin-top:12px;padding:12px;background:var(--bg-2);border-radius:2px">
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:6px">Market Value Estimate</div>
        <div id="extend-market" style="font-weight:700;color:var(--accent);font-size:14px">Loading...</div>
      </div>

      <button class="btn btn-primary" style="width:100%;margin-top:16px" onclick="submitContractExtension(${pid})">Offer Extension</button>

      <div id="extend-result" style="margin-top:16px;padding:12px;background:var(--bg-2);border-radius:2px;display:none"></div>
    </div>
  `;
  document.body.appendChild(extModal);
  loadExtendData(pid);
}

function updateExtendSalaryDisplay() {
  const slider = document.getElementById('extend-salary-slider');
  const input = document.getElementById('extend-salary');
  const display = document.getElementById('extend-salary-display');
  input.value = slider.value;
  if (display) display.textContent = fmt$(parseInt(slider.value));
}

function updateExtendSalarySlider() {
  const slider = document.getElementById('extend-salary-slider');
  const input = document.getElementById('extend-salary');
  const display = document.getElementById('extend-salary-display');
  slider.value = input.value;
  if (display) display.textContent = fmt$(parseInt(input.value));
}

async function loadExtendData(pid) {
  const d = await api('/player/' + pid);
  if (d?.player) {
    const p = d.player;
    const current = `<div style="padding:12px;background:var(--bg-1);border-radius:2px;font-size:12px">
      <div style="margin-bottom:6px"><span style="color:var(--text-muted)">Current Salary:</span> <strong>${fmt$(p.annual_salary)}</strong></div>
      <div><span style="color:var(--text-muted)">Years Remaining:</span> <strong>${p.years_remaining || 0}</strong></div>
    </div>`;
    document.getElementById('extend-current').innerHTML = current;

    const isPit = p.position === 'SP' || p.position === 'RP';
    const overall = isPit
      ? (p.stuff_rating * 2 + p.control_rating * 1.5) / 3.5
      : (p.contact_rating * 1.5 + p.power_rating * 1.5 + p.speed_rating * 0.5 + p.fielding_rating * 0.5) / 4;

    const marketValue = Math.round(overall * 100000 * (p.service_years || 1));
    document.getElementById('extend-market').textContent = fmt$(marketValue);
    document.getElementById('extend-salary').value = marketValue;
    document.getElementById('extend-salary-slider').value = marketValue;
    const display = document.getElementById('extend-salary-display');
    if (display) display.textContent = fmt$(marketValue);
  }
}

async function submitContractExtension(pid) {
  const years = parseInt(document.getElementById('extend-years').value);
  const salary = parseInt(document.getElementById('extend-salary').value);
  const noTrade = document.getElementById('extend-notrade')?.checked || false;

  if (!years || !salary || years < 1 || years > 10) {
    showToast('Invalid years or salary', 'error');
    return;
  }

  const r = await post('/contracts/extend-offer', {
    player_id: pid,
    team_id: STATE.userTeamId,
    salary: salary,
    years: years,
    no_trade_clause: noTrade
  });

  if (!r) {
    showToast('Error submitting extension', 'error');
    return;
  }

  // Display result in modal
  const resultDiv = document.getElementById('extend-result');
  if (!resultDiv) return;

  resultDiv.style.display = 'block';

  if (r.accepted) {
    resultDiv.innerHTML = `
      <div style="color:var(--green);font-weight:700;margin-bottom:8px">✓ ACCEPTED</div>
      <div style="font-size:12px;color:var(--text)">${r.reason}</div>
    `;
    showToast('Contract extended successfully', 'success');
    setTimeout(() => {
      document.getElementById('extend-modal').remove();
      closeModal();
      loadRoster();
    }, 1500);
  } else if (r.counter_offer) {
    const counterSal = r.counter_offer.salary;
    const counterYrs = r.counter_offer.years;
    const counterSalStr = fmt$(counterSal);
    resultDiv.innerHTML = `
      <div style="color:var(--accent);font-weight:700;margin-bottom:8px">COUNTERED</div>
      <div style="font-size:12px;color:var(--text);margin-bottom:8px">${r.reason}</div>
      <div style="padding:8px;background:var(--bg-1);border-left:2px solid var(--accent);margin-bottom:8px">
        <div style="font-size:11px;color:var(--text-muted)">Counter offer:</div>
        <div style="font-weight:700">${counterSalStr}/yr for ${counterYrs} years</div>
      </div>
      <div style="display:flex;gap:6px">
        <button class="btn btn-sm btn-primary" style="flex:1" onclick="acceptExtensionCounter(${pid}, ${counterSal}, ${counterYrs}, ${noTrade})">Accept</button>
        <button class="btn btn-sm" style="flex:1" onclick="declineExtension()">Decline</button>
      </div>
    `;
  } else {
    resultDiv.innerHTML = `
      <div style="color:var(--red);font-weight:700;margin-bottom:8px">✗ REJECTED</div>
      <div style="font-size:12px;color:var(--text)">${r.reason || 'Player is not interested in an extension at this time.'}</div>
    `;
  }
}

async function acceptExtensionCounter(pid, salary, years, noTrade) {
  const r = await post('/contracts/extend-offer', {
    player_id: pid,
    team_id: STATE.userTeamId,
    salary: salary,
    years: years,
    no_trade_clause: noTrade
  });

  if (r?.accepted) {
    showToast('Contract extended at counter offer!', 'success');
    setTimeout(() => {
      document.getElementById('extend-modal').remove();
      closeModal();
      loadRoster();
    }, 1000);
  } else {
    showToast('Player did not accept counter offer', 'info');
  }
}

function declineExtension() {
  document.getElementById('extend-modal').remove();
}

function confirmAddToBlock(pid) {
  document.getElementById('action-confirm-panel')?.remove();

  const bar = document.querySelector('.player-action-bar');
  if (!bar) return;

  const panel = document.createElement('div');
  panel.id = 'action-confirm-panel';
  panel.style.cssText = 'background:var(--bg-2);border:1px solid var(--border);border-radius:4px;padding:12px;margin-top:8px';
  panel.innerHTML = `
    <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px">Add this player to the trading block?</div>
    <div style="display:flex;gap:8px">
      <button class="btn btn-sm" style="background:var(--orange);color:white" onclick="execAddToBlock(${pid})">Confirm Add</button>
      <button class="btn btn-sm" onclick="document.getElementById('action-confirm-panel').remove()">Cancel</button>
    </div>
  `;
  bar.after(panel);
}

async function execAddToBlock(pid) {
  const r = await api(`/trading-block/add/${pid}`, { method: 'POST' });
  if (r?.success) {
    showToast('Player added to trading block', 'success');
    closeModal();
    loadTradingBlock();
  } else {
    showToast(r?.error || 'Error adding to trading block', 'error');
  }
}

async function addToTradeAndSwitch(pid) {
  // Add the player to the trade offer
  STATE.tradeOffer = [pid];
  showScreen('trades');
  closeModal();
  showToast('Player added to trade offer. Select a team to trade with.', 'info');
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

  // Pitch Arsenal (for pitchers)
  let arsenalHtml = '';
  if (r.pitch_arsenal && Array.isArray(r.pitch_arsenal)) {
    arsenalHtml = `<div style="background:var(--bg-2);border:1px solid var(--border);padding:10px;margin:12px 0;border-radius:2px">
      <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--accent)">Pitch Arsenal</div>
      <table style="width:100%;font-size:11px;border-collapse:collapse">
        <thead>
          <tr style="border-bottom:1px solid var(--border)">
            <th style="text-align:left;padding:4px;color:var(--text-dim)">Pitch</th>
            <th style="text-align:right;padding:4px;color:var(--text-dim)">Avg Velo</th>
            <th style="text-align:right;padding:4px;color:var(--text-dim)">Top Velo</th>
            <th style="text-align:right;padding:4px;color:var(--text-dim)">Grade</th>
          </tr>
        </thead>
        <tbody>
          ${r.pitch_arsenal.map(p => `
            <tr style="border-bottom:1px solid var(--border-light)">
              <td style="padding:4px;color:var(--text)">${p.label || p.type}</td>
              <td style="text-align:right;padding:4px;color:var(--text)">${p.avg_velocity} mph</td>
              <td style="text-align:right;padding:4px;color:var(--text)">${p.top_velocity} mph</td>
              <td style="text-align:right;padding:4px"><span class="grade ${gradeClass(p.rating)}" style="font-weight:700">${p.rating}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>`;
  }

  // Exit Velocity (for batters)
  let exitVeloHtml = '';
  if (r.exit_velo) {
    const ev = r.exit_velo;
    exitVeloHtml = `<div style="background:var(--bg-2);border:1px solid var(--border);padding:10px;margin:12px 0;border-radius:2px">
      <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--accent)">Exit Velocity</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px">
        <div style="display:flex;justify-content:space-between">
          <span style="color:var(--text-dim)">Avg Exit Velo</span>
          <span style="color:var(--text);font-weight:600">${ev.avg_exit_velo} mph</span>
        </div>
        <div style="display:flex;justify-content:space-between">
          <span style="color:var(--text-dim)">Max Exit Velo</span>
          <span style="color:var(--text);font-weight:600">${ev.max_exit_velo} mph</span>
        </div>
        <div style="display:flex;justify-content:space-between">
          <span style="color:var(--text-dim)">Barrel Rate</span>
          <span style="color:var(--text);font-weight:600">${ev.barrel_rate}%</span>
        </div>
        <div style="display:flex;justify-content:space-between">
          <span style="color:var(--text-dim)">Hard Hit Rate</span>
          <span style="color:var(--text);font-weight:600">${ev.hard_hit_rate}%</span>
        </div>
      </div>
    </div>`;
  }

  // Narrative
  const narrativeHtml = r.narrative
    ? `<div class="scouting-report" style="font-style:italic">"${r.narrative}"</div>`
    : '';

  el.innerHTML = gradesHtml + compHtml + makeupHtml + arsenalHtml + exitVeloHtml + narrativeHtml +
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
let comparisonBasePlayer = null;

async function compareWithPlayer(pid) {
  // Store the base player and open a search modal to select the comparison player
  comparisonBasePlayer = pid;

  // Create a search modal for selecting the second player
  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.style.display = 'flex';
  modal.onclick = (e) => { if (e.target === modal) { modal.remove(); comparisonBasePlayer = null; } };

  modal.innerHTML = `
    <div class="modal-content" style="max-width:400px">
      <button class="modal-close" onclick="this.closest('.modal').remove(); comparisonBasePlayer = null;">&times;</button>
      <div style="font-weight:700;margin-bottom:12px;font-size:16px">Select Player to Compare</div>
      <input type="text" id="compare-search" placeholder="Search player name..." style="width:100%;padding:8px;margin-bottom:12px;background:var(--bg-2);border:1px solid var(--border);color:var(--text);border-radius:2px">
      <div id="compare-results" style="max-height:400px;overflow-y:auto"></div>
    </div>
  `;
  document.body.appendChild(modal);

  // Bind search input
  const searchInput = document.getElementById('compare-search');
  searchInput.addEventListener('input', async (e) => {
    const query = e.target.value.trim();
    if (query.length < 2) {
      document.getElementById('compare-results').innerHTML = '';
      return;
    }

    const results = await api(`/players/search?q=${encodeURIComponent(query)}`);
    const resultsDiv = document.getElementById('compare-results');

    if (!results?.players || results.players.length === 0) {
      resultsDiv.innerHTML = '<div style="padding:12px;color:var(--text-muted)">No players found</div>';
      return;
    }

    let html = '';
    for (const p of results.players.slice(0, 10)) {
      if (p.id !== comparisonBasePlayer) {
        html += `
          <div style="padding:8px;border-bottom:1px solid var(--border);cursor:pointer;hover-effect" onclick="performComparison(${comparisonBasePlayer}, ${p.id}); this.closest('.modal').remove(); comparisonBasePlayer = null;">
            <div style="font-weight:700">${p.first_name} ${p.last_name}</div>
            <div style="font-size:11px;color:var(--text-muted)">${p.position} | Age ${p.age} | ${p.abbreviation || 'FA'}</div>
          </div>
        `;
      }
    }
    resultsDiv.innerHTML = html;
  });

  searchInput.focus();
}

async function performComparison(pid1, pid2) {
  const p1Data = await api('/player/' + pid1);
  const p2Data = await api('/player/' + pid2);

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
        <th class="r">GB</th><th class="r">L10</th><th class="r">Strk</th><th class="r separator">RS</th><th class="r">RA</th><th class="r">Diff</th></tr></thead>
        <tbody>
        ${teams.map((t, idx) => {
          const l10 = t.last_10_wins != null ? `${t.last_10_wins}-${t.last_10_losses}` : '-';
          const strk = t.streak ? t.streak : '-';
          const clinch = t.clinched ? 'x-' : '';
          const playoffClass = idx < 3 ? 'standings-playoff' : '';
          return `<tr class="${t.team_id === STATE.userTeamId ? 'user-team' : ''} ${playoffClass}" style="cursor:pointer;" onclick="viewTeamRoster(${t.team_id})">
          <td class="text-col"><strong>${clinch}${t.abbreviation}</strong> ${t.name}</td>
          <td class="r">${t.wins}</td><td class="r">${t.losses}</td><td class="r">${t.pct.toFixed(3)}</td>
          <td class="r">${t.gb === 0 ? '-' : t.gb.toFixed(1)}</td>
          <td class="r mono" style="font-size:11px">${l10}</td>
          <td class="r mono" style="font-size:11px;color:${strk.startsWith?.('W') ? 'var(--green)' : strk.startsWith?.('L') ? 'var(--red)' : 'inherit'}">${strk}</td>
          <td class="r separator">${t.runs_scored}</td><td class="r">${t.runs_allowed}</td>
          <td class="r ${t.diff > 0 ? 'positive' : t.diff < 0 ? 'negative' : ''}">${t.diff > 0 ? '+' : ''}${t.diff}</td>
        </tr>`;
        }).join('')}
        </tbody>
      </table></div>`;
      makeSortable(`stand-${league}-${div}`);
    }
    el.innerHTML = html;
  }
}

async function viewTeamRoster(teamId) {
  const data = await api(`/team/${teamId}`);
  if (!data) return;
  const t = data.team;
  const roster = data.roster || [];
  const active = roster.filter(p => p.roster_status === 'active');
  const minors = roster.filter(p => p.roster_status && p.roster_status.startsWith('minors'));
  const injured = roster.filter(p => p.is_injured);

  const renderPlayers = (players, label) => {
    if (!players.length) return '';
    let html = `<div style="font-weight:700;font-size:13px;margin:12px 0 4px;">${label} (${players.length})</div>`;
    html += '<table style="font-size:12px;width:100%"><thead><tr><th class="text-col">Name</th><th class="c">Pos</th><th class="r">Age</th><th class="r">OVR</th><th class="r">Salary</th></tr></thead><tbody>';
    players.forEach(p => {
      const salary = p.annual_salary ? `$${(p.annual_salary/1e6).toFixed(1)}M` : '-';
      html += `<tr onclick="showPlayer(${p.id})" style="cursor:pointer;">
        <td class="text-col">${p.first_name} ${p.last_name}</td>
        <td class="c">${p.position}</td>
        <td class="r">${p.age}</td>
        <td class="r">${gradeHtml(p.overall)}</td>
        <td class="r mono">${salary}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    return html;
  };

  const gm = data.gm ? `${data.gm.first_name} ${data.gm.last_name}` : 'None';
  const payroll = data.payroll ? `$${(data.payroll/1e6).toFixed(1)}M` : '-';

  const content = `
    <div style="padding:24px;max-height:80vh;overflow-y:auto;">
      <h2 style="margin-bottom:4px;">${t.city} ${t.name}</h2>
      <div style="font-size:12px;color:var(--text-secondary);margin-bottom:16px;">
        ${t.league} ${t.division} | GM: ${gm} | Payroll: ${payroll} | W${t.wins || 0}-L${t.losses || 0}
      </div>
      ${renderPlayers(active, 'Active Roster')}
      ${renderPlayers(minors, 'Minor Leagues')}
      ${renderPlayers(injured, 'Injured List')}
    </div>`;

  // Show in a modal
  let modal = document.getElementById('team-roster-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'team-roster-modal';
    modal.className = 'modal';
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
    modal.innerHTML = '<div class="modal-content" style="width:650px;"><button class="modal-close" onclick="document.getElementById(\'team-roster-modal\').style.display=\'none\'">&times;</button><div id="team-roster-body"></div></div>';
    document.body.appendChild(modal);
  }
  document.getElementById('team-roster-body').innerHTML = content;
  modal.style.display = 'block';
}

function switchStandingsTab(e, tab) {
  document.querySelectorAll('.tab-btn').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('[id^="standings-tab-"]').forEach(t => t.style.display = 'none');
  e.target.classList.add('active');
  document.getElementById(`standings-tab-${tab}`).style.display = 'block';

  if (tab === 'awards') {
    loadAwards();
  }
}

async function loadAwards() {
  const season = STATE.season || 2026;
  const el = document.getElementById('awards-body');
  el.innerHTML = '<div class="loading"><span class="spinner"></span> Loading awards...</div>';

  const awards = await api(`/awards/${season}`);
  if (!awards) {
    el.innerHTML = '<div class="empty-state">No awards data available</div>';
    return;
  }

  let html = '';

  // MVP
  html += `<div style="margin-bottom:24px">
    <div class="section-title">Most Valuable Player</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <div class="subsection-title">American League</div>
        <div class="table-wrap"><table style="font-size:12px">
          <thead><tr><th class="text-col">Player</th><th class="r">Points</th></tr></thead>
          <tbody>
          ${(awards.mvp_al || []).map((p, i) => `<tr class="${i === 0 ? 'winner' : ''}">
            <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.name}</td>
            <td class="r">${p.points.toFixed(1)}</td>
          </tr>`).join('')}
          </tbody>
        </table></div>
      </div>
      <div>
        <div class="subsection-title">National League</div>
        <div class="table-wrap"><table style="font-size:12px">
          <thead><tr><th class="text-col">Player</th><th class="r">Points</th></tr></thead>
          <tbody>
          ${(awards.mvp_nl || []).map((p, i) => `<tr class="${i === 0 ? 'winner' : ''}">
            <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.name}</td>
            <td class="r">${p.points.toFixed(1)}</td>
          </tr>`).join('')}
          </tbody>
        </table></div>
      </div>
    </div>
  </div>`;

  // Cy Young
  html += `<div style="margin-bottom:24px">
    <div class="section-title">Cy Young Award</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <div class="subsection-title">American League</div>
        <div class="table-wrap"><table style="font-size:12px">
          <thead><tr><th class="text-col">Pitcher</th><th class="r">Points</th></tr></thead>
          <tbody>
          ${(awards.cy_young_al || []).map((p, i) => `<tr class="${i === 0 ? 'winner' : ''}">
            <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.name}</td>
            <td class="r">${p.points.toFixed(1)}</td>
          </tr>`).join('')}
          </tbody>
        </table></div>
      </div>
      <div>
        <div class="subsection-title">National League</div>
        <div class="table-wrap"><table style="font-size:12px">
          <thead><tr><th class="text-col">Pitcher</th><th class="r">Points</th></tr></thead>
          <tbody>
          ${(awards.cy_young_nl || []).map((p, i) => `<tr class="${i === 0 ? 'winner' : ''}">
            <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.name}</td>
            <td class="r">${p.points.toFixed(1)}</td>
          </tr>`).join('')}
          </tbody>
        </table></div>
      </div>
    </div>
  </div>`;

  // ROY
  html += `<div style="margin-bottom:24px">
    <div class="section-title">Rookie of the Year</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <div class="subsection-title">American League</div>
        <div class="table-wrap"><table style="font-size:12px">
          <thead><tr><th class="text-col">Rookie</th><th class="r">Points</th></tr></thead>
          <tbody>
          ${(awards.roy_al || []).map((p, i) => `<tr class="${i === 0 ? 'winner' : ''}">
            <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.name}</td>
            <td class="r">${p.points.toFixed(1)}</td>
          </tr>`).join('')}
          </tbody>
        </table></div>
      </div>
      <div>
        <div class="subsection-title">National League</div>
        <div class="table-wrap"><table style="font-size:12px">
          <thead><tr><th class="text-col">Rookie</th><th class="r">Points</th></tr></thead>
          <tbody>
          ${(awards.roy_nl || []).map((p, i) => `<tr class="${i === 0 ? 'winner' : ''}">
            <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.name}</td>
            <td class="r">${p.points.toFixed(1)}</td>
          </tr>`).join('')}
          </tbody>
        </table></div>
      </div>
    </div>
  </div>`;

  // Gold Glove
  html += `<div style="margin-bottom:24px">
    <div class="section-title">Gold Glove Awards</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
      <div>
        <div class="subsection-title">American League</div>
        <div class="table-wrap"><table style="font-size:12px">
          <thead><tr><th class="text-col">Position</th><th class="text-col">Player</th></tr></thead>
          <tbody>
          ${Object.entries(awards.gold_glove?.AL || {}).map(([pos, p]) => `<tr>
            <td class="text-col" style="font-weight:600">${pos}</td>
            <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.name}</td>
          </tr>`).join('')}
          </tbody>
        </table></div>
      </div>
      <div>
        <div class="subsection-title">National League</div>
        <div class="table-wrap"><table style="font-size:12px">
          <thead><tr><th class="text-col">Position</th><th class="text-col">Player</th></tr></thead>
          <tbody>
          ${Object.entries(awards.gold_glove?.NL || {}).map(([pos, p]) => `<tr>
            <td class="text-col" style="font-weight:600">${pos}</td>
            <td class="text-col clickable" onclick="showPlayer(${p.player_id})">${p.name}</td>
          </tr>`).join('')}
          </tbody>
        </table></div>
      </div>
    </div>
  </div>`;

  el.innerHTML = html;
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
  const [fin, team, broadcast, stadium] = await Promise.all([
    api('/finances/' + STATE.userTeamId + '/details'),
    api('/finances/' + STATE.userTeamId),
    api('/finances/' + STATE.userTeamId + '/broadcast-status').catch(() => null),
    api('/finances/' + STATE.userTeamId + '/stadium').catch(() => null),
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
      ${fin.luxury_tax > 0 ? `<div class="fin-line" style="color:var(--red)"><span>Luxury Tax (CBT)</span><span>${fmt$(fin.luxury_tax)}</span></div>` : ''}
      <div class="fin-line total"><span>Total Expenses</span><span class="negative">${fmt$(fin.total_expenses)}</span></div>
    </div>
    <div class="card"><h3>Bottom Line</h3>
      <div class="fin-line total"><span>Profit/Loss</span><span class="${fin.profit >= 0 ? 'positive' : 'negative'}">${fmt$(fin.profit)}</span></div>
      <div class="fin-line"><span>Cash on Hand</span><span>${fmt$(team?.cash)}</span></div>
      <div class="fin-line"><span>Franchise Value</span><span>${fmt$(team?.franchise_value)}</span></div>
      <div class="fin-line"><span>Avg Attendance</span><span>${(fin.attendance_avg || 0).toLocaleString()}</span></div>
      <div style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">
        <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Luxury Tax Thresholds</div>
        <div class="fin-line" style="font-size:11px"><span>1st Threshold (20%)</span><span>$237M</span></div>
        <div class="fin-line" style="font-size:11px"><span>2nd Threshold (32%)</span><span>$257M</span></div>
        <div class="fin-line" style="font-size:11px"><span>3rd Threshold (50%+)</span><span>$277M</span></div>
        <div class="fin-line" style="font-size:11px;font-weight:700"><span>Your Payroll</span><span class="${fin.payroll > 237000000 ? 'negative' : ''}">${fmt$(fin.payroll)}</span></div>
      </div>
    </div>
    <div class="card"><h3>Budget Allocations</h3>
      <div class="slider-group">
        <label class="slider-label">Farm System</label>
        <input type="range" min="0" max="50000000" step="500000" value="${team?.farm_budget || 0}" oninput="updateBudgetDisplay(event)" onchange="updateBudget('farm', this.value)">
        <span class="slider-value">${fmt$(team?.farm_budget || 0)}</span>
      </div>
      <div class="slider-group">
        <label class="slider-label">Medical Staff</label>
        <input type="range" min="0" max="50000000" step="500000" value="${team?.medical_budget || 0}" oninput="updateBudgetDisplay(event)" onchange="updateBudget('medical', this.value)">
        <span class="slider-value">${fmt$(team?.medical_budget || 0)}</span>
      </div>
      <div class="slider-group">
        <label class="slider-label">Scouting</label>
        <input type="range" min="0" max="50000000" step="500000" value="${team?.scouting_budget || 0}" oninput="updateBudgetDisplay(event)" onchange="updateBudget('scouting', this.value)">
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
    <div class="card"><h3>Broadcast Rights</h3>
      ${broadcast ? `
        <div class="fin-line"><span>Current Deal</span><span>${broadcast.current_deal_name}</span></div>
        <div class="fin-line"><span>Annual Value</span><span class="positive">${fmt$(broadcast.current_deal_value)}</span></div>
        <div class="fin-line"><span>Years Remaining</span><span>${broadcast.years_remaining}</span></div>
        <div style="margin-top:12px;border-top:1px solid var(--border);padding-top:8px">
          <div class="subsection-title">Available Deals</div>
          ${broadcast.available_deals.map(deal => `
            <div style="padding:6px 0;font-size:11px;display:flex;justify-content:space-between">
              <span>${deal.name} (${deal.years}yr) ${fmt$(deal.estimated_value)}</span>
              <button class="btn btn-sm" onclick="negotiateBroadcastDeal('${deal.type}')" style="padding:2px 6px;font-size:10px">${deal.type === broadcast.current_deal_type ? 'Current' : 'Negotiate'}</button>
            </div>
          `).join('')}
        </div>
      ` : '<div style="color:var(--text-dim)">Loading broadcast data...</div>'}
    </div>
    <div class="card"><h3>Stadium Management</h3>
      ${stadium ? `
        <div class="fin-line"><span>${stadium.stadium_name}</span><span>${stadium.built_year}</span></div>
        <div class="fin-line"><span>Capacity</span><span>${stadium.capacity.toLocaleString()}</span></div>
        <div class="fin-line"><span>Condition</span><span>${stadium.condition}/100</span></div>
        ${stadium.annual_upgrade_revenue > 0 ? `<div class="fin-line"><span>Annual Upgrade Revenue</span><span class="positive">${fmt$(stadium.annual_upgrade_revenue)}</span></div>` : ''}
        <div style="margin-top:12px;border-top:1px solid var(--border);padding-top:8px">
          <div class="subsection-title">Available Upgrades</div>
          ${stadium.available_upgrades.map(upgrade => `
            <div style="padding:6px 0;font-size:10px;display:flex;justify-content:space-between;align-items:center">
              <div>
                <div style="font-weight:600">${upgrade.name}</div>
                <div style="color:var(--text-dim);font-size:9px">${fmt$(upgrade.cost)} | +${fmt$(upgrade.annual_revenue)}/yr</div>
              </div>
              <button class="btn btn-sm" onclick="purchaseStadiumUpgrade('${upgrade.key}')" style="padding:2px 6px;font-size:10px" ${upgrade.purchased ? 'disabled' : ''}>${upgrade.purchased ? 'Owned' : 'Buy'}</button>
            </div>
          `).join('')}
        </div>
      ` : '<div style="color:var(--text-dim)">Loading stadium data...</div>'}
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
// BROADCAST RIGHTS & STADIUM MANAGEMENT
// ============================================================
async function negotiateBroadcastDeal(dealType) {
  if (!STATE.userTeamId) return;
  try {
    const result = await post(`/finances/${STATE.userTeamId}/broadcast-deal`, {
      deal_type: dealType
    });
    if (result.success) {
      showToast(result.message || 'Deal negotiated successfully', 'success');
      loadFinances();
    } else {
      showToast(result.error || 'Failed to negotiate deal', 'error');
    }
  } catch (err) {
    showToast('Error negotiating broadcast deal', 'error');
  }
}

async function purchaseStadiumUpgrade(upgradeKey) {
  if (!STATE.userTeamId) return;
  try {
    const result = await post(`/finances/${STATE.userTeamId}/stadium-upgrade`, {
      upgrade_key: upgradeKey
    });
    if (result.success) {
      showToast(result.message || 'Upgrade purchased', 'success');
      loadFinances();
    } else {
      showToast(result.error || 'Failed to purchase upgrade', 'error');
    }
  } catch (err) {
    showToast('Error purchasing stadium upgrade', 'error');
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
        <td><button class="btn btn-sm btn-primary" onclick="openFANegotiationModal(${p.id})">Negotiate</button></td>
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

async function openFANegotiationModal(pid) {
  if (!STATE.userTeamId) return;

  // Get player details
  const playerData = await api('/player/' + pid);
  if (!playerData?.player) {
    showToast('Could not load player data', 'error');
    return;
  }

  const p = playerData.player;
  const askingSalary = p.asking_salary || 5000000;
  const askingYears = p.asking_years || 3;
  const askingStr = fmt$(askingSalary);

  const modal = document.createElement('div');
  modal.className = 'modal';
  modal.style.display = 'flex';
  modal.id = 'fa-negotiation-modal';
  modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

  modal.innerHTML = `
    <div class="modal-content" style="max-width:450px">
      <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
      <div style="font-weight:700;margin-bottom:16px;font-size:16px">Negotiate with ${p.first_name} ${p.last_name}</div>

      <div style="padding:12px;background:var(--bg-2);border-radius:2px;margin-bottom:16px">
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">ASKING PRICE</div>
        <div style="display:flex;justify-content:space-between;font-weight:700">
          <span>${askingStr}/yr</span>
          <span>${askingYears} years</span>
        </div>
      </div>

      <div style="margin-bottom:12px">
        <label style="font-size:12px;color:var(--text-muted);text-transform:uppercase">Annual Salary</label>
        <div style="display:flex;gap:8px;margin-top:4px">
          <input type="range" id="fa-salary-slider" min="500000" max="20000000" step="100000" value="${askingSalary}" style="flex:1;cursor:pointer" onchange="updateFASalaryDisplay()">
          <div style="display:flex;flex-direction:column;justify-content:center;align-items:flex-end;min-width:120px">
            <input type="number" id="fa-salary-input" min="500000" max="20000000" step="100000" value="${askingSalary}" style="width:100%;padding:6px;background:var(--bg-2);border:1px solid var(--border);color:var(--text);border-radius:2px" onchange="updateFASalarySlider()">
            <div id="fa-salary-display" style="font-size:11px;color:var(--accent);font-weight:600;margin-top:4px">${fmt$(askingSalary)}</div>
          </div>
        </div>
        <div style="font-size:10px;color:var(--text-muted);margin-top:4px" id="fa-salary-pct">100% of asking</div>
      </div>

      <div style="margin-bottom:16px">
        <label style="font-size:12px;color:var(--text-muted);text-transform:uppercase">Years</label>
        <select id="fa-years" style="width:100%;padding:8px;margin-top:4px;background:var(--bg-2);border:1px solid var(--border);color:var(--text);border-radius:2px">
          ${[1,2,3,4,5,6,7,8,9,10].map(y => `<option value="${y}" ${y === askingYears ? 'selected' : ''}>${y}</option>`).join('')}
        </select>
      </div>

      <div style="display:flex;gap:8px">
        <button class="btn btn-primary" style="flex:1" onclick="submitFANegotiation(${pid})">Make Offer</button>
        <button class="btn btn-secondary" style="flex:1" onclick="this.closest('.modal').remove()">Cancel</button>
      </div>

      <div id="fa-negotiation-result" style="margin-top:16px;padding:12px;background:var(--bg-2);border-radius:2px;display:none"></div>
    </div>
  `;
  document.body.appendChild(modal);

  // Store asking price for reference
  window._faAskingSalary = askingSalary;
}

function updateFASalaryDisplay() {
  const slider = document.getElementById('fa-salary-slider');
  const input = document.getElementById('fa-salary-input');
  const pctDiv = document.getElementById('fa-salary-pct');
  const display = document.getElementById('fa-salary-display');

  input.value = slider.value;

  const pct = (slider.value / window._faAskingSalary * 100).toFixed(0);
  pctDiv.textContent = pct + '% of asking';
  if (display) display.textContent = fmt$(parseInt(slider.value));
}

function updateFASalarySlider() {
  const slider = document.getElementById('fa-salary-slider');
  const input = document.getElementById('fa-salary-input');
  const pctDiv = document.getElementById('fa-salary-pct');
  const display = document.getElementById('fa-salary-display');

  slider.value = input.value;

  const pct = (input.value / window._faAskingSalary * 100).toFixed(0);
  pctDiv.textContent = pct + '% of asking';
  if (display) display.textContent = fmt$(parseInt(input.value));
}

async function submitFANegotiation(pid) {
  const salary = parseInt(document.getElementById('fa-salary-input').value);
  const years = parseInt(document.getElementById('fa-years').value);

  if (isNaN(salary) || isNaN(years) || salary < 500000 || years < 1) {
    showToast('Invalid contract terms', 'error');
    return;
  }

  const result = await post('/free-agents/negotiate', {
    player_id: pid,
    team_id: STATE.userTeamId,
    salary: salary,
    years: years
  });

  if (!result) {
    showToast('Error negotiating with player', 'error');
    return;
  }

  // Display result
  const resultDiv = document.getElementById('fa-negotiation-result');
  resultDiv.style.display = 'block';

  if (result.accepted) {
    resultDiv.innerHTML = `
      <div style="color:var(--green);font-weight:700;margin-bottom:8px">✓ ACCEPTED</div>
      <div style="font-size:12px;color:var(--text)">${result.reason}</div>
    `;
    showToast('Player signed!', 'success');
    setTimeout(() => {
      document.getElementById('fa-negotiation-modal').remove();
      loadFA();
    }, 1500);
  } else if (result.counter_offer) {
    const counterSal = result.counter_offer.salary;
    const counterYrs = result.counter_offer.years;
    const counterSalStr = fmt$(counterSal);
    resultDiv.innerHTML = `
      <div style="color:var(--accent);font-weight:700;margin-bottom:8px">✗ COUNTERED</div>
      <div style="font-size:12px;color:var(--text);margin-bottom:8px">${result.reason}</div>
      <div style="padding:8px;background:var(--bg-1);border-left:2px solid var(--accent);margin-bottom:8px">
        <div style="font-size:11px;color:var(--text-muted)">Counter offer:</div>
        <div style="font-weight:700">${counterSalStr}/yr for ${counterYrs} years</div>
      </div>
      <div style="display:flex;gap:6px">
        <button class="btn btn-sm btn-primary" style="flex:1" onclick="acceptFACounter(${pid}, ${counterSal}, ${counterYrs})">Accept</button>
        <button class="btn btn-sm" style="flex:1" onclick="declineAndClose()">Decline</button>
      </div>
    `;
  } else {
    resultDiv.innerHTML = `
      <div style="color:var(--red);font-weight:700;margin-bottom:8px">✗ REJECTED</div>
      <div style="font-size:12px;color:var(--text)">${result.reason || 'Player declined the offer.'}</div>
    `;
  }
}

async function acceptFACounter(pid, salary, years) {
  const result = await post('/free-agents/sign', {
    player_id: pid,
    team_id: STATE.userTeamId,
    salary: salary,
    years: years
  });

  showToast('Player signed at counter offer!', 'success');
  setTimeout(() => {
    document.getElementById('fa-negotiation-modal').remove();
    loadFA();
  }, 1000);
}

function declineAndClose() {
  document.getElementById('fa-negotiation-modal').remove();
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
  const sidebarBadge = document.getElementById('sidebar-msg-count');
  if (unreadCount > 0) {
    if (badge) { badge.textContent = unreadCount; badge.style.display = 'block'; }
    if (sidebarBadge) { sidebarBadge.textContent = unreadCount; sidebarBadge.style.display = 'flex'; }
  } else {
    if (badge) badge.style.display = 'none';
    if (sidebarBadge) sidebarBadge.style.display = 'none';
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
  // Don't handle shortcuts when typing in inputs
  const tag = e.target.tagName;
  const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable;

  if (e.key === 'Escape') closeModal();
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    openGlobalSearch();
    return;
  }

  if (isInput) return;

  // Sim shortcuts
  if (e.key === ' ' || (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey)) {
    e.preventDefault();
    simDays(1);
  }
  if (e.shiftKey && e.key === 'Enter') {
    e.preventDefault();
    simDays(7);
  }

  // Number keys 1-9 for screen navigation
  const screenMap = ['calendar','roster','lineup','depthchart','standings','trades','freeagents','draft','leaders'];
  const num = parseInt(e.key);
  if (num >= 1 && num <= 9 && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const screen = screenMap[num - 1];
    if (screen) showScreen(screen);
  }

  // ? key to toggle keyboard help
  if (e.key === '?') {
    const help = document.getElementById('keyboard-help');
    if (help) help.style.display = help.style.display === 'none' ? 'block' : 'none';
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

  // Create a comprehensive table-based depth chart
  let html = `
    <div style="margin-bottom: 24px;">
      <h4 style="margin-top: 0; margin-bottom: 12px;">Position Players</h4>
      <div class="table-wrap">
        <table id="depth-pos-table" style="font-size: 13px;">
          <thead><tr>
            <th class="text-col">Position</th>
            <th class="text-col">Starter</th>
            <th class="r" style="width: 80px;">Rating</th>
            <th class="text-col">Backup 1</th>
            <th class="r" style="width: 80px;">Rating</th>
            <th class="text-col">Backup 2</th>
            <th class="r" style="width: 80px;">Rating</th>
          </tr></thead>
          <tbody>`;

  const positions = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH'];
  positions.forEach(pos => {
    const players = data[pos] || [];
    const starter = players.find(p => p.status === 'starter');
    const backups = players.filter(p => p.status !== 'starter');

    html += `<tr>
      <td class="text-col"><strong>${pos}</strong></td>
      <td class="text-col" onclick="showPlayer(${starter?.player_id})" style="cursor:pointer;">${starter ? starter.name : '—'}</td>
      <td class="r">${starter ? `<span class="grade ${gradeClass(starter.overall)}">${toGrade(starter.overall)}</span> <span class="mono" style="font-size:10px">(${starter.overall})</span>` : '—'}</td>
      <td class="text-col" onclick="${backups[0] ? `showPlayer(${backups[0].player_id})` : ''}" style="${backups[0] ? 'cursor:pointer;' : ''}">${backups[0] ? backups[0].name : '—'}</td>
      <td class="r">${backups[0] ? `<span class="grade ${gradeClass(backups[0].overall)}">${toGrade(backups[0].overall)}</span> <span class="mono" style="font-size:10px">(${backups[0].overall})</span>` : '—'}</td>
      <td class="text-col" onclick="${backups[1] ? `showPlayer(${backups[1].player_id})` : ''}" style="${backups[1] ? 'cursor:pointer;' : ''}">${backups[1] ? backups[1].name : '—'}</td>
      <td class="r">${backups[1] ? `<span class="grade ${gradeClass(backups[1].overall)}">${toGrade(backups[1].overall)}</span> <span class="mono" style="font-size:10px">(${backups[1].overall})</span>` : '—'}</td>
    </tr>`;
  });
  html += '</tbody></table></div></div>';

  // Pitching staff
  html += `
    <div>
      <h4 style="margin-top: 24px; margin-bottom: 12px;">Pitching Staff</h4>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;">
        <div>
          <h5 style="margin-top: 0;">Starting Rotation</h5>
          <div class="table-wrap">
            <table id="depth-sp-table" style="font-size: 13px;">
              <thead><tr>
                <th class="text-col" style="width: 40px;">SP#</th>
                <th class="text-col">Pitcher</th>
                <th class="r" style="width: 80px;">Rating</th>
              </tr></thead>
              <tbody>`;

  const starters = (data['SP'] || []).slice(0, 5);
  starters.forEach((p, i) => {
    html += `<tr>
      <td class="text-col" style="font-weight:bold;">${i+1}</td>
      <td class="text-col" onclick="showPlayer(${p.player_id})" style="cursor:pointer;">${p.name}</td>
      <td class="r"><span class="grade ${gradeClass(p.overall)}">${toGrade(p.overall)}</span> <span class="mono" style="font-size:10px">(${p.overall})</span></td>
    </tr>`;
  });
  html += '</tbody></table></div></div>';

  html += `
        <div>
          <h5 style="margin-top: 0;">Relief Corps</h5>
          <div class="table-wrap">
            <table id="depth-rp-table" style="font-size: 13px;">
              <thead><tr>
                <th class="text-col">Role</th>
                <th class="text-col">Pitcher</th>
                <th class="r" style="width: 80px;">Rating</th>
              </tr></thead>
              <tbody>`;

  // Categorize relievers
  const relieverRoles = [
    { label: 'CL', find: (name) => name && (name.includes('Closer') || name.includes('Save')) },
    { label: 'SU', find: (name) => name && (name.includes('Setup') || name.includes('Relief')) },
    { label: 'MR', find: (name) => name && (name.includes('Middle') || name.includes('Long')) },
    { label: 'LR', find: (name) => true }  // Catch-all
  ];

  const relievers = (data['RP'] || []).slice(0, 8);
  relievers.forEach((p, i) => {
    const role = i === 0 ? 'CL' : i === 1 ? 'SU' : i < 4 ? 'MR' : 'LR';
    html += `<tr>
      <td class="text-col"><strong>${role}</strong></td>
      <td class="text-col" onclick="showPlayer(${p.player_id})" style="cursor:pointer;">${p.name}</td>
      <td class="r"><span class="grade ${gradeClass(p.overall)}">${toGrade(p.overall)}</span> <span class="mono" style="font-size:10px">(${p.overall})</span></td>
    </tr>`;
  });
  html += '</tbody></table></div></div></div></div>';

  document.getElementById('depthchart-body').innerHTML = html;
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
  loadSavesList();
}

async function loadSavesList() {
  const el = document.getElementById('saves-list');
  try {
    const saves = await get('/saves');
    if (!saves || saves.length === 0) {
      el.innerHTML = '<div style="color:var(--text-dim);">No saves yet</div>';
      return;
    }
    let html = '';
    saves.forEach(s => {
      const dateStr = s.game_date || '?';
      const phase = s.phase || '';
      const size = s.file_size_mb || '?';
      html += `<div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--border-light);">
        <div>
          <span style="font-weight:600;">${s.name}</span>
          <span style="color:var(--text-dim); margin-left:8px;">${dateStr} (${phase}) ${size}MB</span>
        </div>
        <div style="display:flex; gap:4px;">
          <button class="btn btn-sm" onclick="loadGame('${s.name}')" style="font-size:11px;">Load</button>
          <button class="btn btn-sm" onclick="deleteSave('${s.name}')" style="font-size:11px; color:var(--red);">Del</button>
        </div>
      </div>`;
    });
    el.innerHTML = html;
  } catch (e) {
    el.innerHTML = '<div style="color:var(--red);">Error loading saves</div>';
  }
}

async function saveGame() {
  const name = document.getElementById('save-name-input').value.trim();
  if (!name) { showToast('Enter a save name', 'error'); return; }
  const r = await post('/saves/save', { name });
  if (r && r.saved) {
    showToast(`Game saved: ${r.saved}`, 'success');
    document.getElementById('save-name-input').value = '';
    loadSavesList();
  }
}

async function loadGame(name) {
  if (!confirm(`Load save "${name}"? Current progress will be lost if not saved.`)) return;
  const r = await post('/saves/load', { name });
  if (r && r.loaded) {
    showToast(`Loaded: ${r.loaded}`, 'success');
    await loadState();
    closeSettingsModal();
    showScreen('calendar');
  }
}

async function deleteSave(name) {
  if (!confirm(`Delete save "${name}"?`)) return;
  await fetch(`/saves/${name}`, { method: 'DELETE' });
  showToast(`Deleted: ${name}`, 'info');
  loadSavesList();
}

function closeSettingsModal() {
  document.getElementById('settings-modal').style.display = 'none';
}

async function migrateDatabase() {
  const statusEl = document.getElementById('db-status');
  const btn = document.getElementById('migrate-btn');
  statusEl.style.display = 'block';
  statusEl.textContent = 'Running schema migrations...';
  btn.disabled = true;

  try {
    const resp = await fetch('/admin/migrate', { method: 'POST' });
    const data = await resp.json();
    if (data.success) {
      statusEl.textContent = 'Migrations complete: ' + (data.changes || []).join(', ');
      showToast('Schema updated successfully!', 'success');
    } else {
      statusEl.textContent = 'Migration error: ' + data.error;
      showToast('Migration failed: ' + data.error, 'error');
    }
  } catch (e) {
    statusEl.textContent = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
  }
}

async function executeReseed(forceFetch) {
  const endpoint = forceFetch ? '/admin/refetch' : '/admin/reseed';
  const statusEl = document.getElementById('db-status');
  const reseedBtn = document.getElementById('reseed-btn');
  const refetchBtn = document.getElementById('refetch-btn');

  // Hide confirmation panels
  document.getElementById('reseed-confirm').style.display = 'none';
  document.getElementById('refetch-confirm').style.display = 'none';

  statusEl.style.display = 'block';
  statusEl.textContent = 'Working... this takes 3-5 minutes if fetching from the MLB API...';
  reseedBtn.disabled = true;
  refetchBtn.disabled = true;

  try {
    const resp = await fetch(endpoint, { method: 'POST' });
    const data = await resp.json();

    if (data.success) {
      statusEl.textContent = data.steps.join(' | ');
      showToast('Database reseeded! Reloading...', 'success');
      setTimeout(() => window.location.reload(), 2000);
    } else {
      statusEl.textContent = 'Error: ' + data.error;
      showToast('Reseed failed: ' + data.error, 'error');
    }
  } catch (e) {
    statusEl.textContent = 'Error: ' + e.message;
    showToast('Reseed failed: ' + e.message, 'error');
  } finally {
    reseedBtn.disabled = false;
    refetchBtn.disabled = false;
  }
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
  } else if (sort === 'overall') {
    // Calculate overall rating as average of all ceiling ratings
    filtered.sort((a, b) => {
      const avgA = (a.contact_ceiling + a.power_ceiling + a.speed_ceiling + a.fielding_ceiling + a.arm_ceiling + a.stuff_ceiling + a.control_ceiling) / 7;
      const avgB = (b.contact_ceiling + b.power_ceiling + b.speed_ceiling + b.fielding_ceiling + b.arm_ceiling + b.stuff_ceiling + b.control_ceiling) / 7;
      return avgB - avgA;
    });
  } else if (sort === 'stuff') {
    // Pitchers by stuff ceiling to top
    filtered.sort((a, b) => {
      const isPitcherA = a.position === 'SP' || a.position === 'RP';
      const isPitcherB = b.position === 'SP' || b.position === 'RP';
      if (isPitcherA && !isPitcherB) return -1;
      if (!isPitcherA && isPitcherB) return 1;
      return b.stuff_ceiling - a.stuff_ceiling;
    });
  } else if (sort === 'contact') {
    // Hitters by contact ceiling to top
    filtered.sort((a, b) => {
      const isPitcherA = a.position === 'SP' || a.position === 'RP';
      const isPitcherB = b.position === 'SP' || b.position === 'RP';
      if (!isPitcherA && isPitcherB) return -1;
      if (isPitcherA && !isPitcherB) return 1;
      return b.contact_ceiling - a.contact_ceiling;
    });
  } else if (sort === 'power') {
    // Hitters by power ceiling to top
    filtered.sort((a, b) => {
      const isPitcherA = a.position === 'SP' || a.position === 'RP';
      const isPitcherB = b.position === 'SP' || b.position === 'RP';
      if (!isPitcherA && isPitcherB) return -1;
      if (isPitcherA && !isPitcherB) return 1;
      return b.power_ceiling - a.power_ceiling;
    });
  } else if (sort === 'speed') {
    filtered.sort((a, b) => b.speed_ceiling - a.speed_ceiling);
  } else if (sort === 'ceiling') {
    // Max of all ceiling values
    filtered.sort((a, b) => {
      const maxA = Math.max(a.contact_ceiling, a.power_ceiling, a.speed_ceiling, a.fielding_ceiling, a.arm_ceiling, a.stuff_ceiling, a.control_ceiling);
      const maxB = Math.max(b.contact_ceiling, b.power_ceiling, b.speed_ceiling, b.fielding_ceiling, b.arm_ceiling, b.stuff_ceiling, b.control_ceiling);
      return maxB - maxA;
    });
  } else if (sort === 'signability') {
    // Signability: combination of age (younger = easier) and overall ceiling
    filtered.sort((a, b) => {
      const avgA = (a.contact_ceiling + a.power_ceiling + a.speed_ceiling + a.fielding_ceiling + a.arm_ceiling + a.stuff_ceiling + a.control_ceiling) / 7;
      const avgB = (b.contact_ceiling + b.power_ceiling + b.speed_ceiling + b.fielding_ceiling + b.arm_ceiling + b.stuff_ceiling + b.control_ceiling) / 7;
      const scoreA = avgA + (25 - a.age) * 0.5;
      const scoreB = avgB + (25 - b.age) * 0.5;
      return scoreB - scoreA;
    });
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
    const avgOverall = (p.contact_ceiling + p.power_ceiling + p.speed_ceiling + p.fielding_ceiling + p.arm_ceiling + p.stuff_ceiling + p.control_ceiling) / 7;

    // Get top ratings to display as badges
    let topRatings = [];
    if (isPitcher) {
      topRatings = [
        { label: 'STF', value: p.stuff_ceiling },
        { label: 'CTL', value: p.control_ceiling }
      ];
    } else {
      // Hitters - get top 3 tools
      const ratings = [
        { label: 'CON', value: p.contact_ceiling },
        { label: 'POW', value: p.power_ceiling },
        { label: 'SPD', value: p.speed_ceiling },
        { label: 'FLD', value: p.fielding_ceiling },
        { label: 'ARM', value: p.arm_ceiling }
      ];
      topRatings = ratings.sort((a, b) => b.value - a.value).slice(0, 3);
    }

    const badgesHtml = topRatings.map(r => `<span style="display: inline-block; margin-right: 4px; padding: 2px 6px; background: var(--bg-3); border-radius: 2px; font-size: 10px; color: var(--accent); font-weight: 600;">${r.label} ${r.value}</span>`).join('');

    html += `
      <div class="draft-prospect-item" onclick="selectProspect(${p.id})" style="padding: 10px 12px; border-bottom: 1px solid var(--border); cursor: pointer; transition: background 0.2s; ${_selectedProspect?.id === p.id ? 'background: var(--bg-selected);' : 'background: var(--bg-1);'} hover {background: var(--bg-3);}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
          <div style="flex: 1;">
            <div style="font-weight: 600;">${p.first_name} ${p.last_name}</div>
            <div style="font-size: 10px; color: var(--text-dim); margin: 4px 0;">
              <span class="badge">${p.position}</span>
              Age ${p.age} | Rank ${p.overall_rank}
            </div>
            <div style="font-size: 11px; margin-top: 4px;">
              ${badgesHtml}
            </div>
          </div>
          <div style="text-align: right; margin-left: 8px;">
            <div style="font-size: 14px; font-weight: 700; color: var(--accent);">${Math.round(avgOverall)}</div>
            <div style="font-size: 10px; color: var(--text-dim);">OVR</div>
          </div>
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

  html += `
    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);">
      <button class="btn btn-secondary" style="width: 100%; margin-bottom: 12px; font-size: 12px;" onclick="genProspectScout(${_selectedProspect.id})">Generate Scout Report</button>
  `;

  if (_selectedProspect.scouting_report) {
    html += `
      <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); font-size: 11px; line-height: 1.6;">
        <div style="color: var(--text-muted); margin-bottom: 4px;">Quick Notes</div>
        <div style="font-style: italic; color: var(--text-dim);">${_selectedProspect.scouting_report}</div>
      </div>
    `;
  }

  html += '</div><div id="prospect-scout-report" style="margin-top: 12px;"></div>';
  html += '</div>';
  preview.innerHTML = html;

  // Show draft button
  document.getElementById('draft-btn').style.display = 'block';

  // Update list selection
  filterDraftProspects();
}

async function genProspectScout(prospectId) {
  const el = document.getElementById('prospect-scout-report');
  el.innerHTML = '<span class="spinner" style="display: inline-block; width: 12px; height: 12px; border: 2px solid var(--accent); border-radius: 50%; border-right-color: transparent; animation: spin 0.6s linear infinite;"></span> Generating scout report...';

  const r = await api(`/draft/prospect/${prospectId}/scouting-report`);
  if (!r || r.error) {
    el.innerHTML = '<div style="color: var(--red); font-size: 12px;">Scout report unavailable.</div>';
    return;
  }

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
  gradesHtml += '<div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;padding-bottom:4px;border-bottom:1px solid var(--accent)">Floor / Ceiling Grades (20-80)</div>';
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

  // Pitch Arsenal (for pitchers)
  let arsenalHtml = '';
  if (r.pitch_arsenal && Array.isArray(r.pitch_arsenal)) {
    arsenalHtml = `<div style="background:var(--bg-2);border:1px solid var(--border);padding:10px;margin:12px 0;border-radius:2px">
      <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--accent)">Pitch Arsenal</div>
      <table style="width:100%;font-size:11px;border-collapse:collapse">
        <thead>
          <tr style="border-bottom:1px solid var(--border)">
            <th style="text-align:left;padding:4px;color:var(--text-dim)">Pitch</th>
            <th style="text-align:right;padding:4px;color:var(--text-dim)">Avg Velo</th>
            <th style="text-align:right;padding:4px;color:var(--text-dim)">Top Velo</th>
            <th style="text-align:right;padding:4px;color:var(--text-dim)">Grade</th>
          </tr>
        </thead>
        <tbody>
          ${r.pitch_arsenal.map(p => `
            <tr style="border-bottom:1px solid var(--border-light)">
              <td style="padding:4px;color:var(--text)">${p.label || p.type}</td>
              <td style="text-align:right;padding:4px;color:var(--text)">${p.avg_velocity} mph</td>
              <td style="text-align:right;padding:4px;color:var(--text)">${p.top_velocity} mph</td>
              <td style="text-align:right;padding:4px"><span class="grade ${gradeClass(p.rating)}" style="font-weight:700">${p.rating}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>`;
  }

  // Exit Velocity (for batters)
  let exitVeloHtml = '';
  if (r.exit_velo) {
    const ev = r.exit_velo;
    exitVeloHtml = `<div style="background:var(--bg-2);border:1px solid var(--border);padding:10px;margin:12px 0;border-radius:2px">
      <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--accent)">Exit Velocity Projection</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px">
        <div style="display:flex;justify-content:space-between">
          <span style="color:var(--text-dim)">Avg Exit Velo</span>
          <span style="color:var(--text);font-weight:600">${ev.avg_exit_velo} mph</span>
        </div>
        <div style="display:flex;justify-content:space-between">
          <span style="color:var(--text-dim)">Max Exit Velo</span>
          <span style="color:var(--text);font-weight:600">${ev.max_exit_velo} mph</span>
        </div>
        <div style="display:flex;justify-content:space-between">
          <span style="color:var(--text-dim)">Barrel Rate</span>
          <span style="color:var(--text);font-weight:600">${ev.barrel_rate}%</span>
        </div>
        <div style="display:flex;justify-content:space-between">
          <span style="color:var(--text-dim)">Hard Hit Rate</span>
          <span style="color:var(--text);font-weight:600">${ev.hard_hit_rate}%</span>
        </div>
      </div>
    </div>`;
  }

  // Narrative
  const narrativeHtml = r.narrative
    ? `<div class="scouting-report" style="font-style:italic;margin:12px 0;padding:10px;background:var(--bg-2);border-left:3px solid var(--accent)">"${r.narrative}"</div>`
    : '';

  el.innerHTML = gradesHtml + compHtml + arsenalHtml + exitVeloHtml + narrativeHtml +
    `<div style="font-size:9px;color:var(--text-muted);margin-top:8px;text-align:right">Scout confidence: ${r.scout_quality || 'N/A'}/100 | Margin: +/-${margin}</div>`;
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
// GAME DAY
// ============================================================
let _gameDayData = null;
let _gameDayPlays = [];
let _gameDayPlayIndex = 0;
let _gameDayAnimating = false;
let _gameDayPlaySpeed = 500;  // ms per play

async function loadGameDay() {
  const el = document.getElementById('s-gameday');
  if (!el) return;

  // Check if user has a team
  const state = await fetch('/game-state').then(r => r.json());
  if (!state.user_team_id) {
    el.innerHTML = '<div style="padding: 2rem;"><p>No user team selected. Please select a team first.</p><button class="btn btn-primary" onclick="showScreen(\'calendar\')">Back to Calendar</button></div>';
    return;
  }

  // Try to load today's game
  const response = await fetch('/sim/game-live', { method: 'POST' });
  const data = await response.json();

  if (data.error) {
    el.innerHTML = `
      <div style="padding: 2rem; text-align: center;">
        <h3>No Game Today</h3>
        <p>${data.error}</p>
        <button class="btn btn-primary" onclick="simDays(1)">Advance to Next Day</button>
      </div>
    `;
    return;
  }

  _gameDayData = data;
  _gameDayPlays = data.plays || [];
  _gameDayPlayIndex = 0;

  renderGameDayUI();
  initGameDayDisplay();
}

function renderGameDayUI() {
  const d = _gameDayData;
  const el = document.getElementById('s-gameday');
  if (!el) return;

  // Update team names
  document.getElementById('gd-away-name').textContent = `${d.away_team.abbr}`;
  document.getElementById('gd-home-name').textContent = `${d.home_team.abbr}`;

  // Update score
  document.getElementById('gd-score-display').innerHTML = `
    <div>${d.away_team.abbr}: ${d.final_score[1]}</div>
    <div>${d.home_team.abbr}: ${d.final_score[0]}</div>
  `;

  // Build linescore placeholder
  const linescore = `
    <div class="linescore-team">${d.away_team.abbr}</div>
    <div class="linescore-inning">1</div>
    <div class="linescore-inning">2</div>
    <div class="linescore-inning">3</div>
    <div class="linescore-inning">4</div>
    <div class="linescore-inning">5</div>
    <div class="linescore-inning">6</div>
    <div class="linescore-inning">7</div>
    <div class="linescore-inning">8</div>
    <div class="linescore-inning">9</div>
    <div class="linescore-rhe" style="grid-column: 11 / 13;">
      <span>R: ${d.final_score[1]}</span>
      <span>H: 0</span>
      <span>E: 0</span>
    </div>
  `;
  document.getElementById('gd-linescore').innerHTML = linescore;

  // Situation display
  document.getElementById('gd-situation-text').textContent = 'Game Complete';

  // Clear plays feed
  document.getElementById('gd-plays-feed').innerHTML = '';
  _gameDayPlays.forEach(play => {
    addPlayToFeed(play);
  });
}

function initGameDayDisplay() {
  // Reset animation
  _gameDayPlayIndex = 0;
  _gameDayAnimating = false;
  document.getElementById('gd-plays-feed').innerHTML = '';
}

function addPlayToFeed(play) {
  const feed = document.getElementById('gd-plays-feed');
  if (!feed) return;

  const playEl = document.createElement('div');
  playEl.className = `play-item ${play.half}`;
  playEl.innerHTML = `
    <span class="play-time">I${play.inning}${play.half === 'top' ? 'T' : 'B'}:</span>
    <span class="play-text">${play.description}</span>
  `;
  feed.appendChild(playEl);
}

function startLiveGameSim() {
  if (_gameDayAnimating || !_gameDayPlays.length) return;

  _gameDayAnimating = true;
  _gameDayPlayIndex = 0;

  document.getElementById('gd-plays-feed').innerHTML = '';
  animateNextPlay();
}

function animateNextPlay() {
  if (_gameDayPlayIndex >= _gameDayPlays.length) {
    _gameDayAnimating = false;
    return;
  }

  const play = _gameDayPlays[_gameDayPlayIndex];
  addPlayToFeed(play);
  _gameDayPlayIndex++;

  if (_gameDayAnimating) {
    setTimeout(animateNextPlay, _gameDayPlaySpeed);
  }
}

function skipToEnd() {
  _gameDayAnimating = false;
  _gameDayPlayIndex = _gameDayPlays.length;
  document.getElementById('gd-plays-feed').innerHTML = '';
  _gameDayPlays.forEach(play => addPlayToFeed(play));
}

function updateSimSpeed(value) {
  _gameDayPlaySpeed = parseInt(value);
  const speeds = {
    100: '4.0x', 250: '2.0x', 500: '1.0x', 1000: '0.5x', 2000: '0.25x'
  };
  document.getElementById('speed-display').textContent = speeds[value] || '1.0x';
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

  // Load waiver wire and league transactions
  loadWaiverWire();
  loadLeagueTransactions();
}

async function loadWaiverWire() {
  const el = document.getElementById('trans-waivers-list');
  if (!el) return;
  const waivers = await api('/waivers');
  if (!waivers || !waivers.length) {
    el.innerHTML = '<div class="empty-state" style="padding:12px;font-size:11px">No players currently on waivers</div>';
    return;
  }
  let html = '';
  for (const w of waivers) {
    const isPitch = w.position === 'SP' || w.position === 'RP';
    const mainRating = isPitch ? w.stuff_rating : w.contact_rating;
    html += `
      <div style="padding:8px 12px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
        <div style="flex:1">
          <div style="font-weight:500;cursor:pointer" onclick="showPlayer(${w.player_id})">${w.first_name} ${w.last_name}</div>
          <div style="font-size:10px;color:var(--text-dim)">${w.position} | Age ${w.age} | from ${w.original_team_abbr || '?'} | Expires: ${w.expiry_date}</div>
        </div>
        <div style="text-align:right;margin-right:12px;color:var(--accent);font-weight:600">${mainRating}</div>
        <button class="btn btn-primary btn-sm" style="padding:2px 8px;font-size:10px" onclick="claimWaiverPlayer(${w.player_id}, '${w.first_name} ${w.last_name}')">Claim</button>
      </div>`;
  }
  el.innerHTML = html;
}

async function claimWaiverPlayer(pid, name) {
  const r = await post('/waivers/claim/' + pid, {});
  if (r?.success) {
    showToast('Claimed ' + name + ' off waivers!', 'success');
    loadTransactions();
  } else {
    showToast(r?.detail || 'Failed to claim player', 'error');
  }
}

async function loadLeagueTransactions() {
  const el = document.getElementById('trans-league-log');
  if (!el) return;
  const txns = await api('/transactions/recent?limit=50');
  if (!txns || !txns.length) {
    el.innerHTML = '<div class="empty-state" style="padding:12px;font-size:11px">No transactions yet</div>';
    return;
  }
  let html = '';
  for (const t of txns) {
    const typeLabel = {
      'trade': 'Trade', 'waiver_claim': 'Waiver Claim', 'free_agent_signing': 'FA Signing',
      'dfa': 'DFA', 'release': 'Released', 'call_up': 'Call Up', 'option': 'Optioned',
      'contract_extension': 'Extension', 'il_placement': 'Placed on IL', 'il_activation': 'Activated from IL'
    }[t.transaction_type] || t.transaction_type;
    const playerName = t.first_name ? `${t.first_name} ${t.last_name}` : '';
    html += `
      <div style="padding:6px 12px;border-bottom:1px solid var(--border);font-size:11px;display:flex;gap:8px;align-items:center">
        <span style="color:var(--text-muted);min-width:70px">${t.transaction_date || ''}</span>
        <span style="background:var(--bg-2);padding:1px 6px;border-radius:2px;font-size:10px;min-width:80px;text-align:center">${typeLabel}</span>
        <span style="color:var(--accent);min-width:30px">${t.abbreviation || ''}</span>
        <span style="font-weight:500">${playerName}</span>
        <span style="color:var(--text-dim);flex:1">${t.details || ''}</span>
      </div>`;
  }
  el.innerHTML = html;
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
            ${p.is_injured ? ` | <span style="color:var(--red)">${p.injury_type || 'Injured'} (${p.injury_days_remaining || '?'}d)</span>` : ''}
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
// PLAYOFFS
// ============================================================
async function loadPlayoffs() {
  const el = document.getElementById('playoffs-body');

  if (STATE.phase !== 'postseason') {
    el.innerHTML = '<div class="msg-note">Playoffs begin in October during postseason.</div>';
    return;
  }

  const bracket = await api('/playoffs/bracket');
  if (!bracket || !bracket.by_round) {
    el.innerHTML = '<div class="msg-note">No playoff bracket data available.</div>';
    return;
  }

  let html = '<div class="playoff-container">';

  // Build HTML for each round
  const rounds = ['wild_card', 'division_series', 'championship_series', 'world_series'];
  const roundNames = {
    'wild_card': 'Wild Card',
    'division_series': 'Division Series',
    'championship_series': 'Championship Series',
    'world_series': 'World Series'
  };

  for (const round of rounds) {
    const series = bracket.by_round[round] || [];
    if (series.length === 0) continue;

    html += `<div class="playoff-round">
      <div class="playoff-round-name">${roundNames[round]}</div>
      <div class="playoff-series-list">`;

    for (const s of series) {
      const higher = s.higher_seed;
      const lower = s.lower_seed;
      const winner = s.winner;
      const isComplete = s.is_complete;

      const higherWins = s.higher_seed.wins || 0;
      const lowerWins = s.lower_seed.wins || 0;

      let winCondition = 2; // WC is best-of-3
      if (round !== 'wild_card') winCondition = 4; // DS, CS, WS are best-of-7

      const higherStatus = higherWins >= winCondition ? 'series-winner' : 'series-team';
      const lowerStatus = lowerWins >= winCondition ? 'series-winner' : 'series-team';

      html += `<div class="playoff-matchup">
        <div class="series-id">${s.series_id.toUpperCase()}</div>
        <div class="playoff-team ${higherStatus}">
          <div class="team-info">
            <span class="team-abbr">${higher.abbr || 'TBD'}</span>
            <span class="team-name">${higher.name || 'TBD'}</span>
          </div>
          <div class="series-score">${higherWins}</div>
        </div>
        <div class="playoff-team ${lowerStatus}">
          <div class="team-info">
            <span class="team-abbr">${lower.abbr || 'TBD'}</span>
            <span class="team-name">${lower.name || 'TBD'}</span>
          </div>
          <div class="series-score">${lowerWins}</div>
        </div>`;

      if (isComplete && winner) {
        html += `<div class="series-winner">🏆 ${winner.abbr}</div>`;
      }

      html += `</div>`;
    }

    html += `</div></div>`;
  }

  html += '</div>';
  el.innerHTML = html;
}

// ============================================================
// INIT
// ============================================================
function createKeyboardHelp() {
  const div = document.createElement('div');
  div.id = 'keyboard-help';
  div.style.display = 'none';
  div.innerHTML = `
    <div class="kb-help-title">Keyboard Shortcuts <span class="kb-help-close" onclick="document.getElementById('keyboard-help').style.display='none'">&times;</span></div>
    <div class="kb-help-row"><kbd>Space</kbd> / <kbd>Enter</kbd> <span>Sim Day</span></div>
    <div class="kb-help-row"><kbd>Shift+Enter</kbd> <span>Sim Week</span></div>
    <div class="kb-help-row"><kbd>${navigator.platform.includes('Mac') ? 'Cmd' : 'Ctrl'}+K</kbd> <span>Search</span></div>
    <div class="kb-help-row"><kbd>1</kbd>-<kbd>9</kbd> <span>Navigate Screens</span></div>
    <div class="kb-help-row"><kbd>?</kbd> <span>Toggle This Help</span></div>
    <div class="kb-help-row"><kbd>Esc</kbd> <span>Close Modal</span></div>
  `;
  document.body.appendChild(div);
}

async function init() {
  initTheme();
  createKeyboardHelp();
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
