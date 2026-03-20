"""
Front Office - Coaching Staff System
Generates coaching pools, handles hiring/firing, and provides
automatic lineup/rotation management based on coach tendencies.

The user is the GM - coaches handle lineups, rotations, and in-game
decisions automatically based on their tendencies and skills.
"""
import json
import random
from typing import Optional, List, Dict
from ..database.db import get_connection, query, execute


# ============================================================
# NAME POOLS
# ============================================================
FIRST_NAMES = [
    "Mike", "Dave", "Joe", "Bob", "Tom", "Bill", "Jim", "Steve", "Mark", "Chris",
    "Tony", "Frank", "Rick", "Don", "Dan", "Ron", "Jack", "Terry", "Pat", "Ken",
    "Buck", "Dusty", "Skip", "Bud", "Sparky", "Red", "Whitey", "Rocky", "Ozzie", "Lou",
    "Charlie", "Eddie", "Pete", "Ray", "Al", "Hank", "Manny", "Carlos", "Felix", "Luis",
    "Alex", "Matt", "Kevin", "Brian", "Scott", "Craig", "Phil", "Jeff", "Gary", "Bruce",
    "Aaron", "Tim", "Bobby", "Willie", "Reggie", "Curt", "Greg", "Larry", "Wayne", "Dale",
]

LAST_NAMES = [
    "Baker", "Roberts", "Johnson", "Martinez", "Williams", "Thompson", "Anderson",
    "Garcia", "Davis", "Miller", "Wilson", "Moore", "Taylor", "Brown", "Jackson",
    "White", "Harris", "Clark", "Lewis", "Young", "Walker", "Allen", "King",
    "Wright", "Lopez", "Hill", "Scott", "Green", "Adams", "Nelson", "Carter",
    "Mitchell", "Perez", "Robinson", "Torres", "Phillips", "Campbell", "Evans",
    "Turner", "Collins", "Stewart", "Morris", "Murphy", "Rivera", "Cook",
    "Rogers", "Morgan", "Cooper", "Peterson", "Reed", "Bailey", "Sullivan",
    "Ramirez", "Cruz", "Hernandez", "Ortiz", "Gonzalez", "Sanchez", "Diaz", "Reyes",
]

CATCHPHRASES = {
    "fiery": [
        "We're not here to make friends, we're here to win.",
        "You play hard or you don't play at all.",
        "This team needs fire in its belly.",
        "I don't care about feelings, I care about wins.",
        "If you can't handle the heat, get out of the dugout.",
    ],
    "steady": [
        "Trust the process, day by day.",
        "Stay even-keel and the results will come.",
        "We control what we can control.",
        "Consistency wins championships.",
        "Just play good baseball.",
    ],
    "players_coach": [
        "My door is always open.",
        "Happy players play better baseball.",
        "I believe in every guy in this clubhouse.",
        "We're a family first, a team second.",
        "Take care of your players and they'll take care of you.",
    ],
    "disciplinarian": [
        "There's a right way to play this game.",
        "Fundamentals win ballgames.",
        "No excuses, no shortcuts.",
        "You earn your spot every single day.",
        "Discipline is the bridge between goals and accomplishment.",
    ],
    "innovator": [
        "The numbers don't lie.",
        "We're always looking for an edge.",
        "Baseball is evolving and so are we.",
        "Data is our competitive advantage.",
        "Why do it the old way when there's a better way?",
    ],
}


# ============================================================
# COACH ARCHETYPES
# ============================================================
COACH_ARCHETYPES = {
    "old_school_skipper": {
        "personality": "fiery",
        "analytics_orientation": (15, 35),
        "aggressiveness": (60, 85),
        "patience_with_young_players": (25, 45),
        "bullpen_management": (25, 40),
        "platoon_tendency": (20, 40),
        "lineup_construction": (40, 65),
        "game_strategy": (50, 75),
        "player_relations": (35, 55),
        "reputation": (50, 80),
    },
    "analytics_guru": {
        "personality": "innovator",
        "analytics_orientation": (75, 95),
        "aggressiveness": (35, 55),
        "patience_with_young_players": (55, 75),
        "bullpen_management": (60, 85),
        "platoon_tendency": (65, 90),
        "lineup_construction": (65, 90),
        "game_strategy": (55, 75),
        "player_relations": (40, 60),
        "reputation": (40, 70),
    },
    "players_manager": {
        "personality": "players_coach",
        "analytics_orientation": (40, 60),
        "aggressiveness": (40, 60),
        "patience_with_young_players": (70, 90),
        "bullpen_management": (40, 60),
        "platoon_tendency": (35, 55),
        "lineup_construction": (45, 65),
        "game_strategy": (40, 60),
        "player_relations": (75, 95),
        "reputation": (50, 75),
    },
    "drill_sergeant": {
        "personality": "disciplinarian",
        "analytics_orientation": (30, 50),
        "aggressiveness": (50, 70),
        "patience_with_young_players": (20, 40),
        "bullpen_management": (45, 65),
        "platoon_tendency": (30, 50),
        "lineup_construction": (50, 70),
        "game_strategy": (55, 75),
        "player_relations": (25, 45),
        "reputation": (45, 70),
    },
    "balanced_veteran": {
        "personality": "steady",
        "analytics_orientation": (40, 65),
        "aggressiveness": (40, 60),
        "patience_with_young_players": (45, 65),
        "bullpen_management": (45, 65),
        "platoon_tendency": (40, 60),
        "lineup_construction": (50, 70),
        "game_strategy": (50, 70),
        "player_relations": (50, 70),
        "reputation": (50, 75),
    },
    "development_focused": {
        "personality": "players_coach",
        "analytics_orientation": (50, 70),
        "aggressiveness": (30, 50),
        "patience_with_young_players": (80, 95),
        "bullpen_management": (50, 65),
        "platoon_tendency": (35, 55),
        "lineup_construction": (40, 60),
        "game_strategy": (40, 55),
        "player_relations": (65, 85),
        "reputation": (35, 60),
    },
}


def _rand_range(r):
    """Return random int from a (low, high) tuple."""
    return random.randint(r[0], r[1])


def _generate_coach_name(used_names: set) -> str:
    """Generate a unique coach name."""
    for _ in range(100):
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        if name not in used_names:
            used_names.add(name)
            return name
    # Fallback with suffix
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)} Jr."
    used_names.add(name)
    return name


# ============================================================
# GENERATE COACHING POOL
# ============================================================
def generate_coaching_pool():
    """
    Generate ~110 coaches: one manager, one hitting coach, and one pitching
    coach per team (90 assigned), plus ~20 free agent coaches available for hire.
    Returns count of coaches created.
    """
    conn = get_connection()

    # Check if coaches already exist
    existing = conn.execute("SELECT COUNT(*) FROM coaching_staff").fetchone()[0]
    if existing > 0:
        conn.close()
        return {"created": 0, "message": "Coaching pool already exists"}

    teams = conn.execute("SELECT id FROM teams").fetchall()
    team_ids = [t[0] for t in teams]

    used_names = set()
    coaches_created = 0
    archetype_keys = list(COACH_ARCHETYPES.keys())

    def _make_coach(team_id: int, role: str, is_available: int = 0) -> dict:
        """Build a coach dict from a random archetype."""
        archetype_name = random.choice(archetype_keys)
        arch = COACH_ARCHETYPES[archetype_name]
        personality = arch["personality"]
        name = _generate_coach_name(used_names)

        # Role-specific skill boosts
        pitcher_dev = _rand_range((30, 70))
        hitter_dev = _rand_range((30, 70))
        if role == "pitching_coach":
            pitcher_dev = _rand_range((55, 90))
        elif role == "hitting_coach":
            hitter_dev = _rand_range((55, 90))

        age = random.randint(38, 72)
        experience = max(1, age - random.randint(30, 42))

        salary_base = {
            "manager": (1500000, 5000000),
            "hitting_coach": (500000, 1500000),
            "pitching_coach": (500000, 1500000),
            "bench_coach": (400000, 1000000),
            "bullpen_coach": (300000, 800000),
            "first_base_coach": (250000, 600000),
            "third_base_coach": (250000, 600000),
            "farm_director": (400000, 1200000),
            "assistant_gm": (600000, 2000000),
        }
        sal_range = salary_base.get(role, (300000, 1000000))
        salary = random.randint(sal_range[0], sal_range[1])
        # Round to nearest 50k
        salary = (salary // 50000) * 50000

        career_wins = random.randint(0, experience * 80) if role == "manager" else 0
        career_losses = int(career_wins * random.uniform(0.85, 1.15)) if career_wins > 0 else 0

        catchphrase = random.choice(CATCHPHRASES.get(personality, CATCHPHRASES["steady"]))

        return {
            "team_id": team_id,
            "role": role,
            "name": name,
            "age": age,
            "experience": experience,
            "analytics_orientation": _rand_range(arch["analytics_orientation"]),
            "aggressiveness": _rand_range(arch["aggressiveness"]),
            "patience_with_young_players": _rand_range(arch["patience_with_young_players"]),
            "bullpen_management": _rand_range(arch["bullpen_management"]),
            "platoon_tendency": _rand_range(arch["platoon_tendency"]),
            "lineup_construction": _rand_range(arch["lineup_construction"]),
            "pitcher_development": pitcher_dev,
            "hitter_development": hitter_dev,
            "game_strategy": _rand_range(arch["game_strategy"]),
            "player_relations": _rand_range(arch["player_relations"]),
            "reputation": _rand_range(arch["reputation"]),
            "annual_salary": salary,
            "years_remaining": random.randint(1, 4),
            "personality": personality,
            "catchphrase": catchphrase,
            "career_wins": career_wins,
            "career_losses": career_losses,
            "is_available": is_available,
        }

    def _insert_coach(c: dict):
        conn.execute("""
            INSERT INTO coaching_staff (
                team_id, role, name, age, experience,
                analytics_orientation, aggressiveness, patience_with_young_players,
                bullpen_management, platoon_tendency, lineup_construction,
                pitcher_development, hitter_development, game_strategy,
                player_relations, reputation, annual_salary, years_remaining,
                personality, catchphrase, career_wins, career_losses, is_available
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            c["team_id"], c["role"], c["name"], c["age"], c["experience"],
            c["analytics_orientation"], c["aggressiveness"], c["patience_with_young_players"],
            c["bullpen_management"], c["platoon_tendency"], c["lineup_construction"],
            c["pitcher_development"], c["hitter_development"], c["game_strategy"],
            c["player_relations"], c["reputation"], c["annual_salary"], c["years_remaining"],
            c["personality"], c["catchphrase"], c["career_wins"], c["career_losses"],
            c["is_available"],
        ))

    # Assign one manager, one hitting coach, one pitching coach,
    # one farm director, and one assistant GM per team
    for tid in team_ids:
        for role in ["manager", "hitting_coach", "pitching_coach",
                     "farm_director", "assistant_gm"]:
            coach = _make_coach(tid, role, is_available=0)
            _insert_coach(coach)
            coaches_created += 1

    # Generate ~25 free agent coaches
    fa_roles = (
        ["manager"] * 5 +
        ["hitting_coach"] * 5 +
        ["pitching_coach"] * 5 +
        ["bench_coach"] * 3 +
        ["bullpen_coach"] * 2 +
        ["farm_director"] * 3 +
        ["assistant_gm"] * 2
    )
    for role in fa_roles:
        coach = _make_coach(0, role, is_available=1)
        coach["team_id"] = None  # no team (free agent coach)
        _insert_coach(coach)
        coaches_created += 1

    conn.commit()
    conn.close()
    return {"created": coaches_created, "message": f"Generated {coaches_created} coaches"}


# ============================================================
# AUTO SET LINEUP
# ============================================================
def auto_set_lineup(team_id: int) -> dict:
    """
    Manager automatically sets the optimal lineup based on their tendencies.
    Called before each game during sim advance.

    - High analytics_orientation: optimize by OPS, platoon matchups
    - Low analytics_orientation: traditional (best hitter 3rd, power 4th)
    - High aggressiveness: put speedsters at top
    - High platoon_tendency: platoon vs LHP and RHP differently
    """
    conn = get_connection()

    # Get the manager for this team
    manager = conn.execute(
        "SELECT * FROM coaching_staff WHERE team_id=? AND role='manager' AND is_available=0",
        (team_id,)
    ).fetchone()

    if not manager:
        conn.close()
        return {"success": False, "message": "No manager found for team"}

    # Get active position players (not pitchers, not injured)
    batters = conn.execute("""
        SELECT p.*, bs.hits, bs.ab, bs.hr, bs.bb, bs.so, bs.doubles, bs.triples,
               bs.sb, bs.hbp, bs.sf, bs.pa
        FROM players p
        LEFT JOIN batting_stats bs ON bs.player_id = p.id
            AND bs.season = (SELECT season FROM game_state WHERE id=1)
            AND bs.level = 'MLB'
        WHERE p.team_id=? AND p.roster_status='active'
            AND p.position NOT IN ('SP', 'RP') AND p.is_injured=0
        ORDER BY p.contact_rating + p.power_rating DESC
    """, (team_id,)).fetchall()

    if len(batters) < 9:
        conn.close()
        return {"success": False, "message": "Not enough active batters for a lineup"}

    analytics = manager["analytics_orientation"]
    aggression = manager["aggressiveness"]
    platoon = manager["platoon_tendency"]

    # Calculate composite scores for each batter
    scored_batters = []
    for b in batters:
        ab = b["ab"] or 0
        hits = b["hits"] or 0
        hr = b["hr"] or 0
        bb = b["bb"] or 0
        doubles = b["doubles"] or 0
        triples = b["triples"] or 0
        hbp = b["hbp"] or 0
        sf = b["sf"] or 0
        pa = b["pa"] or 0
        sb = b["sb"] or 0

        # Compute OBP and SLG from stats (or estimate from ratings)
        if ab > 20:
            avg = hits / ab
            obp = (hits + bb + hbp) / max(pa, 1)
            slg = (hits + doubles + 2 * triples + 3 * hr) / max(ab, 1)
            ops = obp + slg
        else:
            # Estimate from ratings
            avg = 0.200 + (b["contact_rating"] - 20) * 0.003
            obp = avg + 0.030 + (b["eye_rating"] - 20) * 0.002
            slg = avg + 0.050 + (b["power_rating"] - 20) * 0.005
            ops = obp + slg

        scored_batters.append({
            "id": b["id"],
            "name": f"{b['first_name']} {b['last_name']}",
            "position": b["position"],
            "bats": b["bats"],
            "contact": b["contact_rating"],
            "power": b["power_rating"],
            "speed": b["speed_rating"],
            "eye": b["eye_rating"],
            "fielding": b["fielding_rating"],
            "ops": ops,
            "obp": obp if ab > 20 else obp,
            "slg": slg if ab > 20 else slg,
            "avg": avg,
            "sb": sb,
        })

    # Position assignment: ensure we fill each position
    positions_needed = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
    assigned = {}  # position -> batter
    available = list(scored_batters)

    # First pass: assign best player at each position
    for pos in positions_needed:
        if pos == "DH":
            continue
        candidates = [b for b in available if b["position"] == pos]
        if candidates:
            best = max(candidates, key=lambda x: x["ops"])
            assigned[pos] = best
            available.remove(best)

    # Fill remaining positions with best available
    for pos in positions_needed:
        if pos not in assigned:
            if available:
                best = max(available, key=lambda x: x["ops"])
                assigned[pos] = best
                available.remove(best)

    lineup_players = list(assigned.values())[:9]

    # Now order the lineup based on manager tendencies
    if analytics >= 60:
        # Analytics approach: optimize by OPS
        # 1-2: high OBP, 3-4: high OPS/power, 5-6: next best, 7-9: rest
        lineup_players.sort(key=lambda x: x["ops"], reverse=True)

        # Reorder: best OBP at 1-2, best power at 3-4
        high_obp = sorted(lineup_players, key=lambda x: x["obp"], reverse=True)
        high_ops = sorted(lineup_players, key=lambda x: x["ops"], reverse=True)

        order = [None] * 9
        used = set()

        # Leadoff: highest OBP
        for b in high_obp:
            if b["id"] not in used:
                order[0] = b
                used.add(b["id"])
                break

        # 2nd: next highest OBP (with some speed consideration)
        obp_speed = sorted(
            [b for b in lineup_players if b["id"] not in used],
            key=lambda x: x["obp"] * 0.7 + (x["speed"] / 80) * 0.3, reverse=True
        )
        if obp_speed:
            order[1] = obp_speed[0]
            used.add(obp_speed[0]["id"])

        # 3rd-4th: highest OPS
        for slot in [2, 3]:
            for b in high_ops:
                if b["id"] not in used:
                    order[slot] = b
                    used.add(b["id"])
                    break

        # Fill rest by OPS
        remaining = sorted(
            [b for b in lineup_players if b["id"] not in used],
            key=lambda x: x["ops"], reverse=True
        )
        slot = 4
        for b in remaining:
            if slot < 9:
                order[slot] = b
                slot += 1

        lineup_players = [b for b in order if b is not None]

    elif analytics <= 40:
        # Traditional approach: speed at top, best hitter 3rd, power 4th
        order = [None] * 9
        used = set()

        # Leadoff: speed + contact
        speed_contact = sorted(
            lineup_players,
            key=lambda x: x["speed"] * 0.6 + x["contact"] * 0.4, reverse=True
        )
        order[0] = speed_contact[0]
        used.add(speed_contact[0]["id"])

        # 2nd: contact + speed (less speed emphasis)
        for b in sorted(lineup_players, key=lambda x: x["contact"] * 0.6 + x["speed"] * 0.4, reverse=True):
            if b["id"] not in used:
                order[1] = b
                used.add(b["id"])
                break

        # 3rd: best overall hitter (highest avg/contact)
        for b in sorted(lineup_players, key=lambda x: x["contact"], reverse=True):
            if b["id"] not in used:
                order[2] = b
                used.add(b["id"])
                break

        # 4th: most power
        for b in sorted(lineup_players, key=lambda x: x["power"], reverse=True):
            if b["id"] not in used:
                order[3] = b
                used.add(b["id"])
                break

        # 5th: next best power
        for b in sorted(lineup_players, key=lambda x: x["power"], reverse=True):
            if b["id"] not in used:
                order[4] = b
                used.add(b["id"])
                break

        # Rest by overall
        remaining = sorted(
            [b for b in lineup_players if b["id"] not in used],
            key=lambda x: x["contact"] + x["power"], reverse=True
        )
        slot = 5
        for b in remaining:
            if slot < 9:
                order[slot] = b
                slot += 1

        lineup_players = [b for b in order if b is not None]

    else:
        # Moderate: sort by OPS with slight speed boost at top
        lineup_players.sort(key=lambda x: x["ops"], reverse=True)

    # High aggressiveness: bump fast players up in the order
    if aggression >= 65:
        for i in range(1, len(lineup_players)):
            if lineup_players[i]["speed"] >= 65 and i > 1:
                # Swap fast player closer to top
                target = max(0, i - 2)
                lineup_players.insert(target, lineup_players.pop(i))

    # Build lineup JSON and save
    lineup_data = []
    for i, b in enumerate(lineup_players[:9]):
        pos = "DH"
        # Find the position they were assigned
        for p, assigned_b in assigned.items():
            if assigned_b["id"] == b["id"]:
                pos = p
                break
        lineup_data.append({
            "player_id": b["id"],
            "position": pos,
            "batting_order": i + 1,
        })

    conn.execute(
        "UPDATE teams SET lineup_json=? WHERE id=?",
        (json.dumps(lineup_data), team_id)
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "manager": manager["name"],
        "style": "analytics" if analytics >= 60 else "traditional" if analytics <= 40 else "balanced",
        "lineup": lineup_data,
    }


# ============================================================
# AUTO SET ROTATION
# ============================================================
def auto_set_rotation(team_id: int) -> dict:
    """
    Pitching coach sets the rotation based on their tendencies.

    - High bullpen_management: shorter starts, more bullpen usage
    - Low bullpen_management: let starters go deep
    - Organize by pitcher ratings (stuff + control + stamina)
    """
    conn = get_connection()

    # Get pitching coach
    pitching_coach = conn.execute(
        "SELECT * FROM coaching_staff WHERE team_id=? AND role='pitching_coach' AND is_available=0",
        (team_id,)
    ).fetchone()

    if not pitching_coach:
        conn.close()
        return {"success": False, "message": "No pitching coach found for team"}

    # Get starting pitchers
    starters = conn.execute("""
        SELECT * FROM players
        WHERE team_id=? AND roster_status='active' AND position='SP' AND is_injured=0
        ORDER BY stuff_rating + control_rating + stamina_rating DESC
    """, (team_id,)).fetchall()

    # Get relievers
    relievers = conn.execute("""
        SELECT * FROM players
        WHERE team_id=? AND roster_status='active' AND position='RP' AND is_injured=0
        ORDER BY stuff_rating + control_rating DESC
    """, (team_id,)).fetchall()

    bullpen_mgmt = pitching_coach["bullpen_management"]

    # Build rotation: top 5 starters by composite rating
    rotation = []
    for i, sp in enumerate(starters[:5]):
        composite = sp["stuff_rating"] + sp["control_rating"] + sp["stamina_rating"]
        rotation.append({
            "player_id": sp["id"],
            "name": f"{sp['first_name']} {sp['last_name']}",
            "rotation_spot": i + 1,
            "composite": composite,
        })

    # Set pitch count preferences based on bullpen_management
    if bullpen_mgmt >= 70:
        pitch_count_target = 85  # Quick hook
        style = "quick_hook"
    elif bullpen_mgmt <= 30:
        pitch_count_target = 110  # Let them work deep
        style = "deep_starters"
    else:
        pitch_count_target = 95
        style = "balanced"

    # Build bullpen roles
    bullpen = []
    for i, rp in enumerate(relievers):
        composite = rp["stuff_rating"] + rp["control_rating"]
        role = "middle_relief"
        if i == 0:
            role = "closer"
        elif i <= 2:
            role = "setup"
        elif composite >= 110:
            role = "high_leverage"
        bullpen.append({
            "player_id": rp["id"],
            "name": f"{rp['first_name']} {rp['last_name']}",
            "role": role,
            "composite": composite,
        })

    # Save rotation to team
    rotation_data = {
        "starters": [{"player_id": r["player_id"], "spot": r["rotation_spot"]} for r in rotation],
        "bullpen": [{"player_id": b["player_id"], "role": b["role"]} for b in bullpen],
        "pitch_count_target": pitch_count_target,
        "style": style,
    }

    conn.execute(
        "UPDATE teams SET rotation_json=? WHERE id=?",
        (json.dumps(rotation_data), team_id)
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "coach": pitching_coach["name"],
        "style": style,
        "pitch_count_target": pitch_count_target,
        "rotation": rotation,
        "bullpen": bullpen,
    }


# ============================================================
# COACH IMPACT ON DEVELOPMENT
# ============================================================
def coach_impact_on_development(team_id: int) -> dict:
    """
    During player development phase, coaches affect growth rates.

    - hitting_coach.hitter_development adds bonus to batter rating growth
    - pitching_coach.pitcher_development adds bonus to pitcher growth
    - player_relations affects morale
    """
    conn = get_connection()

    hitting_coach = conn.execute(
        "SELECT * FROM coaching_staff WHERE team_id=? AND role='hitting_coach' AND is_available=0",
        (team_id,)
    ).fetchone()

    pitching_coach = conn.execute(
        "SELECT * FROM coaching_staff WHERE team_id=? AND role='pitching_coach' AND is_available=0",
        (team_id,)
    ).fetchone()

    manager = conn.execute(
        "SELECT * FROM coaching_staff WHERE team_id=? AND role='manager' AND is_available=0",
        (team_id,)
    ).fetchone()

    changes = []

    # Hitting coach impact on batters
    if hitting_coach:
        hitter_dev = hitting_coach["hitter_development"]
        # Bonus: (skill - 50) / 200 -> range of -0.15 to +0.20
        dev_bonus = (hitter_dev - 50) / 200.0

        batters = conn.execute("""
            SELECT id, contact_rating, contact_potential, power_rating, power_potential,
                   eye_rating, eye_potential, age, peak_age, development_rate
            FROM players
            WHERE team_id=? AND roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')
                AND position NOT IN ('SP', 'RP')
        """, (team_id,)).fetchall()

        for b in batters:
            # Only develop players below peak who haven't hit ceiling
            if b["age"] <= b["peak_age"]:
                base_rate = b["development_rate"]
                boosted_rate = base_rate + dev_bonus

                for rating_col, potential_col in [
                    ("contact_rating", "contact_potential"),
                    ("power_rating", "power_potential"),
                    ("eye_rating", "eye_potential"),
                ]:
                    current = b[rating_col]
                    ceiling = b[potential_col]
                    if current < ceiling:
                        growth = max(0, int(boosted_rate * random.uniform(0.5, 2.0)))
                        new_val = min(ceiling, current + growth)
                        if new_val != current:
                            conn.execute(
                                f"UPDATE players SET {rating_col}=? WHERE id=?",
                                (new_val, b["id"])
                            )
                            changes.append(f"Batter {b['id']}: {rating_col} {current}->{new_val}")

    # Pitching coach impact on pitchers
    if pitching_coach:
        pitcher_dev = pitching_coach["pitcher_development"]
        dev_bonus = (pitcher_dev - 50) / 200.0

        pitchers = conn.execute("""
            SELECT id, stuff_rating, stuff_potential, control_rating, control_potential,
                   stamina_rating, stamina_potential, age, peak_age, development_rate
            FROM players
            WHERE team_id=? AND roster_status IN ('active', 'minors_aaa', 'minors_aa', 'minors_low')
                AND position IN ('SP', 'RP')
        """, (team_id,)).fetchall()

        for p in pitchers:
            if p["age"] <= p["peak_age"]:
                base_rate = p["development_rate"]
                boosted_rate = base_rate + dev_bonus

                for rating_col, potential_col in [
                    ("stuff_rating", "stuff_potential"),
                    ("control_rating", "control_potential"),
                    ("stamina_rating", "stamina_potential"),
                ]:
                    current = p[rating_col]
                    ceiling = p[potential_col]
                    if current < ceiling:
                        growth = max(0, int(boosted_rate * random.uniform(0.5, 2.0)))
                        new_val = min(ceiling, current + growth)
                        if new_val != current:
                            conn.execute(
                                f"UPDATE players SET {rating_col}=? WHERE id=?",
                                (new_val, p["id"])
                            )
                            changes.append(f"Pitcher {p['id']}: {rating_col} {current}->{new_val}")

    # Manager's player_relations affects morale
    if manager:
        relations = manager["player_relations"]
        # High relations = morale boost, low = morale drain
        morale_shift = int((relations - 50) / 10)  # -5 to +5 range

        if morale_shift != 0:
            conn.execute("""
                UPDATE players SET morale = MIN(100, MAX(0, morale + ?))
                WHERE team_id=? AND roster_status='active'
            """, (morale_shift, team_id))
            changes.append(f"Morale shift: {morale_shift:+d} (manager relations: {relations})")

    conn.commit()
    conn.close()

    return {
        "success": True,
        "team_id": team_id,
        "changes": changes,
        "hitting_coach": hitting_coach["name"] if hitting_coach else None,
        "pitching_coach": pitching_coach["name"] if pitching_coach else None,
    }


# ============================================================
# HIRE / FIRE / LIST
# ============================================================
def hire_coach(team_id: int, coach_id: int, role: str) -> dict:
    """
    Hire a free agent coach for a specific role.
    If the team already has a coach in that role, they must be fired first.
    """
    conn = get_connection()

    # Check if coach exists and is available
    coach = conn.execute(
        "SELECT * FROM coaching_staff WHERE id=? AND is_available=1",
        (coach_id,)
    ).fetchone()

    if not coach:
        conn.close()
        return {"success": False, "message": "Coach not found or not available"}

    # Check if team already has a coach in this role
    existing = conn.execute(
        "SELECT * FROM coaching_staff WHERE team_id=? AND role=? AND is_available=0",
        (team_id, role)
    ).fetchone()

    if existing:
        conn.close()
        return {
            "success": False,
            "message": f"Team already has a {role.replace('_', ' ')}: {existing['name']}. Fire them first."
        }

    # Hire the coach
    conn.execute(
        "UPDATE coaching_staff SET team_id=?, role=?, is_available=0 WHERE id=?",
        (team_id, role, coach_id)
    )

    # Log as a transaction
    game_date = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    if game_date:
        conn.execute("""
            INSERT INTO transactions (transaction_date, transaction_type, details_json, team1_id)
            VALUES (?, 'coach_hire', ?, ?)
        """, (
            game_date[0],
            json.dumps({"coach_id": coach_id, "name": coach["name"], "role": role}),
            team_id,
        ))

    # Send a message
    team = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()
    if team and game_date:
        conn.execute("""
            INSERT INTO messages (game_date, sender_type, sender_name, recipient_type, subject, body, is_read)
            VALUES (?, 'system', 'Front Office', 'user', ?, ?, 0)
        """, (
            game_date[0],
            f"New {role.replace('_', ' ').title()} Hired",
            f"The {team['city']} {team['name']} have hired {coach['name']} as their new {role.replace('_', ' ')}. "
            f"\"{coach['catchphrase']}\" - {coach['name']}",
        ))

    conn.commit()
    conn.close()

    return {"success": True, "message": f"Hired {coach['name']} as {role.replace('_', ' ')}"}


def fire_coach(coach_id: int) -> dict:
    """Fire a coach. They become available for hire by other teams."""
    conn = get_connection()

    coach = conn.execute(
        "SELECT * FROM coaching_staff WHERE id=? AND is_available=0",
        (coach_id,)
    ).fetchone()

    if not coach:
        conn.close()
        return {"success": False, "message": "Coach not found or already a free agent"}

    team_id = coach["team_id"]
    team = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()

    # Make available
    conn.execute(
        "UPDATE coaching_staff SET team_id=0, is_available=1 WHERE id=?",
        (coach_id,)
    )

    # Log transaction
    game_date = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    if game_date:
        conn.execute("""
            INSERT INTO transactions (transaction_date, transaction_type, details_json, team1_id)
            VALUES (?, 'coach_fire', ?, ?)
        """, (
            game_date[0],
            json.dumps({"coach_id": coach_id, "name": coach["name"], "role": coach["role"]}),
            team_id,
        ))

        # Send message
        if team:
            conn.execute("""
                INSERT INTO messages (game_date, sender_type, sender_name, recipient_type, subject, body, is_read)
                VALUES (?, 'system', 'Front Office', 'user', ?, ?, 0)
            """, (
                game_date[0],
                f"{coach['role'].replace('_', ' ').title()} Fired",
                f"The {team['city']} {team['name']} have relieved {coach['name']} of their duties as {coach['role'].replace('_', ' ')}.",
            ))

    conn.commit()
    conn.close()

    return {"success": True, "message": f"Fired {coach['name']}"}


def get_available_coaches(role: Optional[str] = None) -> list:
    """Get all coaches available for hire, optionally filtered by role."""
    if role:
        coaches = query(
            "SELECT * FROM coaching_staff WHERE is_available=1 AND role=? ORDER BY reputation DESC",
            (role,)
        )
    else:
        coaches = query(
            "SELECT * FROM coaching_staff WHERE is_available=1 ORDER BY role, reputation DESC"
        )
    return [dict(c) for c in coaches]


def get_team_coaching_staff(team_id: int) -> list:
    """Get all coaches for a specific team."""
    coaches = query(
        "SELECT * FROM coaching_staff WHERE team_id=? AND is_available=0 ORDER BY role",
        (team_id,)
    )
    return [dict(c) for c in coaches]


# ============================================================
# COACHING CAREER PROGRESSION & POACHING
# ============================================================

# Career ladder for front office/coaching roles
CAREER_LADDER = {
    "first_base_coach": ["third_base_coach", "bench_coach"],
    "third_base_coach": ["bench_coach", "farm_director"],
    "bench_coach": ["manager", "farm_director"],
    "bullpen_coach": ["pitching_coach"],
    "hitting_coach": ["bench_coach", "farm_director", "assistant_gm"],
    "pitching_coach": ["bench_coach", "farm_director", "assistant_gm"],
    "farm_director": ["assistant_gm"],
    "assistant_gm": ["manager"],  # Can become GM elsewhere (flavor only)
    "manager": [],
}

ROLE_DISPLAY = {
    "manager": "Manager",
    "hitting_coach": "Hitting Coach",
    "pitching_coach": "Pitching Coach",
    "bench_coach": "Bench Coach",
    "bullpen_coach": "Bullpen Coach",
    "first_base_coach": "1B Coach",
    "third_base_coach": "3B Coach",
    "farm_director": "Farm Director",
    "assistant_gm": "Assistant GM",
    "development_coordinator": "Dev Coordinator",
}


def process_coaching_contracts(game_date: str, db_path=None) -> list:
    """Process coaching contracts at end of season. Expire, poach, promote.

    Called during offseason processing.
    Returns list of events.
    """
    events = []

    # Ensure memory_log column exists
    try:
        execute("ALTER TABLE coaching_staff ADD COLUMN memory_log TEXT DEFAULT '[]'",
                db_path=db_path)
    except Exception:
        pass

    # Decrement contract years
    execute("UPDATE coaching_staff SET years_remaining = years_remaining - 1 "
            "WHERE is_available = 0 AND years_remaining > 0", db_path=db_path)

    # Free coaches whose contracts expired
    expired = query(
        "SELECT * FROM coaching_staff WHERE is_available=0 AND years_remaining <= 0",
        db_path=db_path
    )
    for c in expired:
        execute("UPDATE coaching_staff SET is_available=1, team_id=0 WHERE id=?",
                (c["id"],), db_path=db_path)
        events.append({
            "type": "contract_expired",
            "name": c["name"],
            "role": c["role"],
            "team_id": c["team_id"],
        })

    # Poaching: successful coaches with high reputation get offers from other teams
    poach_candidates = query("""
        SELECT * FROM coaching_staff
        WHERE is_available=0 AND reputation >= 70 AND years_remaining <= 1
        ORDER BY reputation DESC
    """, db_path=db_path)

    for candidate in poach_candidates:
        if random.random() > 0.15:  # 15% chance per high-rep coach
            continue

        # Find a team that needs this role's next step
        next_roles = CAREER_LADDER.get(candidate["role"], [])
        if not next_roles:
            continue

        target_role = random.choice(next_roles)

        # Find a team missing this role (or with a weak coach)
        teams_needing = query("""
            SELECT t.id, t.city, t.name FROM teams t
            WHERE t.id != ?
            AND NOT EXISTS (
                SELECT 1 FROM coaching_staff cs
                WHERE cs.team_id = t.id AND cs.role = ? AND cs.is_available = 0
            )
            ORDER BY RANDOM() LIMIT 1
        """, (candidate["team_id"], target_role), db_path=db_path)

        if teams_needing:
            new_team = teams_needing[0]
            old_team_id = candidate["team_id"]

            # Promote and move
            new_salary = int(candidate["annual_salary"] * random.uniform(1.3, 1.8))
            new_salary = (new_salary // 50000) * 50000
            execute("""
                UPDATE coaching_staff SET team_id=?, role=?, annual_salary=?,
                    years_remaining=? WHERE id=?
            """, (new_team["id"], target_role, new_salary,
                  random.randint(2, 4), candidate["id"]), db_path=db_path)

            events.append({
                "type": "poached",
                "name": candidate["name"],
                "old_role": candidate["role"],
                "new_role": target_role,
                "old_team_id": old_team_id,
                "new_team_id": new_team["id"],
                "new_team_name": f"{new_team['city']} {new_team['name']}",
            })

            # Log memory
            _add_coaching_memory(
                candidate["id"],
                f"Promoted to {ROLE_DISPLAY.get(target_role, target_role)} "
                f"with {new_team['city']} {new_team['name']}",
                db_path
            )

    return events


def send_coaching_departure_messages(team_id: int, game_date: str,
                                      events: list, db_path=None):
    """Notify the user when their coaches depart."""
    for ev in events:
        if ev.get("old_team_id") == team_id or ev.get("team_id") == team_id:
            if ev["type"] == "poached":
                body = (
                    f"{ev['name']} has been hired away by the "
                    f"{ev['new_team_name']} as their "
                    f"{ROLE_DISPLAY.get(ev['new_role'], ev['new_role'])}. "
                    f"His strong reputation made him an attractive target. "
                    f"You'll need to find a replacement."
                )
                execute("""
                    INSERT INTO messages (game_date, sender_type, sender_name,
                        recipient_type, recipient_id, subject, body, is_read)
                    VALUES (?, 'system', 'Front Office', 'user', ?, ?, ?, 0)
                """, (game_date, team_id,
                      f"Staff Departure: {ev['name']}",
                      body), db_path=db_path)
            elif ev["type"] == "contract_expired":
                execute("""
                    INSERT INTO messages (game_date, sender_type, sender_name,
                        recipient_type, recipient_id, subject, body, is_read)
                    VALUES (?, 'system', 'Front Office', 'user', ?, ?, ?, 0)
                """, (game_date, team_id,
                      f"Contract Expired: {ev['name']}",
                      f"{ev['name']}'s contract as "
                      f"{ROLE_DISPLAY.get(ev['role'], ev['role'])} has expired. "
                      f"He's now a free agent. You can re-sign him or hire a replacement."),
                    db_path=db_path)


def _add_coaching_memory(coach_id: int, memory: str, db_path=None):
    """Add a memory entry to a coach's memory log."""
    rows = query("SELECT memory_log FROM coaching_staff WHERE id=?",
                 (coach_id,), db_path=db_path)
    if not rows:
        return
    try:
        log = json.loads(rows[0].get("memory_log") or "[]")
    except (json.JSONDecodeError, TypeError):
        log = []
    log.append(memory)
    if len(log) > 20:
        log = log[-20:]
    execute("UPDATE coaching_staff SET memory_log=? WHERE id=?",
            (json.dumps(log), coach_id), db_path=db_path)
