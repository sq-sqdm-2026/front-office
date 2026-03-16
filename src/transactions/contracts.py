"""
Front Office - Contract Logic
Arbitration, extensions, buyouts, option years.
"""
import json
import random
from ..database.db import get_connection, query


def process_arbitration(season: int, db_path: str = None) -> list:
    """Process arbitration-eligible players during offseason."""
    conn = get_connection(db_path)
    results = []

    # Find arb-eligible players (3-6 years service, no long-term deal)
    eligible = conn.execute("""
        SELECT p.*, c.id as contract_id, c.annual_salary, c.years_remaining,
               t.city, t.name as team_name
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        JOIN teams t ON t.id = p.team_id
        WHERE p.service_years >= 3 AND p.service_years < 6
        AND c.years_remaining <= 1
        AND p.roster_status != 'retired'
    """).fetchall()

    for p in eligible:
        # Calculate arb salary based on performance
        is_pitcher = p["position"] in ("SP", "RP")
        if is_pitcher:
            overall = (p["stuff_rating"] * 2 + p["control_rating"] * 1.5) / 3.5
        else:
            overall = (p["contact_rating"] * 1.5 + p["power_rating"] * 1.5 +
                       p["speed_rating"] * 0.5 + p["fielding_rating"] * 0.5) / 4

        # Arb salary: roughly based on overall and service years
        base = overall * 100000  # ~$5M for 50 overall
        service_mult = 1.0 + (p["service_years"] - 3) * 0.3
        new_salary = int(base * service_mult)

        # Update contract
        conn.execute("""
            UPDATE contracts SET annual_salary=?, years_remaining=1
            WHERE id=?
        """, (new_salary, p["contract_id"]))

        results.append({
            "player_id": p["id"],
            "name": f"{p['first_name']} {p['last_name']}",
            "team": f"{p['city']} {p['team_name']}",
            "old_salary": p["annual_salary"],
            "new_salary": new_salary,
        })

    conn.commit()
    conn.close()
    return results


def expire_contracts(season: int, db_path: str = None) -> list:
    """Process expiring contracts at end of season."""
    conn = get_connection(db_path)
    expired = []

    expiring = conn.execute("""
        SELECT p.*, c.id as contract_id, c.annual_salary
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        WHERE c.years_remaining <= 1
        AND p.roster_status != 'retired'
    """).fetchall()

    for p in expiring:
        # Decrement years remaining
        conn.execute("UPDATE contracts SET years_remaining = years_remaining - 1 WHERE id=?",
                    (p["contract_id"],))

        # If now at 0, player becomes free agent (if 6+ service years)
        if p["service_years"] >= 6:
            conn.execute("UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
                        (p["id"],))
            expired.append({
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "status": "free_agent",
            })

    # Update service time for all active players
    conn.execute("""
        UPDATE players SET service_years = service_years + 1.0
        WHERE roster_status = 'active' AND roster_status != 'retired'
    """)

    conn.commit()
    conn.close()
    return expired
