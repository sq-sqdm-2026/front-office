"""
Front Office - Minor League Simulation
Simulates MiLB games (AAA, AA, A) with simplified stat accumulation,
standings tracking, and promotion recommendations.
"""
import random
from datetime import date
from ..database.db import get_connection, query, execute


# Roster status mapping for each level
LEVEL_STATUS = {
    "AAA": "minors_aaa",
    "AA": "minors_aa",
    "High-A": "minors_high_a",
    "A": "minors_low",
    "Rookie": "minors_rookie",
}

# Display labels for roster_status values
STATUS_LEVEL = {v: k for k, v in LEVEL_STATUS.items()}

# MiLB season runs roughly April through September
MILB_SEASON_START_MONTH = 4
MILB_SEASON_END_MONTH = 9

# ~60% chance of a game on any given day (off-days, travel, rain)
GAME_PROBABILITY = 0.60


def _is_milb_season(game_date_obj):
    """Check if the date falls within the MiLB season (Apr-Sep)."""
    return MILB_SEASON_START_MONTH <= game_date_obj.month <= MILB_SEASON_END_MONTH


def _get_players_at_level(team_id, level, db_path=None):
    """Get all players assigned to a specific minor league level."""
    status = LEVEL_STATUS.get(level)
    if not status:
        return [], []

    players = query(
        "SELECT * FROM players WHERE team_id=? AND roster_status=? AND is_injured=0",
        (team_id, status), db_path=db_path
    )

    batters = [p for p in players if p["position"] not in ("SP", "RP")]
    pitchers = [p for p in players if p["position"] in ("SP", "RP")]
    return batters, pitchers


def _sim_batter_game(player, pitcher_quality=50):
    """Simulate a single game's worth of plate appearances for a batter.

    Returns a dict of stat increments.
    """
    pa = random.randint(3, 5)
    contact = player["contact_rating"]
    power = player["power_rating"]
    eye = player["eye_rating"]
    speed = player["speed_rating"]

    stats = {
        "ab": 0, "hits": 0, "doubles": 0, "triples": 0,
        "hr": 0, "rbi": 0, "bb": 0, "so": 0, "sb": 0, "cs": 0,
        "runs": 0,
    }

    for _ in range(pa):
        # Walk probability: based on eye rating vs pitcher control
        bb_chance = 0.05 + (eye - 30) / 600  # ~5-13%
        if random.random() < bb_chance:
            stats["bb"] += 1
            # Steal attempt on walk
            if speed >= 55 and random.random() < (speed - 40) / 200:
                if random.random() < 0.55 + (speed - 50) / 200:
                    stats["sb"] += 1
                else:
                    stats["cs"] += 1
            continue

        stats["ab"] += 1

        # Strikeout probability: inverse of contact
        so_chance = 0.30 - (contact - 30) / 300  # ~13-30%
        if random.random() < so_chance:
            stats["so"] += 1
            continue

        # Hit probability: based on contact rating
        hit_chance = 0.18 + (contact - 30) / 350  # ~18-32%
        if random.random() < hit_chance:
            stats["hits"] += 1
            stats["rbi"] += 1 if random.random() < 0.35 else 0

            # Extra-base hit probability based on power
            xbh_roll = random.random()
            hr_chance = 0.02 + (power - 30) / 400  # ~2-14%
            triple_chance = 0.01 + (speed - 30) / 1000
            double_chance = 0.10 + (power - 30) / 500

            if xbh_roll < hr_chance:
                stats["hr"] += 1
                stats["rbi"] += random.choice([0, 1, 1, 2, 3])
                stats["runs"] += 1
            elif xbh_roll < hr_chance + triple_chance:
                stats["triples"] += 1
                stats["runs"] += 1 if random.random() < 0.6 else 0
            elif xbh_roll < hr_chance + triple_chance + double_chance:
                stats["doubles"] += 1
                stats["runs"] += 1 if random.random() < 0.4 else 0
            else:
                # Single
                stats["runs"] += 1 if random.random() < 0.25 else 0

                # Steal attempt on single
                if speed >= 50 and random.random() < (speed - 35) / 200:
                    if random.random() < 0.55 + (speed - 50) / 200:
                        stats["sb"] += 1
                    else:
                        stats["cs"] += 1
        else:
            # Out in play
            stats["runs"] += 0

    return stats


def _sim_pitcher_game(player, num_batters=25, is_starter=True):
    """Simulate a single game's pitching performance.

    Returns a dict of stat increments.
    """
    stuff = player["stuff_rating"]
    control = player["control_rating"]
    stamina = player["stamina_rating"]

    # Starters pitch ~5-7 innings, relievers ~1-3
    if is_starter:
        target_outs = random.randint(15, 21)  # 5-7 IP
    else:
        target_outs = random.randint(3, 9)  # 1-3 IP

    stats = {
        "ip_outs": 0, "hits_allowed": 0, "er": 0,
        "bb": 0, "so": 0, "hr_allowed": 0,
        "runs": 0,  # runs allowed for standings
    }

    outs = 0
    runs_this_game = 0

    for _ in range(num_batters):
        if outs >= target_outs:
            break

        # Strikeout chance based on stuff
        k_chance = 0.15 + (stuff - 30) / 250  # ~15-35%
        if random.random() < k_chance:
            stats["so"] += 1
            outs += 1
            continue

        # Walk chance based on control (inverse)
        bb_chance = 0.12 - (control - 30) / 400  # ~3-12%
        if random.random() < bb_chance:
            stats["bb"] += 1
            # Runner on, chance to score
            if random.random() < 0.15:
                runs_this_game += 1
            continue

        # Hit allowed
        hit_chance = 0.28 - (stuff - 30) / 500  # ~18-28%
        if random.random() < hit_chance:
            stats["hits_allowed"] += 1

            # HR allowed
            hr_chance = 0.03 + (60 - stuff) / 800
            if random.random() < hr_chance:
                stats["hr_allowed"] += 1
                new_runs = random.choice([1, 1, 1, 2, 2, 3])
                runs_this_game += new_runs
            else:
                # Other hit, chance to score a run
                if random.random() < 0.25:
                    runs_this_game += 1
        else:
            # Out in play
            outs += 1

    stats["ip_outs"] = outs
    stats["er"] = runs_this_game
    stats["runs"] = runs_this_game
    return stats


def simulate_milb_day(team_id, game_date, season, db_path=None):
    """Simulate one day of minor league games for a team at each level.

    Each level (AAA, AA, A) has a ~60% chance of playing on any given day
    during the MiLB season (April-September).
    """
    if isinstance(game_date, str):
        game_date_obj = date.fromisoformat(game_date)
    else:
        game_date_obj = game_date

    if not _is_milb_season(game_date_obj):
        return []

    results = []

    for level in ["AAA", "AA", "High-A", "A", "Rookie"]:
        # ~60% chance of game today
        if random.random() > GAME_PROBABILITY:
            continue

        batters, pitchers = _get_players_at_level(team_id, level, db_path)
        if not batters and not pitchers:
            continue

        conn = get_connection(db_path)

        # Ensure standings row exists
        existing = conn.execute(
            "SELECT id FROM milb_standings WHERE team_id=? AND level=? AND season=?",
            (team_id, level, season)
        ).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO milb_standings (team_id, level, season, wins, losses, runs_scored, runs_allowed) "
                "VALUES (?, ?, ?, 0, 0, 0, 0)",
                (team_id, level, season)
            )

        team_runs = 0
        opp_runs = 0

        # Simulate batting for each batter
        for batter in batters:
            bstats = _sim_batter_game(batter)
            team_runs += bstats["runs"]

            # Upsert milb_batting_stats
            existing_stat = conn.execute(
                "SELECT id, games, ab, hits, doubles, triples, hr, rbi, bb, so, sb, cs "
                "FROM milb_batting_stats WHERE player_id=? AND level=? AND season=?",
                (batter["id"], level, season)
            ).fetchone()

            if existing_stat:
                conn.execute("""
                    UPDATE milb_batting_stats SET
                        games = games + 1,
                        ab = ab + ?,
                        hits = hits + ?,
                        doubles = doubles + ?,
                        triples = triples + ?,
                        hr = hr + ?,
                        rbi = rbi + ?,
                        bb = bb + ?,
                        so = so + ?,
                        sb = sb + ?,
                        cs = cs + ?
                    WHERE player_id=? AND level=? AND season=?
                """, (
                    bstats["ab"], bstats["hits"], bstats["doubles"],
                    bstats["triples"], bstats["hr"], bstats["rbi"],
                    bstats["bb"], bstats["so"], bstats["sb"], bstats["cs"],
                    batter["id"], level, season
                ))
            else:
                conn.execute("""
                    INSERT INTO milb_batting_stats
                        (player_id, team_id, level, season, games, ab, hits, doubles, triples, hr, rbi, bb, so, sb, cs)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    batter["id"], team_id, level, season,
                    bstats["ab"], bstats["hits"], bstats["doubles"],
                    bstats["triples"], bstats["hr"], bstats["rbi"],
                    bstats["bb"], bstats["so"], bstats["sb"], bstats["cs"]
                ))

        # Simulate pitching
        if pitchers:
            # Pick a starter and maybe a reliever
            starter = random.choice([p for p in pitchers if p["position"] == "SP"] or pitchers)
            pstats = _sim_pitcher_game(starter, is_starter=True)
            opp_runs += pstats["runs"]

            # Upsert milb_pitching_stats for starter
            _upsert_pitching_stats(conn, starter["id"], team_id, level, season, pstats, is_start=True)

            # Maybe a reliever pitches too
            relievers = [p for p in pitchers if p["id"] != starter["id"]]
            if relievers and random.random() < 0.5:
                reliever = random.choice(relievers)
                rstats = _sim_pitcher_game(reliever, is_starter=False)
                opp_runs += rstats["runs"]
                _upsert_pitching_stats(conn, reliever["id"], team_id, level, season, rstats, is_start=False)
        else:
            # No pitchers, simulate an opponent score
            opp_runs = random.randint(2, 8)

        # Add some baseline runs if team has few batters
        if len(batters) < 5:
            team_runs += random.randint(1, 4)

        # Ensure a result (no ties)
        if team_runs == opp_runs:
            if random.random() < 0.5:
                team_runs += 1
            else:
                opp_runs += 1

        # Update standings
        if team_runs > opp_runs:
            conn.execute("""
                UPDATE milb_standings SET
                    wins = wins + 1,
                    runs_scored = runs_scored + ?,
                    runs_allowed = runs_allowed + ?
                WHERE team_id=? AND level=? AND season=?
            """, (team_runs, opp_runs, team_id, level, season))

            # Give the winning pitcher a W
            if pitchers:
                _award_decision(conn, starter["id"], level, season, "W")
        else:
            conn.execute("""
                UPDATE milb_standings SET
                    losses = losses + 1,
                    runs_scored = runs_scored + ?,
                    runs_allowed = runs_allowed + ?
                WHERE team_id=? AND level=? AND season=?
            """, (team_runs, opp_runs, team_id, level, season))

            # Give the losing pitcher an L
            if pitchers:
                _award_decision(conn, starter["id"], level, season, "L")

        conn.commit()
        conn.close()

        results.append({
            "team_id": team_id,
            "level": level,
            "team_runs": team_runs,
            "opp_runs": opp_runs,
            "win": team_runs > opp_runs,
        })

    return results


def _upsert_pitching_stats(conn, player_id, team_id, level, season, pstats, is_start=False):
    """Insert or update minor league pitching stats."""
    existing = conn.execute(
        "SELECT id FROM milb_pitching_stats WHERE player_id=? AND level=? AND season=?",
        (player_id, level, season)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE milb_pitching_stats SET
                games = games + 1,
                games_started = games_started + ?,
                ip_outs = ip_outs + ?,
                hits_allowed = hits_allowed + ?,
                er = er + ?,
                bb = bb + ?,
                so = so + ?,
                hr_allowed = hr_allowed + ?
            WHERE player_id=? AND level=? AND season=?
        """, (
            1 if is_start else 0,
            pstats["ip_outs"], pstats["hits_allowed"], pstats["er"],
            pstats["bb"], pstats["so"], pstats["hr_allowed"],
            player_id, level, season
        ))
    else:
        conn.execute("""
            INSERT INTO milb_pitching_stats
                (player_id, team_id, level, season, games, games_started,
                 wins, losses, saves, ip_outs, hits_allowed, er, bb, so, hr_allowed)
            VALUES (?, ?, ?, ?, 1, ?, 0, 0, 0, ?, ?, ?, ?, ?, ?)
        """, (
            player_id, team_id, level, season,
            1 if is_start else 0,
            pstats["ip_outs"], pstats["hits_allowed"], pstats["er"],
            pstats["bb"], pstats["so"], pstats["hr_allowed"]
        ))


def _award_decision(conn, player_id, level, season, decision):
    """Award a W or L to a pitcher."""
    if decision == "W":
        conn.execute(
            "UPDATE milb_pitching_stats SET wins = wins + 1 WHERE player_id=? AND level=? AND season=?",
            (player_id, level, season)
        )
    elif decision == "L":
        conn.execute(
            "UPDATE milb_pitching_stats SET losses = losses + 1 WHERE player_id=? AND level=? AND season=?",
            (player_id, level, season)
        )


def simulate_all_milb_day(game_date, season, db_path=None):
    """Simulate one day of minor league games for all 30 teams."""
    if isinstance(game_date, str):
        game_date_obj = date.fromisoformat(game_date)
    else:
        game_date_obj = game_date

    if not _is_milb_season(game_date_obj):
        return []

    teams = query("SELECT id FROM teams", db_path=db_path)
    all_results = []
    for team in teams:
        results = simulate_milb_day(team["id"], game_date, season, db_path)
        all_results.extend(results)
    return all_results


def get_milb_standings(team_id, level, season, db_path=None):
    """Return standings for a team's minor league affiliate."""
    rows = query(
        "SELECT * FROM milb_standings WHERE team_id=? AND level=? AND season=?",
        (team_id, level, season), db_path=db_path
    )
    if rows:
        row = rows[0]
        w = row["wins"]
        l = row["losses"]
        return {
            "team_id": team_id,
            "level": level,
            "season": season,
            "wins": w,
            "losses": l,
            "pct": round(w / max(1, w + l), 3),
            "runs_scored": row["runs_scored"],
            "runs_allowed": row["runs_allowed"],
        }
    return {
        "team_id": team_id, "level": level, "season": season,
        "wins": 0, "losses": 0, "pct": 0.0, "runs_scored": 0, "runs_allowed": 0,
    }


def get_milb_stats(team_id, level, season, db_path=None):
    """Return batting and pitching stats for players at a level."""
    batting = query("""
        SELECT mbs.*, p.first_name, p.last_name, p.position, p.age,
               p.contact_rating, p.power_rating, p.speed_rating
        FROM milb_batting_stats mbs
        JOIN players p ON p.id = mbs.player_id
        WHERE mbs.team_id=? AND mbs.level=? AND mbs.season=?
        ORDER BY mbs.hits DESC
    """, (team_id, level, season), db_path=db_path)

    pitching = query("""
        SELECT mps.*, p.first_name, p.last_name, p.position, p.age,
               p.stuff_rating, p.control_rating
        FROM milb_pitching_stats mps
        JOIN players p ON p.id = mps.player_id
        WHERE mps.team_id=? AND mps.level=? AND mps.season=?
        ORDER BY mps.wins DESC
    """, (team_id, level, season), db_path=db_path)

    # Compute derived stats
    batting_out = []
    for b in batting:
        ab = b["ab"] or 1
        avg = round(b["hits"] / ab, 3) if ab > 0 else 0
        obp_denom = ab + b["bb"]
        obp = round((b["hits"] + b["bb"]) / max(1, obp_denom), 3)
        slg_num = (b["hits"] - b["doubles"] - b["triples"] - b["hr"]) + \
                  b["doubles"] * 2 + b["triples"] * 3 + b["hr"] * 4
        slg = round(slg_num / max(1, ab), 3)
        batting_out.append({
            **dict(b),
            "avg": avg, "obp": obp, "slg": slg, "ops": round(obp + slg, 3),
        })

    pitching_out = []
    for p in pitching:
        ip_outs = p["ip_outs"] or 1
        ip = ip_outs / 3
        era = round((p["er"] * 9) / max(0.1, ip), 2)
        whip = round((p["bb"] + p["hits_allowed"]) / max(0.1, ip), 2)
        pitching_out.append({
            **dict(p),
            "ip": round(ip, 1), "era": era, "whip": whip,
        })

    return {"batting": batting_out, "pitching": pitching_out}


def get_all_milb_standings(level, season, db_path=None):
    """Return standings for all teams at a given level."""
    rows = query("""
        SELECT ms.*, t.city, t.name, t.abbreviation
        FROM milb_standings ms
        JOIN teams t ON t.id = ms.team_id
        WHERE ms.level=? AND ms.season=?
        ORDER BY ms.wins DESC
    """, (level, season), db_path=db_path)

    standings = []
    for row in rows:
        w = row["wins"]
        l = row["losses"]
        standings.append({
            **dict(row),
            "pct": round(w / max(1, w + l), 3),
        })
    return standings


def milb_promotions_check(team_id, season, game_date, db_path=None):
    """Check if any minor leaguers deserve a promotion recommendation.

    Called at end of each month. Sends messages for standout performers.
    Promotion ladder: Rookie → A → High-A → AA → AAA
    """
    messages = []

    # Batter promotion criteria by level
    # (from_level, to_level, display_from, min_avg, min_hr, min_ab)
    batter_criteria = [
        ("Rookie", "A", "Rookie Ball", 0.320, 5, 30),
        ("A", "High-A", "Low-A", 0.300, 8, 50),
        ("High-A", "AA", "High-A", 0.290, 10, 50),
        ("AA", "AAA", "AA", 0.280, 12, 50),
    ]

    for from_level, to_level, display, min_avg, min_hr, min_ab in batter_criteria:
        batters = query("""
            SELECT mbs.*, p.first_name, p.last_name, p.position
            FROM milb_batting_stats mbs
            JOIN players p ON p.id = mbs.player_id
            WHERE mbs.team_id=? AND mbs.level=? AND mbs.season=?
            AND mbs.ab >= ?
        """, (team_id, from_level, season, min_ab), db_path=db_path)

        for b in batters:
            avg = b["hits"] / max(1, b["ab"])
            if avg >= min_avg and b["hr"] >= min_hr:
                messages.append({
                    "player_id": b["player_id"],
                    "name": f"{b['first_name']} {b['last_name']}",
                    "level": from_level,
                    "target": to_level,
                    "reason": f"hitting .{int(avg * 1000)} with {b['hr']} HR at {display}",
                })

    # Pitcher promotion criteria
    # (from_level, to_level, max_era, min_so, min_ip_outs)
    pitcher_criteria = [
        ("Rookie", "A", 3.50, 25, 20),
        ("A", "High-A", 3.25, 40, 30),
        ("High-A", "AA", 3.00, 50, 30),
        ("AA", "AAA", 3.00, 50, 30),
    ]

    for from_level, to_level, max_era, min_so, min_ip in pitcher_criteria:
        pitchers = query("""
            SELECT mps.*, p.first_name, p.last_name, p.position
            FROM milb_pitching_stats mps
            JOIN players p ON p.id = mps.player_id
            WHERE mps.team_id=? AND mps.level=? AND mps.season=?
            AND mps.ip_outs >= ?
        """, (team_id, from_level, season, min_ip), db_path=db_path)

        for p in pitchers:
            ip = p["ip_outs"] / 3
            era = (p["er"] * 9) / max(0.1, ip)
            if era < max_era and p["so"] >= min_so:
                messages.append({
                    "player_id": p["player_id"],
                    "name": f"{p['first_name']} {p['last_name']}",
                    "level": from_level,
                    "target": to_level,
                    "reason": f"ERA {era:.2f} with {p['so']} K at {from_level}",
                })

    # Send messages from level-specific minor league coaches
    if messages:
        conn = get_connection(db_path)
        state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
        user_team_id = state["user_team_id"] if state else None
        conn.close()

        level_coaches = {
            "Rookie": "Rookie Ball Coordinator",
            "A": "Single-A Manager",
            "High-A": "High-A Manager",
            "AA": "AA Manager",
            "AAA": "AAA Manager",
        }

        promotion_templates = [
            "{name} is tearing it up here at {level}. {reason}. "
            "I think he's outgrown this level - he needs to be challenged at {target}.",
            "Boss, you need to see what {name} is doing down here. {reason}. "
            "This kid is ready for {target}. He's got nothing left to prove at {level}.",
            "Just wanted to flag {name} for you. {reason}. "
            "In my opinion, he'd benefit from a promotion to {target}. "
            "He's dominating the competition at this level.",
            "{name} has been our best player at {level}. {reason}. "
            "I've been working with him daily and he's ready for {target}. "
            "Don't let him get stale down here.",
        ]

        for msg in messages:
            if team_id == user_team_id:
                coach_name = level_coaches.get(msg['level'], 'Farm Director')
                body = random.choice(promotion_templates).format(
                    name=msg['name'], level=msg['level'],
                    target=msg['target'], reason=msg['reason']
                )
                execute("""
                    INSERT INTO messages (game_date, sender_type, sender_name,
                        recipient_type, recipient_id, subject, body, requires_response)
                    VALUES (?, 'coach', ?, 'user', ?,
                        ?, ?, 0)
                """, (
                    game_date, coach_name, team_id,
                    f"Promotion Candidate: {msg['name']}",
                    body
                ), db_path=db_path)

    return messages
