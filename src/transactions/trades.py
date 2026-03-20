"""
Front Office - Trade System
Handles trade proposals, evaluation, execution, and history.
"""
import json
from datetime import date
from ..database.db import get_connection, query, execute
from ..ai.gm_brain import evaluate_trade
from ..ai.proactive_messaging import send_trade_reaction_messages


async def propose_trade(proposing_team_id: int, receiving_team_id: int,
                        players_offered: list[int], players_requested: list[int],
                        cash_included: int = 0, draft_picks_offered: list[dict] = None,
                        draft_picks_requested: list[dict] = None,
                        db_path: str = None) -> dict:
    """
    Propose a trade to another team's GM.
    Draft picks format: [{"season": 2027, "round": 1, "pick_number": 5}, ...]
    Returns the GM's response (accept/reject with reasoning).
    """
    if draft_picks_offered is None:
        draft_picks_offered = []
    if draft_picks_requested is None:
        draft_picks_requested = []

    # Check trade deadline
    state = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
    if state:
        gs = state[0]
        current_date = date.fromisoformat(gs["current_date"])
        season = gs["season"]
        deadline = date(season, 7, 31)
        if gs["phase"] == "regular_season" and current_date > deadline:
            return {
                "error": "Trade deadline has passed. No trades until the offseason."
            }

    # Validate players belong to correct teams
    for pid in players_offered:
        p = query("SELECT team_id FROM players WHERE id=?", (pid,), db_path=db_path)
        if not p or p[0]["team_id"] != proposing_team_id:
            return {"error": f"Player {pid} is not on the proposing team"}

    for pid in players_requested:
        p = query("SELECT team_id FROM players WHERE id=?", (pid,), db_path=db_path)
        if not p or p[0]["team_id"] != receiving_team_id:
            return {"error": f"Player {pid} is not on the receiving team"}

    # Check no-trade clauses and 10-and-5 rights (unified check)
    from ..transactions.contracts import check_no_trade_clause
    for pid in players_requested:
        ntc_result = check_no_trade_clause(
            pid, destination_team_id=proposing_team_id,
            is_ai_trade=False, db_path=db_path
        )
        if ntc_result["blocked"]:
            return {
                "error": f"Player {pid}: {ntc_result['reason']}",
                "ntc_block": True,
                "ntc_type": ntc_result["ntc_type"],
            }

    # Check cash availability
    if cash_included > 0:
        team = query("SELECT cash FROM teams WHERE id=?",
                    (proposing_team_id,), db_path=db_path)
        if team and team[0]["cash"] < cash_included:
            return {"error": "Insufficient cash for this trade"}

    # Validate draft picks belong to correct teams
    for pick in draft_picks_offered:
        ownership = query("""
            SELECT current_owner_team_id FROM draft_pick_ownership
            WHERE season=? AND round=? AND pick_number=?
        """, (pick["season"], pick["round"], pick["pick_number"]), db_path=db_path)
        if not ownership or ownership[0]["current_owner_team_id"] != proposing_team_id:
            return {"error": f"Draft pick not owned by proposing team"}

    for pick in draft_picks_requested:
        ownership = query("""
            SELECT current_owner_team_id FROM draft_pick_ownership
            WHERE season=? AND round=? AND pick_number=?
        """, (pick["season"], pick["round"], pick["pick_number"]), db_path=db_path)
        if not ownership or ownership[0]["current_owner_team_id"] != receiving_team_id:
            return {"error": f"Draft pick not owned by receiving team"}

    # Get GM's evaluation
    result = await evaluate_trade(
        proposing_team_id, receiving_team_id,
        players_offered, players_requested,
        cash_included, db_path
    )

    return result


async def propose_waiver_trade(proposing_team_id: int, receiving_team_id: int,
                               players_offered: list[int], players_requested: list[int],
                               cash_included: int = 0, db_path: str = None) -> dict:
    """
    Propose a post-deadline waiver trade.
    Players must have cleared waivers or been claimed before trading.
    Only available after July 31.
    """
    state = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
    if not state:
        return {"error": "No game state found"}

    gs = state[0]
    current_date = date.fromisoformat(gs["current_date"])
    season = gs["season"]
    deadline = date(season, 7, 31)

    if current_date <= deadline:
        return {"error": "Waiver trades are only available after the July 31 trade deadline."}

    # Verify all requested players have cleared waivers or are on waivers
    for pid in players_requested:
        player = query("SELECT roster_status FROM players WHERE id=?", (pid,), db_path=db_path)
        if not player:
            return {"error": f"Player {pid} not found"}
        # For post-deadline trades, player must have been through waivers
        waiver_record = query("""
            SELECT * FROM waiver_claims
            WHERE player_id=? AND status IN ('cleared', 'claimed')
            ORDER BY id DESC LIMIT 1
        """, (pid,), db_path=db_path)
        if not waiver_record:
            return {
                "error": f"Player {pid} must clear waivers before a post-deadline trade."
            }

    # Validate players belong to correct teams
    for pid in players_offered:
        p = query("SELECT team_id FROM players WHERE id=?", (pid,), db_path=db_path)
        if not p or p[0]["team_id"] != proposing_team_id:
            return {"error": f"Player {pid} is not on the proposing team"}

    for pid in players_requested:
        p = query("SELECT team_id FROM players WHERE id=?", (pid,), db_path=db_path)
        if not p or p[0]["team_id"] != receiving_team_id:
            return {"error": f"Player {pid} is not on the receiving team"}

    # Get GM's evaluation (same logic)
    result = await evaluate_trade(
        proposing_team_id, receiving_team_id,
        players_offered, players_requested,
        cash_included, db_path
    )

    return result


def execute_trade(proposing_team_id: int, receiving_team_id: int,
                  players_offered: list[int], players_requested: list[int],
                  cash_included: int = 0, draft_picks_offered: list[dict] = None,
                  draft_picks_requested: list[dict] = None,
                  db_path: str = None) -> dict:
    """Execute an accepted trade - move players between teams and update roster status."""
    if draft_picks_offered is None:
        draft_picks_offered = []
    if draft_picks_requested is None:
        draft_picks_requested = []

    conn = get_connection(db_path)

    # Move offered players to receiving team
    for pid in players_offered:
        # Update player team and maintain active status
        conn.execute("""UPDATE players SET team_id=?, roster_status='active'
                        WHERE id=? AND roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')""",
                    (receiving_team_id, pid))
        # Update contract team
        conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?",
                    (receiving_team_id, pid))

    # Move requested players to proposing team
    for pid in players_requested:
        # Update player team and maintain active status
        conn.execute("""UPDATE players SET team_id=?, roster_status='active'
                        WHERE id=? AND roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')""",
                    (proposing_team_id, pid))
        # Update contract team
        conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?",
                    (proposing_team_id, pid))

    # Transfer draft picks offered
    for pick in draft_picks_offered:
        conn.execute("""
            UPDATE draft_pick_ownership
            SET current_owner_team_id=?, traded_date=?
            WHERE season=? AND round=? AND pick_number=?
        """, (receiving_team_id, date.today().isoformat(),
              pick["season"], pick["round"], pick["pick_number"]))

    # Transfer draft picks requested
    for pick in draft_picks_requested:
        conn.execute("""
            UPDATE draft_pick_ownership
            SET current_owner_team_id=?, traded_date=?
            WHERE season=? AND round=? AND pick_number=?
        """, (proposing_team_id, date.today().isoformat(),
              pick["season"], pick["round"], pick["pick_number"]))

    # Handle cash transfer
    if cash_included > 0:
        conn.execute("UPDATE teams SET cash = cash - ? WHERE id=?",
                    (cash_included, proposing_team_id))
        conn.execute("UPDATE teams SET cash = cash + ? WHERE id=?",
                    (cash_included, receiving_team_id))

    # Log transaction
    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    game_date = state["current_date"] if state else date.today().isoformat()

    details = {
        "proposing_team": proposing_team_id,
        "receiving_team": receiving_team_id,
        "players_to_receiving": players_offered,
        "players_to_proposing": players_requested,
        "cash": cash_included,
        "draft_picks_to_receiving": draft_picks_offered,
        "draft_picks_to_proposing": draft_picks_requested,
    }
    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, team2_id, player_ids)
        VALUES (?, 'trade', ?, ?, ?, ?)
    """, (game_date, json.dumps(details), proposing_team_id, receiving_team_id,
          ",".join(str(x) for x in players_offered + players_requested)))

    conn.commit()

    # Trigger beat writer and owner reactions for the user's team
    try:
        state_row = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
        user_team_id = state_row[0]["user_team_id"] if state_row else None

        if user_team_id and user_team_id in (proposing_team_id, receiving_team_id):
            # Get player names
            offered_names = []
            for pid in players_offered:
                p = query("SELECT first_name, last_name FROM players WHERE id=?",
                         (pid,), db_path=db_path)
                if p:
                    offered_names.append(f"{p[0]['first_name']} {p[0]['last_name']}")

            requested_names = []
            for pid in players_requested:
                p = query("SELECT first_name, last_name FROM players WHERE id=?",
                         (pid,), db_path=db_path)
                if p:
                    requested_names.append(f"{p[0]['first_name']} {p[0]['last_name']}")

            # Get team names
            t1 = query("SELECT city, name FROM teams WHERE id=?",
                       (proposing_team_id,), db_path=db_path)
            t2 = query("SELECT city, name FROM teams WHERE id=?",
                       (receiving_team_id,), db_path=db_path)
            team1_name = f"{t1[0]['city']} {t1[0]['name']}" if t1 else "Team"
            team2_name = f"{t2[0]['city']} {t2[0]['name']}" if t2 else "Team"

            # From user's perspective: offered = what user gave up, requested = what user got
            if user_team_id == proposing_team_id:
                trade_reaction_details = {
                    "offered_names": offered_names,
                    "requested_names": requested_names,
                    "team_name": team1_name,
                    "other_team_name": team2_name,
                }
            else:
                trade_reaction_details = {
                    "offered_names": requested_names,
                    "requested_names": offered_names,
                    "team_name": team2_name,
                    "other_team_name": team1_name,
                }

            send_trade_reaction_messages(
                user_team_id, game_date, trade_reaction_details, db_path=db_path
            )
    except Exception:
        pass  # Don't let reaction failures break trade execution

    conn.close()

    return {"success": True, "details": details}
