"""
Front Office - Contract Logic
Arbitration, extensions, buyouts, option years.
"""
import json
import random
from ..database.db import get_connection, query


def process_arbitration(season: int, db_path: str = None) -> list:
    """Process arbitration-eligible players during offseason.

    Applies difficulty modifiers to arb salary:
    - Mogul difficulty: Arb salaries +10% higher
    """
    conn = get_connection(db_path)
    results = []

    # Get difficulty setting
    game_state_result = query("SELECT difficulty FROM game_state WHERE id=1", db_path=db_path)
    difficulty = game_state_result[0]["difficulty"] if game_state_result else "manager"

    # Salary modifiers by difficulty
    arb_salary_mods = {
        "fan": 0.95,        # -5% arb salaries
        "coach": 1.0,       # baseline
        "manager": 1.0,     # baseline
        "mogul": 1.10,      # +10% arb salaries
    }
    salary_mod = arb_salary_mods.get(difficulty, 1.0)

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
        new_salary = int(base * service_mult * salary_mod)

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
    """Process expiring contracts at end of season, handling options."""
    conn = get_connection(db_path)
    expired = []

    expiring = conn.execute("""
        SELECT p.*, c.id as contract_id, c.annual_salary, c.opt_out_year,
               c.team_option_year, c.player_option_year, c.years_remaining,
               c.total_years, c.vesting_option_json, c.incentives_json
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        WHERE c.years_remaining <= 1
        AND p.roster_status != 'retired'
    """).fetchall()

    for p in expiring:
        years_to_decrement = 1
        contract_id = p["contract_id"]
        current_year_remaining = p["years_remaining"]
        total_years = p["total_years"]
        years_elapsed = total_years - current_year_remaining

        # Check for player opt-out (executed by player)
        if p["player_option_year"] and p["player_option_year"] == years_elapsed:
            # Player opts out, becomes free agent
            conn.execute("UPDATE contracts SET years_remaining=0 WHERE id=?",
                        (contract_id,))
            conn.execute("UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
                        (p["id"],))
            expired.append({
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "status": "free_agent (player opted out)",
            })
            continue

        # Check for team option (team decides)
        if p["team_option_year"] and p["team_option_year"] == years_elapsed:
            # Team exercises or declines (simplified: always exercises)
            conn.execute("UPDATE contracts SET years_remaining=? WHERE id=?",
                        (1, contract_id))
            expired.append({
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "status": "team option exercised",
            })
            continue

        # Check for opt-out clause (mutual option, player can opt)
        if p["opt_out_year"] and p["opt_out_year"] == years_elapsed:
            # 20% chance player opts out (simplified)
            if random.random() < 0.20:
                conn.execute("UPDATE contracts SET years_remaining=0 WHERE id=?",
                            (contract_id,))
                conn.execute("UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
                            (p["id"],))
                expired.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "status": "free_agent (opted out)",
                })
                continue

        # Normal contract expiration
        conn.execute("UPDATE contracts SET years_remaining = years_remaining - 1 WHERE id=?",
                    (contract_id,))

        # If now at 0, player becomes free agent (if 6+ service years)
        if current_year_remaining - years_to_decrement <= 0 and p["service_years"] >= 6:
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


def process_vesting_options(season: int, db_path: str = None) -> list:
    """Check vesting options on contracts based on performance conditions.

    Vesting options vest if the player meets the specified condition during the
    vesting year. If vested, the contract extends 1 year at the option salary.
    """
    conn = get_connection(db_path)
    results = []

    # Find contracts with vesting options
    vesting = conn.execute("""
        SELECT p.*, c.id as contract_id, c.annual_salary, c.vesting_option_json,
               c.years_remaining, c.total_years, t.id as team_id
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        JOIN teams t ON t.id = p.team_id
        WHERE c.vesting_option_json IS NOT NULL
    """).fetchall()

    for contract in vesting:
        try:
            vesting_data = json.loads(contract["vesting_option_json"])
        except (json.JSONDecodeError, TypeError):
            continue

        vesting_year = vesting_data.get("year")
        condition_type = vesting_data.get("type")
        option_salary = vesting_data.get("salary")

        if vesting_year is None or condition_type is None:
            continue

        # Calculate years elapsed
        total_years = contract["total_years"]
        years_elapsed = total_years - contract["years_remaining"]

        # Check if this is the vesting year
        if years_elapsed == vesting_year:
            # Check if condition is met during this season
            condition_met = _check_vesting_condition(
                contract["id"], condition_type, season, conn
            )

            if condition_met:
                # Option vests: extend contract 1 year at option salary
                new_years_remaining = contract["years_remaining"] + 1
                conn.execute(
                    "UPDATE contracts SET annual_salary=?, years_remaining=?, total_years=? WHERE id=?",
                    (option_salary, new_years_remaining, total_years + 1, contract["contract_id"])
                )

                # Send notification if on user's team
                state_result = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
                user_team_id = state_result["user_team_id"] if state_result else None
                if contract["team_id"] == user_team_id:
                    from .messages import send_vesting_notification
                    player_name = f"{contract['first_name']} {contract['last_name']}"
                    send_vesting_notification(user_team_id, player_name, condition_type, option_salary, db_path=db_path)

                results.append({
                    "player_id": contract["id"],
                    "name": f"{contract['first_name']} {contract['last_name']}",
                    "vesting_condition": condition_type,
                    "new_salary": option_salary,
                    "vested": True,
                })
            else:
                # Option did not vest - no change to contract
                results.append({
                    "player_id": contract["id"],
                    "name": f"{contract['first_name']} {contract['last_name']}",
                    "vesting_condition": condition_type,
                    "vested": False,
                })

    conn.commit()
    conn.close()
    return results


def _check_vesting_condition(player_id: int, condition: str, season: int,
                            conn) -> bool:
    """Evaluate a vesting condition for a player.

    Checks if the player met the specified performance condition during the season.
    """
    if condition == "500_pa":
        # Check if player had 500+ plate appearances this season
        stats = conn.execute("""
            SELECT pa FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats and stats["pa"] >= 500
    elif condition == "150_games":
        # Check if player played 150+ games
        stats = conn.execute("""
            SELECT games FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats and stats["games"] >= 150
    elif condition == "50_starts" or condition == "50_gs":
        # For pitchers: 50+ starts
        stats = conn.execute("""
            SELECT games_started FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats and stats["games_started"] >= 50
    return False


def process_incentive_bonuses(season: int, db_path: str = None) -> list:
    """Calculate and pay out incentive bonuses based on performance achievements."""
    conn = get_connection(db_path)
    results = []

    # Find contracts with incentives
    contracts = conn.execute("""
        SELECT p.*, c.id as contract_id, c.incentives_json,
               t.id as team_id, t.cash
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        JOIN teams t ON t.id = p.team_id
        WHERE c.incentives_json IS NOT NULL
    """).fetchall()

    for contract in contracts:
        try:
            incentives = json.loads(contract["incentives_json"])
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(incentives, list):
            continue

        total_bonus = 0
        earned_bonuses = []

        for incentive in incentives:
            bonus_type = incentive.get("type")
            bonus_amount = incentive.get("bonus", 0)

            earned = _check_incentive_condition(
                contract["id"], bonus_type, season, conn
            )

            if earned:
                total_bonus += bonus_amount
                earned_bonuses.append(bonus_type)

        if total_bonus > 0:
            # Deduct from team cash
            conn.execute(
                "UPDATE teams SET cash = cash - ? WHERE id=?",
                (total_bonus, contract["team_id"])
            )
            results.append({
                "player_id": contract["id"],
                "name": f"{contract['first_name']} {contract['last_name']}",
                "bonus_amount": total_bonus,
                "earned_bonuses": earned_bonuses,
            })

    conn.commit()
    conn.close()
    return results


def _check_incentive_condition(player_id: int, bonus_type: str, season: int,
                              conn) -> bool:
    """Evaluate an incentive condition based on actual season performance.

    Incentive types:
    - all_star: Top 3 position players per position by overall rating
    - mvp_top5: Top 5 position players by (HR + RBI + runs)
    - games_150: 150+ games played
    - cy_young_top3: Top 3 pitchers by (wins - losses + saves)
    """
    if bonus_type == "all_star":
        # Get player info
        player = conn.execute("""
            SELECT p.position, p.contact_rating, p.power_rating, p.speed_rating,
                   p.fielding_rating
            FROM players p WHERE p.id=?
        """, (player_id,)).fetchone()

        if not player or player["position"] in ("SP", "RP"):
            return False

        # Get position and calculate overall rating
        position = player["position"]
        overall = (player["contact_rating"] * 1.5 + player["power_rating"] * 1.5 +
                  player["speed_rating"] * 0.5 + player["fielding_rating"] * 0.5) / 4

        # Find top 3 at this position (by overall rating)
        top_players = conn.execute("""
            SELECT p.id,
                   (p.contact_rating * 1.5 + p.power_rating * 1.5 +
                    p.speed_rating * 0.5 + p.fielding_rating * 0.5) / 4 as overall
            FROM players p
            WHERE p.position=? AND p.roster_status='active'
            ORDER BY overall DESC
            LIMIT 3
        """, (position,)).fetchall()

        # Check if this player is in top 3
        return any(p["id"] == player_id for p in top_players)

    elif bonus_type == "mvp_top5":
        # Get player's season stats (HR + RBI + runs)
        stats = conn.execute("""
            SELECT hr, rbi, runs FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()

        if not stats:
            return False

        player_score = (stats["hr"] or 0) + (stats["rbi"] or 0) + (stats["runs"] or 0)

        # Get top 5 position players by same metric
        top_players = conn.execute("""
            SELECT SUM(bs.hr) + SUM(bs.rbi) + SUM(bs.runs) as total_score
            FROM batting_stats bs
            JOIN players p ON p.id = bs.player_id
            WHERE bs.season=? AND bs.level='MLB'
            AND p.position NOT IN ('SP', 'RP')
            GROUP BY bs.player_id
            ORDER BY total_score DESC
            LIMIT 5
        """, (season,)).fetchall()

        if not top_players:
            return False

        # Check if player_score is >= 5th place score
        min_score = top_players[-1]["total_score"] if top_players else 0
        return player_score >= min_score

    elif bonus_type == "games_150":
        # 150+ games played
        stats = conn.execute("""
            SELECT games FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats and stats["games"] >= 150

    elif bonus_type == "cy_young_top3":
        # Get pitcher's season stats (wins - losses + saves)
        stats = conn.execute("""
            SELECT wins, losses, saves FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()

        if not stats:
            return False

        pitcher_score = (stats["wins"] or 0) - (stats["losses"] or 0) + (stats["saves"] or 0)

        # Get top 3 pitchers by same metric
        top_pitchers = conn.execute("""
            SELECT ps.player_id,
                   SUM(ps.wins) - SUM(ps.losses) + SUM(ps.saves) as total_score
            FROM pitching_stats ps
            WHERE ps.season=? AND ps.level='MLB'
            GROUP BY ps.player_id
            ORDER BY total_score DESC
            LIMIT 3
        """, (season,)).fetchall()

        if not top_pitchers:
            return False

        # Check if pitcher_score is >= 3rd place score
        min_score = top_pitchers[-1]["total_score"] if len(top_pitchers) >= 3 else top_pitchers[0]["total_score"]
        return pitcher_score >= min_score

    return False


def determine_arb_eligibility(season: int, db_path: str = None) -> list:
    """Determine Super 2 and arbitration eligibility for all players."""
    conn = get_connection(db_path)
    updates = []

    # Find players with 2+ but <3 service years
    candidates = conn.execute("""
        SELECT p.id, p.service_years, p.first_name, p.last_name,
               (p.contact_rating + p.power_rating + p.speed_rating +
                p.fielding_rating) / 4.0 as overall
        FROM players p
        WHERE p.service_years >= 2 AND p.service_years < 3
        AND p.roster_status = 'active'
        ORDER BY p.service_years DESC, overall DESC
    """).fetchall()

    if not candidates:
        conn.close()
        return updates

    # Top 22% get an extra year of arbitration (Super 2)
    super_2_count = max(1, len(candidates) // 5)  # ~20% = top 1 in 5
    super_2_players = candidates[:super_2_count]

    for player in super_2_players:
        conn.execute("""
            UPDATE contracts SET is_arb_eligible=1
            WHERE player_id=?
        """, (player["id"],))
        updates.append({
            "player_id": player["id"],
            "name": f"{player['first_name']} {player['last_name']}",
            "status": "super_2_eligible",
        })

    # Regular arb eligibility: 3-6 service years
    arb_eligible = conn.execute("""
        SELECT p.id, p.first_name, p.last_name
        FROM players p
        WHERE p.service_years >= 3 AND p.service_years < 6
        AND p.roster_status = 'active'
    """).fetchall()

    for player in arb_eligible:
        conn.execute("""
            UPDATE contracts SET is_arb_eligible=1
            WHERE player_id=? AND is_arb_eligible=0
        """, (player["id"],))
        updates.append({
            "player_id": player["id"],
            "name": f"{player['first_name']} {player['last_name']}",
            "status": "arb_eligible",
        })

    conn.commit()
    conn.close()
    return updates


def check_10_and_5_rights(player_id: int, db_path: str = None) -> bool:
    """
    Check if a player has 10-and-5 rights.
    Returns True if: 10+ years service AND 5+ years with current team.
    """
    player = query("""
        SELECT p.service_years, p.team_id,
               c.signed_date
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.id=?
    """, (player_id,), db_path=db_path)

    if not player:
        return False

    p = player[0]
    if p["service_years"] < 10:
        return False

    # Calculate years with current team
    if p["team_id"] and p["signed_date"]:
        from datetime import date
        signed = date.fromisoformat(p["signed_date"])
        years_with_team = (date.today() - signed).days / 365.25
        return years_with_team >= 5

    return False


def process_non_tender_decisions(season: int, db_path: str = None) -> list:
    """
    During offseason, AI teams decide whether to tender contracts to
    arbitration-eligible players. If projected arb salary > player value,
    non-tender them (they become free agents).
    """
    conn = get_connection(db_path)
    non_tendered = []

    arb_eligible = conn.execute("""
        SELECT p.*, c.id as contract_id, c.annual_salary,
               t.id as team_id, t.city, t.name as team_name
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        JOIN teams t ON t.id = p.team_id
        WHERE c.is_arb_eligible=1
        AND p.service_years >= 3 AND p.service_years < 6
        AND p.roster_status = 'active'
    """).fetchall()

    for p in arb_eligible:
        # Calculate projected arb salary
        is_pitcher = p["position"] in ("SP", "RP")
        if is_pitcher:
            overall = (p["stuff_rating"] * 2 + p["control_rating"] * 1.5) / 3.5
        else:
            overall = (p["contact_rating"] * 1.5 + p["power_rating"] * 1.5 +
                      p["speed_rating"] * 0.5 + p["fielding_rating"] * 0.5) / 4

        base = overall * 100000
        service_mult = 1.0 + (p["service_years"] - 3) * 0.3
        projected_arb_salary = int(base * service_mult)

        # Estimate player value based on age and ratings
        player_value = overall * 1000000
        age_factor = max(0.5, (35 - p["age"]) / 10.0)
        adjusted_value = player_value * age_factor

        # Decision: non-tender if arb salary > adjusted value
        if projected_arb_salary > adjusted_value and random.random() < 0.6:
            conn.execute("UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
                        (p["id"],))
            non_tendered.append({
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "team": f"{p['city']} {p['team_name']}",
                "projected_arb": projected_arb_salary,
                "player_value": adjusted_value,
            })

    conn.commit()
    conn.close()
    return non_tendered
