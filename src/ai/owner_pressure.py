"""
Front Office - Owner Pressure & Job Security System
Phase 2: Owner sets objectives, evaluates GM performance, and can fire the player.
"""
import random
from ..database.db import query, execute
from ..transactions.messages import send_message


# ============================================================
# OBJECTIVE SETTING
# ============================================================

def set_owner_objectives(team_id: int, season: int, db_path: str = None) -> list:
    """
    Owner sets 2-4 objectives for the season based on owner personality and team quality.

    Returns list of objectives created.
    """
    # Get owner character
    owner = query(
        "SELECT * FROM owner_characters WHERE team_id=?",
        (team_id,), db_path=db_path
    )
    if not owner:
        return []
    owner = owner[0]

    # Get team info
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return []
    team = team[0]

    # Estimate team quality from roster ratings
    roster_strength = _estimate_team_strength(team_id, db_path)
    archetype = owner["archetype"]
    market_size = team["market_size"]

    # Clear any existing active objectives for this season
    execute(
        "DELETE FROM owner_objectives WHERE team_id=? AND season=? AND status='active'",
        (team_id, season), db_path=db_path
    )

    objectives = []

    # Determine objectives based on archetype + team quality + market size
    if archetype == "win_now" or (archetype == "ego_meddler" and roster_strength >= 60):
        # Aggressive win-now owners
        if market_size >= 4:
            objectives.append(("win_ws", None, 1))
        else:
            objectives.append(("win_division", None, 1))
        objectives.append(("make_playoffs", None, 2))
        if roster_strength >= 70:
            objectives.append(("win_ws", None, 2))

    elif archetype == "budget_conscious":
        # Cost-cutters
        objectives.append(("cut_payroll", "$120M", 1))
        if roster_strength >= 50:
            objectives.append(("make_playoffs", None, 2))
        else:
            objectives.append(("develop_prospects", "3", 2))
        objectives.append(("be_profitable", None, 1))

    elif archetype == "patient_builder":
        # Long-term thinkers
        objectives.append(("develop_prospects", "3", 1))
        if roster_strength >= 55:
            objectives.append(("make_playoffs", None, 2))
        else:
            objectives.append(("rebuild", None, 2))
        objectives.append(("cut_payroll", "$150M", 3))

    elif archetype == "competitive_small_market":
        # Small market but wants to win
        objectives.append(("make_playoffs", None, 1))
        objectives.append(("develop_prospects", "2", 2))
        objectives.append(("be_profitable", None, 2))

    elif archetype == "legacy_inheritor":
        # Inherited team, moderate expectations
        if roster_strength >= 55:
            objectives.append(("make_playoffs", None, 1))
        else:
            objectives.append(("rebuild", None, 2))
        objectives.append(("develop_prospects", "2", 2))

    elif archetype == "ego_meddler":
        # Meddling owner, wants flashy results
        objectives.append(("win_division", None, 1))
        objectives.append(("make_playoffs", None, 1))

    else:
        # Balanced / default
        if roster_strength >= 65:
            objectives.append(("win_division", None, 1))
            objectives.append(("make_playoffs", None, 2))
        elif roster_strength >= 45:
            objectives.append(("make_playoffs", None, 1))
            objectives.append(("develop_prospects", "2", 2))
        else:
            objectives.append(("rebuild", None, 1))
            objectives.append(("develop_prospects", "3", 2))

    # Big market bonus objective
    if market_size >= 4 and ("win_ws", None, 1) not in objectives:
        objectives.append(("win_ws", None, 3))

    # Cap at 4 objectives
    objectives = objectives[:4]

    # Insert into database
    created = []
    for obj_type, target, priority in objectives:
        execute("""
            INSERT INTO owner_objectives (team_id, season, objective_type, target_value, priority, status)
            VALUES (?, ?, ?, ?, ?, 'active')
        """, (team_id, season, obj_type, target, priority), db_path=db_path)
        created.append({
            "team_id": team_id,
            "season": season,
            "objective_type": obj_type,
            "target_value": target,
            "priority": priority,
            "status": "active"
        })

    # Initialize job security if not present
    _ensure_job_security_exists(team_id, db_path)

    # Send owner message about objectives
    owner_name = f"{owner['first_name']} {owner['last_name']}"
    obj_descriptions = [_describe_objective(o["objective_type"], o["target_value"], o["priority"])
                        for o in created]
    body = (
        f"From: {owner_name} (Owner)\n\n"
        f"Here are my expectations for the {season} season:\n\n"
        + "\n".join(f"  {i+1}. {desc}" for i, desc in enumerate(obj_descriptions))
        + "\n\nDon't disappoint me."
    )
    send_message(team_id, "owner", f"Season {season} Objectives", body, db_path=db_path)

    return created


def _estimate_team_strength(team_id: int, db_path: str = None) -> int:
    """Estimate team strength on a 0-100 scale from roster ratings."""
    result = query("""
        SELECT AVG(
            CASE WHEN position IN ('SP','RP')
                THEN (stuff_rating + control_rating + stamina_rating) / 3.0
                ELSE (contact_rating + power_rating + speed_rating + fielding_rating + arm_rating) / 5.0
            END
        ) as avg_rating
        FROM players
        WHERE team_id=? AND roster_status='active'
    """, (team_id,), db_path=db_path)
    if result and result[0]["avg_rating"] is not None:
        # Convert 20-80 scale average to 0-100 strength
        avg = result[0]["avg_rating"]
        return max(0, min(100, int((avg - 20) / 60 * 100)))
    return 50


def _describe_objective(obj_type: str, target: str, priority: int) -> str:
    """Human-readable objective description."""
    priority_label = {1: "[CRITICAL]", 2: "[Important]", 3: "[Nice to have]"}
    label = priority_label.get(priority, "")

    descriptions = {
        "win_division": "Win the division",
        "make_playoffs": "Make the playoffs",
        "win_ws": "Win the World Series",
        "rebuild": "Commit to a rebuild - develop young talent",
        "cut_payroll": f"Cut payroll to {target}" if target else "Reduce payroll",
        "develop_prospects": f"Develop at least {target} top prospects" if target else "Develop prospects",
        "be_profitable": "Keep the franchise profitable",
    }
    desc = descriptions.get(obj_type, obj_type)
    return f"{label} {desc}"


def _ensure_job_security_exists(team_id: int, db_path: str = None):
    """Create gm_job_security row if it doesn't exist."""
    existing = query("SELECT id FROM gm_job_security WHERE id=1", db_path=db_path)
    if not existing:
        # Get owner patience from owner_characters
        owner = query(
            "SELECT patience FROM owner_characters WHERE team_id=?",
            (team_id,), db_path=db_path
        )
        patience = owner[0]["patience"] if owner else 50
        execute("""
            INSERT OR IGNORE INTO gm_job_security
                (id, team_id, security_score, owner_patience, owner_mood)
            VALUES (1, ?, 70, ?, 'neutral')
        """, (team_id, patience), db_path=db_path)


# ============================================================
# PERFORMANCE EVALUATION
# ============================================================

def evaluate_gm_performance(team_id: int, db_path: str = None) -> dict:
    """
    End-of-season evaluation. Updates security_score and owner_mood.

    Returns evaluation summary dict.
    """
    _ensure_job_security_exists(team_id, db_path)

    security = query("SELECT * FROM gm_job_security WHERE id=1", db_path=db_path)
    if not security:
        return {"error": "No job security record"}
    security = security[0]

    state = query("SELECT current_date, season FROM game_state WHERE id=1", db_path=db_path)
    if not state:
        return {"error": "No game state"}
    season = state[0]["season"]
    current_date = state[0]["current_date"]

    score = security["security_score"]
    changes = []

    # --- Evaluate objectives ---
    objectives = query(
        "SELECT * FROM owner_objectives WHERE team_id=? AND season=? AND status='active'",
        (team_id, season), db_path=db_path
    )

    team_record = _get_team_record(team_id, season, db_path)
    wins = team_record["wins"]
    losses = team_record["losses"]
    made_playoffs = _check_made_playoffs(team_id, season, db_path)
    won_ws = _check_won_world_series(team_id, season, db_path)

    for obj in objectives:
        obj_met = _check_objective_met(obj, team_id, season, wins, losses,
                                       made_playoffs, won_ws, db_path)
        priority = obj["priority"]

        if obj_met:
            bonus = {1: 25, 2: 20, 3: 15}.get(priority, 15)
            score += bonus
            changes.append(f"+{bonus}: Met objective '{obj['objective_type']}'")
            execute(
                "UPDATE owner_objectives SET status='met' WHERE id=?",
                (obj["id"],), db_path=db_path
            )
        else:
            penalty = {1: -20, 2: -15, 3: -10}.get(priority, -10)
            score += penalty
            changes.append(f"{penalty}: Failed objective '{obj['objective_type']}'")
            execute(
                "UPDATE owner_objectives SET status='failed' WHERE id=?",
                (obj["id"],), db_path=db_path
            )

    # --- Record bonuses/penalties ---
    if wins > losses:
        score += 5
        changes.append("+5: Winning record")
    elif losses > wins:
        score -= 5
        changes.append("-5: Losing record")

    if made_playoffs:
        score += 15
        changes.append("+15: Made playoffs")

    if won_ws:
        score += 30
        changes.append("+30: Won World Series")

    # Consecutive losing seasons
    consecutive = security["consecutive_losing_seasons"]
    if losses > wins:
        consecutive += 1
    else:
        consecutive = 0

    if consecutive > 0:
        penalty = consecutive * -10
        score += penalty
        changes.append(f"{penalty}: {consecutive} consecutive losing season(s)")

    # Playoff appearances tracking
    playoff_apps = security["playoff_appearances"]
    if made_playoffs:
        playoff_apps += 1

    # Luxury tax check
    payroll = _get_team_payroll(team_id, db_path)
    luxury_threshold = 230_000_000  # Approximate MLB luxury tax threshold
    if payroll > luxury_threshold:
        score -= 5
        changes.append("-5: Over luxury tax threshold")

    # Fan sentiment (based on fan_loyalty from teams table)
    team = query("SELECT fan_loyalty FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if team:
        fan_loyalty = team[0]["fan_loyalty"]
        if fan_loyalty >= 70:
            score += 5
            changes.append("+5: High fan sentiment")
        elif fan_loyalty <= 30:
            score -= 5
            changes.append("-5: Low fan sentiment")

    # Owner patience affects thresholds - patient owners soften penalties
    patience = security["owner_patience"]
    if patience >= 70:
        # Patient owner: recover a bit
        score += 5
        changes.append("+5: Patient owner bonus")
    elif patience <= 30:
        # Impatient owner: harsher
        score -= 5
        changes.append("-5: Impatient owner penalty")

    # Clamp score
    score = max(0, min(100, score))

    # Determine mood
    mood = _score_to_mood(score)

    # Update database
    execute("""
        UPDATE gm_job_security SET
            security_score=?,
            owner_mood=?,
            consecutive_losing_seasons=?,
            playoff_appearances=?,
            last_evaluation_date=?
        WHERE id=1
    """, (score, mood, consecutive, playoff_apps, current_date), db_path=db_path)

    # Send evaluation message
    _send_evaluation_message(team_id, score, mood, changes, season, db_path)

    return {
        "security_score": score,
        "owner_mood": mood,
        "consecutive_losing_seasons": consecutive,
        "playoff_appearances": playoff_apps,
        "changes": changes,
        "record": f"{wins}-{losses}",
        "made_playoffs": made_playoffs,
        "won_world_series": won_ws
    }


def _get_team_record(team_id: int, season: int, db_path: str = None) -> dict:
    """Get team W-L record for the season."""
    wins_result = query("""
        SELECT COUNT(*) as w FROM schedule
        WHERE season=? AND is_played=1 AND is_postseason=0
        AND (
            (home_team_id=? AND home_score > away_score)
            OR (away_team_id=? AND away_score > home_score)
        )
    """, (season, team_id, team_id), db_path=db_path)

    losses_result = query("""
        SELECT COUNT(*) as l FROM schedule
        WHERE season=? AND is_played=1 AND is_postseason=0
        AND (
            (home_team_id=? AND home_score < away_score)
            OR (away_team_id=? AND away_score < home_score)
        )
    """, (season, team_id, team_id), db_path=db_path)

    wins = wins_result[0]["w"] if wins_result else 0
    losses = losses_result[0]["l"] if losses_result else 0
    return {"wins": wins, "losses": losses}


def _check_made_playoffs(team_id: int, season: int, db_path: str = None) -> bool:
    """Check if team made the playoffs."""
    result = query("""
        SELECT COUNT(*) as cnt FROM playoff_bracket
        WHERE season=? AND (higher_seed_id=? OR lower_seed_id=?)
    """, (season, team_id, team_id), db_path=db_path)
    return result[0]["cnt"] > 0 if result else False


def _check_won_world_series(team_id: int, season: int, db_path: str = None) -> bool:
    """Check if team won the World Series."""
    result = query("""
        SELECT winner_id FROM playoff_bracket
        WHERE season=? AND round='world_series' AND is_complete=1
    """, (season,), db_path=db_path)
    return result[0]["winner_id"] == team_id if result else False


def _check_objective_met(obj: dict, team_id: int, season: int,
                         wins: int, losses: int,
                         made_playoffs: bool, won_ws: bool,
                         db_path: str = None) -> bool:
    """Check if a specific objective was met."""
    obj_type = obj["objective_type"]
    target = obj["target_value"]

    if obj_type == "win_division":
        # Check if team won their division (top record in division)
        team = query("SELECT league, division FROM teams WHERE id=?",
                     (team_id,), db_path=db_path)
        if not team:
            return False
        league, division = team[0]["league"], team[0]["division"]
        # Get all teams in division and check if this team has the best record
        div_teams = query(
            "SELECT id FROM teams WHERE league=? AND division=?",
            (league, division), db_path=db_path
        )
        best_wins = 0
        best_team = None
        for dt in div_teams:
            rec = _get_team_record(dt["id"], season, db_path)
            if rec["wins"] > best_wins:
                best_wins = rec["wins"]
                best_team = dt["id"]
        return best_team == team_id

    elif obj_type == "make_playoffs":
        return made_playoffs

    elif obj_type == "win_ws":
        return won_ws

    elif obj_type == "rebuild":
        # Rebuild is "met" if team has young talent developing
        young_talent = query("""
            SELECT COUNT(*) as cnt FROM players
            WHERE team_id=? AND age <= 25 AND roster_status IN ('active', 'minors_aaa', 'minors_aa')
            AND (contact_potential >= 60 OR power_potential >= 60
                 OR stuff_potential >= 60 OR control_potential >= 60)
        """, (team_id,), db_path=db_path)
        return young_talent[0]["cnt"] >= 3 if young_talent else False

    elif obj_type == "cut_payroll":
        payroll = _get_team_payroll(team_id, db_path)
        if target:
            # Parse target like "$150M"
            target_val = _parse_money(target)
            return payroll <= target_val
        return payroll <= 120_000_000

    elif obj_type == "develop_prospects":
        # Count prospects who improved significantly
        target_count = int(target) if target else 2
        prospects = query("""
            SELECT COUNT(*) as cnt FROM players
            WHERE team_id=? AND age <= 25
            AND roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')
            AND (contact_potential >= 55 OR power_potential >= 55
                 OR stuff_potential >= 55 OR control_potential >= 55)
        """, (team_id,), db_path=db_path)
        return prospects[0]["cnt"] >= target_count if prospects else False

    elif obj_type == "be_profitable":
        # Check financial history
        fin = query(
            "SELECT profit FROM financial_history WHERE team_id=? AND season=?",
            (team_id, season), db_path=db_path
        )
        return fin[0]["profit"] >= 0 if fin else True  # Default to met if no data

    return False


def _get_team_payroll(team_id: int, db_path: str = None) -> int:
    """Get total team payroll from active contracts."""
    result = query("""
        SELECT COALESCE(SUM(c.annual_salary), 0) as payroll
        FROM contracts c
        JOIN players p ON c.player_id = p.id
        WHERE c.team_id=? AND p.roster_status != 'retired'
    """, (team_id,), db_path=db_path)
    return result[0]["payroll"] if result else 0


def _parse_money(val: str) -> int:
    """Parse money string like '$150M' to integer."""
    val = val.strip().replace("$", "").replace(",", "")
    if val.upper().endswith("M"):
        return int(float(val[:-1]) * 1_000_000)
    elif val.upper().endswith("K"):
        return int(float(val[:-1]) * 1_000)
    try:
        return int(val)
    except ValueError:
        return 150_000_000


def _score_to_mood(score: int) -> str:
    """Convert security score to owner mood."""
    if score >= 90:
        return "elated"
    elif score >= 70:
        return "happy"
    elif score >= 50:
        return "neutral"
    elif score >= 30:
        return "concerned"
    elif score >= 15:
        return "angry"
    else:
        return "furious"


def _send_evaluation_message(team_id: int, score: int, mood: str,
                             changes: list, season: int, db_path: str = None):
    """Send end-of-season evaluation message from owner."""
    owner = query(
        "SELECT first_name, last_name FROM owner_characters WHERE team_id=?",
        (team_id,), db_path=db_path
    )
    owner_name = f"{owner[0]['first_name']} {owner[0]['last_name']}" if owner else "The Owner"

    mood_intro = {
        "elated": "Outstanding season! I couldn't be happier with your work.",
        "happy": "Good season overall. Keep up the solid work.",
        "neutral": "The season was... acceptable. I expect improvement.",
        "concerned": "I'm not happy with how things went. We need to talk.",
        "angry": "This is unacceptable. You're on extremely thin ice.",
        "furious": "I've seen enough. This is your last chance.",
    }

    body = (
        f"From: {owner_name} (Owner)\n"
        f"Subject: Season {season} Performance Review\n\n"
        f"{mood_intro.get(mood, 'Season review.')}\n\n"
        f"Performance Summary:\n"
        + "\n".join(f"  - {c}" for c in changes)
        + f"\n\nJob Security Rating: {score}/100"
    )

    send_message(team_id, "owner", f"Season {season} Review", body, db_path=db_path)


# ============================================================
# FIRING CHECK
# ============================================================

def check_firing(team_id: int, db_path: str = None) -> dict:
    """
    Check if the GM should be fired, warned, or is safe.

    Returns dict with status: 'fired', 'warning', 'concerned', 'safe'
    """
    _ensure_job_security_exists(team_id, db_path)

    security = query("SELECT * FROM gm_job_security WHERE id=1", db_path=db_path)
    if not security:
        return {"status": "safe", "score": 70}
    security = security[0]

    score = security["security_score"]
    warnings = security["warnings_given"]

    if score < 20:
        # FIRED
        return {
            "status": "fired",
            "score": score,
            "message": "You have been relieved of your duties as General Manager.",
            "owner_mood": "furious"
        }
    elif score < 40:
        # WARNING
        new_warnings = warnings + 1
        execute(
            "UPDATE gm_job_security SET warnings_given=? WHERE id=1",
            (new_warnings,), db_path=db_path
        )

        owner = query(
            "SELECT first_name, last_name FROM owner_characters WHERE team_id=?",
            (team_id,), db_path=db_path
        )
        owner_name = f"{owner[0]['first_name']} {owner[0]['last_name']}" if owner else "The Owner"

        warning_msg = (
            f"{owner_name} has called you into the office.\n\n"
            f"\"I'm starting to question some of your decisions. "
            f"This is warning #{new_warnings}. Get it together.\""
        )
        send_message(team_id, "owner", "WARNING: Job In Jeopardy", warning_msg, db_path=db_path)

        return {
            "status": "warning",
            "score": score,
            "warnings": new_warnings,
            "message": warning_msg,
            "owner_mood": "angry"
        }
    elif score < 60:
        return {
            "status": "concerned",
            "score": score,
            "message": "The owner is watching closely.",
            "owner_mood": "concerned"
        }
    else:
        return {
            "status": "safe",
            "score": score,
            "owner_mood": security["owner_mood"]
        }


# ============================================================
# MOOD MESSAGES
# ============================================================

def get_owner_mood_message(team_id: int, db_path: str = None) -> dict:
    """
    Generate a mood-appropriate message from the owner.

    Returns dict with mood, score, and message.
    """
    _ensure_job_security_exists(team_id, db_path)

    security = query("SELECT * FROM gm_job_security WHERE id=1", db_path=db_path)
    if not security:
        return {"mood": "neutral", "score": 70, "message": "No data available."}
    security = security[0]

    score = security["security_score"]
    mood = security["owner_mood"]

    messages = {
        "elated": [
            "Outstanding work! The fans love what you're doing.",
            "I'm thrilled with the direction of this franchise. Keep it up!",
            "You're doing an incredible job. The city is buzzing!",
        ],
        "happy": [
            "Keep up the good work.",
            "I like what I'm seeing. Stay the course.",
            "Things are going well. Let's keep this momentum.",
        ],
        "neutral": [
            "I expect better results.",
            "We need to see improvement. The fans deserve better.",
            "It's been an okay stretch, but okay isn't good enough.",
        ],
        "concerned": [
            "I'm starting to question some of your decisions...",
            "The board is getting restless. We need results.",
            "I'm hearing a lot of complaints from season ticket holders.",
        ],
        "angry": [
            "You're on thin ice. One more bad move and you're done.",
            "I'm losing patience. Fast.",
            "The media is calling for your head, and frankly, I'm not sure I disagree.",
        ],
        "furious": [
            "Clean out your desk.",
            "This is beyond unacceptable. Start looking for another job.",
            "I don't even know what to say anymore.",
        ],
    }

    mood_msgs = messages.get(mood, messages["neutral"])
    message = random.choice(mood_msgs)

    return {
        "mood": mood,
        "score": score,
        "message": message,
        "warnings": security["warnings_given"],
        "consecutive_losing_seasons": security["consecutive_losing_seasons"],
    }


# ============================================================
# PERIODIC PRESSURE MESSAGES
# ============================================================

def send_owner_pressure_messages(team_id: int, game_date: str,
                                 db_path: str = None) -> list:
    """
    Send periodic pressure messages from the owner during the season.
    Called on the 1st of each month during the regular season.

    Returns list of messages sent.
    """
    from datetime import date as dt_date
    sent = []

    _ensure_job_security_exists(team_id, db_path)

    state = query("SELECT season, phase FROM game_state WHERE id=1", db_path=db_path)
    if not state:
        return sent
    season = state[0]["season"]
    phase = state[0]["phase"]

    game_date_obj = dt_date.fromisoformat(game_date)
    month = game_date_obj.month
    day = game_date_obj.day

    # Only send on the 1st of the month
    if day != 1:
        return sent

    owner = query(
        "SELECT first_name, last_name FROM owner_characters WHERE team_id=?",
        (team_id,), db_path=db_path
    )
    owner_name = f"{owner[0]['first_name']} {owner[0]['last_name']}" if owner else "The Owner"

    security = query("SELECT * FROM gm_job_security WHERE id=1", db_path=db_path)
    score = security[0]["security_score"] if security else 70

    if phase == "regular_season":
        record = _get_team_record(team_id, season, db_path)
        wins, losses = record["wins"], record["losses"]

        # Monthly check-in
        if wins > losses:
            if score >= 70:
                msg = f"Good to see us at {wins}-{losses}. Keep the wins coming."
            else:
                msg = f"We're {wins}-{losses}, which is fine, but I still have concerns from earlier."
        elif wins == losses:
            msg = f"A .500 record at {wins}-{losses} isn't going to cut it. We need to make moves."
        else:
            msg = f"We're {wins}-{losses}. This is not what I signed up for."
            # Losing teams lose security
            new_score = max(0, score - 3)
            execute(
                "UPDATE gm_job_security SET security_score=?, owner_mood=? WHERE id=1",
                (new_score, _score_to_mood(new_score)), db_path=db_path
            )

        body = f"From: {owner_name} (Owner)\n\n{msg}"
        send_message(team_id, "owner", f"Monthly Check-in ({_month_name(month)})",
                     body, game_date=game_date, db_path=db_path)
        sent.append({"type": "monthly_checkin", "month": month})

        # Trade deadline pressure (July)
        if month == 7:
            objectives = query(
                "SELECT * FROM owner_objectives WHERE team_id=? AND season=? AND status='active'",
                (team_id, season), db_path=db_path
            )
            contending_objectives = [o for o in objectives
                                     if o["objective_type"] in ("win_division", "make_playoffs", "win_ws")]

            if contending_objectives and wins >= losses:
                deadline_msg = (
                    f"From: {owner_name} (Owner)\n\n"
                    f"The trade deadline is approaching. We're {wins}-{losses} and I expect "
                    f"you to be aggressive. Don't let this opportunity slip away. "
                    f"Open the checkbook if you have to."
                )
                send_message(team_id, "owner", "Trade Deadline Expectations",
                             deadline_msg, game_date=game_date, db_path=db_path)
                sent.append({"type": "trade_deadline_pressure"})
            elif contending_objectives and losses > wins:
                sell_msg = (
                    f"From: {owner_name} (Owner)\n\n"
                    f"We're {wins}-{losses}. I hate to say it, but maybe it's time to "
                    f"think about selling. Get what value you can before the deadline."
                )
                send_message(team_id, "owner", "Trade Deadline: Time to Sell?",
                             sell_msg, game_date=game_date, db_path=db_path)
                sent.append({"type": "trade_deadline_sell"})

    elif phase == "offseason":
        # Budget discussions in offseason (November, December)
        if month in (11, 12):
            payroll = _get_team_payroll(team_id, db_path)
            budget_msg = (
                f"From: {owner_name} (Owner)\n\n"
                f"Let's talk budget for next season. Current payroll commitments: "
                f"${payroll:,}. "
            )
            if score >= 70:
                budget_msg += "You've earned some flexibility. Spend wisely."
            elif score >= 50:
                budget_msg += "Be careful with spending. I want to see improvement first."
            else:
                budget_msg += "We're tightening the purse strings until I see results."

            send_message(team_id, "owner", "Offseason Budget Discussion",
                         budget_msg, game_date=game_date, db_path=db_path)
            sent.append({"type": "budget_discussion", "month": month})

    return sent


def _month_name(month: int) -> str:
    """Get month name from number."""
    names = {
        1: "January", 2: "February", 3: "March", 4: "April",
        5: "May", 6: "June", 7: "July", 8: "August",
        9: "September", 10: "October", 11: "November", 12: "December"
    }
    return names.get(month, str(month))


# ============================================================
# PUBLIC API HELPERS
# ============================================================

def get_job_security(db_path: str = None) -> dict:
    """Get current job security status for the UI."""
    security = query("SELECT * FROM gm_job_security WHERE id=1", db_path=db_path)
    if not security:
        return {
            "security_score": 70,
            "owner_mood": "neutral",
            "owner_patience": 50,
            "consecutive_losing_seasons": 0,
            "playoff_appearances": 0,
            "warnings_given": 0,
            "last_evaluation_date": None,
        }
    s = security[0]
    return {
        "security_score": s["security_score"],
        "owner_mood": s["owner_mood"],
        "owner_patience": s["owner_patience"],
        "consecutive_losing_seasons": s["consecutive_losing_seasons"],
        "playoff_appearances": s["playoff_appearances"],
        "warnings_given": s["warnings_given"],
        "last_evaluation_date": s["last_evaluation_date"],
        "mood_message": get_owner_mood_message(s["team_id"])["message"],
    }


def get_owner_objectives_for_team(team_id: int, season: int = None,
                                  db_path: str = None) -> list:
    """Get objectives for a team, optionally filtered by season."""
    if season:
        rows = query(
            "SELECT * FROM owner_objectives WHERE team_id=? AND season=? ORDER BY priority",
            (team_id, season), db_path=db_path
        )
    else:
        rows = query(
            "SELECT * FROM owner_objectives WHERE team_id=? ORDER BY season DESC, priority",
            (team_id,), db_path=db_path
        )
    return [dict(r) for r in rows] if rows else []
