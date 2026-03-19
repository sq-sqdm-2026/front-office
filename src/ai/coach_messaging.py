"""
Front Office - Coach Messaging Integration
Handles proactive and reactive messaging between coaches and the GM.
Coaches are interactive characters with personalities who message you through the chat system.
"""
from ..database.db import execute, query
from ..transactions.messages import send_message


# Coach response templates based on personality type
COACH_RESPONSES = {
    "fiery": {
        "lineup_pressure": [
            "Look, I've been managing for {experience} years. I know what I'm doing with this lineup.",
            "You want to manage? Then sit in the dugout. Otherwise, let me do my job.",
            "Fine. I'll make the change. But if it backfires, that's on YOU.",
            "I hear you, boss. But I'm telling you, my gut says this is the right call.",
        ],
        "agree": [
            "You're right. I should've seen that. Making the change now.",
            "Good call. I was actually thinking the same thing.",
        ],
        "proactive_concern": [
            "We need to talk. {player_name} is struggling and I'm worried.",
            "The bullpen is GASSED. If you don't get me help, we're going to blow some games.",
            "I can't keep running {player_name} out there every day. The kid needs a breather.",
        ],
        "prospect_ready": [
            "I've been watching {prospect_name} in the minors. Kid's READY. Bring him up.",
            "You've got a stud in {level}. {prospect_name} is tearing the cover off the ball.",
        ],
        "winning_streak": [
            "Don't change a thing. This lineup is ROLLING right now!",
            "Whatever you're doing, keep doing it. The boys are locked in.",
        ],
        "losing_streak": [
            "We need a shake-up. This isn't working and everyone knows it.",
            "I'm running out of answers here. Can we look at making a move?",
        ],
    },
    "steady": {
        "lineup_pressure": [
            "I understand your thinking. Let me look at the numbers and consider it.",
            "I appreciate the input. I'll work {player_name} into the lineup this week.",
            "That's a fair point. I'll adjust things for the next series.",
        ],
        "agree": [
            "Makes sense. I'll take care of it.",
            "You got it. Consider it done.",
        ],
        "proactive_concern": [
            "{player_name}'s numbers have been trending down. We might want to give him a day or two off.",
            "The pitching staff could use a fresh arm. Anyone in the minors worth looking at?",
            "Just a heads up - {player_name} seems a little tight. Might be dealing with something.",
        ],
        "prospect_ready": [
            "{prospect_name} has been performing well in {level}. Worth considering a call-up when the time is right.",
            "I've been getting good reports on {prospect_name}. Steady improvement across the board.",
        ],
        "winning_streak": [
            "Good stretch. Let's stay focused and keep doing what got us here.",
            "The guys are playing well. No need to overthink it.",
        ],
        "losing_streak": [
            "Rough stretch, but I've seen enough to know this team is better than this. We'll turn it around.",
            "Let's not panic. The process is right, results will follow.",
        ],
    },
    "players_coach": {
        "lineup_pressure": [
            "I hear you, but {player_name} needs to know we believe in him. Benching him now would send the wrong message.",
            "I'll talk to {player_name}. If we're going to make a change, I want him to hear it from me first.",
            "Let me handle it my way. Relationships matter in this clubhouse.",
        ],
        "agree": [
            "I'll sit down with {player_name} and explain. He'll understand.",
            "Good idea. I think {player_name} could actually use the rest.",
        ],
        "proactive_concern": [
            "I sat down with {player_name} after the game. Something's off. Personal stuff, I think.",
            "The guys are feeling the pressure. Morale could use a boost - maybe a team dinner?",
            "{player_name} came to me. He's frustrated with his playing time. Can we find him some at-bats?",
        ],
        "prospect_ready": [
            "{prospect_name} is mature beyond his years. The clubhouse would welcome him.",
            "I've talked to some of the vets about {prospect_name}. They're excited to work with the kid.",
        ],
        "winning_streak": [
            "The chemistry in this clubhouse is special right now. These guys love playing together.",
            "You can feel the energy. The guys are having FUN out there.",
        ],
        "losing_streak": [
            "The guys are pressing. They want it too bad. I told them to relax and trust their talent.",
            "Nobody's pointing fingers. That's a good sign. This group will stick together.",
        ],
    },
    "disciplinarian": {
        "lineup_pressure": [
            "Noted. But in my dugout, you earn your spot. {player_name} hasn't earned it yet.",
            "I'll make the change, but {player_name} needs to show me something in BP first.",
            "Fair enough. But I'm holding him accountable. Soft effort won't be tolerated.",
        ],
        "agree": [
            "Agreed. No excuses. Making the move.",
            "Done. And he'll know exactly why.",
        ],
        "proactive_concern": [
            "{player_name} was late to the park today. Not acceptable. I'm considering sitting him.",
            "I benched {player_name} for lack of hustle. Just letting you know.",
            "The fundamentals have been sloppy. I'm adding extra work before games this week.",
        ],
        "prospect_ready": [
            "{prospect_name} has the tools, but does he have the work ethic? I'll find out quickly.",
            "If {prospect_name} comes up, he follows my rules like everyone else. No special treatment.",
        ],
        "winning_streak": [
            "Good. But we haven't won anything yet. Stay hungry.",
            "Don't get comfortable. The work continues.",
        ],
        "losing_streak": [
            "Unacceptable. I'm making changes. Players who don't compete don't play.",
            "Something has to change. Starting with accountability.",
        ],
    },
    "innovator": {
        "lineup_pressure": [
            "I was actually looking at the data on that. The matchup numbers support your idea.",
            "Interesting thought. Let me run the platoon splits and get back to you.",
            "The analytics say {player_name} should be higher in the order. I'll make the adjustment.",
        ],
        "agree": [
            "The numbers back it up. Good call.",
            "I was thinking the same thing. The data is clear.",
        ],
        "proactive_concern": [
            "{player_name}'s exit velocity has dropped 4 mph over the last two weeks. Something's off mechanically.",
            "I've been tracking pitch usage and our bullpen is at critical fatigue levels. We need an arm.",
            "The defensive metrics say we should shift {player_name} to a different position.",
        ],
        "prospect_ready": [
            "The underlying numbers for {prospect_name} are elite. xBA, barrel rate, chase rate - all top-tier.",
            "{prospect_name}'s statcast data in {level} is off the charts. The projection models love him.",
        ],
        "winning_streak": [
            "The run differential says this is sustainable. We're genuinely outplaying opponents.",
            "The process is working. The analytics are validating our approach.",
        ],
        "losing_streak": [
            "The underlying metrics aren't as bad as the record suggests. Some bad luck is involved.",
            "I've identified some adjustments. Small changes to the lineup construction should help.",
        ],
    },
}

# Hitting coach specific messages
HITTING_COACH_MESSAGES = {
    "slump_report": [
        "{player_name}'s swing has gotten long. We're working on shortening it up in the cage.",
        "I've noticed {player_name} is pulling off the ball. We're making an adjustment.",
        "{player_name} is chasing too many pitches outside the zone. We're working on plate discipline.",
        "Good news - {player_name}'s bat speed is still elite. The hits will come.",
    ],
    "breakout": [
        "Whatever we fixed is working. {player_name} looks like a different hitter.",
        "{player_name} made a small mechanical tweak and the results are showing.",
        "The work {player_name} has been putting in is paying off. His approach is night and day.",
    ],
    "prospect_development": [
        "I've been working with {prospect_name} on his two-strike approach. Real coachable kid.",
        "{prospect_name} has made huge strides with his swing mechanics. The power is starting to show.",
    ],
}

# Pitching coach specific messages
PITCHING_COACH_MESSAGES = {
    "bullpen_warning": [
        "The bullpen is running on fumes. We NEED a fresh arm or someone's going to get hurt.",
        "I've got {pitcher_name} on a limited pitch count tonight. He's been overworked.",
        "We need to skip {pitcher_name} in the rotation. His arm needs the extra rest.",
    ],
    "pitcher_development": [
        "{pitcher_name} has been working on a new changeup. It's coming along nicely.",
        "I'm seeing improvement in {pitcher_name}'s command. The walks are down.",
        "{pitcher_name}'s slider has gotten filthy. Best it's looked all season.",
    ],
    "concern": [
        "{pitcher_name}'s velocity was down 2 mph in his last start. Worth monitoring.",
        "I don't love {pitcher_name}'s arm action lately. Might want to get the training staff to take a look.",
    ],
}


import random

def get_coach_response(personality: str, situation: str, **kwargs) -> str:
    """Get a personality-appropriate coach response."""
    templates = COACH_RESPONSES.get(personality, COACH_RESPONSES["steady"])
    messages = templates.get(situation, templates.get("agree", ["Understood."]))
    msg = random.choice(messages)
    return msg.format(**kwargs) if kwargs else msg


def get_hitting_coach_message(situation: str, **kwargs) -> str:
    """Get a hitting coach specific message."""
    messages = HITTING_COACH_MESSAGES.get(situation, ["Working on it."])
    msg = random.choice(messages)
    return msg.format(**kwargs) if kwargs else msg


def get_pitching_coach_message(situation: str, **kwargs) -> str:
    """Get a pitching coach specific message."""
    messages = PITCHING_COACH_MESSAGES.get(situation, ["We're on it."])
    msg = random.choice(messages)
    return msg.format(**kwargs) if kwargs else msg


def send_coach_message(team_id: int, coach_name: str, role: str, body: str,
                       game_date: str = None, db_path: str = None) -> int:
    """Send a message from a coach to the GM through the chat system."""
    if game_date is None:
        state = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
        game_date = state[0]["current_date"] if state else "2026-03-01"

    role_label = {
        "manager": "Manager",
        "hitting_coach": "Hitting Coach",
        "pitching_coach": "Pitching Coach",
        "bench_coach": "Bench Coach",
    }.get(role, role.replace("_", " ").title())

    sender_name = f"{coach_name} ({role_label})"

    execute("""
        INSERT INTO messages (game_date, sender_type, sender_name, recipient_type,
                             recipient_id, subject, body, is_read, requires_response)
        VALUES (?, 'coach', ?, 'user', ?, ?, ?, 0, 0)
    """, (game_date, sender_name, team_id, f"Message from {role_label}", body), db_path=db_path)

    result = query("SELECT last_insert_rowid() as id", db_path=db_path)
    return result[0]["id"] if result else None


def generate_periodic_coach_messages(team_id: int, game_date: str, db_path: str = None):
    """
    Generate proactive coach messages based on team situation.
    Called during sim advance, ~1-2 messages per week.
    """
    # Only generate messages ~15% of the time (roughly 1 per week)
    if random.random() > 0.15:
        return

    # Get coaching staff
    staff = query("""
        SELECT * FROM coaching_staff WHERE team_id=? AND is_available=0
    """, (team_id,), db_path=db_path)

    if not staff:
        return

    # Get team situation
    standings = query("""
        SELECT wins, losses FROM standings_cache
        WHERE team_id=? ORDER BY id DESC LIMIT 1
    """, (team_id,), db_path=db_path)

    # Get recent results to determine streak
    recent_games = query("""
        SELECT home_score, away_score, home_team_id
        FROM schedule
        WHERE (home_team_id=? OR away_team_id=?) AND is_played=1
        ORDER BY game_date DESC LIMIT 5
    """, (team_id, team_id), db_path=db_path) or []

    wins = sum(1 for g in recent_games if
               (g["home_team_id"] == team_id and (g.get("home_score", 0) or 0) > (g.get("away_score", 0) or 0)) or
               (g["home_team_id"] != team_id and (g.get("away_score", 0) or 0) > (g.get("home_score", 0) or 0)))

    streak_type = "winning" if wins >= 4 else "losing" if wins <= 1 else "normal"

    for coach in staff:
        role = coach.get("role", "manager")
        personality = coach.get("personality", "steady")
        name = coach.get("name", "Coach")

        # Manager messages
        if role == "manager":
            if streak_type == "winning":
                msg = get_coach_response(personality, "winning_streak")
                send_coach_message(team_id, name, role, msg, game_date, db_path)
            elif streak_type == "losing":
                msg = get_coach_response(personality, "losing_streak")
                send_coach_message(team_id, name, role, msg, game_date, db_path)
            break  # Only one message per advance

        # Pitching coach messages
        elif role == "pitching_coach":
            if random.random() < 0.3:
                # Find an overworked pitcher
                pitchers = query("""
                    SELECT p.first_name, p.last_name, ps.games
                    FROM players p
                    JOIN pitching_stats ps ON ps.player_id = p.id
                    WHERE p.team_id=? AND p.position='RP' AND ps.games > 30
                    ORDER BY ps.games DESC LIMIT 1
                """, (team_id,), db_path=db_path)
                if pitchers:
                    pitcher = pitchers[0]
                    msg = get_pitching_coach_message("bullpen_warning",
                        pitcher_name=f"{pitcher['first_name']} {pitcher['last_name']}")
                    send_coach_message(team_id, name, role, msg, game_date, db_path)
                break

        # Hitting coach messages
        elif role == "hitting_coach":
            if random.random() < 0.3:
                # Find a slumping batter
                batters = query("""
                    SELECT p.first_name, p.last_name, bs.ab, bs.hits
                    FROM players p
                    JOIN batting_stats bs ON bs.player_id = p.id
                    WHERE p.team_id=? AND bs.ab > 50
                    AND CAST(bs.hits AS REAL) / bs.ab < 0.220
                    ORDER BY CAST(bs.hits AS REAL) / bs.ab ASC LIMIT 1
                """, (team_id,), db_path=db_path)
                if batters:
                    batter = batters[0]
                    msg = get_hitting_coach_message("slump_report",
                        player_name=f"{batter['first_name']} {batter['last_name']}")
                    send_coach_message(team_id, name, role, msg, game_date, db_path)
                break
