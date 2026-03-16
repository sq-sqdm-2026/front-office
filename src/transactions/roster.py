"""
Front Office - Roster Management
40-man roster, call-ups, options, DFA, waivers, service time.
"""
import json
from ..database.db import get_connection, query, execute


def call_up_player(player_id: int, db_path: str = None) -> dict:
    """Promote a minor leaguer to the active roster."""
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}
    if player["roster_status"] not in ("minors_aaa", "minors_aa", "minors_low"):
        conn.close()
        return {"error": "Player is not in the minors"}

    # Check 26-man roster limit
    active_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND roster_status='active'
    """, (player["team_id"],)).fetchone()["c"]

    if active_count >= 26:
        conn.close()
        return {"error": "Active roster is full (26 players). Option or DFA someone first."}

    conn.execute("UPDATE players SET roster_status='active' WHERE id=?", (player_id,))

    state = conn.execute("SELECT current_date FROM game_state WHERE id=1").fetchone()
    game_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'call_up', '{}', ?, ?)
    """, (game_date, player["team_id"], str(player_id)))

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id}


def option_player(player_id: int, level: str = "minors_aaa",
                  db_path: str = None) -> dict:
    """Send an active player to the minors (if options remain)."""
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}
    if player["roster_status"] != "active":
        conn.close()
        return {"error": "Player is not on the active roster"}
    if player["option_years_remaining"] <= 0:
        conn.close()
        return {"error": "Player has no option years remaining. Must DFA instead."}

    conn.execute("UPDATE players SET roster_status=?, option_years_remaining=option_years_remaining-1 WHERE id=?",
                (level, player_id))

    state = conn.execute("SELECT current_date FROM game_state WHERE id=1").fetchone()
    game_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'option', ?, ?, ?)
    """, (game_date, json.dumps({"level": level}), player["team_id"], str(player_id)))

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id, "level": level}


def dfa_player(player_id: int, db_path: str = None) -> dict:
    """Designate a player for assignment."""
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}

    conn.execute("UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
                (player_id,))

    state = conn.execute("SELECT current_date FROM game_state WHERE id=1").fetchone()
    game_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'dfa', '{}', ?, ?)
    """, (game_date, player["team_id"], str(player_id)))

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id}


def get_roster_summary(team_id: int, db_path: str = None) -> dict:
    """Get a team's full roster organized by status."""
    active = query("""
        SELECT p.*, c.annual_salary, c.years_remaining
        FROM players p LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        ORDER BY CASE p.position
            WHEN 'C' THEN 1 WHEN '1B' THEN 2 WHEN '2B' THEN 3
            WHEN '3B' THEN 4 WHEN 'SS' THEN 5 WHEN 'LF' THEN 6
            WHEN 'CF' THEN 7 WHEN 'RF' THEN 8 WHEN 'DH' THEN 9
            WHEN 'SP' THEN 10 WHEN 'RP' THEN 11 END
    """, (team_id,), db_path=db_path)

    minors = query("""
        SELECT p.*, c.annual_salary, c.years_remaining
        FROM players p LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status LIKE 'minors%'
        ORDER BY p.roster_status, p.position
    """, (team_id,), db_path=db_path)

    injured = query("""
        SELECT p.*, c.annual_salary, c.years_remaining
        FROM players p LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.is_injured=1
    """, (team_id,), db_path=db_path)

    payroll = sum(p.get("annual_salary", 0) or 0 for p in active + minors)

    return {
        "active": active,
        "active_count": len(active),
        "minors": minors,
        "minors_count": len(minors),
        "injured": injured,
        "injured_count": len(injured),
        "forty_man_count": len(active) + len(minors),
        "payroll": payroll,
    }
