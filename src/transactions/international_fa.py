"""
Front Office - International Free Agency System
Handles the international signing period, prospects, and bonus pool.
"""
import json
import random
from datetime import date
from ..database.db import get_connection, query, execute

# International countries and their talent distribution
INTERNATIONAL_COUNTRIES = {
    "Dominican Republic": 0.25,  # 25% of prospects
    "Venezuela": 0.20,
    "Cuba": 0.12,
    "Japan": 0.10,
    "Puerto Rico": 0.08,
    "Mexico": 0.07,
    "Brazil": 0.05,
    "South Korea": 0.04,
    "Canada": 0.03,
    "Netherlands": 0.02,
    "Other": 0.04,
}

# Base bonus pool allocations (realistic MLB international pool sizes)
BASE_BONUS_POOL = 5200000  # Overall international pool roughly $5.2M per team


def generate_international_prospects(season: int, db_path: str = None) -> list:
    """
    Generate 30-50 international prospects for the given season.
    Prospects are ages 16-22, mostly from traditional baseball countries.
    """
    conn = get_connection(db_path)

    # Check if already generated
    existing = conn.execute("""
        SELECT COUNT(*) as c FROM international_prospects WHERE season=?
    """, (season,)).fetchone()["c"]

    if existing > 0:
        conn.close()
        return query("""
            SELECT * FROM international_prospects
            WHERE season=? AND is_signed=0
            ORDER BY contact_ceiling + power_ceiling DESC
        """, (season,), db_path=db_path)

    # Generate 35-50 prospects
    prospect_count = random.randint(35, 50)
    prospects = []
    used_names = set()

    first_names = [
        "Juan", "Miguel", "Carlos", "Luis", "Jose", "Pedro", "Diego", "Fernando",
        "Antonio", "Manuel", "Francisco", "Jesus", "Roberto", "Jorge", "Ricardo",
        "Julio", "Marco", "David", "Angel", "Hector", "Oscar", "Rafael", "Victor",
        "Sergio", "Ignacio", "Pablo", "Salvador", "Raul", "Ruben", "Martin",
        "Hiroshi", "Kenji", "Takeshi", "Hideki", "Yoshiro", "Masato", "Yuki",
        "Daiki", "Sato", "Tanaka", "Yamamoto", "Nakamura", "Sakamoto", "Kobayashi",
    ]

    last_names_by_country = {
        "Dominican Republic": [
            "Martinez", "Rodriguez", "Perez", "Garcia", "Hernandez", "Lopez",
            "Gomez", "Sanchez", "Reyes", "Diaz", "Torres", "Santos", "Mora",
            "Nunez", "Contreras", "Encarnacion", "Severino", "Familia",
        ],
        "Venezuela": [
            "Machado", "Cabrera", "Andrus", "Soriano", "Mesoraco", "Bastardo",
            "Vizca", "Amezaga", "Montero", "Feliz", "Rondon", "Obispo", "Gonzalez",
        ],
        "Cuba": [
            "Puig", "Chapman", "Abreu", "Castro", "Fernandez", "Despaigne",
            "Olivera", "Quesada", "Morales", "Noda", "Barbier",
        ],
        "Japan": [
            "Suzuki", "Yamamoto", "Shimizu", "Kawasaki", "Tanaka", "Okada",
            "Sakamoto", "Uchikawa", "Yashiro", "Yanagita", "Yamada",
        ],
        "Puerto Rico": [
            "Bautista", "Cedeño", "Quintero", "Ventura", "Colón", "Morales",
            "Santiago", "de los Santos", "Feliciano", "Gonzalez",
        ],
        "Mexico": [
            "Beltre", "Guerrero", "Lopez", "Herrera", "Romero", "Mejia",
            "Mejia", "Guzman", "Vazquez", "Reyes", "Flores",
        ],
    }

    for rank in range(1, prospect_count + 1):
        # Distribute by country
        rand_val = random.random()
        cumulative = 0
        country = "Dominican Republic"
        for c, pct in INTERNATIONAL_COUNTRIES.items():
            cumulative += pct
            if rand_val <= cumulative:
                country = c
                break

        # Get name
        first = random.choice(first_names)
        if country in last_names_by_country:
            last = random.choice(last_names_by_country[country])
        else:
            last = random.choice(last_names_by_country["Dominican Republic"])

        while f"{first} {last}" in used_names:
            first = random.choice(first_names)
            last = random.choice(
                last_names_by_country.get(country, last_names_by_country["Dominican Republic"])
            )
        used_names.add(f"{first} {last}")

        # Age: mostly 16-22
        age = random.choices(
            [16, 17, 18, 19, 20, 21, 22],
            weights=[2, 3, 8, 12, 10, 8, 4]
        )[0]

        # Position: skew toward pitcher and high-value positions
        position = random.choices(
            ["SS", "2B", "CF", "3B", "C", "1B", "LF", "RF", "SP", "RP"],
            weights=[12, 10, 10, 8, 6, 5, 5, 4, 10, 10]
        )[0]

        # Ratings with floor/ceiling (high uncertainty)
        is_pitcher = position in ("SP", "RP")

        if is_pitcher:
            # Pitchers: stuff and control are key
            stuff_floor = random.randint(30, 45)
            stuff_ceiling = min(80, stuff_floor + random.randint(20, 35))
            control_floor = random.randint(25, 40)
            control_ceiling = min(80, control_floor + random.randint(20, 35))

            prospect = {
                "first_name": first,
                "last_name": last,
                "age": age,
                "birth_country": country,
                "position": position,
                "bats": "R",
                "throws": random.choice(["L", "R"]),
                "contact_floor": 20,
                "contact_ceiling": 30,
                "power_floor": 20,
                "power_ceiling": 30,
                "speed_floor": 25,
                "speed_ceiling": 45,
                "fielding_floor": 30,
                "fielding_ceiling": 55,
                "arm_floor": 35,
                "arm_ceiling": 65,
                "stuff_floor": stuff_floor,
                "stuff_ceiling": stuff_ceiling,
                "control_floor": control_floor,
                "control_ceiling": control_ceiling,
            }
        else:
            # Position players: contact and power key
            contact_floor = random.randint(30, 50)
            contact_ceiling = min(80, contact_floor + random.randint(15, 30))
            power_floor = random.randint(25, 45)
            power_ceiling = min(80, power_floor + random.randint(20, 35))

            prospect = {
                "first_name": first,
                "last_name": last,
                "age": age,
                "birth_country": country,
                "position": position,
                "bats": random.choice(["L", "R", "S"]),
                "throws": random.choice(["L", "R"]),
                "contact_floor": contact_floor,
                "contact_ceiling": contact_ceiling,
                "power_floor": power_floor,
                "power_ceiling": power_ceiling,
                "speed_floor": random.randint(25, 50),
                "speed_ceiling": min(80, random.randint(50, 75)),
                "fielding_floor": random.randint(25, 45),
                "fielding_ceiling": min(80, random.randint(50, 75)),
                "arm_floor": random.randint(30, 50),
                "arm_ceiling": min(80, random.randint(50, 75)),
                "stuff_floor": 20,
                "stuff_ceiling": 25,
                "control_floor": 20,
                "control_ceiling": 25,
            }

        # Generate scouting report
        key_tools = []
        if prospect["contact_ceiling"] >= 60:
            key_tools.append("plus contact")
        if prospect["power_ceiling"] >= 60:
            key_tools.append("power potential")
        if prospect["speed_ceiling"] >= 60:
            key_tools.append("speed")
        if prospect["stuff_ceiling"] >= 60:
            key_tools.append("electric stuff")
        if prospect["control_ceiling"] >= 60:
            key_tools.append("control")

        scouting_report = f"Young prospect from {country}. "
        if key_tools:
            scouting_report += f"Has {', '.join(key_tools)}. "
        scouting_report += f"Age {age}, still developing. Signability: {'High' if age <= 17 else 'Moderate'}."

        prospect["scouting_report"] = scouting_report
        prospects.append(prospect)

    # Insert into database
    for rank, prospect in enumerate(prospects, 1):
        conn.execute("""
            INSERT INTO international_prospects
            (season, first_name, last_name, age, birth_country, position, bats, throws,
             contact_floor, contact_ceiling, power_floor, power_ceiling,
             speed_floor, speed_ceiling, fielding_floor, fielding_ceiling,
             arm_floor, arm_ceiling, scouting_report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            season, prospect["first_name"], prospect["last_name"],
            prospect["age"], prospect["birth_country"], prospect["position"],
            prospect["bats"], prospect["throws"],
            prospect["contact_floor"], prospect["contact_ceiling"],
            prospect["power_floor"], prospect["power_ceiling"],
            prospect["speed_floor"], prospect["speed_ceiling"],
            prospect["fielding_floor"], prospect["fielding_ceiling"],
            prospect["arm_floor"], prospect["arm_ceiling"],
            prospect["scouting_report"]
        ))

    conn.commit()
    conn.close()
    return prospects


def get_international_pool_status(team_id: int, season: int,
                                 db_path: str = None) -> dict:
    """Get a team's international bonus pool status."""
    team = query("""
        SELECT t.cash, t.scouting_staff_budget
        FROM teams t
        WHERE t.id=?
    """, (team_id,), db_path=db_path)

    if not team:
        return {}

    # Calculate team pool: base pool + adjustments based on payroll
    base_pool = BASE_BONUS_POOL
    team_data = team[0]

    # Adjust for market size and budget
    budget_factor = max(0.5, min(2.0, team_data["scouting_staff_budget"] / 10000000.0))
    effective_pool = int(base_pool * budget_factor)

    # Get signed prospects count
    signed = query("""
        SELECT COUNT(*) as count, SUM(signing_bonus) as total_spent
        FROM international_prospects
        WHERE signed_by_team_id=? AND season=?
    """, (team_id, season), db_path=db_path)

    spent = 0
    count = 0
    if signed:
        count = signed[0]["count"] or 0
        spent = signed[0]["total_spent"] or 0

    return {
        "team_id": team_id,
        "season": season,
        "pool_total": effective_pool,
        "pool_spent": spent,
        "pool_remaining": effective_pool - spent,
        "prospects_signed": count,
    }


def process_international_signings(season: int, db_path: str = None) -> list:
    """
    AI teams sign international prospects based on available pool money
    and scouting budget during the signing period.
    """
    conn = get_connection(db_path)
    signings = []

    # Get all teams and their pool status
    teams = query("""
        SELECT t.id, t.city, t.name, t.scouting_staff_budget, t.cash
        FROM teams t
        ORDER BY t.cash DESC
    """, db_path=db_path)

    if not teams:
        conn.close()
        return signings

    # Get available unsigned prospects, ranked by ceiling
    available = query("""
        SELECT * FROM international_prospects
        WHERE season=? AND is_signed=0
        ORDER BY (contact_ceiling + power_ceiling + stuff_ceiling) DESC
    """, (season,), db_path=db_path)

    if not available:
        conn.close()
        return signings

    for team in teams:
        team_id = team["id"]
        pool_status = get_international_pool_status(team_id, season, db_path)

        if pool_status["pool_remaining"] <= 0:
            continue

        # Determine signing aggressiveness based on team budget and scouting
        budget_factor = team["scouting_staff_budget"] / 10000000.0
        aggressiveness = min(0.8, max(0.2, budget_factor))

        # Try to sign prospects
        prospects_to_consider = [p for p in available if p["is_signed"] == 0]
        random.shuffle(prospects_to_consider)

        for prospect in prospects_to_consider:
            if pool_status["pool_remaining"] <= 100000:
                break

            # Calculate signing bonus based on prospect quality and available pool
            ceiling_avg = (
                prospect["contact_ceiling"] + prospect["power_ceiling"] +
                prospect["fielding_ceiling"]
            ) / 3.0

            # Young players cost more
            age_factor = max(0.5, (18 - prospect["age"]) * 0.1)
            base_bonus = int(ceiling_avg * 15000 * age_factor * aggressiveness)

            # Random variation
            bonus = int(base_bonus * random.uniform(0.8, 1.2))
            bonus = min(bonus, int(pool_status["pool_remaining"] * 0.1))  # Max 10% of remaining
            bonus = max(100000, bonus)  # Min $100k

            # Decision: sign if good prospect and pool available
            if ceiling_avg >= 50 and bonus <= pool_status["pool_remaining"]:
                # Sign the prospect
                sign_date = date.today().isoformat()
                conn.execute("""
                    UPDATE international_prospects
                    SET is_signed=1, signed_by_team_id=?, signing_bonus=?, signed_date=?
                    WHERE id=?
                """, (team_id, bonus, sign_date, prospect["id"]))

                # Create player on team in minors
                new_player_id = conn.execute("""
                    INSERT INTO players
                    (team_id, first_name, last_name, age, birth_country,
                     bats, throws, position, contact_rating, power_rating,
                     speed_rating, fielding_rating, arm_rating,
                     contact_potential, power_potential, speed_potential,
                     fielding_potential, arm_potential,
                     roster_status, on_forty_man, service_years)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, 'minors_rookie', 0, 0)
                """, (
                    team_id, prospect["first_name"], prospect["last_name"],
                    prospect["age"], prospect["birth_country"],
                    prospect["bats"], prospect["throws"], prospect["position"],
                    random.randint(prospect["contact_floor"], prospect["contact_ceiling"]),
                    random.randint(prospect["power_floor"], prospect["power_ceiling"]),
                    random.randint(prospect["speed_floor"], prospect["speed_ceiling"]),
                    random.randint(prospect["fielding_floor"], prospect["fielding_ceiling"]),
                    random.randint(prospect["arm_floor"], prospect["arm_ceiling"]),
                    prospect["contact_ceiling"],
                    prospect["power_ceiling"],
                    prospect["speed_ceiling"],
                    prospect["fielding_ceiling"],
                    prospect["arm_ceiling"],
                )).lastrowid

                signings.append({
                    "team_id": team_id,
                    "team_name": f"{team['city']} {team['name']}",
                    "prospect_name": f"{prospect['first_name']} {prospect['last_name']}",
                    "prospect_id": prospect["id"],
                    "player_id": new_player_id,
                    "country": prospect["birth_country"],
                    "position": prospect["position"],
                    "bonus": bonus,
                })

                pool_status["pool_spent"] += bonus
                pool_status["pool_remaining"] -= bonus
                available = [p for p in available if p["id"] != prospect["id"]]

    conn.commit()
    conn.close()
    return signings
