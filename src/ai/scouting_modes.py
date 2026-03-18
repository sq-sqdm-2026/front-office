"""
Front Office - Scouting Modes
Three display modes for player ratings: traditional, stat_based, variable.
Each has different uncertainty/accuracy based on scout quality and playing time.
"""
import json
import random
from ..database.db import query, execute
from .mle import calculate_mle_ratings


def _clamp(value: int, lo: int = 20, hi: int = 80) -> int:
    """Clamp a rating to 20-80 scouting scale."""
    return max(lo, min(hi, int(value)))


def get_scouting_mode():
    """Get the current scouting mode from game_state."""
    result = query("SELECT scouting_mode FROM game_state WHERE id=1")
    if result:
        return result[0]["scouting_mode"]
    return "traditional"


def _get_scouted_ratings_from_cache(player_id: int, season: int, mode: str) -> dict:
    """Check if we have cached scouted ratings for this player in this mode."""
    player = query("SELECT scouted_ratings_json FROM players WHERE id=?", (player_id,))
    if not player or not player[0].get("scouted_ratings_json"):
        return None

    try:
        cached = json.loads(player[0]["scouted_ratings_json"])
        if (cached.get("season") == season and
            cached.get("mode") == mode and
            cached.get("scouted")):
            return cached["scouted"]
    except (json.JSONDecodeError, TypeError):
        pass

    return None


def _save_scouted_ratings_to_cache(player_id: int, season: int, mode: str, scouted: dict):
    """Cache the scouted ratings for a player."""
    cache_data = {
        "season": season,
        "mode": mode,
        "scouted": scouted,
    }
    execute(
        "UPDATE players SET scouted_ratings_json=? WHERE id=?",
        (json.dumps(cache_data), player_id)
    )


def apply_traditional_scouting(player: dict, team_id: int, user_team_id: int,
                               season: int = 2026, is_user_team: bool = False) -> dict:
    """
    Traditional Scouting Mode:
    - True ratings are hidden
    - Displayed ratings = true_rating + random_noise based on scouting budget
    - Better scouting budget = smaller noise margin
    - User's team gets scout quality based on their budget
    - Other teams' players get wider margin (1.5x the margin)
    """
    # Check cache first
    cached = _get_scouted_ratings_from_cache(player["id"], season, "traditional")
    if cached:
        return cached

    # Get the scouting team (user's team)
    scout_team = query("SELECT scouting_staff_budget FROM teams WHERE id=?", (user_team_id,))
    scouting_budget = scout_team[0]["scouting_staff_budget"] if scout_team else 10000000

    # Calculate scout quality: $2M=10, $10M=50, $20M=100
    scout_quality = min(100, max(20, scouting_budget // 200000))

    # Base margin: elite=2, avg=8, poor=15
    base_margin = max(2, int(15 - scout_quality * 0.13))

    # If this is an opponent's player, use wider margin (1.5x)
    if not is_user_team:
        margin = int(base_margin * 1.5)
    else:
        margin = base_margin

    # Apply noise to each rating
    scouted = {}
    pitcher_ratings = ["stuff_rating", "control_rating", "stamina_rating"]
    hitter_ratings = ["contact_rating", "power_rating", "speed_rating", "fielding_rating", "arm_rating"]

    all_ratings = pitcher_ratings + hitter_ratings

    for rating_field in all_ratings:
        true_val = player.get(rating_field, 50)
        if true_val is not None:
            noise = random.randint(-margin, margin)
            displayed = _clamp(true_val + noise)
            scouted[rating_field] = displayed

    # Cache the scouted ratings
    _save_scouted_ratings_to_cache(player["id"], season, "traditional", scouted)

    return scouted


def _get_mlb_playing_time(player_id: int, season: int, is_pitcher: bool) -> dict:
    """Get MLB playing time stats for weighting decisions.
    Returns dict with 'pa' (plate appearances) for hitters or 'ip' (innings pitched) for pitchers.
    """
    if is_pitcher:
        stats = query("""
            SELECT ip_outs FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season))
        ip = (stats[0]["ip_outs"] / 3.0) if stats and stats[0].get("ip_outs") else 0
        return {"ip": ip}
    else:
        stats = query("""
            SELECT pa FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season))
        pa = stats[0]["pa"] if stats and stats[0].get("pa") else 0
        return {"pa": pa}


def _get_age_uncertainty(player: dict) -> int:
    """Calculate uncertainty margin based on player age.
    Younger players have bigger margins, veterans have smaller.
    """
    age = player.get("age", 25)
    if age <= 22:
        return 8  # Young prospect - high uncertainty
    elif age <= 24:
        return 6  # Still developing
    elif age <= 27:
        return 4  # Approaching/at prime
    elif age <= 30:
        return 2  # Established veteran
    else:
        return 1  # Veteran - very known quantity


def _blend_ratings(mle_ratings: dict, actual_ratings: dict, mle_weight: float,
                   rating_fields: list) -> dict:
    """Blend MLE-derived ratings with actual underlying ratings.

    Args:
        mle_ratings: Ratings from MLE calculation
        actual_ratings: True player ratings from database
        mle_weight: Weight for MLE ratings (0.0-1.0), remainder goes to actual
        rating_fields: List of rating field names to blend

    Returns:
        Dict of blended ratings
    """
    actual_weight = 1.0 - mle_weight
    blended = {}
    for field in rating_fields:
        mle_val = mle_ratings.get(field)
        actual_val = actual_ratings.get(field)
        if mle_val is not None and actual_val is not None:
            blended[field] = _clamp(int(round(mle_val * mle_weight + actual_val * actual_weight)))
        elif mle_val is not None:
            blended[field] = mle_val
        elif actual_val is not None:
            blended[field] = actual_val
        else:
            blended[field] = None
    return blended


def apply_stat_based_scouting(player: dict, season: int = 2026) -> dict:
    """
    Stat-Based (MLE) Scouting Mode:
    - Minor league players: ratings derived entirely from MLE-adjusted stats
      (park-factor normalized via mle.py)
    - MLB veterans (200+ PA or 50+ IP): 80% actual MLB stats, 20% MLE
    - MLB players with < 200 PA or < 50 IP: 50% actual, 50% MLE
    - Age-based uncertainty margins applied on top
    - Reports indicate whether ratings are MLE-derived or actual-stats-derived
    """
    # Check cache first
    cached = _get_scouted_ratings_from_cache(player["id"], season, "stat_based")
    if cached:
        return cached

    is_pitcher = player.get("position", "") in ("SP", "RP")

    # Calculate MLE ratings (now park-factor adjusted via mle.py)
    mle_result = calculate_mle_ratings(player["id"], season)

    if not mle_result:
        # No stats available
        return {
            "contact_rating": None,
            "power_rating": None,
            "speed_rating": None,
            "fielding_rating": None,
            "arm_rating": None,
            "stuff_rating": None,
            "control_rating": None,
            "stamina_rating": None,
            "rating_source": "no_data",
        }

    pitcher_ratings = ["stuff_rating", "control_rating", "stamina_rating"]
    hitter_ratings = ["contact_rating", "power_rating", "speed_rating",
                      "fielding_rating", "arm_rating"]

    # Determine the source and weighting
    from_level = mle_result.get("from_level", "")
    rating_source = "mle"  # default: pure MLE
    mle_weight = 1.0

    if from_level == "MLB":
        # MLB player - blend actual ratings with MLE based on playing time
        pt = _get_mlb_playing_time(player["id"], season, is_pitcher)

        if is_pitcher:
            ip = pt.get("ip", 0)
            if ip >= 50:
                # Veteran pitcher: 80% actual, 20% MLE
                mle_weight = 0.20
                rating_source = "mlb_veteran"
            else:
                # Limited sample pitcher: 50/50
                mle_weight = 0.50
                rating_source = "mlb_limited"
        else:
            pa = pt.get("pa", 0)
            if pa >= 200:
                # Veteran hitter: 80% actual, 20% MLE
                mle_weight = 0.20
                rating_source = "mlb_veteran"
            else:
                # Limited sample hitter: 50/50
                mle_weight = 0.50
                rating_source = "mlb_limited"

        # Blend the ratings
        all_fields = pitcher_ratings + hitter_ratings
        blended = _blend_ratings(mle_result, player, mle_weight, all_fields)
    else:
        # Minor league player: pure MLE-derived ratings replace underlying ratings
        blended = {}
        for field in pitcher_ratings + hitter_ratings:
            blended[field] = mle_result.get(field)

    # Apply age-based uncertainty margins
    age_uncertainty = _get_age_uncertainty(player)

    # Scale uncertainty: minor leaguers get full age uncertainty,
    # MLB veterans get reduced uncertainty
    if rating_source == "mlb_veteran":
        uncertainty = max(1, age_uncertainty // 2)
    elif rating_source == "mlb_limited":
        uncertainty = max(2, int(age_uncertainty * 0.75))
    else:
        uncertainty = age_uncertainty

    scouted = {}
    for field in pitcher_ratings + hitter_ratings:
        val = blended.get(field)
        if val is not None:
            noise = random.randint(-uncertainty, uncertainty)
            scouted[field] = _clamp(val + noise)
        else:
            scouted[field] = None

    # Attach metadata for scouting reports
    scouted["rating_source"] = rating_source
    scouted["from_level"] = from_level
    scouted["park_adjusted"] = mle_result.get("park_adjusted", False)
    scouted["mle_weight"] = mle_weight
    scouted["uncertainty"] = uncertainty

    # Cache the scouted ratings
    _save_scouted_ratings_to_cache(player["id"], season, "stat_based", scouted)

    return scouted


def apply_variable_scouting(player: dict, team_id: int, user_team_id: int,
                           season: int = 2026, is_user_team: bool = False) -> dict:
    """
    Variable Scouting Mode:
    - Combines MLE and Traditional approaches
    - Starts with MLE ratings as the base
    - As a player accumulates playing time, uncertainty shrinks automatically
    - For hitters: games_played; for pitchers: innings_pitched
    - After 200+ games (or 100+ IP for pitchers), MLE ratings become very accurate
    - Low playing time players get traditional uncertainty instead
    """
    # Check cache first
    cached = _get_scouted_ratings_from_cache(player["id"], season, "variable")
    if cached:
        return cached

    is_pitcher = player["position"] in ("SP", "RP")

    # Get playing time
    if is_pitcher:
        stats = query("""
            SELECT ip_outs FROM pitching_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player["id"], season))
        playing_time = (stats[0]["ip_outs"] / 3.0) if stats and stats[0]["ip_outs"] else 0
        max_playing_time = 100  # 100 IP = well-known
    else:
        stats = query("""
            SELECT games FROM batting_stats
            WHERE player_id=? AND season=? AND level='MLB'
        """, (player["id"], season))
        playing_time = stats[0]["games"] if stats and stats[0]["games"] else 0
        max_playing_time = 200  # 200 games = well-known

    # Get MLE ratings as the starting point
    mle_result = calculate_mle_ratings(player["id"], season)

    # If player has sufficient playing time, use MLE ratings
    min_playing_time_for_mle = 50 if is_pitcher else 100
    if mle_result and playing_time >= min_playing_time_for_mle:
        # Use MLE ratings with uncertainty that shrinks with playing time
        scouted = {}
        pitcher_ratings = ["stuff_rating", "control_rating", "stamina_rating"]
        hitter_ratings = ["contact_rating", "power_rating", "speed_rating", "fielding_rating", "arm_rating"]
        all_ratings = pitcher_ratings + hitter_ratings

        # Shrink margin based on playing time
        # At min_playing_time: uncertainty = 5
        # At max_playing_time: uncertainty = 1
        playing_time_ratio = min(1.0, (playing_time - min_playing_time_for_mle) / (max_playing_time - min_playing_time_for_mle))
        uncertainty = max(1, int(5 * (1.0 - playing_time_ratio * 0.8)))

        for rating_field in all_ratings:
            mle_val = mle_result.get(rating_field)
            if mle_val is not None:
                # Add small uncertainty around MLE rating
                noise = random.randint(-uncertainty, uncertainty)
                displayed = _clamp(mle_val + noise)
                scouted[rating_field] = displayed
            else:
                scouted[rating_field] = None

        # Cache the scouted ratings
        _save_scouted_ratings_to_cache(player["id"], season, "variable", scouted)
        return scouted

    # Fall back to traditional approach for players with low playing time
    scout_team = query("SELECT scouting_staff_budget FROM teams WHERE id=?", (user_team_id,))
    scouting_budget = scout_team[0]["scouting_staff_budget"] if scout_team else 10000000
    scout_quality = min(100, max(20, scouting_budget // 200000))
    base_margin = max(2, int(15 - scout_quality * 0.13))

    if not is_user_team:
        base_margin = int(base_margin * 1.5)

    # Apply noise to each rating
    scouted = {}
    pitcher_ratings = ["stuff_rating", "control_rating", "stamina_rating"]
    hitter_ratings = ["contact_rating", "power_rating", "speed_rating", "fielding_rating", "arm_rating"]

    all_ratings = pitcher_ratings + hitter_ratings

    for rating_field in all_ratings:
        true_val = player.get(rating_field, 50)
        if true_val is not None:
            noise = random.randint(-base_margin, base_margin)
            displayed = _clamp(true_val + noise)
            scouted[rating_field] = displayed

    # Cache the scouted ratings
    _save_scouted_ratings_to_cache(player["id"], season, "variable", scouted)

    return scouted


def get_displayed_ratings(player: dict, user_team_id: int, season: int = 2026) -> dict:
    """
    Get the displayed ratings for a player based on the current scouting mode.
    This is the main entry point for getting player ratings to display.

    Returns the true rating fields with scouting adjustments applied.
    """
    mode = get_scouting_mode()
    is_user_team = (player.get("team_id") == user_team_id)

    if mode == "stat_based":
        scouted = apply_stat_based_scouting(player, season)
    elif mode == "variable":
        scouted = apply_variable_scouting(player, player.get("team_id"), user_team_id, season, is_user_team)
    else:  # traditional (default)
        scouted = apply_traditional_scouting(player, player.get("team_id"), user_team_id, season, is_user_team)

    # Merge scouted values back into player object
    result = player.copy()

    # MLE metadata fields to pass through (not player rating fields)
    mle_metadata_fields = {"rating_source", "from_level", "park_adjusted",
                           "mle_weight", "uncertainty"}

    for field, value in scouted.items():
        if field in mle_metadata_fields:
            # Always include metadata
            result[field] = value
        elif value is not None:
            result[field] = value

    return result
