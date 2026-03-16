"""
Front Office - Team Chemistry & Player Morale System
Implements Baseball Mogul-style personality, morale, and team chemistry mechanics.

Chemistry affects:
- Development rate (+/-5%)
- Clutch performance (+/-3%)
- Injury recovery (+/-10%)

Morale affects:
- Contact/Power by +/-3 at extremes
- Speed by +/-2
"""
import random
import json
from datetime import datetime, timedelta
from ..database.db import get_connection, query


# =============================================================================
# TEAM CHEMISTRY
# =============================================================================

def calculate_team_chemistry(team_id: int, db_path: str = None) -> int:
    """
    Calculate team chemistry score (0-100) based on:
    - Average leadership on roster (weighted by playing time)
    - Personality conflicts (high ego players clashing)
    - Veteran/rookie balance
    - Win streak / losing streak momentum
    - Recent trades (disruption factor, decays over 30 days)

    Returns chemistry score 0-100.
    """
    conn = get_connection(db_path)

    # Get all active players on team
    players = conn.execute("""
        SELECT p.*, bs.games
        FROM players p
        LEFT JOIN batting_stats bs ON bs.player_id = p.id AND bs.season = 2026
        WHERE p.team_id = ? AND p.roster_status = 'active'
    """, (team_id,)).fetchall()

    if not players:
        return 50

    # Leadership component (weighted by playing time)
    total_games = sum(p["games"] or 0 for p in players)
    if total_games > 0:
        leadership_score = sum((p["leadership"] or 50) * (p["games"] or 0) for p in players) / total_games
    else:
        leadership_score = sum(p["leadership"] or 50 for p in players) / len(players)
    leadership_component = (leadership_score - 50) * 0.3  # -15 to +15

    # Ego conflict component
    high_ego_count = sum(1 for p in players if (p["ego"] or 50) > 65)
    ego_conflict_penalty = high_ego_count * 3  # Each high-ego player reduces by 3

    # Veteran/rookie balance component
    age_std_dev = calculate_age_stddev([p["age"] for p in players])
    # Balanced teams (std dev ~5-6) are best; too homogeneous (std dev <3) or spread (>8) is bad
    balance_penalty = abs(age_std_dev - 5.5) * 2

    # Win streak component (cached in team_chemistry table)
    chemistry_row = conn.execute(
        "SELECT win_streak FROM team_chemistry WHERE team_id = ?", (team_id,)
    ).fetchone()
    streak_bonus = 0
    if chemistry_row and chemistry_row["win_streak"]:
        streak = chemistry_row["win_streak"]
        if streak > 0:
            streak_bonus = min(streak * 1.5, 15)  # +15 max for long win streak
        else:
            streak_bonus = max(streak * 1.0, -15)  # -15 for long loss streak

    # Recent trades (disruption)
    trade_disrupt = 0
    trades_30d = conn.execute("""
        SELECT COUNT(*) as cnt FROM transactions
        WHERE (team1_id = ? OR team2_id = ?)
        AND transaction_type = 'trade'
        AND transaction_date >= date('now', '-30 days')
    """, (team_id, team_id)).fetchone()

    if trades_30d and trades_30d["cnt"]:
        trade_disrupt = -trades_30d["cnt"] * 2

    # Relationships component (friends boost, rivals hurt)
    rel_bonus = 0
    for p in players:
        friends = conn.execute("""
            SELECT COUNT(*) as cnt FROM player_relationships
            WHERE (player_id_1 = ? OR player_id_2 = ?)
            AND relationship_type = 'friend'
        """, (p["id"], p["id"])).fetchone()
        rivals = conn.execute("""
            SELECT COUNT(*) as cnt FROM player_relationships
            WHERE (player_id_1 = ? OR player_id_2 = ?)
            AND relationship_type = 'rival'
        """, (p["id"], p["id"])).fetchone()

        rel_bonus += (friends["cnt"] or 0) * 1.5
        rel_bonus -= (rivals["cnt"] or 0) * 2

    # Sociability boost (high sociability players improve chemistry)
    sociability_component = (sum(p["sociability"] or 50 for p in players) / len(players) - 50) * 0.2

    conn.close()

    # Calculate final score
    base_score = 50
    final_score = (
        base_score
        + leadership_component
        - ego_conflict_penalty
        - balance_penalty
        + streak_bonus
        + trade_disrupt
        + rel_bonus * 0.1
        + sociability_component
    )

    # Clamp to 0-100
    return max(0, min(100, int(final_score)))


def update_team_chemistry(team_id: int, db_path: str = None):
    """Update team chemistry score and cache in database."""
    conn = get_connection(db_path)

    chemistry_score = calculate_team_chemistry(team_id, db_path)

    # Check if chemistry record exists
    existing = conn.execute(
        "SELECT id FROM team_chemistry WHERE team_id = ?", (team_id,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE team_chemistry
            SET chemistry_score = ?, last_updated = ?
            WHERE team_id = ?
        """, (chemistry_score, datetime.now().isoformat(), team_id))
    else:
        conn.execute("""
            INSERT INTO team_chemistry (team_id, chemistry_score, last_updated, recent_trade_count, win_streak)
            VALUES (?, ?, ?, 0, 0)
        """, (team_id, chemistry_score, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def get_chemistry_modifiers(chemistry_score: int) -> dict:
    """Get impact multipliers based on chemistry score."""
    # Range: 0-100
    # Low chemistry (0-30): -5% dev, -3% clutch, -10% injury recovery
    # High chemistry (70-100): +5% dev, +3% clutch, +10% injury recovery
    dev_mod = (chemistry_score - 50) * 0.001  # -0.05 to +0.05
    clutch_mod = (chemistry_score - 50) * 0.0006  # -0.03 to +0.03
    injury_recovery_mod = (chemistry_score - 50) * 0.002  # -0.10 to +0.10

    return {
        "development_rate": 1.0 + dev_mod,
        "clutch_bonus": clutch_mod,
        "injury_recovery": 1.0 + injury_recovery_mod,
    }


# =============================================================================
# PLAYER MORALE
# =============================================================================

def update_player_morale(team_id: int, db_path: str = None):
    """
    Run daily morale updates for all players on a team.
    Morale changes based on:
    - Playing time (starters happy, bench players lose morale)
    - Team winning/losing
    - Being traded (temporary morale drop)
    - Contract status (expiring contract = anxiety)
    - Team chemistry
    """
    conn = get_connection(db_path)

    # Get team record
    wins = conn.execute("""
        SELECT COUNT(*) as wins FROM schedule
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND is_played = 1 AND season = 2026
        AND (
            (home_team_id = ? AND home_score > away_score) OR
            (away_team_id = ? AND away_score > home_score)
        )
    """, (team_id, team_id, team_id, team_id)).fetchone()

    wins = wins["wins"] if wins else 0

    losses = conn.execute("""
        SELECT COUNT(*) as losses FROM schedule
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND is_played = 1 AND season = 2026
        AND (
            (home_team_id = ? AND home_score < away_score) OR
            (away_team_id = ? AND away_score < home_score)
        )
    """, (team_id, team_id, team_id, team_id)).fetchone()

    losses = losses["losses"] if losses else 0

    # Determine team momentum
    recent_games = conn.execute("""
        SELECT
            SUM(CASE WHEN home_team_id = ? AND home_score > away_score THEN 1
                     WHEN away_team_id = ? AND away_score > home_score THEN 1
                     ELSE 0 END) as recent_wins,
            COUNT(*) as total_games
        FROM schedule
        WHERE (home_team_id = ? OR away_team_id = ?)
        AND is_played = 1 AND season = 2026
        AND game_date >= date('now', '-10 days')
    """, (team_id, team_id, team_id, team_id)).fetchone()

    recent_wins = recent_games["recent_wins"] or 0
    recent_total = recent_games["total_games"] or 1
    momentum = "winning" if recent_wins >= recent_total / 2 else "losing"

    # Get chemistry
    chemistry = conn.execute(
        "SELECT chemistry_score FROM team_chemistry WHERE team_id = ?", (team_id,)
    ).fetchone()
    chemistry_score = chemistry["chemistry_score"] if chemistry else 50

    # Get all players
    players = conn.execute("""
        SELECT p.*, c.years_remaining as contract_years_remaining
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id = ? AND p.roster_status = 'active'
    """, (team_id,)).fetchall()

    for p in players:
        morale_delta = 0

        # Playing time component
        games_played = conn.execute("""
            SELECT COUNT(*) as games FROM batting_lines bl
            JOIN schedule s ON bl.schedule_id = s.id
            WHERE bl.player_id = ? AND bl.team_id = ? AND s.season = 2026
        """, (p["id"], team_id)).fetchone()

        games = games_played["games"] or 0
        if games >= 100:
            morale_delta += 3  # Starter
        elif games >= 50:
            morale_delta += 1  # Semi-regular
        elif games < 20:
            morale_delta -= 2  # Bench player

        # Team momentum
        if momentum == "winning":
            morale_delta += 2
        else:
            morale_delta -= 2

        # Chemistry influence
        chemistry_morale = (chemistry_score - 50) * 0.04
        morale_delta += chemistry_morale

        # Contract status (expiring creates anxiety)
        if p["contract_years_remaining"] and p["contract_years_remaining"] <= 1:
            morale_delta -= 3

        # Loyalty influence (high loyalty = more sensitive to team performance)
        loyalty = p["loyalty"] or 50
        morale_delta *= (0.5 + loyalty / 200)

        # Apply morale change
        new_morale = max(0, min(100, (p["morale"] or 50) + morale_delta))
        conn.execute(
            "UPDATE players SET morale = ? WHERE id = ?", (int(new_morale), p["id"])
        )

    conn.commit()
    conn.close()


def get_morale_modifiers(morale: int) -> dict:
    """Get rating modifiers based on player morale."""
    # Extreme morale affects performance
    # 0-30: -3 contact, -3 power, -2 speed
    # 70-100: +3 contact, +3 power, +2 speed
    contact_mod = (morale - 50) * 0.06  # -3 to +3
    power_mod = (morale - 50) * 0.06
    speed_mod = (morale - 50) * 0.04  # -2 to +2

    return {
        "contact": contact_mod,
        "power": power_mod,
        "speed": speed_mod,
    }


# =============================================================================
# PLAYER RELATIONSHIPS
# =============================================================================

def create_player_relationships(team_id: int, db_path: str = None):
    """
    Generate initial relationships for a team based on:
    - Same country
    - Same position group
    - Age gap (mentors are 5+ years older)
    """
    conn = get_connection(db_path)

    players = conn.execute("""
        SELECT id, age, birth_country, position FROM players
        WHERE team_id = ? AND roster_status = 'active'
        ORDER BY id
    """, (team_id,)).fetchall()

    if len(players) < 2:
        conn.close()
        return

    # Clear existing relationships for this team
    player_ids = [p["id"] for p in players]
    if player_ids:
        placeholders = ",".join("?" * len(player_ids))
        conn.execute(f"""
            DELETE FROM player_relationships
            WHERE player_id_1 IN ({placeholders}) OR player_id_2 IN ({placeholders})
        """, player_ids + player_ids)

    # Generate new relationships
    for i, p1 in enumerate(players):
        for p2 in players[i + 1 :]:
            rel_type = None
            strength = 50

            # Same country connection
            if p1["birth_country"] == p2["birth_country"] and random.random() < 0.2:
                rel_type = "friend"
                strength = random.randint(40, 70)

            # Position group connection
            position_groups = {
                "infield": ["C", "1B", "2B", "3B", "SS"],
                "outfield": ["LF", "CF", "RF"],
                "dh": ["DH"],
                "pitcher": ["SP", "RP"],
            }

            p1_group = None
            p2_group = None
            for group, positions in position_groups.items():
                if p1["position"] in positions:
                    p1_group = group
                if p2["position"] in positions:
                    p2_group = group

            if p1_group and p1_group == p2_group and p1_group not in ("dh",):
                if random.random() < 0.15:
                    # Could be friends or rivals
                    rel_type = "friend" if random.random() < 0.7 else "rival"
                    strength = random.randint(30, 80)

            # Age gap - mentor relationship
            age_diff = abs(p1["age"] - p2["age"])
            if age_diff >= 5:
                mentor = p1 if p1["age"] > p2["age"] else p2
                mentee = p2 if p1["age"] > p2["age"] else p1
                if random.random() < 0.1:
                    rel_type = "mentor"
                    strength = random.randint(35, 75)

            # Rivalry from position competition (same position, close age, random chance)
            if (p1["position"] == p2["position"] and abs(p1["age"] - p2["age"]) <= 3
                and random.random() < 0.1):
                rel_type = "rival"
                strength = random.randint(40, 70)

            if rel_type:
                smaller_id = min(p1["id"], p2["id"])
                larger_id = max(p1["id"], p2["id"])
                conn.execute("""
                    INSERT INTO player_relationships
                    (player_id_1, player_id_2, relationship_type, strength, created_date)
                    VALUES (?, ?, ?, ?, ?)
                """, (smaller_id, larger_id, rel_type, strength, datetime.now().isoformat()))

    conn.commit()
    conn.close()


def get_player_relationships(player_id: int, db_path: str = None) -> list:
    """Get all relationships for a player."""
    conn = get_connection(db_path)

    relationships = conn.execute("""
        SELECT
            CASE WHEN player_id_1 = ? THEN player_id_2 ELSE player_id_1 END as other_player_id,
            relationship_type,
            strength
        FROM player_relationships
        WHERE player_id_1 = ? OR player_id_2 = ?
    """, (player_id, player_id, player_id)).fetchall()

    conn.close()
    return [dict(r) for r in relationships] if relationships else []


def apply_trade_morale_penalty(player_id: int, days: int = 14, penalty: int = 10, db_path: str = None):
    """Apply temporary morale penalty when player is traded."""
    conn = get_connection(db_path)

    player = conn.execute("SELECT morale FROM players WHERE id = ?", (player_id,)).fetchone()
    if player:
        new_morale = max(0, (player["morale"] or 50) - penalty)
        conn.execute("UPDATE players SET morale = ? WHERE id = ?", (new_morale, player_id))

    conn.commit()
    conn.close()


# =============================================================================
# HELPERS
# =============================================================================

def calculate_age_stddev(ages: list) -> float:
    """Calculate standard deviation of ages."""
    if not ages or len(ages) < 2:
        return 0
    mean = sum(ages) / len(ages)
    variance = sum((x - mean) ** 2 for x in ages) / len(ages)
    return variance ** 0.5
