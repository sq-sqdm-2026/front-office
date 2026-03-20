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

  RETRO.scheduleId = scheduleId;

  // Load play-by-play data
  loadRetroPlays(scheduleId);

  // Draw initial field
  drawField();
}

async function loadRetroPlays(scheduleId) {
  document.getElementById('retro-situation').textContent = 'Loading play-by-play...';
  const data = await api('/game/' + scheduleId + '/play-by-play');
  if (data && Array.isArray(data) && data.length > 0) {
    RETRO.plays = data;
  } else if (data && data.plays) {
    RETRO.plays = data.plays;
  } else if (data && data.play_by_play) {
    try {
      RETRO.plays = typeof data.play_by_play === 'string' ?
        JSON.parse(data.play_by_play) : data.play_by_play;
    } catch(e) {
      RETRO.plays = [];
    }
  } else {
    RETRO.plays = [];
  }
  if (RETRO.plays.length > 0) {
    document.getElementById('retro-situation').textContent =
      RETRO.plays.length + ' plays loaded. Press Play to watch!';
  } else {
    document.getElementById('retro-situation').textContent = 'No play-by-play data. Sim a game first!';
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
  // Handle both old format ({type, player}) and new format ({description, inning, half, outs, home_score, away_score})
  var desc = '';
  var playType = '';

  if (typeof play === 'string') {
    desc = play;
  } else {
    desc = play.description || play.play || play.text || play.outcome || '';
    playType = play.type || '';
  }
  var descLower = desc.toLowerCase();

  // Update inning/half from play data
  if (play.inning) {
    var inningStr = String(play.inning);
    var inningMatch = inningStr.match(/(\d+)/);
    if (inningMatch) RETRO.inning = parseInt(inningMatch[1]);
    if (/top/i.test(inningStr)) RETRO.halfInning = 'top';
    else if (/bot/i.test(inningStr) || /bottom/i.test(inningStr)) RETRO.halfInning = 'bottom';
  }
  if (play.half) RETRO.halfInning = play.half;
  if (play.outs !== undefined) RETRO.outs = play.outs;

  // Update scores from play data
  if (play.home_score !== undefined) RETRO.homeScore = play.home_score;
  if (play.away_score !== undefined) RETRO.awayScore = play.away_score;

  // Skip end-of-half markers (just update state, no animation)
  if (playType === 'end_half') {
    RETRO.bases = [false, false, false];
    RETRO.outs = 0;
    _updateRetroDisplay(desc, null);
    drawField();
    return;
  }

  // Determine flash text from play type or description
  var flashText = null;
  if (playType === 'home_run' || descLower.includes('home run') || descLower.includes('homer')) {
    RETRO.bases = [false, false, false];
    flashText = 'HR!';
    flashAnimation('HR!', RETRO.COLORS.yellow);
    playRetroSfx('homerun');
  } else if (playType === 'triple' || descLower.includes('triple')) {
    RETRO.bases = [false, false, true];
    flashText = '3B!';
    flashAnimation('3B!', RETRO.COLORS.yellow);
    playRetroSfx('hit');
  } else if (playType === 'double' || descLower.includes('double')) {
    // Advance runners
    if (RETRO.bases[0]) RETRO.bases[2] = true;
    RETRO.bases[1] = true;
    RETRO.bases[0] = false;
    flashText = '2B!';
    flashAnimation('2B!', RETRO.COLORS.yellow);
    playRetroSfx('hit');
  } else if (playType === 'single' || descLower.includes('single') || descLower.includes('singled')) {
    // Advance runners
    if (RETRO.bases[1]) RETRO.bases[2] = true;
    if (RETRO.bases[0]) RETRO.bases[1] = true;
    RETRO.bases[0] = true;
    flashText = 'HIT!';
    flashAnimation('HIT!', RETRO.COLORS.white);
    playRetroSfx('hit');
  } else if (playType === 'walk' || descLower.includes('walk') || descLower.includes('hit by pitch')) {
    // Advance runners on walk (force)
    if (RETRO.bases[0] && RETRO.bases[1]) RETRO.bases[2] = true;
    if (RETRO.bases[0]) RETRO.bases[1] = true;
    RETRO.bases[0] = true;
    flashText = 'BB';
    flashAnimation('BB', RETRO.COLORS.white);
  } else if (playType === 'strikeout' || descLower.includes('strikeout') || descLower.includes('struck out')) {
    flashText = 'K';
    flashAnimation('K', RETRO.COLORS.red);
    playRetroSfx('strikeout');
  } else if (playType === 'out' || descLower.includes('ground') || descLower.includes('fly') || descLower.includes('pop') || descLower.includes('lined out')) {
    flashText = 'OUT';
    flashAnimation('OUT', RETRO.COLORS.red);
    playRetroSfx('out');
  } else if (descLower.includes('error')) {
    RETRO.bases[0] = true;
    flashText = 'E!';
    flashAnimation('E!', RETRO.COLORS.red);
  } else if (descLower.includes('stolen base') || descLower.includes('stole')) {
    flashText = 'SB!';
    flashAnimation('SB!', RETRO.COLORS.yellow);
    playRetroSfx('hit');
  }

  // Build display text with commentary
  var commentary = flashText ? getCommentary(flashText) : '';
  _updateRetroDisplay(desc, commentary);

  // Redraw field
  drawField();
}

function _updateRetroDisplay(playText, commentary) {
  // Update score display with flash effect
  var scoreEl = document.getElementById('retro-score');
  var oldScore = scoreEl.textContent;
  var newScore = RETRO.awayScore + ' - ' + RETRO.homeScore;
  scoreEl.textContent = newScore;
  if (oldScore !== newScore) {
    scoreEl.classList.remove('score-change');
    void scoreEl.offsetWidth;
    scoreEl.classList.add('score-change');
  }

  // Update inning/outs info
  var half = RETRO.halfInning === 'top' ? 'Top' : 'Bot';
  document.getElementById('retro-count').textContent =
    half + ' ' + RETRO.inning + ' | ' + RETRO.outs + ' out';

  // Update situation text WITH commentary (don't overwrite!)
  var sitEl = document.getElementById('retro-situation');
  if (sitEl) {
    if (commentary) {
      sitEl.innerHTML = playText + ' <span style="color:#ffe66d;font-style:italic">' + commentary + '</span>';
    } else {
      sitEl.textContent = playText;
    }
  }
}

function flashAnimation(text, color) {
  var ctx = RETRO.ctx;
  var W = RETRO.canvas.width;
  var H = RETRO.canvas.height;

  // Draw glow background behind text
  var gradient = ctx.createRadialGradient(W/2, H/2 - 60, 10, W/2, H/2 - 60, 100);
  gradient.addColorStop(0, color + '44');
  gradient.addColorStop(1, 'transparent');
  ctx.fillStyle = gradient;
  ctx.fillRect(W/2 - 120, H/2 - 120, 240, 120);

  // Shadow
  ctx.fillStyle = '#000';
  ctx.font = 'bold 42px monospace';
  ctx.textAlign = 'center';
  ctx.fillText(text, W/2 + 2, H/2 - 48);

  // Main text
  ctx.fillStyle = color;
  ctx.fillText(text, W/2, H/2 - 50);
  ctx.textAlign = 'start';

  // Screen shake for big plays
  if (text === 'HR!' || text === '3B!') {
    var canvas = RETRO.canvas;
    var origTransform = canvas.style.transform || '';
    var shakes = [
      {x: -4, y: 2}, {x: 4, y: -2}, {x: -3, y: -3},
      {x: 3, y: 1}, {x: -2, y: 2}, {x: 0, y: 0}
    ];
    shakes.forEach(function(s, i) {
      setTimeout(function() {
        canvas.style.transform = origTransform + ' translate(' + s.x + 'px,' + s.y + 'px)';
      }, i * 50);
    });
  }

  // Draw firework particles for home runs
  if (text === 'HR!') {
    drawFireworks(ctx, W, H);
  }
}

function drawFireworks(ctx, W, H) {
  var colors = ['#ffe66d', '#e63946', '#4a90d9', '#2d8b46', '#fff'];
  for (var burst = 0; burst < 3; burst++) {
    var cx = W * 0.2 + Math.random() * W * 0.6;
    var cy = 30 + Math.random() * 80;
    for (var i = 0; i < 12; i++) {
      var angle = (Math.PI * 2 * i) / 12;
      var dist = 15 + Math.random() * 25;
      var px = cx + Math.cos(angle) * dist;
      var py = cy + Math.sin(angle) * dist;
      ctx.fillStyle = colors[Math.floor(Math.random() * colors.length)];
      ctx.fillRect(px - 2, py - 2, 4, 4);
    }
  }
}

function retroPlayPause() {
  if (RETRO.playing) {
    RETRO.playing = false;
    clearInterval(RETRO.interval);
    stopRetroBGM();
    document.getElementById('retro-play-btn').textContent = '\u25B6 Play';
  } else {
    RETRO.playing = true;
    document.getElementById('retro-play-btn').textContent = '\u23F8 Pause';
    initRetroAudio();
    startRetroBGM();
    RETRO.interval = setInterval(function() {
      if (RETRO.currentPlay < RETRO.plays.length) {
        processPlay(RETRO.plays[RETRO.currentPlay]);
        RETRO.currentPlay++;
      } else {
        retroPlayPause(); // Stop at end
        document.getElementById('retro-situation').textContent = 'GAME OVER - FINAL';
        drawGameOver();
        playRetroSfx(RETRO.homeScore > RETRO.awayScore ? 'gameover_win' : 'gameover_loss');
        // Mark game as watched for spoiler-free mode
        if (typeof markGameWatched === 'function' && RETRO.scheduleId) {
          markGameWatched(RETRO.scheduleId);
        }
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
  // Stop music
  if (RETRO.audioCtx) {
    try { RETRO.audioCtx.close(); } catch(e) {}
    RETRO.audioCtx = null;
  }
  if (RETRO.musicInterval) { clearInterval(RETRO.musicInterval); RETRO.musicInterval = null; }
}

// ============================================================
// GAME OVER SCREEN
// ============================================================
function drawGameOver() {
  var ctx = RETRO.ctx;
  var W = RETRO.canvas.width;
  var H = RETRO.canvas.height;

  // Dim the field
  ctx.fillStyle = 'rgba(0,0,0,0.6)';
  ctx.fillRect(0, 0, W, H);

  // Game Over box
  ctx.fillStyle = '#0a0a1a';
  ctx.fillRect(W/2 - 160, H/2 - 80, 320, 160);
  ctx.strokeStyle = RETRO.COLORS.yellow;
  ctx.lineWidth = 3;
  ctx.strokeRect(W/2 - 160, H/2 - 80, 320, 160);

  ctx.textAlign = 'center';
  ctx.fillStyle = RETRO.COLORS.yellow;
  ctx.font = 'bold 28px monospace';
  ctx.fillText('GAME OVER', W/2, H/2 - 40);

  ctx.font = 'bold 20px monospace';
  ctx.fillStyle = '#fff';
  ctx.fillText(RETRO.awayAbbr + '  ' + RETRO.awayScore + '  -  ' + RETRO.homeScore + '  ' + RETRO.homeAbbr, W/2, H/2);

  var winner = RETRO.homeScore > RETRO.awayScore ? RETRO.homeAbbr :
               RETRO.awayScore > RETRO.homeScore ? RETRO.awayAbbr : 'TIE';
  ctx.font = '14px monospace';
  ctx.fillStyle = RETRO.COLORS.yellow;
  ctx.fillText(winner + ' WINS!', W/2, H/2 + 35);

  ctx.font = '11px monospace';
  ctx.fillStyle = '#888';
  ctx.fillText('Click anywhere to close', W/2, H/2 + 60);
  ctx.textAlign = 'start';

  // Fireworks for the win
  drawFireworks(ctx, W, H);
}

// ============================================================
// CHIPTUNE MUSIC ENGINE (Web Audio API)
// ============================================================
const RETRO_NOTES = {
  C4: 261.63, D4: 293.66, E4: 329.63, F4: 349.23, G4: 392.00,
  A4: 440.00, B4: 493.88, C5: 523.25, D5: 587.33, E5: 659.25,
  F5: 698.46, G5: 783.99, A5: 880.00
};

// Baseball organ riff sequences (each note is [freq, duration_ms])
const RETRO_SONGS = {
  charge: [[RETRO_NOTES.G4,150],[RETRO_NOTES.C5,150],[RETRO_NOTES.E5,150],[RETRO_NOTES.G5,300],[RETRO_NOTES.E5,150],[RETRO_NOTES.G5,450]],
  strikeout: [[RETRO_NOTES.E5,120],[RETRO_NOTES.D5,120],[RETRO_NOTES.C5,300]],
  homerun: [[RETRO_NOTES.C5,100],[RETRO_NOTES.E5,100],[RETRO_NOTES.G5,100],[RETRO_NOTES.C5,100],[RETRO_NOTES.E5,100],[RETRO_NOTES.G5,100],[RETRO_NOTES.A5,400]],
  walkup: [[RETRO_NOTES.C4,200],[RETRO_NOTES.E4,200],[RETRO_NOTES.G4,200],[RETRO_NOTES.C5,400]],
  out: [[RETRO_NOTES.G4,150],[RETRO_NOTES.E4,200]],
  hit: [[RETRO_NOTES.C5,100],[RETRO_NOTES.E5,150]],
  gameover_win: [[RETRO_NOTES.C5,200],[RETRO_NOTES.E5,200],[RETRO_NOTES.G5,200],[RETRO_NOTES.C5,150],[RETRO_NOTES.E5,150],[RETRO_NOTES.G5,150],[RETRO_NOTES.A5,150],[RETRO_NOTES.G5,150],[RETRO_NOTES.A5,400]],
  gameover_loss: [[RETRO_NOTES.E4,300],[RETRO_NOTES.D4,300],[RETRO_NOTES.C4,600]],
};

// Background organ loop
const RETRO_BGM = [
  [RETRO_NOTES.C4,400],[RETRO_NOTES.E4,400],[RETRO_NOTES.G4,400],[RETRO_NOTES.E4,400],
  [RETRO_NOTES.F4,400],[RETRO_NOTES.A4,400],[RETRO_NOTES.G4,400],[RETRO_NOTES.E4,400],
  [RETRO_NOTES.D4,400],[RETRO_NOTES.F4,400],[RETRO_NOTES.E4,400],[RETRO_NOTES.C4,400],
  [0,800], // pause
];

function initRetroAudio() {
  if (RETRO.audioCtx) return;
  try {
    RETRO.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    RETRO.masterGain = RETRO.audioCtx.createGain();
    RETRO.masterGain.gain.value = 0.12;
    RETRO.masterGain.connect(RETRO.audioCtx.destination);
    RETRO.musicEnabled = true;
  } catch(e) {
    RETRO.musicEnabled = false;
  }
}

function playChipNote(freq, duration, startTime, waveType) {
  if (!RETRO.audioCtx || !RETRO.musicEnabled || freq === 0) return;
  var osc = RETRO.audioCtx.createOscillator();
  var gain = RETRO.audioCtx.createGain();
  osc.type = waveType || 'square';
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.3, startTime);
  gain.gain.exponentialRampToValueAtTime(0.01, startTime + duration / 1000);
  osc.connect(gain);
  gain.connect(RETRO.masterGain);
  osc.start(startTime);
  osc.stop(startTime + duration / 1000);
}

function playRetroSfx(name) {
  if (!RETRO.audioCtx) initRetroAudio();
  if (!RETRO.musicEnabled) return;
  var song = RETRO_SONGS[name];
  if (!song) return;
  var t = RETRO.audioCtx.currentTime;
  song.forEach(function(note) {
    playChipNote(note[0], note[1], t, 'square');
    t += note[1] / 1000;
  });
}

function startRetroBGM() {
  if (!RETRO.audioCtx) initRetroAudio();
  if (!RETRO.musicEnabled || RETRO.musicInterval) return;
  var noteIdx = 0;
  function playNextBGMNote() {
    if (!RETRO.playing || !RETRO.musicEnabled) return;
    var note = RETRO_BGM[noteIdx % RETRO_BGM.length];
    if (note[0] > 0) {
      playChipNote(note[0], note[1] * 0.8, RETRO.audioCtx.currentTime, 'triangle');
    }
    noteIdx++;
  }
  RETRO.musicInterval = setInterval(playNextBGMNote, 400);
}

function stopRetroBGM() {
  if (RETRO.musicInterval) {
    clearInterval(RETRO.musicInterval);
    RETRO.musicInterval = null;
  }
}

function toggleRetroMusic() {
  RETRO.musicEnabled = !RETRO.musicEnabled;
  var btn = document.getElementById('retro-music-btn');
  if (btn) btn.textContent = RETRO.musicEnabled ? '\uD83D\uDD0A' : '\uD83D\uDD07';
  if (!RETRO.musicEnabled) stopRetroBGM();
  else if (RETRO.playing) startRetroBGM();
}

// ============================================================
// RETRO COMMENTARY ENGINE
// ============================================================
const COMMENTARY = {
  'HR!': [
    'GONE! That ball is outta here!',
    'Kiss it goodbye! Home run!',
    'He crushed that one! Way back!',
    'BOOM! That\'s a no-doubter!',
    'High fly ball... GOING... GONE!',
  ],
  '3B!': [
    'He\'s going for three! Triple!',
    'Racing around the bases! A stand-up triple!',
    'Off the wall! He legs out a triple!',
  ],
  '2B!': [
    'Gapper! That\'ll be a double!',
    'Off the wall for a double!',
    'He slides into second with a double!',
  ],
  'HIT!': [
    'Base hit!', 'Clean single through the infield.',
    'He pokes one into the outfield.', 'Single!',
  ],
  'K': [
    'STRUCK HIM OUT!', 'K! He goes down swinging.',
    'Called strike three! Sit down!', 'Whiff! Struck out.',
  ],
  'OUT': [
    'Routine play, one down.', 'That\'s an out.',
    'Fielded cleanly for the out.', 'Nothing doing there.',
  ],
  'BB': [
    'Take your base.', 'Ball four, he walks.',
    'Free pass issued.', 'Walk.',
  ],
  'SB!': [
    'He stole it! Safe!', 'He\'s got the stolen base!',
    'Good jump! Stolen base!',
  ],
  'E!': [
    'Error! The throw goes wide!',
    'Oh no, he boots it! Error!',
    'Misplayed! That\'s an error!',
  ],
};

function getCommentary(flashText) {
  var lines = COMMENTARY[flashText];
  if (!lines) return '';
  return lines[Math.floor(Math.random() * lines.length)];
}

// ============================================================
// IN-GAME MESSAGING (Talk to coaches, reporters, owners)
// ============================================================
function showRetroMessagePanel() {
  var panel = document.getElementById('retro-msg-panel');
  if (panel) { panel.style.display = panel.style.display === 'none' ? 'block' : 'none'; return; }

  panel = document.createElement('div');
  panel.id = 'retro-msg-panel';
  panel.style.cssText = 'position:absolute;bottom:60px;right:10px;width:280px;background:#0a0a1a;border:2px solid #333;border-radius:4px;padding:8px;font-family:monospace;font-size:11px;color:#ccc;z-index:1000;max-height:200px;overflow-y:auto;';
  panel.innerHTML = `
    <div style="color:#ffe66d;font-weight:bold;margin-bottom:6px;border-bottom:1px solid #333;padding-bottom:4px;">IN-GAME MESSAGES</div>
    <div id="retro-msg-log" style="max-height:120px;overflow-y:auto;margin-bottom:6px;"></div>
    <div style="display:flex;gap:4px;">
      <select id="retro-msg-to" style="flex:0 0 80px;background:#111;color:#ccc;border:1px solid #333;font-family:monospace;font-size:10px;padding:2px;">
        <option value="coach">Manager</option>
        <option value="reporter">Reporter</option>
        <option value="owner">Owner</option>
        <option value="dugout">Dugout</option>
      </select>
      <input id="retro-msg-input" type="text" placeholder="Type message..." style="flex:1;background:#111;color:#fff;border:1px solid #333;font-family:monospace;font-size:10px;padding:2px 4px;">
      <button onclick="sendRetroMessage()" style="background:#4a90d9;color:#fff;border:none;padding:2px 8px;font-family:monospace;font-size:10px;cursor:pointer;">Send</button>
    </div>
  `;
  var container = document.querySelector('#retro-modal .modal-content');
  if (container) { container.style.position = 'relative'; container.appendChild(panel); }
}

function sendRetroMessage() {
  var input = document.getElementById('retro-msg-input');
  var to = document.getElementById('retro-msg-to');
  var log = document.getElementById('retro-msg-log');
  if (!input || !input.value.trim()) return;
  var msg = input.value.trim();
  var target = to.value;

  // Add user message
  log.innerHTML += '<div style="color:#4a90d9;margin:2px 0;"><b>You \u2192 ' + target + ':</b> ' + msg + '</div>';

  // Generate response based on game situation
  var response = generateRetroResponse(target, msg);
  setTimeout(function() {
    log.innerHTML += '<div style="color:#ffe66d;margin:2px 0;"><b>' + target.charAt(0).toUpperCase() + target.slice(1) + ':</b> ' + response + '</div>';
    log.scrollTop = log.scrollHeight;
  }, 500 + Math.random() * 1000);

  input.value = '';
  log.scrollTop = log.scrollHeight;
}

function generateRetroResponse(target, msg) {
  var inning = RETRO.inning;
  var score = RETRO.homeScore + '-' + RETRO.awayScore;
  var outs = RETRO.outs;

  var responses = {
    coach: [
      'We\'re sticking with the game plan, boss.',
      'I like our matchups today. Trust the process.',
      'The bullpen is ready if we need \'em.',
      inning >= 7 ? 'Late innings, time to tighten up defensively.' : 'Still early, let the boys play.',
      'Our starter\'s dealing today. I\'m letting him go.',
      outs === 2 ? 'Two down, gotta bear down here.' : 'We\'re in good shape.',
    ],
    reporter: [
      'Can I quote you on that? *scribbles in notebook*',
      'The fans are really into this one!',
      'Sources say the trade deadline is heating up...',
      'That\'s going in tomorrow\'s column for sure.',
      'Any comment on the bullpen situation?',
      'The crowd is on their feet!',
    ],
    owner: [
      'Keep winning and the budget conversation gets easier.',
      'I\'m watching from the luxury box. Good stuff.',
      'The investors are happy when we\'re competitive.',
      'Let\'s finish this one strong.',
      'I trust your judgment on the roster moves.',
      'Win this series and we\'ll talk about that extension.',
    ],
    dugout: [
      'LET\'S GO! Rally caps on!',
      '*chewing sunflower seeds intensifies*',
      'Their pitcher is tipping his curveball.',
      'Someone get me a hot dog from the stands.',
      'The wave is going around. Classic.',
      'This ump\'s zone is tighter than a drum.',
    ],
  };

  var options = responses[target] || responses.dugout;
  return options[Math.floor(Math.random() * options.length)];
}
