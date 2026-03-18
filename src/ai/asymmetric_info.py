"""
Front Office - Asymmetric Information System
"What you know depends on who you trust."
Controls how much the user knows about other teams' players, prospects,
and trade intentions based on scouting investment, GM relationships,
beat writers, and agent connections.
"""
import json
import random
from enum import IntEnum
from ..database.db import query, execute, get_connection


class InformationLevel(IntEnum):
    """How much the user knows about a subject. Higher = better intel."""
    UNKNOWN = 0
    RUMOR = 1
    SCOUTED = 2
    VERIFIED = 3
    INSIDER = 4


# Rating fields used across the system
PITCHER_RATINGS = ["stuff_rating", "control_rating", "stamina_rating"]
HITTER_RATINGS = ["contact_rating", "power_rating", "speed_rating",
                  "fielding_rating", "arm_rating"]
ALL_RATINGS = PITCHER_RATINGS + HITTER_RATINGS
POTENTIAL_FIELDS = [f.replace("_rating", "_potential") for f in ALL_RATINGS]


def _clamp(value: int, lo: int = 20, hi: int = 80) -> int:
    """Clamp a rating to the 20-80 scouting scale."""
    return max(lo, min(hi, int(value)))


def _get_user_team_id(db_path: str = None) -> int:
    """Retrieve the user's team id from game_state."""
    gs = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
    return gs[0]["user_team_id"] if gs else None


def _get_game_date(db_path: str = None) -> str:
    """Retrieve the current game date from game_state."""
    gs = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
    return gs[0]["current_date"] if gs else "2026-02-15"


# ------------------------------------------------------------------
# Core: determine information level
# ------------------------------------------------------------------

def get_player_info_level(user_team_id: int, player_id: int,
                          db_path: str = None) -> InformationLevel:
    """Determine how much the user knows about a given player.

    Priority order (highest wins):
      1. Same team           -> VERIFIED
      2. Agent relationship  -> INSIDER
      3. Active scouting     -> SCOUTED (or higher if scout finished)
      4. Division rival      -> RUMOR
      5. Otherwise           -> UNKNOWN
    """
    # 1. Own player?
    own = query(
        "SELECT id FROM players WHERE id=? AND team_id=?",
        (player_id, user_team_id), db_path=db_path,
    )
    if own:
        return InformationLevel.VERIFIED

    # 2. Agent relationship leak?  The user's team has relationships stored
    #    via agent_characters.  If an agent represents the target player AND
    #    also represents a player on the user's team, they leak information.
    agent_link = query("""
        SELECT 1 FROM player_agents pa1
        JOIN player_agents pa2 ON pa1.agent_id = pa2.agent_id
        JOIN players p ON p.id = pa2.player_id
        WHERE pa1.player_id = ? AND p.team_id = ?
        LIMIT 1
    """, (player_id, user_team_id), db_path=db_path)
    if agent_link:
        return InformationLevel.INSIDER

    # 3. Active scouting assignment?
    scout = query("""
        SELECT info_level FROM scouting_assignments
        WHERE team_id=? AND player_id=?
        ORDER BY info_level DESC LIMIT 1
    """, (user_team_id, player_id), db_path=db_path)
    if scout:
        lvl = scout[0]["info_level"]
        try:
            return InformationLevel(lvl)
        except ValueError:
            return InformationLevel.SCOUTED

    # 4. Division rival?
    player_team = query(
        "SELECT team_id FROM players WHERE id=?", (player_id,),
        db_path=db_path,
    )
    if player_team and player_team[0]["team_id"]:
        other_team_id = player_team[0]["team_id"]
        division_match = query("""
            SELECT 1 FROM teams t1
            JOIN teams t2 ON t1.league = t2.league AND t1.division = t2.division
            WHERE t1.id = ? AND t2.id = ?
        """, (user_team_id, other_team_id), db_path=db_path)
        if division_match:
            return InformationLevel.RUMOR

    return InformationLevel.UNKNOWN


# ------------------------------------------------------------------
# Apply uncertainty to player data
# ------------------------------------------------------------------

def apply_info_uncertainty(player_data: dict,
                           info_level: InformationLevel) -> dict:
    """Return a copy of *player_data* with noise / redaction applied.

    - VERIFIED : exact ratings shown
    - INSIDER  : +/- 2 uncertainty on ratings
    - SCOUTED  : +/- 5 uncertainty on ratings
    - RUMOR    : +/- 10 uncertainty, potentials hidden
    - UNKNOWN  : all ratings & potentials hidden, only basic bio visible
    """
    out = player_data.copy()
    out["info_level"] = info_level.name
    out["info_level_value"] = int(info_level)

    if info_level == InformationLevel.VERIFIED:
        return out

    if info_level == InformationLevel.UNKNOWN:
        # Hide all ratings and potentials
        for field in ALL_RATINGS + POTENTIAL_FIELDS:
            out[field] = None
        out["eye_rating"] = None
        out["eye_potential"] = None
        # Hide personality traits
        for trait in ("ego", "leadership", "work_ethic", "clutch",
                      "durability", "loyalty", "greed", "composure",
                      "intelligence", "aggression", "sociability", "morale"):
            out[trait] = None
        return out

    # RUMOR / SCOUTED / INSIDER  -> add noise
    noise_map = {
        InformationLevel.INSIDER: 2,
        InformationLevel.SCOUTED: 5,
        InformationLevel.RUMOR: 10,
    }
    margin = noise_map[info_level]

    for field in ALL_RATINGS:
        val = player_data.get(field)
        if val is not None:
            noise = random.randint(-margin, margin)
            out[field] = _clamp(val + noise)

    # Eye rating
    eye = player_data.get("eye_rating")
    if eye is not None:
        out["eye_rating"] = _clamp(eye + random.randint(-margin, margin))

    # Potentials: visible for INSIDER and SCOUTED, hidden for RUMOR
    if info_level == InformationLevel.RUMOR:
        for field in POTENTIAL_FIELDS:
            out[field] = None
        out["eye_potential"] = None
    else:
        for field in POTENTIAL_FIELDS:
            val = player_data.get(field)
            if val is not None:
                out[field] = _clamp(val + random.randint(-margin, margin))
        eye_pot = player_data.get("eye_potential")
        if eye_pot is not None:
            out["eye_potential"] = _clamp(
                eye_pot + random.randint(-margin, margin)
            )

    return out


# ------------------------------------------------------------------
# Trade intelligence
# ------------------------------------------------------------------

def get_trade_intelligence(user_team_id: int, other_team_id: int,
                           db_path: str = None) -> dict:
    """Return what the user knows about another team's trade intentions.

    Sources of intel:
      - GM relationship score  -> higher = more detail
      - Beat writer contacts   -> intelligence_reports with source='beat_writer'
      - Recent transactions    -> public info
    """
    # GM relationship
    gm = query(
        "SELECT relationships_json FROM gm_characters WHERE team_id=?",
        (user_team_id,), db_path=db_path,
    )
    relationship_score = 50  # neutral default
    if gm and gm[0].get("relationships_json"):
        try:
            rels = json.loads(gm[0]["relationships_json"])
            # relationships are keyed by gm id or team id (varies by save)
            other_gm = query(
                "SELECT id FROM gm_characters WHERE team_id=?",
                (other_team_id,), db_path=db_path,
            )
            if other_gm:
                gm_id_str = str(other_gm[0]["id"])
                relationship_score = rels.get(gm_id_str, 50)
        except (json.JSONDecodeError, TypeError):
            pass

    # Division rivals get a base bonus
    div_match = query("""
        SELECT 1 FROM teams t1 JOIN teams t2
        ON t1.league = t2.league AND t1.division = t2.division
        WHERE t1.id=? AND t2.id=?
    """, (user_team_id, other_team_id), db_path=db_path)
    is_division_rival = bool(div_match)

    # Trading block (public info)
    other_team = query(
        "SELECT trading_block_json FROM teams WHERE id=?",
        (other_team_id,), db_path=db_path,
    )
    trading_block = {}
    if other_team and other_team[0].get("trading_block_json"):
        try:
            trading_block = json.loads(other_team[0]["trading_block_json"])
        except (json.JSONDecodeError, TypeError):
            pass

    # Intelligence reports from our scouts / beat writers
    reports = query("""
        SELECT report_data, source, info_level, game_date
        FROM intelligence_reports
        WHERE team_id=? AND subject_type='team' AND subject_id=?
        ORDER BY game_date DESC LIMIT 5
    """, (user_team_id, other_team_id), db_path=db_path)

    parsed_reports = []
    for r in (reports or []):
        try:
            parsed_reports.append({
                "data": json.loads(r["report_data"]) if r["report_data"] else {},
                "source": r["source"],
                "info_level": r["info_level"],
                "date": r["game_date"],
            })
        except (json.JSONDecodeError, TypeError):
            pass

    # Determine detail level
    if relationship_score >= 75:
        detail = "high"
        intentions_visible = True
    elif relationship_score >= 50 or is_division_rival:
        detail = "medium"
        intentions_visible = True
    else:
        detail = "low"
        intentions_visible = False

    # Recent public transactions for context
    recent_txns = query("""
        SELECT transaction_type, details_json, transaction_date
        FROM transactions
        WHERE (team1_id=? OR team2_id=?)
        ORDER BY transaction_date DESC LIMIT 5
    """, (other_team_id, other_team_id), db_path=db_path)

    result = {
        "other_team_id": other_team_id,
        "relationship_score": relationship_score,
        "is_division_rival": is_division_rival,
        "detail_level": detail,
        "trading_block": trading_block if intentions_visible else {"players": []},
        "intelligence_reports": parsed_reports,
        "recent_transactions": recent_txns or [],
    }

    return result


# ------------------------------------------------------------------
# Scout a player
# ------------------------------------------------------------------

def scout_player(user_team_id: int, player_id: int,
                 db_path: str = None) -> dict:
    """Assign a scout to observe a player, improving info level over time.

    Scout quality is derived from the team's scouting_staff_budget.
    If already scouting this player, returns the existing assignment.
    """
    # Don't scout your own players
    own = query("SELECT id FROM players WHERE id=? AND team_id=?",
                (player_id, user_team_id), db_path=db_path)
    if own:
        return {"status": "already_known",
                "info_level": InformationLevel.VERIFIED.name,
                "message": "This is your own player - you already have full information."}

    # Check for existing assignment
    existing = query("""
        SELECT * FROM scouting_assignments
        WHERE team_id=? AND player_id=?
    """, (user_team_id, player_id), db_path=db_path)
    if existing:
        return {
            "status": "already_scouting",
            "assignment_id": existing[0]["id"],
            "info_level": InformationLevel(existing[0]["info_level"]).name,
            "started_date": existing[0]["started_date"],
            "message": "Scout already assigned to this player.",
        }

    # Calculate scout quality from scouting budget
    team = query("SELECT scouting_staff_budget FROM teams WHERE id=?",
                 (user_team_id,), db_path=db_path)
    budget = team[0]["scouting_staff_budget"] if team else 10_000_000
    # $2M -> quality 10, $10M -> quality 50, $20M -> quality 100
    scout_quality = min(100, max(10, budget // 200_000))

    game_date = _get_game_date(db_path)

    # Initial info level is SCOUTED (the scout has been assigned and will
    # report back basic observations immediately).
    initial_level = int(InformationLevel.SCOUTED)

    execute("""
        INSERT INTO scouting_assignments
            (team_id, player_id, scout_quality, started_date, info_level)
        VALUES (?, ?, ?, ?, ?)
    """, (user_team_id, player_id, scout_quality, game_date, initial_level),
        db_path=db_path)

    # Also create an initial intelligence report
    player_row = query("SELECT first_name, last_name, position, age, team_id FROM players WHERE id=?",
                       (player_id,), db_path=db_path)
    report_data = {}
    if player_row:
        p = player_row[0]
        report_data = {
            "player_name": f"{p['first_name']} {p['last_name']}",
            "position": p["position"],
            "age": p["age"],
            "summary": f"Scout dispatched to observe {p['first_name']} {p['last_name']}. Initial observations incoming.",
        }

    execute("""
        INSERT INTO intelligence_reports
            (team_id, subject_type, subject_id, info_level, report_data, source, game_date)
        VALUES (?, 'player', ?, ?, ?, 'scout', ?)
    """, (user_team_id, player_id, initial_level,
          json.dumps(report_data), game_date), db_path=db_path)

    return {
        "status": "scout_assigned",
        "info_level": InformationLevel(initial_level).name,
        "scout_quality": scout_quality,
        "started_date": game_date,
        "message": f"Scout (quality {scout_quality}) dispatched. Initial report available; deeper intel coming.",
    }


# ------------------------------------------------------------------
# Retrieve all intelligence
# ------------------------------------------------------------------

def get_available_intel(user_team_id: int,
                        db_path: str = None) -> dict:
    """Return all intelligence gathered by the user's team.

    Includes:
      - Active scouting assignments
      - Intelligence reports (all types)
    """
    assignments = query("""
        SELECT sa.*, p.first_name, p.last_name, p.position,
               p.team_id as player_team_id,
               t.city || ' ' || t.name as player_team_name
        FROM scouting_assignments sa
        JOIN players p ON p.id = sa.player_id
        LEFT JOIN teams t ON t.id = p.team_id
        WHERE sa.team_id = ?
        ORDER BY sa.started_date DESC
    """, (user_team_id,), db_path=db_path)

    reports = query("""
        SELECT * FROM intelligence_reports
        WHERE team_id = ?
        ORDER BY game_date DESC
        LIMIT 50
    """, (user_team_id,), db_path=db_path)

    # Parse report_data JSON
    parsed_reports = []
    for r in (reports or []):
        entry = dict(r)
        try:
            entry["report_data"] = json.loads(r["report_data"]) if r["report_data"] else {}
        except (json.JSONDecodeError, TypeError):
            entry["report_data"] = {}
        parsed_reports.append(entry)

    return {
        "scouting_assignments": assignments or [],
        "intelligence_reports": parsed_reports,
    }


# ------------------------------------------------------------------
# Advance scouting (called during day advance to mature assignments)
# ------------------------------------------------------------------

def advance_scouting_assignments(db_path: str = None):
    """Called each game-day advance.  Mature scouting assignments over time.

    Each day a scout is assigned, there is a chance the info_level improves
    based on scout_quality.  Higher quality scouts discover intel faster.
    """
    assignments = query("""
        SELECT sa.*, p.team_id as player_team_id
        FROM scouting_assignments sa
        JOIN players p ON p.id = sa.player_id
        WHERE sa.info_level < ?
    """, (int(InformationLevel.VERIFIED),), db_path=db_path)

    game_date = _get_game_date(db_path)

    for a in (assignments or []):
        current_level = a["info_level"]
        quality = a["scout_quality"]

        # Daily chance to improve: quality/500  (quality 50 -> 10% per day)
        chance = quality / 500.0
        if random.random() < chance:
            new_level = min(current_level + 1, int(InformationLevel.VERIFIED))
            execute("""
                UPDATE scouting_assignments SET info_level=?
                WHERE id=?
            """, (new_level, a["id"]), db_path=db_path)

            # Generate a new intel report for the upgrade
            player_row = query(
                "SELECT first_name, last_name, position FROM players WHERE id=?",
                (a["player_id"],), db_path=db_path,
            )
            if player_row:
                p = player_row[0]
                level_name = InformationLevel(new_level).name
                report = {
                    "player_name": f"{p['first_name']} {p['last_name']}",
                    "position": p["position"],
                    "summary": (
                        f"Scout report upgraded to {level_name} for "
                        f"{p['first_name']} {p['last_name']}."
                    ),
                }
                execute("""
                    INSERT INTO intelligence_reports
                        (team_id, subject_type, subject_id, info_level,
                         report_data, source, game_date)
                    VALUES (?, 'player', ?, ?, ?, 'scout', ?)
                """, (a["team_id"], a["player_id"], new_level,
                      json.dumps(report), game_date), db_path=db_path)
