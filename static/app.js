/* ============================================================
   FRONT OFFICE - Client App
   ============================================================ */

const API = '';  // same origin
let STATE = {
  userTeamId: null,
  userTeamAbbr: '',
  userTeamName: '',
  currentDate: '',
  season: 2026,
  selectedTradeTeam: null,
  tradeOffering: [],
  tradeRequesting: [],
};

// ============================================================
// INTRO / NARRATIVE
// ============================================================
const TEAM_OPTIONS = [
  {
    id: null, // will be set from API
    abbr: 'PIT',
    city: 'Pittsburgh',
    name: 'Pirates',
    owner: 'Marcus Whitfield',
    ownerType: 'Impatient heir who just took over from his father',
    pitch: 'A proud franchise stuck in a two-decade spiral. The farm system has talent but the front office has been allergic to innovation. Whitfield wants someone who thinks differently. The budget is modest but real.',
    challenge: 'Small market, skeptical fanbase, thin major league roster, but a top-10 farm system ready to arrive.',
  },
  {
    id: null,
    abbr: 'KC',
    city: 'Kansas City',
    name: 'Royals',
    owner: 'Dennis Cavanaugh',
    ownerType: 'Self-made tech billionaire, first year of ownership',
    pitch: 'Cavanaugh made his fortune in AI and bought the Royals because he believes baseball is the ultimate optimization problem. He wants a GM who speaks his language. Resources are better than you\'d expect.',
    challenge: 'Mid-market, aging core from a recent playoff push, an owner who will give you rope but expects results by year 3.',
  },
  {
    id: null,
    abbr: 'CIN',
    city: 'Cincinnati',
    name: 'Reds',
    owner: 'Patricia Langford',
    ownerType: 'Lifelong fan, inherited the team, tired of losing',
    pitch: 'Great American Ball Park is a hitter\'s paradise and Langford is ready to spend — within reason. She fired the last GM for being too conservative. She wants bold moves and doesn\'t care if the old guard disapproves.',
    challenge: 'Competitive division, homer-friendly park, passionate but impatient fanbase, and a payroll that needs creative management.',
  },
];

function playIntro() {
  const narrative = document.getElementById('intro-narrative');
  narrative.innerHTML = `
    <p><span class="dim">February 14, 2026</span></p>
    <p>The call comes on a Tuesday morning. An unknown number. You almost don't answer.</p>
    <p>On the other end is a voice you don't recognize — an owner you've only read about. He says the words that change everything: <span class="highlight">"I just fired my General Manager. I've been watching you. I think you're exactly what this franchise needs."</span></p>
    <p>You're not a traditional baseball executive. You never played pro ball, never worked your way up through a scouting department. You're something else — an <span class="gold">outsider with an edge</span>. You understand systems, data, and how to build something from nothing. The old guard thinks you're a joke. The owner thinks you're the future.</p>
    <p>Three teams are interested. Three owners willing to bet on you. Each one a different challenge, a different city, a different story waiting to be written.</p>
    <p><span class="highlight">Choose your franchise.</span></p>
  `;

  const choices = document.getElementById('intro-choices');
  choices.style.display = 'flex';
  choices.innerHTML = TEAM_OPTIONS.map((t, i) => `
    <div class="team-choice" onclick="selectTeam(${i})" id="choice-${i}">
      <h3>${t.city} ${t.name}</h3>
      <p><strong>Owner:</strong> ${t.owner} — ${t.ownerType}</p>
      <p>${t.pitch}</p>
      <p style="color: var(--gold); margin-top: 4px; font-size: 12px;">${t.challenge}</p>
    </div>
  `).join('');
}

function selectTeam(index) {
  document.querySelectorAll('.team-choice').forEach(el => el.classList.remove('selected'));
  document.getElementById(`choice-${index}`).classList.add('selected');
  STATE.selectedIntroTeam = index;
  document.getElementById('intro-start').style.display = 'block';
  document.getElementById('intro-start').style.opacity = '0';
  document.getElementById('intro-start').style.animation = 'fadeIn 0.5s ease forwards';
}

async function startGame() {
  const team = TEAM_OPTIONS[STATE.selectedIntroTeam];

  // Find the real team ID from API
  const teams = await fetch(`${API}/teams`).then(r => r.json());
  const match = teams.find(t => t.abbreviation === team.abbr);
  if (match) {
    STATE.userTeamId = match.id;
    STATE.userTeamAbbr = match.abbreviation;
    STATE.userTeamName = `${match.city} ${match.name}`;
  }

  // Set user team in backend
  await fetch(`${API}/set-user-team`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({team_id: STATE.userTeamId})
  }).catch(() => {});

  // Switch to main app
  document.getElementById('intro-screen').classList.remove('active');
  document.getElementById('app').classList.add('active');

  // Load everything
  await loadGameState();
  showScreen('dashboard');
}

// ============================================================
// GAME STATE
// ============================================================
async function loadGameState() {
  try {
    const state = await fetch(`${API}/game-state`).then(r => r.json());
    STATE.currentDate = state.current_date;
    STATE.season = state.season;
    if (state.user_team_id && !STATE.userTeamId) {
      STATE.userTeamId = state.user_team_id;
    }

    // Load team info
    if (STATE.userTeamId) {
      const team = await fetch(`${API}/team/${STATE.userTeamId}`).then(r => r.json());
      STATE.userTeamAbbr = team.team.abbreviation;
      STATE.userTeamName = `${team.team.city} ${team.team.name}`;

      document.getElementById('header-team-name').textContent = STATE.userTeamName;
      document.getElementById('header-date').textContent = formatDate(STATE.currentDate);

      // Get record
      const standings = await fetch(`${API}/standings`).then(r => r.json());
      for (const [div, teams] of Object.entries(standings)) {
        const us = teams.find(t => t.team_id === STATE.userTeamId);
        if (us) {
          document.getElementById('header-record').textContent = `${us.wins}-${us.losses}`;
          break;
        }
      }
    }
  } catch (e) {
    console.error('Failed to load game state:', e);
  }
}

// ============================================================
// NAVIGATION
// ============================================================
function showScreen(name) {
  document.querySelectorAll('.content-screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  const screen = document.getElementById(`screen-${name}`);
  if (screen) screen.classList.add('active');

  const btn = document.querySelector(`.nav-btn[data-screen="${name}"]`);
  if (btn) btn.classList.add('active');

  // Load data for the screen
  const loaders = {
    dashboard: loadDashboard,
    roster: loadRoster,
    standings: loadStandings,
    schedule: loadSchedule,
    finances: loadFinances,
    trades: loadTradeCenter,
    'free-agents': loadFreeAgents,
    leaders: loadLeaders,
    messages: loadMessages,
  };
  if (loaders[name]) loaders[name]();
}

// ============================================================
// SIMULATION
// ============================================================
async function simDay(days) {
  const btns = document.querySelectorAll('.btn-sim');
  btns.forEach(b => { b.disabled = true; b.textContent = '⏳'; });

  try {
    const result = await fetch(`${API}/sim/advance`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({days})
    }).then(r => r.json());

    await loadGameState();

    // Update ticker
    const ticker = document.getElementById('ticker');
    ticker.textContent = `Simulated ${days} day${days > 1 ? 's' : ''} → ${result.games_played} games played | Now: ${formatDate(result.new_date)}`;

    // Refresh current screen
    const active = document.querySelector('.content-screen.active');
    if (active) {
      const name = active.id.replace('screen-', '');
      showScreen(name);
    }
  } catch (e) {
    console.error('Sim failed:', e);
  }

  btns.forEach(b => b.disabled = false);
  document.querySelectorAll('.btn-sim')[0].textContent = '▶ Sim Day';
  document.querySelectorAll('.btn-sim')[1].textContent = '▶▶ Sim Week';
}

// ============================================================
// DASHBOARD
// ============================================================
async function loadDashboard() {
  // Standings
  const standings = await fetch(`${API}/standings`).then(r => r.json());
  const dashStandings = document.getElementById('dash-standings');
  let userDiv = '';
  for (const [div, teams] of Object.entries(standings)) {
    if (teams.find(t => t.team_id === STATE.userTeamId)) {
      userDiv = div;
      break;
    }
  }
  if (userDiv && standings[userDiv]) {
    dashStandings.innerHTML = renderStandingsTable(standings[userDiv]);
  }

  // Recent scores
  const schedule = await fetch(`${API}/schedule?limit=10`).then(r => r.json());
  const played = schedule.filter(g => g.is_played);
  const dashScores = document.getElementById('dash-scores');
  dashScores.innerHTML = played.slice(-10).reverse().map(g => `
    <div class="score-card">
      <div class="score-teams">
        <span class="${g.away_score > g.home_score ? 'winner' : ''}">${g.away_abbr}</span>
        @ <span class="${g.home_score > g.away_score ? 'winner' : ''}">${g.home_abbr}</span>
      </div>
      <div class="score-result">${g.away_score}-${g.home_score}</div>
      <div style="color:var(--text-muted);font-size:11px;min-width:75px;text-align:right">${g.game_date}</div>
    </div>
  `).join('') || '<p style="color:var(--text-muted)">No games played yet. Sim to begin the season.</p>';

  // Roster snapshot
  if (STATE.userTeamId) {
    const roster = await fetch(`${API}/roster/${STATE.userTeamId}`).then(r => r.json());
    document.getElementById('dash-roster').innerHTML = `
      <div class="finance-line"><span>Active Roster</span><span>${roster.active_count}/26</span></div>
      <div class="finance-line"><span>40-Man</span><span>${roster.forty_man_count}/40</span></div>
      <div class="finance-line"><span>Injured</span><span style="color:var(--red)">${roster.injured_count}</span></div>
      <div class="finance-line"><span>Payroll</span><span style="color:var(--gold)">$${(roster.payroll / 1000000).toFixed(1)}M</span></div>
    `;
  }

  // News/wire
  const msgs = await fetch(`${API}/messages?unread_only=false`).then(r => r.json()).catch(() => []);
  const txns = await fetch(`${API}/transactions?limit=5`).then(r => r.json()).catch(() => []);
  const newsEl = document.getElementById('dash-news');
  if (txns.length > 0) {
    newsEl.innerHTML = txns.map(t => `
      <div style="padding:4px 0;border-bottom:1px solid var(--border);font-size:12px">
        <span style="color:var(--text-muted)">${t.transaction_date}</span>
        <span style="color:var(--accent)">${t.team1_abbr || ''}</span>
        ${t.transaction_type.replace('_', ' ')}
        ${t.team2_abbr ? `with <span style="color:var(--accent)">${t.team2_abbr}</span>` : ''}
      </div>
    `).join('');
  } else {
    newsEl.innerHTML = '<p style="color:var(--text-muted)">Spring Training begins soon. The hot stove is quiet... for now.</p>';
  }
}

// ============================================================
// STANDINGS
// ============================================================
async function loadStandings() {
  const standings = await fetch(`${API}/standings`).then(r => r.json());

  for (const league of ['AL', 'NL']) {
    const container = document.getElementById(`standings-${league.toLowerCase()}`);
    const leagueName = league === 'AL' ? 'American League' : 'National League';
    let html = `<h3>${leagueName}</h3>`;

    for (const div of ['East', 'Central', 'West']) {
      const key = `${league} ${div}`;
      if (standings[key]) {
        html += `<div class="standings-division"><h4>${div}</h4>`;
        html += renderStandingsTable(standings[key]);
        html += '</div>';
      }
    }
    container.innerHTML = html;
  }
}

function renderStandingsTable(teams) {
  return `<table>
    <tr><th>Team</th><th class="num">W</th><th class="num">L</th><th class="num">Pct</th><th class="num">GB</th><th class="num">RS</th><th class="num">RA</th><th class="num">Diff</th></tr>
    ${teams.map(t => `
      <tr class="${t.team_id === STATE.userTeamId ? 'user-team' : ''}">
        <td><strong>${t.abbreviation}</strong> ${t.name}</td>
        <td class="num">${t.wins}</td>
        <td class="num">${t.losses}</td>
        <td class="num">${t.pct.toFixed(3)}</td>
        <td class="num">${t.gb === 0 ? '-' : t.gb.toFixed(1)}</td>
        <td class="num">${t.runs_scored}</td>
        <td class="num">${t.runs_allowed}</td>
        <td class="num ${t.diff > 0 ? 'positive' : t.diff < 0 ? 'negative' : ''}">${t.diff > 0 ? '+' : ''}${t.diff}</td>
      </tr>
    `).join('')}
  </table>`;
}

// ============================================================
// ROSTER
// ============================================================
async function loadRoster() {
  if (!STATE.userTeamId) return;
  const roster = await fetch(`${API}/roster/${STATE.userTeamId}`).then(r => r.json());

  const content = document.getElementById('roster-content');
  const active = roster.active || [];
  const minors = roster.minors || [];
  const injured = roster.injured || [];

  // Default to active tab
  showRosterTab('active', {active, minors, injured});
  STATE._rosterData = {active, minors, injured};
}

function showRosterTab(tab, data) {
  data = data || STATE._rosterData;
  if (!data) return;

  document.querySelectorAll('.roster-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  event?.target?.classList?.add('active');

  const content = document.getElementById('roster-content');
  const players = tab === 'active' ? data.active : tab === 'minors' ? data.minors : data.injured;
  const isPitcher = (p) => p.position === 'SP' || p.position === 'RP';

  const positionPlayers = players.filter(p => !isPitcher(p));
  const pitchers = players.filter(p => isPitcher(p));

  let html = '';

  if (positionPlayers.length) {
    html += '<h3 style="color:var(--text-dim);margin:12px 0 8px;font-size:12px;letter-spacing:2px">POSITION PLAYERS</h3>';
    html += `<table>
      <tr><th>Name</th><th>Pos</th><th>Age</th><th>B/T</th><th>Con</th><th>Pow</th><th>Spd</th><th>Fld</th><th class="num">Salary</th></tr>
      ${positionPlayers.map(p => `
        <tr>
          <td class="clickable" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
          <td>${p.position}</td>
          <td>${p.age}</td>
          <td>${p.bats}/${p.throws}</td>
          <td>${ratingBadge(p.contact_rating)}</td>
          <td>${ratingBadge(p.power_rating)}</td>
          <td>${ratingBadge(p.speed_rating)}</td>
          <td>${ratingBadge(p.fielding_rating)}</td>
          <td class="num">${p.annual_salary ? '$' + (p.annual_salary / 1000000).toFixed(1) + 'M' : 'Pre-Arb'}</td>
        </tr>
      `).join('')}
    </table>`;
  }

  if (pitchers.length) {
    html += '<h3 style="color:var(--text-dim);margin:20px 0 8px;font-size:12px;letter-spacing:2px">PITCHERS</h3>';
    html += `<table>
      <tr><th>Name</th><th>Pos</th><th>Age</th><th>T</th><th>Stuff</th><th>Ctrl</th><th>Stam</th><th class="num">Salary</th></tr>
      ${pitchers.map(p => `
        <tr>
          <td class="clickable" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
          <td>${p.position}</td>
          <td>${p.age}</td>
          <td>${p.throws}</td>
          <td>${ratingBadge(p.stuff_rating)}</td>
          <td>${ratingBadge(p.control_rating)}</td>
          <td>${ratingBadge(p.stamina_rating)}</td>
          <td class="num">${p.annual_salary ? '$' + (p.annual_salary / 1000000).toFixed(1) + 'M' : 'Pre-Arb'}</td>
        </tr>
      `).join('')}
    </table>`;
  }

  if (!players.length) {
    html = '<p class="loading">No players in this category.</p>';
  }

  content.innerHTML = html;
}

function ratingBadge(val) {
  const cls = val >= 70 ? 'rating-elite' : val >= 55 ? 'rating-good' : val >= 40 ? 'rating-avg' : 'rating-below';
  const pct = ((val - 20) / 60) * 100;
  return `<div class="rating-bar"><div class="rating-fill ${cls}" style="width:${pct}%"></div></div>${val}`;
}

// ============================================================
// PLAYER MODAL
// ============================================================
async function showPlayer(playerId) {
  const modal = document.getElementById('player-modal');
  const body = document.getElementById('player-modal-body');
  modal.style.display = 'flex';

  body.innerHTML = '<div class="loading"><span class="spinner"></span> Loading player...</div>';

  const data = await fetch(`${API}/player/${playerId}`).then(r => r.json());
  const p = data.player;
  const isPitcher = p.position === 'SP' || p.position === 'RP';

  let ratingsHtml = '';
  if (isPitcher) {
    ratingsHtml = ['Stuff', 'Control', 'Stamina'].map((label, i) => {
      const val = [p.stuff_rating, p.control_rating, p.stamina_rating][i];
      return ratingCard(label, val);
    }).join('');
  } else {
    ratingsHtml = ['Contact', 'Power', 'Speed', 'Fielding', 'Arm'].map((label, i) => {
      const val = [p.contact_rating, p.power_rating, p.speed_rating, p.fielding_rating, p.arm_rating][i];
      return ratingCard(label, val);
    }).join('');
  }

  const personalityHtml = ['Ego', 'Leadership', 'Work Ethic', 'Clutch', 'Durability'].map((label, i) => {
    const val = [p.ego, p.leadership, p.work_ethic, p.clutch, p.durability][i];
    return ratingCard(label, val);
  }).join('');

  // Stats tables
  let statsHtml = '';
  if (data.batting_stats?.length) {
    const s = data.batting_stats[0];
    const avg = s.ab > 0 ? (s.hits / s.ab).toFixed(3) : '.000';
    const obp = s.pa > 0 ? ((s.hits + s.bb + s.hbp) / s.pa).toFixed(3) : '.000';
    statsHtml = `<table class="player-stats-table">
      <tr><th>G</th><th>AB</th><th>H</th><th>2B</th><th>3B</th><th>HR</th><th>RBI</th><th>BB</th><th>SO</th><th>SB</th><th>AVG</th><th>OBP</th></tr>
      <tr><td>${s.games}</td><td>${s.ab}</td><td>${s.hits}</td><td>${s.doubles}</td><td>${s.triples}</td><td>${s.hr}</td><td>${s.rbi}</td><td>${s.bb}</td><td>${s.so}</td><td>${s.sb}</td><td>${avg}</td><td>${obp}</td></tr>
    </table>`;
  }
  if (data.pitching_stats?.length) {
    const s = data.pitching_stats[0];
    const ip = (s.ip_outs / 3).toFixed(1);
    const era = s.ip_outs > 0 ? (9 * s.er / (s.ip_outs / 3)).toFixed(2) : '0.00';
    statsHtml += `<table class="player-stats-table">
      <tr><th>G</th><th>GS</th><th>W</th><th>L</th><th>SV</th><th>IP</th><th>H</th><th>ER</th><th>BB</th><th>SO</th><th>HR</th><th>ERA</th></tr>
      <tr><td>${s.games}</td><td>${s.games_started}</td><td>${s.wins}</td><td>${s.losses}</td><td>${s.saves}</td><td>${ip}</td><td>${s.hits_allowed}</td><td>${s.er}</td><td>${s.bb}</td><td>${s.so}</td><td>${s.hr_allowed}</td><td>${era}</td></tr>
    </table>`;
  }

  body.innerHTML = `
    <div class="player-header">
      <div>
        <div class="player-name">${p.first_name} ${p.last_name}</div>
        <div class="player-info">${p.position} | Age ${p.age} | ${p.bats}/${p.throws} | ${p.birth_country}</div>
        <div class="player-info">${p.abbreviation || ''} ${p.team_name || 'Free Agent'}</div>
      </div>
      <div class="player-contract">
        <div class="player-salary">${p.annual_salary ? '$' + (p.annual_salary / 1000000).toFixed(1) + 'M/yr' : 'Pre-Arb'}</div>
        <div>${p.years_remaining ? p.years_remaining + ' yr remaining' : ''}</div>
        ${p.no_trade_clause ? '<div style="color:var(--red)">No-Trade Clause</div>' : ''}
      </div>
    </div>
    <h3 style="color:var(--accent);font-size:12px;letter-spacing:2px;margin-bottom:8px">${isPitcher ? 'PITCHING' : 'HITTING'} RATINGS</h3>
    <div class="ratings-grid">${ratingsHtml}</div>
    <h3 style="color:var(--accent);font-size:12px;letter-spacing:2px;margin:16px 0 8px">PERSONALITY</h3>
    <div class="ratings-grid">${personalityHtml}</div>
    ${statsHtml ? '<h3 style="color:var(--accent);font-size:12px;letter-spacing:2px;margin:16px 0 8px">SEASON STATS</h3>' + statsHtml : ''}
    <div style="margin-top:16px">
      <button class="btn btn-primary" onclick="loadScoutingReport(${p.id})">Generate Scouting Report</button>
      <div id="scouting-report-${p.id}" class="scouting-report" style="display:none"></div>
    </div>
  `;
}

function ratingCard(label, val) {
  const color = val >= 70 ? 'var(--gold)' : val >= 55 ? 'var(--green)' : val >= 40 ? 'var(--blue)' : 'var(--red)';
  return `<div class="rating-item">
    <div class="rating-label">${label}</div>
    <div class="rating-value" style="color:${color}">${val}</div>
  </div>`;
}

async function loadScoutingReport(playerId) {
  const el = document.getElementById(`scouting-report-${playerId}`);
  el.style.display = 'block';
  el.innerHTML = '<span class="spinner"></span> Scout is evaluating...';
  const data = await fetch(`${API}/player/${playerId}/scouting-report`).then(r => r.json());
  el.innerHTML = `"${data.report}"`;
}

function closeModal() {
  document.getElementById('player-modal').style.display = 'none';
}

// ============================================================
// SCHEDULE
// ============================================================
async function loadSchedule() {
  const content = document.getElementById('schedule-content');
  content.innerHTML = '<div class="loading"><span class="spinner"></span> Loading schedule...</div>';

  let url = `${API}/schedule?limit=30`;
  if (STATE.userTeamId) url += `&team_id=${STATE.userTeamId}`;
  const games = await fetch(url).then(r => r.json());

  content.innerHTML = `<table>
    <tr><th>Date</th><th>Away</th><th></th><th>Home</th><th>Score</th></tr>
    ${games.map(g => `
      <tr>
        <td>${g.game_date}</td>
        <td class="${g.away_team_id === STATE.userTeamId ? 'user-team' : ''}">${g.away_abbr} ${g.away_city} ${g.away_name}</td>
        <td style="color:var(--text-muted)">@</td>
        <td class="${g.home_team_id === STATE.userTeamId ? 'user-team' : ''}">${g.home_abbr} ${g.home_city} ${g.home_name}</td>
        <td class="num">${g.is_played ? `${g.away_score}-${g.home_score}` : '-'}</td>
      </tr>
    `).join('')}
  </table>`;
}

// ============================================================
// FINANCES
// ============================================================
async function loadFinances() {
  if (!STATE.userTeamId) return;
  const content = document.getElementById('finances-content');
  content.innerHTML = '<div class="loading"><span class="spinner"></span> Loading finances...</div>';

  const fin = await fetch(`${API}/finances/${STATE.userTeamId}/details`).then(r => r.json());
  const team = await fetch(`${API}/finances/${STATE.userTeamId}`).then(r => r.json());

  content.innerHTML = `<div class="finances-grid">
    <div class="finance-card">
      <h3>Revenue</h3>
      <div class="finance-line"><span>Ticket Sales</span><span>$${fmt(fin.ticket_revenue)}</span></div>
      <div class="finance-line"><span>Concessions</span><span>$${fmt(fin.concession_revenue)}</span></div>
      <div class="finance-line"><span>Broadcast</span><span>$${fmt(fin.broadcast_revenue)}</span></div>
      <div class="finance-line"><span>Merchandise</span><span>$${fmt(fin.merchandise_revenue)}</span></div>
      <div class="finance-line total"><span>Total Revenue</span><span class="positive">$${fmt(fin.total_revenue)}</span></div>
    </div>
    <div class="finance-card">
      <h3>Expenses</h3>
      <div class="finance-line"><span>Player Payroll</span><span>$${fmt(fin.payroll)}</span></div>
      <div class="finance-line"><span>Farm System</span><span>$${fmt(fin.farm_expenses)}</span></div>
      <div class="finance-line"><span>Medical Staff</span><span>$${fmt(fin.medical_expenses)}</span></div>
      <div class="finance-line"><span>Scouting</span><span>$${fmt(fin.scouting_expenses)}</span></div>
      <div class="finance-line"><span>Stadium Ops</span><span>$${fmt(fin.stadium_expenses)}</span></div>
      <div class="finance-line"><span>Owner Dividends</span><span>$${fmt(fin.owner_dividends)}</span></div>
      <div class="finance-line total"><span>Total Expenses</span><span class="negative">$${fmt(fin.total_expenses)}</span></div>
    </div>
    <div class="finance-card">
      <h3>Bottom Line</h3>
      <div class="finance-line total">
        <span>Profit/Loss</span>
        <span class="${fin.profit >= 0 ? 'positive' : 'negative'}">$${fmt(fin.profit)}</span>
      </div>
      <div class="finance-line"><span>Cash on Hand</span><span>$${fmt(team.cash)}</span></div>
      <div class="finance-line"><span>Franchise Value</span><span>$${fmt(team.franchise_value)}</span></div>
      <div class="finance-line"><span>Avg Attendance</span><span>${fin.attendance_avg?.toLocaleString() || 0}</span></div>
    </div>
    <div class="finance-card">
      <h3>Budget Allocation</h3>
      <div class="finance-line"><span>Farm System</span><span>$${fmt(team.farm_budget)}</span></div>
      <div class="finance-line"><span>Medical Staff</span><span>$${fmt(team.medical_budget)}</span></div>
      <div class="finance-line"><span>Scouting</span><span>$${fmt(team.scouting_budget)}</span></div>
      <div class="finance-line"><span>Ticket Price</span><span>${team.ticket_price_pct}% of avg</span></div>
      <div class="finance-line"><span>Concession Price</span><span>${team.concession_price_pct}% of avg</span></div>
    </div>
  </div>`;
}

// ============================================================
// TRADE CENTER
// ============================================================
async function loadTradeCenter() {
  const teams = await fetch(`${API}/teams`).then(r => r.json());
  const select = document.getElementById('trade-team-select');
  select.innerHTML = '<option value="">Select a team...</option>' +
    teams.filter(t => t.id !== STATE.userTeamId)
      .map(t => `<option value="${t.id}">${t.abbreviation} ${t.city} ${t.name}</option>`)
      .join('');

  // Load your team's roster
  if (STATE.userTeamId) {
    const roster = await fetch(`${API}/roster/${STATE.userTeamId}`).then(r => r.json());
    document.getElementById('trade-your-name').textContent = STATE.userTeamName;
    document.getElementById('trade-your-players').innerHTML = renderTradeRoster(roster.active, 'offer');
  }

  STATE.tradeOffering = [];
  STATE.tradeRequesting = [];
  updateTradeSlots();
}

async function loadTradeTeam() {
  const teamId = parseInt(document.getElementById('trade-team-select').value);
  if (!teamId) return;
  STATE.selectedTradeTeam = teamId;
  const roster = await fetch(`${API}/roster/${teamId}`).then(r => r.json());
  document.getElementById('trade-other-players').innerHTML = renderTradeRoster(roster.active, 'request');
}

function renderTradeRoster(players, action) {
  return `<table style="font-size:11px">
    ${players.map(p => `
      <tr style="cursor:pointer" onclick="toggleTrade(${p.id}, '${p.first_name} ${p.last_name}', '${p.position}', '${action}')">
        <td>${p.first_name} ${p.last_name}</td>
        <td>${p.position}</td>
        <td>${p.age}</td>
        <td>$${p.annual_salary ? (p.annual_salary/1000000).toFixed(1) + 'M' : 'min'}</td>
      </tr>
    `).join('')}
  </table>`;
}

function toggleTrade(playerId, name, pos, action) {
  const list = action === 'offer' ? STATE.tradeOffering : STATE.tradeRequesting;
  const idx = list.findIndex(p => p.id === playerId);
  if (idx >= 0) {
    list.splice(idx, 1);
  } else {
    list.push({id: playerId, name, pos});
  }
  updateTradeSlots();
}

function updateTradeSlots() {
  document.getElementById('trade-offering').innerHTML =
    STATE.tradeOffering.length ? STATE.tradeOffering.map(p =>
      `<span class="trade-player-chip" onclick="toggleTrade(${p.id},'${p.name}','${p.pos}','offer')">${p.name} (${p.pos}) <span class="remove">×</span></span>`
    ).join('') : 'Click players from your roster to offer...';

  document.getElementById('trade-requesting').innerHTML =
    STATE.tradeRequesting.length ? STATE.tradeRequesting.map(p =>
      `<span class="trade-player-chip" onclick="toggleTrade(${p.id},'${p.name}','${p.pos}','request')">${p.name} (${p.pos}) <span class="remove">×</span></span>`
    ).join('') : 'Click players from their roster to request...';
}

async function submitTrade() {
  if (!STATE.tradeOffering.length || !STATE.tradeRequesting.length) {
    document.getElementById('trade-response').innerHTML = '<p style="color:var(--red)">Select players on both sides first.</p>';
    return;
  }

  document.getElementById('trade-response').innerHTML = '<div class="loading"><span class="spinner"></span> GM is evaluating your proposal...</div>';

  const result = await fetch(`${API}/trade/propose`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      proposing_team_id: STATE.userTeamId,
      receiving_team_id: STATE.selectedTradeTeam,
      players_offered: STATE.tradeOffering.map(p => p.id),
      players_requested: STATE.tradeRequesting.map(p => p.id),
      cash_included: 0
    })
  }).then(r => r.json());

  const accepted = result.accept;
  document.getElementById('trade-response').innerHTML = `
    <div style="text-align:center;margin-bottom:12px">
      <span style="font-size:24px">${accepted ? '✅' : '❌'}</span>
      <h3 style="color:${accepted ? 'var(--green)' : 'var(--red)'}">${accepted ? 'TRADE ACCEPTED' : 'TRADE REJECTED'}</h3>
    </div>
    <div style="color:var(--text-dim);font-size:13px;margin-bottom:8px"><strong>GM says:</strong> "${result.message_to_gm || result.reasoning}"</div>
    ${result.reasoning ? `<div style="color:var(--text-muted);font-size:11px;font-style:italic">Internal reasoning: ${result.reasoning}</div>` : ''}
    ${result.counter_offer ? `<div style="color:var(--gold);margin-top:8px;font-size:12px"><strong>Counter:</strong> ${result.counter_offer}</div>` : ''}
    ${accepted ? '<button class="btn btn-primary" style="margin-top:12px;width:100%" onclick="executeTrade()">Execute Trade</button>' : ''}
  `;
}

async function executeTrade() {
  await fetch(`${API}/trade/execute`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      proposing_team_id: STATE.userTeamId,
      receiving_team_id: STATE.selectedTradeTeam,
      players_offered: STATE.tradeOffering.map(p => p.id),
      players_requested: STATE.tradeRequesting.map(p => p.id),
      cash_included: 0
    })
  });
  document.getElementById('trade-response').innerHTML = '<p style="color:var(--green);text-align:center;font-size:16px">Trade completed!</p>';
  STATE.tradeOffering = [];
  STATE.tradeRequesting = [];
  loadTradeCenter();
}

// ============================================================
// FREE AGENTS
// ============================================================
async function loadFreeAgents() {
  const content = document.getElementById('fa-content');
  content.innerHTML = '<div class="loading"><span class="spinner"></span> Loading free agents...</div>';
  const fas = await fetch(`${API}/free-agents`).then(r => r.json());
  if (!fas.length) {
    content.innerHTML = '<p style="color:var(--text-muted)">No free agents available.</p>';
    return;
  }
  content.innerHTML = `<table>
    <tr><th>Name</th><th>Pos</th><th>Age</th><th>B/T</th><th>Key Rating</th><th class="num">Asking</th><th class="num">Years</th><th>Interest</th><th></th></tr>
    ${fas.slice(0, 40).map(p => {
      const isPitcher = p.position === 'SP' || p.position === 'RP';
      const keyRat = isPitcher ? `STF:${p.stuff_rating}` : `CON:${p.contact_rating} POW:${p.power_rating}`;
      return `<tr>
        <td class="clickable" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
        <td>${p.position}</td><td>${p.age}</td><td>${p.bats}/${p.throws}</td>
        <td>${keyRat}</td>
        <td class="num">$${(p.asking_salary / 1000000).toFixed(1)}M</td>
        <td class="num">${p.asking_years}yr</td>
        <td>${p.market_interest} teams</td>
        <td><button class="btn btn-primary" onclick="signFA(${p.id}, ${p.asking_salary}, ${p.asking_years})" style="font-size:11px;padding:3px 8px">Sign</button></td>
      </tr>`;
    }).join('')}
  </table>`;
}

async function signFA(playerId, salary, years) {
  if (!STATE.userTeamId) return;
  await fetch(`${API}/free-agents/sign`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({player_id: playerId, team_id: STATE.userTeamId, salary, years})
  });
  loadFreeAgents();
}

// ============================================================
// LEADERS
// ============================================================
async function loadLeaders() {
  const stats = [
    {id: 'hr', stat: 'hr', label: 'HR'},
    {id: 'avg', stat: 'hits', label: 'Hits/AVG'},
    {id: 'rbi', stat: 'rbi', label: 'RBI'},
    {id: 'wins', stat: 'wins', label: 'W'},
    {id: 'era', stat: 'so', label: 'SO (pitching)'},
    {id: 'so', stat: 'sb', label: 'SB'},
  ];

  for (const s of stats) {
    const isBatting = ['hr', 'hits', 'rbi', 'sb'].includes(s.stat);
    const url = isBatting
      ? `${API}/leaders/batting?stat=${s.stat}&limit=10`
      : `${API}/leaders/pitching?stat=${s.stat}&limit=10`;
    const data = await fetch(url).then(r => r.json()).catch(() => []);
    const el = document.getElementById(`leaders-${s.id}`);
    el.innerHTML = data.map((p, i) => `
      <div style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--border);font-size:12px">
        <span>${i + 1}. ${p.first_name} ${p.last_name} <span style="color:var(--text-muted)">${p.abbreviation}</span></span>
        <span style="font-weight:bold">${isBatting ? p[s.stat] : (s.stat === 'wins' ? p.wins : p.so)}</span>
      </div>
    `).join('') || '<p style="color:var(--text-muted);font-size:12px">No data yet</p>';
  }
}

// ============================================================
// MESSAGES
// ============================================================
async function loadMessages() {
  const content = document.getElementById('messages-content');
  const msgs = await fetch(`${API}/messages?unread_only=false`).then(r => r.json()).catch(() => []);
  if (!msgs.length) {
    content.innerHTML = '<p style="color:var(--text-muted);padding:20px">Your inbox is empty. Messages from GMs, your owner, agents, and scouts will appear here as the season progresses.</p>';
    return;
  }
  content.innerHTML = msgs.map(m => `
    <div class="message-item ${m.is_read ? '' : 'unread'}">
      <span class="msg-sender">${m.sender_name}</span>
      <span class="msg-date">${m.game_date}</span>
      <div class="msg-body">${m.body}</div>
    </div>
  `).join('');
}

// ============================================================
// HELPERS
// ============================================================
function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T12:00:00');
  return d.toLocaleDateString('en-US', {weekday: 'short', month: 'short', day: 'numeric', year: 'numeric'});
}

function fmt(num) {
  if (!num && num !== 0) return '0';
  if (Math.abs(num) >= 1000000) return (num / 1000000).toFixed(1) + 'M';
  if (Math.abs(num) >= 1000) return (num / 1000).toFixed(0) + 'K';
  return num.toLocaleString();
}

// Close modal on escape
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

// ============================================================
// INIT
// ============================================================
async function init() {
  // Check if game has a user team set
  try {
    const state = await fetch(`${API}/game-state`).then(r => r.json());
    if (state.user_team_id) {
      STATE.userTeamId = state.user_team_id;
      document.getElementById('intro-screen').classList.remove('active');
      document.getElementById('app').classList.add('active');
      await loadGameState();
      showScreen('dashboard');
    } else {
      playIntro();
    }
  } catch (e) {
    playIntro();
  }
}

init();
