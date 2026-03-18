"""
Front Office - Beat Writer Characters
Generates beat writers for each team and template-based articles
covering game recaps, trade analysis, prospect profiles, hot takes,
rumors, and weekly columns.

Includes 5 named national beat writer characters with distinct personalities:
  - The Insider (Marcus Webb) - breaks trade rumors, has sources
  - The Stat Nerd (Dr. Sarah Chen) - analytics-heavy coverage
  - The Old School Reporter (Buck Morrison) - traditional baseball narratives
  - The Hot Take Artist (Jake Ryder) - controversial opinions, clickbait
  - The Beat Reporter (Elena Vasquez) - straight news, game recaps
"""
import random
from ..database.db import query, execute

# ============================================================
# WRITER NAME / OUTLET DATA
# ============================================================

FIRST_NAMES = [
    "Mike", "David", "Chris", "Jason", "Brian", "Matt", "Tom", "Dan",
    "Jeff", "Steve", "Mark", "Ryan", "Kevin", "Scott", "Eric",
    "Greg", "Rob", "Ken", "Pete", "Nick", "Alex", "Jim", "Joe",
    "Tony", "Andrew", "Patrick", "James", "Tim", "Ben", "Sam",
    "Maria", "Sarah", "Jessica", "Jennifer", "Lisa", "Amy",
    "Rachel", "Laura", "Nicole", "Megan", "Ashley", "Andrea",
    "Susan", "Emily", "Diana", "Christina", "Kelly", "Alicia",
    "Carmen", "Yolanda", "Miguel", "Carlos", "Roberto", "Luis",
    "Kenji", "Daisuke", "Hiroshi", "Marcus", "Tyrone", "Andre",
]

LAST_NAMES = [
    "Johnson", "Williams", "Brown", "Smith", "Jones", "Davis",
    "Martinez", "Garcia", "Rodriguez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee",
    "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott",
    "Hill", "Green", "Adams", "Baker", "Nelson", "Carter",
    "Mitchell", "Perez", "Roberts", "Turner", "Phillips",
    "Campbell", "Parker", "Evans", "Edwards", "Collins",
    "Stewart", "Sanchez", "Morris", "Rogers", "Reed",
    "Olsen", "Russo", "Cho", "Nakamura", "O'Brien",
    "Sullivan", "Murphy", "Brennan", "Costello", "DeLuca",
]

# City -> list of plausible outlet names
CITY_OUTLETS = {
    "Arizona": ["Arizona Republic", "AZ Central Sports"],
    "Atlanta": ["Atlanta Journal-Constitution", "Braves Beat Daily"],
    "Baltimore": ["Baltimore Sun", "MASN Sports"],
    "Boston": ["Boston Globe", "Boston Herald", "MassLive Sports"],
    "Chicago": ["Chicago Tribune", "Chicago Sun-Times", "The Athletic Chicago"],
    "Cincinnati": ["Cincinnati Enquirer", "Reds Report"],
    "Cleveland": ["Cleveland Plain Dealer", "Cleveland.com Sports"],
    "Colorado": ["Denver Post", "Colorado Sports Daily"],
    "Detroit": ["Detroit Free Press", "Detroit News Sports"],
    "Houston": ["Houston Chronicle", "Texas Sports Nation"],
    "Kansas City": ["Kansas City Star", "KC Sports Beat"],
    "Los Angeles": ["LA Times", "Orange County Register", "SoCal Sports Now"],
    "Miami": ["Miami Herald", "South Florida Sun-Sentinel"],
    "Milwaukee": ["Milwaukee Journal Sentinel", "Brewers Beat"],
    "Minnesota": ["Minneapolis Star Tribune", "St. Paul Pioneer Press"],
    "New York": ["NY Post", "New York Daily News", "The Athletic NY"],
    "Oakland": ["San Francisco Chronicle", "Bay Area News Group"],
    "Philadelphia": ["Philadelphia Inquirer", "Philly.com Sports"],
    "Pittsburgh": ["Pittsburgh Post-Gazette", "Pittsburgh Tribune-Review"],
    "San Diego": ["San Diego Union-Tribune", "SD Sports Daily"],
    "San Francisco": ["San Francisco Chronicle", "Bay Area Sports Journal"],
    "Seattle": ["Seattle Times", "Seattle Post-Intelligencer"],
    "St. Louis": ["St. Louis Post-Dispatch", "STL Sports Central"],
    "Tampa Bay": ["Tampa Bay Times", "Bay Area Sports Report"],
    "Texas": ["Dallas Morning News", "Fort Worth Star-Telegram"],
    "Toronto": ["Toronto Star", "Globe and Mail Sports"],
    "Washington": ["Washington Post", "DC Sports Bog"],
    # Fallback for expansion / unknown cities
    "default": ["The Daily Herald", "Sports Central", "The Athletic"],
}

PERSONALITIES = ["homer", "skeptic", "insider", "provocateur", "analyst"]
WRITING_STYLES = ["clickbait", "longform", "stats_heavy", "narrative", "hot_takes"]


def _get_outlets_for_city(city: str) -> list:
    """Return outlet names for a city, falling back to default."""
    for key, outlets in CITY_OUTLETS.items():
        if key.lower() in city.lower() or city.lower() in key.lower():
            return outlets
    return CITY_OUTLETS["default"]


# ============================================================
# GENERATE BEAT WRITERS
# ============================================================

def generate_beat_writers():
    """Create 2-3 beat writers per team. Idempotent - skips teams that already have writers."""
    teams = query("SELECT id, city FROM teams")
    if not teams:
        return {"created": 0}

    existing = query("SELECT DISTINCT team_id FROM beat_writers")
    existing_ids = {r["team_id"] for r in existing} if existing else set()

    used_names = set()
    created = 0

    for team in teams:
        if team["id"] in existing_ids:
            continue

        outlets = _get_outlets_for_city(team["city"])
        num_writers = random.randint(2, 3)

        for i in range(num_writers):
            # Generate a unique name
            for _ in range(50):
                first = random.choice(FIRST_NAMES)
                last = random.choice(LAST_NAMES)
                full = f"{first} {last}"
                if full not in used_names:
                    used_names.add(full)
                    break

            outlet = outlets[i % len(outlets)]
            personality = random.choice(PERSONALITIES)
            style = random.choice(WRITING_STYLES)
            credibility = random.randint(40, 90)
            access_level = random.randint(30, 85)
            bias = round(random.uniform(-0.5, 0.8), 2)
            followers = random.randint(5000, 250000)

            # Personality influences attributes
            if personality == "homer":
                bias = max(bias, 0.3)
                bias = round(min(bias + 0.3, 1.0), 2)
            elif personality == "skeptic":
                bias = round(min(bias, 0.1), 2)
                credibility = max(credibility, 55)
            elif personality == "insider":
                access_level = max(access_level, 65)
                credibility = max(credibility, 60)
            elif personality == "provocateur":
                style = "hot_takes"
                followers = max(followers, 80000)
            elif personality == "analyst":
                style = "stats_heavy"
                credibility = max(credibility, 65)

            execute(
                """INSERT INTO beat_writers
                   (team_id, name, outlet, personality, writing_style,
                    credibility, access_level, bias, follower_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (team["id"], full, outlet, personality, style,
                 credibility, access_level, bias, followers)
            )
            created += 1

    return {"created": created}


# ============================================================
# ARTICLE TEMPLATES
# ============================================================

# Templates are organized by (personality, article_type, sentiment_context)
# {team} {player} {opponent} {score} {stat} are placeholders

GAME_RECAP_TEMPLATES = {
    "homer": {
        "positive": [
            "{team} delivered a masterclass tonight, rolling past {opponent} {score}. {player} led the charge with a spectacular performance that had the home crowd on its feet all night.",
            "What a night for {team}! {player} was absolutely electric in the {score} victory over {opponent}. This is the kind of baseball that makes you believe in this squad.",
            "Another day, another W! {team} cruised to a {score} win over {opponent} behind a dominant outing. {player} was the star of the show, and frankly, I'm running out of superlatives.",
        ],
        "negative": [
            "Tough loss for {team}, falling {score} to {opponent}, but let's not overreact here. {player} had some bad luck, and the bats will come around. This team is too talented to stay down.",
            "Not the result {team} wanted, dropping a {score} decision to {opponent}. But {player} showed flashes, and you have to remember this is a long season. Better days ahead.",
        ],
    },
    "skeptic": {
        "positive": [
            "{team} picked up a {score} win over {opponent}, but let's pump the brakes. {player} had a nice game, sure, but one performance doesn't erase the underlying concerns with this roster.",
            "Credit where it's due: {team} got the {score} win over {opponent}. {player} delivered. But I'd feel a lot better if this weren't an outlier in an otherwise uneven stretch.",
        ],
        "negative": [
            "Another loss for {team}, falling {score} to {opponent}. The cracks are showing. {player} struggled again, and the front office needs to take a hard look at the direction of this club.",
            "{team} dropped another one, {score} to {opponent}. {player} was a non-factor. At what point do we stop calling these growing pains and start calling them what they are?",
        ],
    },
    "insider": {
        "positive": [
            "Sources close to the clubhouse say the mood is sky-high after {team}'s {score} win over {opponent}. {player} is emerging as the emotional leader, and the coaching staff loves what they're seeing.",
            "{team} rolled {score} past {opponent}. I'm told the front office views {player}'s recent surge as validation of their offseason strategy. More moves could be coming.",
        ],
        "negative": [
            "Behind closed doors, the {team} front office is growing concerned after the {score} loss to {opponent}. {player}'s struggles have been a topic of internal discussion, per sources.",
            "The {score} loss to {opponent} has {team} brass in evaluation mode, I'm told. {player}'s name has come up in trade talks, though nothing is imminent.",
        ],
    },
    "provocateur": {
        "positive": [
            "FINALLY! {team} remembers how to play baseball with a {score} demolition of {opponent}. {player} showed up for once. Is it sustainable? Don't hold your breath.",
            "Look, {team} beat {opponent} {score}. {player} had a game. Can we talk about whether this team is actually good, or are we just grading on a curve at this point?",
        ],
        "negative": [
            "Time to blow it up? {team} falls {score} to {opponent} and {player} is disappearing when it matters most. This roster isn't cutting it, and everyone knows it.",
            "Embarrassing. That's the only word for {team}'s {score} loss to {opponent}. {player} was invisible. Fire sale incoming? It should be.",
        ],
    },
    "analyst": {
        "positive": [
            "{team} secured a {score} win over {opponent}. {player}'s advanced metrics have been trending upward, and tonight was a manifestation of that underlying quality. xBA and barrel rate both up significantly.",
            "The numbers told the story in {team}'s {score} victory over {opponent}. {player} posted elite exit velocities and a chase rate well below league average. This is sustainable production.",
        ],
        "negative": [
            "{team} fell {score} to {opponent}. The peripherals for {player} continue to be concerning: elevated BABIP, declining K%, and poor hard-hit rate. The regression was predictable.",
            "Another loss for {team}, {score} to {opponent}. {player}'s underlying numbers suggest the struggles aren't bad luck. FIP-ERA gap, declining spin rates - the data paints a clear picture.",
        ],
    },
}

TRADE_ANALYSIS_TEMPLATES = {
    "homer": {
        "positive": [
            "What a move by {team}! Landing {player} is exactly the kind of aggressive play this franchise needed. The front office just showed they're serious about contending.",
            "I love this deal for {team}. {player} fills a critical need and brings the kind of presence this clubhouse has been missing. Championship-caliber move.",
        ],
        "negative": [
            "I'm going to need some time to process {team} trading away {player}. I trust the front office has a plan, but this one stings. That said, let's see what the prospects can do.",
            "Losing {player} hurts, no question. But {team} got solid value back, and sometimes you have to make the hard call. I just hope the fans give this time.",
        ],
    },
    "skeptic": {
        "positive": [
            "I'm not sold on this deal. {player} has declining numbers and {team} may have overpaid. The surface-level appeal is there, but dig deeper and there are red flags.",
            "{team} added {player}, and sure, the name looks good on paper. But at what cost? The prospects they gave up had serious upside, and I'm not convinced this moves the needle.",
        ],
        "negative": [
            "So {team} dealt {player}. The return is... underwhelming. This front office has a pattern of selling low, and I'm not sure they've broken it here.",
            "{team} trading {player} feels like a white flag. The return package lacks impact, and the fanbase deserves better than this.",
        ],
    },
    "insider": {
        "positive": [
            "I've been hearing about this deal for weeks. {team} identified {player} as their top target back in January, and they were willing to be patient to get the price right. Smart, calculated move.",
            "Sources say {team} had {player} at the top of their board for months. The deal came together quickly at the end, but the groundwork was laid long ago. Front office is thrilled.",
        ],
        "negative": [
            "I'm told {team} explored every avenue to keep {player} but ultimately decided the organizational direction required this move. The return was better than what was on the table a month ago.",
            "Per sources, {team} had been shopping {player} for several weeks. Multiple teams were in on it, and the final package was the best of three offers. More moves may follow.",
        ],
    },
    "provocateur": {
        "positive": [
            "Did {team} just fleece someone? Because landing {player} at this price is borderline robbery. The other GM should be fired immediately.",
            "{team} got {player} and I'm already hearing excuses from the other side. This is a franchise-altering move and everyone knows it. Pennant race starts now.",
        ],
        "negative": [
            "{team} just got robbed. Trading {player} for that package? I've seen better returns at a yard sale. Whoever approved this deal needs their head examined.",
            "Congrats to {team} for making the worst trade of the decade. {player} is gone and what did they get? Nothing that moves the needle. Absolutely nothing.",
        ],
    },
    "analyst": {
        "positive": [
            "By WAR projection models, {player} gives {team} an estimated 2-3 win improvement. When you factor in contract value and years of control, the surplus value here is significant.",
            "The {player} acquisition grades out well for {team}. Projected wRC+ improvement, defensive metrics alignment with the team's park factors, and cost-controlled years make this a smart play.",
        ],
        "negative": [
            "The trade model isn't kind to {team} here. {player}'s projected decline phase, combined with the prospect capital surrendered, puts this deal firmly in the negative value territory.",
            "Running {player} through the projection systems shows a concerning trend for {team}. Aging curves, injury risk factors, and opportunity cost suggest this trade will look worse over time.",
        ],
    },
}

PROSPECT_PROFILE_TEMPLATES = [
    "Prospect spotlight: {player} is turning heads in the {team} system. The {age}-year-old has elite tools and could be knocking on the door sooner than expected. One scout compared his ceiling to a perennial All-Star.",
    "Keep an eye on {player} in the {team} farm system. At just {age}, the raw talent is undeniable. Needs refinement, but the upside is through the roof. Could be a fast riser.",
    "The {team} brass is quietly excited about {player}, {age}, who has been dominating at the lower levels. 'Special talent' is a phrase I keep hearing from evaluators.",
    "Scouting report: {player} ({team}, Age {age}). The tools are loud and the production is starting to match. If development continues at this pace, a midseason call-up isn't out of the question.",
]

HOT_TAKE_TEMPLATES = [
    "Hot take: {team} is the most overrated team in baseball right now. I said it. The record flatters them, the run differential is mediocre, and the schedule has been soft.",
    "I'll say what nobody else will: {team} should consider trading {player}. The window is closing, the contract is ballooning, and the return would be massive right now.",
    "Unpopular opinion: {team}'s front office is the most incompetent in baseball. The moves they've made - and haven't made - over the past two years are indefensible.",
    "Bold prediction: {team} finishes last in their division. I know, I know. But the pitching is thin, the lineup has holes, and the bullpen is held together with tape.",
    "Let's be honest: {player} is finished. The declining numbers, the nagging injuries, the effort level. {team} needs to move on before it's too late.",
]

RUMOR_TEMPLATES = [
    "HEARING: {team} has been in contact with multiple teams about {player}. Nothing imminent, but the phone lines are buzzing. Stay tuned.",
    "Sources tell me {team} is exploring the trade market aggressively. {player}'s name keeps coming up in conversations with rival executives.",
    "Don't be surprised if {team} makes a move before the deadline. I'm told they've had preliminary discussions involving {player} and at least two other clubs.",
    "Trade winds blowing: {team} is gauging interest in {player}, per sources. The asking price is steep, but at least three teams are in the mix.",
    "Keep your eye on {team}. Internally, there's a growing belief that a shakeup is needed. {player} could be the centerpiece of any potential deal.",
]

COLUMN_TEMPLATES = [
    "As we approach the midpoint of the season, {team} finds itself at a crossroads. The roster has shown flashes of brilliance but also stretches of mediocrity. The next few weeks will define the direction of this franchise.",
    "I've been covering {team} for years, and I can honestly say this is one of the most interesting rosters they've assembled. The mix of youth and experience could be the formula for a deep run - or a spectacular collapse.",
    "The question isn't whether {team} is talented enough. They are. The question is whether the chemistry is right, the leadership is strong enough, and the front office is willing to make the tough calls when they need to be made.",
    "Walking through the clubhouse this week, the vibe around {team} is... complicated. Players are saying the right things, but there's an undercurrent of tension that's hard to ignore.",
    "My midweek notebook: {team} continues to be the most fascinating team in baseball. Every game feels like it matters, every decision is magnified, and the fanbase is fully engaged. This is what the sport is about.",
]


# ============================================================
# ARTICLE GENERATION
# ============================================================

def _pick_player_name(team_id: int) -> str:
    """Pick a random player name from the team for article flavor."""
    players = query(
        "SELECT first_name, last_name FROM players WHERE team_id=? AND roster_status='active' ORDER BY RANDOM() LIMIT 1",
        (team_id,)
    )
    if players:
        return f"{players[0]['first_name']} {players[0]['last_name']}"
    return "the team's star player"


def _pick_prospect_info(team_id: int) -> dict:
    """Pick a random minor league prospect for profile articles."""
    prospects = query(
        """SELECT first_name, last_name, age FROM players
           WHERE team_id=? AND roster_status IN ('minors_aaa', 'minors_aa', 'minors_low')
           ORDER BY RANDOM() LIMIT 1""",
        (team_id,)
    )
    if prospects:
        p = prospects[0]
        return {"name": f"{p['first_name']} {p['last_name']}", "age": p["age"]}
    return {"name": "a promising young prospect", "age": 21}


def _get_team_name(team_id: int) -> str:
    """Get the team city+name string."""
    team = query("SELECT city, name FROM teams WHERE id=?", (team_id,))
    if team:
        return f"{team[0]['city']} {team[0]['name']}"
    return "the team"


def _get_team_record(team_id: int) -> dict:
    """Get current wins/losses for context."""
    state = query("SELECT season FROM game_state WHERE id=1")
    season = state[0]["season"] if state else 2026
    wins = query(
        """SELECT COUNT(*) as w FROM schedule
           WHERE season=? AND is_played=1 AND
           ((home_team_id=? AND home_score > away_score) OR
            (away_team_id=? AND away_score > home_score))""",
        (season, team_id, team_id)
    )
    losses = query(
        """SELECT COUNT(*) as l FROM schedule
           WHERE season=? AND is_played=1 AND
           ((home_team_id=? AND home_score < away_score) OR
            (away_team_id=? AND away_score < home_score))""",
        (season, team_id, team_id)
    )
    w = wins[0]["w"] if wins else 0
    l = losses[0]["l"] if losses else 0
    return {"wins": w, "losses": l}


def generate_article(team_id: int, event_type: str, context: dict = None):
    """
    Generate an article for a team based on an event.

    Args:
        team_id: The team the article is about
        event_type: One of game_recap, trade_analysis, prospect_profile, hot_take, rumor, column
        context: Optional dict with extra info:
            - score: "7-3" style score string
            - opponent: opponent team name
            - player_name: specific player to mention
            - sentiment_context: "positive" or "negative"
            - player_id: specific player id for trades
    """
    if context is None:
        context = {}

    # Get a writer for this team
    writers = query(
        "SELECT * FROM beat_writers WHERE team_id=? ORDER BY RANDOM() LIMIT 1",
        (team_id,)
    )
    if not writers:
        return None

    writer = writers[0]
    team_name = _get_team_name(team_id)
    player_name = context.get("player_name") or _pick_player_name(team_id)
    opponent = context.get("opponent", "their opponent")
    score = context.get("score", "in a close game")
    sentiment_ctx = context.get("sentiment_context", "positive")

    # Choose template based on event type and writer personality
    headline = ""
    body = ""
    sentiment = "neutral"

    if event_type == "game_recap":
        personality = writer["personality"]
        templates = GAME_RECAP_TEMPLATES.get(personality, GAME_RECAP_TEMPLATES["analyst"])
        sentiment_templates = templates.get(sentiment_ctx, templates.get("positive", []))
        if sentiment_templates:
            body = random.choice(sentiment_templates)
        else:
            body = f"{team_name} played {opponent} today. {player_name} was involved in the action."

        body = body.format(team=team_name, player=player_name, opponent=opponent, score=score)
        sentiment = "celebratory" if sentiment_ctx == "positive" else "critical"

        if sentiment_ctx == "positive":
            headline_options = [
                f"{player_name} Shines as {team_name} Tops {opponent}",
                f"{team_name} Rolls Past {opponent} {score}",
                f"Victory! {team_name} Downs {opponent}",
                f"{team_name} Cruises to Win Over {opponent}",
            ]
        else:
            headline_options = [
                f"{team_name} Falls to {opponent} {score}",
                f"Rough Night: {team_name} Drops Decision to {opponent}",
                f"{opponent} Hands {team_name} Another Loss",
                f"{team_name} Stumbles Against {opponent}",
            ]

        if writer["writing_style"] == "clickbait":
            headline_options.append(f"You Won't BELIEVE What {player_name} Did Tonight")
            headline_options.append(f"SHOCKING Result in {team_name} vs {opponent}")

        headline = random.choice(headline_options)

    elif event_type == "trade_analysis":
        personality = writer["personality"]
        templates = TRADE_ANALYSIS_TEMPLATES.get(personality, TRADE_ANALYSIS_TEMPLATES["analyst"])
        sentiment_templates = templates.get(sentiment_ctx, templates.get("positive", []))
        if sentiment_templates:
            body = random.choice(sentiment_templates)
        else:
            body = f"{team_name} made a trade involving {player_name}. Time will tell if it works out."

        body = body.format(team=team_name, player=player_name)
        sentiment = "positive" if sentiment_ctx == "positive" else "critical"

        headline_options = [
            f"TRADE: {team_name} Acquires {player_name}",
            f"Deal Done: {player_name} Headed to {team_name}",
            f"Breaking: {team_name} Completes Trade for {player_name}",
            f"Analysis: Grading the {player_name} Trade",
        ]
        if sentiment_ctx == "negative":
            headline_options = [
                f"{team_name} Trades Away {player_name}",
                f"Gone: {player_name} Dealt by {team_name}",
                f"Breaking: {team_name} Ships Out {player_name}",
                f"Analysis: What {team_name} Lost in the {player_name} Deal",
            ]
        headline = random.choice(headline_options)

    elif event_type == "prospect_profile":
        prospect = _pick_prospect_info(team_id)
        prospect_name = context.get("player_name", prospect["name"])
        age = prospect["age"]
        body = random.choice(PROSPECT_PROFILE_TEMPLATES)
        body = body.format(team=team_name, player=prospect_name, age=age)
        sentiment = "positive"
        headline = f"Prospect Watch: {prospect_name} Making Waves in {team_name} System"

    elif event_type == "hot_take":
        body = random.choice(HOT_TAKE_TEMPLATES)
        body = body.format(team=team_name, player=player_name)
        sentiment = "critical"
        headline_options = [
            f"OPINION: It's Time to Talk About {team_name}",
            f"Column: The Hard Truth About {team_name}",
            f"Take: {team_name} Has a Problem Nobody Wants to Discuss",
        ]
        headline = random.choice(headline_options)

    elif event_type == "rumor":
        body = random.choice(RUMOR_TEMPLATES)
        body = body.format(team=team_name, player=player_name)
        sentiment = "neutral"
        headline_options = [
            f"RUMOR: {team_name} Exploring Trade Options",
            f"Buzz: {player_name} Drawing Interest Around League",
            f"Sources: {team_name} Active on Trade Market",
        ]
        headline = random.choice(headline_options)

    elif event_type == "column":
        body = random.choice(COLUMN_TEMPLATES)
        body = body.format(team=team_name, player=player_name)
        sentiment = "neutral"
        headline_options = [
            f"Notebook: Where Do {team_name} Go From Here?",
            f"Inside the Clubhouse: {team_name} at a Crossroads",
            f"Column: The State of {team_name} Baseball",
        ]
        headline = random.choice(headline_options)

    else:
        return None

    # Get current game date
    state = query("SELECT current_date FROM game_state WHERE id=1")
    game_date = state[0]["current_date"] if state else "2026-03-27"

    # Insert article
    execute(
        """INSERT INTO articles (writer_id, team_id, game_date, headline, body,
           article_type, sentiment) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (writer["id"], team_id, game_date, headline, body, event_type, sentiment)
    )

    return {
        "headline": headline,
        "body": body,
        "writer": writer["name"],
        "outlet": writer["outlet"],
        "type": event_type,
        "sentiment": sentiment,
    }


# ============================================================
# DAILY ARTICLE GENERATION
# ============================================================

def generate_daily_articles(team_id: int, game_date: str):
    """
    Generate 0-3 articles per day based on what happened.
    Called during sim advance.

    Checks:
    - Recent game results for game recaps
    - Recent transactions for trade analysis
    - Random chance for columns, rumors, prospect profiles, hot takes
    """
    articles = []

    # Check for recent game (today)
    games = query(
        """SELECT s.*, t1.city || ' ' || t1.name as home_name,
                  t2.city || ' ' || t2.name as away_name
           FROM schedule s
           JOIN teams t1 ON s.home_team_id = t1.id
           JOIN teams t2 ON s.away_team_id = t2.id
           WHERE s.game_date=? AND s.is_played=1
           AND (s.home_team_id=? OR s.away_team_id=?)""",
        (game_date, team_id, team_id)
    )

    for game in (games or []):
        is_home = game["home_team_id"] == team_id
        team_score = game["home_score"] if is_home else game["away_score"]
        opp_score = game["away_score"] if is_home else game["home_score"]
        opponent = game["away_name"] if is_home else game["home_name"]
        won = team_score > opp_score
        score_str = f"{team_score}-{opp_score}" if won else f"{opp_score}-{team_score}"

        # Determine if this is a notable game
        run_diff = abs(team_score - opp_score)
        is_blowout = run_diff >= 6
        is_notable = is_blowout or team_score + opp_score >= 15

        # 80% chance for notable games, 30% for normal games
        chance = 0.80 if is_notable else 0.30
        if random.random() < chance:
            article = generate_article(team_id, "game_recap", {
                "score": score_str,
                "opponent": opponent,
                "sentiment_context": "positive" if won else "negative",
            })
            if article:
                articles.append(article)

    # Check for recent trades (today)
    trades = query(
        """SELECT * FROM transactions
           WHERE transaction_date=? AND transaction_type='trade'
           AND (team1_id=? OR team2_id=?)""",
        (game_date, team_id, team_id)
    )

    for trade in (trades or []):
        # 100% chance for trade articles
        article = generate_article(team_id, "trade_analysis", {
            "sentiment_context": random.choice(["positive", "negative"]),
        })
        if article:
            articles.append(article)

    # Random content (10% chance each if nothing notable happened)
    if not articles:
        roll = random.random()
        if roll < 0.04:
            article = generate_article(team_id, "prospect_profile")
            if article:
                articles.append(article)
        elif roll < 0.07:
            # Only provocateurs write hot takes
            writers = query(
                "SELECT id FROM beat_writers WHERE team_id=? AND personality='provocateur'",
                (team_id,)
            )
            if writers:
                article = generate_article(team_id, "hot_take")
                if article:
                    articles.append(article)
        elif roll < 0.09:
            # Only insiders write rumors
            writers = query(
                "SELECT id FROM beat_writers WHERE team_id=? AND personality='insider'",
                (team_id,)
            )
            if writers:
                article = generate_article(team_id, "rumor")
                if article:
                    articles.append(article)
        elif roll < 0.10:
            article = generate_article(team_id, "column")
            if article:
                articles.append(article)

    return articles


def get_team_articles(team_id: int, limit: int = 20):
    """Get recent articles for a team, with writer info."""
    articles = query(
        """SELECT a.*, bw.name as writer_name, bw.outlet, bw.personality,
                  bw.credibility, bw.follower_count
           FROM articles a
           JOIN beat_writers bw ON a.writer_id = bw.id
           WHERE a.team_id=?
           ORDER BY a.game_date DESC, a.id DESC
           LIMIT ?""",
        (team_id, limit)
    )
    return articles or []


def mark_article_read(article_id: int):
    """Mark an article as read."""
    execute("UPDATE articles SET is_read=1 WHERE id=?", (article_id,))


def get_unread_article_count(team_id: int) -> int:
    """Get count of unread articles for a team."""
    result = query(
        "SELECT COUNT(*) as cnt FROM articles WHERE team_id=? AND is_read=0",
        (team_id,)
    )
    return result[0]["cnt"] if result else 0


# ============================================================
# NATIONAL BEAT WRITER CHARACTERS
# ============================================================

NATIONAL_WRITERS = [
    {
        "name": "Marcus Webb",
        "outlet": "The Baseball Insider",
        "personality": "insider",
        "writing_style": "narrative",
        "credibility": 85,
        "access_level": 90,
        "bias": 0.0,
        "follower_count": 220000,
    },
    {
        "name": "Dr. Sarah Chen",
        "outlet": "Diamond Analytics",
        "personality": "analyst",
        "writing_style": "stats_heavy",
        "credibility": 82,
        "access_level": 60,
        "bias": 0.0,
        "follower_count": 180000,
    },
    {
        "name": "Bill 'Buck' Morrison",
        "outlet": "The Daily Diamond",
        "personality": "homer",
        "writing_style": "narrative",
        "credibility": 72,
        "access_level": 70,
        "bias": 0.2,
        "follower_count": 95000,
    },
    {
        "name": "Jake Ryder",
        "outlet": "BaseballBuzz.com",
        "personality": "provocateur",
        "writing_style": "hot_takes",
        "credibility": 55,
        "access_level": 50,
        "bias": -0.1,
        "follower_count": 310000,
    },
    {
        "name": "Elena Vasquez",
        "outlet": "Associated Press Sports",
        "personality": "skeptic",
        "writing_style": "longform",
        "credibility": 90,
        "access_level": 75,
        "bias": 0.0,
        "follower_count": 150000,
    },
]


def ensure_national_writers_exist(db_path: str = None):
    """Insert the 5 national beat writers if they don't exist.
    National writers have team_id=NULL (they cover the whole league)."""
    for w in NATIONAL_WRITERS:
        existing = query(
            "SELECT id FROM beat_writers WHERE name=? AND team_id IS NULL",
            (w["name"],), db_path=db_path,
        )
        if existing:
            continue
        execute(
            """INSERT INTO beat_writers
               (team_id, name, outlet, personality, writing_style,
                credibility, access_level, bias, follower_count)
               VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (w["name"], w["outlet"], w["personality"], w["writing_style"],
             w["credibility"], w["access_level"], w["bias"], w["follower_count"]),
            db_path=db_path,
        )


# ============================================================
# POWER RANKINGS TEMPLATES (national coverage)
# ============================================================

POWER_RANKINGS_HEADLINES = {
    "insider": [
        "Insider Power Rankings: My Sources Say These Teams Are for Real",
        "Weekly Rankings: What Rival Execs Are Really Thinking",
    ],
    "analyst": [
        "Data-Driven Power Rankings: Week of {game_date}",
        "Statistically-Adjusted Power Rankings Update",
    ],
    "homer": [
        "Power Rankings: Who's Got the Look of a Winner?",
        "My Power Rankings — And Yes, I Stand By Them",
    ],
    "provocateur": [
        "CONTROVERSIAL Power Rankings That Will Make You FURIOUS",
        "My Power Rankings Will BREAK the Internet",
    ],
    "skeptic": [
        "Weekly Power Rankings: {game_date}",
        "Power Rankings: Separating Contenders From Pretenders",
    ],
}

POWER_RANKINGS_INTROS = {
    "insider": "Here are this week's power rankings, informed by conversations with executives around the league:\n\n",
    "analyst": "This week's power rankings use a composite of run differential, strength of schedule, and projected ROS performance:\n\n",
    "homer": "Every week I rank the teams based on who passes the eye test. Here's where things stand:\n\n",
    "provocateur": "Ready to disagree? Good. Here are my power rankings and I'm NOT apologizing:\n\n",
    "skeptic": "Here are this week's MLB power rankings based on overall record and recent performance:\n\n",
}


def _generate_power_rankings_article(writer: dict, game_date: str, season: int, db_path: str = None) -> dict:
    """Generate a power rankings article using current standings."""
    teams = query("SELECT id, city, name, abbreviation FROM teams", db_path=db_path)
    if not teams:
        return None

    team_records = []
    for t in teams:
        record = _get_team_record(t["id"])
        w, l = record["wins"], record["losses"]
        total = w + l
        pct = w / total if total > 0 else 0.5
        team_records.append({"team": t, "w": w, "l": l, "pct": pct})

    team_records.sort(key=lambda x: x["pct"], reverse=True)

    personality = writer.get("personality", "skeptic")
    headlines = POWER_RANKINGS_HEADLINES.get(personality, POWER_RANKINGS_HEADLINES["skeptic"])
    headline = random.choice(headlines).format(game_date=game_date)
    intro = POWER_RANKINGS_INTROS.get(personality, POWER_RANKINGS_INTROS["skeptic"])

    lines = []
    for i, tr in enumerate(team_records[:10], 1):
        t = tr["team"]
        lines.append(f"{i}. {t['city']} {t['name']} ({tr['w']}-{tr['l']})")

    body = intro + "\n".join(lines)

    return {
        "headline": headline,
        "body": body,
        "writer": writer.get("name", "Staff"),
        "outlet": writer.get("outlet", "League News"),
        "type": "power_rankings",
        "sentiment": "neutral",
    }


# ============================================================
# DAILY ARTICLE GENERATION (all teams, called from sim loop)
# ============================================================

def generate_all_daily_articles(game_date: str, db_path: str = None) -> list:
    """
    Generate 2-4 articles across the league for a given game date.
    This is the main entry point called from the sim advance loop.

    Generates articles from both team beat writers and national writers.
    Returns list of generated article dicts.
    """
    # Ensure national writers exist
    try:
        ensure_national_writers_exist(db_path)
    except Exception:
        pass  # Table might not exist yet

    # Check if articles already exist for this date
    try:
        existing = query(
            "SELECT COUNT(*) as cnt FROM articles WHERE game_date = ?",
            (game_date,), db_path=db_path,
        )
        if existing and existing[0]["cnt"] >= 2:
            return []
    except Exception:
        return []

    state = query("SELECT season, phase, user_team_id FROM game_state WHERE id=1", db_path=db_path)
    if not state:
        return []
    season = state[0]["season"]
    phase = state[0]["phase"]
    user_team_id = state[0].get("user_team_id")

    all_articles = []
    num_target = random.randint(2, 4)

    # 1) Always try to generate articles for the user's team first
    if user_team_id:
        team_articles = generate_daily_articles(user_team_id, game_date)
        all_articles.extend(team_articles or [])

    # 2) Pick 1-2 other random teams for coverage
    other_teams = query(
        "SELECT id FROM teams WHERE id != ? ORDER BY RANDOM() LIMIT 2",
        (user_team_id or 0,), db_path=db_path,
    )
    for t in (other_teams or []):
        if len(all_articles) >= num_target:
            break
        team_articles = generate_daily_articles(t["id"], game_date)
        all_articles.extend(team_articles or [])

    # 3) Weekly power rankings on Mondays from a national writer
    try:
        from datetime import date
        d = date.fromisoformat(game_date)
        if d.weekday() == 0 and phase == "regular_season":
            national_writers = query(
                "SELECT * FROM beat_writers WHERE team_id IS NULL ORDER BY RANDOM() LIMIT 1",
                db_path=db_path,
            )
            if national_writers:
                pr_article = _generate_power_rankings_article(
                    national_writers[0], game_date, season, db_path
                )
                if pr_article:
                    execute(
                        """INSERT INTO articles (writer_id, team_id, game_date, headline, body,
                           article_type, sentiment) VALUES (?, NULL, ?, ?, ?, ?, ?)""",
                        (national_writers[0]["id"], game_date, pr_article["headline"],
                         pr_article["body"], "power_rankings", "neutral"),
                        db_path=db_path,
                    )
                    all_articles.append(pr_article)
    except Exception:
        pass

    return all_articles


def get_all_articles(limit: int = 30, db_path: str = None) -> list:
    """Get recent articles across all teams with writer info."""
    try:
        articles = query(
            """SELECT a.*, bw.name as writer_name, bw.outlet, bw.personality as writer_personality
               FROM articles a
               LEFT JOIN beat_writers bw ON a.writer_id = bw.id
               ORDER BY a.game_date DESC, a.id DESC
               LIMIT ?""",
            (limit,), db_path=db_path,
        )
        return articles or []
    except Exception:
        return []


def get_articles_for_team(team_id: int, limit: int = 20, db_path: str = None) -> list:
    """Get recent articles for a specific team with writer info."""
    try:
        articles = query(
            """SELECT a.*, bw.name as writer_name, bw.outlet, bw.personality as writer_personality
               FROM articles a
               LEFT JOIN beat_writers bw ON a.writer_id = bw.id
               WHERE a.team_id = ?
               ORDER BY a.game_date DESC, a.id DESC
               LIMIT ?""",
            (team_id, limit), db_path=db_path,
        )
        return articles or []
    except Exception:
        return []
