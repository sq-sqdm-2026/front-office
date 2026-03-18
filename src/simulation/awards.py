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

    # Calculate MVP score using WAR-proxy (wOBA-based)
    candidates = []
    for b in batters:
        ab = max(1, b["ab"])
        pa = ab + b["bb"] + b["hbp"] + b.get("sf", 0)
        singles = b["hits"] - b["doubles"] - b["triples"] - b["hr"]

        # wOBA-style weighted on-base: weights from FanGraphs
        woba = (b["bb"] * 0.69 + b["hbp"] * 0.72 + singles * 0.88 +
                b["doubles"] * 1.27 + b["triples"] * 1.62 + b["hr"] * 2.10) / max(1, pa)

        # WAR proxy = wOBA-based runs above average + baserunning + position
        batting_runs = (woba - 0.320) * pa * 1.2  # runs above average
        baserunning = b["sb"] * 0.2 - b.get("cs", 0) * 0.4
        # Position adjustment (C/SS/CF get bonus, 1B/DH get penalty)
        pos = b.get("position", "")
        pos_adj = {"C": 10, "SS": 7, "CF": 3, "2B": 3, "3B": 2,
                   "RF": -2, "LF": -5, "1B": -10, "DH": -15}.get(pos, 0)

        mvp_score = batting_runs + baserunning + pos_adj

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

        # Cy Young: FIP-based WAR proxy
        # FIP = (13*HR + 3*BB - 2*SO) / IP + constant(~3.10)
        fip = ((13 * p["hr_allowed"] + 3 * p["bb"] - 2 * p["so"]) / max(1, ip)) + 3.10
        # WAR proxy from FIP: lower FIP = more WAR
        fip_war = max(0, (4.50 - fip) * ip / 9.0)
        # Wins bonus (voters still care about wins)
        win_bonus = p["wins"] * 0.8
        # Save bonus for closers
        save_bonus = p["saves"] * 0.5
        cy_score = fip_war * 10 + win_bonus + save_bonus

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
        elif award_type == "silver_slugger":
            result.setdefault("silver_slugger", {"AL": {}, "NL": {}})
            result["silver_slugger"][league][award.get("position", "DH")] = award_dict
        elif award_type == "hof":
            result.setdefault("hof_inductees", [])
            result["hof_inductees"].append(award_dict)

    return result


# ============================================================
# WAR CALCULATION
# ============================================================
def calculate_war(player_id: int, season: int, db_path=None) -> float:
    """Calculate Wins Above Replacement for a player-season.

    Uses a simplified WAR formula:
    Batters: (batting_runs + baserunning_runs + fielding_runs + positional_adj) / runs_per_win
    Pitchers: (league_avg_runs - pitcher_runs) * IP/9 / runs_per_win
    """
    RUNS_PER_WIN = 10.0  # Roughly 10 runs = 1 win

    player = query("SELECT position FROM players WHERE id=?", (player_id,), db_path=db_path)
    if not player:
        return 0.0

    is_pitcher = player[0]["position"] in ("SP", "RP")

    if is_pitcher:
        stats = query("""
            SELECT ip_outs, er, so, bb, hr_allowed, games, games_started
            FROM pitching_stats WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season), db_path=db_path)
        if not stats or stats[0]["ip_outs"] < 9:
            return 0.0
        s = stats[0]
        ip = s["ip_outs"] / 3.0
        era = 9.0 * s["er"] / ip if ip > 0 else 9.0
        # League average ERA ~4.20, replacement level ~5.50
        replacement_era = 5.50
        runs_saved = (replacement_era - era) / 9.0 * ip
        fip = ((13 * s["hr_allowed"] + 3 * s["bb"] - 2 * s["so"]) / ip + 3.20) if ip > 0 else 5.0
        fip_runs_saved = (5.50 - fip) / 9.0 * ip
        # Blend ERA-based and FIP-based
        war = (runs_saved * 0.5 + fip_runs_saved * 0.5) / RUNS_PER_WIN
        return round(max(-2.0, war), 1)
    else:
        stats = query("""
            SELECT ab, hits, doubles, triples, hr, bb, hbp, sb, cs, sf, so, runs, rbi, games
            FROM batting_stats WHERE player_id=? AND season=? AND level='MLB'
        """, (player_id, season), db_path=db_path)
        if not stats or stats[0]["ab"] < 50:
            return 0.0
        s = stats[0]
        pa = s["ab"] + s["bb"] + s["hbp"] + s["sf"]
        if pa == 0:
            return 0.0

        # Batting runs: wOBA-based
        singles = s["hits"] - s["doubles"] - s["triples"] - s["hr"]
        woba = (0.69 * s["bb"] + 0.72 * s["hbp"] + 0.88 * singles +
                1.27 * s["doubles"] + 1.62 * s["triples"] + 2.10 * s["hr"]) / pa
        league_woba = 0.320  # approximate
        woba_scale = 1.15
        batting_runs = (woba - league_woba) / woba_scale * pa

        # Baserunning runs (simplified: SB/CS)
        br_runs = s["sb"] * 0.2 - s["cs"] * 0.45

        # Positional adjustment per 162 games
        pos_adj_map = {
            "C": 12.5, "SS": 7.5, "2B": 3.0, "3B": 2.5, "CF": 2.5,
            "LF": -7.5, "RF": -7.5, "1B": -12.5, "DH": -17.5
        }
        pos = player[0]["position"]
        games_frac = s["games"] / 162.0
        pos_adj = pos_adj_map.get(pos, 0) * games_frac

        # Fielding (simplified: use fielding_rating as proxy)
        p_data = query("SELECT fielding_rating FROM players WHERE id=?",
                        (player_id,), db_path=db_path)
        fld_rating = p_data[0]["fielding_rating"] if p_data else 50
        fielding_runs = (fld_rating - 50) * 0.15 * games_frac

        # Replacement level: ~20 runs per 600 PA
        replacement_runs = 20.0 * (pa / 600.0)

        war = (batting_runs + br_runs + fielding_runs + pos_adj + replacement_runs) / RUNS_PER_WIN
        return round(max(-2.0, war), 1)


def calculate_all_war(season: int, db_path=None) -> list:
    """Calculate WAR for all players with enough playing time in a season."""
    # Batters
    batters = query("""
        SELECT DISTINCT bs.player_id FROM batting_stats bs
        WHERE bs.season=? AND bs.level='MLB' AND bs.ab >= 50
    """, (season,), db_path=db_path)

    # Pitchers
    pitchers = query("""
        SELECT DISTINCT ps.player_id FROM pitching_stats ps
        WHERE ps.season=? AND ps.level='MLB' AND ps.ip_outs >= 30
    """, (season,), db_path=db_path)

    results = []
    seen = set()
    for row in (batters or []) + (pitchers or []):
        pid = row["player_id"]
        if pid in seen:
            continue
        seen.add(pid)
        war = calculate_war(pid, season, db_path)
        p = query("SELECT first_name, last_name, position, team_id FROM players WHERE id=?",
                   (pid,), db_path=db_path)
        if p:
            results.append({
                "player_id": pid,
                "name": f"{p[0]['first_name']} {p[0]['last_name']}",
                "position": p[0]["position"],
                "team_id": p[0]["team_id"],
                "war": war,
            })

    results.sort(key=lambda x: x["war"], reverse=True)
    return results


# ============================================================
# SILVER SLUGGER AWARDS
# ============================================================
def _calculate_silver_sluggers(league: str, season: int, db_path=None) -> dict:
    """Silver Slugger: best offensive player at each position."""
    positions = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
    winners = {}

    for pos in positions:
        batters = query("""
            SELECT bs.player_id, p.first_name, p.last_name, p.team_id, t.abbreviation,
                   bs.ab, bs.hits, bs.hr, bs.rbi, bs.bb, bs.doubles, bs.triples,
                   CASE WHEN bs.ab > 0 THEN 1.0 * bs.hits / bs.ab END as avg
            FROM batting_stats bs
            JOIN players p ON p.id = bs.player_id
            JOIN teams t ON t.id = p.team_id
            WHERE p.position=? AND t.league=? AND bs.season=? AND bs.level='MLB' AND bs.ab >= 100
            ORDER BY (bs.hr * 4 + bs.rbi * 1.5 + bs.hits * 1 + bs.doubles * 1.5 + bs.bb * 0.5) DESC
            LIMIT 1
        """, (pos, league, season), db_path=db_path)

        if batters:
            b = batters[0]
            winners[pos] = {
                "player_id": b["player_id"],
                "name": f"{b['first_name']} {b['last_name']}",
                "team": b["abbreviation"],
                "hr": b["hr"],
                "rbi": b["rbi"],
                "avg": round(b["avg"], 3) if b["avg"] else 0,
            }

    return winners


# ============================================================
# HALL OF FAME VOTING
# ============================================================
def _check_hall_of_fame_eligibility(season: int, db_path=None) -> list:
    """Find retired players eligible for Hall of Fame and vote them in."""
    # Players must be retired for 5+ seasons and have 10+ MLB seasons
    eligible = query("""
        SELECT p.id, p.first_name, p.last_name, p.position, p.age,
               COUNT(DISTINCT bs.season) as batting_seasons,
               SUM(bs.hits) as career_hits, SUM(bs.hr) as career_hr, SUM(bs.rbi) as career_rbi
        FROM players p
        LEFT JOIN batting_stats bs ON bs.player_id = p.id AND bs.level='MLB'
        WHERE p.roster_status = 'retired'
        GROUP BY p.id
        HAVING batting_seasons >= 10
    """, db_path=db_path)

    pitcher_eligible = query("""
        SELECT p.id, p.first_name, p.last_name, p.position,
               COUNT(DISTINCT ps.season) as pitching_seasons,
               SUM(ps.wins) as career_wins, SUM(ps.so) as career_so,
               SUM(ps.saves) as career_saves, SUM(ps.ip_outs) as career_ip_outs,
               CASE WHEN SUM(ps.ip_outs) > 0
                    THEN ROUND(9.0 * SUM(ps.er) / (SUM(ps.ip_outs) / 3.0), 2) END as career_era
        FROM players p
        LEFT JOIN pitching_stats ps ON ps.player_id = p.id AND ps.level='MLB'
        WHERE p.roster_status = 'retired' AND p.position IN ('SP', 'RP')
        GROUP BY p.id
        HAVING pitching_seasons >= 10
    """, db_path=db_path)

    inductees = []

    # Batter HOF threshold: 2000+ hits, or 400+ HR, or exceptional career
    for p in (eligible or []):
        score = 0
        if (p["career_hits"] or 0) >= 3000:
            score += 50
        elif (p["career_hits"] or 0) >= 2500:
            score += 30
        elif (p["career_hits"] or 0) >= 2000:
            score += 15
        if (p["career_hr"] or 0) >= 500:
            score += 40
        elif (p["career_hr"] or 0) >= 400:
            score += 25
        elif (p["career_hr"] or 0) >= 300:
            score += 10
        if (p["career_rbi"] or 0) >= 1500:
            score += 15

        if score >= 40:  # Strong HOF case
            inductees.append({
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "position": p["position"],
                "career_hits": p["career_hits"],
                "career_hr": p["career_hr"],
                "vote_pct": min(99.9, 50 + score),
            })

    # Pitcher HOF threshold: 250+ wins, or 3000+ K, or exceptional ERA
    for p in (pitcher_eligible or []):
        score = 0
        if (p["career_wins"] or 0) >= 300:
            score += 50
        elif (p["career_wins"] or 0) >= 250:
            score += 30
        elif (p["career_wins"] or 0) >= 200:
            score += 15
        if (p["career_so"] or 0) >= 3000:
            score += 30
        elif (p["career_so"] or 0) >= 2500:
            score += 15
        if p["career_era"] and p["career_era"] <= 3.00:
            score += 20
        if (p["career_saves"] or 0) >= 400:
            score += 30

        if score >= 40:
            inductees.append({
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "position": p["position"],
                "career_wins": p["career_wins"],
                "career_so": p["career_so"],
                "vote_pct": min(99.9, 50 + score),
            })

    return inductees


# ============================================================
# ALL-STAR GAME
# ============================================================
def simulate_all_star_game(season: int, db_path=None) -> dict:
    """Select All-Star rosters and simulate the game."""
    from .game_engine import simulate_game, BatterStats, PitcherStats, ParkFactors

    al_batters = []
    nl_batters = []

    # Select top player at each position per league
    for league, roster in [("AL", al_batters), ("NL", nl_batters)]:
        for pos in ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]:
            best = query("""
                SELECT p.*, bs.hits, bs.hr, bs.rbi, bs.ab,
                       CASE WHEN bs.ab > 0 THEN 1.0 * bs.hits / bs.ab END as avg
                FROM players p
                JOIN batting_stats bs ON bs.player_id = p.id
                JOIN teams t ON t.id = p.team_id
                WHERE p.position=? AND t.league=? AND bs.season=?
                AND bs.level='MLB' AND bs.ab >= 100
                ORDER BY (bs.hr * 3 + bs.rbi * 1.5 + bs.hits + bs.bb * 0.5) DESC
                LIMIT 1
            """, (pos, league, season), db_path=db_path)
            if best:
                b = best[0]
                roster.append(BatterStats(
                    player_id=b["id"],
                    name=f"{b['first_name']} {b['last_name']}",
                    position=b["position"],
                    batting_order=len(roster) + 1,
                    bats=b["bats"],
                    contact=b["contact_rating"],
                    power=b["power_rating"],
                    speed=b["speed_rating"],
                    clutch=b["clutch"],
                    fielding=b["fielding_rating"],
                    eye=b.get("eye_rating", 50),
                ))

    # Select pitchers (top 3 starters + 3 relievers per league)
    al_pitchers = []
    nl_pitchers = []
    for league, pitcher_roster in [("AL", al_pitchers), ("NL", nl_pitchers)]:
        for role, limit in [("SP", 3), ("RP", 3)]:
            best_p = query("""
                SELECT p.* FROM players p
                JOIN pitching_stats ps ON ps.player_id = p.id
                JOIN teams t ON t.id = p.team_id
                WHERE p.position=? AND t.league=? AND ps.season=?
                AND ps.level='MLB' AND ps.ip_outs >= 30
                ORDER BY (p.stuff_rating * 2 + p.control_rating * 1.5) DESC
                LIMIT ?
            """, (role, league, season, limit), db_path=db_path)
            for p in (best_p or []):
                pitcher_roster.append(PitcherStats(
                    player_id=p["id"],
                    name=f"{p['first_name']} {p['last_name']}",
                    throws=p["throws"],
                    role="starter" if role == "SP" else "reliever",
                    stuff=p["stuff_rating"],
                    control=p["control_rating"],
                    stamina=p["stamina_rating"],
                    clutch=p["clutch"],
                ))

    if len(al_batters) < 9 or len(nl_batters) < 9:
        return {"error": "Not enough qualified players for All-Star game"}

    park = ParkFactors()  # neutral park
    result = simulate_game(al_batters, nl_batters, al_pitchers, nl_pitchers, park)

    return {
        "al_score": result["away_score"],
        "nl_score": result["home_score"],
        "al_roster": [{"name": b.name, "position": b.position} for b in al_batters],
        "nl_roster": [{"name": b.name, "position": b.position} for b in nl_batters],
        "al_pitchers": [{"name": p.name, "role": p.role} for p in al_pitchers],
        "nl_pitchers": [{"name": p.name, "role": p.role} for p in nl_pitchers],
        "innings": result.get("innings_away", []),
    }
