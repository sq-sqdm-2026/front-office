"""
Front Office - Roster Management
40-man roster, call-ups, options, DFA, waivers, service time.
Includes September callups and position eligibility tracking.
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

    # Check roster limits (26 regular, 28 in September)
    current_date = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
    game_date = current_date[0]["current_date"] if current_date else "2026-01-01"

    from datetime import date
    date_obj = date.fromisoformat(game_date)
    is_september = date_obj.month == 9 and date_obj.day >= 1

    roster_limit = 28 if is_september else 26

    active_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND roster_status='active'
    """, (player["team_id"],)).fetchone()["c"]

    if active_count >= roster_limit:
        conn.close()
        limit_str = "28 (September expansion)" if is_september else "26"
        return {"error": f"Active roster is full ({limit_str} players). Option or DFA someone first."}

    # Check 40-man roster limit
    forty_man_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND on_forty_man=1
    """, (player["team_id"],)).fetchone()["c"]

    if not player["on_forty_man"] and forty_man_count >= 40:
        conn.close()
        return {"error": "40-man roster is full (40 players). Remove someone from the 40-man first."}

    # If player isn't on 40-man, add them
    if not player["on_forty_man"]:
        conn.execute("UPDATE players SET on_forty_man=1 WHERE id=?", (player_id,))

    conn.execute("UPDATE players SET roster_status='active' WHERE id=?", (player_id,))

    state = conn.execute("SELECT current_date FROM game_state WHERE id=1").fetchone()
    call_up_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'call_up', '{}', ?, ?)
    """, (call_up_date, player["team_id"], str(player_id)))

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
    option_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'option', ?, ?, ?)
    """, (option_date, json.dumps({"level": level}), player["team_id"], str(player_id)))

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id, "level": level}


def dfa_player(player_id: int, db_path: str = None) -> dict:
    """Designate a player for assignment. Places on waivers for 7 days."""
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}

    state = conn.execute("SELECT current_date FROM game_state WHERE id=1").fetchone()
    dfa_date = state["current_date"] if state else "2025-01-01"

    conn.execute("UPDATE players SET roster_status='dfa_waivers', on_forty_man=0 WHERE id=?",
                (player_id,))

    from datetime import date, timedelta
    dfa_date_obj = date.fromisoformat(dfa_date)
    expiry_date = (dfa_date_obj + timedelta(days=7)).isoformat()

    conn.execute("""
        INSERT INTO waiver_claims (player_id, original_team_id, dfa_date, expiry_date, status)
        VALUES (?, ?, ?, ?, 'pending')
    """, (player_id, player["team_id"], dfa_date, expiry_date))

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'dfa', '{}', ?, ?)
    """, (dfa_date, player["team_id"], str(player_id)))

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id, "waiver_expiry": expiry_date}


def add_to_forty_man(player_id: int, db_path: str = None) -> dict:
    """Add a player to the 40-man roster."""
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}
    if player["on_forty_man"]:
        conn.close()
        return {"error": "Player is already on the 40-man roster"}

    forty_man_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND on_forty_man=1
    """, (player["team_id"],)).fetchone()["c"]

    if forty_man_count >= 40:
        conn.close()
        return {"error": "40-man roster is full (40 players). Remove someone first."}

    conn.execute("UPDATE players SET on_forty_man=1 WHERE id=?", (player_id,))
    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id}


def remove_from_forty_man(player_id: int, db_path: str = None) -> dict:
    """Remove a player from the 40-man roster."""
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}
    if not player["on_forty_man"]:
        conn.close()
        return {"error": "Player is not on the 40-man roster"}
    if player["roster_status"] == "active":
        conn.close()
        return {"error": "Cannot remove an active player from the 40-man. Option or DFA first."}

    conn.execute("UPDATE players SET on_forty_man=0 WHERE id=?", (player_id,))
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

    forty_man = query("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND on_forty_man=1
    """, (team_id,), db_path=db_path)
    forty_man_count = forty_man[0]["c"] if forty_man else 0

    payroll = sum(p.get("annual_salary", 0) or 0 for p in active + minors)

    return {
        "active": active,
        "active_count": len(active),
        "minors": minors,
        "minors_count": len(minors),
        "injured": injured,
        "injured_count": len(injured),
        "forty_man_count": forty_man_count,
        "payroll": payroll,
    }


def get_player_eligible_positions(player_id: int, db_path: str = None) -> list:
    """Get all positions a player is eligible to play based on games played.
    Returns a list of positions, with primary position first.
    """
    player = query("SELECT position FROM players WHERE id=?", (player_id,), db_path=db_path)
    if not player:
        return []

    primary = player[0]["position"]
    eligible = [primary]

    # Check secondary positions with 10+ games played
    positions = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
    for pos in positions:
        if pos == primary:
            continue

        games_at_pos = query("""
            SELECT COUNT(*) as games FROM batting_lines
            WHERE player_id=? AND position_played=?
        """, (player_id, pos), db_path=db_path)

        if games_at_pos and games_at_pos[0]["games"] >= 10:
            eligible.append(pos)

    return eligible


def update_secondary_positions(player_id: int, db_path: str = None) -> dict:
    """Update secondary_positions field based on games played history.
    Returns updated player data.
    """
    eligible = get_player_eligible_positions(player_id, db_path)
    if not eligible:
        return {"error": "Player not found"}

    primary = eligible[0]
    secondary = ",".join(eligible[1:]) if len(eligible) > 1 else ""

    conn = get_connection(db_path)
    conn.execute("UPDATE players SET secondary_positions=? WHERE id=?",
                (secondary, player_id))
    conn.commit()
    conn.close()

    return {
        "player_id": player_id,
        "primary_position": primary,
        "eligible_positions": eligible,
        "secondary_positions": secondary,
    }


def september_callup_auto(team_id: int, db_path: str = None) -> dict:
    """Auto call-up best available minor leaguers during September."""
    conn = get_connection(db_path)

    # Check if September
    state = conn.execute("SELECT current_date FROM game_state WHERE id=1").fetchone()
    if not state:
        conn.close()
        return {"error": "No game state"}

    from datetime import date
    game_date = date.fromisoformat(state["current_date"])
    if game_date.month != 9 or game_date.day < 1:
        conn.close()
        return {"error": "Not in September"}

    # Get current active roster size
    active_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND roster_status='active'
    """, (team_id,)).fetchone()["c"]

    callup_slots = max(0, 28 - active_count)

    # Get best available minor leaguers
    minors = query("""
        SELECT p.*, c.annual_salary FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status LIKE 'minors%'
        ORDER BY p.power_rating + p.contact_rating DESC
        LIMIT ?
    """, (team_id, callup_slots), db_path=db_path)

    called_up = []
    for player in minors:
        # Call up this player
        call_up_result = call_up_player(player["id"], db_path)
        if call_up_result.get("success"):
            called_up.append({
                "player_id": player["id"],
                "name": f"{player['first_name']} {player['last_name']}",
                "position": player["position"],
            })

    conn.close()

    return {
        "team_id": team_id,
        "called_up_count": len(called_up),
        "called_up": called_up,
    }
