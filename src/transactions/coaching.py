"""
Front Office - Coaching Staff Management
Hire/fire coaches that affect player development, game strategy, and team performance.
"""
import random
from ..database.db import execute, query

COACHING_ROLES = [
    "manager", "hitting_coach", "pitching_coach", "bench_coach",
    "bullpen_coach", "first_base_coach", "third_base_coach", "development_coordinator"
]

FIRST_NAMES = ["Mike", "Tony", "Dave", "Joe", "John", "Mark", "Bob", "Jim", "Tom", "Steve",
               "Pat", "Rick", "Don", "Bill", "Gary", "Bruce", "Ron", "Dan", "Phil", "Ed",
               "Carlos", "Luis", "Pedro", "Ramon", "Ozzie", "Buck", "Dusty", "Terry", "Bobby", "Lou"]
LAST_NAMES = ["Johnson", "Williams", "Martinez", "Garcia", "Anderson", "Wilson", "Baker",
              "Thompson", "Walker", "Robinson", "Mitchell", "Howard", "Young", "Lewis", "Turner",
              "Collins", "Morgan", "Murphy", "Rivera", "Gonzalez", "Ramirez", "Torres", "Cruz", "Ortiz"]

def generate_coach(role: str, quality: str = "average") -> dict:
    """Generate a random coaching staff member."""
    quality_ranges = {
        "elite": (75, 95),
        "good": (60, 80),
        "average": (40, 65),
        "poor": (25, 45),
    }
    low, high = quality_ranges.get(quality, (40, 65))

    return {
        "first_name": random.choice(FIRST_NAMES),
        "last_name": random.choice(LAST_NAMES),
        "role": role,
        "age": random.randint(38, 72),
        "experience": random.randint(1, 30),
        "skill_rating": random.randint(low, high),
        "philosophy": random.choice(["aggressive", "balanced", "conservative", "analytics"]),
        "specialty": random.choice([None, "player_development", "game_strategy", "pitching_mechanics", "hitting_approach"]),
        "salary": random.randint(500000, 3000000),
        "contract_years": random.randint(1, 4),
    }

def seed_coaching_staff(db_path: str = None):
    """Seed all 30 teams with coaching staffs."""
    teams = query("SELECT id FROM teams", db_path=db_path)
    for team in teams:
        existing = query("SELECT COUNT(*) as cnt FROM coaching_staff WHERE team_id=?",
                        (team["id"],), db_path=db_path)
        if existing and existing[0]["cnt"] > 0:
            continue
        for role in COACHING_ROLES:
            coach = generate_coach(role)
            execute("""
                INSERT INTO coaching_staff (team_id, role, first_name, last_name, age, experience,
                    skill_rating, philosophy, specialty, salary, contract_years, is_available)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (team["id"], coach["role"], coach["first_name"], coach["last_name"],
                  coach["age"], coach["experience"], coach["skill_rating"],
                  coach["philosophy"], coach["specialty"], coach["salary"],
                  coach["contract_years"]), db_path=db_path)

    # Generate 20 available free agent coaches
    for _ in range(20):
        role = random.choice(COACHING_ROLES)
        coach = generate_coach(role)
        execute("""
            INSERT INTO coaching_staff (team_id, role, first_name, last_name, age, experience,
                skill_rating, philosophy, specialty, salary, contract_years, is_available)
            VALUES (0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (coach["role"], coach["first_name"], coach["last_name"],
              coach["age"], coach["experience"], coach["skill_rating"],
              coach["philosophy"], coach["specialty"], coach["salary"],
              coach["contract_years"]), db_path=db_path)

def get_coaching_staff(team_id: int, db_path: str = None) -> list:
    """Get all coaches for a team."""
    return query("""
        SELECT * FROM coaching_staff WHERE team_id=? AND is_available=0
        ORDER BY CASE role
            WHEN 'manager' THEN 1 WHEN 'hitting_coach' THEN 2
            WHEN 'pitching_coach' THEN 3 WHEN 'bench_coach' THEN 4
            ELSE 5 END
    """, (team_id,), db_path=db_path)

def get_available_coaches(role: str = None, db_path: str = None) -> list:
    """Get available free agent coaches."""
    if role:
        return query("SELECT * FROM coaching_staff WHERE is_available=1 AND role=? ORDER BY skill_rating DESC",
                     (role,), db_path=db_path)
    return query("SELECT * FROM coaching_staff WHERE is_available=1 ORDER BY skill_rating DESC", db_path=db_path)

def hire_coach(team_id: int, coach_id: int, db_path: str = None) -> dict:
    """Hire a free agent coach."""
    coach = query("SELECT * FROM coaching_staff WHERE id=? AND is_available=1", (coach_id,), db_path=db_path)
    if not coach:
        return {"error": "Coach not available"}

    # Check if team already has someone in that role
    existing = query("SELECT * FROM coaching_staff WHERE team_id=? AND role=? AND is_available=0",
                    (team_id, coach[0]["role"]), db_path=db_path)
    if existing:
        # Fire existing coach first
        fire_coach(team_id, existing[0]["id"], db_path=db_path)

    execute("UPDATE coaching_staff SET team_id=?, is_available=0 WHERE id=?", (team_id, coach_id), db_path=db_path)
    return {"success": True, "coach": coach[0]}

def fire_coach(team_id: int, coach_id: int, db_path: str = None) -> dict:
    """Fire a coach (makes them available)."""
    execute("UPDATE coaching_staff SET team_id=0, is_available=1 WHERE id=? AND team_id=?",
            (coach_id, team_id), db_path=db_path)
    return {"success": True}

def get_coaching_impact(team_id: int, db_path: str = None) -> dict:
    """Calculate coaching staff impact on team performance."""
    staff = get_coaching_staff(team_id, db_path=db_path)
    if not staff:
        return {"hitting_bonus": 0, "pitching_bonus": 0, "development_bonus": 0, "strategy_bonus": 0}

    hitting_bonus = 0
    pitching_bonus = 0
    dev_bonus = 0
    strategy_bonus = 0

    for coach in staff:
        skill = coach["skill_rating"]
        bonus = (skill - 50) / 50  # -1 to +0.9 range

        if coach["role"] == "manager":
            strategy_bonus += bonus * 3
            dev_bonus += bonus
        elif coach["role"] == "hitting_coach":
            hitting_bonus += bonus * 4
        elif coach["role"] == "pitching_coach":
            pitching_bonus += bonus * 4
        elif coach["role"] == "development_coordinator":
            dev_bonus += bonus * 4
        elif coach["role"] == "bench_coach":
            strategy_bonus += bonus * 2
        elif coach["role"] == "bullpen_coach":
            pitching_bonus += bonus * 2

    return {
        "hitting_bonus": round(hitting_bonus, 1),
        "pitching_bonus": round(pitching_bonus, 1),
        "development_bonus": round(dev_bonus, 1),
        "strategy_bonus": round(strategy_bonus, 1),
    }
