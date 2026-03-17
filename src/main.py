"""
Front Office - Main Entry Point
Baseball Universe Simulation powered by Local LLMs.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.staticfiles import StaticFiles
from pathlib import Path

from src.api.routes import app

# ---------------------------------------------------------------------------
# Auto-fetch real MLB data and seed on first run
# ---------------------------------------------------------------------------
cache_file = Path(__file__).parent.parent / "mlb_cache.json"
db_file = Path(__file__).parent.parent / "front_office.db"

if not db_file.exists():
    # Fresh install -- need to seed the database
    if not cache_file.exists():
        # No cache yet -- fetch from MLB Stats API automatically
        print("=" * 60)
        print("First run detected -- fetching real MLB rosters...")
        print("This takes 3-5 minutes (pulling 30 teams from MLB API)")
        print("=" * 60)
        try:
            from src.database.real_data import fetch_all_mlb_data, enrich_teams_with_market_data
            import json

            data = fetch_all_mlb_data()
            data["teams"] = enrich_teams_with_market_data(data["teams"])

            with open(cache_file, "w") as f:
                json.dump(data, f, indent=2)

            total = sum(len(ps) for ps in data["players"].values())
            print(f"\nFetched {len(data['teams'])} teams, {total} players")
            print(f"Saved to {cache_file}")
        except Exception as e:
            print(f"\nFailed to fetch MLB data: {e}")
            print("Falling back to generated rosters.")
            print("You can retry by deleting front_office.db and restarting.")

    if cache_file.exists():
        print("\nSeeding database with REAL MLB data...")
        from src.database.seed_real import seed_real_database
        seed_real_database()
    else:
        print("\nSeeding database with generated data...")
        from src.database.seed import seed_database
        seed_database()
else:
    # DB already exists -- just make sure schema is up to date
    from src.database.db import init_db, migrate_add_broadcast_stadium_columns, migrate_add_eye_rating
    init_db()
    # Apply any pending migrations
    migrate_add_broadcast_stadium_columns()
    migrate_add_eye_rating()

# Ensure minimum free agents exist
try:
    from src.transactions.free_agency import ensure_minimum_free_agents
    result = ensure_minimum_free_agents(min_count=50)
    if result.get("action") == "generated":
        print(f"\nFree agents: {result.get('new_count')} total ({result.get('generated_count')} newly generated)")
except Exception as e:
    print(f"Note: Could not verify free agents on startup: {e}")

# Serve static files (frontend)
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
