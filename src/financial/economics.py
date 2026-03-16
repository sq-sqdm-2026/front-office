"""
Front Office - Financial Model
Revenue (tickets, TV, merch, concessions), expenses, and attendance.
Includes luxury tax, revenue sharing, and franchise valuation dynamics.
"""
import random
from ..database.db import get_connection, query, execute


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

    # Ticket revenue (with home/away split)
    avg_ticket = 35 * (t["ticket_price_pct"] / 100)
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
        broadcast_revenue = broadcast_base.get(t["market_size"], 60) * 1000000

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
    merch_base = t["market_size"] * 5000000
    loyalty_bonus = t["fan_loyalty"] / 100
    merch_revenue = int(merch_base * (0.5 + loyalty_bonus))

    # Stadium upgrade revenue (annual recurring from purchased upgrades)
    stadium_upgrade_revenue = t.get("stadium_revenue_boost", 0)

    local_revenue = ticket_revenue + concession_revenue + merch_revenue + stadium_upgrade_revenue
    total_revenue = local_revenue + broadcast_revenue

    # Apply difficulty modifier to total revenue
    total_revenue = int(total_revenue * revenue_mod)

    # ---- REVENUE SHARING ----

    # All teams contribute 48% of local revenue to pool
    revenue_sharing_contribution = int(local_revenue * 0.48)

    # Get all teams to calculate pool distribution
    all_teams = query("SELECT COUNT(*) as count FROM teams", db_path=db_path)
    team_count = all_teams[0]["count"] if all_teams else 30

    # Calculate total pool (sum of all contributions)
    pool_totals = query("""
        SELECT COUNT(id) as count FROM teams
    """, db_path=db_path)

    # Simplified: assume average team's local revenue for pool calculation
    # Each team gets equal share of pool
    revenue_sharing_receipt = int(revenue_sharing_contribution * (team_count - 1) / team_count)

    total_revenue += revenue_sharing_receipt

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

    # Operating expenses
    farm_expenses = t["farm_system_budget"]
    medical_expenses = t["medical_staff_budget"]
    scouting_expenses = t["scouting_staff_budget"]

    # Stadium operations
    stadium_expenses = int(t["stadium_capacity"] * 800)

    # Owner dividends
    owner_dividends = int(t["franchise_value"] * 0.10)

    total_expenses = (payroll_total + farm_expenses + medical_expenses +
                      scouting_expenses + stadium_expenses + owner_dividends + luxury_tax)

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
        "local_revenue": local_revenue,
        "revenue_sharing_contribution": revenue_sharing_contribution,
        "revenue_sharing_receipt": revenue_sharing_receipt,
        "total_revenue": total_revenue,
        "payroll": payroll_total,
        "luxury_tax": luxury_tax,
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
    """Calculate luxury tax (CBT) owed based on payroll."""
    # CBT thresholds (2026 estimates, adjust as needed)
    CBT_THRESHOLD_1 = 237000000  # First threshold: 20% tax
    CBT_THRESHOLD_2 = 257000000  # Second threshold: 30% tax
    CBT_THRESHOLD_3 = 277000000  # Third threshold: 50% tax

    if payroll <= CBT_THRESHOLD_1:
        return 0

    tax = 0

    # Check for repeat offender (2+ consecutive years over)
    prev_seasons = query("""
        SELECT payroll FROM financial_history
        WHERE team_id=? AND season IN (?, ?)
        ORDER BY season DESC LIMIT 2
    """, (team_id, season - 1, season - 2), db_path=db_path)

    repeat_offender = False
    if len(prev_seasons) >= 2:
        if prev_seasons[0]["payroll"] > CBT_THRESHOLD_1 and \
           prev_seasons[1]["payroll"] > CBT_THRESHOLD_1:
            repeat_offender = True

    # Tier 1: 237M - 257M
    if payroll > CBT_THRESHOLD_1:
        amount_over_1 = min(payroll, CBT_THRESHOLD_2) - CBT_THRESHOLD_1
        tax += int(amount_over_1 * 0.20)

    # Tier 2: 257M - 277M
    if payroll > CBT_THRESHOLD_2:
        amount_over_2 = min(payroll, CBT_THRESHOLD_3) - CBT_THRESHOLD_2
        tax += int(amount_over_2 * 0.30)

    # Tier 3: 277M+
    if payroll > CBT_THRESHOLD_3:
        amount_over_3 = payroll - CBT_THRESHOLD_3
        tax += int(amount_over_3 * 0.50)

    # Repeat offender surcharge (additional 12%)
    if repeat_offender and payroll > CBT_THRESHOLD_1:
        amount_over = payroll - CBT_THRESHOLD_1
        tax += int(amount_over * 0.12)

    return tax


def calculate_franchise_valuation_change(team_id: int, season: int, db_path: str = None) -> float:
    """Calculate franchise value change based on performance and market factors."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return 0.0

    t = team[0]

    # Get wins for the season
    wins = query("""
        SELECT COUNT(*) as w FROM schedule
        WHERE season=? AND is_played=1 AND (
            (home_team_id=? AND home_score > away_score) OR
            (away_team_id=? AND away_score > home_score))
    """, (season, team_id, team_id), db_path=db_path)
    win_count = wins[0]["w"] if wins else 81

    # Base valuation change from wins
    value_change = 1.0
    if win_count >= 90:
        value_change += 0.02  # +2% for winning seasons
    elif win_count < 70:
        value_change -= 0.01  # -1% for losing seasons

    # Attendance factor
    attendance = query("""
        SELECT COALESCE(AVG(gr.attendance), 0) as avg_att
        FROM game_results gr
        JOIN schedule s ON s.id = gr.schedule_id
        WHERE s.home_team_id=? AND s.season=?
    """, (team_id, season), db_path=db_path)
    avg_attendance = attendance[0]["avg_att"] if attendance else 0
    capacity_pct = avg_attendance / max(t["stadium_capacity"], 1)

    if capacity_pct > 0.80:
        value_change += 0.01  # +1% for good attendance

    # Market size factor (larger markets appreciate faster)
    market_multiplier = {1: 0.005, 2: 0.003, 3: 0.002, 4: 0.001, 5: 0.000}
    value_change += market_multiplier.get(t["market_size"], 0.002)

    # Revenue trend (if revenue growing, value grows)
    prev_finances = query("""
        SELECT total_revenue FROM financial_history
        WHERE team_id=? AND season=?
        LIMIT 1
    """, (team_id, season - 1), db_path=db_path)

    if prev_finances:
        current_finances = calculate_season_finances(team_id, season, db_path)
        if current_finances.get("total_revenue", 0) > prev_finances[0]["total_revenue"]:
            value_change += 0.005

    return value_change


def save_season_finances(team_id: int, season: int, db_path: str = None):
    """Calculate and save season finances to history. Update franchise value and broadcast contract."""
    fin = calculate_season_finances(team_id, season, db_path)
    if not fin:
        return

    conn = get_connection(db_path)

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
    new_franchise_value = int(fin.get("franchise_value", 1500000000) * valuation_change)

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
        # Clamp fan_loyalty to 0-100
        conn.execute("""
            UPDATE teams SET fan_loyalty = MAX(0, MIN(100, fan_loyalty + ?))
            WHERE id=?
        """, (blackout_penalty, team_id))

    conn.commit()
    conn.close()
