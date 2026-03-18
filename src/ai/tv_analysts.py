"""
Front Office - TV Analyst Characters (Phase 3)
Fired GMs and retired players become TV analysts who comment on league happenings.
Generates daily segments: hot takes, trade grades, power rankings, player spotlights,
weekly recaps, and analyst debates.
"""
import random
from datetime import datetime
from ..database.db import query, execute, get_connection

# ============================================================
# INITIAL ANALYST ROSTER
# ============================================================
INITIAL_ANALYSTS = [
    # ESPN analysts
    {
        "name": "Tony Castillo",
        "network": "ESPN",
        "show_name": "Baseball Tonight",
        "analyst_type": "hot_take_artist",
        "origin": "Emmy-winning broadcaster, 20 years on air",
        "personality": "provocateur",
        "credibility": 55,
        "hot_take_tendency": 0.85,
        "catchphrase": "THIS IS WHY WE WATCH BASEBALL!",
    },
    {
        "name": "Sandra Mitchell",
        "network": "ESPN",
        "show_name": "Baseball Tonight",
        "analyst_type": "stat_guru",
        "origin": "Former sabermetrics analyst for three MLB front offices",
        "personality": "stat_nerd",
        "credibility": 78,
        "hot_take_tendency": 0.15,
        "catchphrase": "The WAR numbers don't lie, folks.",
    },
    {
        "name": "Marcus Webb",
        "network": "ESPN",
        "show_name": "SportsCenter",
        "analyst_type": "former_player",
        "origin": "15-year MLB veteran, 3x All-Star outfielder",
        "personality": "balanced",
        "credibility": 72,
        "hot_take_tendency": 0.35,
        "catchphrase": "I've been in that clubhouse. I know what it's like.",
    },
    # MLB Network analysts
    {
        "name": "Ray Dominguez",
        "network": "MLB Network",
        "show_name": "MLB Now",
        "analyst_type": "insider",
        "origin": "Award-winning baseball journalist, 25 years covering the game",
        "personality": "balanced",
        "credibility": 85,
        "hot_take_tendency": 0.2,
        "catchphrase": "Sources close to the situation are telling me...",
    },
    {
        "name": "Diane Kowalski",
        "network": "MLB Network",
        "show_name": "Hot Stove",
        "analyst_type": "former_gm",
        "origin": "Former front office executive, built two playoff teams",
        "personality": "balanced",
        "credibility": 80,
        "hot_take_tendency": 0.25,
        "catchphrase": "From the GM's chair, you see this differently.",
    },
    {
        "name": "Terrence Alford",
        "network": "MLB Network",
        "show_name": "MLB Tonight",
        "analyst_type": "commentator",
        "origin": "Hall of Fame voter, author of three baseball books",
        "personality": "balanced",
        "credibility": 70,
        "hot_take_tendency": 0.3,
        "catchphrase": "That's a baseball play right there.",
    },
    # Fox Sports analysts
    {
        "name": "Buck Holloway",
        "network": "Fox Sports",
        "show_name": "Fox Baseball Pregame",
        "analyst_type": "former_player",
        "origin": "Former Gold Glove catcher, 12-year career",
        "personality": "old_school",
        "credibility": 60,
        "hot_take_tendency": 0.5,
        "catchphrase": "Back in my day, we played the game the right way.",
    },
    {
        "name": "Jake Brennan",
        "network": "Fox Sports",
        "show_name": "Fox Baseball Pregame",
        "analyst_type": "commentator",
        "origin": "Former college baseball coach turned broadcaster",
        "personality": "provocateur",
        "credibility": 50,
        "hot_take_tendency": 0.75,
        "catchphrase": "I don't care what the numbers say, watch the game!",
    },
    # TBS
    {
        "name": "Yolanda Chen",
        "network": "TBS",
        "show_name": "MLB on TBS Pregame",
        "analyst_type": "commentator",
        "origin": "Pulitzer-nominated sportswriter turned broadcaster",
        "personality": "balanced",
        "credibility": 75,
        "hot_take_tendency": 0.2,
        "catchphrase": "Let's look at the bigger picture here.",
    },
]


def generate_initial_analysts(db_path=None):
    """Create 8-10 TV analysts across networks if none exist yet."""
    existing = query("SELECT COUNT(*) as cnt FROM tv_analysts", db_path=db_path)
    if existing and existing[0]["cnt"] > 0:
        return {"created": 0, "message": "Analysts already exist"}

    conn = get_connection(db_path)
    created = 0
    for a in INITIAL_ANALYSTS:
        conn.execute("""
            INSERT INTO tv_analysts (name, network, show_name, analyst_type,
                origin, personality, credibility, hot_take_tendency, catchphrase)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            a["name"], a["network"], a["show_name"], a["analyst_type"],
            a["origin"], a["personality"], a["credibility"],
            a["hot_take_tendency"], a["catchphrase"],
        ))
        created += 1
    conn.commit()
    conn.close()
    return {"created": created, "analysts": [a["name"] for a in INITIAL_ANALYSTS]}


def create_analyst_from_fired_gm(gm_name, team_name, db_path=None):
    """When a GM gets fired, they become a TV analyst with a grudge."""
    networks = ["ESPN", "MLB Network", "Fox Sports", "TBS"]
    shows = {
        "ESPN": "Baseball Tonight",
        "MLB Network": "Hot Stove",
        "Fox Sports": "Fox Baseball Pregame",
        "TBS": "MLB on TBS Pregame",
    }
    network = random.choice(networks)

    # Personality mapping: fired GMs tend toward contrarian or provocateur
    personality = random.choice(["contrarian", "balanced", "provocateur"])

    # Find the team ID for potential bias
    teams = query("SELECT id FROM teams WHERE name=? OR city || ' ' || name = ?",
                  (team_name, team_name), db_path=db_path)
    team_id = teams[0]["id"] if teams else None

    catchphrases = [
        f"I built that {team_name} roster, and they're squandering it.",
        f"Trust me, I know how that {team_name} front office operates.",
        "Having sat in that chair, I can tell you this is a mistake.",
        "When I was running things, we did it differently.",
        f"The {team_name} let me go, and look where they are now.",
    ]

    analyst_id = execute("""
        INSERT INTO tv_analysts (name, network, show_name, analyst_type,
            origin, personality, credibility, hot_take_tendency,
            favorite_team_id, catchphrase)
        VALUES (?, ?, ?, 'former_gm', ?, ?, ?, ?, ?, ?)
    """, (
        gm_name,
        network,
        shows.get(network, "Studio Show"),
        f"Former GM of the {team_name}",
        personality,
        75,  # High credibility from inside knowledge
        0.45,  # Moderate hot take tendency
        team_id,  # They still watch their old team closely
        random.choice(catchphrases),
    ), db_path=db_path)

    return {
        "analyst_id": analyst_id,
        "name": gm_name,
        "network": network,
        "origin": f"Former GM of the {team_name}",
    }


# ============================================================
# SEGMENT GENERATION
# ============================================================

def _get_standings_snapshot(db_path=None):
    """Get current W-L records for all teams."""
    rows = query("""
        SELECT t.id, t.city, t.name, t.abbreviation, t.league, t.division,
            COALESCE(w.wins, 0) as wins, COALESCE(w.losses, 0) as losses
        FROM teams t
        LEFT JOIN (
            SELECT team_id,
                SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN is_win = 0 THEN 1 ELSE 0 END) as losses
            FROM (
                SELECT home_team_id as team_id,
                    CASE WHEN home_score > away_score THEN 1 ELSE 0 END as is_win
                FROM schedule WHERE is_played = 1 AND is_postseason = 0
                UNION ALL
                SELECT away_team_id as team_id,
                    CASE WHEN away_score > home_score THEN 1 ELSE 0 END as is_win
                FROM schedule WHERE is_played = 1 AND is_postseason = 0
            )
            GROUP BY team_id
        ) w ON w.team_id = t.id
        ORDER BY wins DESC
    """, db_path=db_path)
    return rows


def _get_recent_trades(game_date, lookback_days=3, db_path=None):
    """Get trades from the last N days."""
    return query("""
        SELECT t.*, t1.city || ' ' || t1.name as team1_name,
               t2.city || ' ' || t2.name as team2_name,
               t1.abbreviation as team1_abbr, t2.abbreviation as team2_abbr
        FROM transactions t
        LEFT JOIN teams t1 ON t1.id = t.team1_id
        LEFT JOIN teams t2 ON t2.id = t.team2_id
        WHERE t.transaction_type = 'trade'
        AND t.transaction_date >= date(?, '-' || ? || ' days')
        AND t.transaction_date <= ?
        ORDER BY t.transaction_date DESC
        LIMIT 5
    """, (game_date, lookback_days, game_date), db_path=db_path)


def _get_hot_hitters(game_date, db_path=None):
    """Find players with notable recent performance."""
    state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
    season = state[0]["season"] if state else 2026
    return query("""
        SELECT p.id, p.first_name, p.last_name, p.position,
               t.city, t.name as team_name, t.abbreviation,
               bs.hits, bs.hr, bs.rbi, bs.ab, bs.games,
               CASE WHEN bs.ab > 0 THEN ROUND(CAST(bs.hits AS REAL) / bs.ab, 3) ELSE 0 END as avg
        FROM batting_stats bs
        JOIN players p ON p.id = bs.player_id
        JOIN teams t ON t.id = bs.team_id
        WHERE bs.season = ? AND bs.level = 'MLB'
        AND bs.ab >= 50
        ORDER BY CASE WHEN bs.ab > 0 THEN CAST(bs.hits AS REAL) / bs.ab ELSE 0 END DESC
        LIMIT 15
    """, (season,), db_path=db_path)


def _get_hot_pitchers(game_date, db_path=None):
    """Find pitchers with notable recent performance."""
    state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
    season = state[0]["season"] if state else 2026
    return query("""
        SELECT p.id, p.first_name, p.last_name, p.position,
               t.city, t.name as team_name, t.abbreviation,
               ps.wins, ps.losses, ps.saves, ps.ip_outs, ps.er, ps.so,
               CASE WHEN ps.ip_outs > 0 THEN ROUND(CAST(ps.er AS REAL) * 27 / ps.ip_outs, 2) ELSE 0 END as era
        FROM pitching_stats ps
        JOIN players p ON p.id = ps.player_id
        JOIN teams t ON t.id = ps.team_id
        WHERE ps.season = ? AND ps.level = 'MLB'
        AND ps.ip_outs >= 30
        ORDER BY era ASC
        LIMIT 10
    """, (season,), db_path=db_path)


def _get_struggling_teams(standings):
    """Find teams with notably bad records."""
    return [t for t in standings if t["wins"] + t["losses"] > 10
            and t["losses"] > t["wins"] * 1.5]


def _get_analysts(db_path=None):
    """Get all active analysts."""
    return query("SELECT * FROM tv_analysts WHERE is_active = 1", db_path=db_path)


def _generate_hot_take(analyst, standings, hot_hitters, hot_pitchers, game_date, db_path=None):
    """Generate a hot take from a provocateur or hot_take_artist."""
    takes = []

    # Struggling team takes
    struggling = _get_struggling_teams(standings)
    if struggling:
        team = random.choice(struggling)
        takes.append({
            "headline": f"{team['city']} {team['name']} Need to Blow It Up",
            "content": (
                f'"{team["city"]} needs to blow it up. This isn\'t working. '
                f'At {team["wins"]}-{team["losses"]}, you\'re wasting everyone\'s time. '
                f'{analyst["catchphrase"]}" — {analyst["name"]}, {analyst["network"]}'
            ),
        })
        takes.append({
            "headline": f"Are the {team['name']} the Worst Team in Baseball?",
            "content": (
                f'"The {team["city"]} {team["name"]} are frauds. I said it in spring training '
                f'and I\'m saying it now. {team["wins"]}-{team["losses"]} is unacceptable for that payroll. '
                f'{analyst["catchphrase"]}" — {analyst["name"]}, {analyst["network"]}'
            ),
        })

    # Hot hitter takes (contrarian angle)
    if hot_hitters:
        hitter = random.choice(hot_hitters[:5])
        avg_str = f".{int(hitter['avg'] * 1000):03d}" if hitter["avg"] < 1 else f"{hitter['avg']:.3f}"
        takes.append({
            "headline": f"Nobody's Talking About {hitter['first_name']} {hitter['last_name']}",
            "content": (
                f'"Nobody\'s talking about {hitter["first_name"]} {hitter["last_name"]} '
                f'and it\'s a CRIME. {avg_str} with {hitter["hr"]} homers and {hitter["rbi"]} RBI. '
                f'He\'s having an MVP-caliber season and we\'re all sleeping on it. '
                f'{analyst["catchphrase"]}" — {analyst["name"]}, {analyst["network"]}'
            ),
        })
        # "Washed" take on a player lower in the list
        if len(hot_hitters) > 8:
            cold_hitter = random.choice(hot_hitters[8:])
            takes.append({
                "headline": f"Is {cold_hitter['first_name']} {cold_hitter['last_name']} Already Washed?",
                "content": (
                    f'"Is {cold_hitter["first_name"]} {cold_hitter["last_name"]} already washed? '
                    f'The numbers say YES. Hitting {cold_hitter["avg"]:.3f} is not going to cut it. '
                    f'{analyst["catchphrase"]}" — {analyst["name"]}, {analyst["network"]}'
                ),
            })

    # Bounce-back takes
    if hot_hitters and len(hot_hitters) > 5:
        comeback = random.choice(hot_hitters[3:8])
        takes.append({
            "headline": f"Hot Take: {comeback['first_name']} {comeback['last_name']} Will Be an All-Star",
            "content": (
                f'"Hot take: {comeback["first_name"]} {comeback["last_name"]} bounces back to be '
                f'an All-Star. I\'m calling it now. The talent is there, the numbers are coming around. '
                f'{analyst["catchphrase"]}" — {analyst["name"]}, {analyst["network"]}'
            ),
        })

    # Top team takes
    if standings:
        best = standings[0]
        takes.append({
            "headline": f"Can Anyone Stop the {best['city']} {best['name']}?",
            "content": (
                f'"The {best["city"]} {best["name"]} at {best["wins"]}-{best["losses"]}... '
                f'I\'m not sure anyone in the league can stop this team right now. '
                f'{analyst["catchphrase"]}" — {analyst["name"]}, {analyst["network"]}'
            ),
        })

    if not takes:
        takes.append({
            "headline": "This Season Has Been Incredible",
            "content": (
                f'"THIS IS WHY WE WATCH BASEBALL! Every night there\'s a story. '
                f'Every night there\'s drama. This season is delivering. '
                f'{analyst["catchphrase"]}" — {analyst["name"]}, {analyst["network"]}'
            ),
        })

    return random.choice(takes)


def _generate_trade_grade(analyst, trade, db_path=None):
    """Generate a trade grade segment."""
    import json
    try:
        details = json.loads(trade.get("details_json", "{}"))
    except (json.JSONDecodeError, TypeError):
        details = {}

    team1_name = trade.get("team1_name", "Team A")
    team2_name = trade.get("team2_name", "Team B")

    # Get player names from details
    team1_gets = details.get("team1_gets", details.get("receiving_players", []))
    team2_gets = details.get("team2_gets", details.get("sending_players", []))

    # Format player lists
    if isinstance(team1_gets, list):
        t1_players = ", ".join(str(p) if isinstance(p, str) else p.get("name", "Unknown") for p in team1_gets) or "players"
    else:
        t1_players = str(team1_gets) or "players"

    if isinstance(team2_gets, list):
        t2_players = ", ".join(str(p) if isinstance(p, str) else p.get("name", "Unknown") for p in team2_gets) or "players"
    else:
        t2_players = str(team2_gets) or "players"

    # Generate grades based on analyst personality
    grades = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F"]
    if analyst["personality"] == "stat_nerd":
        # Stat nerds give more moderate grades
        t1_grade = random.choice(grades[2:7])
        t2_grade = random.choice(grades[3:8])
    elif analyst["personality"] in ("provocateur", "contrarian"):
        # Provocateurs give extreme grades
        t1_grade = random.choice(grades[0:3])
        t2_grade = random.choice(grades[7:])
    else:
        t1_grade = random.choice(grades[1:6])
        t2_grade = random.choice(grades[2:7])

    # Bias: if analyst has favorite team, grade them higher
    if analyst.get("favorite_team_id"):
        if str(analyst["favorite_team_id"]) == str(trade.get("team1_id")):
            t1_grade = random.choice(grades[0:3])
        elif str(analyst["favorite_team_id"]) == str(trade.get("team2_id")):
            t2_grade = random.choice(grades[0:3])

    winner = team1_name if grades.index(t1_grade) < grades.index(t2_grade) else team2_name
    loser = team2_name if winner == team1_name else team1_name

    content = (
        f"{analyst['name']}'s Trade Grade:\n"
        f"{team1_name} gets: {t1_players} \u2014 Grade: {t1_grade}\n"
        f"{team2_name} gets: {t2_players} \u2014 Grade: {t2_grade}\n\n"
        f'"I love this deal for {winner}. '
    )

    if analyst["personality"] == "stat_nerd":
        content += f'The WAR projection heavily favors them going forward. '
    elif analyst["personality"] == "old_school":
        content += f'They got a gamer, a guy who plays the game the right way. '
    else:
        content += f'They addressed a clear need and didn\'t overpay. '

    content += (
        f'{loser}? I don\'t understand what they\'re doing here. '
        f'{analyst["catchphrase"]}" \u2014 {analyst["name"]}, {analyst["network"]}'
    )

    return {
        "headline": f"Trade Grade: {trade.get('team1_abbr', 'TM1')}-{trade.get('team2_abbr', 'TM2')} Deal",
        "content": content,
    }


def _generate_power_rankings(analyst, standings, game_date, db_path=None):
    """Generate weekly power rankings from a stat-oriented analyst."""
    if not standings:
        return None

    # Sort by win pct
    ranked = sorted(standings, key=lambda t: t["wins"] / max(t["wins"] + t["losses"], 1), reverse=True)
    top5 = ranked[:5]

    lines = [f"{analyst['name']}'s Power Rankings ({game_date}):\n"]
    blurbs = [
        "they just keep winning and show no signs of slowing down",
        "the pitching staff has been dominant all season",
        "their lineup is the deepest in baseball right now",
        "a perfect blend of youth and veteran leadership",
        "quietly putting together a special season",
        "the bullpen is lights-out and the rotation is dealing",
        "they have the best run differential in the league",
        "offense firing on all cylinders",
    ]
    random.shuffle(blurbs)

    for i, team in enumerate(top5):
        record = f"{team['wins']}-{team['losses']}"
        blurb = blurbs[i % len(blurbs)]
        lines.append(f"{i+1}. {team['city']} {team['name']} ({record}) \u2014 {blurb}")

    if analyst["personality"] == "stat_nerd":
        lines.append(f'\n"The WAR totals back this up. {analyst["catchphrase"]}" \u2014 {analyst["name"]}, {analyst["network"]}')
    else:
        lines.append(f'\n"{analyst["catchphrase"]}" \u2014 {analyst["name"]}, {analyst["network"]}')

    return {
        "headline": f"Power Rankings: {top5[0]['city']} {top5[0]['name']} Hold the Top Spot",
        "content": "\n".join(lines),
    }


def _generate_player_spotlight(analyst, hot_hitters, hot_pitchers, db_path=None):
    """Generate a player spotlight for a breakout performance."""
    candidates = []
    if hot_hitters:
        for h in hot_hitters[:5]:
            avg_str = f".{int(h['avg'] * 1000):03d}" if h["avg"] < 1 else f"{h['avg']:.3f}"
            candidates.append({
                "name": f"{h['first_name']} {h['last_name']}",
                "team": f"{h['city']} {h['team_name']}",
                "abbr": h["abbreviation"],
                "stat_line": f"{avg_str}/{h['hr']} HR/{h['rbi']} RBI in {h['games']} games",
                "type": "hitter",
            })
    if hot_pitchers:
        for p in hot_pitchers[:3]:
            ip = p["ip_outs"] // 3
            candidates.append({
                "name": f"{p['first_name']} {p['last_name']}",
                "team": f"{p['city']} {p['team_name']}",
                "abbr": p["abbreviation"],
                "stat_line": f"{p['era']:.2f} ERA, {p['wins']}-{p['losses']}, {p['so']} K in {ip} IP",
                "type": "pitcher",
            })

    if not candidates:
        return None

    player = random.choice(candidates)
    if analyst["personality"] == "stat_nerd":
        commentary = (
            f"The advanced metrics are screaming Cy Young/MVP candidate. "
            f"{analyst['catchphrase']}"
        )
    elif analyst["personality"] == "old_school":
        commentary = (
            f"This is a ballplayer. Plays the game hard every single night. "
            f"{analyst['catchphrase']}"
        )
    else:
        commentary = (
            f"This is the kind of performance that changes a franchise. "
            f"{analyst['catchphrase']}"
        )

    return {
        "headline": f"Spotlight: {player['name']} ({player['abbr']}) Is On Fire",
        "content": (
            f"\"Nobody's talking about {player['name']} and it's a CRIME. "
            f"Look at these numbers: {player['stat_line']}. "
            f"{commentary}\" \u2014 {analyst['name']}, {analyst['network']}"
        ),
    }


def _generate_weekly_recap(analyst, standings, game_date, db_path=None):
    """Generate a weekly recap segment."""
    if not standings:
        return None

    sorted_teams = sorted(standings, key=lambda t: t["wins"], reverse=True)
    best = sorted_teams[0] if sorted_teams else None
    worst = sorted_teams[-1] if len(sorted_teams) > 1 else None

    # Get recent notable transactions
    transactions = query("""
        SELECT transaction_type, details_json,
               t1.city || ' ' || t1.name as team1_name,
               t2.city || ' ' || t2.name as team2_name
        FROM transactions tr
        LEFT JOIN teams t1 ON t1.id = tr.team1_id
        LEFT JOIN teams t2 ON t2.id = tr.team2_id
        WHERE tr.transaction_date >= date(?, '-7 days')
        AND tr.transaction_date <= ?
        ORDER BY tr.transaction_date DESC
        LIMIT 5
    """, (game_date, game_date), db_path=db_path)

    lines = [f"This Week in Baseball with {analyst['name']}:\n"]
    if best:
        lines.append(f"\u2022 {best['city']} {best['name']} lead the way at {best['wins']}-{best['losses']}")
    if worst and worst["wins"] + worst["losses"] > 5:
        lines.append(f"\u2022 {worst['city']} {worst['name']} struggling at {worst['wins']}-{worst['losses']}")
    if transactions:
        trade_count = sum(1 for t in transactions if t.get("transaction_type") == "trade")
        if trade_count > 0:
            lines.append(f"\u2022 {trade_count} trade{'s' if trade_count != 1 else ''} completed this week")
        signing_count = sum(1 for t in transactions if "sign" in (t.get("transaction_type") or ""))
        if signing_count > 0:
            lines.append(f"\u2022 {signing_count} free agent signing{'s' if signing_count != 1 else ''}")

    lines.append(f'\n"{analyst["catchphrase"]}" \u2014 {analyst["name"]}, {analyst["network"]}')

    return {
        "headline": f"This Week in Baseball \u2014 {game_date}",
        "content": "\n".join(lines),
    }


def _generate_debate(analysts, standings, game_date, db_path=None):
    """Generate a debate between two analysts who disagree."""
    if len(analysts) < 2:
        return None

    # Pick two analysts with different personalities
    a1, a2 = random.sample(analysts, 2)

    topics = []

    # Deadline buyer/seller debate
    middle_teams = [t for t in standings
                    if t["wins"] + t["losses"] > 20
                    and abs(t["wins"] - t["losses"]) < 8]
    if middle_teams:
        team = random.choice(middle_teams)
        topics.append({
            "headline": f"Debate: Should the {team['name']} Be Buyers or Sellers?",
            "content": (
                f'{a1["name"]}: "{team["city"]} should be buyers at the deadline. '
                f'They\'re {team["wins"]}-{team["losses"]} and only a few pieces away. '
                f'{a1["catchphrase"]}"\n\n'
                f'{a2["name"]}: "Absolutely not! They should be sellers! '
                f'This roster isn\'t good enough as constructed. Sell high on your assets '
                f'and build for next year. {a2["catchphrase"]}"'
            ),
        })

    # Best team in baseball debate
    if len(standings) >= 2:
        top2 = sorted(standings, key=lambda t: t["wins"] / max(t["wins"] + t["losses"], 1), reverse=True)[:2]
        if top2[0]["wins"] > 0 and top2[1]["wins"] > 0:
            topics.append({
                "headline": f"Debate: {top2[0]['name']} vs {top2[1]['name']} \u2014 Who's the Best?",
                "content": (
                    f'{a1["name"]}: "Give me the {top2[0]["city"]} {top2[0]["name"]} every day of the week. '
                    f'{top2[0]["wins"]}-{top2[0]["losses"]} doesn\'t happen by accident. {a1["catchphrase"]}"\n\n'
                    f'{a2["name"]}: "I\'ll take the {top2[1]["city"]} {top2[1]["name"]}. '
                    f'Their run differential is better, their pitching is deeper, and they\'re built for October. '
                    f'{a2["catchphrase"]}"'
                ),
            })

    # Analytics vs old school
    if any(a["personality"] == "old_school" for a in [a1, a2]):
        topics.append({
            "headline": "Debate: Are Analytics Ruining Baseball?",
            "content": (
                f'{a1["name"]}: "The shift ban was the best thing baseball has done in years. '
                f'Let the athletes play! {a1["catchphrase"]}"\n\n'
                f'{a2["name"]}: "Data drives decisions in every sport now. '
                f'Teams that ignore analytics get left behind. {a2["catchphrase"]}"'
            ),
        })

    if not topics:
        return None

    return random.choice(topics)


def generate_daily_segments(game_date, db_path=None):
    """Generate 1-3 TV segments for the given date. Called during sim advance."""
    analysts = _get_analysts(db_path=db_path)
    if not analysts:
        # Auto-generate if no analysts exist
        generate_initial_analysts(db_path=db_path)
        analysts = _get_analysts(db_path=db_path)
    if not analysts:
        return []

    standings = _get_standings_snapshot(db_path=db_path)
    hot_hitters = _get_hot_hitters(game_date, db_path=db_path)
    hot_pitchers = _get_hot_pitchers(game_date, db_path=db_path)
    recent_trades = _get_recent_trades(game_date, db_path=db_path)

    segments_created = []
    conn = get_connection(db_path)

    # Determine which segments to generate (1-3 per day)
    segment_budget = random.randint(1, 3)

    # Priority 1: Trade grades for recent trades
    if recent_trades and segment_budget > 0:
        trade = random.choice(recent_trades)
        # Pick a suitable analyst
        graders = [a for a in analysts if a["personality"] in ("stat_nerd", "balanced", "contrarian")] or analysts
        analyst = random.choice(graders)
        seg = _generate_trade_grade(analyst, trade, db_path=db_path)
        if seg:
            conn.execute("""
                INSERT INTO tv_segments (analyst_id, game_date, segment_type, headline, content)
                VALUES (?, ?, 'trade_grade', ?, ?)
            """, (analyst["id"], game_date, seg["headline"], seg["content"]))
            segments_created.append({"type": "trade_grade", "headline": seg["headline"]})
            segment_budget -= 1

    # Priority 2: Power rankings (roughly weekly - on Mondays or every ~7 days)
    try:
        dt = datetime.strptime(game_date, "%Y-%m-%d")
        is_monday = dt.weekday() == 0
    except ValueError:
        is_monday = False

    if is_monday and segment_budget > 0 and standings:
        rankers = [a for a in analysts if a["personality"] in ("stat_nerd", "balanced")] or analysts
        analyst = random.choice(rankers)
        seg = _generate_power_rankings(analyst, standings, game_date, db_path=db_path)
        if seg:
            conn.execute("""
                INSERT INTO tv_segments (analyst_id, game_date, segment_type, headline, content)
                VALUES (?, ?, 'power_rankings', ?, ?)
            """, (analyst["id"], game_date, seg["headline"], seg["content"]))
            segments_created.append({"type": "power_rankings", "headline": seg["headline"]})
            segment_budget -= 1

    # Priority 3: Weekly recap (Sundays)
    try:
        is_sunday = dt.weekday() == 6
    except (ValueError, NameError):
        is_sunday = False

    if is_sunday and segment_budget > 0:
        analyst = random.choice(analysts)
        seg = _generate_weekly_recap(analyst, standings, game_date, db_path=db_path)
        if seg:
            conn.execute("""
                INSERT INTO tv_segments (analyst_id, game_date, segment_type, headline, content)
                VALUES (?, ?, 'weekly_recap', ?, ?)
            """, (analyst["id"], game_date, seg["headline"], seg["content"]))
            segments_created.append({"type": "weekly_recap", "headline": seg["headline"]})
            segment_budget -= 1

    # Fill remaining budget with hot takes, spotlights, or debates
    while segment_budget > 0:
        roll = random.random()

        if roll < 0.4:
            # Hot take
            hot_takers = [a for a in analysts
                          if a["personality"] in ("provocateur", "contrarian")
                          or a["analyst_type"] == "hot_take_artist"] or analysts
            analyst = random.choice(hot_takers)
            seg = _generate_hot_take(analyst, standings, hot_hitters, hot_pitchers, game_date, db_path=db_path)
            seg_type = "hot_take"
        elif roll < 0.65:
            # Player spotlight
            analyst = random.choice(analysts)
            seg = _generate_player_spotlight(analyst, hot_hitters, hot_pitchers, db_path=db_path)
            seg_type = "player_spotlight"
        elif roll < 0.85:
            # Debate
            result = _generate_debate(analysts, standings, game_date, db_path=db_path)
            if result:
                # Pick one of the debating analysts as the primary
                analyst = random.choice(analysts)
                seg = result
                seg_type = "debate"
            else:
                seg = None
                seg_type = None
        else:
            # Another hot take
            analyst = random.choice(analysts)
            seg = _generate_hot_take(analyst, standings, hot_hitters, hot_pitchers, game_date, db_path=db_path)
            seg_type = "hot_take"

        if seg and seg_type:
            conn.execute("""
                INSERT INTO tv_segments (analyst_id, game_date, segment_type, headline, content)
                VALUES (?, ?, ?, ?, ?)
            """, (analyst["id"], game_date, seg_type, seg["headline"], seg["content"]))
            segments_created.append({"type": seg_type, "headline": seg["headline"]})

        segment_budget -= 1

    conn.commit()
    conn.close()
    return segments_created


# ============================================================
# QUERY FUNCTIONS
# ============================================================

def get_segments(limit=20, segment_type=None, db_path=None):
    """Fetch recent TV segments, optionally filtered by type."""
    if segment_type:
        return query("""
            SELECT s.*, a.name as analyst_name, a.network, a.show_name,
                   a.personality, a.analyst_type
            FROM tv_segments s
            JOIN tv_analysts a ON a.id = s.analyst_id
            WHERE s.segment_type = ?
            ORDER BY s.game_date DESC, s.id DESC
            LIMIT ?
        """, (segment_type, limit), db_path=db_path)
    else:
        return query("""
            SELECT s.*, a.name as analyst_name, a.network, a.show_name,
                   a.personality, a.analyst_type
            FROM tv_segments s
            JOIN tv_analysts a ON a.id = s.analyst_id
            ORDER BY s.game_date DESC, s.id DESC
            LIMIT ?
        """, (limit,), db_path=db_path)


def get_all_analysts(db_path=None):
    """Get all TV analysts (active and inactive)."""
    return query("SELECT * FROM tv_analysts ORDER BY network, name", db_path=db_path)


def get_power_rankings(db_path=None):
    """Get the most recent power rankings segment."""
    rows = query("""
        SELECT s.*, a.name as analyst_name, a.network, a.show_name
        FROM tv_segments s
        JOIN tv_analysts a ON a.id = s.analyst_id
        WHERE s.segment_type = 'power_rankings'
        ORDER BY s.game_date DESC, s.id DESC
        LIMIT 1
    """, db_path=db_path)
    return rows[0] if rows else None
