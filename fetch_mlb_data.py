#!/usr/bin/env python3
"""
Fetch real MLB player/team data and save to mlb_cache.json.
Run this on a machine with internet access (e.g., Mac Mini).

Usage:
    python fetch_mlb_data.py           # Fetch all 30 teams
    python fetch_mlb_data.py --quick   # Fetch just 1 team (NYY) for testing

After running, restart the server with a fresh DB:
    rm front_office.db
    python -m src.main
"""
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database.real_data import fetch_all_mlb_data, enrich_teams_with_market_data

CACHE_PATH = Path(__file__).parent / "mlb_cache.json"


def main():
    print("=" * 60)
    print("MLB Stats API -> Front Office Data Fetcher")
    print("=" * 60)
    print()

    data = fetch_all_mlb_data()
    data["teams"] = enrich_teams_with_market_data(data["teams"])

    # Save to cache
    with open(CACHE_PATH, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nSaved to {CACHE_PATH}")
    print(f"  Teams: {len(data['teams'])}")
    total = sum(len(ps) for ps in data["players"].values())
    print(f"  Players: {total}")

    # Spot check key players
    print("\n--- SPOT CHECK ---")
    checks = [
        ("PIT", "Skenes"),
        ("LAD", "Ohtani"),
        ("NYY", "Judge"),
        ("PHI", "Harper"),
        ("NYM", "Soto"),
    ]
    for abbr, name in checks:
        players = data["players"].get(abbr, [])
        found = [p for p in players if name.lower() in p["last_name"].lower()]
        if found:
            p = found[0]
            pos = p["position"]
            print(f"  OK  {abbr}: {p['first_name']} {p['last_name']} ({pos})")
        else:
            print(f"  MISSING  {abbr}: {name} not found!")

    print("\nDone! Now delete front_office.db and restart the server:")
    print("  rm front_office.db")
    print("  python -m src.main")


if __name__ == "__main__":
    main()
