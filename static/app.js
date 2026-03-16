/* ============================================================
   FRONT OFFICE — Phase 1 Complete UI
   "Bloomberg Terminal meets Baseball Reference"
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
};

// ============================================================
// GRADE SYSTEM (20-80 → letter grades)
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
    <p>On the other end is a voice you don't recognize — an owner you've only read about. <span class="hl">"I just fired my General Manager. I've been watching you. I think you're exactly what this franchise needs."</span></p>
    <p>You're not a traditional baseball executive. You never played pro ball. You're an <span class="gold">outsider with an edge</span>. You understand systems, data, and how to build from nothing. The old guard thinks you're a joke. The owner thinks you're the future.</p>
    <p>Three teams are interested. Three owners willing to bet on you.</p>
    <p><span class="hl">Choose your franchise.</span></p>
  `;
  const choices = document.getElementById('intro-choices');
  choices.style.display = 'flex';
  choices.innerHTML = TEAMS.map((t, i) => `
    <div class="team-choice" onclick="selectTeam(${i})" id="tc-${i}">
      <h3>${t.city} ${t.name}</h3>
      <p><strong>${t.owner}</strong> — ${t.ownerDesc}</p>
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
    calendar: loadCalendar, roster: loadRoster, standings: loadStandings,
    schedule: loadSchedule, finances: loadFinances, trades: loadTrades,
    freeagents: loadFA, leaders: loadLeaders, messages: loadMessages,
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
  if (r) ticker.textContent = `Simulated ${n}d → ${r.games_played} games | ${fmtDate(r.new_date)}`;
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

  // Fetch games for this month
  const games = await api(`/schedule?limit=162&team_id=${STATE.userTeamId}`);
  const monthGames = games?.filter(g => {
    const d = new Date(g.game_date + 'T12:00:00');
    return d.getMonth() === m && d.getFullYear() === y;
  }) || [];

  // Build game lookup by day
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

  // Empty cells before first day
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

  // Sidebar: division standings + recent scores
  calHtml += '<div class="cal-sidebar">';

  // Recent scores
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

  // Division standings
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

  // Parse innings
  let innings = [];
  try { innings = JSON.parse(result?.innings_json || '[[],[]]'); } catch(e) {}
  const awayInnings = innings[0] || [];
  const homeInnings = innings[1] || [];
  const numInnings = Math.max(awayInnings.length, homeInnings.length, 9);

  // Linescore
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

  // Batting lines
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

  // Pitching lines
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
    <div style="padding:12px 16px">
      ${ls}
      ${battingTable(g.away_team_id, g.away_abbr)}
      ${battingTable(g.home_team_id, g.home_abbr)}
      ${pitchingTable(g.away_team_id, g.away_abbr)}
      ${pitchingTable(g.home_team_id, g.home_abbr)}
    </div>
  `;
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

function renderRosterTab(tab) {
  document.querySelectorAll('#s-roster .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`#s-roster .tab-btn[data-tab="${tab}"]`)?.classList.add('active');

  const data = STATE._rosterData;
  if (!data) return;
  const players = tab === 'active' ? data.active : tab === 'minors' ? data.minors : data.injured;
  const el = document.getElementById('roster-body');
  const isPitcher = p => p.position === 'SP' || p.position === 'RP';

  const pos = players.filter(p => !isPitcher(p));
  const pit = players.filter(p => isPitcher(p));

  let html = `<div style="margin-bottom:4px;font-size:11px;color:var(--text-muted)">
    Active: ${data.active_count}/26 | 40-Man: ${data.forty_man_count}/40 | IL: ${data.injured_count} | Payroll: ${fmt$(data.payroll)}
  </div>`;

  if (pos.length) {
    html += `<div class="section-title" style="margin:8px 0 4px">Position Players</div>
    <div class="table-wrap"><table>
      <tr><th class="text-col">Name</th><th class="c">Pos</th><th class="r">Age</th><th class="c">B/T</th>
      <th class="c">Con</th><th class="c">Pow</th><th class="c">Spd</th><th class="c">Fld</th><th class="c">Arm</th>
      <th class="r">Salary</th><th class="r">Yrs</th></tr>
      ${pos.map(p => `<tr>
        <td class="text-col clickable" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
        <td class="c">${p.position}</td><td class="r">${p.age}</td><td class="c">${p.bats}/${p.throws}</td>
        <td class="c">${gradeHtml(p.contact_rating)}</td><td class="c">${gradeHtml(p.power_rating)}</td>
        <td class="c">${gradeHtml(p.speed_rating)}</td><td class="c">${gradeHtml(p.fielding_rating)}</td>
        <td class="c">${gradeHtml(p.arm_rating)}</td>
        <td class="r mono">${p.annual_salary ? fmt$(p.annual_salary) : 'min'}</td>
        <td class="r">${p.years_remaining || '-'}</td>
      </tr>`).join('')}
    </table></div>`;
  }

  if (pit.length) {
    html += `<div class="section-title" style="margin:12px 0 4px">Pitchers</div>
    <div class="table-wrap"><table>
      <tr><th class="text-col">Name</th><th class="c">Pos</th><th class="r">Age</th><th class="c">T</th>
      <th class="c">Stuff</th><th class="c">Ctrl</th><th class="c">Stam</th>
      <th class="r">Salary</th><th class="r">Yrs</th></tr>
      ${pit.map(p => `<tr>
        <td class="text-col clickable" onclick="showPlayer(${p.id})">${p.first_name} ${p.last_name}</td>
        <td class="c">${p.position}</td><td class="r">${p.age}</td><td class="c">${p.throws}</td>
        <td class="c">${gradeHtml(p.stuff_rating)}</td><td class="c">${gradeHtml(p.control_rating)}</td>
        <td class="c">${gradeHtml(p.stamina_rating)}</td>
        <td class="r mono">${p.annual_salary ? fmt$(p.annual_salary) : 'min'}</td>
        <td class="r">${p.years_remaining || '-'}</td>
      </tr>`).join('')}
    </table></div>`;
  }

  if (!players.length) html = '<div class="empty-state">No players in this category</div>';
  el.innerHTML = html;
}

// ============================================================
// PLAYER MODAL
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
      </div>
    </div>
    <div class="modal-body">
      <div class="section-title">${isPit ? 'Pitching' : 'Hitting'} Grades</div>
      <div class="grades-row">${gradesHtml}</div>
      <div class="section-title" style="margin-top:12px">Personality</div>
      <div class="grades-row">${persHtml}</div>
      ${statsHtml}
      <div style="margin-top:12px">
        <button class="btn btn-primary btn-sm" onclick="genScout(${p.id})">Scout Report</button>
        <div id="scout-${p.id}" class="scouting-report" style="display:none"></div>
      </div>
    </div>
  `;
}

async function genScout(pid) {
  const el = document.getElementById('scout-' + pid);
  el.style.display = 'block';
  el.innerHTML = '<span class="spinner"></span> Scout evaluating...';
  const r = await api('/player/' + pid + '/scouting-report');
  el.innerHTML = r?.report ? `"${r.report}"` : 'Scout report unavailable.';
}

function closeModal() { document.getElementById('player-modal').style.display = 'none'; }

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
      <div class="table-wrap" style="margin-bottom:8px"><table>
        <tr><th class="text-col">Team</th><th class="r">W</th><th class="r">L</th><th class="r">Pct</th>
        <th class="r">GB</th><th class="r separator">RS</th><th class="r">RA</th><th class="r">Diff</th></tr>
        ${teams.map(t => `<tr class="${t.team_id === STATE.userTeamId ? 'user-team' : ''}">
          <td class="text-col"><strong>${t.abbreviation}</strong> ${t.name}</td>
          <td class="r">${t.wins}</td><td class="r">${t.losses}</td><td class="r">${t.pct.toFixed(3)}</td>
          <td class="r">${t.gb === 0 ? '-' : t.gb.toFixed(1)}</td>
          <td class="r separator">${t.runs_scored}</td><td class="r">${t.runs_allowed}</td>
          <td class="r ${t.diff > 0 ? 'positive' : t.diff < 0 ? 'negative' : ''}">${t.diff > 0 ? '+' : ''}${t.diff}</td>
        </tr>`).join('')}
      </table></div>`;
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
  el.innerHTML = `<div class="table-wrap"><table>
    <tr><th class="text-col">Date</th><th class="text-col">Away</th><th class="c"></th><th class="text-col">Home</th><th class="r">Score</th><th class="c"></th></tr>
    ${games.map(g => `<tr class="${g.home_team_id === STATE.userTeamId || g.away_team_id === STATE.userTeamId ? 'user-team' : ''}">
      <td class="text-col">${g.game_date}</td>
      <td class="text-col">${g.away_abbr}</td><td class="c" style="color:var(--text-muted)">@</td>
      <td class="text-col">${g.home_abbr}</td>
      <td class="r">${g.is_played ? g.away_score + '-' + g.home_score : '-'}</td>
      <td class="c">${g.is_played ? '<span class="clickable" onclick="showBoxScore(' + g.id + ')">Box</span>' : ''}</td>
    </tr>`).join('')}
  </table></div>`;
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
    <div class="card"><h3>Budget</h3>
      <div class="fin-line"><span>Farm System</span><span>${fmt$(team?.farm_budget)}</span></div>
      <div class="fin-line"><span>Medical Staff</span><span>${fmt$(team?.medical_budget)}</span></div>
      <div class="fin-line"><span>Scouting</span><span>${fmt$(team?.scouting_budget)}</span></div>
    </div>
  </div>`;
}

// ============================================================
// TRADE CENTER
// ============================================================
async function loadTrades() {
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
    ? STATE.tradeOffer.map(p => `<span class="trade-chip" onclick="toggleTrade(${p.id},'${p.name}','${p.pos}','offer')">${p.name} (${p.pos}) ×</span>`).join('')
    : 'Click players to offer...';
  document.getElementById('trade-slot-req').innerHTML = STATE.tradeRequest.length
    ? STATE.tradeRequest.map(p => `<span class="trade-chip" onclick="toggleTrade(${p.id},'${p.name}','${p.pos}','req')">${p.name} (${p.pos}) ×</span>`).join('')
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
// FREE AGENTS
// ============================================================
async function loadFA() {
  const el = document.getElementById('fa-body');
  el.innerHTML = '<div class="loading"><span class="spinner"></span></div>';
  const fas = await api('/free-agents');
  if (!fas?.length) { el.innerHTML = '<div class="empty-state">No free agents available</div>'; return; }
  el.innerHTML = `<div class="table-wrap"><table>
    <tr><th class="text-col">Name</th><th class="c">Pos</th><th class="r">Age</th><th class="c">B/T</th>
    <th class="c">Key</th><th class="r">Ask $</th><th class="r">Yrs</th><th class="r">Teams</th><th></th></tr>
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
  </table></div>`;
}

async function signFA(pid, sal, yrs) {
  if (!STATE.userTeamId) return;
  await post('/free-agents/sign', { player_id: pid, team_id: STATE.userTeamId, salary: sal, years: yrs });
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
      return `<div class="leader-row">
        <span class="leader-rank">${i + 1}.</span>
        <span class="leader-name clickable" onclick="showPlayer(${p.player_id || 0})">${p.first_name} ${p.last_name}</span>
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
// INIT
// ============================================================
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

async function init() {
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
