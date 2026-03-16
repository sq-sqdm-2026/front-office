# Implementation Checklist - Broadcast Rights & Stadium Upgrades

## Completed Tasks

### Database & Schema
- [x] Added columns to `teams` table in schema:
  - `broadcast_deal_type` (TEXT)
  - `broadcast_deal_value` (INTEGER)
  - `broadcast_deal_years_remaining` (INTEGER)
  - `stadium_built_year` (INTEGER)
  - `stadium_condition` (INTEGER)
  - `stadium_upgrades_json` (TEXT)
  - `stadium_revenue_boost` (INTEGER)
- [x] Created migration function `migrate_add_broadcast_stadium_columns()`
- [x] Added migration call to `src/main.py` startup sequence

### Backend - Broadcast System
- [x] Created `src/financial/broadcast_stadium.py` module with:
  - `BROADCAST_DEALS` dict with 4 deal types
  - `calculate_broadcast_deal_value()` - Market-based value calculation
  - `get_broadcast_status()` - Current deal status
  - `negotiate_broadcast_deal()` - Negotiate new deal
  - `apply_broadcast_deal_decrement()` - Decrement deal years at season end
  - `apply_broadcast_loyalty_penalties()` - Apply fan loyalty penalties

### Backend - Stadium System
- [x] Created stadium functions in `src/financial/broadcast_stadium.py`:
  - `STADIUM_UPGRADES` dict with 5 upgrade types
  - `get_stadium_status()` - Current stadium status
  - `purchase_stadium_upgrade()` - One-time upgrade purchase

### Financial Integration
- [x] Updated `src/financial/economics.py`:
  - Check for new `broadcast_deal_value` before legacy system
  - Integrated stadium upgrade revenue into local revenue calculation
  - Maintains backward compatibility with legacy broadcast system

### Season Advancement
- [x] Updated `src/simulation/offseason.py`:
  - Import broadcast functions
  - Call `apply_broadcast_deal_decrement()` on day 91
  - Call `apply_broadcast_loyalty_penalties()` on day 91

### API Endpoints
- [x] Added to `src/api/routes.py`:
  - `GET /finances/{team_id}/broadcast-status` - Get broadcast deal info
  - `POST /finances/{team_id}/broadcast-deal` - Negotiate new deal
  - `GET /finances/{team_id}/stadium` - Get stadium status
  - `POST /finances/{team_id}/stadium-upgrade` - Purchase upgrade

### Frontend - Finances Screen
- [x] Updated `static/app.js`:
  - Modified `loadFinances()` to fetch broadcast and stadium data
  - Added error handling with `.catch(() => null)`
  - Added "Broadcast Rights" card with:
    - Current deal display
    - Available deals list with negotiate buttons
  - Added "Stadium Management" card with:
    - Stadium info (name, capacity, condition)
    - Upgrade revenue tracker
    - Purchase buttons for each upgrade
- [x] Added JavaScript functions:
  - `negotiateBroadcastDeal(dealType)` - Handle broadcast negotiation
  - `purchaseStadiumUpgrade(upgradeKey)` - Handle stadium purchases
  - Both functions refresh Finances screen on success

## Verification Steps

- [x] Python syntax check - All files compile successfully
- [x] Routes module compiles without errors
- [x] Database migration function is safe (uses ALTER TABLE IF NOT EXISTS)
- [x] Backward compatibility maintained (legacy broadcast system still works)
- [x] Financial calculations integrated properly
- [x] Season advancement hooks installed

## Key Features Implemented

### Broadcast Rights
- 4 deal types with varying revenue/duration/loyalty tradeoffs
- Market-based value calculation
- Annual deal year decrements
- Automatic reset to standard when expired
- Fan loyalty penalties for blackout deals

### Stadium Upgrades
- 5 different upgrades with varying costs and benefits
- One-time purchase system (prevents duplicate purchases)
- Recurring annual revenue streams
- Fan loyalty bonuses for improvements
- Robust tracking via JSON

### Financial Integration
- Broadcast revenue flows into total revenue calculation
- Stadium upgrade revenue flows into local revenue
- Both systems properly affect profit/loss
- Backward compatible with legacy systems

### Season Advancement
- Broadcast deals decrement each season
- Expired deals reset to standard
- Annual fan loyalty penalties applied for blackout deals
- All processing happens automatically at offseason day 91

## Files Modified

```
src/
  database/
    schema.py           - Added new columns to schema
    db.py               - Added migration function
  financial/
    economics.py        - Integrated broadcast and stadium revenue
    broadcast_stadium.py - NEW FILE: Complete system implementation
  simulation/
    offseason.py        - Added broadcast deal management
  api/
    routes.py           - Added 4 new endpoints
  main.py               - Added migration call on startup

static/
  app.js                - Updated Finances screen with 2 new cards
```

## Ready for Testing

The implementation is complete and ready for testing:
1. Start the app (migration runs automatically)
2. Go to a team's Finances screen
3. Look for "Broadcast Rights" and "Stadium Management" cards
4. Try negotiating broadcast deals
5. Try purchasing stadium upgrades
6. Play through a season to verify deal years decrement
