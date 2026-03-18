/**
 * Front Office - 8-Bit Baseball Game Viewer
 * Renders play-by-play data as retro pixel art animation on Canvas.
 */

const RETRO = {
  canvas: null,
  ctx: null,
  plays: [],
  currentPlay: 0,
  playing: false,
  interval: null,
  speed: 2000, // ms between plays
  homeScore: 0,
  awayScore: 0,
  inning: 1,
  halfInning: 'top',
  outs: 0,
  bases: [false, false, false], // 1st, 2nd, 3rd

  // Color palette (NES-inspired)
  COLORS: {
    grass: '#2d8b46',
    dirt: '#c4853e',
    darkDirt: '#a06830',
    sky: '#1a1a2e',
    white: '#ffffff',
    yellow: '#ffe66d',
    red: '#e63946',
    blue: '#4a90d9',
    gray: '#888888',
    darkGreen: '#1d6b30',
    foul: '#8b7355',
    base: '#ffffff',
    mound: '#c4853e',
  },
};

function initRetroGame(scheduleId, homeAbbr, awayAbbr, homeName, awayName) {
  RETRO.canvas = document.getElementById('retro-canvas');
  RETRO.ctx = RETRO.canvas.getContext('2d');
  RETRO.homeAbbr = homeAbbr;
  RETRO.awayAbbr = awayAbbr;
  RETRO.homeScore = 0;
  RETRO.awayScore = 0;
  RETRO.inning = 1;
  RETRO.halfInning = 'top';
  RETRO.outs = 0;
  RETRO.bases = [false, false, false];
  RETRO.currentPlay = 0;
  RETRO.playing = false;

  document.getElementById('retro-modal').style.display = 'flex';
  document.getElementById('retro-away').textContent = awayAbbr;
  document.getElementById('retro-home').textContent = homeAbbr;
  document.getElementById('retro-score').textContent = '0 - 0';
  document.getElementById('retro-play-btn').textContent = '\u25B6 Play';
  document.getElementById('retro-speed-btn').textContent = '1x';
  RETRO.speed = 2000;

  // Load play-by-play data
  loadRetroPlays(scheduleId);

  // Draw initial field
  drawField();
}

async function loadRetroPlays(scheduleId) {
  const data = await api('/game/' + scheduleId + '/play-by-play');
  if (data && Array.isArray(data) && data.length > 0) {
    RETRO.plays = data;
    document.getElementById('retro-situation').textContent =
      RETRO.plays.length + ' plays loaded. Press Play to watch!';
  } else if (data && data.plays) {
    RETRO.plays = data.plays;
    document.getElementById('retro-situation').textContent =
      RETRO.plays.length + ' plays loaded. Press Play to watch!';
  } else if (data && data.play_by_play) {
    try {
      RETRO.plays = typeof data.play_by_play === 'string' ?
        JSON.parse(data.play_by_play) : data.play_by_play;
    } catch(e) {
      RETRO.plays = [];
    }
    document.getElementById('retro-situation').textContent =
      RETRO.plays.length + ' plays loaded. Press Play to watch!';
  } else {
    RETRO.plays = [];
    document.getElementById('retro-situation').textContent = 'No play-by-play data available';
  }
}

function drawField() {
  const ctx = RETRO.ctx;
  const W = RETRO.canvas.width;
  const H = RETRO.canvas.height;

  // Sky background
  ctx.fillStyle = RETRO.COLORS.sky;
  ctx.fillRect(0, 0, W, H);

  // Outfield grass (large arc)
  ctx.fillStyle = RETRO.COLORS.grass;
  ctx.beginPath();
  ctx.arc(W/2, H - 40, 320, Math.PI, 0, false);
  ctx.fill();

  // Darker grass pattern (alternating strips for mowing effect)
  ctx.fillStyle = RETRO.COLORS.darkGreen;
  for (var i = 0; i < 6; i++) {
    ctx.beginPath();
    ctx.arc(W/2, H - 40, 320 - i * 50, Math.PI + 0.1, -0.1, false);
    ctx.arc(W/2, H - 40, 320 - i * 50 - 20, -0.1, Math.PI + 0.1, true);
    ctx.fill();
  }

  // Infield dirt diamond
  ctx.fillStyle = RETRO.COLORS.dirt;
  ctx.beginPath();
  ctx.moveTo(W/2, H - 180);     // home plate area
  ctx.lineTo(W/2 + 130, H - 290); // first base
  ctx.lineTo(W/2, H - 400);       // second base
  ctx.lineTo(W/2 - 130, H - 290); // third base
  ctx.closePath();
  ctx.fill();

  // Infield grass
  ctx.fillStyle = RETRO.COLORS.grass;
  ctx.beginPath();
  ctx.moveTo(W/2, H - 220);
  ctx.lineTo(W/2 + 90, H - 300);
  ctx.lineTo(W/2, H - 370);
  ctx.lineTo(W/2 - 90, H - 300);
  ctx.closePath();
  ctx.fill();

  // Pitcher's mound
  ctx.fillStyle = RETRO.COLORS.mound;
  ctx.beginPath();
  ctx.arc(W/2, H - 300, 12, 0, Math.PI * 2);
  ctx.fill();

  // Mound rubber
  ctx.fillStyle = RETRO.COLORS.white;
  ctx.fillRect(W/2 - 4, H - 302, 8, 3);

  // Base paths (white lines)
  ctx.strokeStyle = RETRO.COLORS.white;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(W/2, H - 180);
  ctx.lineTo(W/2 + 130, H - 290);
  ctx.lineTo(W/2, H - 400);
  ctx.lineTo(W/2 - 130, H - 290);
  ctx.closePath();
  ctx.stroke();

  // Foul lines extending to outfield
  ctx.beginPath();
  ctx.moveTo(W/2, H - 180);
  ctx.lineTo(W/2 + 300, H - 470);
  ctx.moveTo(W/2, H - 180);
  ctx.lineTo(W/2 - 300, H - 470);
  ctx.stroke();

  // Home plate (pentagon)
  ctx.fillStyle = RETRO.COLORS.white;
  ctx.beginPath();
  ctx.moveTo(W/2, H - 175);
  ctx.lineTo(W/2 + 8, H - 180);
  ctx.lineTo(W/2 + 8, H - 188);
  ctx.lineTo(W/2, H - 192);
  ctx.lineTo(W/2 - 8, H - 188);
  ctx.lineTo(W/2 - 8, H - 180);
  ctx.closePath();
  ctx.fill();

  // Bases
  drawBase(W/2 + 130, H - 290, RETRO.bases[0]); // 1st
  drawBase(W/2, H - 400, RETRO.bases[1]);         // 2nd
  drawBase(W/2 - 130, H - 290, RETRO.bases[2]);   // 3rd

  // Draw players (simple pixel figures)
  drawPixelPlayer(W/2 - 4, H - 160, RETRO.COLORS.white, 'batter');  // Batter
  drawPixelPlayer(W/2 - 4, H - 308, RETRO.COLORS.red, 'pitcher');   // Pitcher
  drawPixelPlayer(W/2 + 6, H - 166, RETRO.COLORS.gray, 'catcher');  // Catcher

  // Fielders
  drawPixelPlayer(W/2 + 135, H - 295, RETRO.COLORS.blue, 'fielder'); // 1B
  drawPixelPlayer(W/2 + 60, H - 340, RETRO.COLORS.blue, 'fielder');  // 2B
  drawPixelPlayer(W/2 - 60, H - 340, RETRO.COLORS.blue, 'fielder');  // SS
  drawPixelPlayer(W/2 - 135, H - 295, RETRO.COLORS.blue, 'fielder'); // 3B
  drawPixelPlayer(W/2 - 160, H - 430, RETRO.COLORS.blue, 'fielder'); // LF
  drawPixelPlayer(W/2, H - 450, RETRO.COLORS.blue, 'fielder');       // CF
  drawPixelPlayer(W/2 + 160, H - 430, RETRO.COLORS.blue, 'fielder'); // RF

  // Runners on base
  if (RETRO.bases[0]) drawPixelPlayer(W/2 + 120, H - 285, RETRO.COLORS.yellow, 'runner');
  if (RETRO.bases[1]) drawPixelPlayer(W/2 - 10, H - 395, RETRO.COLORS.yellow, 'runner');
  if (RETRO.bases[2]) drawPixelPlayer(W/2 - 120, H - 285, RETRO.COLORS.yellow, 'runner');

  // Scoreboard
  drawScoreboard();

  // Outs indicator
  drawOuts();
}

function drawBase(x, y, occupied) {
  var ctx = RETRO.ctx;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(Math.PI / 4);
  ctx.fillStyle = occupied ? RETRO.COLORS.yellow : RETRO.COLORS.white;
  ctx.fillRect(-7, -7, 14, 14);
  ctx.restore();
}

function drawPixelPlayer(x, y, color, type) {
  var ctx = RETRO.ctx;
  var s = 3; // pixel size

  // Head
  ctx.fillStyle = '#ffd5b0';
  ctx.fillRect(x + s, y - s*4, s*2, s*2);

  // Body
  ctx.fillStyle = color;
  ctx.fillRect(x, y - s*2, s*4, s*3);

  // Legs
  ctx.fillStyle = '#333';
  ctx.fillRect(x, y + s, s*1.5, s*2);
  ctx.fillRect(x + s*2.5, y + s, s*1.5, s*2);

  // Cap
  ctx.fillStyle = color;
  ctx.fillRect(x, y - s*5, s*4, s);
}

function drawScoreboard() {
  var ctx = RETRO.ctx;
  var W = RETRO.canvas.width;

  // Scoreboard background
  ctx.fillStyle = '#0a0a1a';
  ctx.fillRect(W - 180, 10, 170, 70);
  ctx.strokeStyle = '#333';
  ctx.lineWidth = 1;
  ctx.strokeRect(W - 180, 10, 170, 70);

  // Team labels and scores
  ctx.font = '14px monospace';
  ctx.fillStyle = '#aaa';
  ctx.fillText(RETRO.awayAbbr || 'AWY', W - 170, 35);
  ctx.fillText(RETRO.homeAbbr || 'HME', W - 170, 60);

  ctx.fillStyle = RETRO.COLORS.yellow;
  ctx.font = 'bold 16px monospace';
  ctx.fillText(String(RETRO.awayScore), W - 40, 35);
  ctx.fillText(String(RETRO.homeScore), W - 40, 60);

  // Inning
  ctx.fillStyle = '#aaa';
  ctx.font = '12px monospace';
  var half = RETRO.halfInning === 'top' ? '\u25B2' : '\u25BC';
  ctx.fillText(half + ' ' + RETRO.inning, W - 100, 72);
}

function drawOuts() {
  var ctx = RETRO.ctx;

  // Outs circles
  ctx.font = '11px monospace';
  ctx.fillStyle = '#aaa';
  ctx.fillText('OUT', 15, 25);

  for (var i = 0; i < 3; i++) {
    ctx.beginPath();
    ctx.arc(25 + i * 18, 40, 6, 0, Math.PI * 2);
    ctx.fillStyle = i < RETRO.outs ? RETRO.COLORS.red : '#333';
    ctx.fill();
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 1;
    ctx.stroke();
  }
}

function processPlay(play) {
  // Parse play data and update state
  var desc = (typeof play === 'string' ? play : play.description || play.play || play.text || play.outcome || '').toLowerCase();

  // Update inning/half from play data if available
  if (play.inning) {
    // inning field may be like "Top 3" or "Bot 5" or just a number
    var inningStr = String(play.inning);
    var inningMatch = inningStr.match(/(\d+)/);
    if (inningMatch) RETRO.inning = parseInt(inningMatch[1]);
    if (/top/i.test(inningStr)) RETRO.halfInning = 'top';
    else if (/bot/i.test(inningStr) || /bottom/i.test(inningStr)) RETRO.halfInning = 'bottom';
  }
  if (play.half) RETRO.halfInning = play.half;
  if (play.outs !== undefined) RETRO.outs = play.outs;

  // Parse scoring
  if (play.home_score !== undefined) RETRO.homeScore = play.home_score;
  if (play.away_score !== undefined) RETRO.awayScore = play.away_score;

  // Parse base runners from play description
  if (desc.includes('home run') || desc.includes('homer')) {
    RETRO.bases = [false, false, false];
    flashAnimation('HR!', RETRO.COLORS.yellow);
  } else if (desc.includes('triple')) {
    RETRO.bases = [false, false, true];
    flashAnimation('3B!', RETRO.COLORS.yellow);
  } else if (desc.includes('double')) {
    RETRO.bases = [false, true, false];
    flashAnimation('2B!', RETRO.COLORS.yellow);
  } else if (desc.includes('single') || desc.includes('singled')) {
    RETRO.bases[0] = true;
    flashAnimation('HIT!', RETRO.COLORS.white);
  } else if (desc.includes('walk') || desc.includes('walked')) {
    RETRO.bases[0] = true;
    flashAnimation('BB', RETRO.COLORS.white);
  } else if (desc.includes('strikeout') || desc.includes('struck out')) {
    flashAnimation('K', RETRO.COLORS.red);
  } else if (desc.includes('ground') || desc.includes('fly') || desc.includes('pop')) {
    flashAnimation('OUT', RETRO.COLORS.red);
  } else if (desc.includes('error')) {
    RETRO.bases[0] = true;
    flashAnimation('E!', RETRO.COLORS.red);
  } else if (desc.includes('stolen base') || desc.includes('stole')) {
    flashAnimation('SB!', RETRO.COLORS.yellow);
  }

  // Update score display
  document.getElementById('retro-score').textContent =
    RETRO.awayScore + ' - ' + RETRO.homeScore;

  // Update info bar
  var half = RETRO.halfInning === 'top' ? 'Top' : 'Bot';
  document.getElementById('retro-count').textContent =
    half + ' ' + RETRO.inning + ' | ' + RETRO.outs + ' out';

  var playText = typeof play === 'string' ? play :
    (play.description || play.play || play.text || play.outcome || '');
  document.getElementById('retro-situation').textContent = playText;

  // Redraw field
  drawField();
}

function flashAnimation(text, color) {
  var ctx = RETRO.ctx;
  var W = RETRO.canvas.width;
  var H = RETRO.canvas.height;

  // Flash text in center
  ctx.fillStyle = color;
  ctx.font = 'bold 36px monospace';
  ctx.textAlign = 'center';
  ctx.fillText(text, W/2, H/2 - 50);
  ctx.textAlign = 'start';
}

function retroPlayPause() {
  if (RETRO.playing) {
    RETRO.playing = false;
    clearInterval(RETRO.interval);
    document.getElementById('retro-play-btn').textContent = '\u25B6 Play';
  } else {
    RETRO.playing = true;
    document.getElementById('retro-play-btn').textContent = '\u23F8 Pause';
    RETRO.interval = setInterval(function() {
      if (RETRO.currentPlay < RETRO.plays.length) {
        processPlay(RETRO.plays[RETRO.currentPlay]);
        RETRO.currentPlay++;
      } else {
        retroPlayPause(); // Stop at end
        document.getElementById('retro-situation').textContent = 'GAME OVER - FINAL';
      }
    }, RETRO.speed);
  }
}

function retroSpeed() {
  var speeds = [2000, 1000, 500, 200];
  var labels = ['1x', '2x', '4x', '10x'];
  var idx = speeds.indexOf(RETRO.speed);
  var next = (idx + 1) % speeds.length;
  RETRO.speed = speeds[next];
  document.getElementById('retro-speed-btn').textContent = labels[next];

  if (RETRO.playing) {
    clearInterval(RETRO.interval);
    RETRO.interval = setInterval(function() {
      if (RETRO.currentPlay < RETRO.plays.length) {
        processPlay(RETRO.plays[RETRO.currentPlay]);
        RETRO.currentPlay++;
      } else {
        retroPlayPause();
      }
    }, RETRO.speed);
  }
}

function retroSkip() {
  // Skip to next half-inning
  var currentHalf = RETRO.halfInning;
  var currentInning = RETRO.inning;
  while (RETRO.currentPlay < RETRO.plays.length) {
    var play = RETRO.plays[RETRO.currentPlay];
    processPlay(play);
    RETRO.currentPlay++;
    if (RETRO.inning !== currentInning || RETRO.halfInning !== currentHalf) break;
  }
}

function closeRetroGame() {
  RETRO.playing = false;
  if (RETRO.interval) clearInterval(RETRO.interval);
  document.getElementById('retro-modal').style.display = 'none';
}
