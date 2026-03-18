"""
Front Office - Proactive AI Character Messaging
Characters (owner, rival GMs, agents, coaches, beat writers) proactively
reach out to the user/GM based on game events.

Each character type has trigger conditions and personality-driven message
templates. A cooldown system prevents message spam.
"""
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
        AND p.roster_status IN ('minors_aaa', 'minors_aa')
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
            level = {"minors_aaa": "AAA", "minors_aa": "AA"}.get(
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
        level = {"minors_aaa": "AAA", "minors_aa": "AA"}.get(
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
