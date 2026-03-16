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

    # Insert real players
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

            # Determine roster status
            roster_status = p.get("roster_status", "active")
            if total_players > 0:
                # Keep first 26 per team as active, rest as minors
                team_player_count = conn.execute(
                    "SELECT COUNT(*) as c FROM players WHERE team_id=? AND roster_status='active'",
                    (team_id,)).fetchone()["c"]
                is_pitcher = p["position"] in ("SP", "RP")
                if team_player_count >= 26:
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
            total_players += 1

        print(f"  {abbr}: {len(roster)} real players loaded")

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
