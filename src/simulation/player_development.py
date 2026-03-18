"""
Front Office - Player Development System
Handles aging, development curves, decline, and defensive spectrum shifts.

Development model:
- Young players (< peak_age) improve toward their potential ratings
- Players at peak maintain or slowly decline
- Players past peak decline with position-specific curves
- Development rate affected by: work_ethic, farm_system_budget, coaching
- Non-linear events: busts, late bloomers, breakout seasons
- Injuries have permanent impacts on development (Tommy John, ACL, etc.)
- Older players shift to easier defensive positions
"""
import random
from ..database.db import get_connection, query
from .minor_league_parks import get_park_factors, NEUTRAL_PARK


# ---------------------------------------------------------------------------
# Injury keys from injuries.py that cause permanent rating loss
# ---------------------------------------------------------------------------
MAJOR_INJURY_IMPACTS = {
    # Tommy John / UCL injuries: stuff and stamina loss
    "UCL tear (Tommy John)": {"stuff_rating": (-6, -3), "stamina_rating": (-2, -2)},
    "UCL sprain": {"stuff_rating": (-4, -2), "stamina_rating": (-1, -1)},
    # Rotator cuff: severe stuff loss
    "Rotator cuff tear": {"stuff_rating": (-8, -4)},
    "Rotator cuff strain": {"stuff_rating": (-4, -2)},
    # ACL: speed and fielding loss
    "Torn ACL": {"speed_rating": (-10, -5), "fielding_rating": (-2, -2)},
    # Back injuries: power loss
    "Lumbar disc issue": {"power_rating": (-4, -2)},
    "Lower back strain": {"power_rating": (-2, -1)},
    # Labrum: stuff loss (shoulder)
    "Labrum tear": {"stuff_rating": (-5, -3)},
    # Achilles: speed loss
    "Achilles tendon tear": {"speed_rating": (-6, -3)},
}

# Position-weighted breakout ratings: which ratings are most likely to pop
# for each position group
BREAKOUT_WEIGHTS = {
    # Corner infielders/outfielders: power-weighted
    "1B": {"power_rating": 4, "contact_rating": 2, "fielding_rating": 1},
    "3B": {"power_rating": 3, "contact_rating": 2, "fielding_rating": 1, "arm_rating": 1},
    "LF": {"power_rating": 4, "contact_rating": 2, "speed_rating": 1},
    "RF": {"power_rating": 3, "contact_rating": 2, "arm_rating": 1, "speed_rating": 1},
    # Middle infielders: contact-weighted
    "2B": {"contact_rating": 4, "fielding_rating": 2, "speed_rating": 1},
    "SS": {"contact_rating": 3, "fielding_rating": 3, "speed_rating": 1, "arm_rating": 1},
    # Catcher: contact + fielding
    "C":  {"contact_rating": 3, "fielding_rating": 3, "arm_rating": 2},
    # Center field: speed + contact
    "CF": {"speed_rating": 3, "contact_rating": 2, "fielding_rating": 2},
    # DH: pure offense
    "DH": {"power_rating": 4, "contact_rating": 3},
    # Pitchers: stuff-weighted
    "SP": {"stuff_rating": 4, "control_rating": 2, "stamina_rating": 1},
    "RP": {"stuff_rating": 4, "control_rating": 3},
}


def develop_players(season: int, db_path: str = None) -> list:
    """
    Public alias for process_offseason_development.
    Run player development for all players at end of season.
    """
    return process_offseason_development(season, db_path)


def process_offseason_development(season: int, db_path: str = None) -> list:
    """
    Run player development for all players at end of season.
    Called during offseason processing.
    Returns list of notable development changes.
    """
    conn = get_connection(db_path)
    events = []

    # Ensure development columns exist
    _ensure_dev_columns(conn)

    # Generate simulated minor league stats for players without MLB stats
    # so performance-based development works for prospects too
    _generate_minor_league_stats(season, conn)

    players = conn.execute("""
        SELECT p.*, t.farm_system_budget
        FROM players p
        LEFT JOIN teams t ON t.id = p.team_id
        WHERE p.roster_status != 'retired' AND p.roster_status != 'free_agent'
    """).fetchall()

    for p in players:
        changes = _develop_player(dict(p), conn)
        if changes:
            events.append(changes)

    # Age all players by 1
    conn.execute("UPDATE players SET age = age + 1 WHERE roster_status != 'retired'")

    conn.commit()
    conn.close()
    return events


def _ensure_dev_columns(conn):
    """Add is_bust / is_late_bloomer columns if they don't exist yet."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(players)")
    columns = {row[1] for row in cursor.fetchall()}
    if "is_bust" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN is_bust INTEGER NOT NULL DEFAULT 0")
    if "is_late_bloomer" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN is_late_bloomer INTEGER NOT NULL DEFAULT 0")


def _generate_minor_league_stats(season: int, conn):
    """Generate simulated season stats for minor leaguers who didn't play MLB games.
    Stats are derived from their ratings so development has something to work with.
    """
    minors = conn.execute("""
        SELECT p.id, p.position, p.contact_rating, p.power_rating, p.speed_rating,
               p.eye_rating, p.stuff_rating, p.control_rating, p.stamina_rating,
               p.roster_status, p.team_id
        FROM players p
        WHERE p.roster_status IN ('minors_aaa', 'minors_aa', 'minors_low')
        AND p.id NOT IN (
            SELECT DISTINCT player_id FROM batting_stats WHERE season=?
            UNION
            SELECT DISTINCT player_id FROM pitching_stats WHERE season=?
        )
    """, (season, season)).fetchall()

    for m in minors:
        player_id = m[0]
        position = m[1]
        team_id = m[10] or 1
        is_pitcher = position in ("SP", "RP")
        level = {"minors_aaa": "AAA", "minors_aa": "AA", "minors_low": "LOW"}.get(m[9], "AAA")

        # Get park factors for this team's affiliate at this level
        pf = get_park_factors(team_id, level)

        if is_pitcher:
            stuff = m[6] or 50
            control = m[7] or 50
            stamina = m[8] or 50
            # Simulate a minor league pitching season
            games = random.randint(15, 30)
            gs = games if position == "SP" else random.randint(0, 3)
            # IP based on stamina and role
            ip_per_game = (stamina / 15) if position == "SP" else random.uniform(0.7, 2.0)
            ip = ip_per_game * games
            ip_outs = int(ip * 3)
            # ERA derived from stuff + control (normalized against minor league level)
            level_mod = {"AAA": 1.0, "AA": 0.9, "LOW": 0.8}[level]
            base_era = max(1.5, 7.0 - (stuff + control) / 20) * level_mod
            era = base_era + random.uniform(-0.8, 0.8)
            er = max(0, int(era * ip / 9))
            # K/9 from stuff
            k9 = max(3, stuff / 8 + random.uniform(-1, 2))
            so = int(k9 * ip / 9)
            # BB/9 from control
            bb9 = max(1, 8 - control / 10 + random.uniform(-0.5, 1.0))
            bb = int(bb9 * ip / 9)
            hits = int((er * 1.3 + random.randint(2, 10)) * ip / 9)
            hr = int(er * 0.3 + random.randint(0, 3))
            wins = int(games * max(0.2, min(0.7, 0.5 + (50 - base_era * 5) * 0.02)))
            losses = games - wins - random.randint(0, 3)
            losses = max(0, losses)

            # Apply park factors to generated stats
            # Hitter-friendly parks inflate hits, HR, runs against pitchers
            hits = int(round(hits * pf.get("H", 1.0)))
            hr = int(round(hr * pf.get("HR", 1.0)))
            bb = int(round(bb * pf.get("BB", 1.0)))
            so = int(round(so * pf.get("K", 1.0)))
            er = int(round(er * pf.get("R", 1.0)))
            runs_allowed = er + random.randint(0, 5)

            conn.execute("""
                INSERT OR IGNORE INTO pitching_stats
                (player_id, team_id, season, level, games, games_started, wins, losses,
                 saves, holds, blown_saves, ip_outs, hits_allowed, runs_allowed, er,
                 bb, so, hr_allowed, pitches, complete_games, shutouts, quality_starts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
            """, (player_id, team_id, season, level, games, gs, wins, losses,
                  ip_outs, hits, runs_allowed, er, bb, so, hr,
                  int(ip_outs * 4.5)))
        else:
            contact = m[2] or 50
            power = m[3] or 50
            speed = m[4] or 50
            eye = m[5] or 50
            # Simulate a minor league batting season
            games = random.randint(80, 130)
            pa = int(games * random.uniform(3.5, 4.2))
            # Walk rate from eye
            bb_rate = max(0.04, (eye - 30) / 400 + random.uniform(-0.02, 0.02))
            bb = int(pa * bb_rate)
            hbp = random.randint(0, 8)
            sf = random.randint(0, 5)
            ab = pa - bb - hbp - sf
            # AVG from contact (adjusted for level)
            level_mod = {"AAA": 1.0, "AA": 0.95, "LOW": 0.9}[level]
            base_avg = max(0.180, (contact - 20) / 200 + 0.200) * level_mod
            avg = base_avg + random.uniform(-0.025, 0.025)
            hits = int(ab * avg)
            # Power distribution
            hr = max(0, int((power - 25) / 5 * games / 130 + random.randint(-3, 5)))
            doubles = int(hits * random.uniform(0.18, 0.28))
            triples = int(hits * random.uniform(0.01, 0.04))
            singles = hits - doubles - triples - hr
            if singles < 0:
                hr = max(0, hr - abs(singles))
                singles = max(0, singles)
            so = int(ab * max(0.10, 0.35 - contact / 200 + random.uniform(-0.03, 0.03)))
            sb = max(0, int((speed - 30) / 8 + random.randint(-2, 5)))
            cs = int(sb * random.uniform(0.15, 0.35))
            runs = int(hits * 0.4 + bb * 0.3 + hr * 0.6)
            rbi = int(hr * 1.2 + (hits - hr) * 0.25 + random.randint(0, 15))

            # Apply park factors to generated stats
            hits = int(round(hits * pf.get("H", 1.0)))
            doubles = int(round(doubles * pf.get("2B", 1.0)))
            triples = int(round(triples * pf.get("3B", 1.0)))
            hr = int(round(hr * pf.get("HR", 1.0)))
            bb = int(round(bb * pf.get("BB", 1.0)))
            so = int(round(so * pf.get("K", 1.0)))
            runs = int(round(runs * pf.get("R", 1.0)))
            rbi = int(round(rbi * pf.get("R", 1.0)))

            conn.execute("""
                INSERT OR IGNORE INTO batting_stats
                (player_id, team_id, season, level, games, pa, ab, runs, hits,
                 doubles, triples, hr, rbi, bb, so, sb, cs, hbp, sf)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (player_id, team_id, season, level, games, pa, ab, runs, hits,
                  doubles, triples, hr, rbi, bb, so, sb, cs, hbp, sf))


def _get_performance_modifier(p: dict, conn, is_pitcher: bool) -> float:
    """Calculate a development rate modifier based on actual season performance.
    Returns a multiplier: 0.6 (bad season) to 1.4 (great season).
    Players with no stats get 1.0 (neutral).
    """
    player_id = p["id"]

    if is_pitcher:
        row = conn.execute("""
            SELECT ip_outs, er, so, bb, hr_allowed, hits_allowed
            FROM pitching_stats
            WHERE player_id=? AND ip_outs > 0
            ORDER BY season DESC LIMIT 1
        """, (player_id,)).fetchone()
        if not row:
            return 1.0
        ip = row[0] / 3.0
        if ip < 10:
            return 1.0
        era = 9.0 * row[1] / ip
        k_rate = 9.0 * row[2] / ip
        # Great: ERA < 3.5 and K/9 > 8 → 1.3-1.4
        # Good: ERA < 4.2 → 1.1-1.2
        # Average: ERA 4.2-5.0 → 1.0
        # Bad: ERA > 5.0 → 0.7-0.9
        if era < 3.0 and k_rate > 9:
            return 1.4
        elif era < 3.5:
            return 1.25
        elif era < 4.2:
            return 1.1
        elif era < 5.0:
            return 1.0
        elif era < 6.0:
            return 0.85
        else:
            return 0.7
    else:
        row = conn.execute("""
            SELECT ab, hits, hr, bb, so, sb, doubles, triples, hbp, sf
            FROM batting_stats
            WHERE player_id=? AND ab > 0
            ORDER BY season DESC LIMIT 1
        """, (player_id,)).fetchone()
        if not row:
            return 1.0
        ab = row[0]
        if ab < 50:
            return 1.0
        hits, hr, bb, so = row[1], row[2], row[3], row[4]
        doubles, triples = row[6], row[7]
        hbp, sf = row[8] or 0, row[9] or 0
        # Calculate OPS
        obp = (hits + bb + hbp) / max(1, ab + bb + hbp + sf)
        slg = (hits + doubles + triples * 2 + hr * 3) / max(1, ab)
        ops = obp + slg
        # Great: OPS > .850 → 1.3-1.4
        # Good: OPS > .750 → 1.1-1.2
        # Average: OPS .650-.750 → 1.0
        # Bad: OPS < .650 → 0.7-0.9
        if ops > .900:
            return 1.4
        elif ops > .800:
            return 1.2
        elif ops > .720:
            return 1.1
        elif ops > .650:
            return 1.0
        elif ops > .550:
            return 0.85
        else:
            return 0.7


def _get_per_rating_boost(p: dict, conn, is_pitcher: bool) -> dict:
    """Return per-rating targeted development boosts based on what the player
    did well statistically. E.g., a hitter with lots of HR gets a power boost.
    Returns dict of {rating_name: bonus_points} (0-2 range).
    """
    player_id = p["id"]
    boosts = {}

    if is_pitcher:
        row = conn.execute("""
            SELECT ip_outs, so, bb, er
            FROM pitching_stats
            WHERE player_id=? AND ip_outs > 0
            ORDER BY season DESC LIMIT 1
        """, (player_id,)).fetchone()
        if not row or row[0] < 30:
            return boosts
        ip = row[0] / 3.0
        k9 = 9.0 * row[1] / ip
        bb9 = 9.0 * row[2] / ip
        # High K rate → stuff boost
        if k9 > 9.0:
            boosts["stuff_rating"] = 2
        elif k9 > 7.5:
            boosts["stuff_rating"] = 1
        # Low walk rate → control boost
        if bb9 < 2.5:
            boosts["control_rating"] = 2
        elif bb9 < 3.5:
            boosts["control_rating"] = 1
        # Endurance (high IP) → stamina boost
        if ip > 160:
            boosts["stamina_rating"] = 2
        elif ip > 120:
            boosts["stamina_rating"] = 1
    else:
        row = conn.execute("""
            SELECT ab, hits, hr, bb, so, sb, doubles, triples
            FROM batting_stats
            WHERE player_id=? AND ab > 0
            ORDER BY season DESC LIMIT 1
        """, (player_id,)).fetchone()
        if not row or row[0] < 100:
            return boosts
        ab, hits, hr, bb, so, sb = row[0], row[1], row[2], row[3], row[4], row[5]
        avg = hits / ab
        # High AVG → contact boost
        if avg > .300:
            boosts["contact_rating"] = 2
        elif avg > .275:
            boosts["contact_rating"] = 1
        # HR power → power boost
        hr_rate = hr / (ab / 500) if ab > 0 else 0
        if hr_rate > 30:
            boosts["power_rating"] = 2
        elif hr_rate > 20:
            boosts["power_rating"] = 1
        # SB → speed boost
        sb_rate = sb / (ab / 500) if ab > 0 else 0
        if sb_rate > 25:
            boosts["speed_rating"] = 2
        elif sb_rate > 15:
            boosts["speed_rating"] = 1
        # Low K rate → eye boost
        k_rate = so / ab if ab > 0 else 0
        if k_rate < 0.15:
            boosts["eye_rating"] = 2
        elif k_rate < 0.20:
            boosts["eye_rating"] = 1
        # High walk rate → eye boost
        bb_rate = bb / (ab + bb) if (ab + bb) > 0 else 0
        if bb_rate > 0.12:
            boosts["eye_rating"] = boosts.get("eye_rating", 0) + 1

    return boosts


def _develop_player(p: dict, conn) -> dict:
    """Apply development/decline to a single player."""
    age = p["age"]
    peak = p["peak_age"]
    dev_rate = p["development_rate"]
    work_ethic = p["work_ethic"]
    is_pitcher = p["position"] in ("SP", "RP")

    farm_budget = p.get("farm_system_budget", 10000000) or 10000000
    farm_mod = 0.8 + (farm_budget / 50000000)

    changes = {}

    # ------------------------------------------------------------------
    # INJURY IMPACT: Apply permanent rating loss from major injuries
    # ------------------------------------------------------------------
    injury_changes = _apply_injury_impact(p, conn)
    if injury_changes:
        changes.update(injury_changes)

    # ------------------------------------------------------------------
    # PRE-PEAK: Development phase
    # ------------------------------------------------------------------
    if age < peak:
        is_bust = p.get("is_bust", 0)
        is_late_bloomer = p.get("is_late_bloomer", 0)

        # --- Bust check (only if not already busted) ---
        if not is_bust:
            bust_event = _check_bust(p, conn)
            if bust_event:
                changes["bust"] = bust_event
                is_bust = 1

        # --- Late bloomer check (only if age 24+ and not already triggered) ---
        if not is_late_bloomer and age >= 24:
            bloomer_event = _check_late_bloomer(p, conn)
            if bloomer_event:
                changes["late_bloomer"] = bloomer_event
                is_late_bloomer = 1

        # --- Calculate development rate ---
        rate = (work_ethic / 50) * dev_rate * farm_mod
        if p["roster_status"] in ("minors_aaa", "minors_aa", "minors_low"):
            rate *= farm_mod

        # Bust: development slows dramatically
        if is_bust:
            rate *= 0.3

        # Late bloomer: development accelerates
        if is_late_bloomer:
            rate *= 1.5

        # --- Performance-based modifier ---
        # Players who performed well develop faster; poor performers develop slower
        perf_mod = _get_performance_modifier(p, conn, is_pitcher)
        rate *= perf_mod

        # --- Apply development ---
        ratings = _get_rating_fields(is_pitcher)
        perf_boosts = _get_per_rating_boost(p, conn, is_pitcher)
        for rating, potential in ratings:
            current = p[rating]
            pot = p[potential]
            if current < pot:
                # Base improvement + targeted boost from performance
                base_improvement = random.uniform(1, 4) * rate
                targeted_boost = perf_boosts.get(rating, 0)
                improvement = int(base_improvement + targeted_boost)
                new_val = min(pot, current + max(0, improvement))
                if new_val != current:
                    conn.execute(f"UPDATE players SET {rating}=? WHERE id=?",
                                (new_val, p["id"]))
                    if new_val - current >= 3:
                        changes[rating] = (current, new_val)

    # ------------------------------------------------------------------
    # PEAK PHASE: Mostly stable, small random fluctuations
    # ------------------------------------------------------------------
    elif age <= peak + 2:
        ratings = _get_rating_fields(is_pitcher)
        for rating, _ in ratings:
            current = p[rating]
            delta = random.choice([-1, 0, 0, 0, 1])
            new_val = max(20, min(80, current + delta))
            if new_val != current:
                conn.execute(f"UPDATE players SET {rating}=? WHERE id=?",
                            (new_val, p["id"]))

    # ------------------------------------------------------------------
    # DECLINE PHASE: Position-specific decline curves
    # ------------------------------------------------------------------
    else:
        decline_changes = _apply_position_decline(p, age, peak, is_pitcher, conn)
        if decline_changes:
            changes.update(decline_changes)

        # Position shift for aging defensive players
        position_shifts = _calculate_position_shift(p, age, conn)
        if position_shifts:
            changes["position_shift"] = position_shifts

        # Retirement check
        overall = _calc_overall(p, is_pitcher)
        if overall < 25 and age > 35:
            conn.execute("UPDATE players SET roster_status='retired' WHERE id=?",
                        (p["id"],))
            changes["retired"] = True

    # ------------------------------------------------------------------
    # BREAKOUT SEASON: Can happen at any age (more likely 23-27)
    # ------------------------------------------------------------------
    breakout = _check_breakout(p, age, is_pitcher, conn)
    if breakout:
        changes["breakout"] = breakout

    if changes:
        return {
            "player_id": p["id"],
            "name": f"{p['first_name']} {p['last_name']}",
            "age": age,
            "changes": changes,
        }
    return None


# ======================================================================
# NON-LINEAR DEVELOPMENT EVENTS
# ======================================================================

def _check_bust(p: dict, conn) -> dict:
    """
    Check if a pre-peak prospect busts.
    Higher-ceiling prospects are less likely to bust.
    Returns bust info dict or None.
    """
    is_pitcher = p["position"] in ("SP", "RP")
    overall_potential = _calc_overall_potential(p, is_pitcher)

    # Determine bust probability based on prospect caliber
    if overall_potential >= 65:
        bust_chance = 0.03   # 1st-round caliber
    elif overall_potential >= 50:
        bust_chance = 0.08   # Mid-round
    else:
        bust_chance = 0.15   # Late-round

    if random.random() >= bust_chance:
        return None

    # BUST TRIGGERED: Cap potential 10-20 points below current ceiling
    reduction = random.randint(10, 20)
    ratings = _get_rating_fields(is_pitcher)
    capped = {}
    for rating, potential in ratings:
        old_pot = p[potential]
        new_pot = max(20, old_pot - reduction)
        if new_pot != old_pot:
            conn.execute(f"UPDATE players SET {potential}=? WHERE id=?",
                        (new_pot, p["id"]))
            p[potential] = new_pot
            capped[potential] = (old_pot, new_pot)

    conn.execute("UPDATE players SET is_bust=1 WHERE id=?", (p["id"],))

    return {
        "type": "bust",
        "potential_reduction": reduction,
        "capped_potentials": capped,
    }


def _check_late_bloomer(p: dict, conn) -> dict:
    """
    Check if a player aged 24+ becomes a late bloomer.
    4% base chance, higher with good work ethic.
    Returns late bloomer info dict or None.
    """
    base_chance = 0.04
    # Work ethic bonus: 80 work_ethic -> +2% chance
    ethic_bonus = (p["work_ethic"] - 50) / 50 * 0.02
    chance = base_chance + ethic_bonus

    if random.random() >= chance:
        return None

    # LATE BLOOMER TRIGGERED: Shift peak age 2-3 years later
    peak_shift = random.randint(2, 3)
    new_peak = p["peak_age"] + peak_shift

    conn.execute("UPDATE players SET peak_age=?, is_late_bloomer=1 WHERE id=?",
                (new_peak, p["id"]))
    p["peak_age"] = new_peak

    return {
        "type": "late_bloomer",
        "peak_shift": peak_shift,
        "new_peak_age": new_peak,
    }


def _check_breakout(p: dict, age: int, is_pitcher: bool, conn) -> dict:
    """
    Check if a player has a breakout season (big jump in one key rating).
    3% base chance, higher for age 23-27.
    Returns breakout info dict or None.
    """
    base_chance = 0.03
    # Age 23-27 bonus
    if 23 <= age <= 27:
        base_chance = 0.05

    if random.random() >= base_chance:
        return None

    # Determine which rating breaks out, weighted by position
    position = p["position"]
    weights = BREAKOUT_WEIGHTS.get(position, BREAKOUT_WEIGHTS.get("DH"))

    # Filter to ratings this player actually uses
    valid_ratings = {r for r, _ in _get_rating_fields(is_pitcher)}
    eligible = {r: w for r, w in weights.items() if r in valid_ratings}
    if not eligible:
        return None

    # Weighted random selection
    rating_names = list(eligible.keys())
    rating_weights = [eligible[r] for r in rating_names]
    chosen_rating = random.choices(rating_names, weights=rating_weights, k=1)[0]

    # Gain 5-8 points
    gain = random.randint(5, 8)
    current = p[chosen_rating]
    new_val = min(80, current + gain)
    actual_gain = new_val - current

    if actual_gain <= 0:
        return None

    conn.execute(f"UPDATE players SET {chosen_rating}=? WHERE id=?",
                (new_val, p["id"]))

    return {
        "type": "breakout",
        "rating": chosen_rating,
        "old_value": current,
        "new_value": new_val,
        "gain": actual_gain,
    }


# ======================================================================
# POSITION-SPECIFIC DECLINE
# ======================================================================

def _apply_position_decline(p: dict, age: int, peak: int, is_pitcher: bool, conn) -> dict:
    """
    Apply position-specific decline curves instead of uniform decline.

    Hitter decline order:
      - Speed: starts at peak, accelerates after 32
      - Fielding: starts at peak, moderate rate
      - Contact: starts 2 years after peak, slow
      - Power: starts 3 years after peak, very slow
      - Arm: starts at peak, moderate

    Pitcher decline order:
      - Stamina: declines fastest, starts at peak
      - Stuff: starts at peak, moderate
      - Control: can IMPROVE until 33, then slow decline
    """
    years_past_peak = age - peak
    changes = {}

    if is_pitcher:
        # --- STAMINA: declines fastest ---
        stam_decline_rate = 0.6 + years_past_peak * 0.4
        stam_decline = int(stam_decline_rate * random.uniform(1.5, 3.0))
        new_stam = max(20, p["stamina_rating"] - stam_decline)
        if new_stam != p["stamina_rating"]:
            conn.execute("UPDATE players SET stamina_rating=? WHERE id=?",
                        (new_stam, p["id"]))
            if p["stamina_rating"] - new_stam >= 3:
                changes["stamina_rating"] = (p["stamina_rating"], new_stam)

        # --- STUFF: moderate decline ---
        stuff_decline_rate = 0.4 + years_past_peak * 0.3
        stuff_decline = int(stuff_decline_rate * random.uniform(1.0, 2.0))
        new_stuff = max(20, p["stuff_rating"] - stuff_decline)
        if new_stuff != p["stuff_rating"]:
            conn.execute("UPDATE players SET stuff_rating=? WHERE id=?",
                        (new_stuff, p["id"]))
            if p["stuff_rating"] - new_stuff >= 3:
                changes["stuff_rating"] = (p["stuff_rating"], new_stuff)

        # --- CONTROL: can improve until 33, then slow decline ---
        if age <= 33:
            # Control can still improve slightly
            ctrl_delta = random.choice([-1, 0, 0, 1, 1, 2])
            new_ctrl = max(20, min(80, p["control_rating"] + ctrl_delta))
        else:
            ctrl_decline_rate = 0.2 + (age - 33) * 0.15
            ctrl_decline = int(ctrl_decline_rate * random.uniform(0.5, 1.5))
            new_ctrl = max(20, p["control_rating"] - ctrl_decline)
        if new_ctrl != p["control_rating"]:
            conn.execute("UPDATE players SET control_rating=? WHERE id=?",
                        (new_ctrl, p["id"]))
            if abs(p["control_rating"] - new_ctrl) >= 3:
                changes["control_rating"] = (p["control_rating"], new_ctrl)

    else:
        # --- SPEED: declines fastest, starts at peak, accelerates after 32 ---
        speed_base = 0.5 + years_past_peak * 0.3
        if age > 32:
            speed_base += (age - 32) * 0.4  # accelerates
        speed_decline = int(speed_base * random.uniform(1.5, 3.0))
        new_speed = max(20, p["speed_rating"] - speed_decline)
        if new_speed != p["speed_rating"]:
            conn.execute("UPDATE players SET speed_rating=? WHERE id=?",
                        (new_speed, p["id"]))
            if p["speed_rating"] - new_speed >= 3:
                changes["speed_rating"] = (p["speed_rating"], new_speed)

        # --- FIELDING: moderate decline, starts at peak ---
        field_decline_rate = 0.3 + years_past_peak * 0.2
        field_decline = int(field_decline_rate * random.uniform(0.5, 2.0))
        new_field = max(20, p["fielding_rating"] - field_decline)
        if new_field != p["fielding_rating"]:
            conn.execute("UPDATE players SET fielding_rating=? WHERE id=?",
                        (new_field, p["id"]))
            if p["fielding_rating"] - new_field >= 3:
                changes["fielding_rating"] = (p["fielding_rating"], new_field)

        # --- ARM: moderate decline, starts at peak ---
        arm_decline_rate = 0.3 + years_past_peak * 0.2
        arm_decline = int(arm_decline_rate * random.uniform(0.5, 1.5))
        new_arm = max(20, p["arm_rating"] - arm_decline)
        if new_arm != p["arm_rating"]:
            conn.execute("UPDATE players SET arm_rating=? WHERE id=?",
                        (new_arm, p["id"]))
            if p["arm_rating"] - new_arm >= 3:
                changes["arm_rating"] = (p["arm_rating"], new_arm)

        # --- CONTACT: slow decline, starts 2 years after peak ---
        if years_past_peak > 2:
            contact_years = years_past_peak - 2
            contact_decline_rate = 0.2 + contact_years * 0.15
            contact_decline = int(contact_decline_rate * random.uniform(0.5, 1.5))
            new_contact = max(20, p["contact_rating"] - contact_decline)
            if new_contact != p["contact_rating"]:
                conn.execute("UPDATE players SET contact_rating=? WHERE id=?",
                            (new_contact, p["id"]))
                if p["contact_rating"] - new_contact >= 3:
                    changes["contact_rating"] = (p["contact_rating"], new_contact)

        # --- POWER: holds longest, starts 3 years after peak, slow decline ---
        if years_past_peak > 3:
            power_years = years_past_peak - 3
            power_decline_rate = 0.15 + power_years * 0.1
            power_decline = int(power_decline_rate * random.uniform(0.5, 1.5))
            new_power = max(20, p["power_rating"] - power_decline)
            if new_power != p["power_rating"]:
                conn.execute("UPDATE players SET power_rating=? WHERE id=?",
                            (new_power, p["id"]))
                if p["power_rating"] - new_power >= 3:
                    changes["power_rating"] = (p["power_rating"], new_power)

    return changes


# ======================================================================
# INJURY IMPACT ON DEVELOPMENT
# ======================================================================

def _apply_injury_impact(p: dict, conn) -> dict:
    """
    Check if a player has a major injury and apply permanent rating loss.
    Only triggers when the player is currently injured (caught during offseason).
    After applying, clears the injury_type so it doesn't re-apply next year.
    """
    injury_type = p.get("injury_type")
    if not injury_type:
        return None

    # Find matching injury impact
    impacts = MAJOR_INJURY_IMPACTS.get(injury_type)
    if not impacts:
        return None

    changes = {}
    for rating, (worst, best) in impacts.items():
        # worst is a larger negative, best is a smaller negative
        # e.g. (-6, -3) means lose between 3 and 6 points
        loss = random.randint(worst, best)  # negative number
        current = p.get(rating, 50)
        new_val = max(20, current + loss)
        if new_val != current:
            conn.execute(f"UPDATE players SET {rating}=? WHERE id=?",
                        (new_val, p["id"]))
            p[rating] = new_val
            changes[f"injury_impact_{rating}"] = {
                "injury": injury_type,
                "rating": rating,
                "old": current,
                "new": new_val,
                "loss": current - new_val,
            }

    return changes


# ======================================================================
# POSITION SHIFTS (unchanged)
# ======================================================================

def _calculate_position_shift(p: dict, age: int, conn) -> dict:
    """Determine if player shifts to easier defensive position due to age."""
    current_position = p["position"]
    new_position = None
    fielding_boost = 0

    # SS -> 3B (5% chance per year past 32)
    if current_position == "SS" and age > 32:
        chance = (age - 32) * 0.05
        if random.random() < chance:
            new_position = "3B"
            fielding_boost = random.randint(3, 5)

    # 3B -> 1B (3% chance per year past 33)
    elif current_position == "3B" and age > 33:
        chance = (age - 33) * 0.03
        if random.random() < chance:
            new_position = "1B"
            fielding_boost = random.randint(3, 5)

    # CF -> LF/RF (5% chance per year past 31)
    elif current_position == "CF" and age > 31:
        chance = (age - 31) * 0.05
        if random.random() < chance:
            new_position = random.choice(["LF", "RF"])
            fielding_boost = random.randint(3, 5)

    # LF/RF -> DH (3% chance per year past 35)
    elif current_position in ("LF", "RF") and age > 35:
        chance = (age - 35) * 0.03
        if random.random() < chance:
            new_position = "DH"
            fielding_boost = 0

    # 2B -> 3B (3% chance per year past 33)
    elif current_position == "2B" and age > 33:
        chance = (age - 33) * 0.03
        if random.random() < chance:
            new_position = "3B"
            fielding_boost = random.randint(3, 5)

    if new_position:
        # Update position
        conn.execute("UPDATE players SET position=? WHERE id=?",
                    (new_position, p["id"]))

        # Boost fielding at new position
        if fielding_boost > 0:
            new_fielding = min(80, p["fielding_rating"] + fielding_boost)
            conn.execute("UPDATE players SET fielding_rating=? WHERE id=?",
                        (new_fielding, p["id"]))

        return {
            "from_position": current_position,
            "to_position": new_position,
            "fielding_boost": fielding_boost,
        }

    return None


# ======================================================================
# HELPERS
# ======================================================================

def _get_rating_fields(is_pitcher: bool) -> list:
    """Get (rating, potential) field pairs."""
    if is_pitcher:
        return [
            ("stuff_rating", "stuff_potential"),
            ("control_rating", "control_potential"),
            ("stamina_rating", "stamina_potential"),
        ]
    return [
        ("contact_rating", "contact_potential"),
        ("power_rating", "power_potential"),
        ("speed_rating", "speed_potential"),
        ("fielding_rating", "fielding_potential"),
        ("arm_rating", "arm_potential"),
    ]


def _calc_overall(p: dict, is_pitcher: bool) -> float:
    if is_pitcher:
        return (p["stuff_rating"] * 2 + p["control_rating"] * 1.5 + p["stamina_rating"] * 0.5) / 4
    return (p["contact_rating"] * 1.5 + p["power_rating"] * 1.5 +
            p["speed_rating"] * 0.5 + p["fielding_rating"] * 0.5) / 4


def _calc_overall_potential(p: dict, is_pitcher: bool) -> float:
    """Calculate overall potential rating for bust probability tiers."""
    if is_pitcher:
        return (p["stuff_potential"] * 2 + p["control_potential"] * 1.5 + p["stamina_potential"] * 0.5) / 4
    return (p["contact_potential"] * 1.5 + p["power_potential"] * 1.5 +
            p["speed_potential"] * 0.5 + p["fielding_potential"] * 0.5) / 4


def get_player_eligible_positions(player_id: int, db_path: str = None) -> list:
    """Get all positions a player is eligible to play based on games played."""
    conn = get_connection(db_path)

    # Get primary position
    player = conn.execute("SELECT position FROM players WHERE id=?",
                         (player_id,)).fetchone()
    if not player:
        return []

    primary = player["position"]
    eligible = [primary]

    # Check secondary positions with 10+ games played
    positions = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "DH"]
    for pos in positions:
        if pos == primary:
            continue

        games_at_pos = conn.execute("""
            SELECT COUNT(*) as games FROM batting_lines
            WHERE player_id=? AND position_played=?
        """, (player_id, pos)).fetchone()

        if games_at_pos and games_at_pos["games"] >= 10:
            eligible.append(pos)

    conn.close()
    return eligible


def update_secondary_positions(player_id: int, db_path: str = None):
    """Update secondary_positions field based on games played history."""
    eligible = get_player_eligible_positions(player_id, db_path)
    if not eligible:
        return

    primary = eligible[0]
    secondary = ",".join(eligible[1:]) if len(eligible) > 1 else ""

    conn = get_connection(db_path)
    conn.execute("UPDATE players SET secondary_positions=? WHERE id=?",
                (secondary, player_id))
    conn.commit()
    conn.close()
