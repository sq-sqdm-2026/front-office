"""
Front Office - Season Manager
Handles advancing the sim by days/weeks, running scheduled games,
updating standings, and tracking the season calendar.
"""
import json
from datetime import date, timedelta
from ..database.db import get_connection, query, execute
from .game_engine import (
    simulate_game, BatterStats, PitcherStats, ParkFactors
)
from .strategy import get_strategy
from .chemistry import (
    update_player_morale, update_team_chemistry, calculate_team_chemistry
)


def get_standings(season: int = None, db_path: str = None) -> dict:
    """Get current standings grouped by division."""
    if season is None:
        state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
        season = state[0]["season"] if state else 2025

    teams = query("SELECT * FROM teams", db_path=db_path)

    standings = {}
    for t in teams:
        div_key = f"{t['league']} {t['division']}"
        if div_key not in standings:
            standings[div_key] = []

        # Get W-L record
        wins = query("""
            SELECT COUNT(*) as w FROM schedule
            WHERE season=? AND is_played=1 AND (
                (home_team_id=? AND home_score > away_score) OR
                (away_team_id=? AND away_score > home_score)
            )
        """, (season, t["id"], t["id"]), db_path=db_path)[0]["w"]

        losses = query("""
            SELECT COUNT(*) as l FROM schedule
            WHERE season=? AND is_played=1 AND (
                (home_team_id=? AND home_score < away_score) OR
                (away_team_id=? AND away_score < home_score)
            )
        """, (season, t["id"], t["id"]), db_path=db_path)[0]["l"]

        # Runs scored/allowed
        rs_home = query("""
            SELECT COALESCE(SUM(home_score), 0) as rs FROM schedule
            WHERE season=? AND is_played=1 AND home_team_id=?
        """, (season, t["id"]), db_path=db_path)[0]["rs"]
        rs_away = query("""
            SELECT COALESCE(SUM(away_score), 0) as rs FROM schedule
            WHERE season=? AND is_played=1 AND away_team_id=?
        """, (season, t["id"]), db_path=db_path)[0]["rs"]
        ra_home = query("""
            SELECT COALESCE(SUM(away_score), 0) as ra FROM schedule
            WHERE season=? AND is_played=1 AND home_team_id=?
        """, (season, t["id"]), db_path=db_path)[0]["ra"]
        ra_away = query("""
            SELECT COALESCE(SUM(home_score), 0) as ra FROM schedule
            WHERE season=? AND is_played=1 AND away_team_id=?
        """, (season, t["id"]), db_path=db_path)[0]["ra"]

        pct = wins / max(1, wins + losses)

        # --- L10: last 10 games record ---
        last_10_games = query("""
            SELECT
                CASE
                    WHEN (home_team_id=? AND home_score > away_score)
                      OR (away_team_id=? AND away_score > home_score)
                    THEN 'W' ELSE 'L'
                END as result
            FROM schedule
            WHERE season=? AND is_played=1 AND (home_team_id=? OR away_team_id=?)
            ORDER BY game_date DESC
            LIMIT 10
        """, (t["id"], t["id"], season, t["id"], t["id"]), db_path=db_path)

        l10_wins = sum(1 for g in last_10_games if g["result"] == "W")
        l10_losses = len(last_10_games) - l10_wins

        # --- Streak: current W/L streak ---
        recent_games = query("""
            SELECT
                CASE
                    WHEN (home_team_id=? AND home_score > away_score)
                      OR (away_team_id=? AND away_score > home_score)
                    THEN 'W' ELSE 'L'
                END as result
            FROM schedule
            WHERE season=? AND is_played=1 AND (home_team_id=? OR away_team_id=?)
            ORDER BY game_date DESC
        """, (t["id"], t["id"], season, t["id"], t["id"]), db_path=db_path)

        streak = ""
        if recent_games:
            streak_type = recent_games[0]["result"]
            streak_count = 0
            for g in recent_games:
                if g["result"] == streak_type:
                    streak_count += 1
                else:
                    break
            streak = f"{streak_type}{streak_count}"

        # --- Games remaining ---
        games_remaining = query("""
            SELECT COUNT(*) as cnt FROM schedule
            WHERE season=? AND is_played=0 AND is_postseason=0
            AND (home_team_id=? OR away_team_id=?)
        """, (season, t["id"], t["id"]), db_path=db_path)[0]["cnt"]

        standings[div_key].append({
            "team_id": t["id"],
            "city": t["city"],
            "name": t["name"],
            "abbreviation": t["abbreviation"],
            "wins": wins,
            "losses": losses,
            "pct": round(pct, 3),
            "runs_scored": rs_home + rs_away,
            "runs_allowed": ra_home + ra_away,
            "diff": (rs_home + rs_away) - (ra_home + ra_away),
            "l10_wins": l10_wins,
            "l10_losses": l10_losses,
            "streak": streak,
            "games_remaining": games_remaining,
        })

    # Sort each division by win pct, then run differential as tiebreaker
    for div_key in standings:
        standings[div_key].sort(key=lambda x: (-x["pct"], -x["wins"], -x["diff"]))
        if standings[div_key]:
            leader = standings[div_key][0]
            for t in standings[div_key]:
                t["gb"] = ((leader["wins"] - t["wins"]) + (t["losses"] - leader["losses"])) / 2

        # --- Magic number & clinched ---
        if len(standings[div_key]) >= 2:
            leader = standings[div_key][0]
            second = standings[div_key][1]
            # Magic number = 2nd place games remaining + 1 - (leader wins - 2nd place wins)
            magic = second["games_remaining"] + 1 - (leader["wins"] - second["wins"])
            leader["magic_number"] = max(0, magic)
            leader["clinched"] = magic <= 0
            # Other teams: no magic number (they are chasing)
            for t in standings[div_key][1:]:
                t["magic_number"] = None
                t["clinched"] = False
        else:
            for t in standings[div_key]:
                t["magic_number"] = None
                t["clinched"] = False

    return standings


def _fill_position_lineup(batters_data, opposing_pitcher_throws=None):
    """Build a position-constrained lineup from available batters.

    Returns (starters, bench) where starters is a list of 9 players with
    one player per defensive position, and bench is the rest.
    """
    # Defensive positions to fill (one each)
    FIELD_POSITIONS = ["C", "1B", "2B", "SS", "3B", "LF", "CF", "RF"]

    # Fallback mappings: if no player at a position, try these alternatives
    POSITION_FALLBACKS = {
        "C": [],
        "1B": ["3B", "LF", "RF", "DH"],
        "2B": ["SS", "3B"],
        "SS": ["2B", "3B"],
        "3B": ["SS", "2B", "1B"],
        "LF": ["CF", "RF"],
        "CF": ["LF", "RF"],
        "RF": ["LF", "CF"],
    }

    def _platoon_bonus(b):
        bonus = 0
        if opposing_pitcher_throws:
            bats = b["bats"]
            if bats == "S":
                bonus += 3
            elif (opposing_pitcher_throws == "L" and bats == "R") or \
                 (opposing_pitcher_throws == "R" and bats == "L"):
                bonus += 5
            elif (opposing_pitcher_throws == "L" and bats == "L") or \
                 (opposing_pitcher_throws == "R" and bats == "R"):
                bonus -= 3
            if b.get("platoon_split_json"):
                try:
                    splits = json.loads(b["platoon_split_json"])
                    key = "vs_lhp" if opposing_pitcher_throws == "L" else "vs_rhp"
                    if key in splits:
                        bonus += splits[key].get("contact", 0) * 0.3 + splits[key].get("power", 0) * 0.2
                except:
                    pass
        return bonus

    def _fielding_score(b):
        return (b["fielding_rating"] or 0) + _platoon_bonus(b)

    def _hitting_score(b):
        return (b["contact_rating"] or 0) + (b["power_rating"] or 0) + _platoon_bonus(b)

    def _cf_score(b):
        return (b["speed_rating"] or 0) + (b["fielding_rating"] or 0) + _platoon_bonus(b)

    used_ids = set()
    starters = {}  # position -> player

    # Score function per position
    pos_scoring = {
        "C": _fielding_score,
        "1B": _hitting_score,
        "2B": _fielding_score,
        "SS": _fielding_score,
        "3B": _fielding_score,
        "LF": _hitting_score,
        "CF": _cf_score,
        "RF": _hitting_score,
    }

    # Fill each defensive position with best player at that position
    for pos in FIELD_POSITIONS:
        score_fn = pos_scoring[pos]
        candidates = [b for b in batters_data if b["position"] == pos and b["id"] not in used_ids]
        if not candidates:
            # Try fallbacks
            for fallback_pos in POSITION_FALLBACKS.get(pos, []):
                candidates = [b for b in batters_data if b["position"] == fallback_pos and b["id"] not in used_ids]
                if candidates:
                    break
        if candidates:
            candidates.sort(key=score_fn, reverse=True)
            best = candidates[0]
            starters[pos] = best
            used_ids.add(best["id"])

    # DH: best remaining hitter not in the field
    remaining = [b for b in batters_data if b["id"] not in used_ids]
    remaining.sort(key=_hitting_score, reverse=True)
    if remaining:
        starters["DH"] = remaining[0]
        used_ids.add(remaining[0]["id"])

    # If we have fewer than 9 starters (position gaps), fill with best remaining
    while len(starters) < 9 and remaining:
        remaining = [b for b in batters_data if b["id"] not in used_ids]
        if not remaining:
            break
        remaining.sort(key=_hitting_score, reverse=True)
        # Assign to a made-up utility slot
        starters[f"UTIL{len(starters)}"] = remaining[0]
        used_ids.add(remaining[0]["id"])

    # Build batting order intelligently
    starter_list = list(starters.items())  # (position, player) pairs

    def _obp_score(b):
        return (b["speed_rating"] or 0) * 0.5 + (b["contact_rating"] or 0) * 1.0 + _platoon_bonus(b)

    def _contact_score(b):
        return (b["contact_rating"] or 0) + _platoon_bonus(b)

    def _balanced_score(b):
        return (b["contact_rating"] or 0) * 0.6 + (b["power_rating"] or 0) * 0.6 + _platoon_bonus(b)

    def _power_score(b):
        return (b["power_rating"] or 0) + _platoon_bonus(b)

    def _overall_score(b):
        return (b["contact_rating"] or 0) + (b["power_rating"] or 0) + (b["speed_rating"] or 0) * 0.3 + _platoon_bonus(b)

    # Sort candidates for each batting order slot
    available = list(starter_list)
    ordered = []

    def _pick_best(scoring_fn):
        nonlocal available
        if not available:
            return None
        available.sort(key=lambda x: scoring_fn(x[1]), reverse=True)
        pick = available.pop(0)
        return pick

    # 1st: leadoff - highest OBP (speed + contact)
    ordered.append(_pick_best(_obp_score))
    # 2nd: best contact
    ordered.append(_pick_best(_contact_score))
    # 3rd: best balanced
    ordered.append(_pick_best(_balanced_score))
    # 4th: cleanup - highest power
    ordered.append(_pick_best(_power_score))
    # 5th: second highest power
    ordered.append(_pick_best(_power_score))
    # 6th-9th: remaining by overall descending
    while available:
        ordered.append(_pick_best(_overall_score))

    # Filter out None entries
    ordered = [x for x in ordered if x is not None]

    bench = [b for b in batters_data if b["id"] not in used_ids]

    return ordered, bench


def _load_team_lineup(team_id: int, db_path: str = None, opposing_pitcher_throws: str = None) -> tuple:
    """Load a team's active batters and pitchers from the database.

    Args:
        opposing_pitcher_throws: 'L' or 'R' for auto-platoon optimization.
            If provided, lineup is optimized against that handedness.
    """
    batters_data = query("""
        SELECT p.*, c.annual_salary FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.position NOT IN ('SP', 'RP')
        ORDER BY p.contact_rating + p.power_rating DESC
    """, (team_id,), db_path=db_path)

    pitchers_data = query("""
        SELECT p.*, c.annual_salary FROM players p
        LEFT JOIN contracts c ON c.player_id = p.id
        WHERE p.team_id=? AND p.roster_status='active'
        AND p.position IN ('SP', 'RP')
        ORDER BY p.position ASC, p.stuff_rating + p.control_rating DESC
    """, (team_id,), db_path=db_path)

    # Build position-constrained lineup
    ordered_starters, bench = _fill_position_lineup(
        batters_data, opposing_pitcher_throws
    )

    # Build batting order from position-constrained starters, then bench
    lineup = []
    for i, (pos, b) in enumerate(ordered_starters):
        lineup.append(BatterStats(
            player_id=b["id"],
            name=f"{b['first_name']} {b['last_name']}",
            position=pos if not pos.startswith("UTIL") else b["position"],
            batting_order=i + 1,
            bats=b["bats"],
            contact=b["contact_rating"],
            power=b["power_rating"],
            speed=b["speed_rating"],
            clutch=b["clutch"],
            fielding=b["fielding_rating"],
            eye=b.get("eye_rating", 50),
            morale=b["morale"],
            height_inches=b.get("height_inches") or 73,
        ))
    # Add bench players after starters
    for i, b in enumerate(bench):
        lineup.append(BatterStats(
            player_id=b["id"],
            name=f"{b['first_name']} {b['last_name']}",
            position=b["position"],
            batting_order=len(ordered_starters) + i + 1,
            bats=b["bats"],
            contact=b["contact_rating"],
            power=b["power_rating"],
            speed=b["speed_rating"],
            clutch=b["clutch"],
            fielding=b["fielding_rating"],
            eye=b.get("eye_rating", 50),
            morale=b["morale"],
            height_inches=b.get("height_inches") or 73,
        ))

    # Load per-player strategy overrides
    player_ids = [b.player_id for b in lineup]
    if player_ids:
        placeholders = ",".join(str(pid) for pid in player_ids)
        strategies = query(
            f"SELECT * FROM player_strategy WHERE player_id IN ({placeholders})",
            db_path=db_path
        )
        strat_map = {s["player_id"]: s for s in strategies}
        for b in lineup:
            if b.player_id in strat_map:
                s = strat_map[b.player_id]
                b.steal_aggression = s.get("steal_aggression", 3)
                b.bunt_tendency = s.get("bunt_tendency", 3)
                b.hit_and_run_tendency = s.get("hit_and_run", 3)

    # Load pitcher fatigue data to filter out those needing rest
    team = query("SELECT team_strategy_json FROM teams WHERE id=?",
                 (team_id,), db_path=db_path)
    fatigue_data = {}
    if team and team[0].get("team_strategy_json"):
        try:
            strategy = json.loads(team[0]["team_strategy_json"])
            fatigue_data = strategy.get("pitcher_fatigue", {})
        except:
            fatigue_data = {}

    # Get current date for rest calculation
    state = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
    current_date = state[0]["current_date"] if state else "2026-02-15"
    from datetime import datetime
    current = datetime.fromisoformat(current_date).date()

    # Query recent pitching lines from last 3 days for fatigue carryover
    recent_pitching = {}
    try:
        three_days_ago = (current - timedelta(days=3)).isoformat()
        recent_lines = query("""
            SELECT pl.player_id, s.game_date, pl.pitches, pl.ip_outs, pl.is_starter
            FROM pitching_lines pl
            JOIN schedule s ON s.id = pl.schedule_id
            WHERE s.game_date >= ? AND s.game_date < ?
              AND pl.team_id = ?
            ORDER BY s.game_date DESC
        """, (three_days_ago, current.isoformat(), team_id), db_path=db_path)

        for line in recent_lines:
            pid = line["player_id"]
            if pid not in recent_pitching:
                recent_pitching[pid] = []
            game_dt = datetime.fromisoformat(line["game_date"]).date()
            days_ago = (current - game_dt).days
            recent_pitching[pid].append({
                "days_ago": days_ago,
                "pitches": line["pitches"],
                "ip_outs": line["ip_outs"],
                "is_starter": line["is_starter"],
            })
    except Exception:
        recent_pitching = {}

    def _calc_fatigue_modifiers(player_id):
        """Calculate fatigue stuff/control modifiers from recent appearances."""
        if player_id not in recent_pitching:
            return 1.0, 1.0, False
        appearances = recent_pitching[player_id]
        days_pitched = set(app["days_ago"] for app in appearances)
        pitched_yesterday = 1 in days_pitched
        pitched_2_ago = 2 in days_pitched
        games_in_last_3 = len(days_pitched)
        if games_in_last_3 >= 2:
            return 0.80, 0.85, pitched_yesterday
        if pitched_yesterday:
            return 0.85, 0.90, True
        if pitched_2_ago:
            return 0.95, 0.97, False
        return 1.0, 1.0, False

    # Build pitching staff, filtering relievers by rest status
    pitchers = []
    starters = [p for p in pitchers_data if p["position"] == "SP"]
    relievers = [p for p in pitchers_data if p["position"] == "RP"]

    # EMERGENCY: If team has no RPs (e.g. DB hasn't been reseeded after SP/RP fix),
    # convert excess SPs into relievers so the team has a functional bullpen.
    # Keep top 5 SPs as starters, use the rest as emergency relievers.
    if not relievers and len(starters) > 5:
        sorted_sp = sorted(starters, key=lambda p: p["stuff_rating"] + p["control_rating"], reverse=True)
        starters = sorted_sp[:5]
        relievers = sorted_sp[5:]
    elif not relievers and len(starters) > 1:
        # Very few pitchers: keep 1 as starter, rest become relievers
        sorted_sp = sorted(starters, key=lambda p: p["stuff_rating"] + p["control_rating"], reverse=True)
        starters = sorted_sp[:1]
        relievers = sorted_sp[1:]

    # Select today's starter using the rotation system (enforces rest days)
    starter_id = _rotate_starter(team_id, db_path)
    starter_player = None
    if starter_id:
        starter_player = next((p for p in starters if p["id"] == starter_id), None)
    # Fallback: if rotation returned an RP (bullpen day) or unknown ID, find them
    if not starter_player and starter_id:
        starter_player = next((p for p in pitchers_data if p["id"] == starter_id), None)
    # Ultimate fallback: first available SP
    if not starter_player and starters:
        starter_player = starters[0]

    # Add starter
    if starter_player:
        p = starter_player
        # Load pitch repertoire from database instead of hardcoding
        pitch_types = []
        if p.get("pitch_repertoire_json"):
            try:
                repertoire = json.loads(p["pitch_repertoire_json"])
                pitch_types = [(pitch["type"], pitch.get("rating", 50)) for pitch in repertoire]
            except:
                pass
        if not pitch_types:
            pitch_types = [("4SFB", max(50, p["stuff_rating"])), ("SL", max(40, p["control_rating"])), ("CB", max(35, p["control_rating"] - 5))]

        # Apply fatigue carryover modifiers (temporary, not saved to DB)
        s_stuff_mod, s_ctrl_mod, s_pitched_yesterday = _calc_fatigue_modifiers(p["id"])

        pitchers.append(PitcherStats(
            player_id=p["id"],
            name=f"{p['first_name']} {p['last_name']}",
            throws=p["throws"],
            role="starter",
            stuff=p["stuff_rating"],
            control=p["control_rating"],
            stamina=p["stamina_rating"],
            clutch=p["clutch"],
            pitch_types=pitch_types,
            fatigue_stuff_modifier=s_stuff_mod,
            fatigue_control_modifier=s_ctrl_mod,
            pitched_yesterday=s_pitched_yesterday,
        ))

    # Check if starter pitched within last 4 days (starters should NOT be available)
    if starter_player and starter_player["id"] in recent_pitching:
        starter_appearances = recent_pitching[starter_player["id"]]
        recent_start_days = [a["days_ago"] for a in starter_appearances if a["is_starter"]]
        if any(d <= 4 for d in recent_start_days):
            # This starter pitched too recently — skip and find next available
            # The _rotate_starter function should handle this, but as a safety net:
            pass  # Already handled by _rotate_starter's 4-day rest check

    # Add relievers, excluding those who need rest
    available_relievers = []
    fatigued_relievers = []
    for p in relievers:
        reliever_id = p["id"]
        if str(reliever_id) in fatigue_data:
            fatigue = fatigue_data[str(reliever_id)]
            last_game = datetime.fromisoformat(fatigue["last_game_date"]).date()
            rest_needed = fatigue.get("rest_days_needed", 1)
            days_rested = (current - last_game).days
            if days_rested < rest_needed:
                fatigued_relievers.append(p)
                continue  # Skip, still needs rest
        available_relievers.append(p)

    # Use up to 6 available relievers
    selected_relievers = available_relievers[:6]

    # Emergency fallback: if fewer than 6 available, add fatigued relievers (never blank out the bullpen)
    if len(selected_relievers) < 6:
        remaining_slots = 6 - len(selected_relievers)
        selected_relievers.extend(fatigued_relievers[:remaining_slots])

    # Assign bullpen roles based on ratings
    def _assign_reliever_roles(relievers_list):
        """Assign closer/setup/loogy/middle/long roles based on ratings."""
        if not relievers_list:
            return {}
        # Score each reliever by stuff + clutch for role assignment
        scored = [(p, p["stuff_rating"] + p["clutch"]) for p in relievers_list]
        scored.sort(key=lambda x: x[1], reverse=True)

        roles = {}
        loogy_assigned = False

        for i, (p, score) in enumerate(scored):
            pid = p["id"]
            if i == 0:
                roles[pid] = "closer"
            elif i == 1:
                roles[pid] = "setup"
            elif (not loogy_assigned and p["throws"] == "L"
                  and p["stuff_rating"] >= 50):
                roles[pid] = "loogy"
                loogy_assigned = True
            else:
                # Lowest stamina = middle, highest stamina = long
                roles[pid] = None  # placeholder, assigned below

        # Assign middle/long to remaining unassigned
        unassigned = [(p, s) for p, s in scored if roles.get(p["id"]) is None]
        if unassigned:
            unassigned.sort(key=lambda x: x[0]["stamina_rating"])
            for j, (p, s) in enumerate(unassigned):
                if j < len(unassigned) // 2:
                    roles[p["id"]] = "middle"
                else:
                    roles[p["id"]] = "long"
            # Edge case: single unassigned gets "middle"
            for p, s in unassigned:
                if roles.get(p["id"]) is None:
                    roles[p["id"]] = "middle"

        return roles

    reliever_roles = _assign_reliever_roles(selected_relievers)

    for p in selected_relievers:
        # Load pitch repertoire from database instead of hardcoding
        pitch_types = []
        if p.get("pitch_repertoire_json"):
            try:
                repertoire = json.loads(p["pitch_repertoire_json"])
                pitch_types = [(pitch["type"], pitch.get("rating", 50)) for pitch in repertoire]
            except:
                pass
        if not pitch_types:
            pitch_types = [("4SFB", max(50, p["stuff_rating"])), ("SL", max(40, p["control_rating"]))]

        # Apply fatigue carryover modifiers (temporary, not saved to DB)
        r_stuff_mod, r_ctrl_mod, r_pitched_yesterday = _calc_fatigue_modifiers(p["id"])

        pitchers.append(PitcherStats(
            player_id=p["id"],
            name=f"{p['first_name']} {p['last_name']}",
            throws=p["throws"],
            role=reliever_roles.get(p["id"], "middle"),
            stuff=p["stuff_rating"],
            control=p["control_rating"],
            stamina=p["stamina_rating"],
            clutch=p["clutch"],
            pitch_types=pitch_types,
            fatigue_stuff_modifier=r_stuff_mod,
            fatigue_control_modifier=r_ctrl_mod,
            pitched_yesterday=r_pitched_yesterday,
        ))

    # Load per-pitcher custom pitch count limits
    pitcher_ids = [p.player_id for p in pitchers]
    if pitcher_ids:
        placeholders = ",".join(str(pid) for pid in pitcher_ids)
        p_strategies = query(
            f"SELECT player_id, pitch_count_limit FROM player_strategy WHERE player_id IN ({placeholders}) AND pitch_count_limit IS NOT NULL",
            db_path=db_path
        )
        for ps in p_strategies:
            for p in pitchers:
                if p.player_id == ps["player_id"]:
                    p.custom_pitch_count_limit = ps["pitch_count_limit"]

    return lineup, pitchers


def _get_park_factors(team_id: int, db_path: str = None) -> ParkFactors:
    """Load park factors for a team's stadium."""
    team = query("SELECT * FROM teams WHERE id=?", (team_id,), db_path=db_path)
    if not team:
        return ParkFactors()
    t = team[0]
    return ParkFactors.from_stadium(
        t["lf_distance"], t["lcf_distance"], t["cf_distance"],
        t["rcf_distance"], t["rf_distance"],
        bool(t["is_dome"]), t.get("altitude", 0),
        t.get("surface", "grass"), t.get("foul_territory", "average")
    )


def _rotate_starter(team_id: int, db_path: str = None) -> int:
    """Get the next starter in a 5-man rotation, enforcing rest days.

    Rotation order comes from teams.rotation_json (a JSON list of player IDs).
    If rotation_json is not set, the order is determined by stuff+control rating.

    Each starter pitches every 5th day.  If the next man up is injured or
    fatigued (fewer than 4 days rest), skip to the next man in rotation order.
    If *no* starter is available, use the best-rested reliever as a spot start.
    Emergency fallback: most-rested starter even without full rest.
    """
    from datetime import datetime, timedelta as td

    # ------------------------------------------------------------------
    # 1. Build the rotation order
    # ------------------------------------------------------------------
    team_row = query("SELECT rotation_json, team_strategy_json FROM teams WHERE id=?",
                     (team_id,), db_path=db_path)
    rotation_order = None
    fatigue_data = {}
    if team_row:
        # Parse rotation_json
        if team_row[0].get("rotation_json"):
            try:
                rotation_order = json.loads(team_row[0]["rotation_json"])
                if not isinstance(rotation_order, list):
                    rotation_order = None
            except (json.JSONDecodeError, TypeError):
                rotation_order = None
        # Parse fatigue data
        if team_row[0].get("team_strategy_json"):
            try:
                strategy = json.loads(team_row[0]["team_strategy_json"])
                fatigue_data = strategy.get("pitcher_fatigue", {})
            except (json.JSONDecodeError, TypeError):
                fatigue_data = {}

    # Get all active starters with their last-start date
    starters = query("""
        SELECT p.id, p.first_name, p.last_name,
            p.stuff_rating, p.control_rating,
            COALESCE(
                (SELECT MAX(s.game_date) FROM pitching_lines pl
                 JOIN schedule s ON s.id = pl.schedule_id
                 WHERE pl.player_id = p.id AND pl.is_starter = 1),
                '2000-01-01'
            ) as last_start
        FROM players p
        WHERE p.team_id=? AND p.position='SP' AND p.roster_status='active'
        ORDER BY p.stuff_rating + p.control_rating DESC
    """, (team_id,), db_path=db_path)

    if not starters:
        return None

    starter_map = {s["id"]: s for s in starters}

    # If rotation_json is set, filter to only active starters and preserve order
    if rotation_order:
        ordered_ids = [pid for pid in rotation_order if pid in starter_map]
        # Append any active starters not in the stored rotation (new call-ups, etc.)
        for s in starters:
            if s["id"] not in ordered_ids:
                ordered_ids.append(s["id"])
    else:
        # Default order: by stuff + control descending
        ordered_ids = [s["id"] for s in starters]

    # Cap at 5-man rotation
    rotation_ids = ordered_ids[:5]

    # ------------------------------------------------------------------
    # 2. Determine current date
    # ------------------------------------------------------------------
    state = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
    current_date = state[0]["current_date"] if state else "2026-02-15"
    current = datetime.fromisoformat(current_date).date()

    # ------------------------------------------------------------------
    # 3. Find who is "next up" in the rotation
    # ------------------------------------------------------------------
    # The next starter is determined by who has the most days since their
    # last start, in rotation order.  Among starters with >= 4 days rest,
    # we pick the first one in rotation order whose last start is earliest.

    def _days_since_last_start(pid):
        s = starter_map.get(pid)
        if not s:
            return 999
        last = datetime.fromisoformat(s["last_start"]).date()
        return (current - last).days

    # Build list of rested starters in rotation order
    fully_rested = []
    for pid in rotation_ids:
        days_rest = _days_since_last_start(pid)
        # Also check fatigue tracking
        if str(pid) in fatigue_data:
            fatigue = fatigue_data[str(pid)]
            last_game = datetime.fromisoformat(fatigue["last_game_date"]).date()
            days_rest = min(days_rest, (current - last_game).days)
        if days_rest >= 4:
            fully_rested.append((pid, days_rest))

    if fully_rested:
        # Pick the starter with the most rest (longest since last start),
        # breaking ties by rotation order (already in order).
        fully_rested.sort(key=lambda x: -x[1])
        chosen_id = fully_rested[0][0]
        # Persist updated rotation so the *next* call skips past this starter
        _persist_rotation(team_id, rotation_ids, db_path)
        return chosen_id

    # ------------------------------------------------------------------
    # 4. No fully-rested starter — try best-rested reliever (bullpen day)
    # ------------------------------------------------------------------
    relievers = query("""
        SELECT p.id, p.first_name, p.last_name,
            COALESCE(
                (SELECT MAX(s.game_date) FROM pitching_lines pl
                 JOIN schedule s ON s.id = pl.schedule_id
                 WHERE pl.player_id = p.id),
                '2000-01-01'
            ) as last_game
        FROM players p
        WHERE p.team_id=? AND p.position='RP' AND p.roster_status='active'
    """, (team_id,), db_path=db_path)

    if relievers:
        best_rested = None
        most_days = -999
        for reliever in relievers:
            days_since = (current - datetime.fromisoformat(reliever["last_game"]).date()).days
            if days_since > most_days:
                most_days = days_since
                best_rested = reliever
        if best_rested:
            return best_rested["id"]

    # ------------------------------------------------------------------
    # 5. Emergency fallback: most-rested starter regardless of rest
    # ------------------------------------------------------------------
    best_rest_starter = None
    best_rest_days = -999
    for pid in rotation_ids:
        days_rest = _days_since_last_start(pid)
        if str(pid) in fatigue_data:
            fatigue = fatigue_data[str(pid)]
            last_game = datetime.fromisoformat(fatigue["last_game_date"]).date()
            days_rest = min(days_rest, (current - last_game).days)
        if days_rest > best_rest_days:
            best_rest_days = days_rest
            best_rest_starter = pid

    return best_rest_starter if best_rest_starter else starters[0]["id"]


def _persist_rotation(team_id: int, rotation_ids: list, db_path: str = None):
    """Save the current rotation order back to teams.rotation_json."""
    conn = get_connection(db_path)
    conn.execute("UPDATE teams SET rotation_json=? WHERE id=?",
                 (json.dumps(rotation_ids), team_id))
    conn.commit()
    conn.close()


def _load_team_strategy(team_id: int, db_path: str = None) -> dict:
    """Load team strategy settings from the database."""
    team = query("SELECT team_strategy_json FROM teams WHERE id=?",
                 (team_id,), db_path=db_path)
    if team and team[0].get("team_strategy_json"):
        return get_strategy(team[0]["team_strategy_json"])
    return get_strategy()


def _determine_phase(game_date: date, season: int) -> str:
    """Determine the current season phase based on date."""
    month = game_date.month
    day = game_date.day

    if month >= 11 or (month <= 2 and day <= 14):
        return "offseason"
    if month == 2 and day > 14:
        return "spring_training"
    if month == 3 and day < 26:
        return "spring_training"
    if (month == 3 and day >= 26) or (4 <= month <= 8) or (month == 9 and day <= 28):
        return "regular_season"
    if month == 9 and day > 28:
        return "regular_season"
    if month == 10:
        return "postseason"

    return "regular_season"


def is_past_trade_deadline(game_date: date) -> bool:
    """Check if the current date is past the July 31 trade deadline."""
    return game_date.month > 7 or (game_date.month == 7 and game_date.day > 31)


def is_all_star_break(game_date: date) -> bool:
    """Check if the date falls during the All-Star break (July 14-16)."""
    return game_date.month == 7 and 14 <= game_date.day <= 16


def is_all_star_game_day(game_date: date) -> bool:
    """Check if this is the All-Star Game day (July 15)."""
    return game_date.month == 7 and game_date.day == 15


def _generate_key_plays(game_result: dict, home_team_id: int, away_team_id: int) -> list:
    """Generate play-by-play summary focusing on key events."""
    key_plays = []

    # If game engine already has play_by_play data, use it
    if "play_by_play" in game_result and game_result["play_by_play"]:
        return game_result["play_by_play"]

    # Fallback: extract key plays from lineup stats
    home_lineup = game_result.get("home_lineup", [])
    away_lineup = game_result.get("away_lineup", [])
    home_pitchers = game_result.get("home_pitchers", [])
    away_pitchers = game_result.get("away_pitchers", [])

    # Scan all batters for key plays
    for lineup, team_id in [(home_lineup, home_team_id), (away_lineup, away_team_id)]:
        for batter in lineup:
            # Home runs (most important)
            if batter.hr > 0:
                for _ in range(batter.hr):
                    key_plays.append({
                        "type": "HR",
                        "player": batter.name,
                        "team_id": team_id,
                        "inning": None,
                    })
            # Strikeouts (mark important outs)
            if batter.so > 0:
                for _ in range(batter.so):
                    key_plays.append({
                        "type": "SO",
                        "player": batter.name,
                        "team_id": team_id,
                    })
            # Stolen bases
            if batter.sb > 0:
                for _ in range(batter.sb):
                    key_plays.append({
                        "type": "SB",
                        "player": batter.name,
                        "team_id": team_id,
                    })
            # Reached on error
            if batter.reached_on_error > 0:
                for _ in range(batter.reached_on_error):
                    key_plays.append({
                        "type": "ROE",
                        "player": batter.name,
                        "team_id": team_id,
                    })

    # Scan pitchers for changes and key moments
    for pitchers, team_id in [(home_pitchers, home_team_id), (away_pitchers, away_team_id)]:
        for i, pitcher in enumerate(pitchers):
            if i > 0 and pitcher.ip_outs > 0:  # Relief pitcher who threw
                key_plays.append({
                    "type": "PITCHING_CHANGE",
                    "player": pitcher.name,
                    "team_id": team_id,
                })

    # Bench usage events (pinch hitters and defensive substitutions)
    bench_usage = game_result.get("bench_usage", {})
    for side, team_id in [("home_subbed_out", home_team_id), ("away_subbed_out", away_team_id)]:
        for sub in bench_usage.get(side, []):
            key_plays.append({
                "type": "SUBSTITUTION",
                "player": sub["name"],
                "team_id": team_id,
                "description": f"{sub['name']} removed ({sub['position']})",
            })

    return key_plays


def _initialize_pitcher_fatigue(team_id: int, db_path: str = None):
    """Create or initialize fatigue tracking for a team."""
    conn = get_connection(db_path)
    team = conn.execute("SELECT team_strategy_json FROM teams WHERE id=?",
                       (team_id,)).fetchone()
    if not team:
        return

    strategy_json = team["team_strategy_json"] or "{}"
    try:
        strategy = json.loads(strategy_json)
    except:
        strategy = {}

    if "pitcher_fatigue" not in strategy:
        strategy["pitcher_fatigue"] = {}

    conn.execute("UPDATE teams SET team_strategy_json=? WHERE id=?",
                (json.dumps(strategy), team_id))
    conn.commit()
    conn.close()


def _update_pitcher_rest(game_date: str, db_path: str = None):
    """Update pitcher rest days after each game."""
    conn = get_connection(db_path)

    # Get all games played today
    games = query("""
        SELECT gr.id, pl.player_id, pl.ip_outs, pl.pitches, s.home_team_id, s.away_team_id
        FROM game_results gr
        JOIN pitching_lines pl ON pl.schedule_id = gr.schedule_id
        JOIN schedule s ON s.id = gr.schedule_id
        WHERE s.game_date = ?
    """, (game_date,), db_path=db_path)

    for game in games:
        pitcher_id = game["player_id"]
        pitches = game["pitches"]
        ip_outs = game["ip_outs"]

        # Determine rest needed (strict enforcement)
        if ip_outs >= 15:  # 5+ innings (starter)
            rest_needed = 4  # Starters must have 4 days rest minimum
            if pitches > 110:
                rest_needed = 5  # Extra day if very high pitch count
        elif pitches >= 45:  # heavy reliever use (45+ pitches)
            rest_needed = 2  # 2 days rest for heavy use
        elif pitches >= 30:  # moderate reliever use (30-44 pitches)
            rest_needed = 1  # 1 day rest for moderate use
        else:
            rest_needed = 0  # Light use, no rest required

        if rest_needed > 0:
            # Store last game date in team strategy for this pitcher
            teams = [game["home_team_id"], game["away_team_id"]]
            for team_id in teams:
                team_row = conn.execute("SELECT team_strategy_json FROM teams WHERE id=?",
                                       (team_id,)).fetchone()
                if not team_row:
                    continue

                strategy_json = team_row["team_strategy_json"] or "{}"
                try:
                    strategy = json.loads(strategy_json)
                except:
                    strategy = {}

                if "pitcher_fatigue" not in strategy:
                    strategy["pitcher_fatigue"] = {}

                strategy["pitcher_fatigue"][str(pitcher_id)] = {
                    "last_game_date": game_date,
                    "rest_days_needed": rest_needed,
                    "pitches_thrown": pitches,
                }

                conn.execute("UPDATE teams SET team_strategy_json=? WHERE id=?",
                            (json.dumps(strategy), team_id))

    conn.commit()
    conn.close()


def sim_spring_training_day(game_date: str, db_path: str = None) -> list:
    """Simulate spring training exhibition games. Stats don't count for regular season.
    Each team plays ~30 spring training games (roughly 1 game/day from Feb 22 - Mar 25).
    Games use full simulation but results aren't saved to batting_stats/pitching_stats.
    """
    import random as _st_random

    parsed_date = date.fromisoformat(game_date)

    # Spring training games: ~70% chance each team plays on any given day
    teams = query("SELECT id FROM teams", db_path=db_path)
    team_ids = [t["id"] for t in teams]
    _st_random.shuffle(team_ids)

    # Pair up teams for exhibition games
    playing_teams = [tid for tid in team_ids if _st_random.random() < 0.70]
    if len(playing_teams) % 2 == 1:
        playing_teams.pop()  # Even it out

    results = []
    conn = get_connection(db_path)

    for i in range(0, len(playing_teams), 2):
        home_id = playing_teams[i]
        away_id = playing_teams[i + 1]

        home_lineup, home_pitchers = _load_team_lineup(home_id, db_path)
        away_lineup, away_pitchers = _load_team_lineup(away_id, db_path)

        if not home_lineup or not away_lineup or not home_pitchers or not away_pitchers:
            continue

        park = _get_park_factors(home_id, db_path)
        home_strategy = _load_team_strategy(home_id, db_path)
        away_strategy = _load_team_strategy(away_id, db_path)

        try:
            result = simulate_game(
                home_lineup, away_lineup,
                home_pitchers, away_pitchers,
                park,
                home_strategy=home_strategy,
                away_strategy=away_strategy
            )

            home_info = query("SELECT city, name, abbreviation FROM teams WHERE id=?",
                            (home_id,), db_path=db_path)
            away_info = query("SELECT city, name, abbreviation FROM teams WHERE id=?",
                            (away_id,), db_path=db_path)

            results.append({
                "date": game_date,
                "type": "spring_training",
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_team": f"{home_info[0]['city']} {home_info[0]['name']}" if home_info else str(home_id),
                "away_team": f"{away_info[0]['city']} {away_info[0]['name']}" if away_info else str(away_id),
                "home_abbreviation": home_info[0]["abbreviation"] if home_info else "",
                "away_abbreviation": away_info[0]["abbreviation"] if away_info else "",
                "home_score": result["home_score"],
                "away_score": result["away_score"],
                "innings": result.get("innings_played", 9),
            })
        except Exception:
            continue

    conn.close()
    return results


def auto_trim_roster_for_opening_day(db_path: str = None):
    """Auto-trim all teams to 26-man active rosters for Opening Day.
    Options excess players to minors, prioritizing keeping higher-rated players.
    Only runs for AI teams (not user's team — user gets a notification instead).
    """
    state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
    user_team_id = state[0]["user_team_id"] if state else None

    teams = query("SELECT id, city, name FROM teams", db_path=db_path)
    trimmed = []

    for team in teams:
        team_id = team["id"]
        if team_id == user_team_id:
            continue  # User manages their own roster

        active = query("""
            SELECT p.id, p.first_name, p.last_name, p.position, p.overall,
                   p.option_years_remaining
            FROM players p
            WHERE p.team_id=? AND p.roster_status='active'
            ORDER BY p.overall ASC
        """, (team_id,), db_path=db_path)

        excess = len(active) - 26
        if excess <= 0:
            continue

        # Option the lowest-rated players with option years remaining
        optioned = []
        for player in active:
            if excess <= 0:
                break
            if player.get("option_years_remaining", 0) and player["option_years_remaining"] > 0:
                execute("""
                    UPDATE players SET roster_status='minors_aaa',
                    option_years_remaining = option_years_remaining - 1
                    WHERE id=?
                """, (player["id"],), db_path=db_path)
                optioned.append(f"{player['first_name']} {player['last_name']}")
                excess -= 1

        if optioned:
            trimmed.append({
                "team": f"{team['city']} {team['name']}",
                "team_id": team_id,
                "optioned": optioned
            })

    return trimmed


def sim_day(game_date: str = None, db_path: str = None) -> list:
    """Simulate all games for a given date. Returns list of results."""
    if game_date is None:
        state = query("SELECT current_date FROM game_state WHERE id=1", db_path=db_path)
        game_date = state[0]["current_date"]

    parsed_date = date.fromisoformat(game_date)
    phase = _determine_phase(parsed_date, parsed_date.year)
    if phase == "spring_training":
        return []

    # All-Star break: no regular season games July 14-16
    if is_all_star_break(parsed_date):
        return []

    # Check for September 1 (expansion to 28-man roster)
    is_september = parsed_date.month == 9 and parsed_date.day >= 1

    games = query("""
        SELECT * FROM schedule
        WHERE game_date=? AND is_played=0 AND is_postseason=0
    """, (game_date,), db_path=db_path)

    results = []
    conn = get_connection(db_path)

    for game in games:
        home_id = game["home_team_id"]
        away_id = game["away_team_id"]

        # First pass: load pitchers to determine starter handedness
        home_lineup, home_pitchers = _load_team_lineup(home_id, db_path)
        away_lineup, away_pitchers = _load_team_lineup(away_id, db_path)

        # Auto-platoon: reload lineups optimized against opposing starter's hand
        home_starter_throws = home_pitchers[0].throws if home_pitchers else "R"
        away_starter_throws = away_pitchers[0].throws if away_pitchers else "R"
        away_lineup, _ = _load_team_lineup(away_id, db_path, opposing_pitcher_throws=home_starter_throws)
        home_lineup, _ = _load_team_lineup(home_id, db_path, opposing_pitcher_throws=away_starter_throws)

        park = _get_park_factors(home_id, db_path)

        # September callups: expand active roster temporarily
        if is_september:
            # Load additional minor leaguers as callups
            callup_limit = 2
            home_callups = query("""
                SELECT p.*, c.annual_salary FROM players p
                LEFT JOIN contracts c ON c.player_id = p.id
                WHERE p.team_id=? AND p.roster_status LIKE 'minors%'
                AND p.position NOT IN ('SP', 'RP')
                ORDER BY p.power_rating + p.contact_rating DESC
                LIMIT ?
            """, (home_id, callup_limit), db_path=db_path)

            for callup in home_callups:
                if callup["position"] not in ("SP", "RP"):
                    home_lineup.append(BatterStats(
                        player_id=callup["id"],
                        name=f"{callup['first_name']} {callup['last_name']}",
                        position=callup["position"],
                        batting_order=len(home_lineup) + 1,
                        bats=callup["bats"],
                        contact=callup["contact_rating"],
                        power=callup["power_rating"],
                        speed=callup["speed_rating"],
                        clutch=callup["clutch"],
                        fielding=callup["fielding_rating"],
                        eye=callup.get("eye_rating", 50),
                        height_inches=callup.get("height_inches") or 73,
                    ))

            # Away team callups too
            away_callups = query("""
                SELECT p.*, c.annual_salary FROM players p
                LEFT JOIN contracts c ON c.player_id = p.id
                WHERE p.team_id=? AND p.roster_status LIKE 'minors%%'
                AND p.position NOT IN ('SP', 'RP')
                ORDER BY p.power_rating + p.contact_rating DESC
                LIMIT ?
            """, (away_id, callup_limit), db_path=db_path)

            for callup in away_callups:
                if callup["position"] not in ("SP", "RP"):
                    away_lineup.append(BatterStats(
                        player_id=callup["id"],
                        name=f"{callup['first_name']} {callup['last_name']}",
                        position=callup["position"],
                        batting_order=len(away_lineup) + 1,
                        bats=callup["bats"],
                        contact=callup["contact_rating"],
                        power=callup["power_rating"],
                        speed=callup["speed_rating"],
                        clutch=callup["clutch"],
                        fielding=callup["fielding_rating"],
                        eye=callup.get("eye_rating", 50),
                        height_inches=callup.get("height_inches") or 73,
                    ))

        if not home_lineup or not away_lineup or not home_pitchers or not away_pitchers:
            continue

        home_strategy = _load_team_strategy(home_id, db_path)
        away_strategy = _load_team_strategy(away_id, db_path)

        # Load team chemistry scores
        home_chemistry = calculate_team_chemistry(home_id, db_path)
        away_chemistry = calculate_team_chemistry(away_id, db_path)

        # Phase 5: compute analytics integration modifiers
        from ..ai.analytics_integration import (
            calculate_chemistry_performance_bonus,
            calculate_relationship_defense_effects,
        )
        home_analytics = {
            "chemistry_bonus": calculate_chemistry_performance_bonus(home_id, db_path),
            "defense_effects": calculate_relationship_defense_effects(home_id, db_path),
        }
        away_analytics = {
            "chemistry_bonus": calculate_chemistry_performance_bonus(away_id, db_path),
            "defense_effects": calculate_relationship_defense_effects(away_id, db_path),
        }

        result = simulate_game(
            home_lineup, away_lineup,
            home_pitchers, away_pitchers,
            park, home_id, away_id,
            home_strategy, away_strategy,
            home_chemistry=home_chemistry, away_chemistry=away_chemistry,
            home_analytics=home_analytics, away_analytics=away_analytics,
        )

        # Save to database
        conn.execute("""
            UPDATE schedule SET is_played=1, home_score=?, away_score=?
            WHERE id=?
        """, (result["home_score"], result["away_score"], game["id"]))

        # Generate key plays for play-by-play
        key_plays = _generate_key_plays(result, home_id, away_id)

        # Save game result with play-by-play
        conn.execute("""
            INSERT INTO game_results (schedule_id, innings_json, play_by_play_json,
                winning_pitcher_id, losing_pitcher_id, save_pitcher_id, attendance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            game["id"],
            json.dumps([result["innings_away"], result["innings_home"]]),
            json.dumps(key_plays),
            next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "W"), None),
            next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "L"), None),
            next((p.player_id for p in result["home_pitchers"] + result["away_pitchers"] if p.decision == "S"), None),
            _estimate_attendance(home_id, db_path),
        ))

        # Save batting lines
        for lineup, team_id in [(result["home_lineup"], home_id), (result["away_lineup"], away_id)]:
            for b in lineup:
                conn.execute("""
                    INSERT INTO batting_lines (schedule_id, player_id, team_id,
                        batting_order, position_played, ab, runs, hits, doubles,
                        triples, hr, rbi, bb, so, sb, cs, hbp, sf)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (game["id"], b.player_id, team_id, b.batting_order,
                      b.position, b.ab, b.runs, b.hits, b.doubles, b.triples,
                      b.hr, b.rbi, b.bb, b.so, b.sb, b.cs, b.hbp, b.sf))

                conn.execute("""
                    INSERT INTO batting_stats (player_id, team_id, season, level, games,
                        pa, ab, runs, hits, doubles, triples, hr, rbi, bb, so, sb, cs, hbp, sf)
                    VALUES (?, ?, ?, 'MLB', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(player_id, team_id, season, level) DO UPDATE SET
                        games = games + 1,
                        pa = pa + excluded.pa,
                        ab = ab + excluded.ab,
                        runs = runs + excluded.runs,
                        hits = hits + excluded.hits,
                        doubles = doubles + excluded.doubles,
                        triples = triples + excluded.triples,
                        hr = hr + excluded.hr,
                        rbi = rbi + excluded.rbi,
                        bb = bb + excluded.bb,
                        so = so + excluded.so,
                        sb = sb + excluded.sb,
                        cs = cs + excluded.cs,
                        hbp = hbp + excluded.hbp,
                        sf = sf + excluded.sf
                """, (b.player_id, team_id, game["season"],
                      b.ab + b.bb + b.hbp + b.sf,
                      b.ab, b.runs, b.hits, b.doubles, b.triples,
                      b.hr, b.rbi, b.bb, b.so, b.sb, b.cs, b.hbp, b.sf))

        # Save pitching lines
        for pitchers, team_id, opp_score in [
            (result["home_pitchers"], home_id, result["away_score"]),
            (result["away_pitchers"], away_id, result["home_score"])
        ]:
            # Determine CG/SHO/QS for the starter
            starter = next((p for p in pitchers if p.is_starter), None)
            relievers_used = sum(1 for p in pitchers if not p.is_starter and p.ip_outs > 0)
            total_game_outs = sum(p.ip_outs for p in pitchers)

            for p in pitchers:
                if p.ip_outs == 0 and p.pitches == 0:
                    continue

                # Calculate CG, SHO, QS for starters
                is_cg = 0
                is_sho = 0
                is_qs = 0
                if p.is_starter:
                    # Complete game: starter recorded all outs (no relievers used)
                    if relievers_used == 0 and p.ip_outs >= 27:
                        is_cg = 1
                        # Shutout: complete game with 0 runs allowed
                        if p.runs_allowed == 0:
                            is_sho = 1
                    # Quality start: 6+ IP (18+ outs) and 3 or fewer ER
                    if p.ip_outs >= 18 and p.er <= 3:
                        is_qs = 1

                conn.execute("""
                    INSERT INTO pitching_lines (schedule_id, player_id, team_id,
                        pitch_order, ip_outs, hits_allowed, runs_allowed, er,
                        bb, so, hr_allowed, pitches, is_starter, decision)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (game["id"], p.player_id, team_id, p.pitch_order,
                      p.ip_outs, p.hits_allowed, p.runs_allowed, p.er,
                      p.bb_allowed, p.so_pitched, p.hr_allowed, p.pitches,
                      1 if p.is_starter else 0, p.decision))

                conn.execute("""
                    INSERT INTO pitching_stats (player_id, team_id, season, level, games,
                        games_started, wins, losses, saves, holds, ip_outs,
                        hits_allowed, runs_allowed, er, bb, so, hr_allowed, pitches,
                        complete_games, shutouts, quality_starts)
                    VALUES (?, ?, ?, 'MLB', 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(player_id, team_id, season, level) DO UPDATE SET
                        games = games + 1,
                        games_started = games_started + excluded.games_started,
                        wins = wins + excluded.wins,
                        losses = losses + excluded.losses,
                        saves = saves + excluded.saves,
                        holds = holds + excluded.holds,
                        ip_outs = ip_outs + excluded.ip_outs,
                        hits_allowed = hits_allowed + excluded.hits_allowed,
                        runs_allowed = runs_allowed + excluded.runs_allowed,
                        er = er + excluded.er,
                        bb = bb + excluded.bb,
                        so = so + excluded.so,
                        hr_allowed = hr_allowed + excluded.hr_allowed,
                        pitches = pitches + excluded.pitches,
                        complete_games = complete_games + excluded.complete_games,
                        shutouts = shutouts + excluded.shutouts,
                        quality_starts = quality_starts + excluded.quality_starts
                """, (p.player_id, team_id, game["season"],
                      1 if p.is_starter else 0,
                      1 if p.decision == "W" else 0,
                      1 if p.decision == "L" else 0,
                      1 if p.decision == "S" else 0,
                      1 if p.decision == "H" else 0,
                      p.ip_outs, p.hits_allowed, p.runs_allowed, p.er,
                      p.bb_allowed, p.so_pitched, p.hr_allowed, p.pitches,
                      is_cg, is_sho, is_qs))

        # Save pitch log entries
        pitch_log = result.get("pitch_log", [])
        for pl in pitch_log:
            conn.execute("""
                INSERT INTO pitch_log (game_id, inning, at_bat_num, pitch_num,
                    pitcher_id, batter_id, pitch_type, velocity, result, zone,
                    count_balls, count_strikes, outs, runners_on, score_diff, season)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (game["id"], pl["inning"], pl["at_bat_num"], pl["pitch_num"],
                  pl["pitcher_id"], pl["batter_id"], pl["pitch_type"], pl["velocity"],
                  pl["result"], pl["zone"], pl["count_balls"], pl["count_strikes"],
                  pl["outs"], pl["runners_on"], pl["score_diff"], game["season"]))

        # Save matchup stats (head-to-head batter vs pitcher)
        matchup_data = result.get("matchup_data", {})
        for (batter_id, pitcher_id), mstats in matchup_data.items():
            conn.execute("""
                INSERT INTO matchup_stats (batter_id, pitcher_id, season, pa, ab, h,
                    doubles, triples, hr, rbi, bb, so, hbp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(batter_id, pitcher_id, season) DO UPDATE SET
                    pa = pa + excluded.pa,
                    ab = ab + excluded.ab,
                    h = h + excluded.h,
                    doubles = doubles + excluded.doubles,
                    triples = triples + excluded.triples,
                    hr = hr + excluded.hr,
                    rbi = rbi + excluded.rbi,
                    bb = bb + excluded.bb,
                    so = so + excluded.so,
                    hbp = hbp + excluded.hbp
            """, (batter_id, pitcher_id, game["season"],
                  mstats["pa"], mstats["ab"], mstats["h"],
                  mstats["doubles"], mstats["triples"], mstats["hr"],
                  mstats["rbi"], mstats["bb"], mstats["so"], mstats["hbp"]))

        results.append({
            "schedule_id": game["id"],
            "home_team_id": home_id,
            "away_team_id": away_id,
            "home_score": result["home_score"],
            "away_score": result["away_score"],
            "innings": len(result["innings_away"]),
        })

    conn.commit()
    conn.close()

    # Update pitcher fatigue AFTER pitching_lines are committed to the database
    _update_pitcher_rest(game_date, db_path)

    # Update morale for both teams after game (after closing main connection)
    for result_item in results:
        update_player_morale(result_item["home_team_id"], db_path)
        update_player_morale(result_item["away_team_id"], db_path)

    # Update team chemistry after games
    for result_item in results:
        update_team_chemistry(result_item["home_team_id"], db_path)
        update_team_chemistry(result_item["away_team_id"], db_path)

    # Phase 5: streak-driven morale adjustments
    from ..ai.analytics_integration import update_streak_morale
    for result_item in results:
        update_streak_morale(result_item["home_team_id"], db_path)
        update_streak_morale(result_item["away_team_id"], db_path)

    return results


def _estimate_attendance(team_id: int, db_path: str = None) -> int:
    """Estimate game attendance using dynamic attendance model."""
    from ..financial.economics import calculate_dynamic_attendance
    game_state = query("SELECT season FROM game_state WHERE id=1", db_path=db_path)
    season = game_state[0]["season"] if game_state else 2026
    result = calculate_dynamic_attendance(team_id, season, db_path)
    return result["attendance"]


def advance_date(days: int = 1, db_path: str = None) -> dict:
    """Advance the sim by N days, playing all games along the way."""
    state = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
    if not state:
        return {"error": "No game state found"}

    current = date.fromisoformat(state[0]["current_date"])
    season = state[0]["season"]
    all_results = []
    spring_training_results = []
    waiver_outcomes = []
    ai_trade_events = []
    offseason_events = []
    playoff_results = []

    last_phase = _determine_phase(current, season)

    for d in range(days):
        game_date_obj = current + timedelta(days=d)
        game_date = game_date_obj.isoformat()

        phase = _determine_phase(game_date_obj, season)
        execute("UPDATE game_state SET phase=? WHERE id=1",
                (phase,), db_path=db_path)

        # Detect transition from spring training to regular season
        if last_phase == "spring_training" and phase == "regular_season":
            trim_results = auto_trim_roster_for_opening_day(db_path)
            if trim_results:
                offseason_events.append({
                    "type": "opening_day_roster_trim",
                    "teams_trimmed": trim_results
                })

        # Detect transition from regular season to postseason
        if last_phase == "regular_season" and phase == "postseason":
            # Evaluate GM performance at end of regular season
            try:
                from ..ai.owner_pressure import evaluate_gm_performance, check_firing
                user_state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
                if user_state and user_state[0]["user_team_id"]:
                    eval_result = evaluate_gm_performance(user_state[0]["user_team_id"], db_path)
                    fire_check = check_firing(user_state[0]["user_team_id"], db_path)
                    offseason_events.append({
                        "type": "gm_evaluation",
                        "evaluation": eval_result,
                        "firing_status": fire_check
                    })
            except Exception as e:
                offseason_events.append({"type": "gm_evaluation_error", "error": str(e)})

            # Calculate season awards at the end of regular season
            from .awards import calculate_season_awards
            try:
                calculate_season_awards(season, db_path)
                offseason_events.append({"type": "awards_calculated", "season": season})
            except Exception as e:
                offseason_events.append({"type": "awards_error", "error": str(e)})

            # Recalibrate ratings to prevent drift
            try:
                from ..api.routes import recalibrate_ratings as _recal
                import asyncio
                # Can't await in sync context, so do it directly
                from ..database.db import get_connection as _get_conn
                import math as _math
                _conn = _get_conn(db_path)
                _rating_cols = ["contact_rating", "power_rating", "speed_rating",
                               "fielding_rating", "arm_rating", "eye_rating",
                               "stuff_rating", "control_rating", "stamina_rating"]
                for _col in _rating_cols:
                    _is_pitching = _col in ("stuff_rating", "control_rating", "stamina_rating")
                    _pos_filter = "IN ('SP', 'RP')" if _is_pitching else "NOT IN ('SP', 'RP')"
                    _rows = _conn.execute(
                        f"SELECT {_col} FROM players WHERE roster_status='active' AND position {_pos_filter}"
                    ).fetchall()
                    if not _rows:
                        continue
                    _vals = [r[0] for r in _rows]
                    _n = len(_vals)
                    _mean = sum(_vals) / _n
                    _var = sum((v - _mean) ** 2 for v in _vals) / _n
                    _std = _math.sqrt(_var) if _var > 0 else 10
                    if abs(_mean - 50) > 1 or abs(_std - 10) > 1:
                        for _r in _conn.execute(
                            f"SELECT id, {_col} FROM players WHERE roster_status='active' AND position {_pos_filter}"
                        ).fetchall():
                            _z = (_r[1] - _mean) / _std if _std > 0 else 0
                            _new = max(20, min(80, round(50 + _z * 10)))
                            if _new != _r[1]:
                                _conn.execute(f"UPDATE players SET {_col}=? WHERE id=?", (_new, _r[0]))
                _conn.commit()
                _conn.close()
                offseason_events.append({"type": "ratings_recalibrated", "season": season})
            except Exception as e:
                offseason_events.append({"type": "recalibration_error", "error": str(e)})

        if phase == "offseason":
            from .offseason import process_offseason_day
            off_result = process_offseason_day(game_date, season, db_path)
            offseason_events.append(off_result)
        elif phase == "spring_training":
            # Spring training: exhibition games (stats don't count)
            st_results = sim_spring_training_day(game_date, db_path)
            spring_training_results.extend(st_results)

            # Simulate minor league games during spring training
            from .minor_leagues import simulate_all_milb_day
            try:
                simulate_all_milb_day(game_date, season, db_path)
            except Exception:
                pass  # Don't let MiLB errors block main sim
        elif phase == "postseason":
            # Handle playoff advancement
            from .playoffs import advance_playoff_round, get_playoff_bracket, generate_playoff_bracket

            # Check if bracket exists; if not, generate it
            existing_bracket = query("SELECT COUNT(*) as cnt FROM playoff_bracket WHERE season=?",
                                    (season,), db_path=db_path)
            if existing_bracket[0]["cnt"] == 0:
                # First day of postseason, generate bracket
                generate_playoff_bracket(season, db_path)

            playoff_round_result = advance_playoff_round(season, db_path)
            playoff_results.append(playoff_round_result)
        else:
            # Process injuries and IL management before simulating games
            from .injuries import check_injuries_for_day
            from ..transactions.roster import auto_manage_injured_list
            check_injuries_for_day(game_date, db_path)
            auto_manage_injured_list(game_date, db_path)

            # All-Star Game on July 15
            if is_all_star_game_day(game_date_obj):
                from .awards import simulate_all_star_game
                try:
                    asg_result = simulate_all_star_game(season, db_path)
                    offseason_events.append({"type": "all_star_game", **asg_result})
                except Exception as e:
                    offseason_events.append({"type": "all_star_error", "error": str(e)})

            day_results = sim_day(game_date, db_path)
            all_results.extend(day_results)

            from ..transactions.waivers import process_waivers
            waivers = process_waivers(game_date, db_path)
            if waivers:
                waiver_outcomes.extend(waivers)

            if phase == "regular_season":
                from ..transactions.ai_trades import process_ai_trades
                ai_trades = process_ai_trades(game_date, db_path)
                if ai_trades:
                    ai_trade_events.extend(ai_trades)

                # Check for trading block offers (uses improved system from ai_trades)
                from ..transactions.ai_trades import process_trading_block_offers
                trading_offers = process_trading_block_offers(game_date, db_path)
                if trading_offers:
                    ai_trade_events.extend([{"type": "trading_block_offer", "offer": o} for o in trading_offers])

                # Owner pressure messages on the 1st of each month
                if game_date_obj.day == 1:
                    try:
                        from ..ai.owner_pressure import send_owner_pressure_messages
                        user_state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
                        if user_state and user_state[0]["user_team_id"]:
                            owner_msgs = send_owner_pressure_messages(
                                user_state[0]["user_team_id"], game_date, db_path
                            )
                            if owner_msgs:
                                offseason_events.extend([{"type": "owner_pressure", **m} for m in owner_msgs])
                    except Exception:
                        pass

                # Minor league promotion checks on the 1st of each month
                if game_date_obj.day == 1:
                    try:
                        from .minor_leagues import milb_promotions_check
                        all_teams = query("SELECT id FROM teams", db_path=db_path)
                        for t in all_teams:
                            milb_promotions_check(t["id"], season, game_date, db_path)
                    except Exception:
                        pass

            # Simulate minor league games during regular season
            from .minor_leagues import simulate_all_milb_day
            try:
                simulate_all_milb_day(game_date, season, db_path)
            except Exception:
                pass  # Don't let MiLB errors block main sim

            # Weekly podcast generation (every 7 days during regular season)
            if phase == "regular_season" and game_date_obj.weekday() == 0:  # Mondays
                try:
                    from ..ai.podcast import should_generate_podcast, generate_weekly_podcast
                    if should_generate_podcast(game_date, season, db_path):
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                import concurrent.futures
                                with concurrent.futures.ThreadPoolExecutor() as pool:
                                    pool.submit(
                                        asyncio.run,
                                        generate_weekly_podcast(game_date, season, db_path)
                                    ).result(timeout=60)
                            else:
                                loop.run_until_complete(
                                    generate_weekly_podcast(game_date, season, db_path)
                                )
                        except RuntimeError:
                            asyncio.run(
                                generate_weekly_podcast(game_date, season, db_path)
                            )
                except Exception:
                    pass  # Don't let podcast errors block sim

        last_phase = phase

    new_date = (current + timedelta(days=days)).isoformat()
    new_date_obj = current + timedelta(days=days)
    final_phase = _determine_phase(new_date_obj, season)
    execute("UPDATE game_state SET current_date=?, phase=?, current_hour=8 WHERE id=1",
            (new_date, final_phase), db_path=db_path)

    result = {
        "new_date": new_date,
        "phase": final_phase,
        "games_played": len(all_results),
        "results": all_results,
    }

    if spring_training_results:
        result["spring_training"] = spring_training_results
    if waiver_outcomes:
        result["waiver_outcomes"] = waiver_outcomes
    if ai_trade_events:
        result["ai_trades"] = ai_trade_events
    if offseason_events:
        result["offseason"] = offseason_events
    if playoff_results:
        result["playoffs"] = playoff_results

    return result



# process_trading_block_offers has been moved to src/transactions/ai_trades.py
# for better organization with all trade logic in one module.
