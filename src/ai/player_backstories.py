"""
Front Office - Player Backstory Generator
Creates rich, immersive backstories for players using template-based randomization.
No LLM needed - carefully crafted templates produce unique narratives for every player.
"""
import random
import json
from ..database.db import query, execute, get_connection

# ============================================================
# DATA POOLS
# ============================================================

US_STATES = [
    "Alabama", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Florida", "Georgia", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas",
    "Kentucky", "Louisiana", "Maryland", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Jersey", "New Mexico",
    "New York", "North Carolina", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "South Carolina", "Tennessee", "Texas", "Utah", "Virginia", "Washington",
    "West Virginia", "Wisconsin",
]

HIGH_SCHOOLS = [
    "Central", "Lincoln", "Washington", "Jefferson", "Roosevelt", "Kennedy",
    "Heritage", "Riverside", "Valley", "Westlake", "Eastside", "Northview",
    "Southridge", "Oak Grove", "Pine Ridge", "Cedar Creek", "Eagle Mountain",
    "Falcon Ridge", "Mustang Valley", "Thunder Ridge", "Canyon View", "Lakewood",
    "Bayshore", "Hillcrest", "Stonewall", "Magnolia", "Palmetto", "Lone Star",
]

UNIVERSITIES = [
    "LSU", "Vanderbilt", "Florida", "Texas", "Stanford", "Miami",
    "Oregon State", "Virginia", "UCLA", "Arizona State", "Ole Miss",
    "Arkansas", "NC State", "TCU", "Wake Forest", "Tennessee",
    "Clemson", "Georgia", "South Carolina", "Mississippi State",
    "Cal State Fullerton", "Rice", "Long Beach State", "Coastal Carolina",
    "East Carolina", "Dallas Baptist", "Texas Tech", "Oklahoma State",
]

DR_CITIES = [
    "San Pedro de Macoris", "Santo Domingo", "Santiago", "La Romana",
    "San Cristobal", "Bani", "Azua", "Monte Cristi",
]

LATIN_COUNTRIES = {
    "Dominican Republic": DR_CITIES,
    "Venezuela": ["Maracaibo", "Valencia", "Caracas", "Barquisimeto", "Puerto La Cruz"],
    "Cuba": ["Havana", "Santiago de Cuba", "Cienfuegos", "Pinar del Rio"],
    "Puerto Rico": ["San Juan", "Caguas", "Bayamon", "Ponce", "Carolina"],
    "Panama": ["Panama City", "Colon", "David"],
    "Mexico": ["Culiacan", "Hermosillo", "Monterrey", "Guadalajara", "Mexico City"],
    "Colombia": ["Cartagena", "Barranquilla", "Bogota"],
    "Nicaragua": ["Managua", "Leon", "Chinandega"],
}

ASIAN_COUNTRIES = ["Japan", "South Korea", "Taiwan"]

FATHER_FIRST_NAMES = [
    "Miguel", "Carlos", "David", "James", "Robert", "Antonio", "Luis",
    "Jose", "Juan", "Pedro", "Rafael", "Ramon", "Victor", "Eduardo",
    "Roberto", "Daniel", "Michael", "Thomas", "William", "Richard",
]

COMP_PLAYERS_HITTER = [
    "Ken Griffey Jr.", "Mike Trout", "Albert Pujols", "Manny Ramirez",
    "Derek Jeter", "Alex Rodriguez", "Vladimir Guerrero", "Barry Bonds",
    "Chipper Jones", "Roberto Clemente", "George Brett", "Rod Carew",
    "Joe DiMaggio", "Hank Aaron", "Willie Mays", "Mickey Mantle",
    "Frank Robinson", "Ernie Banks", "Eddie Murray", "Tony Gwynn",
    "Cal Ripken Jr.", "Rickey Henderson", "Roberto Alomar", "Ichiro Suzuki",
]

COMP_PLAYERS_PITCHER = [
    "Pedro Martinez", "Greg Maddux", "Randy Johnson", "Roger Clemens",
    "Mariano Rivera", "Tom Seaver", "Sandy Koufax", "Nolan Ryan",
    "Bob Gibson", "Clayton Kershaw", "Justin Verlander", "Max Scherzer",
    "Johan Santana", "Roy Halladay", "John Smoltz", "Trevor Hoffman",
    "Dennis Eckersley", "Catfish Hunter", "Whitey Ford", "Jim Palmer",
]

# ============================================================
# ORIGIN STORY GENERATORS
# ============================================================

def _origin_small_town_usa(player):
    state = random.choice(US_STATES)
    hs = random.choice(HIGH_SCHOOLS)
    sport2 = random.choice(["football", "basketball", "track", "soccer"])
    return f"Grew up in a small town in {state}, where he was a three-sport athlete at {hs} High School. Baseball was always his first love, but his {sport2} coach still says he was the best player they ever had."


def _origin_college_walkon(player):
    univ = random.choice(UNIVERSITIES)
    return f"A walk-on at {univ}, {player['first_name']} wasn't even scouted until a bird-dog scout saw him crush BP pitches into the parking lot. By his junior year, he was the best player on the team."


def _origin_baseball_family(player):
    father = random.choice(FATHER_FIRST_NAMES)
    level = random.choice(["minor leaguer", "minor league journeyman", "Double-A standout", "Triple-A veteran"])
    return f"Son of former {level} {father} {player['last_name']}, baseball was in his blood from day one. He could hit a wiffle ball over the backyard fence by age four."


def _origin_converted_athlete(player):
    sport = random.choice(["quarterback", "wide receiver", "point guard", "soccer goalkeeper"])
    univ = random.choice(UNIVERSITIES)
    if player['position'] in ('SP', 'RP'):
        return f"Converted from {sport} to pitcher his junior year at {univ} after his arm strength caught the coaching staff's eye. His fastball touched 95 within six months of picking up a baseball full-time."
    else:
        return f"A former {sport} at {univ} who switched to baseball full-time after his raw athleticism made scouts drool. His speed and instincts translated immediately."


def _origin_latin_signee(player):
    country = player.get('birth_country', 'Dominican Republic')
    if country in LATIN_COUNTRIES:
        city = random.choice(LATIN_COUNTRIES[country])
    else:
        country = "Dominican Republic"
        city = random.choice(DR_CITIES)
    bonus = random.choice(["$50K", "$75K", "$125K", "$200K", "$500K", "$1.2M", "$2.5M"])
    age = random.choice([16, 16, 16, 17, 17])
    return f"Signed out of {country} at {age} for a {bonus} bonus after impressing at a showcase in {city}. He was raw but the tools were undeniable from the first swing."


def _origin_late_round_gem(player):
    rd = random.choice([15, 22, 28, 33, 38, 40])
    return f"A {rd}th-round pick that nobody expected to make it past A-ball. He proved every doubter wrong with a relentless work ethic and an innate feel for the game that can't be taught."


def _origin_consensus_pick(player):
    is_pit = player['position'] in ('SP', 'RP')
    comp = random.choice(COMP_PLAYERS_PITCHER if is_pit else COMP_PLAYERS_HITTER)
    univ = random.choice(UNIVERSITIES)
    return f"Consensus top pick who drew comparisons to {comp} from the moment he stepped on campus at {univ}. Scouts couldn't find a hole in his game if they tried."


def _origin_international_star(player):
    country = player.get('birth_country', 'Japan')
    if country in ASIAN_COUNTRIES:
        league = {"Japan": "NPB", "South Korea": "KBO", "Taiwan": "CPBL"}.get(country, "NPB")
        return f"Dominated {league} for five seasons before making the jump to the majors. The transition wasn't easy, but his talent was too obvious to ignore."
    return _origin_latin_signee(player)


def _origin_hometown_hero(player):
    state = random.choice(US_STATES)
    hs = random.choice(HIGH_SCHOOLS)
    return f"A local legend at {hs} High in {state}, where he still holds every hitting record in the book. The whole town packed the gym for his draft night, and the cheers could be heard three blocks away."


def _origin_late_bloomer(player):
    univ = random.choice(UNIVERSITIES)
    return f"Didn't start playing organized baseball until age 14. By the time he walked on at {univ}, coaches could see the raw tools hiding behind the late start. Some scouts say his ceiling is limitless precisely because he's still learning the game."


def _get_origin_story(player):
    """Select and generate an origin story based on player attributes."""
    is_latin = player.get('birth_country', 'USA') in LATIN_COUNTRIES
    is_asian = player.get('birth_country', 'USA') in ASIAN_COUNTRIES
    is_high_potential = _avg_potential(player) >= 65
    is_low_potential = _avg_potential(player) < 45
    is_late_bloomer_flag = player.get('is_late_bloomer', 0)

    # Build weighted pool based on player attributes
    pool = []
    if is_latin:
        pool += [_origin_latin_signee] * 5
        pool += [_origin_baseball_family] * 2
    elif is_asian:
        pool += [_origin_international_star] * 5
    else:
        pool += [_origin_small_town_usa] * 3
        pool += [_origin_college_walkon] * 2
        pool += [_origin_baseball_family] * 2
        pool += [_origin_converted_athlete] * 2
        pool += [_origin_hometown_hero] * 2

    if is_high_potential:
        pool += [_origin_consensus_pick] * 3
    if is_low_potential:
        pool += [_origin_late_round_gem] * 4
    if is_late_bloomer_flag:
        pool += [_origin_late_bloomer] * 4

    if not pool:
        pool = [_origin_small_town_usa, _origin_college_walkon, _origin_late_round_gem]

    return random.choice(pool)(player)


# ============================================================
# PERSONALITY QUIRK GENERATORS
# ============================================================

def _get_quirks(player):
    """Generate a list of personality quirks based on traits."""
    quirks = []

    ego = player.get('ego', 50)
    work_ethic = player.get('work_ethic', 50)
    leadership = player.get('leadership', 50)
    aggression = player.get('aggression', 50)
    clutch = player.get('clutch', 50)
    durability = player.get('durability', 50)
    composure = player.get('composure', 50)
    intelligence = player.get('intelligence', 50)
    sociability = player.get('sociability', 50)
    loyalty = player.get('loyalty', 50)
    greed = player.get('greed', 50)

    # High ego
    if ego >= 75:
        quirks.append(random.choice([
            "Known for his swagger and post-homer bat flips that drive opposing pitchers crazy",
            "Walks to the plate like he owns the stadium. Pitchers hate it. Fans love it",
            "Has been known to call his shots before stepping into the box",
            "His confidence borders on arrogance, but he backs it up between the lines",
        ]))
    elif ego <= 25:
        quirks.append(random.choice([
            "So humble that teammates have to remind him he's an All-Star caliber talent",
            "Deflects every compliment to his teammates. Reporters love him, agents despair",
            "Refuses to do post-game interviews unless the whole team wins",
        ]))

    # High work ethic
    if work_ethic >= 75:
        quirks.append(random.choice([
            "First one at the park, last one to leave. His teammates joke that he has a sleeping bag in the cage",
            "Takes 500 swings a day in the cage, rain or shine, January or July",
            "Studies film of opposing pitchers like a PhD student preparing a dissertation",
            "Groundskeepers have started leaving a key under the mat for his 5 AM sessions",
        ]))
    elif work_ethic <= 25:
        quirks.append(random.choice([
            "Relies almost entirely on natural talent. Coaches wish he'd put in extra work",
            "Has all the tools but doesn't always bring the toolbox to the park",
        ]))

    # High leadership
    if leadership >= 75:
        quirks.append(random.choice([
            "Runs the clubhouse meeting before every series. Veterans and rookies alike look up to him",
            "The unofficial captain. When he talks, the room goes silent",
            "Took the entire pitching staff out to dinner after a tough road trip. Picked up the tab",
            "Mentors every rookie who comes through the system. Three of his proteges are now starters",
        ]))

    # High aggression
    if aggression >= 75:
        quirks.append(random.choice([
            "Plays with an edge. Has been ejected 3 times this season and wouldn't have it any other way",
            "Slides hard into second base. Middle infielders have learned to get out of his way",
            "Once charged the mound after getting brushed back. The benches cleared but nobody wanted to fight him",
            "Breaks a bat over his knee after every strikeout. The equipment manager orders extras",
        ]))
    elif aggression <= 25:
        quirks.append(random.choice([
            "The calmest player in the dugout. Nothing rattles him, nothing fires him up",
            "Plays the game at his own pace. Steady as a metronome",
        ]))

    # Clutch
    if clutch >= 75:
        quirks.append(random.choice([
            "Something changes in his eyes in the 7th inning. Teammates call him 'Mr. October'",
            "Batting average goes up 80 points with runners in scoring position. Can't explain it, just feel it",
            "Lives for the big moment. His walk-off stats are the stuff of legend",
            "Two outs, runner on third, game on the line? That's when he's at his most dangerous",
        ]))
    elif clutch <= 25:
        quirks.append(random.choice([
            "Dominant in low-leverage spots but tends to tighten up when the game's on the line",
            "Numbers are great through six innings but the pressure gets to him late",
        ]))

    # Durability
    if durability <= 30:
        quirks.append(random.choice([
            "Talent has never been the question. It's whether his body can hold up for 162",
            "Made of glass according to the training staff. Made of gold according to the scouts",
            "His MRI folder is thicker than most team media guides",
            "When he's healthy, he's a top-10 player. The problem is staying healthy",
        ]))
    elif durability >= 80:
        quirks.append(random.choice([
            "Hasn't missed a game in three years. The training staff calls him 'The Machine'",
            "Built like a fire hydrant. Opposing runners bounce off him at home plate",
            "His body recovers overnight. Trainers have given up trying to explain it",
        ]))

    # Composure
    if composure >= 75:
        quirks.append(random.choice([
            "Ice water in his veins. Heart rate actually drops in high-pressure at-bats",
            "Handles the New York media circus like he's been doing it for 20 years",
        ]))

    # Intelligence
    if intelligence >= 75:
        quirks.append(random.choice([
            "Baseball IQ off the charts. Knows the opposing pitcher's tendencies better than the catcher",
            "Adjusts his approach mid-at-bat. Pitchers say it's like throwing to a computer",
            "Reads the game three pitches ahead. Teammates swear he can predict stolen base attempts",
        ]))

    # Low ego + high work ethic combo
    if ego <= 35 and work_ethic >= 65:
        quirks.append(random.choice([
            "Quiet lunch-pail type. Shows up, does his work, goes home",
            "You'd never know he was a professional athlete if you met him at the grocery store",
            "Blue-collar player in a white-collar game. Fans in the bleachers adore him",
        ]))

    # Sociability
    if sociability >= 80:
        quirks.append(random.choice([
            "The glue of the clubhouse. Organizes team poker nights and golf outings",
            "Knows every stadium worker by name. Tips the clubhouse attendants triple",
            "His locker is the social hub of the dugout. Even the coaches hang around",
        ]))
    elif sociability <= 25:
        quirks.append(random.choice([
            "A loner in the clubhouse. Puts his headphones on and disappears into his own world",
            "Eats alone, stretches alone, prepares alone. But between the lines, he's all team",
        ]))

    # Loyalty
    if loyalty >= 80:
        quirks.append(random.choice([
            "Has turned down bigger offers to stay put. Says he bleeds the team colors",
            "Told his agent he'd take a hometown discount before negotiations even started",
        ]))

    # Greed
    if greed >= 80:
        quirks.append(random.choice([
            "Has three agents and an accountant. Knows his market value down to the penny",
            "Once held out of spring training over a $500K difference. It's always about the money",
        ]))

    # Limit to 3-4 quirks max
    if len(quirks) > 4:
        quirks = random.sample(quirks, 4)
    elif len(quirks) == 0:
        quirks.append(random.choice([
            "A steady, reliable presence in the lineup. Nothing flashy, just consistently good",
            "Goes about his business without fanfare. The kind of player every team needs",
            "Teammates describe him as 'just a ballplayer.' He'd take that as a compliment",
        ]))

    return quirks


# ============================================================
# TOOL DESCRIPTIONS (based on ratings)
# ============================================================

def _get_tool_descriptions(player):
    """Generate vivid tool descriptions based on player ratings."""
    descriptions = []
    is_pit = player['position'] in ('SP', 'RP')

    if is_pit:
        stuff = player.get('stuff_rating', 20)
        control = player.get('control_rating', 20)
        stamina = player.get('stamina_rating', 20)

        if stuff >= 75:
            descriptions.append(random.choice([
                "Electric arm with a fastball that jumps out of his hand. Hitters describe it as 'invisible'",
                "His stuff is filthy. Batters look silly swinging at pitches that started in the zone and ended in another zip code",
                "Possesses a wipeout slider that has haunted hitters' nightmares from coast to coast",
            ]))
        elif stuff >= 60:
            descriptions.append(random.choice([
                "Solid arsenal with two plus pitches. Not unhittable, but tough to square up consistently",
                "Fastball sits 93-95 with late life. Gets plenty of swings and misses up in the zone",
            ]))

        if control >= 75:
            descriptions.append(random.choice([
                "Paints corners like Picasso. Can put a fastball on a nickel at 60 feet, 6 inches",
                "Pinpoint command. Walks are as rare as a no-hitter in his outings",
                "Commands all four quadrants of the zone. Hitters never get a pitch to drive",
            ]))
        elif control <= 35:
            descriptions.append(random.choice([
                "The stuff is tantalizing but the walks will drive you crazy. When he finds the zone, look out",
                "A six-inning pitcher trapped in a five-walk body. The potential is maddening",
            ]))

        if stamina >= 70:
            descriptions.append(random.choice([
                "A true workhorse. Can go deep into games without losing velocity",
                "Built to eat innings. His 100th pitch is as nasty as his first",
            ]))
    else:
        contact = player.get('contact_rating', 50)
        power = player.get('power_rating', 50)
        speed = player.get('speed_rating', 50)
        arm = player.get('arm_rating', 50)
        fielding = player.get('fielding_rating', 50)
        eye = player.get('eye_rating', 50)

        if contact >= 75:
            descriptions.append(random.choice([
                "Bat-to-ball skills that would make Tony Gwynn proud. Can hit a ball thrown behind a barn",
                "Rarely strikes out. Puts the barrel on everything and uses the whole field",
                "A hitting savant. His bat control is so precise that coaches use him as a demonstration for prospects",
            ]))
        elif contact >= 60:
            descriptions.append(random.choice([
                "Solid contact skills with an advanced approach. Rarely gives away an at-bat",
                "Compact swing that stays in the zone a long time. Gets his fair share of hits",
            ]))

        if power >= 75:
            descriptions.append(random.choice([
                "Raw power that registers on the Richter scale. Scouts clock his exit velocity at 110+",
                "When he connects, the ball sounds different. Outfielders don't even bother running",
                "30-homer power that plays in any ballpark. His batting practice sessions draw crowds",
            ]))
        elif power >= 60:
            descriptions.append(random.choice([
                "Sneaky pop. Doesn't look like a power hitter until the ball clears the wall in a hurry",
                "20-homer power with the potential for more as he learns to lift the ball",
            ]))

        if speed >= 75:
            descriptions.append(random.choice([
                "Wheels that would make Rickey Henderson take notice. Can go first-to-third on a bloop single",
                "Blazing speed that changes the game on the bases and in the outfield. A true game-changer",
                "A legitimate stolen base threat every time he reaches. Pitchers can't ignore him",
            ]))

        if arm >= 75 and player['position'] not in ('1B', 'DH'):
            descriptions.append(random.choice([
                "A cannon arm that once threw a runner out from the warning track on a frozen rope",
                "The kind of arm that makes runners think twice about taking the extra base",
                "Arm strength that scouts drool over. His throws from deep short look like line drives",
            ]))

        if fielding >= 75:
            descriptions.append(random.choice([
                "Gold Glove-caliber defender who makes the impossible look routine",
                "His range is absurd. Balls that should be hits die in his glove like they're magnetized",
                "A defensive wizard. Highlight-reel plays are just Tuesday for this guy",
            ]))

        if eye >= 75:
            descriptions.append(random.choice([
                "Elite plate discipline. Draws walks like other players draw breath",
                "Has an uncanny ability to lay off pitches just off the plate. Pitchers despise his patience",
            ]))

    # Limit to 2-3 tool descriptions
    if len(descriptions) > 3:
        descriptions = random.sample(descriptions, 3)

    return descriptions


# ============================================================
# NICKNAME GENERATOR
# ============================================================

def _generate_nickname(player):
    """Generate a fun nickname based on player profile."""
    is_pit = player['position'] in ('SP', 'RP')
    first = player['first_name']
    last = player['last_name']
    power = player.get('power_rating', 50)
    speed = player.get('speed_rating', 50)
    stuff = player.get('stuff_rating', 20)
    control = player.get('control_rating', 20)
    position = player['position']

    pool = []

    # Position-based
    if position == 'C':
        pool += ["The Wall", "The General", "Iron Mike", "The Backstop", "The Field Marshal"]
    elif position in ('SP', 'RP'):
        pool += [f"Filthy {first}", "The Doctor", "Lights Out", "The Freezer", "The Iceman"]
        if stuff >= 70:
            pool += ["Nasty", "Electric", "The Nightmare", f"{first} Heat"]
        if control >= 70:
            pool += ["The Surgeon", "Bullseye", "The Painter", "Pinpoint"]
        if position == 'RP':
            pool += ["The Door", "Lockdown", "The Eraser", "Shutdown"]

    # Power hitters
    if not is_pit and power >= 65:
        pool += ["The Hammer", "Big Stick", "Boom Boom", "The Masher", "Thunder",
                 f"Big {first}", "The Slugger", "Dynamite", "Hercules"]

    # Speed guys
    if not is_pit and speed >= 65:
        pool += ["Flash", "Wheels", "The Blur", "Jet", "Zoom", "Mercury",
                 "The Rocket", "Roadrunner", "Turbo"]

    # Name-based nicknames
    if len(last) > 5:
        pool.append(f"{last[:len(last)-2]}inator")
    pool.append(f"Big {first}")
    if last.endswith('s'):
        pool.append(f"{last[:-1]}y")
    elif last.endswith('n') or last.endswith('r'):
        pool.append(f"{last}s")

    # Short last name gets "The [Last Name]"
    if len(last) <= 5:
        pool.append(f"The {last}")

    # First initial + last name combos
    pool.append(f"{first[0]}-{last}")
    pool.append(f"{first[0]}.{last[0]}.")

    if not pool:
        pool = [f"Big {first}", f"The {last}"]

    return random.choice(pool)


# ============================================================
# POTENTIAL / CEILING DESCRIPTIONS
# ============================================================

def _avg_potential(player):
    """Calculate average potential for ceiling assessment."""
    is_pit = player['position'] in ('SP', 'RP')
    if is_pit:
        pots = [player.get('stuff_potential', 20), player.get('control_potential', 20),
                player.get('stamina_potential', 20)]
    else:
        pots = [player.get('contact_potential', 50), player.get('power_potential', 50),
                player.get('speed_potential', 50), player.get('fielding_potential', 50),
                player.get('arm_potential', 50)]
    return sum(pots) / len(pots) if pots else 50


def _avg_current(player):
    """Calculate average current rating."""
    is_pit = player['position'] in ('SP', 'RP')
    if is_pit:
        rats = [player.get('stuff_rating', 20), player.get('control_rating', 20),
                player.get('stamina_rating', 20)]
    else:
        rats = [player.get('contact_rating', 50), player.get('power_rating', 50),
                player.get('speed_rating', 50), player.get('fielding_rating', 50),
                player.get('arm_rating', 50)]
    return sum(rats) / len(rats) if rats else 50


def _get_potential_description(player):
    """Generate a scouting assessment of the player's ceiling."""
    avg_pot = _avg_potential(player)
    avg_cur = _avg_current(player)
    gap = avg_pot - avg_cur

    if avg_pot >= 70 and avg_cur >= 60:
        return random.choice([
            "Scouts believe the ceiling is a perennial All-Star. One evaluator said, 'This kid could be special.'",
            "The complete package. Multiple scouts have him pegged as a future franchise cornerstone.",
            "Every tool grades out as plus or better at peak. This is the kind of player you build a team around.",
        ])
    elif avg_pot >= 70 and avg_cur < 55:
        return random.choice([
            "The tools are tantalizing but raw. There's a world where this kid figures it out and becomes a star.",
            "Sky-high ceiling with a basement floor. The variance in his outcomes is extreme, but the upside is electric.",
            "A scout's dream and a manager's headache. The talent is undeniable but the consistency isn't there yet.",
        ])
    elif avg_pot >= 55 and avg_cur >= 50:
        return random.choice([
            "One of the safer bets in the organization. The floor is an everyday starter, the ceiling is an All-Star.",
            "Projects as a solid regular with upside. The kind of player who keeps your lineup honest.",
            "Won't set the world on fire, but he'll hold down a roster spot for a decade. Every contender needs a few of these.",
        ])
    elif avg_pot >= 55 and avg_cur < 45:
        return random.choice([
            "Still years away, but the raw tools flash. Patient organizations will be rewarded.",
            "A project, but the kind of project that makes player development departments look brilliant when it works.",
        ])
    elif avg_pot < 45:
        return random.choice([
            "A solid major leaguer who knows his role. Won't wow you, but won't embarrass you either.",
            "Organizational depth piece with a clear role. Every championship roster has a few of these guys.",
            "Not a star, but a professional. Does his job, cashes his check, and helps you win 85 games.",
        ])
    else:
        return random.choice([
            "Evaluators are split. Some see a starter, others see a useful bench piece. Time will tell.",
            "The tools say everyday player. The instincts say something more. Worth betting on.",
        ])


# ============================================================
# MAIN BACKSTORY GENERATOR
# ============================================================

def generate_backstory(player):
    """
    Generate a rich, immersive backstory for a player.
    Returns dict with backstory, nickname, quirks, origin_story.
    """
    # Seed RNG based on player ID for deterministic but unique results
    rng_seed = player.get('id', 0) * 7919 + hash(player.get('last_name', '')) % 10000
    random.seed(rng_seed)

    origin = _get_origin_story(player)
    quirks = _get_quirks(player)
    tools = _get_tool_descriptions(player)
    potential = _get_potential_description(player)
    nickname = _generate_nickname(player)

    # Assemble the full backstory (3-5 sentences)
    parts = [origin]

    # Add 1-2 tool descriptions
    if tools:
        parts.append(random.choice(tools) + ".")

    # Add potential assessment
    parts.append(potential)

    backstory = " ".join(parts)

    # Reset random seed
    random.seed()

    return {
        "backstory": backstory,
        "nickname": nickname,
        "quirks": json.dumps(quirks),
        "origin_story": origin,
    }


def generate_all_backstories(force=False):
    """
    Generate and store backstories for all players.
    If force=False, only generates for players without a backstory.
    Returns count of players updated.
    """
    conn = get_connection()
    try:
        if force:
            players = conn.execute(
                "SELECT * FROM players"
            ).fetchall()
        else:
            players = conn.execute(
                "SELECT * FROM players WHERE backstory IS NULL"
            ).fetchall()

        if not players:
            conn.close()
            return 0

        # Convert rows to dicts
        columns = [desc[0] for desc in conn.execute("SELECT * FROM players LIMIT 1").description]
        player_dicts = [dict(zip(columns, row)) for row in players]

        count = 0
        for p in player_dicts:
            result = generate_backstory(p)
            conn.execute(
                """UPDATE players SET backstory=?, nickname=?, quirks=?, origin_story=?
                   WHERE id=?""",
                (result['backstory'], result['nickname'], result['quirks'],
                 result['origin_story'], p['id'])
            )
            count += 1

        conn.commit()
        return count
    finally:
        conn.close()


def get_backstory_display(player):
    """
    Return formatted backstory data for UI display.
    """
    return {
        "backstory": player.get("backstory"),
        "nickname": player.get("nickname"),
        "quirks": json.loads(player.get("quirks") or "[]"),
        "origin_story": player.get("origin_story"),
    }
