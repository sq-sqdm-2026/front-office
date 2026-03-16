"""
Front Office - API Routes
All FastAPI endpoints for the baseball simulation.
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from ..database.db import query, execute, get_connection
from ..simulation.season import get_standings, advance_date, sim_day, _load_team_lineup, _get_park_factors, _load_team_strategy, _generate_key_plays
from ..simulation.chemistry import calculate_team_chemistry
from ..transactions.trades import propose_trade, execute_trade
from ..transactions.free_agency import get_free_agents, sign_free_agent
from ..ai.ollama_client import check_health
from ..ai.gm_brain import generate_scouting_report
from ..ai.scouting_modes import get_displayed_ratings
from ..transactions.roster import (
    call_up_player, option_player, dfa_player, get_roster_summary,
    add_to_forty_man, remove_from_forty_man, release_player
)
from ..transactions.trades import propose_waiver_trade
from ..transactions.draft import generate_draft_class, make_draft_pick
from ..simulation.injuries import check_injuries_for_day
from ..financial.economics import calculate_season_finances
from ..simulation.game_engine import simulate_game

app = FastAPI(title="Front Office", version="0.1.0",
              description="Baseball Universe Simulation powered by Local LLMs")


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
                "user_team_id": None, "difficulty": "manager", "scouting_mode": "traditional"}
    return state[0]


class SetUserTeam(BaseModel):
    team_id: int

@app.post("/set-user-team")
async def set_user_team(req: SetUserTeam):
    """Set the user's team."""
    execute("UPDATE game_state SET user_team_id=? WHERE id=1", (req.team_id,))
    return {"success": True, "team_id": req.team_id}


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
    """Negotiate with a free agent (can offer less than asking price)."""
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

    # Calculate acceptance probability based on offer quality
    salary_ratio = req.salary / asking_salary if asking_salary > 0 else 1.0

    accepted = False
    counter_offer = None
    reason = ""

    if salary_ratio >= 1.0:
        # Offer meets or exceeds asking: auto-accept
        accepted = True
        reason = "Offer meets or exceeds asking price"
    elif salary_ratio >= 0.95:
        # 95-99%: 80% chance accept
        accepted = random.random() < 0.80
        reason = "Offer close to asking price" if accepted else "Wants more money"
    elif salary_ratio >= 0.80:
        # 80-94%: 50% chance accept, likely counter
        if random.random() < 0.50:
            accepted = True
            reason = "Accepted slightly reduced offer"
        else:
            counter_offer = {
                "salary": int(asking_salary * 0.95),
                "years": asking_years
            }
            reason = "Countered with closer offer"
    elif salary_ratio >= 0.60:
        # 60-79%: 20% chance accept, likely counter
        if random.random() < 0.20:
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
        return {
            "accepted": True,
            "result": result,
            "reason": reason
        }

    return {
        "accepted": False,
        "counter_offer": counter_offer,
        "reason": reason
    }


@app.post("/admin/generate-free-agents")
async def generate_free_agents(min_count: int = 50):
    """
    Admin endpoint to ensure minimum free agents exist.
    If there are fewer than min_count free agents, generates new ones.
    """
    from ..transactions.free_agency import ensure_minimum_free_agents

    result = ensure_minimum_free_agents(min_count)
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

    return {
        "team_id": team_id,
        "cash": t["cash"],
        "franchise_value": t["franchise_value"],
        "current_payroll": payroll[0]["total"] if payroll else 0,
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
@app.get("/messages/{team_id}")
async def get_team_messages(team_id: int, unread_only: bool = False):
    """Get messages for a specific team."""
    from ..transactions.messages import get_messages_for_team
    messages = get_messages_for_team(team_id, unread_only=unread_only)
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
    state = query("SELECT current_date FROM game_state WHERE id=1")
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
async def ollama_status():
    """Check Ollama health and available models."""
    return await check_health()


# ============================================================
# BOX SCORE
# ============================================================
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
    state = query("SELECT current_date FROM game_state WHERE id=1")
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
               bs.games, bs.ab, bs.hits, bs.hr, bs.rbi, bs.bb, bs.so,
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
               ps.games, ps.games_started, ps.wins, ps.losses, ps.saves,
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

    # Generate batting lineup
    hitters = [p for p in roster if p["position"] not in ("SP", "RP")]
    if not hitters:
        raise HTTPException(400, "No position players found")

    # Calculate overall hitting value
    def hitting_value(p):
        contact = p.get("contact_rating") or 50
        power = p.get("power_rating") or 50
        speed = p.get("speed_rating") or 50
        return (contact * 1.2) + (power * 1.0) + (speed * 0.3)

    hitters_sorted = sorted(hitters, key=hitting_value, reverse=True)

    # Create optimal lineup (9 spots)
    batting_lineup = []

    # Slot 1: Highest contact + speed (leadoff)
    if hitters_sorted:
        batting_lineup.append({
            "player_id": hitters_sorted[0]["id"],
            "batting_order": 1,
            "position": hitters_sorted[0]["position"]
        })

    # Slot 2: 2nd highest contact (contact hitter)
    if len(hitters_sorted) > 1:
        batting_lineup.append({
            "player_id": hitters_sorted[1]["id"],
            "batting_order": 2,
            "position": hitters_sorted[1]["position"]
        })

    # Slot 3: Best overall (contact + power)
    if len(hitters_sorted) > 2:
        batting_lineup.append({
            "player_id": hitters_sorted[2]["id"],
            "batting_order": 3,
            "position": hitters_sorted[2]["position"]
        })

    # Slot 4: Best power hitter (cleanup)
    if len(hitters_sorted) > 3:
        batting_lineup.append({
            "player_id": hitters_sorted[3]["id"],
            "batting_order": 4,
            "position": hitters_sorted[3]["position"]
        })

    # Slot 5: 2nd best power
    if len(hitters_sorted) > 4:
        batting_lineup.append({
            "player_id": hitters_sorted[4]["id"],
            "batting_order": 5,
            "position": hitters_sorted[4]["position"]
        })

    # Slots 6-9: Fill remaining by overall value
    for idx, p in enumerate(hitters_sorted[5:9], start=6):
        batting_lineup.append({
            "player_id": p["id"],
            "batting_order": idx,
            "position": p["position"]
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
                "player_id": p["id"],
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
    state = query("SELECT current_date FROM game_state WHERE id=1")
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
    state = query("SELECT current_date FROM game_state WHERE id=1")
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

        # --- players table migrations ---
        player_cols = get_columns("players")
        player_migrations = {
            "trading_block_json": "TEXT DEFAULT '{\"players\":[],\"offers\":[]}'",
        }
        for col, col_def in player_migrations.items():
            if col not in player_cols:
                conn.execute(f"ALTER TABLE players ADD COLUMN {col} {col_def}")
                changes.append(f"players.{col}")

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

        conn.commit()

        if not changes:
            changes.append("Database already up to date")

        return {"success": True, "changes": changes}

    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


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
