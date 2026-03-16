"""
Front Office - Seed Data
Populates the database with all 30 MLB teams, generated players,
GM/owner characters, and a 162-game schedule.
"""
import random
import json
from datetime import date, timedelta
from .db import get_connection, init_db

# ============================================================
# ALL 30 MLB TEAMS
# ============================================================
TEAMS = [
    # AL East
    {"city": "New York", "name": "Yankees", "abbr": "NYY", "league": "AL", "division": "East",
     "stadium": "Yankee Stadium", "capacity": 46537, "lf": 318, "lcf": 399, "cf": 408, "rcf": 385, "rf": 314,
     "market": 5, "pop": 20140000, "income": 72000, "fan_base": 90, "dome": 0},
    {"city": "Boston", "name": "Red Sox", "abbr": "BOS", "league": "AL", "division": "East",
     "stadium": "Fenway Park", "capacity": 37755, "lf": 310, "lcf": 379, "cf": 390, "rcf": 380, "rf": 302,
     "market": 4, "pop": 4900000, "income": 70000, "fan_base": 88, "dome": 0},
    {"city": "Toronto", "name": "Blue Jays", "abbr": "TOR", "league": "AL", "division": "East",
     "stadium": "Rogers Centre", "capacity": 49282, "lf": 328, "lcf": 375, "cf": 400, "rcf": 375, "rf": 328,
     "market": 4, "pop": 6200000, "income": 52000, "fan_base": 65, "dome": 1},
    {"city": "Baltimore", "name": "Orioles", "abbr": "BAL", "league": "AL", "division": "East",
     "stadium": "Camden Yards", "capacity": 45971, "lf": 333, "lcf": 364, "cf": 400, "rcf": 373, "rf": 318,
     "market": 3, "pop": 2800000, "income": 62000, "fan_base": 55, "dome": 0},
    {"city": "Tampa Bay", "name": "Rays", "abbr": "TB", "league": "AL", "division": "East",
     "stadium": "Tropicana Field", "capacity": 25000, "lf": 315, "lcf": 370, "cf": 404, "rcf": 370, "rf": 322,
     "market": 2, "pop": 3200000, "income": 50000, "fan_base": 35, "dome": 1},
    # AL Central
    {"city": "Cleveland", "name": "Guardians", "abbr": "CLE", "league": "AL", "division": "Central",
     "stadium": "Progressive Field", "capacity": 34830, "lf": 325, "lcf": 370, "cf": 400, "rcf": 375, "rf": 325,
     "market": 2, "pop": 2060000, "income": 50000, "fan_base": 55, "dome": 0},
    {"city": "Minnesota", "name": "Twins", "abbr": "MIN", "league": "AL", "division": "Central",
     "stadium": "Target Field", "capacity": 38544, "lf": 339, "lcf": 377, "cf": 404, "rcf": 367, "rf": 328,
     "market": 3, "pop": 3700000, "income": 58000, "fan_base": 60, "dome": 0},
    {"city": "Detroit", "name": "Tigers", "abbr": "DET", "league": "AL", "division": "Central",
     "stadium": "Comerica Park", "capacity": 41083, "lf": 345, "lcf": 370, "cf": 420, "rcf": 365, "rf": 330,
     "market": 3, "pop": 4300000, "income": 48000, "fan_base": 58, "dome": 0},
    {"city": "Kansas City", "name": "Royals", "abbr": "KC", "league": "AL", "division": "Central",
     "stadium": "Kauffman Stadium", "capacity": 37903, "lf": 330, "lcf": 387, "cf": 410, "rcf": 387, "rf": 330,
     "market": 2, "pop": 2200000, "income": 52000, "fan_base": 50, "dome": 0},
    {"city": "Chicago", "name": "White Sox", "abbr": "CWS", "league": "AL", "division": "Central",
     "stadium": "Guaranteed Rate Field", "capacity": 40615, "lf": 330, "lcf": 375, "cf": 400, "rcf": 375, "rf": 335,
     "market": 3, "pop": 9500000, "income": 58000, "fan_base": 45, "dome": 0},
    # AL West
    {"city": "Houston", "name": "Astros", "abbr": "HOU", "league": "AL", "division": "West",
     "stadium": "Minute Maid Park", "capacity": 41168, "lf": 315, "lcf": 362, "cf": 409, "rcf": 373, "rf": 326,
     "market": 4, "pop": 7100000, "income": 55000, "fan_base": 70, "dome": 1},
    {"city": "Seattle", "name": "Mariners", "abbr": "SEA", "league": "AL", "division": "West",
     "stadium": "T-Mobile Park", "capacity": 47929, "lf": 331, "lcf": 378, "cf": 401, "rcf": 381, "rf": 326,
     "market": 3, "pop": 4000000, "income": 62000, "fan_base": 55, "dome": 1},
    {"city": "Texas", "name": "Rangers", "abbr": "TEX", "league": "AL", "division": "West",
     "stadium": "Globe Life Field", "capacity": 40300, "lf": 329, "lcf": 372, "cf": 407, "rcf": 374, "rf": 326,
     "market": 3, "pop": 7600000, "income": 55000, "fan_base": 60, "dome": 1},
    {"city": "Los Angeles", "name": "Angels", "abbr": "LAA", "league": "AL", "division": "West",
     "stadium": "Angel Stadium", "capacity": 45517, "lf": 330, "lcf": 387, "cf": 400, "rcf": 370, "rf": 330,
     "market": 4, "pop": 13200000, "income": 60000, "fan_base": 55, "dome": 0},
    {"city": "Oakland", "name": "Athletics", "abbr": "OAK", "league": "AL", "division": "West",
     "stadium": "Sacramento Sutter Health Park", "capacity": 14014, "lf": 330, "lcf": 375, "cf": 400, "rcf": 375, "rf": 330,
     "market": 1, "pop": 2200000, "income": 65000, "fan_base": 30, "dome": 0},
    # NL East
    {"city": "Atlanta", "name": "Braves", "abbr": "ATL", "league": "NL", "division": "East",
     "stadium": "Truist Park", "capacity": 41084, "lf": 335, "lcf": 385, "cf": 400, "rcf": 375, "rf": 325,
     "market": 4, "pop": 6100000, "income": 55000, "fan_base": 70, "dome": 0},
    {"city": "Philadelphia", "name": "Phillies", "abbr": "PHI", "league": "NL", "division": "East",
     "stadium": "Citizens Bank Park", "capacity": 42792, "lf": 329, "lcf": 374, "cf": 401, "rcf": 369, "rf": 330,
     "market": 4, "pop": 6200000, "income": 58000, "fan_base": 75, "dome": 0},
    {"city": "New York", "name": "Mets", "abbr": "NYM", "league": "NL", "division": "East",
     "stadium": "Citi Field", "capacity": 41922, "lf": 335, "lcf": 379, "cf": 408, "rcf": 383, "rf": 330,
     "market": 5, "pop": 20140000, "income": 72000, "fan_base": 75, "dome": 0},
    {"city": "Washington", "name": "Nationals", "abbr": "WSH", "league": "NL", "division": "East",
     "stadium": "Nationals Park", "capacity": 41339, "lf": 336, "lcf": 377, "cf": 402, "rcf": 370, "rf": 335,
     "market": 4, "pop": 6300000, "income": 68000, "fan_base": 50, "dome": 0},
    {"city": "Miami", "name": "Marlins", "abbr": "MIA", "league": "NL", "division": "East",
     "stadium": "LoanDepot Park", "capacity": 36742, "lf": 344, "lcf": 386, "cf": 407, "rcf": 392, "rf": 335,
     "market": 3, "pop": 6200000, "income": 52000, "fan_base": 30, "dome": 1},
    # NL Central
    {"city": "Milwaukee", "name": "Brewers", "abbr": "MIL", "league": "NL", "division": "Central",
     "stadium": "American Family Field", "capacity": 41900, "lf": 344, "lcf": 371, "cf": 400, "rcf": 374, "rf": 345,
     "market": 2, "pop": 1600000, "income": 50000, "fan_base": 65, "dome": 1},
    {"city": "Chicago", "name": "Cubs", "abbr": "CHC", "league": "NL", "division": "Central",
     "stadium": "Wrigley Field", "capacity": 41649, "lf": 355, "lcf": 368, "cf": 400, "rcf": 368, "rf": 353,
     "market": 4, "pop": 9500000, "income": 58000, "fan_base": 85, "dome": 0},
    {"city": "St. Louis", "name": "Cardinals", "abbr": "STL", "league": "NL", "division": "Central",
     "stadium": "Busch Stadium", "capacity": 45494, "lf": 336, "lcf": 375, "cf": 400, "rcf": 375, "rf": 335,
     "market": 3, "pop": 2800000, "income": 50000, "fan_base": 85, "dome": 0},
    {"city": "Pittsburgh", "name": "Pirates", "abbr": "PIT", "league": "NL", "division": "Central",
     "stadium": "PNC Park", "capacity": 38362, "lf": 325, "lcf": 383, "cf": 399, "rcf": 375, "rf": 320,
     "market": 2, "pop": 2360000, "income": 48000, "fan_base": 50, "dome": 0},
    {"city": "Cincinnati", "name": "Reds", "abbr": "CIN", "league": "NL", "division": "Central",
     "stadium": "Great American Ball Park", "capacity": 42319, "lf": 328, "lcf": 379, "cf": 404, "rcf": 370, "rf": 325,
     "market": 2, "pop": 2200000, "income": 48000, "fan_base": 55, "dome": 0},
    # NL West
    {"city": "Los Angeles", "name": "Dodgers", "abbr": "LAD", "league": "NL", "division": "West",
     "stadium": "Dodger Stadium", "capacity": 56000, "lf": 330, "lcf": 385, "cf": 395, "rcf": 385, "rf": 330,
     "market": 5, "pop": 13200000, "income": 60000, "fan_base": 90, "dome": 0},
    {"city": "San Diego", "name": "Padres", "abbr": "SD", "league": "NL", "division": "West",
     "stadium": "Petco Park", "capacity": 42445, "lf": 334, "lcf": 367, "cf": 396, "rcf": 382, "rf": 322,
     "market": 3, "pop": 3300000, "income": 58000, "fan_base": 55, "dome": 0},
    {"city": "Arizona", "name": "Diamondbacks", "abbr": "ARI", "league": "NL", "division": "West",
     "stadium": "Chase Field", "capacity": 48519, "lf": 330, "lcf": 374, "cf": 407, "rcf": 374, "rf": 334,
     "market": 3, "pop": 4900000, "income": 50000, "fan_base": 45, "dome": 1},
    {"city": "San Francisco", "name": "Giants", "abbr": "SF", "league": "NL", "division": "West",
     "stadium": "Oracle Park", "capacity": 41915, "lf": 339, "lcf": 364, "cf": 399, "rcf": 365, "rf": 309,
     "market": 4, "pop": 4700000, "income": 68000, "fan_base": 70, "dome": 0},
    {"city": "Colorado", "name": "Rockies", "abbr": "COL", "league": "NL", "division": "West",
     "stadium": "Coors Field", "capacity": 50144, "lf": 347, "lcf": 390, "cf": 415, "rcf": 375, "rf": 350,
     "market": 3, "pop": 2900000, "income": 55000, "fan_base": 50, "dome": 0},
]

# ============================================================
# GENERATED NAMES
# ============================================================
FIRST_NAMES = [
    "James", "Michael", "Robert", "David", "William", "John", "Carlos", "Jose", "Luis",
    "Miguel", "Rafael", "Juan", "Pedro", "Marcus", "Anthony", "Brandon", "Tyler", "Ryan",
    "Austin", "Colton", "Bryce", "Chase", "Derek", "Tanner", "Cody", "Jake", "Kyle",
    "Matt", "Nick", "Zach", "Aaron", "Adam", "Alex", "Andrew", "Ben", "Brian",
    "Chris", "Daniel", "Eric", "Frank", "Greg", "Henry", "Ian", "Jason", "Kevin",
    "Leo", "Nathan", "Oscar", "Patrick", "Quinn", "Sam", "Travis", "Victor", "Wesley",
    "Yoenis", "Angel", "Fernando", "Hector", "Javier", "Manuel", "Ramon", "Roberto",
    "Salvador", "Julio", "Vladimir", "Wander", "Shohei", "Yoshinobu", "Seiya", "Jung",
    "Hyun", "Wei", "Kenji", "Daisuke", "Mookie", "Ozzie", "Trea", "Jazz", "Gunnar",
    "Adley", "Corbin", "Spencer", "Shane", "Grayson", "Gavin", "Wyatt", "Cooper",
    "Dillon", "Hunter", "Mason", "Brady", "Nolan", "Tucker", "Maverick", "Cruz",
    "Enrique", "Francisco", "Andres", "Cristian", "Yadier", "Sandy", "Framber",
    "Ranger", "Walker", "Ryne", "Bo", "Cavan", "Nate", "Ty", "Cal"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Martinez", "Rodriguez",
    "Lopez", "Hernandez", "Gonzalez", "Perez", "Ramirez", "Torres", "Flores", "Rivera",
    "Sanchez", "Diaz", "Cruz", "Morales", "Ortiz", "Reyes", "Gutierrez", "Castillo",
    "Romero", "Anderson", "Thomas", "Taylor", "Wilson", "Davis", "Miller", "Moore",
    "Clark", "Lewis", "Walker", "Hall", "Allen", "Young", "King", "Wright",
    "Scott", "Green", "Baker", "Adams", "Nelson", "Hill", "Carter", "Mitchell",
    "Roberts", "Campbell", "Parker", "Evans", "Edwards", "Collins", "Stewart", "Murphy",
    "Sullivan", "Hayes", "Fisher", "Gibson", "Harper", "Wagner", "Freeman", "Turner",
    "Cole", "Kershaw", "Verlander", "Scherzer", "deGrom", "Alcantara", "Woodruff",
    "Cabrera", "Betts", "Trout", "Ohtani", "Soto", "Acuna", "Tatis", "Guerrero",
    "Alvarez", "Bichette", "Devers", "Arenado", "Goldschmidt", "Lindor", "Franco",
    "Henderson", "Carroll", "Witt", "Rutschman", "Strider", "Skenes", "Webb",
    "McLanahan", "Cease", "Burns", "Stone", "O'Brien", "McCarthy", "Fitzgerald"
]

GM_FIRST = ["Brian", "Dave", "Mike", "Chris", "James", "Perry", "Derek", "Craig",
            "Billy", "Andrew", "Chaim", "Farhan", "Jeff", "Jed", "Ben", "Erik",
            "Mark", "Scott", "Dan", "Rick", "Jerry", "Peter", "Ross", "Dayton",
            "Nick", "Kevin", "Matt", "Brandon", "Jason", "Steve"]
GM_LAST = ["Cashman", "Dombrowski", "Elias", "Hazen", "Click", "Minasian", "Bloom",
           "Zaidi", "Luhnow", "Friedman", "Hoyer", "Mozeliak", "Cherington", "Stearns",
           "Preller", "Falvey", "Harris", "Antonetti", "Beane", "Epstein", "Rizzo",
           "Alderson", "Dipoto", "Moore", "Krall", "Gomes", "Young", "Swanson",
           "Williams", "Neander"]
OWNER_FIRST = ["Hal", "John", "Mark", "Steve", "Arte", "Ken", "Jim", "Bob",
               "Dick", "Jerry", "Tom", "Chris", "Ted", "Bruce", "Fred", "Larry",
               "George", "Ray", "Bill", "David", "Stuart", "Craig", "Jeff", "Peter",
               "Mike", "Dennis", "Phil", "Robert", "Sam", "Dan"]
OWNER_LAST = ["Steinbrenner", "Henry", "Attanasio", "Cohen", "Moreno", "Kendrick",
              "Crane", "Castellini", "Monfort", "Reinsdorf", "Pohlad", "Ilitch",
              "Lerner", "Rogers", "Sternberg", "DeWitt", "Nutting", "Ricketts",
              "Fisher", "Davis", "Sherman", "Mets-corp", "Guggenheim", "Seidler",
              "Bridich", "Ward", "Falcone", "Angelos", "Stanton", "Huntington"]

PHILOSOPHIES = ["analytics", "old_school", "balanced", "moneyball"]
NEGOTIATION_STYLES = ["aggressive", "fair", "passive", "desperate"]
OWNER_ARCHETYPES = ["win_now", "budget_conscious", "patient_builder",
                    "ego_meddler", "legacy_inheritor", "competitive_small_market"]

POSITIONS_BATTING = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
POSITIONS_PITCHING = ["SP", "SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP", "RP"]
COUNTRIES = ["USA", "USA", "USA", "USA", "USA", "Dominican Republic", "Dominican Republic",
             "Venezuela", "Cuba", "Puerto Rico", "Mexico", "Japan", "South Korea",
             "Colombia", "Panama", "Canada", "Curacao", "Nicaragua"]


def _random_name(used_names: set) -> tuple:
    for _ in range(100):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        full = f"{first} {last}"
        if full not in used_names:
            used_names.add(full)
            return first, last
    # fallback
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES) + str(random.randint(1, 99))
    used_names.add(f"{first} {last}")
    return first, last


def _generate_player(position: str, tier: str, used_names: set) -> dict:
    """Generate a player with ratings based on tier (star/starter/bench/prospect)."""
    first, last = _random_name(used_names)
    is_pitcher = position in ("SP", "RP")

    # Base ratings by tier
    if tier == "star":
        base_range = (65, 80)
        pot_bonus = random.randint(0, 5)
    elif tier == "starter":
        base_range = (45, 65)
        pot_bonus = random.randint(0, 10)
    elif tier == "bench":
        base_range = (35, 55)
        pot_bonus = random.randint(0, 15)
    else:  # prospect
        base_range = (25, 45)
        pot_bonus = random.randint(10, 25)

    age_ranges = {
        "star": (26, 34),
        "starter": (24, 32),
        "bench": (23, 35),
        "prospect": (19, 24),
    }
    age = random.randint(*age_ranges[tier])

    def _rat():
        return max(20, min(80, random.randint(*base_range)))

    contact = _rat()
    power = _rat()
    speed = max(20, _rat() - (age - 27) * 2 if age > 27 else _rat())
    fielding = _rat()
    arm = _rat()

    if is_pitcher:
        stuff = _rat()
        control = _rat()
        stamina = random.randint(40, 80) if position == "SP" else random.randint(20, 50)
        # Pitchers don't need high hitting stats
        contact = max(20, random.randint(20, 35))
        power = max(20, random.randint(20, 30))
    else:
        stuff = 20
        control = 20
        stamina = 20

    bats = random.choices(["R", "L", "S"], weights=[55, 30, 15])[0]
    throws = "L" if (is_pitcher and random.random() < 0.30) else ("L" if random.random() < 0.12 else "R")

    # Contract details based on tier
    if tier == "star":
        salary = random.randint(15000000, 35000000)
        years = random.randint(2, 6)
        ntc = random.choices([0, 1, 2], weights=[30, 40, 30])[0]
    elif tier == "starter":
        salary = random.randint(3000000, 15000000)
        years = random.randint(1, 4)
        ntc = random.choices([0, 1, 2], weights=[70, 15, 15])[0]
    elif tier == "bench":
        salary = random.randint(750000, 5000000)
        years = random.randint(1, 3)
        ntc = 0
    else:
        salary = random.randint(720000, 1000000)
        years = random.randint(1, 3)
        ntc = 0

    roster_status = "active" if tier in ("star", "starter", "bench") else "minors_aaa"

    return {
        "first_name": first,
        "last_name": last,
        "age": age,
        "birth_country": random.choice(COUNTRIES),
        "bats": bats,
        "throws": throws,
        "position": position,
        "contact_rating": contact,
        "power_rating": power,
        "speed_rating": speed,
        "fielding_rating": fielding,
        "arm_rating": arm,
        "stuff_rating": stuff,
        "control_rating": control,
        "stamina_rating": stamina,
        "contact_potential": min(80, contact + pot_bonus),
        "power_potential": min(80, power + pot_bonus),
        "speed_potential": min(80, speed + pot_bonus),
        "fielding_potential": min(80, fielding + pot_bonus),
        "arm_potential": min(80, arm + pot_bonus),
        "stuff_potential": min(80, stuff + pot_bonus) if is_pitcher else 20,
        "control_potential": min(80, control + pot_bonus) if is_pitcher else 20,
        "stamina_potential": min(80, stamina + pot_bonus) if is_pitcher else 20,
        "ego": random.randint(20, 90),
        "leadership": random.randint(20, 80),
        "work_ethic": random.randint(30, 90),
        "clutch": random.randint(20, 80),
        "durability": random.randint(30, 90),
        "roster_status": roster_status,
        "peak_age": random.randint(26, 30),
        "development_rate": round(random.uniform(0.7, 1.3), 2),
        "service_years": max(0, age - 22 + random.uniform(-2, 2)) if tier != "prospect" else 0,
        "option_years_remaining": 3 if tier == "prospect" else max(0, random.randint(0, 2)),
        "salary": salary,
        "contract_years": years,
        "ntc": ntc,
    }


def _generate_roster(used_names: set) -> list:
    """Generate a full 40-man roster with realistic distribution."""
    players = []

    # Active roster (26 players): 13 position + 13 pitchers
    # Stars: 2-3 per team
    star_positions = random.sample(POSITIONS_BATTING, 2)
    has_star_pitcher = random.random() < 0.6

    # Position players
    for pos in POSITIONS_BATTING:
        tier = "star" if pos in star_positions else random.choices(
            ["starter", "bench"], weights=[70, 30])[0]
        players.append(_generate_player(pos, tier, used_names))

    # Bench (4 extra position players)
    bench_positions = random.sample(["C", "IF", "IF", "OF"], 4)
    bench_map = {"IF": random.choice(["1B", "2B", "3B", "SS"]),
                 "OF": random.choice(["LF", "CF", "RF"]),
                 "C": "C"}
    for bp in bench_positions:
        pos = bench_map.get(bp, bp)
        players.append(_generate_player(pos, "bench", used_names))

    # Pitching staff: 5 SP + 8 RP
    for i, pos in enumerate(["SP", "SP", "SP", "SP", "SP", "RP", "RP", "RP", "RP", "RP", "RP", "RP", "RP"]):
        if i == 0 and has_star_pitcher:
            tier = "star"
        elif i < 3:
            tier = "starter"
        else:
            tier = random.choices(["starter", "bench"], weights=[50, 50])[0]
        players.append(_generate_player(pos, tier, used_names))

    # Minor leaguers (14 more to fill 40-man)
    minor_positions = (
        random.sample(POSITIONS_BATTING, 5) +
        ["SP", "SP", "SP", "RP", "RP"] +
        random.sample(POSITIONS_BATTING, 4)
    )
    for pos in minor_positions:
        p = _generate_player(pos, "prospect", used_names)
        level = random.choice(["minors_aaa", "minors_aa", "minors_low"])
        p["roster_status"] = level
        players.append(p)

    return players


def _generate_schedule(season: int, team_ids: list) -> list:
    """Generate a 162-game schedule with proper series structure."""
    games = []
    start_date = date(season, 3, 26)  # Opening Day 2026

    # Group teams by division
    # We'll do a simplified but realistic schedule:
    # - 13 games vs each division rival (4 rivals * 13 = 52)
    # - 7 games vs each same-league non-division team (10 teams * 7 = 70)
    # - 4 games vs each interleague matchup (roughly 10 teams * 4 = 40)
    # Total = 162

    # For now, generate random matchups distributed across the season
    # ensuring each team plays 162 games with ~81 home / ~81 away
    random.seed(season)  # reproducible

    # Build all needed series
    from .db import query
    teams_data = query("SELECT id, league, division FROM teams")
    teams_by_div = {}
    teams_by_league = {}
    for t in teams_data:
        key = f"{t['league']}_{t['division']}"
        teams_by_div.setdefault(key, []).append(t['id'])
        teams_by_league.setdefault(t['league'], []).append(t['id'])

    all_series = []

    for t in teams_data:
        tid = t['id']
        div_key = f"{t['league']}_{t['division']}"
        league = t['league']
        other_league = "NL" if league == "AL" else "AL"

        # Division rivals: 4 series of 3-4 games each = ~13 games per rival
        div_rivals = [x for x in teams_by_div[div_key] if x != tid]
        for rival in div_rivals:
            if tid < rival:  # avoid duplicates
                for _ in range(4):
                    length = random.choice([3, 3, 3, 4])
                    home = tid if random.random() < 0.5 else rival
                    away = rival if home == tid else tid
                    all_series.append((home, away, length))

        # Same league, different division: ~2 series of 3-4 games each
        same_league_other = [x for x in teams_by_league[league]
                            if x != tid and x not in teams_by_div[div_key]]
        for opp in same_league_other:
            if tid < opp:
                for _ in range(2):
                    length = random.choice([3, 3, 4])
                    home = tid if random.random() < 0.5 else opp
                    away = opp if home == tid else tid
                    all_series.append((home, away, length))

        # Interleague: ~1 series of 3 games each vs ~10 opponents
        il_opps = teams_by_league[other_league]
        for opp in il_opps[:5]:
            if tid < opp:
                length = random.choice([3, 3])
                home = tid if random.random() < 0.5 else opp
                away = opp if home == tid else tid
                all_series.append((home, away, length))

    # Distribute series across ~183 days (late March through September)
    random.shuffle(all_series)
    game_date = start_date
    team_last_game = {}

    for home, away, length in all_series:
        # Find next available date where neither team is playing
        attempt_date = game_date
        for _ in range(200):
            h_last = team_last_game.get(home)
            a_last = team_last_game.get(away)
            ok = True
            for d in range(length):
                check = attempt_date + timedelta(days=d)
                if check.month > 9 or (check.month == 9 and check.day > 28):
                    ok = False
                    break
            if ok:
                break
            attempt_date += timedelta(days=1)

        for d in range(length):
            gd = attempt_date + timedelta(days=d)
            games.append({
                "season": season,
                "game_date": gd.isoformat(),
                "home_team_id": home,
                "away_team_id": away,
                "game_number": 1,
            })
            team_last_game[home] = gd
            team_last_game[away] = gd

        game_date = start_date + timedelta(days=random.randint(0, 180))

    return games


def seed_database(db_path: str = None):
    """Full database seed: teams, players, GMs, owners, schedule."""
    init_db(db_path)
    conn = get_connection(db_path)

    # Check if already seeded
    count = conn.execute("SELECT COUNT(*) as c FROM teams").fetchone()["c"]
    if count > 0:
        print("Database already seeded.")
        conn.close()
        return

    print("Seeding database...")

    # Insert teams
    team_ids = []
    for t in TEAMS:
        cursor = conn.execute("""
            INSERT INTO teams (city, name, abbreviation, league, division,
                stadium_name, stadium_capacity, lf_distance, lcf_distance,
                cf_distance, rcf_distance, rf_distance, is_dome, market_size,
                region_population, per_capita_income, fan_base)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (t["city"], t["name"], t["abbr"], t["league"], t["division"],
              t["stadium"], t["capacity"], t["lf"], t["lcf"], t["cf"],
              t["rcf"], t["rf"], t["dome"], t["market"], t["pop"],
              t["income"], t["fan_base"]))
        team_ids.append(cursor.lastrowid)

    # Generate and insert players + contracts
    used_names = set()
    total_players = 0
    for i, team_id in enumerate(team_ids):
        roster = _generate_roster(used_names)
        for p in roster:
            salary = p.pop("salary")
            contract_years = p.pop("contract_years")
            ntc = p.pop("ntc")

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
            """, (team_id, p["first_name"], p["last_name"], p["age"], p["birth_country"],
                  p["bats"], p["throws"], p["position"],
                  p["contact_rating"], p["power_rating"], p["speed_rating"],
                  p["fielding_rating"], p["arm_rating"],
                  p["stuff_rating"], p["control_rating"], p["stamina_rating"],
                  p["contact_potential"], p["power_potential"], p["speed_potential"],
                  p["fielding_potential"], p["arm_potential"],
                  p["stuff_potential"], p["control_potential"], p["stamina_potential"],
                  p["ego"], p["leadership"], p["work_ethic"], p["clutch"], p["durability"],
                  p["roster_status"], p["peak_age"], p["development_rate"],
                  p["service_years"], p["option_years_remaining"]))

            player_id = cursor.lastrowid
            conn.execute("""
                INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
                    annual_salary, no_trade_clause, signed_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (player_id, team_id, contract_years, contract_years,
                  salary, ntc, "2026-01-15"))
            total_players += 1

        print(f"  {TEAMS[i]['abbr']}: {len(roster)} players generated")

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
            "catchphrase": random.choice(["We like our guys", "It's a process", "We're always looking to improve",
                                          "Championship or bust", "Trust the pipeline"]),
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
        # Budget willingness correlates with market size
        market = TEAMS[i]["market"]
        budget_base = market * 15 + random.randint(-10, 10)

        objectives = [
            {"type": "short_term", "description": random.choice([
                "Make the playoffs", "Win the division", "Improve by 10 wins",
                "Develop young talent", "Reduce payroll by 15%"
            ]), "deadline": 2025, "met": False}
        ]

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

    # Generate schedule using the proper balanced schedule generator
    print("Generating 162-game schedule...")
    try:
        from ..simulation.schedule import generate_schedule
        teams_data = [{"id": tid, "league": TEAMS[i]["league"], "division": TEAMS[i]["division"]}
                      for i, tid in enumerate(team_ids)]
        schedule_games = generate_schedule(2026, teams_data)
    except Exception as e:
        print(f"  Falling back to simple schedule generator: {e}")
        schedule_games = _generate_schedule(2026, team_ids)
    for g in schedule_games:
        conn.execute("""
            INSERT INTO schedule (season, game_date, home_team_id, away_team_id, game_number)
            VALUES (?, ?, ?, ?, ?)
        """, (g["season"], g["game_date"], g["home_team_id"], g["away_team_id"], g["game_number"]))

    # Initialize game state — just before spring training 2026
    conn.execute("""
        INSERT OR REPLACE INTO game_state (id, current_date, season, phase, difficulty)
        VALUES (1, '2026-02-15', 2026, 'spring_training', 'manager')
    """)

    conn.commit()

    # Print summary
    game_count = conn.execute("SELECT COUNT(*) as c FROM schedule").fetchone()["c"]
    print(f"\nSeed complete!")
    print(f"  Teams: {len(team_ids)}")
    print(f"  Players: {total_players}")
    print(f"  Scheduled games: {game_count}")

    conn.close()


if __name__ == "__main__":
    seed_database()
