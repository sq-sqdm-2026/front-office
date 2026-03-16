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
from ..transactions.roster import call_up_player, option_player, dfa_player, get_roster_summary
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
                "user_team_id": None, "difficulty": "manager"}
    return state[0]


class SetUserTeam(BaseModel):
    team_id: int

@app.post("/set-user-team")
async def set_user_team(req: SetUserTeam):
    """Set the user's team."""
    execute("UPDATE game_state SET user_team_id=? WHERE id=1", (req.team_id,))
    return {"success": True, "team_id": req.team_id}


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
        "player": player[0],
        "batting_stats": batting,
        "pitching_stats": pitching,
    }


@app.get("/player/{player_id}/scouting-report")
async def player_scouting_report(player_id: int):
    """Generate an LLM-written scouting report."""
    report = await generate_scouting_report(player_id)
    return {"player_id": player_id, "report": report}


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


# ============================================================
# MESSAGES
# ============================================================
@app.get("/messages")
async def get_messages(unread_only: bool = True):
    """Get pending messages (GM chats, owner check-ins, notifications)."""
    condition = "AND is_read=0" if unread_only else ""
    return query(f"""
        SELECT * FROM messages
        WHERE recipient_type='user' {condition}
        ORDER BY game_date DESC, id DESC
        LIMIT 50
    """)


class MessageSend(BaseModel):
    recipient_type: str  # gm, owner
    recipient_id: int
    body: str

@app.post("/messages/send")
async def send_message(msg: MessageSend):
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
# ROSTER MANAGEMENT
# ============================================================
@app.get("/roster/{team_id}")
async def roster(team_id: int):
    """Full roster breakdown: active, minors, injured."""
    return get_roster_summary(team_id)


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
