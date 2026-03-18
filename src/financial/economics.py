"""
Front Office - Financial Model
Revenue (tickets, TV, merch, concessions), expenses, and attendance.
Includes luxury tax, revenue sharing, payroll floor, and franchise valuation dynamics.
"""
import random
from ..database.db import get_connection, query, execute


# ---- CONSTANTS ----

PAYROLL_FLOOR = 50_000_000

# CBT thresholds (2026 estimates)
CBT_THRESHOLD_1 = 241_000_000  # 20% tax
CBT_THRESHOLD_2 = 261_000_000  # 32% tax on amount over T1
CBT_THRESHOLD_3 = 281_000_000  # 62% tax on amount over T2 + 110% surtax over T3

# Revenue sharing contribution rate
REVENUE_SHARING_RATE = 0.48

# Attendance model constants
BASE_ATTENDANCE_BY_MARKET = {1: 18000, 2: 24000, 3: 30000, 4: 35000, 5: 40000}
TICKET_PRICE_BY_MARKET = {1: 25, 2: 35, 3: 45, 4: 55, 5: 65}
DEFAULT_STADIUM_CAPACITY = 45000
NEW_STADIUM_BOUNCE_YEARS = 3
NEW_STADIUM_BOUNCE_PCT = 0.15


def calculate_dynamic_attendance(team_id: int, season: int, db_path: str = None) -> dict:
    """Calculate dynamic per-game attendance based on multiple factors.

    Returns dict with 'attendance' (per-game estimate) and component breakdowns.
    """
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return {"attendance": 30000, "components": {}}
    t = team[0]

    market_size = t["market_size"]
    stadium_cap = t.get("stadium_capacity", DEFAULT_STADIUM_CAPACITY)

    # 1. Base attendance from market size
    base = BASE_ATTENDANCE_BY_MARKET.get(market_size, 30000)

    # 2. Winning bonus/penalty
    wins_data = query("""
        SELECT COUNT(*) as w FROM schedule
        WHERE season=? AND is_played=1 AND (
            (home_team_id=? AND home_score > away_score) OR
            (away_team_id=? AND away_score > home_score))
    """, (season, team_id, team_id), db_path=db_path)
    losses_data = query("""
        SELECT COUNT(*) as l FROM schedule
        WHERE season=? AND is_played=1 AND (
            (home_team_id=? AND home_score < away_score) OR
            (away_team_id=? AND away_score < home_score))
    """, (season, team_id, team_id), db_path=db_path)
    win_count = wins_data[0]["w"] if wins_data else 0
    loss_count = losses_data[0]["l"] if losses_data else 0
    total_games = win_count + loss_count

    winning_bonus = 0
    if total_games > 0:
        games_above_500 = win_count - (total_games / 2)
        if games_above_500 > 0:
            winning_bonus = int(games_above_500 * 100)
        else:
            winning_bonus = int(games_above_500 * 150)  # -150 per loss below .500

    # 3. Star power: +500 per player with overall >= 75 (max +3000)
    #    Overall approximated as average of contact, power, speed, fielding, arm, eye
    #    (for pitchers: stuff, control, stamina are used instead of batting ratings)
    star_players = query("""
        SELECT COUNT(*) as cnt FROM players
        WHERE team_id=? AND roster_status='active'
        AND (
            CASE WHEN position IN ('SP', 'RP')
                THEN (stuff_rating + control_rating + stamina_rating) / 3
                ELSE (contact_rating + power_rating + speed_rating + fielding_rating + arm_rating + eye_rating) / 6
            END
        ) >= 75
    """, (team_id,), db_path=db_path)
    star_count = star_players[0]["cnt"] if star_players else 0
    star_bonus = min(star_count * 500, 3000)

    # 4. Streak bonus
    streak_bonus = 0
    recent_games = query("""
        SELECT
            CASE WHEN (s.home_team_id=? AND gr.home_score > gr.away_score)
                 OR (s.away_team_id=? AND gr.away_score > gr.home_score)
                 THEN 1 ELSE 0 END as won
        FROM game_results gr
        JOIN schedule s ON s.id = gr.schedule_id
        WHERE (s.home_team_id=? OR s.away_team_id=?) AND s.season=?
        ORDER BY s.game_date DESC LIMIT 10
    """, (team_id, team_id, team_id, team_id, season), db_path=db_path)

    if recent_games and len(recent_games) >= 5:
        # Check win streak
        win_streak = 0
        for g in recent_games:
            if g["won"] == 1:
                win_streak += 1
            else:
                break
        # Check loss streak
        loss_streak = 0
        for g in recent_games:
            if g["won"] == 0:
                loss_streak += 1
            else:
                break

        if win_streak >= 5:
            streak_bonus = 1000
        elif loss_streak >= 5:
            streak_bonus = -500

    # 5. Stadium quality (revenue boost as percentage of base)
    stadium_revenue_boost = t.get("stadium_revenue_boost", 0)
    # Treat every $1M of stadium revenue boost as ~1% attendance boost
    stadium_quality_pct = min(stadium_revenue_boost / 1_000_000 * 0.01, 0.15)
    stadium_quality_bonus = int(base * stadium_quality_pct)

    # 6. New stadium bounce: +15% for first 3 years after stadium upgrade
    new_stadium_bonus = 0
    game_state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
    current_season = game_state[0]["season"] if game_state else season
    stadium_built = t.get("stadium_built_year", 2000)
    years_since_build = current_season - stadium_built
    if 0 <= years_since_build < NEW_STADIUM_BOUNCE_YEARS:
        new_stadium_bonus = int(base * NEW_STADIUM_BOUNCE_PCT)

    # 7. Playoff contention: +10% if within 5 games of playoff spot after July
    contention_bonus = 0
    # Simple proxy: if team is above .450 and it's past game 81 (roughly July)
    if total_games > 81 and total_games > 0:
        win_pct = win_count / total_games
        if win_pct >= 0.450:
            contention_bonus = int(base * 0.10)

    # Sum it all up
    raw_attendance = (base + winning_bonus + star_bonus + streak_bonus +
                      stadium_quality_bonus + new_stadium_bonus + contention_bonus)

    # Add random variance (±5%)
    variance = random.uniform(0.95, 1.05)
    raw_attendance = int(raw_attendance * variance)

    # Cap at stadium capacity
    final_attendance = max(8000, min(stadium_cap, raw_attendance))

    return {
        "attendance": final_attendance,
        "components": {
            "base": base,
            "winning_bonus": winning_bonus,
            "star_bonus": star_bonus,
            "streak_bonus": streak_bonus,
            "stadium_quality_bonus": stadium_quality_bonus,
            "new_stadium_bonus": new_stadium_bonus,
            "contention_bonus": contention_bonus,
            "wins": win_count,
            "losses": loss_count,
        }
    }


def calculate_season_finances(team_id: int, season: int, db_path: str = None) -> dict:
    """Calculate full season financial picture for a team.

    Applies difficulty modifiers to revenue based on game_state difficulty setting.
    """
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return {}
    t = team[0]

    # Get difficulty setting
    game_state = query("SELECT difficulty FROM game_state WHERE id=1", db_path=db_path)
    difficulty = game_state[0]["difficulty"] if game_state else "manager"

    # Revenue modifiers by difficulty
    difficulty_mods = {
        "fan": 1.05,        # +5% revenue
        "coach": 1.0,       # baseline
        "manager": 1.0,     # baseline
        "mogul": 0.90,      # -10% revenue
    }
    revenue_mod = difficulty_mods.get(difficulty, 1.0)

    # Get season attendance
    attendance = query("""
        SELECT COALESCE(SUM(gr.attendance), 0) as total,
               COUNT(gr.id) as home_games,
               COALESCE(AVG(gr.attendance), 0) as avg
        FROM game_results gr
        JOIN schedule s ON s.id = gr.schedule_id
        WHERE s.home_team_id=? AND s.season=?
    """, (team_id, season), db_path=db_path)
    att = attendance[0] if attendance else {"total": 0, "home_games": 0, "avg": 0}

    # ---- REVENUE ----

    # Calculate home/away game split for revenue
    home_games = query("""
        SELECT COUNT(*) as count FROM schedule
        WHERE season=? AND home_team_id=? AND is_played=1
    """, (season, team_id), db_path=db_path)
    home_game_count = home_games[0]["count"] if home_games else 0

    away_games = query("""
        SELECT COUNT(*) as count FROM schedule
        WHERE season=? AND away_team_id=? AND is_played=1
    """, (season, team_id), db_path=db_path)
    away_game_count = away_games[0]["count"] if away_games else 0

    total_games = home_game_count + away_game_count

    # Home team gets 85% of gate revenue (tickets + concessions)
    # Away team gets 15% of gate revenue
    if total_games > 0:
        home_att_pct = home_game_count / total_games
        away_att_pct = away_game_count / total_games
    else:
        home_att_pct = 0.5
        away_att_pct = 0.5

    # Ticket revenue (market-based ticket pricing)
    market_size = t["market_size"]
    avg_ticket = TICKET_PRICE_BY_MARKET.get(market_size, 45) * (t["ticket_price_pct"] / 100)
    total_ticket_base = int(att["total"] * avg_ticket)
    ticket_revenue = int(total_ticket_base * (home_att_pct * 0.85 + away_att_pct * 0.15))

    # Concession revenue (with home/away split)
    avg_concession = 30 * (t["concession_price_pct"] / 100)
    elasticity = 1.5 - (t["concession_price_pct"] / 200)
    total_concession_base = int(att["total"] * avg_concession * elasticity)
    concession_revenue = int(total_concession_base * (home_att_pct * 0.85 + away_att_pct * 0.15))

    # Broadcast revenue: use new broadcast deal system if available, fall back to legacy system
    broadcast_deal_value = t.get("broadcast_deal_value", 0)
    if broadcast_deal_value > 0:
        # New broadcast deal system
        broadcast_revenue = broadcast_deal_value
    else:
        # Legacy broadcast contract system (for backward compatibility)
        broadcast_base = {1: 25, 2: 45, 3: 80, 4: 140, 5: 250}
        broadcast_revenue = broadcast_base.get(market_size, 60) * 1000000

        # Apply broadcast contract type multiplier
        contract_type = t.get("broadcast_contract_type", "normal")
        if contract_type == "cable":
            broadcast_revenue = int(broadcast_revenue * 1.3)
        elif contract_type == "blackout":
            broadcast_revenue = int(broadcast_revenue * 1.5)

    # Performance bonus
    wins = query("""
        SELECT COUNT(*) as w FROM schedule
        WHERE season=? AND is_played=1 AND (
            (home_team_id=? AND home_score > away_score) OR
            (away_team_id=? AND away_score > home_score))
    """, (season, team_id, team_id), db_path=db_path)
    win_count = wins[0]["w"] if wins else 0
    if win_count > 90:
        broadcast_revenue = int(broadcast_revenue * 1.1)

    # Merchandise
    merch_base = market_size * 5000000
    loyalty_bonus = t["fan_loyalty"] / 100
    merch_revenue = int(merch_base * (0.5 + loyalty_bonus))

    # Stadium upgrade revenue (annual recurring from purchased upgrades)
    stadium_upgrade_revenue = t.get("stadium_revenue_boost", 0)

    # Sponsorship revenue (market-size based, part of local revenue)
    sponsorship_revenue = int(market_size * 3_000_000 * (0.8 + t["fan_loyalty"] / 250))

    local_revenue = (ticket_revenue + concession_revenue + merch_revenue +
                     stadium_upgrade_revenue + sponsorship_revenue)
    total_revenue = local_revenue + broadcast_revenue

    # Apply difficulty modifier to total revenue
    total_revenue = int(total_revenue * revenue_mod)

    # ---- EXPENSES ----

    # Payroll
    payroll = query("""
        SELECT COALESCE(SUM(c.annual_salary), 0) as total
        FROM contracts c JOIN players p ON p.id = c.player_id
        WHERE c.team_id=? AND p.roster_status != 'free_agent'
    """, (team_id,), db_path=db_path)
    payroll_total = payroll[0]["total"] if payroll else 0

    # Luxury tax (CBT) calculation
    luxury_tax = _calculate_luxury_tax(payroll_total, team_id, season, db_path)

    # Payroll floor penalty
    payroll_floor_penalty = 0
    if payroll_total < PAYROLL_FLOOR:
        payroll_floor_penalty = PAYROLL_FLOOR - payroll_total

    # Operating expenses
    farm_expenses = t["farm_system_budget"]
    medical_expenses = t["medical_staff_budget"]
    scouting_expenses = t["scouting_staff_budget"]

    # Stadium operations
    stadium_expenses = int(t["stadium_capacity"] * 800)

    # Owner dividends
    owner_dividends = int(t["franchise_value"] * 0.10)

    total_expenses = (payroll_total + farm_expenses + medical_expenses +
                      scouting_expenses + stadium_expenses + owner_dividends +
                      luxury_tax + payroll_floor_penalty)

    profit = total_revenue - total_expenses

    # Handle broadcast contract type penalties/restrictions
    contract_years_remaining = t.get("broadcast_contract_years_remaining", 3)
    blackout_penalty = 0

    if t.get("broadcast_contract_type") == "blackout":
        # Blackout contract reduces fan loyalty by 2 per season
        blackout_penalty = -2

    result = {
        "team_id": team_id,
        "season": season,
        "ticket_revenue": ticket_revenue,
        "concession_revenue": concession_revenue,
        "broadcast_revenue": broadcast_revenue,
        "merchandise_revenue": merch_revenue,
        "sponsorship_revenue": sponsorship_revenue,
        "local_revenue": local_revenue,
        "total_revenue": total_revenue,
        "payroll": payroll_total,
        "luxury_tax": luxury_tax,
        "payroll_floor_penalty": payroll_floor_penalty,
        "farm_expenses": farm_expenses,
        "medical_expenses": medical_expenses,
        "scouting_expenses": scouting_expenses,
        "stadium_expenses": stadium_expenses,
        "owner_dividends": owner_dividends,
        "total_expenses": total_expenses,
        "profit": profit,
        "attendance_total": int(att["total"]),
        "attendance_avg": int(att["avg"]),
        "wins": win_count,
        "broadcast_contract_type": t.get("broadcast_contract_type", "normal"),
        "broadcast_contract_years_remaining": contract_years_remaining,
        "blackout_penalty": blackout_penalty,
        "home_games": home_game_count,
        "away_games": away_game_count,
    }

    return result


def _calculate_luxury_tax(payroll: int, team_id: int, season: int, db_path: str = None) -> int:
    """Calculate luxury tax (CBT) with repeat offender surcharges and multiple thresholds.

    Thresholds (2026):
      T1: $241M — 20% (1st year), 32% (2nd), 62% (3rd+)
      T2: $261M — 32% tax on amount over T1
      T3: $281M — 62% tax on amount over T2 + 110% surtax on amount over T3
    """
    if payroll <= CBT_THRESHOLD_1:
        return 0

    # Determine consecutive years over CBT
    consecutive_years = _get_consecutive_years_over_cbt(team_id, season, db_path)

    # Tier 1 rate depends on consecutive years
    if consecutive_years == 0:
        tier1_rate = 0.20   # First year over
    elif consecutive_years == 1:
        tier1_rate = 0.32   # 2nd consecutive year
    else:
        tier1_rate = 0.62   # 3rd+ consecutive year

    tax = 0

    # Tier 1: T1 to T2
    amount_in_tier1 = min(payroll, CBT_THRESHOLD_2) - CBT_THRESHOLD_1
    tax += int(amount_in_tier1 * tier1_rate)

    # Tier 2: T2 to T3
    if payroll > CBT_THRESHOLD_2:
        amount_in_tier2 = min(payroll, CBT_THRESHOLD_3) - CBT_THRESHOLD_2
        tax += int(amount_in_tier2 * 0.32)

    # Tier 3: T3+
    if payroll > CBT_THRESHOLD_3:
        amount_over_t2 = payroll - CBT_THRESHOLD_2
        amount_over_t3 = payroll - CBT_THRESHOLD_3
        tax += int(amount_over_t2 * 0.62)
        tax += int(amount_over_t3 * 1.10)  # 110% surtax on amount over T3

    return tax


def _get_consecutive_years_over_cbt(team_id: int, season: int, db_path: str = None) -> int:
    """Count how many consecutive prior seasons the team was over the CBT threshold."""
    consecutive = 0
    for s in range(season - 1, season - 10, -1):
        prev = query("""
            SELECT payroll FROM financial_history
            WHERE team_id=? AND season=?
            LIMIT 1
        """, (team_id, s), db_path=db_path)
        if prev and prev[0]["payroll"] > CBT_THRESHOLD_1:
            consecutive += 1
        else:
            break
    return consecutive


def _check_cbt_draft_pick_loss(team_id: int, season: int, db_path: str = None) -> bool:
    """Check if team loses first-round draft pick due to exceeding T3.

    Returns True if team should lose their first-round pick.
    """
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return False

    payroll = query("""
        SELECT COALESCE(SUM(c.annual_salary), 0) as total
        FROM contracts c JOIN players p ON p.id = c.player_id
        WHERE c.team_id=? AND p.roster_status != 'free_agent'
    """, (team_id,), db_path=db_path)
    payroll_total = payroll[0]["total"] if payroll else 0

    # Lose pick if over T3 AND 3+ consecutive years over CBT
    if payroll_total > CBT_THRESHOLD_3:
        consecutive = _get_consecutive_years_over_cbt(team_id, season, db_path)
        if consecutive >= 2:  # This is the 3rd+ year
            return True

    return False


def calculate_franchise_valuation_change(team_id: int, season: int, db_path: str = None) -> float:
    """Calculate franchise value change based on performance and market factors.

    Returns a multiplier (e.g., 1.08 = +8% increase).
    Capped at ±25% per year.
    """
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return 1.0

    t = team[0]

    # Get wins for the season
    wins = query("""
        SELECT COUNT(*) as w FROM schedule
        WHERE season=? AND is_played=1 AND (
            (home_team_id=? AND home_score > away_score) OR
            (away_team_id=? AND away_score > home_score))
    """, (season, team_id, team_id), db_path=db_path)
    win_count = wins[0]["w"] if wins else 81

    # Start with base appreciation (+3% general sports market growth)
    pct_change = 0.03

    # Winning premium
    if win_count >= 95:
        pct_change += 0.05
    elif win_count >= 90:
        pct_change += 0.03
    elif win_count >= 85:
        pct_change += 0.01
    elif win_count < 65:
        pct_change -= 0.05
    elif win_count < 75:
        pct_change -= 0.02

    # Playoff run bonuses
    playoff_result = query("""
        SELECT COUNT(*) as series_count
        FROM playoff_bracket
        WHERE season=? AND (higher_seed_id=? OR lower_seed_id=?)
    """, (season, team_id, team_id), db_path=db_path)

    if playoff_result and playoff_result[0]["series_count"] > 0:
        # Check if team won the World Series
        ws_result = query("""
            SELECT winner_id FROM playoff_bracket
            WHERE season=? AND round='world_series'
            LIMIT 1
        """, (season,), db_path=db_path)
        ws_winner = ws_result[0]["winner_id"] if ws_result and ws_result[0].get("winner_id") else None

        lcs_result = query("""
            SELECT winner_id FROM playoff_bracket
            WHERE season=? AND round='championship_series'
              AND (higher_seed_id=? OR lower_seed_id=?)
            LIMIT 1
        """, (season, team_id, team_id), db_path=db_path)
        lcs_winner = lcs_result[0]["winner_id"] if lcs_result and lcs_result[0].get("winner_id") else None

        if ws_winner == team_id:
            pct_change += 0.20  # Won World Series
        elif lcs_winner == team_id:
            pct_change += 0.10  # Won LCS
        else:
            pct_change += 0.05  # Made playoffs

    # Market size: large markets appreciate faster
    market_appreciation = {1: 0.00, 2: 0.005, 3: 0.01, 4: 0.015, 5: 0.02}
    pct_change += market_appreciation.get(t["market_size"], 0.01)

    # Revenue trend: compare to prior year
    prev_finances = query("""
        SELECT total_revenue FROM financial_history
        WHERE team_id=? AND season=?
        LIMIT 1
    """, (team_id, season - 1), db_path=db_path)

    if prev_finances:
        current_finances = calculate_season_finances(team_id, season, db_path)
        current_rev = current_finances.get("total_revenue", 0)
        prev_rev = prev_finances[0]["total_revenue"]
        if prev_rev > 0 and current_rev > prev_rev:
            pct_change += 0.02
        elif prev_rev > 0 and current_rev < prev_rev:
            pct_change -= 0.01

    # New stadium bonus: +15% in year of opening
    stadium_built = t.get("stadium_built_year", 2000)
    if stadium_built == season:
        pct_change += 0.15

    # Cap at ±25% per year
    pct_change = max(-0.25, min(0.25, pct_change))

    return 1.0 + pct_change


def _calculate_revenue_sharing(all_team_finances: list) -> dict:
    """Calculate market-weighted revenue sharing across all teams.

    Each team contributes 48% of local revenue to pool.
    Pool is divided equally among all teams.
    Teams below payroll floor cannot receive revenue sharing.

    Args:
        all_team_finances: list of dicts from calculate_season_finances for each team

    Returns:
        dict mapping team_id -> {"contribution": int, "receipt": int, "net": int}
    """
    team_count = len(all_team_finances)
    if team_count == 0:
        return {}

    # Each team contributes 48% of local revenue
    contributions = {}
    total_pool = 0
    below_floor_teams = set()

    for fin in all_team_finances:
        tid = fin["team_id"]
        local_rev = fin["local_revenue"]
        contribution = int(local_rev * REVENUE_SHARING_RATE)
        contributions[tid] = contribution
        total_pool += contribution

        # Track teams below payroll floor
        if fin["payroll"] < PAYROLL_FLOOR:
            below_floor_teams.add(tid)
            # Below-floor teams also pay floor penalty into the pool
            total_pool += fin.get("payroll_floor_penalty", 0)

    # Eligible recipients = teams NOT below payroll floor
    eligible_count = team_count - len(below_floor_teams)
    if eligible_count <= 0:
        eligible_count = team_count  # fallback: everyone gets share
        below_floor_teams = set()

    equal_share = int(total_pool / eligible_count) if eligible_count > 0 else 0

    results = {}
    for fin in all_team_finances:
        tid = fin["team_id"]
        contribution = contributions[tid]

        if tid in below_floor_teams:
            # Below-floor teams cannot receive revenue sharing
            receipt = 0
        else:
            receipt = equal_share

        net = receipt - contribution
        results[tid] = {
            "contribution": contribution,
            "receipt": receipt,
            "net": net,
        }

    return results


def process_end_of_season_finances(season: int, db_path: str = None) -> list:
    """Process end-of-season finances for ALL teams with proper revenue sharing.

    This is the main entry point for end-of-season financial processing.
    It calculates finances for every team, then applies market-weighted
    revenue sharing, payroll floor enforcement, luxury tax, and franchise
    value changes.

    Returns list of per-team financial summaries.
    """
    all_teams = query("SELECT id FROM teams", db_path=db_path)
    if not all_teams:
        return []

    # Step 1: Calculate base finances for every team
    all_finances = []
    for team_row in all_teams:
        tid = team_row["id"]
        fin = calculate_season_finances(tid, season, db_path)
        if fin:
            all_finances.append(fin)

    # Step 2: Calculate revenue sharing (market-weighted)
    sharing = _calculate_revenue_sharing(all_finances)

    # Step 3: Apply revenue sharing, save, and update each team
    results = []
    conn = get_connection(db_path)

    for fin in all_finances:
        tid = fin["team_id"]
        share_info = sharing.get(tid, {"contribution": 0, "receipt": 0, "net": 0})

        # Adjust total revenue with revenue sharing net effect
        fin["revenue_sharing_contribution"] = share_info["contribution"]
        fin["revenue_sharing_receipt"] = share_info["receipt"]
        fin["revenue_sharing_net"] = share_info["net"]
        fin["total_revenue"] += share_info["net"]
        fin["profit"] = fin["total_revenue"] - fin["total_expenses"]

        # Payroll floor: reduce fan satisfaction
        if fin["payroll"] < PAYROLL_FLOOR:
            conn.execute("""
                UPDATE teams SET fan_loyalty = MAX(0, fan_loyalty - 5)
                WHERE id=?
            """, (tid,))

        # Save financial history
        conn.execute("""
            INSERT OR REPLACE INTO financial_history
                (team_id, season, ticket_revenue, concession_revenue, broadcast_revenue,
                 merchandise_revenue, total_revenue, payroll, farm_expenses, medical_expenses,
                 scouting_expenses, stadium_expenses, owner_dividends, total_expenses,
                 profit, attendance_total, attendance_avg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tid, season, fin["ticket_revenue"], fin["concession_revenue"],
              fin["broadcast_revenue"], fin["merchandise_revenue"], fin["total_revenue"],
              fin["payroll"], fin["farm_expenses"], fin["medical_expenses"],
              fin["scouting_expenses"], fin["stadium_expenses"], fin["owner_dividends"],
              fin["total_expenses"], fin["profit"],
              fin["attendance_total"], fin["attendance_avg"]))

        # Update team cash
        conn.execute("UPDATE teams SET cash = cash + ? WHERE id=?",
                     (fin["profit"], tid))

        # Update franchise valuation
        valuation_change = calculate_franchise_valuation_change(tid, season, db_path)
        team_row = conn.execute("SELECT franchise_value FROM teams WHERE id=?",
                                (tid,)).fetchone()
        if team_row:
            current_value = team_row["franchise_value"]
            updated_value = int(current_value * valuation_change)
            conn.execute("UPDATE teams SET franchise_value=? WHERE id=?",
                         (updated_value, tid))
            fin["franchise_value_change"] = valuation_change
            fin["new_franchise_value"] = updated_value

        # Check for CBT draft pick loss
        if _check_cbt_draft_pick_loss(tid, season, db_path):
            fin["lost_first_round_pick"] = True
            # Remove first-round pick if draft_pick_ownership table tracks it
            conn.execute("""
                DELETE FROM draft_pick_ownership
                WHERE current_owner_team_id=? AND season=? AND round=1
            """, (tid, season + 1))

        # Handle broadcast contract: decrement years remaining
        contract_years = fin.get("broadcast_contract_years_remaining", 3)
        new_contract_years = max(0, contract_years - 1)

        if new_contract_years == 0:
            conn.execute("""
                UPDATE teams SET broadcast_contract_type='normal',
                               broadcast_contract_years_remaining=3
                WHERE id=?
            """, (tid,))
        else:
            conn.execute("UPDATE teams SET broadcast_contract_years_remaining=? WHERE id=?",
                         (new_contract_years, tid))

        # Apply blackout penalty to fan loyalty
        blackout_penalty = fin.get("blackout_penalty", 0)
        if blackout_penalty != 0:
            conn.execute("""
                UPDATE teams SET fan_loyalty = MAX(0, MIN(100, fan_loyalty + ?))
                WHERE id=?
            """, (blackout_penalty, tid))

        results.append(fin)

    conn.commit()
    conn.close()

    return results


def save_season_finances(team_id: int, season: int, db_path: str = None):
    """Calculate and save season finances for a single team.

    NOTE: For proper revenue sharing across all teams, use
    process_end_of_season_finances() instead. This function is kept
    for backward compatibility but does not calculate league-wide
    revenue sharing correctly.
    """
    fin = calculate_season_finances(team_id, season, db_path)
    if not fin:
        return

    conn = get_connection(db_path)

    # Revenue sharing estimate for single-team mode (approximate)
    local_rev = fin["local_revenue"]
    contribution = int(local_rev * REVENUE_SHARING_RATE)
    # Approximate: assume average team contributes same as this team
    receipt = contribution  # Net zero in single-team mode
    fin["revenue_sharing_contribution"] = contribution
    fin["revenue_sharing_receipt"] = receipt

    # Save financial history
    conn.execute("""
        INSERT OR REPLACE INTO financial_history
            (team_id, season, ticket_revenue, concession_revenue, broadcast_revenue,
             merchandise_revenue, total_revenue, payroll, farm_expenses, medical_expenses,
             scouting_expenses, stadium_expenses, owner_dividends, total_expenses,
             profit, attendance_total, attendance_avg)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (team_id, season, fin["ticket_revenue"], fin["concession_revenue"],
          fin["broadcast_revenue"], fin["merchandise_revenue"], fin["total_revenue"],
          fin["payroll"], fin["farm_expenses"], fin["medical_expenses"],
          fin["scouting_expenses"], fin["stadium_expenses"], fin["owner_dividends"],
          fin["total_expenses"], fin["profit"],
          fin["attendance_total"], fin["attendance_avg"]))

    # Update team cash
    conn.execute("UPDATE teams SET cash = cash + ? WHERE id=?",
                (fin["profit"], team_id))

    # Update franchise valuation
    valuation_change = calculate_franchise_valuation_change(team_id, season, db_path)

    team = conn.execute("SELECT franchise_value FROM teams WHERE id=?",
                       (team_id,)).fetchone()
    if team:
        current_value = team["franchise_value"]
        updated_value = int(current_value * valuation_change)
        conn.execute("UPDATE teams SET franchise_value=? WHERE id=?",
                    (updated_value, team_id))

    # Handle broadcast contract: decrement years remaining
    contract_years = fin.get("broadcast_contract_years_remaining", 3)
    new_contract_years = max(0, contract_years - 1)

    # If contract expired, reset to normal
    if new_contract_years == 0:
        conn.execute("""
            UPDATE teams SET broadcast_contract_type='normal',
                           broadcast_contract_years_remaining=3
            WHERE id=?
        """, (team_id,))
    else:
        conn.execute("UPDATE teams SET broadcast_contract_years_remaining=? WHERE id=?",
                    (new_contract_years, team_id))

    # Apply blackout penalty to fan loyalty
    blackout_penalty = fin.get("blackout_penalty", 0)
    if blackout_penalty != 0:
        conn.execute("""
            UPDATE teams SET fan_loyalty = MAX(0, MIN(100, fan_loyalty + ?))
            WHERE id=?
        """, (blackout_penalty, team_id))

    # Payroll floor: reduce fan loyalty if below
    if fin["payroll"] < PAYROLL_FLOOR:
        conn.execute("""
            UPDATE teams SET fan_loyalty = MAX(0, fan_loyalty - 5)
            WHERE id=?
        """, (team_id,))

    conn.commit()
    conn.close()
