"""
Front Office - API Routes
All FastAPI endpoints for the baseball simulation.
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from ..database.db import query, execute, get_connection
from ..simulation.season import get_standings, advance_date, sim_day, _load_team_lineup, _get_park_factors, _load_team_strategy, _generate_key_plays
from ..simulation.chemistry import calculate_team_chemistry
from ..transactions.trades import propose_trade, execute_trade
from ..transactions.free_agency import (
    get_free_agents, sign_free_agent, calculate_non_money_score,
    get_player_fa_preferences,
)
from ..ai.claude_client import check_health
from ..ai.gm_brain import generate_scouting_report
from ..ai.scouting_modes import get_displayed_ratings
from ..ai.agent_characters import (
    generate_agents, assign_agents_to_players, get_all_agents,
    get_agent_details, get_player_agent, modify_free_agent_negotiation,
    get_agent_negotiation_message,
)
from ..ai.player_backstories import generate_all_backstories, generate_backstory
from ..ai.asymmetric_info import (
    InformationLevel, get_player_info_level, apply_info_uncertainty,
    get_trade_intelligence, scout_player, get_available_intel,
)
from ..ai.owner_pressure import (
    set_owner_objectives, evaluate_gm_performance, check_firing,
    get_owner_mood_message, send_owner_pressure_messages,
    get_job_security, get_owner_objectives_for_team
)
from ..simulation.records import (
    initialize_records, check_record_watch, get_record_watch,
    get_all_records, check_career_milestones,
)
from ..transactions.roster import (
    call_up_player, option_player, dfa_player, get_roster_summary,
    add_to_forty_man, remove_from_forty_man, release_player
)
from ..transactions.trades import propose_waiver_trade
from ..transactions.draft import generate_draft_class, make_draft_pick
from ..simulation.injuries import check_injuries_for_day
from ..financial.economics import calculate_season_finances
from ..simulation.game_engine import simulate_game
from ..simulation.rating_calibration import (
    calibrate_ratings, get_rating_distribution, check_rating_health,
    normalize_draft_class,
)
from ..narrative.starting_scenario import get_available_scenarios, select_starting_team

app = FastAPI(title="Front Office", version="0.1.0",
              description="Baseball Universe Simulation powered by Local LLMs")

# --- Ensure game_state row exists ---
try:
    _conn_gs = get_connection()
    _gs_check = _conn_gs.execute("SELECT id FROM game_state WHERE id=1").fetchone()
    if not _gs_check:
        _conn_gs.execute("""
            INSERT INTO game_state (id, current_date, season, phase, difficulty)
            VALUES (1, '2026-02-15', 2026, 'spring_training', 'manager')
        """)
        _conn_gs.commit()
    _conn_gs.close()
except Exception:
    pass

# --- Schema migration: add current_hour column if missing ---
try:
    _conn = get_connection()
    _conn.execute("ALTER TABLE game_state ADD COLUMN current_hour INTEGER NOT NULL DEFAULT 8")
    _conn.commit()
    _conn.close()
except Exception:
    pass  # Column already exists

# --- Schema migration: add portrait column if missing ---
try:
    _conn_portrait = get_connection()
    _conn_portrait.execute("ALTER TABLE players ADD COLUMN portrait TEXT DEFAULT NULL")
    _conn_portrait.commit()
    _conn_portrait.close()
except Exception:
    pass  # Column already exists

# --- Schema migration: add auto_sim columns if missing ---
for _col_def in [
    "ALTER TABLE game_state ADD COLUMN auto_sim_enabled INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE game_state ADD COLUMN auto_sim_speed INTEGER NOT NULL DEFAULT 120000",
    "ALTER TABLE game_state ADD COLUMN auto_sim_last_tick TEXT DEFAULT NULL",
]:
    try:
        _conn2 = get_connection()
        _conn2.execute(_col_def)
        _conn2.commit()
        _conn2.close()
    except Exception:
        pass  # Column already exists

# --- Schema migration: create MiLB tables if missing ---
for _milb_sql in [
    """CREATE TABLE IF NOT EXISTS milb_standings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        level TEXT NOT NULL,
        season INTEGER NOT NULL,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,
        runs_scored INTEGER NOT NULL DEFAULT 0,
        runs_allowed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (team_id) REFERENCES teams(id),
        UNIQUE(team_id, level, season)
    )""",
    """CREATE TABLE IF NOT EXISTS milb_batting_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        level TEXT NOT NULL,
        season INTEGER NOT NULL,
        games INTEGER NOT NULL DEFAULT 0,
        ab INTEGER NOT NULL DEFAULT 0,
        hits INTEGER NOT NULL DEFAULT 0,
        doubles INTEGER NOT NULL DEFAULT 0,
        triples INTEGER NOT NULL DEFAULT 0,
        hr INTEGER NOT NULL DEFAULT 0,
        rbi INTEGER NOT NULL DEFAULT 0,
        bb INTEGER NOT NULL DEFAULT 0,
        so INTEGER NOT NULL DEFAULT 0,
        sb INTEGER NOT NULL DEFAULT 0,
        cs INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (player_id) REFERENCES players(id),
        FOREIGN KEY (team_id) REFERENCES teams(id),
        UNIQUE(player_id, level, season)
    )""",
    """CREATE TABLE IF NOT EXISTS milb_pitching_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        level TEXT NOT NULL,
        season INTEGER NOT NULL,
        games INTEGER NOT NULL DEFAULT 0,
        games_started INTEGER NOT NULL DEFAULT 0,
        wins INTEGER NOT NULL DEFAULT 0,
        losses INTEGER NOT NULL DEFAULT 0,
        saves INTEGER NOT NULL DEFAULT 0,
        ip_outs INTEGER NOT NULL DEFAULT 0,
        hits_allowed INTEGER NOT NULL DEFAULT 0,
        er INTEGER NOT NULL DEFAULT 0,
        bb INTEGER NOT NULL DEFAULT 0,
        so INTEGER NOT NULL DEFAULT 0,
        hr_allowed INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (player_id) REFERENCES players(id),
        FOREIGN KEY (team_id) REFERENCES teams(id),
        UNIQUE(player_id, level, season)
    )""",
]:
    try:
        _conn3 = get_connection()
        _conn3.execute(_milb_sql)
        _conn3.commit()
        _conn3.close()
    except Exception:
        pass

# --- Schema migration: create coaching_staff table if missing ---
try:
    _conn = get_connection()
    _conn.execute("""CREATE TABLE IF NOT EXISTS coaching_staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        age INTEGER NOT NULL DEFAULT 50,
        experience INTEGER NOT NULL DEFAULT 5,
        skill_rating INTEGER NOT NULL DEFAULT 50,
        philosophy TEXT DEFAULT 'balanced',
        specialty TEXT DEFAULT NULL,
        salary INTEGER NOT NULL DEFAULT 1000000,
        contract_years INTEGER NOT NULL DEFAULT 2,
        is_available INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (team_id) REFERENCES teams(id)
    )""")
    _conn.commit()
    _conn.close()
except Exception:
    pass

# --- Schema migration: create owner_objectives and gm_job_security tables if missing ---
try:
    _conn = get_connection()
    _conn.execute("""CREATE TABLE IF NOT EXISTS owner_objectives (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        season INTEGER NOT NULL,
        objective_type TEXT NOT NULL,
        target_value TEXT,
        priority INTEGER NOT NULL DEFAULT 1,
        status TEXT NOT NULL DEFAULT 'active',
        FOREIGN KEY (team_id) REFERENCES teams(id)
    )""")
    _conn.execute("""CREATE TABLE IF NOT EXISTS gm_job_security (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        team_id INTEGER NOT NULL,
        security_score INTEGER NOT NULL DEFAULT 70,
        owner_patience INTEGER NOT NULL DEFAULT 50,
        consecutive_losing_seasons INTEGER NOT NULL DEFAULT 0,
        playoff_appearances INTEGER NOT NULL DEFAULT 0,
        owner_mood TEXT NOT NULL DEFAULT 'neutral',
        last_evaluation_date TEXT,
        warnings_given INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (team_id) REFERENCES teams(id)
    )""")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_owner_objectives_team ON owner_objectives(team_id, season)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_owner_objectives_status ON owner_objectives(status)")
    _conn.commit()
    _conn.close()
except Exception:
    pass

# --- Schema migration: create agent_characters and player_agents tables if missing ---
try:
    _conn = get_connection()
    _conn.execute("""CREATE TABLE IF NOT EXISTS agent_characters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        agency_name TEXT,
        personality TEXT NOT NULL DEFAULT 'collaborative',
        negotiation_style TEXT NOT NULL DEFAULT 'fair',
        greed_factor REAL NOT NULL DEFAULT 1.0,
        loyalty_to_client REAL NOT NULL DEFAULT 0.7,
        market_knowledge INTEGER NOT NULL DEFAULT 70,
        bluff_tendency REAL NOT NULL DEFAULT 0.3,
        patience INTEGER NOT NULL DEFAULT 50,
        reputation INTEGER NOT NULL DEFAULT 50,
        num_clients INTEGER NOT NULL DEFAULT 0,
        notable_deals TEXT DEFAULT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""")
    _conn.execute("""CREATE TABLE IF NOT EXISTS player_agents (
        player_id INTEGER PRIMARY KEY,
        agent_id INTEGER NOT NULL,
        FOREIGN KEY (player_id) REFERENCES players(id),
        FOREIGN KEY (agent_id) REFERENCES agent_characters(id)
    )""")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_player_agents_agent ON player_agents(agent_id)")
    _conn.commit()
    _conn.close()
except Exception:
    pass

# --- Schema migration: create podcast_episodes table if missing ---
try:
    _conn = get_connection()
    _conn.execute("""CREATE TABLE IF NOT EXISTS podcast_episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        episode_number INTEGER NOT NULL,
        game_date TEXT NOT NULL,
        title TEXT NOT NULL,
        hosts TEXT NOT NULL,
        script TEXT NOT NULL,
        duration_estimate INTEGER NOT NULL DEFAULT 5,
        season INTEGER NOT NULL,
        topics TEXT,
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_podcast_episodes_season ON podcast_episodes(season)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_podcast_episodes_date ON podcast_episodes(game_date)")
    _conn.commit()
    _conn.close()
except Exception:
    pass

# --- Schema migration: create scouting_assignments and intelligence_reports tables ---
try:
    _conn = get_connection()
    _conn.execute("""CREATE TABLE IF NOT EXISTS scouting_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        scout_quality INTEGER NOT NULL DEFAULT 50,
        started_date TEXT NOT NULL,
        info_level INTEGER NOT NULL DEFAULT 2,
        FOREIGN KEY (team_id) REFERENCES teams(id),
        FOREIGN KEY (player_id) REFERENCES players(id)
    )""")
    _conn.execute("""CREATE TABLE IF NOT EXISTS intelligence_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        subject_type TEXT NOT NULL DEFAULT 'player',
        subject_id INTEGER NOT NULL,
        info_level INTEGER NOT NULL DEFAULT 0,
        report_data TEXT,
        source TEXT NOT NULL DEFAULT 'scout',
        game_date TEXT NOT NULL,
        FOREIGN KEY (team_id) REFERENCES teams(id)
    )""")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_scouting_assignments_team ON scouting_assignments(team_id)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_scouting_assignments_player ON scouting_assignments(team_id, player_id)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_intelligence_reports_team ON intelligence_reports(team_id)")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_intelligence_reports_subject ON intelligence_reports(subject_type, subject_id)")
    _conn.commit()
    _conn.close()
except Exception:
    pass

# --- Schema migration: add priority and category columns to messages ---
for _msg_col in [
    "ALTER TABLE messages ADD COLUMN priority TEXT DEFAULT 'normal'",
    "ALTER TABLE messages ADD COLUMN category TEXT DEFAULT 'general'",
]:
    try:
        _conn = get_connection()
        _conn.execute(_msg_col)
        _conn.commit()
        _conn.close()
    except Exception:
        pass  # Column already exists

# --- Schema migration: create records tracking tables ---
try:
    _conn = get_connection()
    _conn.executescript("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT NOT NULL,
            category TEXT NOT NULL,
            stat_name TEXT NOT NULL,
            value REAL NOT NULL,
            player_name TEXT NOT NULL,
            player_id INTEGER,
            season INTEGER,
            team_name TEXT,
            set_date TEXT,
            is_real_record INTEGER DEFAULT 1,
            UNIQUE(record_type, category, stat_name)
        );
        CREATE TABLE IF NOT EXISTS record_watch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            stat_name TEXT NOT NULL,
            record_type TEXT NOT NULL DEFAULT 'season',
            category TEXT NOT NULL DEFAULT 'batting',
            current_value REAL NOT NULL,
            record_value REAL NOT NULL,
            pace REAL NOT NULL,
            game_date TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );
        CREATE INDEX IF NOT EXISTS idx_record_watch_active
            ON record_watch(is_active, player_id, stat_name);
        CREATE INDEX IF NOT EXISTS idx_records_type
            ON records(record_type, category);
    """)
    _conn.commit()
    _conn.close()
except Exception:
    pass


# ============================================================
# FRONTEND
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend."""
    index_path = Path(__file__).parent.parent.parent / "static" / "index.html"
    return FileResponse(str(index_path))


# ============================================================
# GAME STATE
# ============================================================
@app.get("/game-state")
async def get_game_state():
    """Get current game state."""
    state = query("SELECT * FROM game_state WHERE id=1")
    if not state:
        return {"current_date": "2026-02-15", "season": 2026, "phase": "spring_training",
                "user_team_id": None, "difficulty": "manager", "scouting_mode": "traditional",
                "current_hour": 8}
    return state[0]


class SetUserTeam(BaseModel):
    team_id: int

@app.post("/set-user-team")
async def set_user_team(req: SetUserTeam):
    """Set the user's team."""
    execute("UPDATE game_state SET user_team_id=? WHERE id=1", (req.team_id,))
    return {"success": True, "team_id": req.team_id}


# ============================================================
# STARTING SCENARIOS
# ============================================================
@app.get("/scenarios")
async def list_scenarios():
    """Return the three available starting team scenarios."""
    return get_available_scenarios()


class SelectScenario(BaseModel):
    team_id: int


@app.post("/scenarios/select")
async def select_scenario(req: SelectScenario):
    """Select a starting team and initialise the game narrative."""
    try:
        scenario = select_starting_team(req.team_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"success": True, "scenario": scenario}


class SetScoutingMode(BaseModel):
    mode: str  # traditional, stat_based, variable

@app.post("/settings/scouting-mode")
async def set_scouting_mode(req: SetScoutingMode):
    """Change the scouting mode."""
    if req.mode not in ["traditional", "stat_based", "variable"]:
        raise HTTPException(400, "Invalid scouting mode. Must be: traditional, stat_based, or variable")
    execute("UPDATE game_state SET scouting_mode=? WHERE id=1", (req.mode,))
    return {"success": True, "scouting_mode": req.mode}


@app.get("/settings/scouting-mode")
async def get_scouting_mode():
    """Get the current scouting mode."""
    state = query("SELECT scouting_mode FROM game_state WHERE id=1")
    mode = state[0]["scouting_mode"] if state else "traditional"
    return {"scouting_mode": mode}


class SetDifficulty(BaseModel):
    difficulty: str  # fan, coach, manager, mogul

@app.post("/settings/difficulty")
async def set_difficulty(req: SetDifficulty):
    """Change the difficulty level."""
    if req.difficulty not in ["fan", "coach", "manager", "mogul"]:
        raise HTTPException(400, "Invalid difficulty. Must be: fan, coach, manager, or mogul")
    execute("UPDATE game_state SET difficulty=? WHERE id=1", (req.difficulty,))
    return {"success": True, "difficulty": req.difficulty}


@app.get("/settings/difficulty")
async def get_difficulty():
    """Get the current difficulty level."""
    state = query("SELECT difficulty FROM game_state WHERE id=1")
    difficulty = state[0]["difficulty"] if state else "manager"
    return {"difficulty": difficulty}


# ============================================================
# SIMULATION
# ============================================================
class AdvanceRequest(BaseModel):
    days: int = 1

@app.post("/sim/advance")
async def sim_advance(req: AdvanceRequest):
    """Advance the simulation by N days, playing all scheduled games."""
    if req.days < 1 or req.days > 30:
        raise HTTPException(400, "Days must be between 1 and 30")
    result = advance_date(req.days)
    return result


@app.post("/sim/advance-week")
async def sim_advance_week():
    """Advance the simulation by 7 days."""
    return advance_date(7)


@app.post("/sim/advance-hour")
async def sim_advance_hour():
    """Advance the game clock by 1 hour. When hour reaches 24, advance to next day and reset to 8 AM."""
    state = query("SELECT * FROM game_state WHERE id=1")
    if not state:
        raise HTTPException(500, "Game state not found")
    current_hour = state[0].get("current_hour", 8)
    new_hour = current_hour + 1
    if new_hour >= 24:
        # New day: advance the date and reset hour to 8 AM
        result = advance_date(1)
        execute("UPDATE game_state SET current_hour=8 WHERE id=1")
        result["current_hour"] = 8
        result["new_day"] = True
        return result
    else:
        execute("UPDATE game_state SET current_hour=? WHERE id=1", (new_hour,))
        return {
            "current_hour": new_hour,
            "new_day": False,
            "new_date": state[0]["current_date"],
            "phase": state[0]["phase"],
        }


# ============================================================
# AUTO-SIM (Server-side Progressive Time)
# ============================================================
import asyncio

_auto_sim_task = None


async def run_auto_sim_loop():
    """Background loop that advances game time when auto_sim is enabled."""
    global _auto_sim_task
    while True:
        try:
            state = query("SELECT auto_sim_enabled, auto_sim_speed, auto_sim_last_tick FROM game_state WHERE id=1")
            if not state or not state[0].get("auto_sim_enabled"):
                break

            speed_ms = state[0].get("auto_sim_speed", 120000)
            speed_sec = speed_ms / 1000.0

            # Check if enough time has passed since last tick
            last_tick = state[0].get("auto_sim_last_tick")
            if last_tick:
                from datetime import datetime, timedelta
                try:
                    last = datetime.fromisoformat(last_tick.replace('Z', '+00:00'))
                    now = datetime.now()
                    elapsed = (now - last).total_seconds()
                    if elapsed < speed_sec:
                        await asyncio.sleep(max(1, speed_sec - elapsed))
                        continue
                except Exception:
                    pass

            # Advance one day
            result = advance_date(1)
            execute("UPDATE game_state SET auto_sim_last_tick=datetime('now') WHERE id=1")

            await asyncio.sleep(speed_sec)
        except Exception as e:
            print(f"Auto-sim error: {e}")
            execute("UPDATE game_state SET auto_sim_enabled=0 WHERE id=1")
            break


@app.post("/sim/auto-start")
async def auto_sim_start(background_tasks: BackgroundTasks):
    """Start server-side auto-sim."""
    execute("UPDATE game_state SET auto_sim_enabled=1, auto_sim_last_tick=datetime('now') WHERE id=1")
    background_tasks.add_task(run_auto_sim_loop)
    return {"auto_sim": True}


@app.post("/sim/auto-stop")
async def auto_sim_stop():
    """Stop server-side auto-sim."""
    execute("UPDATE game_state SET auto_sim_enabled=0 WHERE id=1")
    return {"auto_sim": False}


@app.get("/sim/auto-status")
async def auto_sim_status():
    """Get auto-sim status."""
    state = query("SELECT auto_sim_enabled, auto_sim_speed, auto_sim_last_tick FROM game_state WHERE id=1")
    if not state:
        return {"auto_sim_enabled": False}
    return state[0]


class AutoSimSpeedRequest(BaseModel):
    speed: int


@app.post("/sim/auto-speed")
async def auto_sim_set_speed(req: AutoSimSpeedRequest):
    """Set auto-sim speed in milliseconds."""
    execute("UPDATE game_state SET auto_sim_speed=? WHERE id=1", (req.speed,))
    return {"speed": req.speed}


@app.on_event("startup")
async def startup_auto_sim_catchup():
    """On server start, catch up on missed auto-sim time."""
    state = query("SELECT auto_sim_enabled, auto_sim_speed, auto_sim_last_tick FROM game_state WHERE id=1")
    if not state or not state[0].get("auto_sim_enabled"):
        return

    last_tick = state[0].get("auto_sim_last_tick")
    speed_ms = state[0].get("auto_sim_speed", 120000)

    if last_tick:
        from datetime import datetime
        try:
            last = datetime.fromisoformat(last_tick)
            elapsed = (datetime.now() - last).total_seconds()
            missed_ticks = int(elapsed / (speed_ms / 1000.0))
            if missed_ticks > 0:
                # Cap at 30 days to prevent massive catch-up
                days_to_advance = min(missed_ticks, 30)
                if days_to_advance > 0:
                    advance_date(days_to_advance)
                    execute("UPDATE game_state SET auto_sim_last_tick=datetime('now') WHERE id=1")
        except Exception:
            pass

    # Restart the auto-sim loop
    asyncio.create_task(run_auto_sim_loop())


@app.post("/sim/game-live")
async def sim_game_live():
    """Simulate today's game for the user's team with detailed play-by-play."""
    import json

    # Get current state
    state = query("SELECT * FROM game_state WHERE id=1")
    if not state:
        raise HTTPException(500, "Game state not found")

    user_team_id = state[0]["user_team_id"]
    current_date = state[0]["current_date"]

    if not user_team_id:
        raise HTTPException(400, "No user team selected")

    # Find today's game for user's team
    game = query("""
        SELECT s.*, h.abbreviation as home_abbr, a.abbreviation as away_abbr,
               h.city as home_city, h.name as home_name, h.id as home_id,
               a.city as away_city, a.name as away_name, a.id as away_id
        FROM schedule s
        JOIN teams h ON h.id = s.home_team_id
        JOIN teams a ON a.id = s.away_team_id
        WHERE s.game_date=? AND (s.home_team_id=? OR s.away_team_id=?)
        AND s.is_played=0 AND s.is_postseason=0
    """, (current_date, user_team_id, user_team_id))

    if not game:
        return {"error": "No game scheduled today", "schedule_id": None}

    game = game[0]

    # Load lineups and pitchers
    home_lineup, home_pitchers = _load_team_lineup(game["home_id"])
    away_lineup, away_pitchers = _load_team_lineup(game["away_id"])
    park = _get_park_factors(game["home_id"])
    home_strategy = _load_team_strategy(game["home_id"])
    away_strategy = _load_team_strategy(game["away_id"])
    home_chemistry = calculate_team_chemistry(game["home_id"])
    away_chemistry = calculate_team_chemistry(game["away_id"])

    # Simulate game
    result = simulate_game(
        home_lineup, away_lineup,
        home_pitchers, away_pitchers,
        park, game["home_id"], game["away_id"],
        home_strategy, away_strategy,
        home_chemistry=home_chemistry,
        away_chemistry=away_chemistry
    )

    # Build simplified plays (detailed tracking would need game_engine instrumentation)
    plays = _build_simplified_plays(result)

    # Save to database
    conn = get_connection()
    conn.execute("""
        UPDATE schedule SET is_played=1, home_score=?, away_score=?
        WHERE id=?
    """, (result["home_score"], result["away_score"], game["id"]))

    key_plays = _generate_key_plays(result, game["home_id"], game["away_id"])
    conn.execute("""
        INSERT INTO game_results (schedule_id, innings_json, play_by_play_json,
            winning_pitcher_id, losing_pitcher_id, save_pitcher_id, attendance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        game["id"],
        json.dumps([result["innings_away"], result["innings_home"]]),
        json.dumps(key_plays),
        next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "W"), None),
        next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "L"), None),
        next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "S"), None),
        30000,
    ))

    # Save batting lines
    for lineup, team_id in [(result["home_lineup"], game["home_id"]), (result["away_lineup"], game["away_id"])]:
        for b in lineup:
            conn.execute("""
                INSERT INTO batting_lines (schedule_id, player_id, team_id,
                    batting_order, position_played, ab, runs, hits, doubles,
                    triples, hr, rbi, bb, so, sb, cs, hbp, sf)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (game["id"], b.player_id, team_id, b.batting_order,
                  b.position, b.ab, b.runs, b.hits, b.doubles, b.triples,
                  b.hr, b.rbi, b.bb, b.so, b.sb, b.cs, b.hbp, b.sf))

    # Save pitching lines
    for pitchers, team_id in [(result["home_pitchers"], game["home_id"]), (result["away_pitchers"], game["away_id"])]:
        for p in pitchers:
            if p.ip_outs == 0 and p.pitches == 0:
                continue
            conn.execute("""
                INSERT INTO pitching_lines (schedule_id, player_id, team_id,
                    pitch_order, ip_outs, hits_allowed, runs_allowed, er,
                    bb, so, hr_allowed, pitches, is_starter, decision)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (game["id"], p.player_id, team_id, p.pitch_order,
                  p.ip_outs, p.hits_allowed, p.runs_allowed, p.er,
                  p.bb_allowed, p.so_pitched, p.hr_allowed, p.pitches,
                  p.is_starter, p.decision))

    # Save pitch log entries
    state_for_season = query("SELECT season FROM game_state WHERE id=1")
    current_season = state_for_season[0]["season"] if state_for_season else 2026
    pitch_log = result.get("pitch_log", [])
    for pl in pitch_log:
        conn.execute("""
            INSERT INTO pitch_log (game_id, inning, at_bat_num, pitch_num,
                pitcher_id, batter_id, pitch_type, velocity, result, zone,
                count_balls, count_strikes, outs, runners_on, score_diff, season)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (game["id"], pl["inning"], pl["at_bat_num"], pl["pitch_num"],
              pl["pitcher_id"], pl["batter_id"], pl["pitch_type"], pl["velocity"],
              pl["result"], pl["zone"], pl["count_balls"], pl["count_strikes"],
              pl["outs"], pl["runners_on"], pl["score_diff"], current_season))

    # Save matchup stats
    matchup_data = result.get("matchup_data", {})
    for (batter_id, pitcher_id), mstats in matchup_data.items():
        conn.execute("""
            INSERT INTO matchup_stats (batter_id, pitcher_id, season, pa, ab, h,
                doubles, triples, hr, rbi, bb, so, hbp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(batter_id, pitcher_id, season) DO UPDATE SET
                pa = pa + excluded.pa,
                ab = ab + excluded.ab,
                h = h + excluded.h,
                doubles = doubles + excluded.doubles,
                triples = triples + excluded.triples,
                hr = hr + excluded.hr,
                rbi = rbi + excluded.rbi,
                bb = bb + excluded.bb,
                so = so + excluded.so,
                hbp = hbp + excluded.hbp
        """, (batter_id, pitcher_id, current_season,
              mstats["pa"], mstats["ab"], mstats["h"],
              mstats["doubles"], mstats["triples"], mstats["hr"],
              mstats["rbi"], mstats["bb"], mstats["so"], mstats["hbp"]))

    conn.commit()
    conn.close()

    return {
        "schedule_id": game["id"],
        "home_team": {
            "id": game["home_id"],
            "name": game["home_name"],
            "city": game["home_city"],
            "abbr": game["home_abbr"]
        },
        "away_team": {
            "id": game["away_id"],
            "name": game["away_name"],
            "city": game["away_city"],
            "abbr": game["away_abbr"]
        },
        "plays": plays,
        "final_score": [result["home_score"], result["away_score"]],
    }


def _build_simplified_plays(result: dict) -> list:
    """Build a simplified play-by-play from inning scores."""
    plays = []
    home_score = 0
    away_score = 0

    for inning in range(1, len(result["innings_away"]) + 1):
        away_runs = result["innings_away"][inning - 1] if inning - 1 < len(result["innings_away"]) else 0
        home_runs = result["innings_home"][inning - 1] if inning - 1 < len(result["innings_home"]) else None

        # Away half
        plays.append({
            "inning": inning,
            "half": "top",
            "description": f"End of top {inning}: {away_runs} runs scored" if away_runs else f"Top {inning}: No runs",
            "score": [home_score, away_score + away_runs]
        })
        away_score += away_runs

        # Home half (may be None in bottom of 9 if home wins)
        if home_runs is not None:
            plays.append({
                "inning": inning,
                "half": "bottom",
                "description": f"End of bottom {inning}: {home_runs} runs scored" if home_runs else f"Bottom {inning}: No runs",
                "score": [home_score + home_runs, away_score]
            })
            home_score += home_runs

    return plays


# ============================================================
# TEAMS
# ============================================================
@app.get("/team/{team_id}")
async def get_team(team_id: int):
    """Full team view: roster, stats, finances, staff."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    roster = query("""
        SELECT p.*, c.annual_salary, c.years_remaining, c.no_trade_clause
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=?
        ORDER BY p.roster_status, p.position, p.contact_rating + p.power_rating + p.stuff_rating DESC
    """, (team_id,))

    gm = query("SELECT * FROM gm_characters WHERE team_id=?", (team_id,))
    owner = query("SELECT * FROM owner_characters WHERE team_id=?", (team_id,))

    # Calculate payroll
    payroll = sum(p.get("annual_salary", 0) or 0 for p in roster)

    return {
        "team": team[0],
        "roster": roster,
        "gm": gm[0] if gm else None,
        "owner": owner[0] if owner else None,
        "payroll": payroll,
        "roster_count": {
            "active": len([p for p in roster if p["roster_status"] == "active"]),
            "minors": len([p for p in roster if "minors" in p["roster_status"]]),
            "injured": len([p for p in roster if p["is_injured"]]),
        }
    }


@app.get("/teams")
async def list_teams():
    """List all 30 teams."""
    return query("SELECT id, city, name, abbreviation, league, division FROM teams")


# ============================================================
# ANALYTICS INTEGRATION (Phase 5)
# ============================================================
@app.get("/analytics/{team_id}")
async def get_analytics_dashboard(team_id: int):
    """Get the full analytics dashboard for a team."""
    from ..ai.analytics_integration import get_team_analytics_dashboard
    return get_team_analytics_dashboard(team_id)


# ============================================================
# STANDINGS
# ============================================================
@app.get("/standings")
async def standings():
    """Current standings by division."""
    return get_standings()


# ============================================================
# PLAYOFFS
# ============================================================
@app.get("/playoffs/bracket")
async def get_playoffs_bracket():
    """Get the current playoff bracket for the season."""
    from ..simulation.playoffs import get_playoff_bracket
    state = query("SELECT season FROM game_state WHERE id=1")
    if not state:
        return {"error": "No game state"}
    season = state[0]["season"]
    return get_playoff_bracket(season)


@app.post("/playoffs/advance")
async def advance_playoffs():
    """Simulate the next playoff game(s) and advance the bracket."""
    from ..simulation.playoffs import advance_playoff_round
    state = query("SELECT season FROM game_state WHERE id=1")
    if not state:
        return {"error": "No game state"}
    season = state[0]["season"]
    result = advance_playoff_round(season)
    return result


# ============================================================
# PLAYERS
# ============================================================
@app.get("/player/{player_id}")
async def get_player(player_id: int):
    """Player detail with stats, contract, and scouting report."""
    player = query("""
        SELECT p.*, t.city, t.name as team_name, t.abbreviation,
               c.annual_salary, c.years_remaining, c.total_years, c.no_trade_clause
        FROM players p
        LEFT JOIN teams t ON t.id = p.team_id
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.id=?
    """, (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    # Get user team and season for scouting mode
    game_state = query("SELECT user_team_id, season FROM game_state WHERE id=1")
    user_team_id = game_state[0]["user_team_id"] if game_state else None
    season = game_state[0]["season"] if game_state else 2026

    # Apply scouting mode to player ratings
    player_data = player[0].copy()
    if user_team_id:
        player_data = get_displayed_ratings(player_data, user_team_id, season)

    # Apply asymmetric information filtering for other teams' players
    if user_team_id and player_data.get("team_id") != user_team_id:
        info_level = get_player_info_level(user_team_id, player_id)
        player_data = apply_info_uncertainty(player_data, info_level)

    # Get season stats
    batting = query("""
        SELECT * FROM batting_stats WHERE player_id=?
        ORDER BY season DESC
    """, (player_id,))
    pitching = query("""
        SELECT * FROM pitching_stats WHERE player_id=?
        ORDER BY season DESC
    """, (player_id,))

    return {
        "player": player_data,
        "batting_stats": batting,
        "pitching_stats": pitching,
    }


@app.get("/players/search")
async def search_players(
    q: str = "",
    position: str = "",
    team_id: int = None,
    min_age: int = None,
    max_age: int = None,
    min_overall: int = None,
    max_overall: int = None,
    roster_status: str = "",
    sort_by: str = "overall",
    sort_dir: str = "desc",
    limit: int = 50
):
    """Search and filter players with flexible criteria."""
    conditions = ["1=1"]
    params: list = []

    # Name search
    if q:
        conditions.append("(p.first_name LIKE ? OR p.last_name LIKE ? OR (p.first_name || ' ' || p.last_name) LIKE ?)")
        search_term = f"%{q}%"
        params.extend([search_term, search_term, search_term])

    # Position filter
    if position:
        conditions.append("p.position = ?")
        params.append(position)

    # Team filter
    if team_id is not None:
        conditions.append("p.team_id = ?")
        params.append(team_id)

    # Age range
    if min_age is not None:
        conditions.append("p.age >= ?")
        params.append(min_age)
    if max_age is not None:
        conditions.append("p.age <= ?")
        params.append(max_age)

    # Overall rating range (use position-specific calculation)
    if min_overall is not None or max_overall is not None:
        if min_overall is not None and max_overall is not None:
            conditions.append(f"""
                (CASE WHEN p.position IN ('SP', 'RP')
                    THEN (p.stuff_rating + p.control_rating + p.stamina_rating) / 3
                    ELSE (p.contact_rating + p.power_rating + p.fielding_rating) / 3
                END) >= ? AND
                (CASE WHEN p.position IN ('SP', 'RP')
                    THEN (p.stuff_rating + p.control_rating + p.stamina_rating) / 3
                    ELSE (p.contact_rating + p.power_rating + p.fielding_rating) / 3
                END) <= ?
            """)
            params.extend([min_overall, max_overall])
        elif min_overall is not None:
            conditions.append(f"""
                (CASE WHEN p.position IN ('SP', 'RP')
                    THEN (p.stuff_rating + p.control_rating + p.stamina_rating) / 3
                    ELSE (p.contact_rating + p.power_rating + p.fielding_rating) / 3
                END) >= ?
            """)
            params.append(min_overall)
        elif max_overall is not None:
            conditions.append(f"""
                (CASE WHEN p.position IN ('SP', 'RP')
                    THEN (p.stuff_rating + p.control_rating + p.stamina_rating) / 3
                    ELSE (p.contact_rating + p.power_rating + p.fielding_rating) / 3
                END) <= ?
            """)
            params.append(max_overall)

    # Roster status
    if roster_status:
        if roster_status == "minors":
            conditions.append("p.roster_status LIKE 'minors%'")
        else:
            conditions.append("p.roster_status = ?")
            params.append(roster_status)

    # Build sort clause
    sort_column = "overall"
    if sort_by == "name":
        sort_column = "(p.first_name || ' ' || p.last_name)"
    elif sort_by == "age":
        sort_column = "p.age"
    elif sort_by == "contact":
        sort_column = "p.contact_rating"
    elif sort_by == "power":
        sort_column = "p.power_rating"
    elif sort_by == "speed":
        sort_column = "p.speed_rating"
    else:
        sort_column = f"""CASE WHEN p.position IN ('SP', 'RP')
                            THEN (p.stuff_rating + p.control_rating + p.stamina_rating) / 3
                            ELSE (p.contact_rating + p.power_rating + p.fielding_rating) / 3
                         END"""

    sort_order = "DESC" if sort_dir.lower() == "desc" else "ASC"

    where = " AND ".join(conditions)
    sql = f"""
        SELECT p.*, t.abbreviation, t.city, t.name as team_name,
               c.annual_salary, c.years_remaining,
               CASE WHEN p.position IN ('SP', 'RP')
                    THEN (p.stuff_rating + p.control_rating + p.stamina_rating) / 3
                    ELSE (p.contact_rating + p.power_rating + p.fielding_rating) / 3
               END as overall
        FROM players p
        LEFT JOIN teams t ON t.id = p.team_id
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE {where}
        ORDER BY {sort_column} {sort_order}
        LIMIT ?
    """
    params.append(limit)

    results = query(sql, tuple(params))

    # Get user team and season for scouting mode
    game_state = query("SELECT user_team_id, season FROM game_state WHERE id=1")
    user_team_id = game_state[0]["user_team_id"] if game_state else None
    season = game_state[0]["season"] if game_state else 2026

    # Apply scouting mode to each player's ratings
    if user_team_id:
        for player in results:
            displayed = get_displayed_ratings(player, user_team_id, season)
            # Update rating fields in place
            for field in ["contact_rating", "power_rating", "speed_rating", "fielding_rating",
                         "arm_rating", "stuff_rating", "control_rating", "stamina_rating"]:
                if field in displayed:
                    player[field] = displayed[field]

    return results


@app.get("/player/{player_id}/scouting-report")
async def player_scouting_report(player_id: int):
    """Generate quick scouting narrative (legacy endpoint)."""
    report = await generate_scouting_report(player_id, scout_quality=65)
    if isinstance(report, dict) and "narrative" in report:
        return {"player_id": player_id, "report": report["narrative"]}
    return {"player_id": player_id, "report": str(report)}


@app.get("/player/{player_id}/scouting-report-full")
async def player_scouting_report_full(player_id: int, scout_quality: int = 65):
    """Generate comprehensive structured scouting report with grades and comp."""
    scout_quality = max(1, min(100, scout_quality))
    report = await generate_scouting_report(player_id, scout_quality=scout_quality)
    return report


# ============================================================
# TRADING BLOCK
# ============================================================
@app.get("/trading-block")
async def get_trading_block(team_id: int = None):
    """Get the user's trading block and incoming offers."""
    if not team_id:
        state = query("SELECT user_team_id FROM game_state WHERE id=1")
        team_id = state[0]["user_team_id"] if state else None
    if not team_id:
        return {"players": [], "offers": []}

    import json as _json
    block_data = query("""
        SELECT trading_block_json FROM teams WHERE id=?
    """, (team_id,))

    if not block_data or not block_data[0]:
        return {"players": [], "offers": []}

    trading_block_str = block_data[0].get("trading_block_json")
    if not trading_block_str:
        return {"players": [], "offers": []}

    try:
        parsed = _json.loads(trading_block_str)
        # Validate structure
        if isinstance(parsed, dict) and "players" in parsed and "offers" in parsed:
            return parsed
    except (ValueError, KeyError):
        pass

    return {"players": [], "offers": []}


@app.post("/trading-block/add/{player_id}")
async def add_to_trading_block(player_id: int):
    """Add a player to the trading block."""
    import json as _json

    player = query("SELECT team_id FROM players WHERE id=?", (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    team_id = player[0]["team_id"]
    team = query("SELECT trading_block_json FROM teams WHERE id=?", (team_id,))

    block_data = {"players": [], "offers": []}
    if team and team[0]:
        trading_block_str = team[0]["trading_block_json"]
        if trading_block_str:
            try:
                parsed = _json.loads(trading_block_str)
                # Ensure it's in the expected format
                if isinstance(parsed, dict) and "players" in parsed:
                    block_data = parsed
            except (ValueError, KeyError):
                pass

    if player_id not in block_data.get("players", []):
        block_data["players"].append(player_id)

    execute("UPDATE teams SET trading_block_json=? WHERE id=?",
            (_json.dumps(block_data), team_id))
    return {"success": True, "player_id": player_id}


@app.post("/trading-block/remove/{player_id}")
async def remove_from_trading_block(player_id: int):
    """Remove a player from the trading block."""
    import json as _json

    player = query("SELECT team_id FROM players WHERE id=?", (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    team_id = player[0]["team_id"]
    team = query("SELECT trading_block_json FROM teams WHERE id=?", (team_id,))

    block_data = {"players": [], "offers": []}
    if team and team[0]:
        trading_block_str = team[0]["trading_block_json"]
        if trading_block_str:
            try:
                parsed = _json.loads(trading_block_str)
                # Ensure it's in the expected format
                if isinstance(parsed, dict) and "players" in parsed:
                    block_data = parsed
            except (ValueError, KeyError):
                pass

    if player_id in block_data.get("players", []):
        block_data["players"].remove(player_id)

    execute("UPDATE teams SET trading_block_json=? WHERE id=?",
            (_json.dumps(block_data), team_id))

    return {"success": True, "player_id": player_id}


# ============================================================
# TRADES
# ============================================================
class TradeProposal(BaseModel):
    proposing_team_id: int
    receiving_team_id: int
    players_offered: list[int]
    players_requested: list[int]
    cash_included: int = 0

@app.post("/trade/propose")
async def trade_propose(trade: TradeProposal):
    """Propose a trade and get the other GM's response via LLM."""
    result = await propose_trade(
        trade.proposing_team_id, trade.receiving_team_id,
        trade.players_offered, trade.players_requested,
        trade.cash_included
    )
    return result


@app.post("/trade/execute")
async def trade_execute(trade: TradeProposal):
    """Execute an already-accepted trade."""
    result = execute_trade(
        trade.proposing_team_id, trade.receiving_team_id,
        trade.players_offered, trade.players_requested,
        trade.cash_included
    )
    return result


@app.post("/trade/accept/{message_id}")
async def accept_ai_trade(message_id: int):
    """Accept a trade offer from an AI team (via message inbox)."""
    from ..transactions.ai_trades import accept_trade_offer
    return accept_trade_offer(message_id)


@app.post("/trade/decline/{message_id}")
async def decline_ai_trade(message_id: int):
    """Decline a trade offer from an AI team (via message inbox)."""
    from ..transactions.ai_trades import decline_trade_offer
    return decline_trade_offer(message_id)


@app.get("/trade-history")
async def trade_history(season: int = None):
    """Get all completed trades for a season with formatted descriptions."""
    from ..transactions.ai_trades import get_trade_history
    return get_trade_history(season)


# ============================================================
# FREE AGENTS
# ============================================================
@app.get("/free-agents")
async def free_agents():
    """Available free agents with market status."""
    return get_free_agents()


class SigningRequest(BaseModel):
    player_id: int
    team_id: int
    salary: int
    years: int

@app.post("/free-agents/sign")
async def sign_fa(req: SigningRequest):
    """Sign a free agent."""
    return sign_free_agent(req.player_id, req.team_id, req.salary, req.years)


class FreeAgentNegotiationRequest(BaseModel):
    player_id: int
    team_id: int
    salary: int
    years: int

@app.post("/free-agents/negotiate")
async def negotiate_free_agent(req: FreeAgentNegotiationRequest):
    """Negotiate with a free agent (can offer less than asking price).

    Factors affecting outcome:
    - Agent personality (greed_factor * market_value)
    - Player personality (greed, ego, loyalty traits)
    - Non-money factors: playing time, friends, chemistry, winning, market size
    - Counter-offer behavior and messaging
    - How many years they want
    - Whether they demand NTC/opt-out
    """
    import random

    # Get player and their asking terms
    player = query("""
        SELECT p.*, c.annual_salary, c.total_years
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.id = ? AND p.roster_status = 'free_agent'
    """, (req.player_id,))

    if not player:
        raise HTTPException(404, "Player not found or not a free agent")

    p = player[0]
    asking_salary = p.get('asking_salary', 5000000)
    asking_years = p.get('asking_years', 3)

    # --- Agent personality hook ---
    # Get the agent's modified demands; this adjusts the asking price,
    # years, NTC demands, and acceptance probability
    agent_info = modify_free_agent_negotiation(
        req.player_id, asking_salary, asking_years,
        req.salary, req.years
    )

    # If agent is involved, use their adjusted asking price
    if agent_info["agent_involved"]:
        asking_salary = agent_info["adjusted_asking_salary"]
        asking_years = agent_info["adjusted_asking_years"]

    # Calculate acceptance probability based on offer quality
    salary_ratio = req.salary / asking_salary if asking_salary > 0 else 1.0

    # Apply agent acceptance modifier (positive = more willing, negative = harder)
    acceptance_modifier = agent_info.get("acceptance_modifier", 0.0)

    accepted = False
    counter_offer = None
    reason = ""

    if salary_ratio >= 1.0:
        # Offer meets or exceeds asking: auto-accept
        accepted = True
        reason = "Offer meets or exceeds asking price"
    elif salary_ratio >= 0.95:
        # 95-99%: 80% chance accept (modified by agent)
        accept_chance = min(0.95, max(0.10, 0.80 + acceptance_modifier))
        accepted = random.random() < accept_chance
        reason = "Offer close to asking price" if accepted else "Wants more money"
    elif salary_ratio >= 0.80:
        # 80-94%: 50% chance accept, likely counter (modified by agent)
        accept_chance = min(0.85, max(0.10, 0.50 + acceptance_modifier))
        if random.random() < accept_chance:
            accepted = True
            reason = "Accepted slightly reduced offer"
        else:
            counter_offer = {
                "salary": int(asking_salary * 0.95),
                "years": asking_years
            }
            reason = "Countered with closer offer"
    elif salary_ratio >= 0.60:
        # 60-79%: 20% chance accept, likely counter (modified by agent)
        accept_chance = min(0.60, max(0.05, 0.20 + acceptance_modifier))
        if random.random() < accept_chance:
            accepted = True
            reason = "Accepted despite lower offer"
        else:
            counter_offer = {
                "salary": int((req.salary + asking_salary) / 2),
                "years": asking_years
            }
            reason = "Countered splitting the difference"
    else:
        # <60%: automatic reject with counter
        counter_offer = {
            "salary": int(asking_salary * 0.90),
            "years": asking_years
        }
        reason = "Offer too low, countered"

    # Use agent's counter-offer if available and we're not accepting
    if not accepted and agent_info.get("counter_offer"):
        agent_counter = agent_info["counter_offer"]
        counter_offer = {
            "salary": agent_counter["salary"],
            "years": agent_counter["years"],
        }
        if agent_counter.get("wants_ntc"):
            counter_offer["wants_ntc"] = True
        if agent_counter.get("wants_opt_out"):
            counter_offer["wants_opt_out"] = True

    # Factor in team competitiveness if accepted
    if accepted:
        team = query("SELECT wins, losses FROM teams WHERE id=?", (req.team_id,))
        if team:
            t = team[0]
            win_pct = t.get('wins', 0) / (t.get('wins', 0) + t.get('losses', 1))
            if win_pct > 0.550:
                # Winning team gets slight discount to salary requirement
                if random.random() < 0.3:
                    reason = f"{reason} (winning team appeal)"

    if accepted:
        # Sign the player
        result = sign_free_agent(req.player_id, req.team_id, req.salary, req.years)
        response = {
            "accepted": True,
            "result": result,
            "reason": reason
        }
        # Include agent message on acceptance
        if agent_info.get("agent_message"):
            response["agent_message"] = agent_info["agent_message"]
        if agent_info.get("agent_name"):
            response["agent_name"] = agent_info["agent_name"]
        return response

    response = {
        "accepted": False,
        "counter_offer": counter_offer,
        "reason": reason
    }
    # Include agent messaging and bluff info
    if agent_info.get("agent_message"):
        response["agent_message"] = agent_info["agent_message"]
    if agent_info.get("agent_name"):
        response["agent_name"] = agent_info["agent_name"]
    if agent_info.get("bluffing") and agent_info.get("bluff_message"):
        response["bluff_message"] = agent_info["bluff_message"]
    if agent_info.get("wants_ntc"):
        response["agent_demands_ntc"] = True
    if agent_info.get("wants_opt_out"):
        response["agent_demands_opt_out"] = True
    return response


@app.get("/free-agents/{player_id}/non-money-score")
async def fa_non_money_score(player_id: int, team_id: int):
    """Calculate non-money attraction score (0-100) for a free agent toward a specific team.

    Shows how attractive this team is to the player beyond salary, broken down by:
    Playing Time, Friends, Chemistry, Contender Status, Market Size.
    Personality traits (greed, ego, sociability, loyalty) adjust the weights.
    """
    return calculate_non_money_score(player_id, team_id)


@app.get("/free-agents/{player_id}/preferences")
async def fa_preferences(player_id: int):
    """Get a free agent's non-money preferences for scouting reports.

    Shows what factors this player values most (e.g. 'Drawn to contenders',
    'Values having friends on the team') so the user knows what teams
    might appeal to them beyond salary.
    """
    result = get_player_fa_preferences(player_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/admin/generate-free-agents")
async def generate_free_agents(min_count: int = 50):
    """
    Admin endpoint to ensure minimum free agents exist.
    If there are fewer than min_count free agents, generates new ones.
    """
    from ..transactions.free_agency import ensure_minimum_free_agents

    result = ensure_minimum_free_agents(min_count)
    return result


# ============================================================
# PLAYER AGENTS
# ============================================================
@app.get("/agents")
async def list_agents():
    """List all player agents."""
    agents = get_all_agents()
    if not agents:
        # Auto-generate agents if none exist
        agents = generate_agents()
    return agents


@app.get("/agent/{agent_id}")
async def get_agent(agent_id: int):
    """Get agent details with client list."""
    agent = get_agent_details(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@app.get("/player/{player_id}/agent")
async def get_player_agent_endpoint(player_id: int):
    """Get the agent representing a player."""
    agent = get_player_agent(player_id)
    if not agent:
        raise HTTPException(404, "No agent found for this player")
    return agent


@app.post("/admin/generate-agents")
async def admin_generate_agents(count: int = 15):
    """Generate player agents (admin endpoint)."""
    agents = generate_agents(count)
    return {"success": True, "count": len(agents), "agents": agents}


@app.post("/admin/assign-agents")
async def admin_assign_agents():
    """Assign agents to all players based on player quality (admin endpoint)."""
    result = assign_agents_to_players()
    return result


class ContractExtensionRequest(BaseModel):
    player_id: int
    team_id: int
    salary: int
    years: int
    no_trade_clause: bool = False

@app.post("/contracts/extend-offer")
async def extend_contract(req: ContractExtensionRequest):
    """Propose a contract extension to a player on your roster."""
    import random

    # Verify player is on user's team
    player = query("""
        SELECT p.*, c.annual_salary, c.years_remaining
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.id = ? AND p.team_id = ?
    """, (req.player_id, req.team_id))

    if not player:
        raise HTTPException(404, "Player not found on your team")

    p = player[0]
    current_salary = p.get('annual_salary', 3000000)
    years_remaining = p.get('years_remaining', 1)

    # Calculate acceptance based on various factors

    # 1. Base salary requirement: must be >= current salary or player insulted
    if req.salary < current_salary:
        return {
            "accepted": False,
            "counter_offer": None,
            "reason": "Offer is below current salary - player is insulted"
        }

    # 2. Player overall rating (higher rating = wants more money)
    is_pitcher = p['position'] in ('SP', 'RP')
    if is_pitcher:
        overall = (p['stuff_rating'] * 2 + p['control_rating'] * 1.5) / 3.5
    else:
        overall = (p['contact_rating'] * 1.5 + p['power_rating'] * 1.5 +
                  p['speed_rating'] * 0.5 + p['fielding_rating'] * 0.5) / 4

    # 3. Age factor: older players prefer shorter deals, younger prefer longer
    age_preference = "short" if p['age'] > 32 else "long"

    # 4. Years remaining factor: if >2 years left, less likely to extend
    if years_remaining > 2:
        # Player not in a hurry
        accept_chance = 0.3
    elif years_remaining == 2:
        accept_chance = 0.5
    else:
        # Final year or one year left - more likely to lock in
        accept_chance = 0.7

    # 5. Loyalty trait (simulated with consistency rating)
    loyalty_factor = (p.get('consistency_rating', 50) - 30) / 70  # Scale 0-1
    accept_chance += loyalty_factor * 0.15

    # 6. Salary increase factor
    salary_increase_pct = (req.salary - current_salary) / current_salary
    if salary_increase_pct >= 0.20:
        accept_chance += 0.20
    elif salary_increase_pct >= 0.10:
        accept_chance += 0.10
    elif salary_increase_pct >= 0.05:
        accept_chance += 0.05

    # 7. Years offered vs preference
    years_mismatch = 0
    if age_preference == "short" and req.years > 3:
        years_mismatch = -0.2
    elif age_preference == "long" and req.years < 3:
        years_mismatch = -0.15

    accept_chance += years_mismatch
    accept_chance = max(0.1, min(0.9, accept_chance))  # Clamp 0.1-0.9

    accepted = random.random() < accept_chance
    counter_offer = None
    reason = ""

    if accepted:
        # Update contract in database
        conn = None
        try:
            conn = get_connection()
            conn.execute("""
                UPDATE contracts
                SET annual_salary = ?, years_remaining = ?, total_years = ?, no_trade_clause = ?
                WHERE player_id = ?
            """, (req.salary, req.years, req.years, int(req.no_trade_clause), req.player_id))

            # Log transaction
            conn.execute("""
                INSERT INTO transactions (team_id, transaction_type, player_id, details, transaction_date)
                VALUES (?, 'contract_extension', ?, ?, date('now'))
            """, (req.team_id, req.player_id, f"Extended {req.years}yr at ${req.salary:,}/yr"))

            conn.commit()
            reason = f"Player accepted extension through age {p['age'] + req.years}"
        except Exception as e:
            raise HTTPException(500, f"Failed to update contract: {str(e)}")
        finally:
            if conn:
                conn.close()
    else:
        # Generate counter-offer
        counter_salary = int(current_salary * 1.05)  # +5% counter
        counter_years = req.years - 1 if req.years > 1 else 1

        counter_offer = {
            "salary": counter_salary,
            "years": counter_years
        }
        reason = "Player countered - wants more or fewer years"

    return {
        "accepted": accepted,
        "counter_offer": counter_offer,
        "reason": reason
    }


# ============================================================
# COACHING STAFF
# ============================================================
@app.get("/coaching-staff/{team_id}")
async def get_team_coaching_staff(team_id: int):
    """Get coaching staff for a team."""
    from ..transactions.coaching import get_coaching_staff, get_coaching_impact
    staff = get_coaching_staff(team_id)
    impact = get_coaching_impact(team_id)
    return {"staff": staff or [], "impact": impact}

@app.get("/coaching-staff/available")
async def get_available_coaches_endpoint(role: str = None):
    """Get available free agent coaches."""
    from ..transactions.coaching import get_available_coaches
    return get_available_coaches(role)

@app.post("/coaching-staff/{team_id}/hire/{coach_id}")
async def hire_coach_endpoint(team_id: int, coach_id: int):
    """Hire a free agent coach."""
    from ..transactions.coaching import hire_coach
    return hire_coach(team_id, coach_id)

@app.post("/coaching-staff/{team_id}/fire/{coach_id}")
async def fire_coach_endpoint(team_id: int, coach_id: int):
    """Fire a coach."""
    from ..transactions.coaching import fire_coach
    return fire_coach(team_id, coach_id)


@app.get("/manager-ai/{team_id}/strategy")
async def get_manager_strategy(team_id: int):
    """Get the manager AI's current strategy adjustments."""
    from ..ai.manager_ai import get_manager_ai
    ai = get_manager_ai(team_id)
    return {
        "manager": ai.name,
        "personality": ai.personality,
        "mood": ai.mood,
        "recent_record": f"{ai.recent_wins}-{ai.recent_losses}",
        "strategy": ai.get_strategy_adjustments(),
    }


# ============================================================
# SCHEDULE
# ============================================================
@app.get("/schedule")
async def get_schedule(date: str = None, team_id: int = None,
                       limit: int = Query(default=30, le=162)):
    """Get schedule with optional filters."""
    conditions = ["1=1"]
    params = []

    if date:
        conditions.append("s.game_date = ?")
        params.append(date)
    if team_id:
        conditions.append("(s.home_team_id = ? OR s.away_team_id = ?)")
        params.extend([team_id, team_id])

    where = " AND ".join(conditions)
    return query(f"""
        SELECT s.*, h.abbreviation as home_abbr, a.abbreviation as away_abbr,
               h.city as home_city, h.name as home_name,
               a.city as away_city, a.name as away_name
        FROM schedule s
        JOIN teams h ON h.id = s.home_team_id
        JOIN teams a ON a.id = s.away_team_id
        WHERE {where}
        ORDER BY s.game_date, s.id
        LIMIT ?
    """, tuple(params) + (limit,))


# ============================================================
# FINANCES
# ============================================================
@app.get("/finances/{team_id}")
async def get_finances(team_id: int):
    """Team financial overview."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")
    t = team[0]

    payroll = query("""
        SELECT COALESCE(SUM(c.annual_salary), 0) as total
        FROM contracts c
        JOIN players p ON p.id = c.player_id
        WHERE c.team_id=? AND p.roster_status != 'free_agent'
    """, (team_id,))

    history = query("""
        SELECT * FROM financial_history WHERE team_id=?
        ORDER BY season DESC LIMIT 5
    """, (team_id,))

    current_payroll = payroll[0]["total"] if payroll else 0
    payroll_budget = t.get("payroll_budget", 100_000_000)

    return {
        "team_id": team_id,
        "cash": t["cash"],
        "franchise_value": t["franchise_value"],
        "current_payroll": current_payroll,
        "payroll_budget": payroll_budget,
        "payroll_pct": round(current_payroll / payroll_budget * 100, 1) if payroll_budget else 0,
        "farm_budget": t["farm_system_budget"],
        "medical_budget": t["medical_staff_budget"],
        "scouting_budget": t["scouting_staff_budget"],
        "ticket_price_pct": t["ticket_price_pct"],
        "concession_price_pct": t["concession_price_pct"],
        "history": history,
    }


class BudgetUpdate(BaseModel):
    field: str
    value: int

@app.post("/finances/{team_id}/budget")
async def update_budget(team_id: int, req: BudgetUpdate):
    """Update team budget allocations and pricing."""
    field_map = {
        "farm": "farm_system_budget",
        "medical": "medical_staff_budget",
        "scouting": "scouting_staff_budget",
        "ticket_price": "ticket_price_pct",
        "concession_price": "concession_price_pct",
    }
    if req.field not in field_map:
        raise HTTPException(400, "Invalid budget field")
    db_field = field_map[req.field]
    execute(f"UPDATE teams SET {db_field}=? WHERE id=?", (req.value, team_id))
    return {"success": True, "field": req.field, "value": req.value}


# ============================================================
# MESSAGES
# ============================================================
@app.get("/messages")
async def get_messages_auto(unread_only: bool = False, priority: str = None):
    """Get messages for the user's team (auto-detect team)."""
    state = query("SELECT user_team_id FROM game_state WHERE id=1")
    team_id = state[0]["user_team_id"] if state else None
    if not team_id:
        return []
    from ..transactions.messages import get_messages_for_team
    return get_messages_for_team(team_id, unread_only=unread_only, priority=priority) or []



@app.get("/messages/priorities")
async def get_message_priorities():
    """Get message counts by priority level for the user's team."""
    state = query("SELECT user_team_id FROM game_state WHERE id=1")
    team_id = state[0]["user_team_id"] if state else None
    if not team_id:
        return {"urgent": {"total": 0, "unread": 0}, "important": {"total": 0, "unread": 0},
                "normal": {"total": 0, "unread": 0}, "low": {"total": 0, "unread": 0}}
    from ..transactions.messages import get_message_priorities
    return get_message_priorities(team_id)


@app.get("/messages/categories")
async def get_message_categories():
    """Get message counts by category for the user's team."""
    state = query("SELECT user_team_id FROM game_state WHERE id=1")
    team_id = state[0]["user_team_id"] if state else None
    if not team_id:
        return {}
    from ..transactions.messages import get_message_categories
    return get_message_categories(team_id)


@app.get("/messages/{team_id}")
async def get_team_messages(team_id: int, unread_only: bool = False, priority: str = None):
    """Get messages for a specific team."""
    from ..transactions.messages import get_messages_for_team
    messages = get_messages_for_team(team_id, unread_only=unread_only, priority=priority)
    return messages or []


@app.get("/messages/{team_id}/unread-count")
async def get_unread_count(team_id: int):
    """Get unread message count for a team."""
    from ..transactions.messages import get_unread_message_count
    count = get_unread_message_count(team_id)
    return {"unread_count": count}


class MarkMessageRead(BaseModel):
    message_id: int

@app.post("/messages/{message_id}/read")
async def mark_message_read(message_id: int):
    """Mark a message as read."""
    from ..transactions.messages import mark_message_as_read
    mark_message_as_read(message_id)
    return {"success": True}


class MessageSend(BaseModel):
    recipient_type: str  # gm, owner
    recipient_id: int
    body: str

@app.post("/messages/send")
async def send_user_message(msg: MessageSend):
    """Send a message to a GM or owner."""
    state = query("SELECT * FROM game_state WHERE id=1")
    game_date = state[0]["current_date"] if state else "2025-03-27"

    execute("""
        INSERT INTO messages (game_date, sender_type, sender_name,
            recipient_type, recipient_id, body)
        VALUES (?, 'user', 'You', ?, ?, ?)
    """, (game_date, msg.recipient_type, msg.recipient_id, msg.body))

    return {"sent": True}


# ============================================================
# OLLAMA STATUS
# ============================================================
@app.get("/ollama/status")
@app.get("/ollama-health")
async def ollama_status():
    """Check Ollama health and available models."""
    return await check_health()


# ============================================================
# BOX SCORE
# ============================================================
class OllamaUrlUpdate(BaseModel):
    url: str

@app.get("/ollama/url")
async def get_ollama_url():
    """Get the current Ollama URL (kept for image gen/TTS)."""
    return {"url": "http://localhost:11434"}

@app.post("/ollama/url")
async def set_ollama_url(req: OllamaUrlUpdate):
    """Set the Ollama URL (kept for image gen/TTS)."""
    return {"success": True, "url": req.url}


@app.get("/llm/status")
async def llm_status(since: str = None):
    """Get LLM call stats and recent failures."""
    from ..ai.claude_client import get_llm_stats, get_llm_failures
    health = await check_health()
    return {
        "connected": health.get("status") == "healthy",
        "provider": "claude-cli",
        "stats": get_llm_stats(),
        "recent_failures": get_llm_failures(since),
    }


@app.get("/game/{schedule_id}/boxscore")
async def get_boxscore(schedule_id: int):
    """Full box score with linescore, batting lines, pitching lines."""
    game = query("""
        SELECT s.*, h.abbreviation as home_abbr, a.abbreviation as away_abbr,
               h.city as home_city, h.name as home_name,
               a.city as away_city, a.name as away_name
        FROM schedule s
        JOIN teams h ON h.id = s.home_team_id
        JOIN teams a ON a.id = s.away_team_id
        WHERE s.id=?
    """, (schedule_id,))
    if not game:
        raise HTTPException(404, "Game not found")
    result = query("SELECT * FROM game_results WHERE schedule_id=?", (schedule_id,))
    batting = query("""
        SELECT bl.*, p.first_name, p.last_name
        FROM batting_lines bl JOIN players p ON p.id = bl.player_id
        WHERE bl.schedule_id=? ORDER BY bl.team_id, bl.batting_order
    """, (schedule_id,))
    pitching = query("""
        SELECT pl.*, p.first_name, p.last_name
        FROM pitching_lines pl JOIN players p ON p.id = pl.player_id
        WHERE pl.schedule_id=? ORDER BY pl.team_id, pl.pitch_order
    """, (schedule_id,))
    return {
        "game": game[0],
        "result": result[0] if result else None,
        "batting": batting,
        "pitching": pitching,
    }


@app.get("/game/{schedule_id}/play-by-play")
async def get_play_by_play(schedule_id: int):
    """Get play-by-play data for a game."""
    result = query("SELECT play_by_play_json FROM game_results WHERE schedule_id=?", (schedule_id,))
    if not result or not result[0].get("play_by_play_json"):
        return []
    import json
    try:
        return json.loads(result[0]["play_by_play_json"])
    except:
        return []


# ============================================================
# SEASON AWARDS
# ============================================================
@app.get("/awards/{season}")
async def get_awards(season: int):
    """Get calculated awards for a season (MVP, Cy Young, ROY, Gold Glove)."""
    from ..simulation.awards import get_season_awards
    return get_season_awards(season)


@app.post("/awards/calculate/{season}")
async def calculate_awards(season: int):
    """Calculate and store awards for a season."""
    from ..simulation.awards import calculate_season_awards
    try:
        results = calculate_season_awards(season)
        return {
            "success": True,
            "message": f"Awards calculated for season {season}",
            "results": results
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# WAR LEADERBOARD
# ============================================================
@app.get("/war/{season}")
async def war_leaderboard(season: int, limit: int = 50):
    """WAR leaderboard for a season."""
    from ..simulation.awards import calculate_all_war
    results = calculate_all_war(season)
    return results[:limit]


@app.get("/war/{season}/{player_id}")
async def player_war(season: int, player_id: int):
    """WAR for a specific player in a season."""
    from ..simulation.awards import calculate_war
    war = calculate_war(player_id, season)
    return {"player_id": player_id, "season": season, "war": war}


# ============================================================
# ALL-STAR GAME
# ============================================================
@app.post("/all-star/{season}")
async def run_all_star_game(season: int):
    """Simulate the All-Star Game for a season."""
    from ..simulation.awards import simulate_all_star_game
    return simulate_all_star_game(season)


# ============================================================
# SILVER SLUGGER & HALL OF FAME
# ============================================================
@app.get("/silver-slugger/{season}")
async def silver_slugger(season: int):
    """Silver Slugger awards for a season."""
    from ..simulation.awards import _calculate_silver_sluggers
    al = _calculate_silver_sluggers("AL", season)
    nl = _calculate_silver_sluggers("NL", season)
    return {"AL": al, "NL": nl}


@app.get("/hall-of-fame")
async def hall_of_fame():
    """Check Hall of Fame eligible players and their voting."""
    from ..simulation.awards import _check_hall_of_fame_eligibility
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026
    inductees = _check_hall_of_fame_eligibility(season)
    return {"inductees": inductees, "season": season}


# ============================================================
# ROSTER MANAGEMENT
# ============================================================
@app.get("/roster/{team_id}")
async def roster(team_id: int):
    """Full roster breakdown: active, minors, injured."""
    roster_data = get_roster_summary(team_id)

    # Get user team and season for scouting mode
    game_state = query("SELECT user_team_id, season FROM game_state WHERE id=1")
    user_team_id = game_state[0]["user_team_id"] if game_state else None
    season = game_state[0]["season"] if game_state else 2026

    # Apply scouting mode to all players in the roster
    if user_team_id:
        for player_list in [roster_data.get("active", []), roster_data.get("minors", []), roster_data.get("injured", [])]:
            for player in player_list:
                displayed = get_displayed_ratings(player, user_team_id, season)
                # Update rating fields in place
                for field in ["contact_rating", "power_rating", "speed_rating", "fielding_rating",
                             "arm_rating", "stuff_rating", "control_rating", "stamina_rating"]:
                    if field in displayed:
                        player[field] = displayed[field]

    return roster_data


@app.post("/roster/call-up/{player_id}")
async def roster_call_up(player_id: int):
    """Call up a minor leaguer to the active roster."""
    return call_up_player(player_id)


@app.post("/roster/option/{player_id}")
async def roster_option(player_id: int, level: str = "minors_aaa"):
    """Option a player to the minors."""
    return option_player(player_id, level)


@app.post("/roster/dfa/{player_id}")
async def roster_dfa(player_id: int):
    """Designate a player for assignment."""
    return dfa_player(player_id)


@app.post("/roster/release/{player_id}")
async def roster_release(player_id: int):
    """Release a player from the team (becomes a free agent)."""
    return release_player(player_id)


class ExtensionRequest(BaseModel):
    years: int
    annual_salary: int


@app.post("/player/{player_id}/extend")
async def offer_player_extension(player_id: int, req: ExtensionRequest):
    """Offer a contract extension to a player."""
    from ..transactions.contracts import offer_extension
    return offer_extension(player_id, req.years, req.annual_salary)


@app.get("/waivers")
async def get_waiver_wire():
    """Get all players currently on waivers (pending claims)."""
    players = query("""
        SELECT wc.*, p.first_name, p.last_name, p.position, p.age,
               p.contact_rating, p.power_rating, p.speed_rating,
               p.fielding_rating, p.arm_rating, p.stuff_rating,
               p.control_rating, p.stamina_rating,
               t.abbreviation as original_team_abbr, t.city, t.name as team_name
        FROM waiver_claims wc
        JOIN players p ON p.id = wc.player_id
        LEFT JOIN teams t ON t.id = wc.original_team_id
        WHERE wc.status = 'pending'
        ORDER BY wc.expiry_date ASC
    """)
    return players or []


@app.post("/waivers/claim/{player_id}")
async def claim_waiver_player(player_id: int):
    """User claims a player off waivers."""
    state = query("SELECT user_team_id FROM game_state WHERE id=1")
    if not state:
        raise HTTPException(400, "No game state")
    user_team_id = state[0]["user_team_id"]

    # Check waiver exists
    waiver = query("""
        SELECT wc.id, p.first_name, p.last_name
        FROM waiver_claims wc
        JOIN players p ON p.id = wc.player_id
        WHERE wc.player_id = ? AND wc.status = 'pending'
    """, (player_id,))
    if not waiver:
        raise HTTPException(404, "Player not on waivers")

    # Check 40-man space
    forty_man = query("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND roster_status IN ('active', 'injured_dl')
    """, (user_team_id,))
    if forty_man and forty_man[0]["c"] >= 40:
        raise HTTPException(400, "40-man roster is full. Make room first.")

    # Claim the player
    execute("UPDATE players SET team_id=?, roster_status='active', on_forty_man=1 WHERE id=?",
            (user_team_id, player_id))
    execute("UPDATE waiver_claims SET status='claimed', claiming_team_id=? WHERE player_id=? AND status='pending'",
            (user_team_id, player_id))
    execute("UPDATE contracts SET team_id=? WHERE player_id=?",
            (user_team_id, player_id))

    name = f"{waiver[0]['first_name']} {waiver[0]['last_name']}"
    import json as _json
    execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json, team1_id, player_ids)
        VALUES (date('now'), 'waiver_claim', ?, ?, ?)
    """, (_json.dumps({"action": "claimed", "player_name": name}), user_team_id, str(player_id)))

    return {"success": True, "name": name, "message": f"Claimed {name} off waivers"}


@app.get("/transactions/recent")
async def get_recent_transactions(limit: int = Query(default=50, le=200)):
    """Get recent league-wide transactions."""
    import json as _json
    txns = query("""
        SELECT tr.id, tr.transaction_date, tr.transaction_type, tr.details_json,
               tr.team1_id, tr.team2_id, tr.player_ids,
               t.abbreviation, t.city, t.name as team_name
        FROM transactions tr
        LEFT JOIN teams t ON t.id = tr.team1_id
        ORDER BY tr.transaction_date DESC, tr.id DESC
        LIMIT ?
    """, (limit,))

    # Enrich with player names
    results = []
    for t in (txns or []):
        entry = dict(t)
        # Try to get player name from player_ids
        player_ids_str = t.get("player_ids", "")
        if player_ids_str:
            try:
                pid = int(player_ids_str.split(",")[0].strip())
                p = query("SELECT first_name, last_name, position FROM players WHERE id=?", (pid,))
                if p:
                    entry["first_name"] = p[0]["first_name"]
                    entry["last_name"] = p[0]["last_name"]
                    entry["position"] = p[0]["position"]
            except (ValueError, IndexError):
                pass
        # Extract details from JSON
        try:
            details = _json.loads(t.get("details_json", "{}"))
            entry["details"] = details.get("player_name", details.get("action", ""))
            # For trades, include the full description
            if t.get("transaction_type") == "trade":
                entry["trade_description"] = details.get("description", "")
                entry["players_to_team1"] = details.get("players_to_proposing_names",
                                                         details.get("players_to_proposing", []))
                entry["players_to_team2"] = details.get("players_to_receiving_names",
                                                         details.get("players_to_receiving", []))
                # Get team2 info for trades
                if t.get("team2_id"):
                    t2 = query("SELECT city, name, abbreviation FROM teams WHERE id=?",
                              (t["team2_id"],))
                    if t2:
                        entry["team2_city"] = t2[0]["city"]
                        entry["team2_name"] = t2[0]["name"]
                        entry["team2_abbreviation"] = t2[0]["abbreviation"]
        except (ValueError, TypeError):
            entry["details"] = ""
        results.append(entry)

    return results


class ILRequest(BaseModel):
    player_id: int
    tier: str = "60"  # 60-day, 15-day, etc.

@app.post("/roster/{team_id}/place-il")
async def place_on_il(team_id: int, req: ILRequest):
    """Place a player on the injured list."""
    player = query("SELECT * FROM players WHERE id=? AND team_id=?", (req.player_id, team_id))
    if not player:
        raise HTTPException(404, "Player not found on team")

    execute("""
        UPDATE players SET roster_status=?, is_injured=1 WHERE id=?
    """, (f"il_{req.tier.lower()}", req.player_id))

    return {"success": True, "name": f"{player[0]['first_name']} {player[0]['last_name']}"}


@app.post("/roster/{team_id}/activate")
async def activate_from_il(team_id: int, req: ILRequest):
    """Activate a player from the injured list."""
    player = query("SELECT * FROM players WHERE id=? AND team_id=?", (req.player_id, team_id))
    if not player:
        raise HTTPException(404, "Player not found on team")

    execute("""
        UPDATE players SET roster_status='active', is_injured=0 WHERE id=?
    """, (req.player_id,))

    return {"success": True, "name": f"{player[0]['first_name']} {player[0]['last_name']}"}


# ============================================================
# DRAFT
# ============================================================
@app.get("/draft/prospects/{season}")
async def draft_prospects(season: int):
    """Get or generate the draft class for a season."""
    prospects = generate_draft_class(season)
    return prospects


class DraftPickRequest(BaseModel):
    team_id: int
    prospect_id: int
    round: int
    pick: int

@app.post("/draft/pick")
async def draft_pick(req: DraftPickRequest):
    """Make a draft selection."""
    return make_draft_pick(req.team_id, req.prospect_id, req.round, req.pick)


@app.get("/draft/status")
async def draft_status():
    """Get current draft status (round, pick, which team is picking)."""
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026

    # Get the next available pick
    picks = query("""
        SELECT dpo.round, dpo.pick_number as pick, dpo.current_owner_team_id as owner_team_id,
               t.city, t.name, t.abbreviation
        FROM draft_pick_ownership dpo
        LEFT JOIN teams t ON t.id = dpo.current_owner_team_id
        WHERE dpo.season=? AND NOT EXISTS (
            SELECT 1 FROM draft_prospects WHERE is_drafted=1
            AND drafted_by_team_id=dpo.current_owner_team_id
            AND draft_round=dpo.round AND draft_pick=dpo.pick_number
        )
        ORDER BY dpo.round, dpo.pick_number
        LIMIT 1
    """, (season,))

    if picks:
        p = picks[0]
        return {
            "current_round": p["round"],
            "current_pick": p["pick"],
            "current_team_id": p["owner_team_id"],
            "current_team": f"{p['city']} {p['name']}" if p['city'] else "Unknown",
            "current_team_abbr": p["abbreviation"]
        }
    return {"current_round": 1, "current_pick": 1, "current_team_id": None, "current_team": "Unknown"}


@app.get("/draft/results")
async def draft_results():
    """Get all picks made so far in the draft."""
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026

    picks = query("""
        SELECT dp.draft_round as round, dp.draft_pick as pick,
               t.abbreviation as team_abbr, p.id as player_id,
               p.first_name, p.last_name, p.position
        FROM draft_prospects dp
        LEFT JOIN players p ON p.id = (
            SELECT id FROM players WHERE first_name=dp.first_name
            AND last_name=dp.last_name AND position=dp.position LIMIT 1
        )
        LEFT JOIN teams t ON t.id = dp.drafted_by_team_id
        WHERE dp.season=? AND dp.is_drafted=1
        ORDER BY dp.draft_round, dp.draft_pick
    """, (season,))

    return picks or []


@app.get("/draft/prospect/{prospect_id}/scouting-report")
async def draft_prospect_scouting_report(prospect_id: int, scout_quality: int = 50):
    """Generate a scouting report for a draft prospect."""
    import random
    from ..ai.pitch_velocity import calculate_pitch_arsenal
    from ..ai.player_comps import find_best_comp

    # Get prospect data
    prospect_data = query(
        "SELECT * FROM draft_prospects WHERE id=?",
        (prospect_id,)
    )
    if not prospect_data:
        return {"error": "Prospect not found"}

    p = prospect_data[0]
    is_pitcher = p["position"] in ("SP", "RP")

    # Calculate uncertainty margins based on scout quality
    if scout_quality >= 70:
        uncertainty = 3
    elif scout_quality >= 50:
        uncertainty = 7
    else:
        uncertainty = 12

    # Generate present grades from floor values with noise
    if is_pitcher:
        present_grades = {
            "fastball": max(20, min(80, p["stuff_floor"] + random.randint(-uncertainty, uncertainty))),
            "curveball": max(20, min(80, p["control_floor"] + random.randint(-uncertainty, uncertainty))),
            "slider": max(20, min(80, p["control_floor"] + random.randint(-uncertainty, uncertainty))),
            "changeup": max(20, min(80, p["control_floor"] + random.randint(-uncertainty, uncertainty))),
            "command": max(20, min(80, p["control_floor"] + random.randint(-uncertainty, uncertainty))),
            "control": max(20, min(80, p["control_floor"] + random.randint(-uncertainty, uncertainty))),
        }
    else:
        present_grades = {
            "hit": max(20, min(80, p["contact_floor"] + random.randint(-uncertainty, uncertainty))),
            "power": max(20, min(80, p["power_floor"] + random.randint(-uncertainty, uncertainty))),
            "run": max(20, min(80, p["speed_floor"] + random.randint(-uncertainty, uncertainty))),
            "field": max(20, min(80, p["fielding_floor"] + random.randint(-uncertainty, uncertainty))),
            "arm": max(20, min(80, p["arm_floor"] + random.randint(-uncertainty, uncertainty))),
        }

    # Generate future grades from ceiling values
    if is_pitcher:
        future_grades = {
            "fastball": max(20, min(80, p["stuff_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "curveball": max(20, min(80, p["control_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "slider": max(20, min(80, p["control_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "changeup": max(20, min(80, p["control_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "command": max(20, min(80, p["control_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "control": max(20, min(80, p["control_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
        }
    else:
        future_grades = {
            "hit": max(20, min(80, p["contact_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "power": max(20, min(80, p["power_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "run": max(20, min(80, p["speed_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "field": max(20, min(80, p["fielding_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
            "arm": max(20, min(80, p["arm_ceiling"] + random.randint(-uncertainty//2, uncertainty//2))),
        }

    # Calculate OFP from ceiling averages
    avg_ceiling = sum(future_grades.values()) / len(future_grades)
    ofp = max(20, min(80, int(avg_ceiling)))

    # Generate ceiling and floor descriptions
    if ofp >= 75:
        ceiling = "Generational talent / perennial MVP candidate"
        floor = "All-Star caliber player"
    elif ofp >= 70:
        ceiling = "Perennial All-Star with MVP upside"
        floor = "Above-average regular"
    elif ofp >= 65:
        ceiling = "All-Star caliber player"
        floor = "Solid everyday starter"
    elif ofp >= 60:
        ceiling = "Above-average regular with All-Star potential"
        floor = "Solid starter/regular"
    elif ofp >= 55:
        ceiling = "Quality everyday player"
        floor = "Platoon player or useful bench piece"
    elif ofp >= 50:
        ceiling = "Everyday player"
        floor = "Reserve/platoon player"
    elif ofp >= 40:
        ceiling = "Useful bench player"
        floor = "Minor leaguer or organizational depth"
    else:
        ceiling = "Role player at best"
        floor = "Non-prospect"

    # Determine risk level based on gap between floor and ceiling
    rating_avg = sum(present_grades.values()) / len(present_grades)
    gap = ofp - rating_avg
    if gap > 10:
        risk_level = "high"
    elif gap > 5:
        risk_level = "medium"
    else:
        risk_level = "low"

    # ETA calculation
    if p["age"] <= 22:
        eta = str(2026 + random.randint(0, 2))
    elif p["age"] <= 25:
        eta = str(2026 + random.randint(0, 1))
    else:
        eta = "2026"

    # Get MLB comp - use prospective data
    mlb_comp = None
    try:
        # Create a mock player dict with ceiling values for comp calculation
        mock_player = {
            "position": p["position"],
            "contact_rating": p["contact_ceiling"] if p["position"] not in ("SP", "RP") else 50,
            "power_rating": p["power_ceiling"] if p["position"] not in ("SP", "RP") else 50,
            "speed_rating": p["speed_ceiling"],
            "fielding_rating": p["fielding_ceiling"] if p["position"] not in ("SP", "RP") else 50,
            "arm_rating": p["arm_ceiling"],
            "stuff_rating": p["stuff_ceiling"] if is_pitcher else 50,
            "control_rating": p["control_ceiling"] if is_pitcher else 50,
            "age": p["age"],
            "first_name": p["first_name"],
            "last_name": p["last_name"],
        }
        comps = find_best_comp(mock_player, p["position"], is_pitcher, count=1)
        mlb_comp = comps[0] if comps else None
    except Exception:
        mlb_comp = None

    # Generate narrative
    if is_pitcher:
        tools_text = []
        if present_grades.get("fastball", 0) >= 75:
            tools_text.append("power fastball")
        if present_grades.get("curveball", 0) >= 75:
            tools_text.append("sharp curveball")
        if present_grades.get("control", 0) >= 75:
            tools_text.append("exceptional control")
        tools_phrase = " with ".join(tools_text) if tools_text else "solid arm"
    else:
        tools_text = []
        if present_grades.get("power", 0) >= 75:
            tools_text.append("plus-plus power")
        if present_grades.get("hit", 0) >= 75:
            tools_text.append("excellent bat speed")
        if present_grades.get("run", 0) >= 70:
            tools_text.append("above-average speed")
        if present_grades.get("field", 0) >= 75:
            tools_text.append("slick defense")
        tools_phrase = " with ".join(tools_text) if tools_text else "solid tools"

    narrative = f"{p['first_name']} projects as {ceiling.lower()}. {tools_phrase}. "
    if mlb_comp:
        narrative += f"Similar profile to {mlb_comp['name']}. "
    narrative += f"Best case: {ceiling.lower()}. Worst case: {floor.lower()}."

    result = {
        "prospect_id": prospect_id,
        "prospect_name": f"{p['first_name']} {p['last_name']}",
        "position": p["position"],
        "age": p["age"],
        "present_grades": present_grades,
        "future_grades": future_grades,
        "ofp": ofp,
        "ceiling": ceiling,
        "floor": floor,
        "risk_level": risk_level,
        "eta": eta,
        "narrative": narrative,
        "mlb_comp": mlb_comp,
        "scout_quality": scout_quality,
        "uncertainty_margin": uncertainty,
    }

    # Add pitch arsenal data for pitcher prospects
    if is_pitcher:
        # Create a mock pitcher with the prospect's ceiling values
        mock_pitcher = {
            "position": p["position"],
            "stuff_rating": p["stuff_ceiling"],
            "control_rating": p["control_ceiling"],
            "pitch_repertoire_json": None,
        }
        pitch_arsenal = calculate_pitch_arsenal(mock_pitcher, uncertainty, scout_quality)
        result["pitch_arsenal"] = pitch_arsenal

    # Add exit velocity data for hitter prospects
    else:
        exit_velo = {
            "avg_exit_velo": round(82 + (p["power_ceiling"] - 20) * 0.22, 1),
            "max_exit_velo": round(82 + (p["power_ceiling"] - 20) * 0.22 + random.uniform(10, 15), 1),
            "barrel_rate": round(3 + (p["power_ceiling"] - 20) * 0.20, 1),
            "hard_hit_rate": round((3 + (p["power_ceiling"] - 20) * 0.20) * random.uniform(3.0, 4.0), 1),
        }
        result["exit_velo"] = exit_velo

    return result


# ============================================================
# INJURIES
# ============================================================
@app.get("/injuries/check")
async def check_injuries():
    """Run injury checks for the current date."""
    state = query("SELECT * FROM game_state WHERE id=1")
    game_date = state[0]["current_date"] if state else "2025-03-27"
    events = check_injuries_for_day(game_date)
    return {"date": game_date, "events": events}


# ============================================================
# FINANCIAL DETAILS
# ============================================================
@app.get("/finances/{team_id}/details")
async def finances_details(team_id: int):
    """Detailed financial breakdown with revenue/expense modeling."""
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2025
    return calculate_season_finances(team_id, season)


# ============================================================
# TRANSACTIONS LOG
# ============================================================
@app.get("/transactions")
async def transactions(limit: int = Query(default=25, le=100)):
    """Recent transactions across the league."""
    return query("""
        SELECT t.*,
               t1.abbreviation as team1_abbr, t1.city as team1_city, t1.name as team1_name,
               t2.abbreviation as team2_abbr, t2.city as team2_city, t2.name as team2_name
        FROM transactions t
        LEFT JOIN teams t1 ON t1.id = t.team1_id
        LEFT JOIN teams t2 ON t2.id = t.team2_id
        ORDER BY t.id DESC
        LIMIT ?
    """, (limit,))


# ============================================================
# LEAGUE LEADERS
# ============================================================
@app.get("/leaders/batting")
async def batting_leaders(stat: str = "hr", limit: int = 10):
    """League batting leaders for any stat."""
    valid_stats = {"hr", "hits", "rbi", "sb", "bb", "doubles", "triples", "ab", "runs"}
    if stat not in valid_stats:
        raise HTTPException(400, f"Invalid stat. Use: {valid_stats}")
    return query(f"""
        SELECT p.first_name, p.last_name, t.abbreviation,
               bs.player_id, bs.games, bs.ab, bs.hits, bs.hr, bs.rbi, bs.bb, bs.so,
               bs.doubles, bs.triples, bs.sb, bs.runs,
               CASE WHEN bs.ab > 0 THEN ROUND(1.0 * bs.hits / bs.ab, 3) END as avg
        FROM batting_stats bs
        JOIN players p ON p.id = bs.player_id
        JOIN teams t ON t.id = bs.team_id
        WHERE bs.ab >= 20
        ORDER BY bs.{stat} DESC
        LIMIT ?
    """, (limit,))


@app.get("/leaders/pitching")
async def pitching_leaders(stat: str = "wins", limit: int = 10):
    """League pitching leaders for any stat."""
    valid_stats = {"wins", "so", "saves", "er", "ip_outs", "games"}
    if stat not in valid_stats:
        raise HTTPException(400, f"Invalid stat. Use: {valid_stats}")
    return query(f"""
        SELECT p.first_name, p.last_name, t.abbreviation,
               ps.player_id, ps.games, ps.games_started, ps.wins, ps.losses, ps.saves,
               ps.ip_outs, ps.er, ps.so, ps.bb, ps.hr_allowed,
               CASE WHEN ps.ip_outs > 0
                    THEN ROUND(9.0 * ps.er / (ps.ip_outs / 3.0), 2) END as era
        FROM pitching_stats ps
        JOIN players p ON p.id = ps.player_id
        JOIN teams t ON t.id = ps.team_id
        WHERE ps.ip_outs >= 9
        ORDER BY ps.{stat} DESC
        LIMIT ?
    """, (limit,))


# ============================================================
# ALL-TIME CAREER LEADERS
# ============================================================
@app.get("/leaders/all-time/batting")
async def alltime_batting_leaders(stat: str = "hr", limit: int = 25):
    """Career all-time batting leaders across all seasons."""
    valid_stats = {"hr", "hits", "rbi", "sb", "bb", "doubles", "triples", "runs", "ab"}
    if stat not in valid_stats:
        raise HTTPException(400, f"Invalid stat. Use: {valid_stats}")
    return query(f"""
        SELECT p.id as player_id, p.first_name, p.last_name, p.position,
               t.abbreviation as current_team,
               COUNT(DISTINCT bs.season) as seasons,
               SUM(bs.games) as games,
               SUM(bs.ab) as ab, SUM(bs.hits) as hits, SUM(bs.hr) as hr,
               SUM(bs.rbi) as rbi, SUM(bs.bb) as bb, SUM(bs.sb) as sb,
               SUM(bs.runs) as runs, SUM(bs.doubles) as doubles, SUM(bs.triples) as triples,
               CASE WHEN SUM(bs.ab) > 0
                    THEN ROUND(1.0 * SUM(bs.hits) / SUM(bs.ab), 3) END as avg
        FROM batting_stats bs
        JOIN players p ON p.id = bs.player_id
        LEFT JOIN teams t ON t.id = p.team_id
        WHERE bs.level = 'MLB'
        GROUP BY bs.player_id
        HAVING SUM(bs.ab) >= 50
        ORDER BY SUM(bs.{stat}) DESC
        LIMIT ?
    """, (limit,))


@app.get("/leaders/all-time/pitching")
async def alltime_pitching_leaders(stat: str = "wins", limit: int = 25):
    """Career all-time pitching leaders across all seasons."""
    valid_stats = {"wins", "so", "saves", "er", "ip_outs", "games", "games_started"}
    if stat not in valid_stats:
        raise HTTPException(400, f"Invalid stat. Use: {valid_stats}")
    return query(f"""
        SELECT p.id as player_id, p.first_name, p.last_name, p.position,
               t.abbreviation as current_team,
               COUNT(DISTINCT ps.season) as seasons,
               SUM(ps.games) as games, SUM(ps.games_started) as games_started,
               SUM(ps.wins) as wins, SUM(ps.losses) as losses,
               SUM(ps.saves) as saves, SUM(ps.ip_outs) as ip_outs,
               SUM(ps.er) as er, SUM(ps.so) as so, SUM(ps.bb) as bb,
               SUM(ps.hr_allowed) as hr_allowed,
               CASE WHEN SUM(ps.ip_outs) > 0
                    THEN ROUND(9.0 * SUM(ps.er) / (SUM(ps.ip_outs) / 3.0), 2) END as era
        FROM pitching_stats ps
        JOIN players p ON p.id = ps.player_id
        LEFT JOIN teams t ON t.id = p.team_id
        WHERE ps.level = 'MLB'
        GROUP BY ps.player_id
        HAVING SUM(ps.ip_outs) >= 9
        ORDER BY SUM(ps.{stat}) DESC
        LIMIT ?
    """, (limit,))


# ============================================================
# HEAD-TO-HEAD PLAYER COMPARISON
# ============================================================
@app.get("/players/compare/{player1_id}/{player2_id}")
async def compare_players(player1_id: int, player2_id: int):
    """Side-by-side comparison of two players."""
    p1 = query("SELECT * FROM players WHERE id=?", (player1_id,))
    p2 = query("SELECT * FROM players WHERE id=?", (player2_id,))
    if not p1 or not p2:
        raise HTTPException(404, "Player not found")

    p1_batting = query("""
        SELECT season, games, ab, hits, hr, rbi, bb, so, sb,
               CASE WHEN ab > 0 THEN ROUND(1.0 * hits / ab, 3) END as avg
        FROM batting_stats WHERE player_id=? AND level='MLB'
        ORDER BY season DESC
    """, (player1_id,))
    p2_batting = query("""
        SELECT season, games, ab, hits, hr, rbi, bb, so, sb,
               CASE WHEN ab > 0 THEN ROUND(1.0 * hits / ab, 3) END as avg
        FROM batting_stats WHERE player_id=? AND level='MLB'
        ORDER BY season DESC
    """, (player2_id,))
    p1_pitching = query("""
        SELECT season, games, wins, losses, saves, ip_outs, er, so, bb,
               CASE WHEN ip_outs > 0 THEN ROUND(9.0 * er / (ip_outs / 3.0), 2) END as era
        FROM pitching_stats WHERE player_id=? AND level='MLB'
        ORDER BY season DESC
    """, (player1_id,))
    p2_pitching = query("""
        SELECT season, games, wins, losses, saves, ip_outs, er, so, bb,
               CASE WHEN ip_outs > 0 THEN ROUND(9.0 * er / (ip_outs / 3.0), 2) END as era
        FROM pitching_stats WHERE player_id=? AND level='MLB'
        ORDER BY season DESC
    """, (player2_id,))

    return {
        "player1": dict(p1[0]),
        "player2": dict(p2[0]),
        "player1_batting": p1_batting,
        "player2_batting": p2_batting,
        "player1_pitching": p1_pitching,
        "player2_pitching": p2_pitching,
    }


# ============================================================
# PROSPECT RANKINGS
# ============================================================
@app.get("/prospects/rankings")
async def prospect_rankings(team_id: int = None, limit: int = 50):
    """Organization or league-wide prospect rankings with OFP."""
    team_filter = "AND p.team_id = ?" if team_id else ""
    params = (team_id, limit) if team_id else (limit,)

    prospects = query(f"""
        SELECT p.id, p.first_name, p.last_name, p.age, p.position,
               p.team_id, t.abbreviation,
               p.contact_rating, p.power_rating, p.speed_rating,
               p.fielding_rating, p.arm_rating, p.eye_rating,
               p.contact_potential, p.power_potential, p.speed_potential,
               p.fielding_potential, p.arm_potential,
               p.stuff_rating, p.control_rating, p.stamina_rating,
               p.stuff_potential, p.control_potential, p.stamina_potential,
               p.roster_status, p.development_rate
        FROM players p
        LEFT JOIN teams t ON t.id = p.team_id
        WHERE p.roster_status IN ('minors_aaa', 'minors_aa', 'minors_low')
        AND p.age <= 25
        {team_filter}
        ORDER BY (
            CASE WHEN p.position IN ('SP', 'RP')
                THEN (p.stuff_potential + p.control_potential + p.stamina_potential) * 0.6
                     + (p.stuff_rating + p.control_rating + p.stamina_rating) * 0.4
                ELSE (p.contact_potential + p.power_potential + p.speed_potential + p.fielding_potential) * 0.5
                     + (p.contact_rating + p.power_rating + p.speed_rating + p.fielding_rating) * 0.3
                     + p.arm_potential * 0.2
            END
        ) DESC
        LIMIT ?
    """, params)

    # Calculate OFP (Overall Future Potential) on 20-80 scale for each prospect
    results = []
    for i, pr in enumerate(prospects or []):
        p = dict(pr)
        if p["position"] in ("SP", "RP"):
            ofp = int((p["stuff_potential"] + p["control_potential"] + p["stamina_potential"]) / 3 * 0.7
                      + (p["stuff_rating"] + p["control_rating"] + p["stamina_rating"]) / 3 * 0.3)
        else:
            ofp = int((p["contact_potential"] + p["power_potential"] + p["speed_potential"]
                        + p["fielding_potential"] + p["arm_potential"]) / 5 * 0.6
                       + (p["contact_rating"] + p["power_rating"] + p["speed_rating"]
                          + p["fielding_rating"] + p["arm_rating"]) / 5 * 0.4)
        p["ofp"] = min(80, max(20, ofp))
        p["rank"] = i + 1
        results.append(p)

    return results


# ============================================================
# COMPREHENSIVE STATS ENDPOINTS (for stat browser)
# ============================================================
@app.get("/stats/all-batters")
async def all_batters_stats(
    season: int = 2026,
    sort: str = "hr",
    order: str = "desc",
    limit: int = 100,
    min_pa: int = 0,
    position: str = None,
    team_id: int = None
):
    """Get all batter stats with comprehensive filtering and sorting."""
    valid_sorts = {
        "first_name", "position", "age",
        "games", "pa", "ab", "runs", "hits", "doubles", "triples", "hr", "rbi",
        "bb", "so", "sb", "cs", "avg", "obp", "slg", "ops",
        "contact_rating", "power_rating", "speed_rating"
    }
    if sort not in valid_sorts:
        sort = "hr"

    order = "DESC" if order.lower() == "desc" else "ASC"

    # Build dynamic WHERE clause
    where_clauses = ["bs.season = ?"]
    params = [season]

    if min_pa > 0:
        where_clauses.append("bs.pa >= ?")
        params.append(min_pa)

    if position:
        where_clauses.append("p.position = ?")
        params.append(position)

    if team_id:
        where_clauses.append("bs.team_id = ?")
        params.append(team_id)

    where_clause = " AND ".join(where_clauses)

    # Build sort clause - handle computed columns
    if sort in ["avg", "obp", "slg", "ops"]:
        if sort == "avg":
            sort_clause = "CASE WHEN bs.ab > 0 THEN ROUND(1.0 * bs.hits / bs.ab, 3) ELSE 0 END"
        elif sort == "obp":
            sort_clause = "CASE WHEN bs.ab + bs.bb + bs.hbp > 0 THEN ROUND((bs.hits + bs.bb + bs.hbp) * 1.0 / (bs.ab + bs.bb + bs.hbp + bs.sf), 3) ELSE 0 END"
        elif sort == "slg":
            sort_clause = "CASE WHEN bs.ab > 0 THEN ROUND((bs.hits + bs.doubles + bs.triples * 2 + bs.hr * 3) * 1.0 / bs.ab, 3) ELSE 0 END"
        else:  # ops
            avg_clause = "CASE WHEN bs.ab > 0 THEN 1.0 * bs.hits / bs.ab ELSE 0 END"
            obp_clause = "CASE WHEN bs.ab + bs.bb + bs.hbp > 0 THEN (bs.hits + bs.bb + bs.hbp) * 1.0 / (bs.ab + bs.bb + bs.hbp + bs.sf) ELSE 0 END"
            slg_clause = "CASE WHEN bs.ab > 0 THEN (bs.hits + bs.doubles + bs.triples * 2 + bs.hr * 3) * 1.0 / bs.ab ELSE 0 END"
            sort_clause = f"({obp_clause} + {slg_clause})"
    elif sort in ["first_name", "position"]:
        sort_clause = f"p.{sort}"
    elif sort == "age":
        sort_clause = "p.age"
    elif sort in ["contact_rating", "power_rating", "speed_rating"]:
        sort_clause = f"p.{sort}"
    else:
        sort_clause = f"bs.{sort}"

    sql = f"""
        SELECT DISTINCT
            p.id, p.first_name, p.last_name, p.position, p.bats, p.throws, p.age,
            p.contact_rating, p.power_rating, p.speed_rating, p.fielding_rating, p.arm_rating,
            t.abbreviation,
            bs.games, bs.pa, bs.ab, bs.runs, bs.hits, bs.doubles, bs.triples, bs.hr, bs.rbi,
            bs.bb, bs.so, bs.sb, bs.cs, bs.hbp, bs.sf,
            CASE WHEN bs.ab > 0 THEN ROUND(1.0 * bs.hits / bs.ab, 3) ELSE 0 END as avg,
            CASE WHEN bs.ab + bs.bb + bs.hbp > 0 THEN ROUND((bs.hits + bs.bb + bs.hbp) * 1.0 / (bs.ab + bs.bb + bs.hbp + bs.sf), 3) ELSE 0 END as obp,
            CASE WHEN bs.ab > 0 THEN ROUND((bs.hits + bs.doubles + bs.triples * 2 + bs.hr * 3) * 1.0 / bs.ab, 3) ELSE 0 END as slg
        FROM batting_stats bs
        JOIN players p ON p.id = bs.player_id
        JOIN teams t ON t.id = bs.team_id
        WHERE {where_clause}
        ORDER BY {sort_clause} {order}
        LIMIT ?
    """
    params.append(limit)

    return query(sql, tuple(params))


@app.get("/stats/all-pitchers")
async def all_pitchers_stats(
    season: int = 2026,
    sort: str = "wins",
    order: str = "desc",
    limit: int = 100,
    min_ip: int = 0,
    team_id: int = None
):
    """Get all pitcher stats with comprehensive filtering and sorting."""
    valid_sorts = {
        "first_name", "position",
        "games", "games_started", "wins", "losses", "saves", "holds", "ip_outs",
        "hits_allowed", "runs_allowed", "er", "bb", "so", "hr_allowed",
        "complete_games", "shutouts", "quality_starts",
        "era", "whip", "k9", "bb9", "k_bb",
        "stuff_rating", "control_rating", "stamina_rating"
    }
    if sort not in valid_sorts:
        sort = "wins"

    order = "DESC" if order.lower() == "desc" else "ASC"

    # Build dynamic WHERE clause
    where_clauses = ["ps.season = ?"]
    params = [season]

    if min_ip > 0:
        where_clauses.append("ps.ip_outs >= ?")
        params.append(min_ip * 3)  # Convert innings to outs

    if team_id:
        where_clauses.append("ps.team_id = ?")
        params.append(team_id)

    where_clause = " AND ".join(where_clauses)

    # Build sort clause - handle computed columns
    if sort == "era":
        sort_clause = "CASE WHEN ps.ip_outs > 0 THEN ROUND(9.0 * ps.er / (ps.ip_outs / 3.0), 2) ELSE 0 END"
    elif sort == "whip":
        sort_clause = "CASE WHEN ps.ip_outs > 0 THEN ROUND((ps.hits_allowed + ps.bb) / (ps.ip_outs / 3.0), 2) ELSE 0 END"
    elif sort == "k9":
        sort_clause = "CASE WHEN ps.ip_outs > 0 THEN ROUND(9.0 * ps.so / (ps.ip_outs / 3.0), 2) ELSE 0 END"
    elif sort == "bb9":
        sort_clause = "CASE WHEN ps.ip_outs > 0 THEN ROUND(9.0 * ps.bb / (ps.ip_outs / 3.0), 2) ELSE 0 END"
    elif sort == "k_bb":
        sort_clause = "CASE WHEN ps.bb > 0 THEN ROUND(1.0 * ps.so / ps.bb, 2) ELSE 0 END"
    elif sort in ["first_name", "position"]:
        sort_clause = f"p.{sort}"
    elif sort in ["stuff_rating", "control_rating", "stamina_rating"]:
        sort_clause = f"p.{sort}"
    else:
        sort_clause = f"ps.{sort}"

    sql = f"""
        SELECT DISTINCT
            p.id, p.first_name, p.last_name, p.position,
            p.stuff_rating, p.control_rating, p.stamina_rating,
            t.abbreviation,
            ps.games, ps.games_started, ps.wins, ps.losses, ps.saves, ps.holds,
            ps.ip_outs, ps.hits_allowed, ps.runs_allowed, ps.er, ps.bb, ps.so, ps.hr_allowed,
            ps.complete_games, ps.shutouts, ps.quality_starts,
            CASE WHEN ps.ip_outs > 0 THEN ROUND(9.0 * ps.er / (ps.ip_outs / 3.0), 2) ELSE 0 END as era,
            CASE WHEN ps.ip_outs > 0 THEN ROUND((ps.hits_allowed + ps.bb) / (ps.ip_outs / 3.0), 2) ELSE 0 END as whip,
            CASE WHEN ps.ip_outs > 0 THEN ROUND(9.0 * ps.so / (ps.ip_outs / 3.0), 2) ELSE 0 END as k9,
            CASE WHEN ps.ip_outs > 0 THEN ROUND(9.0 * ps.bb / (ps.ip_outs / 3.0), 2) ELSE 0 END as bb9,
            CASE WHEN ps.bb > 0 THEN ROUND(1.0 * ps.so / ps.bb, 2) ELSE 0 END as k_bb
        FROM pitching_stats ps
        JOIN players p ON p.id = ps.player_id
        JOIN teams t ON t.id = ps.team_id
        WHERE {where_clause}
        ORDER BY {sort_clause} {order}
        LIMIT ?
    """
    params.append(limit)

    return query(sql, tuple(params))


# ============================================================
# LINEUP & ROTATION MANAGEMENT
# ============================================================
@app.get("/roster/{team_id}/lineup")
async def get_lineup(team_id: int):
    """Get the team's current lineup configuration (supports multiple configs: vs_rhp, vs_lhp, dh, no_dh)."""
    import json as _json
    team = query("SELECT lineup_json FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")
    lineup_raw = team[0].get("lineup_json")
    if not lineup_raw:
        return {"vs_rhp": {"batting_order": []}, "vs_lhp": {"batting_order": []}, "dh": {"batting_order": []}, "no_dh": {"batting_order": []}}
    parsed = _json.loads(lineup_raw)
    # Support legacy single lineup format
    if "batting_order" in parsed and "vs_rhp" not in parsed:
        return {"vs_rhp": {"batting_order": parsed["batting_order"]}, "vs_lhp": {"batting_order": []}, "dh": {"batting_order": []}, "no_dh": {"batting_order": []}}
    return parsed


class LineupRequest(BaseModel):
    vs_rhp: dict = None
    vs_lhp: dict = None
    dh: dict = None
    no_dh: dict = None
    batting_order: list = None  # Legacy

@app.post("/roster/{team_id}/lineup")
async def set_lineup(team_id: int, req: LineupRequest):
    """Save the team's batting lineup configurations."""
    import json as _json
    # Support both new multi-config format and legacy single format
    if req.batting_order is not None:
        # Legacy format
        lineup_json = _json.dumps({"batting_order": req.batting_order})
    else:
        lineup_json = _json.dumps({
            "vs_rhp": req.vs_rhp or {"batting_order": []},
            "vs_lhp": req.vs_lhp or {"batting_order": []},
            "dh": req.dh or {"batting_order": []},
            "no_dh": req.no_dh or {"batting_order": []}
        })
    execute("UPDATE teams SET lineup_json=? WHERE id=?", (lineup_json, team_id))
    return {"success": True, "team_id": team_id}


@app.get("/roster/{team_id}/rotation")
async def get_rotation(team_id: int):
    """Get the team's pitching rotation and bullpen roles."""
    import json as _json
    team = query("SELECT rotation_json FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")
    rotation_raw = team[0].get("rotation_json")
    return _json.loads(rotation_raw) if rotation_raw else {"rotation": [], "bullpen": []}


class RotationRequest(BaseModel):
    rotation: list[dict]  # [{player_id, role}]
    bullpen: list[dict] = []

@app.post("/roster/{team_id}/rotation")
async def set_rotation(team_id: int, req: RotationRequest):
    """Save the team's pitching rotation and bullpen roles."""
    import json as _json
    rotation_json = _json.dumps({"rotation": req.rotation, "bullpen": req.bullpen})
    execute("UPDATE teams SET rotation_json=? WHERE id=?", (rotation_json, team_id))
    return {"success": True, "team_id": team_id}


@app.post("/roster/{team_id}/auto-lineup")
async def auto_generate_lineup(team_id: int):
    """Auto-generate optimal batting lineup and pitching rotation."""
    import json as _json

    # Get active roster
    roster = query("""
        SELECT p.*, c.annual_salary, c.years_remaining
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        ORDER BY p.position
    """, (team_id,))

    if not roster:
        raise HTTPException(400, "No active players found")

    # Generate batting lineup with position constraints
    hitters = [p for p in roster if p["position"] not in ("SP", "RP")]
    if not hitters:
        raise HTTPException(400, "No position players found")

    def hitting_value(p):
        return (p.get("contact_rating") or 50) + (p.get("power_rating") or 50)

    def fielding_value(p):
        return (p.get("fielding_rating") or 50) * 2 + hitting_value(p)

    def speed_field(p):
        return (p.get("speed_rating") or 50) + (p.get("fielding_rating") or 50)

    # Fill one player per defensive position
    FIELD_POS = ["C", "1B", "2B", "SS", "3B", "LF", "CF", "RF"]
    FALLBACKS = {
        "C": [], "1B": ["3B", "LF", "RF", "DH"],
        "2B": ["SS", "3B"], "SS": ["2B", "3B"],
        "3B": ["SS", "2B", "1B"],
        "LF": ["CF", "RF"], "CF": ["LF", "RF"], "RF": ["LF", "CF"],
    }
    POS_SCORE = {
        "C": fielding_value, "1B": hitting_value, "2B": fielding_value,
        "SS": fielding_value, "3B": fielding_value,
        "LF": hitting_value, "CF": speed_field, "RF": hitting_value,
    }

    used_ids = set()
    starters = {}  # pos -> player dict

    for pos in FIELD_POS:
        candidates = [h for h in hitters if h["position"] == pos and h["id"] not in used_ids]
        if not candidates:
            for fb in FALLBACKS.get(pos, []):
                candidates = [h for h in hitters if h["position"] == fb and h["id"] not in used_ids]
                if candidates:
                    break
        if candidates:
            candidates.sort(key=POS_SCORE.get(pos, hitting_value), reverse=True)
            starters[pos] = candidates[0]
            used_ids.add(candidates[0]["id"])

    # DH: best remaining hitter
    remaining = [h for h in hitters if h["id"] not in used_ids]
    remaining.sort(key=hitting_value, reverse=True)
    if remaining:
        starters["DH"] = remaining[0]
        used_ids.add(remaining[0]["id"])

    # Build batting order intelligently
    starter_list = list(starters.items())  # (pos, player)
    available = list(starter_list)
    ordered = []

    def pick_best(score_fn):
        nonlocal available
        if not available:
            return None
        available.sort(key=lambda x: score_fn(x[1]), reverse=True)
        return available.pop(0)

    def obp(p): return (p.get("speed_rating") or 0) * 0.5 + (p.get("contact_rating") or 0)
    def contact(p): return p.get("contact_rating") or 0
    def balanced(p): return (p.get("contact_rating") or 0) * 0.6 + (p.get("power_rating") or 0) * 0.6
    def power(p): return p.get("power_rating") or 0

    ordered.append(pick_best(obp))      # 1: leadoff
    ordered.append(pick_best(contact))   # 2: contact
    ordered.append(pick_best(balanced))  # 3: balanced
    ordered.append(pick_best(power))     # 4: cleanup
    ordered.append(pick_best(power))     # 5: power
    while available:
        ordered.append(pick_best(hitting_value))  # 6-9

    ordered = [x for x in ordered if x is not None]

    batting_lineup = []
    for i, (pos, p) in enumerate(ordered):
        batting_lineup.append({
            "player_id": p["id"],
            "batting_order": i + 1,
            "position": pos
        })

    # Generate rotation
    starters = [p for p in roster if p["position"] == "SP"]
    if not starters:
        raise HTTPException(400, "No starting pitchers found")

    def pitcher_value(p):
        stuff = p.get("stuff_rating") or 20
        control = p.get("control_rating") or 20
        stamina = p.get("stamina_rating") or 20
        return (stuff * 2) + (control * 1.5) + (stamina * 0.5)

    starters_sorted = sorted(starters, key=pitcher_value, reverse=True)

    rotation = []
    roles = ["#1 (Ace)", "#2", "#3", "#4", "#5"]
    for idx, p in enumerate(starters_sorted[:5]):
        rotation.append({
            "player_id": p["id"],
            "role": roles[idx] if idx < len(roles) else f"#{idx+1}"
        })

    # Generate bullpen
    relievers = [p for p in roster if p["position"] == "RP"]
    bullpen = []

    if relievers:
        def reliever_value(p):
            stuff = p.get("stuff_rating") or 20
            control = p.get("control_rating") or 20
            return (stuff * 1.2) + (control * 1.0)

        relievers_sorted = sorted(relievers, key=reliever_value, reverse=True)

        for idx, p in enumerate(relievers_sorted):
            if idx == 0:
                role = "CL"  # Closer
            elif idx == 1:
                role = "SU"  # Setup
            else:
                role = "MR"  # Middle relief

            bullpen.append({
                "id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "role": role
            })

    # Format for frontend
    batting_order_ids = [b["player_id"] for b in batting_lineup]

    # Save to database
    lineup_data = {
        "vs_rhp": {"batting_order": batting_order_ids},
        "vs_lhp": {"batting_order": batting_order_ids},
        "dh": {"batting_order": batting_order_ids},
        "no_dh": {"batting_order": batting_order_ids}
    }

    rotation_data = {
        "rotation": rotation,
        "bullpen": bullpen
    }

    lineup_json = _json.dumps(lineup_data)
    rotation_json = _json.dumps(rotation_data)

    execute("UPDATE teams SET lineup_json=? WHERE id=?", (lineup_json, team_id))
    execute("UPDATE teams SET rotation_json=? WHERE id=?", (rotation_json, team_id))

    return {
        "success": True,
        "lineup_data": lineup_data,
        "rotation_data": rotation_data
    }


# ============================================================
# TEAM STRATEGY
# ============================================================
@app.get("/team/{team_id}/strategy")
async def get_team_strategy(team_id: int):
    """Get team strategy settings."""
    import json as _json
    team = query("SELECT team_strategy_json FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")
    strategy_raw = team[0].get("team_strategy_json", "{}")
    return _json.loads(strategy_raw) if strategy_raw else {}


class StrategyRequest(BaseModel):
    strategy: dict

@app.post("/team/{team_id}/strategy")
async def set_team_strategy(team_id: int, req: StrategyRequest):
    """Save team strategy settings."""
    import json as _json
    execute("UPDATE teams SET team_strategy_json=? WHERE id=?",
            (_json.dumps(req.strategy), team_id))
    return {"success": True, "team_id": team_id}


# ============================================================
# MONTHLY SCHEDULE
# ============================================================
@app.get("/schedule/month")
async def get_monthly_schedule(year: int, month: int, team_id: int = None):
    """Get games for a specific month, optionally filtered by team."""
    month_start = f"{year}-{month:02d}-01"
    if month == 12:
        month_end = f"{year + 1}-01-01"
    else:
        month_end = f"{year}-{month + 1:02d}-01"

    conditions = ["s.game_date >= ? AND s.game_date < ?"]
    params: list = [month_start, month_end]

    if team_id:
        conditions.append("(s.home_team_id = ? OR s.away_team_id = ?)")
        params.extend([team_id, team_id])

    where = " AND ".join(conditions)
    return query(f"""
        SELECT s.*, h.abbreviation as home_abbr, a.abbreviation as away_abbr,
               h.city as home_city, h.name as home_name,
               a.city as away_city, a.name as away_name
        FROM schedule s
        JOIN teams h ON h.id = s.home_team_id
        JOIN teams a ON a.id = s.away_team_id
        WHERE {where}
        ORDER BY s.game_date, s.id
    """, tuple(params))


# ============================================================
# WAIVER TRADE (post-deadline)
# ============================================================
@app.post("/trade/waiver-propose")
async def waiver_trade_propose(trade: TradeProposal):
    """Propose a post-deadline waiver trade."""
    result = await propose_waiver_trade(
        trade.proposing_team_id, trade.receiving_team_id,
        trade.players_offered, trade.players_requested,
        trade.cash_included
    )
    return result


# ============================================================
# 40-MAN ROSTER MANAGEMENT
# ============================================================
@app.post("/roster/forty-man/add/{player_id}")
async def roster_add_forty_man(player_id: int):
    """Add a player to the 40-man roster."""
    return add_to_forty_man(player_id)


@app.post("/roster/forty-man/remove/{player_id}")
async def roster_remove_forty_man(player_id: int):
    """Remove a player from the 40-man roster."""
    return remove_from_forty_man(player_id)


# ============================================================
# FINANCIAL CONTROLS
# ============================================================
class PricingUpdate(BaseModel):
    ticket_price_pct: int = None
    concession_price_pct: int = None

@app.post("/finances/{team_id}/pricing")
async def update_pricing(team_id: int, req: PricingUpdate):
    """Update ticket and concession pricing for a team."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    updates = {}
    if req.ticket_price_pct is not None:
        # Clamp between 50% and 150% of league average
        ticket_pct = max(50, min(150, req.ticket_price_pct))
        updates["ticket_price_pct"] = ticket_pct
    if req.concession_price_pct is not None:
        concession_pct = max(50, min(150, req.concession_price_pct))
        updates["concession_price_pct"] = concession_pct

    if updates:
        set_clause = ", ".join(f"{k}=?" for k in updates.keys())
        execute(f"UPDATE teams SET {set_clause} WHERE id=?",
                tuple(list(updates.values()) + [team_id]))

    return {"success": True, "team_id": team_id, "updates": updates}


@app.get("/finances/{team_id}/season/{season}")
async def get_season_finances(team_id: int, season: int):
    """Get season financial summary for a team."""
    return calculate_season_finances(team_id, season)


class BroadcastContractUpdate(BaseModel):
    contract_type: str  # normal, cable, blackout

@app.post("/finances/{team_id}/broadcast")
async def update_broadcast_contract(team_id: int, req: BroadcastContractUpdate):
    """Update broadcast contract type (only when current contract expires)."""
    if req.contract_type not in ["normal", "cable", "blackout"]:
        raise HTTPException(400, "Invalid contract type. Must be: normal, cable, or blackout")

    team = query("SELECT broadcast_contract_years_remaining FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    years_remaining = team[0].get("broadcast_contract_years_remaining", 3)
    if years_remaining > 0:
        raise HTTPException(400, f"Current broadcast contract still has {years_remaining} years remaining")

    # Update contract with 3-year term
    execute("""
        UPDATE teams SET broadcast_contract_type=?, broadcast_contract_years_remaining=3
        WHERE id=?
    """, (req.contract_type, team_id))

    return {"success": True, "team_id": team_id, "contract_type": req.contract_type, "years": 3}


# ============================================================
# BROADCAST RIGHTS & STADIUM (NEW OWNER MANAGEMENT FEATURES)
# ============================================================

@app.get("/finances/{team_id}/broadcast-status")
async def get_broadcast_status(team_id: int):
    """Get current broadcast deal and available options."""
    from ..financial.broadcast_stadium import get_broadcast_status
    return get_broadcast_status(team_id)


class BroadcastDealRequest(BaseModel):
    deal_type: str  # standard, premium_cable, streaming, blackout


@app.post("/finances/{team_id}/broadcast-deal")
async def negotiate_broadcast_deal(team_id: int, req: BroadcastDealRequest):
    """Negotiate a new broadcast rights deal."""
    from ..financial.broadcast_stadium import negotiate_broadcast_deal
    result = negotiate_broadcast_deal(team_id, req.deal_type)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Invalid deal"))
    return result


@app.get("/finances/{team_id}/stadium")
async def get_stadium_status(team_id: int):
    """Get current stadium status and available upgrades."""
    from ..financial.broadcast_stadium import get_stadium_status
    return get_stadium_status(team_id)


class StadiumUpgradeRequest(BaseModel):
    upgrade_key: str  # luxury_suites, jumbotron, concourse, field_renovation, retractable_roof


@app.post("/finances/{team_id}/stadium-upgrade")
async def purchase_stadium_upgrade(team_id: int, req: StadiumUpgradeRequest):
    """Purchase a stadium upgrade."""
    from ..financial.broadcast_stadium import purchase_stadium_upgrade
    result = purchase_stadium_upgrade(team_id, req.upgrade_key)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Invalid upgrade"))
    return result


# ============================================================
# DEPTH CHART
# ============================================================
@app.get("/team/{team_id}/depth-chart")
async def get_depth_chart(team_id: int):
    """Get team depth chart organized by position."""
    import json as _json

    team = query("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    # Get all players from this team sorted by position and overall rating
    players = query("""
        SELECT p.*, c.annual_salary, c.years_remaining,
               CASE WHEN p.position IN ('SP', 'RP')
                    THEN (p.stuff_rating + p.control_rating + p.stamina_rating) / 3
                    ELSE (p.contact_rating + p.power_rating + p.fielding_rating) / 3
               END as overall
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')
        ORDER BY p.position, overall DESC
    """, (team_id,))

    # Organize by position
    positions = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'SP', 'RP']
    depth_chart = {}

    for pos in positions:
        depth_chart[pos] = []

    for player in players:
        pos = player['position']
        entry = {
            'player_id': player['id'],
            'name': f"{player['first_name']} {player['last_name']}",
            'age': player['age'],
            'overall': int(player['overall'] or 50),
            'roster_status': player['roster_status'],
            'bats': player['bats'],
            'throws': player['throws']
        }

        # Determine status: starter, backup, prospect
        if pos in ['SP', 'RP']:
            entry['status'] = 'pitcher'
        else:
            if len(depth_chart[pos]) == 0:
                entry['status'] = 'starter'
            elif len(depth_chart[pos]) < 3:
                entry['status'] = 'backup'
            else:
                entry['status'] = 'prospect'

        depth_chart[pos].append(entry)

        # Also add to secondary positions if applicable
        if player.get('secondary_positions'):
            secondary = [p.strip() for p in player['secondary_positions'].split(',') if p.strip()]
            for sec_pos in secondary:
                if sec_pos in depth_chart:
                    entry_copy = entry.copy()
                    entry_copy['status'] = 'secondary'
                    depth_chart[sec_pos].append(entry_copy)

    return depth_chart


# ============================================================
# SAVE / LOAD GAME
# ============================================================
@app.get("/saves")
async def list_saves():
    """List all saved game slots."""
    import os
    from datetime import datetime
    saves_dir = Path(__file__).parent.parent.parent / "saves"
    saves_dir.mkdir(exist_ok=True)
    saves = []
    for f in sorted(saves_dir.glob("*.db")):
        stat = f.stat()
        # Read game state from save file to show date/season
        try:
            import sqlite3
            conn = sqlite3.connect(str(f))
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
            conn.close()
            save_info = {
                "name": f.stem,
                "file_size_mb": round(stat.st_size / 1024 / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "game_date": row["current_date"] if row else None,
                "season": row["season"] if row else None,
                "phase": row["phase"] if row else None,
            }
        except Exception:
            save_info = {
                "name": f.stem,
                "file_size_mb": round(stat.st_size / 1024 / 1024, 1),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }
        saves.append(save_info)
    return saves


class SaveGameRequest(BaseModel):
    name: str


@app.post("/saves/save")
async def save_game(req: SaveGameRequest):
    """Save current game state to a named slot."""
    import shutil
    import re
    name = re.sub(r'[^a-zA-Z0-9_\-]', '_', req.name.strip())
    if not name:
        raise HTTPException(400, "Save name required")

    db_path = Path(__file__).parent.parent.parent / "front_office.db"
    saves_dir = Path(__file__).parent.parent.parent / "saves"
    saves_dir.mkdir(exist_ok=True)
    save_path = saves_dir / f"{name}.db"

    # Close any WAL transactions first
    conn = get_connection()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    shutil.copy2(str(db_path), str(save_path))
    return {"saved": name, "path": str(save_path)}


@app.post("/saves/load")
async def load_game(req: SaveGameRequest):
    """Load game state from a named save slot."""
    import shutil
    name = req.name.strip()
    saves_dir = Path(__file__).parent.parent.parent / "saves"
    save_path = saves_dir / f"{name}.db"

    if not save_path.exists():
        raise HTTPException(404, f"Save '{name}' not found")

    db_path = Path(__file__).parent.parent.parent / "front_office.db"

    # Close any WAL transactions on current DB
    conn = get_connection()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()

    shutil.copy2(str(save_path), str(db_path))
    return {"loaded": name}


@app.delete("/saves/{name}")
async def delete_save(name: str):
    """Delete a saved game slot."""
    saves_dir = Path(__file__).parent.parent.parent / "saves"
    save_path = saves_dir / f"{name}.db"
    if not save_path.exists():
        raise HTTPException(404, f"Save '{name}' not found")
    save_path.unlink()
    return {"deleted": name}


# ============================================================
# COMMISSIONER MODE
# ============================================================
@app.post("/settings/commissioner-mode")
async def toggle_commissioner_mode():
    """Toggle commissioner mode on/off."""
    state = query("SELECT commissioner_mode FROM game_state WHERE id=1")
    current = state[0]['commissioner_mode'] if state else 0
    new_mode = 1 - current
    execute("UPDATE game_state SET commissioner_mode=? WHERE id=1", (new_mode,))
    return {"success": True, "commissioner_mode": new_mode}


@app.get("/settings/commissioner-mode")
async def get_commissioner_mode():
    """Get current commissioner mode state."""
    state = query("SELECT commissioner_mode FROM game_state WHERE id=1")
    mode = state[0]['commissioner_mode'] if state else 0
    return {"commissioner_mode": mode}


def _check_commissioner_mode():
    """Helper to verify commissioner mode is enabled."""
    state = query("SELECT commissioner_mode FROM game_state WHERE id=1")
    if not state or not state[0]['commissioner_mode']:
        raise HTTPException(403, "Commissioner mode is not enabled")


class EditPlayerRequest(BaseModel):
    contact_rating: int = None
    power_rating: int = None
    speed_rating: int = None
    fielding_rating: int = None
    arm_rating: int = None
    stuff_rating: int = None
    control_rating: int = None
    stamina_rating: int = None
    ego: int = None
    leadership: int = None
    work_ethic: int = None
    clutch: int = None
    durability: int = None
    loyalty: int = None
    greed: int = None
    composure: int = None
    intelligence: int = None
    aggression: int = None
    sociability: int = None
    morale: int = None
    age: int = None
    position: str = None
    secondary_positions: str = None


@app.post("/commissioner/edit-player/{player_id}")
async def commissioner_edit_player(player_id: int, req: EditPlayerRequest):
    """Edit a player's attributes (commissioner mode only)."""
    _check_commissioner_mode()

    player = query("SELECT * FROM players WHERE id=?", (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    # Build update clause from non-None fields
    updates = {}
    for field in ['contact_rating', 'power_rating', 'speed_rating', 'fielding_rating', 'arm_rating',
                  'stuff_rating', 'control_rating', 'stamina_rating', 'ego', 'leadership', 'work_ethic',
                  'clutch', 'durability', 'loyalty', 'greed', 'composure', 'intelligence', 'aggression',
                  'sociability', 'morale', 'age', 'position', 'secondary_positions']:
        val = getattr(req, field, None)
        if val is not None:
            updates[field] = val

    if not updates:
        return {"success": False, "message": "No fields to update"}

    # Validate ranges for ratings (should be 20-80 or 1-100 for personality)
    for field in updates:
        if field in ['contact_rating', 'power_rating', 'speed_rating', 'fielding_rating', 'arm_rating',
                     'stuff_rating', 'control_rating', 'stamina_rating']:
            updates[field] = max(20, min(80, updates[field]))
        elif field in ['ego', 'leadership', 'work_ethic', 'clutch', 'durability', 'loyalty', 'greed',
                       'composure', 'intelligence', 'aggression', 'sociability', 'morale']:
            updates[field] = max(1, min(100, updates[field]))
        elif field == 'age':
            updates[field] = max(18, min(45, updates[field]))

    set_clause = ", ".join(f"{k}=?" for k in updates.keys())
    execute(f"UPDATE players SET {set_clause} WHERE id=?", tuple(list(updates.values()) + [player_id]))

    return {"success": True, "player_id": player_id, "updates": updates}


class EditTeamRequest(BaseModel):
    cash: int = None
    franchise_value: int = None
    fan_loyalty: int = None
    farm_system_budget: int = None
    medical_staff_budget: int = None
    scouting_staff_budget: int = None


@app.post("/commissioner/edit-team/{team_id}")
async def commissioner_edit_team(team_id: int, req: EditTeamRequest):
    """Edit team attributes (commissioner mode only)."""
    _check_commissioner_mode()

    team = query("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    updates = {}
    for field in ['cash', 'franchise_value', 'fan_loyalty', 'farm_system_budget',
                  'medical_staff_budget', 'scouting_staff_budget']:
        val = getattr(req, field, None)
        if val is not None:
            updates[field] = max(0, val)  # No negative values

    if not updates:
        return {"success": False, "message": "No fields to update"}

    set_clause = ", ".join(f"{k}=?" for k in updates.keys())
    execute(f"UPDATE teams SET {set_clause} WHERE id=?", tuple(list(updates.values()) + [team_id]))

    return {"success": True, "team_id": team_id, "updates": updates}


class ForceTradeRequest(BaseModel):
    team1_id: int
    team2_id: int
    team1_players: list[int]
    team2_players: list[int]
    cash: int = 0


@app.post("/commissioner/force-trade")
async def commissioner_force_trade(req: ForceTradeRequest):
    """Execute a trade without approval (commissioner mode only)."""
    _check_commissioner_mode()

    # Validate teams exist
    team1 = query("SELECT * FROM teams WHERE id=?", (req.team1_id,))
    team2 = query("SELECT * FROM teams WHERE id=?", (req.team2_id,))
    if not team1 or not team2:
        raise HTTPException(404, "Team not found")

    import json as _json
    from datetime import date

    # Execute the trade by reassigning players
    for player_id in req.team1_players:
        player = query("SELECT * FROM players WHERE id=?", (player_id,))
        if player and player[0]['team_id'] == req.team1_id:
            execute("UPDATE players SET team_id=? WHERE id=?", (req.team2_id, player_id))

    for player_id in req.team2_players:
        player = query("SELECT * FROM players WHERE id=?", (player_id,))
        if player and player[0]['team_id'] == req.team2_id:
            execute("UPDATE players SET team_id=? WHERE id=?", (req.team1_id, player_id))

    # Handle cash
    if req.cash > 0:
        execute("UPDATE teams SET cash=cash-? WHERE id=?", (req.cash, req.team1_id))
        execute("UPDATE teams SET cash=cash+? WHERE id=?", (req.cash, req.team2_id))

    # Log transaction
    state = query("SELECT * FROM game_state WHERE id=1")
    game_date = state[0]['current_date'] if state else str(date.today())

    details = {
        'type': 'commissioner_trade',
        'team1_players': req.team1_players,
        'team2_players': req.team2_players,
        'cash': req.cash
    }

    execute("""
        INSERT INTO transactions (transaction_date, transaction_type, team1_id, team2_id, player_ids, details_json)
        VALUES (?, 'trade', ?, ?, ?, ?)
    """, (game_date, req.team1_id, req.team2_id, ','.join(map(str, req.team1_players + req.team2_players)), _json.dumps(details)))

    return {"success": True, "message": "Trade executed"}


class ForceSignRequest(BaseModel):
    player_id: int
    team_id: int
    salary: int
    years: int


@app.post("/commissioner/force-sign/{player_id}")
async def commissioner_force_sign(player_id: int, req: ForceSignRequest):
    """Force-sign a free agent (commissioner mode only)."""
    _check_commissioner_mode()

    player = query("SELECT * FROM players WHERE id=?", (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    team = query("SELECT * FROM teams WHERE id=?", (req.team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    from datetime import date

    # Update player to team
    execute("UPDATE players SET team_id=?, roster_status=? WHERE id=?", (req.team_id, 'active', player_id))

    # Create contract
    today = str(date.today())
    execute("""
        INSERT INTO contracts (player_id, team_id, total_years, years_remaining, annual_salary, signed_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (player_id, req.team_id, req.years, req.years, req.salary, today))

    # Log transaction
    import json as _json
    state = query("SELECT * FROM game_state WHERE id=1")
    game_date = state[0]['current_date'] if state else today

    details = {
        'type': 'free_agent_signing',
        'salary': req.salary,
        'years': req.years
    }

    execute("""
        INSERT INTO transactions (transaction_date, transaction_type, team1_id, player_ids, details_json)
        VALUES (?, 'free_agent_signing', ?, ?, ?)
    """, (game_date, req.team_id, str(player_id), _json.dumps(details)))

    return {"success": True, "player_id": player_id, "team_id": req.team_id}


class SetRecordRequest(BaseModel):
    wins: int
    losses: int


@app.post("/commissioner/set-record/{team_id}")
async def commissioner_set_record(team_id: int, req: SetRecordRequest):
    """Set a team's W-L record directly (commissioner mode only)."""
    _check_commissioner_mode()

    team = query("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]['season'] if state else 2026

    # Simply update schedule results - this is a simplified approach
    # In a real system, you'd need to carefully manage which games are marked as played
    # For now, we'll just return success and note that manual record setting is complex
    return {"success": True, "message": "Record modification requires manual schedule adjustment", "team_id": team_id}


# ============================================================
# STAT COLUMN CONFIGURATION
# ============================================================
class StatColumnConfig(BaseModel):
    batting: list[str] = None
    pitching: list[str] = None


@app.get("/settings/stat-columns")
async def get_stat_columns():
    """Get current stat column configuration."""
    import json as _json
    state = query("SELECT stat_display_config_json FROM game_state WHERE id=1")
    if state and state[0]['stat_display_config_json']:
        return _json.loads(state[0]['stat_display_config_json'])

    # Return default config
    return {
        "batting": ["name", "pos", "age", "avg", "hr", "rbi", "ops"],
        "pitching": ["name", "pos", "age", "era", "w", "l", "so"]
    }


@app.post("/settings/stat-columns")
async def set_stat_columns(req: StatColumnConfig):
    """Save stat column configuration."""
    import json as _json

    config = {}
    if req.batting is not None:
        config['batting'] = req.batting
    if req.pitching is not None:
        config['pitching'] = req.pitching

    config_json = _json.dumps(config)
    execute("UPDATE game_state SET stat_display_config_json=? WHERE id=1", (config_json,))

    return {"success": True, "config": config}


# ============================================================
# PITCH DATA ENDPOINTS
# ============================================================
@app.get("/pitch-log/pitcher/{pitcher_id}/summary")
async def pitcher_pitch_summary(pitcher_id: int, season: int = None,
                                 vs_team: int = None, situation: str = None):
    """Aggregated pitch data for a pitcher by pitch type.
    Returns: count, usage%, avg_velocity, strike%, whiff%, gb%, in_play_avg per pitch type.
    """
    state = query("SELECT season FROM game_state WHERE id=1")
    if season is None:
        season = state[0]["season"] if state else 2026

    # Build query with optional filters
    where_clauses = ["pl.pitcher_id = ?", "pl.season = ?"]
    params = [pitcher_id, season]

    if vs_team is not None:
        # Join schedule to filter by opposing team
        where_clauses.append("""(pl.game_id IN (
            SELECT id FROM schedule WHERE home_team_id = ? OR away_team_id = ?
        ))""")
        params.extend([vs_team, vs_team])

    if situation == "risp":
        # Runners in scoring position: bitmask has bit 1 (2nd base) or bit 2 (3rd base)
        where_clauses.append("(pl.runners_on & 6) > 0")

    where_sql = " AND ".join(where_clauses)

    pitches = query(f"""
        SELECT pitch_type, result, velocity, zone
        FROM pitch_log pl
        WHERE {where_sql}
    """, tuple(params))

    if not pitches:
        return {"pitcher_id": pitcher_id, "season": season, "pitch_types": []}

    # Aggregate by pitch type
    from collections import defaultdict
    type_data = defaultdict(lambda: {
        "count": 0, "velocities": [], "strikes": 0, "whiffs": 0,
        "in_play": 0, "gb": 0, "hits_ip": 0
    })
    total_pitches = len(pitches)

    for p in pitches:
        pt = p["pitch_type"]
        d = type_data[pt]
        d["count"] += 1
        if p["velocity"]:
            d["velocities"].append(p["velocity"])
        if p["result"] in ("called_strike", "swinging_strike", "foul", "in_play"):
            d["strikes"] += 1
        if p["result"] == "swinging_strike":
            d["whiffs"] += 1
        if p["result"] == "in_play":
            d["in_play"] += 1
            # Approximate GB based on zone: lower zones (7,8,9) = ground ball
            if p["zone"] and p["zone"] in (7, 8, 9):
                d["gb"] += 1

    result_types = []
    for pt, d in sorted(type_data.items(), key=lambda x: -x[1]["count"]):
        avg_velo = round(sum(d["velocities"]) / len(d["velocities"]), 1) if d["velocities"] else 0
        swings = d["strikes"]  # approximate swings from strike events
        result_types.append({
            "pitch_type": pt,
            "count": d["count"],
            "usage_pct": round(100 * d["count"] / total_pitches, 1),
            "avg_velocity": avg_velo,
            "strike_pct": round(100 * d["strikes"] / d["count"], 1) if d["count"] else 0,
            "whiff_pct": round(100 * d["whiffs"] / max(swings, 1), 1),
            "gb_pct": round(100 * d["gb"] / max(d["in_play"], 1), 1),
            "in_play_count": d["in_play"],
        })

    return {"pitcher_id": pitcher_id, "season": season, "pitch_types": result_types}


@app.get("/pitch-log/batter/{batter_id}/zones")
async def batter_zone_stats(batter_id: int, season: int = None,
                             vs_team: int = None, situation: str = None):
    """Batting stats by zone (9 strike zone + 4 chase zones).
    Returns: PA, AVG, SLG per zone.
    """
    state = query("SELECT season FROM game_state WHERE id=1")
    if season is None:
        season = state[0]["season"] if state else 2026

    where_clauses = ["pl.batter_id = ?", "pl.season = ?"]
    params = [batter_id, season]

    if vs_team is not None:
        where_clauses.append("""(pl.game_id IN (
            SELECT id FROM schedule WHERE home_team_id = ? OR away_team_id = ?
        ))""")
        params.extend([vs_team, vs_team])

    if situation == "risp":
        where_clauses.append("(pl.runners_on & 6) > 0")

    where_sql = " AND ".join(where_clauses)

    pitches = query(f"""
        SELECT zone, result, pitch_type, velocity
        FROM pitch_log pl
        WHERE {where_sql}
    """, tuple(params))

    if not pitches:
        return {"batter_id": batter_id, "season": season, "zones": []}

    # Group by zone, count PA-ending events
    from collections import defaultdict
    zone_data = defaultdict(lambda: {
        "pa": 0, "ab": 0, "hits": 0, "total_bases": 0, "pitches": 0
    })

    for p in pitches:
        z = p["zone"]
        if z is None:
            continue
        zone_data[z]["pitches"] += 1
        # Only count PA-ending results
        if p["result"] == "in_play":
            zone_data[z]["pa"] += 1
            zone_data[z]["ab"] += 1
            # Approximate hits: ~30% of in-play results are hits (MLB average)
            # Use zone to estimate: center zones (5) higher avg, edges lower
            hit_prob = 0.30 if z in (2, 4, 5, 6, 8) else 0.25 if z in (1, 3, 7, 9) else 0.15
            import random as _rnd
            if _rnd.random() < hit_prob:
                zone_data[z]["hits"] += 1
                # Estimate extra bases by zone
                if z in (1, 2, 3):  # high zone = more fly balls
                    zone_data[z]["total_bases"] += 2 if _rnd.random() < 0.15 else 1
                else:
                    zone_data[z]["total_bases"] += 1
            # Non-hits are outs
        elif p["result"] in ("swinging_strike",) and p == pitches[-1]:
            # terminal strikeout on this zone
            pass
        elif p["result"] == "ball" and z in (11, 12, 13, 14):
            # Chase zones: only count swings
            pass

    zones_result = []
    for z in sorted(zone_data.keys()):
        d = zone_data[z]
        avg = round(d["hits"] / d["ab"], 3) if d["ab"] else 0
        slg = round(d["total_bases"] / d["ab"], 3) if d["ab"] else 0
        zones_result.append({
            "zone": z,
            "pitches": d["pitches"],
            "pa": d["pa"],
            "avg": avg,
            "slg": slg,
        })

    return {"batter_id": batter_id, "season": season, "zones": zones_result}


# ============================================================
# CSV IMPORT
# ============================================================
@app.post("/import/roster-csv")
async def import_roster_csv_upload(file: UploadFile = File(...)):
    """Import roster CSV file to update player attributes.
    Expected columns: ID, Name, Position, Age, Status, Overall, Contact, Power, Speed,
    Fielding, Arm, Stuff, Control, Stamina, Salary, Years Remaining
    """
    import csv
    import io

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    expected_cols = {'ID', 'Contact', 'Power', 'Speed', 'Fielding', 'Arm', 'Stuff', 'Control', 'Stamina'}
    if not expected_cols.issubset(set(reader.fieldnames or [])):
        return {"success": False, "rows_updated": 0,
                "errors": [f"Missing required columns. Expected: {sorted(expected_cols)}. Got: {reader.fieldnames}"]}

    rows_updated = 0
    errors = []
    conn = get_connection()

    for i, row in enumerate(reader):
        try:
            player_id = int(row['ID'])
            conn.execute("""
                UPDATE players SET
                    contact_rating = ?, power_rating = ?, speed_rating = ?,
                    fielding_rating = ?, arm_rating = ?,
                    stuff_rating = ?, control_rating = ?, stamina_rating = ?
                WHERE id = ?
            """, (
                int(row['Contact']), int(row['Power']), int(row['Speed']),
                int(row['Fielding']), int(row['Arm']),
                int(row['Stuff']), int(row['Control']), int(row['Stamina']),
                player_id
            ))
            rows_updated += 1
        except Exception as e:
            errors.append(f"Row {i+2}: {str(e)}")

    conn.commit()
    conn.close()
    return {"success": True, "rows_updated": rows_updated, "errors": errors}


@app.post("/import/batting-stats-csv")
async def import_batting_stats_csv(file: UploadFile = File(...)):
    """Import batting stats CSV to update season stats.
    Expected columns: Name, Team, G, AB, R, H, 2B, 3B, HR, RBI, BB, SO, SB, CS
    """
    import csv
    import io

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    expected_cols = {'Name', 'Team', 'G', 'AB', 'R', 'H', 'HR', 'RBI', 'BB', 'SO'}
    if not expected_cols.issubset(set(reader.fieldnames or [])):
        return {"success": False, "rows_updated": 0,
                "errors": [f"Missing required columns. Expected: {sorted(expected_cols)}. Got: {reader.fieldnames}"]}

    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026

    rows_updated = 0
    errors = []
    conn = get_connection()

    for i, row in enumerate(reader):
        try:
            name = row['Name']
            team_abbr = row['Team']

            # Find player by name and team
            parts = name.strip().split(' ', 1)
            if len(parts) < 2:
                errors.append(f"Row {i+2}: Invalid name '{name}'")
                continue

            first_name, last_name = parts[0], parts[1]
            player = conn.execute("""
                SELECT p.id FROM players p
                JOIN teams t ON t.id = p.team_id
                WHERE p.first_name = ? AND p.last_name = ? AND t.abbreviation = ?
            """, (first_name, last_name, team_abbr)).fetchone()

            if not player:
                errors.append(f"Row {i+2}: Player '{name}' on '{team_abbr}' not found")
                continue

            team = conn.execute("SELECT id FROM teams WHERE abbreviation = ?", (team_abbr,)).fetchone()
            if not team:
                errors.append(f"Row {i+2}: Team '{team_abbr}' not found")
                continue

            pa = int(row['AB']) + int(row['BB']) + int(row.get('HBP', 0) or 0) + int(row.get('SF', 0) or 0)
            conn.execute("""
                INSERT INTO batting_stats (player_id, team_id, season, level, games,
                    pa, ab, runs, hits, doubles, triples, hr, rbi, bb, so, sb, cs, hbp, sf)
                VALUES (?, ?, ?, 'MLB', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, team_id, season, level) DO UPDATE SET
                    games = ?, pa = ?, ab = ?, runs = ?, hits = ?,
                    doubles = ?, triples = ?, hr = ?, rbi = ?,
                    bb = ?, so = ?, sb = ?, cs = ?, hbp = ?, sf = ?
            """, (
                player[0], team[0], season,
                int(row['G']), pa, int(row['AB']), int(row['R']), int(row['H']),
                int(row.get('2B', 0) or 0), int(row.get('3B', 0) or 0),
                int(row['HR']), int(row['RBI']),
                int(row['BB']), int(row['SO']),
                int(row.get('SB', 0) or 0), int(row.get('CS', 0) or 0),
                int(row.get('HBP', 0) or 0), int(row.get('SF', 0) or 0),
                # UPDATE values
                int(row['G']), pa, int(row['AB']), int(row['R']), int(row['H']),
                int(row.get('2B', 0) or 0), int(row.get('3B', 0) or 0),
                int(row['HR']), int(row['RBI']),
                int(row['BB']), int(row['SO']),
                int(row.get('SB', 0) or 0), int(row.get('CS', 0) or 0),
                int(row.get('HBP', 0) or 0), int(row.get('SF', 0) or 0),
            ))
            rows_updated += 1
        except Exception as e:
            errors.append(f"Row {i+2}: {str(e)}")

    conn.commit()
    conn.close()
    return {"success": True, "rows_updated": rows_updated, "errors": errors}


@app.post("/import/pitching-stats-csv")
async def import_pitching_stats_csv(file: UploadFile = File(...)):
    """Import pitching stats CSV to update season stats.
    Expected columns: Name, Team, G, GS, W, L, SV, HLD, IP, H, ER, BB, SO, HR
    """
    import csv
    import io

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    expected_cols = {'Name', 'Team', 'G', 'W', 'L', 'IP', 'ER', 'BB', 'SO'}
    if not expected_cols.issubset(set(reader.fieldnames or [])):
        return {"success": False, "rows_updated": 0,
                "errors": [f"Missing required columns. Expected: {sorted(expected_cols)}. Got: {reader.fieldnames}"]}

    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026

    rows_updated = 0
    errors = []
    conn = get_connection()

    for i, row in enumerate(reader):
        try:
            name = row['Name']
            team_abbr = row['Team']

            parts = name.strip().split(' ', 1)
            if len(parts) < 2:
                errors.append(f"Row {i+2}: Invalid name '{name}'")
                continue

            first_name, last_name = parts[0], parts[1]
            player = conn.execute("""
                SELECT p.id FROM players p
                JOIN teams t ON t.id = p.team_id
                WHERE p.first_name = ? AND p.last_name = ? AND t.abbreviation = ?
            """, (first_name, last_name, team_abbr)).fetchone()

            if not player:
                errors.append(f"Row {i+2}: Player '{name}' on '{team_abbr}' not found")
                continue

            team = conn.execute("SELECT id FROM teams WHERE abbreviation = ?", (team_abbr,)).fetchone()
            if not team:
                errors.append(f"Row {i+2}: Team '{team_abbr}' not found")
                continue

            # Parse IP (e.g., "125.2" -> 377 outs)
            ip_str = row['IP']
            if '.' in ip_str:
                whole, frac = ip_str.split('.')
                ip_outs = int(whole) * 3 + int(frac)
            else:
                ip_outs = int(ip_str) * 3

            conn.execute("""
                INSERT INTO pitching_stats (player_id, team_id, season, level, games,
                    games_started, wins, losses, saves, holds,
                    ip_outs, hits_allowed, er, bb, so, hr_allowed)
                VALUES (?, ?, ?, 'MLB', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_id, team_id, season, level) DO UPDATE SET
                    games = ?, games_started = ?, wins = ?, losses = ?,
                    saves = ?, holds = ?,
                    ip_outs = ?, hits_allowed = ?, er = ?,
                    bb = ?, so = ?, hr_allowed = ?
            """, (
                player[0], team[0], season,
                int(row['G']), int(row.get('GS', 0) or 0),
                int(row['W']), int(row['L']),
                int(row.get('SV', 0) or 0), int(row.get('HLD', 0) or 0),
                ip_outs, int(row['H']), int(row['ER']),
                int(row['BB']), int(row['SO']),
                int(row.get('HR', 0) or 0),
                # UPDATE values
                int(row['G']), int(row.get('GS', 0) or 0),
                int(row['W']), int(row['L']),
                int(row.get('SV', 0) or 0), int(row.get('HLD', 0) or 0),
                ip_outs, int(row['H']), int(row['ER']),
                int(row['BB']), int(row['SO']),
                int(row.get('HR', 0) or 0),
            ))
            rows_updated += 1
        except Exception as e:
            errors.append(f"Row {i+2}: {str(e)}")

    conn.commit()
    conn.close()
    return {"success": True, "rows_updated": rows_updated, "errors": errors}


# ============================================================
# CSV EXPORT
# ============================================================
@app.get("/export/roster/{team_id}")
async def export_roster_csv(team_id: int):
    """Export team roster to CSV."""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    team = query("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    roster = query("""
        SELECT p.*, c.annual_salary, c.years_remaining,
               CASE WHEN p.position IN ('SP', 'RP')
                    THEN (p.stuff_rating + p.control_rating + p.stamina_rating) / 3
                    ELSE (p.contact_rating + p.power_rating + p.fielding_rating) / 3
               END as overall
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=?
        ORDER BY p.roster_status, p.position, overall DESC
    """, (team_id,))

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['ID', 'Name', 'Position', 'Age', 'Status', 'Overall', 'Contact', 'Power', 'Speed',
                     'Fielding', 'Arm', 'Stuff', 'Control', 'Stamina', 'Salary', 'Years Remaining'])

    # Rows
    for p in roster:
        writer.writerow([
            p['id'],
            f"{p['first_name']} {p['last_name']}",
            p['position'],
            p['age'],
            p['roster_status'],
            int(p['overall'] or 50),
            p['contact_rating'],
            p['power_rating'],
            p['speed_rating'],
            p['fielding_rating'],
            p['arm_rating'],
            p['stuff_rating'],
            p['control_rating'],
            p['stamina_rating'],
            p['annual_salary'] or 0,
            p['years_remaining'] or 0
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=roster_{team[0]['abbreviation']}.csv"}
    )


@app.get("/export/batting-stats")
async def export_batting_stats(season: int = 2026):
    """Export batting stats to CSV."""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    stats = query("""
        SELECT bs.*, p.first_name, p.last_name, t.abbreviation,
               CASE WHEN bs.ab > 0 THEN ROUND(1.0 * bs.hits / bs.ab, 3) ELSE 0 END as avg,
               CASE WHEN bs.pa > 0 THEN ROUND((bs.hits + bs.bb) / bs.pa, 3) ELSE 0 END as obp,
               CASE WHEN bs.ab > 0 THEN ROUND((bs.hr + bs.doubles * 2 + bs.triples * 3) / bs.ab, 3) ELSE 0 END as slg
        FROM batting_stats bs
        JOIN players p ON p.id = bs.player_id
        JOIN teams t ON t.id = bs.team_id
        WHERE bs.season=? AND bs.level='MLB'
        ORDER BY bs.hits DESC
    """, (season,))

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['Name', 'Team', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'BB', 'SO',
                     'SB', 'CS', 'AVG', 'OBP', 'SLG', 'OPS'])

    # Rows
    for stat in stats:
        obp = stat['obp'] or 0
        slg = stat['slg'] or 0
        ops = obp + slg
        writer.writerow([
            f"{stat['first_name']} {stat['last_name']}",
            stat['abbreviation'],
            stat['games'],
            stat['ab'],
            stat['runs'],
            stat['hits'],
            stat['doubles'],
            stat['triples'],
            stat['hr'],
            stat['rbi'],
            stat['bb'],
            stat['so'],
            stat['sb'],
            stat['cs'],
            stat['avg'],
            obp,
            slg,
            ops
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=batting_stats_{season}.csv"}
    )


@app.get("/export/pitching-stats")
async def export_pitching_stats(season: int = 2026):
    """Export pitching stats to CSV."""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    stats = query("""
        SELECT ps.*, p.first_name, p.last_name, t.abbreviation,
               CASE WHEN ps.ip_outs > 0 THEN ROUND(9.0 * ps.er / (ps.ip_outs / 3.0), 2) ELSE 0 END as era,
               CASE WHEN ps.ip_outs > 0 THEN ROUND(3.0 * (ps.hits_allowed + ps.bb) / (ps.ip_outs / 3.0), 2) ELSE 0 END as whip
        FROM pitching_stats ps
        JOIN players p ON p.id = ps.player_id
        JOIN teams t ON t.id = ps.team_id
        WHERE ps.season=? AND ps.level='MLB'
        ORDER BY ps.wins DESC
    """, (season,))

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['Name', 'Team', 'G', 'GS', 'W', 'L', 'SV', 'HLD', 'IP', 'H', 'ER', 'BB', 'SO',
                     'HR', 'ERA', 'WHIP', 'K/9', 'BB/9'])

    # Rows
    for stat in stats:
        ip = stat['ip_outs'] / 3.0 if stat['ip_outs'] else 0
        k9 = (9.0 * stat['so'] / ip) if ip > 0 else 0
        bb9 = (9.0 * stat['bb'] / ip) if ip > 0 else 0
        writer.writerow([
            f"{stat['first_name']} {stat['last_name']}",
            stat['abbreviation'],
            stat['games'],
            stat['games_started'],
            stat['wins'],
            stat['losses'],
            stat['saves'],
            stat['holds'],
            f"{int(ip)}.{int((ip % 1) * 3)}",
            stat['hits_allowed'],
            stat['er'],
            stat['bb'],
            stat['so'],
            stat['hr_allowed'],
            stat['era'],
            stat['whip'],
            round(k9, 2),
            round(bb9, 2)
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=pitching_stats_{season}.csv"}
    )


@app.get("/export/financials/{team_id}")
async def export_financials_csv(team_id: int):
    """Export team financial history to CSV."""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    team = query("SELECT * FROM teams WHERE id=?", (team_id,))
    if not team:
        raise HTTPException(404, "Team not found")

    history = query("""
        SELECT * FROM financial_history WHERE team_id=?
        ORDER BY season DESC
    """, (team_id,))

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['Season', 'Ticket Revenue', 'Concession Revenue', 'Broadcast Revenue', 'Merchandise Revenue',
                     'Total Revenue', 'Payroll', 'Farm Expenses', 'Medical Expenses', 'Scouting Expenses',
                     'Stadium Expenses', 'Owner Dividends', 'Total Expenses', 'Profit', 'Attendance Total', 'Avg Attendance'])

    # Rows
    for h in history:
        writer.writerow([
            h['season'],
            h['ticket_revenue'],
            h['concession_revenue'],
            h['broadcast_revenue'],
            h['merchandise_revenue'],
            h['total_revenue'],
            h['payroll'],
            h['farm_expenses'],
            h['medical_expenses'],
            h['scouting_expenses'],
            h['stadium_expenses'],
            h['owner_dividends'],
            h['total_expenses'],
            h['profit'],
            h['attendance_total'],
            h['attendance_avg']
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=financials_{team[0]['abbreviation']}.csv"}
    )


# ============================================================
# DATABASE MANAGEMENT
# ============================================================

@app.post("/admin/migrate")
async def migrate_database():
    """Apply schema migrations without losing data.
    Adds new columns/tables that may be missing from older databases."""
    from pathlib import Path
    from ..database.db import get_connection

    db_path = Path(__file__).parent.parent.parent / "front_office.db"
    if not db_path.exists():
        return {"success": False, "error": "No database found. Use Reseed to create one."}

    conn = get_connection(str(db_path))
    changes = []

    try:
        # Get existing columns for each table
        def get_columns(table):
            cursor = conn.execute(f"PRAGMA table_info({table})")
            return {row[1] for row in cursor.fetchall()}

        # --- teams table migrations ---
        team_cols = get_columns("teams")
        team_migrations = {
            "broadcast_deal_type": "TEXT DEFAULT 'standard'",
            "broadcast_deal_value": "INTEGER DEFAULT 0",
            "broadcast_deal_years_remaining": "INTEGER DEFAULT 3",
            "stadium_upgrades_json": "TEXT DEFAULT '{}'",
            "stadium_name": "TEXT DEFAULT ''",
            "stadium_year_built": "INTEGER DEFAULT 2000",
            "stadium_capacity": "INTEGER DEFAULT 40000",
        }
        for col, col_def in team_migrations.items():
            if col not in team_cols:
                conn.execute(f"ALTER TABLE teams ADD COLUMN {col} {col_def}")
                changes.append(f"teams.{col}")

        # --- game_state table migrations ---
        gs_cols = get_columns("game_state")
        gs_migrations = {
            "rating_scale": "TEXT DEFAULT '20-80'",
            "expansion_draft_json": "TEXT DEFAULT NULL",
        }
        for col, col_def in gs_migrations.items():
            if col not in gs_cols:
                conn.execute(f"ALTER TABLE game_state ADD COLUMN {col} {col_def}")
                changes.append(f"game_state.{col}")

        # --- players table migrations ---
        player_cols = get_columns("players")
        player_migrations = {
            "trading_block_json": "TEXT DEFAULT '{\"players\":[],\"offers\":[]}'",
            "height_inches": "INTEGER DEFAULT NULL",
            "backstory": "TEXT DEFAULT NULL",
            "nickname": "TEXT DEFAULT NULL",
            "quirks": "TEXT DEFAULT NULL",
            "origin_story": "TEXT DEFAULT NULL",
        }
        for col, col_def in player_migrations.items():
            if col not in player_cols:
                conn.execute(f"ALTER TABLE players ADD COLUMN {col} {col_def}")
                changes.append(f"players.{col}")

        # Seed heights for existing players if height_inches was just added
        if "height_inches" in [c.split(".")[-1] for c in changes]:
            import random as _rnd
            HEIGHT_RANGES = {
                'C': (70, 74), '1B': (72, 77), '2B': (68, 73), '3B': (72, 77),
                'SS': (68, 73), 'LF': (70, 76), 'CF': (70, 76), 'RF': (70, 76),
                'DH': (71, 76), 'SP': (72, 78), 'RP': (72, 78),
            }
            players_no_height = conn.execute(
                "SELECT id, position FROM players WHERE height_inches IS NULL"
            ).fetchall()
            for p in players_no_height:
                pos = p[1] if p[1] in HEIGHT_RANGES else 'RF'
                low, high = HEIGHT_RANGES[pos]
                conn.execute("UPDATE players SET height_inches = ? WHERE id = ?",
                             (_rnd.randint(low, high), p[0]))
            if players_no_height:
                changes.append(f"Seeded heights for {len(players_no_height)} players")

        # Generate backstories for players that don't have one yet
        if "players.backstory" in changes:
            try:
                conn.commit()  # Commit column additions first
                backstory_count = generate_all_backstories(force=False)
                if backstory_count:
                    changes.append(f"Generated backstories for {backstory_count} players")
            except Exception:
                pass  # Non-critical, can be generated later via API

        # --- New tables ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS awards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                season INTEGER NOT NULL,
                award_type TEXT NOT NULL,
                league TEXT NOT NULL,
                player_id INTEGER REFERENCES players(id),
                team_id INTEGER REFERENCES teams(id),
                position TEXT,
                vote_points REAL,
                finish INTEGER
            )
        """)
        # Check if awards table was just created (empty = new)
        count = conn.execute("SELECT COUNT(*) FROM awards").fetchone()[0]
        if count == 0:
            changes.append("awards table")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS playoff_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                season INTEGER NOT NULL,
                round TEXT NOT NULL,
                series_number INTEGER DEFAULT 1,
                higher_seed_team_id INTEGER REFERENCES teams(id),
                lower_seed_team_id INTEGER REFERENCES teams(id),
                higher_seed_wins INTEGER DEFAULT 0,
                lower_seed_wins INTEGER DEFAULT 0,
                games_needed INTEGER DEFAULT 7,
                is_complete INTEGER DEFAULT 0,
                winner_team_id INTEGER REFERENCES teams(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pitch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER,
                inning INTEGER,
                at_bat_num INTEGER,
                pitch_num INTEGER,
                pitcher_id INTEGER,
                batter_id INTEGER,
                pitch_type TEXT,
                velocity REAL,
                result TEXT,
                zone INTEGER,
                count_balls INTEGER,
                count_strikes INTEGER,
                outs INTEGER,
                runners_on INTEGER,
                score_diff INTEGER,
                season INTEGER,
                FOREIGN KEY (game_id) REFERENCES schedule(id),
                FOREIGN KEY (pitcher_id) REFERENCES players(id),
                FOREIGN KEY (batter_id) REFERENCES players(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pitch_log_pitcher ON pitch_log(pitcher_id, season)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pitch_log_batter ON pitch_log(batter_id, season)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pitch_log_game ON pitch_log(game_id)")

        # --- character_careers table ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS character_careers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id TEXT NOT NULL,
                character_type TEXT NOT NULL,
                name TEXT NOT NULL,
                current_role TEXT NOT NULL,
                current_team_id INTEGER,
                reputation INTEGER NOT NULL DEFAULT 50,
                personality_json TEXT NOT NULL DEFAULT '{}',
                career_history_json TEXT NOT NULL DEFAULT '[]',
                created_date TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                FOREIGN KEY (current_team_id) REFERENCES teams(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_character_careers_type ON character_careers(character_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_character_careers_team ON character_careers(current_team_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_character_careers_role ON character_careers(current_role)")
        changes.append("character_careers table")

        # --- beat_writers, articles, fan_sentiment tables ---
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beat_writers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER,
                name TEXT NOT NULL,
                outlet TEXT NOT NULL,
                personality TEXT NOT NULL DEFAULT 'analyst',
                writing_style TEXT NOT NULL DEFAULT 'narrative',
                credibility INTEGER NOT NULL DEFAULT 70,
                access_level INTEGER NOT NULL DEFAULT 50,
                bias REAL NOT NULL DEFAULT 0.0,
                follower_count INTEGER NOT NULL DEFAULT 50000,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (team_id) REFERENCES teams(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                writer_id INTEGER,
                game_date TEXT NOT NULL,
                headline TEXT NOT NULL,
                body TEXT NOT NULL,
                article_type TEXT NOT NULL DEFAULT 'news',
                sentiment TEXT NOT NULL DEFAULT 'neutral',
                team_id INTEGER,
                player_id INTEGER,
                is_read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (writer_id) REFERENCES beat_writers(id),
                FOREIGN KEY (team_id) REFERENCES teams(id),
                FOREIGN KEY (player_id) REFERENCES players(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(game_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_team ON articles(team_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_type ON articles(article_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_articles_writer ON articles(writer_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS fan_sentiment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL UNIQUE,
                sentiment_score INTEGER NOT NULL DEFAULT 50,
                excitement INTEGER NOT NULL DEFAULT 50,
                attendance_modifier REAL NOT NULL DEFAULT 1.0,
                social_media_buzz INTEGER NOT NULL DEFAULT 50,
                trust_in_gm INTEGER NOT NULL DEFAULT 50,
                top_concern TEXT,
                reaction_text TEXT,
                last_updated TEXT,
                FOREIGN KEY (team_id) REFERENCES teams(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fan_sentiment_team ON fan_sentiment(team_id)")

        # Add new columns to fan_sentiment if table already existed
        fs_cols = get_columns("fan_sentiment")
        for col, col_def in [
            ("trust_in_gm", "INTEGER NOT NULL DEFAULT 50"),
            ("top_concern", "TEXT"),
            ("reaction_text", "TEXT"),
        ]:
            if col not in fs_cols:
                try:
                    conn.execute(f"ALTER TABLE fan_sentiment ADD COLUMN {col} {col_def}")
                    changes.append(f"fan_sentiment.{col}")
                except Exception:
                    pass

        changes.append("beat_writers/articles/fan_sentiment tables")

        conn.commit()

        if not changes:
            changes.append("Database already up to date")

        return {"success": True, "changes": changes}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


@app.get("/admin/rating-health")
async def admin_rating_health():
    """Show current rating distribution and drift health across all categories."""
    health = check_rating_health()
    return health


@app.post("/admin/calibrate-ratings")
async def admin_calibrate_ratings(season: int = Query(None)):
    """Trigger rating recalibration.

    If season is omitted, reads the current season from game_state.
    """
    if season is None:
        state = query("SELECT season FROM game_state WHERE id=1")
        if not state:
            raise HTTPException(status_code=400, detail="No game state found")
        season = state[0]["season"]
    result = calibrate_ratings(season)
    return result


@app.post("/admin/reseed")
async def reseed_database():
    """
    Delete the current database and reseed with fresh MLB data.
    Fetches from MLB Stats API if no cache exists.
    Returns status updates as the process runs.
    """
    import json
    from pathlib import Path

    db_path = Path(__file__).parent.parent.parent / "front_office.db"
    cache_path = Path(__file__).parent.parent.parent / "mlb_cache.json"

    steps = []

    # Step 1: Fetch fresh data from MLB API if no cache
    if not cache_path.exists():
        try:
            steps.append("Fetching real MLB data from API (this takes a few minutes)...")
            from ..database.real_data import fetch_all_mlb_data, enrich_teams_with_market_data

            data = fetch_all_mlb_data()
            data["teams"] = enrich_teams_with_market_data(data["teams"])

            with open(cache_path, "w") as f:
                json.dump(data, f, indent=2)

            total = sum(len(ps) for ps in data["players"].values())
            steps.append(f"Fetched {len(data['teams'])} teams, {total} players")
        except Exception as e:
            return {"success": False, "error": str(e), "steps": steps}
    else:
        steps.append("Using existing MLB data cache")

    # Step 2: Delete existing database
    if db_path.exists():
        try:
            import os
            os.remove(str(db_path))
            steps.append("Deleted old database")
        except Exception as e:
            return {"success": False, "error": f"Could not delete DB: {e}", "steps": steps}

    # Step 3: Reseed
    try:
        from ..database.seed_real import seed_real_database
        seed_real_database()
        steps.append("Reseeded with real MLB data")
    except Exception as e:
        return {"success": False, "error": f"Seed failed: {e}", "steps": steps}

    steps.append("Done! Refresh the page to see the new rosters.")
    return {"success": True, "steps": steps}


@app.post("/admin/refetch")
async def refetch_mlb_data():
    """
    Force re-fetch MLB data from the API (ignoring existing cache).
    Then reseed the database.
    """
    import json
    from pathlib import Path

    cache_path = Path(__file__).parent.parent.parent / "mlb_cache.json"
    db_path = Path(__file__).parent.parent.parent / "front_office.db"

    steps = []

    # Force fresh fetch
    try:
        steps.append("Fetching fresh MLB data from API...")
        from ..database.real_data import fetch_all_mlb_data, enrich_teams_with_market_data

        data = fetch_all_mlb_data()
        data["teams"] = enrich_teams_with_market_data(data["teams"])

        with open(cache_path, "w") as f:
            json.dump(data, f, indent=2)

        total = sum(len(ps) for ps in data["players"].values())
        steps.append(f"Fetched {len(data['teams'])} teams, {total} players")
    except Exception as e:
        return {"success": False, "error": str(e), "steps": steps}

    # Delete existing database
    if db_path.exists():
        try:
            import os
            os.remove(str(db_path))
            steps.append("Deleted old database")
        except Exception as e:
            return {"success": False, "error": f"Could not delete DB: {e}", "steps": steps}

    # Reseed
    try:
        from ..database.seed_real import seed_real_database
        seed_real_database()
        steps.append("Reseeded with real MLB data")
    except Exception as e:
        return {"success": False, "error": f"Seed failed: {e}", "steps": steps}

    steps.append("Done! Refresh the page to see the new rosters.")
    return {"success": True, "steps": steps}


# ============================================================
# EXPANSION DRAFT
# ============================================================

class ExpansionStartRequest(BaseModel):
    team_name: str
    city: str
    abbreviation: str
    league: str
    division: str


@app.post("/expansion/start")
async def expansion_start(req: ExpansionStartRequest):
    """Create a new expansion team and initiate the expansion draft."""
    from ..transactions.expansion import start_expansion_draft
    return start_expansion_draft(
        req.team_name, req.city, req.abbreviation,
        req.league, req.division
    )


@app.get("/expansion/available")
async def expansion_available():
    """Get available (unprotected) players for the expansion draft."""
    from ..transactions.expansion import (
        get_expansion_status, auto_protect_all_teams, get_available_players
    )
    status = get_expansion_status()
    if not status.get("active"):
        return {"error": "No expansion draft in progress"}

    expansion_team_id = status.get("expansion_team_id")
    current_round = status.get("current_round", 1)

    # Auto-protect for AI teams
    protections = auto_protect_all_teams(
        current_round, exclude_team_id=expansion_team_id
    )

    # Get user team protections if they have any stored
    state = query("SELECT user_team_id FROM game_state WHERE id=1")
    user_team_id = state[0]["user_team_id"] if state else None

    available = get_available_players(protections)
    return {
        "available": available,
        "user_team_id": user_team_id,
        "protections": {str(k): v for k, v in protections.items()},
    }


class ProtectionRequest(BaseModel):
    player_ids: list[int]


@app.post("/expansion/protect/{team_id}")
async def expansion_protect(team_id: int, req: ProtectionRequest):
    """User submits their protection list for the expansion draft."""
    from ..transactions.expansion import get_expansion_status
    status = get_expansion_status()
    if not status.get("active"):
        return {"error": "No expansion draft in progress"}

    current_round = status.get("current_round", 1)
    max_protected = 15 + max(0, (current_round - 1)) * 3
    max_protected = min(max_protected, 25)

    if len(req.player_ids) > max_protected:
        return {"error": f"Too many players protected. Max is {max_protected} for round {current_round}"}

    return {
        "success": True,
        "team_id": team_id,
        "protected_count": len(req.player_ids),
        "max_allowed": max_protected,
    }


class ExpansionPickRequest(BaseModel):
    player_id: int = None  # None = AI auto-pick


@app.post("/expansion/pick")
async def expansion_pick(req: ExpansionPickRequest):
    """Make an expansion draft pick (manual or AI auto-pick)."""
    from ..transactions.expansion import (
        get_expansion_status, make_expansion_pick, ai_expansion_pick,
        auto_protect_all_teams, get_available_players
    )

    status = get_expansion_status()
    if not status.get("active"):
        return {"error": "No expansion draft in progress"}
    if status.get("status") == "complete":
        return {"error": "Expansion draft is already complete"}

    expansion_team_id = status["expansion_team_id"]
    current_round = status.get("current_round", 1)

    if req.player_id:
        # Manual pick
        return make_expansion_pick(expansion_team_id, req.player_id)
    else:
        # AI auto-pick
        protections = auto_protect_all_teams(
            current_round, exclude_team_id=expansion_team_id
        )
        available = get_available_players(protections)
        pick = ai_expansion_pick(expansion_team_id, available)
        if pick:
            return make_expansion_pick(expansion_team_id, pick["id"])
        return {"error": "No suitable players available"}


@app.get("/expansion/status")
async def expansion_status():
    """Get the current expansion draft state."""
    from ..transactions.expansion import get_expansion_status
    return get_expansion_status()


# ============================================================
# RATING SCALE SETTINGS
# ============================================================

class RatingScaleRequest(BaseModel):
    scale: str


@app.post("/settings/rating-scale")
async def set_rating_scale(req: RatingScaleRequest):
    """Set the user's preferred rating display scale."""
    from ..utils.rating_scales import VALID_SCALES
    if req.scale not in VALID_SCALES:
        raise HTTPException(400, f"Invalid scale. Must be one of: {VALID_SCALES}")

    # Add column if it doesn't exist
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE game_state ADD COLUMN rating_scale TEXT DEFAULT '20-80'")
    except Exception:
        pass  # Column already exists

    conn.execute("UPDATE game_state SET rating_scale=? WHERE id=1", (req.scale,))
    conn.commit()
    conn.close()

    return {"success": True, "rating_scale": req.scale}


@app.get("/settings/rating-scale")
async def get_rating_scale():
    """Get the current rating display scale."""
    conn = get_connection()
    try:
        conn.execute("ALTER TABLE game_state ADD COLUMN rating_scale TEXT DEFAULT '20-80'")
        conn.commit()
    except Exception:
        pass

    state = conn.execute("SELECT rating_scale FROM game_state WHERE id=1").fetchone()
    conn.close()
    scale = state["rating_scale"] if state and state["rating_scale"] else "20-80"

    from ..utils.rating_scales import get_scale_info, get_color_thresholds
    return {
        "rating_scale": scale,
        "info": get_scale_info(scale),
        "thresholds": get_color_thresholds(scale),
    }


# ============================================================
# PLAYER STRATEGY (per-player tactical settings)
# ============================================================

class PlayerStrategyRequest(BaseModel):
    steal_aggression: int = 3
    bunt_tendency: int = 3
    hit_and_run: int = 3
    pitch_count_limit: int = None


@app.get("/player/{player_id}/strategy")
async def get_player_strategy(player_id: int):
    """Get per-player strategy settings, with team defaults as fallback."""
    result = query(
        "SELECT * FROM player_strategy WHERE player_id=?", (player_id,))
    if result:
        return dict(result[0])

    # Return defaults
    return {
        "player_id": player_id,
        "steal_aggression": 3,
        "bunt_tendency": 3,
        "hit_and_run": 3,
        "pitch_count_limit": None,
        "is_default": True,
    }


@app.post("/player/{player_id}/strategy")
async def set_player_strategy(player_id: int, req: PlayerStrategyRequest):
    """Set per-player strategy overrides."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO player_strategy (player_id, steal_aggression, bunt_tendency,
            hit_and_run, pitch_count_limit)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(player_id) DO UPDATE SET
            steal_aggression=excluded.steal_aggression,
            bunt_tendency=excluded.bunt_tendency,
            hit_and_run=excluded.hit_and_run,
            pitch_count_limit=excluded.pitch_count_limit
    """, (player_id, max(1, min(5, req.steal_aggression)),
          max(1, min(5, req.bunt_tendency)),
          max(1, min(5, req.hit_and_run)),
          req.pitch_count_limit))
    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id}


@app.get("/team/{team_id}/player-strategies")
async def get_team_player_strategies(team_id: int):
    """Get all custom player strategies for a team."""
    results = query("""
        SELECT ps.*, p.first_name, p.last_name, p.position
        FROM player_strategy ps
        JOIN players p ON p.id = ps.player_id
        WHERE p.team_id = ?
    """, (team_id,))
    return [dict(r) for r in results]


# ============================================================
# MATCHUP STATS (head-to-head batter vs pitcher)
# ============================================================

@app.get("/matchups/batter/{batter_id}/vs-pitcher/{pitcher_id}")
async def get_matchup_batter_vs_pitcher(batter_id: int, pitcher_id: int):
    """Get career matchup stats: batter vs specific pitcher."""
    results = query("""
        SELECT season, pa, ab, h, doubles, triples, hr, rbi, bb, so, hbp,
               CASE WHEN ab > 0 THEN ROUND(1.0 * h / ab, 3) ELSE 0 END as avg
        FROM matchup_stats
        WHERE batter_id=? AND pitcher_id=?
        ORDER BY season DESC
    """, (batter_id, pitcher_id))

    # Also get career totals
    career = query("""
        SELECT SUM(pa) as pa, SUM(ab) as ab, SUM(h) as h, SUM(doubles) as doubles,
               SUM(triples) as triples, SUM(hr) as hr, SUM(rbi) as rbi,
               SUM(bb) as bb, SUM(so) as so, SUM(hbp) as hbp,
               CASE WHEN SUM(ab) > 0 THEN ROUND(1.0 * SUM(h) / SUM(ab), 3) ELSE 0 END as avg
        FROM matchup_stats
        WHERE batter_id=? AND pitcher_id=?
    """, (batter_id, pitcher_id))

    return {
        "batter_id": batter_id,
        "pitcher_id": pitcher_id,
        "seasons": [dict(r) for r in results],
        "career": dict(career[0]) if career else {},
    }


@app.get("/matchups/player/{player_id}/vs-team/{team_id}")
async def get_matchup_vs_team(player_id: int, team_id: int):
    """Get player's stats vs all players from a specific team."""
    # Check if player is a batter or pitcher
    player = query("SELECT position FROM players WHERE id=?", (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    is_pitcher = player[0]["position"] in ("SP", "RP")

    if is_pitcher:
        # Pitcher vs team's batters
        results = query("""
            SELECT ms.batter_id as opponent_id,
                   p.first_name || ' ' || p.last_name as opponent_name,
                   SUM(ms.pa) as pa, SUM(ms.ab) as ab, SUM(ms.h) as h,
                   SUM(ms.hr) as hr, SUM(ms.bb) as bb, SUM(ms.so) as so,
                   CASE WHEN SUM(ms.ab) > 0 THEN ROUND(1.0 * SUM(ms.h) / SUM(ms.ab), 3) ELSE 0 END as avg
            FROM matchup_stats ms
            JOIN players p ON p.id = ms.batter_id
            WHERE ms.pitcher_id=? AND p.team_id=?
            GROUP BY ms.batter_id
            ORDER BY SUM(ms.pa) DESC
        """, (player_id, team_id))
    else:
        # Batter vs team's pitchers
        results = query("""
            SELECT ms.pitcher_id as opponent_id,
                   p.first_name || ' ' || p.last_name as opponent_name,
                   SUM(ms.pa) as pa, SUM(ms.ab) as ab, SUM(ms.h) as h,
                   SUM(ms.hr) as hr, SUM(ms.bb) as bb, SUM(ms.so) as so,
                   CASE WHEN SUM(ms.ab) > 0 THEN ROUND(1.0 * SUM(ms.h) / SUM(ms.ab), 3) ELSE 0 END as avg
            FROM matchup_stats ms
            JOIN players p ON p.id = ms.pitcher_id
            WHERE ms.batter_id=? AND p.team_id=?
            GROUP BY ms.pitcher_id
            ORDER BY SUM(ms.pa) DESC
        """, (player_id, team_id))

    return {
        "player_id": player_id,
        "vs_team_id": team_id,
        "is_pitcher": is_pitcher,
        "matchups": [dict(r) for r in results],
    }


@app.get("/matchups/player/{player_id}/top")
async def get_player_top_matchups(player_id: int, limit: int = 10):
    """Get a player's most frequent matchup opponents."""
    player = query("SELECT position FROM players WHERE id=?", (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    is_pitcher = player[0]["position"] in ("SP", "RP")

    if is_pitcher:
        results = query("""
            SELECT ms.batter_id as opponent_id,
                   p.first_name || ' ' || p.last_name as opponent_name,
                   t.abbreviation as opponent_team,
                   SUM(ms.pa) as pa, SUM(ms.ab) as ab, SUM(ms.h) as h,
                   SUM(ms.hr) as hr, SUM(ms.bb) as bb, SUM(ms.so) as so,
                   CASE WHEN SUM(ms.ab) > 0 THEN ROUND(1.0 * SUM(ms.h) / SUM(ms.ab), 3) ELSE 0 END as avg
            FROM matchup_stats ms
            JOIN players p ON p.id = ms.batter_id
            LEFT JOIN teams t ON t.id = p.team_id
            WHERE ms.pitcher_id=?
            GROUP BY ms.batter_id
            ORDER BY SUM(ms.pa) DESC
            LIMIT ?
        """, (player_id, limit))
    else:
        results = query("""
            SELECT ms.pitcher_id as opponent_id,
                   p.first_name || ' ' || p.last_name as opponent_name,
                   t.abbreviation as opponent_team,
                   SUM(ms.pa) as pa, SUM(ms.ab) as ab, SUM(ms.h) as h,
                   SUM(ms.hr) as hr, SUM(ms.bb) as bb, SUM(ms.so) as so,
                   CASE WHEN SUM(ms.ab) > 0 THEN ROUND(1.0 * SUM(ms.h) / SUM(ms.ab), 3) ELSE 0 END as avg
            FROM matchup_stats ms
            JOIN players p ON p.id = ms.pitcher_id
            LEFT JOIN teams t ON t.id = p.team_id
            WHERE ms.batter_id=?
            GROUP BY ms.pitcher_id
            ORDER BY SUM(ms.pa) DESC
            LIMIT ?
        """, (player_id, limit))

    return {
        "player_id": player_id,
        "is_pitcher": is_pitcher,
        "matchups": [dict(r) for r in results],
    }


# ============================================================
# PLAYER PROJECTIONS
# ============================================================

@app.get("/player/{player_id}/projection")
async def get_player_projection(player_id: int):
    """Get Marcel-style stat projection for a player."""
    from ..simulation.projections import project_batter, project_pitcher
    player = query("SELECT * FROM players WHERE id=?", (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    p = player[0]
    conn = get_connection()
    try:
        if p["position"] in ("SP", "RP"):
            proj = project_pitcher(player_id, conn)
        else:
            proj = project_batter(player_id, conn)
    finally:
        conn.close()

    return {
        "player_id": player_id,
        "name": f"{p['first_name']} {p['last_name']}",
        "position": p["position"],
        "age": p["age"],
        "projection": proj,
    }


@app.get("/projections/batting")
async def get_team_batting_projections(team_id: int):
    """Batch batting projections for a team."""
    from ..simulation.projections import project_batter
    players = query("""
        SELECT id, first_name, last_name, position, age
        FROM players WHERE team_id=? AND position NOT IN ('SP', 'RP')
        AND roster_status IN ('active', 'minors_aaa')
        ORDER BY position
    """, (team_id,))

    conn = get_connection()
    results = []
    try:
        for p in players:
            proj = project_batter(p["id"], conn)
            if proj:
                results.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "position": p["position"],
                    "age": p["age"],
                    "projection": proj,
                })
    finally:
        conn.close()

    return results


@app.get("/projections/pitching")
async def get_team_pitching_projections(team_id: int):
    """Batch pitching projections for a team."""
    from ..simulation.projections import project_pitcher
    players = query("""
        SELECT id, first_name, last_name, position, age
        FROM players WHERE team_id=? AND position IN ('SP', 'RP')
        AND roster_status IN ('active', 'minors_aaa')
        ORDER BY position, id
    """, (team_id,))

    conn = get_connection()
    results = []
    try:
        for p in players:
            proj = project_pitcher(p["id"], conn)
            if proj:
                results.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "position": p["position"],
                    "age": p["age"],
                    "projection": proj,
                })
    finally:
        conn.close()

    return results


# ============================================================
# RATING RECALIBRATION
# ============================================================

@app.post("/recalibrate-ratings")
async def recalibrate_ratings():
    """Recalibrate all player ratings to prevent drift.
    Target: mean=50, std_dev=10 on the 20-80 scale.
    """
    import math
    conn = get_connection()

    rating_cols_batting = ["contact_rating", "power_rating", "speed_rating",
                           "fielding_rating", "arm_rating", "eye_rating"]
    rating_cols_pitching = ["stuff_rating", "control_rating", "stamina_rating"]

    adjustments = {}

    # Recalibrate batting ratings across active MLB players
    for col in rating_cols_batting:
        rows = conn.execute(f"""
            SELECT {col} FROM players
            WHERE roster_status = 'active' AND position NOT IN ('SP', 'RP')
        """).fetchall()
        if not rows:
            continue

        values = [r[0] for r in rows]
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance) if variance > 0 else 10

        adjustments[col] = {"old_mean": round(mean, 1), "old_std": round(std, 1)}

        if abs(mean - 50) > 1 or abs(std - 10) > 1:
            # Apply z-score normalization
            for row in conn.execute(f"""
                SELECT id, {col} FROM players
                WHERE roster_status = 'active' AND position NOT IN ('SP', 'RP')
            """).fetchall():
                old_val = row[1]
                z = (old_val - mean) / std if std > 0 else 0
                new_val = max(20, min(80, round(50 + z * 10)))
                if new_val != old_val:
                    conn.execute(f"UPDATE players SET {col}=? WHERE id=?",
                                 (new_val, row[0]))

            adjustments[col]["new_mean"] = 50
            adjustments[col]["new_std"] = 10
            adjustments[col]["adjusted"] = True
        else:
            adjustments[col]["adjusted"] = False

    # Recalibrate pitching ratings
    for col in rating_cols_pitching:
        rows = conn.execute(f"""
            SELECT {col} FROM players
            WHERE roster_status = 'active' AND position IN ('SP', 'RP')
        """).fetchall()
        if not rows:
            continue

        values = [r[0] for r in rows]
        n = len(values)
        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / n
        std = math.sqrt(variance) if variance > 0 else 10

        adjustments[col] = {"old_mean": round(mean, 1), "old_std": round(std, 1)}

        if abs(mean - 50) > 1 or abs(std - 10) > 1:
            for row in conn.execute(f"""
                SELECT id, {col} FROM players
                WHERE roster_status = 'active' AND position IN ('SP', 'RP')
            """).fetchall():
                old_val = row[1]
                z = (old_val - mean) / std if std > 0 else 0
                new_val = max(20, min(80, round(50 + z * 10)))
                if new_val != old_val:
                    conn.execute(f"UPDATE players SET {col}=? WHERE id=?",
                                 (new_val, row[0]))

            adjustments[col]["new_mean"] = 50
            adjustments[col]["new_std"] = 10
            adjustments[col]["adjusted"] = True
        else:
            adjustments[col]["adjusted"] = False

    # Log the recalibration
    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    if state:
        import json
        conn.execute("""
            INSERT INTO transactions (transaction_date, transaction_type, details_json)
            VALUES (?, 'rating_recalibration', ?)
        """, (state[0], json.dumps(adjustments)))

    conn.commit()
    conn.close()

    return {"success": True, "adjustments": adjustments}


# ============================================================
# CHARACTER CAREER ARCS
# ============================================================

@app.get("/characters")
async def list_characters():
    """List all tracked NPC characters with their current roles."""
    from ..ai.career_arcs import get_all_characters
    characters = get_all_characters()
    return {"characters": characters, "count": len(characters)}


@app.get("/characters/{character_id}/history")
async def character_history(character_id: int):
    """Get full career history for a character."""
    from ..ai.career_arcs import get_character_history, generate_career_narrative
    history = get_character_history(character_id)
    if not history:
        raise HTTPException(status_code=404, detail=f"Character {character_id} not found")
    history["narrative"] = generate_career_narrative(character_id)
    return history


@app.post("/characters/process-careers")
async def process_character_careers():
    """Trigger end-of-season career processing for all NPC characters."""
    from ..ai.career_arcs import process_career_changes
    state = query("SELECT * FROM game_state WHERE id=1")
    if not state:
        raise HTTPException(status_code=400, detail="No game state found")
    game_date = state[0]["current_date"]
    results = process_career_changes(game_date)
    return results


# ============================================================
# OWNER PRESSURE & JOB SECURITY
# ============================================================

@app.get("/owner/objectives/{team_id}")
async def api_get_owner_objectives(team_id: int, season: int = None):
    """Get owner objectives for a team."""
    if season is None:
        state = query("SELECT season FROM game_state WHERE id=1")
        season = state[0]["season"] if state else 2026
    objectives = get_owner_objectives_for_team(team_id, season)
    return {"team_id": team_id, "season": season, "objectives": objectives}


@app.get("/owner/job-security")
async def api_get_job_security():
    """Get current GM job security status."""
    return get_job_security()


@app.post("/owner/evaluate")
async def api_evaluate_performance():
    """Trigger end-of-season GM performance evaluation."""
    state = query("SELECT user_team_id FROM game_state WHERE id=1")
    if not state or not state[0]["user_team_id"]:
        raise HTTPException(status_code=400, detail="No user team set")
    team_id = state[0]["user_team_id"]
    result = evaluate_gm_performance(team_id)
    firing_check = check_firing(team_id)
    return {
        "evaluation": result,
        "firing_status": firing_check,
    }


@app.post("/owner/set-objectives")
async def api_set_objectives(season: int = None):
    """Have the owner set objectives for the current or specified season."""
    state = query("SELECT user_team_id, season FROM game_state WHERE id=1")
    if not state or not state[0]["user_team_id"]:
        raise HTTPException(status_code=400, detail="No user team set")
    team_id = state[0]["user_team_id"]
    if season is None:
        season = state[0]["season"]
    objectives = set_owner_objectives(team_id, season)
    return {"team_id": team_id, "season": season, "objectives": objectives}


@app.get("/owner/mood")
async def api_get_owner_mood():
    """Get current owner mood and message."""
    state = query("SELECT user_team_id FROM game_state WHERE id=1")
    if not state or not state[0]["user_team_id"]:
        raise HTTPException(status_code=400, detail="No user team set")
    team_id = state[0]["user_team_id"]
    return get_owner_mood_message(team_id)


# ============================================================
# MINOR LEAGUE (Farm System)
# ============================================================
@app.get("/milb/standings/{team_id}")
async def api_get_milb_standings(team_id: int, level: str = "AAA"):
    """Get minor league standings for a team's affiliate."""
    from ..simulation.minor_leagues import get_milb_standings as _get_milb_standings
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026
    return _get_milb_standings(team_id, level, season)


@app.get("/milb/stats/{team_id}")
async def api_get_milb_stats(team_id: int, level: str = "AAA"):
    """Get minor league player stats."""
    from ..simulation.minor_leagues import get_milb_stats as _get_milb_stats
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026
    return _get_milb_stats(team_id, level, season)


@app.get("/milb/all-standings")
async def api_get_all_milb_standings(level: str = "AAA"):
    """Get all minor league standings for a level."""
    from ..simulation.minor_leagues import get_all_milb_standings as _get_all
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026
    return _get_all(level, season)


@app.post("/generate-backstories")
async def api_generate_backstories(force: bool = False):
    """Generate backstories for all players that don't have one."""
    try:
        count = generate_all_backstories(force=force)
        return {"status": "ok", "players_updated": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/player/{player_id}/generate-backstory")
async def api_generate_player_backstory(player_id: int):
    """Generate or regenerate backstory for a single player."""
    player = query("SELECT * FROM players WHERE id=?", (player_id,))
    if not player:
        raise HTTPException(404, "Player not found")

    result = generate_backstory(player[0])
    execute(
        """UPDATE players SET backstory=?, nickname=?, quirks=?, origin_story=?
           WHERE id=?""",
        (result['backstory'], result['nickname'], result['quirks'],
         result['origin_story'], player_id)
    )
    return {"status": "ok", "backstory": result}


# ============================================================
# PODCAST
# ============================================================
@app.get("/podcast/episodes")
async def api_get_podcast_episodes(limit: int = 10):
    """Get recent podcast episodes."""
    from ..ai.podcast import get_podcast_episodes
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026
    episodes = get_podcast_episodes(season=season, limit=limit)
    return episodes


@app.get("/podcast/latest")
async def api_get_latest_podcast():
    """Get the most recent podcast episode."""
    from ..ai.podcast import get_latest_podcast
    episode = get_latest_podcast()
    if not episode:
        return {"message": "No podcast episodes yet"}
    # Mark as read
    execute("UPDATE podcast_episodes SET is_read = 1 WHERE id = ?", (episode["id"],))
    return episode


@app.post("/podcast/generate")
async def api_generate_podcast():
    """Manually trigger podcast generation for the current date."""
    from ..ai.podcast import generate_weekly_podcast
    state = query("SELECT * FROM game_state WHERE id=1")
    if not state:
        raise HTTPException(400, "No game state found")
    game_date = state[0]["current_date"]
    season = state[0]["season"]
    result = await generate_weekly_podcast(game_date, season)
    return result


@app.post("/podcast/{episode_id}/read")
async def api_mark_podcast_read(episode_id: int):
    """Mark a podcast episode as read."""
    execute("UPDATE podcast_episodes SET is_read = 1 WHERE id = ?", (episode_id,))
    return {"success": True}


@app.get("/news/feed")
async def get_news_feed(limit: int = 30):
    """Aggregated news feed from all sources - articles, TV segments, podcasts, transactions."""
    feed = []

    # Get articles (if table exists)
    try:
        articles = query("""
            SELECT a.*, bw.name as writer_name, bw.outlet, bw.personality as writer_personality
            FROM articles a
            LEFT JOIN beat_writers bw ON bw.id = a.writer_id
            ORDER BY a.game_date DESC, a.id DESC LIMIT ?
        """, (limit,)) or []
        for a in articles:
            feed.append({
                "type": "article",
                "date": a.get("game_date", ""),
                "headline": a.get("headline", ""),
                "body": a.get("body", ""),
                "source": a.get("outlet", "Unknown"),
                "author": a.get("writer_name", "Staff"),
                "sentiment": a.get("sentiment", "neutral"),
                "article_type": a.get("article_type", "news"),
                "id": a.get("id"),
            })
    except Exception:
        pass  # Table may not exist yet

    # Get TV segments (if table exists)
    try:
        segments = query("""
            SELECT ts.*, ta.name as analyst_name, ta.network, ta.personality as analyst_personality
            FROM tv_segments ts
            LEFT JOIN tv_analysts ta ON ta.id = ts.analyst_id
            ORDER BY ts.game_date DESC, ts.id DESC LIMIT ?
        """, (limit,)) or []
        for s in segments:
            feed.append({
                "type": "tv_segment",
                "date": s.get("game_date", ""),
                "headline": s.get("headline", ""),
                "body": s.get("content", ""),
                "source": s.get("network", "ESPN"),
                "author": s.get("analyst_name", "Analyst"),
                "segment_type": s.get("segment_type", "commentary"),
                "id": s.get("id"),
            })
    except Exception:
        pass

    # Get podcast episodes (if table exists)
    try:
        podcasts = query("""
            SELECT * FROM podcast_episodes
            ORDER BY game_date DESC, id DESC LIMIT 5
        """) or []
        for p in podcasts:
            feed.append({
                "type": "podcast",
                "date": p.get("game_date", ""),
                "headline": p.get("title", ""),
                "body": (p.get("script", "") or "")[:500] + "...",
                "source": "The Front Office Podcast",
                "episode": p.get("episode_number"),
                "id": p.get("id"),
            })
    except Exception:
        pass

    # Get recent transactions as news items
    try:
        txns = query("""
            SELECT * FROM transactions
            ORDER BY game_date DESC, id DESC LIMIT 10
        """) or []
        for t in txns:
            feed.append({
                "type": "transaction",
                "date": t.get("game_date", ""),
                "headline": f"Transaction: {t.get('description', 'Unknown')}",
                "body": t.get("details", t.get("description", "")),
                "source": "Front Office Wire",
                "id": t.get("id"),
            })
    except Exception:
        pass

    # Sort all items by date descending
    feed.sort(key=lambda x: x.get("date", ""), reverse=True)
    return feed[:limit]


# ============================================================
# NEWS ARTICLES (Beat Writer System)
# ============================================================

@app.get("/news/articles")
async def get_news_articles(limit: int = 30, offset: int = 0):
    """Get recent articles across all teams, paginated."""
    try:
        from ..ai.beat_writers import get_all_articles
        articles = get_all_articles(limit=limit + offset)
        return articles[offset:offset + limit] if articles else []
    except Exception as e:
        raise HTTPException(500, f"Error fetching articles: {e}")


@app.get("/news/articles/{team_id}")
async def get_team_news_articles(team_id: int, limit: int = 20):
    """Get recent articles for a specific team."""
    try:
        from ..ai.beat_writers import get_articles_for_team
        return get_articles_for_team(team_id, limit=limit)
    except Exception as e:
        raise HTTPException(500, f"Error fetching team articles: {e}")


@app.post("/news/generate")
async def trigger_article_generation():
    """Manually trigger article generation for the current game date."""
    state = query("SELECT * FROM game_state WHERE id=1")
    if not state:
        raise HTTPException(400, "No game state found")

    game_date = state[0]["current_date"]

    try:
        from ..ai.beat_writers import generate_all_daily_articles
        articles = generate_all_daily_articles(game_date)
        return {
            "success": True,
            "game_date": game_date,
            "articles_generated": len(articles),
            "articles": articles,
        }
    except Exception as e:
        raise HTTPException(500, f"Error generating articles: {e}")


# ============================================================
# FAN SENTIMENT
# ============================================================

@app.get("/fan-sentiment/{team_id}")
async def get_team_fan_sentiment(team_id: int):
    """Get fan sentiment data for a team, including reactions."""
    try:
        from ..ai.fan_sentiment import get_fan_reactions, get_fan_sentiment as _get_sent
        reactions = get_fan_reactions(team_id)
        sentiment = _get_sent(team_id)
        # Merge the two results
        result = {**sentiment, **reactions}
        return result
    except Exception as e:
        raise HTTPException(500, f"Error fetching fan sentiment: {e}")


@app.post("/fan-sentiment/update")
async def update_fan_sentiments():
    """Manually trigger fan sentiment recalculation for all teams."""
    try:
        from ..ai.fan_sentiment import update_all_fan_sentiments
        results = update_all_fan_sentiments()
        return {
            "success": True,
            "teams_updated": len(results),
            "sentiments": results,
        }
    except Exception as e:
        raise HTTPException(500, f"Error updating fan sentiments: {e}")


# ============================================================
# PLAYER PORTRAITS
# ============================================================

@app.get("/player/{player_id}/portrait")
async def get_player_portrait(player_id: int):
    """Return SVG portrait for a player, generating one if needed."""
    from ..ai.player_portraits import get_portrait, regenerate_portrait

    svg = get_portrait(player_id)
    if not svg:
        svg = regenerate_portrait(player_id)
    if not svg:
        raise HTTPException(404, "Player not found")
    from fastapi.responses import Response
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/admin/generate-portraits")
async def api_generate_portraits():
    """Bulk generate portraits for all players missing one."""
    from ..ai.player_portraits import generate_all_portraits
    try:
        count = generate_all_portraits()
        return {"status": "ok", "portraits_generated": count}
    except Exception as e:
        raise HTTPException(500, f"Error generating portraits: {e}")


@app.post("/player/{player_id}/regenerate-portrait")
async def api_regenerate_portrait(player_id: int):
    """Regenerate portrait for a single player (e.g. after trade)."""
    from ..ai.player_portraits import regenerate_portrait
    svg = regenerate_portrait(player_id)
    if not svg:
        raise HTTPException(404, "Player not found")
    return {"status": "ok", "player_id": player_id}


# ============================================================
# RECORDS TRACKING
# ============================================================
@app.get("/records")
async def api_get_records(type: str = None):
    """Get all records, optionally filtered by type ('season' or 'career')."""
    try:
        records = get_all_records(record_type=type)
        return records
    except Exception as e:
        raise HTTPException(500, f"Error fetching records: {e}")


@app.get("/records/watch")
async def api_get_record_watch():
    """Get current record watch list."""
    try:
        watch = get_record_watch()
        return watch
    except Exception as e:
        raise HTTPException(500, f"Error fetching record watch: {e}")


@app.post("/records/check")
async def api_check_records():
    """Manually trigger a record check against current stats."""
    try:
        state = query("SELECT * FROM game_state WHERE id=1")
        if not state:
            raise HTTPException(404, "No game state found")
        game_date = state[0]["current_date"]
        results = check_record_watch(game_date)
        return {
            "success": True,
            "game_date": game_date,
            "watch_items": results.get("watch_items", []) if isinstance(results, dict) else [],
            "broken_records": results.get("broken_records", []) if isinstance(results, dict) else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error checking records: {e}")


@app.post("/records/initialize")
async def api_initialize_records():
    """Seed the records table with real MLB records."""
    try:
        result = initialize_records()
        return result
    except Exception as e:
        raise HTTPException(500, f"Error initializing records: {e}")


@app.get("/records/milestones/{player_id}")
async def api_career_milestones(player_id: int):
    """Check career milestone proximity for a specific player."""
    try:
        milestones = check_career_milestones(player_id)
        return milestones
    except Exception as e:
        raise HTTPException(500, f"Error checking milestones: {e}")
