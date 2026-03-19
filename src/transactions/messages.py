"""
Front Office - Messages and Notifications System
Helper functions for sending notifications about key game events.
Supports priority inbox with categorized messages.
"""
from datetime import date
from ..database.db import execute, query, get_connection

# Priority mapping by category - determines default priority for each message category
CATEGORY_PRIORITY_MAP = {
    "trade_offer": "urgent",
    "owner": "important",
    "injury": "important",
    "transaction": "normal",
    "draft": "normal",
    "financial": "normal",
    "milestone": "normal",
    "general": "low",
}


def send_message(team_id: int, category: str, subject: str, body: str,
                 game_date: str = None, priority: str = None,
                 db_path: str = None) -> int:
    """
    Send a message/notification to the user's team.

    Args:
        team_id: ID of the recipient team
        category: Message category (trade_offer, injury, transaction, draft, milestone, financial, owner)
        subject: Short message subject
        body: Full message body
        game_date: Date of the message (defaults to current game date)
        priority: Message priority (urgent, important, normal, low). Auto-derived from category if not set.
        db_path: Database path

    Returns:
        The message ID
    """
    if game_date is None:
        state = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
        game_date = state[0]["current_date"] if state else date.today().isoformat()

    if priority is None:
        priority = CATEGORY_PRIORITY_MAP.get(category, "normal")

    execute("""
        INSERT INTO messages (game_date, sender_type, sender_name, recipient_type,
                             recipient_id, subject, body, is_read, requires_response,
                             priority, category)
        VALUES (?, 'system', 'Front Office', 'user', ?, ?, ?, 0, 0, ?, ?)
    """, (game_date, team_id, subject, body, priority, category), db_path=db_path)

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

    return send_message(receiving_team_id, "trade_offer", subject, body,
                        priority="urgent", db_path=db_path)


def send_injury_message(team_id: int, player_name: str, il_tier: str,
                       db_path: str = None) -> int:
    """Send an injury notification."""
    subject = f"{player_name} Placed on IL"
    body = f"{player_name} has been placed on the {il_tier}-day injured list."
    return send_message(team_id, "injury", subject, body,
                        priority="important", db_path=db_path)


def send_injury_activation_message(team_id: int, player_name: str,
                                   db_path: str = None) -> int:
    """Send an injury activation notification."""
    subject = f"{player_name} Activated"
    body = f"{player_name} has been activated from the injured list."
    return send_message(team_id, "injury", subject, body,
                        priority="important", db_path=db_path)


def send_free_agent_signing_message(team_id: int, player_name: str,
                                    signing_team_name: str, contract_value: int = None,
                                    db_path: str = None) -> int:
    """Send a free agent signing notification."""
    subject = f"{player_name} Signed"
    if contract_value:
        body = f"{signing_team_name} signs {player_name} to a contract worth ${contract_value:,}."
    else:
        body = f"{signing_team_name} signs {player_name}."
    return send_message(team_id, "transaction", subject, body,
                        priority="normal", db_path=db_path)


def send_draft_notification(team_id: int, player_name: str, round_num: int,
                           pick_num: int, team_name: str = None,
                           db_path: str = None) -> int:
    """Send a draft pick notification."""
    subject = f"Round {round_num}, Pick {pick_num}: {player_name}"
    if team_name:
        body = f"{team_name} selects {player_name} in Round {round_num}, Pick {pick_num}."
    else:
        body = f"{player_name} was selected in Round {round_num}, Pick {pick_num}."
    return send_message(team_id, "draft", subject, body,
                        priority="normal", db_path=db_path)


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

    return send_message(team_id, "milestone", subject, body,
                        priority="normal", db_path=db_path)


def send_luxury_tax_notification(team_id: int, payroll: int, threshold: int,
                                 db_path: str = None) -> int:
    """Send a luxury tax warning."""
    subject = "Luxury Tax Threshold Exceeded"
    excess = payroll - threshold
    body = f"Your payroll (${payroll:,}) exceeds the luxury tax threshold (${threshold:,}) by ${excess:,}."
    return send_message(team_id, "financial", subject, body,
                        priority="normal", db_path=db_path)


def send_qo_compensation_message(team_id: int, player_name: str,
                                 db_path: str = None) -> int:
    """Send a QO compensation pick notification."""
    subject = f"Compensation Pick: {player_name}"
    body = f"You have received a compensation draft pick for the loss of {player_name} to free agency."
    return send_message(team_id, "milestone", subject, body,
                        priority="normal", db_path=db_path)


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
                         priority: str = None, limit: int = 50,
                         db_path: str = None) -> list:
    """Get messages for a team, optionally filtered by priority."""
    # Check if priority column exists
    from ..database.db import get_connection
    conn = get_connection(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()]
    conn.close()
    has_priority = "priority" in cols

    conditions = []
    params = [team_id]

    if unread_only:
        conditions.append("AND is_read=0")
    if priority and has_priority:
        conditions.append("AND priority=?")
        params.append(priority)

    params.append(limit)
    condition_str = " ".join(conditions)

    if has_priority:
        order_clause = """ORDER BY
            CASE priority
                WHEN 'urgent' THEN 0
                WHEN 'important' THEN 1
                WHEN 'normal' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            game_date DESC, id DESC"""
    else:
        order_clause = "ORDER BY game_date DESC, id DESC"

    return query(f"""
        SELECT * FROM messages
        WHERE recipient_id=? AND recipient_type='user' {condition_str}
        {order_clause}
        LIMIT ?
    """, tuple(params), db_path=db_path)


def get_messages_by_priority(team_id: int, priority: str = None,
                             db_path: str = None) -> list:
    """
    Get messages filtered by priority level.

    Args:
        team_id: ID of the team
        priority: Filter by priority (urgent, important, normal, low). None returns all.
        db_path: Database path

    Returns:
        List of messages sorted by priority then date
    """
    return get_messages_for_team(team_id, priority=priority, db_path=db_path)


def get_message_priorities(team_id: int, db_path: str = None) -> dict:
    """
    Get message counts grouped by priority level.

    Args:
        team_id: ID of the team
        db_path: Database path

    Returns:
        Dict with priority counts, e.g. {'urgent': 2, 'important': 5, 'normal': 10, 'low': 3}
    """
    # Check if priority column exists
    from ..database.db import get_connection
    conn = get_connection(db_path)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(messages)").fetchall()]
    conn.close()

    if "priority" not in cols:
        # No priority column - count all as normal
        total_rows = query("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN is_read=0 THEN 1 ELSE 0 END) as unread
            FROM messages WHERE recipient_id=? AND recipient_type='user'
        """, (team_id,), db_path=db_path)
        total = total_rows[0]["total"] if total_rows else 0
        unread = total_rows[0]["unread"] if total_rows else 0
        return {
            "urgent": {"total": 0, "unread": 0},
            "important": {"total": 0, "unread": 0},
            "normal": {"total": total, "unread": unread},
            "low": {"total": 0, "unread": 0},
        }

    rows = query("""
        SELECT COALESCE(priority, 'normal') as priority,
               COUNT(*) as total,
               SUM(CASE WHEN is_read=0 THEN 1 ELSE 0 END) as unread
        FROM messages
        WHERE recipient_id=? AND recipient_type='user'
        GROUP BY COALESCE(priority, 'normal')
    """, (team_id,), db_path=db_path)

    result = {
        "urgent": {"total": 0, "unread": 0},
        "important": {"total": 0, "unread": 0},
        "normal": {"total": 0, "unread": 0},
        "low": {"total": 0, "unread": 0},
    }
    for row in (rows or []):
        p = row["priority"]
        if p in result:
            result[p] = {"total": row["total"], "unread": row["unread"]}

    return result


def get_message_categories(team_id: int, db_path: str = None) -> dict:
    """
    Get message counts grouped by category.

    Args:
        team_id: ID of the team
        db_path: Database path

    Returns:
        Dict with category counts, e.g. {'trade_offer': {'total': 2, 'unread': 1}, ...}
    """
    rows = query("""
        SELECT COALESCE(category, 'general') as category,
               COUNT(*) as total,
               SUM(CASE WHEN is_read=0 THEN 1 ELSE 0 END) as unread
        FROM messages
        WHERE recipient_id=? AND recipient_type='user'
        GROUP BY COALESCE(category, 'general')
    """, (team_id,), db_path=db_path)

    result = {}
    for row in (rows or []):
        result[row["category"]] = {"total": row["total"], "unread": row["unread"]}

    return result
