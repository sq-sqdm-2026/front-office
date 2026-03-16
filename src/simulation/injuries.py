"""
Front Office - Injury System
Random injuries weighted by durability, position, and fatigue.
"""
import random
from ..database.db import get_connection, query

INJURY_TYPES = {
    # (name, min_days, max_days, severity_weight, il_tier)
    # IL tiers: 10-day (for position players), 15-day (for pitchers), 60-day (for severe)
    "hamstring_strain": ("Hamstring strain", 10, 30, 3, "10-day"),
    "oblique_strain": ("Oblique strain", 14, 35, 2, "15-day"),
    "shoulder_inflammation": ("Shoulder inflammation", 7, 21, 3, "10-day"),
    "elbow_soreness": ("Elbow soreness", 5, 15, 2, "10-day"),
    "back_spasms": ("Back spasms", 3, 14, 4, "10-day"),
    "ankle_sprain": ("Ankle sprain", 7, 28, 3, "10-day"),
    "knee_contusion": ("Knee contusion", 5, 21, 2, "10-day"),
    "wrist_inflammation": ("Wrist inflammation", 7, 21, 2, "10-day"),
    "groin_strain": ("Groin strain", 14, 42, 2, "15-day"),
    "ucl_sprain": ("UCL sprain", 60, 365, 0.3, "60-day"),  # Tommy John territory
    "torn_acl": ("Torn ACL", 180, 365, 0.1, "60-day"),
    "concussion": ("Concussion", 7, 21, 0.5, "10-day"),
    "hand_fracture": ("Hand fracture", 28, 60, 0.5, "15-day"),
    "rib_fracture": ("Rib fracture", 21, 45, 0.3, "15-day"),
    "lat_strain": ("Lat strain", 21, 45, 1, "15-day"),
    "quad_strain": ("Quad strain", 10, 28, 2, "10-day"),
    "calf_strain": ("Calf strain", 10, 28, 2, "10-day"),
    "hip_impingement": ("Hip impingement", 14, 60, 0.5, "60-day"),
    "forearm_tightness": ("Forearm tightness", 7, 21, 2, "10-day"),
    "neck_stiffness": ("Neck stiffness", 3, 10, 3, "10-day"),
}

# Pitcher-specific injuries weighted higher
PITCHER_INJURIES = ["shoulder_inflammation", "elbow_soreness", "ucl_sprain",
                     "lat_strain", "forearm_tightness", "oblique_strain"]
POSITION_INJURIES = ["hamstring_strain", "ankle_sprain", "knee_contusion",
                      "groin_strain", "quad_strain", "calf_strain", "wrist_inflammation"]


def check_injuries_for_day(game_date: str, db_path: str = None) -> list:
    """Check for new injuries and update healing for existing ones."""
    conn = get_connection(db_path)
    events = []

    # Heal existing injuries
    healing = conn.execute("""
        SELECT id, first_name, last_name, team_id, injury_days_remaining
        FROM players WHERE is_injured=1 AND injury_days_remaining > 0
    """).fetchall()

    for p in healing:
        new_days = p["injury_days_remaining"] - 1
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

    for p in active:
        # Base injury chance per day: ~0.15% (roughly 1 injury per 3 weeks per player)
        # Adjusted by durability (20=2x chance, 80=0.5x chance)
        base_chance = 0.0015
        durability_mod = 2.0 - (p["durability"] / 50)  # 20->1.6, 50->1.0, 80->0.4
        age_mod = 1.0 + max(0, (p["age"] - 30) * 0.03)  # older = more injury prone

        chance = base_chance * durability_mod * age_mod

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
