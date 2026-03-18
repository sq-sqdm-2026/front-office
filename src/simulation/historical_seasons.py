"""
Front Office - Historical Seasons
Play through different baseball eras with era-appropriate rules,
player generation, and game parameter adjustments.

Inspired by Baseball Mogul's historical season mode.
"""
import random
from ..database.db import execute, query, get_connection

# ============================================================
# ERA DEFINITIONS
# ============================================================
ERAS = {
    "modern": {
        "name": "Modern Era",
        "years": "2020-2026",
        "start_year": 2020,
        "end_year": 2026,
        "description": (
            "The current era of baseball. Universal DH, pitch clocks, "
            "shift restrictions, and analytics-driven front offices. "
            "The game is faster but home runs still reign."
        ),
        "flavor": "Three true outcomes meet pace-of-play reforms.",
        "default": True,
    },
    "steroid": {
        "name": "Steroid Era",
        "years": "1995-2005",
        "start_year": 1995,
        "end_year": 2005,
        "description": (
            "The era of inflated power numbers. Home run records fell, "
            "offensive output soared, and pitchers struggled to keep up. "
            "Ballparks were smaller, muscles were bigger."
        ),
        "flavor": "Chicks dig the long ball.",
    },
    "dead_ball": {
        "name": "Dead Ball Era",
        "years": "1900-1919",
        "start_year": 1900,
        "end_year": 1919,
        "description": (
            "Low-scoring games dominated by pitching and small ball. "
            "The baseball itself was softer, reused until discolored, "
            "and home runs were rare. Stolen bases and bunts won games."
        ),
        "flavor": "Inside baseball at its finest.",
    },
    "golden_age": {
        "name": "Golden Age",
        "years": "1950-1969",
        "start_year": 1950,
        "end_year": 1969,
        "description": (
            "The integration era. Jackie Robinson broke the barrier in 1947, "
            "and by the 1950s the game's greatest talents came from all "
            "backgrounds. Iconic franchises, legendary players, day games."
        ),
        "flavor": "Say Hey, the Mick, and Hammerin' Hank.",
    },
    "free_agency": {
        "name": "Free Agency Dawn",
        "years": "1975-1990",
        "start_year": 1975,
        "end_year": 1990,
        "description": (
            "The reserve clause is dead. Players can sell their services "
            "to the highest bidder. Salaries explode, dynasties shift, "
            "and the business of baseball changes forever."
        ),
        "flavor": "The players finally get paid.",
    },
}

# ============================================================
# ERA MODIFIERS - adjustments to game simulation parameters
# ============================================================
ERA_MODIFIERS = {
    "modern": {
        "power_modifier": 1.0,
        "contact_modifier": 1.0,
        "speed_modifier": 0.95,
        "pitch_speed_modifier": 1.0,
        "strikeout_modifier": 1.15,
        "walk_modifier": 1.0,
        "hr_modifier": 1.05,
        "salary_scale": 1.0,
        "stadium_dimension_modifier": 1.0,
        "num_teams": 30,
        "roster_size": 26,
        "min_salary": 720000,
        "avg_star_salary": 25000000,
    },
    "steroid": {
        "power_modifier": 1.30,
        "contact_modifier": 1.05,
        "speed_modifier": 1.0,
        "pitch_speed_modifier": 0.95,
        "strikeout_modifier": 1.0,
        "walk_modifier": 1.05,
        "hr_modifier": 1.40,
        "salary_scale": 0.45,
        "stadium_dimension_modifier": 0.97,
        "num_teams": 30,
        "roster_size": 25,
        "min_salary": 200000,
        "avg_star_salary": 12000000,
    },
    "dead_ball": {
        "power_modifier": 0.50,
        "contact_modifier": 1.10,
        "speed_modifier": 1.20,
        "pitch_speed_modifier": 0.75,
        "strikeout_modifier": 0.70,
        "walk_modifier": 0.85,
        "hr_modifier": 0.20,
        "salary_scale": 0.002,
        "stadium_dimension_modifier": 1.10,
        "num_teams": 16,
        "roster_size": 25,
        "min_salary": 1500,
        "avg_star_salary": 10000,
    },
    "golden_age": {
        "power_modifier": 1.05,
        "contact_modifier": 1.10,
        "speed_modifier": 1.10,
        "pitch_speed_modifier": 0.85,
        "strikeout_modifier": 0.85,
        "walk_modifier": 1.0,
        "hr_modifier": 1.0,
        "salary_scale": 0.01,
        "stadium_dimension_modifier": 1.03,
        "num_teams": 20,
        "roster_size": 25,
        "min_salary": 6000,
        "avg_star_salary": 100000,
    },
    "free_agency": {
        "power_modifier": 1.05,
        "contact_modifier": 1.05,
        "speed_modifier": 1.10,
        "pitch_speed_modifier": 0.90,
        "strikeout_modifier": 0.90,
        "walk_modifier": 1.0,
        "hr_modifier": 1.05,
        "salary_scale": 0.15,
        "stadium_dimension_modifier": 1.0,
        "num_teams": 26,
        "roster_size": 25,
        "min_salary": 40000,
        "avg_star_salary": 2000000,
    },
}

# ============================================================
# ERA-SPECIFIC RULES
# ============================================================
ERA_RULES = {
    "modern": {
        "dh_rule": "universal",
        "roster_size": 26,
        "has_draft": True,
        "draft_rounds": 20,
        "has_free_agency": True,
        "has_arbitration": True,
        "has_luxury_tax": True,
        "has_revenue_sharing": True,
        "has_pitch_clock": True,
        "has_shift_restrictions": True,
        "has_replay": True,
        "has_wild_card": True,
        "wild_card_teams": 3,
        "playoff_teams": 12,
        "schedule_games": 162,
        "notes": [
            "Universal DH in both leagues.",
            "26-man rosters with 13-pitcher limit.",
            "Pitch clock enforced.",
            "Defensive shift restrictions in effect.",
        ],
    },
    "steroid": {
        "dh_rule": "al_only",
        "roster_size": 25,
        "has_draft": True,
        "draft_rounds": 50,
        "has_free_agency": True,
        "has_arbitration": True,
        "has_luxury_tax": True,
        "has_revenue_sharing": True,
        "has_pitch_clock": False,
        "has_shift_restrictions": False,
        "has_replay": False,
        "has_wild_card": True,
        "wild_card_teams": 1,
        "playoff_teams": 8,
        "schedule_games": 162,
        "notes": [
            "DH in American League only.",
            "No pitch clock or shift restrictions.",
            "Single wild card per league.",
            "Performance-enhancing substances are widespread.",
            "Smaller ballparks and juiced baseballs.",
        ],
    },
    "dead_ball": {
        "dh_rule": "none",
        "roster_size": 25,
        "has_draft": False,
        "draft_rounds": 0,
        "has_free_agency": False,
        "has_arbitration": False,
        "has_luxury_tax": False,
        "has_revenue_sharing": False,
        "has_pitch_clock": False,
        "has_shift_restrictions": False,
        "has_replay": False,
        "has_wild_card": False,
        "wild_card_teams": 0,
        "playoff_teams": 2,
        "schedule_games": 154,
        "notes": [
            "No DH in either league.",
            "No amateur draft; teams sign players directly.",
            "Reserve clause binds players to teams for life.",
            "Only the pennant winners meet in the World Series.",
            "The ball is dead. Home runs are a rarity.",
            "Pitchers routinely throw complete games.",
        ],
    },
    "golden_age": {
        "dh_rule": "none",
        "roster_size": 25,
        "has_draft": False,
        "draft_rounds": 0,
        "has_free_agency": False,
        "has_arbitration": False,
        "has_luxury_tax": False,
        "has_revenue_sharing": False,
        "has_pitch_clock": False,
        "has_shift_restrictions": False,
        "has_replay": False,
        "has_wild_card": False,
        "wild_card_teams": 0,
        "playoff_teams": 2,
        "schedule_games": 154,
        "notes": [
            "No DH. Pitchers bat.",
            "No amateur draft until 1965.",
            "Reserve clause still in effect.",
            "Only pennant winners play in the World Series.",
            "Integration transforms the talent pool.",
            "Day games are the norm. Night baseball is still novel.",
        ],
    },
    "free_agency": {
        "dh_rule": "al_only",
        "roster_size": 25,
        "has_draft": True,
        "draft_rounds": 60,
        "has_free_agency": True,
        "has_arbitration": True,
        "has_luxury_tax": False,
        "has_revenue_sharing": False,
        "has_pitch_clock": False,
        "has_shift_restrictions": False,
        "has_replay": False,
        "has_wild_card": False,
        "wild_card_teams": 0,
        "playoff_teams": 4,
        "schedule_games": 162,
        "notes": [
            "DH in American League only.",
            "Free agency after 6 years of service.",
            "Salary arbitration available.",
            "No luxury tax or revenue sharing.",
            "LCS and World Series only. No wild card.",
            "Drug testing is nonexistent.",
        ],
    },
}

# ============================================================
# ERA-APPROPRIATE NAMES
# ============================================================
ERA_FIRST_NAMES = {
    "modern": [
        "Bryce", "Mookie", "Shohei", "Ronald", "Juan", "Trea", "Wander",
        "Julio", "Gunnar", "Adley", "Corbin", "Spencer", "Jazz", "Elly",
        "Bobby", "Marcell", "Yordan", "Kyle", "Shane", "Gerrit", "Zack",
        "Tyler", "Dylan", "Cody", "Gavin", "Royce", "Jackson", "Colton",
        "Bryson", "Wyatt",
    ],
    "steroid": [
        "Barry", "Mark", "Sammy", "Roger", "Alex", "Manny", "Jeff",
        "Ken", "Jason", "Derek", "Gary", "Mike", "Pedro", "Greg",
        "Ivan", "Troy", "Jim", "Larry", "Rafael", "Albert", "Carlos",
        "Todd", "Scott", "Eric", "Mo", "Nomar", "Andruw", "Chipper",
        "Edgar", "David",
    ],
    "dead_ball": [
        "Walter", "Christy", "Ty", "Honus", "Napoleon", "Mordecai",
        "Eddie", "Tris", "Frank", "Sam", "Johnny", "Addie", "Rube",
        "Joe", "Ed", "Harry", "George", "Fred", "Bill", "Hugh",
        "Nap", "Buck", "Cy", "Zack", "Ray", "Chief", "Home Run",
        "Shoeless", "Hal", "Art",
    ],
    "golden_age": [
        "Mickey", "Willie", "Hank", "Ted", "Sandy", "Roberto", "Duke",
        "Warren", "Whitey", "Ernie", "Don", "Al", "Roy", "Bob",
        "Harvey", "Billy", "Gil", "Roger", "Richie", "Maury",
        "Juan", "Jim", "Brooks", "Frank", "Lou", "Harmon", "Orlando",
        "Tony", "Carl", "Elston",
    ],
    "free_agency": [
        "Reggie", "Nolan", "Steve", "Dave", "George", "Ozzie", "Cal",
        "Ryne", "Wade", "Kirby", "Rickey", "Tony", "Don", "Jack",
        "Dwight", "Darryl", "Dale", "Robin", "Andre", "Tim", "Mike",
        "Keith", "Gary", "Eddie", "Fernando", "Orel", "Dennis",
        "Kirk", "Paul", "Jose",
    ],
}

ERA_LAST_NAMES = {
    "modern": [
        "Ohtani", "Betts", "Soto", "Acuna", "Harper", "Turner", "Franco",
        "Henderson", "Carroll", "Witt", "Rutschman", "Burns", "Chisholm",
        "De La Cruz", "Skenes", "Webb", "Cole", "Tucker", "Alvarez",
        "Devers", "Vlad", "Stott", "Bohm", "Riley", "Harris",
        "Seager", "Semien", "Ramirez", "Guerrero", "Rodriguez",
    ],
    "steroid": [
        "Bonds", "McGwire", "Sosa", "Clemens", "Rodriguez", "Ramirez",
        "Bagwell", "Griffey", "Giambi", "Jeter", "Sheffield", "Piazza",
        "Martinez", "Maddux", "Pujols", "Thome", "Helton", "Walker",
        "Guerrero", "Edmonds", "Berkman", "Kent", "Jones", "Schilling",
        "Rivera", "Garciaparra", "Posada", "Delgado", "Beltran", "Ortiz",
    ],
    "dead_ball": [
        "Johnson", "Mathewson", "Cobb", "Wagner", "Lajoie", "Brown",
        "Collins", "Speaker", "Chance", "Crawford", "Evers", "Joss",
        "Waddell", "Jackson", "Walsh", "Hooper", "Doyle", "Clarke",
        "Baker", "Wheat", "Chase", "Young", "Plank", "McGinnity",
        "Bender", "Tinker", "Sheckard", "Dahlen", "Leach", "Seymour",
    ],
    "golden_age": [
        "Mantle", "Mays", "Aaron", "Williams", "Koufax", "Clemente",
        "Snider", "Spahn", "Ford", "Banks", "Drysdale", "Kaline",
        "Campanella", "Gibson", "Kuenn", "Hodges", "Maris", "Allen",
        "Wills", "Marichal", "Bunning", "Robinson", "Brock",
        "Killebrew", "Cepeda", "Gwynn", "Yastrzemski", "Howard",
        "Aparicio", "Colavito",
    ],
    "free_agency": [
        "Jackson", "Ryan", "Carlton", "Brett", "Smith", "Ripken",
        "Sandberg", "Boggs", "Puckett", "Henderson", "Gwynn", "Mattingly",
        "Morris", "Gooden", "Strawberry", "Murphy", "Yount", "Dawson",
        "Raines", "Molitor", "Schmidt", "Carter", "Murray", "Eckersley",
        "Valenzuela", "Hershiser", "Sutter", "Gibson", "Winfield", "Canseco",
    ],
}

# ============================================================
# ERA-SPECIFIC POSITION WEIGHTS
# Closers were rare before ~1970; relief pitching evolved over time.
# ============================================================
ERA_POSITION_WEIGHTS = {
    "modern": {
        "batting": ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"],
        "pitching": ["SP", "SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP", "RP", "RP", "RP"],
        "closer_exists": True,
    },
    "steroid": {
        "batting": ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"],
        "pitching": ["SP", "SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP", "RP", "RP", "RP"],
        "closer_exists": True,
    },
    "dead_ball": {
        "batting": ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"],
        "pitching": ["SP", "SP", "SP", "SP", "SP", "SP", "RP", "RP"],
        "closer_exists": False,
    },
    "golden_age": {
        "batting": ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"],
        "pitching": ["SP", "SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP"],
        "closer_exists": False,
    },
    "free_agency": {
        "batting": ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"],
        "pitching": ["SP", "SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP", "RP", "RP"],
        "closer_exists": True,
    },
}


# ============================================================
# PUBLIC API
# ============================================================

def get_available_eras():
    """Return list of available historical era packages for UI display."""
    result = []
    for era_key, era in ERAS.items():
        modifiers = ERA_MODIFIERS[era_key]
        rules = ERA_RULES[era_key]
        result.append({
            "id": era_key,
            "name": era["name"],
            "years": era["years"],
            "start_year": era["start_year"],
            "end_year": era["end_year"],
            "description": era["description"],
            "flavor": era["flavor"],
            "default": era.get("default", False),
            "num_teams": modifiers["num_teams"],
            "schedule_games": rules["schedule_games"],
            "dh_rule": rules["dh_rule"],
            "has_free_agency": rules["has_free_agency"],
            "has_draft": rules["has_draft"],
            "playoff_teams": rules["playoff_teams"],
            "notes": rules["notes"],
        })
    return result


def apply_era_modifiers(era, db_path=None):
    """Adjust game parameters in the database for the selected era.

    Updates game_state with era info and adjusts team/salary parameters
    to reflect the chosen historical period.
    """
    if era not in ERA_MODIFIERS:
        raise ValueError(f"Unknown era: {era}. Valid eras: {list(ERA_MODIFIERS.keys())}")

    mods = ERA_MODIFIERS[era]
    rules = ERA_RULES[era]
    era_info = ERAS[era]

    # Store era in game_state
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Add era column if it doesn't exist
    cursor.execute("PRAGMA table_info(game_state)")
    cols = {row[1] for row in cursor.fetchall()}
    if "era" not in cols:
        conn.execute("ALTER TABLE game_state ADD COLUMN era TEXT DEFAULT 'modern'")
    if "era_start_year" not in cols:
        conn.execute("ALTER TABLE game_state ADD COLUMN era_start_year INTEGER DEFAULT 2020")

    # Set the era and adjust the season year
    start_year = era_info["start_year"]
    conn.execute(
        "UPDATE game_state SET era=?, era_start_year=?, season=? WHERE id=1",
        (era, start_year, start_year)
    )

    # Adjust player ratings based on era modifiers
    power_mod = mods["power_modifier"]
    contact_mod = mods["contact_modifier"]
    speed_mod = mods["speed_modifier"]

    # Scale all player power ratings
    if power_mod != 1.0:
        conn.execute(
            "UPDATE players SET power_rating = MIN(80, MAX(20, CAST(power_rating * ? AS INTEGER)))",
            (power_mod,)
        )
        conn.execute(
            "UPDATE players SET power_potential = MIN(80, MAX(20, CAST(power_potential * ? AS INTEGER)))",
            (power_mod,)
        )

    # Scale contact ratings
    if contact_mod != 1.0:
        conn.execute(
            "UPDATE players SET contact_rating = MIN(80, MAX(20, CAST(contact_rating * ? AS INTEGER)))",
            (contact_mod,)
        )
        conn.execute(
            "UPDATE players SET contact_potential = MIN(80, MAX(20, CAST(contact_potential * ? AS INTEGER)))",
            (contact_mod,)
        )

    # Scale speed ratings
    if speed_mod != 1.0:
        conn.execute(
            "UPDATE players SET speed_rating = MIN(80, MAX(20, CAST(speed_rating * ? AS INTEGER)))",
            (speed_mod,)
        )
        conn.execute(
            "UPDATE players SET speed_potential = MIN(80, MAX(20, CAST(speed_potential * ? AS INTEGER)))",
            (speed_mod,)
        )

    # Scale pitcher stamina for dead-ball era (more complete games)
    if era in ("dead_ball", "golden_age"):
        conn.execute(
            "UPDATE players SET stamina_rating = MIN(80, stamina_rating + 15) "
            "WHERE position IN ('SP')"
        )
        conn.execute(
            "UPDATE players SET stamina_potential = MIN(80, stamina_potential + 15) "
            "WHERE position IN ('SP')"
        )

    # Scale salaries
    salary_scale = mods["salary_scale"]
    if salary_scale != 1.0:
        conn.execute(
            "UPDATE contracts SET annual_salary = MAX(?, CAST(annual_salary * ? AS INTEGER))",
            (mods["min_salary"], salary_scale)
        )

    # Adjust stadium dimensions
    dim_mod = mods["stadium_dimension_modifier"]
    if dim_mod != 1.0:
        conn.execute(
            "UPDATE teams SET lf_distance = CAST(lf_distance * ? AS INTEGER), "
            "lcf_distance = CAST(lcf_distance * ? AS INTEGER), "
            "cf_distance = CAST(cf_distance * ? AS INTEGER), "
            "rcf_distance = CAST(rcf_distance * ? AS INTEGER), "
            "rf_distance = CAST(rf_distance * ? AS INTEGER)",
            (dim_mod, dim_mod, dim_mod, dim_mod, dim_mod)
        )

    conn.commit()
    conn.close()

    return {
        "era": era,
        "name": era_info["name"],
        "modifiers_applied": mods,
        "rules": rules,
    }


def generate_era_rosters(era, db_path=None):
    """Generate era-appropriate player names for all teams.

    Replaces existing player names with era-appropriate names
    while keeping ratings intact (ratings are adjusted by apply_era_modifiers).
    """
    if era not in ERAS:
        raise ValueError(f"Unknown era: {era}. Valid eras: {list(ERAS.keys())}")

    first_names = ERA_FIRST_NAMES.get(era, ERA_FIRST_NAMES["modern"])
    last_names = ERA_LAST_NAMES.get(era, ERA_LAST_NAMES["modern"])

    conn = get_connection(db_path)
    players = conn.execute("SELECT id FROM players").fetchall()

    used_names = set()
    for player in players:
        for _ in range(100):
            first = random.choice(first_names)
            last = random.choice(last_names)
            full = f"{first} {last}"
            if full not in used_names:
                used_names.add(full)
                break
        else:
            # Fallback: append number to ensure uniqueness
            first = random.choice(first_names)
            last = random.choice(last_names) + str(random.randint(1, 99))
            used_names.add(f"{first} {last}")

        conn.execute(
            "UPDATE players SET first_name=?, last_name=? WHERE id=?",
            (first, last, player["id"])
        )

    # Adjust position distribution for the era
    pos_weights = ERA_POSITION_WEIGHTS[era]

    # Remove DH position players in eras without DH
    if "DH" not in pos_weights["batting"]:
        # Convert DH players to corner outfield or first base
        dh_players = conn.execute(
            "SELECT id FROM players WHERE position='DH'"
        ).fetchall()
        for p in dh_players:
            new_pos = random.choice(["1B", "LF", "RF"])
            conn.execute(
                "UPDATE players SET position=? WHERE id=?",
                (new_pos, p["id"])
            )

    # In eras without closers, convert RP stamina expectations
    if not pos_weights["closer_exists"]:
        # Increase RP stamina to reflect multi-inning relief roles
        conn.execute(
            "UPDATE players SET stamina_rating = MIN(80, stamina_rating + 10) "
            "WHERE position='RP'"
        )

    conn.commit()
    conn.close()

    return {
        "era": era,
        "players_updated": len(players),
        "name_pool_size": len(first_names) * len(last_names),
    }


def get_era_rules(era):
    """Return era-specific rule variations.

    Returns a dict of rules and restrictions that apply to the selected era,
    for use by the game engine and transaction systems.
    """
    if era not in ERA_RULES:
        raise ValueError(f"Unknown era: {era}. Valid eras: {list(ERA_RULES.keys())}")

    return ERA_RULES[era]


def start_historical_game(era, team_id=None, db_path=None):
    """Initialize a new game in a historical era.

    This is the main entry point called by the API. It:
    1. Applies era modifiers to game parameters
    2. Generates era-appropriate rosters
    3. Updates game state with era info
    4. Optionally sets the user's team

    Returns summary of the initialized game.
    """
    if era not in ERAS:
        raise ValueError(f"Unknown era: {era}. Valid eras: {list(ERAS.keys())}")

    era_info = ERAS[era]

    # Apply modifiers (adjusts ratings, salaries, stadiums)
    modifier_result = apply_era_modifiers(era, db_path)

    # Generate era-appropriate player names
    roster_result = generate_era_rosters(era, db_path)

    # Update game state dates to match era
    start_year = era_info["start_year"]
    execute(
        "UPDATE game_state SET current_date=?, season=?, phase='spring_training' WHERE id=1",
        (f"{start_year}-02-15", start_year),
        db_path
    )

    # Set user team if specified
    if team_id is not None:
        execute(
            "UPDATE game_state SET user_team_id=? WHERE id=1",
            (team_id,),
            db_path
        )

    rules = get_era_rules(era)

    return {
        "success": True,
        "era": era,
        "name": era_info["name"],
        "years": era_info["years"],
        "start_year": start_year,
        "description": era_info["description"],
        "rules_summary": rules["notes"],
        "players_updated": roster_result["players_updated"],
        "modifiers": modifier_result["modifiers_applied"],
    }
