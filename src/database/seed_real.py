"""
Front Office - Seed with Real MLB Data
Uses cached data from the MLB Stats API to populate the database
with real players, teams, and stadiums.
"""
import json
import random
from pathlib import Path
from .db import get_connection, init_db
from .seed import (GM_FIRST, GM_LAST, OWNER_FIRST, OWNER_LAST,
                   PHILOSOPHIES, NEGOTIATION_STYLES, OWNER_ARCHETYPES)


CACHE_PATH = Path(__file__).parent.parent.parent / "mlb_cache.json"

# Realistic 26-man active roster slots
ROSTER_SLOTS = {
    # Position players (13)
    "C": 2, "1B": 1, "2B": 1, "SS": 1, "3B": 1,
    "LF": 2, "CF": 1, "RF": 1, "DH": 1,
    # Utility spots filled by best remaining IF/OF
}
# Total position players = 13 (11 above + 1 utility IF + 1 utility OF)
PITCHER_SLOTS = {"SP": 5, "RP": 8}  # 8 RP includes 1 closer


def _assign_realistic_rosters(conn, team_ids):
    """After all players are inserted as minors_aaa, promote 26 to active
    with a realistic position distribution: 13 position players + 13 pitchers."""

    for team_id in team_ids:
        all_players = conn.execute(
            "SELECT id, position, contact_rating, power_rating, speed_rating, "
            "fielding_rating, arm_rating, stuff_rating, control_rating, stamina_rating "
            "FROM players WHERE team_id=?",
            (team_id,)
        ).fetchall()

        promoted_ids = set()

        # Helper to pick best available player at a position
        def pick_best(position, key_fn, count=1):
            candidates = [p for p in all_players
                          if p["position"] == position and p["id"] not in promoted_ids]
            candidates.sort(key=key_fn, reverse=True)
            picked = []
            for c in candidates[:count]:
                promoted_ids.add(c["id"])
                picked.append(c)
            return picked

        # Helper for hitting value
        def hitting_val(p):
            return (p["contact_rating"] or 0) + (p["power_rating"] or 0)

        def fielding_val(p):
            return (p["fielding_rating"] or 0) * 2 + hitting_val(p)

        def pitching_val(p):
            return (p["stuff_rating"] or 0) + (p["control_rating"] or 0)

        # Fill required position player slots
        pick_best("C", fielding_val, 2)
        pick_best("1B", hitting_val, 1)
        pick_best("2B", fielding_val, 1)
        pick_best("SS", fielding_val, 1)
        pick_best("3B", fielding_val, 1)
        pick_best("LF", hitting_val, 2)
        pick_best("CF", lambda p: (p["speed_rating"] or 0) + (p["fielding_rating"] or 0), 1)
        pick_best("RF", hitting_val, 1)
        pick_best("DH", hitting_val, 1)

        # Utility IF: best remaining IF (2B/SS/3B/1B)
        util_if = [p for p in all_players
                   if p["position"] in ("2B", "SS", "3B", "1B") and p["id"] not in promoted_ids]
        util_if.sort(key=hitting_val, reverse=True)
        if util_if:
            promoted_ids.add(util_if[0]["id"])

        # Utility OF: best remaining OF (LF/CF/RF)
        util_of = [p for p in all_players
                   if p["position"] in ("LF", "CF", "RF") and p["id"] not in promoted_ids]
        util_of.sort(key=hitting_val, reverse=True)
        if util_of:
            promoted_ids.add(util_of[0]["id"])

        # Now we should have 13 position players (or fewer if team lacks depth)
        pos_count = len(promoted_ids)

        # Fill pitcher slots: 5 SP + 8 RP
        pick_best("SP", pitching_val, 5)
        pick_best("RP", pitching_val, 8)

        pitcher_count = len(promoted_ids) - pos_count

        # If we don't have enough RPs, convert extra SPs
        if pitcher_count < 13:
            remaining_sp = [p for p in all_players
                            if p["position"] == "SP" and p["id"] not in promoted_ids]
            remaining_sp.sort(key=pitching_val, reverse=True)
            needed = 13 - pitcher_count
            for sp in remaining_sp[:needed]:
                promoted_ids.add(sp["id"])

        # If we still don't have 26, fill with best remaining players
        while len(promoted_ids) < 26:
            remaining = [p for p in all_players if p["id"] not in promoted_ids]
            if not remaining:
                break
            remaining.sort(key=lambda p: hitting_val(p) + pitching_val(p), reverse=True)
            promoted_ids.add(remaining[0]["id"])

        # Update roster statuses
        if promoted_ids:
            placeholders = ",".join("?" * len(promoted_ids))
            conn.execute(
                f"UPDATE players SET roster_status='active' WHERE id IN ({placeholders})",
                list(promoted_ids)
            )

        # Remaining players stay as minors_aaa (already set)
        active_count = len(promoted_ids)
        total = len(all_players)
        print(f"  Team {team_id}: {active_count} active, {total - active_count} minors")


def seed_real_database(db_path: str = None):
    """Seed the database with real MLB data from cache."""
    if not CACHE_PATH.exists():
        print("No MLB data cache found. Run real_data.py first.")
        print("Falling back to generated data...")
        from .seed import seed_database
        seed_database(db_path)
        return

    init_db(db_path)
    conn = get_connection(db_path)

    count = conn.execute("SELECT COUNT(*) as c FROM teams").fetchone()["c"]
    if count > 0:
        print("Database already seeded.")
        conn.close()
        return

    with open(CACHE_PATH) as f:
        data = json.load(f)

    teams_data = data["teams"]
    players_data = data["players"]

    print("Seeding database with REAL MLB data...")

    # Insert teams
    team_ids = []
    team_abbrs = []
    for t in teams_data:
        cursor = conn.execute("""
            INSERT INTO teams (city, name, abbreviation, league, division,
                stadium_name, stadium_capacity, lf_distance, lcf_distance,
                cf_distance, rcf_distance, rf_distance, is_dome, surface,
                market_size, region_population, per_capita_income, fan_base)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (t["city"], t["name"], t["abbr"], t["league"], t["division"],
              t["stadium"], t.get("capacity", 40000),
              t.get("lf", 330), t.get("lcf", 370), t.get("cf", 400),
              t.get("rcf", 370), t.get("rf", 330),
              t.get("dome", 0), t.get("surface", "grass"),
              t.get("market", 3), t.get("pop", 3000000),
              t.get("income", 55000), t.get("fan_base", 50)))
        team_ids.append(cursor.lastrowid)
        team_abbrs.append(t["abbr"])

    # Insert real players (all as minors_aaa initially, then assign rosters)
    total_players = 0
    for i, (team_id, abbr) in enumerate(zip(team_ids, team_abbrs)):
        roster = players_data.get(abbr, [])
        if not roster:
            print(f"  {abbr}: No players in cache, generating...")
            continue

        for p in roster:
            salary = p.get("salary", 750000)
            contract_years = p.get("contract_years", 1)
            ntc = p.get("ntc", 0)

            # Insert all as minors_aaa; we'll assign proper rosters below
            roster_status = "minors_aaa"

            cursor = conn.execute("""
                INSERT INTO players (team_id, first_name, last_name, age, birth_country,
                    bats, throws, position, contact_rating, power_rating, speed_rating,
                    fielding_rating, arm_rating, stuff_rating, control_rating, stamina_rating,
                    contact_potential, power_potential, speed_potential, fielding_potential,
                    arm_potential, stuff_potential, control_potential, stamina_potential,
                    ego, leadership, work_ethic, clutch, durability,
                    roster_status, peak_age, development_rate, service_years,
                    option_years_remaining)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (team_id, p["first_name"], p["last_name"], p["age"],
                  p.get("birth_country", "USA"),
                  p.get("bats", "R"), p.get("throws", "R"), p["position"],
                  p["contact_rating"], p["power_rating"], p["speed_rating"],
                  p["fielding_rating"], p["arm_rating"],
                  p.get("stuff_rating", 20), p.get("control_rating", 20), p.get("stamina_rating", 20),
                  min(80, p["contact_rating"] + random.randint(0, 5)),
                  min(80, p["power_rating"] + random.randint(0, 5)),
                  min(80, p["speed_rating"] + random.randint(0, 5)),
                  min(80, p["fielding_rating"] + random.randint(0, 5)),
                  min(80, p["arm_rating"] + random.randint(0, 5)),
                  min(80, p.get("stuff_rating", 20) + random.randint(0, 5)),
                  min(80, p.get("control_rating", 20) + random.randint(0, 5)),
                  min(80, p.get("stamina_rating", 20) + random.randint(0, 5)),
                  random.randint(20, 80), random.randint(20, 80),
                  random.randint(40, 90), random.randint(30, 80), random.randint(40, 85),
                  roster_status,
                  random.randint(26, 30), round(random.uniform(0.8, 1.2), 2),
                  max(0, p["age"] - 22 + random.uniform(-1, 1)),
                  3 if p["age"] < 25 else max(0, random.randint(0, 2))))

            player_id = cursor.lastrowid
            conn.execute("""
                INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
                    annual_salary, no_trade_clause, signed_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (player_id, team_id, contract_years, contract_years,
                  salary, ntc, "2026-01-15"))

            # Insert historical stats if available
            if p.get("hitting_stats"):
                stats = p["hitting_stats"]
                conn.execute("""
                    INSERT OR IGNORE INTO batting_stats (
                        player_id, team_id, season, level, games, pa, ab, runs, hits,
                        doubles, triples, hr, rbi, bb, so, sb, cs, hbp, sf)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, team_id, 2024, "MLB",
                    int(stats.get("gamesPlayed", 0)),
                    int(stats.get("plateAppearances", 0)),
                    int(stats.get("atBats", 0)),
                    int(stats.get("runs", 0)),
                    int(stats.get("hits", 0)),
                    int(stats.get("doubles", 0)),
                    int(stats.get("triples", 0)),
                    int(stats.get("homeRuns", 0)),
                    int(stats.get("rbi", 0)),
                    int(stats.get("baseOnBalls", 0)),
                    int(stats.get("strikeOuts", 0)),
                    int(stats.get("stolenBases", 0)),
                    int(stats.get("caughtStealing", 0)),
                    int(stats.get("hitByPitch", 0)),
                    int(stats.get("sacFlies", 0))
                ))

            if p.get("pitching_stats"):
                stats = p["pitching_stats"]
                ip_str = stats.get("inningsPitched", "0.0")
                try:
                    ip_parts = str(ip_str).split(".")
                    ip_outs = int(ip_parts[0]) * 3 + (int(ip_parts[1]) if len(ip_parts) > 1 else 0)
                except (ValueError, IndexError):
                    ip_outs = 0

                conn.execute("""
                    INSERT OR IGNORE INTO pitching_stats (
                        player_id, team_id, season, level, games, games_started, wins,
                        losses, saves, ip_outs, hits_allowed, runs_allowed, er, bb, so,
                        hr_allowed, pitches)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    player_id, team_id, 2024, "MLB",
                    int(stats.get("gamesPitched", 0)),
                    int(stats.get("gamesStarted", 0)),
                    int(stats.get("wins", 0)),
                    int(stats.get("losses", 0)),
                    int(stats.get("saves", 0)),
                    ip_outs,
                    int(stats.get("hits", 0)),
                    int(stats.get("runs", 0)),
                    int(stats.get("earnedRuns", 0)),
                    int(stats.get("baseOnBalls", 0)),
                    int(stats.get("strikeOuts", 0)),
                    int(stats.get("homeRuns", 0)),
                    int(stats.get("pitches", 0))
                ))

            total_players += 1

        print(f"  {abbr}: {len(roster)} real players loaded")

    # Assign proper roster slots per team (13 position players + 13 pitchers = 26 active)
    print("Assigning realistic roster compositions...")
    _assign_realistic_rosters(conn, team_ids)

    # Insert GM characters
    random.shuffle(GM_FIRST)
    random.shuffle(GM_LAST)
    for i, team_id in enumerate(team_ids):
        philosophy = random.choice(PHILOSOPHIES)
        personality = {
            "background": random.choice(["analytics_dept", "former_player", "scouting", "journalism", "law"]),
            "quirks": random.choice(["never_trades_within_division", "loves_veterans", "prospect_hoarder",
                                     "always_in_on_big_names", "builds_through_draft",
                                     "overpays_closers", "undervalues_defense", "analytics_obsessed"]),
        }
        conn.execute("""
            INSERT INTO gm_characters (team_id, first_name, last_name, age, philosophy,
                risk_tolerance, ego, negotiation_style, competence, patience,
                job_security, personality_json, contract_years_remaining)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (team_id, GM_FIRST[i % len(GM_FIRST)], GM_LAST[i % len(GM_LAST)],
              random.randint(35, 65), philosophy,
              random.randint(20, 90), random.randint(20, 90),
              random.choice(NEGOTIATION_STYLES),
              random.randint(30, 90), random.randint(20, 80),
              random.randint(40, 90), json.dumps(personality),
              random.randint(1, 5)))

    # Insert owner characters
    random.shuffle(OWNER_FIRST)
    random.shuffle(OWNER_LAST)
    for i, team_id in enumerate(team_ids):
        archetype = random.choice(OWNER_ARCHETYPES)
        market = teams_data[i].get("market", 3)
        budget_base = market * 15 + random.randint(-10, 10)
        objectives = [{"type": "short_term",
                       "description": random.choice(["Make the playoffs", "Win the division",
                                                     "Improve by 10 wins", "Develop young talent"]),
                       "deadline": 2026, "met": False}]
        conn.execute("""
            INSERT INTO owner_characters (team_id, first_name, last_name, age,
                archetype, budget_willingness, patience, meddling,
                objectives_json, personality_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (team_id, OWNER_FIRST[i % len(OWNER_FIRST)], OWNER_LAST[i % len(OWNER_LAST)],
              random.randint(45, 80), archetype,
              max(10, min(100, budget_base)),
              random.randint(20, 80), random.randint(10, 70),
              json.dumps(objectives), json.dumps({"net_worth_billions": round(random.uniform(1.5, 15.0), 1)})))

    # Generate free agents from MLB data
    print("Generating free agents...")
    from .seed import POSITIONS_BATTING, POSITIONS_PITCHING, _generate_player, FIRST_NAMES, LAST_NAMES

    free_agent_count = random.randint(100, 150)
    used_names = set()

    # Collect all player names already used in rosters
    existing = conn.execute("SELECT first_name, last_name FROM players").fetchall()
    for p in existing:
        used_names.add(f"{p['first_name']} {p['last_name']}")

    for _ in range(free_agent_count):
        position = random.choice(POSITIONS_BATTING + POSITIONS_PITCHING)
        age = random.randint(28, 38)

        if random.random() < 0.85:
            tier = "bench"
        else:
            tier = "starter"

        p = _generate_player(position, tier, used_names)
        p["age"] = age

        cursor = conn.execute("""
            INSERT INTO players (team_id, first_name, last_name, age, birth_country,
                bats, throws, position, contact_rating, power_rating, speed_rating,
                fielding_rating, arm_rating, stuff_rating, control_rating, stamina_rating,
                contact_potential, power_potential, speed_potential, fielding_potential,
                arm_potential, stuff_potential, control_potential, stamina_potential,
                ego, leadership, work_ethic, clutch, durability,
                roster_status, peak_age, development_rate, service_years,
                option_years_remaining)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (None, p["first_name"], p["last_name"], p["age"], p["birth_country"],
              p["bats"], p["throws"], p["position"],
              p["contact_rating"], p["power_rating"], p["speed_rating"],
              p["fielding_rating"], p["arm_rating"],
              p["stuff_rating"], p["control_rating"], p["stamina_rating"],
              p["contact_potential"], p["power_potential"], p["speed_potential"],
              p["fielding_potential"], p["arm_potential"],
              p["stuff_potential"], p["control_potential"], p["stamina_potential"],
              p["ego"], p["leadership"], p["work_ethic"], p["clutch"], p["durability"],
              "free_agent", p["peak_age"], p["development_rate"],
              p["service_years"], p["option_years_remaining"]))
        total_players += 1

    print(f"  Generated {free_agent_count} free agents")

    conn.commit()

    # Generate schedule
    print("Generating 162-game schedule...")
    try:
        from ..simulation.schedule import generate_schedule
        teams_for_sched = [{"id": tid, "league": teams_data[i]["league"],
                           "division": teams_data[i]["division"]}
                          for i, tid in enumerate(team_ids)]
        schedule_games = generate_schedule(2026, teams_for_sched)
    except Exception as e:
        print(f"  Schedule fallback: {e}")
        from .seed import _generate_schedule
        schedule_games = _generate_schedule(2026, team_ids)

    for g in schedule_games:
        conn.execute("""
            INSERT INTO schedule (season, game_date, home_team_id, away_team_id, game_number)
            VALUES (?, ?, ?, ?, ?)
        """, (g["season"], g["game_date"], g["home_team_id"], g["away_team_id"],
              g.get("game_number", 1)))

    conn.execute("""
        INSERT OR REPLACE INTO game_state (id, current_date, season, phase, difficulty)
        VALUES (1, '2026-02-15', 2026, 'spring_training', 'manager')
    """)

    conn.commit()

    game_count = conn.execute("SELECT COUNT(*) as c FROM schedule").fetchone()["c"]
    print(f"\nReal data seed complete!")
    print(f"  Teams: {len(team_ids)}")
    print(f"  Players: {total_players}")
    print(f"  Scheduled games: {game_count}")

    conn.close()


if __name__ == "__main__":
    seed_real_database()
