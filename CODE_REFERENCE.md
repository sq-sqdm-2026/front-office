# Code Reference - Strategy & Personality Features

## Module: src/simulation/game_engine.py

### New Functions for Strategic Plays

#### `_attempt_hit_and_run(bases: BaseState, outs: int, batter: BatterStats, hit_and_run_mult: float = 1.0) -> bool`
Determines if hit-and-run should be attempted.

**Parameters**:
- `bases`: Current base state (runner on 1st required)
- `outs`: Current outs (must be < 2)
- `batter`: Batter stats (contact >= 40 required)
- `hit_and_run_mult`: Strategy multiplier (0.3-2.0)

**Returns**: True if play should be executed

**Logic**:
```
- Requires: runner on 1st, no runner on 2nd/3rd, < 2 outs
- Base attempt rate: 5% * multiplier
- Batter must have contact >= 40
```

---

#### `_apply_hit_and_run(pitcher: PitcherStats, batter: BatterStats, park: ParkFactors) -> str`
Resolves hit-and-run at-bat outcome.

**Returns**: Outcome ("HR", "3B", "2B", "1B", "GO", "FO")

**Mechanics**:
- Contact chance: +20% (1.2x multiplier)
- Power: -30% (0.7x multiplier)
- Fly balls less likely (0.15x vs 0.22x)
- Ground balls more likely

**Example**:
```python
outcome = _apply_hit_and_run(pitcher, batter, park)
if outcome == "1B":
    bases.second = bases.first
    bases.first = batter.player_id
```

---

#### `_attempt_suicide_squeeze(bases: BaseState, outs: int, batter: BatterStats, squeeze_mult: float = 1.0) -> bool`
Determines if suicide squeeze should be attempted.

**Parameters**:
- `bases`: Must have runner on 3rd
- `outs`: Must be < 2
- `batter`: Batter stats (low power preferred)
- `squeeze_mult`: Strategy multiplier (0.2-1.5)

**Logic**:
```
- Base attempt rate: 2% * multiplier
- Power penalty: (1 - (batter.power - 40) * 0.01) per 5 points below 45
- Low power batters more likely
```

---

#### `_apply_suicide_squeeze(batter: BatterStats, pitcher: PitcherStats, park: ParkFactors) -> str`
Resolves squeeze outcome.

**Returns**: "SAC" (successful) or "SO" (failed)

**Bunt Success Rate**:
```
base_rate = 0.3
contact_modifier = (batter.contact / 50.0) * 1.5
success_rate = base_rate * contact_modifier
success_rate = max(0.2, min(0.8, success_rate))
```

**Outcomes**:
- Success: Runner scores, batter gets sacrifice fly credit
- Failure: Strikeout, runner at risk of being caught at plate

---

#### `_attempt_intentional_walk(bases: BaseState, outs: int, batter: BatterStats, next_batter: BatterStats = None, ibb_threshold: int = 80) -> bool`
Determines if intentional walk should be issued.

**Conditions**:
```python
- First base MUST be empty (bases.first == 0)
- Runner in scoring position (bases.second or bases.third)
- Batter power >= ibb_threshold (default: 80)
- Outs < 2
```

**Decision Logic**:
```python
ibb_prob = 0.3  # Base probability
if next_batter:
    power_diff = batter.power - next_batter.power
    if power_diff >= 15:
        ibb_prob = 0.7  # Significantly better matchup
return random.random() < ibb_prob
```

---

#### `_attempt_defensive_shift(batter: BatterStats) -> bool`
Determines if infield shift should be deployed.

**Returns**: True if batter matches shift criteria

**Criteria** (extreme pull hitter):
```python
return batter.power > 65 and batter.contact < 45
```

**Typical Candidates**:
- High power (75+), low contact (35-40)
- Example: cleanup sluggers with strikeout tendencies

---

#### `_apply_shift_modifier(outcome: str) -> str`
Modifies hit outcome based on shift deployment.

**Modifications**:
```python
if outcome == "1B":
    # 15% of singles become groundouts with shift
    if random.random() < 0.15:
        return "GO"
elif outcome == "2B":
    # Pulled balls go for extra bases more often
    if random.random() < 0.10:
        return "2B"  # Stays double or becomes triple
return outcome
```

**Examples**:
- Weak single pulled into shift: converted to groundout
- Line drive up gap: stays double/triple

---

#### `_should_pinch_hit(lineup: list, current_batter_idx: int, inning: int, score_diff: int) -> bool`
Determines if pinch hit should be made.

**Conditions**:
```python
- Inning >= 7
- Pitcher batting (power < 35)
- Close game (|score_diff| <= 3)
```

**Future Integration**:
- Will require bench roster system
- Needs available position player lookup

---

#### `_should_make_defensive_substitution(lineup: list, inning: int, score_diff: int, team_ahead: bool) -> bool`
Determines if defensive substitution should be made.

**Conditions**:
```python
- Team ahead (team_ahead == True)
- Inning >= 7
- Score_diff >= 1
- Probability: 20% in inning 8+, 10% in inning 7
```

**Future Integration**:
- Requires bench availability system
- Should pull poor fielders (fielding < 45)
- Replace with defensive specialists

---

### Modified Game Loop Structure

The `simulate_game()` function now integrates strategies as follows:

**For each half-inning at-bat**:
```python
# 1. Attempt stolen base (existing)
sb_attempt, sb_success, sb_outs = _attempt_stolen_base(...)

# 2. NEW: Check strategic plays (priority order)
hit_and_run = _attempt_hit_and_run(bases, outs, batter, multiplier)
suicide_squeeze = _attempt_suicide_squeeze(bases, outs, batter, multiplier)
intentional_walk = _attempt_intentional_walk(bases, outs, batter, next_batter, threshold)
sac_bunt = (not hit_and_run and not suicide_squeeze and not intentional_walk and
           _attempt_sac_bunt(...))

# 3. NEW: Check defensive shift
use_shift = _attempt_defensive_shift(batter) and random.random() < shift_tendency

# 4. Handle intentional walk (no pitch thrown)
if intentional_walk:
    batter.bb += 1
    run _advance_runners with "BB" outcome
    continue

# 5. Execute selected play or normal at-bat
if hit_and_run:
    outcome = _apply_hit_and_run(pitcher, batter, park)
elif suicide_squeeze:
    outcome = _apply_suicide_squeeze(batter, pitcher, park)
elif sac_bunt:
    # Handle bunt
else:
    outcome, pitches = _resolve_at_bat_with_count(...)

# 6. Apply shift modifier if deployed
if use_shift and outcome in ("1B", "2B", "3B"):
    outcome = _apply_shift_modifier(outcome)
```

---

## Module: src/simulation/strategy.py

### Configuration Constants

#### `DEFAULT_STRATEGY` Dictionary
```python
{
    "steal_frequency": "normal",           # conservative/normal/aggressive
    "bunt_frequency": "normal",            # never/sacrifice_only/normal/aggressive
    "pitch_count_limit": 100,              # starter max pitches
    "ibb_threshold": 80,                   # power rating threshold
    "infield_in_threshold": 7,             # inning number
    "hit_and_run_freq": "normal",          # conservative/normal/aggressive
    "squeeze_freq": "conservative",        # conservative/normal/aggressive
    "shift_tendency": 0.7,                 # 0.0-1.0
    "defensive_sub_tendency": 0.6,         # 0.0-1.0
    "aggression": 50,                      # 0-100
}
```

#### `HIT_AND_RUN_MULTIPLIER` Dictionary
```python
{
    "conservative": 0.3,   # 1.5% base attempt rate
    "normal": 1.0,         # 5% base attempt rate
    "aggressive": 2.0,     # 10% base attempt rate
}
```

#### `SQUEEZE_MULTIPLIER` Dictionary
```python
{
    "conservative": 0.2,   # 0.4% base attempt rate
    "normal": 0.8,         # 1.6% base attempt rate
    "aggressive": 1.5,     # 3% base attempt rate
}
```

### Functions

#### `get_strategy(strategy_json: str = None) -> dict`
Parses team strategy JSON or returns defaults.

**Example**:
```python
from src.simulation.strategy import DEFAULT_STRATEGY

# Load from database JSON
strategy = get_strategy(team.team_strategy_json)

# Or create custom
my_strategy = dict(DEFAULT_STRATEGY)
my_strategy["hit_and_run_freq"] = "aggressive"
my_strategy["aggression"] = 75
```

---

## Module: src/simulation/chemistry.py

### Team Chemistry Functions

#### `calculate_team_chemistry(team_id: int, db_path: str = None) -> int`
Computes team chemistry score (0-100).

**Scoring Components**:

1. **Leadership Component** (±15):
   ```python
   leadership_score = weighted_average(player.leadership by playing_time)
   component = (leadership_score - 50) * 0.3
   ```

2. **Ego Conflict Penalty** (0 to -∞):
   ```python
   high_ego_count = sum(1 for p if p.ego > 65)
   penalty = high_ego_count * 3
   ```

3. **Age Balance** (0 to -∞):
   ```python
   age_stddev = std_deviation(all_player_ages)
   optimal_stddev = 5.5  # years
   penalty = abs(age_stddev - optimal_stddev) * 2
   ```

4. **Win Streak** (±15):
   ```python
   if streak > 0:
       bonus = min(streak * 1.5, 15)
   else:
       bonus = max(streak * 1.0, -15)
   ```

5. **Recent Trades** (0 to -∞):
   ```python
   trades_30d = count(trades in last 30 days)
   disrupt = -trades_30d * 2
   ```

6. **Relationships** (scaled):
   ```python
   rel_bonus = sum(friends) * 1.5 - sum(rivals) * 2
   contribution = rel_bonus * 0.1
   ```

7. **Sociability** (±10):
   ```python
   avg_sociability = average(player.sociability)
   component = (avg_sociability - 50) * 0.2
   ```

**Result**: Clamp to [0, 100]

---

#### `get_chemistry_modifiers(chemistry_score: int) -> dict`
Returns performance multipliers based on chemistry.

**Returns**:
```python
{
    "development_rate": 1.0 + (score - 50) * 0.001,      # 0.95 to 1.05
    "clutch_bonus": (score - 50) * 0.0006,               # -0.03 to +0.03
    "injury_recovery": 1.0 + (score - 50) * 0.002,       # 0.90 to 1.10
}
```

**Examples**:
```python
# Low chemistry (25)
mods = get_chemistry_modifiers(25)
# {development_rate: 0.975, clutch_bonus: -0.015, injury_recovery: 0.90}

# High chemistry (75)
mods = get_chemistry_modifiers(75)
# {development_rate: 1.025, clutch_bonus: +0.015, injury_recovery: 1.10}
```

---

### Player Morale Functions

#### `update_player_morale(team_id: int, db_path: str = None)`
Daily morale update for all team players.

**Morale Adjustments** (cumulative):

1. **Playing Time** (±3):
   ```python
   if games >= 100:
       delta = +3  # Starter
   elif games >= 50:
       delta = +1  # Semi-regular
   elif games < 20:
       delta = -2  # Bench player
   ```

2. **Team Momentum** (±2):
   ```python
   if recent_wins >= recent_total / 2:
       delta = +2  # Winning momentum
   else:
       delta = -2  # Losing momentum
   ```

3. **Chemistry Influence** (±4):
   ```python
   delta = (chemistry_score - 50) * 0.04
   ```

4. **Contract Status** (-3):
   ```python
   if contract_years_remaining <= 1:
       delta = -3  # Expiring contract anxiety
   ```

5. **Loyalty Multiplier** (0.5x to 1.5x):
   ```python
   total_delta *= (0.5 + loyalty / 200)
   ```

**Result**: Clamp to [0, 100]

---

#### `get_morale_modifiers(morale: int) -> dict`
Returns rating adjustments based on morale.

**Returns**:
```python
{
    "contact": (morale - 50) * 0.06,      # -3 to +3
    "power": (morale - 50) * 0.06,        # -3 to +3
    "speed": (morale - 50) * 0.04,        # -2 to +2
}
```

**Application Example**:
```python
morale_mods = get_morale_modifiers(player.morale)
effective_contact = player.contact + morale_mods["contact"]
effective_power = player.power + morale_mods["power"]
```

---

### Player Relationships Functions

#### `create_player_relationships(team_id: int, db_path: str = None)`
Generate initial team relationships during seeding.

**Relationship Types**:

1. **Country Connection** (20% if same country):
   ```python
   type = "friend"
   strength = random(40-70)
   ```

2. **Position Group** (15% if same group, non-pitcher):
   ```python
   # Groups: infield, outfield, dh, pitcher
   type = "friend" (70%) or "rival" (30%)
   strength = random(30-80)
   ```

3. **Age Gap Mentor** (10% if 5+ years difference):
   ```python
   older = mentor, younger = mentee
   type = "mentor"
   strength = random(35-75)
   ```

4. **Position Competition** (10% if same pos, age close):
   ```python
   type = "rival"
   strength = random(40-70)
   ```

---

#### `get_player_relationships(player_id: int, db_path: str = None) -> list`
Retrieve all relationships for a player.

**Returns**:
```python
[
    {
        "other_player_id": 102,
        "relationship_type": "friend",
        "strength": 55,
    },
    ...
]
```

---

#### `apply_trade_morale_penalty(player_id: int, days: int = 14, penalty: int = 10, db_path: str = None)`
Apply morale penalty when player is traded.

**Mechanics**:
```python
new_morale = max(0, player.morale - penalty)
# Default: -10 morale (recovers over time via update_player_morale)
```

---

### Helper Functions

#### `calculate_age_stddev(ages: list) -> float`
Computes standard deviation of player ages.

**Formula**:
```python
mean = sum(ages) / len(ages)
variance = sum((x - mean)^2) / len(ages)
stddev = sqrt(variance)
```

**Interpretation**:
- stddev < 3: Very homogeneous (all young or all old)
- stddev 5-6: Optimal balance
- stddev > 8: Highly spread (poor rookie/veteran balance)

---

## Module: src/database/schema.py

### New Player Fields (Integer, 1-100)

```sql
loyalty INTEGER NOT NULL DEFAULT 50           -- attachment to team
greed INTEGER NOT NULL DEFAULT 50            -- money vs winning
composure INTEGER NOT NULL DEFAULT 50        -- pressure handling
intelligence INTEGER NOT NULL DEFAULT 50     -- baseball IQ
aggression INTEGER NOT NULL DEFAULT 50       -- intensity/fights
sociability INTEGER NOT NULL DEFAULT 50      -- teammate bonds
morale INTEGER NOT NULL DEFAULT 50           -- current morale (0-100)
```

### New Tables

**player_relationships**
```sql
CREATE TABLE IF NOT EXISTS player_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id_1 INTEGER NOT NULL,            -- lower ID (enforced unique)
    player_id_2 INTEGER NOT NULL,            -- higher ID (enforced unique)
    relationship_type TEXT NOT NULL,         -- 'friend'|'rival'|'mentor'
    strength INTEGER NOT NULL DEFAULT 50,    -- 1-100 intensity
    created_date TEXT NOT NULL,              -- ISO 8601 timestamp
    UNIQUE(player_id_1, player_id_2),       -- One relationship per pair
    FOREIGN KEY (player_id_1) REFERENCES players(id),
    FOREIGN KEY (player_id_2) REFERENCES players(id)
);
```

**team_chemistry**
```sql
CREATE TABLE IF NOT EXISTS team_chemistry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL UNIQUE,
    chemistry_score INTEGER NOT NULL DEFAULT 50,    -- 0-100
    last_updated TEXT NOT NULL,                     -- ISO 8601
    recent_trade_count INTEGER NOT NULL DEFAULT 0,  -- rolling 30-day count
    win_streak INTEGER NOT NULL DEFAULT 0,          -- positive/negative
    FOREIGN KEY (team_id) REFERENCES teams(id)
);
```

---

## Integration Points

### In Season Simulation (season.py)

**Daily Update Call**:
```python
from src.simulation.chemistry import update_player_morale, update_team_chemistry

# During game loop / season simulation
def simulate_day(game_date, season):
    # ... simulate games ...

    # Update team dynamics
    for team_id in all_teams:
        update_team_chemistry(team_id)
        update_player_morale(team_id)
```

### In Player Development (player_development.py)

**Apply Chemistry Modifiers**:
```python
from src.simulation.chemistry import get_chemistry_modifiers

def process_offseason_development(season):
    for team_id in all_teams:
        chemistry = calculate_team_chemistry(team_id)
        mods = get_chemistry_modifiers(chemistry)

        for player in team_players:
            # Adjust development rate
            player.development_rate *= mods["development_rate"]
```

### In Trade Processing (transactions/trades.py)

**Apply Trade Penalties**:
```python
from src.simulation.chemistry import apply_trade_morale_penalty

def execute_trade(player_ids, team1_id, team2_id):
    for player_id in player_ids:
        apply_trade_morale_penalty(player_id, days=14, penalty=10)
```

---

## Data Flow Diagram

```
GAME SIMULATION
    ├── simulate_game()
    │   ├── Pre-compute strategy multipliers
    │   ├── For each at-bat:
    │   │   ├── Check hit-and-run → _apply_hit_and_run()
    │   │   ├── Check squeeze → _apply_suicide_squeeze()
    │   │   ├── Check IBB → intentional walk
    │   │   ├── Check shift → _apply_shift_modifier()
    │   │   └── Resolve outcome
    │   └── Return box score
    │
TEAM DYNAMICS
    ├── Daily Update
    │   ├── update_player_morale(team_id)
    │   │   ├── Get team record (wins/losses)
    │   │   ├── Get recent momentum
    │   │   ├── Get chemistry score
    │   │   └── Update each player.morale
    │   │
    │   └── update_team_chemistry(team_id)
    │       ├── calculate_team_chemistry()
    │       │   ├── Leadership component
    │       │   ├── Ego conflicts
    │       │   ├── Age balance
    │       │   ├── Win streak
    │       │   ├── Recent trades
    │       │   ├── Relationships
    │       │   └── Sociability
    │       └── Cache score in database
    │
PLAYER DEVELOPMENT
    ├── get_chemistry_modifiers(chemistry)
    │   └── Apply to development_rate multiplier
    │
    └── get_morale_modifiers(morale)
        └── Apply to contact/power/speed ratings
```

---

## Performance Considerations

### Time Complexity

- **Chemistry Calculation**: O(n) where n = active roster size
  - Database queries: n batting_stats lookups
  - Relationship lookups: O(n) per player
- **Morale Update**: O(n) per team
- **Game Simulation**: No significant overhead from new features

### Memory Usage

- New tables minimal impact
- Strategy multipliers pre-computed once per game
- Chemistry cached in database (reuse across calculations)

### Optimization Tips

```python
# Cache chemistry during season simulation
chemistry_cache = {}
for team_id in all_teams:
    chemistry_cache[team_id] = calculate_team_chemistry(team_id)

# Reuse for multiple operations
mods = get_chemistry_modifiers(chemistry_cache[team_id])

# Batch relationship queries
def get_team_relationships(team_id):
    # Single query for all team relationships
    # vs n queries per player
```

---

## Testing Checklist

- [x] Strategy parsing with all new fields
- [x] Hit-and-run attempt and execution
- [x] Suicide squeeze attempt and execution
- [x] Intentional walk decision logic
- [x] Defensive shift deployment
- [x] Shift outcome modifiers
- [x] Chemistry calculation components
- [x] Chemistry morale modifiers
- [x] Morale update mechanics
- [x] Age standard deviation helper
- [x] Full game simulation with strategies
