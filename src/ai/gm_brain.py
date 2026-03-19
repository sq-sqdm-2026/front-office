"""
Front Office - GM Brain
LLM-powered decision making pipeline for AI General Managers.
Each GM evaluates trades, free agents, and roster moves through
their personality lens via Ollama.
"""
import json
import random
from typing import Optional
from ..database.db import query
from .ollama_client import generate_json, generate


TRADE_EVAL_SYSTEM = """You are {gm_name}, General Manager of the {team_name}.
Your philosophy: {philosophy}. Risk tolerance: {risk}/100. Ego: {ego}/100.
Competence: {competence}/100. Job security: {job_security}/100.
Style: {negotiation_style}.
{personality_details}

Your owner wants: {owner_objectives}
Current record: {record}

Evaluate this trade proposal and respond with JSON:
{{
    "accept": true/false,
    "reasoning": "your internal thought process",
    "counter_offer": null or "description of what you'd want instead",
    "emotional_reaction": "confident/angry/desperate/insulted/excited/neutral",
    "message_to_gm": "what you'd say to the proposing GM"
}}"""


def _get_team_needs(team_id: int, db_path: str = None) -> dict:
    """Calculate positional WAR-proxy and identify weak spots."""
    positions = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF', 'DH', 'SP', 'RP']
    needs = {}
    for pos in positions:
        best = query("""
            SELECT MAX(
                CASE WHEN position IN ('SP','RP')
                    THEN stuff_rating + control_rating + stamina_rating
                    ELSE contact_rating + power_rating + speed_rating + fielding_rating
                END
            ) as best
            FROM players
            WHERE team_id=? AND position=? AND roster_status='active'
        """, (team_id, pos), db_path=db_path)
        needs[pos] = best[0]['best'] if best and best[0]['best'] else 0
    return needs


async def evaluate_trade(proposing_team_id: int, receiving_team_id: int,
                         players_offered: list, players_requested: list,
                         cash_included: int = 0, db_path: str = None) -> dict:
    """Have the receiving team's GM evaluate a trade proposal via LLM."""
    # Load GM personality
    gm = query("SELECT * FROM gm_characters WHERE team_id=?",
               (receiving_team_id,), db_path=db_path)
    if not gm:
        return {"accept": False, "reasoning": "GM not found"}
    gm = gm[0]

    team = query("SELECT * FROM teams WHERE id=?",
                 (receiving_team_id,), db_path=db_path)
    team = team[0] if team else {}

    owner = query("SELECT * FROM owner_characters WHERE team_id=?",
                  (receiving_team_id,), db_path=db_path)
    owner_obj = owner[0]["objectives_json"] if owner else "[]"

    # Load player details
    offered_details = []
    for pid in players_offered:
        p = query("""SELECT p.*, c.annual_salary, c.years_remaining
                     FROM players p LEFT JOIN contracts c ON c.player_id=p.id
                     WHERE p.id=?""", (pid,), db_path=db_path)
        if p:
            offered_details.append(p[0])

    requested_details = []
    for pid in players_requested:
        p = query("""SELECT p.*, c.annual_salary, c.years_remaining
                     FROM players p LEFT JOIN contracts c ON c.player_id=p.id
                     WHERE p.id=?""", (pid,), db_path=db_path)
        if p:
            requested_details.append(p[0])

    # Format player info for prompt
    def _fmt_player(p):
        pos = p["position"]
        if pos in ("SP", "RP"):
            ratings = f"Stuff:{p['stuff_rating']} Ctrl:{p['control_rating']} Stam:{p['stamina_rating']}"
        else:
            ratings = f"Con:{p['contact_rating']} Pow:{p['power_rating']} Spd:{p['speed_rating']} Fld:{p['fielding_rating']}"
        salary = f"${p.get('annual_salary', 0):,}/yr" if p.get('annual_salary') else "pre-arb"
        return f"{p['first_name']} {p['last_name']} ({pos}, Age {p['age']}, {ratings}, {salary})"

    offered_str = "\n".join(f"  - {_fmt_player(p)}" for p in offered_details) or "  (none)"
    requested_str = "\n".join(f"  - {_fmt_player(p)}" for p in requested_details) or "  (none)"

    # Build prompt
    personality = json.loads(gm["personality_json"]) if gm["personality_json"] else {}
    personality_str = ", ".join(f"{k}: {v}" for k, v in personality.items())

    system = TRADE_EVAL_SYSTEM.format(
        gm_name=f"{gm['first_name']} {gm['last_name']}",
        team_name=f"{team.get('city', '')} {team.get('name', '')}",
        philosophy=gm["philosophy"],
        risk=gm["risk_tolerance"],
        ego=gm["ego"],
        competence=gm["competence"],
        job_security=gm["job_security"],
        negotiation_style=gm["negotiation_style"],
        personality_details=personality_str,
        owner_objectives=owner_obj,
        record="(season in progress)",
    )

    prompt = f"""Trade proposal:

YOU RECEIVE:
{offered_str}
{f'Plus ${cash_included:,} cash' if cash_included else ''}

YOU GIVE UP:
{requested_str}

Consider: Does this make your team better? Does it fit your philosophy?
What's your relationship with this GM? Is your owner pressuring you?
How's your job security?"""

    # Try LLM first, fall back to algorithmic
    try:
        result = await generate_json(prompt, task_type="strategic", system_prompt=system)
        if result and "error" not in result:
            return result
    except Exception as e:
        pass

    # Fallback: algorithmic evaluation (LLM was unavailable)
    fallback = _algorithmic_trade_eval(gm, offered_details, requested_details,
                                       cash_included, receiving_team_id, db_path)
    fallback["_used_fallback"] = True
    return fallback


def _algorithmic_trade_eval(gm: dict, offered: list, requested: list,
                            cash: int = 0, team_id: int = None,
                            db_path: str = None) -> dict:
    """Fallback trade evaluation using math when LLM is unavailable.

    Applies difficulty modifiers:
    - Fan difficulty: AI teams favor trades with player by +10%
    - Coach difficulty: Normal (baseline)
    - Manager difficulty: AI teams resist trades by -10%
    - Mogul difficulty: AI teams resist trades by -20%
    """
    # Get difficulty setting for trade acceptance threshold
    game_state = query("SELECT difficulty FROM game_state WHERE id=1", db_path=db_path)
    difficulty = game_state[0]["difficulty"] if game_state else "manager"

    # Trade acceptance modifiers by difficulty
    difficulty_trade_mods = {
        "fan": 0.90,        # +10% acceptance (lower threshold)
        "coach": 1.0,       # baseline
        "manager": 1.0,     # baseline
        "mogul": 1.20,      # -20% acceptance (higher threshold)
    }
    trade_threshold_mod = difficulty_trade_mods.get(difficulty, 1.0)

    # Get team needs for roster-aware evaluation
    needs = {}
    if team_id:
        needs = _get_team_needs(team_id, db_path)

    def _player_value(p: dict, for_team: bool = False) -> float:
        if p["position"] in ("SP", "RP"):
            raw = (p["stuff_rating"] * 2 + p["control_rating"] * 1.5 +
                   p["stamina_rating"] * 0.5)
        else:
            raw = (p["contact_rating"] * 1.5 + p["power_rating"] * 1.5 +
                   p["speed_rating"] * 0.5 + p["fielding_rating"] * 0.5)
        # Age adjustment
        age_penalty = max(0, (p["age"] - 28) * 3)
        # Contract value (cheap good players are more valuable)
        salary = p.get("annual_salary", 750000) or 750000
        salary_mod = max(0.5, 1.5 - salary / 30000000)
        base_value = (raw - age_penalty) * salary_mod

        # Roster-aware adjustments for incoming players
        if for_team and needs:
            pos = p["position"]
            pos_strength = needs.get(pos, 0)
            if pos_strength < 150:
                # Weak spot - player fills a need, increase value by 25%
                base_value *= 1.25
            elif pos_strength >= 200:
                # Already strong position - decrease value by 15%
                base_value *= 0.85

        return base_value

    # Offered players are incoming TO the evaluating team (roster-aware)
    offered_value = sum(_player_value(p, for_team=True) for p in offered) + cash / 1000000
    # Requested players are going OUT (no roster adjustment)
    requested_value = sum(_player_value(p, for_team=False) for p in requested)

    ratio = offered_value / max(1, requested_value)

    # GM personality affects threshold
    threshold = 0.85 + (100 - gm["competence"]) * 0.003  # bad GMs accept worse deals
    if gm["emotional_state"] == "desperate":
        threshold -= 0.15

    # Apply difficulty modifier to threshold
    threshold *= trade_threshold_mod

    accept = ratio >= threshold

    # Generate structured counter-offer if rejected
    counter_offer = None
    if not accept and team_id:
        counter_offer = _generate_counter_offer(
            offered, requested, offered_value, requested_value,
            threshold, team_id, gm, needs, _player_value, db_path
        )

    return {
        "accept": accept,
        "reasoning": f"Algorithmic: value ratio {ratio:.2f} vs threshold {threshold:.2f}",
        "counter_offer": counter_offer,
        "emotional_reaction": "neutral" if accept else ("frustrated" if ratio < 0.5 else "interested"),
        "message_to_gm": "Deal." if accept else (
            counter_offer.get("message", "We'd need more to make this work.") if counter_offer
            else "We'd need more to make this work."
        ),
    }


def _generate_counter_offer(offered, requested, offered_val, requested_val,
                             threshold, team_id, gm, needs, value_fn, db_path=None):
    """Generate a structured counter-offer with specific player suggestions."""
    value_gap = requested_val * threshold - offered_val

    if value_gap <= 0:
        return None

    # Look for players on the proposing team that could fill the gap
    # (proposing team = the team that sent the offer, their players are in 'offered')
    proposing_team_id = offered[0]["team_id"] if offered else None
    if not proposing_team_id:
        return {"message": "We'd need significantly more value coming back.", "players_wanted": []}

    # Find available players from proposing team we'd want
    available = query("""
        SELECT p.*, c.annual_salary, c.years_remaining FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.id NOT IN ({})
        ORDER BY p.contact_rating + p.power_rating + p.stuff_rating DESC
        LIMIT 20
    """.format(",".join(str(p["id"]) for p in offered) if offered else "0"),
        (proposing_team_id,), db_path=db_path)

    if not available:
        return {"message": "We'd need more talent to make this work.", "players_wanted": []}

    # Score each available player and find ones that fill the value gap
    candidates = []
    for p in available:
        p_val = value_fn(dict(p), for_team=True)
        pos = p["position"]
        # Prefer players at positions of need
        need_bonus = 1.0
        if needs and pos in needs and needs[pos] < 150:
            need_bonus = 1.3
        candidates.append((p, p_val * need_bonus, p_val))

    candidates.sort(key=lambda x: x[1], reverse=True)

    # Pick the minimum set of players to close the value gap
    players_wanted = []
    remaining_gap = value_gap
    for player, adj_val, raw_val in candidates:
        if remaining_gap <= 0:
            break
        players_wanted.append({
            "id": player["id"],
            "name": f"{player['first_name']} {player['last_name']}",
            "position": player["position"],
            "age": player["age"],
        })
        remaining_gap -= raw_val
        if len(players_wanted) >= 2:
            break  # Don't ask for too many extra players

    if not players_wanted:
        return {"message": "The value isn't there for us.", "players_wanted": []}

    names = " and ".join(p["name"] for p in players_wanted)
    return {
        "message": f"We like the framework, but we'd need you to include {names} to make this work.",
        "players_wanted": players_wanted,
        "value_gap": round(value_gap, 1),
    }


async def generate_scouting_report(player_id: int, scout_quality: int = 50,
                                   db_path: str = None) -> dict:
    """
    Generate a comprehensive scouting report with present/future grades,
    narrative, comp, and uncertainty margins based on scout quality.
    """
    player = query("""SELECT * FROM players WHERE id=?""",
                   (player_id,), db_path=db_path)
    if not player:
        return {"error": "Player not found"}
    p = player[0]

    is_pitcher = p["position"] in ("SP", "RP")

    # Calculate uncertainty margins based on scout quality
    if scout_quality >= 70:
        uncertainty = 3  # Elite scout: +/- 3
    elif scout_quality >= 50:
        uncertainty = 7  # Average scout: +/- 7
    else:
        uncertainty = 12  # Poor scout: +/- 12

    # Generate present grades (based on current ratings with noise)
    if is_pitcher:
        present_grades = {
            "fastball": max(20, min(80, p["stuff_rating"] + random.randint(-uncertainty, uncertainty))),
            "curveball": max(20, min(80, p["control_rating"] + random.randint(-uncertainty, uncertainty))),
            "slider": max(20, min(80, p["control_rating"] + random.randint(-uncertainty, uncertainty))),
            "changeup": max(20, min(80, p["control_rating"] + random.randint(-uncertainty, uncertainty))),
            "command": max(20, min(80, p["control_rating"] + random.randint(-uncertainty, uncertainty))),
            "control": max(20, min(80, p["control_rating"] + random.randint(-uncertainty, uncertainty))),
        }
        # Future grades: add development and age adjustment
        age_adj = max(-5, 5 - max(0, (p["age"] - 27) * 1.5))
        dev_bonus = p["development_rate"] * 5
        future_grades = {
            "fastball": max(20, min(80, present_grades["fastball"] + int(dev_bonus + age_adj))),
            "curveball": max(20, min(80, present_grades["curveball"] + int(dev_bonus + age_adj))),
            "slider": max(20, min(80, present_grades["slider"] + int(dev_bonus + age_adj))),
            "changeup": max(20, min(80, present_grades["changeup"] + int(dev_bonus + age_adj))),
            "command": max(20, min(80, present_grades["command"] + int(dev_bonus + age_adj))),
            "control": max(20, min(80, present_grades["control"] + int(dev_bonus + age_adj))),
        }
    else:
        present_grades = {
            "hit": max(20, min(80, p["contact_rating"] + random.randint(-uncertainty, uncertainty))),
            "power": max(20, min(80, p["power_rating"] + random.randint(-uncertainty, uncertainty))),
            "run": max(20, min(80, p["speed_rating"] + random.randint(-uncertainty, uncertainty))),
            "field": max(20, min(80, p["fielding_rating"] + random.randint(-uncertainty, uncertainty))),
            "arm": max(20, min(80, p["arm_rating"] + random.randint(-uncertainty, uncertainty))),
        }
        # Future grades with development and age
        age_adj = max(-5, 8 - max(0, (p["age"] - 27) * 2))
        dev_bonus = p["development_rate"] * 5
        future_grades = {
            "hit": max(20, min(80, present_grades["hit"] + int(dev_bonus + age_adj))),
            "power": max(20, min(80, present_grades["power"] + int(dev_bonus + age_adj))),
            "run": max(20, min(80, present_grades["run"] + int(dev_bonus + age_adj))),
            "field": max(20, min(80, present_grades["field"] + int(dev_bonus + age_adj))),
            "arm": max(20, min(80, present_grades["arm"] + int(dev_bonus + age_adj))),
        }

    # Calculate OFP (Overall Future Potential)
    # Use the HIGHER of present or future grades (established stars shouldn't lose OFP)
    avg_future = sum(future_grades.values()) / len(future_grades)
    avg_present = sum(present_grades.values()) / len(present_grades)
    best_avg = max(avg_future, avg_present)
    # Adjust by makeup (ego affects ceiling, but only slightly)
    makeup_adj = (50 - p["ego"]) / 100 * 2  # Reduced from *5 to *2
    ofp = max(20, min(80, int(best_avg + makeup_adj)))

    # Generate ceiling and floor descriptions
    if ofp >= 75:
        ceiling = "Generational talent / perennial MVP candidate"
        floor = "All-Star caliber player"
    elif ofp >= 70:
        ceiling = "Perennial All-Star with MVP upside"
        floor = "Above-average regular"
    elif ofp >= 65:
        ceiling = "All-Star caliber player"
        floor = "Solid everyday starter"
    elif ofp >= 60:
        ceiling = "Above-average regular with All-Star potential"
        floor = "Solid starter/regular"
    elif ofp >= 55:
        ceiling = "Quality everyday player"
        floor = "Platoon player or useful bench piece"
    elif ofp >= 50:
        ceiling = "Everyday player"
        floor = "Reserve/platoon player"
    elif ofp >= 40:
        ceiling = "Useful bench player"
        floor = "Minor leaguer or organizational depth"
    else:
        ceiling = "Role player at best"
        floor = "Non-prospect"

    # Determine risk level based on grades vs potential
    rating_avg = sum(present_grades.values()) / len(present_grades)
    gap = ofp - rating_avg
    if gap > 10:
        risk_level = "high"
    elif gap > 5:
        risk_level = "medium"
    else:
        risk_level = "low"

    # ETA calculation
    if p["age"] <= 22:
        eta = str(2026 + random.randint(0, 2))
    elif p["age"] <= 25:
        eta = str(2026 + random.randint(0, 1))
    else:
        eta = "2026"

    # Get MLB comp
    from .player_comps import find_best_comp
    comps = find_best_comp(p, p["position"], is_pitcher, count=1)
    mlb_comp = comps[0] if comps else None

    # Try LLM for narrative, fall back to algorithmic
    narrative = await _generate_scouting_narrative(p, present_grades, future_grades,
                                                   ceiling, floor, is_pitcher, mlb_comp,
                                                   scout_quality, db_path)

    # Check if stat-based scouting is active and include MLE metadata
    from .scouting_modes import get_scouting_mode
    from .mle import calculate_mle_ratings
    scouting_mode = get_scouting_mode()
    mle_info = None
    if scouting_mode == "stat_based":
        mle_result = calculate_mle_ratings(player_id, season=2026)
        if mle_result:
            from_level = mle_result.get("from_level", "")
            is_mle = mle_result.get("is_mle", False)
            park_adjusted = mle_result.get("park_adjusted", False)
            if is_mle:
                source_desc = f"MLE-derived from {from_level} stats"
                if park_adjusted:
                    source_desc += " (park-factor adjusted)"
            else:
                source_desc = "Derived from actual MLB stats"
            mle_info = {
                "rating_source": "mle" if is_mle else "mlb_actual",
                "from_level": from_level,
                "park_adjusted": park_adjusted,
                "source_description": source_desc,
            }

    result = {
        "player_id": player_id,
        "player_name": f"{p['first_name']} {p['last_name']}",
        "position": p["position"],
        "age": p["age"],
        "present_grades": present_grades,
        "future_grades": future_grades,
        "ofp": ofp,
        "ceiling": ceiling,
        "floor": floor,
        "risk_level": risk_level,
        "eta": eta,
        "narrative": narrative,
        "mlb_comp": mlb_comp,
        "scout_quality": scout_quality,
        "uncertainty_margin": uncertainty,
        "scouting_mode": scouting_mode,
        "mle_info": mle_info,
        "physical": {
            "height": "6-0",  # Would come from extended player data
            "weight": "190",
            "body_type": "athletic",
            "bats": p["bats"],
            "throws": p["throws"],
        },
        "makeup": {
            "ego": p["ego"],
            "leadership": p["leadership"],
            "work_ethic": p["work_ethic"],
            "clutch": p["clutch"],
        },
    }

    # Add pitch arsenal data for pitchers
    if is_pitcher:
        from .pitch_velocity import calculate_pitch_arsenal
        pitch_arsenal = calculate_pitch_arsenal(p, uncertainty, scout_quality)
        result["pitch_arsenal"] = pitch_arsenal

    # Add exit velocity data for batters
    else:
        exit_velo = {
            "avg_exit_velo": round(82 + (p["power_rating"] - 20) * 0.22, 1),
            "max_exit_velo": round(82 + (p["power_rating"] - 20) * 0.22 + random.uniform(10, 15), 1),
            "barrel_rate": round(3 + (p["power_rating"] - 20) * 0.20, 1),
            "hard_hit_rate": round((3 + (p["power_rating"] - 20) * 0.20) * random.uniform(3.0, 4.0), 1),
        }
        result["exit_velo"] = exit_velo

    return result


async def _generate_scouting_narrative(player: dict, present_grades: dict,
                                       future_grades: dict, ceiling: str, floor: str,
                                       is_pitcher: bool, mlb_comp: Optional[dict],
                                       scout_quality: int, db_path: str = None) -> str:
    """Generate narrative portion of scouting report via LLM or algorithm."""
    if is_pitcher:
        grades_str = f"Fastball: {present_grades.get('fastball')}, Curveball: {present_grades.get('curveball')}, Control: {present_grades.get('control')}"
        tools_desc = "arm"
    else:
        grades_str = f"Hit: {present_grades.get('hit')}, Power: {present_grades.get('power')}, Speed: {present_grades.get('run')}, Defense: {present_grades.get('field')}"
        tools_desc = "bat"

    comp_info = ""
    if mlb_comp:
        comp_info = f"\nCompare favorably to {mlb_comp['name']} ({mlb_comp['years']}): {mlb_comp['description']}"

    prompt = f"""Write a professional scouting report narrative (2-3 sentences) for this player.
Use authentic scouting terminology. Mention ceiling/floor, makeup, and specific tool strengths.

Player: {player['first_name']} {player['last_name']}, {player['position']}, Age {player['age']}
Present Grades: {grades_str}
Ceiling: {ceiling}
Floor: {floor}
Makeup: Leadership {player['leadership']}, Work Ethic {player['work_ethic']}, Ego {player['ego']}{comp_info}

Use scouting language like: plus, loose arm action, projectable, barrel control, repeatable delivery, etc."""

    system = f"You are an experienced professional baseball scout. Confidence level: {scout_quality}/100."

    try:
        narrative = await generate(prompt, task_type="creative", system_prompt=system)
        if narrative and "[LLM unavailable" not in narrative:
            return narrative
    except Exception:
        pass

    # Fallback: algorithmic narrative (LLM was unavailable)
    fallback_text = _generate_algorithmic_narrative(player, present_grades, future_grades,
                                                     ceiling, floor, is_pitcher, mlb_comp)
    return "[AI Offline] " + fallback_text


def _generate_algorithmic_narrative(player: dict, present_grades: dict, future_grades: dict,
                                    ceiling: str, floor: str, is_pitcher: bool,
                                    mlb_comp: Optional[dict]) -> str:
    """Generate narrative using template-based approach."""
    tools_text = []
    if is_pitcher:
        if present_grades.get("fastball", 0) >= 75:
            tools_text.append("power fastball")
        if present_grades.get("curveball", 0) >= 75:
            tools_text.append("sharp curveball")
        if present_grades.get("control", 0) >= 75:
            tools_text.append("exceptional control")
    else:
        if present_grades.get("power", 0) >= 75:
            tools_text.append("plus-plus power")
        if present_grades.get("hit", 0) >= 75:
            tools_text.append("excellent bat speed")
        if present_grades.get("run", 0) >= 70:
            tools_text.append("above-average speed")
        if present_grades.get("field", 0) >= 75:
            tools_text.append("slick defense")

    tools_phrase = " with ".join(tools_text) if tools_text else "solid tools"

    ego_text = "high maintenance player" if player["ego"] >= 70 else "good makeup" if player["ego"] <= 40 else "average approach"

    narrative = f"{player['first_name']} projects as {ceiling.lower()}. {tools_phrase}. {ego_text}. "

    if mlb_comp:
        narrative += f"Similar profile to {mlb_comp['name']}. "

    narrative += f"Best case: {ceiling.lower()}. Worst case: {floor.lower()}."

    return narrative
