"""
Front Office - Amateur Draft System
20-round draft with procedurally generated prospects.
Scouting uncertainty baked into floor/ceiling ratings.
"""
import random
import json
from ..database.db import get_connection, query
from ..database.seed import FIRST_NAMES, LAST_NAMES, COUNTRIES


POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "SP", "SP", "SP", "RP"]


def generate_draft_class(season: int, db_path: str = None) -> list:
    """Generate a full draft class of ~600 prospects (20 rounds * 30 teams)."""
    conn = get_connection(db_path)

    # Check if already generated
    existing = conn.execute("SELECT COUNT(*) as c FROM draft_prospects WHERE season=?",
                           (season,)).fetchone()["c"]
    if existing > 0:
        conn.close()
        return query("SELECT * FROM draft_prospects WHERE season=? ORDER BY overall_rank",
                    (season,), db_path=db_path)

    used_names = set()
    prospects = []

    for rank in range(1, 601):
        # Top prospects have higher ceilings
        if rank <= 30:  # 1st round
            tier = "elite"
        elif rank <= 90:  # 2nd-3rd round
            tier = "good"
        elif rank <= 180:  # 4th-6th round
            tier = "average"
        elif rank <= 300:  # 7th-10th round
            tier = "below_average"
        else:  # 11th-20th round
            tier = "lottery"

        prospect = _generate_prospect(tier, rank, used_names)
        prospect["season"] = season
        prospect["overall_rank"] = rank

        conn.execute("""
            INSERT INTO draft_prospects (season, first_name, last_name, age, position,
                bats, throws, contact_floor, contact_ceiling, power_floor, power_ceiling,
                speed_floor, speed_ceiling, fielding_floor, fielding_ceiling,
                arm_floor, arm_ceiling, stuff_floor, stuff_ceiling,
                control_floor, control_ceiling, overall_rank, scouting_report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (season, prospect["first_name"], prospect["last_name"], prospect["age"],
              prospect["position"], prospect["bats"], prospect["throws"],
              prospect["contact_floor"], prospect["contact_ceiling"],
              prospect["power_floor"], prospect["power_ceiling"],
              prospect["speed_floor"], prospect["speed_ceiling"],
              prospect["fielding_floor"], prospect["fielding_ceiling"],
              prospect["arm_floor"], prospect["arm_ceiling"],
              prospect["stuff_floor"], prospect["stuff_ceiling"],
              prospect["control_floor"], prospect["control_ceiling"],
              rank, prospect.get("scouting_report", "")))

        prospects.append(prospect)

    conn.commit()
    conn.close()
    return prospects


def _generate_prospect(tier: str, rank: int, used_names: set) -> dict:
    """Generate a single draft prospect with floor/ceiling uncertainty."""
    position = random.choice(POSITIONS)
    is_pitcher = position in ("SP", "RP")

    # Name generation
    for _ in range(100):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        if f"{first} {last}" not in used_names:
            used_names.add(f"{first} {last}")
            break

    age = random.choices([18, 19, 20, 21, 22], weights=[10, 15, 25, 30, 20])[0]

    # Tier-based rating ranges
    ranges = {
        "elite": {"base": (55, 75), "spread": (10, 20)},
        "good": {"base": (45, 65), "spread": (12, 22)},
        "average": {"base": (35, 55), "spread": (15, 25)},
        "below_average": {"base": (25, 45), "spread": (15, 30)},
        "lottery": {"base": (20, 40), "spread": (15, 35)},
    }

    r = ranges[tier]

    def _floor_ceiling():
        mid = random.randint(*r["base"])
        spread = random.randint(*r["spread"])
        floor = max(20, mid - spread // 2)
        ceiling = min(80, mid + spread // 2)
        return floor, ceiling

    cf, cc = _floor_ceiling()
    pf, pc = _floor_ceiling()
    sf, sc = _floor_ceiling()
    ff, fc = _floor_ceiling()
    af, ac = _floor_ceiling()

    if is_pitcher:
        stf, stc = _floor_ceiling()
        ctf, ctc = _floor_ceiling()
    else:
        stf, stc = 20, 20
        ctf, ctc = 20, 20

    return {
        "first_name": first,
        "last_name": last,
        "age": age,
        "position": position,
        "bats": random.choices(["R", "L", "S"], weights=[55, 30, 15])[0],
        "throws": "L" if (is_pitcher and random.random() < 0.30) else "R",
        "contact_floor": cf, "contact_ceiling": cc,
        "power_floor": pf, "power_ceiling": pc,
        "speed_floor": sf, "speed_ceiling": sc,
        "fielding_floor": ff, "fielding_ceiling": fc,
        "arm_floor": af, "arm_ceiling": ac,
        "stuff_floor": stf, "stuff_ceiling": stc,
        "control_floor": ctf, "control_ceiling": ctc,
        "birth_country": random.choice(COUNTRIES),
    }


def initialize_draft_pick_ownership(season: int, db_path: str = None) -> list:
    """
    Initialize draft pick ownership for a season.
    Each team owns one pick per round (rounds 1-20), 30 teams * 20 rounds = 600 picks.
    """
    conn = get_connection(db_path)

    # Check if already initialized
    existing = conn.execute("""
        SELECT COUNT(*) as c FROM draft_pick_ownership WHERE season=?
    """, (season,)).fetchone()["c"]

    if existing > 0:
        conn.close()
        return query("""
            SELECT * FROM draft_pick_ownership WHERE season=?
            ORDER BY round, pick_number
        """, (season,), db_path=db_path)

    # Get all teams
    teams = conn.execute("SELECT id FROM teams ORDER BY id").fetchall()
    team_ids = [t["id"] for t in teams]

    picks_created = []

    # Create picks for 20 rounds
    for round_num in range(1, 21):
        # Rotate team order by round (worst record gets earlier picks - simplified: reverse order)
        team_order = list(reversed(team_ids)) if round_num % 2 == 0 else team_ids

        for pick_num, team_id in enumerate(team_order, 1):
            conn.execute("""
                INSERT INTO draft_pick_ownership
                (season, round, pick_number, original_team_id, current_owner_team_id)
                VALUES (?, ?, ?, ?, ?)
            """, (season, round_num, pick_num, team_id, team_id))

            picks_created.append({
                "season": season,
                "round": round_num,
                "pick": pick_num,
                "owner_team_id": team_id,
            })

    conn.commit()
    conn.close()
    return picks_created


def make_draft_pick(team_id: int, prospect_id: int, round_num: int,
                    pick_num: int, db_path: str = None) -> dict:
    """Draft a prospect - creates a real player from the prospect template."""
    conn = get_connection(db_path)

    prospect = conn.execute("SELECT * FROM draft_prospects WHERE id=? AND is_drafted=0",
                           (prospect_id,)).fetchone()
    if not prospect:
        conn.close()
        return {"error": "Prospect not found or already drafted"}

    p = dict(prospect)

    # Resolve actual ratings from floor/ceiling range
    contact = random.randint(p["contact_floor"], p["contact_ceiling"])
    power = random.randint(p["power_floor"], p["power_ceiling"])
    speed = random.randint(p["speed_floor"], p["speed_ceiling"])
    fielding = random.randint(p["fielding_floor"], p["fielding_ceiling"])
    arm = random.randint(p["arm_floor"], p["arm_ceiling"])
    stuff = random.randint(p["stuff_floor"], p["stuff_ceiling"])
    control = random.randint(p["control_floor"], p["control_ceiling"])

    # Create the player
    cursor = conn.execute("""
        INSERT INTO players (team_id, first_name, last_name, age, bats, throws,
            position, contact_rating, power_rating, speed_rating, fielding_rating,
            arm_rating, stuff_rating, control_rating, stamina_rating,
            contact_potential, power_potential, speed_potential, fielding_potential,
            arm_potential, stuff_potential, control_potential, stamina_potential,
            ego, leadership, work_ethic, clutch, durability,
            roster_status, peak_age, development_rate, option_years_remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, 'minors_low', ?, ?, 3)
    """, (team_id, p["first_name"], p["last_name"], p["age"], p["bats"], p["throws"],
          p["position"], contact, power, speed, fielding, arm, stuff, control,
          random.randint(30, 70),
          p["contact_ceiling"], p["power_ceiling"], p["speed_ceiling"],
          p["fielding_ceiling"], p["arm_ceiling"], p["stuff_ceiling"],
          p["control_ceiling"], random.randint(30, 70),
          random.randint(20, 80), random.randint(20, 70),
          random.randint(30, 90), random.randint(20, 80), random.randint(30, 90),
          random.randint(24, 29), round(random.uniform(0.7, 1.3), 2)))

    player_id = cursor.lastrowid

    # Create rookie contract
    signing_bonus = max(100000, 5000000 - (round_num * 200000))
    conn.execute("""
        INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
            annual_salary, signing_bonus, signed_date)
        VALUES (?, ?, 4, 4, 720000, ?, ?)
    """, (player_id, team_id, signing_bonus,
          f"{p['season']}-07-15"))

    # Mark prospect as drafted
    conn.execute("""
        UPDATE draft_prospects SET is_drafted=1, drafted_by_team_id=?,
            draft_round=?, draft_pick=? WHERE id=?
    """, (team_id, round_num, pick_num, prospect_id))

    # Log transaction
    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'draft_pick', ?, ?, ?)
    """, (f"{p['season']}-07-15",
          json.dumps({"round": round_num, "pick": pick_num,
                     "prospect_name": f"{p['first_name']} {p['last_name']}"}),
          team_id, str(player_id)))

    # Send notification if drafted by user's team
    state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
    user_team_id = state["user_team_id"] if state else None
    if team_id == user_team_id:
        from .messages import send_draft_notification
        player_name = f"{p['first_name']} {p['last_name']}"
        team = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()
        team_name = f"{team['city']} {team['name']}" if team else "Your Team"
        send_draft_notification(user_team_id, player_name, round_num, pick_num, team_name, db_path=db_path)

    conn.commit()
    conn.close()

    return {
        "success": True,
        "player_id": player_id,
        "name": f"{p['first_name']} {p['last_name']}",
        "position": p["position"],
        "round": round_num,
        "pick": pick_num,
    }
