"""
Front Office - Free Agency System
Handles free agent market, signings, and contract negotiations.
"""
import json
import random
from ..database.db import get_connection, query, execute


def get_free_agents(db_path: str = None) -> list:
    """Get all available free agents with their asking prices."""
    players = query("""
        SELECT p.*, c.annual_salary as last_salary
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.roster_status = 'free_agent'
        ORDER BY p.contact_rating + p.power_rating + p.stuff_rating DESC
    """, db_path=db_path)

    result = []
    for p in players:
        # Calculate asking price based on ratings and age
        value = _calculate_market_value(p)
        result.append({
            **p,
            "asking_salary": value["salary"],
            "asking_years": value["years"],
            "market_interest": value["interest"],
        })
    return result


def _calculate_market_value(player: dict) -> dict:
    """Estimate a player's market value for free agency."""
    is_pitcher = player["position"] in ("SP", "RP")

    if is_pitcher:
        overall = (player["stuff_rating"] * 2 + player["control_rating"] * 1.5 +
                   player["stamina_rating"] * 0.5) / 4
    else:
        overall = (player["contact_rating"] * 1.5 + player["power_rating"] * 1.5 +
                   player["speed_rating"] * 0.5 + player["fielding_rating"] * 0.5) / 4

    # Age depreciation
    age = player["age"]
    if age <= 28:
        age_mult = 1.1
    elif age <= 32:
        age_mult = 1.0
    elif age <= 35:
        age_mult = 0.75
    else:
        age_mult = 0.5

    # Base salary from overall rating
    if overall >= 70:
        base_salary = random.randint(20000000, 35000000)
        years = random.randint(4, 7)
    elif overall >= 60:
        base_salary = random.randint(10000000, 22000000)
        years = random.randint(3, 5)
    elif overall >= 50:
        base_salary = random.randint(3000000, 12000000)
        years = random.randint(2, 4)
    elif overall >= 40:
        base_salary = random.randint(1000000, 5000000)
        years = random.randint(1, 3)
    else:
        base_salary = random.randint(750000, 2000000)
        years = 1

    salary = int(base_salary * age_mult)
    years = max(1, int(years * age_mult))

    # Market interest (how many teams want this player)
    interest = max(1, min(15, int(overall / 5)))

    return {"salary": salary, "years": years, "interest": interest}


def sign_free_agent(player_id: int, team_id: int, salary: int, years: int,
                    db_path: str = None) -> dict:
    """Sign a free agent to a contract."""
    conn = get_connection(db_path)

    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}
    if player["roster_status"] != "free_agent":
        conn.close()
        return {"error": "Player is not a free agent"}

    # Check team can afford it
    team = conn.execute("SELECT cash FROM teams WHERE id=?", (team_id,)).fetchone()
    if not team:
        conn.close()
        return {"error": "Team not found"}

    # Update player
    conn.execute("UPDATE players SET team_id=?, roster_status='active' WHERE id=?",
                (team_id, player_id))

    # Create contract
    state = conn.execute("SELECT current_date FROM game_state WHERE id=1").fetchone()
    game_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
            annual_salary, signed_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (player_id, team_id, years, years, salary, game_date))

    # Log transaction
    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'free_agent_signing', ?, ?, ?)
    """, (game_date, json.dumps({"salary": salary, "years": years}),
          team_id, str(player_id)))

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id, "team_id": team_id,
            "salary": salary, "years": years}
