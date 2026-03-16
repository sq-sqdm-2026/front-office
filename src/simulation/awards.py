"""
Front Office - Season Awards Calculation
Computes MVP, Cy Young, Rookie of the Year, and Gold Glove awards
based on player season statistics.
"""
import json
from ..database.db import query, execute, get_connection


def calculate_season_awards(season: int, db_path=None) -> dict:
    """
    Calculate end-of-season awards for both leagues.

    Returns dict with:
    {
        "mvp_al": [{"player_id": int, "name": str, "team": str, "points": float, "finish": 1}, ...],
        "mvp_nl": [...],
        "cy_young_al": [...],
        "cy_young_nl": [...],
        "roy_al": [...],
        "roy_nl": [...],
        "gold_glove": {"AL": {"C": {...}, "1B": {...}, ...}, "NL": {...}}
    }
    """
    results = {
        "mvp_al": [],
        "mvp_nl": [],
        "cy_young_al": [],
        "cy_young_nl": [],
        "roy_al": [],
        "roy_nl": [],
        "gold_glove": {"AL": {}, "NL": {}}
    }

    # Calculate MVPs
    mvp_al = _calculate_mvp("AL", season, db_path)
    mvp_nl = _calculate_mvp("NL", season, db_path)
    results["mvp_al"] = mvp_al
    results["mvp_nl"] = mvp_nl

    # Calculate Cy Youngs
    cy_al = _calculate_cy_young("AL", season, db_path)
    cy_nl = _calculate_cy_young("NL", season, db_path)
    results["cy_young_al"] = cy_al
    results["cy_young_nl"] = cy_nl

    # Calculate ROY
    roy_al = _calculate_rookie_of_year("AL", season, db_path)
    roy_nl = _calculate_rookie_of_year("NL", season, db_path)
    results["roy_al"] = roy_al
    results["roy_nl"] = roy_nl

    # Calculate Gold Gloves
    gg_al = _calculate_gold_gloves("AL", season, db_path)
    gg_nl = _calculate_gold_gloves("NL", season, db_path)
    results["gold_glove"]["AL"] = gg_al
    results["gold_glove"]["NL"] = gg_nl

    # Store all awards in database
    _store_awards_in_db(season, results, db_path)

    return results


def _calculate_mvp(league: str, season: int, db_path=None) -> list:
    """Calculate MVP for a league. Returns top 5 finishers with vote points."""

    # Get all batters in the league with their season stats
    batters = query("""
        SELECT
            bs.player_id,
            p.first_name,
            p.last_name,
            p.team_id,
            t.abbreviation,
            t.league,
            bs.hits,
            bs.bb,
            bs.hbp,
            bs.hr,
            bs.rbi,
            bs.sb,
            bs.runs,
            bs.so,
            COUNT(DISTINCT s.id) as games
        FROM batting_stats bs
        JOIN players p ON p.id = bs.player_id
        JOIN teams t ON t.id = p.team_id
        LEFT JOIN batting_lines bl ON bl.player_id = p.id
        LEFT JOIN schedule s ON s.id = bl.schedule_id AND s.season = ?
        WHERE bs.season = ? AND t.league = ? AND bs.level = 'MLB'
        GROUP BY bs.player_id
        HAVING games >= 100
        ORDER BY hits DESC
    """, (season, season, league), db_path=db_path)

    if not batters:
        return []

    # Calculate MVP score for each batter
    candidates = []
    for b in batters:
        # WAR proxy: (hits + bb + hbp) * 0.5 + hr * 1.5 + rbi * 0.3 + sb * 0.3 + runs * 0.3 - so * 0.1
        mvp_score = (
            (b["hits"] + b["bb"] + b["hbp"]) * 0.5 +
            b["hr"] * 1.5 +
            b["rbi"] * 0.3 +
            b["sb"] * 0.3 +
            b["runs"] * 0.3 -
            b["so"] * 0.1
        )

        # Get team wins for this player's team
        team_wins = query("""
            SELECT COUNT(*) as wins FROM schedule
            WHERE season = ? AND (
                (home_team_id = ? AND home_score > away_score) OR
                (away_team_id = ? AND away_score > home_score)
            )
        """, (season, b["team_id"], b["team_id"]), db_path=db_path)[0]["wins"]

        # Boost for winning teams (top 5 teams get bonus)
        if team_wins >= 95:
            mvp_score *= 1.15
        elif team_wins >= 90:
            mvp_score *= 1.10
        elif team_wins >= 85:
            mvp_score *= 1.05

        candidates.append({
            "player_id": b["player_id"],
            "name": f"{b['first_name']} {b['last_name']}",
            "team": b["abbreviation"],
            "team_id": b["team_id"],
            "points": round(mvp_score, 2),
            "games": b["games"]
        })

    # Sort by points and return top 5
    candidates.sort(key=lambda x: x["points"], reverse=True)
    for i, candidate in enumerate(candidates[:5]):
        candidate["finish"] = i + 1

    return candidates[:5]


def _calculate_cy_young(league: str, season: int, db_path=None) -> list:
    """Calculate Cy Young for a league. Returns top 5 finishers."""

    # Get all pitchers in the league with their season stats
    pitchers = query("""
        SELECT
            ps.player_id,
            p.first_name,
            p.last_name,
            p.team_id,
            t.abbreviation,
            ps.wins,
            ps.losses,
            ps.so,
            ps.er,
            ps.ip_outs,
            ps.saves,
            ps.bb,
            ps.hr_allowed,
            ps.games_started
        FROM pitching_stats ps
        JOIN players p ON p.id = ps.player_id
        JOIN teams t ON t.id = p.team_id
        WHERE ps.season = ? AND t.league = ? AND ps.level = 'MLB'
            AND ps.ip_outs > 0
        ORDER BY ps.wins DESC, ps.ip_outs DESC
    """, (season, league), db_path=db_path)

    if not pitchers:
        return []

    candidates = []
    for p in pitchers:
        ip = p["ip_outs"] / 3.0  # Convert outs to innings

        # Minimum innings requirement
        if p["games_started"] > 0 and ip < 100:
            continue  # Starter minimum: 100 IP
        if p["games_started"] == 0 and ip < 50:
            continue  # Reliever minimum: 50 IP

        # Cy Young formula: wins * 5 + so * 0.5 - er * 2 + saves * 3 + (ip_outs/3) * 0.5 - bb * 0.3 - hr_allowed * 1.5
        cy_score = (
            p["wins"] * 5 +
            p["so"] * 0.5 -
            p["er"] * 2 +
            p["saves"] * 3 +
            (p["ip_outs"] / 3.0) * 0.5 -
            p["bb"] * 0.3 -
            p["hr_allowed"] * 1.5
        )

        candidates.append({
            "player_id": p["player_id"],
            "name": f"{p['first_name']} {p['last_name']}",
            "team": p["abbreviation"],
            "team_id": p["team_id"],
            "points": round(cy_score, 2),
            "wins": p["wins"],
            "ip": round(ip, 1)
        })

    candidates.sort(key=lambda x: x["points"], reverse=True)
    for i, candidate in enumerate(candidates[:5]):
        candidate["finish"] = i + 1

    return candidates[:5]


def _calculate_rookie_of_year(league: str, season: int, db_path=None) -> list:
    """Calculate Rookie of the Year. Same formulas but only for players with <= 1 service year."""

    # Get batters and pitchers eligible as rookies
    batters = query("""
        SELECT
            bs.player_id,
            p.first_name,
            p.last_name,
            p.team_id,
            t.abbreviation,
            p.service_years,
            bs.hits,
            bs.bb,
            bs.hbp,
            bs.hr,
            bs.rbi,
            bs.sb,
            bs.runs,
            bs.so,
            COUNT(DISTINCT bl.schedule_id) as games
        FROM batting_stats bs
        JOIN players p ON p.id = bs.player_id
        JOIN teams t ON t.id = p.team_id
        LEFT JOIN batting_lines bl ON bl.player_id = p.id
        LEFT JOIN schedule s ON s.id = bl.schedule_id AND s.season = ?
        WHERE bs.season = ? AND t.league = ? AND bs.level = 'MLB'
            AND p.service_years <= 1.0
        GROUP BY bs.player_id
        HAVING games >= 50
    """, (season, season, league), db_path=db_path)

    pitchers = query("""
        SELECT
            ps.player_id,
            p.first_name,
            p.last_name,
            p.team_id,
            t.abbreviation,
            p.service_years,
            ps.wins,
            ps.so,
            ps.er,
            ps.ip_outs,
            ps.saves,
            ps.bb,
            ps.hr_allowed,
            ps.games_started
        FROM pitching_stats ps
        JOIN players p ON p.id = ps.player_id
        JOIN teams t ON t.id = p.team_id
        WHERE ps.season = ? AND t.league = ? AND ps.level = 'MLB'
            AND p.service_years <= 1.0
            AND ps.ip_outs > 0
    """, (season, league), db_path=db_path)

    candidates = []

    # Score batters
    for b in batters:
        roy_score = (
            (b["hits"] + b["bb"] + b["hbp"]) * 0.5 +
            b["hr"] * 1.5 +
            b["rbi"] * 0.3 +
            b["sb"] * 0.3 +
            b["runs"] * 0.3 -
            b["so"] * 0.1
        )

        candidates.append({
            "player_id": b["player_id"],
            "name": f"{b['first_name']} {b['last_name']}",
            "team": b["abbreviation"],
            "team_id": b["team_id"],
            "points": round(roy_score, 2),
            "finish": 0
        })

    # Score pitchers
    for p in pitchers:
        ip = p["ip_outs"] / 3.0

        if p["games_started"] > 0 and ip < 50:
            continue
        if p["games_started"] == 0 and ip < 20:
            continue

        roy_score = (
            p["wins"] * 5 +
            p["so"] * 0.5 -
            p["er"] * 2 +
            p["saves"] * 3 +
            (p["ip_outs"] / 3.0) * 0.5 -
            p["bb"] * 0.3 -
            p["hr_allowed"] * 1.5
        )

        candidates.append({
            "player_id": p["player_id"],
            "name": f"{p['first_name']} {p['last_name']}",
            "team": p["abbreviation"],
            "team_id": p["team_id"],
            "points": round(roy_score, 2),
            "finish": 0
        })

    candidates.sort(key=lambda x: x["points"], reverse=True)
    for i, candidate in enumerate(candidates[:3]):
        candidate["finish"] = i + 1

    return candidates[:3]


def _calculate_gold_gloves(league: str, season: int, db_path=None) -> dict:
    """Calculate Gold Glove awards (one per position per league). Returns dict keyed by position."""

    positions = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
    gold_gloves = {}

    for position in positions:
        # Get all players who played this position with fielding stats
        fielders = query("""
            SELECT
                p.id,
                p.first_name,
                p.last_name,
                p.team_id,
                t.abbreviation,
                p.fielding_rating,
                COUNT(DISTINCT bl.schedule_id) as games_at_pos
            FROM players p
            JOIN teams t ON t.id = p.team_id
            LEFT JOIN batting_lines bl ON bl.player_id = p.id
                AND bl.position_played = ?
            LEFT JOIN schedule s ON s.id = bl.schedule_id AND s.season = ?
            WHERE p.position = ? AND t.league = ? AND p.roster_status = 'active'
            GROUP BY p.id
            HAVING games_at_pos >= 30
            ORDER BY p.fielding_rating DESC
        """, (position, season, position, league), db_path=db_path)

        if fielders and len(fielders) > 0:
            winner = fielders[0]
            gold_gloves[position] = {
                "player_id": winner["id"],
                "name": f"{winner['first_name']} {winner['last_name']}",
                "team": winner["abbreviation"],
                "team_id": winner["team_id"],
                "fielding_rating": winner["fielding_rating"],
                "games": winner["games_at_pos"]
            }

    return gold_gloves


def _store_awards_in_db(season: int, results: dict, db_path=None):
    """Store calculated awards in the database."""
    conn = get_connection(db_path)

    all_awards = []

    # MVP awards
    for award_list, league in [
        (results["mvp_al"], "AL"),
        (results["mvp_nl"], "NL")
    ]:
        for award in award_list:
            all_awards.append(("mvp", league, award["player_id"], award["team_id"], None, award["points"], award["finish"]))

    # Cy Young awards
    for award_list, league in [
        (results["cy_young_al"], "AL"),
        (results["cy_young_nl"], "NL")
    ]:
        for award in award_list:
            all_awards.append(("cy_young", league, award["player_id"], award["team_id"], None, award["points"], award["finish"]))

    # ROY awards
    for award_list, league in [
        (results["roy_al"], "AL"),
        (results["roy_nl"], "NL")
    ]:
        for award in award_list:
            all_awards.append(("roy", league, award["player_id"], award["team_id"], None, award["points"], award["finish"]))

    # Gold Glove awards
    for league in ["AL", "NL"]:
        for position, award in results["gold_glove"][league].items():
            all_awards.append(("gold_glove", league, award["player_id"], award["team_id"], position, None, 1))

    # Insert all awards
    for award_type, league, player_id, team_id, position, vote_points, finish in all_awards:
        try:
            conn.execute("""
                INSERT OR REPLACE INTO awards
                (season, award_type, league, player_id, team_id, position, vote_points, finish)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (season, award_type, league, player_id, team_id, position, vote_points, finish))
        except Exception as e:
            print(f"Error storing award: {e}")

    conn.commit()
    conn.close()


def get_season_awards(season: int, db_path=None) -> dict:
    """Retrieve all awards for a season from the database."""
    awards = query("""
        SELECT
            award_type,
            league,
            player_id,
            p.first_name,
            p.last_name,
            team_id,
            t.abbreviation,
            position,
            vote_points,
            finish
        FROM awards a
        JOIN players p ON p.id = a.player_id
        JOIN teams t ON t.id = a.team_id
        WHERE season = ?
        ORDER BY award_type, league, finish
    """, (season,), db_path=db_path)

    result = {
        "mvp_al": [],
        "mvp_nl": [],
        "cy_young_al": [],
        "cy_young_nl": [],
        "roy_al": [],
        "roy_nl": [],
        "gold_glove": {"AL": {}, "NL": {}}
    }

    for award in awards:
        award_type = award["award_type"]
        league = award["league"]

        award_dict = {
            "player_id": award["player_id"],
            "name": f"{award['first_name']} {award['last_name']}",
            "team": award["abbreviation"],
            "team_id": award["team_id"],
            "finish": award["finish"]
        }

        if award["vote_points"] is not None:
            award_dict["points"] = award["vote_points"]

        if award_type == "mvp":
            key = f"mvp_{league.lower()}"
            result[key].append(award_dict)
        elif award_type == "cy_young":
            key = f"cy_young_{league.lower()}"
            result[key].append(award_dict)
        elif award_type == "roy":
            key = f"roy_{league.lower()}"
            result[key].append(award_dict)
        elif award_type == "gold_glove":
            result["gold_glove"][league][award["position"]] = award_dict

    return result
