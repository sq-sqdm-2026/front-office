"""
Front Office - Analytics Integration
Deep connections between chemistry, morale, relationships, and on-field performance.
Implements Phase 5 features: chemistry feedback loops, morale impact on specific stats,
relationship effects on team defense, and streak-driven morale.
"""
import random
from ..database.db import query, execute


def calculate_chemistry_performance_bonus(team_id: int, db_path: str = None) -> dict:
    """
    Chemistry feedback loop: team chemistry directly modifies game performance.

    Returns per-team bonuses/penalties applied during game simulation.
    """
    # Get team chemistry
    chem = query("""
        SELECT chemistry_score FROM team_chemistry WHERE team_id=?
    """, (team_id,), db_path=db_path)

    chemistry = chem[0]["chemistry_score"] if chem else 50

    # Chemistry -> Performance mapping
    # 80+ chemistry: team plays ABOVE their talent level
    # 50 chemistry: neutral
    # <30 chemistry: team plays BELOW talent

    bonus = (chemistry - 50) / 50  # -1.0 to +0.6 range

    return {
        "contact_bonus": round(bonus * 3, 1),      # +/- 3 contact rating points
        "power_bonus": round(bonus * 2, 1),         # +/- 2 power
        "fielding_bonus": round(bonus * 4, 1),      # Chemistry affects defense a LOT
        "pitching_bonus": round(bonus * 2, 1),      # +/- 2 stuff/control
        "error_rate_modifier": 1.0 - (bonus * 0.3), # High chemistry = fewer errors
        "clutch_bonus": round(bonus * 5, 1),        # Chemistry = clutch performance
        "double_play_bonus": round(bonus * 0.1, 2), # Better chemistry = more DPs turned
        "chemistry_score": chemistry,
    }


def calculate_morale_stat_effects(player_id: int, db_path: str = None) -> dict:
    """
    Morale impact on specific performance metrics.
    Goes beyond the basic contact/power/speed already in the game.

    Returns modifiers for specific game situations.
    """
    player = query("""
        SELECT morale, clutch, ego, work_ethic, leadership
        FROM players WHERE id=?
    """, (player_id,), db_path=db_path)

    if not player:
        return {"hr_modifier": 1.0, "k_modifier": 1.0, "risp_modifier": 1.0,
                "first_pitch_modifier": 1.0, "late_inning_modifier": 1.0}

    p = player[0]
    morale = p.get("morale", 50)
    clutch = p.get("clutch", 50)
    ego = p.get("ego", 50)
    work_ethic = p.get("work_ethic", 50)

    morale_factor = (morale - 50) / 50  # -1 to +1

    return {
        # High morale = more HRs (confidence at the plate)
        "hr_modifier": 1.0 + (morale_factor * 0.15),

        # Low morale = more strikeouts (pressing, expanding zone)
        "k_modifier": 1.0 - (morale_factor * 0.12),

        # Morale + clutch = RISP performance
        "risp_modifier": 1.0 + (morale_factor * 0.1) + ((clutch - 50) / 100 * 0.15),

        # High ego + low morale = terrible first-pitch swinging (impatient)
        "first_pitch_modifier": 1.0 - (ego / 100 * (1 - morale / 100) * 0.2),

        # Work ethic sustains performance in late innings
        "late_inning_modifier": 1.0 + (work_ethic - 50) / 200,

        # Overall approach quality
        "plate_discipline_modifier": 1.0 + (morale_factor * 0.08),

        "morale": morale,
    }


def calculate_relationship_defense_effects(team_id: int, db_path: str = None) -> dict:
    """
    Relationship effects on team defense.
    Friends turn more double plays, rivals make errors near each other.
    """
    relationships = query("""
        SELECT pr.player_id_1, pr.player_id_2, pr.relationship_type,
               p1.position as pos1, p2.position as pos2,
               p1.first_name as name1, p2.first_name as name2
        FROM player_relationships pr
        JOIN players p1 ON p1.id = pr.player_id_1
        JOIN players p2 ON p2.id = pr.player_id_2
        WHERE p1.team_id=? AND p2.team_id=?
    """, (team_id, team_id), db_path=db_path) or []

    dp_bonus = 0.0
    error_penalty = 0.0
    relay_bonus = 0.0
    friend_pairs = []
    rival_pairs = []

    for rel in relationships:
        pos1 = rel.get("pos1", "")
        pos2 = rel.get("pos2", "")
        rel_type = rel.get("relationship_type", "neutral")

        if rel_type == "friend":
            friend_pairs.append((rel.get("name1"), rel.get("name2")))

            # Friends at adjacent positions = better defense
            # SS-2B friends = elite double play combo
            if set([pos1, pos2]) == {"SS", "2B"}:
                dp_bonus += 0.05  # 5% more DPs

            # OF friends = better relay throws
            if pos1 in ("LF", "CF", "RF") and pos2 in ("LF", "CF", "RF"):
                relay_bonus += 0.03

            # IF friends = better communication on pop-ups
            if pos1 in ("SS", "2B", "3B", "1B") and pos2 in ("SS", "2B", "3B", "1B"):
                error_penalty -= 0.02  # Fewer errors

        elif rel_type == "rival":
            rival_pairs.append((rel.get("name1"), rel.get("name2")))

            # Rivals at adjacent positions = defensive lapses
            if set([pos1, pos2]) == {"SS", "2B"}:
                dp_bonus -= 0.03
                error_penalty += 0.03

            # Any rival pair on defense = tension
            error_penalty += 0.01

    return {
        "dp_modifier": 1.0 + dp_bonus,
        "error_modifier": 1.0 + error_penalty,
        "relay_modifier": 1.0 + relay_bonus,
        "friend_pairs": friend_pairs[:5],  # Top 5 for display
        "rival_pairs": rival_pairs[:5],
        "total_friends": len(friend_pairs),
        "total_rivals": len(rival_pairs),
    }


def update_streak_morale(team_id: int, db_path: str = None):
    """
    Win-loss streaks compound morale effects.
    Called after each game during sim advance.
    """
    # Get recent results
    recent = query("""
        SELECT home_score, away_score, home_team_id, game_date
        FROM schedule
        WHERE (home_team_id=? OR away_team_id=?) AND is_played=1
        ORDER BY game_date DESC LIMIT 10
    """, (team_id, team_id), db_path=db_path) or []

    if not recent:
        return

    # Calculate current streak
    streak = 0
    streak_type = None
    for g in recent:
        is_home = g["home_team_id"] == team_id
        home_won = (g.get("home_score", 0) or 0) > (g.get("away_score", 0) or 0)
        won = (is_home and home_won) or (not is_home and not home_won)

        if streak_type is None:
            streak_type = "W" if won else "L"
            streak = 1
        elif (won and streak_type == "W") or (not won and streak_type == "L"):
            streak += 1
        else:
            break

    # Streak morale effects (compound)
    if streak_type == "W" and streak >= 3:
        # Winning streak: morale boost grows with streak
        morale_bump = min(streak * 2, 15)  # Cap at +15
        execute("""
            UPDATE players SET morale = MIN(100, morale + ?)
            WHERE team_id=? AND morale < 90
        """, (morale_bump, team_id), db_path=db_path)

    elif streak_type == "L" and streak >= 3:
        # Losing streak: morale drain accelerates
        morale_drain = min(streak * 2, 15)  # Cap at -15

        # High-leadership players resist morale drain
        execute("""
            UPDATE players SET morale = MAX(10, morale - ?)
            WHERE team_id=? AND leadership < 70
        """, (morale_drain, team_id), db_path=db_path)

        # Leaders only lose half the morale
        execute("""
            UPDATE players SET morale = MAX(20, morale - ?)
            WHERE team_id=? AND leadership >= 70
        """, (morale_drain // 2, team_id), db_path=db_path)


def get_team_analytics_dashboard(team_id: int, db_path: str = None) -> dict:
    """
    Full analytics dashboard combining all Phase 5 metrics.
    Used by the frontend to show the "hidden" performance factors.
    """
    chem = calculate_chemistry_performance_bonus(team_id, db_path)
    defense = calculate_relationship_defense_effects(team_id, db_path)

    # Get team average morale
    avg_morale = query("""
        SELECT AVG(morale) as avg_morale FROM players WHERE team_id=? AND team_id IS NOT NULL
    """, (team_id,), db_path=db_path)

    morale_avg = avg_morale[0]["avg_morale"] if avg_morale and avg_morale[0]["avg_morale"] else 50

    return {
        "chemistry": chem,
        "defense_relationships": defense,
        "team_morale": round(morale_avg, 1),
        "morale_trend": "rising" if morale_avg > 60 else "falling" if morale_avg < 40 else "stable",
        "intangibles_rating": round((chem["chemistry_score"] + morale_avg) / 2, 1),
    }
