# Implementation Details - Code Locations & File Paths

## File Locations

### New Files Created

1. **`/sessions/charming-gracious-curie/mnt/front-office/src/ai/mle.py`**
   - Major League Equivalencies system
   - 219 lines of code
   - Main functions:
     - `calculate_mle_ratings(player_id, season)` - Calculate ratings from stats
     - `_calculate_mle_hitting_ratings(player_id, level, season)` - Hitter MLE
     - `_calculate_mle_pitching_ratings(player_id, level, season)` - Pitcher MLE
   - MLE_FACTORS dictionary with conversion rates for AAA, AA, A, LOW

2. **`/sessions/charming-gracious-curie/mnt/front-office/src/ai/scouting_modes.py`**
   - Scouting mode implementation
   - 359 lines of code
   - Main functions:
     - `get_scouting_mode()` - Get current mode from game_state
     - `apply_traditional_scouting(player, team_id, user_team_id, season, is_user_team)`
     - `apply_stat_based_scouting(player, season)`
     - `apply_variable_scouting(player, team_id, user_team_id, season, is_user_team)`
     - `get_displayed_ratings(player, user_team_id, season)` - Main entry point
     - Cache management functions

### Modified Files

1. **`/sessions/charming-gracious-curie/mnt/front-office/src/database/schema.py`**
   
   **Changes**:
   - Line 16: Added `scouting_mode TEXT NOT NULL DEFAULT 'traditional'` to game_state
   - Line 61-62: Added to teams table:
     - `broadcast_contract_type TEXT NOT NULL DEFAULT 'normal'`
     - `broadcast_contract_years_remaining INTEGER NOT NULL DEFAULT 3`
   - Line 128: Added to players table:
     - `scouted_ratings_json TEXT DEFAULT NULL`

2. **`/sessions/charming-gracious-curie/mnt/front-office/src/api/routes.py`**
   
   **Imports** (Line 14):
   - Added: `from ..ai.scouting_modes import get_displayed_ratings`
   
   **Endpoints Added**:
   - Lines 63-73: `POST /settings/scouting-mode` - Change scouting mode
   - Lines 76-80: `GET /settings/scouting-mode` - Get current mode
   - Lines 154-171: Modified `GET /player/{player_id}` - Apply scouting
   - Lines 287-302: Modified `GET /players/search` - Apply scouting to search results
   - Lines 651-668: Modified `GET /roster/{team_id}` - Apply scouting to roster
   - Lines 1008-1028: `POST /finances/{team_id}/broadcast` - Set broadcast contract
   
   **Modified Functions**:
   - Line 47: Updated `GET /game-state` to include scouting_mode in response

3. **`/sessions/charming-gracious-curie/mnt/front-office/src/financial/economics.py`**
   
   **Function: `calculate_season_finances()`**
   - Lines 44-103: Completely rewritten revenue calculation section
     - Added home/away game counting logic
     - Added broadcast contract type multiplier
     - Added home/away revenue split (85/15)
   - Lines 153-162: Added broadcast contract fields to result dict
   
   **Function: `save_season_finances()`**
   - Lines 320-343: Added broadcast contract handling
     - Contract year decrement
     - Reset to 'normal' on expiration
     - Blackout loyalty penalty application
     - Fan loyalty clamping

---

## Schema Changes Summary

### Table: game_state
```sql
scouting_mode TEXT NOT NULL DEFAULT 'traditional'  -- traditional, stat_based, variable
```

### Table: teams
```sql
broadcast_contract_type TEXT NOT NULL DEFAULT 'normal'           -- normal, cable, blackout
broadcast_contract_years_remaining INTEGER NOT NULL DEFAULT 3    -- countdown to expiration
```

### Table: players
```sql
scouted_ratings_json TEXT DEFAULT NULL  -- Cached {"season": 2026, "mode": "traditional", "scouted": {...}}
```

---

## API Endpoints

### Scouting Mode Management
```
POST /settings/scouting-mode
GET /settings/scouting-mode
```

### Broadcast Contract Management
```
POST /finances/{team_id}/broadcast
```

### Modified Endpoints (Apply Scouting)
```
GET /player/{player_id}
GET /players/search
GET /roster/{team_id}
GET /game-state  -- now includes scouting_mode
GET /finances/{team_id}/details  -- now includes broadcast contract info
```

---

## Core Logic Snippets

### Traditional Scouting Margin Calculation
```python
scouting_budget = team["scouting_staff_budget"]
scout_quality = min(100, max(20, scouting_budget // 200000))
base_margin = max(2, int(15 - scout_quality * 0.13))
margin = int(base_margin * 1.5) if not is_user_team else base_margin
displayed_rating = _clamp(true_rating + random.randint(-margin, margin))
```

### Variable Scouting Uncertainty Decay
```python
playing_time_ratio = min(1.0, playing_time / max_playing_time)  # 0-1 scale
margin_multiplier = max(0.2, 1.0 - playing_time_ratio)  # 1.0 to 0.2
margin = max(2, int(base_margin * margin_multiplier))
```

### Broadcast Revenue Multiplier
```python
contract_type = team.get("broadcast_contract_type", "normal")
if contract_type == "cable":
    broadcast_revenue = int(broadcast_revenue * 1.3)
elif contract_type == "blackout":
    broadcast_revenue = int(broadcast_revenue * 1.5)
```

### Home/Away Revenue Split
```python
home_att_pct = home_game_count / total_games
away_att_pct = away_game_count / total_games
gate_revenue = base_gate_revenue * (home_att_pct * 0.85 + away_att_pct * 0.15)
```

---

## Testing Commands

### Verify All Files Compile
```bash
cd /sessions/charming-gracious-curie/mnt/front-office
python -m py_compile src/database/schema.py src/api/routes.py src/ai/mle.py src/ai/scouting_modes.py src/financial/economics.py
```

### Quick Import Test
```bash
python -c "from src.ai.mle import calculate_mle_ratings; from src.ai.scouting_modes import get_displayed_ratings; print('OK')"
```

---

## Integration Checklist

- [x] Schema updated with 3 new fields
- [x] MLE module created and tested
- [x] Scouting modes module created and tested
- [x] Economics module updated with broadcast/home-away logic
- [x] API routes updated with scouting application
- [x] New endpoints added for settings and broadcast
- [x] All Python files compile without errors
- [x] Caching strategy implemented
- [x] Documentation created

---

## Performance Considerations

### Scouting Cache
- Reduces recalculation on repeated page loads
- Cache invalidates per-season automatically
- Stores JSON in players.scouted_ratings_json column

### Query Optimization
- Home/away game counting done once per season calculation
- Scouted ratings pulled from cache if available
- No additional database round-trips for scouting

### Complexity
- Traditional: O(1) per rating with small random noise
- Stat-Based: O(1) lookup of cached MLE conversion
- Variable: O(1) single query for playing time + margin calc

---

## Frontend Implementation Notes

### Scouting Mode UI
Should add dropdown selector in app header or settings:
```html
<select id="scouting-mode-selector">
  <option value="traditional">Traditional Scouting</option>
  <option value="stat_based">Stat-Based (MLE)</option>
  <option value="variable">Variable Scouting</option>
</select>
```

### Broadcast Contract UI
On Finances page, when years_remaining == 0:
```html
<fieldset>
  <legend>Broadcast Contract (EXPIRED - Renew Now)</legend>
  <label><input type="radio" name="contract" value="normal"> Normal (baseline revenue)</label>
  <label><input type="radio" name="contract" value="cable"> Cable (+30% revenue, 5-year lock)</label>
  <label><input type="radio" name="contract" value="blackout"> Blackout (+50% revenue, -2 loyalty/year)</label>
  <button onclick="updateBroadcast()">Accept Contract</button>
</fieldset>
```

### Rating Display
Backend now returns scouted values; frontend uses them directly:
```javascript
// No longer needed - backend handles it
// player.contact_rating is already the scouted value
console.log(player.contact_rating)  // 55 (with uncertainty)
```

---

## Database Migration Notes

When applying to existing database:
```sql
-- Add new columns to existing tables
ALTER TABLE game_state ADD COLUMN scouting_mode TEXT NOT NULL DEFAULT 'traditional';
ALTER TABLE teams ADD COLUMN broadcast_contract_type TEXT NOT NULL DEFAULT 'normal';
ALTER TABLE teams ADD COLUMN broadcast_contract_years_remaining INTEGER NOT NULL DEFAULT 3;
ALTER TABLE players ADD COLUMN scouted_ratings_json TEXT DEFAULT NULL;
```

---

## Version Information

- Implementation Date: March 16, 2026
- Python Version: 3.10+
- Dependencies: None (uses existing imports)
- FastAPI Version: Compatible with existing routes
- SQLite: Compatible with existing schema

