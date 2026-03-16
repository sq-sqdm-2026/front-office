"""
Front Office - API Routes
All FastAPI endpoints for the baseball simulation.
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from ..database.db import query, execute
from ..simulation.season import get_standings, advance_date, sim_day
from ..transactions.trades import propose_trade, execute_trade
from ..transactions.free_agency import get_free_agents, sign_free_agent
from ..ai.ollama_client import check_health
from ..ai.gm_brain import generate_scouting_report
from ..ai.scouting_modes import get_displayed_ratings
from ..transactions.roster import (
    call_up_player, option_player, dfa_player, get_roster_summary,
    add_to_forty_man, remove_from_forty_man
)
from ..transactions.trades import propose_waiver_trade
from ..transactions.draft import generate_draft_class, make_draft_pick
from ..simulation.injuries import check_injuries_for_day
from ..financial.economics import calculate_season_finances

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

    if not block_data or not block_data[0].get("trading_block_json"):
        return {"players": [], "offers": []}

    return _json.loads(block_data[0]["trading_block_json"])


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
    if team and team[0].get("trading_block_json"):
        block_data = _json.loads(team[0]["trading_block_json"])

    if player_id not in block_data["players"]:
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

    if team and team[0].get("trading_block_json"):
        block_data = _json.loads(team[0]["trading_block_json"])
        if player_id in block_data["players"]:
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


class LineupRequest(BaseModel):
    lineup: list[int]  # Player IDs in batting order (1-9)
    rotation: list[int] = []  # Pitcher IDs for rotation (optional)

@app.post("/roster/{team_id}/lineup")
async def save_lineup(team_id: int, req: LineupRequest):
    """Save custom batting lineup and/or pitching rotation."""
    import json as _json

    # Validate that players belong to the team
    for pid in req.lineup + req.rotation:
        player = query("SELECT team_id FROM players WHERE id=?", (pid,))
        if not player or player[0]["team_id"] != team_id:
            raise HTTPException(400, f"Player {pid} not on team {team_id}")

    # Save lineup JSON
    lineup_json = _json.dumps({"player_ids": req.lineup})
    rotation_json = _json.dumps({"player_ids": req.rotation}) if req.rotation else None

    execute("UPDATE teams SET lineup_json=?, rotation_json=? WHERE id=?",
            (lineup_json, rotation_json, team_id))

    return {
        "success": True,
        "team_id": team_id,
        "lineup_count": len(req.lineup),
        "rotation_count": len(req.rotation),
    }


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
