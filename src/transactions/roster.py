"""
Front Office - Roster Management
40-man roster, call-ups, options, DFA, waivers, service time.
Includes September callups, position eligibility tracking, Rule 5 draft,
IL auto-management, and rehab assignments.
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
    if player["roster_status"] not in ("minors_aaa", "minors_aa", "minors_high_a", "minors_low", "minors_rookie"):
        conn.close()
        return {"error": "Player is not in the minors"}

    # Check roster limits (26 regular, 28 in September)
    current_date = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
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

    # Check 40-man roster limit (all players flagged on_forty_man)
    forty_man_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND on_forty_man=1
    """, (player["team_id"],)).fetchone()["c"]

    if forty_man_count >= 40:
        conn.close()
        return {"error": "40-man roster is full (40 players). Remove someone from the 40-man first."}

    # Mark player as on 40-man (if not already)
    if not player["on_forty_man"]:
        conn.execute("UPDATE players SET on_forty_man=1 WHERE id=?", (player_id,))

    conn.execute("UPDATE players SET roster_status='active' WHERE id=?", (player_id,))

    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    call_up_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'call_up', '{}', ?, ?)
    """, (call_up_date, player["team_id"], str(player_id)))

    conn.commit()

    # Character reactions to the call-up
    player_name = f"{player['first_name']} {player['last_name']}"
    from_level = {"minors_aaa": "AAA", "minors_aa": "AA",
                  "minors_low": "Low-A"}.get(player["roster_status"], "the minors")
    try:
        state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
        if state and state[0]["user_team_id"] == player["team_id"]:
            from ..ai.proactive_messaging import send_callup_reactions
            send_callup_reactions(
                player["team_id"], call_up_date, player_name,
                from_level, db_path=db_path
            )
    except Exception:
        pass

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

    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    option_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'option', ?, ?, ?)
    """, (option_date, json.dumps({"level": level}), player["team_id"], str(player_id)))

    conn.commit()

    # Character reactions to the option
    player_name = f"{player['first_name']} {player['last_name']}"
    level_label = {"minors_aaa": "AAA", "minors_aa": "AA",
                   "minors_low": "Low-A"}.get(level, level)
    try:
        state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
        if state and state[0]["user_team_id"] == player["team_id"]:
            from ..ai.proactive_messaging import send_option_reactions
            send_option_reactions(
                player["team_id"], option_date, player_name,
                level_label, player_id=player_id, db_path=db_path
            )
    except Exception:
        pass

    conn.close()
    return {"success": True, "player_id": player_id, "level": level}


def dfa_player(player_id: int, db_path: str = None) -> dict:
    """Designate a player for assignment. Places on waivers for 7 days."""
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}

    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
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

    # Character reactions to the DFA
    player_name = f"{player['first_name']} {player['last_name']}"
    try:
        user_state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
        if user_state and user_state[0]["user_team_id"] == player["team_id"]:
            from ..ai.proactive_messaging import send_dfa_reactions
            send_dfa_reactions(
                player["team_id"], dfa_date, player_name,
                player_id=player_id, db_path=db_path
            )
    except Exception:
        pass

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

    # Count actual 40-man roster spots (all players flagged on_forty_man)
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


def release_player(player_id: int, db_path: str = None) -> dict:
    """Release a player from the team. They become a free agent."""
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}

    # Set player as free agent
    conn.execute("""
        UPDATE players SET team_id=NULL, roster_status='free_agent', on_forty_man=0
        WHERE id=?
    """, (player_id,))

    # Delete any existing contract
    conn.execute("DELETE FROM contracts WHERE player_id=?", (player_id,))

    # Log the transaction
    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    release_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'release', '{}', ?, ?)
    """, (release_date, player["team_id"], str(player_id)))

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
        WHERE p.team_id=? AND (p.is_injured=1 OR p.roster_status IN ('injured_dl', 'rehab'))
    """, (team_id,), db_path=db_path)

    # 40-man roster includes all players flagged on_forty_man
    # (active, IL, and minor leaguers added to 40-man)
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
    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
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


# ============================================================
# RULE 5 DRAFT
# ============================================================

def process_rule_5_draft(season: int, db_path: str = None) -> list:
    """
    Process the Rule 5 Draft.

    Eligibility:
    - Players NOT on the 40-man roster
    - In the minors
    - Signed/drafted 5+ years ago if signed at age 18 or younger (high school)
    - Signed/drafted 4+ years ago if signed at age 19+ (college)

    Rules:
    - Each team can select one Rule 5 eligible player from another team for $100,000
    - The selecting team MUST keep the player on 25-man active roster all next season
    - If they can't, must offer back to original team for $50,000
    - Draft order: inverse of regular season standings (worst record first)

    AI logic: select a player if overall rating >= 45 AND 40-man roster has space.
    """
    conn = get_connection(db_path)

    # Get current game state
    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    current_date = state["current_date"] if state else "2026-01-01"
    user_team_id = state["user_team_id"] if state else None

    # Get eligible players:
    # High school players (signed at 18 or younger): need 5+ years in system
    # College players (signed at 19+): need 4+ years in system
    # We approximate by age: if current age - 18 >= 5 (joined at 18, 5 years)
    # or age - 19 >= 4 (joined at 19+, 4 years)
    # This simplification matches the existing approach
    eligible = query("""
        SELECT p.*, t.id as current_team_id, t.city as team_city, t.name as team_name
        FROM players p
        JOIN teams t ON t.id = p.team_id
        WHERE p.on_forty_man = 0
        AND p.roster_status LIKE 'minors%'
        AND (
            (p.age - 18 >= 5) OR (p.age - 19 >= 4)
        )
        ORDER BY (p.contact_rating + p.power_rating + p.speed_rating +
                  p.fielding_rating + p.stuff_rating + p.control_rating) DESC
    """, db_path=db_path)

    if not eligible:
        conn.close()
        return []

    # Get teams in draft order (inverse of regular season standings = worst first)
    teams = query("""
        SELECT t.id, t.city, t.name FROM teams t
    """, db_path=db_path)

    # Calculate W-L for each team to determine draft order
    team_records = []
    for t in teams:
        wins = query("""
            SELECT COUNT(*) as w FROM schedule
            WHERE season=? AND is_played=1 AND is_postseason=0 AND (
                (home_team_id=? AND home_score > away_score) OR
                (away_team_id=? AND away_score > home_score)
            )
        """, (season, t["id"], t["id"]), db_path=db_path)[0]["w"]

        team_records.append({
            "id": t["id"],
            "city": t["city"],
            "name": t["name"],
            "wins": wins,
        })

    # Sort by wins ascending (worst record picks first)
    team_records.sort(key=lambda x: x["wins"])

    picks = []
    selected_player_ids = set()

    for team in team_records:
        if not eligible:
            break

        team_id = team["id"]

        # Skip user's team (they handle Rule 5 manually via UI)
        if team_id == user_team_id:
            continue

        # Check 40-man roster space
        forty_man_count = conn.execute("""
            SELECT COUNT(*) as c FROM players
            WHERE team_id=? AND on_forty_man=1
        """, (team_id,)).fetchone()["c"]

        if forty_man_count >= 40:
            continue  # No 40-man room

        # AI decision: select best available player with overall rating >= 45
        best_fit = None
        best_idx = None

        for i, player in enumerate(eligible):
            if player["id"] in selected_player_ids:
                continue
            if player["current_team_id"] == team_id:
                continue  # Can't select from own organization

            # Calculate overall rating
            if player["position"] in ("SP", "RP"):
                overall = (player["stuff_rating"] + player["control_rating"] +
                          player["stamina_rating"]) / 3
            else:
                overall = (player["contact_rating"] + player["power_rating"] +
                          player["speed_rating"] + player["fielding_rating"]) / 4

            if overall >= 45:
                best_fit = player
                best_idx = i
                break

        if not best_fit:
            continue  # No suitable player found

        player_id = best_fit["id"]
        from_team_id = best_fit["current_team_id"]

        # Transfer to new team: must go on active roster and 40-man
        conn.execute("""
            UPDATE players SET team_id=?, on_forty_man=1, roster_status='active'
            WHERE id=?
        """, (team_id, player_id))

        # Create minimum salary contract ($100,000 selection fee, league minimum salary)
        from datetime import date
        conn.execute("""
            INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
                annual_salary, signed_date)
            VALUES (?, ?, 1, 1, 750000, ?)
        """, (player_id, team_id, current_date))

        # Track in transactions
        conn.execute("""
            INSERT INTO transactions (transaction_date, transaction_type,
                details_json, team1_id, team2_id, player_ids)
            VALUES (?, 'rule_5_draft', ?, ?, ?, ?)
        """, (current_date,
              json.dumps({
                  "from_team_id": from_team_id,
                  "to_team_id": team_id,
                  "selection_fee": 100000,
                  "must_remain_active_roster": True,
                  "return_fee": 50000,
              }),
              from_team_id, team_id, str(player_id)))

        picks.append({
            "team_id": team_id,
            "team_name": f"{team['city']} {team['name']}",
            "player_id": player_id,
            "player_name": f"{best_fit['first_name']} {best_fit['last_name']}",
            "position": best_fit["position"],
            "from_team": f"{best_fit['team_city']} {best_fit['team_name']}",
        })

        selected_player_ids.add(player_id)
        eligible.pop(best_idx)

    conn.commit()
    conn.close()

    return picks


# ============================================================
# IL AUTO-MANAGEMENT
# ============================================================

def auto_manage_injured_list(game_date: str, db_path: str = None) -> list:
    """
    Automatically manage the injured list:
    - When a player is injured, ensure they are on roster_status='injured_dl'
    - When an injury heals (injury_days_remaining reaches 0), move back to active
      IF roster space exists, otherwise keep on IL until manually activated

    This is called from the daily sim loop (advance_date or check_injuries_for_day).
    Note: Most IL management is now handled directly in check_injuries_for_day(),
    but this function catches any edge cases where the status is out of sync.
    """
    conn = get_connection(db_path)
    events = []

    # Fix any players who are injured but not on IL status
    mismatched = conn.execute("""
        SELECT id, first_name, last_name, team_id, injury_type, il_tier
        FROM players
        WHERE is_injured=1 AND injury_days_remaining > 0
        AND roster_status NOT IN ('injured_dl', 'rehab')
    """).fetchall()

    for p in mismatched:
        conn.execute("""
            UPDATE players SET roster_status='injured_dl' WHERE id=?
        """, (p["id"],))
        events.append({
            "type": "auto_il_placement",
            "player_id": p["id"],
            "name": f"{p['first_name']} {p['last_name']}",
            "team_id": p["team_id"],
        })

    # Find healed players still stuck on IL (injury cleared but status not updated)
    healed_on_il = conn.execute("""
        SELECT id, first_name, last_name, team_id
        FROM players
        WHERE is_injured=0 AND injury_days_remaining=0
        AND roster_status='injured_dl' AND injury_type IS NULL
    """).fetchall()

    from datetime import date as date_cls
    date_obj = date_cls.fromisoformat(game_date)
    roster_limit = 28 if date_obj.month == 9 else 26

    for p in healed_on_il:
        active_count = conn.execute("""
            SELECT COUNT(*) as c FROM players
            WHERE team_id=? AND roster_status='active'
        """, (p["team_id"],)).fetchone()["c"]

        if active_count < roster_limit:
            conn.execute("""
                UPDATE players SET roster_status='active', il_tier=NULL WHERE id=?
            """, (p["id"],))
            events.append({
                "type": "auto_il_activation",
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "team_id": p["team_id"],
            })

    conn.commit()
    conn.close()
    return events


def activate_from_il(player_id: int, db_path: str = None) -> dict:
    """
    Manually activate a player from the injured list.
    Used when auto-activation couldn't happen due to roster constraints
    (the user must option/DFA someone first, then activate).
    """
    conn = get_connection(db_path)
    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}

    if player["is_injured"] and player["injury_days_remaining"] > 0:
        conn.close()
        return {"error": "Player is still injured and cannot be activated yet."}

    if player["roster_status"] == "rehab" and player.get("injury_days_remaining", 0) > 0:
        conn.close()
        return {"error": "Player is still on a rehab assignment."}

    # Check roster space
    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    game_date = state["current_date"] if state else "2026-01-01"

    from datetime import date
    date_obj = date.fromisoformat(game_date)
    roster_limit = 28 if date_obj.month == 9 else 26

    active_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND roster_status='active'
    """, (player["team_id"],)).fetchone()["c"]

    if active_count >= roster_limit:
        conn.close()
        return {"error": f"Active roster is full ({roster_limit} players). Option or DFA someone first."}

    conn.execute("""
        UPDATE players SET roster_status='active', is_injured=0,
            injury_type=NULL, injury_days_remaining=0, il_tier=NULL
        WHERE id=?
    """, (player_id,))

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'il_activation', '{}', ?, ?)
    """, (game_date, player["team_id"], str(player_id)))

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id}
