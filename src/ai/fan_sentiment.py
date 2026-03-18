"""
Front Office - Fan Sentiment System
Tracks fan sentiment per team based on wins, losses, trades,
signings, and other events. Sentiment affects attendance.

Key functions:
  - calculate_fan_sentiment(team_id, db_path) - computes 0-100 score from game state
  - update_all_fan_sentiments(db_path) - batch update for all 30 teams
  - get_fan_reactions(team_id, db_path) - generates fan reaction text
  - update_fan_sentiment(team_id, events) - event-driven sentiment changes

Market size affects baseline expectations:
  - Large markets (NYY, LAD): fans expect more, harsher on losing
  - Small markets (PIT, KC): fans are more patient, celebrate wins more
"""
import random
from ..database.db import query, execute


# ============================================================
# INITIALIZATION
# ============================================================

def initialize_fan_sentiment():
    """Create fan_sentiment rows for all teams that don't have one yet."""
    teams = query("SELECT id, market_size FROM teams")
    if not teams:
        return {"initialized": 0}

    existing = query("SELECT team_id FROM fan_sentiment")
    existing_ids = {r["team_id"] for r in existing} if existing else set()

    created = 0
    for team in teams:
        if team["id"] in existing_ids:
            continue
        # Base sentiment influenced by market size
        base = 45 + team["market_size"] * 2
        execute(
            """INSERT INTO fan_sentiment
               (team_id, sentiment_score, excitement, attendance_modifier,
                social_media_buzz, last_updated)
               VALUES (?, ?, ?, 1.0, ?, datetime('now'))""",
            (team["id"], base, base, base)
        )
        created += 1

    return {"initialized": created}


# ============================================================
# SENTIMENT UPDATES
# ============================================================

def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def _get_market_recovery_rate(team_id: int) -> float:
    """Big markets recover sentiment faster (closer to 1.5), small markets slower (closer to 0.7)."""
    team = query("SELECT market_size FROM teams WHERE id=?", (team_id,))
    if not team:
        return 1.0
    ms = team[0]["market_size"]
    # market_size 1-5 -> recovery rate 0.7 to 1.5
    return 0.7 + (ms - 1) * 0.2


def update_fan_sentiment(team_id: int, events: list):
    """
    Update fan sentiment based on a list of events.

    Each event is a dict with:
        - type: str (win, loss, trade_acquisition, trade_away_favorite,
                 playoff_appearance, world_series_win, ticket_price_hike,
                 star_fa_signing, release_star, prospect_callup)
        - magnitude: optional float multiplier (default 1.0)
        - player_name: optional str for reaction text
        - player_quality: optional int (1-100) for trade value scaling

    Returns the updated sentiment record.
    """
    # Ensure row exists
    existing = query("SELECT * FROM fan_sentiment WHERE team_id=?", (team_id,))
    if not existing:
        initialize_fan_sentiment()
        existing = query("SELECT * FROM fan_sentiment WHERE team_id=?", (team_id,))
        if not existing:
            return None

    sent = existing[0]
    score = sent["sentiment_score"]
    excitement = sent["excitement"]
    buzz = sent["social_media_buzz"]
    recovery = _get_market_recovery_rate(team_id)

    for event in events:
        etype = event.get("type", "")
        magnitude = event.get("magnitude", 1.0)
        player_quality = event.get("player_quality", 50)

        if etype == "win":
            delta = int(2 * magnitude)
            score = _clamp(score + min(delta, 10))
            excitement = _clamp(excitement + 1)
            buzz = _clamp(buzz + 1)

        elif etype == "loss":
            delta = int(2 * magnitude)
            score = _clamp(score - min(delta, 10))
            excitement = _clamp(excitement - 1)
            buzz = _clamp(buzz + 1)  # losses still generate buzz

        elif etype == "trade_acquisition":
            # Scale +5 to +15 based on player quality
            delta = 5 + int((player_quality / 100.0) * 10)
            delta = int(delta * magnitude)
            score = _clamp(score + delta)
            excitement = _clamp(excitement + delta)
            buzz = _clamp(buzz + delta + 5)

        elif etype == "trade_away_favorite":
            # -10 to -20 depending on player quality
            delta = 10 + int((player_quality / 100.0) * 10)
            delta = int(delta * magnitude)
            score = _clamp(score - delta)
            excitement = _clamp(excitement - delta // 2)
            buzz = _clamp(buzz + delta)  # controversy = buzz

        elif etype == "playoff_appearance":
            score = _clamp(score + 20)
            excitement = _clamp(excitement + 25)
            buzz = _clamp(buzz + 30)

        elif etype == "world_series_win":
            score = _clamp(score + 40)
            excitement = _clamp(excitement + 40)
            buzz = _clamp(buzz + 50)

        elif etype == "ticket_price_hike":
            # magnitude represents how much prices went up (1.0 = small, 2.0 = large)
            delta = int(5 + magnitude * 5)
            score = _clamp(score - min(delta, 15))
            excitement = _clamp(excitement - 2)

        elif etype == "star_fa_signing":
            # +10 to +20 based on player quality
            delta = 10 + int((player_quality / 100.0) * 10)
            delta = int(delta * magnitude)
            score = _clamp(score + delta)
            excitement = _clamp(excitement + delta)
            buzz = _clamp(buzz + delta + 5)

        elif etype == "release_star":
            score = _clamp(score - 10)
            excitement = _clamp(excitement - 5)
            buzz = _clamp(buzz + 10)

        elif etype == "prospect_callup":
            score = _clamp(score + 5)
            excitement = _clamp(excitement + 8)
            buzz = _clamp(buzz + 5)

    # Natural regression toward 50 (modulated by market size)
    if score > 55:
        score = _clamp(int(score - 0.5 * recovery))
    elif score < 45:
        score = _clamp(int(score + 0.5 * recovery))

    # Buzz always decays toward baseline
    if buzz > 55:
        buzz = _clamp(buzz - 1)

    # Calculate attendance modifier
    att_mod = calculate_attendance_modifier_value(score)

    # Get game date
    state = query("SELECT current_date FROM game_state WHERE id=1")
    game_date = state[0]["current_date"] if state else None

    execute(
        """UPDATE fan_sentiment
           SET sentiment_score=?, excitement=?, attendance_modifier=?,
               social_media_buzz=?, last_updated=?
           WHERE team_id=?""",
        (score, excitement, att_mod, buzz, game_date, team_id)
    )

    return {
        "team_id": team_id,
        "sentiment_score": score,
        "excitement": excitement,
        "attendance_modifier": att_mod,
        "social_media_buzz": buzz,
    }


# ============================================================
# FAN REACTIONS
# ============================================================

REACTIONS = {
    "win": {
        "high": [
            "Fans are electric! The crowd is on its feet as {team} keeps rolling!",
            "Social media is BUZZING after another {team} victory. Season ticket renewals are through the roof.",
            "The energy in {stadium} is incredible. {team} fans are dreaming big.",
        ],
        "mid": [
            "A solid win for {team}. Fans are feeling good about the direction of the club.",
            "Nice win for {team}. The faithful are cautiously optimistic.",
        ],
        "low": [
            "A win is a win, but {team} fans remain skeptical. It'll take more than one game to change minds.",
            "{team} got the W, but the stands were half-empty. Winning alone won't fix the trust deficit.",
        ],
    },
    "loss": {
        "high": [
            "One loss won't dampen the spirits of {team} fans. They know this team is special.",
            "Tough loss for {team}, but the fanbase remains confident. 'We'll get 'em tomorrow' is the mood.",
        ],
        "mid": [
            "Frustration is building among {team} fans after another loss. Patience is wearing thin.",
            "Social media is grumbling after {team}'s loss. Not panic time yet, but the mood is shifting.",
        ],
        "low": [
            "Social media is melting down over this loss. {team} fans have had enough.",
            "Boos rain down at {stadium}. {team} fans are fed up, and who can blame them?",
            "Empty seats tell the story. {team} fans are voting with their feet after another defeat.",
        ],
    },
    "trade_acquisition": {
        "high": [
            "Fans are electrified after the blockbuster trade! {team} just made a statement.",
            "Season ticket sales are surging after {team}'s big acquisition. The fanbase is ALL IN.",
        ],
        "mid": [
            "Mixed reactions from {team} fans on the trade. Some love it, some want to see results first.",
        ],
        "low": [
            "Even a big trade can't save the mood. {team} fans want to see wins, not just transactions.",
        ],
    },
    "trade_away_favorite": {
        "high": [
            "The trade stings, but {team} fans trust the process. 'In the front office we trust' trending on social media.",
        ],
        "mid": [
            "Anger and sadness from {team} fans after trading away a fan favorite. The front office better be right about this one.",
            "Social media is NOT happy. {team} fans feel betrayed by the trade. Jerseys being returned at the team store.",
        ],
        "low": [
            "Fury in the fanbase. {team} fans are canceling season tickets and burning jerseys after the trade. The disconnect between ownership and fans has never been wider.",
        ],
    },
    "playoff_appearance": {
        "high": [
            "PLAYOFF BASEBALL! {team} fans are going absolutely wild. {stadium} is going to be ROCKING.",
        ],
        "mid": [
            "{team} is heading to the playoffs! Fans are cautiously excited, hoping this team can make a deep run.",
        ],
        "low": [
            "Against all odds, {team} made the playoffs. Even the doubters are starting to believe.",
        ],
    },
    "world_series_win": {
        "high": [
            "WORLD CHAMPIONS! {team} fans are celebrating in the streets! A moment for the ages!",
            "The parade route is set! {team} fans are living the dream. This city will never forget this night.",
        ],
        "mid": [
            "WORLD SERIES CHAMPIONS! {team} fans can finally exhale. Years of patience have paid off!",
        ],
        "low": [
            "THEY DID IT! Even the most cynical {team} fans are in tears of joy. World Series Champions!",
        ],
    },
    "star_fa_signing": {
        "high": [
            "BLOCKBUSTER SIGNING! {team} fans are over the moon. Jersey sales are going through the roof!",
        ],
        "mid": [
            "Big signing for {team}! Fans are optimistic, though some worry about the contract length.",
        ],
        "low": [
            "A big name, sure, but {team} fans have been burned before. 'Show me on the field' is the mood.",
        ],
    },
    "prospect_callup": {
        "high": [
            "The future is NOW! {team} fans have been waiting for this prospect call-up, and the hype is real.",
        ],
        "mid": [
            "Interesting call-up by {team}. Fans are curious to see what the kid can do at the big league level.",
        ],
        "low": [
            "Another prospect call-up. {team} fans have seen this movie before - they'll believe it when they see results.",
        ],
    },
}


def get_fan_reaction(team_id: int, event_type: str) -> str:
    """
    Returns a text reaction based on current sentiment and event type.
    """
    # Get current sentiment
    sent = query("SELECT * FROM fan_sentiment WHERE team_id=?", (team_id,))
    if not sent:
        return "The fans are watching closely."

    score = sent[0]["sentiment_score"]

    # Get team info
    team = query("SELECT city, name, stadium_name FROM teams WHERE id=?", (team_id,))
    team_name = f"{team[0]['city']} {team[0]['name']}" if team else "the team"
    stadium = team[0]["stadium_name"] if team else "the stadium"

    # Determine sentiment tier
    if score >= 70:
        tier = "high"
    elif score >= 40:
        tier = "mid"
    else:
        tier = "low"

    reactions = REACTIONS.get(event_type, {}).get(tier, [])
    if not reactions:
        # Fallback
        if score >= 70:
            return f"{team_name} fans are riding high right now."
        elif score >= 40:
            return f"{team_name} fans are in a wait-and-see mode."
        else:
            return f"Patience is running thin among {team_name} fans."

    reaction = random.choice(reactions)
    return reaction.format(team=team_name, stadium=stadium)


# ============================================================
# ATTENDANCE MODIFIER
# ============================================================

def calculate_attendance_modifier_value(sentiment_score: int) -> float:
    """Calculate attendance multiplier from sentiment score."""
    if sentiment_score > 80:
        return 1.15
    elif sentiment_score > 60:
        return 1.05
    elif sentiment_score >= 40:
        return 1.0
    elif sentiment_score >= 20:
        return 0.9
    else:
        return 0.75


def calculate_attendance_modifier(team_id: int) -> float:
    """Get attendance modifier for a team based on current sentiment."""
    sent = query("SELECT sentiment_score FROM fan_sentiment WHERE team_id=?", (team_id,))
    if not sent:
        return 1.0
    return calculate_attendance_modifier_value(sent[0]["sentiment_score"])


def get_fan_sentiment(team_id: int) -> dict:
    """Get full fan sentiment data for a team."""
    sent = query("SELECT * FROM fan_sentiment WHERE team_id=?", (team_id,))
    if not sent:
        # Initialize if missing
        initialize_fan_sentiment()
        sent = query("SELECT * FROM fan_sentiment WHERE team_id=?", (team_id,))
    if not sent:
        return {
            "team_id": team_id,
            "sentiment_score": 50,
            "excitement": 50,
            "attendance_modifier": 1.0,
            "social_media_buzz": 50,
            "last_updated": None,
        }

    result = dict(sent[0])

    # Add descriptive label
    score = result["sentiment_score"]
    if score >= 80:
        result["mood"] = "Euphoric"
        result["mood_emoji"] = "fire"
    elif score >= 65:
        result["mood"] = "Excited"
        result["mood_emoji"] = "star"
    elif score >= 50:
        result["mood"] = "Content"
        result["mood_emoji"] = "thumbsup"
    elif score >= 35:
        result["mood"] = "Restless"
        result["mood_emoji"] = "neutral"
    elif score >= 20:
        result["mood"] = "Frustrated"
        result["mood_emoji"] = "thumbsdown"
    else:
        result["mood"] = "Furious"
        result["mood_emoji"] = "anger"

    return result


# ============================================================
# MARKET SIZE EXPECTATIONS
# ============================================================

# Teams with market_size 5 expect playoffs; market_size 1 celebrates .500
MARKET_BASELINE = {
    5: 45,  # Big-market fans start slightly below neutral (expect excellence)
    4: 48,
    3: 50,  # Mid-market fans start neutral
    2: 52,
    1: 55,  # Small-market fans start slightly above neutral (more patient)
}

MARKET_WIN_EXPECTATION = {
    5: 90,   # Yankees fans expect 90+ wins
    4: 85,
    3: 81,   # .500 ball
    2: 75,
    1: 70,   # Small market fans happy with competitiveness
}


# ============================================================
# CALCULATE FAN SENTIMENT (from game state)
# ============================================================

def calculate_fan_sentiment(team_id: int, db_path: str = None) -> dict:
    """
    Calculate a 0-100 fan sentiment score from current game state.

    Factors (weighted):
      - Win/loss record (40%)
      - Recent trend (last 10 games) (15%)
      - Recent transactions (big signings +, losing favorites -) (15%)
      - Payroll relative to market (10%)
      - Star player presence (10%)
      - Playoff contention (10%)

    Market size affects the baseline expectation.

    Returns dict with sentiment_score, excitement, trust_in_gm,
    top_concern, attendance_modifier.
    """
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return {"team_id": team_id, "sentiment_score": 50}
    team = team[0]
    market_size = team.get("market_size", 3)

    state = query("SELECT season, phase, current_date FROM game_state WHERE id=1", db_path=db_path)
    if not state:
        return {"team_id": team_id, "sentiment_score": 50}
    season = state[0]["season"]
    game_date = state[0]["current_date"]

    # --- Factor 1: Win/Loss Record (40%) ---
    wins_data = query(
        """SELECT COUNT(*) as w FROM schedule
           WHERE season=? AND is_played=1
           AND ((home_team_id=? AND home_score > away_score)
             OR (away_team_id=? AND away_score > home_score))""",
        (season, team_id, team_id), db_path=db_path,
    )
    losses_data = query(
        """SELECT COUNT(*) as l FROM schedule
           WHERE season=? AND is_played=1
           AND ((home_team_id=? AND home_score < away_score)
             OR (away_team_id=? AND away_score < home_score))""",
        (season, team_id, team_id), db_path=db_path,
    )
    wins = wins_data[0]["w"] if wins_data else 0
    losses = losses_data[0]["l"] if losses_data else 0
    total_games = wins + losses

    if total_games > 0:
        win_pct = wins / total_games
        expected_wins = MARKET_WIN_EXPECTATION.get(market_size, 81)
        projected_wins = win_pct * 162
        # Score relative to market expectation
        win_delta = projected_wins - expected_wins
        record_score = _clamp(50 + int(win_delta * 1.5), 10, 95)
    else:
        record_score = MARKET_BASELINE.get(market_size, 50)

    # --- Factor 2: Recent Trend (last 10 games) (15%) ---
    recent_games = query(
        """SELECT home_team_id, away_team_id, home_score, away_score
           FROM schedule
           WHERE season=? AND is_played=1
           AND (home_team_id=? OR away_team_id=?)
           ORDER BY game_date DESC LIMIT 10""",
        (season, team_id, team_id), db_path=db_path,
    ) or []
    recent_wins = 0
    for g in recent_games:
        is_home = g["home_team_id"] == team_id
        if is_home and g["home_score"] > g["away_score"]:
            recent_wins += 1
        elif not is_home and g["away_score"] > g["home_score"]:
            recent_wins += 1
    if recent_games:
        trend_score = _clamp(int((recent_wins / len(recent_games)) * 100), 10, 95)
    else:
        trend_score = 50

    # --- Factor 3: Recent Transactions (15%) ---
    transactions = query(
        """SELECT transaction_type, details_json FROM transactions
           WHERE (team1_id=? OR team2_id=?)
           AND transaction_date >= date(?, '-30 days')""",
        (team_id, team_id, game_date), db_path=db_path,
    ) or []
    transaction_score = 50
    for txn in transactions:
        ttype = txn["transaction_type"]
        if ttype == "free_agent_signing":
            transaction_score = _clamp(transaction_score + 5)
        elif ttype == "trade":
            transaction_score = _clamp(transaction_score + 3)  # Trades can go either way
        elif ttype == "release":
            transaction_score = _clamp(transaction_score - 3)
        elif ttype == "extension":
            transaction_score = _clamp(transaction_score + 4)

    # --- Factor 4: Payroll relative to market (10%) ---
    payroll_data = query(
        """SELECT COALESCE(SUM(c.annual_salary), 0) as payroll
           FROM contracts c WHERE c.team_id=? AND c.years_remaining > 0""",
        (team_id,), db_path=db_path,
    )
    payroll = payroll_data[0]["payroll"] if payroll_data else 0
    # League average payroll ~$150M
    avg_payroll = 150_000_000
    if market_size >= 4:
        # Big-market fans expect spending
        payroll_score = _clamp(50 + int((payroll - avg_payroll * 1.2) / 5_000_000), 20, 80)
    elif market_size <= 2:
        # Small-market fans appreciate any spending
        payroll_score = _clamp(50 + int((payroll - avg_payroll * 0.6) / 3_000_000), 20, 80)
    else:
        payroll_score = _clamp(50 + int((payroll - avg_payroll) / 5_000_000), 20, 80)

    # --- Factor 5: Star Player Presence (10%) ---
    stars = query(
        """SELECT COUNT(*) as cnt FROM players
           WHERE team_id=? AND roster_status='active'
           AND (contact_rating >= 70 OR power_rating >= 70
                OR stuff_rating >= 70 OR control_rating >= 70)""",
        (team_id,), db_path=db_path,
    )
    star_count = stars[0]["cnt"] if stars else 0
    star_score = _clamp(40 + star_count * 10, 30, 90)

    # --- Factor 6: Playoff Contention (10%) ---
    if total_games >= 20:
        if win_pct >= 0.550:
            contention_score = 75
        elif win_pct >= 0.500:
            contention_score = 55
        elif win_pct >= 0.450:
            contention_score = 40
        else:
            contention_score = 25
    else:
        contention_score = 50

    # --- Weighted Composite ---
    sentiment_score = _clamp(int(
        record_score * 0.40 +
        trend_score * 0.15 +
        transaction_score * 0.15 +
        payroll_score * 0.10 +
        star_score * 0.10 +
        contention_score * 0.10
    ))

    # Determine excitement (more volatile, trend-heavy)
    excitement = _clamp(int(
        trend_score * 0.40 +
        transaction_score * 0.30 +
        contention_score * 0.30
    ))

    # Trust in GM (transaction and payroll heavy)
    trust_in_gm = _clamp(int(
        transaction_score * 0.40 +
        record_score * 0.30 +
        payroll_score * 0.30
    ))

    # Top concern
    scores = {
        "winning": record_score,
        "recent form": trend_score,
        "roster moves": transaction_score,
        "spending": payroll_score,
        "star power": star_score,
        "playoff chances": contention_score,
    }
    worst_area = min(scores, key=scores.get)
    top_concern = f"Fans are most concerned about: {worst_area}"

    att_mod = calculate_attendance_modifier_value(sentiment_score)

    return {
        "team_id": team_id,
        "sentiment_score": sentiment_score,
        "excitement": excitement,
        "trust_in_gm": trust_in_gm,
        "attendance_modifier": att_mod,
        "top_concern": top_concern,
        "game_date": game_date,
    }


def update_all_fan_sentiments(db_path: str = None) -> list:
    """
    Recalculate and store fan sentiment for all 30 teams.
    Called periodically from the sim advance loop.

    Returns list of sentiment dicts.
    """
    teams = query("SELECT id FROM teams", db_path=db_path)
    if not teams:
        return []

    # Ensure rows exist
    try:
        initialize_fan_sentiment()
    except Exception:
        pass

    results = []
    for team in teams:
        team_id = team["id"]
        sentiment = calculate_fan_sentiment(team_id, db_path)

        # Update the fan_sentiment table
        existing = query("SELECT id FROM fan_sentiment WHERE team_id=?", (team_id,), db_path=db_path)
        if existing:
            execute(
                """UPDATE fan_sentiment
                   SET sentiment_score=?, excitement=?, attendance_modifier=?,
                       trust_in_gm=?, top_concern=?, last_updated=?
                   WHERE team_id=?""",
                (
                    sentiment["sentiment_score"],
                    sentiment["excitement"],
                    sentiment["attendance_modifier"],
                    sentiment.get("trust_in_gm", 50),
                    sentiment.get("top_concern"),
                    sentiment.get("game_date"),
                    team_id,
                ),
                db_path=db_path,
            )
        else:
            execute(
                """INSERT INTO fan_sentiment
                   (team_id, sentiment_score, excitement, attendance_modifier,
                    social_media_buzz, trust_in_gm, top_concern, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    team_id,
                    sentiment["sentiment_score"],
                    sentiment["excitement"],
                    sentiment["attendance_modifier"],
                    sentiment["excitement"],  # Use excitement as initial buzz
                    sentiment.get("trust_in_gm", 50),
                    sentiment.get("top_concern"),
                    sentiment.get("game_date"),
                ),
                db_path=db_path,
            )

        results.append(sentiment)

    return results


# ============================================================
# FAN REACTION TEXT GENERATION
# ============================================================

FAN_REACTION_TEMPLATES = {
    "euphoric": [
        "\"This is OUR year! I can feel it!\" - @{team_abbr}Fan4Life",
        "\"I haven't been this excited since the last championship run. This team is SPECIAL.\"",
        "\"Just bought playoff tickets. Don't care if they're available yet. I BELIEVE.\"",
        "\"Whole city is buzzing about {team_name}. You love to see it.\"",
    ],
    "excited": [
        "\"Really liking what I see from {team_name}. Keep it up!\"",
        "\"Finally, a team worth watching! {team_name} making baseball fun again.\"",
        "\"Season ticket renewal was the easiest decision I've made all year.\"",
    ],
    "content": [
        "\"Solid team this year. Not championship caliber yet, but we're heading in the right direction.\"",
        "\"Can't complain. {team_name} are competitive and that's all I ask.\"",
        "\"Enjoying the season so far. Let's see how it plays out.\"",
    ],
    "restless": [
        "\"I'm getting a little worried about {team_name}. We need to make a move.\"",
        "\"This team needs SOMETHING. A spark. A trade. Anything.\"",
        "\"I keep waiting for {team_name} to turn it around, but patience is running out.\"",
    ],
    "frustrated": [
        "\"What is this front office DOING? {team_name} fans deserve better.\"",
        "\"I'm not spending another dollar on this team until they show me they care about winning.\"",
        "\"Embarrassing. There's no other word for what {team_name} is putting on the field.\"",
    ],
    "furious": [
        "\"SELL THE TEAM. I'm done. {team_name} ownership doesn't care about the fans.\"",
        "\"Boycott time. I'm not watching another game until something changes.\"",
        "\"This is the worst {team_name} team I've seen in my lifetime. Absolute disgrace.\"",
    ],
}


def get_fan_reactions(team_id: int, db_path: str = None) -> dict:
    """
    Generate fan reaction text based on current sentiment level.

    Returns dict with:
      - sentiment_score: 0-100
      - mood: descriptive string
      - reactions: list of 2-3 fan reaction quotes
      - top_concern: what fans care about most
      - attendance_modifier: float multiplier
    """
    sentiment = calculate_fan_sentiment(team_id, db_path)
    score = sentiment["sentiment_score"]

    # Get team info for templates
    team = query(
        "SELECT city, name, abbreviation FROM teams WHERE id=?",
        (team_id,), db_path=db_path,
    )
    if team:
        team_name = f"{team[0]['city']} {team[0]['name']}"
        team_abbr = team[0]["abbreviation"]
    else:
        team_name = "the team"
        team_abbr = "MLB"

    # Determine mood tier
    if score >= 80:
        mood = "Euphoric"
        tier = "euphoric"
    elif score >= 65:
        mood = "Excited"
        tier = "excited"
    elif score >= 50:
        mood = "Content"
        tier = "content"
    elif score >= 35:
        mood = "Restless"
        tier = "restless"
    elif score >= 20:
        mood = "Frustrated"
        tier = "frustrated"
    else:
        mood = "Furious"
        tier = "furious"

    templates = FAN_REACTION_TEMPLATES.get(tier, FAN_REACTION_TEMPLATES["content"])
    num_reactions = min(random.randint(2, 3), len(templates))
    selected = random.sample(templates, num_reactions)
    reactions = [t.format(team_name=team_name, team_abbr=team_abbr) for t in selected]

    return {
        "team_id": team_id,
        "sentiment_score": score,
        "mood": mood,
        "reactions": reactions,
        "top_concern": sentiment.get("top_concern", ""),
        "attendance_modifier": sentiment["attendance_modifier"],
        "excitement": sentiment["excitement"],
        "trust_in_gm": sentiment.get("trust_in_gm", 50),
    }
