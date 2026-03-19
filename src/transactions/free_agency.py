"""
Front Office - Free Agency System
Handles free agent market, signings, and contract negotiations.

Features:
- Tiered bidding wars (Elite/Good/Average/Depth)
- Age-adjusted and position-adjusted market values
- Recent performance adjustments
- Qualifying offer tracking and draft pick compensation
"""
import json
import random
from datetime import datetime
from ..database.db import get_connection, query, execute


# In-memory tracking for bidding wars during offseason
# Structure: {player_id: {
#     "tier": str,                  # Elite/Good/Average/Depth
#     "interested_teams": [int],    # team IDs still bidding
#     "offers": {team_id: {"salary": int, "years": int, "day_offered": int}},
#     "days_on_market": int,
#     "asking_salary": int,
#     "asking_years": int,
#     "qo_status": str|None,       # "extended", "accepted", "rejected", None
#     "original_team_id": int|None, # team that extended QO (for comp picks)
# }}
_best_offers = {}


# Qualifying offer value ($21M one-year deal)
QO_VALUE = 21_000_000
QO_WAR_THRESHOLD = 2.5


def get_free_agents(db_path: str = None) -> list:
    """Get all available free agents with their asking prices."""
    players = query("""
        SELECT p.*, c.annual_salary as last_salary
        FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.roster_status = 'free_agent'
        ORDER BY p.contact_rating + p.power_rating + p.stuff_rating DESC
    """, db_path=db_path)

    result = []
    for p in players:
        # Calculate asking price based on ratings, age, position
        value = _calculate_market_value(p, db_path=db_path)
        bidding = _best_offers.get(p["id"], {})
        best_offer = None
        if bidding.get("offers"):
            # Find highest current offer
            best_tid = max(bidding["offers"], key=lambda t: bidding["offers"][t]["salary"])
            best_offer = {
                "team_id": best_tid,
                "salary": bidding["offers"][best_tid]["salary"],
                "years": bidding["offers"][best_tid]["years"],
                "date": bidding["offers"][best_tid].get("day_offered", 0),
            }
        # Non-money preferences for this player (what they value beyond salary)
        prefs = get_player_fa_preferences(p["id"], db_path=db_path)

        result.append({
            **p,
            "asking_salary": value["salary"],
            "asking_years": value["years"],
            "market_interest": value["interest"],
            "tier": value["tier"],
            "best_offer": best_offer,
            "qo_status": bidding.get("qo_status"),
            "non_money_preferences": {
                "money_weight": prefs.get("money_weight", 0.65),
                "non_money_weight": prefs.get("non_money_weight", 0.35),
                "personality_summary": prefs.get("personality_summary", []),
                "top_factor": prefs.get("top_factor", "Playing Time"),
                "factor_weights": prefs.get("factor_weights", {}),
            },
        })
    return result


def _calculate_overall(player: dict) -> float:
    """Calculate a player's overall rating from component ratings."""
    is_pitcher = player["position"] in ("SP", "RP")
    if is_pitcher:
        overall = (player["stuff_rating"] * 2 + player["control_rating"] * 1.5 +
                   player["stamina_rating"] * 0.5) / 4
    else:
        overall = (player["contact_rating"] * 1.5 + player["power_rating"] * 1.5 +
                   player["speed_rating"] * 0.5 + player["fielding_rating"] * 0.5) / 4
    return overall


def _get_player_tier(overall: float) -> str:
    """Classify a player into a market tier based on overall rating."""
    if overall >= 70:
        return "Elite"
    elif overall >= 60:
        return "Good"
    elif overall >= 50:
        return "Average"
    else:
        return "Depth"


def _calculate_market_value(player: dict, db_path: str = None) -> dict:
    """
    Estimate a player's market value for free agency.

    Includes adjustments for:
    - Age (years and salary multipliers)
    - Position premiums/discounts
    - Recent performance (stats vs ratings)
    """
    overall = _calculate_overall(player)
    tier = _get_player_tier(overall)
    age = player["age"]
    position = player["position"]

    # --- Base salary and years from overall rating ---
    if overall >= 70:
        base_salary = int(random.uniform(22_000_000, 35_000_000))
        base_years = random.randint(4, 7)
    elif overall >= 60:
        base_salary = int(random.uniform(12_000_000, 22_000_000))
        base_years = random.randint(3, 5)
    elif overall >= 50:
        base_salary = int(random.uniform(4_000_000, 12_000_000))
        base_years = random.randint(2, 4)
    elif overall >= 40:
        base_salary = int(random.uniform(1_500_000, 5_000_000))
        base_years = random.randint(1, 3)
    else:
        base_salary = int(random.uniform(750_000, 2_000_000))
        base_years = 1

    # --- Age adjustment ---
    if 26 <= age <= 29:
        age_salary_mult = 1.0
        age_years_mult = 1.0
    elif 30 <= age <= 31:
        age_salary_mult = 1.0
        age_years_mult = 0.85
    elif 32 <= age <= 33:
        age_salary_mult = 0.9
        age_years_mult = 0.7
    elif age >= 34:
        age_salary_mult = 0.75
        age_years_mult = 0.5
    else:
        # Young (< 26) - shouldn't be common in FA, but handle it
        age_salary_mult = 1.1
        age_years_mult = 1.1

    # --- Position adjustment ---
    if position == "SP":
        pos_salary_mult = 1.15
        pos_years_mult = 1.0
    elif position == "RP":
        pos_salary_mult = 0.8
        pos_years_mult = 0.75  # shorter deals for relievers
    elif position == "C":
        pos_salary_mult = 0.9
        pos_years_mult = 1.0
    elif position == "DH":
        pos_salary_mult = 0.85
        pos_years_mult = 1.0
    else:
        pos_salary_mult = 1.0
        pos_years_mult = 1.0

    # --- Recent performance adjustment ---
    perf_mult = 1.0
    if db_path is not None:
        perf_mult = _get_performance_adjustment(player, db_path)

    # --- Personality adjustment (greed & ego) ---
    greed = player.get("greed", 50) or 50
    ego = player.get("ego", 50) or 50

    # Greed affects salary demands
    if greed > 70:
        # Greedy players demand 10-25% more (scaled linearly from 70-100)
        greed_salary_mult = 1.10 + (greed - 70) / 30 * 0.15
    elif greed < 40:
        # Generous/team-friendly players accept 5-15% less (scaled from 40-0)
        greed_salary_mult = 0.95 - (40 - greed) / 40 * 0.10
    else:
        greed_salary_mult = 1.0

    # High ego demands longer contracts (players want commitment / respect)
    if ego > 70:
        ego_years_bonus = 1 if ego > 85 else (1 if random.random() < 0.5 else 0)
    else:
        ego_years_bonus = 0

    # --- Compute final values ---
    salary = int(base_salary * age_salary_mult * pos_salary_mult * perf_mult * greed_salary_mult)
    years = max(1, int(base_years * age_years_mult * pos_years_mult) + ego_years_bonus)

    # Cap years for old players
    if age >= 34:
        years = min(years, 2)

    # Market interest based on tier
    if tier == "Elite":
        interest = random.randint(3, 6)
    elif tier == "Good":
        interest = random.randint(2, 4)
    elif tier == "Average":
        interest = random.randint(1, 2)
    else:
        interest = random.randint(0, 1)

    return {"salary": salary, "years": years, "interest": interest, "tier": tier}


def _get_performance_adjustment(player: dict, db_path: str) -> float:
    """
    Check recent season stats vs ratings. If player significantly
    underperformed their ratings, reduce market value by 10-20%.
    """
    try:
        is_pitcher = player["position"] in ("SP", "RP")

        if is_pitcher:
            stats = query("""
                SELECT ip_outs, er, bb, so, games
                FROM pitching_stats
                WHERE player_id = ? AND level = 'MLB'
                ORDER BY season DESC LIMIT 1
            """, (player["id"],), db_path=db_path)

            if not stats or stats[0]["games"] < 10:
                return 1.0

            s = stats[0]
            ip = s["ip_outs"] / 3.0
            if ip < 20:
                return 1.0

            era = (s["er"] / ip) * 9.0
            # Expected ERA from ratings: lower stuff/control = higher ERA
            expected_era = max(2.0, 6.5 - (player["stuff_rating"] + player["control_rating"]) / 25)

            if era > expected_era + 1.5:
                return random.uniform(0.80, 0.90)  # Bad year: 10-20% reduction
            elif era > expected_era + 0.75:
                return random.uniform(0.90, 0.95)  # Slightly below expectations
        else:
            stats = query("""
                SELECT hits, ab, hr, bb, so, games
                FROM batting_stats
                WHERE player_id = ? AND level = 'MLB'
                ORDER BY season DESC LIMIT 1
            """, (player["id"],), db_path=db_path)

            if not stats or stats[0]["games"] < 30:
                return 1.0

            s = stats[0]
            if s["ab"] < 100:
                return 1.0

            avg = s["hits"] / s["ab"]
            # Expected AVG from ratings
            expected_avg = 0.200 + (player["contact_rating"] / 200)

            if avg < expected_avg - 0.040:
                return random.uniform(0.80, 0.90)
            elif avg < expected_avg - 0.020:
                return random.uniform(0.90, 0.95)

    except Exception:
        pass

    return 1.0


def _approximate_war(player: dict) -> float:
    """
    Quick WAR approximation from ratings for QO eligibility.
    Not a real WAR calculation, just a rough proxy.
    """
    overall = _calculate_overall(player)
    # Map overall rating to approximate WAR:
    # 80 overall ~ 6 WAR, 70 ~ 4 WAR, 60 ~ 2.5 WAR, 50 ~ 1.5 WAR, 40 ~ 0.5 WAR
    if overall >= 70:
        war = 3.0 + (overall - 70) * 0.3
    elif overall >= 60:
        war = 1.5 + (overall - 60) * 0.15
    elif overall >= 50:
        war = 0.5 + (overall - 50) * 0.1
    else:
        war = max(0, (overall - 30) * 0.025)

    # Age penalty
    age = player.get("age", 27)
    if age >= 34:
        war *= 0.7
    elif age >= 32:
        war *= 0.85

    return round(war, 1)


def sign_free_agent(player_id: int, team_id: int, salary: int, years: int,
                    db_path: str = None) -> dict:
    """Sign a free agent to a contract. Handles QO draft pick compensation."""
    conn = get_connection(db_path)

    player = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player:
        conn.close()
        return {"error": "Player not found"}
    if player["roster_status"] != "free_agent":
        conn.close()
        return {"error": "Player is not a free agent"}

    # Check team can afford it
    team = conn.execute("SELECT cash FROM teams WHERE id=?", (team_id,)).fetchone()
    if not team:
        conn.close()
        return {"error": "Team not found"}

    # Check 40-man roster limit
    forty_man_count = conn.execute("""
        SELECT COUNT(*) as c FROM players
        WHERE team_id=? AND on_forty_man=1
    """, (team_id,)).fetchone()["c"]

    if forty_man_count >= 40:
        conn.close()
        return {"error": "40-man roster is full (40 players). Remove someone from the 40-man first."}

    # Update player
    conn.execute("""
        UPDATE players SET team_id=?, roster_status='active', on_forty_man=1
        WHERE id=?
    """, (team_id, player_id))

    # Create contract
    state = conn.execute("SELECT * FROM game_state WHERE id=1").fetchone()
    game_date = state["current_date"] if state else "2025-01-01"

    conn.execute("""
        INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
            annual_salary, signed_date)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (player_id, team_id, years, years, salary, game_date))

    details = {"salary": salary, "years": years}

    # --- QO draft pick compensation ---
    bidding = _best_offers.get(player_id, {})
    if bidding.get("qo_status") == "rejected" and bidding.get("original_team_id"):
        original_team_id = bidding["original_team_id"]
        details["qo_compensation"] = True
        details["original_team_id"] = original_team_id

        # Original team receives compensation draft pick (after round 1)
        season_row = conn.execute("SELECT season FROM game_state WHERE id=1").fetchone()
        comp_season = (season_row["season"] if season_row else 2025) + 1

        # Find next available comp pick number after round 1
        existing_comp = conn.execute("""
            SELECT MAX(pick_number) as max_pick FROM draft_pick_ownership
            WHERE season=? AND round=1
        """, (comp_season,)).fetchone()
        next_pick = (existing_comp["max_pick"] or 30) + 1

        conn.execute("""
            INSERT INTO draft_pick_ownership
            (season, round, pick_number, original_team_id, current_owner_team_id, traded_date)
            VALUES (?, 1, ?, ?, ?, NULL)
        """, (comp_season, next_pick, original_team_id, original_team_id))

        details["comp_pick"] = {"team_id": original_team_id, "round": 1, "pick": next_pick}

        # Signing team loses a draft pick (3rd round by default)
        lost_round = 3
        conn.execute("""
            DELETE FROM draft_pick_ownership
            WHERE season=? AND round=? AND current_owner_team_id=?
            AND id = (
                SELECT id FROM draft_pick_ownership
                WHERE season=? AND round=? AND current_owner_team_id=?
                ORDER BY pick_number ASC LIMIT 1
            )
        """, (comp_season, lost_round, team_id,
              comp_season, lost_round, team_id))

        details["pick_lost"] = {"team_id": team_id, "round": lost_round}

    # Log transaction
    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'free_agent_signing', ?, ?, ?)
    """, (game_date, json.dumps(details), team_id, str(player_id)))

    # Send notification if signing team is the user's team
    state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
    user_team_id = state["user_team_id"] if state else None
    if team_id == user_team_id:
        from .messages import send_free_agent_signing_message
        team_row = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()
        team_name = f"{team_row['city']} {team_row['name']}" if team_row else "Unknown"
        player_name = f"{player['first_name']} {player['last_name']}"
        send_free_agent_signing_message(user_team_id, player_name, team_name, salary, db_path=db_path)

    # Clear bidding state
    _best_offers.pop(player_id, None)

    conn.commit()
    conn.close()
    return {"success": True, "player_id": player_id, "team_id": team_id,
            "salary": salary, "years": years, "details": details}


def _calculate_non_money_attraction(player: dict, team_id: int, conn,
                                    db_path: str = None) -> float:
    """
    Calculate non-money attraction factors for a free agent toward a team.
    Returns a modifier between -0.30 and +0.40 that adjusts signing probability.

    Factors:
    - Playing time: penalty if team already has a star at the position
    - Friends on team: bonus for existing friendships
    - Team chemistry: high-chemistry teams are more attractive
    - Winning: teams with winning records attract FAs
    - Market size: big-market teams get a small bonus
    - Loyalty: players with high loyalty prefer re-signing with previous team
    """
    modifier = 0.0
    position = player.get("position", "")
    player_id = player["id"]

    # Personality traits that modify factor weights
    greed = player.get("greed", 50) or 50
    ego = player.get("ego", 50) or 50       # "ambition" — favors contenders/big markets
    sociability = player.get("sociability", 50) or 50
    loyalty = player.get("loyalty", 50) or 50

    # Personality-based weight multipliers (each factor scaled by relevant trait)
    # Sociability amplifies friends factor: 0.5x at sociability=0, 1.5x at sociability=100
    friends_weight = 0.5 + sociability / 100.0
    # Ego/ambition amplifies contender + market factors: 0.6x at ego=0, 1.4x at ego=100
    ambition_weight = 0.6 + ego * 0.008
    # High greed reduces all non-money factors (handled in the combined scoring, but
    # also slightly dampens the modifier here)
    greed_dampening = 1.0 - (max(0, greed - 50) / 200.0)  # 1.0 at greed=50, 0.75 at greed=100

    # --- Playing time: check if team has a high-rated player at same position ---
    try:
        incumbent = conn.execute("""
            SELECT contact_rating, power_rating, stuff_rating, control_rating,
                   speed_rating, fielding_rating, position
            FROM players
            WHERE team_id = ? AND position = ? AND roster_status = 'active'
            ORDER BY (contact_rating + power_rating + stuff_rating + control_rating) DESC
            LIMIT 1
        """, (team_id, position)).fetchone()

        if incumbent:
            inc_dict = dict(incumbent)
            inc_overall = _calculate_overall(inc_dict)
            player_overall = _calculate_overall(player)
            if inc_overall >= 65 and inc_overall >= player_overall:
                # Star incumbent — reduced playing time likelihood
                modifier -= random.uniform(0.10, 0.20)
    except Exception:
        pass

    # --- Friends on team (amplified by sociability) ---
    try:
        friend_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM player_relationships pr
            JOIN players p ON (
                (pr.player_id_1 = ? AND pr.player_id_2 = p.id) OR
                (pr.player_id_2 = ? AND pr.player_id_1 = p.id)
            )
            WHERE pr.relationship_type = 'friend'
            AND p.team_id = ?
        """, (player_id, player_id, team_id)).fetchone()["cnt"]
        if friend_count > 0:
            # Base 10-15% bonus, capped at 3 friends, scaled by sociability
            base_friend_bonus = min(friend_count, 3) * random.uniform(0.033, 0.05)
            modifier += base_friend_bonus * friends_weight
    except Exception:
        pass

    # --- Team chemistry ---
    try:
        from ..simulation.chemistry import calculate_team_chemistry
        chem = calculate_team_chemistry(team_id, db_path=db_path)
        team_chem = chem if isinstance(chem, (int, float)) else (
            chem.get("overall", 50) if isinstance(chem, dict) else 50
        )
        if team_chem > 70:
            modifier += random.uniform(0.05, 0.10)
        elif team_chem < 30:
            modifier -= random.uniform(0.03, 0.07)
    except Exception:
        pass

    # --- Winning record / contender status (amplified by ambition/ego) ---
    try:
        record = conn.execute(
            "SELECT wins, losses FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        if record:
            total_games = (record["wins"] or 0) + (record["losses"] or 0)
            if total_games > 0:
                win_pct = record["wins"] / total_games
                if win_pct >= 0.550:
                    modifier += random.uniform(0.05, 0.10) * ambition_weight
                elif win_pct < 0.400:
                    modifier -= random.uniform(0.03, 0.07) * ambition_weight
    except Exception:
        pass

    # --- Market size (amplified by ambition/ego) ---
    try:
        team_info = conn.execute(
            "SELECT market_size FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        if team_info:
            mkt = team_info["market_size"] or 3
            if mkt >= 5:
                modifier += random.uniform(0.03, 0.06) * ambition_weight
            elif mkt >= 4:
                modifier += random.uniform(0.01, 0.03) * ambition_weight
            elif mkt <= 1:
                modifier -= random.uniform(0.01, 0.03) * ambition_weight
    except Exception:
        pass

    # --- Loyalty: prefer re-signing with previous team ---
    try:
        if loyalty > 60:
            # Check if this team was the player's most recent team
            prev_contract = conn.execute("""
                SELECT team_id FROM contracts
                WHERE player_id = ?
                ORDER BY signed_date DESC LIMIT 1
            """, (player_id,)).fetchone()
            if prev_contract and prev_contract["team_id"] == team_id:
                # Loyalty bonus: up to 15% for very loyal players
                loyalty_bonus = 0.15 * ((loyalty - 60) / 40)
                modifier += max(0.05, loyalty_bonus)
    except Exception:
        pass

    # Apply greed dampening — greedy players care less about non-money factors
    modifier *= greed_dampening

    return max(-0.30, min(0.40, modifier))


def calculate_non_money_score(player_id: int, team_id: int, db_path: str = None) -> dict:
    """
    Calculate a non-money attraction score (0-100) for a free agent toward a team.

    Breaks down into weighted components:
    - Playing Time (30%): Will this team start the player?
    - Friends on Team (20%): player_relationships friends on this team
    - Clubhouse/Chemistry (15%): Team chemistry score
    - Contender Status (25%): Team win/loss record and playoff chances
    - Market Size (10%): Big market exposure advantage

    Personality modifiers adjust component weights:
    - High sociability increases Friends weight
    - High ego/ambition increases Contender + Market weight
    - High loyalty adds bonus for previous team
    - High greed reduces overall non-money influence (reflected in money_weight)

    Returns dict with:
    - score: 0-100 overall non-money score
    - components: breakdown of each factor's contribution
    - money_weight: how much this player weights money vs non-money (greed-based)
    - top_factors: ordered list of what this player values most
    """
    conn = get_connection(db_path)

    player_row = conn.execute("SELECT * FROM players WHERE id=?", (player_id,)).fetchone()
    if not player_row:
        conn.close()
        return {"score": 50, "components": {}, "money_weight": 0.65, "top_factors": []}

    player = dict(player_row)
    position = player.get("position", "")

    # Personality traits
    greed = player.get("greed", 50) or 50
    ego = player.get("ego", 50) or 50
    sociability = player.get("sociability", 50) or 50
    loyalty = player.get("loyalty", 50) or 50

    # --- Playing Time (0-100) ---
    playing_time_score = 70  # default: decent chance
    try:
        incumbent = conn.execute("""
            SELECT contact_rating, power_rating, stuff_rating, control_rating,
                   speed_rating, fielding_rating, position
            FROM players
            WHERE team_id = ? AND position = ? AND roster_status = 'active'
            ORDER BY (contact_rating + power_rating + stuff_rating + control_rating) DESC
            LIMIT 1
        """, (team_id, position)).fetchone()

        if incumbent:
            inc_dict = dict(incumbent)
            inc_overall = _calculate_overall(inc_dict)
            player_overall = _calculate_overall(player)
            if inc_overall >= player_overall + 10:
                playing_time_score = 20  # clear backup role
            elif inc_overall >= player_overall:
                playing_time_score = 40  # platoon/competition
            elif player_overall > inc_overall + 5:
                playing_time_score = 90  # clear starter
            else:
                playing_time_score = 65  # slight edge
        else:
            playing_time_score = 95  # no incumbent, guaranteed starter
    except Exception:
        pass

    # --- Friends on Team (0-100) ---
    friends_score = 30  # baseline: no friends
    try:
        friend_count = conn.execute("""
            SELECT COUNT(*) as cnt FROM player_relationships pr
            JOIN players p ON (
                (pr.player_id_1 = ? AND pr.player_id_2 = p.id) OR
                (pr.player_id_2 = ? AND pr.player_id_1 = p.id)
            )
            WHERE pr.relationship_type = 'friend'
            AND p.team_id = ?
        """, (player_id, player_id, team_id)).fetchone()["cnt"]
        if friend_count >= 3:
            friends_score = 90
        elif friend_count == 2:
            friends_score = 75
        elif friend_count == 1:
            friends_score = 55
    except Exception:
        pass

    # --- Clubhouse / Chemistry (0-100) ---
    chemistry_score = 50
    try:
        from ..simulation.chemistry import calculate_team_chemistry
        chem = calculate_team_chemistry(team_id, db_path=db_path)
        team_chem = chem if isinstance(chem, (int, float)) else (
            chem.get("overall", 50) if isinstance(chem, dict) else 50
        )
        chemistry_score = max(0, min(100, int(team_chem)))
    except Exception:
        pass

    # --- Contender Status (0-100) ---
    contender_score = 50
    try:
        record = conn.execute(
            "SELECT wins, losses FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        if record:
            total_games = (record["wins"] or 0) + (record["losses"] or 0)
            if total_games > 0:
                win_pct = record["wins"] / total_games
                # Map win% to 0-100: .400 = 20, .500 = 50, .600 = 80, .650+ = 95
                contender_score = max(0, min(100, int((win_pct - 0.300) * 250)))
    except Exception:
        pass

    # --- Market Size (0-100) ---
    market_score = 50
    try:
        team_info = conn.execute(
            "SELECT market_size FROM teams WHERE id = ?", (team_id,)
        ).fetchone()
        if team_info:
            mkt = team_info["market_size"] or 3
            market_score = max(0, min(100, mkt * 20))  # 1->20, 3->60, 5->100
    except Exception:
        pass

    # --- Loyalty bonus (adds to score if this was player's previous team) ---
    loyalty_bonus = 0
    try:
        if loyalty > 50:
            prev_contract = conn.execute("""
                SELECT team_id FROM contracts
                WHERE player_id = ?
                ORDER BY signed_date DESC LIMIT 1
            """, (player_id,)).fetchone()
            if prev_contract and prev_contract["team_id"] == team_id:
                loyalty_bonus = int((loyalty - 50) * 0.3)  # up to +15
    except Exception:
        pass

    conn.close()

    # --- Personality-adjusted weights ---
    # Base weights: playing_time=30, friends=20, chemistry=15, contender=25, market=10
    w_playing_time = 30
    w_friends = 20 * (0.5 + sociability / 100.0)       # 10-30 based on sociability
    w_contender = 25 * (0.6 + ego * 0.008)              # 15-35 based on ego/ambition
    w_market = 10 * (0.6 + ego * 0.008)                  # 6-14 based on ego/ambition
    w_chemistry = 15

    # Normalize weights to sum to 100
    total_w = w_playing_time + w_friends + w_chemistry + w_contender + w_market
    w_playing_time = w_playing_time / total_w * 100
    w_friends = w_friends / total_w * 100
    w_chemistry = w_chemistry / total_w * 100
    w_contender = w_contender / total_w * 100
    w_market = w_market / total_w * 100

    # Weighted score
    score = (
        playing_time_score * w_playing_time / 100 +
        friends_score * w_friends / 100 +
        chemistry_score * w_chemistry / 100 +
        contender_score * w_contender / 100 +
        market_score * w_market / 100 +
        loyalty_bonus
    )
    score = max(0, min(100, int(score)))

    # Money weight based on greed: high greed = 0.80, low greed = 0.50
    money_weight = 0.50 + (greed / 100.0) * 0.30  # 0.50 at greed=0, 0.80 at greed=100

    components = {
        "playing_time": {"score": playing_time_score, "weight": round(w_playing_time, 1)},
        "friends": {"score": friends_score, "weight": round(w_friends, 1)},
        "chemistry": {"score": chemistry_score, "weight": round(w_chemistry, 1)},
        "contender": {"score": contender_score, "weight": round(w_contender, 1)},
        "market_size": {"score": market_score, "weight": round(w_market, 1)},
    }
    if loyalty_bonus > 0:
        components["loyalty_bonus"] = {"score": loyalty_bonus, "weight": 0}

    # Top factors — what this player cares most about (sorted by effective weight)
    factor_labels = {
        "playing_time": "Playing Time",
        "friends": "Friends on Team",
        "chemistry": "Clubhouse Atmosphere",
        "contender": "Winning / Contender",
        "market_size": "Big Market / Exposure",
    }
    top_factors = sorted(
        [(k, components[k]["weight"]) for k in factor_labels],
        key=lambda x: x[1],
        reverse=True,
    )
    top_factors = [
        {"factor": factor_labels[k], "weight": w}
        for k, w in top_factors
    ]

    return {
        "score": score,
        "components": components,
        "money_weight": round(money_weight, 2),
        "non_money_weight": round(1.0 - money_weight, 2),
        "top_factors": top_factors,
    }


def get_player_fa_preferences(player_id: int, db_path: str = None) -> dict:
    """
    Get a free agent's non-money preferences for scouting reports / FA listings.

    Shows what factors this player values most so the user can understand
    which teams might appeal to them beyond salary.

    Returns dict with personality summary, factor weights, and advice text.
    """
    player_rows = query(
        "SELECT * FROM players WHERE id=?", (player_id,), db_path=db_path
    )
    if not player_rows:
        return {"error": "Player not found"}

    player = player_rows[0]
    greed = player.get("greed", 50) or 50
    ego = player.get("ego", 50) or 50
    sociability = player.get("sociability", 50) or 50
    loyalty = player.get("loyalty", 50) or 50

    # Money weight
    money_weight = 0.50 + (greed / 100.0) * 0.30

    # Describe personality tendencies
    traits = []
    if greed >= 70:
        traits.append("Motivated primarily by money")
    elif greed <= 30:
        traits.append("Willing to take a discount for the right fit")

    if ego >= 70:
        traits.append("Drawn to contenders and big markets")
    elif ego <= 30:
        traits.append("Content with a quiet role on any team")

    if sociability >= 70:
        traits.append("Values having friends on the team")
    elif sociability <= 30:
        traits.append("Prefers to keep to himself")

    if loyalty >= 70:
        traits.append("Strongly prefers staying with his current team")
    elif loyalty <= 30:
        traits.append("No attachment to any particular team")

    if not traits:
        traits.append("Balanced — weighs money and fit equally")

    # Build factor weight summary
    w_friends = 20 * (0.5 + sociability / 100.0)
    w_contender = 25 * (0.6 + ego * 0.008)
    w_market = 10 * (0.6 + ego * 0.008)
    w_playing_time = 30
    w_chemistry = 15
    total_w = w_playing_time + w_friends + w_chemistry + w_contender + w_market

    factor_weights = {
        "Playing Time": round(w_playing_time / total_w * 100, 1),
        "Friends on Team": round(w_friends / total_w * 100, 1),
        "Clubhouse Atmosphere": round(w_chemistry / total_w * 100, 1),
        "Winning / Contender": round(w_contender / total_w * 100, 1),
        "Big Market / Exposure": round(w_market / total_w * 100, 1),
    }

    # Sort by weight descending
    sorted_factors = sorted(factor_weights.items(), key=lambda x: x[1], reverse=True)

    return {
        "player_id": player_id,
        "player_name": f"{player['first_name']} {player['last_name']}",
        "money_weight": round(money_weight, 2),
        "non_money_weight": round(1.0 - money_weight, 2),
        "personality_summary": traits,
        "factor_weights": dict(sorted_factors),
        "top_factor": sorted_factors[0][0] if sorted_factors else "Playing Time",
        "greed": greed,
        "ego": ego,
        "sociability": sociability,
        "loyalty": loyalty,
    }


def _initialize_bidding(fa: dict, offseason_day: int, db_path: str = None) -> dict:
    """Set up initial bidding state for a free agent if not already tracked."""
    player_id = fa["id"]
    if player_id in _best_offers:
        return _best_offers[player_id]

    market_value = _calculate_market_value(dict(fa), db_path=db_path)

    bidding = {
        "tier": market_value["tier"],
        "interested_teams": [],
        "offers": {},
        "days_on_market": 0,
        "asking_salary": market_value["salary"],
        "asking_years": market_value["years"],
        "qo_status": None,
        "original_team_id": None,
    }
    _best_offers[player_id] = bidding
    return bidding


def process_free_agency_day(game_date: str, offseason_day: int = 0,
                            db_path: str = None) -> list:
    """
    Process one day of AI free agency activity during offseason.

    Implements tiered bidding wars:
    - Elite: 3-6 teams interested, competitive bidding
    - Good: 2-4 teams interested
    - Average: 1-2 teams
    - Depth: 0-1 teams

    Returns list of signings and offers made.
    """
    conn = get_connection(db_path)
    events = []

    state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
    user_team_id = state["user_team_id"] if state else None

    # Get all free agents
    free_agents = conn.execute("""
        SELECT p.* FROM players p
        WHERE p.roster_status = 'free_agent'
    """).fetchall()

    if not free_agents:
        conn.close()
        return events

    # Get AI teams with budget info
    teams = conn.execute("""
        SELECT t.id, t.cash, oc.budget_willingness
        FROM teams t
        LEFT JOIN owner_characters oc ON oc.team_id = t.id
        WHERE t.id != ?
    """, (user_team_id or -1,)).fetchall()

    teams_list = [dict(t) for t in teams]

    for fa in free_agents:
        fa_dict = dict(fa)
        player_id = fa["id"]
        bidding = _initialize_bidding(fa_dict, offseason_day, db_path)
        bidding["days_on_market"] += 1

        # Apply asking price drops based on days on market
        effective_asking = bidding["asking_salary"]
        if offseason_day > 60:
            effective_asking = int(effective_asking * 0.70)
        elif offseason_day > 30:
            effective_asking = int(effective_asking * 0.90)

        tier = bidding["tier"]

        # --- Phase 1: Recruit interested teams if not enough ---
        target_interest = {
            "Elite": random.randint(3, 6),
            "Good": random.randint(2, 4),
            "Average": random.randint(1, 2),
            "Depth": random.randint(0, 1),
        }.get(tier, 1)

        if len(bidding["interested_teams"]) < target_interest:
            # Try to recruit new interested teams
            random.shuffle(teams_list)
            for team in teams_list:
                if len(bidding["interested_teams"]) >= target_interest:
                    break
                if team["id"] in bidding["interested_teams"]:
                    continue

                # Check 40-man space
                forty_man = conn.execute("""
                    SELECT COUNT(*) as c FROM players
                    WHERE team_id=? AND on_forty_man=1
                """, (team["id"],)).fetchone()["c"]
                if forty_man >= 40:
                    continue

                # Check budget
                budget_mult = (team["budget_willingness"] or 50) / 100
                max_budget = int(team["cash"] * 0.15 * budget_mult)
                if effective_asking > max_budget:
                    continue

                # Check team need at this position
                from ..ai.gm_brain import _get_team_needs
                needs = _get_team_needs(team["id"], db_path)
                pos_strength = needs.get(fa["position"], 200)

                # More likely to be interested if position is weak
                if pos_strength >= 200 and random.random() > 0.30:
                    continue

                bidding["interested_teams"].append(team["id"])

        # --- Phase 2: Interested teams make or raise offers ---
        for team_id in list(bidding["interested_teams"]):
            team_row = next((t for t in teams_list if t["id"] == team_id), None)
            if not team_row:
                continue

            budget_mult = (team_row["budget_willingness"] or 50) / 100
            max_budget = int(team_row["cash"] * 0.15 * budget_mult)

            existing_offer = bidding["offers"].get(team_id)

            if existing_offer is None:
                # Initial offer: 80-100% of asking
                offer_salary = int(effective_asking * random.uniform(0.80, 1.00))
                offer_years = bidding["asking_years"]

                if offer_salary > max_budget:
                    # Can't afford, drop out
                    bidding["interested_teams"].remove(team_id)
                    continue

                bidding["offers"][team_id] = {
                    "salary": offer_salary,
                    "years": offer_years,
                    "day_offered": offseason_day,
                }

                events.append({
                    "type": "offer",
                    "player_id": player_id,
                    "player_name": f"{fa['first_name']} {fa['last_name']}",
                    "team_id": team_id,
                    "salary": offer_salary,
                    "years": offer_years,
                })

            elif len(bidding["offers"]) > 1:
                # Multiple offers exist — bidding war, raise by 5-15%
                current_max = max(o["salary"] for o in bidding["offers"].values())

                if existing_offer["salary"] < current_max:
                    # Need to raise to stay competitive
                    raise_pct = random.uniform(1.05, 1.15)
                    new_salary = int(existing_offer["salary"] * raise_pct)

                    if new_salary > max_budget:
                        # Drop out of bidding
                        bidding["interested_teams"].remove(team_id)
                        del bidding["offers"][team_id]
                        events.append({
                            "type": "dropped_out",
                            "player_id": player_id,
                            "player_name": f"{fa['first_name']} {fa['last_name']}",
                            "team_id": team_id,
                        })
                        continue

                    bidding["offers"][team_id]["salary"] = new_salary
                    bidding["offers"][team_id]["day_offered"] = offseason_day

                    events.append({
                        "type": "offer_raised",
                        "player_id": player_id,
                        "player_name": f"{fa['first_name']} {fa['last_name']}",
                        "team_id": team_id,
                        "salary": new_salary,
                        "years": existing_offer["years"],
                    })

        # --- Phase 3: Check if player should sign (with non-money factors) ---
        if not bidding["offers"]:
            continue

        # Score each offer using greed-based money_weight.
        # High greed (100) = money_weight 0.80, low greed (0) = money_weight 0.50
        # This means a non-greedy player might choose a lower offer from a
        # contender with friends over top dollar from a rebuilding team.
        fa_greed = fa_dict.get("greed", 50) or 50
        money_weight = 0.50 + (fa_greed / 100.0) * 0.30
        non_money_weight = 1.0 - money_weight

        offer_scores = {}
        offer_attractions = {}
        for tid, offer in bidding["offers"].items():
            # Salary score: normalized to asking price
            salary_score = offer["salary"] / max(1, effective_asking)
            # Non-money factors for this team
            attraction = _calculate_non_money_attraction(
                fa_dict, tid, conn, db_path=db_path
            )
            offer_attractions[tid] = attraction
            # Combined score: weighted by player's greed
            offer_scores[tid] = (
                salary_score * money_weight +
                (1.0 + attraction) * non_money_weight
            )

        # Pick the best overall offer (not just highest salary)
        best_team_id = max(offer_scores, key=lambda t: offer_scores[t])
        best_offer = bidding["offers"][best_team_id]
        best_attraction = offer_attractions[best_team_id]

        should_sign = False

        # Condition 1: Only 1 bidder remains and they've been on market 3+ days
        if len(bidding["offers"]) == 1 and bidding["days_on_market"] >= 3:
            should_sign = True

        # Condition 2: After 7+ days of bidding
        if bidding["days_on_market"] >= 7 and len(bidding["offers"]) >= 1:
            # Non-money attraction can accelerate or delay signing
            sign_chance = 0.20 + (bidding["days_on_market"] - 7) * 0.10 + best_attraction * 0.15
            if random.random() < min(max(sign_chance, 0.05), 0.85):
                should_sign = True

        # Condition 3: Offer exceeds 120% of asking price
        if best_offer["salary"] > effective_asking * 1.20:
            should_sign = True

        # Condition 4: Offer below asking but strong non-money attraction
        if (best_offer["salary"] >= effective_asking * 0.90
                and best_attraction >= 0.20
                and bidding["days_on_market"] >= 5):
            if random.random() < 0.40 + best_attraction:
                should_sign = True

        # Don't sign too early in the offseason (wait until day 14 minimum)
        if offseason_day < 14 and not (best_offer["salary"] > effective_asking * 1.30):
            should_sign = False

        if should_sign:
            team_id = best_team_id
            salary = best_offer["salary"]
            years = best_offer["years"]

            # Re-check 40-man
            forty_man = conn.execute("""
                SELECT COUNT(*) as c FROM players
                WHERE team_id=? AND on_forty_man=1
            """, (team_id,)).fetchone()["c"]

            if forty_man >= 40:
                # Remove this team, don't sign yet
                bidding["interested_teams"] = [t for t in bidding["interested_teams"] if t != team_id]
                del bidding["offers"][team_id]
                continue

            conn.execute("""
                UPDATE players SET team_id=?, roster_status='active', on_forty_man=1
                WHERE id=?
            """, (team_id, player_id))

            conn.execute("""
                INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
                    annual_salary, signed_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (player_id, team_id, years, years, salary, game_date))

            details = {"salary": salary, "years": years, "ai_initiated": True,
                        "tier": tier, "days_on_market": bidding["days_on_market"]}

            # Handle QO compensation on signing
            if bidding.get("qo_status") == "rejected" and bidding.get("original_team_id"):
                original_team_id = bidding["original_team_id"]
                details["qo_compensation"] = True
                details["original_team_id"] = original_team_id

                season_row = conn.execute("SELECT season FROM game_state WHERE id=1").fetchone()
                comp_season = (season_row["season"] if season_row else 2025) + 1

                existing_comp = conn.execute("""
                    SELECT MAX(pick_number) as max_pick FROM draft_pick_ownership
                    WHERE season=? AND round=1
                """, (comp_season,)).fetchone()
                next_pick = (existing_comp["max_pick"] or 30) + 1

                conn.execute("""
                    INSERT INTO draft_pick_ownership
                    (season, round, pick_number, original_team_id, current_owner_team_id, traded_date)
                    VALUES (?, 1, ?, ?, ?, NULL)
                """, (comp_season, next_pick, original_team_id, original_team_id))

                # Signing team loses 3rd-round pick
                conn.execute("""
                    DELETE FROM draft_pick_ownership
                    WHERE season=? AND round=3 AND current_owner_team_id=?
                    AND id = (
                        SELECT id FROM draft_pick_ownership
                        WHERE season=? AND round=3 AND current_owner_team_id=?
                        ORDER BY pick_number ASC LIMIT 1
                    )
                """, (comp_season, team_id, comp_season, team_id))

                details["comp_pick"] = {"team_id": original_team_id, "round": 1, "pick": next_pick}
                details["pick_lost"] = {"team_id": team_id, "round": 3}

                # Notify user if their team lost/gained a pick
                if original_team_id == user_team_id:
                    from .messages import send_qo_compensation_message
                    player_name = f"{fa['first_name']} {fa['last_name']}"
                    send_qo_compensation_message(user_team_id, player_name, db_path=db_path)

            conn.execute("""
                INSERT INTO transactions (transaction_date, transaction_type, details_json,
                    team1_id, player_ids)
                VALUES (?, 'free_agent_signing', ?, ?, ?)
            """, (game_date, json.dumps(details), team_id, str(player_id)))

            _best_offers.pop(player_id, None)

            events.append({
                "type": "signing",
                "player_id": player_id,
                "player_name": f"{fa['first_name']} {fa['last_name']}",
                "team_id": team_id,
                "salary": salary,
                "years": years,
                "tier": tier,
            })

    conn.commit()
    conn.close()
    return events


def process_qualifying_offers(season: int, db_path: str = None) -> dict:
    """
    Process qualifying offers at the start of the offseason.

    - Teams extend QOs ($21M, 1 year) to their own free agents with WAR_approx >= 2.5
    - Players accept if their market value < $21M/year, otherwise reject
    - Rejected QO status is tracked so signing teams lose a draft pick
    - Accepting teams get the player back on a 1-year/$21M deal

    Returns summary of QO activity.
    """
    conn = get_connection(db_path)
    results = {
        "total": 0,
        "qo_extended": [],
        "qo_accepted": [],
        "qo_rejected": [],
    }

    state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
    user_team_id = state["user_team_id"] if state else None

    # Get all free agents (just became free agents this offseason)
    free_agents = conn.execute("""
        SELECT p.* FROM players p
        WHERE p.roster_status = 'free_agent'
    """).fetchall()

    if not free_agents:
        conn.close()
        return results

    # For each free agent, check if their previous team should extend a QO
    # We look at the most recent transaction or contract to determine previous team
    for fa in free_agents:
        fa_dict = dict(fa)
        war = _approximate_war(fa_dict)

        if war < QO_WAR_THRESHOLD:
            continue

        # Find the team that last had this player (from expired contract)
        prev_contract = conn.execute("""
            SELECT team_id FROM contracts
            WHERE player_id = ?
            ORDER BY signed_date DESC LIMIT 1
        """, (fa["id"],)).fetchone()

        if not prev_contract:
            # Also check transactions for the team
            prev_tx = conn.execute("""
                SELECT team1_id FROM transactions
                WHERE player_ids LIKE ? AND transaction_type IN ('contract_expired', 'free_agent_signing')
                ORDER BY transaction_date DESC LIMIT 1
            """, (str(fa["id"]),)).fetchone()
            original_team_id = prev_tx["team1_id"] if prev_tx else None
        else:
            original_team_id = prev_contract["team_id"]

        if not original_team_id:
            continue

        # Team extends QO
        player_name = f"{fa['first_name']} {fa['last_name']}"
        results["qo_extended"].append({
            "player_id": fa["id"],
            "player_name": player_name,
            "team_id": original_team_id,
            "war_approx": war,
        })

        # Initialize bidding state
        bidding = _initialize_bidding(fa_dict, 0, db_path)
        bidding["original_team_id"] = original_team_id

        # Player decision: accept if market value < $21M/year
        market_value = _calculate_market_value(fa_dict, db_path=db_path)
        if market_value["salary"] < QO_VALUE:
            # Accept QO - player goes back to original team on 1yr/$21M
            bidding["qo_status"] = "accepted"

            conn.execute("""
                UPDATE players SET team_id=?, roster_status='active', on_forty_man=1
                WHERE id=?
            """, (original_team_id, fa["id"]))

            conn.execute("""
                INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
                    annual_salary, signed_date)
                VALUES (?, ?, 1, 1, ?, ?)
            """, (fa["id"], original_team_id, QO_VALUE,
                  f"{season}-11-15"))

            conn.execute("""
                INSERT INTO transactions (transaction_date, transaction_type, details_json,
                    team1_id, player_ids)
                VALUES (?, 'qualifying_offer_accepted', ?, ?, ?)
            """, (f"{season}-11-15",
                  json.dumps({"salary": QO_VALUE, "years": 1, "war_approx": war}),
                  original_team_id, str(fa["id"])))

            results["qo_accepted"].append({
                "player_id": fa["id"],
                "player_name": player_name,
                "team_id": original_team_id,
            })

            # Clean up bidding state since player is no longer a free agent
            _best_offers.pop(fa["id"], None)

        else:
            # Reject QO - player stays in free agent pool with QO tag
            bidding["qo_status"] = "rejected"

            conn.execute("""
                INSERT INTO transactions (transaction_date, transaction_type, details_json,
                    team1_id, player_ids)
                VALUES (?, 'qualifying_offer_rejected', ?, ?, ?)
            """, (f"{season}-11-15",
                  json.dumps({"salary": QO_VALUE, "years": 1, "war_approx": war,
                              "market_value_salary": market_value["salary"]}),
                  original_team_id, str(fa["id"])))

            results["qo_rejected"].append({
                "player_id": fa["id"],
                "player_name": player_name,
                "team_id": original_team_id,
                "market_value": market_value["salary"],
            })

    results["total"] = len(results["qo_extended"])
    conn.commit()
    conn.close()
    return results


def ensure_minimum_free_agents(min_count: int = 50, db_path: str = None) -> dict:
    """
    Check if there are fewer than min_count free agents.
    If so, generate new ones to bring it back to min_count.
    Returns info about actions taken.
    """
    from ..database.seed import POSITIONS_BATTING, POSITIONS_PITCHING, _generate_player, FIRST_NAMES, LAST_NAMES

    conn = get_connection(db_path)

    # Count current free agents
    current_count = conn.execute(
        "SELECT COUNT(*) as c FROM players WHERE roster_status = 'free_agent'"
    ).fetchone()["c"]

    if current_count >= min_count:
        conn.close()
        return {
            "action": "none",
            "current_free_agents": current_count,
            "target_count": min_count,
            "message": f"Sufficient free agents ({current_count}). No action needed."
        }

    # Need to generate more
    needed = min_count - current_count
    used_names = set()

    # Collect all existing player names
    existing = conn.execute("SELECT first_name, last_name FROM players").fetchall()
    for p in existing:
        used_names.add(f"{p['first_name']} {p['last_name']}")

    generated = 0
    for _ in range(needed):
        position = random.choice(POSITIONS_BATTING + POSITIONS_PITCHING)
        age = random.randint(28, 38)

        if random.random() < 0.85:
            tier = "bench"
        else:
            tier = "starter"

        p = _generate_player(position, tier, used_names)
        p["age"] = age

        try:
            conn.execute("""
                INSERT INTO players (team_id, first_name, last_name, age, birth_country,
                    bats, throws, position, contact_rating, power_rating, speed_rating,
                    fielding_rating, arm_rating, stuff_rating, control_rating, stamina_rating,
                    contact_potential, power_potential, speed_potential, fielding_potential,
                    arm_potential, stuff_potential, control_potential, stamina_potential,
                    ego, leadership, work_ethic, clutch, durability,
                    roster_status, peak_age, development_rate, service_years,
                    option_years_remaining)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (None, p["first_name"], p["last_name"], p["age"], p["birth_country"],
                  p["bats"], p["throws"], p["position"],
                  p["contact_rating"], p["power_rating"], p["speed_rating"],
                  p["fielding_rating"], p["arm_rating"],
                  p["stuff_rating"], p["control_rating"], p["stamina_rating"],
                  p["contact_potential"], p["power_potential"], p["speed_potential"],
                  p["fielding_potential"], p["arm_potential"],
                  p["stuff_potential"], p["control_potential"], p["stamina_potential"],
                  p["ego"], p["leadership"], p["work_ethic"], p["clutch"], p["durability"],
                  "free_agent", p["peak_age"], p["development_rate"],
                  p["service_years"], p["option_years_remaining"]))
            generated += 1
        except Exception as e:
            print(f"Error generating free agent: {e}")
            continue

    conn.commit()
    conn.close()

    return {
        "action": "generated",
        "generated_count": generated,
        "previous_count": current_count,
        "new_count": current_count + generated,
        "target_count": min_count,
        "message": f"Generated {generated} free agents. Total now: {current_count + generated}"
    }
