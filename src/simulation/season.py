"""
Front Office - Season Manager
Handles advancing the sim by days/weeks, running scheduled games,
updating standings, and tracking the season calendar.
"""
import json
from datetime import date, timedelta
from ..database.db import get_connection, query, execute
from .game_engine import (
    simulate_game, BatterStats, PitcherStats, ParkFactors
)


def get_standings(season: int = None, db_path: str = None) -> dict:
    """Get current standings grouped by division."""
    if season is None:
        state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
        season = state[0]["season"] if state else 2025

    teams = query("SELECT * FROM teams", db_path=db_path)

    standings = {}
    for t in teams:
        div_key = f"{t['league']} {t['division']}"
        if div_key not in standings:
            standings[div_key] = []

        # Get W-L record
        wins = query("""
            SELECT COUNT(*) as w FROM schedule
            WHERE season=? AND is_played=1 AND (
                (home_team_id=? AND home_score > away_score) OR
                (away_team_id=? AND away_score > home_score)
            )
        """, (season, t["id"], t["id"]), db_path=db_path)[0]["w"]

        losses = query("""
            SELECT COUNT(*) as l FROM schedule
            WHERE season=? AND is_played=1 AND (
                (home_team_id=? AND home_score < away_score) OR
                (away_team_id=? AND away_score < home_score)
            )
        """, (season, t["id"], t["id"]), db_path=db_path)[0]["l"]

        # Runs scored/allowed
        rs_home = query("""
            SELECT COALESCE(SUM(home_score), 0) as rs FROM schedule
            WHERE season=? AND is_played=1 AND home_team_id=?
        """, (season, t["id"]), db_path=db_path)[0]["rs"]
        rs_away = query("""
            SELECT COALESCE(SUM(away_score), 0) as rs FROM schedule
            WHERE season=? AND is_played=1 AND away_team_id=?
        """, (season, t["id"]), db_path=db_path)[0]["rs"]
        ra_home = query("""
            SELECT COALESCE(SUM(away_score), 0) as ra FROM schedule
            WHERE season=? AND is_played=1 AND home_team_id=?
        """, (season, t["id"]), db_path=db_path)[0]["ra"]
        ra_away = query("""
            SELECT COALESCE(SUM(home_score), 0) as ra FROM schedule
            WHERE season=? AND is_played=1 AND away_team_id=?
        """, (season, t["id"]), db_path=db_path)[0]["ra"]

        pct = wins / max(1, wins + losses)
        standings[div_key].append({
            "team_id": t["id"],
            "city": t["city"],
            "name": t["name"],
            "abbreviation": t["abbreviation"],
            "wins": wins,
            "losses": losses,
            "pct": round(pct, 3),
            "runs_scored": rs_home + rs_away,
            "runs_allowed": ra_home + ra_away,
            "diff": (rs_home + rs_away) - (ra_home + ra_away),
        })

    # Sort each division by win pct, calculate GB
    for div_key in standings:
        standings[div_key].sort(key=lambda x: (-x["pct"], -x["wins"]))
        if standings[div_key]:
            leader = standings[div_key][0]
            for t in standings[div_key]:
                t["gb"] = ((leader["wins"] - t["wins"]) + (t["losses"] - leader["losses"])) / 2

    return standings


def _load_team_lineup(team_id: int, db_path: str = None) -> tuple:
    """Load a team's active batters and pitchers from the database."""
    batters_data = query("""
        SELECT p.*, c.annual_salary FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.position NOT IN ('SP', 'RP')
        ORDER BY p.contact_rating + p.power_rating DESC
    """, (team_id,), db_path=db_path)

    pitchers_data = query("""
        SELECT p.*, c.annual_salary FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.position IN ('SP', 'RP')
        ORDER BY p.position ASC, p.stuff_rating + p.control_rating DESC
    """, (team_id,), db_path=db_path)

    # Build batting order (simplified auto-sort)
    lineup = []
    # Sort: speed leadoff, then power/contact, pitcher last
    sorted_batters = sorted(batters_data,
        key=lambda b: (b["speed_rating"] * 0.3 + b["contact_rating"] * 0.7),
        reverse=True)

    for i, b in enumerate(sorted_batters[:9]):
        lineup.append(BatterStats(
            player_id=b["id"],
            name=f"{b['first_name']} {b['last_name']}",
            position=b["position"],
            batting_order=i + 1,
            bats=b["bats"],
            contact=b["contact_rating"],
            power=b["power_rating"],
            speed=b["speed_rating"],
            clutch=b["clutch"],
        ))

    # Build pitching staff
    pitchers = []
    starters = [p for p in pitchers_data if p["position"] == "SP"]
    relievers = [p for p in pitchers_data if p["position"] == "RP"]

    for p in (starters[:1] + relievers[:6]):  # 1 starter + up to 6 relievers
        pitchers.append(PitcherStats(
            player_id=p["id"],
            name=f"{p['first_name']} {p['last_name']}",
            throws=p["throws"],
            role="starter" if p["position"] == "SP" else "reliever",
            stuff=p["stuff_rating"],
            control=p["control_rating"],
            stamina=p["stamina_rating"],
            clutch=p["clutch"],
        ))

    return lineup, pitchers


def _get_park_factors(team_id: int, db_path: str = None) -> ParkFactors:
    """Load park factors for a team's stadium."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return ParkFactors()
    t = team[0]
    return ParkFactors.from_stadium(
        t["lf_distance"], t["lcf_distance"], t["cf_distance"],
        t["rcf_distance"], t["rf_distance"],
        bool(t["is_dome"]), t.get("altitude", 0),
        t.get("surface", "grass"), t.get("foul_territory", "average")
    )


def _rotate_starter(team_id: int, db_path: str = None) -> int:
    """Get the next starter in the rotation based on recent usage."""
    starters = query("""
        SELECT p.id, p.first_name, p.last_name,
            COALESCE(
                (SELECT MAX(s.game_date) FROM pitching_lines pl
                 JOIN schedule s ON s.id = pl.schedule_id
                 WHERE pl.player_id = p.id AND pl.is_starter = 1),
                '2000-01-01'
            ) as last_start
        FROM players p
        WHERE p.team_id=? AND p.position='SP' AND p.roster_status='active'
        ORDER BY last_start ASC
        LIMIT 1
    """, (team_id,), db_path=db_path)
    return starters[0]["id"] if starters else None


def sim_day(game_date: str = None, db_path: str = None) -> list:
    """Simulate all games for a given date. Returns list of results."""
    if game_date is None:
        state = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
        game_date = state[0]["current_date"]

    games = query("""
        SELECT * FROM schedule
        WHERE game_date=? AND is_played=0 AND is_postseason=0
    """, (game_date,), db_path=db_path)

    results = []
    conn = get_connection(db_path)

    for game in games:
        home_id = game["home_team_id"]
        away_id = game["away_team_id"]

        home_lineup, home_pitchers = _load_team_lineup(home_id, db_path)
        away_lineup, away_pitchers = _load_team_lineup(away_id, db_path)
        park = _get_park_factors(home_id, db_path)

        if not home_lineup or not away_lineup or not home_pitchers or not away_pitchers:
            continue

        result = simulate_game(
            home_lineup, away_lineup,
            home_pitchers, away_pitchers,
            park, home_id, away_id
        )

        # Save to database
        conn.execute("""
            UPDATE schedule SET is_played=1, home_score=?, away_score=?
            WHERE id=?
        """, (result["home_score"], result["away_score"], game["id"]))

        # Save game result
        conn.execute("""
            INSERT INTO game_results (schedule_id, innings_json,
                winning_pitcher_id, losing_pitcher_id, save_pitcher_id, attendance)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            game["id"],
            json.dumps([result["innings_away"], result["innings_home"]]),
            next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "W"), None),
            next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "L"), None),
            next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "S"), None),
            _estimate_attendance(home_id, db_path),
        ))

        # Save batting lines
        for lineup, team_id in [(result["home_lineup"], home_id), (result["away_lineup"], away_id)]:
            for b in lineup:
                conn.execute("""
                    INSERT INTO batting_lines (schedule_id, player_id, team_id,
                        batting_order, position_played, ab, runs, hits, doubles,
                        triples, hr, rbi, bb, so, sb, cs, hbp, sf)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (game["id"], b.player_id, team_id, b.batting_order,
                      b.position, b.ab, b.runs, b.hits, b.doubles, b.triples,
                      b.hr, b.rbi, b.bb, b.so, b.sb, b.cs, b.hbp, b.sf))

                # Update season stats
                conn.execute("""
                    INSERT INTO batting_stats (player_id, team_id, season, level, games,
                        pa, ab, runs, hits, doubles, triples, hr, rbi, bb, so, sb, cs, hbp, sf)
                    VALUES (?, ?, ?, 'MLB', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(player_id, team_id, season, level) DO UPDATE SET
                        games = games + 1,
                        pa = pa + excluded.pa,
                        ab = ab + excluded.ab,
                        runs = runs + excluded.runs,
                        hits = hits + excluded.hits,
                        doubles = doubles + excluded.doubles,
                        triples = triples + excluded.triples,
                        hr = hr + excluded.hr,
                        rbi = rbi + excluded.rbi,
                        bb = bb + excluded.bb,
                        so = so + excluded.so,
                        sb = sb + excluded.sb,
                        cs = cs + excluded.cs,
                        hbp = hbp + excluded.hbp,
                        sf = sf + excluded.sf
                """, (b.player_id, team_id, game["season"],
                      b.ab + b.bb + b.hbp + b.sf,
                      b.ab, b.runs, b.hits, b.doubles, b.triples,
                      b.hr, b.rbi, b.bb, b.so, b.sb, b.cs, b.hbp, b.sf))

        # Save pitching lines
        for pitchers, team_id in [(result["home_pitchers"], home_id), (result["away_pitchers"], away_id)]:
            for p in pitchers:
                if p.ip_outs == 0 and p.pitches == 0:
                    continue
                conn.execute("""
                    INSERT INTO pitching_lines (schedule_id, player_id, team_id,
                        pitch_order, ip_outs, hits_allowed, runs_allowed, er,
                        bb, so, hr_allowed, pitches, is_starter, decision)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (game["id"], p.player_id, team_id, p.pitch_order,
                      p.ip_outs, p.hits_allowed, p.runs_allowed, p.er,
                      p.bb_allowed, p.so_pitched, p.hr_allowed, p.pitches,
                      1 if p.is_starter else 0, p.decision))

                # Update season pitching stats
                conn.execute("""
                    INSERT INTO pitching_stats (player_id, team_id, season, level, games,
                        games_started, wins, losses, saves, ip_outs,
                        hits_allowed, runs_allowed, er, bb, so, hr_allowed, pitches)
                    VALUES (?, ?, ?, 'MLB', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(player_id, team_id, season, level) DO UPDATE SET
                        games = games + 1,
                        games_started = games_started + excluded.games_started,
                        wins = wins + excluded.wins,
                        losses = losses + excluded.losses,
                        saves = saves + excluded.saves,
                        ip_outs = ip_outs + excluded.ip_outs,
                        hits_allowed = hits_allowed + excluded.hits_allowed,
                        runs_allowed = runs_allowed + excluded.runs_allowed,
                        er = er + excluded.er,
                        bb = bb + excluded.bb,
                        so = so + excluded.so,
                        hr_allowed = hr_allowed + excluded.hr_allowed,
                        pitches = pitches + excluded.pitches
                """, (p.player_id, team_id, game["season"],
                      1 if p.is_starter else 0,
                      1 if p.decision == "W" else 0,
                      1 if p.decision == "L" else 0,
                      1 if p.decision == "S" else 0,
                      p.ip_outs, p.hits_allowed, p.runs_allowed, p.er,
                      p.bb_allowed, p.so_pitched, p.hr_allowed, p.pitches))

        results.append({
            "schedule_id": game["id"],
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_score": result["home_score"],
            "away_score": result["away_score"],
            "innings": len(result["innings_away"]),
        })

    conn.commit()
    conn.close()
    return results


def _estimate_attendance(team_id: int, db_path: str = None) -> int:
    """Estimate game attendance based on team popularity and performance."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return 30000
    t = team[0]
    base = t["stadium_capacity"] * 0.5
    loyalty_bonus = t["fan_loyalty"] / 100 * t["stadium_capacity"] * 0.4
    import random
    variance = random.uniform(0.85, 1.15)
    return int(min(t["stadium_capacity"], (base + loyalty_bonus) * variance))


def advance_date(days: int = 1, db_path: str = None) -> dict:
    """Advance the sim by N days, playing all games along the way."""
    state = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
    if not state:
        return {"error": "No game state found"}

    current = date.fromisoformat(state[0]["current_date"])
    all_results = []

    for d in range(days):
        game_date = (current + timedelta(days=d)).isoformat()
        day_results = sim_day(game_date, db_path)
        all_results.extend(day_results)

    new_date = (current + timedelta(days=days)).isoformat()
    execute("UPDATE game_state SET current_date=? WHERE id=1",
            (new_date,), db_path=db_path)

    return {
        "new_date": new_date,
        "games_played": len(all_results),
        "results": all_results,
    }
