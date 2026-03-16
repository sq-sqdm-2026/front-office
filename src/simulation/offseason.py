"""
Front Office - Offseason Sequence
Handles the structured offseason flow: contract expirations, arbitration,
free agency hot stove, amateur draft, and spring training prep.
"""
from ..database.db import query, execute
from ..transactions.contracts import process_arbitration, expire_contracts
from ..transactions.free_agency import process_free_agency_day


def process_offseason_day(game_date: str, season: int, db_path: str = None) -> dict:
    """
    Handle one day of offseason processing.

    Offseason phases:
    - Day 1-7: Contract expirations + arbitration
    - Day 8-60: Free agency hot stove
    - Day 61: Amateur draft
    - Day 62-90: More free agency
    - Day 90+: Spring training prep
    """
    # Calculate which offseason day we're on
    # Offseason starts after regular season ends (roughly Nov 1)
    from datetime import date
    current = date.fromisoformat(game_date)

    # Determine offseason start date (Nov 1 of the season year)
    offseason_start = date(season, 11, 1)
    if current < offseason_start:
        # We might be in early-year offseason (Jan-Feb before spring training)
        offseason_start = date(season - 1, 11, 1)

    offseason_day = (current - offseason_start).days + 1
    offseason_day = max(1, offseason_day)

    events = {
        "date": game_date,
        "offseason_day": offseason_day,
        "phase": "",
        "events": [],
    }

    # Day 1-7: Contract expirations + arbitration
    if 1 <= offseason_day <= 7:
        events["phase"] = "contract_expirations"
        if offseason_day == 1:
            expired = expire_contracts(season, db_path)
            events["events"].append({
                "type": "contracts_expired",
                "count": len(expired),
                "players": expired[:10],  # Cap display at 10
            })
        if offseason_day == 3:
            arb_results = process_arbitration(season, db_path)
            events["events"].append({
                "type": "arbitration",
                "count": len(arb_results),
                "results": arb_results[:10],
            })

    # Day 8-60: Free agency hot stove
    elif 8 <= offseason_day <= 60:
        events["phase"] = "free_agency"
        fa_events = process_free_agency_day(game_date, offseason_day, db_path)
        if fa_events:
            signings = [e for e in fa_events if e["type"] == "signing"]
            offers = [e for e in fa_events if e["type"] == "offer"]
            events["events"].append({
                "type": "free_agency_activity",
                "signings": len(signings),
                "offers": len(offers),
                "details": signings[:5],  # Show top 5 signings
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
            # Simple draft order (reverse standings would be ideal, but keep simple)
            import random
            team_order = [t["id"] for t in teams]
            random.shuffle(team_order)

            draft_picks = []
            pick_num = 1
            for team_id in team_order:
                if team_id == user_team_id:
                    # Skip user's pick - they draft manually
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
        # Transition to spring training phase
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
