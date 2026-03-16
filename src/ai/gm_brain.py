"""
Front Office - GM Brain
LLM-powered decision making pipeline for AI General Managers.
Each GM evaluates trades, free agents, and roster moves through
their personality lens via Ollama.
"""
import json
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
        if "error" not in result:
            return result
    except Exception:
        pass

    # Tier 1 fallback: algorithmic evaluation
    return _algorithmic_trade_eval(gm, offered_details, requested_details,
                                   cash_included, receiving_team_id, db_path)


def _algorithmic_trade_eval(gm: dict, offered: list, requested: list,
                            cash: int = 0, team_id: int = None,
                            db_path: str = None) -> dict:
    """Fallback trade evaluation using math when LLM is unavailable."""
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

    accept = ratio >= threshold

    return {
        "accept": accept,
        "reasoning": f"Algorithmic: value ratio {ratio:.2f} vs threshold {threshold:.2f}",
        "counter_offer": None if accept else "Need more value coming back",
        "emotional_reaction": "neutral",
        "message_to_gm": "Deal." if accept else "We'd need more to make this work.",
    }


async def generate_scouting_report(player_id: int, scout_quality: int = 50,
                                   db_path: str = None) -> str:
    """Generate an LLM-written scouting report for a player."""
    player = query("""SELECT * FROM players WHERE id=?""",
                   (player_id,), db_path=db_path)
    if not player:
        return "Player not found."
    p = player[0]

    is_pitcher = p["position"] in ("SP", "RP")

    if is_pitcher:
        ratings_str = (f"Stuff: {p['stuff_rating']}, Control: {p['control_rating']}, "
                       f"Stamina: {p['stamina_rating']}")
    else:
        ratings_str = (f"Contact: {p['contact_rating']}, Power: {p['power_rating']}, "
                       f"Speed: {p['speed_rating']}, Fielding: {p['fielding_rating']}, "
                       f"Arm: {p['arm_rating']}")

    prompt = f"""Write a 2-3 sentence scouting report for this player in a scout's voice.
Be opinionated and specific. Compare to real MLB players if appropriate.

Player: {p['first_name']} {p['last_name']}
Position: {p['position']}, Age: {p['age']}, Bats: {p['bats']}, Throws: {p['throws']}
Ratings (20-80 scale): {ratings_str}
Personality: Ego {p['ego']}, Leadership {p['leadership']}, Work Ethic {p['work_ethic']}, Clutch {p['clutch']}
Country: {p['birth_country']}

{'Include uncertainty - this scout is not very accurate.' if scout_quality < 40 else ''}
{'This scout has excellent judgment.' if scout_quality > 70 else ''}"""

    report = await generate(prompt, task_type="creative",
                           system_prompt="You are an experienced baseball scout writing a report for the GM.")
    return report or f"Solid {'arm' if is_pitcher else 'bat'}. Projects as a {'rotation piece' if is_pitcher else 'everyday player'}."
