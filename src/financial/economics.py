"""
Front Office - Financial Model
Revenue (tickets, TV, merch, concessions), expenses, and attendance.
Based on Baseball Mogul's economic model.
"""
import random
from ..database.db import get_connection, query, execute


def calculate_season_finances(team_id: int, season: int, db_path: str = None) -> dict:
    """Calculate full season financial picture for a team."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return {}
    t = team[0]

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

    # Ticket revenue: attendance * avg ticket price
    # MLB avg ticket ~$35, adjusted by team pricing
    avg_ticket = 35 * (t["ticket_price_pct"] / 100)
    ticket_revenue = int(att["total"] * avg_ticket)

    # Concession revenue: ~$25-40 per fan, adjusted by pricing
    avg_concession = 30 * (t["concession_price_pct"] / 100)
    # Higher prices = fewer purchases (elasticity)
    elasticity = 1.5 - (t["concession_price_pct"] / 200)
    concession_revenue = int(att["total"] * avg_concession * elasticity)

    # Broadcast revenue: market-based
    # Big market: $100-300M, small market: $20-60M
    broadcast_base = {1: 25, 2: 45, 3: 80, 4: 140, 5: 250}
    broadcast_revenue = broadcast_base.get(t["market_size"], 60) * 1000000
    # Performance bonus: winning teams get slight bump
    wins = query("""
        SELECT COUNT(*) as w FROM schedule
        WHERE season=? AND is_played=1 AND (
            (home_team_id=? AND home_score > away_score) OR
            (away_team_id=? AND away_score > home_score))
    """, (season, team_id, team_id), db_path=db_path)
    win_count = wins[0]["w"] if wins else 0
    if win_count > 90:
        broadcast_revenue = int(broadcast_revenue * 1.1)

    # Merchandise: correlated with market + fan loyalty + winning
    merch_base = t["market_size"] * 5000000
    loyalty_bonus = t["fan_loyalty"] / 100
    merch_revenue = int(merch_base * (0.5 + loyalty_bonus))

    total_revenue = ticket_revenue + concession_revenue + broadcast_revenue + merch_revenue

    # ---- EXPENSES ----

    # Payroll
    payroll = query("""
        SELECT COALESCE(SUM(c.annual_salary), 0) as total
        FROM contracts c JOIN players p ON p.id = c.player_id
        WHERE c.team_id=? AND p.roster_status != 'free_agent'
    """, (team_id,), db_path=db_path)
    payroll_total = payroll[0]["total"] if payroll else 0

    # Operating expenses
    farm_expenses = t["farm_system_budget"]
    medical_expenses = t["medical_staff_budget"]
    scouting_expenses = t["scouting_staff_budget"]

    # Stadium operations: ~$30-50M
    stadium_expenses = int(t["stadium_capacity"] * 800)

    # Owner dividends: ~10% of franchise value
    owner_dividends = int(t["franchise_value"] * 0.10)

    total_expenses = (payroll_total + farm_expenses + medical_expenses +
                      scouting_expenses + stadium_expenses + owner_dividends)

    profit = total_revenue - total_expenses

    result = {
        "team_id": team_id,
        "season": season,
        "ticket_revenue": ticket_revenue,
        "concession_revenue": concession_revenue,
        "broadcast_revenue": broadcast_revenue,
        "merchandise_revenue": merch_revenue,
        "total_revenue": total_revenue,
        "payroll": payroll_total,
        "farm_expenses": farm_expenses,
        "medical_expenses": medical_expenses,
        "scouting_expenses": scouting_expenses,
        "stadium_expenses": stadium_expenses,
        "owner_dividends": owner_dividends,
        "total_expenses": total_expenses,
        "profit": profit,
        "attendance_total": int(att["total"]),
        "attendance_avg": int(att["avg"]),
    }

    return result


def save_season_finances(team_id: int, season: int, db_path: str = None):
    """Calculate and save season finances to history."""
    fin = calculate_season_finances(team_id, season, db_path)
    if not fin:
        return

    conn = get_connection(db_path)
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
    conn.commit()
    conn.close()
