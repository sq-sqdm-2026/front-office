"""
Front Office - Injury System
Random injuries weighted by durability, position, and fatigue.
"""
import random
from ..database.db import get_connection, query

INJURY_TYPES = {
    # (name, min_days, max_days, severity_weight, il_tier)
    # IL tiers: 10-day (for position players), 15-day (for pitchers), 60-day (for severe)
    #
    # === SOFT TISSUE / MUSCLE STRAINS ===
    "hamstring_strain": ("Hamstring strain", 10, 30, 3, "10-day"),
    "hamstring_tear": ("Hamstring tear", 42, 90, 0.4, "60-day"),
    "oblique_strain": ("Oblique strain", 14, 35, 2, "15-day"),
    "groin_strain": ("Groin strain", 14, 42, 2, "15-day"),
    "quad_strain": ("Quadriceps strain", 10, 28, 2, "10-day"),
    "quad_contusion": ("Quadriceps contusion", 5, 14, 3, "10-day"),
    "calf_strain": ("Calf strain", 10, 28, 2, "10-day"),
    "calf_cramp": ("Calf cramp", 1, 5, 5, "10-day"),
    "hip_flexor_strain": ("Hip flexor strain", 10, 28, 2, "10-day"),
    "hip_impingement": ("Hip impingement", 14, 60, 0.5, "60-day"),
    "abdominal_strain": ("Abdominal strain", 10, 28, 2, "10-day"),
    "intercostal_strain": ("Intercostal strain", 14, 35, 1, "15-day"),
    "adductor_strain": ("Adductor strain", 10, 28, 2, "10-day"),
    "lat_strain": ("Lat strain", 21, 45, 1, "15-day"),
    "pectoral_strain": ("Pectoral strain", 14, 42, 0.8, "15-day"),
    "triceps_strain": ("Triceps strain", 10, 28, 1.5, "10-day"),
    "biceps_tendinitis": ("Biceps tendinitis", 14, 35, 1, "15-day"),
    #
    # === BACK & SPINE ===
    "back_spasms": ("Back spasms", 3, 14, 4, "10-day"),
    "lower_back_strain": ("Lower back strain", 10, 28, 2, "10-day"),
    "lumbar_disc": ("Lumbar disc issue", 21, 90, 0.3, "60-day"),
    "thoracic_strain": ("Thoracic spine strain", 7, 21, 2, "10-day"),
    "neck_stiffness": ("Neck stiffness", 3, 10, 3, "10-day"),
    "cervical_strain": ("Cervical strain", 7, 21, 2, "10-day"),
    #
    # === SHOULDER ===
    "shoulder_inflammation": ("Shoulder inflammation", 7, 21, 3, "10-day"),
    "shoulder_impingement": ("Shoulder impingement", 14, 42, 1, "15-day"),
    "rotator_cuff_strain": ("Rotator cuff strain", 21, 60, 0.5, "15-day"),
    "rotator_cuff_tear": ("Rotator cuff tear", 120, 365, 0.1, "60-day"),
    "labrum_tear": ("Labrum tear", 90, 270, 0.15, "60-day"),
    "shoulder_subluxation": ("Shoulder subluxation", 14, 42, 0.5, "15-day"),
    "ac_joint_sprain": ("AC joint sprain", 10, 28, 1, "10-day"),
    "shoulder_tendinitis": ("Shoulder tendinitis", 10, 28, 2, "10-day"),
    #
    # === ELBOW & ARM ===
    "elbow_soreness": ("Elbow soreness", 5, 15, 2, "10-day"),
    "elbow_inflammation": ("Elbow inflammation", 10, 28, 2, "10-day"),
    "ucl_sprain": ("UCL sprain", 60, 365, 0.3, "60-day"),  # Tommy John territory
    "ucl_tear": ("UCL tear (Tommy John)", 300, 420, 0.05, "60-day"),
    "flexor_tendon_strain": ("Flexor tendon strain", 14, 42, 1, "15-day"),
    "ulnar_nerve_irritation": ("Ulnar nerve irritation", 7, 28, 1.5, "10-day"),
    "forearm_tightness": ("Forearm tightness", 7, 21, 2, "10-day"),
    "forearm_strain": ("Forearm strain", 14, 35, 1.5, "15-day"),
    "triceps_tendinitis": ("Triceps tendinitis", 10, 28, 1.5, "10-day"),
    #
    # === WRIST & HAND ===
    "wrist_inflammation": ("Wrist inflammation", 7, 21, 2, "10-day"),
    "wrist_sprain": ("Wrist sprain", 7, 28, 2, "10-day"),
    "hamate_fracture": ("Hamate bone fracture", 28, 56, 0.4, "15-day"),
    "hand_fracture": ("Hand fracture", 28, 60, 0.5, "15-day"),
    "finger_sprain": ("Finger sprain", 5, 14, 3, "10-day"),
    "finger_fracture": ("Finger fracture", 21, 42, 0.8, "15-day"),
    "thumb_sprain": ("Thumb sprain", 7, 21, 2, "10-day"),
    "thumb_ucl": ("Thumb UCL sprain", 14, 35, 1, "15-day"),
    "jammed_finger": ("Jammed finger", 3, 10, 4, "10-day"),
    "hand_contusion": ("Hand contusion", 3, 14, 3, "10-day"),
    #
    # === KNEE ===
    "knee_contusion": ("Knee contusion", 5, 21, 2, "10-day"),
    "knee_sprain": ("Knee sprain", 10, 35, 1.5, "15-day"),
    "torn_acl": ("Torn ACL", 180, 365, 0.1, "60-day"),
    "mcl_sprain": ("MCL sprain", 14, 42, 0.8, "15-day"),
    "torn_meniscus": ("Torn meniscus", 28, 90, 0.3, "60-day"),
    "knee_inflammation": ("Knee inflammation", 5, 14, 3, "10-day"),
    "patellar_tendinitis": ("Patellar tendinitis", 10, 28, 2, "10-day"),
    "knee_bone_bruise": ("Knee bone bruise", 14, 42, 1, "15-day"),
    #
    # === ANKLE & FOOT ===
    "ankle_sprain": ("Ankle sprain", 7, 28, 3, "10-day"),
    "high_ankle_sprain": ("High ankle sprain", 21, 56, 0.5, "15-day"),
    "achilles_tendinitis": ("Achilles tendinitis", 14, 42, 1, "15-day"),
    "achilles_tear": ("Achilles tendon tear", 180, 365, 0.05, "60-day"),
    "plantar_fasciitis": ("Plantar fasciitis", 14, 60, 0.5, "15-day"),
    "foot_fracture": ("Foot fracture", 28, 60, 0.4, "15-day"),
    "toe_fracture": ("Toe fracture", 14, 35, 1, "10-day"),
    "turf_toe": ("Turf toe", 7, 28, 2, "10-day"),
    "heel_contusion": ("Heel contusion", 5, 14, 3, "10-day"),
    "shin_splints": ("Shin splints", 7, 21, 2, "10-day"),
    #
    # === HEAD & FACE ===
    "concussion": ("Concussion", 7, 21, 0.5, "10-day"),
    "facial_contusion": ("Facial contusion", 3, 10, 3, "10-day"),
    "broken_nose": ("Broken nose", 7, 21, 1, "10-day"),
    "orbital_fracture": ("Orbital fracture", 28, 56, 0.2, "15-day"),
    "jaw_contusion": ("Jaw contusion", 5, 14, 2, "10-day"),
    "dental_injury": ("Dental injury", 1, 3, 4, "10-day"),
    #
    # === TORSO ===
    "rib_fracture": ("Rib fracture", 21, 45, 0.3, "15-day"),
    "rib_contusion": ("Rib contusion", 5, 14, 3, "10-day"),
    "collarbone_fracture": ("Collarbone fracture", 42, 90, 0.2, "60-day"),
    "sternum_contusion": ("Sternum contusion", 5, 14, 2, "10-day"),
    #
    # === ILLNESS & OTHER ===
    "flu": ("Flu / viral illness", 2, 7, 4, "10-day"),
    "food_poisoning": ("Food poisoning", 1, 3, 4, "10-day"),
    "dehydration": ("Dehydration", 1, 3, 5, "10-day"),
    "heat_exhaustion": ("Heat exhaustion", 1, 5, 3, "10-day"),
    "appendicitis": ("Appendicitis", 14, 28, 0.1, "15-day"),
    "eye_irritation": ("Eye irritation", 1, 5, 4, "10-day"),
    #
    # === HIT BY PITCH INJURIES ===
    "hbp_bruise": ("Bruise (hit by pitch)", 1, 7, 4, "10-day"),
    "hbp_rib": ("Rib injury (hit by pitch)", 7, 21, 1, "10-day"),
    "hbp_hand": ("Hand injury (hit by pitch)", 7, 28, 1.5, "10-day"),
    "hbp_elbow": ("Elbow injury (hit by pitch)", 5, 14, 2, "10-day"),
}

# Pitcher-specific injuries weighted higher
PITCHER_INJURIES = [
    "shoulder_inflammation", "shoulder_impingement", "shoulder_tendinitis",
    "rotator_cuff_strain", "labrum_tear",
    "elbow_soreness", "elbow_inflammation", "ucl_sprain", "ucl_tear",
    "flexor_tendon_strain", "ulnar_nerve_irritation",
    "forearm_tightness", "forearm_strain",
    "lat_strain", "oblique_strain", "intercostal_strain",
    "biceps_tendinitis", "triceps_tendinitis", "triceps_strain",
    "back_spasms", "lower_back_strain",
    "finger_sprain", "jammed_finger",
    "knee_inflammation", "ankle_sprain",
]
POSITION_INJURIES = [
    "hamstring_strain", "hamstring_tear",
    "quad_strain", "quad_contusion",
    "calf_strain", "calf_cramp",
    "groin_strain", "hip_flexor_strain", "adductor_strain",
    "ankle_sprain", "high_ankle_sprain",
    "knee_contusion", "knee_sprain", "mcl_sprain", "patellar_tendinitis",
    "wrist_inflammation", "wrist_sprain",
    "hand_contusion", "finger_sprain", "finger_fracture", "thumb_sprain",
    "hamate_fracture", "jammed_finger",
    "oblique_strain", "abdominal_strain",
    "back_spasms", "lower_back_strain",
    "turf_toe", "plantar_fasciitis", "shin_splints", "heel_contusion",
    "concussion", "hbp_bruise", "hbp_hand",
    "flu", "dehydration",
]


def check_injuries_for_day(game_date: str, db_path: str = None) -> list:
    """Check for new injuries and update healing for existing ones."""
    conn = get_connection(db_path)
    events = []

    # Load medical staff budgets for healing rate bonus
    team_medical_budgets = {}
    teams_for_medical = conn.execute("SELECT id, medical_staff_budget FROM teams").fetchall()
    for t in teams_for_medical:
        team_medical_budgets[t["id"]] = t.get("medical_staff_budget") or 10_000_000

    # Heal existing injuries
    healing = conn.execute("""
        SELECT id, first_name, last_name, team_id, injury_days_remaining
        FROM players WHERE is_injured=1 AND injury_days_remaining > 0
    """).fetchall()

    for p in healing:
        # Medical budget affects healing rate:
        # $5M = 1 day/day, $10M = 1 day/day, $15M = ~15% chance of extra healing day,
        # $20M+ = ~25% chance of extra healing day (recover faster)
        med_budget = team_medical_budgets.get(p["team_id"], 10_000_000)
        heal_rate = 1  # base: 1 day healed per day
        if med_budget > 10_000_000:
            bonus_chance = min(0.30, (med_budget - 10_000_000) / 40_000_000)
            if random.random() < bonus_chance:
                heal_rate = 2  # lucky extra healing day
        new_days = p["injury_days_remaining"] - heal_rate
        if new_days <= 0:
            conn.execute("""
                UPDATE players SET is_injured=0, injury_type=NULL,
                    injury_days_remaining=0, il_tier=NULL, roster_status='active'
                WHERE id=?
            """, (p["id"],))

            # Send notification if player is on user's team
            state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
            user_team_id = state["user_team_id"] if state else None
            if p["team_id"] == user_team_id:
                from .messages import send_injury_activation_message
                player_name = f"{p['first_name']} {p['last_name']}"
                send_injury_activation_message(user_team_id, player_name, db_path=db_path)

            events.append({
                "type": "injury_return",
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "team_id": p["team_id"],
            })
        else:
            conn.execute("UPDATE players SET injury_days_remaining=? WHERE id=?",
                        (new_days, p["id"]))

    # Check for new injuries (only active players)
    active = conn.execute("""
        SELECT id, first_name, last_name, team_id, position, durability, age
        FROM players WHERE roster_status='active' AND is_injured=0
    """).fetchall()

    # Load pitcher fatigue data for overuse injury calculation
    all_teams_fatigue = {}
    teams_data = conn.execute("SELECT id, team_strategy_json, medical_staff_budget FROM teams").fetchall()
    for t in teams_data:
        if t["team_strategy_json"]:
            try:
                import json as _json
                strat = _json.loads(t["team_strategy_json"])
                all_teams_fatigue[t["id"]] = strat.get("pitcher_fatigue", {})
            except:
                pass

    # Build medical budget lookup (higher budget = faster recovery, fewer injuries)
    medical_budgets = {t["id"]: (t["medical_staff_budget"] or 10_000_000) for t in teams_data}

    from datetime import datetime
    current = datetime.fromisoformat(game_date).date()

    for p in active:
        # Base injury chance per day: ~0.15% (roughly 1 injury per 3 weeks per player)
        # Adjusted by durability (20=2x chance, 80=0.5x chance)
        base_chance = 0.0015
        durability_mod = 2.0 - (p["durability"] / 50)  # 20->1.6, 50->1.0, 80->0.4
        age_mod = 1.0 + max(0, (p["age"] - 30) * 0.03)  # older = more injury prone

        # Pitcher fatigue/overuse modifier: pitchers used on back-to-back days
        # or with high recent pitch counts are more injury prone
        fatigue_mod = 1.0
        if p["position"] in ("SP", "RP") and p["team_id"] in all_teams_fatigue:
            pitcher_fatigue = all_teams_fatigue[p["team_id"]].get(str(p["id"]))
            if pitcher_fatigue:
                try:
                    last_game = datetime.fromisoformat(pitcher_fatigue["last_game_date"]).date()
                    days_since = (current - last_game).days
                    rest_needed = pitcher_fatigue.get("rest_days_needed", 1)
                    if days_since < rest_needed:
                        # Overworked: significant injury risk increase
                        fatigue_mod = 1.5 + (rest_needed - days_since) * 0.3
                    pitches_last = pitcher_fatigue.get("last_pitch_count", 0)
                    if pitches_last > 100:
                        # High pitch count previous outing
                        fatigue_mod *= 1.0 + (pitches_last - 100) * 0.01
                except (ValueError, KeyError):
                    pass

        # Medical staff budget modifier: better staff = fewer injuries
        # $5M budget = 1.15x injury rate, $10M = 1.0x, $15M = 0.90x, $20M = 0.85x
        team_medical = medical_budgets.get(p["team_id"], 10_000_000)
        medical_mod = 1.0 - (team_medical - 10_000_000) / 100_000_000  # scales around $10M baseline
        medical_mod = max(0.80, min(1.20, medical_mod))

        chance = base_chance * durability_mod * age_mod * fatigue_mod * medical_mod

        if random.random() < chance:
            # Pick injury type based on position
            is_pitcher = p["position"] in ("SP", "RP")
            pool = PITCHER_INJURIES if is_pitcher else POSITION_INJURIES
            injury_key = random.choice(pool)
            injury = INJURY_TYPES[injury_key]

            days = random.randint(injury[1], injury[2])
            il_tier = injury[4] if len(injury) > 4 else "10-day"

            conn.execute("""
                UPDATE players SET is_injured=1, injury_type=?,
                    injury_days_remaining=?, il_tier=?, roster_status='injured_dl'
                WHERE id=?
            """, (injury[0], days, il_tier, p["id"]))

            # Send notification if player is on user's team
            state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
            user_team_id = state["user_team_id"] if state else None
            if p["team_id"] == user_team_id:
                from .messages import send_injury_message
                player_name = f"{p['first_name']} {p['last_name']}"
                send_injury_message(user_team_id, player_name, il_tier, db_path=db_path)

            events.append({
                "type": "new_injury",
                "player_id": p["id"],
                "name": f"{p['first_name']} {p['last_name']}",
                "team_id": p["team_id"],
                "injury": injury[0],
                "days": days,
                "il_tier": il_tier,
            })

    conn.commit()
    conn.close()
    return events
