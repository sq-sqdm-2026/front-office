"""
Front Office - Contract Logic
Arbitration, extensions, buyouts, option years.
"""
import json
import random
from datetime import date
from ..database.db import get_connection, query


# ---------------------------------------------------------------------------
# WAR approximation helpers
# ---------------------------------------------------------------------------

def _calc_war_approx(player_row) -> float:
    """Estimate WAR from player ratings. Works with dict-like rows."""
    is_pitcher = player_row["position"] in ("SP", "RP")
    if is_pitcher:
        raw = (
            player_row["stuff_rating"] * 2
            + player_row["control_rating"] * 1.5
            + player_row["stamina_rating"] * 0.5
        ) / 4
    else:
        raw = (
            player_row["contact_rating"]
            + player_row["power_rating"]
            + player_row["speed_rating"]
            + player_row["fielding_rating"]
        ) / 4
    return max(0.0, (raw - 40) * 0.15)


def _war_to_salary(war: float) -> int:
    """Convert a WAR estimate to a dollar salary using tiered scale."""
    if war < 1:
        return int(1_000_000 + war * 2_000_000)
    elif war < 2:
        return int(3_000_000 + (war - 1) * 3_000_000)
    elif war < 3:
        return int(6_000_000 + (war - 2) * 4_000_000)
    elif war < 4:
        return int(10_000_000 + (war - 3) * 6_000_000)
    elif war < 5:
        return int(16_000_000 + (war - 4) * 6_000_000)
    else:
        return int(22_000_000 + (war - 5) * 4_000_000)


# ---------------------------------------------------------------------------
# 1. Comparables-based arbitration
# ---------------------------------------------------------------------------

def process_arbitration(season: int, db_path: str = None) -> list:
    """Process arbitration-eligible players during offseason.

    Uses a comparables-based system:
    1. Look for similar players (same position, +/-1 service year) who signed
       contracts recently.
    2. If no comparables, fall back to a WAR-approximation formula.
    3. Apply +/-15% negotiation randomness and difficulty modifier.
    """
    conn = get_connection(db_path)
    results = []

    # Get difficulty setting
    game_state_result = query("SELECT difficulty FROM game_state WHERE id=1", db_path=db_path)
    difficulty = game_state_result[0]["difficulty"] if game_state_result else "manager"

    arb_salary_mods = {
        "fan": 0.95,
        "coach": 1.0,
        "manager": 1.0,
        "mogul": 1.10,
    }
    salary_mod = arb_salary_mods.get(difficulty, 1.0)

    # Find arb-eligible players (3-6 years service, or Super 2 eligible)
    eligible = conn.execute("""
        SELECT p.*, c.id as contract_id, c.annual_salary, c.years_remaining,
               c.is_arb_eligible, t.city, t.name as team_name
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        JOIN teams t ON t.id = p.team_id
        WHERE ((p.service_years >= 3 AND p.service_years < 6)
               OR c.is_arb_eligible = 1)
        AND c.years_remaining <= 1
        AND p.roster_status != 'retired'
    """).fetchall()

    for p in eligible:
        # --- Step 1: try comparables ---
        comparable_salary = _find_comparable_salary(p, conn)

        if comparable_salary is not None:
            base_salary = comparable_salary
        else:
            # --- Step 2: WAR-approximation fallback ---
            war = _calc_war_approx(p)
            base_salary = _war_to_salary(war)

        # Service-year bump (arb years 1-3 get progressive raises)
        service_years = p["service_years"]
        if service_years < 3:
            # Super 2: smaller bump
            service_mult = 0.8
        elif service_years < 4:
            service_mult = 1.0
        elif service_years < 5:
            service_mult = 1.15
        else:
            service_mult = 1.30

        # Negotiation randomness +/- 15%
        negotiation_factor = 1.0 + random.uniform(-0.15, 0.15)

        new_salary = int(base_salary * service_mult * salary_mod * negotiation_factor)
        new_salary = max(750_000, new_salary)  # league minimum floor

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
            "method": "comparables" if comparable_salary is not None else "war_approx",
        })

    conn.commit()
    conn.close()
    return results


def _find_comparable_salary(player_row, conn):
    """Find comparable contracts: same position, similar service time (+-1yr).

    Returns the average salary of comparables, or None if none found.
    """
    position = player_row["position"]
    service = player_row["service_years"]

    comps = conn.execute("""
        SELECT c.annual_salary
        FROM contracts c
        JOIN players p ON p.id = c.player_id
        WHERE p.position = ?
        AND p.service_years BETWEEN ? AND ?
        AND c.player_id != ?
        AND c.signed_date IS NOT NULL
        ORDER BY c.signed_date DESC
        LIMIT 10
    """, (position, service - 1, service + 1, player_row["id"])).fetchall()

    if not comps:
        return None

    avg_salary = sum(c["annual_salary"] for c in comps) // len(comps)
    return avg_salary


# ---------------------------------------------------------------------------
# 1b. Contract Extensions
# ---------------------------------------------------------------------------

def offer_extension(player_id: int, years: int, annual_salary: int,
                    db_path: str = None) -> dict:
    """Offer a contract extension to a player on the user's team.
    Player accepts based on: fair value, years remaining, age, personality.
    Returns {accepted, message, details}.
    """
    conn = get_connection(db_path)

    player = conn.execute("""
        SELECT p.*, c.annual_salary as current_salary, c.years_remaining
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.id=?
    """, (player_id,)).fetchone()

    if not player:
        conn.close()
        return {"accepted": False, "message": "Player not found"}

    player = dict(player)
    war = _calc_war_approx(player)
    fair_salary = _war_to_salary(war)
    age = player["age"]
    greed = player.get("greed", 50) or 50
    loyalty = player.get("loyalty", 50) or 50
    current_salary = player.get("current_salary") or 720_000
    years_left = player.get("years_remaining") or 0

    # --- Acceptance logic ---
    # Players want: fair value, security (years), and may have personality preferences
    salary_ratio = annual_salary / max(1, fair_salary)
    accept_score = 0

    # Salary fairness (biggest factor)
    if salary_ratio >= 1.15:
        accept_score += 40  # Overpay
    elif salary_ratio >= 1.0:
        accept_score += 30
    elif salary_ratio >= 0.85:
        accept_score += 15
    elif salary_ratio >= 0.70:
        accept_score += 5
    else:
        accept_score -= 20  # Lowball

    # Years offered (security)
    if years >= 4:
        accept_score += 15
    elif years >= 3:
        accept_score += 10
    elif years >= 2:
        accept_score += 5

    # Greed: high greed wants more money
    accept_score -= (greed - 50) * 0.3

    # Loyalty: loyal players more likely to accept
    accept_score += (loyalty - 50) * 0.2

    # Age: older players want security
    if age >= 32:
        accept_score += 10
    elif age >= 29:
        accept_score += 5

    # Already under contract with years left → harder to get them to extend
    if years_left >= 3:
        accept_score -= 15  # No urgency
    elif years_left >= 2:
        accept_score -= 5

    # Raise vs current salary
    if annual_salary > current_salary * 1.2:
        accept_score += 10  # Significant raise

    # Acceptance threshold: 50+
    accepted = accept_score >= 50 or (accept_score >= 35 and random.random() < 0.5)

    if accepted:
        # Update contract
        conn.execute("""
            UPDATE contracts SET annual_salary=?, years_remaining=?, total_years=?
            WHERE player_id=?
        """, (annual_salary, years, years, player_id))

        # Log transaction
        conn.execute("""
            INSERT INTO transactions (team_id, transaction_type, player_id, details, transaction_date)
            VALUES (?, 'extension', ?, ?, ?)
        """, (player["team_id"], player_id,
              json.dumps({"years": years, "salary": annual_salary, "fair_value": fair_salary}),
              date.today().isoformat()))

        conn.commit()
        conn.close()
        return {
            "accepted": True,
            "message": f"{player['first_name']} {player['last_name']} accepted a {years}-year, ${annual_salary/1e6:.1f}M/yr extension!",
            "details": {"years": years, "salary": annual_salary}
        }
    else:
        conn.close()
        reason = "wants more money" if salary_ratio < 0.9 else "not interested right now" if years_left >= 3 else "wants to test free agency"
        return {
            "accepted": False,
            "message": f"{player['first_name']} {player['last_name']} declined — {reason}.",
            "fair_salary": fair_salary,
            "accept_score": accept_score,
        }


# ---------------------------------------------------------------------------
# 2. Team / Player option logic
# ---------------------------------------------------------------------------

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

        # ---- Player option ----
        if p["player_option_year"] and p["player_option_year"] == years_elapsed:
            # Player opts out if market value > remaining value, stays if
            # declining or older than 33.
            war = _calc_war_approx(p)
            market_value = _war_to_salary(war)
            remaining_value = p["annual_salary"] * current_year_remaining
            age = p["age"]

            if age <= 33 and market_value > remaining_value:
                # Player opts out
                conn.execute("UPDATE contracts SET years_remaining=0 WHERE id=?",
                             (contract_id,))
                conn.execute(
                    "UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
                    (p["id"],))
                expired.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "status": "free_agent (player opted out)",
                })
            else:
                # Player stays
                conn.execute(
                    "UPDATE contracts SET years_remaining = years_remaining - 1 WHERE id=?",
                    (contract_id,))
                expired.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "status": "player option - stayed",
                })
            continue

        # ---- Team option ----
        if p["team_option_year"] and p["team_option_year"] == years_elapsed:
            war = _calc_war_approx(p)
            projected_value = war * 8_000_000
            option_salary = p["annual_salary"]
            peak_age = p["peak_age"]
            age = p["age"]
            is_declining = age > peak_age + 3

            if projected_value > option_salary:
                # Exercise: player is worth more than the option costs
                conn.execute("UPDATE contracts SET years_remaining=? WHERE id=?",
                             (1, contract_id))
                expired.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "status": "team option exercised",
                })
            elif is_declining and option_salary > projected_value * 1.2:
                # Decline: player is declining and option is overpriced
                # Pay buyout (10% of option salary, standard buyout)
                buyout = option_salary // 10
                conn.execute("UPDATE teams SET cash = cash - ? WHERE id=?",
                             (buyout, p["team_id"]))
                conn.execute("UPDATE contracts SET years_remaining=0 WHERE id=?",
                             (contract_id,))
                conn.execute(
                    "UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
                    (p["id"],))
                expired.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "status": f"team option declined (buyout: ${buyout:,})",
                })
            else:
                # Borderline: exercise
                conn.execute("UPDATE contracts SET years_remaining=? WHERE id=?",
                             (1, contract_id))
                expired.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "status": "team option exercised",
                })
            continue

        # ---- Opt-out clause (mutual) ----
        if p["opt_out_year"] and p["opt_out_year"] == years_elapsed:
            war = _calc_war_approx(p)
            market_value = _war_to_salary(war)
            remaining_value = p["annual_salary"] * current_year_remaining
            age = p["age"]

            if age <= 33 and market_value > remaining_value:
                conn.execute("UPDATE contracts SET years_remaining=0 WHERE id=?",
                             (contract_id,))
                conn.execute(
                    "UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
                    (p["id"],))
                expired.append({
                    "player_id": p["id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "status": "free_agent (opted out)",
                })
                continue

        # ---- Normal contract expiration ----
        conn.execute(
            "UPDATE contracts SET years_remaining = years_remaining - 1 WHERE id=?",
            (contract_id,))

        if current_year_remaining - years_to_decrement <= 0 and p["service_years"] >= 6:
            conn.execute(
                "UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
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


# ---------------------------------------------------------------------------
# Vesting options (unchanged)
# ---------------------------------------------------------------------------

def process_vesting_options(season: int, db_path: str = None) -> list:
    """Check vesting options on contracts based on performance conditions.

    Vesting options vest if the player meets the specified condition during the
    vesting year. If vested, the contract extends 1 year at the option salary.
    """
    conn = get_connection(db_path)
    results = []

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

        total_years = contract["total_years"]
        years_elapsed = total_years - contract["years_remaining"]

        if years_elapsed == vesting_year:
            condition_met = _check_vesting_condition(
                contract["id"], condition_type, season, conn
            )

            if condition_met:
                new_years_remaining = contract["years_remaining"] + 1
                conn.execute(
                    "UPDATE contracts SET annual_salary=?, years_remaining=?, total_years=? WHERE id=?",
                    (option_salary, new_years_remaining, total_years + 1, contract["contract_id"])
                )

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
    """Evaluate a vesting condition for a player."""
    if condition == "500_pa":
        stats = conn.execute("""
            SELECT pa FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats and stats["pa"] >= 500
    elif condition == "150_games":
        stats = conn.execute("""
            SELECT games FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats and stats["games"] >= 150
    elif condition == "50_starts" or condition == "50_gs":
        stats = conn.execute("""
            SELECT games_started FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats and stats["games_started"] >= 50
    return False


# ---------------------------------------------------------------------------
# 5. Incentive bonus processing (with stat checks)
# ---------------------------------------------------------------------------

def process_incentive_bonuses(season: int, db_path: str = None) -> list:
    """Calculate and pay out incentive bonuses based on performance achievements.

    Checks actual batting/pitching stats against thresholds:
    - Batting: 500+ PA, .300+ AVG, 30+ HR, 100+ RBI, 200+ hits
    - Pitching: 200+ IP, sub-3.00 ERA, 15+ wins, 200+ SO
    Also handles the legacy incentive types (all_star, mvp_top5, etc.).
    """
    conn = get_connection(db_path)
    results = []

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

            if not bonus_type or not bonus_amount:
                continue

            earned = _check_incentive_condition(
                contract["id"], bonus_type, season, conn
            )

            if earned:
                total_bonus += bonus_amount
                earned_bonuses.append(bonus_type)

        if total_bonus > 0:
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

    Supported types:
    - Batting thresholds: 500_pa, batting_avg_300, hr_30, rbi_100, hits_200
    - Pitching thresholds: ip_200, era_300, wins_15, so_200
    - Legacy award proxies: all_star, mvp_top5, games_150, cy_young_top3
    """
    # ---- Batting stat thresholds ----
    if bonus_type == "500_pa":
        stats = conn.execute("""
            SELECT pa FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats is not None and (stats["pa"] or 0) >= 500

    elif bonus_type == "batting_avg_300":
        stats = conn.execute("""
            SELECT hits, ab FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        if not stats or not stats["ab"] or stats["ab"] < 100:
            return False
        avg = (stats["hits"] or 0) / stats["ab"]
        return avg >= 0.300

    elif bonus_type == "hr_30":
        stats = conn.execute("""
            SELECT hr FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats is not None and (stats["hr"] or 0) >= 30

    elif bonus_type == "rbi_100":
        stats = conn.execute("""
            SELECT rbi FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats is not None and (stats["rbi"] or 0) >= 100

    elif bonus_type == "hits_200":
        stats = conn.execute("""
            SELECT hits FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats is not None and (stats["hits"] or 0) >= 200

    # ---- Pitching stat thresholds ----
    elif bonus_type == "ip_200":
        stats = conn.execute("""
            SELECT ip_outs FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        if not stats:
            return False
        ip = (stats["ip_outs"] or 0) / 3.0
        return ip >= 200.0

    elif bonus_type == "era_300":
        stats = conn.execute("""
            SELECT er, ip_outs FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        if not stats or not stats["ip_outs"] or stats["ip_outs"] < 30:
            return False
        ip = stats["ip_outs"] / 3.0
        era = (stats["er"] or 0) * 9.0 / ip
        return era < 3.00

    elif bonus_type == "wins_15":
        stats = conn.execute("""
            SELECT wins FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats is not None and (stats["wins"] or 0) >= 15

    elif bonus_type == "so_200":
        stats = conn.execute("""
            SELECT so FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats is not None and (stats["so"] or 0) >= 200

    # ---- Legacy award-proxy types ----
    elif bonus_type == "all_star":
        player = conn.execute("""
            SELECT p.position, p.contact_rating, p.power_rating, p.speed_rating,
                   p.fielding_rating
            FROM players p WHERE p.id=?
        """, (player_id,)).fetchone()

        if not player or player["position"] in ("SP", "RP"):
            return False

        position = player["position"]
        top_players = conn.execute("""
            SELECT p.id,
                   (p.contact_rating * 1.5 + p.power_rating * 1.5 +
                    p.speed_rating * 0.5 + p.fielding_rating * 0.5) / 4 as overall
            FROM players p
            WHERE p.position=? AND p.roster_status='active'
            ORDER BY overall DESC
            LIMIT 3
        """, (position,)).fetchall()

        return any(p["id"] == player_id for p in top_players)

    elif bonus_type == "mvp_top5":
        stats = conn.execute("""
            SELECT hr, rbi, runs FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()

        if not stats:
            return False

        player_score = (stats["hr"] or 0) + (stats["rbi"] or 0) + (stats["runs"] or 0)

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
        min_score = top_players[-1]["total_score"] if top_players else 0
        return player_score >= min_score

    elif bonus_type == "games_150":
        stats = conn.execute("""
            SELECT games FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()
        return stats is not None and (stats["games"] or 0) >= 150

    elif bonus_type == "cy_young_top3":
        stats = conn.execute("""
            SELECT wins, losses, saves FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season)).fetchone()

        if not stats:
            return False

        pitcher_score = (stats["wins"] or 0) - (stats["losses"] or 0) + (stats["saves"] or 0)

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
        min_score = top_pitchers[-1]["total_score"] if len(top_pitchers) >= 3 else top_pitchers[0]["total_score"]
        return pitcher_score >= min_score

    return False


# ---------------------------------------------------------------------------
# Super 2 / arb eligibility
# ---------------------------------------------------------------------------

def determine_arb_eligibility(season: int, db_path: str = None) -> list:
    """Determine Super 2 and arbitration eligibility for all players.

    Super Two: players with 2+ but <3 service years AND in the top 22% of
    service time among that cohort become arb-eligible early.
    """
    conn = get_connection(db_path)
    updates = []

    # Super 2 candidates: 2+ but <3 service years, sorted by service time desc
    candidates = conn.execute("""
        SELECT p.id, p.service_years, p.first_name, p.last_name,
               (p.contact_rating + p.power_rating + p.speed_rating +
                p.fielding_rating) / 4.0 as overall
        FROM players p
        WHERE p.service_years >= 2 AND p.service_years < 3
        AND p.roster_status = 'active'
        ORDER BY p.service_years DESC, overall DESC
    """).fetchall()

    if candidates:
        # Top 22% by service time get Super 2 status
        super_2_count = max(1, int(len(candidates) * 0.22))
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


# ---------------------------------------------------------------------------
# 4. 10-and-5 rights
# ---------------------------------------------------------------------------

def check_10_and_5_rights(player_id: int, db_path: str = None) -> bool:
    """Check if a player has 10-and-5 rights.

    Returns True if the player has 10+ MLB service years AND has been with
    their current team for 5+ consecutive years. This gives full no-trade
    protection.
    """
    player = query("""
        SELECT p.service_years, p.team_id, c.signed_date
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.id=?
    """, (player_id,), db_path=db_path)

    if not player:
        return False

    p = player[0]

    # Need 10+ service years
    if p["service_years"] < 10:
        return False

    # Need to be on a team
    if not p["team_id"]:
        return False

    # Check years with current team via game_state season context
    if p["signed_date"]:
        try:
            signed = date.fromisoformat(p["signed_date"])
        except (ValueError, TypeError):
            return False

        # Use game_state current_date for in-game time rather than real date
        game_state = query(
            "SELECT current_date FROM game_state WHERE id=1", db_path=db_path
        )
        if game_state and game_state[0]["current_date"]:
            try:
                current = date.fromisoformat(game_state[0]["current_date"])
            except (ValueError, TypeError):
                current = date.today()
        else:
            current = date.today()

        years_with_team = (current - signed).days / 365.25
        return years_with_team >= 5

    return False


# ---------------------------------------------------------------------------
# 3. No-trade clause checking (modified / limited / full)
# ---------------------------------------------------------------------------

def check_no_trade_clause(player_id: int, destination_team_id: int = None,
                          is_ai_trade: bool = False,
                          db_path: str = None) -> dict:
    """Evaluate whether a no-trade clause blocks a trade.

    Schema uses no_trade_clause column: 0=none, 1=full, 2=partial.

    Returns dict with:
      - blocked (bool): whether the trade is blocked
      - ntc_type: "none", "full", "modified", "limited"
      - reason: human-readable explanation
    """
    contract = query(
        "SELECT no_trade_clause FROM contracts WHERE player_id=?",
        (player_id,), db_path=db_path
    )

    if not contract:
        return {"blocked": False, "ntc_type": "none", "reason": "No contract found"}

    ntc_value = contract[0]["no_trade_clause"]

    if ntc_value == 0:
        return {"blocked": False, "ntc_type": "none", "reason": "No NTC"}

    # Also check 10-and-5 rights (grants full NTC automatically)
    has_10_and_5 = check_10_and_5_rights(player_id, db_path)
    if has_10_and_5:
        if is_ai_trade:
            # 10% chance player consents if going to a contender
            # (simplified: random since we don't know contender status here)
            if random.random() < 0.10:
                return {
                    "blocked": False,
                    "ntc_type": "full_10_and_5",
                    "reason": "Player consented to trade (10-and-5 rights waived)",
                }
        return {
            "blocked": True,
            "ntc_type": "full_10_and_5",
            "reason": "Player has 10-and-5 rights (full no-trade protection)",
        }

    if ntc_value == 1:
        # Full NTC: blocks all trades
        if is_ai_trade:
            # 10% chance player consents if going to a contender
            if random.random() < 0.10:
                return {
                    "blocked": False,
                    "ntc_type": "full",
                    "reason": "Player consented to waive full NTC",
                }
        return {
            "blocked": True,
            "ntc_type": "full",
            "reason": "Player has a full no-trade clause",
        }

    elif ntc_value == 2:
        # Partial NTC: modified (blocks up to 10 teams) or limited (up to 5)
        # For AI trades: 20% chance the player blocks trade to any given team
        if is_ai_trade:
            if random.random() < 0.20:
                return {
                    "blocked": True,
                    "ntc_type": "modified",
                    "reason": "Player exercised modified no-trade clause to block this trade",
                }
            return {
                "blocked": False,
                "ntc_type": "modified",
                "reason": "Player allowed trade (modified NTC did not block)",
            }
        # For user trades: flag it but don't auto-block
        return {
            "blocked": False,
            "ntc_type": "modified",
            "reason": "Player has a modified no-trade clause (may block)",
        }

    return {"blocked": False, "ntc_type": "none", "reason": "Unknown NTC value"}


# ---------------------------------------------------------------------------
# Non-tender decisions
# ---------------------------------------------------------------------------

def process_non_tender_decisions(season: int, db_path: str = None) -> list:
    """During offseason, AI teams decide whether to tender contracts to
    arbitration-eligible players. Uses WAR-based valuation."""
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
        war = _calc_war_approx(p)
        projected_arb_salary = _war_to_salary(war)

        # Service-year bump
        service_mult = 1.0 + (p["service_years"] - 3) * 0.15
        projected_arb_salary = int(projected_arb_salary * service_mult)

        # Player value adjusted for age
        player_value = war * 8_000_000
        age_factor = max(0.5, (35 - p["age"]) / 10.0)
        adjusted_value = player_value * age_factor

        if projected_arb_salary > adjusted_value and random.random() < 0.6:
            conn.execute(
                "UPDATE players SET roster_status='free_agent', team_id=NULL WHERE id=?",
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
