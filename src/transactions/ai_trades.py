"""
Front Office - AI-Initiated Trades
Daily automated trade logic for AI-controlled teams.
Pure algorithmic evaluation (no LLM calls) for batch processing speed.
"""
import json
import random
from ..database.db import get_connection, query, execute
from ..ai.gm_brain import _get_team_needs


def process_ai_trades(game_date: str, db_path: str = None) -> list:
    """
    Run daily AI trade logic. Each AI team has a small chance of proposing a trade.
    Returns list of executed trades (or user messages for user-team involvement).
    """
    conn = get_connection(db_path)
    executed_trades = []

    # Get user team to exclude from auto-execution
    state = conn.execute("SELECT user_team_id, season, current_date FROM game_state WHERE id=1").fetchone()
    user_team_id = state["user_team_id"] if state else None
    season = state["season"] if state else 2026

    # Check trade deadline
    from datetime import date
    current_date = date.fromisoformat(game_date)
    deadline = date(season, 7, 31)
    if current_date > deadline:
        conn.close()
        return executed_trades  # No AI trades after deadline

    # Get all AI teams
    teams = conn.execute("SELECT id FROM teams").fetchall()
    ai_team_ids = [t["id"] for t in teams if t["id"] != user_team_id]

    for team_id in ai_team_ids:
        # 2% daily chance of attempting a trade
        if random.random() > 0.02:
            continue

        # Get team needs
        needs = _get_team_needs(team_id, db_path)
        if not needs:
            continue

        # Find biggest positional need (lowest rated position)
        weakest_pos = min(needs, key=lambda p: needs[p])
        weakest_score = needs[weakest_pos]

        # Only pursue trades if there's a real weakness
        if weakest_score >= 180:
            continue

        # Scan other teams for available players at that position
        candidates = conn.execute("""
            SELECT p.*, c.annual_salary, c.years_remaining, c.no_trade_clause
            FROM players p
            LEFT JOIN contracts c ON c.player_id = p.id
            WHERE p.position = ? AND p.roster_status = 'active'
            AND p.team_id != ?
            AND COALESCE(c.no_trade_clause, 0) = 0
            ORDER BY CASE WHEN p.position IN ('SP','RP')
                THEN p.stuff_rating + p.control_rating + p.stamina_rating
                ELSE p.contact_rating + p.power_rating + p.speed_rating + p.fielding_rating
            END DESC
            LIMIT 10
        """, (weakest_pos, team_id)).fetchall()

        if not candidates:
            continue

        # Pick a reasonable target (not the absolute best, more realistic)
        target_idx = random.randint(0, min(4, len(candidates) - 1))
        target = candidates[target_idx]
        target_team_id = target["team_id"]

        # Calculate target value
        if target["position"] in ("SP", "RP"):
            target_value = (target["stuff_rating"] * 2 + target["control_rating"] * 1.5 +
                           target["stamina_rating"] * 0.5)
        else:
            target_value = (target["contact_rating"] * 1.5 + target["power_rating"] * 1.5 +
                           target["speed_rating"] * 0.5 + target["fielding_rating"] * 0.5)

        # Find players to offer from our roster (positions we're strong at)
        strongest_pos = max(needs, key=lambda p: needs[p])
        our_players = conn.execute("""
            SELECT p.*, c.annual_salary, c.years_remaining
            FROM players p
            LEFT JOIN contracts c ON c.player_id = p.id
            WHERE p.team_id = ? AND p.roster_status = 'active'
            AND p.position = ?
            ORDER BY CASE WHEN p.position IN ('SP','RP')
                THEN p.stuff_rating + p.control_rating + p.stamina_rating
                ELSE p.contact_rating + p.power_rating + p.speed_rating + p.fielding_rating
            END DESC
        """, (team_id, strongest_pos)).fetchall()

        if not our_players:
            continue

        # Find a package that roughly matches the target's value
        offered = []
        offered_value = 0
        for p in our_players:
            if p["position"] in ("SP", "RP"):
                pv = (p["stuff_rating"] * 2 + p["control_rating"] * 1.5 +
                      p["stamina_rating"] * 0.5)
            else:
                pv = (p["contact_rating"] * 1.5 + p["power_rating"] * 1.5 +
                      p["speed_rating"] * 0.5 + p["fielding_rating"] * 0.5)
            offered.append(p)
            offered_value += pv
            if offered_value >= target_value * 0.85:
                break

        if offered_value < target_value * 0.70:
            continue  # Can't make a fair offer

        # If target is on user's team, send a message instead of auto-executing
        if target_team_id == user_team_id:
            team_info = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()
            offered_names = ", ".join(f"{p['first_name']} {p['last_name']}" for p in offered)
            conn.execute("""
                INSERT INTO messages (game_date, sender_type, sender_name,
                    recipient_type, recipient_id, subject, body,
                    requires_response, response_options_json)
                VALUES (?, 'gm', ?, 'user', NULL, ?, ?, 1, ?)
            """, (
                game_date,
                f"{team_info['city']} {team_info['name']} GM",
                f"Trade Inquiry: {target['first_name']} {target['last_name']}",
                f"We're interested in acquiring {target['first_name']} {target['last_name']}. "
                f"We'd be willing to offer {offered_names} in return. What do you think?",
                json.dumps(["Accept", "Counter", "Decline"]),
            ))
            executed_trades.append({
                "type": "proposal_to_user",
                "proposing_team_id": team_id,
                "target_player": f"{target['first_name']} {target['last_name']}",
            })
            continue

        # Check if the other AI team would accept (simple value comparison)
        other_needs = _get_team_needs(target_team_id, db_path)
        other_pos = offered[0]["position"] if offered else None

        # Other team accepts if they get value at a position of need
        other_pos_strength = other_needs.get(other_pos, 200) if other_pos else 200
        value_ratio = offered_value / max(1, target_value)

        # Accept if fair value and fills a need
        accept = value_ratio >= 0.85 and other_pos_strength < 200

        if not accept:
            continue

        # Execute the trade
        offered_ids = [p["id"] for p in offered]
        requested_ids = [target["id"]]

        for pid in offered_ids:
            conn.execute("UPDATE players SET team_id=? WHERE id=?", (target_team_id, pid))
            conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?", (target_team_id, pid))

        for pid in requested_ids:
            conn.execute("UPDATE players SET team_id=? WHERE id=?", (team_id, pid))
            conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?", (team_id, pid))

        details = {
            "proposing_team": team_id,
            "receiving_team": target_team_id,
            "players_to_receiving": offered_ids,
            "players_to_proposing": requested_ids,
            "cash": 0,
            "ai_initiated": True,
        }
        conn.execute("""
            INSERT INTO transactions (transaction_date, transaction_type, details_json,
                team1_id, team2_id, player_ids)
            VALUES (?, 'trade', ?, ?, ?, ?)
        """, (game_date, json.dumps(details), team_id, target_team_id,
              ",".join(str(x) for x in offered_ids + requested_ids)))

        executed_trades.append({
            "type": "executed",
            "proposing_team_id": team_id,
            "receiving_team_id": target_team_id,
            "players_offered": offered_ids,
            "players_requested": requested_ids,
        })

    conn.commit()
    conn.close()
    return executed_trades
