from __future__ import annotations

"""
Front Office - Rating Recalibration System

Maintains league-wide rating calibration on the 20-80 scouting scale where
50 = average.  Player development (growth/decline) can cause the league-wide
mean to drift from 50 over multiple seasons.  This module detects drift and
applies gradual corrections so that downstream systems (simulation engine,
trade logic, scouting reports) stay properly calibrated.

Design principle (from Baseball Mogul lessons):
  "Rating calibration matters more than rating accuracy.  If your ratings
   drift over time (average creeping from 75 to 82), everything downstream
   breaks.  Recalibrate every season."
"""
import logging
import random
from ..database.db import get_connection, query

logger = logging.getLogger(__name__)

# Rating columns shared across hitters and pitchers
HITTER_RATINGS = ["contact_rating", "power_rating", "speed_rating",
                  "fielding_rating", "arm_rating"]
PITCHER_RATINGS = ["stuff_rating", "control_rating", "stamina_rating"]
ALL_RATINGS = HITTER_RATINGS + PITCHER_RATINGS

# Target mean on the 20-80 scouting scale
TARGET_MEAN = 50

# Only correct if the average drifts more than this many points from 50
DRIFT_THRESHOLD = 2

# Never adjust more than this many points in a single season (gradual fix)
MAX_CORRECTION_PER_SEASON = 3

# Hard floor / ceiling on the 20-80 scale
RATING_FLOOR = 20
RATING_CEILING = 80


# ======================================================================
# PUBLIC API
# ======================================================================

def calibrate_ratings(season: int, db_path: str = None) -> dict:
    """Recalibrate league-wide ratings at end of season.

    For each rating category, calculate the current league-wide average.
    If it has drifted more than DRIFT_THRESHOLD points from TARGET_MEAN,
    apply a gradual correction (capped at MAX_CORRECTION_PER_SEASON).

    Returns a summary dict of adjustments made.
    """
    conn = get_connection(db_path)
    adjustments = {}

    # Calibrate hitter ratings (non-pitchers)
    for rating in HITTER_RATINGS:
        adj = _calibrate_single_rating(conn, rating, is_pitcher=False)
        if adj:
            adjustments[rating] = adj

    # Calibrate pitcher ratings
    for rating in PITCHER_RATINGS:
        adj = _calibrate_single_rating(conn, rating, is_pitcher=True)
        if adj:
            adjustments[rating] = adj

    conn.commit()
    conn.close()

    if adjustments:
        logger.info("Season %d rating calibration applied: %s", season, adjustments)
    else:
        logger.info("Season %d rating calibration: no adjustments needed", season)

    return {
        "season": season,
        "adjustments": adjustments,
        "status": "calibrated" if adjustments else "healthy",
    }


def get_rating_distribution(db_path: str = None) -> dict:
    """Return current distribution stats for each rating category.

    Returns dict keyed by rating name, each containing:
      mean, std_dev, min, max, count
    """
    conn = get_connection(db_path)
    distribution = {}

    for rating in HITTER_RATINGS:
        distribution[rating] = _compute_stats(conn, rating, is_pitcher=False)

    for rating in PITCHER_RATINGS:
        distribution[rating] = _compute_stats(conn, rating, is_pitcher=True)

    conn.close()
    return distribution


def check_rating_health(db_path: str = None) -> dict:
    """Return a health report on whether ratings are drifting.

    For each rating, reports the current mean, how far it is from 50,
    and whether it exceeds the drift threshold.
    """
    distribution = get_rating_distribution(db_path)
    issues = []

    for rating, stats in distribution.items():
        if stats["count"] == 0:
            continue
        drift = stats["mean"] - TARGET_MEAN
        if abs(drift) > DRIFT_THRESHOLD:
            issues.append({
                "rating": rating,
                "mean": stats["mean"],
                "drift": round(drift, 2),
                "severity": "high" if abs(drift) > 5 else "moderate",
            })

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "distribution": distribution,
    }


def normalize_draft_class(season: int, db_path: str = None) -> dict:
    """Ensure a draft class has a proper talent distribution.

    Checks the drafted players from the given season and adjusts if the
    class is skewed too far toward busts or studs.  Uses floor/ceiling
    columns from draft_prospects to detect imbalance, then nudges the
    current ratings of the drafted players toward a healthier curve.

    Returns a summary of any adjustments.
    """
    conn = get_connection(db_path)

    # Get players drafted in this season (those whose draft info matches)
    drafted = conn.execute("""
        SELECT p.id, p.position,
               p.contact_rating, p.power_rating, p.speed_rating,
               p.fielding_rating, p.arm_rating,
               p.stuff_rating, p.control_rating, p.stamina_rating
        FROM players p
        JOIN draft_prospects dp ON dp.drafted_player_id = p.id
        WHERE dp.season = ? AND dp.is_drafted = 1
    """, (season,)).fetchall()

    if not drafted:
        # Fallback: try finding recently created young players for the season
        drafted = conn.execute("""
            SELECT id, position,
                   contact_rating, power_rating, speed_rating,
                   fielding_rating, arm_rating,
                   stuff_rating, control_rating, stamina_rating
            FROM players
            WHERE age <= 22 AND draft_year = ?
        """, (season,)).fetchall()

    if not drafted:
        conn.close()
        return {"season": season, "status": "no_draft_class_found", "adjusted": 0}

    drafted = [dict(row) for row in drafted]
    adjusted_count = 0

    # Compute class-wide means for hitter and pitcher ratings
    hitters = [p for p in drafted if p["position"] not in ("SP", "RP")]
    pitchers = [p for p in drafted if p["position"] in ("SP", "RP")]

    # Normalize hitter ratings
    for rating in HITTER_RATINGS:
        adjusted_count += _normalize_group(conn, hitters, rating)

    # Normalize pitcher ratings
    for rating in PITCHER_RATINGS:
        adjusted_count += _normalize_group(conn, pitchers, rating)

    conn.commit()
    conn.close()

    status = "adjusted" if adjusted_count > 0 else "healthy"
    logger.info("Draft class %d normalization: %d ratings adjusted", season, adjusted_count)
    return {"season": season, "status": status, "adjusted": adjusted_count,
            "players_checked": len(drafted)}


# ======================================================================
# INTERNAL HELPERS
# ======================================================================

def _calibrate_single_rating(conn, rating: str, is_pitcher: bool) -> dict | None:
    """Check and correct drift for a single rating column.

    Returns adjustment info dict, or None if no correction needed.
    """
    position_filter = "IN ('SP', 'RP')" if is_pitcher else "NOT IN ('SP', 'RP')"

    row = conn.execute(f"""
        SELECT AVG({rating}) as mean, COUNT(*) as cnt
        FROM players
        WHERE position {position_filter}
          AND roster_status != 'retired'
          AND {rating} IS NOT NULL
    """).fetchone()

    if not row or row["cnt"] == 0:
        return None

    current_mean = row["mean"]
    drift = current_mean - TARGET_MEAN

    if abs(drift) <= DRIFT_THRESHOLD:
        return None

    # Determine correction: move toward 50 but cap at MAX_CORRECTION_PER_SEASON
    if drift > 0:
        correction = -min(drift, MAX_CORRECTION_PER_SEASON)
    else:
        correction = min(-drift, MAX_CORRECTION_PER_SEASON)

    correction = round(correction)
    if correction == 0:
        return None

    # Apply correction to all active players in this group
    conn.execute(f"""
        UPDATE players
        SET {rating} = MAX({RATING_FLOOR}, MIN({RATING_CEILING}, {rating} + ?))
        WHERE position {position_filter}
          AND roster_status != 'retired'
          AND {rating} IS NOT NULL
    """, (correction,))

    logger.info("Calibrated %s: mean=%.1f, drift=%.1f, correction=%+d",
                rating, current_mean, drift, correction)

    return {
        "previous_mean": round(current_mean, 2),
        "drift": round(drift, 2),
        "correction": correction,
        "new_estimated_mean": round(current_mean + correction, 2),
    }


def _compute_stats(conn, rating: str, is_pitcher: bool) -> dict:
    """Compute mean, std dev, min, max for a rating column."""
    position_filter = "IN ('SP', 'RP')" if is_pitcher else "NOT IN ('SP', 'RP')"

    row = conn.execute(f"""
        SELECT AVG({rating}) as mean,
               COUNT(*) as cnt,
               MIN({rating}) as min_val,
               MAX({rating}) as max_val
        FROM players
        WHERE position {position_filter}
          AND roster_status != 'retired'
          AND {rating} IS NOT NULL
    """).fetchone()

    if not row or row["cnt"] == 0:
        return {"mean": 0, "std_dev": 0, "min": 0, "max": 0, "count": 0}

    # SQLite doesn't have STDDEV, compute manually
    mean = row["mean"]
    variance_row = conn.execute(f"""
        SELECT AVG(({rating} - ?) * ({rating} - ?)) as variance
        FROM players
        WHERE position {position_filter}
          AND roster_status != 'retired'
          AND {rating} IS NOT NULL
    """, (mean, mean)).fetchone()

    std_dev = (variance_row["variance"] ** 0.5) if variance_row["variance"] else 0

    return {
        "mean": round(mean, 2),
        "std_dev": round(std_dev, 2),
        "min": row["min_val"],
        "max": row["max_val"],
        "count": row["cnt"],
    }


def _normalize_group(conn, players: list, rating: str) -> int:
    """Normalize a single rating across a group of drafted players.

    If the group mean is more than 5 points from TARGET_MEAN, shift
    individual ratings to pull the class back toward a balanced distribution.

    Returns count of players adjusted.
    """
    if not players:
        return 0

    values = [p[rating] for p in players if p.get(rating) is not None]
    if not values:
        return 0

    group_mean = sum(values) / len(values)
    drift = group_mean - TARGET_MEAN

    # Draft classes can be slightly above/below average, only correct big skews
    if abs(drift) <= 5:
        return 0

    # Cap correction at 3 points per player
    correction = -min(abs(drift), MAX_CORRECTION_PER_SEASON)
    if drift < 0:
        correction = -correction  # positive correction if mean is too low

    correction = round(correction)
    if correction == 0:
        return 0

    adjusted = 0
    for p in players:
        val = p.get(rating)
        if val is None:
            continue
        new_val = max(RATING_FLOOR, min(RATING_CEILING, val + correction))
        if new_val != val:
            conn.execute(f"UPDATE players SET {rating} = ? WHERE id = ?",
                         (new_val, p["id"]))
            adjusted += 1

    return adjusted
