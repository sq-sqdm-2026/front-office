"""
Front Office - Starting Narrative & Team Selection
Defines the three available team scenarios for the opening of the game.
Each scenario has a unique owner personality, challenge, and set of welcome messages.
"""
from ..database.db import execute, query
from ..transactions.messages import send_message


# ============================================================
# SCENARIO DEFINITIONS
# ============================================================

SCENARIOS = [
    {
        "team_abbr": "PIT",
        "owner_name": "Bob Nutting",
        "owner_personality": {
            "archetype": "budget_conscious",
            "traits": ["frugal", "analytical", "patient", "risk-averse"],
            "communication_style": "measured and businesslike",
            "hot_buttons": ["payroll overruns", "bad contracts", "prospect trades"],
            "praise_triggers": ["under-budget moves", "prospect development", "creative solutions"],
        },
        "challenge_description": (
            "Tight budget, great farm system, rebuilding. The Pirates have one of "
            "baseball's best farm systems but ownership keeps the purse strings tight. "
            "You'll need to build a contender on a shoestring budget while developing "
            "homegrown talent. The fans are skeptical — they've heard 'trust the process' before."
        ),
        "starting_budget_modifier": 0.75,  # 75% of league-average payroll ceiling
        "owner_patience": "high",
        "initial_messages": [
            {
                "sender_name": "Bob Nutting",
                "sender_type": "owner",
                "subject": "Welcome Aboard",
                "body": (
                    "I'm going to be straight with you. This franchise has been the punchline of "
                    "too many jokes for too long, and I know a lot of people blame me for that. "
                    "Maybe some of it's fair.\n\n"
                    "But I hired you because you see what I see — a farm system loaded with talent "
                    "that's about to arrive. I don't need you to spend like the Dodgers. I need you "
                    "to be smarter than the Dodgers.\n\n"
                    "The budget is what it is. Don't come to me asking for $200 million payrolls. "
                    "Find value. Develop our kids. Build something that lasts.\n\n"
                    "— Bob"
                ),
            },
            {
                "sender_name": "Bob Nutting",
                "sender_type": "owner",
                "subject": "Expectations for 2026",
                "body": (
                    "I'm not expecting a playoff run this year — I'm realistic about where we are. "
                    "But I want to see progress. The kids need to play, the payroll needs to stay "
                    "manageable, and by 2028 I want this team competing for the Central.\n\n"
                    "Show me you can build a plan and stick to it. That's all I ask.\n\n"
                    "— Bob"
                ),
            },
        ],
    },
    {
        "team_abbr": "KC",
        "owner_name": "John Sherman",
        "owner_personality": {
            "archetype": "competitive_small_market",
            "traits": ["competitive", "impatient", "demanding", "passionate"],
            "communication_style": "direct and emotional",
            "hot_buttons": ["losing streaks", "empty stadium", "stale roster"],
            "praise_triggers": ["winning streaks", "fan engagement", "bold trades"],
        },
        "challenge_description": (
            "Mid-market team with an aging core that needs retooling. The Royals had their "
            "window and it's closing fast. Key veterans are declining, the farm system is thin, "
            "and the owner's patience is wearing thin. You need to thread the needle — stay "
            "competitive while getting younger, or commit to a full tear-down and face the "
            "owner's wrath."
        ),
        "starting_budget_modifier": 0.90,  # 90% of league-average payroll ceiling
        "owner_patience": "medium",
        "initial_messages": [
            {
                "sender_name": "John Sherman",
                "sender_type": "owner",
                "subject": "Welcome to Kansas City",
                "body": (
                    "Let me tell you what I told the last GM on his way out: I didn't buy this "
                    "team to lose. Kansas City is a baseball town. These fans deserve better than "
                    "what we've been giving them.\n\n"
                    "I brought you in because the analytics crowd says you're the real deal. I "
                    "hope they're right, because my patience isn't infinite.\n\n"
                    "We've got some good pieces but the core is aging. I need you to figure out "
                    "what's worth keeping and what needs to go. But understand this — I want to "
                    "compete. I'm not interested in a five-year rebuild. The fans won't wait that "
                    "long, and neither will I.\n\n"
                    "— John"
                ),
            },
            {
                "sender_name": "John Sherman",
                "sender_type": "owner",
                "subject": "The Clock Is Ticking",
                "body": (
                    "One more thing. I've given you a three-year deal. That's not a threat — "
                    "it's reality. Show me meaningful improvement by year two, or we'll both be "
                    "looking for new jobs.\n\n"
                    "I'm giving you more payroll flexibility than the last guy had. Use it wisely. "
                    "I want bold moves, not safe ones.\n\n"
                    "— John"
                ),
            },
        ],
    },
    {
        "team_abbr": "CIN",
        "owner_name": "Bob Castellini",
        "owner_personality": {
            "archetype": "ego_meddler",
            "traits": ["impatient", "meddlesome", "passionate", "unpredictable"],
            "communication_style": "emotional and involved",
            "hot_buttons": ["media criticism", "empty seats", "prospect-heavy trades"],
            "praise_triggers": ["big-name signings", "winning", "media praise"],
        },
        "challenge_description": (
            "Small market with some talent but a dysfunctional front office. The Reds have "
            "a hitter-friendly park and some exciting young bats, but the organization has been "
            "a revolving door of GMs and conflicting philosophies. The owner is impatient, "
            "meddlesome, and will second-guess your every move. Can you build a winner while "
            "managing up?"
        ),
        "starting_budget_modifier": 0.80,  # 80% of league-average payroll ceiling
        "owner_patience": "low",
        "initial_messages": [
            {
                "sender_name": "Bob Castellini",
                "sender_type": "owner",
                "subject": "Big Plans for Cincinnati",
                "body": (
                    "I've fired a lot of GMs. Let's get that out of the way. Not because I enjoy "
                    "it — because none of them could get the job done.\n\n"
                    "You're different, or so they tell me. Analytics, AI, whatever it is you do. "
                    "I don't care how you do it. I care about results. I want to see this team in "
                    "the postseason, and I want to see it soon.\n\n"
                    "This is a passionate city. The fans are starving for a winner. Great American "
                    "Ball Park should be rocking every night, not half-empty.\n\n"
                    "Don't let me down.\n\n"
                    "— Bob"
                ),
            },
            {
                "sender_name": "Bob Castellini",
                "sender_type": "owner",
                "subject": "A Few Ground Rules",
                "body": (
                    "I'm going to be involved. That's not negotiable. I want to know about every "
                    "major move before it happens. No surprises.\n\n"
                    "I also want big names. The fans need someone to get excited about. I don't "
                    "want to hear about WAR and launch angles — I want to hear about guys who put "
                    "butts in seats.\n\n"
                    "We've got some nice young hitters. Build around them. Get me some pitching. "
                    "And for God's sake, do something about the bullpen.\n\n"
                    "— Bob"
                ),
            },
        ],
    },
]


def get_available_scenarios(db_path: str = None) -> list[dict]:
    """
    Return the three starting team scenarios.

    Each scenario is enriched with the actual team_id from the database
    (matched by abbreviation). If the database is not available or a team
    is missing, the scenario is still returned with team_id=None.
    """
    results = []
    for scenario in SCENARIOS:
        team_rows = query(
            "SELECT id, city, name FROM teams WHERE abbreviation=?",
            (scenario["team_abbr"],),
            db_path=db_path,
        )
        team_id = team_rows[0]["id"] if team_rows else None
        city = team_rows[0]["city"] if team_rows else ""
        name = team_rows[0]["name"] if team_rows else ""

        results.append({
            "team_id": team_id,
            "team_abbr": scenario["team_abbr"],
            "team_city": city,
            "team_name": name,
            "owner_name": scenario["owner_name"],
            "owner_personality": scenario["owner_personality"],
            "challenge_description": scenario["challenge_description"],
            "starting_budget_modifier": scenario["starting_budget_modifier"],
            "owner_patience": scenario["owner_patience"],
            "initial_messages": scenario["initial_messages"],
        })
    return results


def select_starting_team(team_id: int, db_path: str = None) -> dict:
    """
    Select a starting team and initialize the game narrative.

    - Sets user_team_id in game_state
    - Sets the game date to 2026-02-14
    - Sends owner welcome messages via the messages system
    - Initializes owner_characters and gm_job_security rows

    Returns the selected scenario details.

    Raises ValueError if team_id does not match any available scenario.
    """
    # Find the matching scenario
    scenarios = get_available_scenarios(db_path=db_path)
    scenario = None
    for s in scenarios:
        if s["team_id"] == team_id:
            scenario = s
            break

    if scenario is None:
        raise ValueError(f"Team ID {team_id} is not an available starting scenario.")

    # 1. Update game_state: set user team and starting date
    execute(
        "UPDATE game_state SET user_team_id=?, current_date='2026-02-14' WHERE id=1",
        (team_id,),
        db_path=db_path,
    )

    # 2. Send owner welcome messages
    raw_scenario = None
    for s in SCENARIOS:
        if s["team_abbr"] == scenario["team_abbr"]:
            raw_scenario = s
            break

    if raw_scenario:
        for msg in raw_scenario["initial_messages"]:
            # Insert directly to control sender_type and sender_name
            execute(
                """INSERT INTO messages
                   (game_date, sender_type, sender_name, recipient_type,
                    recipient_id, subject, body, is_read, requires_response,
                    priority, category)
                   VALUES ('2026-02-14', ?, ?, 'user', ?, ?, ?, 0, 0,
                    ?, ?)""",
                (
                    msg["sender_type"],
                    msg["sender_name"],
                    team_id,
                    msg["subject"],
                    msg["body"],
                    msg.get("priority", "important"),
                    msg.get("category", "general"),
                ),
                db_path=db_path,
            )

    # 3. Initialize owner_characters row if not already present
    existing_owner = query(
        "SELECT id FROM owner_characters WHERE team_id=?",
        (team_id,),
        db_path=db_path,
    )
    if not existing_owner and raw_scenario:
        import json
        name_parts = raw_scenario["owner_name"].split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        personality = raw_scenario["owner_personality"]
        patience_map = {"low": 25, "medium": 50, "high": 75}
        budget_map = {"low": 30, "medium": 50, "high": 70}

        execute(
            """INSERT INTO owner_characters
               (team_id, first_name, last_name, archetype,
                budget_willingness, patience, meddling, personality_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                team_id,
                first_name,
                last_name,
                personality["archetype"],
                int(raw_scenario["starting_budget_modifier"] * 100),
                patience_map.get(raw_scenario["owner_patience"], 50),
                70 if "meddlesome" in personality["traits"] else 30,
                json.dumps(personality),
            ),
            db_path=db_path,
        )

    # 4. Initialize gm_job_security row if not already present
    existing_security = query(
        "SELECT id FROM gm_job_security WHERE id=1",
        db_path=db_path,
    )
    if not existing_security:
        patience_map = {"low": 30, "medium": 55, "high": 80}
        execute(
            """INSERT INTO gm_job_security
               (id, team_id, security_score, owner_patience, owner_mood)
               VALUES (1, ?, 70, ?, 'neutral')""",
            (
                team_id,
                patience_map.get(scenario["owner_patience"], 50),
            ),
            db_path=db_path,
        )

    return scenario
