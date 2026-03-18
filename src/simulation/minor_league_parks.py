"""
Front Office - Minor League Park Factors
Realistic park factors for MiLB stadiums organized by league.
Each factor is relative to 1.0 (neutral). Values > 1.0 favor that stat, < 1.0 suppress it.

Based on 5-year tendencies:
- PCL parks are generally hitter-friendly (high altitude, dry air)
- Eastern League parks tend to be more neutral/pitcher-friendly
- International League is a mix
- Lower levels show wider variance due to smaller samples
"""


# ======================================================================
# INTERNATIONAL LEAGUE (AAA)
# ======================================================================
INTERNATIONAL_LEAGUE = {
    "Syracuse": {  # NBT Bank Stadium
        "H": 1.02, "2B": 1.04, "3B": 0.95, "HR": 1.00, "BB": 1.00, "K": 0.99, "R": 1.01,
    },
    "Rochester": {  # Innovative Field
        "H": 0.98, "2B": 0.97, "3B": 1.05, "HR": 0.96, "BB": 1.01, "K": 1.02, "R": 0.97,
    },
    "Buffalo": {  # Sahlen Field
        "H": 0.99, "2B": 1.00, "3B": 0.90, "HR": 1.03, "BB": 1.00, "K": 1.00, "R": 1.01,
    },
    "Columbus": {  # Huntington Park
        "H": 1.01, "2B": 1.02, "3B": 0.98, "HR": 1.02, "BB": 0.99, "K": 0.99, "R": 1.02,
    },
    "Norfolk": {  # Harbor Park
        "H": 0.97, "2B": 0.96, "3B": 0.85, "HR": 0.94, "BB": 1.01, "K": 1.03, "R": 0.95,
    },
    "Durham": {  # Durham Bulls Athletic Park
        "H": 1.03, "2B": 1.05, "3B": 1.00, "HR": 1.04, "BB": 0.99, "K": 0.98, "R": 1.04,
    },
    "Scranton/Wilkes-Barre": {  # PNC Field
        "H": 0.98, "2B": 0.99, "3B": 0.92, "HR": 0.97, "BB": 1.01, "K": 1.01, "R": 0.97,
    },
    "Indianapolis": {  # Victory Field
        "H": 1.00, "2B": 1.01, "3B": 1.02, "HR": 1.01, "BB": 1.00, "K": 1.00, "R": 1.01,
    },
    "Charlotte": {  # Truist Field
        "H": 1.04, "2B": 1.03, "3B": 1.00, "HR": 1.06, "BB": 0.98, "K": 0.97, "R": 1.05,
    },
    "Louisville": {  # Louisville Slugger Field
        "H": 1.02, "2B": 1.03, "3B": 0.98, "HR": 1.03, "BB": 1.00, "K": 0.99, "R": 1.03,
    },
    "Lehigh Valley": {  # Coca-Cola Park
        "H": 1.01, "2B": 1.02, "3B": 0.95, "HR": 1.01, "BB": 1.00, "K": 1.00, "R": 1.01,
    },
    "Worcester": {  # Polar Park
        "H": 0.99, "2B": 1.00, "3B": 0.90, "HR": 0.98, "BB": 1.00, "K": 1.01, "R": 0.98,
    },
}


# ======================================================================
# PACIFIC COAST LEAGUE (AAA) - Generally hitter-friendly
# ======================================================================
PACIFIC_COAST_LEAGUE = {
    "Las Vegas": {  # Las Vegas Ballpark - extreme hitter's park (altitude + dry air)
        "H": 1.12, "2B": 1.10, "3B": 1.05, "HR": 1.18, "BB": 0.97, "K": 0.92, "R": 1.18,
    },
    "Albuquerque": {  # Rio Grande Credit Union Field - extreme altitude (5,300 ft)
        "H": 1.14, "2B": 1.12, "3B": 1.08, "HR": 1.20, "BB": 0.96, "K": 0.90, "R": 1.20,
    },
    "El Paso": {  # Southwest University Park - high altitude (3,800 ft)
        "H": 1.10, "2B": 1.08, "3B": 1.06, "HR": 1.15, "BB": 0.97, "K": 0.93, "R": 1.15,
    },
    "Sacramento": {  # Sutter Health Park
        "H": 1.04, "2B": 1.05, "3B": 1.02, "HR": 1.03, "BB": 1.00, "K": 0.99, "R": 1.04,
    },
    "Reno": {  # Greater Nevada Field - high altitude (4,500 ft)
        "H": 1.10, "2B": 1.09, "3B": 1.04, "HR": 1.14, "BB": 0.97, "K": 0.93, "R": 1.14,
    },
    "Salt Lake City": {  # Smith's Ballpark - high altitude (4,200 ft)
        "H": 1.09, "2B": 1.08, "3B": 1.04, "HR": 1.13, "BB": 0.98, "K": 0.94, "R": 1.12,
    },
    "Round Rock": {  # Dell Diamond
        "H": 1.05, "2B": 1.06, "3B": 1.02, "HR": 1.06, "BB": 0.99, "K": 0.98, "R": 1.06,
    },
    "Sugar Land": {  # Constellation Field
        "H": 1.03, "2B": 1.04, "3B": 1.00, "HR": 1.04, "BB": 1.00, "K": 0.99, "R": 1.04,
    },
    "Oklahoma City": {  # Chickasaw Bricktown Ballpark
        "H": 1.06, "2B": 1.05, "3B": 1.03, "HR": 1.08, "BB": 0.99, "K": 0.97, "R": 1.07,
    },
    "Tacoma": {  # Cheney Stadium
        "H": 0.97, "2B": 0.98, "3B": 0.95, "HR": 0.95, "BB": 1.01, "K": 1.02, "R": 0.96,
    },
    "Nashville": {  # First Horizon Park
        "H": 1.03, "2B": 1.04, "3B": 1.00, "HR": 1.05, "BB": 1.00, "K": 0.99, "R": 1.04,
    },
    "Iowa": {  # Principal Park
        "H": 1.02, "2B": 1.03, "3B": 1.01, "HR": 1.03, "BB": 1.00, "K": 0.99, "R": 1.03,
    },
}


# ======================================================================
# EASTERN LEAGUE (AA) - Generally neutral to pitcher-friendly
# ======================================================================
EASTERN_LEAGUE = {
    "Binghamton": {  # Mirabito Stadium
        "H": 0.96, "2B": 0.97, "3B": 0.90, "HR": 0.94, "BB": 1.01, "K": 1.03, "R": 0.95,
    },
    "New Hampshire": {  # Delta Dental Stadium
        "H": 0.98, "2B": 0.99, "3B": 0.95, "HR": 0.97, "BB": 1.00, "K": 1.01, "R": 0.97,
    },
    "Portland": {  # Hadlock Field
        "H": 0.97, "2B": 0.98, "3B": 0.88, "HR": 0.95, "BB": 1.01, "K": 1.02, "R": 0.96,
    },
    "Hartford": {  # Dunkin' Donuts Park
        "H": 0.99, "2B": 1.00, "3B": 0.92, "HR": 0.98, "BB": 1.00, "K": 1.00, "R": 0.99,
    },
    "Somerset": {  # TD Bank Ballpark
        "H": 1.01, "2B": 1.02, "3B": 0.95, "HR": 1.02, "BB": 1.00, "K": 0.99, "R": 1.01,
    },
    "Reading": {  # FirstEnergy Stadium
        "H": 1.00, "2B": 1.01, "3B": 0.97, "HR": 1.01, "BB": 1.00, "K": 1.00, "R": 1.00,
    },
    "Erie": {  # UPMC Park
        "H": 0.97, "2B": 0.98, "3B": 0.93, "HR": 0.96, "BB": 1.01, "K": 1.02, "R": 0.96,
    },
    "Akron": {  # Canal Park
        "H": 1.00, "2B": 1.01, "3B": 0.98, "HR": 1.00, "BB": 1.00, "K": 1.00, "R": 1.00,
    },
    "Richmond": {  # The Diamond
        "H": 1.02, "2B": 1.03, "3B": 1.00, "HR": 1.03, "BB": 0.99, "K": 0.99, "R": 1.02,
    },
    "Harrisburg": {  # FNB Field
        "H": 0.98, "2B": 0.99, "3B": 0.94, "HR": 0.97, "BB": 1.01, "K": 1.01, "R": 0.97,
    },
    "Altoona": {  # Peoples Natural Gas Field
        "H": 0.96, "2B": 0.97, "3B": 0.92, "HR": 0.94, "BB": 1.02, "K": 1.03, "R": 0.95,
    },
    "Bowie": {  # Prince George's Stadium
        "H": 1.01, "2B": 1.02, "3B": 0.96, "HR": 1.01, "BB": 1.00, "K": 1.00, "R": 1.01,
    },
}


# ======================================================================
# SOUTHERN LEAGUE (AA)
# ======================================================================
SOUTHERN_LEAGUE = {
    "Birmingham": {  # Regions Field
        "H": 1.01, "2B": 1.02, "3B": 0.98, "HR": 1.02, "BB": 1.00, "K": 0.99, "R": 1.01,
    },
    "Chattanooga": {  # AT&T Field
        "H": 1.03, "2B": 1.04, "3B": 1.00, "HR": 1.04, "BB": 0.99, "K": 0.98, "R": 1.04,
    },
    "Mississippi": {  # Trustmark Park
        "H": 1.02, "2B": 1.03, "3B": 1.01, "HR": 1.03, "BB": 1.00, "K": 0.99, "R": 1.03,
    },
    "Biloxi": {  # MGM Park
        "H": 1.00, "2B": 1.01, "3B": 0.97, "HR": 1.00, "BB": 1.00, "K": 1.00, "R": 1.00,
    },
    "Tennessee": {  # Smokies Stadium
        "H": 0.99, "2B": 1.00, "3B": 0.96, "HR": 0.98, "BB": 1.00, "K": 1.01, "R": 0.99,
    },
    "Rocket City": {  # Toyota Field
        "H": 1.01, "2B": 1.02, "3B": 0.99, "HR": 1.02, "BB": 1.00, "K": 0.99, "R": 1.01,
    },
    "Pensacola": {  # Admiral Fetterman Field
        "H": 1.00, "2B": 1.01, "3B": 0.98, "HR": 1.01, "BB": 1.00, "K": 1.00, "R": 1.00,
    },
    "Montgomery": {  # Riverwalk Stadium
        "H": 1.02, "2B": 1.03, "3B": 1.00, "HR": 1.03, "BB": 0.99, "K": 0.99, "R": 1.02,
    },
    "Amarillo": {  # Hodgetown - high altitude (3,600 ft)
        "H": 1.08, "2B": 1.07, "3B": 1.04, "HR": 1.10, "BB": 0.98, "K": 0.95, "R": 1.10,
    },
    "Midland": {  # Momentum Bank Ballpark - high altitude
        "H": 1.06, "2B": 1.05, "3B": 1.03, "HR": 1.08, "BB": 0.98, "K": 0.96, "R": 1.07,
    },
}


# ======================================================================
# MIDWEST LEAGUE (A)
# ======================================================================
MIDWEST_LEAGUE = {
    "South Bend": {  # Four Winds Field
        "H": 0.99, "2B": 1.00, "3B": 0.97, "HR": 0.98, "BB": 1.00, "K": 1.00, "R": 0.99,
    },
    "Great Lakes": {  # Dow Diamond
        "H": 0.98, "2B": 0.99, "3B": 0.95, "HR": 0.97, "BB": 1.01, "K": 1.01, "R": 0.97,
    },
    "West Michigan": {  # LMCU Ballpark
        "H": 0.97, "2B": 0.98, "3B": 0.93, "HR": 0.96, "BB": 1.01, "K": 1.02, "R": 0.96,
    },
    "Fort Wayne": {  # Parkview Field
        "H": 1.01, "2B": 1.02, "3B": 0.98, "HR": 1.01, "BB": 1.00, "K": 0.99, "R": 1.01,
    },
    "Dayton": {  # Day Air Ballpark
        "H": 1.00, "2B": 1.01, "3B": 0.98, "HR": 1.00, "BB": 1.00, "K": 1.00, "R": 1.00,
    },
    "Lake County": {  # Classic Park
        "H": 1.02, "2B": 1.03, "3B": 1.00, "HR": 1.03, "BB": 0.99, "K": 0.99, "R": 1.02,
    },
    "Lansing": {  # Jackson Field
        "H": 0.98, "2B": 0.99, "3B": 0.96, "HR": 0.97, "BB": 1.01, "K": 1.01, "R": 0.97,
    },
    "Wisconsin": {  # Neuroscience Group Field
        "H": 0.97, "2B": 0.98, "3B": 0.95, "HR": 0.96, "BB": 1.01, "K": 1.02, "R": 0.96,
    },
    "Beloit": {  # ABC Supply Stadium
        "H": 1.00, "2B": 1.01, "3B": 0.97, "HR": 1.00, "BB": 1.00, "K": 1.00, "R": 1.00,
    },
    "Cedar Rapids": {  # Veterans Memorial Stadium
        "H": 1.01, "2B": 1.02, "3B": 0.99, "HR": 1.01, "BB": 1.00, "K": 0.99, "R": 1.01,
    },
    "Peoria": {  # Dozer Park
        "H": 1.00, "2B": 1.01, "3B": 0.98, "HR": 1.00, "BB": 1.00, "K": 1.00, "R": 1.00,
    },
    "Quad Cities": {  # Modern Woodmen Park
        "H": 0.99, "2B": 1.00, "3B": 0.96, "HR": 0.98, "BB": 1.01, "K": 1.01, "R": 0.99,
    },
}


# ======================================================================
# SOUTH ATLANTIC LEAGUE (A)
# ======================================================================
SOUTH_ATLANTIC_LEAGUE = {
    "Greenville": {  # Fluor Field
        "H": 1.01, "2B": 1.02, "3B": 0.98, "HR": 1.01, "BB": 1.00, "K": 0.99, "R": 1.01,
    },
    "Rome": {  # AdventHealth Stadium
        "H": 1.02, "2B": 1.03, "3B": 1.00, "HR": 1.03, "BB": 0.99, "K": 0.99, "R": 1.02,
    },
    "Asheville": {  # McCormick Field - altitude (2,100 ft)
        "H": 1.05, "2B": 1.04, "3B": 1.02, "HR": 1.06, "BB": 0.99, "K": 0.97, "R": 1.06,
    },
    "Bowling Green": {  # Bowling Green Ballpark
        "H": 1.00, "2B": 1.01, "3B": 0.98, "HR": 1.00, "BB": 1.00, "K": 1.00, "R": 1.00,
    },
    "Brooklyn": {  # Maimonides Park
        "H": 0.97, "2B": 0.98, "3B": 0.88, "HR": 0.95, "BB": 1.02, "K": 1.02, "R": 0.96,
    },
    "Jersey Shore": {  # ShoreTown Ballpark
        "H": 0.99, "2B": 1.00, "3B": 0.95, "HR": 0.98, "BB": 1.00, "K": 1.01, "R": 0.99,
    },
    "Hickory": {  # L.P. Frans Stadium
        "H": 1.03, "2B": 1.04, "3B": 1.01, "HR": 1.04, "BB": 0.99, "K": 0.98, "R": 1.04,
    },
    "Winston-Salem": {  # Truist Stadium
        "H": 1.01, "2B": 1.02, "3B": 0.99, "HR": 1.02, "BB": 1.00, "K": 0.99, "R": 1.01,
    },
    "Aberdeen": {  # Leidos Field
        "H": 0.98, "2B": 0.99, "3B": 0.94, "HR": 0.97, "BB": 1.01, "K": 1.01, "R": 0.97,
    },
    "Hudson Valley": {  # Heritage Financial Park
        "H": 0.99, "2B": 1.00, "3B": 0.93, "HR": 0.98, "BB": 1.00, "K": 1.01, "R": 0.99,
    },
}


# ======================================================================
# ALL PARKS BY LEAGUE LEVEL
# ======================================================================
PARKS_BY_LEAGUE = {
    "International League": INTERNATIONAL_LEAGUE,
    "Pacific Coast League": PACIFIC_COAST_LEAGUE,
    "Eastern League": EASTERN_LEAGUE,
    "Southern League": SOUTHERN_LEAGUE,
    "Midwest League": MIDWEST_LEAGUE,
    "South Atlantic League": SOUTH_ATLANTIC_LEAGUE,
}

PARKS_BY_LEVEL = {
    "AAA": {**INTERNATIONAL_LEAGUE, **PACIFIC_COAST_LEAGUE},
    "AA": {**EASTERN_LEAGUE, **SOUTHERN_LEAGUE},
    "A": {**MIDWEST_LEAGUE, **SOUTH_ATLANTIC_LEAGUE},
    "LOW": {**MIDWEST_LEAGUE, **SOUTH_ATLANTIC_LEAGUE},  # Low-A uses same parks
}


# ======================================================================
# MLB TEAM -> MILB AFFILIATE MAPPING
# Maps MLB team abbreviation to park name at each level
# ======================================================================
MLB_AFFILIATES = {
    "NYY": {"AAA": "Scranton/Wilkes-Barre", "AA": "Somerset", "A": "Hudson Valley"},
    "NYM": {"AAA": "Syracuse", "AA": "Binghamton", "A": "Brooklyn"},
    "BOS": {"AAA": "Worcester", "AA": "Portland", "A": "Greenville"},
    "TBR": {"AAA": "Durham", "AA": "Montgomery", "A": "Bowling Green"},
    "BAL": {"AAA": "Norfolk", "AA": "Bowie", "A": "Aberdeen"},
    "TOR": {"AAA": "Buffalo", "AA": "New Hampshire", "A": "South Bend"},
    "CLE": {"AAA": "Columbus", "AA": "Akron", "A": "Lake County"},
    "CHW": {"AAA": "Charlotte", "AA": "Birmingham", "A": "Winston-Salem"},
    "DET": {"AAA": "Toledo", "AA": "Erie", "A": "West Michigan"},
    "KCR": {"AAA": "Omaha", "AA": "Biloxi", "A": "Quad Cities"},
    "MIN": {"AAA": "St. Paul", "AA": "Chattanooga", "A": "Cedar Rapids"},
    "HOU": {"AAA": "Sugar Land", "AA": "Rocket City", "A": "Asheville"},
    "LAA": {"AAA": "Salt Lake City", "AA": "Midland", "A": "Great Lakes"},
    "OAK": {"AAA": "Las Vegas", "AA": "Amarillo", "A": "Lansing"},
    "SEA": {"AAA": "Tacoma", "AA": "Tennessee", "A": "Beloit"},
    "TEX": {"AAA": "Round Rock", "AA": "Reading", "A": "Hickory"},
    "ATL": {"AAA": "Nashville", "AA": "Mississippi", "A": "Rome"},
    "MIA": {"AAA": "Jacksonville", "AA": "Pensacola", "A": "Jupiter"},
    "PHI": {"AAA": "Lehigh Valley", "AA": "Reading", "A": "Jersey Shore"},
    "WSN": {"AAA": "Rochester", "AA": "Harrisburg", "A": "Dayton"},
    "CHC": {"AAA": "Iowa", "AA": "Tennessee", "A": "South Bend"},
    "CIN": {"AAA": "Louisville", "AA": "Chattanooga", "A": "Dayton"},
    "MIL": {"AAA": "Nashville", "AA": "Biloxi", "A": "Wisconsin"},
    "PIT": {"AAA": "Indianapolis", "AA": "Altoona", "A": "Fort Wayne"},
    "STL": {"AAA": "Memphis", "AA": "Springfield", "A": "Peoria"},
    "ARI": {"AAA": "Reno", "AA": "Amarillo", "A": "Hillsboro"},
    "COL": {"AAA": "Albuquerque", "AA": "Hartford", "A": "Dayton"},
    "LAD": {"AAA": "Oklahoma City", "AA": "Biloxi", "A": "Great Lakes"},
    "SDP": {"AAA": "El Paso", "AA": "Midland", "A": "Fort Wayne"},
    "SFG": {"AAA": "Sacramento", "AA": "Richmond", "A": "Greenville"},
}


# Neutral park factors (fallback for unmapped parks)
NEUTRAL_PARK = {
    "H": 1.00, "2B": 1.00, "3B": 1.00, "HR": 1.00, "BB": 1.00, "K": 1.00, "R": 1.00,
}


def get_park_factors(team_id_or_abbrev, level: str) -> dict:
    """
    Get park factors for a team's affiliate at a given level.

    Args:
        team_id_or_abbrev: Either a team abbreviation (str) or team_id (int)
        level: One of 'AAA', 'AA', 'A', 'LOW'

    Returns:
        Dict with keys: H, 2B, 3B, HR, BB, K, R (all floats around 1.0)
    """
    from ..database.db import query as db_query

    # Convert team_id to abbreviation if needed
    if isinstance(team_id_or_abbrev, int):
        team = db_query("SELECT abbreviation FROM teams WHERE id=?", (team_id_or_abbrev,))
        if not team:
            return NEUTRAL_PARK.copy()
        abbrev = team[0]["abbreviation"]
    else:
        abbrev = team_id_or_abbrev

    # Normalize level
    level = level.upper()
    if level in ("LOW", "A+", "A-"):
        level = "A"

    # Look up affiliate park name
    affiliates = MLB_AFFILIATES.get(abbrev, {})
    park_name = affiliates.get(level)

    if not park_name:
        return NEUTRAL_PARK.copy()

    # Look up park factors
    level_parks = PARKS_BY_LEVEL.get(level, {})
    factors = level_parks.get(park_name)

    if not factors:
        return NEUTRAL_PARK.copy()

    return factors.copy()


def get_all_park_factors_for_level(level: str) -> dict:
    """Get all park factors for a given level. Returns dict of {park_name: factors}."""
    level = level.upper()
    if level in ("LOW", "A+", "A-"):
        level = "A"
    return PARKS_BY_LEVEL.get(level, {}).copy()
