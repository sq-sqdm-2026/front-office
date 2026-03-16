"""
Front Office - Playoff Bracket Generation and Simulation
Handles Wild Card Series, Division Series, Championship Series, and World Series.
"""
from ..database.db import query, execute, get_connection
import json


def get_division_winners(season: int, db_path: str = None) -> dict:
    """
    Get the division winner (best record) for each of the 6 divisions.
    Returns dict: {division_key: team_data}
    """
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

        pct = wins / max(1, wins + losses)
        standings[div_key].append({
            "team_id": t["id"],
            "city": t["city"],
            "name": t["name"],
            "abbreviation": t["abbreviation"],
            "league": t["league"],
            "division": t["division"],
            "wins": wins,
            "losses": losses,
            "pct": pct,
        })

    # Sort each division by win pct to get winner
    division_winners = {}
    for div_key in standings:
        if standings[div_key]:
            standings[div_key].sort(key=lambda x: (-x["pct"], -x["wins"]))
            division_winners[div_key] = standings[div_key][0]

    return division_winners


def get_wildcard_teams(season: int, db_path: str = None) -> dict:
    """
    Get the 3 wild card teams per league (best records among non-division winners).
    Returns dict: {league: [teams]}
    """
    teams = query("SELECT * FROM teams", db_path=db_path)
    division_winners = get_division_winners(season, db_path)
    winner_ids = set(w["team_id"] for w in division_winners.values())

    by_league = {"AL": [], "NL": []}

    for t in teams:
        if t["id"] in winner_ids:
            continue  # Skip division winners

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

        pct = wins / max(1, wins + losses)
        by_league[t["league"]].append({
            "team_id": t["id"],
            "city": t["city"],
            "name": t["name"],
            "abbreviation": t["abbreviation"],
            "league": t["league"],
            "division": t["division"],
            "wins": wins,
            "losses": losses,
            "pct": pct,
        })

    # Sort each league by wins and get top 3 wild cards
    wildcard_by_league = {}
    for league in ["AL", "NL"]:
        by_league[league].sort(key=lambda x: (-x["wins"], -x["pct"]))
        wildcard_by_league[league] = by_league[league][:3]

    return wildcard_by_league


def generate_playoff_bracket(season: int, db_path: str = None) -> dict:
    """
    Generate the complete playoff bracket for the season.
    Modern MLB format:
    - 6 division winners (seeds 1-3 per league by record)
    - 3 wild cards per league (seeds 4-6 per league)

    Wild Card Series (best-of-3):
    - #4 vs #5, #3 vs #6 in each league

    Division Series (best-of-5):
    - #1 vs lowest remaining, #2 vs other remaining

    Championship Series (best-of-7):
    - DS winners face each other

    World Series (best-of-7):
    - AL champ vs NL champ
    """
    conn = get_connection(db_path)

    # Clear any existing bracket for this season
    conn.execute("DELETE FROM playoff_bracket WHERE season=?", (season,))
    conn.commit()

    # Get division winners and wild cards
    division_winners = get_division_winners(season, db_path)
    wildcard_teams = get_wildcard_teams(season, db_path)

    # Build AL teams (1-6 seed)
    al_div_winners = [w for k, w in division_winners.items() if "AL" in k]
    al_div_winners.sort(key=lambda x: (-x["wins"], -x["pct"]))

    al_seeds = al_div_winners + wildcard_teams["AL"]  # Divisions 1-3, wild cards 4-6

    # Build NL teams
    nl_div_winners = [w for k, w in division_winners.items() if "NL" in k]
    nl_div_winners.sort(key=lambda x: (-x["wins"], -x["pct"]))

    nl_seeds = nl_div_winners + wildcard_teams["NL"]

    # ============================================================
    # WILD CARD SERIES (Best of 3)
    # ============================================================
    wc_series = []

    # AL: #4 vs #5, #3 vs #6
    wc_series.append({
        "series_id": "al_wc1",
        "league": "AL",
        "seed_higher": 4,
        "seed_lower": 5,
        "higher_seed_id": al_seeds[3]["team_id"],
        "lower_seed_id": al_seeds[4]["team_id"],
    })
    wc_series.append({
        "series_id": "al_wc2",
        "league": "AL",
        "seed_higher": 3,
        "seed_lower": 6,
        "higher_seed_id": al_seeds[2]["team_id"],
        "lower_seed_id": al_seeds[5]["team_id"],
    })

    # NL: #4 vs #5, #3 vs #6
    wc_series.append({
        "series_id": "nl_wc1",
        "league": "NL",
        "seed_higher": 4,
        "seed_lower": 5,
        "higher_seed_id": nl_seeds[3]["team_id"],
        "lower_seed_id": nl_seeds[4]["team_id"],
    })
    wc_series.append({
        "series_id": "nl_wc2",
        "league": "NL",
        "seed_higher": 3,
        "seed_lower": 6,
        "higher_seed_id": nl_seeds[2]["team_id"],
        "lower_seed_id": nl_seeds[5]["team_id"],
    })

    # Insert wild card series
    for series in wc_series:
        conn.execute("""
            INSERT INTO playoff_bracket
            (season, round, series_id, higher_seed_id, lower_seed_id, higher_seed_wins, lower_seed_wins, is_complete)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0)
        """, (season, "wild_card", series["series_id"], series["higher_seed_id"], series["lower_seed_id"]))

    conn.commit()

    # Build bracket data to return
    bracket = {
        "season": season,
        "al_seeds": [
            {"seed": i+1, "team_id": t["team_id"], "abbr": t["abbreviation"], "wins": t["wins"], "losses": t["losses"]}
            for i, t in enumerate(al_seeds)
        ],
        "nl_seeds": [
            {"seed": i+1, "team_id": t["team_id"], "abbr": t["abbreviation"], "wins": t["wins"], "losses": t["losses"]}
            for i, t in enumerate(nl_seeds)
        ],
        "wild_card": [s for s in wc_series],
    }

    conn.close()
    return bracket


def advance_playoff_round(season: int, db_path: str = None) -> dict:
    """
    Simulate the next playoff game(s) and advance the bracket.
    Returns info on games simulated and bracket progression.
    """
    from .season import _load_team_lineup, _get_park_factors, _load_team_strategy
    from ..simulation.chemistry import calculate_team_chemistry
    from .game_engine import simulate_game

    conn = get_connection(db_path)

    # Find all incomplete series
    incomplete_series = query("""
        SELECT * FROM playoff_bracket
        WHERE season=? AND is_complete=0
        ORDER BY round = 'world_series' DESC, round, series_id
    """, (season,), db_path=db_path)

    if not incomplete_series:
        conn.close()
        return {"message": "No active playoff series"}

    results = []

    for series in incomplete_series:
        series_id = series["series_id"]
        higher_id = series["higher_seed_id"]
        lower_id = series["lower_seed_id"]
        higher_wins = series["higher_seed_wins"]
        lower_wins = series["lower_seed_wins"]

        # Determine series length and win condition
        if series["round"] == "wild_card":
            wins_needed = 2  # Best of 3
        else:  # DS, CS, WS
            wins_needed = 4  # Best of 7

        # If series is already won, skip
        if higher_wins >= wins_needed or lower_wins >= wins_needed:
            continue

        # Simulate the next game
        try:
            home_lineup, home_pitchers = _load_team_lineup(higher_id, db_path)
            away_lineup, away_pitchers = _load_team_lineup(lower_id, db_path)
            park = _get_park_factors(higher_id, db_path)
            home_strategy = _load_team_strategy(higher_id, db_path)
            away_strategy = _load_team_strategy(lower_id, db_path)
            home_chemistry = calculate_team_chemistry(higher_id, db_path)
            away_chemistry = calculate_team_chemistry(lower_id, db_path)

            game_result = simulate_game(
                home_lineup, away_lineup,
                home_pitchers, away_pitchers,
                park, higher_id, lower_id,
                home_strategy, away_strategy,
                home_chemistry=home_chemistry,
                away_chemistry=away_chemistry
            )

            # Determine winner of this game
            if game_result["home_score"] > game_result["away_score"]:
                higher_wins += 1
                game_winner_id = higher_id
            else:
                lower_wins += 1
                game_winner_id = lower_id

            results.append({
                "series_id": series_id,
                "home_team_id": higher_id,
                "away_team_id": lower_id,
                "home_score": game_result["home_score"],
                "away_score": game_result["away_score"],
                "series_score": f"{higher_wins}-{lower_wins}",
            })

            # Update series in DB
            series_complete = 0
            series_winner = None
            if higher_wins >= wins_needed:
                series_complete = 1
                series_winner = higher_id
            elif lower_wins >= wins_needed:
                series_complete = 1
                series_winner = lower_id

            conn.execute("""
                UPDATE playoff_bracket
                SET higher_seed_wins=?, lower_seed_wins=?, is_complete=?, winner_id=?
                WHERE series_id=? AND season=?
            """, (higher_wins, lower_wins, series_complete, series_winner, series_id, season))

            # If series is complete, check if we need to generate next round
            if series_complete:
                generate_next_round(season, series["round"], db_path, conn)

        except Exception as e:
            print(f"Error simulating playoff game for {series_id}: {e}")

    conn.commit()
    conn.close()

    return {
        "games_played": len(results),
        "results": results,
    }


def generate_next_round(season: int, current_round: str, db_path: str = None, conn=None):
    """
    When a round is complete, generate matchups for the next round.
    """
    should_close = conn is None
    if conn is None:
        conn = get_connection(db_path)

    # Check if all series in current round are complete
    incomplete = query("""
        SELECT COUNT(*) as cnt FROM playoff_bracket
        WHERE season=? AND round=? AND is_complete=0
    """, (season, current_round), db_path=db_path)

    if incomplete[0]["cnt"] > 0:
        if should_close:
            conn.close()
        return  # Current round not done yet

    # All current round series are complete, generate next round
    if current_round == "wild_card":
        generate_division_series(season, db_path, conn)
    elif current_round == "division_series":
        generate_championship_series(season, db_path, conn)
    elif current_round == "championship_series":
        generate_world_series(season, db_path, conn)

    if should_close:
        conn.close()


def generate_division_series(season: int, db_path: str = None, conn=None):
    """
    After Wild Card Series, generate Division Series matchups.
    #1 vs lowest remaining WC winner, #2 vs other WC winner.
    """
    should_close = conn is None
    if conn is None:
        conn = get_connection(db_path)

    for league in ["AL", "NL"]:
        # Get #1 seed (bye team from WC1)
        seed_1_result = query("""
            SELECT higher_seed_id as team_id FROM playoff_bracket
            WHERE season=? AND series_id = ?
        """, (season, f"{league.lower()}_wc1"), db_path=db_path)

        # Get #2 seed (bye team from WC2)
        seed_2_result = query("""
            SELECT higher_seed_id as team_id FROM playoff_bracket
            WHERE season=? AND series_id = ?
        """, (season, f"{league.lower()}_wc2"), db_path=db_path)

        if not seed_1_result or not seed_2_result:
            continue

        seed_1_id = seed_1_result[0]["team_id"]
        seed_2_id = seed_2_result[0]["team_id"]

        # Get WC winners
        wc1_winner = query("""
            SELECT winner_id FROM playoff_bracket
            WHERE season=? AND series_id = ?
        """, (season, f"{league.lower()}_wc1"), db_path=db_path)

        wc2_winner = query("""
            SELECT winner_id FROM playoff_bracket
            WHERE season=? AND series_id = ?
        """, (season, f"{league.lower()}_wc2"), db_path=db_path)

        if not wc1_winner or not wc2_winner:
            continue

        wc1_id = wc1_winner[0]["winner_id"]
        wc2_id = wc2_winner[0]["winner_id"]

        # WC1 was #4 vs #5, WC2 was #3 vs #6
        # #1 faces the WC winner from #3 vs #6 (lowest remaining seed)
        # #2 faces the WC winner from #4 vs #5 (higher seed)
        ds1_higher = seed_1_id
        ds1_lower = wc2_id  # Winner from #3 vs #6

        ds2_higher = seed_2_id
        ds2_lower = wc1_id  # Winner from #4 vs #5

        # Create DS series
        conn.execute("""
            INSERT INTO playoff_bracket
            (season, round, series_id, higher_seed_id, lower_seed_id, higher_seed_wins, lower_seed_wins, is_complete)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0)
        """, (season, "division_series", f"{league.lower()}_ds1", ds1_higher, ds1_lower))

        conn.execute("""
            INSERT INTO playoff_bracket
            (season, round, series_id, higher_seed_id, lower_seed_id, higher_seed_wins, lower_seed_wins, is_complete)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0)
        """, (season, "division_series", f"{league.lower()}_ds2", ds2_higher, ds2_lower))

    if should_close:
        conn.close()


def generate_championship_series(season: int, db_path: str = None, conn=None):
    """
    After Division Series, generate Championship Series matchups.
    DS1 winner vs DS2 winner in each league.
    """
    should_close = conn is None
    if conn is None:
        conn = get_connection(db_path)

    for league in ["AL", "NL"]:
        ds1_winner = query("""
            SELECT winner_id FROM playoff_bracket
            WHERE season=? AND series_id = ?
        """, (season, f"{league.lower()}_ds1"), db_path=db_path)

        ds2_winner = query("""
            SELECT winner_id FROM playoff_bracket
            WHERE season=? AND series_id = ?
        """, (season, f"{league.lower()}_ds2"), db_path=db_path)

        if not ds1_winner or not ds2_winner:
            continue

        # #1 seed (ds1) gets home field
        conn.execute("""
            INSERT INTO playoff_bracket
            (season, round, series_id, higher_seed_id, lower_seed_id, higher_seed_wins, lower_seed_wins, is_complete)
            VALUES (?, ?, ?, ?, ?, 0, 0, 0)
        """, (season, "championship_series", f"{league.lower()}_cs",
              ds1_winner[0]["winner_id"], ds2_winner[0]["winner_id"]))

    if should_close:
        conn.close()


def generate_world_series(season: int, db_path: str = None, conn=None):
    """
    After Championship Series, generate World Series.
    AL champ vs NL champ.
    """
    should_close = conn is None
    if conn is None:
        conn = get_connection(db_path)

    al_champ = query("""
        SELECT winner_id FROM playoff_bracket
        WHERE season=? AND series_id = 'al_cs'
    """, (season,), db_path=db_path)

    nl_champ = query("""
        SELECT winner_id FROM playoff_bracket
        WHERE season=? AND series_id = 'nl_cs'
    """, (season,), db_path=db_path)

    if not al_champ or not nl_champ:
        if should_close:
            conn.close()
        return

    # AL typically gets home field (alternates by year, but simplify for now)
    conn.execute("""
        INSERT INTO playoff_bracket
        (season, round, series_id, higher_seed_id, lower_seed_id, higher_seed_wins, lower_seed_wins, is_complete)
        VALUES (?, ?, ?, ?, ?, 0, 0, 0)
    """, (season, "world_series", "ws", al_champ[0]["winner_id"], nl_champ[0]["winner_id"]))

    if should_close:
        conn.close()


def get_playoff_bracket(season: int, db_path: str = None) -> dict:
    """
    Return the full playoff bracket with team names, seeds, series scores, and status.
    """
    bracket_data = query("""
        SELECT
            pb.*,
            t1.abbreviation as higher_abbr,
            t1.city as higher_city,
            t1.name as higher_name,
            t2.abbreviation as lower_abbr,
            t2.city as lower_city,
            t2.name as lower_name,
            tw.abbreviation as winner_abbr
        FROM playoff_bracket pb
        LEFT JOIN teams t1 ON t1.id = pb.higher_seed_id
        LEFT JOIN teams t2 ON t2.id = pb.lower_seed_id
        LEFT JOIN teams tw ON tw.id = pb.winner_id
        WHERE pb.season=?
        ORDER BY
            CASE pb.round
                WHEN 'wild_card' THEN 1
                WHEN 'division_series' THEN 2
                WHEN 'championship_series' THEN 3
                WHEN 'world_series' THEN 4
            END,
            pb.series_id
    """, (season,), db_path=db_path)

    # Organize by round
    by_round = {}
    for row in bracket_data:
        round_name = row["round"]
        if round_name not in by_round:
            by_round[round_name] = []

        by_round[round_name].append({
            "series_id": row["series_id"],
            "higher_seed": {
                "team_id": row["higher_seed_id"],
                "abbr": row["higher_abbr"],
                "city": row["higher_city"],
                "name": row["higher_name"],
                "wins": row["higher_seed_wins"],
            },
            "lower_seed": {
                "team_id": row["lower_seed_id"],
                "abbr": row["lower_abbr"],
                "city": row["lower_city"],
                "name": row["lower_name"],
                "wins": row["lower_seed_wins"],
            },
            "winner": {
                "team_id": row["winner_id"],
                "abbr": row["winner_abbr"],
            } if row["winner_id"] else None,
            "is_complete": bool(row["is_complete"]),
        })

    return {
        "season": season,
        "by_round": by_round,
    }
