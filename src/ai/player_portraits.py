"""
Front Office - Player Portrait Generator
Creates unique 8-bit style SVG player portraits based on player attributes.
Procedural pixel-art avatar generator - no AI/LLM needed.
Deterministic: same player_id always produces the same portrait.
"""
import random
from ..database.db import query, execute, get_connection


# ============================================================
# COLOR PALETTES (retro limited palette)
# ============================================================

SKIN_TONES = [
    "#FFDFC4",  # Light
    "#F0C8A0",  # Fair
    "#D4A574",  # Medium
    "#C68642",  # Tan
    "#8D5524",  # Brown
    "#5C3A1E",  # Dark brown
    "#704214",  # Deep tan
    "#E8B88A",  # Warm light
]

HAIR_COLORS = [
    "#1A1A1A",  # Black
    "#3D2314",  # Dark brown
    "#6B3A2A",  # Brown
    "#8B6914",  # Dark blonde
    "#C4A35A",  # Blonde
    "#D4691A",  # Red/Auburn
    "#808080",  # Gray (veteran)
    "#2C1A0E",  # Very dark brown
]

EYE_COLORS = [
    "#3D2B1F",  # Brown
    "#5B3A29",  # Hazel
    "#4682B4",  # Blue
    "#2E8B57",  # Green
    "#1A1A1A",  # Very dark
]

# Team colors by team_id (mapped to 30 MLB-style teams)
# Fallback palette for any team_id
TEAM_COLORS = {
    1: ("#C41E3A", "#0C2340"),   # Red / Navy
    2: ("#003831", "#EFB21E"),   # Green / Gold
    3: ("#BD3039", "#27251F"),   # Red / Black
    4: ("#DF4601", "#27251F"),   # Orange / Black
    5: ("#BD3039", "#0C2340"),   # Red / Navy
    6: ("#CC3433", "#0C2340"),   # Red / Navy
    7: ("#E31937", "#002D62"),   # Red / Blue
    8: ("#0C2340", "#B6922E"),   # Navy / Gold
    9: ("#002D62", "#E31937"),   # Blue / Red
    10: ("#0E3386", "#EF3E42"),  # Blue / Red
    11: ("#003263", "#FD5A1E"),  # Blue / Orange
    12: ("#005A9C", "#A71930"),  # Blue / Red
    13: ("#0C2C56", "#C4CED4"),  # Navy / Silver
    14: ("#134A8E", "#E8291C"),  # Blue / Red
    15: ("#27251F", "#FDB827"),  # Black / Gold
    16: ("#C41E3A", "#0C2340"),  # Red / Navy
    17: ("#E31937", "#14225A"),  # Red / Navy
    18: ("#12284B", "#005C5C"),  # Navy / Teal
    19: ("#003278", "#E4002B"),  # Blue / Red
    20: ("#002D72", "#FF5910"),  # Blue / Orange
    21: ("#AB0003", "#0C2340"),  # Maroon / Navy
    22: ("#E81828", "#002D62"),  # Red / Blue
    23: ("#FD5A1E", "#27251F"),  # Orange / Black
    24: ("#002D62", "#FDB827"),  # Navy / Gold
    25: ("#0C2340", "#8FBCE6"),  # Navy / Light blue
    26: ("#BD3039", "#0C2340"),  # Red / Navy
    27: ("#2F241D", "#E8D100"),  # Brown / Yellow
    28: ("#003DA5", "#C4CED4"),  # Blue / Silver
    29: ("#092C5C", "#002D62"),  # Navy / Blue
    30: ("#AB0003", "#14225A"),  # Red / Navy
}

# Skin tone tendency by region (uses birth_country)
COUNTRY_SKIN_WEIGHTS = {
    "USA": [0.20, 0.20, 0.15, 0.10, 0.10, 0.05, 0.10, 0.10],
    "Dominican Republic": [0.05, 0.10, 0.20, 0.25, 0.20, 0.10, 0.05, 0.05],
    "Venezuela": [0.10, 0.15, 0.20, 0.20, 0.15, 0.05, 0.10, 0.05],
    "Cuba": [0.10, 0.15, 0.20, 0.20, 0.15, 0.05, 0.10, 0.05],
    "Puerto Rico": [0.10, 0.15, 0.20, 0.20, 0.15, 0.05, 0.10, 0.05],
    "Mexico": [0.05, 0.15, 0.25, 0.20, 0.15, 0.05, 0.10, 0.05],
    "Japan": [0.25, 0.30, 0.20, 0.10, 0.02, 0.01, 0.02, 0.10],
    "South Korea": [0.25, 0.30, 0.20, 0.10, 0.02, 0.01, 0.02, 0.10],
    "Taiwan": [0.25, 0.30, 0.20, 0.10, 0.02, 0.01, 0.02, 0.10],
    "Colombia": [0.10, 0.15, 0.20, 0.20, 0.15, 0.05, 0.10, 0.05],
    "Panama": [0.05, 0.10, 0.15, 0.20, 0.25, 0.10, 0.10, 0.05],
    "Nicaragua": [0.10, 0.15, 0.20, 0.20, 0.15, 0.05, 0.10, 0.05],
    "Canada": [0.25, 0.20, 0.15, 0.10, 0.10, 0.05, 0.05, 0.10],
    "Australia": [0.25, 0.20, 0.15, 0.10, 0.10, 0.05, 0.05, 0.10],
}

DEFAULT_SKIN_WEIGHTS = [0.15, 0.15, 0.15, 0.15, 0.10, 0.10, 0.10, 0.10]

# Hair color weights by skin tone index (darker skin -> darker hair more likely)
HAIR_WEIGHTS_BY_SKIN = {
    0: [0.10, 0.10, 0.15, 0.20, 0.20, 0.15, 0.05, 0.05],  # Light skin: varied
    1: [0.10, 0.15, 0.20, 0.20, 0.15, 0.10, 0.05, 0.05],
    2: [0.25, 0.25, 0.20, 0.10, 0.05, 0.05, 0.05, 0.05],
    3: [0.30, 0.25, 0.20, 0.05, 0.02, 0.03, 0.05, 0.10],
    4: [0.40, 0.20, 0.15, 0.02, 0.01, 0.02, 0.05, 0.15],
    5: [0.45, 0.20, 0.10, 0.02, 0.01, 0.02, 0.05, 0.15],
    6: [0.35, 0.25, 0.15, 0.05, 0.02, 0.03, 0.05, 0.10],
    7: [0.15, 0.15, 0.20, 0.15, 0.15, 0.10, 0.05, 0.05],
}


# ============================================================
# HAIR STYLE DRAWING FUNCTIONS
# ============================================================

def _hair_buzz(rng, hair_color, skin_idx):
    """Buzz cut / very short."""
    return f'''<rect x="22" y="14" width="36" height="8" rx="4" fill="{hair_color}"/>
    <rect x="20" y="18" width="40" height="4" fill="{hair_color}"/>'''


def _hair_short(rng, hair_color, skin_idx):
    """Short cropped hair."""
    return f'''<rect x="20" y="12" width="40" height="12" rx="5" fill="{hair_color}"/>
    <rect x="18" y="18" width="44" height="6" fill="{hair_color}"/>'''


def _hair_medium(rng, hair_color, skin_idx):
    """Medium length hair."""
    return f'''<rect x="18" y="10" width="44" height="16" rx="6" fill="{hair_color}"/>
    <rect x="16" y="18" width="48" height="8" fill="{hair_color}"/>
    <rect x="16" y="26" width="6" height="8" fill="{hair_color}"/>
    <rect x="58" y="26" width="6" height="8" fill="{hair_color}"/>'''


def _hair_long(rng, hair_color, skin_idx):
    """Longer hair flowing down."""
    return f'''<rect x="18" y="10" width="44" height="16" rx="6" fill="{hair_color}"/>
    <rect x="14" y="18" width="52" height="8" fill="{hair_color}"/>
    <rect x="14" y="26" width="8" height="16" fill="{hair_color}"/>
    <rect x="58" y="26" width="8" height="16" fill="{hair_color}"/>'''


def _hair_flat_top(rng, hair_color, skin_idx):
    """Flat top style."""
    return f'''<rect x="20" y="8" width="40" height="6" fill="{hair_color}"/>
    <rect x="22" y="14" width="36" height="10" fill="{hair_color}"/>'''


def _hair_curly(rng, hair_color, skin_idx):
    """Curly/afro texture."""
    dots = ""
    for y in range(8, 22, 3):
        for x in range(18, 62, 4):
            if rng.random() > 0.25:
                dots += f'<rect x="{x}" y="{y}" width="3" height="3" rx="1" fill="{hair_color}"/>'
    return f'''<rect x="18" y="10" width="44" height="14" rx="7" fill="{hair_color}"/>
    {dots}'''


def _hair_mohawk(rng, hair_color, skin_idx):
    """Mohawk style."""
    return f'''<rect x="32" y="4" width="16" height="8" rx="2" fill="{hair_color}"/>
    <rect x="30" y="12" width="20" height="10" rx="3" fill="{hair_color}"/>'''


def _hair_parted(rng, hair_color, skin_idx):
    """Side-parted hair."""
    side = rng.choice(["left", "right"])
    if side == "left":
        return f'''<rect x="18" y="10" width="44" height="14" rx="5" fill="{hair_color}"/>
        <rect x="18" y="14" width="2" height="10" fill="{hair_color}" opacity="0.3"/>
        <rect x="30" y="10" width="2" height="6" fill="{hair_color}" opacity="0.5"/>'''
    else:
        return f'''<rect x="18" y="10" width="44" height="14" rx="5" fill="{hair_color}"/>
        <rect x="60" y="14" width="2" height="10" fill="{hair_color}" opacity="0.3"/>
        <rect x="48" y="10" width="2" height="6" fill="{hair_color}" opacity="0.5"/>'''


def _hair_receding(rng, hair_color, skin_idx):
    """Receding hairline."""
    return f'''<rect x="26" y="12" width="28" height="10" rx="4" fill="{hair_color}"/>
    <rect x="18" y="18" width="44" height="6" fill="{hair_color}"/>'''


def _hair_bald(rng, hair_color, skin_idx):
    """Bald / shaved head - no hair drawn, slight shine."""
    return f'''<ellipse cx="40" cy="20" rx="4" ry="2" fill="white" opacity="0.15"/>'''


HAIR_STYLES = [
    _hair_buzz, _hair_short, _hair_medium, _hair_long,
    _hair_flat_top, _hair_curly, _hair_mohawk, _hair_parted,
    _hair_receding, _hair_bald,
]


# ============================================================
# FACIAL FEATURE FUNCTIONS
# ============================================================

def _draw_eyes(rng, eye_color):
    """Draw pixel-art eyes."""
    style = rng.randint(0, 3)
    if style == 0:  # Round eyes
        return f'''<rect x="28" y="30" width="6" height="4" rx="2" fill="white"/>
        <rect x="46" y="30" width="6" height="4" rx="2" fill="white"/>
        <rect x="30" y="31" width="3" height="3" rx="1" fill="{eye_color}"/>
        <rect x="48" y="31" width="3" height="3" rx="1" fill="{eye_color}"/>'''
    elif style == 1:  # Narrow eyes
        return f'''<rect x="27" y="31" width="8" height="3" rx="1" fill="white"/>
        <rect x="45" y="31" width="8" height="3" rx="1" fill="white"/>
        <rect x="30" y="31" width="3" height="3" rx="1" fill="{eye_color}"/>
        <rect x="48" y="31" width="3" height="3" rx="1" fill="{eye_color}"/>'''
    elif style == 2:  # Wide eyes
        return f'''<rect x="26" y="29" width="8" height="5" rx="2" fill="white"/>
        <rect x="46" y="29" width="8" height="5" rx="2" fill="white"/>
        <rect x="29" y="30" width="4" height="4" rx="1" fill="{eye_color}"/>
        <rect x="49" y="30" width="4" height="4" rx="1" fill="{eye_color}"/>
        <rect x="30" y="31" width="2" height="2" fill="#111"/>
        <rect x="50" y="31" width="2" height="2" fill="#111"/>'''
    else:  # Determined eyes (intense)
        return f'''<rect x="26" y="29" width="9" height="5" rx="2" fill="white"/>
        <rect x="45" y="29" width="9" height="5" rx="2" fill="white"/>
        <rect x="29" y="30" width="4" height="3" rx="1" fill="{eye_color}"/>
        <rect x="48" y="30" width="4" height="3" rx="1" fill="{eye_color}"/>
        <rect x="26" y="28" width="9" height="2" rx="1" fill="#333" opacity="0.5"/>
        <rect x="45" y="28" width="9" height="2" rx="1" fill="#333" opacity="0.5"/>'''


def _draw_eyebrows(rng, hair_color):
    """Draw eyebrows."""
    thickness = rng.choice([1, 2, 2, 3])
    return f'''<rect x="27" y="{28 - thickness}" width="8" height="{thickness}" rx="1" fill="{hair_color}" opacity="0.8"/>
    <rect x="46" y="{28 - thickness}" width="8" height="{thickness}" rx="1" fill="{hair_color}" opacity="0.8"/>'''


def _draw_nose(rng, skin_color):
    """Draw a simple nose."""
    style = rng.randint(0, 2)
    # Darken skin slightly for nose shadow
    if style == 0:  # Small nose
        return f'''<rect x="38" y="35" width="4" height="4" rx="1" fill="{skin_color}" opacity="0.7"/>'''
    elif style == 1:  # Medium nose
        return f'''<rect x="37" y="34" width="6" height="5" rx="1" fill="{skin_color}" opacity="0.7"/>'''
    else:  # Wide nose
        return f'''<rect x="36" y="35" width="8" height="4" rx="2" fill="{skin_color}" opacity="0.7"/>'''


def _draw_mouth(rng):
    """Draw mouth."""
    style = rng.randint(0, 3)
    if style == 0:  # Neutral
        return '<rect x="35" y="42" width="10" height="2" rx="1" fill="#C0392B" opacity="0.7"/>'
    elif style == 1:  # Slight smile
        return '''<rect x="34" y="42" width="12" height="2" rx="1" fill="#C0392B" opacity="0.7"/>
        <rect x="33" y="41" width="2" height="2" rx="1" fill="#C0392B" opacity="0.5"/>
        <rect x="45" y="41" width="2" height="2" rx="1" fill="#C0392B" opacity="0.5"/>'''
    elif style == 2:  # Grin
        return '''<rect x="33" y="42" width="14" height="3" rx="1" fill="#C0392B" opacity="0.7"/>
        <rect x="35" y="42" width="10" height="2" fill="white" opacity="0.3"/>'''
    else:  # Serious
        return '<rect x="36" y="43" width="8" height="1" fill="#8B4513" opacity="0.6"/>'


def _draw_facial_hair(rng, hair_color, personality_ego, personality_work_ethic):
    """Conditionally draw facial hair based on personality traits."""
    # Use ego + work_ethic as seed for facial hair likelihood
    chance = (personality_ego + (100 - personality_work_ethic)) / 200.0
    if rng.random() > chance + 0.3:
        return ""

    style = rng.randint(0, 4)
    opacity = "0.6"
    if style == 0:  # Stubble
        dots = ""
        for y in range(44, 50, 2):
            for x in range(32, 48, 3):
                if rng.random() > 0.3:
                    dots += f'<rect x="{x}" y="{y}" width="1" height="1" fill="{hair_color}" opacity="0.4"/>'
        return dots
    elif style == 1:  # Goatee
        return f'''<rect x="36" y="44" width="8" height="4" rx="1" fill="{hair_color}" opacity="{opacity}"/>'''
    elif style == 2:  # Full beard
        return f'''<rect x="28" y="44" width="24" height="6" rx="3" fill="{hair_color}" opacity="{opacity}"/>
        <rect x="30" y="38" width="4" height="8" fill="{hair_color}" opacity="{opacity}"/>
        <rect x="46" y="38" width="4" height="8" fill="{hair_color}" opacity="{opacity}"/>'''
    elif style == 3:  # Mustache
        return f'''<rect x="33" y="40" width="14" height="3" rx="1" fill="{hair_color}" opacity="{opacity}"/>'''
    else:  # Chin strap
        return f'''<rect x="26" y="40" width="4" height="10" rx="1" fill="{hair_color}" opacity="{opacity}"/>
        <rect x="50" y="40" width="4" height="10" rx="1" fill="{hair_color}" opacity="{opacity}"/>
        <rect x="30" y="48" width="20" height="3" rx="1" fill="{hair_color}" opacity="{opacity}"/>'''


def _draw_glasses(rng):
    """Draw glasses (rare)."""
    return '''<rect x="24" y="28" width="12" height="8" rx="2" fill="none" stroke="#333" stroke-width="1.5"/>
    <rect x="44" y="28" width="12" height="8" rx="2" fill="none" stroke="#333" stroke-width="1.5"/>
    <line x1="36" y1="31" x2="44" y2="31" stroke="#333" stroke-width="1"/>
    <line x1="24" y1="31" x2="20" y2="30" stroke="#333" stroke-width="1"/>
    <line x1="56" y1="31" x2="60" y2="30" stroke="#333" stroke-width="1"/>'''


def _draw_ears(skin_color):
    """Draw simple ears."""
    return f'''<rect x="16" y="28" width="5" height="8" rx="2" fill="{skin_color}"/>
    <rect x="59" y="28" width="5" height="8" rx="2" fill="{skin_color}"/>'''


# ============================================================
# CAP / HELMET
# ============================================================

def _draw_cap(rng, primary_color, secondary_color):
    """Draw a baseball cap."""
    style = rng.randint(0, 1)
    if style == 0:  # Forward-facing cap
        return f'''<rect x="14" y="10" width="52" height="14" rx="6" fill="{primary_color}"/>
        <rect x="10" y="20" width="60" height="4" rx="1" fill="{primary_color}"/>
        <rect x="10" y="22" width="28" height="4" rx="1" fill="{primary_color}" opacity="0.8"/>
        <rect x="36" y="14" width="6" height="8" rx="1" fill="{secondary_color}"/>'''
    else:  # Helmet style
        return f'''<rect x="14" y="8" width="52" height="16" rx="8" fill="{primary_color}"/>
        <rect x="12" y="20" width="56" height="4" rx="1" fill="{primary_color}" opacity="0.9"/>
        <rect x="36" y="12" width="6" height="8" rx="1" fill="{secondary_color}"/>
        <ellipse cx="40" cy="12" rx="6" ry="2" fill="white" opacity="0.1"/>'''


# ============================================================
# JERSEY / BODY
# ============================================================

def _draw_jersey(rng, primary_color, secondary_color, jersey_number):
    """Draw jersey/body with number."""
    num_str = str(jersey_number)
    # Calculate text position based on number of digits
    if len(num_str) == 1:
        num_x = 36
    else:
        num_x = 32

    return f'''<rect x="18" y="54" width="44" height="30" rx="3" fill="{primary_color}"/>
    <rect x="18" y="54" width="44" height="4" fill="{secondary_color}"/>
    <rect x="10" y="56" width="14" height="22" rx="4" fill="{primary_color}"/>
    <rect x="56" y="56" width="14" height="22" rx="4" fill="{primary_color}"/>
    <text x="{num_x}" y="76" font-family="monospace" font-size="14" font-weight="bold"
          fill="{secondary_color}" stroke="white" stroke-width="0.5">{num_str}</text>
    <line x1="40" y1="54" x2="40" y2="58" stroke="{secondary_color}" stroke-width="2"/>'''


# ============================================================
# NECK
# ============================================================

def _draw_neck(skin_color):
    """Draw neck connecting head to body."""
    return f'''<rect x="34" y="48" width="12" height="8" fill="{skin_color}"/>'''


# ============================================================
# MAIN PORTRAIT GENERATOR
# ============================================================

def generate_portrait(player, db_path=None):
    """Generate a unique SVG portrait string for a player.

    Args:
        player: dict with player attributes (id, birth_country, ego, work_ethic, etc.)
        db_path: optional database path

    Returns:
        SVG string of the player portrait
    """
    pid = player.get("id", 0)
    rng = random.Random(pid)  # Deterministic seed

    # --- Pick skin tone ---
    country = player.get("birth_country", "USA") or "USA"
    skin_weights = COUNTRY_SKIN_WEIGHTS.get(country, DEFAULT_SKIN_WEIGHTS)
    skin_idx = rng.choices(range(len(SKIN_TONES)), weights=skin_weights, k=1)[0]
    skin_color = SKIN_TONES[skin_idx]

    # --- Pick hair ---
    hair_weights = HAIR_WEIGHTS_BY_SKIN.get(skin_idx, HAIR_WEIGHTS_BY_SKIN[0])
    hair_idx = rng.choices(range(len(HAIR_COLORS)), weights=hair_weights, k=1)[0]
    # Veterans (age > 35) may go gray
    age = player.get("age", 25)
    if age > 35 and rng.random() < (age - 35) * 0.15:
        hair_idx = 6  # Gray
    hair_color = HAIR_COLORS[hair_idx]

    # Pick hair style
    hair_style_fn = rng.choice(HAIR_STYLES)
    # Older players more likely to be bald/receding
    if age > 33 and rng.random() < 0.3:
        hair_style_fn = rng.choice([_hair_receding, _hair_bald, _hair_buzz])

    # --- Pick eye color ---
    eye_color = rng.choice(EYE_COLORS)

    # --- Team colors ---
    team_id = player.get("team_id")
    if team_id and team_id in TEAM_COLORS:
        primary_color, secondary_color = TEAM_COLORS[team_id]
    elif team_id:
        # Generate colors from team_id for unknown teams
        t_rng = random.Random(team_id * 7919)
        primary_color = f"#{t_rng.randint(0, 0xFFFFFF):06x}"
        secondary_color = f"#{t_rng.randint(0, 0xFFFFFF):06x}"
    else:
        # Free agent - gray jersey
        primary_color = "#555555"
        secondary_color = "#999999"

    # --- Jersey number ---
    jersey_number = pid % 99 + 1

    # --- Personality-driven features ---
    ego = player.get("ego", 50)
    work_ethic = player.get("work_ethic", 50)

    # Glasses: rare (based on eye_rating for the irony)
    eye_rating = player.get("eye_rating", 50)
    has_glasses = rng.random() < 0.06  # ~6% of players

    # --- Assemble SVG ---
    parts = []

    # Background
    parts.append('<rect width="80" height="100" fill="#2a2a3e" rx="4"/>')

    # Neck
    parts.append(_draw_neck(skin_color))

    # Jersey/body
    parts.append(_draw_jersey(rng, primary_color, secondary_color, jersey_number))

    # Head shape (oval)
    parts.append(f'<ellipse cx="40" cy="32" rx="20" ry="22" fill="{skin_color}"/>')

    # Ears
    parts.append(_draw_ears(skin_color))

    # Hair (behind cap for some styles, but cap goes on top)
    hair_svg = hair_style_fn(rng, hair_color, skin_idx)

    # Eyes
    parts.append(_draw_eyes(rng, eye_color))

    # Eyebrows
    parts.append(_draw_eyebrows(rng, hair_color))

    # Nose
    parts.append(_draw_nose(rng, skin_color))

    # Mouth
    parts.append(_draw_mouth(rng))

    # Facial hair
    parts.append(_draw_facial_hair(rng, hair_color, ego, work_ethic))

    # Glasses (if applicable)
    if has_glasses:
        parts.append(_draw_glasses(rng))

    # Cap/helmet (on top of head/hair)
    cap_svg = _draw_cap(rng, primary_color, secondary_color)
    parts.append(cap_svg)

    # Hair that peeks out from under cap
    # Only show hair below cap line for non-bald styles
    if hair_style_fn not in (_hair_bald,):
        # Show sideburns / hair peeking out
        parts.append(f'''<rect x="18" y="22" width="4" height="6" fill="{hair_color}" opacity="0.7"/>
        <rect x="58" y="22" width="4" height="6" fill="{hair_color}" opacity="0.7"/>''')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 100" width="80" height="100">
  <defs>
    <style>text {{ font-family: monospace; }}</style>
  </defs>
  {''.join(parts)}
</svg>'''

    return svg


def generate_all_portraits(db_path=None):
    """Generate portraits for all players that don't have one yet.

    Returns:
        int: number of portraits generated
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Ensure portrait column exists
    cursor.execute("PRAGMA table_info(players)")
    columns = {row[1] for row in cursor.fetchall()}
    if "portrait" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN portrait TEXT DEFAULT NULL")
        conn.commit()

    # Get all players missing portraits
    players = conn.execute(
        "SELECT * FROM players WHERE portrait IS NULL"
    ).fetchall()
    players = [dict(p) for p in players]

    count = 0
    for player in players:
        svg = generate_portrait(player, db_path)
        conn.execute(
            "UPDATE players SET portrait = ? WHERE id = ?",
            (svg, player["id"])
        )
        count += 1

    conn.commit()
    conn.close()
    return count


def get_portrait(player_id, db_path=None):
    """Get stored SVG portrait for a player.

    Args:
        player_id: the player's ID

    Returns:
        SVG string or None if no portrait exists
    """
    rows = query(
        "SELECT portrait FROM players WHERE id = ?",
        (player_id,),
        db_path
    )
    if rows and rows[0].get("portrait"):
        return rows[0]["portrait"]
    return None


def regenerate_portrait(player_id, db_path=None):
    """Regenerate portrait for a specific player (e.g., after a trade changes team).

    Returns:
        SVG string of the new portrait
    """
    rows = query("SELECT * FROM players WHERE id = ?", (player_id,), db_path)
    if not rows:
        return None

    svg = generate_portrait(rows[0], db_path)
    execute(
        "UPDATE players SET portrait = ? WHERE id = ?",
        (svg, player_id),
        db_path
    )
    return svg
