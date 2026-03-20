"""
Front Office - AI-Initiated Trades
Daily automated trade logic for AI-controlled teams.
Pure algorithmic evaluation (no LLM calls) for batch processing speed.

Includes:
- AI-to-AI trades (auto-executed)
- AI-to-User trade proposals (sent as messages with accept/reject)
- Trading block response system (AI evaluates user's trading block players)
- Trade history logging
"""
import json
import random
from datetime import date
from ..database.db import get_connection, query, execute
from ..ai.proactive_messaging import send_trade_reaction_messages


def _row_get(row, key, default=None):
    """Safe .get() for sqlite3.Row objects."""
    try:
        val = row[key]
        return val if val is not None else default
    except (IndexError, KeyError):
        return default
from ..ai.gm_brain import _get_team_needs


def _calculate_player_value(player: dict) -> float:
    """Calculate a player's trade value based on ratings, age, and contract."""
    if player["position"] in ("SP", "RP"):
        base_value = (player["stuff_rating"] * 2 + player["control_rating"] * 1.5 +
                      player["stamina_rating"] * 0.5)
    else:
        base_value = (player["contact_rating"] * 1.5 + player["power_rating"] * 1.5 +
                      player["speed_rating"] * 0.5 + player["fielding_rating"] * 0.5)

    # Age adjustment: younger players are worth more
    age = _row_get(player, "age", 28)
    if age <= 25:
        base_value *= 1.2
    elif age <= 28:
        base_value *= 1.1
    elif age >= 33:
        base_value *= 0.8
    elif age >= 36:
        base_value *= 0.6

    # Contract value: cheaper players relative to value are worth more
    salary = _row_get(player, "annual_salary", 0)
    if salary > 20_000_000:
        base_value *= 0.85
    elif salary < 2_000_000:
        base_value *= 1.15

    return base_value


def _build_trade_package(conn, team_id: int, target_value: float,
                         needs: dict, db_path: str = None) -> list:
    """Build a package of players from team_id that approximates target_value.

    Offers players from positions of surplus (strongest positions).
    Returns list of player dicts or empty list if no fair package possible.
    """
    # Sort positions by strength (strongest first) - offer from surplus
    sorted_positions = sorted(needs.keys(), key=lambda p: needs[p], reverse=True)

    all_candidates = []
    for pos in sorted_positions[:4]:  # Check top 4 strongest positions
        players = conn.execute("""
            SELECT p.*, c.annual_salary, c.years_remaining
            FROM players p
            LEFT JOIN contracts c ON c.player_id = p.id
            WHERE p.team_id = ? AND p.roster_status = 'active'
            AND p.position = ?
            ORDER BY CASE WHEN p.position IN ('SP','RP')
                THEN p.stuff_rating + p.control_rating + p.stamina_rating
                ELSE p.contact_rating + p.power_rating + p.speed_rating + p.fielding_rating
            END DESC
        """, (team_id, pos)).fetchall()

        # Only offer if team has 2+ players at this position (keep at least 1)
        if len(players) >= 2:
            # Don't offer the best player at the position, offer 2nd-best onward
            all_candidates.extend(players[1:])

    if not all_candidates:
        return []

    # Sort candidates by value descending
    all_candidates.sort(key=lambda p: _calculate_player_value(p), reverse=True)

    # Build package to match target value (aim for 90-120% of target)
    offered = []
    offered_value = 0
    for p in all_candidates:
        pv = _calculate_player_value(p)
        offered.append(p)
        offered_value += pv
        if offered_value >= target_value * 0.90:
            break
        if len(offered) >= 3:  # Max 3 players in a package
            break

    if offered_value < target_value * 0.75:
        return []  # Can't make a fair offer

    return offered


def _format_player_details(player: dict) -> dict:
    """Format player info for trade offer message display."""
    result = {
        "id": player["id"],
        "name": f"{player['first_name']} {player['last_name']}",
        "position": player["position"],
        "age": _row_get(player, "age", 0),
    }
    if player["position"] in ("SP", "RP"):
        result["ratings"] = {
            "stuff": player["stuff_rating"],
            "control": player["control_rating"],
            "stamina": player["stamina_rating"],
        }
    else:
        result["ratings"] = {
            "contact": player["contact_rating"],
            "power": player["power_rating"],
            "speed": player["speed_rating"],
            "fielding": player["fielding_rating"],
        }
    salary = _row_get(player, "annual_salary", 0)
    if salary:
        result["salary"] = salary
    years = _row_get(player, "years_remaining")
    if years:
        result["years_remaining"] = years
    return result


def _send_trade_offer_to_user(conn, game_date: str, proposing_team_id: int,
                               user_team_id: int, target_player: dict,
                               offered_players: list, reason: str = "need") -> dict:
    """Send a structured trade offer message to the user's inbox.

    Stores full trade data in response_options_json so the frontend
    can render accept/reject buttons with the trade details.
    """
    team_info = conn.execute(
        "SELECT city, name FROM teams WHERE id=?", (proposing_team_id,)
    ).fetchone()
    team_name = f"{team_info['city']} {team_info['name']}"

    target_name = f"{target_player['first_name']} {target_player['last_name']}"
    offered_details = [_format_player_details(p) for p in offered_players]
    offered_names = ", ".join(d["name"] for d in offered_details)

    # Build detailed body
    body_lines = [
        f"The {team_name} would like to acquire {target_name} ({target_player['position']}).",
        "",
        "In return, we are offering:",
    ]
    for d in offered_details:
        ratings_str = ", ".join(f"{k.title()}: {v}" for k, v in d["ratings"].items())
        salary_str = f" (${d['salary']:,}/yr)" if d.get("salary") else ""
        body_lines.append(f"  - {d['name']} ({d['position']}, age {d['age']}){salary_str}")
        body_lines.append(f"    Ratings: {ratings_str}")

    body_lines.append("")
    body_lines.append("Would you like to accept this trade?")

    # Trade data stored for programmatic accept/reject
    trade_data = {
        "type": "trade_offer",
        "proposing_team_id": proposing_team_id,
        "proposing_team_name": team_name,
        "receiving_team_id": user_team_id,
        "players_offered": [p["id"] for p in offered_players],
        "players_offered_details": offered_details,
        "players_requested": [target_player["id"]],
        "players_requested_details": [_format_player_details(target_player)],
        "reason": reason,
    }

    response_options = {
        "options": ["Accept", "Decline"],
        "trade_data": trade_data,
    }

    conn.execute("""
        INSERT INTO messages (game_date, sender_type, sender_name,
            recipient_type, recipient_id, subject, body,
            requires_response, response_options_json)
        VALUES (?, 'gm', ?, 'user', ?, ?, ?, 1, ?)
    """, (
        game_date,
        f"{team_name} GM",
        user_team_id,
        f"Trade Offer: {target_name}",
        "\n".join(body_lines),
        json.dumps(response_options),
    ))

    return {
        "type": "proposal_to_user",
        "proposing_team_id": proposing_team_id,
        "proposing_team_name": team_name,
        "target_player": target_name,
        "offered_players": [d["name"] for d in offered_details],
    }


def _find_user_targets(conn, team_id: int, user_team_id: int,
                        needs: dict, db_path: str = None) -> list:
    """Find attractive trade targets on the user's team for a given AI team.

    Targets players where:
    1. The AI team has a positional need (weak spot)
    2. The user has surplus at that position (multiple good players)
    3. The player is on the trading block
    """
    targets = []

    # Check trading block first (highest priority)
    block_data = conn.execute(
        "SELECT trading_block_json FROM teams WHERE id=?", (user_team_id,)
    ).fetchone()

    trading_block_ids = []
    if block_data and block_data["trading_block_json"]:
        try:
            parsed = json.loads(block_data["trading_block_json"])
            if isinstance(parsed, dict):
                trading_block_ids = parsed.get("players", [])
            elif isinstance(parsed, list):
                trading_block_ids = parsed
        except (json.JSONDecodeError, TypeError):
            pass

    # Get positions where AI team is weak
    weak_positions = [pos for pos, score in needs.items() if score < 160]

    if not weak_positions:
        return []

    for pos in weak_positions:
        # Find user's players at this position
        user_players = conn.execute("""
            SELECT p.*, c.annual_salary, c.years_remaining, c.no_trade_clause
            FROM players p
            LEFT JOIN contracts c ON c.player_id = p.id
            WHERE p.team_id = ? AND p.position = ? AND p.roster_status = 'active'
            ORDER BY CASE WHEN p.position IN ('SP','RP')
                THEN p.stuff_rating + p.control_rating + p.stamina_rating
                ELSE p.contact_rating + p.power_rating + p.speed_rating + p.fielding_rating
            END DESC
        """, (user_team_id, pos)).fetchall()

        if not user_players:
            continue

        for player in user_players:
            # Check NTC
            from .contracts import check_no_trade_clause
            ntc_result = check_no_trade_clause(
                player["id"], destination_team_id=team_id,
                is_ai_trade=True, db_path=db_path
            )
            if ntc_result["blocked"]:
                continue

            priority = 0
            reason = "need"

            # Boost priority if player is on trading block
            if player["id"] in trading_block_ids:
                priority += 50
                reason = "trading_block"

            # Boost priority if user has surplus (2+ players at position)
            if len(user_players) >= 2:
                priority += 20
                reason = reason if reason == "trading_block" else "surplus"

            # Boost based on how badly AI team needs this position
            need_gap = 160 - needs[pos]
            priority += need_gap

            targets.append({
                "player": player,
                "priority": priority,
                "reason": reason,
            })

    # Sort by priority descending
    targets.sort(key=lambda t: t["priority"], reverse=True)
    return targets[:5]  # Return top 5 candidates


def _attempt_rebuilder_sell(conn, team_id: int, ai_team_ids: list,
                           user_team_id: int, team_records: dict,
                           season: int, db_path: str = None) -> dict:
    """Rebuilding team tries to sell an expiring-contract veteran to a contender.
    Returns trade result dict or None.
    """
    # Find veterans with 1 year or less on contract (rental candidates)
    rentals = conn.execute("""
        SELECT p.*, c.annual_salary, c.years_remaining
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND c.years_remaining <= 1 AND p.overall >= 55 AND p.age >= 27
        ORDER BY p.overall DESC
        LIMIT 5
    """, (team_id,)).fetchall()

    if not rentals:
        return None

    target = dict(random.choice(rentals[:3]))  # Pick from top 3
    target_value = _calculate_player_value(target)

    # Find contending teams interested in this position
    contender_ids = [
        tid for tid in ai_team_ids
        if tid != team_id and tid != user_team_id
        and team_records.get(tid, (0, 0))[0] / max(1, sum(team_records.get(tid, (0, 0)))) >= 0.520
    ]

    if not contender_ids:
        return None

    random.shuffle(contender_ids)

    for buyer_id in contender_ids[:5]:
        buyer_needs = _get_team_needs(buyer_id, db_path)
        pos_strength = buyer_needs.get(target["position"], 200)

        # Buyer wants this position?
        if pos_strength >= 200:
            continue

        # Build prospect package from buyer
        prospects = conn.execute("""
            SELECT p.*, c.annual_salary FROM players p
            LEFT JOIN contracts c ON c.player_id = p.id
            WHERE p.team_id=? AND p.age <= 25
            AND p.roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')
            ORDER BY p.overall DESC
            LIMIT 10
        """, (buyer_id,)).fetchall()

        if not prospects:
            continue

        # Package 1-2 prospects worth ~80-100% of veteran value
        package = []
        package_value = 0
        for prospect in prospects:
            p_dict = dict(prospect)
            p_val = _calculate_player_value(p_dict)
            package.append(p_dict)
            package_value += p_val
            if package_value >= target_value * 0.75:
                break

        if package_value < target_value * 0.50:
            continue

        # Execute trade
        for p in package:
            conn.execute("UPDATE players SET team_id=? WHERE id=?", (team_id, p["id"]))
            conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?", (team_id, p["id"]))

        conn.execute("UPDATE players SET team_id=? WHERE id=?", (buyer_id, target["id"]))
        conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?", (buyer_id, target["id"]))

        # Log transaction
        team1_info = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()
        team2_info = conn.execute("SELECT city, name FROM teams WHERE id=?", (buyer_id,)).fetchone()
        target_name = f"{target['first_name']} {target['last_name']}"
        package_names = [f"{p['first_name']} {p['last_name']}" for p in package]

        details = json.dumps({
            "type": "deadline_sell",
            "seller": f"{team1_info['city']} {team1_info['name']}" if team1_info else "",
            "buyer": f"{team2_info['city']} {team2_info['name']}" if team2_info else "",
            "veteran": target_name,
            "prospects": package_names,
        })

        conn.execute("""
            INSERT INTO transactions (team_id, transaction_type, player_id,
                                      details, transaction_date)
            VALUES (?, 'trade', ?, ?, ?)
        """, (team_id, target["id"], details, date.today().isoformat()))
        conn.execute("""
            INSERT INTO transactions (team_id, transaction_type, player_id,
                                      details, transaction_date)
            VALUES (?, 'trade', ?, ?, ?)
        """, (buyer_id, target["id"], details, date.today().isoformat()))

        conn.commit()

        return {
            "type": "deadline_trade",
            "seller_team": f"{team1_info['city']} {team1_info['name']}" if team1_info else str(team_id),
            "buyer_team": f"{team2_info['city']} {team2_info['name']}" if team2_info else str(buyer_id),
            "veteran": target_name,
            "prospects_received": package_names,
        }

    return None


def process_ai_trades(game_date: str, db_path: str = None) -> list:
    """
    Run daily AI trade logic. Each AI team has a small chance of proposing a trade.
    Returns list of executed trades (or user messages for user-team involvement).

    AI teams can:
    1. Trade with other AI teams (auto-executed)
    2. Propose trades TO the user's team (sent as inbox messages)
    3. Target user's trading block players with higher priority
    """
    conn = get_connection(db_path)
    executed_trades = []

    # Get user team to exclude from auto-execution
    state = conn.execute(
        "SELECT * FROM game_state WHERE id=1"
    ).fetchone()
    user_team_id = state["user_team_id"] if state else None
    season = state["season"] if state else 2026

    # Check trade deadline
    current_date = date.fromisoformat(game_date)
    deadline = date(season, 7, 31)
    if current_date > deadline:
        conn.close()
        return executed_trades  # No AI trades after deadline

    # Deadline urgency: trade frequency ramps up in July
    days_to_deadline = (deadline - current_date).days
    if days_to_deadline <= 3:
        trade_chance = 0.25  # Deadline frenzy: 25% daily
    elif days_to_deadline <= 14:
        trade_chance = 0.15  # Deadline push: 15% daily
    elif days_to_deadline <= 31:
        trade_chance = 0.08  # July heating up: 8% daily
    else:
        trade_chance = 0.05  # Normal: 5% daily

    # Get all AI teams with records for contender/rebuilder classification
    teams = conn.execute("SELECT id FROM teams").fetchall()
    ai_team_ids = [t["id"] for t in teams if t["id"] != user_team_id]

    # Calculate records from schedule (played games)
    team_records = {}
    for t in teams:
        tid = t["id"]
        wins = conn.execute("""
            SELECT COUNT(*) FROM schedule
            WHERE is_played=1 AND (
                (home_team_id=? AND home_score > away_score)
                OR (away_team_id=? AND away_score > home_score)
            )
        """, (tid, tid)).fetchone()[0]
        losses = conn.execute("""
            SELECT COUNT(*) FROM schedule
            WHERE is_played=1 AND (
                (home_team_id=? AND home_score < away_score)
                OR (away_team_id=? AND away_score < home_score)
            )
        """, (tid, tid)).fetchone()[0]
        team_records[tid] = (wins, losses)

    for team_id in ai_team_ids:
        if random.random() > trade_chance:
            continue

        wins, losses = team_records.get(team_id, (0, 0))
        total_games = wins + losses
        win_pct = wins / max(1, total_games)

        # Near deadline: contenders buy, rebuilders sell
        is_deadline_mode = days_to_deadline <= 31 and total_games >= 50
        is_contender = win_pct >= 0.540 and is_deadline_mode
        is_rebuilder = win_pct < 0.440 and is_deadline_mode

        # Get team needs
        needs = _get_team_needs(team_id, db_path)
        if not needs:
            continue

        # Rebuilders at deadline: try to sell veterans for prospects
        if is_rebuilder:
            rebuild_trade = _attempt_rebuilder_sell(conn, team_id, ai_team_ids,
                                                    user_team_id, team_records, season, db_path)
            if rebuild_trade:
                executed_trades.append(rebuild_trade)
            continue

        # Find biggest positional need (lowest rated position)
        weakest_pos = min(needs, key=lambda p: needs[p])
        weakest_score = needs[weakest_pos]

        # Contenders at deadline: lower the bar for accepting trades
        need_threshold = 200 if is_contender else 180
        if weakest_score >= need_threshold:
            continue

        # ---- PHASE 1: Check if user's team has good targets ----
        if user_team_id and random.random() < 0.40:  # 40% of trade attempts consider user's team
            user_targets = _find_user_targets(
                conn, team_id, user_team_id, needs, db_path
            )

            if user_targets:
                # Pick the best target
                best = user_targets[0]
                target = best["player"]
                target_value = _calculate_player_value(target)

                # Build an offer package
                offered = _build_trade_package(conn, team_id, target_value, needs, db_path)

                if offered:
                    result = _send_trade_offer_to_user(
                        conn, game_date, team_id, user_team_id,
                        target, offered, reason=best["reason"]
                    )
                    executed_trades.append(result)
                    continue  # This team made their move for the day

        # ---- PHASE 2: Standard AI-to-AI trade logic ----
        # Scan other AI teams for available players at the weak position
        candidates_raw = conn.execute("""
            SELECT p.*, c.annual_salary, c.years_remaining, c.no_trade_clause
            FROM players p
            LEFT JOIN contracts c ON c.player_id = p.id
            WHERE p.position = ? AND p.roster_status = 'active'
            AND p.team_id != ? AND p.team_id != ?
            ORDER BY CASE WHEN p.position IN ('SP','RP')
                THEN p.stuff_rating + p.control_rating + p.stamina_rating
                ELSE p.contact_rating + p.power_rating + p.speed_rating + p.fielding_rating
            END DESC
            LIMIT 20
        """, (weakest_pos, team_id, user_team_id or -1)).fetchall()

        # Filter through NTC / 10-and-5 checks
        from .contracts import check_no_trade_clause
        candidates = []
        for cand in candidates_raw:
            ntc_result = check_no_trade_clause(
                cand["id"], destination_team_id=team_id,
                is_ai_trade=True, db_path=db_path
            )
            if not ntc_result["blocked"]:
                candidates.append(cand)
            if len(candidates) >= 10:
                break

        if not candidates:
            continue

        # Pick a reasonable target (not the absolute best, more realistic)
        target_idx = random.randint(0, min(4, len(candidates) - 1))
        target = candidates[target_idx]
        target_team_id = target["team_id"]

        # Calculate target value
        target_value = _calculate_player_value(target)

        # Build trade package
        offered = _build_trade_package(conn, team_id, target_value, needs, db_path)

        if not offered:
            continue

        offered_value = sum(_calculate_player_value(p) for p in offered)

        # Check if the other AI team would accept (simple value comparison)
        other_needs = _get_team_needs(target_team_id, db_path)
        other_pos = offered[0]["position"] if offered else None

        # Other team accepts if they get value at a position of need
        other_pos_strength = other_needs.get(other_pos, 200) if other_pos else 200
        value_ratio = offered_value / max(1, target_value)

        # Accept if fair value and fills a need
        accept = value_ratio >= 0.85 and other_pos_strength < 200

        if not accept:
            continue

        # Execute the trade
        offered_ids = [p["id"] for p in offered]
        requested_ids = [target["id"]]

        for pid in offered_ids:
            conn.execute("UPDATE players SET team_id=? WHERE id=?", (target_team_id, pid))
            conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?", (target_team_id, pid))

        for pid in requested_ids:
            conn.execute("UPDATE players SET team_id=? WHERE id=?", (team_id, pid))
            conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?", (team_id, pid))

        # Build descriptive trade details for history
        offered_names = [f"{p['first_name']} {p['last_name']}" for p in offered]
        target_name = f"{target['first_name']} {target['last_name']}"
        team1_info = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()
        team2_info = conn.execute("SELECT city, name FROM teams WHERE id=?", (target_team_id,)).fetchone()

        details = {
            "proposing_team": team_id,
            "proposing_team_name": f"{team1_info['city']} {team1_info['name']}" if team1_info else "",
            "receiving_team": target_team_id,
            "receiving_team_name": f"{team2_info['city']} {team2_info['name']}" if team2_info else "",
            "players_to_receiving": offered_ids,
            "players_to_receiving_names": offered_names,
            "players_to_proposing": requested_ids,
            "players_to_proposing_names": [target_name],
            "cash": 0,
            "ai_initiated": True,
            "description": (
                f"{team1_info['city']} {team1_info['name']} traded "
                f"{', '.join(offered_names)} to "
                f"{team2_info['city']} {team2_info['name']} for {target_name}"
            ) if team1_info and team2_info else "",
        }
        conn.execute("""
            INSERT INTO transactions (transaction_date, transaction_type, details_json,
                team1_id, team2_id, player_ids)
            VALUES (?, 'trade', ?, ?, ?, ?)
        """, (game_date, json.dumps(details), team_id, target_team_id,
              ",".join(str(x) for x in offered_ids + requested_ids)))

        executed_trades.append({
            "type": "executed",
            "proposing_team_id": team_id,
            "receiving_team_id": target_team_id,
            "players_offered": offered_ids,
            "players_requested": requested_ids,
        })

    conn.commit()
    conn.close()
    return executed_trades


def process_trading_block_offers(game_date: str, db_path: str = None) -> list:
    """
    Process AI team trade offers for players on the user's trading block.

    AI teams evaluate trading block players against their needs and send
    real trade offers with actual player packages. Each trading block player
    has a 15% daily chance of attracting interest. Multiple teams can bid
    on the same player.

    Returns list of trade offers made.
    """
    state = query("SELECT user_team_id, season FROM game_state WHERE id=1", db_path=db_path)
    user_team_id = state[0]["user_team_id"] if state else None
    if not user_team_id:
        return []

    season = state[0]["season"] if state else 2026
    current_date = date.fromisoformat(game_date)
    deadline = date(season, 7, 31)
    if current_date > deadline:
        return []

    # Get user's trading block
    team = query("SELECT trading_block_json FROM teams WHERE id=?",
                (user_team_id,), db_path=db_path)

    if not team or not _row_get(team[0], "trading_block_json"):
        return []

    try:
        parsed = json.loads(team[0]["trading_block_json"])
    except (json.JSONDecodeError, TypeError):
        return []

    # Handle both formats: list of IDs or dict with "players" key
    if isinstance(parsed, dict):
        trading_block_ids = parsed.get("players", [])
    elif isinstance(parsed, list):
        trading_block_ids = parsed
    else:
        return []

    if not trading_block_ids:
        return []

    conn = get_connection(db_path)
    offers = []

    for player_id in trading_block_ids:
        # 15% daily chance per player (up from 10%, more responsive to trading block)
        if random.random() > 0.15:
            continue

        # Get player details
        player_row = conn.execute("""
            SELECT p.*, c.annual_salary, c.years_remaining, c.no_trade_clause
            FROM players p
            LEFT JOIN contracts c ON c.player_id = p.id
            WHERE p.id = ?
        """, (player_id,)).fetchone()

        if not player_row:
            continue

        player = dict(player_row)
        player_name = f"{player['first_name']} {player['last_name']}"
        target_value = _calculate_player_value(player)

        # Find AI teams that need this position
        ai_teams = conn.execute(
            "SELECT id, city, name FROM teams WHERE id != ?", (user_team_id,)
        ).fetchall()

        interested_teams = []
        for ai_team in ai_teams:
            team_needs = _get_team_needs(ai_team["id"], db_path)
            pos_strength = team_needs.get(player["position"], 200)
            if pos_strength < 170:  # Team has a need at this position
                interested_teams.append({
                    "team": ai_team,
                    "needs": team_needs,
                    "need_severity": 170 - pos_strength,
                })

        if not interested_teams:
            continue

        # Sort by need severity, pick 1-2 teams to make offers
        interested_teams.sort(key=lambda t: t["need_severity"], reverse=True)
        num_offers = min(random.randint(1, 2), len(interested_teams))

        for i in range(num_offers):
            ai_team_data = interested_teams[i]
            ai_team = ai_team_data["team"]
            ai_needs = ai_team_data["needs"]

            # Check NTC
            from .contracts import check_no_trade_clause
            ntc_result = check_no_trade_clause(
                player_id, destination_team_id=ai_team["id"],
                is_ai_trade=True, db_path=db_path
            )
            if ntc_result["blocked"]:
                continue

            # Build a real trade package
            offered = _build_trade_package(
                conn, ai_team["id"], target_value, ai_needs, db_path
            )

            if not offered:
                continue

            # Send the offer as a message
            result = _send_trade_offer_to_user(
                conn, game_date, ai_team["id"], user_team_id,
                player, offered, reason="trading_block"
            )
            offers.append(result)

    conn.commit()
    conn.close()
    return offers


def accept_trade_offer(message_id: int, db_path: str = None) -> dict:
    """Accept a trade offer from an AI team (called when user clicks Accept).

    Reads the trade data from the message's response_options_json,
    executes the trade, and records it in transactions.
    """
    conn = get_connection(db_path)

    # Get the message with trade data
    msg = conn.execute(
        "SELECT * FROM messages WHERE id=?", (message_id,)
    ).fetchone()

    if not msg:
        conn.close()
        return {"success": False, "error": "Message not found"}

    try:
        response_data = json.loads(msg["response_options_json"])
        trade_data = response_data.get("trade_data")
    except (json.JSONDecodeError, TypeError, KeyError):
        conn.close()
        return {"success": False, "error": "No trade data in message"}

    if not trade_data or trade_data.get("type") != "trade_offer":
        conn.close()
        return {"success": False, "error": "Message is not a trade offer"}

    proposing_team_id = trade_data["proposing_team_id"]
    receiving_team_id = trade_data["receiving_team_id"]
    players_offered = trade_data["players_offered"]
    players_requested = trade_data["players_requested"]

    # Validate players still belong to correct teams
    for pid in players_offered:
        p = conn.execute("SELECT team_id FROM players WHERE id=?", (pid,)).fetchone()
        if not p or p["team_id"] != proposing_team_id:
            conn.close()
            return {"success": False, "error": f"Player {pid} is no longer on the proposing team. Trade expired."}

    for pid in players_requested:
        p = conn.execute("SELECT team_id FROM players WHERE id=?", (pid,)).fetchone()
        if not p or p["team_id"] != receiving_team_id:
            conn.close()
            return {"success": False, "error": f"Player {pid} is no longer on your team. Trade expired."}

    # Execute the trade: move players
    for pid in players_offered:
        conn.execute("""UPDATE players SET team_id=?, roster_status='active'
                        WHERE id=? AND roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')""",
                    (receiving_team_id, pid))
        conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?",
                    (receiving_team_id, pid))

    for pid in players_requested:
        conn.execute("""UPDATE players SET team_id=?, roster_status='active'
                        WHERE id=? AND roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')""",
                    (proposing_team_id, pid))
        conn.execute("UPDATE contracts SET team_id=? WHERE player_id=?",
                    (proposing_team_id, pid))

    # Get game date and team names for the transaction log
    gs = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    game_date = gs["current_date"] if gs else date.today().isoformat()

    team1_info = conn.execute("SELECT city, name FROM teams WHERE id=?", (proposing_team_id,)).fetchone()
    team2_info = conn.execute("SELECT city, name FROM teams WHERE id=?", (receiving_team_id,)).fetchone()

    # Get player names for description
    offered_names = []
    for pid in players_offered:
        p = conn.execute("SELECT first_name, last_name FROM players WHERE id=?", (pid,)).fetchone()
        if p:
            offered_names.append(f"{p['first_name']} {p['last_name']}")

    requested_names = []
    for pid in players_requested:
        p = conn.execute("SELECT first_name, last_name FROM players WHERE id=?", (pid,)).fetchone()
        if p:
            requested_names.append(f"{p['first_name']} {p['last_name']}")

    details = {
        "proposing_team": proposing_team_id,
        "proposing_team_name": f"{team1_info['city']} {team1_info['name']}" if team1_info else "",
        "receiving_team": receiving_team_id,
        "receiving_team_name": f"{team2_info['city']} {team2_info['name']}" if team2_info else "",
        "players_to_receiving": players_offered,
        "players_to_receiving_names": offered_names,
        "players_to_proposing": players_requested,
        "players_to_proposing_names": requested_names,
        "cash": 0,
        "ai_initiated": True,
        "accepted_by_user": True,
        "description": (
            f"{team1_info['city']} {team1_info['name']} traded "
            f"{', '.join(offered_names)} to "
            f"{team2_info['city']} {team2_info['name']} for "
            f"{', '.join(requested_names)}"
        ) if team1_info and team2_info else "",
    }

    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, team2_id, player_ids)
        VALUES (?, 'trade', ?, ?, ?, ?)
    """, (game_date, json.dumps(details), proposing_team_id, receiving_team_id,
          ",".join(str(x) for x in players_offered + players_requested)))

    # Mark the message as read and responded to
    conn.execute("UPDATE messages SET is_read=1, requires_response=0 WHERE id=?",
                (message_id,))

    # Remove accepted player from trading block if they were on it
    block = conn.execute(
        "SELECT trading_block_json FROM teams WHERE id=?", (receiving_team_id,)
    ).fetchone()
    if block and block["trading_block_json"]:
        try:
            parsed = json.loads(block["trading_block_json"])
            if isinstance(parsed, dict):
                player_list = parsed.get("players", [])
                for pid in players_requested:
                    if pid in player_list:
                        player_list.remove(pid)
                parsed["players"] = player_list
                conn.execute("UPDATE teams SET trading_block_json=? WHERE id=?",
                            (json.dumps(parsed), receiving_team_id))
            elif isinstance(parsed, list):
                for pid in players_requested:
                    if pid in parsed:
                        parsed.remove(pid)
                conn.execute("UPDATE teams SET trading_block_json=? WHERE id=?",
                            (json.dumps(parsed), receiving_team_id))
        except (json.JSONDecodeError, TypeError):
            pass

    conn.commit()
    conn.close()

    # Trigger beat writer and owner reactions
    try:
        user_team_name = f"{team2_info['city']} {team2_info['name']}" if team2_info else "Your Team"
        other_team_name = f"{team1_info['city']} {team1_info['name']}" if team1_info else "Other Team"

        trade_reaction_details = {
            "offered_names": requested_names,   # What the user gave up
            "requested_names": offered_names,    # What the user received
            "team_name": user_team_name,
            "other_team_name": other_team_name,
        }
        send_trade_reaction_messages(
            receiving_team_id, game_date, trade_reaction_details, db_path=db_path
        )
    except Exception:
        pass  # Don't let reaction failures break trade acceptance

    return {
        "success": True,
        "details": details,
        "message": f"Trade completed! {', '.join(requested_names)} traded for {', '.join(offered_names)}."
    }


def decline_trade_offer(message_id: int, db_path: str = None) -> dict:
    """Decline a trade offer from an AI team."""
    execute("UPDATE messages SET is_read=1, requires_response=0 WHERE id=?",
            (message_id,), db_path=db_path)
    return {"success": True, "message": "Trade offer declined."}


def get_trade_history(season: int = None, db_path: str = None) -> list:
    """Get all completed trades for a season with formatted descriptions.

    Returns a list of trade records with human-readable descriptions.
    """
    if season is None:
        state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
        season = state[0]["season"] if state else 2026

    trades = query("""
        SELECT t.*,
               t1.city as team1_city, t1.name as team1_name, t1.abbreviation as team1_abbr,
               t2.city as team2_city, t2.name as team2_name, t2.abbreviation as team2_abbr
        FROM transactions t
        LEFT JOIN teams t1 ON t1.id = t.team1_id
        LEFT JOIN teams t2 ON t2.id = t.team2_id
        WHERE t.transaction_type = 'trade'
        AND t.transaction_date >= ? AND t.transaction_date <= ?
        ORDER BY t.transaction_date DESC, t.id DESC
    """, (f"{season}-01-01", f"{season}-12-31"), db_path=db_path)

    if not trades:
        return []

    results = []
    for trade in trades:
        entry = {
            "id": trade["id"],
            "date": trade["transaction_date"],
            "team1_id": trade["team1_id"],
            "team1_name": f"{trade['team1_city']} {trade['team1_name']}" if trade.get("team1_city") else "",
            "team1_abbr": trade.get("team1_abbr", ""),
            "team2_id": trade["team2_id"],
            "team2_name": f"{trade['team2_city']} {trade['team2_name']}" if trade.get("team2_city") else "",
            "team2_abbr": trade.get("team2_abbr", ""),
        }

        # Parse details for player names and description
        try:
            details = json.loads(trade.get("details_json", "{}"))
            entry["description"] = details.get("description", "")

            # If no pre-built description, build one from player IDs
            if not entry["description"]:
                players_to_receiving = details.get("players_to_receiving", [])
                players_to_proposing = details.get("players_to_proposing", [])

                # Look up player names
                to_receiving_names = details.get("players_to_receiving_names", [])
                to_proposing_names = details.get("players_to_proposing_names", [])

                if not to_receiving_names:
                    for pid in players_to_receiving:
                        p = query("SELECT first_name, last_name FROM players WHERE id=?",
                                 (pid,), db_path=db_path)
                        if p:
                            to_receiving_names.append(f"{p[0]['first_name']} {p[0]['last_name']}")

                if not to_proposing_names:
                    for pid in players_to_proposing:
                        p = query("SELECT first_name, last_name FROM players WHERE id=?",
                                 (pid,), db_path=db_path)
                        if p:
                            to_proposing_names.append(f"{p[0]['first_name']} {p[0]['last_name']}")

                team1 = entry["team1_name"] or "Team A"
                team2 = entry["team2_name"] or "Team B"

                if to_receiving_names and to_proposing_names:
                    entry["description"] = (
                        f"{team1} traded {', '.join(to_receiving_names)} to "
                        f"{team2} for {', '.join(to_proposing_names)}"
                    )

            entry["players_to_team1"] = details.get("players_to_proposing_names",
                                                      details.get("players_to_proposing", []))
            entry["players_to_team2"] = details.get("players_to_receiving_names",
                                                      details.get("players_to_receiving", []))
            entry["cash"] = details.get("cash", 0)
            entry["ai_initiated"] = details.get("ai_initiated", False)
        except (json.JSONDecodeError, TypeError):
            entry["description"] = ""
            entry["players_to_team1"] = []
            entry["players_to_team2"] = []
            entry["cash"] = 0
            entry["ai_initiated"] = False

        results.append(entry)

    return results
