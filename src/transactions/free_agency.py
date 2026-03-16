"""
Front Office - Free Agency System
Handles free agent market, signings, and contract negotiations.
"""
import json
import random
from ..database.db import get_connection, query, execute


# In-memory tracking for best offers during offseason
# Structure: {player_id: {"team_id": int, "salary": int, "years": int, "date": str}}
_best_offers = {}


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
        best = _best_offers.get(p["id"])
        result.append({
            **p,
            "asking_salary": value["salary"],
            "asking_years": value["years"],
            "market_interest": value["interest"],
            "best_offer": best,
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

    # Check 40-man roster limit
    forty_man_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND on_forty_man=1
    """, (team_id,)).fetchone()["c"]

    if forty_man_count >= 40:
        conn.close()
        return {"error": "40-man roster is full (40 players). Remove someone from the 40-man first."}

    # Update player
    conn.execute("""
        UPDATE players SET team_id=?, roster_status='active', on_forty_man=1
        WHERE id=?
    """, (team_id, player_id))

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

    # Send notification if signing team is the user's team
    state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
    user_team_id = state["user_team_id"] if state else None
    if team_id == user_team_id:
        from .messages import send_free_agent_signing_message
        team = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()
        team_name = f"{team['city']} {team['name']}" if team else "Unknown"
        player_name = f"{player['first_name']} {player['last_name']}"
        send_free_agent_signing_message(user_team_id, player_name, team_name, salary, db_path=db_path)

    # Clear best offer tracking
    _best_offers.pop(player_id, None)

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id, "team_id": team_id,
            "salary": salary, "years": years}


def process_free_agency_day(game_date: str, offseason_day: int = 0,
                            db_path: str = None) -> list:
    """
    Process one day of AI free agency activity during offseason.
    AI teams evaluate free agents and make offers.
    Returns list of signings and offers made.
    """
    conn = get_connection(db_path)
    events = []

    state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
    user_team_id = state["user_team_id"] if state else None

    # Get all free agents
    free_agents = conn.execute("""
        SELECT p.* FROM players p
        WHERE p.roster_status = 'free_agent'
    """).fetchall()

    if not free_agents:
        conn.close()
        return events

    # Get AI teams with budget info
    teams = conn.execute("""
        SELECT t.id, t.cash, oc.budget_willingness
        FROM teams t
        LEFT JOIN owner_characters oc ON oc.team_id = t.id
        WHERE t.id != ?
    """, (user_team_id or -1,)).fetchall()

    for fa in free_agents:
        market_value = _calculate_market_value(dict(fa))
        asking_salary = market_value["salary"]

        # Apply asking price drops based on offseason duration
        if offseason_day > 60:
            asking_salary = int(asking_salary * 0.70)  # 30% total drop
        elif offseason_day > 30:
            asking_salary = int(asking_salary * 0.90)  # 10% drop

        for team in teams:
            # 5% daily chance per free agent per team
            if random.random() > 0.05:
                continue

            # Check 40-man space
            forty_man = conn.execute("""
                SELECT COUNT(*) as c FROM players
                WHERE team_id=? AND on_forty_man=1
            """, (team["id"],)).fetchone()["c"]

            if forty_man >= 40:
                continue

            # Check budget
            budget_mult = (team["budget_willingness"] or 50) / 100
            max_budget = int(team["cash"] * 0.15 * budget_mult)  # Max 15% of cash per signing

            if asking_salary > max_budget:
                continue

            # Check team need at this position
            from ..ai.gm_brain import _get_team_needs
            needs = _get_team_needs(team["id"], db_path)
            pos_strength = needs.get(fa["position"], 200)

            # More likely to sign if position is weak
            if pos_strength >= 200 and random.random() > 0.20:
                continue  # Skip strong positions most of the time

            # Calculate offer: 80-120% of asking based on need
            need_mult = 1.2 if pos_strength < 150 else 0.8 if pos_strength >= 200 else 1.0
            offer_salary = int(asking_salary * random.uniform(0.80, 1.20) * need_mult)
            offer_years = market_value["years"]

            # Compare to best existing offer
            current_best = _best_offers.get(fa["id"])
            if current_best and current_best["salary"] >= offer_salary:
                continue  # Don't beat existing offer

            # Update best offer
            _best_offers[fa["id"]] = {
                "team_id": team["id"],
                "salary": offer_salary,
                "years": offer_years,
                "date": game_date,
            }

            events.append({
                "type": "offer",
                "player_id": fa["id"],
                "player_name": f"{fa['first_name']} {fa['last_name']}",
                "team_id": team["id"],
                "salary": offer_salary,
                "years": offer_years,
            })

    # After offseason day 14, start signing players who have strong offers
    if offseason_day >= 14:
        for fa in free_agents:
            best = _best_offers.get(fa["id"])
            if not best:
                continue

            # Higher chance of signing as offseason progresses
            sign_chance = 0.05 + (offseason_day - 14) * 0.005  # Ramps up over time
            sign_chance = min(sign_chance, 0.30)

            if random.random() > sign_chance:
                continue

            # Execute the signing
            team_id = best["team_id"]

            # Re-check 40-man
            forty_man = conn.execute("""
                SELECT COUNT(*) as c FROM players
                WHERE team_id=? AND on_forty_man=1
            """, (team_id,)).fetchone()["c"]

            if forty_man >= 40:
                _best_offers.pop(fa["id"], None)
                continue

            conn.execute("""
                UPDATE players SET team_id=?, roster_status='active', on_forty_man=1
                WHERE id=?
            """, (team_id, fa["id"]))

            conn.execute("""
                INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
                    annual_salary, signed_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fa["id"], team_id, best["years"], best["years"],
                  best["salary"], game_date))

            conn.execute("""
                INSERT INTO transactions (transaction_date, transaction_type, details_json,
                    team1_id, player_ids)
                VALUES (?, 'free_agent_signing', ?, ?, ?)
            """, (game_date, json.dumps({"salary": best["salary"], "years": best["years"],
                                         "ai_initiated": True}),
                  team_id, str(fa["id"])))

            _best_offers.pop(fa["id"], None)

            events.append({
                "type": "signing",
                "player_id": fa["id"],
                "player_name": f"{fa['first_name']} {fa['last_name']}",
                "team_id": team_id,
                "salary": best["salary"],
                "years": best["years"],
            })

    conn.commit()
    conn.close()
    return events
