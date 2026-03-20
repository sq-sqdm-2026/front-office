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
from ..transactions.free_agency import process_free_agency_day, process_qualifying_offers
from ..transactions.international_fa import generate_international_prospects, process_international_signings
from ..transactions.roster import process_rule_5_draft
from ..financial.economics import save_season_finances, process_end_of_season_finances
from ..financial.broadcast_stadium import apply_broadcast_deal_decrement, apply_broadcast_loyalty_penalties
from ..simulation.player_development import process_offseason_development
from ..simulation.rating_calibration import calibrate_ratings
from ..ai.career_arcs import process_career_changes


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
            # Process coaching staff contracts (poaching, promotions, expirations)
            try:
                from ..ai.coaching_staff import process_coaching_contracts, send_coaching_departure_messages
                coaching_events = process_coaching_contracts(game_date, db_path)
                if coaching_events:
                    events["events"].append({
                        "type": "coaching_changes",
                        "count": len(coaching_events),
                        "details": coaching_events[:10],
                    })
                    # Notify user about their staff departures
                    user_state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
                    if user_state and user_state[0]["user_team_id"]:
                        send_coaching_departure_messages(
                            user_state[0]["user_team_id"], game_date, coaching_events, db_path
                        )
            except Exception:
                pass
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
            # End of season: calculate finances for all teams with proper revenue sharing
            finance_results = process_end_of_season_finances(season, db_path)
            # Also apply broadcast deal decrements and loyalty penalties
            teams = query("SELECT id FROM teams", db_path=db_path)
            for team in teams:
                team_id = team["id"]
                apply_broadcast_deal_decrement(team_id, db_path)
                apply_broadcast_loyalty_penalties(team_id, db_path)
            events["events"].append({
                "type": "season_finances_calculated",
                "teams": len(finance_results),
            })

            # Apply offseason player development (aging, improvements, declines)
            dev_events = process_offseason_development(season, db_path)
            if dev_events:
                events["events"].append({
                    "type": "player_development",
                    "players_changed": len(dev_events),
                    "notable": dev_events[:3],
                })

            # Recalibrate league-wide ratings to prevent drift from 50
            cal_result = calibrate_ratings(season, db_path)
            if cal_result.get("adjustments"):
                events["events"].append({
                    "type": "rating_calibration",
                    "adjustments": cal_result["adjustments"],
                })

            # Process NPC career changes (firings, promotions, retirements)
            career_results = process_career_changes(game_date, db_path)
            career_event_count = (
                len(career_results.get("firings", []))
                + len(career_results.get("promotions", []))
                + len(career_results.get("retirements", []))
                + len(career_results.get("new_roles", []))
            )
            if career_event_count > 0:
                events["events"].append({
                    "type": "career_changes",
                    "total": career_event_count,
                    "firings": len(career_results.get("firings", [])),
                    "promotions": len(career_results.get("promotions", [])),
                    "retirements": len(career_results.get("retirements", [])),
                    "new_roles": len(career_results.get("new_roles", [])),
                    "details": career_results,
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



# process_qualifying_offers is now imported from ..transactions.free_agency
# process_rule_5_draft is now imported from ..transactions.roster
