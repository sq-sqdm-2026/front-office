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


def apply_stat_based_scouting(player: dict, season: int = 2026) -> dict:
    """
    Stat-Based (MLE) Scouting Mode:
    - Ratings projected entirely from accumulated stats using MLE
    - Players with no stats show "?" (None)
    - Uncertainty shrinks with more playing time
    """
    # Check cache first
    cached = _get_scouted_ratings_from_cache(player["id"], season, "stat_based")
    if cached:
        return cached

    # Calculate MLE ratings
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
        }

    # Return MLE ratings (they already include uncertainty within the calculation)
    scouted = {
        "contact_rating": mle_result.get("contact_rating"),
        "power_rating": mle_result.get("power_rating"),
        "speed_rating": mle_result.get("speed_rating"),
        "fielding_rating": mle_result.get("fielding_rating"),
        "arm_rating": mle_result.get("arm_rating"),
        "stuff_rating": mle_result.get("stuff_rating"),
        "control_rating": mle_result.get("control_rating"),
        "stamina_rating": mle_result.get("stamina_rating"),
    }

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
    for field, value in scouted.items():
        if value is not None:
            result[field] = value

    return result
