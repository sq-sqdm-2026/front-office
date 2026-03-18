"""
Front Office - Agent Characters (Phase 2)
Player agents with distinct negotiation personalities who represent players
in contract talks, free agency, and extensions.

Each agent has a personality archetype that affects:
- Salary demands (greed_factor)
- Bluffing behavior (bluff_tendency)
- Patience in negotiations (patience)
- Whether they push for NTC/opt-outs (loyalty_to_client)
- Negotiation messaging style
"""
import json
import random
from typing import Optional
from ..database.db import get_connection, query, execute


# ============================================================
# AGENT ARCHETYPES
# ============================================================
AGENT_ARCHETYPES = {
    "power_broker": {
        "personality": "aggressive",
        "negotiation_style": "hardball",
        "greed_factor": (1.15, 1.35),
        "loyalty_to_client": (0.4, 0.6),
        "market_knowledge": (80, 95),
        "bluff_tendency": (0.5, 0.8),
        "patience": (60, 85),
        "reputation": (75, 95),
    },
    "players_friend": {
        "personality": "player_first",
        "negotiation_style": "fair",
        "greed_factor": (0.95, 1.10),
        "loyalty_to_client": (0.8, 1.0),
        "market_knowledge": (60, 80),
        "bluff_tendency": (0.1, 0.3),
        "patience": (40, 65),
        "reputation": (50, 75),
    },
    "boutique": {
        "personality": "collaborative",
        "negotiation_style": "flexible",
        "greed_factor": (0.85, 1.0),
        "loyalty_to_client": (0.7, 0.95),
        "market_knowledge": (55, 75),
        "bluff_tendency": (0.05, 0.2),
        "patience": (30, 55),
        "reputation": (35, 60),
    },
    "shark": {
        "personality": "shark",
        "negotiation_style": "theatrical",
        "greed_factor": (1.20, 1.40),
        "loyalty_to_client": (0.3, 0.5),
        "market_knowledge": (70, 90),
        "bluff_tendency": (0.6, 0.9),
        "patience": (50, 80),
        "reputation": (55, 80),
    },
    "old_school": {
        "personality": "passive",
        "negotiation_style": "fair",
        "greed_factor": (0.90, 1.05),
        "loyalty_to_client": (0.5, 0.7),
        "market_knowledge": (40, 65),
        "bluff_tendency": (0.05, 0.15),
        "patience": (70, 95),
        "reputation": (40, 65),
    },
}

# Name pools for generating plausible agent names
AGENT_FIRST_NAMES = [
    "Scott", "Drew", "Casey", "Rich", "Arn", "Joel", "Dan", "Greg",
    "Mark", "Jeff", "Paul", "Dennis", "Jay", "Brian", "Steve",
    "Tony", "David", "Mike", "Ben", "Chris", "Alan", "Seth",
    "Nate", "Matt", "Ryan", "Eric", "Jason", "Kevin", "Tom", "Rob",
]

AGENT_LAST_NAMES = [
    "Boras", "Lozano", "Close", "Tellem", "Hendricks", "Wolfe",
    "Levinson", "Gershon", "Shapiro", "Schwartz", "Rosen", "Stein",
    "Harper", "Morrison", "Calloway", "Davenport", "Whitfield",
    "Pratt", "Sinclair", "Thornton", "Vasquez", "O'Brien",
    "Castellano", "Kirkpatrick", "Brennan", "Fitzgerald", "Sterling",
    "Aldridge", "Blackwell", "Cortez",
]

AGENCY_PREFIXES = [
    "Elite", "Premier", "Apex", "Diamond", "Summit", "Pinnacle",
    "Legacy", "Vanguard", "Pacific", "Atlantic", "National",
    "Continental", "Cornerstone", "Titan", "Monarch",
]

AGENCY_SUFFIXES = [
    "Sports Group", "Sports Management", "Sports Agency",
    "Athletic Representation", "Player Management", "Sports Advisors",
    "Sports Partners", "Talent Group", "Sports Associates",
    "Sports Consulting", "Management Group",
]

# Archetype-specific notable deals templates
NOTABLE_DEALS_TEMPLATES = {
    "power_broker": [
        "Negotiated a record $350M/12yr deal for a franchise shortstop",
        "Secured $28M AAV for a 32-year-old starter",
        "Landed full NTC and opt-out after year 3 on a 7-year deal",
    ],
    "players_friend": [
        "Helped client return to hometown team on a fair deal",
        "Negotiated a deal with heavy incentives to reward performance",
        "Secured a playing-time guarantee for a young outfielder",
    ],
    "boutique": [
        "Found the right fit for a veteran catcher with a contender",
        "Negotiated a 2-year prove-it deal that paid off big",
        "Placed 3 clients on the same playoff-bound roster",
    ],
    "shark": [
        "Leaked false offer reports to drive bidding to $200M+",
        "Waited until February to sign, extracting a 40% premium",
        "Convinced a team to add a vesting option worth $30M",
    ],
    "old_school": [
        "Handshake deal completed in 48 hours",
        "Quiet negotiation landed a solid 4-year extension",
        "Maintained a 20-year relationship with one franchise",
    ],
}


def _rand_range(r: tuple) -> float:
    """Generate a random value from a (min, max) tuple."""
    return round(random.uniform(r[0], r[1]), 2)


def _rand_range_int(r: tuple) -> int:
    """Generate a random integer from a (min, max) tuple."""
    return random.randint(r[0], r[1])


def _generate_agency_name() -> str:
    """Generate a plausible agency name."""
    return f"{random.choice(AGENCY_PREFIXES)} {random.choice(AGENCY_SUFFIXES)}"


def generate_agents(count: int = 15, db_path: str = None) -> list:
    """
    Generate diverse player agents with realistic names and personalities.

    Distribution across archetypes:
    - 3 Power Brokers (the big dogs)
    - 3 Player's Friends (client-focused)
    - 3 Boutique agents (small, personal)
    - 3 Sharks (aggressive, theatrical)
    - 3 Old School (patient, traditional)

    If count != 15, distributes proportionally.
    """
    conn = get_connection(db_path)

    # Check if agents already exist
    existing = conn.execute("SELECT COUNT(*) as c FROM agent_characters").fetchone()["c"]
    if existing > 0:
        agents = conn.execute("SELECT * FROM agent_characters").fetchall()
        conn.close()
        return [dict(a) for a in agents]

    archetype_names = list(AGENT_ARCHETYPES.keys())
    per_archetype = max(1, count // len(archetype_names))
    remainder = count - per_archetype * len(archetype_names)

    used_names = set()
    agents = []

    for i, archetype_key in enumerate(archetype_names):
        arch = AGENT_ARCHETYPES[archetype_key]
        n = per_archetype + (1 if i < remainder else 0)

        for _ in range(n):
            # Generate unique name
            while True:
                first = random.choice(AGENT_FIRST_NAMES)
                last = random.choice(AGENT_LAST_NAMES)
                full = f"{first} {last}"
                if full not in used_names:
                    used_names.add(full)
                    break

            agency = _generate_agency_name()
            notable = json.dumps(random.sample(
                NOTABLE_DEALS_TEMPLATES[archetype_key],
                k=min(2, len(NOTABLE_DEALS_TEMPLATES[archetype_key]))
            ))

            agent_data = {
                "name": full,
                "agency_name": agency,
                "personality": arch["personality"],
                "negotiation_style": arch["negotiation_style"],
                "greed_factor": _rand_range(arch["greed_factor"]),
                "loyalty_to_client": _rand_range(arch["loyalty_to_client"]),
                "market_knowledge": _rand_range_int(arch["market_knowledge"]),
                "bluff_tendency": _rand_range(arch["bluff_tendency"]),
                "patience": _rand_range_int(arch["patience"]),
                "reputation": _rand_range_int(arch["reputation"]),
                "num_clients": 0,
                "notable_deals": notable,
            }

            conn.execute("""
                INSERT INTO agent_characters
                (name, agency_name, personality, negotiation_style, greed_factor,
                 loyalty_to_client, market_knowledge, bluff_tendency, patience,
                 reputation, num_clients, notable_deals)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent_data["name"], agent_data["agency_name"],
                agent_data["personality"], agent_data["negotiation_style"],
                agent_data["greed_factor"], agent_data["loyalty_to_client"],
                agent_data["market_knowledge"], agent_data["bluff_tendency"],
                agent_data["patience"], agent_data["reputation"],
                agent_data["num_clients"], agent_data["notable_deals"],
            ))
            agents.append(agent_data)

    conn.commit()

    # Retrieve with IDs
    result = conn.execute("SELECT * FROM agent_characters").fetchall()
    conn.close()
    return [dict(a) for a in result]


def assign_agents_to_players(db_path: str = None) -> dict:
    """
    Assign agents to all players. Better players (higher OVR) get assigned to
    higher-reputation agents.

    Client distribution:
    - Top agents (Power Broker, Shark): ~40-60 clients each
    - Mid agents (Player's Friend): ~20-40 clients each
    - Boutique agents: ~10-20 clients each
    - Old School: ~15-30 clients each
    """
    conn = get_connection(db_path)

    # Ensure agents exist
    agent_count = conn.execute("SELECT COUNT(*) as c FROM agent_characters").fetchone()["c"]
    if agent_count == 0:
        conn.close()
        generate_agents(db_path=db_path)
        conn = get_connection(db_path)

    # Get all agents sorted by reputation (highest first)
    agents = conn.execute("""
        SELECT * FROM agent_characters ORDER BY reputation DESC
    """).fetchall()
    agents = [dict(a) for a in agents]

    if not agents:
        conn.close()
        return {"error": "No agents found"}

    # Clear existing assignments
    conn.execute("DELETE FROM player_agents")

    # Get all players with an overall rating proxy, sorted best to worst
    players = conn.execute("""
        SELECT id, position, roster_status,
            CASE WHEN position IN ('SP', 'RP')
                THEN (stuff_rating * 2 + control_rating * 1.5 + stamina_rating * 0.5) / 4.0
                ELSE (contact_rating * 1.5 + power_rating * 1.5 + speed_rating * 0.5 + fielding_rating * 0.5) / 4.0
            END as overall
        FROM players
        ORDER BY overall DESC
    """).fetchall()
    players = [dict(p) for p in players]

    if not players:
        conn.close()
        return {"error": "No players found"}

    # Determine target client counts based on personality
    target_clients = {}
    for agent in agents:
        personality = agent["personality"]
        if personality in ("aggressive", "shark"):
            target_clients[agent["id"]] = random.randint(40, 60)
        elif personality == "player_first":
            target_clients[agent["id"]] = random.randint(20, 40)
        elif personality == "collaborative":
            target_clients[agent["id"]] = random.randint(10, 20)
        elif personality == "passive":
            target_clients[agent["id"]] = random.randint(15, 30)
        else:
            target_clients[agent["id"]] = random.randint(15, 35)

    # Normalize targets to fit total player count
    total_targets = sum(target_clients.values())
    total_players = len(players)
    if total_targets > 0:
        scale = total_players / total_targets
        for aid in target_clients:
            target_clients[aid] = max(1, int(target_clients[aid] * scale))

    # Assign players: top players go to top agents (weighted)
    current_counts = {a["id"]: 0 for a in agents}
    assignments = 0

    for player in players:
        # Build weighted pool: higher reputation agents get first pick of top players
        # But respect capacity limits
        available_agents = [
            a for a in agents
            if current_counts[a["id"]] < target_clients[a["id"]]
        ]

        if not available_agents:
            # All agents at capacity, just assign to the one with fewest
            available_agents = agents

        # Weight by reputation (top players more likely to go to top agents)
        if player["overall"] >= 65:
            # Star players: heavily favor top-reputation agents
            weights = [a["reputation"] ** 2 for a in available_agents]
        elif player["overall"] >= 50:
            # Average players: slight preference for higher reputation
            weights = [a["reputation"] for a in available_agents]
        else:
            # Below average: more random, slight favor to boutique/old school
            weights = []
            for a in available_agents:
                w = 50  # base weight
                if a["personality"] in ("collaborative", "passive"):
                    w = 80
                elif a["personality"] in ("aggressive", "shark"):
                    w = 30
                weights.append(w)

        total_w = sum(weights)
        if total_w == 0:
            chosen = random.choice(available_agents)
        else:
            r = random.random() * total_w
            cumulative = 0
            chosen = available_agents[-1]
            for a, w in zip(available_agents, weights):
                cumulative += w
                if r <= cumulative:
                    chosen = a
                    break

        conn.execute(
            "INSERT OR REPLACE INTO player_agents (player_id, agent_id) VALUES (?, ?)",
            (player["id"], chosen["id"])
        )
        current_counts[chosen["id"]] = current_counts.get(chosen["id"], 0) + 1
        assignments += 1

    # Update num_clients on each agent
    for agent in agents:
        conn.execute(
            "UPDATE agent_characters SET num_clients = ? WHERE id = ?",
            (current_counts[agent["id"]], agent["id"])
        )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "total_assignments": assignments,
        "agent_distribution": {
            a["name"]: current_counts[a["id"]] for a in agents
        },
    }


def get_player_agent(player_id: int, db_path: str = None) -> Optional[dict]:
    """Get the agent representing a specific player."""
    rows = query("""
        SELECT ac.* FROM agent_characters ac
        JOIN player_agents pa ON pa.agent_id = ac.id
        WHERE pa.player_id = ?
    """, (player_id,), db_path=db_path)
    if rows:
        agent = dict(rows[0])
        if agent.get("notable_deals"):
            try:
                agent["notable_deals"] = json.loads(agent["notable_deals"])
            except (json.JSONDecodeError, TypeError):
                pass
        return agent
    return None


def get_agent_details(agent_id: int, db_path: str = None) -> Optional[dict]:
    """Get agent details including client list."""
    rows = query("SELECT * FROM agent_characters WHERE id = ?", (agent_id,), db_path=db_path)
    if not rows:
        return None

    agent = dict(rows[0])
    if agent.get("notable_deals"):
        try:
            agent["notable_deals"] = json.loads(agent["notable_deals"])
        except (json.JSONDecodeError, TypeError):
            pass

    # Get client list
    clients = query("""
        SELECT p.id, p.first_name, p.last_name, p.position, p.age,
               p.roster_status, p.team_id,
               CASE WHEN p.position IN ('SP', 'RP')
                   THEN (p.stuff_rating * 2 + p.control_rating * 1.5 + p.stamina_rating * 0.5) / 4.0
                   ELSE (p.contact_rating * 1.5 + p.power_rating * 1.5 +
                         p.speed_rating * 0.5 + p.fielding_rating * 0.5) / 4.0
               END as overall
        FROM players p
        JOIN player_agents pa ON pa.player_id = p.id
        WHERE pa.agent_id = ?
        ORDER BY overall DESC
    """, (agent_id,), db_path=db_path)

    agent["clients"] = [dict(c) for c in clients]
    return agent


def get_all_agents(db_path: str = None) -> list:
    """List all player agents."""
    rows = query("SELECT * FROM agent_characters ORDER BY reputation DESC", db_path=db_path)
    result = []
    for r in rows:
        agent = dict(r)
        if agent.get("notable_deals"):
            try:
                agent["notable_deals"] = json.loads(agent["notable_deals"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(agent)
    return result


# ============================================================
# NEGOTIATION BEHAVIOR
# ============================================================

def get_agent_demands(agent_id: int, player_id: int, base_value: int,
                      base_years: int = 3, negotiation_round: int = 0,
                      db_path: str = None) -> dict:
    """
    Given a player's market value, the agent modifies demands based on personality.

    Returns a dict with:
    - salary: adjusted salary demand
    - years: adjusted years demand
    - wants_ntc: whether agent demands a no-trade clause
    - wants_opt_out: whether agent demands an opt-out
    - bluffing: whether agent is claiming other offers exist
    - bluff_message: the bluff text if bluffing
    - patience_factor: how quickly demands drop (0-1, higher = more patient)
    """
    agent = get_player_agent_by_agent_id(agent_id, db_path)
    if not agent:
        # No agent found, return base values
        return {
            "salary": base_value,
            "years": base_years,
            "wants_ntc": False,
            "wants_opt_out": False,
            "bluffing": False,
            "bluff_message": None,
            "patience_factor": 0.5,
        }

    # --- Salary adjustment via greed_factor ---
    adjusted_salary = int(base_value * agent["greed_factor"])

    # --- Patience: demands drop over negotiation rounds ---
    patience_factor = agent["patience"] / 100.0
    if negotiation_round > 0:
        # Patient agents drop demands slowly; impatient ones drop faster
        drop_rate = (1.0 - patience_factor) * 0.05  # 0-5% per round
        rounds_factor = max(0.70, 1.0 - (drop_rate * negotiation_round))
        adjusted_salary = int(adjusted_salary * rounds_factor)

    # --- Years: aggressive/shark agents push for more years ---
    adjusted_years = base_years
    if agent["personality"] in ("aggressive", "shark"):
        adjusted_years = min(base_years + random.randint(1, 2), 10)
    elif agent["personality"] == "passive":
        adjusted_years = max(base_years - 1, 1)

    # --- NTC demand: based on loyalty_to_client and player quality ---
    player_info = query("SELECT * FROM players WHERE id = ?", (player_id,), db_path=db_path)
    wants_ntc = False
    wants_opt_out = False

    if player_info:
        p = player_info[0]
        is_pitcher = p["position"] in ("SP", "RP")
        if is_pitcher:
            overall = (p["stuff_rating"] * 2 + p["control_rating"] * 1.5 +
                       p["stamina_rating"] * 0.5) / 4
        else:
            overall = (p["contact_rating"] * 1.5 + p["power_rating"] * 1.5 +
                       p["speed_rating"] * 0.5 + p["fielding_rating"] * 0.5) / 4

        # NTC: high loyalty agents push for it on good+ players
        if agent["loyalty_to_client"] > 0.6 and overall >= 60:
            wants_ntc = random.random() < agent["loyalty_to_client"]
        elif agent["personality"] == "shark" and overall >= 55:
            wants_ntc = random.random() < 0.5

        # Opt-out: aggressive agents push for opt-outs on long deals
        if adjusted_years >= 4:
            if agent["personality"] in ("aggressive", "shark"):
                wants_opt_out = random.random() < 0.6
            elif agent["loyalty_to_client"] > 0.8:
                wants_opt_out = random.random() < 0.4

    # --- Bluffing: chance of claiming other teams are offering more ---
    bluffing = random.random() < agent["bluff_tendency"]
    bluff_message = None
    if bluffing:
        bluff_premium = random.randint(5, 20)
        bluff_salary = int(adjusted_salary * (1 + bluff_premium / 100))
        bluff_messages = [
            f"We have another offer on the table for ${bluff_salary:,}/yr. You'll need to do better.",
            f"Multiple teams are in the ${bluff_salary:,} range. This is a competitive market.",
            f"I can't name names, but there's serious interest well above your current offer.",
            f"Another club offered ${bluff_salary:,} with a full NTC. Just saying.",
            f"My client has options. We're looking at something north of ${bluff_salary:,}.",
        ]
        bluff_message = random.choice(bluff_messages)

    return {
        "salary": adjusted_salary,
        "years": adjusted_years,
        "wants_ntc": wants_ntc,
        "wants_opt_out": wants_opt_out,
        "bluffing": bluffing,
        "bluff_message": bluff_message,
        "patience_factor": patience_factor,
        "agent_name": agent["name"],
        "agent_personality": agent["personality"],
    }


def get_player_agent_by_agent_id(agent_id: int, db_path: str = None) -> Optional[dict]:
    """Get agent by their ID."""
    rows = query("SELECT * FROM agent_characters WHERE id = ?", (agent_id,), db_path=db_path)
    if rows:
        return dict(rows[0])
    return None


# ============================================================
# AGENT NEGOTIATION MESSAGES
# ============================================================

# Message templates keyed by personality and context
_NEGOTIATION_MESSAGES = {
    "aggressive": {
        "initial_demand": [
            "Let's not waste each other's time. My client is worth every penny of ${salary:,}. That's the starting point.",
            "We both know what {player_name} brings to the table. ${salary:,} per year, {years} years. Non-negotiable.",
            "{player_name} is a premium talent. The market says ${salary:,}. I'd suggest you move fast before the price goes up.",
        ],
        "counter": [
            "That's not going to get it done. We need to see ${salary:,} minimum.",
            "I appreciate the effort, but my client deserves more. Come back with something serious.",
            "You're going to need to add at least ${gap:,} to that. Other teams understand {player_name}'s value.",
        ],
        "accept": [
            "We have a deal. {player_name} is excited to get to work.",
            "Done. Let's get the paperwork signed before anyone changes their mind.",
        ],
        "reject": [
            "We're done here. I'll be taking calls from other interested teams.",
            "This isn't close. When you're ready to talk real numbers, you know where to find me.",
        ],
        "bluff": [
            "I've got three teams willing to go higher than this. Your move.",
            "The phone hasn't stopped ringing. You need to step up or step aside.",
        ],
    },
    "player_first": {
        "initial_demand": [
            "{player_name} wants to be somewhere they're valued. ${salary:,} over {years} years feels right.",
            "My client cares about fit as much as money. ${salary:,} and a good role is what we're looking for.",
            "Let's find something that works for everyone. {player_name} is looking at ${salary:,} range.",
        ],
        "counter": [
            "{player_name} appreciates the interest, but we need to get closer to ${salary:,}.",
            "The money matters, but so does the situation. Can we meet in the middle around ${salary:,}?",
        ],
        "accept": [
            "{player_name} is thrilled. This is the right fit and the right deal.",
            "My client wanted to be here. Let's make it official.",
        ],
        "reject": [
            "We appreciate the talks, but {player_name} feels they can find a better fit elsewhere.",
            "It's not just about the money. The role and situation need to be right too.",
        ],
        "bluff": [
            "{player_name} has other options that might be a better fit. Something to keep in mind.",
        ],
    },
    "collaborative": {
        "initial_demand": [
            "I think we can find common ground here. We're looking at ${salary:,} over {years} years.",
            "Let's work together on this. ${salary:,} per year seems fair for what {player_name} offers.",
        ],
        "counter": [
            "We're not far apart. How about ${salary:,}? I think that's fair for both sides.",
            "I hear you. Let's split the difference at ${salary:,}.",
        ],
        "accept": [
            "Great working with you on this. {player_name} is ready to contribute.",
            "Fair deal for everyone. Let's get it done.",
        ],
        "reject": [
            "I don't think we're going to get there on this one. No hard feelings.",
            "We're too far apart. Maybe we can revisit later.",
        ],
        "bluff": [
            "There is some interest from other clubs, for what it's worth.",
        ],
    },
    "shark": {
        "initial_demand": [
            "My client's market value is ${salary:,} per year. That's based on the comps. Don't insult us with lowball offers.",
            "{player_name} is the best player on the market. ${salary:,} is actually a discount. You're welcome.",
            "Let me be clear: ${salary:,} per year, {years} years, full NTC. That's the deal.",
        ],
        "counter": [
            "I just got off the phone with another GM who's willing to go to ${salary:,}. Ball's in your court.",
            "You're going to feel really silly when {player_name} signs somewhere else for ${salary:,}.",
            "My phone is blowing up. ${salary:,} is the new floor. Take it or leave it.",
        ],
        "accept": [
            "Smart move. You won't regret this.",
            "You got yourself a star. My fee is worth every penny.",
        ],
        "reject": [
            "I've never seen a team lowball this badly. We're done.",
            "You had your chance. I'll be calling your division rivals now.",
        ],
        "bluff": [
            "I have four teams bidding right now. This is going to get expensive for somebody.",
            "A mystery team just offered ${salary:,}. Can you beat that?",
        ],
    },
    "passive": {
        "initial_demand": [
            "We think ${salary:,} over {years} years is a fair value. What do you think?",
            "{player_name} has been consistent for a long time. ${salary:,} per year seems reasonable.",
        ],
        "counter": [
            "We'd like to get a bit closer to ${salary:,} if possible.",
            "That's a bit low. Is there room to come up to ${salary:,}?",
        ],
        "accept": [
            "{player_name} is happy with the deal. Looking forward to a good season.",
            "Sounds good. Let's finalize this.",
        ],
        "reject": [
            "I think we'll keep looking for now. Thank you for your time.",
            "We're going to take some time to consider other options.",
        ],
        "bluff": [
            "There might be some other interest out there. Just wanted to let you know.",
        ],
    },
}


def get_agent_negotiation_message(agent_id: int, context: str,
                                  player_name: str = "the player",
                                  salary: int = 0, years: int = 1,
                                  gap: int = 0,
                                  db_path: str = None) -> Optional[str]:
    """
    Generate a personality-appropriate message for trade talks,
    FA negotiations, or extensions.

    Args:
        agent_id: The agent's ID
        context: One of 'initial_demand', 'counter', 'accept', 'reject', 'bluff'
        player_name: Player's display name
        salary: Relevant salary figure for message formatting
        years: Contract years
        gap: Salary gap between offer and demand (for counters)

    Returns:
        A formatted negotiation message string, or None if agent not found.
    """
    agent = get_player_agent_by_agent_id(agent_id, db_path)
    if not agent:
        return None

    personality = agent["personality"]

    # Map personality to message templates
    personality_key = {
        "aggressive": "aggressive",
        "player_first": "player_first",
        "collaborative": "collaborative",
        "shark": "shark",
        "passive": "passive",
    }.get(personality, "collaborative")

    templates = _NEGOTIATION_MESSAGES.get(personality_key, _NEGOTIATION_MESSAGES["collaborative"])
    context_templates = templates.get(context, templates.get("counter", ["No comment."]))

    template = random.choice(context_templates)

    # Format the template
    try:
        message = template.format(
            player_name=player_name,
            salary=salary,
            years=years,
            gap=gap,
        )
    except (KeyError, IndexError):
        message = template

    return f"[{agent['name']}, {agent.get('agency_name', 'Independent')}]: {message}"


# ============================================================
# FREE AGENCY INTEGRATION
# ============================================================

def modify_free_agent_negotiation(player_id: int, base_salary: int,
                                  base_years: int, offer_salary: int,
                                  offer_years: int,
                                  negotiation_round: int = 0,
                                  db_path: str = None) -> dict:
    """
    Hook into the free agency negotiation flow. When signing a free agent,
    the agent's personality modifies:
    - Initial asking price (greed_factor * market_value)
    - Counter-offer behavior
    - How many years they want
    - Whether they demand NTC

    Returns modified negotiation result with agent influence.
    """
    agent = get_player_agent(player_id, db_path)
    if not agent:
        # No agent assigned; use base negotiation logic
        return {
            "agent_involved": False,
            "adjusted_asking_salary": base_salary,
            "adjusted_asking_years": base_years,
            "acceptance_modifier": 0.0,
            "wants_ntc": False,
            "wants_opt_out": False,
            "agent_message": None,
        }

    # Get agent's demands
    demands = get_agent_demands(
        agent["id"], player_id, base_salary, base_years,
        negotiation_round, db_path
    )

    # Calculate acceptance modifier based on agent personality
    # This shifts the probability of accepting an offer
    salary_ratio = offer_salary / demands["salary"] if demands["salary"] > 0 else 1.0

    acceptance_modifier = 0.0
    if agent["personality"] == "passive":
        acceptance_modifier = 0.10  # More willing to accept
    elif agent["personality"] == "collaborative":
        acceptance_modifier = 0.05
    elif agent["personality"] == "aggressive":
        acceptance_modifier = -0.10  # Harder to please
    elif agent["personality"] == "shark":
        acceptance_modifier = -0.15  # Very hard to please
    elif agent["personality"] == "player_first":
        # Depends on team quality (would need team context)
        acceptance_modifier = 0.0

    # Patience affects counter-offer behavior
    patience_factor = demands["patience_factor"]

    # Generate appropriate message
    if salary_ratio >= 1.0:
        context = "accept"
    elif salary_ratio >= 0.80:
        context = "counter"
    else:
        context = "reject"

    player_info = query(
        "SELECT first_name, last_name FROM players WHERE id = ?",
        (player_id,), db_path=db_path
    )
    player_name = "the player"
    if player_info:
        player_name = f"{player_info[0]['first_name']} {player_info[0]['last_name']}"

    gap = demands["salary"] - offer_salary
    message = get_agent_negotiation_message(
        agent["id"], context,
        player_name=player_name,
        salary=demands["salary"],
        years=demands["years"],
        gap=abs(gap),
        db_path=db_path,
    )

    # Build counter-offer if not accepting
    counter_offer = None
    if context in ("counter", "reject"):
        # Agent's counter: split the difference (modified by patience)
        if context == "counter":
            # Patient agents counter closer to their demand
            split = 0.3 + (patience_factor * 0.4)  # 0.3-0.7 weight toward agent demand
            counter_salary = int(offer_salary + (demands["salary"] - offer_salary) * split)
        else:
            # Reject: counter at 90-95% of demand
            counter_salary = int(demands["salary"] * random.uniform(0.90, 0.95))

        counter_offer = {
            "salary": counter_salary,
            "years": demands["years"],
            "wants_ntc": demands["wants_ntc"],
            "wants_opt_out": demands["wants_opt_out"],
        }

    return {
        "agent_involved": True,
        "agent_name": agent["name"],
        "agent_personality": agent["personality"],
        "adjusted_asking_salary": demands["salary"],
        "adjusted_asking_years": demands["years"],
        "acceptance_modifier": acceptance_modifier,
        "wants_ntc": demands["wants_ntc"],
        "wants_opt_out": demands["wants_opt_out"],
        "bluffing": demands.get("bluffing", False),
        "bluff_message": demands.get("bluff_message"),
        "agent_message": message,
        "counter_offer": counter_offer,
        "patience_factor": patience_factor,
    }
