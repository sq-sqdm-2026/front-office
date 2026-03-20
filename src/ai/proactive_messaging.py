"""
Front Office - Proactive AI Character Messaging
Characters (owner, rival GMs, agents, coaches, beat writers) proactively
reach out to the user/GM based on game events.

Each character type has trigger conditions and personality-driven message
templates. A cooldown system prevents message spam.
"""
import json
import random
from datetime import date as dt_date, timedelta
from ..database.db import query, execute
from ..transactions.messages import send_message


# ============================================================
# COOLDOWN DEFAULTS (game days)
# ============================================================
DEFAULT_COOLDOWN_DAYS = 3
OWNER_COOLDOWN_DAYS = 5
AGENT_COOLDOWN_DAYS = 4
RIVAL_GM_COOLDOWN_DAYS = 7
BEAT_WRITER_COOLDOWN_DAYS = 5


# ============================================================
# PUBLIC API
# ============================================================

def send_trade_reaction_messages(team_id: int, game_date: str,
                                  trade_details: dict,
                                  db_path: str = None) -> list:
    """
    Send beat writer and owner reaction messages after a trade is executed.

    Args:
        team_id: The user's team ID
        game_date: Current game date string
        trade_details: Dict with keys: offered_names, requested_names,
                       team_name, other_team_name
        db_path: Database path

    Returns list of messages sent.
    """
    sent = []
    _ensure_table_exists(db_path)

    offered_names = trade_details.get("offered_names", [])
    requested_names = trade_details.get("requested_names", [])
    team_name = trade_details.get("team_name", "your team")
    other_team_name = trade_details.get("other_team_name", "the other team")

    offered_str = ", ".join(offered_names) if offered_names else "players"
    requested_str = ", ".join(requested_names) if requested_names else "players"

    # --- Beat writer reaction ---
    writer_name = random.choice(BEAT_WRITER_NAMES)

    beat_writer_templates = [
        (f"Breaking: {team_name} has traded {offered_str} to {other_team_name} "
         f"in exchange for {requested_str}. This is a big move. "
         "Any comment for the fans on the thinking behind this deal?"),
        (f"Just got word on the {offered_str}-for-{requested_str} trade with "
         f"{other_team_name}. My readers are going to want to hear from you on this one. "
         "What's the message to the fanbase?"),
        (f"The trade wires are buzzing. {offered_str} headed to {other_team_name}, "
         f"{requested_str} coming back. I'm filing my story in an hour - "
         "can I get a quote from the GM?"),
    ]

    beat_body = random.choice(beat_writer_templates)

    response_options = {
        "options": [
            "I'm excited about what this means for our future",
            "No comment",
            "We felt this was the best move for the organization",
        ]
    }

    # Send beat writer message with response options
    execute("""
        INSERT INTO messages (game_date, sender_type, sender_name, recipient_type,
                             recipient_id, subject, body, is_read, requires_response,
                             response_options_json)
        VALUES (?, ?, ?, 'user', ?, ?, ?, 0, 1, ?)
    """, (game_date, "reporter", f"{writer_name} (Beat Writer)", team_id,
          f"Trade Reaction: {offered_str} for {requested_str}",
          beat_body, json.dumps(response_options)), db_path=db_path)

    sent.append({"character_type": "beat_writer", "trigger": "trade_reaction",
                "character_name": writer_name})

    # --- Owner reaction ---
    owner = query("SELECT * FROM owner_characters WHERE team_id=?",
                  (team_id,), db_path=db_path)
    if owner:
        owner = owner[0]
        owner_name = f"{owner['first_name']} {owner['last_name']}"

        # Determine tone: positive if team acquired more players than it gave up,
        # or concerned if it gave up more
        gave_up_count = len(offered_names)
        got_back_count = len(requested_names)

        if got_back_count >= gave_up_count:
            owner_templates = [
                (f"I like this deal. Bringing in {requested_str} shows we're serious "
                 f"about competing. Good work."),
                (f"I just heard about the trade. {requested_str} - that's the kind of "
                 f"player who puts fans in seats. Well done."),
                (f"Nice move getting {requested_str}. I trust your judgment on this one. "
                 f"Let's make it count."),
            ]
        else:
            owner_templates = [
                (f"I see we gave up {offered_str} to get {requested_str}. "
                 f"That's a lot of talent going out the door. I hope you know what you're doing."),
                (f"Just saw the trade. Giving up {offered_str} makes me nervous. "
                 f"I need {requested_str} to be worth it. Don't let me down."),
                (f"That's a bold move trading {offered_str}. The fans liked those guys. "
                 f"{requested_str} better produce."),
            ]

        owner_body = random.choice(owner_templates)
        _send_character_message(
            team_id, "owner", owner_name, "About the Trade",
            owner_body, game_date, db_path
        )
        sent.append({"character_type": "owner", "trigger": "trade_reaction",
                    "character_name": owner_name})

    return sent


def check_and_send_proactive_messages(team_id: int, game_date: str,
                                       db_path: str = None) -> list:
    """
    Main entry point. Called during sim advance for each day.
    Checks all trigger conditions and sends messages from various characters.

    Returns list of messages sent (dicts with character_type, trigger, etc.).
    """
    sent = []

    # Ensure the proactive_message_log table exists
    _ensure_table_exists(db_path)

    # Owner messages
    try:
        owner_msgs = _check_owner_triggers(team_id, game_date, db_path)
        sent.extend(owner_msgs)
    except Exception:
        pass

    # Coach messages
    try:
        coach_msgs = _check_coach_triggers(team_id, game_date, db_path)
        sent.extend(coach_msgs)
    except Exception:
        pass

    # Agent messages
    try:
        agent_msgs = _check_agent_triggers(team_id, game_date, db_path)
        sent.extend(agent_msgs)
    except Exception:
        pass

    # Rival GM messages
    try:
        rival_msgs = _check_rival_gm_triggers(team_id, game_date, db_path)
        sent.extend(rival_msgs)
    except Exception:
        pass

    # Beat writer messages
    try:
        writer_msgs = _check_beat_writer_triggers(team_id, game_date, db_path)
        sent.extend(writer_msgs)
    except Exception:
        pass

    return sent


# ============================================================
# COOLDOWN HELPERS
# ============================================================

def _is_on_cooldown(character_type: str, character_id: str, trigger_type: str,
                     team_id: int, game_date: str, db_path: str = None) -> bool:
    """Check if a character+trigger combination is still on cooldown."""
    rows = query("""
        SELECT cooldown_until FROM proactive_message_log
        WHERE character_type=? AND character_id=? AND trigger_type=? AND team_id=?
        ORDER BY cooldown_until DESC LIMIT 1
    """, (character_type, str(character_id), trigger_type, team_id), db_path=db_path)
    if not rows:
        return False
    return game_date < rows[0]["cooldown_until"]


def _record_message(character_type: str, character_id: str, trigger_type: str,
                     team_id: int, game_date: str, cooldown_days: int = DEFAULT_COOLDOWN_DAYS,
                     db_path: str = None):
    """Record a sent message and set its cooldown."""
    cooldown_until = (dt_date.fromisoformat(game_date) +
                      timedelta(days=cooldown_days)).isoformat()
    execute("""
        INSERT INTO proactive_message_log
        (character_type, character_id, trigger_type, team_id, game_date, cooldown_until)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (character_type, str(character_id), trigger_type, team_id,
          game_date, cooldown_until), db_path=db_path)


def _ensure_table_exists(db_path: str = None):
    """Create the proactive_message_log table if it doesn't exist."""
    execute("""
        CREATE TABLE IF NOT EXISTS proactive_message_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_type TEXT NOT NULL,
            character_id TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            game_date TEXT NOT NULL,
            cooldown_until TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """, db_path=db_path)
    execute("""
        CREATE INDEX IF NOT EXISTS idx_proactive_msg_cooldown
        ON proactive_message_log(character_type, character_id, trigger_type, team_id)
    """, db_path=db_path)


# ============================================================
# OWNER TRIGGERS
# ============================================================

OWNER_MESSAGES = {
    "losing_streak": {
        "win_now": [
            "We need to talk about the direction of this team. This losing streak is unacceptable. I didn't invest in this franchise to watch us lose.",
            "I'm getting calls from sponsors. {streak} straight losses? What's the plan here?",
            "This is embarrassing. {streak} games. Fix it or I'll find someone who will.",
        ],
        "budget_conscious": [
            "We're losing and spending money we don't have. {streak} losses in a row. Something has to change.",
            "I understand we're rebuilding, but {streak} straight losses? The fans are restless.",
        ],
        "patient_builder": [
            "I know we're building for the future, but {streak} losses in a row tests my patience. Is the process working?",
            "I trust the plan, but this {streak}-game skid has people asking questions. Just keeping you informed.",
        ],
        "ego_meddler": [
            "I'VE been watching every game. {streak} losses. I have some lineup ideas I want you to implement immediately.",
            "My friends are laughing at me. {streak} straight losses. Make some changes TODAY.",
        ],
        "default": [
            "We need to talk about the direction of this team. This {streak}-game losing streak concerns me.",
            "I don't like what I'm seeing. {streak} losses in a row. What's your plan to turn this around?",
        ],
    },
    "payroll_over_budget": {
        "budget_conscious": [
            "I'm very concerned about our spending. We're {pct}% over budget. This is not sustainable. Start making cuts.",
            "The books don't lie. We're {pct}% over what I approved. I need a plan to reduce payroll within the month.",
        ],
        "win_now": [
            "I see we're {pct}% over budget. If we're winning, I can live with it. But the results better justify the spending.",
            "The payroll is {pct}% above what we discussed. I trust you, but this better translate to wins.",
        ],
        "default": [
            "I'm concerned about our spending. We're {pct}% over the budget I set. Let's discuss how to rein this in.",
            "Our payroll has gotten out of hand - {pct}% over budget. I need you to be more disciplined with the checkbook.",
        ],
    },
    "clinch_playoff": {
        "default": [
            "Congratulations! The fans are excited and so am I. This is what I invested in. Don't stop here.",
            "We're in the playoffs! Outstanding work. Now let's make a deep run.",
            "I just opened a bottle of champagne. Playoff baseball! Well done.",
        ],
    },
    "attendance_dropping": {
        "default": [
            "I've noticed empty seats at the ballpark. We need to give the fans a reason to show up. What's the plan?",
            "Attendance is down and that means revenue is down. We need to make this team exciting again.",
            "The stadium is looking half-empty. We need to put a better product on the field or make some exciting moves.",
        ],
    },
}


def _check_owner_triggers(team_id: int, game_date: str,
                           db_path: str = None) -> list:
    """Check owner-specific trigger conditions."""
    sent = []

    owner = query("SELECT * FROM owner_characters WHERE team_id=?",
                  (team_id,), db_path=db_path)
    if not owner:
        return sent
    owner = owner[0]
    owner_name = f"{owner['first_name']} {owner['last_name']}"
    archetype = owner.get("archetype", "balanced")
    char_id = str(owner["id"])

    # --- Losing streak (5+) ---
    if not _is_on_cooldown("owner", char_id, "losing_streak", team_id, game_date, db_path):
        streak = _get_losing_streak(team_id, db_path)
        if streak >= 5:
            templates = OWNER_MESSAGES["losing_streak"].get(
                archetype, OWNER_MESSAGES["losing_streak"]["default"])
            body_template = random.choice(templates)
            body = body_template.format(streak=streak)
            _send_character_message(
                team_id, "owner", owner_name, "We Need to Talk",
                body, game_date, db_path
            )
            _record_message("owner", char_id, "losing_streak", team_id,
                           game_date, OWNER_COOLDOWN_DAYS, db_path)
            sent.append({"character_type": "owner", "trigger": "losing_streak",
                        "character_name": owner_name})

    # --- Payroll over budget (10%+) ---
    if not _is_on_cooldown("owner", char_id, "payroll_over_budget", team_id, game_date, db_path):
        payroll = _get_team_payroll(team_id, db_path)
        budget = _get_team_budget(team_id, owner, db_path)
        if budget > 0 and payroll > budget * 1.10:
            pct = int((payroll / budget - 1) * 100)
            templates = OWNER_MESSAGES["payroll_over_budget"].get(
                archetype, OWNER_MESSAGES["payroll_over_budget"]["default"])
            body = random.choice(templates).format(pct=pct)
            _send_character_message(
                team_id, "owner", owner_name, "Payroll Concerns",
                body, game_date, db_path
            )
            _record_message("owner", char_id, "payroll_over_budget", team_id,
                           game_date, OWNER_COOLDOWN_DAYS * 3, db_path)
            sent.append({"character_type": "owner", "trigger": "payroll_over_budget",
                        "character_name": owner_name})

    # --- Attendance dropping ---
    if not _is_on_cooldown("owner", char_id, "attendance_dropping", team_id, game_date, db_path):
        if _is_attendance_dropping(team_id, db_path):
            body = random.choice(OWNER_MESSAGES["attendance_dropping"]["default"])
            _send_character_message(
                team_id, "owner", owner_name, "Empty Seats",
                body, game_date, db_path
            )
            _record_message("owner", char_id, "attendance_dropping", team_id,
                           game_date, OWNER_COOLDOWN_DAYS * 4, db_path)
            sent.append({"character_type": "owner", "trigger": "attendance_dropping",
                        "character_name": owner_name})

    return sent


# ============================================================
# COACH TRIGGERS
# ============================================================

COACH_PROACTIVE_MESSAGES = {
    "prospect_ready": {
        "fiery": [
            "I've been watching {prospect} tear it up in {level}. The kid is READY. Bring him up and let him play!",
            "You've got a stud rotting in the minors. {prospect} is hitting {avg} in {level}. Call him up!",
        ],
        "steady": [
            "I think {prospect} is ready for the show. Steady improvement in {level}, hitting {avg}. Worth considering a call-up.",
            "{prospect} has been performing well in {level}. The reports are all positive. Might be time.",
        ],
        "innovator": [
            "The data on {prospect} is incredible. His {level} statcast numbers are elite - barrel rate, chase rate, all of it. He's ready.",
            "{prospect}'s underlying metrics in {level} scream big-league ready. The projection models agree.",
        ],
        "players_coach": [
            "{prospect} is mature beyond his years. The guys in {level} say he's a leader. I think the clubhouse would welcome him.",
            "I've talked to some vets about {prospect}. They're excited to work with the kid. He's ready.",
        ],
        "disciplinarian": [
            "{prospect} has earned it. Works hard, first one at the park in {level}. He's got the discipline for the big leagues.",
            "If {prospect} comes up, he follows my rules like everyone else. But the kid has earned a shot. Hitting {avg} in {level}.",
        ],
        "default": [
            "I think {prospect} is ready for a promotion from {level}. He's been hitting {avg} and looking confident.",
            "{prospect} has been impressive in {level}. Might be time to give him a look at the big-league level.",
        ],
    },
    "player_struggling": {
        "fiery": [
            "{player} needs to figure it out. Hitting {avg} over the last two weeks. I'm thinking about sitting him.",
            "Something's off with {player}. He's pressing. Might need a day or two on the bench.",
        ],
        "steady": [
            "{player} needs some time to work on his mechanics. His numbers have dipped lately ({avg}). Maybe a day off would help.",
            "Just a heads up - {player} has been struggling. Might want to lighten his load for a few games.",
        ],
        "innovator": [
            "{player}'s exit velocity has dropped significantly. Hitting {avg} with poor quality contact. Something mechanical is off.",
            "The underlying numbers for {player} are concerning. Launch angle, barrel rate, all trending wrong.",
        ],
        "default": [
            "{player} has been struggling lately, hitting {avg}. He might need a breather or some extra batting practice.",
            "Wanted to flag that {player} hasn't been himself. His numbers ({avg}) suggest something's off.",
        ],
    },
    "lineup_suggestion": {
        "fiery": [
            "Have you considered moving {player} up in the order? He's been our hottest hitter. I'd bat him {slot}.",
            "I want to shake things up. {player} should be hitting higher. The lineup needs energy.",
        ],
        "innovator": [
            "The data suggests {player} would produce more run value batting {slot}. The OBP and wRC+ support it.",
            "I ran the numbers on lineup optimization. Moving {player} to the {slot} spot could add 0.2 runs per game.",
        ],
        "default": [
            "Have you considered moving {player} up in the order? He's been swinging a hot bat lately.",
            "Just a thought - {player} in the {slot} spot could give us a spark. His recent numbers back it up.",
        ],
    },
}


def _check_coach_triggers(team_id: int, game_date: str,
                           db_path: str = None) -> list:
    """Check coach-specific trigger conditions."""
    sent = []

    # Only fire ~20% of the time to avoid flooding
    if random.random() > 0.20:
        return sent

    # Get the manager
    staff = query("""
        SELECT * FROM coaching_staff
        WHERE team_id=? AND role='manager' AND is_available=0
    """, (team_id,), db_path=db_path)
    if not staff:
        return sent
    coach = staff[0]
    coach_name = f"{coach['first_name']} {coach['last_name']}"
    personality = coach.get("philosophy", "balanced")
    # Map philosophy to message personality keys
    personality_key = {
        "aggressive": "fiery", "analytics": "innovator",
        "conservative": "steady", "balanced": "steady",
    }.get(personality, "default")
    char_id = str(coach["id"])

    # --- Prospect ready for call-up ---
    if not _is_on_cooldown("coach", char_id, "prospect_ready", team_id, game_date, db_path):
        prospect = _get_ready_prospect(team_id, db_path)
        if prospect:
            templates = COACH_PROACTIVE_MESSAGES["prospect_ready"].get(
                personality_key, COACH_PROACTIVE_MESSAGES["prospect_ready"]["default"])
            body = random.choice(templates).format(
                prospect=prospect["name"],
                level=prospect["level"],
                avg=prospect["avg"],
            )
            _send_character_message(
                team_id, "coach", f"{coach_name} (Manager)",
                f"About {prospect['name']}...", body, game_date, db_path
            )
            _record_message("coach", char_id, "prospect_ready", team_id,
                           game_date, DEFAULT_COOLDOWN_DAYS * 3, db_path)
            sent.append({"character_type": "coach", "trigger": "prospect_ready",
                        "character_name": coach_name})

    # --- Player struggling ---
    if not sent and not _is_on_cooldown("coach", char_id, "player_struggling", team_id, game_date, db_path):
        struggling = _get_struggling_player(team_id, db_path)
        if struggling:
            templates = COACH_PROACTIVE_MESSAGES["player_struggling"].get(
                personality_key, COACH_PROACTIVE_MESSAGES["player_struggling"]["default"])
            body = random.choice(templates).format(
                player=struggling["name"],
                avg=struggling["avg"],
            )
            _send_character_message(
                team_id, "coach", f"{coach_name} (Manager)",
                f"Concern about {struggling['name']}", body, game_date, db_path
            )
            _record_message("coach", char_id, "player_struggling", team_id,
                           game_date, DEFAULT_COOLDOWN_DAYS * 2, db_path)
            sent.append({"character_type": "coach", "trigger": "player_struggling",
                        "character_name": coach_name})

    # --- Lineup suggestion ---
    if not sent and not _is_on_cooldown("coach", char_id, "lineup_suggestion", team_id, game_date, db_path):
        hot_hitter = _get_hot_hitter(team_id, db_path)
        if hot_hitter and random.random() < 0.3:
            slots = ["2nd", "3rd", "cleanup", "leadoff"]
            slot = random.choice(slots)
            templates = COACH_PROACTIVE_MESSAGES["lineup_suggestion"].get(
                personality_key, COACH_PROACTIVE_MESSAGES["lineup_suggestion"]["default"])
            body = random.choice(templates).format(
                player=hot_hitter["name"], slot=slot)
            _send_character_message(
                team_id, "coach", f"{coach_name} (Manager)",
                "Lineup Thought", body, game_date, db_path
            )
            _record_message("coach", char_id, "lineup_suggestion", team_id,
                           game_date, DEFAULT_COOLDOWN_DAYS * 3, db_path)
            sent.append({"character_type": "coach", "trigger": "lineup_suggestion",
                        "character_name": coach_name})

    return sent


# ============================================================
# AGENT TRIGGERS
# ============================================================

AGENT_PROACTIVE_MESSAGES = {
    "contract_expiring": {
        "aggressive": [
            "Just giving you a heads up - my client {player}'s contract is up after this season. We'll be exploring all options. If you want to keep him, let's talk now before the price goes up.",
            "{player} has been a key piece for you. His deal expires soon. I've already gotten calls from other teams. Your move.",
        ],
        "player_first": [
            "My client {player} loves it here, but his contract is expiring. He'd like to stay if the deal is right. Can we start a conversation?",
            "{player} wants to know where he stands. His contract is up soon. He's hoping you'll make him a fair offer.",
        ],
        "collaborative": [
            "Hey, wanted to reach out about {player}. His contract expires after this season. I think we can work something out that's fair for everyone.",
            "{player}'s deal is up soon. Rather than wait for free agency, maybe we can find common ground on an extension?",
        ],
        "shark": [
            "Clock is ticking on {player}. Contract's up after this year. I've got four teams calling me already. If you want to keep him, you better act fast.",
            "You're going to see {player}'s name in every hot stove column this winter unless we get a deal done now. What's your best offer?",
        ],
        "passive": [
            "Just wanted to let you know {player}'s contract situation. His deal is up after this season. If you're interested in extending, we're open to talking.",
            "{player} has enjoyed his time with you. His contract expires soon. Let us know if you'd like to discuss an extension.",
        ],
    },
    "playing_time": {
        "aggressive": [
            "We need to discuss {player}'s role. He's not getting the at-bats he deserves. If this continues, we'll be requesting a trade.",
            "{player} is too good to sit on the bench. He needs regular playing time. Figure it out or we have a problem.",
        ],
        "player_first": [
            "{player} came to me about his playing time. He's frustrated. Can we find a way to get him more opportunities?",
            "My client {player} just wants to play. He's a competitor. Can we talk about getting him more at-bats?",
        ],
        "default": [
            "We need to discuss {player}'s role on the team. He's not happy with his playing time and I think we need to address it.",
            "{player} feels he's not getting a fair chance. Can we talk about his role going forward?",
        ],
    },
    "free_agent_interest": {
        "aggressive": [
            "{player} is available and has interest in playing for you. He's a difference-maker. Let's talk numbers.",
            "I represent {player} and I know you've got a need. He wants to compete for a winner. Your team fits.",
        ],
        "player_first": [
            "{player} has been following your team. He's interested in the fit. Should we explore this?",
            "My client {player} specifically mentioned wanting to play for your organization. I think it could work.",
        ],
        "default": [
            "{player} is a free agent and has expressed interest in playing for your team. Would you like to discuss?",
            "Reaching out because {player} is available and I think he'd be a great fit for what you're building.",
        ],
    },
}


def _check_agent_triggers(team_id: int, game_date: str,
                           db_path: str = None) -> list:
    """Check agent-specific trigger conditions."""
    sent = []

    # Only fire ~15% of the time
    if random.random() > 0.15:
        return sent

    # --- Contract expiring ---
    expiring_players = _get_expiring_contracts(team_id, db_path)
    for ep in expiring_players[:1]:  # Max 1 per day
        agent = ep.get("agent")
        if not agent:
            continue
        agent_name = agent["name"]
        char_id = str(agent["id"])
        personality = agent.get("personality", "collaborative")

        if _is_on_cooldown("agent", char_id, "contract_expiring", team_id, game_date, db_path):
            continue

        templates = AGENT_PROACTIVE_MESSAGES["contract_expiring"].get(
            personality, AGENT_PROACTIVE_MESSAGES["contract_expiring"].get("collaborative", []))
        if not templates:
            continue

        body = random.choice(templates).format(player=ep["name"])
        sender = f"{agent_name} ({agent.get('agency_name', 'Sports Agency')})"
        _send_character_message(
            team_id, "agent", sender,
            f"Regarding {ep['name']}'s Contract", body, game_date, db_path
        )
        _record_message("agent", char_id, "contract_expiring", team_id,
                       game_date, AGENT_COOLDOWN_DAYS * 5, db_path)
        sent.append({"character_type": "agent", "trigger": "contract_expiring",
                    "character_name": agent_name, "player": ep["name"]})

    # --- Playing time complaint ---
    if not sent:
        bench_player = _get_unhappy_bench_player(team_id, db_path)
        if bench_player and bench_player.get("agent"):
            agent = bench_player["agent"]
            char_id = str(agent["id"])
            if not _is_on_cooldown("agent", char_id, "playing_time", team_id, game_date, db_path):
                personality = agent.get("personality", "collaborative")
                templates = AGENT_PROACTIVE_MESSAGES["playing_time"].get(
                    personality, AGENT_PROACTIVE_MESSAGES["playing_time"]["default"])
                body = random.choice(templates).format(player=bench_player["name"])
                sender = f"{agent['name']} ({agent.get('agency_name', 'Sports Agency')})"
                _send_character_message(
                    team_id, "agent", sender,
                    f"About {bench_player['name']}'s Role", body, game_date, db_path
                )
                _record_message("agent", char_id, "playing_time", team_id,
                               game_date, AGENT_COOLDOWN_DAYS * 3, db_path)
                sent.append({"character_type": "agent", "trigger": "playing_time",
                            "character_name": agent["name"]})

    return sent


# ============================================================
# RIVAL GM TRIGGERS
# ============================================================

RIVAL_GM_MESSAGES = {
    "trade_inquiry": [
        "I've been looking at your roster and I think there might be a deal to be made. Got a few minutes to talk?",
        "My scouts have been watching some of your guys. I might have something that interests you. Let's chat.",
        "Just wanted to check in. We have some pieces that might fill a need for you. Interested in talking trade?",
        "Between you and me, my owner is pushing me to make a move. I think we could help each other out.",
    ],
    "hot_stove": [
        "Just checking in before the deadline. Any players you're looking to move?",
        "The hot stove is heating up. I've got assets and I'm looking to deal. You in the market?",
        "Everyone's making calls right now. Figured I'd reach out before the deadline madness.",
        "Hey, before the deadline hits - any chance you'd listen on some of your bullpen arms?",
    ],
    "sweetened_deal": [
        "What if we sweetened the deal? I can add a prospect to the package.",
        "I know we didn't connect last time, but I've got a new proposal that might change your mind.",
        "Let me try this again. I'll throw in an extra piece. Take another look?",
    ],
}


def _check_rival_gm_triggers(team_id: int, game_date: str,
                               db_path: str = None) -> list:
    """Check rival GM trigger conditions."""
    sent = []

    # Low probability per day - rival GMs are occasional
    if random.random() > 0.08:
        return sent

    game_date_obj = dt_date.fromisoformat(game_date)
    month = game_date_obj.month

    # Pick a random rival team
    rivals = query("""
        SELECT t.id, t.city, t.name FROM teams t
        WHERE t.id != ? ORDER BY RANDOM() LIMIT 1
    """, (team_id,), db_path=db_path)
    if not rivals:
        return sent
    rival = rivals[0]
    rival_name = f"{rival['city']} {rival['name']}"
    char_id = str(rival["id"])

    # Determine trigger type
    if month in (7,) and not _is_on_cooldown("rival_gm", char_id, "hot_stove", team_id, game_date, db_path):
        # Trade deadline month
        body = random.choice(RIVAL_GM_MESSAGES["hot_stove"])
        _send_character_message(
            team_id, "rival_gm", f"GM, {rival_name}",
            f"Call from {rival_name}", body, game_date, db_path
        )
        _record_message("rival_gm", char_id, "hot_stove", team_id,
                       game_date, RIVAL_GM_COOLDOWN_DAYS, db_path)
        sent.append({"character_type": "rival_gm", "trigger": "hot_stove",
                    "character_name": rival_name})
    elif not _is_on_cooldown("rival_gm", char_id, "trade_inquiry", team_id, game_date, db_path):
        body = random.choice(RIVAL_GM_MESSAGES["trade_inquiry"])
        _send_character_message(
            team_id, "rival_gm", f"GM, {rival_name}",
            f"Trade Interest from {rival_name}", body, game_date, db_path
        )
        _record_message("rival_gm", char_id, "trade_inquiry", team_id,
                       game_date, RIVAL_GM_COOLDOWN_DAYS, db_path)
        sent.append({"character_type": "rival_gm", "trigger": "trade_inquiry",
                    "character_name": rival_name})

    return sent


# ============================================================
# BEAT WRITER TRIGGERS
# ============================================================

BEAT_WRITER_NAMES = [
    "Mike Sullivan", "Sarah Chen", "David Rodriguez", "Emily Watson",
    "Chris Martinez", "Jessica Taylor", "Ryan O'Brien", "Amanda Brooks",
    "Tom Brennan", "Katie Morrison",
]

BEAT_WRITER_MESSAGES = {
    "wants_quote": [
        "Working on a piece about the team's direction this season. Any comment for the record?",
        "I'm writing a column about your offseason moves. Care to share your thought process?",
        "Deadline's tonight for my weekly column. The fans want to hear from the front office. Got a minute?",
        "Doing a feature on the team's youth movement. Would love a quote about your development philosophy.",
    ],
    "heard_rumor": [
        "I'm hearing from sources that the {rival_team} is interested in {player}. Any truth to that?",
        "Word around the league is that you've been getting calls about {player}. Care to comment?",
        "My sources tell me there's trade buzz around {player}. Is he available?",
        "Got a tip that a {division} rival has been scouting {player} heavily. Anything you want to say?",
    ],
    "hot_streak_story": [
        "Your team's been on a tear lately. I'd love to write about what's clicking. What changed?",
        "The fans are buzzing about this hot streak. What's been the key? I'm writing it up for tomorrow's edition.",
    ],
    "cold_streak_story": [
        "I know this isn't what you want to hear, but I need a comment on the recent struggles. My editor's asking.",
        "The fans are frustrated with the losing. I'm going to write something either way - better if it includes your perspective.",
    ],
}


def _check_beat_writer_triggers(team_id: int, game_date: str,
                                 db_path: str = None) -> list:
    """Check beat writer trigger conditions."""
    sent = []

    # Low probability - beat writers message occasionally
    if random.random() > 0.06:
        return sent

    writer_name = random.choice(BEAT_WRITER_NAMES)
    char_id = writer_name  # Use name as ID since there's no table

    # Determine what to write about
    streak = _get_recent_streak(team_id, db_path)

    if streak >= 5 and not _is_on_cooldown("beat_writer", char_id, "hot_streak_story", team_id, game_date, db_path):
        body = random.choice(BEAT_WRITER_MESSAGES["hot_streak_story"])
        _send_character_message(
            team_id, "reporter", f"{writer_name} (Beat Writer)",
            "Quick Question for a Story", body, game_date, db_path
        )
        _record_message("beat_writer", char_id, "hot_streak_story", team_id,
                       game_date, BEAT_WRITER_COOLDOWN_DAYS, db_path)
        sent.append({"character_type": "beat_writer", "trigger": "hot_streak_story",
                    "character_name": writer_name})
    elif streak <= -5 and not _is_on_cooldown("beat_writer", char_id, "cold_streak_story", team_id, game_date, db_path):
        body = random.choice(BEAT_WRITER_MESSAGES["cold_streak_story"])
        _send_character_message(
            team_id, "reporter", f"{writer_name} (Beat Writer)",
            "Need a Comment", body, game_date, db_path
        )
        _record_message("beat_writer", char_id, "cold_streak_story", team_id,
                       game_date, BEAT_WRITER_COOLDOWN_DAYS, db_path)
        sent.append({"character_type": "beat_writer", "trigger": "cold_streak_story",
                    "character_name": writer_name})
    elif not _is_on_cooldown("beat_writer", char_id, "heard_rumor", team_id, game_date, db_path):
        # Rumor about a player
        rumor = _get_trade_rumor_context(team_id, db_path)
        if rumor:
            body = random.choice(BEAT_WRITER_MESSAGES["heard_rumor"]).format(**rumor)
            _send_character_message(
                team_id, "reporter", f"{writer_name} (Beat Writer)",
                "Heard Something Interesting...", body, game_date, db_path
            )
            _record_message("beat_writer", char_id, "heard_rumor", team_id,
                           game_date, BEAT_WRITER_COOLDOWN_DAYS, db_path)
            sent.append({"character_type": "beat_writer", "trigger": "heard_rumor",
                        "character_name": writer_name})
    elif not _is_on_cooldown("beat_writer", char_id, "wants_quote", team_id, game_date, db_path):
        body = random.choice(BEAT_WRITER_MESSAGES["wants_quote"])
        _send_character_message(
            team_id, "reporter", f"{writer_name} (Beat Writer)",
            "Request for Comment", body, game_date, db_path
        )
        _record_message("beat_writer", char_id, "wants_quote", team_id,
                       game_date, BEAT_WRITER_COOLDOWN_DAYS, db_path)
        sent.append({"character_type": "beat_writer", "trigger": "wants_quote",
                    "character_name": writer_name})

    return sent


# ============================================================
# MESSAGE SENDING HELPER
# ============================================================

def _send_character_message(team_id: int, sender_type: str, sender_name: str,
                             subject: str, body: str, game_date: str,
                             db_path: str = None) -> int:
    """Send a message from a character using the messages table directly.
    Uses the same table as send_message() but with proper sender_type."""
    execute("""
        INSERT INTO messages (game_date, sender_type, sender_name, recipient_type,
                             recipient_id, subject, body, is_read, requires_response)
        VALUES (?, ?, ?, 'user', ?, ?, ?, 0, 0)
    """, (game_date, sender_type, sender_name, team_id, subject, body),
         db_path=db_path)

    result = query("""
        SELECT id FROM messages
        WHERE game_date=? AND recipient_id=? AND subject=?
        ORDER BY id DESC LIMIT 1
    """, (game_date, team_id, subject), db_path=db_path)

    return result[0]["id"] if result else None


# ============================================================
# DATA QUERY HELPERS
# ============================================================

def _get_losing_streak(team_id: int, db_path: str = None) -> int:
    """Get current consecutive loss count."""
    recent = query("""
        SELECT
            CASE
                WHEN home_team_id = ? THEN
                    CASE WHEN home_score > away_score THEN 'W' ELSE 'L' END
                ELSE
                    CASE WHEN away_score > home_score THEN 'W' ELSE 'L' END
            END as result
        FROM schedule
        WHERE (home_team_id=? OR away_team_id=?) AND is_played=1
        ORDER BY game_date DESC, id DESC
        LIMIT 20
    """, (team_id, team_id, team_id), db_path=db_path)

    streak = 0
    for g in recent:
        if g["result"] == "L":
            streak += 1
        else:
            break
    return streak


def _get_recent_streak(team_id: int, db_path: str = None) -> int:
    """Get recent streak (positive = winning, negative = losing)."""
    recent = query("""
        SELECT
            CASE
                WHEN home_team_id = ? THEN
                    CASE WHEN home_score > away_score THEN 'W' ELSE 'L' END
                ELSE
                    CASE WHEN away_score > home_score THEN 'W' ELSE 'L' END
            END as result
        FROM schedule
        WHERE (home_team_id=? OR away_team_id=?) AND is_played=1
        ORDER BY game_date DESC, id DESC
        LIMIT 20
    """, (team_id, team_id, team_id), db_path=db_path)

    if not recent:
        return 0

    first_result = recent[0]["result"]
    streak = 0
    for g in recent:
        if g["result"] == first_result:
            streak += 1
        else:
            break
    return streak if first_result == "W" else -streak


def _get_team_payroll(team_id: int, db_path: str = None) -> int:
    """Get total team payroll."""
    result = query("""
        SELECT COALESCE(SUM(c.annual_salary), 0) as payroll
        FROM contracts c
        JOIN players p ON c.player_id = p.id
        WHERE c.team_id=? AND p.roster_status != 'retired'
    """, (team_id,), db_path=db_path)
    return result[0]["payroll"] if result else 0


def _get_team_budget(team_id: int, owner: dict, db_path: str = None) -> int:
    """Estimate team budget based on owner willingness and market size."""
    team = query("SELECT market_size, franchise_value FROM teams WHERE id=?",
                 (team_id,), db_path=db_path)
    if not team:
        return 150_000_000

    market = team[0]["market_size"]
    willingness = owner.get("budget_willingness", 50)

    # Base budget scales with market size
    base = {1: 80_000_000, 2: 110_000_000, 3: 140_000_000,
            4: 180_000_000, 5: 220_000_000}.get(market, 140_000_000)

    # Willingness modifies budget +/- 30%
    modifier = 0.7 + (willingness / 100.0) * 0.6
    return int(base * modifier)


def _is_attendance_dropping(team_id: int, db_path: str = None) -> bool:
    """Check if fan loyalty has dropped below 35."""
    team = query("SELECT fan_loyalty FROM teams WHERE id=?",
                 (team_id,), db_path=db_path)
    return team[0]["fan_loyalty"] < 35 if team else False


def _get_ready_prospect(team_id: int, db_path: str = None) -> dict:
    """Find a prospect performing well in the minors."""
    prospects = query("""
        SELECT p.id, p.first_name, p.last_name, p.roster_status,
               p.contact_rating, p.power_rating, p.contact_potential, p.power_potential,
               bs.hits, bs.ab
        FROM players p
        LEFT JOIN batting_stats bs ON bs.player_id = p.id
        WHERE p.team_id=? AND p.age <= 25
        AND p.roster_status IN ('minors_aaa', 'minors_aa', 'minors_high_a')
        AND (p.contact_potential >= 60 OR p.power_potential >= 60
             OR p.stuff_potential >= 60 OR p.control_potential >= 60)
        ORDER BY (p.contact_potential + p.power_potential) DESC
        LIMIT 5
    """, (team_id,), db_path=db_path)

    for p in prospects:
        ab = p.get("ab") or 0
        hits = p.get("hits") or 0
        avg = f".{int(hits / ab * 1000):03d}" if ab >= 30 else ".---"
        if ab >= 30 and hits / ab >= 0.270:
            level = {"minors_aaa": "AAA", "minors_aa": "AA", "minors_high_a": "High-A", "minors_low": "A", "minors_rookie": "Rookie"}.get(
                p["roster_status"], "the minors")
            return {
                "name": f"{p['first_name']} {p['last_name']}",
                "level": level,
                "avg": avg,
            }

    # Even if stats aren't great, high-potential guys might be "ready"
    if prospects:
        p = prospects[0]
        ab = p.get("ab") or 0
        hits = p.get("hits") or 0
        avg = f".{int(hits / ab * 1000):03d}" if ab >= 30 else ".---"
        level = {"minors_aaa": "AAA", "minors_aa": "AA", "minors_high_a": "High-A", "minors_low": "A", "minors_rookie": "Rookie"}.get(
            p["roster_status"], "the minors")
        if random.random() < 0.3:
            return {"name": f"{p['first_name']} {p['last_name']}",
                    "level": level, "avg": avg}

    return None


def _get_struggling_player(team_id: int, db_path: str = None) -> dict:
    """Find an active player who is struggling."""
    players = query("""
        SELECT p.first_name, p.last_name, bs.ab, bs.hits
        FROM players p
        JOIN batting_stats bs ON bs.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.position NOT IN ('SP', 'RP')
        AND bs.ab >= 50
        AND CAST(bs.hits AS REAL) / bs.ab < 0.210
        ORDER BY CAST(bs.hits AS REAL) / bs.ab ASC
        LIMIT 3
    """, (team_id,), db_path=db_path)

    if players:
        p = random.choice(players)
        avg = f".{int(p['hits'] / p['ab'] * 1000):03d}" if p['ab'] > 0 else ".000"
        return {"name": f"{p['first_name']} {p['last_name']}", "avg": avg}
    return None


def _get_hot_hitter(team_id: int, db_path: str = None) -> dict:
    """Find a player who is hitting well."""
    players = query("""
        SELECT p.first_name, p.last_name, bs.ab, bs.hits
        FROM players p
        JOIN batting_stats bs ON bs.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.position NOT IN ('SP', 'RP')
        AND bs.ab >= 50
        AND CAST(bs.hits AS REAL) / bs.ab > 0.300
        ORDER BY CAST(bs.hits AS REAL) / bs.ab DESC
        LIMIT 3
    """, (team_id,), db_path=db_path)

    if players:
        p = random.choice(players)
        return {"name": f"{p['first_name']} {p['last_name']}"}
    return None


def _get_expiring_contracts(team_id: int, db_path: str = None) -> list:
    """Get players whose contracts expire after this season."""
    players = query("""
        SELECT p.id, p.first_name, p.last_name, p.position, c.years_remaining
        FROM contracts c
        JOIN players p ON c.player_id = p.id
        WHERE c.team_id=? AND c.years_remaining = 1
        AND p.roster_status = 'active'
        ORDER BY c.annual_salary DESC
        LIMIT 5
    """, (team_id,), db_path=db_path)

    result = []
    for p in players:
        agent = _get_player_agent_safe(p["id"], db_path)
        result.append({
            "name": f"{p['first_name']} {p['last_name']}",
            "player_id": p["id"],
            "agent": agent,
        })
    return result


def _get_unhappy_bench_player(team_id: int, db_path: str = None) -> dict:
    """Find a decent player with low playing time (potential playing time complaint)."""
    players = query("""
        SELECT p.id, p.first_name, p.last_name,
               COALESCE(bs.ab, 0) as ab,
               CASE WHEN p.position IN ('SP', 'RP')
                   THEN (p.stuff_rating + p.control_rating) / 2
                   ELSE (p.contact_rating + p.power_rating) / 2
               END as talent
        FROM players p
        LEFT JOIN batting_stats bs ON bs.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.position NOT IN ('SP', 'RP')
        ORDER BY talent DESC
        LIMIT 15
    """, (team_id,), db_path=db_path)

    # Find a talented player with low AB count (suggesting bench role)
    for p in players:
        if p["talent"] >= 50 and p["ab"] < 100:
            agent = _get_player_agent_safe(p["id"], db_path)
            if agent:
                return {
                    "name": f"{p['first_name']} {p['last_name']}",
                    "player_id": p["id"],
                    "agent": agent,
                }
    return None


def _get_player_agent_safe(player_id: int, db_path: str = None) -> dict:
    """Safely get a player's agent, returning None if not found."""
    try:
        rows = query("""
            SELECT ac.* FROM agent_characters ac
            JOIN player_agents pa ON pa.agent_id = ac.id
            WHERE pa.player_id = ?
        """, (player_id,), db_path=db_path)
        return dict(rows[0]) if rows else None
    except Exception:
        return None


def _get_trade_rumor_context(team_id: int, db_path: str = None) -> dict:
    """Generate context for a trade rumor from a beat writer."""
    # Pick a notable player from the team
    players = query("""
        SELECT p.first_name, p.last_name
        FROM players p
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.position NOT IN ('SP', 'RP')
        ORDER BY (p.contact_rating + p.power_rating) DESC
        LIMIT 5
    """, (team_id,), db_path=db_path)

    if not players:
        return None

    player = random.choice(players)
    player_name = f"{player['first_name']} {player['last_name']}"

    # Pick a rival team
    team = query("SELECT league, division FROM teams WHERE id=?",
                 (team_id,), db_path=db_path)
    if not team:
        return None

    rivals = query("""
        SELECT city, name, division FROM teams
        WHERE id != ? ORDER BY RANDOM() LIMIT 1
    """, (team_id,), db_path=db_path)

    if not rivals:
        return None

    rival = rivals[0]
    return {
        "player": player_name,
        "rival_team": f"{rival['city']} {rival['name']}",
        "division": rival["division"],
    }


# ============================================================
# EVENT-DRIVEN REACTIONS
# Characters react to specific game events as they happen.
# These are called from the event sources (injuries, roster
# moves, signings, milestones, etc.) instead of being polled.
# ============================================================

def send_injury_reactions(team_id: int, game_date: str, player_name: str,
                          injury_type: str, il_tier: str, player_id: int = None,
                          db_path: str = None) -> list:
    """React to a key player injury. Coach, beat writer, and agent respond."""
    sent = []
    _ensure_table_exists(db_path)

    # --- Coach reaction ---
    staff = query("""
        SELECT * FROM coaching_staff
        WHERE team_id=? AND role='manager' AND is_available=0
    """, (team_id,), db_path=db_path)
    if staff:
        coach = staff[0]
        coach_name = f"{coach['first_name']} {coach['last_name']}"
        char_id = str(coach["id"])
        if not _is_on_cooldown("coach", char_id, "injury_reaction", team_id, game_date, db_path):
            personality = coach.get("philosophy", "balanced")
            severity = "out a while" if il_tier == "60-day" else "day-to-day"
            coach_templates = {
                "aggressive": [
                    f"Losing {player_name} to a {injury_type} hurts. We need somebody to step up NOW. "
                    f"Next man up mentality.",
                    f"{player_name} is down with a {injury_type}. This is a gut check for the whole team. "
                    f"I'll adjust the lineup.",
                ],
                "analytics": [
                    f"With {player_name} out ({injury_type}), I've been looking at our depth options. "
                    f"The numbers say we can cover this. Let me show you what I'm thinking.",
                    f"We lose some WAR with {player_name} on the shelf, but I think we can "
                    f"redistribute production. Let me work on the matchups.",
                ],
                "conservative": [
                    f"Hate to see {player_name} go down with a {injury_type}. "
                    f"We'll be careful with the replacement. No need to panic.",
                    f"{player_name}'s {injury_type} is a setback, but we've got capable guys ready. "
                    f"We'll manage.",
                ],
                "default": [
                    f"Just wanted to let you know I'm adjusting things with {player_name} out. "
                    f"The {injury_type} looks like he'll be {severity}. We'll manage.",
                    f"Tough blow losing {player_name} to a {injury_type}. "
                    f"I have some ideas on how to fill the gap.",
                ],
            }
            key = {"aggressive": "aggressive", "analytics": "analytics",
                   "conservative": "conservative"}.get(personality, "default")
            body = random.choice(coach_templates.get(key, coach_templates["default"]))
            _send_character_message(
                team_id, "coach", f"{coach_name} (Manager)",
                f"{player_name} Injury Update", body, game_date, db_path
            )
            _record_message("coach", char_id, "injury_reaction", team_id,
                           game_date, 2, db_path)
            sent.append({"character_type": "coach", "trigger": "injury_reaction"})

    # --- Beat writer reaction (asks for comment on significant injuries) ---
    if il_tier in ("15-day", "60-day"):
        writer_name = random.choice(BEAT_WRITER_NAMES)
        char_id = writer_name
        if not _is_on_cooldown("beat_writer", char_id, "injury_story", team_id, game_date, db_path):
            writer_templates = [
                f"Just heard {player_name} is heading to the IL with a {injury_type}. "
                f"How does this affect the team's plans? I need a quote for the story.",
                f"Sources saying {player_name} has a {injury_type}. This is a big loss. "
                f"Any idea on the timeline? My readers are going to want to know.",
                f"Breaking: {player_name} to the {il_tier} IL ({injury_type}). "
                f"What's the plan to replace his production? Filing in an hour.",
            ]
            _send_character_message(
                team_id, "reporter", f"{writer_name} (Beat Writer)",
                f"Injury Report: {player_name}", random.choice(writer_templates),
                game_date, db_path
            )
            _record_message("beat_writer", char_id, "injury_story", team_id,
                           game_date, 3, db_path)
            sent.append({"character_type": "beat_writer", "trigger": "injury_story"})

    # --- Agent reaction (if player has an agent and it's a serious injury) ---
    if player_id and il_tier in ("15-day", "60-day"):
        agent = _get_player_agent_safe(player_id, db_path)
        if agent:
            agent_name = agent["name"]
            char_id = str(agent["id"])
            if not _is_on_cooldown("agent", char_id, "injury_concern", team_id, game_date, db_path):
                personality = agent.get("personality", "collaborative")
                agent_templates = {
                    "aggressive": [
                        f"I just heard about {player_name}'s {injury_type}. I need to know he's "
                        f"getting the best medical care. Don't rush him back.",
                        f"We need to talk about {player_name}. A {injury_type} is serious. "
                        f"I want to make sure the team's medical staff has a proper rehab plan.",
                    ],
                    "player_first": [
                        f"{player_name} called me about the {injury_type}. He's worried. "
                        f"Can you assure me the team will take care of him?",
                        f"Just checking in on {player_name}. He's dealing with a lot right now. "
                        f"The {injury_type} has him down. Please take good care of him.",
                    ],
                    "default": [
                        f"Reaching out about {player_name}'s {injury_type}. "
                        f"I'd appreciate an update on the timeline when you have one.",
                        f"Wanted to check in on {player_name}. How's the {injury_type} looking? "
                        f"We just want to make sure everything is being handled well.",
                    ],
                }
                key = personality if personality in agent_templates else "default"
                body = random.choice(agent_templates[key])
                sender = f"{agent_name} ({agent.get('agency_name', 'Sports Agency')})"
                _send_character_message(
                    team_id, "agent", sender,
                    f"Checking on {player_name}", body, game_date, db_path
                )
                _record_message("agent", char_id, "injury_concern", team_id,
                               game_date, 5, db_path)
                sent.append({"character_type": "agent", "trigger": "injury_concern"})

    return sent


def send_callup_reactions(team_id: int, game_date: str, player_name: str,
                          from_level: str = "AAA", db_path: str = None) -> list:
    """React to a prospect call-up. Coach and beat writer respond."""
    sent = []
    _ensure_table_exists(db_path)

    # --- Coach reaction ---
    staff = query("""
        SELECT * FROM coaching_staff
        WHERE team_id=? AND role='manager' AND is_available=0
    """, (team_id,), db_path=db_path)
    if staff:
        coach = staff[0]
        coach_name = f"{coach['first_name']} {coach['last_name']}"
        char_id = str(coach["id"])
        if not _is_on_cooldown("coach", char_id, "callup_reaction", team_id, game_date, db_path):
            coach_templates = [
                f"Good call bringing up {player_name}. I've been watching him in {from_level} "
                f"and I think he's ready. I'll find him at-bats right away.",
                f"Excited to have {player_name} up here. The reports from {from_level} "
                f"were outstanding. I'll work him into the lineup this week.",
                f"{player_name} joining us from {from_level} is a shot of energy this team needs. "
                f"The clubhouse is buzzing about the kid.",
                f"I'll take good care of {player_name}. He earned this promotion from {from_level}. "
                f"Might ease him in off the bench first, then we'll see.",
            ]
            _send_character_message(
                team_id, "coach", f"{coach_name} (Manager)",
                f"Welcome {player_name}", random.choice(coach_templates),
                game_date, db_path
            )
            _record_message("coach", char_id, "callup_reaction", team_id,
                           game_date, 5, db_path)
            sent.append({"character_type": "coach", "trigger": "callup_reaction"})

    # --- Beat writer covers the call-up ---
    writer_name = random.choice(BEAT_WRITER_NAMES)
    char_id = writer_name
    if not _is_on_cooldown("beat_writer", char_id, "callup_story", team_id, game_date, db_path):
        writer_templates = [
            f"Hearing that {player_name} is getting the call from {from_level}. "
            f"What's the plan for him? Everyday player or easing him in?",
            f"The {player_name} call-up is the story of the day. Prospect hounds are excited. "
            f"How do you see him fitting in with the big league club?",
            f"Sources confirm {player_name} is being promoted from {from_level}. "
            f"The fans have been waiting for this. Any comment on his role?",
        ]
        _send_character_message(
            team_id, "reporter", f"{writer_name} (Beat Writer)",
            f"Call-Up: {player_name}", random.choice(writer_templates),
            game_date, db_path
        )
        _record_message("beat_writer", char_id, "callup_story", team_id,
                       game_date, 3, db_path)
        sent.append({"character_type": "beat_writer", "trigger": "callup_story"})

    return sent


def send_signing_reactions(team_id: int, game_date: str, player_name: str,
                           salary: int, years: int, db_path: str = None) -> list:
    """React to a free agent signing. Owner and beat writer respond."""
    sent = []
    _ensure_table_exists(db_path)

    salary_m = salary / 1_000_000
    total_m = salary_m * years

    # --- Owner reaction ---
    owner = query("SELECT * FROM owner_characters WHERE team_id=?",
                  (team_id,), db_path=db_path)
    if owner:
        owner = owner[0]
        owner_name = f"{owner['first_name']} {owner['last_name']}"
        char_id = str(owner["id"])
        archetype = owner.get("archetype", "balanced")
        if not _is_on_cooldown("owner", char_id, "signing_reaction", team_id, game_date, db_path):
            if total_m >= 50:  # Big contract
                owner_templates = {
                    "budget_conscious": [
                        f"${total_m:.0f}M for {player_name}? That's a lot of money. "
                        f"He better be worth every penny. I'm trusting your judgment here.",
                        f"I see we're committing ${salary_m:.0f}M a year to {player_name}. "
                        f"That's a big chunk of the budget. This better pay off.",
                    ],
                    "win_now": [
                        f"Love the {player_name} signing! ${salary_m:.0f}M/year shows we're "
                        f"serious about winning. This is the kind of move I want to see.",
                        f"{player_name} is exactly what we needed. The money? Don't worry about it. "
                        f"I want a championship.",
                    ],
                    "default": [
                        f"Good signing getting {player_name}. {years} years, ${salary_m:.0f}M per. "
                        f"I think the fans will be excited about this one.",
                        f"Just saw the {player_name} deal. ${total_m:.0f}M total. "
                        f"I hope this is the piece that puts us over the top.",
                    ],
                }
            else:  # Smaller deal
                owner_templates = {
                    "default": [
                        f"Nice pickup getting {player_name}. Smart, affordable move.",
                        f"I like the {player_name} signing. Good value at ${salary_m:.1f}M.",
                    ],
                }
            key = archetype if archetype in owner_templates else "default"
            body = random.choice(owner_templates.get(key, owner_templates["default"]))
            _send_character_message(
                team_id, "owner", owner_name, f"Re: {player_name} Signing",
                body, game_date, db_path
            )
            _record_message("owner", char_id, "signing_reaction", team_id,
                           game_date, 3, db_path)
            sent.append({"character_type": "owner", "trigger": "signing_reaction"})

    # --- Beat writer wants a quote ---
    if total_m >= 20 or years >= 3:  # Newsworthy signings only
        writer_name = random.choice(BEAT_WRITER_NAMES)
        char_id = writer_name
        if not _is_on_cooldown("beat_writer", char_id, "signing_story", team_id, game_date, db_path):
            writer_templates = [
                f"The {player_name} signing is official. {years} years, ${salary_m:.0f}M AAV. "
                f"How does he fit into the plan? I'm putting together a column.",
                f"Just got confirmation on the {player_name} deal. ${total_m:.0f}M total. "
                f"Big investment. What made him the guy?",
                f"Fans are reacting to the {player_name} signing. "
                f"Some love it, some hate the money. What's the message from the front office?",
            ]
            _send_character_message(
                team_id, "reporter", f"{writer_name} (Beat Writer)",
                f"New Signing: {player_name}", random.choice(writer_templates),
                game_date, db_path
            )
            _record_message("beat_writer", char_id, "signing_story", team_id,
                           game_date, 3, db_path)
            sent.append({"character_type": "beat_writer", "trigger": "signing_story"})

    return sent


def send_milestone_reactions(team_id: int, game_date: str, player_name: str,
                             milestone: str, db_path: str = None) -> list:
    """React to a player milestone or record. Beat writer and owner respond."""
    sent = []
    _ensure_table_exists(db_path)

    # --- Beat writer wants the story ---
    writer_name = random.choice(BEAT_WRITER_NAMES)
    char_id = writer_name
    if not _is_on_cooldown("beat_writer", char_id, "milestone_story", team_id, game_date, db_path):
        writer_templates = [
            f"Historic moment for {player_name}: {milestone}! "
            f"I'm writing a feature piece. Can I get a quote from the front office?",
            f"{player_name} just hit a milestone - {milestone}. "
            f"The fans are going crazy. What does this moment mean to the organization?",
            f"Incredible achievement by {player_name}: {milestone}. "
            f"I need a comment from the GM for the story. This is front-page stuff.",
        ]
        _send_character_message(
            team_id, "reporter", f"{writer_name} (Beat Writer)",
            f"Milestone: {player_name}", random.choice(writer_templates),
            game_date, db_path
        )
        _record_message("beat_writer", char_id, "milestone_story", team_id,
                       game_date, 3, db_path)
        sent.append({"character_type": "beat_writer", "trigger": "milestone_story"})

    # --- Owner congratulates ---
    owner = query("SELECT * FROM owner_characters WHERE team_id=?",
                  (team_id,), db_path=db_path)
    if owner:
        owner = owner[0]
        owner_name = f"{owner['first_name']} {owner['last_name']}"
        char_id = str(owner["id"])
        if not _is_on_cooldown("owner", char_id, "milestone_reaction", team_id, game_date, db_path):
            owner_templates = [
                f"Did you see {player_name}? {milestone}! "
                f"That's the kind of thing that makes owning a team worth it. Congratulations.",
                f"{player_name} - {milestone}. Outstanding. "
                f"Make sure he knows how much we appreciate what he's doing for this franchise.",
                f"What a moment for {player_name}. {milestone}. "
                f"This is good for the brand. The whole city is talking about us.",
            ]
            _send_character_message(
                team_id, "owner", owner_name,
                f"Congrats on {player_name}", random.choice(owner_templates),
                game_date, db_path
            )
            _record_message("owner", char_id, "milestone_reaction", team_id,
                           game_date, 5, db_path)
            sent.append({"character_type": "owner", "trigger": "milestone_reaction"})

    return sent


def send_dfa_reactions(team_id: int, game_date: str, player_name: str,
                       player_id: int = None, db_path: str = None) -> list:
    """React to a player being DFA'd. Beat writer and agent respond."""
    sent = []
    _ensure_table_exists(db_path)

    # --- Beat writer asks about the move ---
    writer_name = random.choice(BEAT_WRITER_NAMES)
    char_id = writer_name
    if not _is_on_cooldown("beat_writer", char_id, "dfa_story", team_id, game_date, db_path):
        writer_templates = [
            f"Sources say {player_name} has been designated for assignment. "
            f"Surprising move. What led to this decision?",
            f"Just got word on the {player_name} DFA. "
            f"The fans are going to have questions. Can I get a comment?",
            f"{player_name} DFA'd. That's a roster shakeup. "
            f"Is this about making room for someone or a performance decision?",
        ]
        _send_character_message(
            team_id, "reporter", f"{writer_name} (Beat Writer)",
            f"DFA: {player_name}", random.choice(writer_templates),
            game_date, db_path
        )
        _record_message("beat_writer", char_id, "dfa_story", team_id,
                       game_date, 3, db_path)
        sent.append({"character_type": "beat_writer", "trigger": "dfa_story"})

    # --- Agent is unhappy ---
    if player_id:
        agent = _get_player_agent_safe(player_id, db_path)
        if agent:
            agent_name = agent["name"]
            char_id = str(agent["id"])
            if not _is_on_cooldown("agent", char_id, "dfa_reaction", team_id, game_date, db_path):
                personality = agent.get("personality", "collaborative")
                agent_templates = {
                    "aggressive": [
                        f"You DFA'd {player_name}? We're going to remember this. "
                        f"My client deserved better than being thrown away.",
                        f"I can't believe you're cutting {player_name} loose. "
                        f"This is going to make it very hard for us to do business in the future.",
                    ],
                    "shark": [
                        f"So {player_name} is DFA'd. Fine. I'll have him signed somewhere else "
                        f"by the end of the week. Your loss.",
                        f"You're making a mistake letting {player_name} go. "
                        f"Mark my words, you'll regret this.",
                    ],
                    "player_first": [
                        f"{player_name} is devastated by the DFA. He gave everything to this team. "
                        f"I hope you at least had the decency to tell him face to face.",
                        f"My client is hurting right now. The DFA was unexpected. "
                        f"I just hope he lands somewhere that appreciates him.",
                    ],
                    "default": [
                        f"I understand the {player_name} DFA is a business decision. "
                        f"I'll be working to find him a new home.",
                        f"Disappointed about {player_name}, but I get it. "
                        f"Any chance you'd work out a trade instead of putting him through waivers?",
                    ],
                }
                key = personality if personality in agent_templates else "default"
                body = random.choice(agent_templates[key])
                sender = f"{agent_name} ({agent.get('agency_name', 'Sports Agency')})"
                _send_character_message(
                    team_id, "agent", sender,
                    f"About {player_name}'s DFA", body, game_date, db_path
                )
                _record_message("agent", char_id, "dfa_reaction", team_id,
                               game_date, 5, db_path)
                sent.append({"character_type": "agent", "trigger": "dfa_reaction"})

    return sent


def send_deadline_urgency(team_id: int, game_date: str,
                          db_path: str = None) -> list:
    """Send urgent messages as the trade deadline approaches (last 3 days of July)."""
    sent = []
    _ensure_table_exists(db_path)

    from datetime import date as date_cls
    d = date_cls.fromisoformat(game_date)
    if d.month != 7 or d.day < 29:
        return sent

    days_left = 31 - d.day  # July has 31 days, deadline is July 31

    # --- Rival GMs get aggressive ---
    rivals = query("""
        SELECT t.id, t.city, t.name FROM teams t
        WHERE t.id != ? ORDER BY RANDOM() LIMIT 2
    """, (team_id,), db_path=db_path)
    for rival in rivals:
        char_id = str(rival["id"])
        rival_name = f"{rival['city']} {rival['name']}"
        if not _is_on_cooldown("rival_gm", char_id, "deadline_push", team_id, game_date, db_path):
            if days_left <= 1:
                templates = [
                    "Last chance. Deadline's in hours. I have a deal that works for both of us. "
                    "Yes or no?",
                    "Clock is ticking. I need an answer on a deal today or I'm calling someone else.",
                    "Final offer. After today, we're done. What do you say?",
                ]
            else:
                templates = [
                    f"We've got {days_left} days until the deadline. I'm ready to make a move. "
                    f"Are you buying or selling?",
                    f"Deadline is {days_left} days away. My owner wants a splash. "
                    f"Got anyone you'd move?",
                ]
            _send_character_message(
                team_id, "rival_gm", f"GM, {rival_name}",
                "Trade Deadline", random.choice(templates), game_date, db_path
            )
            _record_message("rival_gm", char_id, "deadline_push", team_id,
                           game_date, 2, db_path)
            sent.append({"character_type": "rival_gm", "trigger": "deadline_push",
                        "character_name": rival_name})

    # --- Beat writer wants deadline preview ---
    writer_name = random.choice(BEAT_WRITER_NAMES)
    char_id = writer_name
    if not _is_on_cooldown("beat_writer", char_id, "deadline_story", team_id, game_date, db_path):
        if days_left <= 1:
            templates = [
                "It's deadline day. Phones are ringing across the league. "
                "Are you a buyer or a seller? I need to file my story.",
                "Trade deadline is HERE. My sources say you've been in talks with multiple teams. "
                "Anything close to getting done?",
            ]
        else:
            templates = [
                f"Trade deadline is {days_left} days away. The whole league is making calls. "
                f"Where does your team stand? Buying or selling?",
                f"I'm writing my deadline preview piece. {days_left} days to go. "
                f"Any hints on what moves the front office is considering?",
            ]
        _send_character_message(
            team_id, "reporter", f"{writer_name} (Beat Writer)",
            "Trade Deadline Watch", random.choice(templates), game_date, db_path
        )
        _record_message("beat_writer", char_id, "deadline_story", team_id,
                       game_date, 2, db_path)
        sent.append({"character_type": "beat_writer", "trigger": "deadline_story"})

    # --- Agents push for clarity ---
    expiring = _get_expiring_contracts(team_id, db_path)
    for ep in expiring[:1]:
        agent = ep.get("agent")
        if not agent:
            continue
        char_id = str(agent["id"])
        if not _is_on_cooldown("agent", char_id, "deadline_pressure", team_id, game_date, db_path):
            templates = [
                f"Deadline's almost here. If you're not going to extend {ep['name']}, "
                f"I need to know NOW so we can plan for free agency.",
                f"With the deadline {days_left} days away, other teams are calling about {ep['name']}. "
                f"Are you trading him or extending him? I need an answer.",
            ]
            sender = f"{agent['name']} ({agent.get('agency_name', 'Sports Agency')})"
            _send_character_message(
                team_id, "agent", sender,
                f"Deadline: {ep['name']}'s Future", random.choice(templates),
                game_date, db_path
            )
            _record_message("agent", char_id, "deadline_pressure", team_id,
                           game_date, 3, db_path)
            sent.append({"character_type": "agent", "trigger": "deadline_pressure"})

    return sent


def send_option_reactions(team_id: int, game_date: str, player_name: str,
                          level: str = "AAA", player_id: int = None,
                          db_path: str = None) -> list:
    """React to a player being optioned to the minors."""
    sent = []
    _ensure_table_exists(db_path)

    # --- Agent unhappy about demotion ---
    if player_id:
        agent = _get_player_agent_safe(player_id, db_path)
        if agent:
            agent_name = agent["name"]
            char_id = str(agent["id"])
            if not _is_on_cooldown("agent", char_id, "option_reaction", team_id, game_date, db_path):
                personality = agent.get("personality", "collaborative")
                agent_templates = {
                    "aggressive": [
                        f"Sending {player_name} down to {level}? He's not going to be happy about this. "
                        f"You're hurting his development by jerking him around.",
                        f"{player_name} deserves a real shot, not a bus ticket to {level}. "
                        f"This better be temporary.",
                    ],
                    "player_first": [
                        f"{player_name} is disappointed about the {level} assignment. "
                        f"He was hoping to prove himself up here. When can he expect another chance?",
                        f"I get the roster math, but {player_name} took the {level} option hard. "
                        f"Just wanted you to know where his head is at.",
                    ],
                    "default": [
                        f"I understand the {player_name} option to {level}. "
                        f"Can you give me a timeline on when he might be back?",
                        f"My client {player_name} is heading to {level}. He'll make the most of it. "
                        f"Just keep him in mind when a spot opens up.",
                    ],
                }
                key = personality if personality in agent_templates else "default"
                body = random.choice(agent_templates[key])
                sender = f"{agent_name} ({agent.get('agency_name', 'Sports Agency')})"
                _send_character_message(
                    team_id, "agent", sender,
                    f"Re: {player_name} to {level}", body, game_date, db_path
                )
                _record_message("agent", char_id, "option_reaction", team_id,
                               game_date, 7, db_path)
                sent.append({"character_type": "agent", "trigger": "option_reaction"})

    return sent
