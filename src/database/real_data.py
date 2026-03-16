"""
Front Office - Real MLB Data Fetcher
Pulls real player/team data from the free MLB Stats API (statsapi.mlb.com)
and converts it to the format expected by our seed script.
"""
from __future__ import annotations
import time
import random
from typing import Optional
import httpx

BASE_URL = "https://statsapi.mlb.com/api/v1"
REQUEST_DELAY = 0.5  # seconds between requests to be respectful

# ---------------------------------------------------------------------------
# City name overrides: MLB API locationName -> our game city name
# ---------------------------------------------------------------------------
CITY_OVERRIDES = {
    "Flushing": "New York",
    "Bronx": "New York",
    "Sacramento": "Oakland",
    "St. Petersburg": "Tampa Bay",
    "Anaheim": "Los Angeles",
    "Arlington": "Texas",
    "Minneapolis": "Minnesota",
    "Cumberland": "Atlanta",      # Truist Park is in Cumberland, GA
    "Denver": "Colorado",
    "Phoenix": "Arizona",
    "San Francisco": "San Francisco",
}

# MLB API abbreviation -> our abbreviation (where they differ)
ABBR_OVERRIDES = {
    "ATH": "OAK",  # Athletics moved to Sacramento but we keep OAK
    "AZ": "ARI",   # Diamondbacks
    "WSN": "WSH",  # Nationals
    "CHW": "CWS",  # White Sox
    "TBR": "TB",   # Rays
    "SDP": "SD",   # Padres
    "SFG": "SF",   # Giants
    "KCR": "KC",   # Royals
}

# ---------------------------------------------------------------------------
# Position mapping from MLB API abbreviations to our schema positions
# ---------------------------------------------------------------------------
POSITION_MAP = {
    "C": "C", "1B": "1B", "2B": "2B", "3B": "3B", "SS": "SS",
    "LF": "LF", "CF": "CF", "RF": "RF", "DH": "DH",
    "SP": "SP", "RP": "RP", "CL": "RP",
    # Generic positions from API
    "P": "SP", "OF": "CF", "IF": "SS",
    "TWP": "SP",  # two-way player
    "PH": "DH", "PR": "CF",
}

# Fielding/arm base ratings by position (for estimation)
FIELDING_BASE = {
    "C": 55, "1B": 40, "2B": 55, "3B": 50, "SS": 60, "LF": 45,
    "CF": 60, "RF": 50, "DH": 20, "SP": 35, "RP": 35,
}
ARM_BASE = {
    "C": 60, "1B": 35, "2B": 45, "3B": 55, "SS": 60, "LF": 45,
    "CF": 50, "RF": 65, "DH": 20, "SP": 40, "RP": 40,
}

# Division ID -> (league, division) mapping
DIVISION_MAP = {
    200: ("AL", "West"),
    201: ("AL", "East"),
    202: ("AL", "Central"),
    203: ("NL", "West"),
    204: ("NL", "East"),
    205: ("NL", "Central"),
}


def _clamp(value: int, lo: int = 20, hi: int = 80) -> int:
    """Clamp a rating to the 20-80 scouting scale."""
    return max(lo, min(hi, int(value)))


def _api_get(client: httpx.Client, path: str, params: dict = None) -> Optional[dict]:
    """Make a GET request to the MLB Stats API with rate limiting."""
    url = f"{BASE_URL}{path}"
    try:
        resp = client.get(url, params=params or {}, timeout=15.0)
        resp.raise_for_status()
        time.sleep(REQUEST_DELAY)
        return resp.json()
    except (httpx.HTTPStatusError, httpx.RequestError, Exception) as e:
        print(f"  [WARN] API error for {path}: {e}")
        time.sleep(REQUEST_DELAY)
        return None


# ===================================================================
# TEAM FETCHING
# ===================================================================

def _fetch_teams(client: httpx.Client) -> list[dict]:
    """Fetch all 30 MLB teams with venue info."""
    data = _api_get(client, "/teams", {"sportId": 1})
    if not data:
        raise RuntimeError("Failed to fetch teams from MLB API")

    teams = []
    for t in data.get("teams", []):
        if not t.get("active"):
            continue

        div_id = t.get("division", {}).get("id", 0)
        league, division = DIVISION_MAP.get(div_id, ("AL", "East"))

        location = t.get("locationName", "Unknown")
        city = CITY_OVERRIDES.get(location, location)

        venue = t.get("venue", {})
        raw_abbr = t.get("abbreviation", "UNK")
        abbr = ABBR_OVERRIDES.get(raw_abbr, raw_abbr)

        teams.append({
            "mlb_id": t["id"],
            "city": city,
            "name": t.get("teamName", t.get("name", "Unknown")),
            "abbreviation": abbr,
            "league": league,
            "division": division,
            "venue_id": venue.get("id"),
            "stadium_name": venue.get("name", "Unknown Stadium"),
        })

    return teams


def _fetch_venue_dimensions(client: httpx.Client, venue_id: int) -> dict:
    """Fetch stadium field dimensions for a venue."""
    defaults = {"lf": 330, "lcf": 370, "cf": 400, "rcf": 370, "rf": 330,
                "capacity": 40000, "is_dome": 0, "surface": "grass"}

    if not venue_id:
        return defaults

    data = _api_get(client, f"/venues/{venue_id}", {"hydrate": "fieldInfo"})
    if not data:
        return defaults

    venues = data.get("venues", [])
    if not venues:
        return defaults

    v = venues[0]
    fi = v.get("fieldInfo", {})
    # capacity, turfType, roofType are inside fieldInfo
    cap = fi.get("capacity", v.get("capacity", defaults["capacity"]))
    roof = fi.get("roofType", v.get("roofType", ""))
    surface = fi.get("turfType", "grass")

    # The fieldInfo contains dimensions like leftLine, leftCenter, center, etc.
    result = {
        "lf": fi.get("leftLine", fi.get("leftField", defaults["lf"])),
        "lcf": fi.get("leftCenter", defaults["lcf"]),
        "cf": fi.get("center", defaults["cf"]),
        "rcf": fi.get("rightCenter", defaults["rcf"]),
        "rf": fi.get("rightLine", fi.get("rightField", defaults["rf"])),
        "capacity": cap if isinstance(cap, int) else defaults["capacity"],
        "is_dome": 1 if roof.lower() in ("dome", "retractable") else 0,
        "surface": "turf" if "turf" in surface.lower() or "artificial" in surface.lower() else "grass",
    }
    return result


# ===================================================================
# PLAYER FETCHING
# ===================================================================

def _fetch_roster(client: httpx.Client, mlb_team_id: int) -> list[dict]:
    """Fetch the 40-man roster for a team. Returns list of basic player info."""
    data = _api_get(client, f"/teams/{mlb_team_id}/roster", {"rosterType": "40Man"})
    if not data:
        return []

    players = []
    for entry in data.get("roster", []):
        person = entry.get("person", {})
        pos_info = entry.get("position", {})
        status = entry.get("status", {})

        api_pos = pos_info.get("abbreviation", "DH")
        position = POSITION_MAP.get(api_pos, "DH")

        # Determine roster status from API status code
        status_code = status.get("code", "A")
        if status_code == "A":
            roster_status = "active"
        elif status_code in ("MIN", "NRI"):
            roster_status = "minors_aaa"
        elif status_code in ("D10", "D15", "D60"):
            roster_status = "active"  # injured but on 40-man
        else:
            roster_status = "active"

        players.append({
            "mlb_id": person.get("id"),
            "full_name": person.get("fullName", "Unknown Player"),
            "position": position,
            "roster_status": roster_status,
        })

    return players


def _fetch_player_details(client: httpx.Client, player_id: int) -> Optional[dict]:
    """Fetch detailed player info + 2024 stats."""
    data = _api_get(
        client,
        f"/people/{player_id}",
        {"hydrate": "stats(group=[hitting,pitching],type=[season],season=2024)"},
    )
    if not data:
        return None

    people = data.get("people", [])
    if not people:
        return None

    p = people[0]

    # Parse basic bio
    first_name = p.get("firstName", p.get("useName", "Unknown"))
    last_name = p.get("lastName", "Player")
    age = p.get("currentAge", 27)
    birth_country = p.get("birthCountry", "USA")
    bat_side = p.get("batSide", {}).get("code", "R")
    pitch_hand = p.get("pitchHand", {}).get("code", "R")
    primary_pos = p.get("primaryPosition", {}).get("abbreviation", "DH")
    position = POSITION_MAP.get(primary_pos, "DH")

    # Map bat side codes
    bats = {"R": "R", "L": "L", "S": "S"}.get(bat_side, "R")
    throws = {"R": "R", "L": "L"}.get(pitch_hand, "R")

    # Extract stats
    hitting_stats = None
    pitching_stats = None
    for stat_group in p.get("stats", []):
        group_name = stat_group.get("group", {}).get("displayName", "")
        splits = stat_group.get("splits", [])
        if not splits:
            continue
        # Use the last split (most recent / total for season)
        stat = splits[-1].get("stat", {})
        if group_name == "hitting" and stat:
            hitting_stats = stat
        elif group_name == "pitching" and stat:
            pitching_stats = stat

    return {
        "first_name": first_name,
        "last_name": last_name,
        "age": age,
        "birth_country": birth_country,
        "bats": bats,
        "throws": throws,
        "position": position,
        "hitting_stats": hitting_stats,
        "pitching_stats": pitching_stats,
    }


# ===================================================================
# STAT -> RATING CONVERSIONS
# ===================================================================

def _safe_float(val, default=0.0) -> float:
    """Safely convert a value to float."""
    try:
        if isinstance(val, str):
            return float(val)
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _hitting_ratings(stats: dict, position: str, age: int) -> dict:
    """Convert 2024 hitting stats to 20-80 scouting ratings."""
    avg = _safe_float(stats.get("avg"), 0.250)
    slg = _safe_float(stats.get("slg"), 0.400)
    obp = _safe_float(stats.get("obp"), 0.320)
    ab = _safe_float(stats.get("atBats"), 1)
    so = _safe_float(stats.get("strikeOuts"), 0)
    hr = _safe_float(stats.get("homeRuns"), 0)
    sb = _safe_float(stats.get("stolenBases"), 0)
    triples = _safe_float(stats.get("triples"), 0)
    games = _safe_float(stats.get("gamesPlayed"), 1)

    # Avoid division by zero
    ab = max(ab, 1)
    games = max(games, 1)

    k_rate = so / ab
    hr_rate = hr / ab
    iso = max(0, slg - avg)  # isolated power
    sb_per_game = sb / games
    triples_per_game = triples / games

    # Contact: based on AVG and K-rate
    # .300 avg + low K = 80, .200 avg + high K = 20
    contact_from_avg = (avg - 0.180) / 0.140 * 60 + 20  # .180=20, .320=80
    contact_from_k = (1 - k_rate / 0.35) * 60 + 20       # 0% K=80, 35% K=20
    contact = _clamp((contact_from_avg * 0.6 + contact_from_k * 0.4))

    # Power: based on ISO and HR rate
    # ISO .300+ = 80, ISO .050 = 20
    power_from_iso = (iso - 0.050) / 0.250 * 60 + 20
    power_from_hr = (hr_rate - 0.010) / 0.060 * 60 + 20
    power = _clamp((power_from_iso * 0.6 + power_from_hr * 0.4))

    # Speed: based on SB and triples
    speed_from_sb = (sb_per_game - 0.02) / 0.25 * 60 + 30
    speed_from_3b = triples_per_game / 0.03 * 20 + 30
    speed = _clamp((speed_from_sb * 0.7 + speed_from_3b * 0.3))
    # Age-based speed decline
    if age > 30:
        speed = _clamp(speed - (age - 30) * 3)

    # Fielding: position-based with some variance
    fielding_base = FIELDING_BASE.get(position, 45)
    fielding = _clamp(fielding_base + random.randint(-8, 8))

    # Arm: position-based with some variance
    arm_base = ARM_BASE.get(position, 45)
    arm = _clamp(arm_base + random.randint(-8, 8))

    return {
        "contact_rating": contact,
        "power_rating": power,
        "speed_rating": speed,
        "fielding_rating": fielding,
        "arm_rating": arm,
    }


def _pitching_ratings(stats: dict, position: str, age: int) -> dict:
    """Convert 2024 pitching stats to 20-80 scouting ratings."""
    ip_str = stats.get("inningsPitched", "0")
    # IP is stored as "123.1" where .1 = 1/3, .2 = 2/3
    try:
        parts = str(ip_str).split(".")
        ip = float(parts[0]) + (float(parts[1]) / 3 if len(parts) > 1 else 0)
    except (ValueError, IndexError):
        ip = 0

    ip = max(ip, 1.0)  # avoid division by zero

    so = _safe_float(stats.get("strikeOuts"), 0)
    bb = _safe_float(stats.get("baseOnBalls"), 0)
    hr = _safe_float(stats.get("homeRuns"), 0)
    er = _safe_float(stats.get("earnedRuns"), 0)
    gs = _safe_float(stats.get("gamesStarted"), 0)
    games = _safe_float(stats.get("gamesPitched", stats.get("gamesPlayed", 0)), 0)

    k_per_9 = (so / ip) * 9
    bb_per_9 = (bb / ip) * 9
    hr_per_9 = (hr / ip) * 9
    era = (er / ip) * 9

    # FIP approximation: (13*HR + 3*BB - 2*K) / IP + 3.10
    fip = (13 * hr + 3 * bb - 2 * so) / ip + 3.10

    # Stuff: based on K/9 and FIP
    # K/9 of 12+ = 80, K/9 of 4 = 20
    stuff_from_k = (k_per_9 - 4.0) / 8.0 * 60 + 20
    stuff_from_fip = (5.50 - fip) / 4.0 * 60 + 20  # FIP 1.5=80, FIP 5.5=20
    stuff = _clamp((stuff_from_k * 0.5 + stuff_from_fip * 0.5))

    # Control: based on BB/9 inverse
    # BB/9 of 1.0 = 80, BB/9 of 5.5 = 20
    control = _clamp((5.5 - bb_per_9) / 4.5 * 60 + 20)

    # Stamina: based on IP/GS for starters, low for relievers
    is_starter = position == "SP"
    if is_starter and gs > 0:
        ip_per_start = ip / gs
        # 7.0 IP/GS = 80, 4.0 IP/GS = 20
        stamina = _clamp((ip_per_start - 4.0) / 3.0 * 60 + 20)
    elif is_starter:
        stamina = _clamp(50)
    else:
        # Relievers: base 30-45
        stamina = _clamp(random.randint(25, 45))

    return {
        "stuff_rating": stuff,
        "control_rating": control,
        "stamina_rating": stamina,
    }


def _default_hitting_ratings(position: str, age: int) -> dict:
    """Reasonable defaults when no 2024 stats exist."""
    is_pitcher = position in ("SP", "RP")

    if is_pitcher:
        return {
            "contact_rating": _clamp(random.randint(20, 30)),
            "power_rating": _clamp(random.randint(20, 25)),
            "speed_rating": _clamp(random.randint(25, 40)),
            "fielding_rating": _clamp(FIELDING_BASE.get(position, 35) + random.randint(-5, 5)),
            "arm_rating": _clamp(ARM_BASE.get(position, 40) + random.randint(-5, 5)),
        }

    # Position player without stats -- likely young/prospect or injured
    if age <= 24:
        base = random.randint(35, 50)  # prospect range
    elif age <= 30:
        base = random.randint(40, 55)
    else:
        base = random.randint(35, 50)

    return {
        "contact_rating": _clamp(base + random.randint(-5, 5)),
        "power_rating": _clamp(base + random.randint(-8, 8)),
        "speed_rating": _clamp(base + random.randint(-5, 5) - max(0, (age - 30) * 3)),
        "fielding_rating": _clamp(FIELDING_BASE.get(position, 45) + random.randint(-8, 8)),
        "arm_rating": _clamp(ARM_BASE.get(position, 45) + random.randint(-8, 8)),
    }


def _default_pitching_ratings(position: str, age: int) -> dict:
    """Reasonable defaults when no 2024 pitching stats exist."""
    if position not in ("SP", "RP"):
        return {"stuff_rating": 20, "control_rating": 20, "stamina_rating": 20}

    if age <= 24:
        base = random.randint(35, 55)
    elif age <= 30:
        base = random.randint(40, 55)
    else:
        base = random.randint(35, 50)

    return {
        "stuff_rating": _clamp(base + random.randint(-5, 5)),
        "control_rating": _clamp(base + random.randint(-5, 5)),
        "stamina_rating": _clamp(
            random.randint(45, 65) if position == "SP" else random.randint(25, 40)
        ),
    }


def _build_player_dict(details: dict, roster_entry: dict) -> dict:
    """Build a player dict matching our DB schema from API data."""
    position = details["position"]
    # If the roster says SP/RP but player detail says something else, prefer roster
    if roster_entry["position"] in ("SP", "RP"):
        position = roster_entry["position"]

    age = details["age"]
    is_pitcher = position in ("SP", "RP")

    # Calculate hitting ratings
    if details["hitting_stats"] and not is_pitcher:
        hit_ratings = _hitting_ratings(details["hitting_stats"], position, age)
    else:
        hit_ratings = _default_hitting_ratings(position, age)

    # Calculate pitching ratings
    if details["pitching_stats"] and is_pitcher:
        pitch_ratings = _pitching_ratings(details["pitching_stats"], position, age)
    else:
        pitch_ratings = _default_pitching_ratings(position, age)

    # Potential: current + some upside based on age
    if age <= 25:
        pot_bonus = random.randint(5, 15)
    elif age <= 28:
        pot_bonus = random.randint(2, 8)
    elif age <= 32:
        pot_bonus = random.randint(0, 3)
    else:
        pot_bonus = 0  # veterans are what they are

    # Personality traits (randomized -- API doesn't have these)
    ego = random.randint(25, 85)
    leadership = random.randint(25, 75)
    work_ethic = random.randint(35, 85)
    clutch = random.randint(25, 75)
    durability = random.randint(35, 85)

    # Service time / options estimate from age
    if age <= 23:
        service_years = round(random.uniform(0, 1.5), 1)
        option_years = 3
        roster_status = roster_entry.get("roster_status", "minors_aaa")
    elif age <= 26:
        service_years = round(random.uniform(0.5, 3.5), 1)
        option_years = random.randint(1, 3)
        roster_status = roster_entry.get("roster_status", "active")
    else:
        service_years = round(random.uniform(3.0, age - 22.0), 1)
        option_years = 0
        roster_status = roster_entry.get("roster_status", "active")

    # Contract estimate from age/ratings
    overall = max(hit_ratings.values()) if not is_pitcher else max(pitch_ratings.values())
    if overall >= 65 and service_years >= 3:
        salary = random.randint(12_000_000, 35_000_000)
        contract_years = random.randint(2, 6)
        ntc = random.choices([0, 1, 2], weights=[30, 40, 30])[0]
    elif overall >= 50 and service_years >= 2:
        salary = random.randint(3_000_000, 15_000_000)
        contract_years = random.randint(1, 4)
        ntc = random.choices([0, 1, 2], weights=[70, 20, 10])[0]
    elif service_years >= 1:
        salary = random.randint(750_000, 5_000_000)
        contract_years = random.randint(1, 3)
        ntc = 0
    else:
        salary = random.randint(720_000, 740_000)
        contract_years = random.randint(1, 3)
        ntc = 0

    peak_age = random.randint(26, 30)

    return {
        "first_name": details["first_name"],
        "last_name": details["last_name"],
        "age": age,
        "birth_country": details["birth_country"],
        "bats": details["bats"],
        "throws": details["throws"],
        "position": position,
        **hit_ratings,
        **pitch_ratings,
        "contact_potential": min(80, hit_ratings["contact_rating"] + pot_bonus),
        "power_potential": min(80, hit_ratings["power_rating"] + pot_bonus),
        "speed_potential": min(80, hit_ratings["speed_rating"] + pot_bonus),
        "fielding_potential": min(80, hit_ratings["fielding_rating"] + pot_bonus),
        "arm_potential": min(80, hit_ratings["arm_rating"] + pot_bonus),
        "stuff_potential": min(80, pitch_ratings["stuff_rating"] + pot_bonus) if is_pitcher else 20,
        "control_potential": min(80, pitch_ratings["control_rating"] + pot_bonus) if is_pitcher else 20,
        "stamina_potential": min(80, pitch_ratings["stamina_rating"] + pot_bonus) if is_pitcher else 20,
        "ego": ego,
        "leadership": leadership,
        "work_ethic": work_ethic,
        "clutch": clutch,
        "durability": durability,
        "roster_status": roster_status,
        "peak_age": peak_age,
        "development_rate": round(random.uniform(0.7, 1.3), 2),
        "service_years": service_years,
        "option_years_remaining": option_years,
        "salary": salary,
        "contract_years": contract_years,
        "ntc": ntc,
    }


# ===================================================================
# MAIN ENTRY POINT
# ===================================================================

def fetch_all_mlb_data() -> dict:
    """
    Fetch all 30 MLB teams, their rosters, and player stats from the
    MLB Stats API. Returns a dict with:
      - "teams": list of team dicts (matching our DB schema fields)
      - "players": dict mapping team abbreviation to list of player dicts
    """
    result = {"teams": [], "players": {}}

    with httpx.Client() as client:
        # 1. Fetch all teams
        print("Fetching MLB teams...")
        raw_teams = _fetch_teams(client)
        print(f"  Found {len(raw_teams)} teams")

        # 2. For each team, fetch venue dimensions and roster
        for i, team in enumerate(raw_teams):
            abbr = team["abbreviation"]
            print(f"\n[{i+1}/30] {team['city']} {team['name']} ({abbr})")

            # Fetch venue dimensions
            print(f"  Fetching venue dimensions for {team['stadium_name']}...")
            dims = _fetch_venue_dimensions(client, team.get("venue_id"))

            team_dict = {
                "city": team["city"],
                "name": team["name"],
                "abbr": abbr,
                "league": team["league"],
                "division": team["division"],
                "stadium": team["stadium_name"],
                "capacity": dims["capacity"],
                "lf": dims["lf"],
                "lcf": dims["lcf"],
                "cf": dims["cf"],
                "rcf": dims["rcf"],
                "rf": dims["rf"],
                "dome": dims["is_dome"],
                # These are not from the API, use reasonable defaults
                "market": 3,
                "pop": 3000000,
                "income": 55000,
                "fan_base": 50,
            }
            result["teams"].append(team_dict)

            # Fetch 40-man roster
            print(f"  Fetching 40-man roster...")
            roster = _fetch_roster(client, team["mlb_id"])
            print(f"  Found {len(roster)} players on 40-man roster")

            # Fetch details for each player
            team_players = []
            for j, entry in enumerate(roster):
                player_id = entry.get("mlb_id")
                if not player_id:
                    continue

                details = _fetch_player_details(client, player_id)
                if not details:
                    print(f"    [{j+1}/{len(roster)}] SKIP {entry['full_name']} (no data)")
                    continue

                player_dict = _build_player_dict(details, entry)
                team_players.append(player_dict)

                if (j + 1) % 10 == 0 or j == len(roster) - 1:
                    print(f"    [{j+1}/{len(roster)}] players processed")

            result["players"][abbr] = team_players

    return result


# ===================================================================
# Market/financial data enrichment (not from API)
# ===================================================================
MARKET_DATA = {
    "NYY": {"market": 5, "pop": 20140000, "income": 72000, "fan_base": 90},
    "BOS": {"market": 4, "pop": 4900000, "income": 70000, "fan_base": 88},
    "TOR": {"market": 4, "pop": 6200000, "income": 52000, "fan_base": 65},
    "BAL": {"market": 3, "pop": 2800000, "income": 62000, "fan_base": 55},
    "TB":  {"market": 2, "pop": 3200000, "income": 50000, "fan_base": 35},
    "CLE": {"market": 2, "pop": 2060000, "income": 50000, "fan_base": 55},
    "MIN": {"market": 3, "pop": 3700000, "income": 58000, "fan_base": 60},
    "DET": {"market": 3, "pop": 4300000, "income": 48000, "fan_base": 58},
    "KC":  {"market": 2, "pop": 2200000, "income": 52000, "fan_base": 50},
    "CWS": {"market": 3, "pop": 9500000, "income": 58000, "fan_base": 45},
    "HOU": {"market": 4, "pop": 7100000, "income": 55000, "fan_base": 70},
    "SEA": {"market": 3, "pop": 4000000, "income": 62000, "fan_base": 55},
    "TEX": {"market": 3, "pop": 7600000, "income": 55000, "fan_base": 60},
    "LAA": {"market": 4, "pop": 13200000, "income": 60000, "fan_base": 55},
    "ATH": {"market": 1, "pop": 2200000, "income": 65000, "fan_base": 30},
    "OAK": {"market": 1, "pop": 2200000, "income": 65000, "fan_base": 30},
    "ATL": {"market": 4, "pop": 6100000, "income": 55000, "fan_base": 70},
    "PHI": {"market": 4, "pop": 6200000, "income": 58000, "fan_base": 75},
    "NYM": {"market": 5, "pop": 20140000, "income": 72000, "fan_base": 75},
    "WSH": {"market": 4, "pop": 6300000, "income": 68000, "fan_base": 50},
    "MIA": {"market": 3, "pop": 6200000, "income": 52000, "fan_base": 30},
    "MIL": {"market": 2, "pop": 1600000, "income": 50000, "fan_base": 65},
    "CHC": {"market": 4, "pop": 9500000, "income": 58000, "fan_base": 85},
    "STL": {"market": 3, "pop": 2800000, "income": 50000, "fan_base": 85},
    "PIT": {"market": 2, "pop": 2360000, "income": 48000, "fan_base": 50},
    "CIN": {"market": 2, "pop": 2200000, "income": 48000, "fan_base": 55},
    "LAD": {"market": 5, "pop": 13200000, "income": 60000, "fan_base": 90},
    "SD":  {"market": 3, "pop": 3300000, "income": 58000, "fan_base": 55},
    "ARI": {"market": 3, "pop": 4900000, "income": 50000, "fan_base": 45},
    "SF":  {"market": 4, "pop": 4700000, "income": 68000, "fan_base": 70},
    "COL": {"market": 3, "pop": 2900000, "income": 55000, "fan_base": 50},
}


def enrich_teams_with_market_data(teams: list[dict]) -> list[dict]:
    """Add market/financial data that isn't in the MLB API."""
    for team in teams:
        abbr = team.get("abbr", "")
        market = MARKET_DATA.get(abbr, {})
        team["market"] = market.get("market", team.get("market", 3))
        team["pop"] = market.get("pop", team.get("pop", 3000000))
        team["income"] = market.get("income", team.get("income", 55000))
        team["fan_base"] = market.get("fan_base", team.get("fan_base", 50))
    return teams


# ===================================================================
# CLI TEST
# ===================================================================

if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("MLB Stats API -> Front Office Data Fetcher")
    print("=" * 60)

    # Allow fetching just one team for quick testing
    quick_test = "--quick" in sys.argv

    if quick_test:
        print("\n*** QUICK TEST MODE: Fetching 1 team only ***\n")
        with httpx.Client() as client:
            raw_teams = _fetch_teams(client)
            # Pick the Yankees for a quick test
            test_team = next((t for t in raw_teams if t["abbreviation"] == "NYY"), raw_teams[0])
            abbr = test_team["abbreviation"]

            dims = _fetch_venue_dimensions(client, test_team.get("venue_id"))
            print(f"Team: {test_team['city']} {test_team['name']}")
            print(f"Stadium: {test_team['stadium_name']}")
            print(f"Dimensions: LF={dims['lf']} LCF={dims['lcf']} CF={dims['cf']} RCF={dims['rcf']} RF={dims['rf']}")
            print(f"Dome: {dims['is_dome']}  Surface: {dims['surface']}  Capacity: {dims['capacity']}")

            roster = _fetch_roster(client, test_team["mlb_id"])
            print(f"\n40-man roster: {len(roster)} players")

            # Fetch first 5 players as sample
            for i, entry in enumerate(roster[:5]):
                details = _fetch_player_details(client, entry["mlb_id"])
                if details:
                    player = _build_player_dict(details, entry)
                    pos = player["position"]
                    is_p = pos in ("SP", "RP")
                    print(f"\n  {player['first_name']} {player['last_name']} ({pos}) Age {player['age']}")
                    print(f"    Bats: {player['bats']}  Throws: {player['throws']}  Country: {player['birth_country']}")
                    print(f"    Contact: {player['contact_rating']}  Power: {player['power_rating']}  "
                          f"Speed: {player['speed_rating']}  Field: {player['fielding_rating']}  Arm: {player['arm_rating']}")
                    if is_p:
                        print(f"    Stuff: {player['stuff_rating']}  Control: {player['control_rating']}  "
                              f"Stamina: {player['stamina_rating']}")
    else:
        data = fetch_all_mlb_data()
        data["teams"] = enrich_teams_with_market_data(data["teams"])

        print("\n" + "=" * 60)
        print("FETCH SUMMARY")
        print("=" * 60)
        print(f"Teams fetched: {len(data['teams'])}")
        total_players = sum(len(ps) for ps in data["players"].values())
        print(f"Total players: {total_players}")
        print(f"\nPer-team breakdown:")
        for team in data["teams"]:
            abbr = team["abbr"]
            players = data["players"].get(abbr, [])
            pitchers = [p for p in players if p["position"] in ("SP", "RP")]
            hitters = [p for p in players if p["position"] not in ("SP", "RP")]
            print(f"  {abbr:>4}: {len(players):>3} players ({len(hitters)} pos, {len(pitchers)} P) "
                  f"| {team['stadium']} ({team.get('lf')}-{team.get('cf')}-{team.get('rf')})")
