"""
Front Office - Waiver Wire System
Handles DFA waiver claims, processing, and clearing waivers.
"""
import random
from ..database.db import get_connection, query


def process_waivers(game_date: str, db_path: str = None) -> list:
    """
    Process all pending waiver claims that have reached their expiry date.
    AI teams evaluate players on waivers and may claim them.
    Returns list of waiver outcomes.
    """
    conn = get_connection(db_path)
    outcomes = []

    # Find all expired pending waivers
    pending = conn.execute("""
        SELECT wc.*, p.first_name, p.last_name, p.position, p.age,
               p.contact_rating, p.power_rating, p.speed_rating,
               p.fielding_rating, p.stuff_rating, p.control_rating,
               p.stamina_rating
        FROM waiver_claims wc
        JOIN players p ON p.id = wc.player_id
        WHERE wc.expiry_date <= ? AND wc.status = 'pending'
    """, (game_date,)).fetchall()

    if not pending:
        conn.close()
        return outcomes

    # Get all teams for claim evaluation
    teams = conn.execute("SELECT id FROM teams").fetchall()
    user_state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
    user_team_id = user_state["user_team_id"] if user_state else None

    for claim in pending:
        # Calculate player overall rating
        is_pitcher = claim["position"] in ("SP", "RP")
        if is_pitcher:
            overall = (claim["stuff_rating"] * 2 + claim["control_rating"] * 1.5 +
                       claim["stamina_rating"] * 0.5) / 4
        else:
            overall = (claim["contact_rating"] * 1.5 + claim["power_rating"] * 1.5 +
                       claim["speed_rating"] * 0.5 + claim["fielding_rating"] * 0.5) / 4

        claimed = False
        claiming_team_id = None

        # Only evaluate if player is above threshold (overall >= 50)
        if overall >= 50:
            # Shuffle teams for random priority order
            team_ids = [t["id"] for t in teams
                        if t["id"] != claim["original_team_id"] and t["id"] != user_team_id]
            random.shuffle(team_ids)

            for team_id in team_ids:
                # Check if team has positional need
                pos = claim["position"]
                best_at_pos = conn.execute("""
                    SELECT MAX(
                        CASE WHEN position IN ('SP','RP')
                            THEN stuff_rating + control_rating + stamina_rating
                            ELSE contact_rating + power_rating + speed_rating + fielding_rating
                        END
                    ) as best
                    FROM players
                    WHERE team_id=? AND position=? AND roster_status='active'
                """, (team_id, pos)).fetchone()

                has_need = (best_at_pos["best"] or 0) < 180  # weak spot

                # ~30% base claim chance, higher with need
                claim_chance = 0.30 if has_need else 0.10
                if random.random() < claim_chance:
                    # Check 40-man space (active + injured only)
                    forty_man = conn.execute("""
                        SELECT COUNT(*) as c FROM players
                        WHERE team_id=? AND roster_status IN ('active', 'injured_dl')
                    """, (team_id,)).fetchone()["c"]

                    if forty_man < 40:
                        claimed = True
                        claiming_team_id = team_id
                        break

        if claimed:
            # Move player to claiming team
            conn.execute("""
                UPDATE players SET team_id=?, roster_status='active',
                    on_forty_man=1
                WHERE id=?
            """, (claiming_team_id, claim["player_id"]))
            conn.execute("""
                UPDATE waiver_claims SET status='claimed', claiming_team_id=?
                WHERE id=?
            """, (claiming_team_id, claim["id"]))
            # Update contract team if exists
            conn.execute("""
                UPDATE contracts SET team_id=? WHERE player_id=?
            """, (claiming_team_id, claim["player_id"]))

            outcomes.append({
                "player_id": claim["player_id"],
                "name": f"{claim['first_name']} {claim['last_name']}",
                "status": "claimed",
                "claiming_team_id": claiming_team_id,
                "original_team_id": claim["original_team_id"],
            })
        else:
            # Player clears waivers — original team can send to minors or release.
            # AI teams: send to minors if they have minor-league depth room,
            # otherwise release outright.
            conn.execute("""
                UPDATE waiver_claims SET status='cleared' WHERE id=?
            """, (claim["id"],))

            # Check if original team still exists and wants to keep the player
            orig_team = claim["original_team_id"]
            user_state_row = conn.execute(
                "SELECT user_team_id FROM game_state WHERE id=1"
            ).fetchone()
            user_tid = user_state_row["user_team_id"] if user_state_row else None

            if orig_team and orig_team != user_tid:
                # AI team: send to minors if overall >= 40, else release
                if overall >= 40:
                    conn.execute("""
                        UPDATE players SET roster_status='minors_aaa',
                            on_forty_man=0
                        WHERE id=?
                    """, (claim["player_id"],))
                    outcomes.append({
                        "player_id": claim["player_id"],
                        "name": f"{claim['first_name']} {claim['last_name']}",
                        "status": "outrighted_to_minors",
                        "original_team_id": orig_team,
                    })
                else:
                    # Release — becomes free agent
                    conn.execute("""
                        UPDATE players SET roster_status='free_agent',
                            team_id=NULL, on_forty_man=0
                        WHERE id=?
                    """, (claim["player_id"],))
                    outcomes.append({
                        "player_id": claim["player_id"],
                        "name": f"{claim['first_name']} {claim['last_name']}",
                        "status": "released",
                        "original_team_id": orig_team,
                    })
            else:
                # User's team or unknown — mark as cleared, let user decide
                conn.execute("""
                    UPDATE players SET roster_status='cleared_waivers',
                        on_forty_man=0
                    WHERE id=?
                """, (claim["player_id"],))
                outcomes.append({
                    "player_id": claim["player_id"],
                    "name": f"{claim['first_name']} {claim['last_name']}",
                    "status": "cleared",
                    "original_team_id": orig_team,
                })

    conn.commit()
    conn.close()
    return outcomes
