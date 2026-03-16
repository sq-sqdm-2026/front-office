"""
Front Office - Player Development System
Handles aging, development curves, and decline.

Development model:
- Young players (< peak_age) improve toward their potential ratings
- Players at peak maintain or slowly decline
- Players past peak decline, accelerating after 33-34
- Development rate affected by: work_ethic, farm_system_budget, coaching
- Not every player follows the same curve (randomness baked in)
"""
import random
from ..database.db import get_connection, query


def process_offseason_development(season: int, db_path: str = None) -> list:
    """
    Run player development for all players at end of season.
    Called during offseason processing.
    Returns list of notable development changes.
    """
    conn = get_connection(db_path)
    events = []

    players = conn.execute("""
        SELECT p.*, t.farm_system_budget
        FROM players p
        LEFT JOIN teams t ON t.id = p.team_id
        WHERE p.roster_status != 'retired' AND p.roster_status != 'free_agent'
    """).fetchall()

    for p in players:
        changes = _develop_player(dict(p), conn)
        if changes:
            events.append(changes)

    # Age all players by 1
    conn.execute("UPDATE players SET age = age + 1 WHERE roster_status != 'retired'")

    conn.commit()
    conn.close()
    return events


def _develop_player(p: dict, conn) -> dict:
    """Apply development/decline to a single player."""
    age = p["age"]
    peak = p["peak_age"]
    dev_rate = p["development_rate"]
    work_ethic = p["work_ethic"]
    is_pitcher = p["position"] in ("SP", "RP")

    # Farm system quality affects minor league development
    farm_budget = p.get("farm_system_budget", 10000000) or 10000000
    farm_mod = 0.8 + (farm_budget / 50000000)  # 0.8 to 1.2

    changes = {}

    if age < peak:
        # DEVELOPMENT PHASE: Move toward potential
        # Speed: work_ethic * dev_rate * farm_budget modifier
        # Each rating improves by 1-5 points per year (capped at potential)
        rate = (work_ethic / 50) * dev_rate * farm_mod
        if p["roster_status"] in ("minors_aaa", "minors_aa", "minors_low"):
            rate *= farm_mod  # farm budget matters more for minors

        ratings = _get_rating_fields(is_pitcher)
        for rating, potential in ratings:
            current = p[rating]
            pot = p[potential]
            if current < pot:
                improvement = int(random.uniform(1, 4) * rate)
                new_val = min(pot, current + improvement)
                if new_val != current:
                    conn.execute(f"UPDATE players SET {rating}=? WHERE id=?",
                                (new_val, p["id"]))
                    if new_val - current >= 3:
                        changes[rating] = (current, new_val)

    elif age <= peak + 2:
        # PEAK PHASE: Mostly stable, small random fluctuations
        ratings = _get_rating_fields(is_pitcher)
        for rating, _ in ratings:
            current = p[rating]
            delta = random.choice([-1, 0, 0, 0, 1])
            new_val = max(20, min(80, current + delta))
            if new_val != current:
                conn.execute(f"UPDATE players SET {rating}=? WHERE id=?",
                            (new_val, p["id"]))

    else:
        # DECLINE PHASE: Ratings drop, accelerating with age
        years_past_peak = age - peak
        decline_rate = 0.5 + years_past_peak * 0.3  # gets worse each year

        # Speed declines fastest
        speed_decline = int(decline_rate * random.uniform(1.5, 3.0))
        new_speed = max(20, p["speed_rating"] - speed_decline)
        if new_speed != p["speed_rating"]:
            conn.execute("UPDATE players SET speed_rating=? WHERE id=?",
                        (new_speed, p["id"]))
            if p["speed_rating"] - new_speed >= 3:
                changes["speed_rating"] = (p["speed_rating"], new_speed)

        # Other ratings decline more slowly
        ratings = _get_rating_fields(is_pitcher)
        for rating, _ in ratings:
            if rating == "speed_rating":
                continue
            current = p[rating]
            decline = int(decline_rate * random.uniform(0.5, 2.0))
            new_val = max(20, current - decline)
            if new_val != current:
                conn.execute(f"UPDATE players SET {rating}=? WHERE id=?",
                            (new_val, p["id"]))
                if current - new_val >= 3:
                    changes[rating] = (current, new_val)

        # Retirement check: if overall drops below threshold
        overall = _calc_overall(p, is_pitcher)
        if overall < 25 and age > 35:
            conn.execute("UPDATE players SET roster_status='retired' WHERE id=?",
                        (p["id"],))
            changes["retired"] = True

    if changes:
        return {
            "player_id": p["id"],
            "name": f"{p['first_name']} {p['last_name']}",
            "age": age,
            "changes": changes,
        }
    return None


def _get_rating_fields(is_pitcher: bool) -> list:
    """Get (rating, potential) field pairs."""
    if is_pitcher:
        return [
            ("stuff_rating", "stuff_potential"),
            ("control_rating", "control_potential"),
            ("stamina_rating", "stamina_potential"),
        ]
    return [
        ("contact_rating", "contact_potential"),
        ("power_rating", "power_potential"),
        ("speed_rating", "speed_potential"),
        ("fielding_rating", "fielding_potential"),
        ("arm_rating", "arm_potential"),
    ]


def _calc_overall(p: dict, is_pitcher: bool) -> float:
    if is_pitcher:
        return (p["stuff_rating"] * 2 + p["control_rating"] * 1.5 + p["stamina_rating"] * 0.5) / 4
    return (p["contact_rating"] * 1.5 + p["power_rating"] * 1.5 +
            p["speed_rating"] * 0.5 + p["fielding_rating"] * 0.5) / 4
