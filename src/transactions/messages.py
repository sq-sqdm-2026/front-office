"""
Front Office - Messages and Notifications System
Helper functions for sending notifications about key game events.
"""
from datetime import date
from ..database.db import execute, query, get_connection


def send_message(team_id: int, category: str, subject: str, body: str,
                 game_date: str = None, db_path: str = None) -> int:
    """
    Send a message/notification to the user's team.

    Args:
        team_id: ID of the recipient team
        category: Message category (trade_offer, injury, transaction, draft, milestone, financial)
        subject: Short message subject
        body: Full message body
        game_date: Date of the message (defaults to current game date)
        db_path: Database path

    Returns:
        The message ID
    """
    if game_date is None:
        state = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
        game_date = state[0]["current_date"] if state else date.today().isoformat()

    execute("""
        INSERT INTO messages (game_date, sender_type, sender_name, recipient_type,
                             recipient_id, subject, body, is_read, requires_response)
        VALUES (?, 'system', 'Front Office', 'user', ?, ?, ?, 0, 0)
    """, (game_date, team_id, subject, body), db_path=db_path)

    # Get the inserted message ID
    result = query("""
        SELECT id FROM messages
        WHERE game_date=? AND recipient_id=? AND subject=?
        ORDER BY id DESC LIMIT 1
    """, (game_date, team_id, subject), db_path=db_path)

    return result[0]["id"] if result else None


def send_trade_offer_message(proposing_team_id: int, receiving_team_id: int,
                             trade_details: dict, db_path: str = None) -> int:
    """Send a trade offer notification."""
    proposing_team = query("SELECT city, name FROM teams WHERE id=?",
                          (proposing_team_id,), db_path=db_path)
    team_name = f"{proposing_team[0]['city']} {proposing_team[0]['name']}" if proposing_team else "Unknown Team"

    subject = f"Trade Offer from {team_name}"
    body = f"The {team_name} has proposed a trade. Check the Transactions tab for details."

    return send_message(receiving_team_id, "trade_offer", subject, body, db_path=db_path)


def send_injury_message(team_id: int, player_name: str, il_tier: str,
                       db_path: str = None) -> int:
    """Send an injury notification."""
    subject = f"{player_name} Placed on IL"
    body = f"{player_name} has been placed on the {il_tier}-day injured list."
    return send_message(team_id, "injury", subject, body, db_path=db_path)


def send_injury_activation_message(team_id: int, player_name: str,
                                   db_path: str = None) -> int:
    """Send an injury activation notification."""
    subject = f"{player_name} Activated"
    body = f"{player_name} has been activated from the injured list."
    return send_message(team_id, "injury", subject, body, db_path=db_path)


def send_free_agent_signing_message(team_id: int, player_name: str,
                                    signing_team_name: str, contract_value: int = None,
                                    db_path: str = None) -> int:
    """Send a free agent signing notification."""
    subject = f"{player_name} Signed"
    if contract_value:
        body = f"{signing_team_name} signs {player_name} to a contract worth ${contract_value:,}."
    else:
        body = f"{signing_team_name} signs {player_name}."
    return send_message(team_id, "transaction", subject, body, db_path=db_path)


def send_draft_notification(team_id: int, player_name: str, round_num: int,
                           pick_num: int, team_name: str = None,
                           db_path: str = None) -> int:
    """Send a draft pick notification."""
    subject = f"Round {round_num}, Pick {pick_num}: {player_name}"
    if team_name:
        body = f"{team_name} selects {player_name} in Round {round_num}, Pick {pick_num}."
    else:
        body = f"{player_name} was selected in Round {round_num}, Pick {pick_num}."
    return send_message(team_id, "draft", subject, body, db_path=db_path)


def send_vesting_notification(team_id: int, player_name: str, condition: str,
                             new_salary: int = None, db_path: str = None) -> int:
    """Send a contract vesting notification."""
    subject = f"{player_name}'s Option Vested"
    condition_desc = {
        "500_pa": "500+ plate appearances",
        "150_games": "150+ games played",
        "50_starts": "50+ starts",
        "50_gs": "50+ games started",
    }.get(condition, condition)

    body = f"{player_name}'s contract option has vested based on {condition_desc}."
    if new_salary:
        body += f" New salary: ${new_salary:,}."

    return send_message(team_id, "milestone", subject, body, db_path=db_path)


def send_luxury_tax_notification(team_id: int, payroll: int, threshold: int,
                                 db_path: str = None) -> int:
    """Send a luxury tax warning."""
    subject = "Luxury Tax Threshold Exceeded"
    excess = payroll - threshold
    body = f"Your payroll (${payroll:,}) exceeds the luxury tax threshold (${threshold:,}) by ${excess:,}."
    return send_message(team_id, "financial", subject, body, db_path=db_path)


def send_qo_compensation_message(team_id: int, player_name: str,
                                 db_path: str = None) -> int:
    """Send a QO compensation pick notification."""
    subject = f"Compensation Pick: {player_name}"
    body = f"You have received a compensation draft pick for the loss of {player_name} to free agency."
    return send_message(team_id, "milestone", subject, body, db_path=db_path)


def get_unread_message_count(team_id: int, db_path: str = None) -> int:
    """Get the count of unread messages for a team."""
    result = query("""
        SELECT COUNT(*) as count FROM messages
        WHERE recipient_id=? AND recipient_type='user' AND is_read=0
    """, (team_id,), db_path=db_path)
    return result[0]["count"] if result else 0


def mark_message_as_read(message_id: int, db_path: str = None) -> bool:
    """Mark a message as read."""
    execute("UPDATE messages SET is_read=1 WHERE id=?", (message_id,), db_path=db_path)
    return True


def get_messages_for_team(team_id: int, unread_only: bool = False,
                         limit: int = 50, db_path: str = None) -> list:
    """Get messages for a team."""
    condition = "AND is_read=0" if unread_only else ""
    return query(f"""
        SELECT * FROM messages
        WHERE recipient_id=? AND recipient_type='user' {condition}
        ORDER BY game_date DESC, id DESC
        LIMIT ?
    """, (team_id, limit), db_path=db_path)
