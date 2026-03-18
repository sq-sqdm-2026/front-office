"""
Front Office - Character Career Arcs
Dynamic career progression for NPC characters: scouts become GMs,
fired GMs become TV analysts, agents retire into front offices.
"""
import json
import random
from datetime import date
from ..database.db import query, execute, get_connection


# ============================================================
# CAREER PATH DEFINITIONS
# ============================================================
CAREER_PATHS = {
    "scouting": {
        "name": "Scouting Track",
        "progression": ["Scout", "Senior Scout", "Scouting Director", "Assistant GM", "GM"],
        "fired_options": ["TV Analyst", "Front Office Consultant", "Scout"],
    },
    "coaching": {
        "name": "Coaching Track",
        "progression": ["Minor League Manager", "Major League Coach", "Bench Coach", "Manager"],
        "fired_options": ["TV Analyst", "Minor League Manager", "Front Office Consultant"],
    },
    "media": {
        "name": "Media Track",
        "progression": ["Beat Writer", "National Writer", "Podcast Host", "TV Analyst"],
        "fired_options": ["Beat Writer", "Podcast Host"],
    },
    "agent": {
        "name": "Agent Track",
        "progression": ["Junior Agent", "Agent", "Super Agent"],
        "retired_options": ["Front Office Executive", "TV Analyst", "Front Office Consultant"],
    },
}

# Personality trait templates for character generation
PERSONALITY_TRAITS = [
    "analytical", "old_school", "fiery", "calm", "charismatic",
    "stubborn", "innovative", "risk_taker", "conservative", "media_savvy",
    "player_friendly", "demanding", "loyal", "political", "visionary",
]

NETWORKS = ["ESPN", "MLB Network", "Fox Sports", "TBS", "CBS Sports"]
SHOW_NAMES = [
    "Baseball Tonight", "MLB Now", "Hot Stove", "The Diamond Report",
    "Hardball Talk", "The Dugout", "Inside Baseball", "Around the Horn",
]


# ============================================================
# TABLE CREATION
# ============================================================
def ensure_career_tables(db_path: str = None):
    """Create the character_careers table if it doesn't exist."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS character_careers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id TEXT NOT NULL,
            character_type TEXT NOT NULL,
            name TEXT NOT NULL,
            current_role TEXT NOT NULL,
            current_team_id INTEGER,
            reputation INTEGER NOT NULL DEFAULT 50,
            personality_json TEXT NOT NULL DEFAULT '{}',
            career_history_json TEXT NOT NULL DEFAULT '[]',
            created_date TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            FOREIGN KEY (current_team_id) REFERENCES teams(id)
        );
        CREATE INDEX IF NOT EXISTS idx_character_careers_type
            ON character_careers(character_type);
        CREATE INDEX IF NOT EXISTS idx_character_careers_team
            ON character_careers(current_team_id);
        CREATE INDEX IF NOT EXISTS idx_character_careers_role
            ON character_careers(current_role);
    """)
    conn.commit()
    conn.close()


# ============================================================
# CHARACTER CAREER CLASS
# ============================================================
class CharacterCareer:
    """Represents an NPC character with a dynamic career arc."""

    def __init__(self, id=None, character_id=None, character_type="scouting",
                 name="", current_role="Scout", current_team_id=None,
                 reputation=50, personality=None, career_history=None,
                 created_date=None, last_updated=None):
        self.id = id
        self.character_id = character_id or f"{character_type}_{random.randint(1000, 9999)}"
        self.character_type = character_type
        self.name = name
        self.current_role = current_role
        self.current_team_id = current_team_id
        self.reputation = max(0, min(100, reputation))
        self.personality = personality or self._generate_personality()
        self.career_history = career_history or []
        self.created_date = created_date or date.today().isoformat()
        self.last_updated = last_updated or date.today().isoformat()

    def _generate_personality(self) -> dict:
        traits = random.sample(PERSONALITY_TRAITS, 3)
        return {
            "primary_trait": traits[0],
            "secondary_trait": traits[1],
            "hidden_trait": traits[2],
            "ambition": random.randint(30, 90),
            "patience": random.randint(20, 80),
            "media_comfort": random.randint(20, 90),
        }

    def add_history_entry(self, role: str, team_id: int = None,
                          season: int = None, reason: str = ""):
        entry = {
            "role": role,
            "team_id": team_id,
            "season": season,
            "reason": reason,
            "date": date.today().isoformat(),
        }
        self.career_history.append(entry)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "character_id": self.character_id,
            "character_type": self.character_type,
            "name": self.name,
            "current_role": self.current_role,
            "current_team_id": self.current_team_id,
            "reputation": self.reputation,
            "personality": self.personality,
            "career_history": self.career_history,
            "created_date": self.created_date,
            "last_updated": self.last_updated,
        }

    def save(self, db_path: str = None):
        """Save or update this character in the database."""
        ensure_career_tables(db_path)
        now = date.today().isoformat()
        self.last_updated = now

        if self.id:
            execute("""
                UPDATE character_careers
                SET current_role=?, current_team_id=?, reputation=?,
                    personality_json=?, career_history_json=?, last_updated=?
                WHERE id=?
            """, (
                self.current_role, self.current_team_id, self.reputation,
                json.dumps(self.personality), json.dumps(self.career_history),
                now, self.id,
            ), db_path=db_path)
            return self.id
        else:
            self.id = execute("""
                INSERT INTO character_careers
                (character_id, character_type, name, current_role, current_team_id,
                 reputation, personality_json, career_history_json, created_date, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.character_id, self.character_type, self.name,
                self.current_role, self.current_team_id, self.reputation,
                json.dumps(self.personality), json.dumps(self.career_history),
                self.created_date, now,
            ), db_path=db_path)
            return self.id

    @classmethod
    def from_row(cls, row: dict) -> "CharacterCareer":
        return cls(
            id=row["id"],
            character_id=row["character_id"],
            character_type=row["character_type"],
            name=row["name"],
            current_role=row["current_role"],
            current_team_id=row.get("current_team_id"),
            reputation=row["reputation"],
            personality=json.loads(row.get("personality_json", "{}")),
            career_history=json.loads(row.get("career_history_json", "[]")),
            created_date=row.get("created_date", ""),
            last_updated=row.get("last_updated", ""),
        )


# ============================================================
# CORE FUNCTIONS
# ============================================================

def _get_career_path(character_type: str) -> dict:
    """Get career path definition for a character type."""
    return CAREER_PATHS.get(character_type, CAREER_PATHS["scouting"])


def _next_role(character_type: str, current_role: str) -> str | None:
    """Get the next promotion role, or None if at top."""
    path = _get_career_path(character_type)
    progression = path["progression"]
    if current_role in progression:
        idx = progression.index(current_role)
        if idx < len(progression) - 1:
            return progression[idx + 1]
    return None


def _fired_role(character_type: str) -> str:
    """Get a role for a fired character."""
    path = _get_career_path(character_type)
    options = path.get("fired_options", ["TV Analyst"])
    return random.choice(options)


def _retired_role(character_type: str) -> str:
    """Get a role for a retiring character."""
    path = _get_career_path(character_type)
    options = path.get("retired_options", ["Front Office Consultant"])
    return random.choice(options)


def get_all_characters(db_path: str = None) -> list[dict]:
    """Get all tracked characters with current roles."""
    ensure_career_tables(db_path)
    rows = query("""
        SELECT cc.*, t.city, t.name as team_name
        FROM character_careers cc
        LEFT JOIN teams t ON cc.current_team_id = t.id
        ORDER BY cc.character_type, cc.reputation DESC
    """, db_path=db_path)
    results = []
    for row in rows:
        char = CharacterCareer.from_row(row)
        d = char.to_dict()
        d["team_city"] = row.get("city")
        d["team_name"] = row.get("team_name")
        results.append(d)
    return results


def get_character_history(character_id: int, db_path: str = None) -> dict | None:
    """Return full career timeline for a character by DB id."""
    ensure_career_tables(db_path)
    rows = query("SELECT * FROM character_careers WHERE id=?", (character_id,), db_path=db_path)
    if not rows:
        return None
    char = CharacterCareer.from_row(rows[0])
    result = char.to_dict()

    # Enrich history entries with team names
    if char.career_history:
        team_ids = {e.get("team_id") for e in char.career_history if e.get("team_id")}
        if team_ids:
            placeholders = ",".join("?" * len(team_ids))
            teams = query(
                f"SELECT id, city, name FROM teams WHERE id IN ({placeholders})",
                tuple(team_ids), db_path=db_path,
            )
            team_map = {t["id"]: f"{t['city']} {t['name']}" for t in teams}
            for entry in result["career_history"]:
                tid = entry.get("team_id")
                if tid and tid in team_map:
                    entry["team_name"] = team_map[tid]

    return result


def generate_career_narrative(character_id: int, db_path: str = None) -> str:
    """Create a text description of a character's career journey."""
    ensure_career_tables(db_path)
    char_data = get_character_history(character_id, db_path)
    if not char_data:
        return "Character not found."

    name = char_data["name"]
    role = char_data["current_role"]
    rep = char_data["reputation"]
    personality = char_data.get("personality", {})
    history = char_data.get("career_history", [])

    # Build narrative
    parts = []
    primary_trait = personality.get("primary_trait", "experienced")
    parts.append(f"{name} is a {primary_trait} {role.lower()}")

    if rep >= 80:
        parts[0] += " widely regarded as one of the best in the business."
    elif rep >= 60:
        parts[0] += " with a solid reputation around the league."
    elif rep >= 40:
        parts[0] += " still building a name in professional baseball."
    else:
        parts[0] += " looking to rebuild credibility after some setbacks."

    if history:
        parts.append(f"Over a career spanning {len(history)} role changes,")
        roles_held = [e["role"] for e in history]
        unique_roles = list(dict.fromkeys(roles_held))  # preserve order, dedupe
        if len(unique_roles) > 1:
            parts[-1] += f" {name} has served as {', '.join(unique_roles[:-1])}"
            parts[-1] += f" and {unique_roles[-1]}."
        else:
            parts[-1] += f" {name} has served as {unique_roles[0]}."

        # Check for firings
        firings = [e for e in history if "fired" in e.get("reason", "").lower()]
        if firings:
            parts.append(
                f"After being let go, {name} reinvented themselves and"
                f" found new purpose as a {role.lower()}."
            )

        # Check for promotions
        promotions = [e for e in history if "promot" in e.get("reason", "").lower()]
        if promotions:
            parts.append(
                f"Known for a strong work ethic, {name} earned"
                f" {len(promotions)} promotion{'s' if len(promotions) > 1 else ''}"
                f" through the ranks."
            )

    ambition = personality.get("ambition", 50)
    if ambition > 70:
        parts.append(f"Colleagues note {name}'s relentless drive to reach the top.")
    elif ambition < 30:
        parts.append(f"{name} is content to master the current role without chasing titles.")

    return " ".join(parts)


# ============================================================
# CAREER CHANGE OPERATIONS
# ============================================================

def fire_gm(team_id: int, db_path: str = None) -> dict:
    """
    Fire a team's GM and create a TV analyst character from them.
    Returns dict with details of the firing and new role.
    """
    ensure_career_tables(db_path)

    # Get the GM from gm_characters
    gms = query("SELECT * FROM gm_characters WHERE team_id=?", (team_id,), db_path=db_path)
    if not gms:
        return {"success": False, "error": f"No GM found for team {team_id}"}
    gm = gms[0]
    gm_name = f"{gm['first_name']} {gm['last_name']}"

    # Get team info
    teams = query("SELECT city, name FROM teams WHERE id=?", (team_id,), db_path=db_path)
    team_label = f"{teams[0]['city']} {teams[0]['name']}" if teams else f"Team {team_id}"

    # Get the game state for season
    state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
    season = state[0]["season"] if state else 2026

    # Check if character already exists in career tracking
    existing = query(
        "SELECT * FROM character_careers WHERE name=? AND character_type='scouting'",
        (gm_name,), db_path=db_path,
    )

    new_role = _fired_role("scouting")

    if existing:
        char = CharacterCareer.from_row(existing[0])
        char.add_history_entry(
            role=char.current_role, team_id=team_id,
            season=season, reason=f"Fired as GM of {team_label}",
        )
        char.current_role = new_role
        char.current_team_id = None
        char.reputation = max(0, char.reputation - random.randint(5, 15))
    else:
        # Create new career character from existing GM
        personality_data = json.loads(gm.get("personality_json", "{}"))
        char = CharacterCareer(
            character_type="scouting",
            name=gm_name,
            current_role=new_role,
            current_team_id=None,
            reputation=max(20, gm.get("competence", 50) - random.randint(0, 10)),
            personality={
                "primary_trait": gm.get("philosophy", "balanced"),
                "secondary_trait": gm.get("negotiation_style", "fair"),
                "hidden_trait": random.choice(PERSONALITY_TRAITS),
                "ambition": min(100, gm.get("ego", 50) + 10),
                "patience": gm.get("patience", 50),
                "media_comfort": random.randint(40, 80),
                **personality_data,
            },
        )
        char.add_history_entry(
            role="GM", team_id=team_id,
            season=season, reason=f"Fired as GM of {team_label}",
        )
        char.current_role = new_role

    char.save(db_path)

    # If becoming a TV Analyst, also insert into tv_analysts table
    if new_role == "TV Analyst":
        _create_tv_analyst_from_character(char, f"Former GM of {team_label}", db_path)

    return {
        "success": True,
        "character_id": char.id,
        "name": gm_name,
        "previous_role": "GM",
        "previous_team": team_label,
        "new_role": new_role,
        "reputation": char.reputation,
    }


def promote_scout(scout_id: int, to_role: str = None, db_path: str = None) -> dict:
    """Promote a scout (or any character) to the next role in their career path."""
    ensure_career_tables(db_path)

    rows = query("SELECT * FROM character_careers WHERE id=?", (scout_id,), db_path=db_path)
    if not rows:
        return {"success": False, "error": f"Character {scout_id} not found"}

    char = CharacterCareer.from_row(rows[0])
    old_role = char.current_role

    # Determine target role
    if to_role:
        target_role = to_role
    else:
        target_role = _next_role(char.character_type, char.current_role)
        if not target_role:
            return {
                "success": False,
                "error": f"{char.name} is already at the top of the {char.character_type} track ({char.current_role})",
            }

    state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
    season = state[0]["season"] if state else 2026

    char.add_history_entry(
        role=old_role, team_id=char.current_team_id,
        season=season, reason=f"Promoted from {old_role} to {target_role}",
    )
    char.current_role = target_role
    char.reputation = min(100, char.reputation + random.randint(3, 10))
    char.save(db_path)

    return {
        "success": True,
        "character_id": char.id,
        "name": char.name,
        "previous_role": old_role,
        "new_role": target_role,
        "reputation": char.reputation,
    }


def _create_tv_analyst_from_character(char: CharacterCareer, origin: str,
                                       db_path: str = None):
    """Insert a row into tv_analysts from a career character."""
    network = random.choice(NETWORKS)
    show = random.choice(SHOW_NAMES)
    personality_trait = char.personality.get("primary_trait", "balanced")
    analyst_type = "former_gm" if "GM" in origin else "commentator"

    # Map personality traits to tv analyst personalities
    trait_map = {
        "analytical": "stat_nerd",
        "old_school": "old_school",
        "fiery": "provocateur",
        "charismatic": "balanced",
        "stubborn": "contrarian",
        "innovative": "stat_nerd",
        "conservative": "old_school",
        "media_savvy": "balanced",
    }
    tv_personality = trait_map.get(personality_trait, "balanced")

    execute("""
        INSERT INTO tv_analysts
        (name, network, show_name, analyst_type, origin, personality,
         credibility, hot_take_tendency, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        char.name, network, show, analyst_type, origin,
        tv_personality, max(30, char.reputation), round(random.uniform(0.2, 0.6), 2),
    ), db_path=db_path)


# ============================================================
# END-OF-SEASON PROCESSING
# ============================================================

def process_career_changes(game_date: str, db_path: str = None) -> dict:
    """
    Process end-of-season career changes for all NPC characters.
    Called at the end of each season during offseason processing.

    - Evaluates GM performance -> fires underperformers
    - Promotes successful scouts
    - Fires losing managers
    - Retires veteran agents
    - Advances media careers
    """
    ensure_career_tables(db_path)

    state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
    season = state[0]["season"] if state else 2026
    results = {
        "season": season,
        "date": game_date,
        "firings": [],
        "promotions": [],
        "retirements": [],
        "new_roles": [],
    }

    # 1. Evaluate GMs - fire those with bad records and low job security
    _process_gm_firings(season, results, db_path)

    # 2. Evaluate managers - fire those with losing records
    _process_manager_firings(season, results, db_path)

    # 3. Promote high-reputation scouts/characters
    _process_promotions(season, results, db_path)

    # 4. Retire aging agents
    _process_agent_retirements(season, results, db_path)

    # 5. Advance media careers
    _process_media_careers(season, results, db_path)

    return results


def _process_gm_firings(season: int, results: dict, db_path: str = None):
    """Fire GMs with low job security or bad records."""
    # Check gm_job_security if available
    security_rows = query("""
        SELECT gjs.team_id, gjs.security_score, gjs.consecutive_losing_seasons
        FROM gm_job_security gjs
        WHERE gjs.security_score < 25
    """, db_path=db_path)

    for row in security_rows:
        team_id = row["team_id"]
        result = fire_gm(team_id, db_path)
        if result.get("success"):
            results["firings"].append(result)

    # Also check teams with very bad records that might not have job security tracked
    season_records = query("""
        SELECT sh.team_id, sh.wins, sh.losses
        FROM season_history sh
        WHERE sh.season = ? AND sh.wins < 55
        ORDER BY sh.wins ASC
        LIMIT 3
    """, (season,), db_path=db_path)

    for row in season_records:
        team_id = row["team_id"]
        # Only fire if not already fired this cycle
        already_fired = any(
            f.get("previous_team", "").endswith(str(team_id)) or
            f.get("character_id") == team_id
            for f in results["firings"]
        )
        if already_fired:
            continue
        # Random chance based on how bad the record is
        win_pct = row["wins"] / max(1, row["wins"] + row["losses"])
        if win_pct < 0.35 or (win_pct < 0.43 and random.random() < 0.4):
            result = fire_gm(team_id, db_path)
            if result.get("success"):
                results["firings"].append(result)


def _process_manager_firings(season: int, results: dict, db_path: str = None):
    """Fire managers of teams with bad records."""
    # Look at coaching_staff for managers
    managers = query("""
        SELECT cs.id, cs.team_id, cs.first_name, cs.last_name,
               sh.wins, sh.losses
        FROM coaching_staff cs
        LEFT JOIN season_history sh ON cs.team_id = sh.team_id AND sh.season = ?
        WHERE cs.role = 'manager'
    """, (season,), db_path=db_path)

    for mgr in managers:
        wins = mgr.get("wins") or 0
        losses = mgr.get("losses") or 0
        if wins + losses == 0:
            continue

        win_pct = wins / (wins + losses)
        mgr_name = f"{mgr['first_name']} {mgr['last_name']}"

        # Fire managers with really bad records
        if win_pct < 0.38 or (win_pct < 0.43 and random.random() < 0.3):
            # Track in career system
            existing = query(
                "SELECT * FROM character_careers WHERE name=? AND character_type='coaching'",
                (mgr_name,), db_path=db_path,
            )

            new_role = _fired_role("coaching")

            if existing:
                char = CharacterCareer.from_row(existing[0])
            else:
                char = CharacterCareer(
                    character_type="coaching",
                    name=mgr_name,
                    current_role="Manager",
                    current_team_id=mgr["team_id"],
                    reputation=max(20, mgr.get("skill_rating", 50) - 10),
                )

            teams = query("SELECT city, name FROM teams WHERE id=?",
                          (mgr["team_id"],), db_path=db_path)
            team_label = f"{teams[0]['city']} {teams[0]['name']}" if teams else "their team"

            char.add_history_entry(
                role="Manager", team_id=mgr["team_id"],
                season=season,
                reason=f"Fired as manager of {team_label} ({wins}-{losses})",
            )
            char.current_role = new_role
            char.current_team_id = None
            char.reputation = max(0, char.reputation - random.randint(5, 12))
            char.save(db_path)

            if new_role == "TV Analyst":
                _create_tv_analyst_from_character(
                    char, f"Former manager of {team_label}", db_path,
                )

            results["firings"].append({
                "character_id": char.id,
                "name": mgr_name,
                "previous_role": "Manager",
                "previous_team": team_label,
                "new_role": new_role,
                "record": f"{wins}-{losses}",
            })


def _process_promotions(season: int, results: dict, db_path: str = None):
    """Promote high-reputation characters up their career track."""
    characters = query("""
        SELECT * FROM character_careers
        WHERE reputation >= 65
        ORDER BY reputation DESC
    """, db_path=db_path)

    for row in characters:
        char = CharacterCareer.from_row(row)
        next_role = _next_role(char.character_type, char.current_role)
        if not next_role:
            continue

        # Promotion chance based on reputation
        promo_chance = (char.reputation - 50) / 100.0
        if random.random() < promo_chance:
            old_role = char.current_role
            char.add_history_entry(
                role=old_role, team_id=char.current_team_id,
                season=season, reason=f"Promoted from {old_role} to {next_role}",
            )
            char.current_role = next_role
            char.reputation = min(100, char.reputation + random.randint(2, 8))
            char.save(db_path)

            results["promotions"].append({
                "character_id": char.id,
                "name": char.name,
                "previous_role": old_role,
                "new_role": next_role,
                "reputation": char.reputation,
            })


def _process_agent_retirements(season: int, results: dict, db_path: str = None):
    """Retire veteran agents and transition them to front office roles."""
    # Check agents from agent_characters table
    agents = query("""
        SELECT * FROM agent_characters
        WHERE reputation >= 75
    """, db_path=db_path)

    for agent in agents:
        # Small chance experienced agents retire each year
        if random.random() > 0.1:
            continue

        agent_name = agent["name"]
        new_role = _retired_role("agent")

        # Check if already tracked
        existing = query(
            "SELECT * FROM character_careers WHERE name=? AND character_type='agent'",
            (agent_name,), db_path=db_path,
        )

        if existing:
            char = CharacterCareer.from_row(existing[0])
        else:
            char = CharacterCareer(
                character_type="agent",
                name=agent_name,
                current_role="Super Agent",
                reputation=agent.get("reputation", 70),
                personality={
                    "primary_trait": agent.get("personality", "collaborative"),
                    "secondary_trait": agent.get("negotiation_style", "fair"),
                    "hidden_trait": random.choice(PERSONALITY_TRAITS),
                    "ambition": 60,
                    "patience": agent.get("patience", 50),
                    "media_comfort": 60,
                },
            )

        char.add_history_entry(
            role=char.current_role, season=season,
            reason=f"Retired from agenting, became {new_role}",
        )
        char.current_role = new_role
        char.save(db_path)

        if new_role == "TV Analyst":
            _create_tv_analyst_from_character(
                char, f"Former super agent ({agent.get('agency_name', 'Independent')})",
                db_path,
            )

        results["retirements"].append({
            "character_id": char.id,
            "name": agent_name,
            "previous_role": "Super Agent",
            "new_role": new_role,
            "reputation": char.reputation,
        })


def _process_media_careers(season: int, results: dict, db_path: str = None):
    """Advance media career characters along the media track."""
    media_chars = query("""
        SELECT * FROM character_careers
        WHERE character_type = 'media'
        AND reputation >= 55
    """, db_path=db_path)

    for row in media_chars:
        char = CharacterCareer.from_row(row)
        next_role = _next_role("media", char.current_role)
        if not next_role:
            continue

        # Media careers advance more slowly
        promo_chance = (char.reputation - 40) / 200.0
        if random.random() < promo_chance:
            old_role = char.current_role
            char.add_history_entry(
                role=old_role, season=season,
                reason=f"Advanced from {old_role} to {next_role}",
            )
            char.current_role = next_role
            char.reputation = min(100, char.reputation + random.randint(3, 8))
            char.save(db_path)

            if next_role == "TV Analyst":
                _create_tv_analyst_from_character(
                    char, f"Former {old_role.lower()}", db_path,
                )

            results["new_roles"].append({
                "character_id": char.id,
                "name": char.name,
                "previous_role": old_role,
                "new_role": next_role,
                "reputation": char.reputation,
            })
