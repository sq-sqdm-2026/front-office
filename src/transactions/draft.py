"""
Front Office - Amateur Draft System
20-round draft with procedurally generated prospects.
Scouting uncertainty baked into floor/ceiling ratings.

Features:
- Draft order based on inverse regular-season record (worst first)
- Slot values & bonus pools for rounds 1-10
- Signability ratings per prospect (college senior / junior / HS / JuCo)
- Competitive balance lottery picks (CB-A after round 1, CB-B after round 2)
"""
import random
import json
import functools
from ..database.db import get_connection, query
from ..database.seed import FIRST_NAMES, LAST_NAMES, COUNTRIES


POSITIONS = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "SP", "SP", "SP", "RP"]

# Prospect background types and their signability ranges
PROSPECT_TYPES = ["college_senior", "college_junior", "high_school", "juco"]
PROSPECT_TYPE_WEIGHTS = [25, 30, 30, 15]
SIGNABILITY_RANGES = {
    "college_senior": (90, 100),
    "college_junior": (60, 85),
    "high_school": (40, 75),
    "juco": (80, 95),
}
# Age ranges per prospect type
PROSPECT_AGE_RANGES = {
    "college_senior": (21, 22),
    "college_junior": (20, 21),
    "high_school": (18, 18),
    "juco": (19, 20),
}

# Number of competitive balance picks per round
CB_PICKS_PER_ROUND = 6


# ============================================================
# SLOT VALUES
# ============================================================

def get_slot_value(overall_pick: int) -> int:
    """
    Return the slot value in dollars for a given overall pick number.

    Pick 1: $9,800,000
    Pick 2: $8,500,000
    Picks 3-5: $7,000,000 - $5,500,000 (linear decrease)
    Picks 6-10: $5,000,000 - $4,000,000
    Picks 11-30: $3,500,000 - $2,000,000
    Round 2 (picks 31-60): $1,500,000 - $800,000
    Round 3-5 (picks 61-150): $600,000 - $200,000
    Round 6+ (picks 151+): $150,000 flat
    """
    if overall_pick == 1:
        return 9_800_000
    if overall_pick == 2:
        return 8_500_000
    if 3 <= overall_pick <= 5:
        # Linear from 7,000,000 (pick 3) to 5,500,000 (pick 5)
        return int(7_000_000 - (overall_pick - 3) * (1_500_000 / 2))
    if 6 <= overall_pick <= 10:
        # Linear from 5,000,000 (pick 6) to 4,000,000 (pick 10)
        return int(5_000_000 - (overall_pick - 6) * (1_000_000 / 4))
    if 11 <= overall_pick <= 30:
        # Linear from 3,500,000 (pick 11) to 2,000,000 (pick 30)
        return int(3_500_000 - (overall_pick - 11) * (1_500_000 / 19))
    if 31 <= overall_pick <= 60:
        # Round 2: linear from 1,500,000 to 800,000
        return int(1_500_000 - (overall_pick - 31) * (700_000 / 29))
    if 61 <= overall_pick <= 150:
        # Rounds 3-5: linear from 600,000 to 200,000
        return int(600_000 - (overall_pick - 61) * (400_000 / 89))
    # Round 6+
    return 150_000


def calculate_bonus_pool(team_picks: list[dict]) -> int:
    """
    Calculate a team's total bonus pool from their picks in rounds 1-10.
    team_picks: list of dicts with at least 'round' and 'overall_pick' keys.
    """
    total = 0
    for pick in team_picks:
        if pick["round"] <= 10:
            total += get_slot_value(pick["overall_pick"])
    return total


# ============================================================
# DRAFT ORDER (inverse regular-season record)
# ============================================================

def _get_team_standings(season: int, conn) -> list[dict]:
    """
    Query the schedule table to compute W-L records for each team.
    Returns list of {team_id, wins, losses} sorted worst-to-best.
    """
    # Count wins from played regular-season games
    rows = conn.execute("""
        SELECT team_id, SUM(wins) as wins, SUM(losses) as losses
        FROM (
            SELECT home_team_id AS team_id,
                   SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END) AS losses
            FROM schedule
            WHERE season = ? AND is_played = 1 AND is_postseason = 0
            GROUP BY home_team_id
            UNION ALL
            SELECT away_team_id AS team_id,
                   SUM(CASE WHEN away_score > home_score THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN away_score < home_score THEN 1 ELSE 0 END) AS losses
            FROM schedule
            WHERE season = ? AND is_played = 1 AND is_postseason = 0
            GROUP BY away_team_id
        )
        GROUP BY team_id
    """, (season, season)).fetchall()

    standings = [dict(r) for r in rows]
    return standings


def _head_to_head_record(team_a: int, team_b: int, season: int, conn) -> int:
    """
    Return net wins of team_a vs team_b in the given season.
    Positive = team_a won more, negative = team_b won more, 0 = tied.
    """
    rows = conn.execute("""
        SELECT
            SUM(CASE
                WHEN (home_team_id = ? AND home_score > away_score)
                  OR (away_team_id = ? AND away_score > home_score) THEN 1
                ELSE 0 END) as a_wins,
            SUM(CASE
                WHEN (home_team_id = ? AND home_score > away_score)
                  OR (away_team_id = ? AND away_score > home_score) THEN 1
                ELSE 0 END) as b_wins
        FROM schedule
        WHERE season = ? AND is_played = 1 AND is_postseason = 0
          AND ((home_team_id = ? AND away_team_id = ?)
            OR (home_team_id = ? AND away_team_id = ?))
    """, (team_a, team_a, team_b, team_b, season,
          team_a, team_b, team_b, team_a)).fetchone()

    if rows is None:
        return 0
    a_wins = rows["a_wins"] or 0
    b_wins = rows["b_wins"] or 0
    return a_wins - b_wins


def get_draft_order(season: int, conn) -> list[int]:
    """
    Determine draft order based on inverse regular-season record.
    Worst record picks first. Same order every round (no alternating).

    Tiebreakers: head-to-head record, then random.
    If no games played (first season), use reverse team_id order.
    """
    standings = _get_team_standings(season, conn)

    # Get all team IDs
    all_teams = conn.execute("SELECT id FROM teams ORDER BY id").fetchall()
    all_team_ids = [t["id"] for t in all_teams]

    if not standings:
        # First season / no games played: reverse team_id
        return list(reversed(all_team_ids))

    # Build a lookup: team_id -> {wins, losses, win_pct}
    record_map = {}
    for s in standings:
        total = s["wins"] + s["losses"]
        record_map[s["team_id"]] = {
            "wins": s["wins"],
            "losses": s["losses"],
            "win_pct": s["wins"] / total if total > 0 else 0.0,
        }

    # Teams without any games get 0-0 record
    for tid in all_team_ids:
        if tid not in record_map:
            record_map[tid] = {"wins": 0, "losses": 0, "win_pct": 0.0}

    # Sort: lowest win_pct first (worst record picks first)
    # For ties, use head-to-head then random
    def _compare(a_id, b_id):
        a_pct = record_map[a_id]["win_pct"]
        b_pct = record_map[b_id]["win_pct"]
        if a_pct != b_pct:
            return -1 if a_pct < b_pct else 1
        # Tied — head-to-head (team with WORSE h2h picks earlier)
        h2h = _head_to_head_record(a_id, b_id, season, conn)
        if h2h != 0:
            # If a_id lost more h2h matchups, a_id picks earlier (lower = worse = earlier)
            return -1 if h2h < 0 else 1
        # Random tiebreaker (deterministic per pair for consistency)
        return -1 if hash((a_id, b_id, season)) % 2 == 0 else 1

    sorted_ids = sorted(all_team_ids, key=functools.cmp_to_key(_compare))
    return sorted_ids


# ============================================================
# COMPETITIVE BALANCE PICKS
# ============================================================

def _get_cb_eligible_teams(conn) -> tuple[list[int], list[int]]:
    """
    Determine teams eligible for competitive balance picks.
    CB-A: 6 teams with lowest cash / market_size (proxy for revenue)
    CB-B: next 6 lowest
    Returns (cb_a_team_ids, cb_b_team_ids).
    """
    rows = conn.execute("""
        SELECT id, cash, market_size,
               CAST(cash AS REAL) / CASE WHEN market_size > 0 THEN market_size ELSE 1 END AS revenue_proxy
        FROM teams
        ORDER BY revenue_proxy ASC, market_size ASC
    """).fetchall()

    team_ids = [r["id"] for r in rows]
    cb_a = team_ids[:CB_PICKS_PER_ROUND]
    cb_b = team_ids[CB_PICKS_PER_ROUND:CB_PICKS_PER_ROUND * 2]
    return cb_a, cb_b


# ============================================================
# SIGNABILITY
# ============================================================

def _check_signability(signability: int) -> bool:
    """
    Determine if a drafted player signs.
    Returns True if the player signs, False if they refuse.
    """
    if signability < 50:
        return random.random() >= 0.30  # 70% chance signs
    elif signability < 70:
        return random.random() >= 0.10  # 90% chance signs
    else:
        return True  # Always signs


# ============================================================
# SCHEMA MIGRATION
# ============================================================

def migrate_draft_signability(db_path: str = None):
    """Add signability, prospect_type, and signing_demand columns to draft_prospects."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(draft_prospects)")
    columns = {row[1] for row in cursor.fetchall()}

    if "signability" not in columns:
        conn.execute("ALTER TABLE draft_prospects ADD COLUMN signability INTEGER NOT NULL DEFAULT 75")
    if "prospect_type" not in columns:
        conn.execute("ALTER TABLE draft_prospects ADD COLUMN prospect_type TEXT NOT NULL DEFAULT 'college_senior'")
    if "signing_demand" not in columns:
        conn.execute("ALTER TABLE draft_prospects ADD COLUMN signing_demand INTEGER NOT NULL DEFAULT 0")

    # Also add is_cb_pick to draft_pick_ownership if missing
    cursor.execute("PRAGMA table_info(draft_pick_ownership)")
    dpo_columns = {row[1] for row in cursor.fetchall()}
    if "is_cb_pick" not in dpo_columns:
        conn.execute("ALTER TABLE draft_pick_ownership ADD COLUMN is_cb_pick INTEGER NOT NULL DEFAULT 0")

    # Add bonus pool tracking columns to a new or existing table
    # We'll track it on draft_pick_ownership per-pick: slot_value, signed_amount
    if "slot_value" not in dpo_columns:
        conn.execute("ALTER TABLE draft_pick_ownership ADD COLUMN slot_value INTEGER NOT NULL DEFAULT 0")
    if "signed_amount" not in dpo_columns:
        conn.execute("ALTER TABLE draft_pick_ownership ADD COLUMN signed_amount INTEGER DEFAULT NULL")

    conn.commit()
    conn.close()


# ============================================================
# GENERATE DRAFT CLASS
# ============================================================

def generate_draft_class(season: int, db_path: str = None) -> list:
    """Generate a full draft class of ~600 prospects (20 rounds * 30 teams)."""
    conn = get_connection(db_path)

    # Run migration to ensure columns exist
    migrate_draft_signability(db_path)

    # Check if already generated
    existing = conn.execute("SELECT COUNT(*) as c FROM draft_prospects WHERE season=?",
                           (season,)).fetchone()["c"]
    if existing > 0:
        conn.close()
        return query("SELECT * FROM draft_prospects WHERE season=? ORDER BY overall_rank",
                    (season,), db_path=db_path)

    used_names = set()
    prospects = []

    for rank in range(1, 601):
        # Top prospects have higher ceilings
        if rank <= 30:  # 1st round
            tier = "elite"
        elif rank <= 90:  # 2nd-3rd round
            tier = "good"
        elif rank <= 180:  # 4th-6th round
            tier = "average"
        elif rank <= 300:  # 7th-10th round
            tier = "below_average"
        else:  # 11th-20th round
            tier = "lottery"

        prospect = _generate_prospect(tier, rank, used_names)
        prospect["season"] = season
        prospect["overall_rank"] = rank

        conn.execute("""
            INSERT INTO draft_prospects (season, first_name, last_name, age, position,
                bats, throws, contact_floor, contact_ceiling, power_floor, power_ceiling,
                speed_floor, speed_ceiling, fielding_floor, fielding_ceiling,
                arm_floor, arm_ceiling, stuff_floor, stuff_ceiling,
                control_floor, control_ceiling, overall_rank, scouting_report,
                signability, prospect_type, signing_demand)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (season, prospect["first_name"], prospect["last_name"], prospect["age"],
              prospect["position"], prospect["bats"], prospect["throws"],
              prospect["contact_floor"], prospect["contact_ceiling"],
              prospect["power_floor"], prospect["power_ceiling"],
              prospect["speed_floor"], prospect["speed_ceiling"],
              prospect["fielding_floor"], prospect["fielding_ceiling"],
              prospect["arm_floor"], prospect["arm_ceiling"],
              prospect["stuff_floor"], prospect["stuff_ceiling"],
              prospect["control_floor"], prospect["control_ceiling"],
              rank, prospect.get("scouting_report", ""),
              prospect["signability"], prospect["prospect_type"],
              prospect["signing_demand"]))

        prospects.append(prospect)

    conn.commit()
    conn.close()
    return prospects


def _generate_prospect(tier: str, rank: int, used_names: set) -> dict:
    """Generate a single draft prospect with floor/ceiling uncertainty and signability."""
    position = random.choice(POSITIONS)
    is_pitcher = position in ("SP", "RP")

    # Determine prospect type
    prospect_type = random.choices(PROSPECT_TYPES, weights=PROSPECT_TYPE_WEIGHTS)[0]

    # Name generation
    for _ in range(100):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        if f"{first} {last}" not in used_names:
            used_names.add(f"{first} {last}")
            break

    # Age based on prospect type
    age_lo, age_hi = PROSPECT_AGE_RANGES[prospect_type]
    age = random.randint(age_lo, age_hi)

    # Signability based on prospect type
    sig_lo, sig_hi = SIGNABILITY_RANGES[prospect_type]
    signability = random.randint(sig_lo, sig_hi)

    # Signing demand: how much over/under slot they want
    # Low signability prospects tend to demand more (overslot)
    if signability < 60:
        # Wants overslot: 110-150% of slot
        signing_demand = random.randint(110, 150)
    elif signability < 80:
        # Around slot: 90-115%
        signing_demand = random.randint(90, 115)
    else:
        # Easy sign: 70-100% of slot
        signing_demand = random.randint(70, 100)

    # Tier-based rating ranges
    ranges = {
        "elite": {"base": (55, 75), "spread": (10, 20)},
        "good": {"base": (45, 65), "spread": (12, 22)},
        "average": {"base": (35, 55), "spread": (15, 25)},
        "below_average": {"base": (25, 45), "spread": (15, 30)},
        "lottery": {"base": (20, 40), "spread": (15, 35)},
    }

    r = ranges[tier]

    def _floor_ceiling():
        mid = random.randint(*r["base"])
        spread = random.randint(*r["spread"])
        floor = max(20, mid - spread // 2)
        ceiling = min(80, mid + spread // 2)
        return floor, ceiling

    cf, cc = _floor_ceiling()
    pf, pc = _floor_ceiling()
    sf, sc = _floor_ceiling()
    ff, fc = _floor_ceiling()
    af, ac = _floor_ceiling()

    if is_pitcher:
        stf, stc = _floor_ceiling()
        ctf, ctc = _floor_ceiling()
    else:
        stf, stc = 20, 20
        ctf, ctc = 20, 20

    return {
        "first_name": first,
        "last_name": last,
        "age": age,
        "position": position,
        "bats": random.choices(["R", "L", "S"], weights=[55, 30, 15])[0],
        "throws": "L" if (is_pitcher and random.random() < 0.30) else "R",
        "contact_floor": cf, "contact_ceiling": cc,
        "power_floor": pf, "power_ceiling": pc,
        "speed_floor": sf, "speed_ceiling": sc,
        "fielding_floor": ff, "fielding_ceiling": fc,
        "arm_floor": af, "arm_ceiling": ac,
        "stuff_floor": stf, "stuff_ceiling": stc,
        "control_floor": ctf, "control_ceiling": ctc,
        "birth_country": random.choice(COUNTRIES),
        "signability": signability,
        "prospect_type": prospect_type,
        "signing_demand": signing_demand,
    }


# ============================================================
# INITIALIZE DRAFT PICK OWNERSHIP
# ============================================================

def initialize_draft_pick_ownership(season: int, db_path: str = None) -> list:
    """
    Initialize draft pick ownership for a season.
    Draft order based on inverse regular-season record (worst team picks first).
    Same order every round (no alternating).
    Includes competitive balance picks after rounds 1 and 2.
    """
    conn = get_connection(db_path)

    # Run migration to ensure columns exist
    migrate_draft_signability(db_path)

    # Check if already initialized
    existing = conn.execute("""
        SELECT COUNT(*) as c FROM draft_pick_ownership WHERE season=?
    """, (season,)).fetchone()["c"]

    if existing > 0:
        conn.close()
        return query("""
            SELECT * FROM draft_pick_ownership WHERE season=?
            ORDER BY round, pick_number
        """, (season,), db_path=db_path)

    # Determine draft order from previous season's standings
    prev_season = season - 1
    draft_order = get_draft_order(prev_season, conn)

    # Get competitive balance eligible teams
    cb_a_teams, cb_b_teams = _get_cb_eligible_teams(conn)

    picks_created = []
    overall_pick_counter = 0

    for round_num in range(1, 21):
        # Same order every round — worst record first
        for pick_in_round, team_id in enumerate(draft_order, 1):
            overall_pick_counter += 1
            slot_val = get_slot_value(overall_pick_counter)

            conn.execute("""
                INSERT INTO draft_pick_ownership
                (season, round, pick_number, original_team_id, current_owner_team_id,
                 is_cb_pick, slot_value)
                VALUES (?, ?, ?, ?, ?, 0, ?)
            """, (season, round_num, pick_in_round, team_id, team_id, slot_val))

            picks_created.append({
                "season": season,
                "round": round_num,
                "pick": pick_in_round,
                "owner_team_id": team_id,
                "is_cb_pick": False,
                "slot_value": slot_val,
            })

        # Insert CB-A picks after round 1
        if round_num == 1:
            for cb_idx, cb_team_id in enumerate(cb_a_teams):
                overall_pick_counter += 1
                slot_val = get_slot_value(overall_pick_counter)
                cb_pick_num = 30 + cb_idx + 1  # picks 31-36 in "CB-A round"

                conn.execute("""
                    INSERT OR IGNORE INTO draft_pick_ownership
                    (season, round, pick_number, original_team_id, current_owner_team_id,
                     is_cb_pick, slot_value)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (season, 1, cb_pick_num, cb_team_id, cb_team_id, slot_val))

                picks_created.append({
                    "season": season,
                    "round": 1,
                    "pick": cb_pick_num,
                    "owner_team_id": cb_team_id,
                    "is_cb_pick": True,
                    "slot_value": slot_val,
                })

        # Insert CB-B picks after round 2
        if round_num == 2:
            for cb_idx, cb_team_id in enumerate(cb_b_teams):
                overall_pick_counter += 1
                slot_val = get_slot_value(overall_pick_counter)
                cb_pick_num = 30 + cb_idx + 1

                conn.execute("""
                    INSERT OR IGNORE INTO draft_pick_ownership
                    (season, round, pick_number, original_team_id, current_owner_team_id,
                     is_cb_pick, slot_value)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (season, 2, cb_pick_num, cb_team_id, cb_team_id, slot_val))

                picks_created.append({
                    "season": season,
                    "round": 2,
                    "pick": cb_pick_num,
                    "owner_team_id": cb_team_id,
                    "is_cb_pick": True,
                    "slot_value": slot_val,
                })

    conn.commit()
    conn.close()
    return picks_created


# ============================================================
# BONUS POOL HELPERS
# ============================================================

def get_team_bonus_pool(team_id: int, season: int, db_path: str = None) -> dict:
    """
    Calculate a team's bonus pool and current spending.
    Returns {total_pool, spent, remaining, over_limit, penalty_triggered}.
    """
    conn = get_connection(db_path)

    # Sum slot values for this team's picks in rounds 1-10
    pool_row = conn.execute("""
        SELECT COALESCE(SUM(slot_value), 0) as total_pool
        FROM draft_pick_ownership
        WHERE season = ? AND current_owner_team_id = ? AND round <= 10
    """, (season, team_id)).fetchone()
    total_pool = pool_row["total_pool"]

    # Sum signed amounts for this team's picks in rounds 1-10
    spent_row = conn.execute("""
        SELECT COALESCE(SUM(signed_amount), 0) as spent
        FROM draft_pick_ownership
        WHERE season = ? AND current_owner_team_id = ? AND round <= 10
          AND signed_amount IS NOT NULL
    """, (season, team_id)).fetchone()
    spent = spent_row["spent"]

    remaining = total_pool - spent
    over_limit = spent > total_pool
    # Penalty: exceeding pool by more than 5%
    penalty_threshold = total_pool * 1.05
    penalty_triggered = spent > penalty_threshold

    conn.close()
    return {
        "total_pool": total_pool,
        "spent": spent,
        "remaining": remaining,
        "over_limit": over_limit,
        "penalty_triggered": penalty_triggered,
    }


def record_signing_amount(season: int, round_num: int, pick_number: int,
                          amount: int, db_path: str = None):
    """Record the actual signing bonus for a pick (for bonus pool tracking)."""
    conn = get_connection(db_path)
    conn.execute("""
        UPDATE draft_pick_ownership
        SET signed_amount = ?
        WHERE season = ? AND round = ? AND pick_number = ?
    """, (amount, season, round_num, pick_number))
    conn.commit()
    conn.close()


# ============================================================
# MAKE DRAFT PICK
# ============================================================

def make_draft_pick(team_id: int, prospect_id: int, round_num: int,
                    pick_num: int, db_path: str = None,
                    signing_amount: int = None) -> dict:
    """
    Draft a prospect - creates a real player from the prospect template.

    signing_amount: override for the signing bonus. If None, uses slot value.
    If the prospect doesn't sign (signability check), returns failure info.
    """
    conn = get_connection(db_path)

    prospect = conn.execute("SELECT * FROM draft_prospects WHERE id=? AND is_drafted=0",
                           (prospect_id,)).fetchone()
    if not prospect:
        conn.close()
        return {"error": "Prospect not found or already drafted"}

    p = dict(prospect)

    # --- Signability check ---
    signability = p.get("signability", 100)
    if not _check_signability(signability):
        # Player doesn't sign — mark as drafted but no player created
        conn.execute("""
            UPDATE draft_prospects SET is_drafted=1, drafted_by_team_id=?,
                draft_round=?, draft_pick=? WHERE id=?
        """, (team_id, round_num, pick_num, prospect_id))

        # Log the failed signing
        conn.execute("""
            INSERT INTO transactions (transaction_date, transaction_type, details_json,
                team1_id, player_ids)
            VALUES (?, 'draft_pick_unsigned', ?, ?, ?)
        """, (f"{p['season']}-07-15",
              json.dumps({"round": round_num, "pick": pick_num,
                         "prospect_name": f"{p['first_name']} {p['last_name']}",
                         "signability": signability,
                         "comp_pick_earned": True}),
              team_id, ""))

        conn.commit()
        conn.close()
        return {
            "success": False,
            "unsigned": True,
            "name": f"{p['first_name']} {p['last_name']}",
            "signability": signability,
            "round": round_num,
            "pick": pick_num,
            "message": f"{p['first_name']} {p['last_name']} has declined to sign. "
                       f"Team earns a compensatory pick in next year's draft.",
        }

    # --- Resolve actual ratings from floor/ceiling range ---
    contact = random.randint(p["contact_floor"], p["contact_ceiling"])
    power = random.randint(p["power_floor"], p["power_ceiling"])
    speed = random.randint(p["speed_floor"], p["speed_ceiling"])
    fielding = random.randint(p["fielding_floor"], p["fielding_ceiling"])
    arm = random.randint(p["arm_floor"], p["arm_ceiling"])
    stuff = random.randint(p["stuff_floor"], p["stuff_ceiling"])
    control = random.randint(p["control_floor"], p["control_ceiling"])

    # --- Determine signing bonus ---
    # Calculate overall pick number for slot value
    overall_pick = (round_num - 1) * 30 + pick_num
    slot_val = get_slot_value(overall_pick)

    if signing_amount is None:
        # Default: use prospect's signing demand as % of slot
        demand_pct = p.get("signing_demand", 100)
        signing_bonus = int(slot_val * demand_pct / 100)
    else:
        signing_bonus = signing_amount

    # Record signing amount for bonus pool tracking
    record_signing_amount(p["season"], round_num, pick_num, signing_bonus, db_path)

    # --- Create the player ---
    cursor = conn.execute("""
        INSERT INTO players (team_id, first_name, last_name, age, bats, throws,
            position, contact_rating, power_rating, speed_rating, fielding_rating,
            arm_rating, stuff_rating, control_rating, stamina_rating,
            contact_potential, power_potential, speed_potential, fielding_potential,
            arm_potential, stuff_potential, control_potential, stamina_potential,
            ego, leadership, work_ethic, clutch, durability,
            roster_status, peak_age, development_rate, option_years_remaining)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, 'minors_low', ?, ?, 3)
    """, (team_id, p["first_name"], p["last_name"], p["age"], p["bats"], p["throws"],
          p["position"], contact, power, speed, fielding, arm, stuff, control,
          random.randint(30, 70),
          p["contact_ceiling"], p["power_ceiling"], p["speed_ceiling"],
          p["fielding_ceiling"], p["arm_ceiling"], p["stuff_ceiling"],
          p["control_ceiling"], random.randint(30, 70),
          random.randint(20, 80), random.randint(20, 70),
          random.randint(30, 90), random.randint(20, 80), random.randint(30, 90),
          random.randint(24, 29), round(random.uniform(0.7, 1.3), 2)))

    player_id = cursor.lastrowid

    # Create rookie contract with the determined signing bonus
    conn.execute("""
        INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
            annual_salary, signing_bonus, signed_date)
        VALUES (?, ?, 4, 4, 720000, ?, ?)
    """, (player_id, team_id, signing_bonus,
          f"{p['season']}-07-15"))

    # Mark prospect as drafted
    conn.execute("""
        UPDATE draft_prospects SET is_drafted=1, drafted_by_team_id=?,
            draft_round=?, draft_pick=? WHERE id=?
    """, (team_id, round_num, pick_num, prospect_id))

    # Log transaction
    conn.execute("""
        INSERT INTO transactions (transaction_date, transaction_type, details_json,
            team1_id, player_ids)
        VALUES (?, 'draft_pick', ?, ?, ?)
    """, (f"{p['season']}-07-15",
          json.dumps({"round": round_num, "pick": pick_num,
                     "prospect_name": f"{p['first_name']} {p['last_name']}",
                     "slot_value": slot_val,
                     "signing_bonus": signing_bonus,
                     "signability": signability}),
          team_id, str(player_id)))

    # Check bonus pool penalty
    pool_info = get_team_bonus_pool(team_id, p["season"], db_path)
    if pool_info["penalty_triggered"]:
        # Log the penalty — team loses a future 1st-round pick
        conn.execute("""
            INSERT INTO transactions (transaction_date, transaction_type, details_json,
                team1_id, player_ids)
            VALUES (?, 'bonus_pool_penalty', ?, ?, '')
        """, (f"{p['season']}-07-15",
              json.dumps({"team_id": team_id,
                         "pool_total": pool_info["total_pool"],
                         "pool_spent": pool_info["spent"],
                         "overage_pct": round((pool_info["spent"] / pool_info["total_pool"] - 1) * 100, 1)
                         if pool_info["total_pool"] > 0 else 0,
                         "penalty": "loss_of_future_first_round_pick"}),
              team_id))

    # Send notification if drafted by user's team
    state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
    user_team_id = state["user_team_id"] if state else None
    if team_id == user_team_id:
        from .messages import send_draft_notification
        player_name = f"{p['first_name']} {p['last_name']}"
        team = conn.execute("SELECT city, name FROM teams WHERE id=?", (team_id,)).fetchone()
        team_name = f"{team['city']} {team['name']}" if team else "Your Team"
        send_draft_notification(user_team_id, player_name, round_num, pick_num, team_name, db_path=db_path)

    conn.commit()
    conn.close()

    return {
        "success": True,
        "player_id": player_id,
        "name": f"{p['first_name']} {p['last_name']}",
        "position": p["position"],
        "round": round_num,
        "pick": pick_num,
        "slot_value": slot_val,
        "signing_bonus": signing_bonus,
        "signability": signability,
    }
