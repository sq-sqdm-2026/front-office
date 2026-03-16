# Usage Examples - Strategy & Personality Features

## Table of Contents
1. [Strategy Configuration](#strategy-configuration)
2. [In-Game Strategy](#in-game-strategy)
3. [Chemistry System](#chemistry-system)
4. [Morale Management](#morale-management)
5. [Player Relationships](#player-relationships)
6. [Complete Workflow](#complete-workflow)

---

## Strategy Configuration

### Example 1: Conservative Manager (Small Market Team)

```python
from src.simulation.strategy import DEFAULT_STRATEGY

conservative_strategy = dict(DEFAULT_STRATEGY)
conservative_strategy.update({
    "steal_frequency": "conservative",    # Only fast runners steal
    "bunt_frequency": "sacrifice_only",   # Bunts only in specific situations
    "hit_and_run_freq": "conservative",   # Rarely aggressive
    "squeeze_freq": "conservative",       # Avoid risky plays
    "shift_tendency": 0.9,                # Deploy shift frequently
    "ibb_threshold": 85,                  # Only walk best hitters
    "aggression": 35,                     # Play it safe
})
```

### Example 2: Aggressive Manager (Win-Now Team)

```python
aggressive_strategy = dict(DEFAULT_STRATEGY)
aggressive_strategy.update({
    "steal_frequency": "aggressive",      # Even marginal runners steal
    "bunt_frequency": "aggressive",       # Use bunts creatively
    "hit_and_run_freq": "aggressive",     # Aggressive base running
    "squeeze_freq": "normal",             # Willing to squeeze
    "shift_tendency": 0.5,                # Less reliant on shift
    "ibb_threshold": 75,                  # Walk good hitters too
    "pitch_count_limit": 85,              # Push starters
    "aggression": 75,                     # Play aggressive
})
```

### Example 3: Balanced Manager (Midwest Team)

```python
balanced_strategy = dict(DEFAULT_STRATEGY)
balanced_strategy.update({
    "steal_frequency": "normal",
    "bunt_frequency": "normal",
    "hit_and_run_freq": "normal",
    "squeeze_freq": "conservative",
    "shift_tendency": 0.7,
    "ibb_threshold": 80,
    "aggression": 50,
})
```

---

## In-Game Strategy

### Example 4: Simulating a Game with Custom Strategies

```python
from src.simulation.game_engine import simulate_game, BatterStats, PitcherStats, ParkFactors
from src.simulation.strategy import DEFAULT_STRATEGY

# Create lineups and pitchers...
home_lineup = [
    BatterStats(1, "Batter1", "C", 1, "R", 65, 60, 55, 50),
    BatterStats(2, "Batter2", "1B", 2, "R", 70, 75, 50, 55),
    # ... more batters
]

away_lineup = [
    BatterStats(101, "Hitter1", "SS", 1, "R", 60, 55, 70, 50),
    BatterStats(102, "Slugger", "RF", 2, "R", 45, 80, 60, 55),
    # ... more batters
]

home_pitchers = [PitcherStats(1, "Starter1", "R", "starter", 68, 62, 70, 50)]
away_pitchers = [PitcherStats(101, "Starter2", "R", "starter", 65, 60, 65, 50)]

park = ParkFactors.from_stadium(
    lf=330, lcf=375, cf=400, rcf=375, rf=330,
    is_dome=False, altitude=0
)

# Define strategies
home_strategy = dict(DEFAULT_STRATEGY)
home_strategy["hit_and_run_freq"] = "aggressive"
home_strategy["squeeze_freq"] = "normal"
home_strategy["shift_tendency"] = 0.8

away_strategy = dict(DEFAULT_STRATEGY)
away_strategy["steal_frequency"] = "aggressive"
away_strategy["aggression"] = 70

# Simulate
result = simulate_game(
    home_lineup, away_lineup,
    home_pitchers, away_pitchers,
    park,
    home_team_id=1,
    away_team_id=2,
    home_strategy=home_strategy,
    away_strategy=away_strategy
)

print(f"Final Score: Away {result['away_score']} - Home {result['home_score']}")
```

### Example 5: Dynamic Strategy Based on Game Situation

```python
def get_dynamic_strategy(team_record, league_position, game_situation):
    """Adjust strategy based on team performance and game situation."""
    strategy = dict(DEFAULT_STRATEGY)

    # Struggling teams play more conservatively
    if team_record["wins"] < team_record["losses"]:
        strategy["aggression"] = 35
        strategy["steal_frequency"] = "conservative"
    # Teams in contention play more aggressively
    elif league_position <= 3:
        strategy["aggression"] = 75
        strategy["hit_and_run_freq"] = "aggressive"

    # Early game: standard strategy
    if game_situation["inning"] <= 4:
        strategy["pitch_count_limit"] = 110
    # Late game, close: be aggressive
    elif game_situation["inning"] >= 7 and abs(game_situation["score_diff"]) <= 2:
        strategy["hit_and_run_freq"] = "aggressive"
        strategy["squeeze_freq"] = "normal"
        strategy["aggression"] = 70

    return strategy

# Usage
team_record = {"wins": 65, "losses": 70}
league_position = 5
game_situation = {"inning": 8, "score_diff": 1}

strategy = get_dynamic_strategy(team_record, league_position, game_situation)
```

---

## Chemistry System

### Example 6: Calculate Team Chemistry

```python
from src.simulation.chemistry import calculate_team_chemistry, get_chemistry_modifiers
from src.database.db import get_connection

# Get chemistry score
chemistry_score = calculate_team_chemistry(team_id=5)

# Get impact multipliers
mods = get_chemistry_modifiers(chemistry_score)

print(f"Team Chemistry: {chemistry_score}/100")
print(f"  Development Rate: {mods['development_rate']:.1%}")
print(f"  Clutch Bonus: {mods['clutch_bonus']:.1%}")
print(f"  Injury Recovery: {mods['injury_recovery']:.1%}")

# Example output for high chemistry (75):
# Team Chemistry: 75/100
#   Development Rate: 102.5%
#   Clutch Bonus: 0.9%
#   Injury Recovery: 115.0%
```

### Example 7: Apply Chemistry to Player Development

```python
from src.simulation.player_development import _develop_player
from src.simulation.chemistry import get_chemistry_modifiers

def develop_player_with_chemistry(player_dict, team_id, conn):
    """Develop player with chemistry modifiers applied."""

    # Get base development
    changes = _develop_player(player_dict, conn)

    # Get team chemistry
    chemistry = calculate_team_chemistry(team_id)
    mods = get_chemistry_modifiers(chemistry)

    # Adjust development rate
    adjusted_rate = player_dict["development_rate"] * mods["development_rate"]

    # Apply adjustment
    if changes:
        for rating_field, (old_val, new_val) in changes.items():
            if rating_field != "position_shift" and rating_field != "retired":
                # Adjust improvement magnitude
                improvement = new_val - old_val
                adjusted_improvement = int(improvement * mods["development_rate"])
                new_val = old_val + adjusted_improvement
                changes[rating_field] = (old_val, new_val)

    return changes

# Usage
for player in all_players:
    changes = develop_player_with_chemistry(player, team_id, conn)
    if changes:
        print(f"{player['name']}: {changes}")
```

### Example 8: Track Chemistry Over Time

```python
from src.simulation.chemistry import update_team_chemistry, calculate_team_chemistry

def track_team_chemistry(team_id, season_start_date, season_end_date):
    """Track chemistry changes throughout season."""
    from src.database.db import get_connection
    from datetime import timedelta, datetime

    conn = get_connection()
    chemistry_history = []

    current_date = datetime.fromisoformat(season_start_date)
    end_date = datetime.fromisoformat(season_end_date)

    while current_date <= end_date:
        # Simulate daily activities...
        # Then update chemistry
        update_team_chemistry(team_id)

        # Record chemistry
        chemistry = conn.execute(
            "SELECT chemistry_score FROM team_chemistry WHERE team_id = ?",
            (team_id,)
        ).fetchone()

        chemistry_history.append({
            "date": current_date.isoformat(),
            "chemistry": chemistry["chemistry_score"],
        })

        current_date += timedelta(days=1)

    conn.close()

    # Analyze trend
    avg_chemistry = sum(c["chemistry"] for c in chemistry_history) / len(chemistry_history)
    print(f"Average Chemistry: {avg_chemistry:.1f}")

    return chemistry_history
```

---

## Morale Management

### Example 9: Check Player Morale

```python
from src.simulation.chemistry import get_morale_modifiers

# Get player stats
player = conn.execute(
    "SELECT * FROM players WHERE id = ?", (player_id,)
).fetchone()

morale = player["morale"]

# Get performance impact
mods = get_morale_modifiers(morale)

print(f"Player: {player['first_name']} {player['last_name']}")
print(f"Morale: {morale}/100")
print(f"Performance Adjustments:")
print(f"  Contact: {mods['contact']:+.1f}")
print(f"  Power: {mods['power']:+.1f}")
print(f"  Speed: {mods['speed']:+.1f}")

# Example for low morale (25):
# Morale: 25/100
# Performance Adjustments:
#   Contact: -1.5
#   Power: -1.5
#   Speed: -1.0

# Example for high morale (85):
# Morale: 85/100
# Performance Adjustments:
#   Contact: +2.1
#   Power: +2.1
#   Speed: +1.4
```

### Example 10: Update Team Morale Daily

```python
from src.simulation.chemistry import update_player_morale, update_team_chemistry

def simulate_season_day(team_id, game_date):
    """Daily simulation including morale updates."""

    # ... simulate games for the day ...

    # Update team dynamics
    update_team_chemistry(team_id)
    update_player_morale(team_id)

    # Report morale changes
    players = conn.execute(
        "SELECT id, first_name, last_name, morale FROM players WHERE team_id = ?",
        (team_id,)
    ).fetchall()

    print(f"\nMorale Report for {game_date}:")
    for p in players:
        morale_status = "🔴 Low" if p["morale"] < 30 else "🟡 Medium" if p["morale"] < 70 else "🟢 High"
        print(f"  {p['first_name']} {p['last_name']}: {p['morale']}/100 {morale_status}")
```

### Example 11: Identify Morale Problems

```python
def identify_morale_issues(team_id, threshold=35):
    """Find players with morale below threshold."""
    from src.database.db import get_connection

    conn = get_connection()

    problems = conn.execute("""
        SELECT id, first_name, last_name, morale, position, contract_years_remaining
        FROM players
        WHERE team_id = ? AND morale < ? AND roster_status = 'active'
        ORDER BY morale ASC
    """, (team_id, threshold)).fetchall()

    if problems:
        print(f"⚠️  Morale Issues ({len(problems)} players):")
        for p in problems:
            print(f"  {p['first_name']} {p['last_name']} ({p['position']}): {p['morale']}/100")
            if p["contract_years_remaining"] and p["contract_years_remaining"] <= 1:
                print(f"    -> Contract expires soon - likely cause")
    else:
        print("✓ All players have healthy morale")

    conn.close()
```

---

## Player Relationships

### Example 12: Generate Team Relationships

```python
from src.simulation.chemistry import create_player_relationships

# During team creation/seeding
team_id = 1

# Generate relationships based on country, position, age, etc.
create_player_relationships(team_id)

print(f"Generated relationships for team {team_id}")

# Check relationships
conn = get_connection()
relationships = conn.execute("""
    SELECT
        p1.first_name || ' ' || p1.last_name as player1,
        p2.first_name || ' ' || p2.last_name as player2,
        relationship_type,
        strength
    FROM player_relationships pr
    JOIN players p1 ON p1.id = pr.player_id_1
    JOIN players p2 ON p2.id = pr.player_id_2
    WHERE p1.team_id = ? OR p2.team_id = ?
    ORDER BY strength DESC
""", (team_id, team_id)).fetchall()

print(f"Team {team_id} Relationships:")
for rel in relationships:
    icon = "👥" if rel["relationship_type"] == "friend" else "⚔️" if rel["relationship_type"] == "rival" else "👨‍🏫"
    print(f"  {icon} {rel['player1']} <-> {rel['player2']}")
    print(f"     Type: {rel['relationship_type']}, Strength: {rel['strength']}/100")

conn.close()
```

### Example 13: Track Relationship Effects on Chemistry

```python
def analyze_relationship_impact(team_id):
    """Quantify relationships' impact on team chemistry."""
    from src.database.db import get_connection

    conn = get_connection()

    # Count relationships
    friends = conn.execute("""
        SELECT COUNT(*) as cnt FROM player_relationships
        WHERE (player_id_1 IN (SELECT id FROM players WHERE team_id = ?) OR
               player_id_2 IN (SELECT id FROM players WHERE team_id = ?))
        AND relationship_type = 'friend'
    """, (team_id, team_id)).fetchone()

    rivals = conn.execute("""
        SELECT COUNT(*) as cnt FROM player_relationships
        WHERE (player_id_1 IN (SELECT id FROM players WHERE team_id = ?) OR
               player_id_2 IN (SELECT id FROM players WHERE team_id = ?))
        AND relationship_type = 'rival'
    """, (team_id, team_id)).fetchone()

    # Calculate impact
    friend_bonus = (friends["cnt"] or 0) * 1.5
    rival_penalty = (rivals["cnt"] or 0) * 2.0
    net_impact = friend_bonus - rival_penalty

    print(f"Relationship Impact on Team {team_id}:")
    print(f"  Friends: {friends['cnt']} (+{friend_bonus:.1f} chemistry)")
    print(f"  Rivals: {rivals['cnt']} (-{rival_penalty:.1f} chemistry)")
    print(f"  Net Impact: {net_impact:+.1f} chemistry points")

    conn.close()
```

### Example 14: Handle Trade Morale Impact

```python
from src.simulation.chemistry import apply_trade_morale_penalty, create_player_relationships

def execute_trade_with_morale(player_ids_out, player_ids_in, team_id):
    """Execute trade and handle morale impacts."""

    # Players leaving
    for player_id in player_ids_out:
        apply_trade_morale_penalty(player_id, days=14, penalty=15)
        print(f"Player {player_id} traded away: -15 morale")

    # Players arriving
    for player_id in player_ids_in:
        # New player starts with default morale 50
        conn = get_connection()
        conn.execute("UPDATE players SET morale = 50 WHERE id = ?", (player_id,))
        conn.commit()
        conn.close()
        print(f"Player {player_id} acquired: reset to 50 morale")

    # Regenerate team relationships with new roster
    create_player_relationships(team_id)

    # Update chemistry
    from src.simulation.chemistry import update_team_chemistry
    update_team_chemistry(team_id)

    print(f"Team {team_id} chemistry updated after trade")
```

---

## Complete Workflow

### Example 15: Full Season Simulation with All Features

```python
from src.simulation.game_engine import simulate_game
from src.simulation.chemistry import update_player_morale, update_team_chemistry, create_player_relationships
from src.simulation.strategy import DEFAULT_STRATEGY
from src.database.db import get_connection
from datetime import datetime, timedelta

def simulate_season(season=2026, user_team_id=1):
    """Complete season simulation with strategy and personality."""
    conn = get_connection()

    # Get all games for season
    schedule = conn.execute("""
        SELECT * FROM schedule
        WHERE season = ? AND is_played = 0
        ORDER BY game_date
    """, (season,)).fetchall()

    # Initialize team relationships
    for team_id in range(1, 31):  # 30 MLB teams
        create_player_relationships(team_id)

    games_played = 0

    for game in schedule:
        game_date = game["game_date"]
        home_team_id = game["home_team_id"]
        away_team_id = game["away_team_id"]

        # Get lineups and strategies
        home_lineup = get_team_lineup(home_team_id, conn)
        away_lineup = get_team_lineup(away_team_id, conn)
        home_pitchers = get_team_pitchers(home_team_id, conn)
        away_pitchers = get_team_pitchers(away_team_id, conn)

        # Get strategies from team preferences
        home_team = conn.execute("SELECT * FROM teams WHERE id = ?", (home_team_id,)).fetchone()
        away_team = conn.execute("SELECT * FROM teams WHERE id = ?", (away_team_id,)).fetchone()

        home_strategy = get_strategy(home_team["team_strategy_json"]) if home_team["team_strategy_json"] else dict(DEFAULT_STRATEGY)
        away_strategy = get_strategy(away_team["team_strategy_json"]) if away_team["team_strategy_json"] else dict(DEFAULT_STRATEGY)

        park = get_team_park_factors(home_team_id, conn)

        # Simulate game
        result = simulate_game(
            home_lineup, away_lineup,
            home_pitchers, away_pitchers,
            park,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            home_strategy=home_strategy,
            away_strategy=away_strategy
        )

        # Record result
        save_game_result(game["id"], result, conn)
        games_played += 1

        # Update team dynamics every 5 games or on specific dates
        if games_played % 5 == 0:
            for team_id in [home_team_id, away_team_id]:
                update_team_chemistry(team_id)
                update_player_morale(team_id)

        print(f"[{game_date}] {away_team['abbreviation']} @ {home_team['abbreviation']}: "
              f"{result['away_score']}-{result['home_score']}")

    # Final season update
    for team_id in range(1, 31):
        update_team_chemistry(team_id)
        update_player_morale(team_id)

    print(f"\nSeason {season} Complete: {games_played} games played")
    conn.close()

# Run simulation
simulate_season(season=2026, user_team_id=1)
```

### Example 16: Manager AI with Strategy Personality

```python
def get_manager_strategy(gm_id, team_record, game_situation):
    """Generate strategy based on manager personality."""
    from src.database.db import get_connection

    conn = get_connection()

    gm = conn.execute("SELECT * FROM gm_characters WHERE id = ?", (gm_id,)).fetchone()

    # Base strategy on philosophy
    strategy = dict(DEFAULT_STRATEGY)

    if gm["philosophy"] == "analytics":
        # Analytics managers: precise, shift-heavy
        strategy["shift_tendency"] = 0.95
        strategy["ibb_threshold"] = 75  # More selective walks
        strategy["pitch_count_limit"] = 90  # Push starters less
    elif gm["philosophy"] == "old_school":
        # Old school: conservative, bunts, steal
        strategy["bunt_frequency"] = "aggressive"
        strategy["steal_frequency"] = "aggressive"
        strategy["shift_tendency"] = 0.3
    elif gm["philosophy"] == "moneyball":
        # Moneyball: OBP focus, walks, avoid strikeouts
        strategy["ibb_threshold"] = 70
        strategy["steal_frequency"] = "conservative"

    # Adjust by personality
    if gm["risk_tolerance"] > 70:
        strategy["aggression"] = 80
        strategy["hit_and_run_freq"] = "aggressive"
    elif gm["risk_tolerance"] < 30:
        strategy["aggression"] = 20
        strategy["squeeze_freq"] = "conservative"

    # Adjust by game situation
    if abs(game_situation["score_diff"]) > 5:
        # Blowout: save resources
        strategy["steal_frequency"] = "conservative"
    elif game_situation["inning"] >= 8 and abs(game_situation["score_diff"]) <= 1:
        # Tight late game: more aggressive
        strategy["hit_and_run_freq"] = "aggressive"
        strategy["squeeze_freq"] = "normal"

    # Adjust by team record
    if team_record["wins"] < team_record["losses"]:
        strategy["aggression"] = max(30, strategy["aggression"] - 20)
    elif team_record["wins"] > team_record["losses"] + 10:
        strategy["aggression"] = min(80, strategy["aggression"] + 20)

    conn.close()
    return strategy

# Usage
gm_id = 1
team_record = {"wins": 70, "losses": 65}
game_situation = {"inning": 8, "score_diff": 1}

strategy = get_manager_strategy(gm_id, team_record, game_situation)
```

---

## Summary

These examples demonstrate:

1. **Strategy Customization**: Creating team-specific strategies
2. **Game Simulation**: Simulating games with custom strategies
3. **Chemistry Tracking**: Calculating and applying chemistry effects
4. **Morale Management**: Monitoring and adjusting player morale
5. **Relationships**: Managing player relationships and impacts
6. **Integrated Workflow**: Full season simulation with all systems
7. **AI Integration**: Manager personality influencing strategy

The system is flexible and can be extended with additional factors, more sophisticated decision-making, and deeper personality-driven behaviors.
