"""
Front Office - Expansion Draft System
Full expansion draft mechanics allowing a new team to join the league.
Existing teams protect players, expansion team selects from unprotected.

Features:
- Create a new franchise (team, GM, owner)
- AI-driven protection lists (highest OVR first, weighted by age/contract)
- Exclusions: under-22 players and those drafted in last 3 seasons
- AI expansion picks based on positional need, rating, age, contract
- ~30 rounds to fill a full roster
"""
import json
import random
from ..database.db import get_connection, query, execute


# Positions needed for a full roster
POSITION_TARGETS = {
    "C": 2, "1B": 2, "2B": 2, "3B": 2, "SS": 2,
    "LF": 2, "CF": 2, "RF": 2, "DH": 1,
    "SP": 5, "RP": 7,
}
TOTAL_PICKS = sum(POSITION_TARGETS.values())  # ~29


def _calculate_player_ovr(player: dict) -> float:
    """Calculate overall rating for a player."""
    pos = player.get("position", "")
    if pos in ("SP", "RP"):
        return (
            player.get("stuff_rating", 40) * 2
            + player.get("control_rating", 40) * 1.5
            + player.get("stamina_rating", 40) * 0.5
        ) / 4.0
    else:
        return (
            player.get("contact_rating", 40) * 1.5
            + player.get("power_rating", 40) * 1.5
            + player.get("speed_rating", 40) * 0.5
            + player.get("fielding_rating", 40) * 0.5
        ) / 4.0


def _protection_score(player: dict) -> float:
    """Score for protection priority. Higher = more worth protecting."""
    ovr = _calculate_player_ovr(player)
    age = player.get("age", 30)
    salary = player.get("annual_salary", 0) or 0

    # Age factor: younger players more worth protecting
    if age <= 25:
        age_mult = 1.2
    elif age <= 29:
        age_mult = 1.0
    elif age <= 32:
        age_mult = 0.85
    else:
        age_mult = 0.65

    # Contract value penalty: huge contracts less worth protecting
    salary_penalty = 0
    if salary > 20_000_000:
        salary_penalty = (salary - 20_000_000) / 100_000_000  # small penalty

    return ovr * age_mult - salary_penalty * 5


# ============================================================
# CREATE EXPANSION TEAM
# ============================================================

def start_expansion_draft(team_name: str, city: str, abbreviation: str,
                          league: str, division: str, db_path: str = None) -> dict:
    """
    Create a new expansion team and initialize the draft state.
    Returns the new team info and draft metadata.
    """
    conn = get_connection(db_path)

    # Check abbreviation uniqueness
    existing = conn.execute(
        "SELECT id FROM teams WHERE abbreviation=?", (abbreviation,)
    ).fetchone()
    if existing:
        conn.close()
        return {"error": f"Abbreviation '{abbreviation}' already exists"}

    # Create the team
    cursor = conn.execute("""
        INSERT INTO teams (city, name, abbreviation, league, division,
            cash, payroll_budget, market_size, fan_loyalty, fan_expectation,
            franchise_value, farm_system_budget, scouting_staff_budget,
            medical_staff_budget, ticket_price_pct, concession_price_pct)
        VALUES (?, ?, ?, ?, ?, 100000000, 80000000, 50, 50, 30,
                500000000, 5000000, 3000000, 2000000, 100, 100)
    """, (city, team_name, abbreviation, league, division))
    team_id = cursor.lastrowid

    # Create a GM character
    conn.execute("""
        INSERT INTO gm_characters (team_id, name, personality, risk_tolerance,
            trade_aggressiveness, prospect_preference, analytics_focus)
        VALUES (?, ?, 'balanced', 50, 50, 50, 50)
    """, (team_id, f"{city} GM"))

    # Create an owner character
    conn.execute("""
        INSERT INTO owner_characters (team_id, name, patience, spending_willingness,
            win_now_pressure, meddling_tendency)
        VALUES (?, ?, 60, 60, 30, 20)
    """, (team_id, f"{city} Ownership Group"))

    # Store expansion draft state in game_state or a separate mechanism
    # We'll use a simple approach: store in-progress state as JSON
    draft_state = {
        "expansion_team_id": team_id,
        "current_round": 1,
        "picks_made": [],
        "total_picks_target": TOTAL_PICKS,
        "status": "protecting",  # protecting -> drafting -> complete
    }

    # Store draft state — add column if needed
    try:
        conn.execute("ALTER TABLE game_state ADD COLUMN expansion_draft_json TEXT DEFAULT NULL")
    except Exception:
        pass  # Column already exists

    conn.execute(
        "UPDATE game_state SET expansion_draft_json=? WHERE id=1",
        (json.dumps(draft_state),)
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "team_id": team_id,
        "team_name": f"{city} {team_name}",
        "abbreviation": abbreviation,
        "league": league,
        "division": division,
        "draft_state": draft_state,
    }


# ============================================================
# PROTECTION LISTS
# ============================================================

def get_protection_list(team_id: int, round_num: int, db_path: str = None) -> list:
    """
    Generate AI protection list for a team.
    Round 1: protect 15 players. Each subsequent round: +3 more.
    Priority: highest overall first, weighted by age and contract value.
    Returns list of player IDs that should be protected.
    """
    protection_count = 15 + max(0, (round_num - 1)) * 3
    protection_count = min(protection_count, 25)  # cap at 25

    conn = get_connection(db_path)

    # Get all eligible players for this team (on roster)
    players = conn.execute("""
        SELECT p.*, c.annual_salary, c.years_remaining
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id = ?
        AND p.roster_status != 'free_agent'
    """, (team_id,)).fetchall()

    conn.close()

    players = [dict(p) for p in players]

    # Sort by protection score descending
    players.sort(key=lambda p: _protection_score(p), reverse=True)

    # Return top N player IDs
    protected_ids = [p["id"] for p in players[:protection_count]]
    return protected_ids


def auto_protect_all_teams(round_num: int, exclude_team_id: int = None,
                           db_path: str = None) -> dict:
    """
    Have all AI teams generate their protection lists.
    Returns {team_id: [protected_player_ids]}.
    """
    teams = query("SELECT id FROM teams", db_path=db_path)
    protections = {}

    for team in teams:
        tid = team["id"]
        if tid == exclude_team_id:
            continue
        protections[tid] = get_protection_list(tid, round_num, db_path)

    return protections


# ============================================================
# AVAILABLE PLAYERS
# ============================================================

def get_available_players(protections: dict = None, db_path: str = None) -> list:
    """
    Get all unprotected players available for the expansion draft.
    Excludes:
    - Players under age 22
    - Players drafted in the last 3 seasons
    - Protected players (from protections dict)
    - Free agents
    - Players already on the expansion team
    """
    conn = get_connection(db_path)

    # Get expansion team ID
    state = conn.execute("SELECT expansion_draft_json FROM game_state WHERE id=1").fetchone()
    draft_state = {}
    if state and state["expansion_draft_json"]:
        draft_state = json.loads(state["expansion_draft_json"])
    expansion_team_id = draft_state.get("expansion_team_id")

    # Get current season
    gs = conn.execute("SELECT season FROM game_state WHERE id=1").fetchone()
    season = gs["season"] if gs else 2026

    # Build excluded player IDs set
    excluded_ids = set()
    if protections:
        for team_id, player_ids in protections.items():
            excluded_ids.update(player_ids)

    # Get players drafted in last 3 seasons
    recent_drafted = conn.execute("""
        SELECT DISTINCT p.id FROM players p
        JOIN draft_prospects dp ON dp.first_name = p.first_name
            AND dp.last_name = p.last_name
        WHERE dp.is_drafted = 1 AND dp.season >= ?
    """, (season - 3,)).fetchall()
    for row in recent_drafted:
        excluded_ids.add(row["id"])

    # Get all eligible players
    all_players = conn.execute("""
        SELECT p.*, c.annual_salary, c.years_remaining,
               t.city as team_city, t.name as team_name, t.abbreviation as team_abbr
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        LEFT JOIN teams t ON t.id = p.team_id
        WHERE p.age >= 22
        AND p.roster_status != 'free_agent'
        AND (p.team_id IS NOT NULL AND p.team_id != ?)
    """, (expansion_team_id or -1,)).fetchall()

    conn.close()

    available = []
    for p in all_players:
        pd = dict(p)
        if pd["id"] not in excluded_ids:
            pd["overall"] = round(_calculate_player_ovr(pd), 1)
            available.append(pd)

    # Sort by overall descending
    available.sort(key=lambda x: x["overall"], reverse=True)
    return available


# ============================================================
# AI EXPANSION PICK
# ============================================================

def ai_expansion_pick(expansion_team_id: int, available: list,
                      db_path: str = None):
    """
    AI selects the best available player based on:
    - Positional need (fill each position first)
    - Overall rating
    - Age (prefer younger)
    - Contract (prefer cheaper)
    Returns the selected player dict or None.
    """
    conn = get_connection(db_path)

    # Get current roster composition
    roster = conn.execute("""
        SELECT position, COUNT(*) as cnt
        FROM players WHERE team_id = ?
        GROUP BY position
    """, (expansion_team_id,)).fetchall()
    conn.close()

    filled = {row["position"]: row["cnt"] for row in roster}

    # Determine positional needs
    needs = {}
    for pos, target in POSITION_TARGETS.items():
        current = filled.get(pos, 0)
        if current < target:
            needs[pos] = target - current

    if not available:
        return None

    # Score each available player
    scored = []
    for p in available:
        pos = p.get("position", "")
        ovr = p.get("overall", 0) or _calculate_player_ovr(p)
        age = p.get("age", 30)
        salary = p.get("annual_salary", 0) or 0

        # Need bonus: big bonus if position needed
        need_bonus = 0
        if pos in needs:
            need_bonus = 15 * needs[pos]
        elif pos in ("LF", "CF", "RF") and any(
            op in needs for op in ("LF", "CF", "RF")
        ):
            # Outfielders are somewhat interchangeable
            need_bonus = 8

        # Age bonus: prefer 24-30
        if 24 <= age <= 28:
            age_bonus = 5
        elif 22 <= age <= 30:
            age_bonus = 2
        else:
            age_bonus = -3

        # Salary penalty
        salary_penalty = 0
        if salary > 15_000_000:
            salary_penalty = (salary - 15_000_000) / 10_000_000 * 3

        score = ovr + need_bonus + age_bonus - salary_penalty
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)

    # Pick the best
    if scored:
        return scored[0][1]
    return None


# ============================================================
# MAKE EXPANSION PICK
# ============================================================

def make_expansion_pick(expansion_team_id: int, player_id: int,
                        db_path: str = None) -> dict:
    """
    Execute an expansion draft pick: transfer player to expansion team.
    Creates a new contract if needed.
    """
    conn = get_connection(db_path)

    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}

    old_team_id = player["team_id"]
    player_name = f"{player['first_name']} {player['last_name']}"

    # Transfer player
    conn.execute("""
        UPDATE players SET team_id=?, roster_status='active', on_forty_man=1
        WHERE id=?
    """, (expansion_team_id, player_id))

    # Transfer contract
    conn.execute("""
        UPDATE contracts SET team_id=? WHERE player_id=?
    """, (expansion_team_id, player_id))

    # If no contract exists, create a minimum one
    existing_contract = conn.execute(
        "SELECT id FROM contracts WHERE player_id=?", (player_id,)
    ).fetchone()
    if not existing_contract:
        gs = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
        current_date = gs["current_date"] if gs else "2026-01-01"
        conn.execute("""
            INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
                annual_salary, signed_date)
            VALUES (?, ?, 1, 1, 750000, ?)
        """, (player_id, expansion_team_id, current_date))

    # Log transaction
    gs = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    current_date = gs["current_date"] if gs else "2026-01-01"
    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, team2_id, player_ids)
        VALUES (?, 'expansion_draft', ?, ?, ?, ?)
    """, (
        current_date,
        json.dumps({
            "player_name": player_name,
            "from_team_id": old_team_id,
            "to_team_id": expansion_team_id,
            "position": player["position"],
        }),
        expansion_team_id,
        old_team_id,
        str(player_id),
    ))

    # Update draft state
    state_row = conn.execute(
        "SELECT expansion_draft_json FROM game_state WHERE id=1"
    ).fetchone()
    if state_row and state_row["expansion_draft_json"]:
        draft_state = json.loads(state_row["expansion_draft_json"])
        draft_state["picks_made"].append({
            "player_id": player_id,
            "player_name": player_name,
            "position": player["position"],
            "from_team_id": old_team_id,
            "overall": round(_calculate_player_ovr(dict(player)), 1),
        })
        picks_count = len(draft_state["picks_made"])
        draft_state["current_round"] = picks_count + 1
        if picks_count >= draft_state["total_picks_target"]:
            draft_state["status"] = "complete"
        else:
            draft_state["status"] = "drafting"
        conn.execute(
            "UPDATE game_state SET expansion_draft_json=? WHERE id=1",
            (json.dumps(draft_state),)
        )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "player_id": player_id,
        "player_name": player_name,
        "position": player["position"],
        "from_team_id": old_team_id,
    }


# ============================================================
# GET EXPANSION DRAFT STATUS
# ============================================================

def get_expansion_status(db_path: str = None) -> dict:
    """Get current state of the expansion draft."""
    conn = get_connection(db_path)
    state_row = conn.execute(
        "SELECT expansion_draft_json FROM game_state WHERE id=1"
    ).fetchone()
    conn.close()

    if not state_row or not state_row["expansion_draft_json"]:
        return {"active": False}

    draft_state = json.loads(state_row["expansion_draft_json"])
    draft_state["active"] = True
    return draft_state


def complete_expansion_draft(db_path: str = None) -> dict:
    """Mark the expansion draft as complete and clear the state."""
    conn = get_connection(db_path)
    state_row = conn.execute(
        "SELECT expansion_draft_json FROM game_state WHERE id=1"
    ).fetchone()

    if state_row and state_row["expansion_draft_json"]:
        draft_state = json.loads(state_row["expansion_draft_json"])
        draft_state["status"] = "complete"
        conn.execute(
            "UPDATE game_state SET expansion_draft_json=? WHERE id=1",
            (json.dumps(draft_state),)
        )

    conn.commit()
    conn.close()
    return {"success": True}
