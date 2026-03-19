"""
Front Office - Weekly Podcast Script Generation
Generates entertaining podcast scripts that recap the week's action
in a conversational, sports-talk-radio style.
"""
import json
from datetime import date, timedelta
from ..database.db import query, execute, get_connection
from .claude_client import generate

# ============================================================
# PODCAST HOSTS
# ============================================================
HOSTS = [
    {
        "name": "Mike Tanner",
        "style": "play-by-play",
        "tendency": "enthusiastic",
        "catchphrase": "And THAT is what baseball is all about!",
    },
    {
        "name": "Lisa Chen",
        "style": "analyst",
        "tendency": "analytical",
        "catchphrase": "Let's look at the numbers here...",
    },
    {
        "name": "Big Earl Jackson",
        "style": "color",
        "tendency": "old_school",
        "catchphrase": "Back in MY day...",
    },
]

SHOW_NAME = "The Front Office Podcast"


# ============================================================
# DATA GATHERING
# ============================================================
def get_week_summary(game_date: str, season: int, db_path: str = None) -> dict:
    """Query the database for the past 7 days of baseball action."""
    end_date = date.fromisoformat(game_date)
    start_date = end_date - timedelta(days=7)
    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    # --- User's team ---
    state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
    user_team_id = state[0]["user_team_id"] if state else None

    user_team = None
    if user_team_id:
        teams = query("SELECT * FROM teams WHERE id=?", (user_team_id,), db_path=db_path)
        if teams:
            user_team = teams[0]

    # --- Recent game results (all teams) ---
    recent_games = query("""
        SELECT s.*,
               ht.city || ' ' || ht.name AS home_name, ht.abbreviation AS home_abbr,
               at.city || ' ' || at.name AS away_name, at.abbreviation AS away_abbr
        FROM schedule s
        JOIN teams ht ON s.home_team_id = ht.id
        JOIN teams at ON s.away_team_id = at.id
        WHERE s.season = ? AND s.is_played = 1
          AND s.game_date > ? AND s.game_date <= ?
        ORDER BY s.game_date DESC
        LIMIT 50
    """, (season, start_str, end_str), db_path=db_path) or []

    # --- User team results this week ---
    user_games = []
    if user_team_id:
        user_games = [g for g in recent_games
                      if g["home_team_id"] == user_team_id
                      or g["away_team_id"] == user_team_id]

    # --- Standings (current) ---
    standings_data = _get_condensed_standings(season, db_path)

    # --- Hot hitters (last 7 days via batting_lines) ---
    hot_hitters = query("""
        SELECT p.first_name, p.last_name, p.position, t.abbreviation AS team,
               COUNT(DISTINCT bl.schedule_id) AS games,
               SUM(bl.ab) AS ab, SUM(bl.hits) AS h, SUM(bl.hr) AS hr,
               SUM(bl.rbi) AS rbi, SUM(bl.bb) AS bb, SUM(bl.so) AS so
        FROM batting_lines bl
        JOIN schedule s ON bl.schedule_id = s.id
        JOIN players p ON bl.player_id = p.id
        JOIN teams t ON bl.team_id = t.id
        WHERE s.game_date > ? AND s.game_date <= ? AND s.season = ?
          AND bl.ab >= 10
        GROUP BY bl.player_id
        HAVING SUM(bl.ab) >= 15
        ORDER BY CAST(SUM(bl.hits) AS REAL) / MAX(SUM(bl.ab), 1) DESC
        LIMIT 5
    """, (start_str, end_str, season), db_path=db_path) or []

    # --- Cold hitters (struggling stars) ---
    cold_hitters = query("""
        SELECT p.first_name, p.last_name, p.position, t.abbreviation AS team,
               COUNT(DISTINCT bl.schedule_id) AS games,
               SUM(bl.ab) AS ab, SUM(bl.hits) AS h, SUM(bl.hr) AS hr,
               SUM(bl.rbi) AS rbi, SUM(bl.so) AS so
        FROM batting_lines bl
        JOIN schedule s ON bl.schedule_id = s.id
        JOIN players p ON bl.player_id = p.id
        JOIN teams t ON bl.team_id = t.id
        WHERE s.game_date > ? AND s.game_date <= ? AND s.season = ?
          AND bl.ab >= 10
        GROUP BY bl.player_id
        HAVING SUM(bl.ab) >= 15
        ORDER BY CAST(SUM(bl.hits) AS REAL) / MAX(SUM(bl.ab), 1) ASC
        LIMIT 5
    """, (start_str, end_str, season), db_path=db_path) or []

    # --- Hot pitchers ---
    hot_pitchers = query("""
        SELECT p.first_name, p.last_name, p.position, t.abbreviation AS team,
               COUNT(DISTINCT pl2.schedule_id) AS games,
               SUM(pl2.ip_outs) AS ip_outs, SUM(pl2.er) AS er,
               SUM(pl2.so) AS so, SUM(pl2.hits_allowed) AS ha,
               SUM(pl2.bb) AS bb
        FROM pitching_lines pl2
        JOIN schedule s ON pl2.schedule_id = s.id
        JOIN players p ON pl2.player_id = p.id
        JOIN teams t ON pl2.team_id = t.id
        WHERE s.game_date > ? AND s.game_date <= ? AND s.season = ?
          AND pl2.ip_outs >= 9
        GROUP BY pl2.player_id
        HAVING SUM(pl2.ip_outs) >= 12
        ORDER BY CAST(SUM(pl2.er) AS REAL) / MAX(SUM(pl2.ip_outs), 1) * 27.0 ASC
        LIMIT 5
    """, (start_str, end_str, season), db_path=db_path) or []

    # --- Trades this week ---
    trades = query("""
        SELECT * FROM transactions
        WHERE transaction_date > ? AND transaction_date <= ?
          AND transaction_type IN ('trade', 'free_agent_signing', 'release', 'dfa')
        ORDER BY transaction_date DESC
        LIMIT 10
    """, (start_str, end_str), db_path=db_path) or []

    # --- Injuries this week ---
    injuries = query("""
        SELECT p.first_name, p.last_name, p.position, p.injury_type,
               p.injury_days_remaining, p.il_tier, t.abbreviation AS team
        FROM players p
        JOIN teams t ON p.team_id = t.id
        WHERE p.is_injured = 1 AND p.roster_status = 'injured_dl'
        ORDER BY p.injury_days_remaining DESC
        LIMIT 10
    """, db_path=db_path) or []

    # --- Milestones (season stats thresholds) ---
    milestones = _check_milestones(season, db_path)

    # --- Recent call-ups ---
    callups = query("""
        SELECT * FROM transactions
        WHERE transaction_date > ? AND transaction_date <= ?
          AND transaction_type = 'call_up'
        ORDER BY transaction_date DESC
        LIMIT 5
    """, (start_str, end_str), db_path=db_path) or []

    return {
        "user_team": user_team,
        "user_games": user_games,
        "recent_games": recent_games,
        "standings": standings_data,
        "hot_hitters": hot_hitters,
        "cold_hitters": cold_hitters,
        "hot_pitchers": hot_pitchers,
        "trades": trades,
        "injuries": injuries,
        "milestones": milestones,
        "callups": callups,
        "start_date": start_str,
        "end_date": end_str,
    }


def _get_condensed_standings(season: int, db_path: str = None) -> list:
    """Get a condensed standings snapshot for all divisions."""
    teams = query("SELECT * FROM teams", db_path=db_path) or []
    results = []
    for t in teams:
        wins_row = query("""
            SELECT COUNT(*) as w FROM schedule
            WHERE season=? AND is_played=1 AND (
                (home_team_id=? AND home_score > away_score) OR
                (away_team_id=? AND away_score > home_score)
            )
        """, (season, t["id"], t["id"]), db_path=db_path)
        losses_row = query("""
            SELECT COUNT(*) as l FROM schedule
            WHERE season=? AND is_played=1 AND (
                (home_team_id=? AND home_score < away_score) OR
                (away_team_id=? AND away_score < home_score)
            )
        """, (season, t["id"], t["id"]), db_path=db_path)
        w = wins_row[0]["w"] if wins_row else 0
        l = losses_row[0]["l"] if losses_row else 0
        results.append({
            "team": f"{t['city']} {t['name']}",
            "abbr": t["abbreviation"],
            "division": f"{t['league']} {t['division']}",
            "wins": w,
            "losses": l,
        })
    # Sort by division, then wins desc
    results.sort(key=lambda x: (-x["wins"],))
    return results


def _check_milestones(season: int, db_path: str = None) -> list:
    """Check for notable season stat milestones."""
    milestones = []

    # HR milestones (30, 40, 50)
    hr_leaders = query("""
        SELECT p.first_name, p.last_name, t.abbreviation AS team, bs.hr
        FROM batting_stats bs
        JOIN players p ON bs.player_id = p.id
        JOIN teams t ON bs.team_id = t.id
        WHERE bs.season = ? AND bs.level = 'MLB' AND bs.hr >= 30
        ORDER BY bs.hr DESC LIMIT 10
    """, (season,), db_path=db_path) or []
    for h in hr_leaders:
        milestone = None
        if h["hr"] >= 50:
            milestone = "50 HR"
        elif h["hr"] >= 40:
            milestone = "40 HR"
        elif h["hr"] >= 30:
            milestone = "30 HR"
        if milestone:
            milestones.append(
                f"{h['first_name']} {h['last_name']} ({h['team']}) has reached {milestone} ({h['hr']})"
            )

    # 100 RBI milestone
    rbi_leaders = query("""
        SELECT p.first_name, p.last_name, t.abbreviation AS team, bs.rbi
        FROM batting_stats bs
        JOIN players p ON bs.player_id = p.id
        JOIN teams t ON bs.team_id = t.id
        WHERE bs.season = ? AND bs.level = 'MLB' AND bs.rbi >= 100
        ORDER BY bs.rbi DESC LIMIT 10
    """, (season,), db_path=db_path) or []
    for r in rbi_leaders:
        milestones.append(
            f"{r['first_name']} {r['last_name']} ({r['team']}) has {r['rbi']} RBI"
        )

    # 15+ wins for pitchers
    win_leaders = query("""
        SELECT p.first_name, p.last_name, t.abbreviation AS team, ps.wins
        FROM pitching_stats ps
        JOIN players p ON ps.player_id = p.id
        JOIN teams t ON ps.team_id = t.id
        WHERE ps.season = ? AND ps.level = 'MLB' AND ps.wins >= 15
        ORDER BY ps.wins DESC LIMIT 10
    """, (season,), db_path=db_path) or []
    for w in win_leaders:
        milestones.append(
            f"{w['first_name']} {w['last_name']} ({w['team']}) has {w['wins']} wins"
        )

    # 200+ strikeout pitchers
    so_leaders = query("""
        SELECT p.first_name, p.last_name, t.abbreviation AS team, ps.so
        FROM pitching_stats ps
        JOIN players p ON ps.player_id = p.id
        JOIN teams t ON ps.team_id = t.id
        WHERE ps.season = ? AND ps.level = 'MLB' AND ps.so >= 200
        ORDER BY ps.so DESC LIMIT 5
    """, (season,), db_path=db_path) or []
    for s in so_leaders:
        milestones.append(
            f"{s['first_name']} {s['last_name']} ({s['team']}) has {s['so']} strikeouts"
        )

    return milestones


# ============================================================
# SCRIPT GENERATION
# ============================================================
def _build_script_prompt(summary: dict, episode_number: int, week_number: int) -> str:
    """Build the LLM prompt for generating a podcast script."""

    # Format the data into readable summaries for the LLM
    sections = []

    # User team performance
    user_team = summary.get("user_team")
    if user_team and summary.get("user_games"):
        team_name = f"{user_team['city']} {user_team['name']}"
        user_wins = sum(
            1 for g in summary["user_games"]
            if (g["home_team_id"] == user_team["id"] and g["home_score"] > g["away_score"])
            or (g["away_team_id"] == user_team["id"] and g["away_score"] > g["home_score"])
        )
        user_losses = len(summary["user_games"]) - user_wins
        game_details = []
        for g in summary["user_games"][:5]:
            is_home = g["home_team_id"] == user_team["id"]
            opp = g["away_name"] if is_home else g["home_name"]
            my_score = g["home_score"] if is_home else g["away_score"]
            opp_score = g["away_score"] if is_home else g["home_score"]
            result = "W" if my_score > opp_score else "L"
            game_details.append(f"  {result} {'vs' if is_home else '@'} {opp} {my_score}-{opp_score}")
        sections.append(
            f"USER'S TEAM ({team_name}): Went {user_wins}-{user_losses} this week\n" +
            "\n".join(game_details)
        )

    # Hot hitters
    if summary.get("hot_hitters"):
        lines = ["HOT HITTERS THIS WEEK:"]
        for h in summary["hot_hitters"]:
            ab = h["ab"] or 1
            avg = h["h"] / ab if ab > 0 else 0
            lines.append(
                f"  {h['first_name']} {h['last_name']} ({h['team']}, {h['position']}): "
                f".{int(avg*1000):03d} ({h['h']}-for-{ab}), {h['hr']} HR, {h['rbi']} RBI"
            )
        sections.append("\n".join(lines))

    # Cold hitters
    if summary.get("cold_hitters"):
        lines = ["COLD HITTERS THIS WEEK:"]
        for h in summary["cold_hitters"]:
            ab = h["ab"] or 1
            avg = h["h"] / ab if ab > 0 else 0
            lines.append(
                f"  {h['first_name']} {h['last_name']} ({h['team']}, {h['position']}): "
                f".{int(avg*1000):03d} ({h['h']}-for-{ab}), {h.get('so', 0)} SO"
            )
        sections.append("\n".join(lines))

    # Hot pitchers
    if summary.get("hot_pitchers"):
        lines = ["HOT PITCHERS THIS WEEK:"]
        for p in summary["hot_pitchers"]:
            ip_outs = p["ip_outs"] or 1
            ip = ip_outs / 3
            era = (p["er"] / ip * 9) if ip > 0 else 0
            lines.append(
                f"  {p['first_name']} {p['last_name']} ({p['team']}, {p['position']}): "
                f"{era:.2f} ERA, {ip:.1f} IP, {p['so']} K"
            )
        sections.append("\n".join(lines))

    # Standings snapshot
    if summary.get("standings"):
        lines = ["STANDINGS LEADERS (by division):"]
        divs = {}
        for t in summary["standings"]:
            div = t["division"]
            if div not in divs:
                divs[div] = []
            divs[div].append(t)
        for div in sorted(divs.keys()):
            div_teams = sorted(divs[div], key=lambda x: -x["wins"])[:3]
            top = div_teams[0]
            lines.append(f"  {div}: {top['abbr']} ({top['wins']}-{top['losses']})")
        sections.append("\n".join(lines))

    # Trades
    if summary.get("trades"):
        lines = ["TRANSACTIONS THIS WEEK:"]
        for t in summary["trades"][:5]:
            try:
                details = json.loads(t.get("details_json", "{}"))
                desc = details.get("description", t["transaction_type"])
            except (json.JSONDecodeError, TypeError):
                desc = t["transaction_type"]
            lines.append(f"  [{t['transaction_date']}] {desc}")
        sections.append("\n".join(lines))

    # Injuries
    if summary.get("injuries"):
        lines = ["NOTABLE INJURIES:"]
        for inj in summary["injuries"][:5]:
            lines.append(
                f"  {inj['first_name']} {inj['last_name']} ({inj['team']}, {inj['position']}): "
                f"{inj['injury_type']} - {inj['injury_days_remaining']} days remaining ({inj['il_tier'] or 'IL'})"
            )
        sections.append("\n".join(lines))

    # Milestones
    if summary.get("milestones"):
        lines = ["SEASON MILESTONES:"]
        for m in summary["milestones"][:5]:
            lines.append(f"  {m}")
        sections.append("\n".join(lines))

    # Call-ups
    if summary.get("callups"):
        lines = ["RECENT CALL-UPS:"]
        for c in summary["callups"]:
            try:
                details = json.loads(c.get("details_json", "{}"))
                desc = details.get("description", "Call-up")
            except (json.JSONDecodeError, TypeError):
                desc = "Call-up"
            lines.append(f"  [{c['transaction_date']}] {desc}")
        sections.append("\n".join(lines))

    data_block = "\n\n".join(sections) if sections else "Not much action this week - slow news day."

    prompt = f"""You are a script writer for "{SHOW_NAME}", a fictional weekly baseball podcast.

Write a podcast transcript for Episode {episode_number}, Week {week_number} recap.

HOSTS:
- Mike Tanner (play-by-play host, enthusiastic, catchphrase: "And THAT is what baseball is all about!")
- Lisa Chen (analyst, analytical, loves stats, catchphrase: "Let's look at the numbers here...")
- Big Earl Jackson (color commentator, old school, nostalgic, catchphrase: "Back in MY day...")

WEEK'S DATA:
{data_block}

INSTRUCTIONS:
- Write a natural-sounding podcast transcript with 8-15 exchanges between hosts
- Start with Mike's intro welcoming listeners
- Cover 3-4 of the most interesting topics from the data
- Have Lisa cite specific stats from the data
- Have Big Earl drop in with old-school takes and his catchphrase at least once
- Include friendly banter and disagreements between hosts
- End with Mike's sign-off using his catchphrase
- Use the format: "MIKE: ...", "LISA: ...", "EARL: ..."
- Keep it entertaining and conversational, like real sports talk radio
- Make host reactions feel genuine - excited about hot streaks, concerned about slumps
- Generate a catchy episode subtitle/title (5-8 words)
- Do NOT use markdown formatting. Just plain text with host name prefixes.

Output format:
TITLE: [Your catchy episode title]

[transcript here]"""

    return prompt


def _generate_fallback_script(summary: dict, episode_number: int, week_number: int) -> tuple:
    """Generate a script without the LLM, using templates."""
    title = f"Week {week_number} in Review"

    lines = []
    lines.append(
        f"MIKE: Welcome back to {SHOW_NAME}! I'm Mike Tanner, joined as always by the brilliant "
        f"Lisa Chen and the legendary Big Earl Jackson. What a week in baseball, folks!"
    )

    # Talk about hot hitters
    if summary.get("hot_hitters"):
        h = summary["hot_hitters"][0]
        ab = h["ab"] or 1
        avg = h["h"] / ab if ab > 0 else 0
        lines.append(
            f"LISA: Let's look at the numbers here... {h['first_name']} {h['last_name']} of the "
            f"{h['team']} has been absolutely ON FIRE this week. We're talking a "
            f".{int(avg*1000):03d} batting average with {h['hr']} home runs and {h['rbi']} RBI. "
            f"That's elite production, Mike."
        )
        lines.append(
            f"MIKE: You can't pitch around this guy right now. Every at-bat feels like something's "
            f"going to happen!"
        )
        lines.append(
            f"EARL: Back in MY day, we didn't need all these fancy stats to know a guy was raking. "
            f"You just watched him at the plate and you KNEW. And let me tell you, {h['last_name']} "
            f"has got that LOOK right now."
        )

    # User's team
    user_team = summary.get("user_team")
    if user_team and summary.get("user_games"):
        team_name = f"{user_team['city']} {user_team['name']}"
        user_wins = sum(
            1 for g in summary["user_games"]
            if (g["home_team_id"] == user_team["id"] and g["home_score"] > g["away_score"])
            or (g["away_team_id"] == user_team["id"] and g["away_score"] > g["home_score"])
        )
        user_losses = len(summary["user_games"]) - user_wins
        if user_wins > user_losses:
            lines.append(
                f"MIKE: And how about the {team_name}? Going {user_wins}-{user_losses} this week! "
                f"Things are looking up for our squad!"
            )
            lines.append(
                f"LISA: The underlying numbers support it too. This isn't just luck, Mike."
            )
        elif user_wins < user_losses:
            lines.append(
                f"MIKE: Now, we have to talk about the {team_name}. {user_wins}-{user_losses} "
                f"this week. Not what you want to see."
            )
            lines.append(
                f"LISA: Let's look at the numbers here... there are some concerning trends, "
                f"but I think there's reason for optimism going forward."
            )
        else:
            lines.append(
                f"MIKE: The {team_name} went {user_wins}-{user_losses} this week. Treading water."
            )

    # Cold hitters
    if summary.get("cold_hitters"):
        c = summary["cold_hitters"][0]
        ab = c["ab"] or 1
        avg = c["h"] / ab if ab > 0 else 0
        lines.append(
            f"LISA: On the flip side, {c['first_name']} {c['last_name']} of the {c['team']} "
            f"is really struggling right now. Just .{int(avg*1000):03d} this week with "
            f"{c.get('so', 0)} strikeouts."
        )
        lines.append(
            f"EARL: Every hitter goes through slumps. The great ones find their way out. "
            f"I've seen this before - he'll be fine."
        )

    # Injuries
    if summary.get("injuries"):
        inj = summary["injuries"][0]
        lines.append(
            f"MIKE: We do have some injury news to report. {inj['first_name']} {inj['last_name']} "
            f"of the {inj['team']} is dealing with {inj['injury_type']}. That's a big loss."
        )

    # Milestones
    if summary.get("milestones"):
        lines.append(
            f"MIKE: Before we go, some milestone watch: {summary['milestones'][0]}. Incredible stuff."
        )

    # Trades
    if summary.get("trades"):
        lines.append(
            f"LISA: And we had some front office activity this week. The transaction wire was "
            f"buzzing with {len(summary['trades'])} moves. GMs are clearly positioning for the stretch."
        )

    # Sign-off
    lines.append(
        f"MIKE: That's all the time we have this week, folks! Lisa, Earl, thanks as always for "
        f"the great insights. And THAT is what baseball is all about! See you next week on "
        f"{SHOW_NAME}!"
    )
    lines.append(f"LISA: Thanks Mike! Stay safe out there.")
    lines.append(f"EARL: Keep swinging, everybody.")

    script = "\n\n".join(lines)
    return title, script


# ============================================================
# MAIN GENERATION
# ============================================================
async def generate_weekly_podcast(game_date: str, season: int, db_path: str = None) -> dict:
    """Generate a weekly podcast episode covering the past 7 days of action."""

    # Get the next episode number
    last_ep = query(
        "SELECT MAX(episode_number) as max_ep FROM podcast_episodes WHERE season = ?",
        (season,), db_path=db_path
    )
    episode_number = (last_ep[0]["max_ep"] or 0) + 1 if last_ep else 1

    # Calculate week number from opening day (approx April 1)
    current = date.fromisoformat(game_date)
    opening_day = date(season, 4, 1)
    week_number = max(1, ((current - opening_day).days // 7) + 1)

    # Gather week summary data
    summary = get_week_summary(game_date, season, db_path)

    # Build prompt and try LLM generation
    prompt = _build_script_prompt(summary, episode_number, week_number)

    try:
        raw_script = await generate(
            prompt,
            task_type="creative",
            system_prompt=(
                "You are a sports podcast script writer. Write entertaining, natural-sounding "
                "podcast transcripts. Keep it conversational and fun. Output ONLY the script "
                "with no markdown formatting."
            ),
            temperature=0.85,
            max_tokens=2048,
        )

        # Extract title from LLM output
        title = f"Week {week_number} Recap"
        if raw_script and "TITLE:" in raw_script:
            title_line = raw_script.split("TITLE:")[1].split("\n")[0].strip()
            if title_line:
                title = title_line
            # Remove the TITLE line from the script body
            script_body = raw_script.split("\n", 2)
            # Find the first host line
            script_start = raw_script.find("MIKE:")
            if script_start == -1:
                script_start = raw_script.find("LISA:")
            if script_start == -1:
                script_start = raw_script.find("EARL:")
            if script_start >= 0:
                script = raw_script[script_start:].strip()
            else:
                script = raw_script.strip()
        elif raw_script and not raw_script.startswith("[LLM"):
            script = raw_script.strip()
        else:
            # Fallback to template-based generation
            title, script = _generate_fallback_script(summary, episode_number, week_number)
            script = "[AI Offline — template script] " + script

    except Exception:
        # Fallback to template-based generation
        title, script = _generate_fallback_script(summary, episode_number, week_number)
        script = "[AI Offline — template script] " + script

    # Determine topics covered
    topics = []
    if summary.get("hot_hitters"):
        topics.append("hot_hitters")
    if summary.get("cold_hitters"):
        topics.append("cold_hitters")
    if summary.get("hot_pitchers"):
        topics.append("pitching")
    if summary.get("trades"):
        topics.append("trades")
    if summary.get("injuries"):
        topics.append("injuries")
    if summary.get("milestones"):
        topics.append("milestones")
    if summary.get("user_games"):
        topics.append("user_team")
    if summary.get("callups"):
        topics.append("prospect_watch")

    # Build the formatted header
    hosts_list = [h["name"] for h in HOSTS]
    full_script = (
        f"THE FRONT OFFICE PODCAST - Episode {episode_number}\n"
        f'"{title}"\n'
        f"Hosts: {hosts_list[0]} & {hosts_list[1]} (with special guest {hosts_list[2]})\n"
        f"\n---\n\n"
        f"{script}"
    )

    # Estimate duration (roughly 1 minute per 150 words)
    word_count = len(full_script.split())
    duration_estimate = max(3, min(15, word_count // 150))

    # Store in database
    execute("""
        INSERT INTO podcast_episodes
        (episode_number, game_date, title, hosts, script, duration_estimate, season, topics)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        episode_number,
        game_date,
        title,
        json.dumps(hosts_list),
        full_script,
        duration_estimate,
        season,
        json.dumps(topics),
    ), db_path=db_path)

    return {
        "episode_number": episode_number,
        "title": title,
        "duration_estimate": duration_estimate,
        "topics": topics,
    }


def generate_weekly_podcast_sync(game_date: str, season: int, db_path: str = None) -> dict:
    """Synchronous wrapper for generate_weekly_podcast."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context, use a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(
                    asyncio.run,
                    generate_weekly_podcast(game_date, season, db_path)
                ).result(timeout=60)
            return result
        else:
            return loop.run_until_complete(
                generate_weekly_podcast(game_date, season, db_path)
            )
    except RuntimeError:
        return asyncio.run(generate_weekly_podcast(game_date, season, db_path))


# ============================================================
# RETRIEVAL
# ============================================================
def get_podcast_episodes(season: int = None, limit: int = 10, db_path: str = None) -> list:
    """Fetch recent podcast episodes."""
    if season:
        episodes = query("""
            SELECT * FROM podcast_episodes
            WHERE season = ?
            ORDER BY episode_number DESC
            LIMIT ?
        """, (season, limit), db_path=db_path)
    else:
        episodes = query("""
            SELECT * FROM podcast_episodes
            ORDER BY id DESC
            LIMIT ?
        """, (limit,), db_path=db_path)
    return episodes or []


def get_latest_podcast(db_path: str = None) -> dict:
    """Get the most recent podcast episode."""
    result = query("""
        SELECT * FROM podcast_episodes
        ORDER BY id DESC
        LIMIT 1
    """, db_path=db_path)
    return result[0] if result else None


def should_generate_podcast(game_date: str, season: int, db_path: str = None) -> bool:
    """Check if 7 days have passed since the last podcast episode."""
    last = query("""
        SELECT game_date FROM podcast_episodes
        WHERE season = ?
        ORDER BY id DESC
        LIMIT 1
    """, (season,), db_path=db_path)

    if not last:
        # No episodes yet this season - generate if we're in regular season
        return True

    last_date = date.fromisoformat(last[0]["game_date"])
    current = date.fromisoformat(game_date)
    return (current - last_date).days >= 7
