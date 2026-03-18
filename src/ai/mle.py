"""
Front Office - Major League Equivalencies (MLE)
Converts minor league stats to estimated MLB equivalent ratings using MLE factors.
Integrates minor league park factors to normalize stats before conversion.
"""
import random
from ..database.db import query
from ..simulation.minor_league_parks import get_park_factors, NEUTRAL_PARK


# MLE conversion factors by level
MLE_FACTORS = {
    "AAA": {
        "batting_avg": 0.90,
        "hr": 0.85,
        "bb": 0.95,
        "k": 1.05,
        "era": 1.10,
    },
    "AA": {
        "batting_avg": 0.82,
        "hr": 0.75,
        "bb": 0.88,
        "k": 1.12,
        "era": 1.25,
    },
    "A": {
        "batting_avg": 0.72,
        "hr": 0.60,
        "bb": 0.80,
        "k": 1.20,
        "era": 1.45,
    },
    "LOW": {
        "batting_avg": 0.72,
        "hr": 0.60,
        "bb": 0.80,
        "k": 1.20,
        "era": 1.45,
    },
}


def _clamp(value: int, lo: int = 20, hi: int = 80) -> int:
    """Clamp a rating to 20-80 scouting scale."""
    return max(lo, min(hi, int(value)))


def park_adjust_stats(stats: dict, park_factors: dict, is_pitcher: bool = False) -> dict:
    """
    Normalize raw stats for park effects before MLE conversion.
    Divides counting/rate stats by park factors to remove park inflation/deflation.

    For a hitter in Las Vegas (HR factor 1.18), 30 HR becomes 30/1.18 = ~25.4 HR.
    For a pitcher in a hitter's park (R factor 1.15), ER gets divided by R factor.

    Args:
        stats: Dict of raw stats from the database (batting_stats or pitching_stats row)
        park_factors: Dict with keys H, 2B, 3B, HR, BB, K, R
        is_pitcher: Whether these are pitching stats

    Returns:
        New dict with park-adjusted stats (original dict is not modified)
    """
    adjusted = dict(stats)

    if is_pitcher:
        # Adjust pitching stats: hits allowed, HR allowed, BB, K, ER/runs
        h_factor = park_factors.get("H", 1.0)
        hr_factor = park_factors.get("HR", 1.0)
        bb_factor = park_factors.get("BB", 1.0)
        k_factor = park_factors.get("K", 1.0)
        r_factor = park_factors.get("R", 1.0)

        if adjusted.get("hits_allowed"):
            adjusted["hits_allowed"] = int(round(adjusted["hits_allowed"] / h_factor))
        if adjusted.get("hr_allowed"):
            adjusted["hr_allowed"] = int(round(adjusted["hr_allowed"] / hr_factor))
        if adjusted.get("bb"):
            adjusted["bb"] = int(round(adjusted["bb"] / bb_factor))
        if adjusted.get("so"):
            adjusted["so"] = int(round(adjusted["so"] / k_factor))
        if adjusted.get("er"):
            adjusted["er"] = int(round(adjusted["er"] / r_factor))
        if adjusted.get("runs_allowed"):
            adjusted["runs_allowed"] = int(round(adjusted["runs_allowed"] / r_factor))
    else:
        # Adjust batting stats
        h_factor = park_factors.get("H", 1.0)
        doubles_factor = park_factors.get("2B", 1.0)
        triples_factor = park_factors.get("3B", 1.0)
        hr_factor = park_factors.get("HR", 1.0)
        bb_factor = park_factors.get("BB", 1.0)
        k_factor = park_factors.get("K", 1.0)
        r_factor = park_factors.get("R", 1.0)

        if adjusted.get("hits"):
            adjusted["hits"] = int(round(adjusted["hits"] / h_factor))
        if adjusted.get("doubles"):
            adjusted["doubles"] = int(round(adjusted["doubles"] / doubles_factor))
        if adjusted.get("triples"):
            adjusted["triples"] = int(round(adjusted["triples"] / triples_factor))
        if adjusted.get("hr"):
            adjusted["hr"] = int(round(adjusted["hr"] / hr_factor))
        if adjusted.get("bb"):
            adjusted["bb"] = int(round(adjusted["bb"] / bb_factor))
        if adjusted.get("so"):
            adjusted["so"] = int(round(adjusted["so"] / k_factor))
        if adjusted.get("runs"):
            adjusted["runs"] = int(round(adjusted["runs"] / r_factor))
        if adjusted.get("rbi"):
            adjusted["rbi"] = int(round(adjusted["rbi"] / r_factor))

    return adjusted


def _get_player_team_id(player_id: int) -> int:
    """Get the team_id for a player."""
    result = query("SELECT team_id FROM players WHERE id=?", (player_id,))
    if result and result[0]["team_id"]:
        return result[0]["team_id"]
    return None


def _get_player_level(player_id: int, season: int) -> str:
    """Get the highest level a player played at in the season."""
    stats = query("""
        SELECT DISTINCT level FROM batting_stats
        WHERE player_id=? AND season=?
        ORDER BY
            CASE WHEN level='MLB' THEN 0
                 WHEN level='AAA' THEN 1
                 WHEN level='AA' THEN 2
                 WHEN level='A' THEN 3
                 WHEN level='LOW' THEN 4
                 ELSE 5
            END
    """, (player_id, season))

    if stats:
        return stats[0]["level"]
    return "LOW"


def calculate_mle_ratings(player_id: int, season: int = 2026) -> dict:
    """
    Calculate MLE-based ratings for a player from their minor league stats.
    Returns None if player has no stats.
    """
    player = query("SELECT * FROM players WHERE id=?", (player_id,))
    if not player:
        return None

    p = player[0]
    is_pitcher = p["position"] in ("SP", "RP")

    # Get player's stats at highest minor league level
    level = _get_player_level(player_id, season)

    if level == "MLB":
        # Player is in MLB - use actual ratings
        return {
            "contact_rating": p["contact_rating"],
            "power_rating": p["power_rating"],
            "speed_rating": p["speed_rating"],
            "fielding_rating": p["fielding_rating"],
            "arm_rating": p["arm_rating"],
            "stuff_rating": p["stuff_rating"],
            "control_rating": p["control_rating"],
            "stamina_rating": p["stamina_rating"],
            "is_mle": False,
            "from_level": "MLB",
        }

    if is_pitcher:
        return _calculate_mle_pitching_ratings(player_id, level, season)
    else:
        return _calculate_mle_hitting_ratings(player_id, level, season)


def _calculate_mle_hitting_ratings(player_id: int, level: str, season: int) -> dict:
    """Calculate MLE hitting ratings from minor league stats."""
    raw_stats = query("""
        SELECT * FROM batting_stats
        WHERE player_id=? AND season=? AND level=?
    """, (player_id, season, level))

    if not raw_stats:
        # No stats at this level
        return None

    raw_stats = raw_stats[0]

    # Apply park factor normalization before MLE conversion
    team_id = raw_stats.get("team_id") or _get_player_team_id(player_id)
    if team_id:
        pf = get_park_factors(team_id, level)
    else:
        pf = NEUTRAL_PARK
    stats = park_adjust_stats(dict(raw_stats), pf, is_pitcher=False)

    pa = stats.get("pa", 0) or 1
    ab = stats.get("ab", 0) or 1

    # Check uncertainty based on playing time
    games = stats.get("games", 0) or 0
    if pa < 100:
        uncertainty = 10
    elif pa < 300:
        uncertainty = 5
    else:
        uncertainty = 2

    # Get MLE factors for this level
    factors = MLE_FACTORS.get(level, MLE_FACTORS["LOW"])

    # Apply MLE conversion to raw stats
    if ab > 0:
        batting_avg = stats.get("hits", 0) / ab
    else:
        batting_avg = 0

    mle_batting_avg = batting_avg * factors["batting_avg"]

    # Estimate power from HR rate
    hr_rate = stats.get("hr", 0) / max(ab, 1)
    mle_hr_rate = hr_rate * factors["hr"]

    # Estimate strikeout rate
    k_rate = stats.get("so", 0) / max(ab, 1)
    mle_k_rate = k_rate / factors["k"]  # Divide because factor increases in minors

    # Walk rate
    bb_rate = stats.get("bb", 0) / max(pa, 1)
    mle_bb_rate = bb_rate * factors["bb"]

    # Calculate contact rating from batting avg and K rate
    if mle_batting_avg >= 0.320:
        contact_from_avg = 75
    elif mle_batting_avg >= 0.300:
        contact_from_avg = 70
    elif mle_batting_avg >= 0.280:
        contact_from_avg = 65
    elif mle_batting_avg >= 0.260:
        contact_from_avg = 60
    elif mle_batting_avg >= 0.240:
        contact_from_avg = 50
    elif mle_batting_avg >= 0.220:
        contact_from_avg = 40
    else:
        contact_from_avg = 30

    if mle_k_rate <= 0.15:
        contact_from_k = 80
    elif mle_k_rate <= 0.18:
        contact_from_k = 70
    elif mle_k_rate <= 0.21:
        contact_from_k = 60
    elif mle_k_rate <= 0.25:
        contact_from_k = 50
    elif mle_k_rate <= 0.28:
        contact_from_k = 40
    else:
        contact_from_k = 30

    contact = _clamp(int(contact_from_avg * 0.6 + contact_from_k * 0.4))
    contact += random.randint(-uncertainty, uncertainty)
    contact = _clamp(contact)

    # Calculate power rating from ISO and HR rate
    iso = max(0, (mle_batting_avg + mle_hr_rate) - mle_batting_avg)

    if iso >= 0.250:
        power_from_iso = 80
    elif iso >= 0.220:
        power_from_iso = 75
    elif iso >= 0.190:
        power_from_iso = 70
    elif iso >= 0.160:
        power_from_iso = 60
    elif iso >= 0.120:
        power_from_iso = 50
    elif iso >= 0.080:
        power_from_iso = 40
    else:
        power_from_iso = 30

    if mle_hr_rate >= 0.050:
        power_from_hr = 75
    elif mle_hr_rate >= 0.040:
        power_from_hr = 65
    elif mle_hr_rate >= 0.035:
        power_from_hr = 55
    elif mle_hr_rate >= 0.025:
        power_from_hr = 45
    elif mle_hr_rate >= 0.015:
        power_from_hr = 35
    else:
        power_from_hr = 25

    power = _clamp(int(power_from_iso * 0.6 + power_from_hr * 0.4))
    power += random.randint(-uncertainty, uncertainty)
    power = _clamp(power)

    # Speed from stolen bases
    sb_per_game = stats.get("sb", 0) / max(games, 1)
    if sb_per_game >= 0.30:
        speed = 75
    elif sb_per_game >= 0.20:
        speed = 65
    elif sb_per_game >= 0.10:
        speed = 55
    elif sb_per_game >= 0.05:
        speed = 45
    else:
        speed = 35

    speed += random.randint(-uncertainty, uncertainty)
    speed = _clamp(speed)

    # Fielding and arm (position-based, as we don't have defensive stats)
    fielding = 50 + random.randint(-5, 5)
    arm = 50 + random.randint(-5, 5)

    return {
        "contact_rating": contact,
        "power_rating": power,
        "speed_rating": speed,
        "fielding_rating": _clamp(fielding),
        "arm_rating": _clamp(arm),
        "stuff_rating": None,
        "control_rating": None,
        "stamina_rating": None,
        "is_mle": True,
        "from_level": level,
        "uncertainty": uncertainty,
        "playing_time": pa,
        "park_adjusted": pf != NEUTRAL_PARK,
    }


def _calculate_mle_pitching_ratings(player_id: int, level: str, season: int) -> dict:
    """Calculate MLE pitching ratings from minor league stats."""
    raw_stats = query("""
        SELECT * FROM pitching_stats
        WHERE player_id=? AND season=? AND level=?
    """, (player_id, season, level))

    if not raw_stats:
        return None

    raw_stats = raw_stats[0]

    # Apply park factor normalization before MLE conversion
    team_id = raw_stats.get("team_id") or _get_player_team_id(player_id)
    if team_id:
        pf = get_park_factors(team_id, level)
    else:
        pf = NEUTRAL_PARK
    stats = park_adjust_stats(dict(raw_stats), pf, is_pitcher=True)

    ip_outs = stats.get("ip_outs", 0) or 1
    ip = ip_outs / 3.0  # Convert outs to innings

    # Check uncertainty based on playing time
    if ip < 30:
        uncertainty = 10
    elif ip < 80:
        uncertainty = 5
    else:
        uncertainty = 2

    factors = MLE_FACTORS.get(level, MLE_FACTORS["LOW"])

    # Calculate K/9 and BB/9 with MLE adjustment
    k = stats.get("so", 0)
    bb = stats.get("bb", 0)
    er = stats.get("er", 0)

    k_per_9 = (k / ip * 9) if ip > 0 else 0
    bb_per_9 = (bb / ip * 9) if ip > 0 else 0
    era = (er / ip * 9) if ip > 0 else 9.00

    # Apply MLE adjustment
    mle_k_per_9 = k_per_9 * factors["k"]
    mle_bb_per_9 = bb_per_9 / factors["bb"]  # Divide because factor decreases
    mle_era = era * factors["era"]

    # Calculate stuff rating from K/9
    if mle_k_per_9 >= 11.0:
        stuff = 80
    elif mle_k_per_9 >= 10.0:
        stuff = 75
    elif mle_k_per_9 >= 9.0:
        stuff = 70
    elif mle_k_per_9 >= 8.0:
        stuff = 60
    elif mle_k_per_9 >= 7.0:
        stuff = 50
    elif mle_k_per_9 >= 6.0:
        stuff = 40
    else:
        stuff = 30

    stuff += random.randint(-uncertainty, uncertainty)
    stuff = _clamp(stuff)

    # Calculate control rating from BB/9 and ERA
    if mle_bb_per_9 <= 2.0:
        control_from_bb = 80
    elif mle_bb_per_9 <= 2.5:
        control_from_bb = 70
    elif mle_bb_per_9 <= 3.0:
        control_from_bb = 60
    elif mle_bb_per_9 <= 3.5:
        control_from_bb = 50
    elif mle_bb_per_9 <= 4.0:
        control_from_bb = 40
    else:
        control_from_bb = 30

    if mle_era <= 2.50:
        control_from_era = 75
    elif mle_era <= 3.00:
        control_from_era = 65
    elif mle_era <= 3.50:
        control_from_era = 55
    elif mle_era <= 4.00:
        control_from_era = 45
    elif mle_era <= 4.50:
        control_from_era = 35
    else:
        control_from_era = 25

    control = _clamp(int(control_from_bb * 0.6 + control_from_era * 0.4))
    control += random.randint(-uncertainty, uncertainty)
    control = _clamp(control)

    # Stamina (innings pitched per game started)
    games_started = stats.get("games_started", 0) or 1
    ip_per_start = ip / games_started if games_started > 0 else 5.0

    if ip_per_start >= 6.5:
        stamina = 75
    elif ip_per_start >= 6.0:
        stamina = 65
    elif ip_per_start >= 5.5:
        stamina = 55
    elif ip_per_start >= 5.0:
        stamina = 45
    else:
        stamina = 35

    stamina += random.randint(-uncertainty, uncertainty)
    stamina = _clamp(stamina)

    return {
        "contact_rating": None,
        "power_rating": None,
        "speed_rating": None,
        "fielding_rating": None,
        "arm_rating": None,
        "stuff_rating": stuff,
        "control_rating": control,
        "stamina_rating": stamina,
        "is_mle": True,
        "from_level": level,
        "uncertainty": uncertainty,
        "playing_time": ip,
        "park_adjusted": pf != NEUTRAL_PARK,
    }
