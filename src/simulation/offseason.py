"""
Front Office - Offseason Sequence
Handles the structured offseason flow: contract expirations, arbitration,
free agency, Rule 5 draft, amateur draft, international signings, and spring training prep.
"""
import json
import random
from datetime import date
from ..database.db import query, execute, get_connection
from ..transactions.contracts import (
    process_arbitration, expire_contracts, process_vesting_options,
    process_incentive_bonuses, determine_arb_eligibility, process_non_tender_decisions
)
from ..transactions.free_agency import process_free_agency_day
from ..transactions.international_fa import generate_international_prospects, process_international_signings
from ..financial.economics import save_season_finances
from ..simulation.player_development import process_offseason_development


def process_offseason_day(game_date: str, season: int, db_path: str = None) -> dict:
    """
    Handle one day of offseason processing.

    Offseason phases:
    - Day 1-7: Contract expirations + arbitration
    - Day 8: Rule 5 Draft
    - Day 9-60: Free agency hot stove
    - Day 61: Amateur draft
    - Day 62-90: More free agency
    - Day 90+: Spring training prep
    """
    current = date.fromisoformat(game_date)

    # Determine offseason start date (Nov 1 of the season year)
    offseason_start = date(season, 11, 1)
    if current < offseason_start:
        offseason_start = date(season - 1, 11, 1)

    offseason_day = (current - offseason_start).days + 1
    offseason_day = max(1, offseason_day)

    events = {
        "date": game_date,
        "offseason_day": offseason_day,
        "phase": "",
        "events": [],
    }

    # Day 1-7: Contract expirations + arbitration + vesting/incentives
    if 1 <= offseason_day <= 7:
        events["phase"] = "contract_expirations"
        if offseason_day == 1:
            # Process vesting options first
            vesting_results = process_vesting_options(season, db_path)
            if vesting_results:
                events["events"].append({
                    "type": "vesting_options",
                    "count": len(vesting_results),
                    "details": vesting_results[:5],
                })

            # Process incentive bonuses from last year
            bonus_results = process_incentive_bonuses(season - 1, db_path)
            if bonus_results:
                events["events"].append({
                    "type": "incentive_bonuses_paid",
                    "count": len(bonus_results),
                    "details": bonus_results[:5],
                })

            expired = expire_contracts(season, db_path)
            events["events"].append({
                "type": "contracts_expired",
                "count": len(expired),
                "players": expired[:10],
            })
        if offseason_day == 2:
            # Determine arb eligibility including Super 2
            arb_updates = determine_arb_eligibility(season, db_path)
            events["events"].append({
                "type": "arb_eligibility_determined",
                "count": len(arb_updates),
                "details": arb_updates[:10],
            })
        if offseason_day == 3:
            arb_results = process_arbitration(season, db_path)
            events["events"].append({
                "type": "arbitration",
                "count": len(arb_results),
                "results": arb_results[:10],
            })
        if offseason_day == 5:
            # Process non-tender decisions
            non_tendered = process_non_tender_decisions(season, db_path)
            if non_tendered:
                events["events"].append({
                    "type": "non_tenders",
                    "count": len(non_tendered),
                    "details": non_tendered[:5],
                })
            # Process qualifying offers
            qo_results = process_qualifying_offers(season, db_path)
            if qo_results:
                events["events"].append({
                    "type": "qualifying_offers",
                    "count": qo_results.get("total", 0),
                    "details": qo_results,
                })

    # Day 8: Rule 5 Draft
    elif offseason_day == 8:
        events["phase"] = "rule_5_draft"
        rule5_results = process_rule_5_draft(season, db_path)
        events["events"].append({
            "type": "rule_5_draft",
            "picks": len(rule5_results),
            "details": rule5_results[:5],
        })

    # Day 9-60: Free agency hot stove
    elif 9 <= offseason_day <= 60:
        events["phase"] = "free_agency"
        fa_events = process_free_agency_day(game_date, offseason_day, db_path)
        if fa_events:
            signings = [e for e in fa_events if e["type"] == "signing"]
            offers = [e for e in fa_events if e["type"] == "offer"]
            events["events"].append({
                "type": "free_agency_activity",
                "signings": len(signings),
                "offers": len(offers),
                "details": signings[:5],
            })

    # Day 55: International signing period
    elif offseason_day == 55:
        events["phase"] = "international_signing"
        try:
            # Generate international prospects if not already done
            prospects = generate_international_prospects(season, db_path)

            # Process AI team signings
            signings = process_international_signings(season, db_path)
            events["events"].append({
                "type": "international_signings",
                "total_prospects": len(prospects),
                "signed": len(signings),
                "details": signings[:8],
            })
        except Exception as e:
            events["events"].append({
                "type": "international_error",
                "message": str(e),
            })

    # Day 61: Amateur draft
    elif offseason_day == 61:
        events["phase"] = "amateur_draft"
        try:
            from ..transactions.draft import generate_draft_class, make_draft_pick
            # Generate draft class if not already done
            prospects = generate_draft_class(season + 1, db_path)

            # Auto-draft for AI teams
            state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
            user_team_id = state[0]["user_team_id"] if state else None

            teams = query("SELECT id FROM teams ORDER BY id", db_path=db_path)
            import random
            team_order = [t["id"] for t in teams]
            random.shuffle(team_order)

            draft_picks = []
            pick_num = 1
            for team_id in team_order:
                if team_id == user_team_id:
                    events["events"].append({
                        "type": "your_draft_pick",
                        "round": 1,
                        "pick": pick_num,
                        "message": "It's your turn to draft!",
                    })
                    pick_num += 1
                    continue

                # AI auto-picks best available
                available = query("""
                    SELECT * FROM draft_prospects
                    WHERE season=? AND is_drafted=0
                    ORDER BY overall_rank ASC LIMIT 1
                """, (season + 1,), db_path=db_path)

                if available:
                    result = make_draft_pick(team_id, available[0]["id"], 1, pick_num, db_path)
                    if result.get("success"):
                        draft_picks.append(result)
                pick_num += 1

            events["events"].append({
                "type": "draft_complete",
                "picks_made": len(draft_picks),
            })
        except Exception as e:
            events["events"].append({
                "type": "draft_error",
                "message": str(e),
            })

    # Day 62-90: More free agency
    elif 62 <= offseason_day <= 90:
        events["phase"] = "late_free_agency"
        fa_events = process_free_agency_day(game_date, offseason_day, db_path)
        if fa_events:
            signings = [e for e in fa_events if e["type"] == "signing"]
            events["events"].append({
                "type": "late_fa_activity",
                "signings": len(signings),
                "details": signings[:5],
            })

    # Day 90+: Spring training prep
    else:
        events["phase"] = "spring_training_prep"
        if offseason_day == 91:
            # End of season: calculate finances and apply player development
            teams = query("SELECT id FROM teams", db_path=db_path)
            for team in teams:
                team_id = team["id"]
                save_season_finances(team_id, season, db_path)
            events["events"].append({
                "type": "season_finances_calculated",
                "teams": len(teams),
            })

            # Apply offseason player development (aging, improvements, declines)
            dev_events = process_offseason_development(season, db_path)
            if dev_events:
                events["events"].append({
                    "type": "player_development",
                    "players_changed": len(dev_events),
                    "notable": dev_events[:3],
                })

        if offseason_day >= 95:
            next_season = season + 1
            execute("""
                UPDATE game_state SET phase='spring_training', season=?
                WHERE id=1
            """, (next_season,), db_path=db_path)
            events["events"].append({
                "type": "phase_change",
                "new_phase": "spring_training",
                "new_season": next_season,
            })

    return events


def process_qualifying_offers(season: int, db_path: str = None) -> dict:
    """
    Process qualifying offers and compensation draft picks.

    Rules (simplified MLB model):
    - Teams that lose free agents eligible for QO (1+ year service, top 20% salary) receive a comp pick
    - If a player rejects the QO and signs elsewhere, their original team gets a comp pick
    - Comp picks are added at the end of the first round
    """
    conn = get_connection(db_path)
    results = {
        "total": 0,
        "qo_issued": 0,
        "qo_rejected": 0,
        "comp_picks_awarded": [],
        "picks_lost": [],
    }

    # Get all players who were signed in the previous season as free agents
    # These are QO-eligible if they have 1+ service years and top 20% salary
    fa_players = query("""
        SELECT p.id, p.first_name, p.last_name, p.team_id,
               c.annual_salary, p.service_years
        FROM players p
        JOIN contracts c ON c.player_id = p.id
        WHERE p.service_years >= 1
        AND c.signed_date LIKE ?
    """, (f"{season-1}%",), db_path=db_path)

    if not fa_players:
        conn.close()
        return results

    # Get salary distribution to determine top 20%
    all_salaries = query("""
        SELECT annual_salary FROM contracts WHERE annual_salary > 0
        ORDER BY annual_salary DESC
    """, db_path=db_path)

    if not all_salaries:
        conn.close()
        return results

    # Top 20% of all salaries
    threshold_idx = max(0, int(len(all_salaries) * 0.2))
    qo_threshold = all_salaries[threshold_idx]["annual_salary"] if threshold_idx < len(all_salaries) else 0

    # Process QO-eligible players
    comp_pick_count = 0
    for player in fa_players:
        if player["annual_salary"] >= qo_threshold:
            # This player is eligible for QO
            # 70% chance they accept QO, 30% reject and sign elsewhere
            if random.random() < 0.70:
                results["qo_issued"] += 1
            else:
                results["qo_rejected"] += 1
                # Player rejects QO and will sign elsewhere - original team gets comp pick
                original_team = player["team_id"]
                comp_pick_count += 1

                # Add compensation pick at end of first round
                # Find the next available comp pick slot
                next_pick = execute("""
                    INSERT INTO draft_pick_ownership
                    (season, round, pick_number, original_team_id, current_owner_team_id, traded_date)
                    VALUES (?, 1, 30 + ?, ?, ?, NULL)
                """, (season, comp_pick_count, original_team, original_team), db_path=db_path)

                results["comp_picks_awarded"].append({
                    "team_id": original_team,
                    "player": f"{player['first_name']} {player['last_name']}",
                    "reason": "lost_qo_free_agent",
                    "pick_round": 1,
                    "pick_number": 30 + comp_pick_count,
                })

                # Send message to user if it's their team
                state = conn.execute("SELECT user_team_id FROM game_state WHERE id=1").fetchone()
                user_team_id = state["user_team_id"] if state else None
                if original_team == user_team_id:
                    from ..transactions.messages import send_qo_compensation_message
                    player_name = f"{player['first_name']} {player['last_name']}"
                    send_qo_compensation_message(user_team_id, player_name, db_path=db_path)

    results["total"] = results["qo_issued"] + results["qo_rejected"]
    conn.commit()
    conn.close()
    return results


def process_rule_5_draft(season: int, db_path: str = None) -> list:
    """
    Process the Rule 5 Draft.

    Eligibility: Players not on 40-man roster with 5+ years in minors
    (signed at 18) or 4+ years (signed at 19+).
    Picked players must stay on 25-man roster all season or offered back.
    """
    conn = get_connection(db_path)

    # Get eligible players
    eligible = query("""
        SELECT p.*, t.id as current_team_id
        FROM players p
        JOIN teams t ON t.id = p.team_id
        WHERE p.on_forty_man = 0
        AND p.roster_status LIKE 'minors%'
        AND (
            (p.age - 18 >= 5) OR (p.age - 19 >= 4)
        )
        ORDER BY p.power_rating + p.contact_rating DESC
    """, db_path=db_path)

    if not eligible:
        return []

    # Get teams in reverse order (worst record gets first pick)
    teams = query("""
        SELECT t.id, t.city, t.name
        FROM teams t
        ORDER BY t.id
    """, db_path=db_path)

    picks = []

    # Each team gets one pick per round (simplified: just round 1)
    for team in teams:
        if not eligible:
            break

        team_id = team["id"]
        best_fit = None
        best_idx = 0

        # AI team selects player with best fit to roster needs
        # Simplified: just pick the best available overall
        for i, player in enumerate(eligible):
            if player["current_team_id"] != team_id:
                best_fit = player
                best_idx = i
                break

        if best_fit:
            # Make the pick
            player_id = best_fit["id"]

            # Transfer to new team
            conn.execute("""
                UPDATE players SET team_id=?, on_forty_man=1, roster_status='active'
                WHERE id=?
            """, (team_id, player_id))

            # Create contract
            conn.execute("""
                INSERT INTO contracts (player_id, team_id, total_years, years_remaining,
                    annual_salary, signed_date)
                VALUES (?, ?, 1, 1, 750000, ?)
            """, (player_id, team_id, date.today().isoformat()))

            # Track in transactions
            conn.execute("""
                INSERT INTO transactions (transaction_date, transaction_type,
                    details_json, team1_id, team2_id, player_ids)
                VALUES (?, 'rule_5_draft', ?, ?, ?, ?)
            """, (date.today().isoformat(),
                  json.dumps({
                      "from_team_id": best_fit["current_team_id"],
                      "to_team_id": team_id,
                      "must_remain_25_man": True,
                  }),
                  best_fit["current_team_id"], team_id, str(player_id)))

            picks.append({
                "team_id": team_id,
                "team_name": f"{team['city']} {team['name']}",
                "player_id": player_id,
                "player_name": f"{best_fit['first_name']} {best_fit['last_name']}",
                "position": best_fit["position"],
            })

            # Remove from eligible list
            eligible.pop(best_idx)

    conn.commit()
    conn.close()

    return picks
