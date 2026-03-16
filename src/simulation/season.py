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
from .strategy import get_strategy
from .chemistry import (
    update_player_morale, update_team_chemistry, calculate_team_chemistry
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
            fielding=b["fielding_rating"],
            morale=b["morale"],
        ))

    # Load pitcher fatigue data to filter out those needing rest
    team = query("SELECT team_strategy_json FROM teams WHERE id=?",
                 (team_id,), db_path=db_path)
    fatigue_data = {}
    if team and team[0].get("team_strategy_json"):
        try:
            strategy = json.loads(team[0]["team_strategy_json"])
            fatigue_data = strategy.get("pitcher_fatigue", {})
        except:
            fatigue_data = {}

    # Get current date for rest calculation
    state = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
    current_date = state[0]["current_date"] if state else "2026-02-15"
    from datetime import datetime
    current = datetime.fromisoformat(current_date).date()

    # Build pitching staff, filtering relievers by rest status
    pitchers = []
    starters = [p for p in pitchers_data if p["position"] == "SP"]
    relievers = [p for p in pitchers_data if p["position"] == "RP"]

    # Add starter
    if starters:
        p = starters[0]
        pitch_types = [("FB", 70), ("SL", 60), ("CB", 55)]
        pitchers.append(PitcherStats(
            player_id=p["id"],
            name=f"{p['first_name']} {p['last_name']}",
            throws=p["throws"],
            role="starter",
            stuff=p["stuff_rating"],
            control=p["control_rating"],
            stamina=p["stamina_rating"],
            clutch=p["clutch"],
            pitch_types=pitch_types,
        ))

    # Add relievers, excluding those who need rest
    available_relievers = []
    fatigued_relievers = []
    for p in relievers:
        reliever_id = p["id"]
        if str(reliever_id) in fatigue_data:
            fatigue = fatigue_data[str(reliever_id)]
            last_game = datetime.fromisoformat(fatigue["last_game_date"]).date()
            rest_needed = fatigue.get("rest_days_needed", 1)
            days_rested = (current - last_game).days
            if days_rested < rest_needed:
                fatigued_relievers.append(p)
                continue  # Skip, still needs rest
        available_relievers.append(p)

    # Use up to 6 available relievers
    selected_relievers = available_relievers[:6]

    # Emergency fallback: if fewer than 6 available, add fatigued relievers (never blank out the bullpen)
    if len(selected_relievers) < 6:
        remaining_slots = 6 - len(selected_relievers)
        selected_relievers.extend(fatigued_relievers[:remaining_slots])

    for p in selected_relievers:
        pitch_types = [("FB", 70), ("SL", 60), ("CB", 55)]
        pitchers.append(PitcherStats(
            player_id=p["id"],
            name=f"{p['first_name']} {p['last_name']}",
            throws=p["throws"],
            role="reliever",
            stuff=p["stuff_rating"],
            control=p["control_rating"],
            stamina=p["stamina_rating"],
            clutch=p["clutch"],
            pitch_types=pitch_types,
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
    """Get the next starter in the rotation, enforcing 4+ days rest.
    If no starter has 4+ days rest, use the best-rested reliever as a spot starter.
    Emergency fallback: use most-rested pitcher if all are fatigued."""
    # Load team's pitcher fatigue tracking
    team = query("SELECT team_strategy_json FROM teams WHERE id=?",
                 (team_id,), db_path=db_path)
    fatigue_data = {}
    if team and team[0].get("team_strategy_json"):
        try:
            strategy = json.loads(team[0]["team_strategy_json"])
            fatigue_data = strategy.get("pitcher_fatigue", {})
        except:
            fatigue_data = {}

    # Get current date
    state = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
    current_date = state[0]["current_date"] if state else "2026-02-15"

    # Find starters by recency
    from datetime import datetime, timedelta
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
    """, (team_id,), db_path=db_path)

    # Filter starters: those with 4+ days rest
    current = datetime.fromisoformat(current_date).date()
    fully_rested = []
    for starter in starters:
        starter_id = starter["id"]
        if str(starter_id) in fatigue_data:
            fatigue = fatigue_data[str(starter_id)]
            last_game = datetime.fromisoformat(fatigue["last_game_date"]).date()
            rest_needed = fatigue.get("rest_days_needed", 4)
            days_rested = (current - last_game).days
            if days_rested < 4:  # Strict 4+ days for starters
                continue
        fully_rested.append(starter)

    # If a fully-rested starter is available, use them
    if fully_rested:
        return fully_rested[0]["id"]

    # Otherwise, find the best-rested reliever as spot starter (bullpen day)
    relievers = query("""
        SELECT p.id, p.first_name, p.last_name,
            COALESCE(
                (SELECT MAX(s.game_date) FROM pitching_lines pl
                 JOIN schedule s ON s.id = pl.schedule_id
                 WHERE pl.player_id = p.id),
                '2000-01-01'
            ) as last_game
        FROM players p
        WHERE p.team_id=? AND p.position='RP' AND p.roster_status='active'
        ORDER BY last_game DESC
    """, (team_id,), db_path=db_path)

    if relievers:
        # Find best-rested reliever
        best_rested = None
        most_days = -999
        for reliever in relievers:
            reliever_id = reliever["id"]
            last_game_date = reliever["last_game"]
            days_since = (current - datetime.fromisoformat(last_game_date).date()).days
            if days_since > most_days:
                most_days = days_since
                best_rested = reliever
        if best_rested:
            return best_rested["id"]

    # Ultimate fallback: return the most-rested starter even if they haven't had full rest
    best_rest_starter = None
    best_rest_days = -999
    for starter in starters:
        starter_id = starter["id"]
        if str(starter_id) in fatigue_data:
            fatigue = fatigue_data[str(starter_id)]
            last_game = datetime.fromisoformat(fatigue["last_game_date"]).date()
            days_rested = (current - last_game).days
            if days_rested > best_rest_days:
                best_rest_days = days_rested
                best_rest_starter = starter
        else:
            best_rest_starter = starter
            break

    return best_rest_starter["id"] if best_rest_starter else (starters[0]["id"] if starters else None)


def _load_team_strategy(team_id: int, db_path: str = None) -> dict:
    """Load team strategy settings from the database."""
    team = query("SELECT team_strategy_json FROM teams WHERE id=?",
                 (team_id,), db_path=db_path)
    if team and team[0].get("team_strategy_json"):
        return get_strategy(team[0]["team_strategy_json"])
    return get_strategy()


def _determine_phase(game_date: date, season: int) -> str:
    """Determine the current season phase based on date."""
    month = game_date.month
    day = game_date.day

    if month >= 11 or (month <= 2 and day <= 14):
        return "offseason"
    if month == 2 and day > 14:
        return "spring_training"
    if month == 3 and day < 26:
        return "spring_training"
    if (month == 3 and day >= 26) or (4 <= month <= 8) or (month == 9 and day <= 28):
        return "regular_season"
    if month == 9 and day > 28:
        return "regular_season"
    if month == 10:
        return "postseason"

    return "regular_season"


def is_past_trade_deadline(game_date: date) -> bool:
    """Check if the current date is past the July 31 trade deadline."""
    return game_date.month > 7 or (game_date.month == 7 and game_date.day > 31)


def _generate_key_plays(game_result: dict, home_team_id: int, away_team_id: int) -> list:
    """Generate play-by-play summary focusing on key events."""
    key_plays = []

    # If game engine already has play_by_play data, use it
    if "play_by_play" in game_result and game_result["play_by_play"]:
        return game_result["play_by_play"]

    # Fallback: extract key plays from lineup stats
    home_lineup = game_result.get("home_lineup", [])
    away_lineup = game_result.get("away_lineup", [])
    home_pitchers = game_result.get("home_pitchers", [])
    away_pitchers = game_result.get("away_pitchers", [])

    # Scan all batters for key plays
    for lineup, team_id in [(home_lineup, home_team_id), (away_lineup, away_team_id)]:
        for batter in lineup:
            # Home runs (most important)
            if batter.hr > 0:
                for _ in range(batter.hr):
                    key_plays.append({
                        "type": "HR",
                        "player": batter.name,
                        "team_id": team_id,
                        "inning": None,
                    })
            # Strikeouts (mark important outs)
            if batter.so > 0:
                for _ in range(batter.so):
                    key_plays.append({
                        "type": "SO",
                        "player": batter.name,
                        "team_id": team_id,
                    })
            # Stolen bases
            if batter.sb > 0:
                for _ in range(batter.sb):
                    key_plays.append({
                        "type": "SB",
                        "player": batter.name,
                        "team_id": team_id,
                    })
            # Reached on error
            if batter.reached_on_error > 0:
                for _ in range(batter.reached_on_error):
                    key_plays.append({
                        "type": "ROE",
                        "player": batter.name,
                        "team_id": team_id,
                    })

    # Scan pitchers for changes and key moments
    for pitchers, team_id in [(home_pitchers, home_team_id), (away_pitchers, away_team_id)]:
        for i, pitcher in enumerate(pitchers):
            if i > 0 and pitcher.ip_outs > 0:  # Relief pitcher who threw
                key_plays.append({
                    "type": "PITCHING_CHANGE",
                    "player": pitcher.name,
                    "team_id": team_id,
                })

    return key_plays


def _initialize_pitcher_fatigue(team_id: int, db_path: str = None):
    """Create or initialize fatigue tracking for a team."""
    conn = get_connection(db_path)
    team = conn.execute("SELECT team_strategy_json FROM teams WHERE id=?",
                       (team_id,)).fetchone()
    if not team:
        return

    strategy_json = team["team_strategy_json"] or "{}"
    try:
        strategy = json.loads(strategy_json)
    except:
        strategy = {}

    if "pitcher_fatigue" not in strategy:
        strategy["pitcher_fatigue"] = {}

    conn.execute("UPDATE teams SET team_strategy_json=? WHERE id=?",
                (json.dumps(strategy), team_id))
    conn.commit()
    conn.close()


def _update_pitcher_rest(game_date: str, db_path: str = None):
    """Update pitcher rest days after each game."""
    conn = get_connection(db_path)

    # Get all games played today
    games = query("""
        SELECT gr.id, pl.player_id, pl.ip_outs, pl.pitches, s.home_team_id, s.away_team_id
        FROM game_results gr
        JOIN pitching_lines pl ON pl.schedule_id = gr.schedule_id
        JOIN schedule s ON s.id = gr.schedule_id
        WHERE s.game_date = ?
    """, (game_date,), db_path=db_path)

    for game in games:
        pitcher_id = game["player_id"]
        pitches = game["pitches"]
        ip_outs = game["ip_outs"]

        # Determine rest needed (strict enforcement)
        if ip_outs >= 15:  # 5+ innings (starter)
            rest_needed = 4  # Starters must have 4 days rest minimum
            if pitches > 110:
                rest_needed = 5  # Extra day if very high pitch count
        elif pitches >= 45:  # heavy reliever use (45+ pitches)
            rest_needed = 2  # 2 days rest for heavy use
        elif pitches >= 30:  # moderate reliever use (30-44 pitches)
            rest_needed = 1  # 1 day rest for moderate use
        else:
            rest_needed = 0  # Light use, no rest required

        if rest_needed > 0:
            # Store last game date in team strategy for this pitcher
            teams = [game["home_team_id"], game["away_team_id"]]
            for team_id in teams:
                team_row = conn.execute("SELECT team_strategy_json FROM teams WHERE id=?",
                                       (team_id,)).fetchone()
                if not team_row:
                    continue

                strategy_json = team_row["team_strategy_json"] or "{}"
                try:
                    strategy = json.loads(strategy_json)
                except:
                    strategy = {}

                if "pitcher_fatigue" not in strategy:
                    strategy["pitcher_fatigue"] = {}

                strategy["pitcher_fatigue"][str(pitcher_id)] = {
                    "last_game_date": game_date,
                    "rest_days_needed": rest_needed,
                    "pitches_thrown": pitches,
                }

                conn.execute("UPDATE teams SET team_strategy_json=? WHERE id=?",
                            (json.dumps(strategy), team_id))

    conn.commit()
    conn.close()


def sim_day(game_date: str = None, db_path: str = None) -> list:
    """Simulate all games for a given date. Returns list of results."""
    if game_date is None:
        state = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
        game_date = state[0]["current_date"]

    parsed_date = date.fromisoformat(game_date)
    phase = _determine_phase(parsed_date, parsed_date.year)
    if phase == "spring_training":
        return []

    # Check for September 1 (expansion to 28-man roster)
    is_september = parsed_date.month == 9 and parsed_date.day >= 1

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

        # September callups: expand active roster temporarily
        if is_september:
            # Load additional minor leaguers as callups
            callup_limit = 2
            home_callups = query("""
                SELECT p.*, c.annual_salary FROM players p
                LEFT JOIN contracts c ON c.player_id = p.id
                WHERE p.team_id=? AND p.roster_status LIKE 'minors%'
                AND p.position NOT IN ('SP', 'RP')
                ORDER BY p.power_rating + p.contact_rating DESC
                LIMIT ?
            """, (home_id, callup_limit), db_path=db_path)

            for callup in home_callups:
                if callup["position"] not in ("SP", "RP"):
                    home_lineup.append(BatterStats(
                        player_id=callup["id"],
                        name=f"{callup['first_name']} {callup['last_name']}",
                        position=callup["position"],
                        batting_order=len(home_lineup) + 1,
                        bats=callup["bats"],
                        contact=callup["contact_rating"],
                        power=callup["power_rating"],
                        speed=callup["speed_rating"],
                        clutch=callup["clutch"],
                        fielding=callup["fielding_rating"],
                    ))

        if not home_lineup or not away_lineup or not home_pitchers or not away_pitchers:
            continue

        home_strategy = _load_team_strategy(home_id, db_path)
        away_strategy = _load_team_strategy(away_id, db_path)

        # Load team chemistry scores
        home_chemistry = calculate_team_chemistry(home_id, db_path)
        away_chemistry = calculate_team_chemistry(away_id, db_path)

        result = simulate_game(
            home_lineup, away_lineup,
            home_pitchers, away_pitchers,
            park, home_id, away_id,
            home_strategy, away_strategy,
            home_chemistry=home_chemistry, away_chemistry=away_chemistry
        )

        # Update pitcher rest tracking
        _update_pitcher_rest(game_date, db_path)

        # Save to database
        conn.execute("""
            UPDATE schedule SET is_played=1, home_score=?, away_score=?
            WHERE id=?
        """, (result["home_score"], result["away_score"], game["id"]))

        # Generate key plays for play-by-play
        key_plays = _generate_key_plays(result, home_id, away_id)

        # Save game result with play-by-play
        conn.execute("""
            INSERT INTO game_results (schedule_id, innings_json, play_by_play_json,
                winning_pitcher_id, losing_pitcher_id, save_pitcher_id, attendance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            game["id"],
            json.dumps([result["innings_away"], result["innings_home"]]),
            json.dumps(key_plays),
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

    # Update morale for both teams after game (after closing main connection)
    for result_item in results:
        update_player_morale(result_item["home_team_id"], db_path)
        update_player_morale(result_item["away_team_id"], db_path)

    # Update team chemistry after games
    for result_item in results:
        update_team_chemistry(result_item["home_team_id"], db_path)
        update_team_chemistry(result_item["away_team_id"], db_path)

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
    season = state[0]["season"]
    all_results = []
    waiver_outcomes = []
    ai_trade_events = []
    offseason_events = []

    for d in range(days):
        game_date_obj = current + timedelta(days=d)
        game_date = game_date_obj.isoformat()

        phase = _determine_phase(game_date_obj, season)
        execute("UPDATE game_state SET phase=? WHERE id=1",
                (phase,), db_path=db_path)

        if phase == "offseason":
            from .offseason import process_offseason_day
            off_result = process_offseason_day(game_date, season, db_path)
            offseason_events.append(off_result)
        else:
            day_results = sim_day(game_date, db_path)
            all_results.extend(day_results)

            from ..transactions.waivers import process_waivers
            waivers = process_waivers(game_date, db_path)
            if waivers:
                waiver_outcomes.extend(waivers)

            if phase == "regular_season":
                from ..transactions.ai_trades import process_ai_trades
                ai_trades = process_ai_trades(game_date, db_path)
                if ai_trades:
                    ai_trade_events.extend(ai_trades)

                # Check for trading block offers
                trading_offers = process_trading_block_offers(game_date, db_path)
                if trading_offers:
                    ai_trade_events.extend([{"type": "trading_block_offer", "offer": o} for o in trading_offers])

    new_date = (current + timedelta(days=days)).isoformat()
    new_date_obj = current + timedelta(days=days)
    final_phase = _determine_phase(new_date_obj, season)
    execute("UPDATE game_state SET current_date=?, phase=? WHERE id=1",
            (new_date, final_phase), db_path=db_path)

    result = {
        "new_date": new_date,
        "phase": final_phase,
        "games_played": len(all_results),
        "results": all_results,
    }

    if waiver_outcomes:
        result["waiver_outcomes"] = waiver_outcomes
    if ai_trade_events:
        result["ai_trades"] = ai_trade_events
    if offseason_events:
        result["offseason"] = offseason_events

    return result


def process_trading_block_offers(game_date: str, db_path: str = None) -> list:
    """
    Process AI team trade offers for players on the user's trading block.

    During the regular season, AI teams periodically evaluate players on the user's
    trading block and may make trade offers. Each trading block player has a 10%
    chance per day that an AI team makes an offer.

    Returns list of trade offers made.
    """
    import random

    state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
    user_team_id = state[0]["user_team_id"] if state else None

    if not user_team_id:
        return []

    # Get user's team with trading block
    team = query("SELECT trading_block_json FROM teams WHERE id=?",
                (user_team_id,), db_path=db_path)

    if not team or not team[0].get("trading_block_json"):
        return []

    try:
        trading_block = json.loads(team[0]["trading_block_json"])
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(trading_block, list) or len(trading_block) == 0:
        return []

    offers = []

    # For each player on the trading block, 10% chance per day an AI team makes an offer
    for player_id in trading_block:
        if random.random() < 0.10:
            # AI team wants to make an offer
            player = query("SELECT first_name, last_name, position FROM players WHERE id=?",
                          (player_id,), db_path=db_path)

            if not player:
                continue

            # Pick a random AI team (not the user's team)
            ai_teams = query("""
                SELECT id, city, name FROM teams WHERE id != ? ORDER BY RANDOM() LIMIT 1
            """, (user_team_id,), db_path=db_path)

            if not ai_teams:
                continue

            proposing_team = ai_teams[0]
            player_info = player[0]
            player_name = f"{player_info['first_name']} {player_info['last_name']}"
            proposing_team_name = f"{proposing_team['city']} {proposing_team['name']}"

            # Create a simple offer (some prospects/picks)
            offer_details = {
                "proposing_team_id": proposing_team["id"],
                "proposing_team_name": proposing_team_name,
                "player_id": player_id,
                "player_name": player_name,
                "assets": [
                    {"type": "prospects", "count": random.randint(1, 3)},
                    {"type": "draft_picks", "count": random.randint(0, 2)},
                ]
            }

            # Send notification to user
            from ..transactions.messages import send_message
            subject = f"Trade Interest: {player_name}"
            body = f"The {proposing_team_name} has expressed trade interest in {player_name}. Check the Transactions tab for details."
            send_message(user_team_id, "trade_offer", subject, body, game_date, db_path=db_path)

            offers.append(offer_details)

    return offers
