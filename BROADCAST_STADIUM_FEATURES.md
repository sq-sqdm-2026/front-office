# Broadcast Rights & Stadium Management Features

## Overview

Added two major Baseball Mogul-style owner management features to the Front Office baseball simulator:

1. **TV Broadcast Rights Negotiation** - Dynamic broadcast deal negotiation system
2. **Stadium Upgrades** - Capital investment system for stadium improvements

Both systems integrate fully with the financial model and season advancement cycle.

---

## 1. TV BROADCAST RIGHTS SYSTEM

### Database Schema

New columns added to `teams` table:
- `broadcast_deal_type TEXT DEFAULT 'standard'` - Type of broadcast deal
- `broadcast_deal_value INTEGER DEFAULT 0` - Annual value in dollars
- `broadcast_deal_years_remaining INTEGER DEFAULT 3` - Years until deal expires

### Deal Types

Four broadcast deal types available, each with different revenue multipliers and terms:

#### Standard Regional
- **Multiplier**: 1.0x base revenue
- **Duration**: 3 years
- **Value Range**: $35-55M/year (market-dependent)
- **Fan Loyalty Impact**: None
- **Restrictions**: None

#### Premium Cable
- **Multiplier**: 1.3x base revenue
- **Duration**: 5 years (locked)
- **Value Range**: $50-80M/year
- **Fan Loyalty Impact**: None
- **Benefits**: Highest revenue commitment, long-term stability

#### Streaming Exclusive
- **Multiplier**: 1.2x base revenue
- **Duration**: 4 years
- **Value Range**: $40-70M/year
- **Fan Loyalty Impact**: -5 per deal
- **Note**: Reduces fan loyalty due to blackout restrictions

#### Blackout Package
- **Multiplier**: 1.5x base revenue
- **Duration**: 3 years
- **Value Range**: $60-100M/year
- **Fan Loyalty Impact**: -10 per deal (and -10 each season while active)
- **Warning**: Highest revenue but most damaging to fan loyalty

### Revenue Calculation

Base broadcast value is calculated from market fundamentals:
```
base_value = (market_size * 8,000,000) + (fan_base * 200,000)
deal_value = base_value * deal_multiplier
```

Then clamped to deal-type specific ranges (e.g., Standard: $35M-$55M)

### Frontend UI

New "Broadcast Rights" card in Finances screen shows:
- Current deal name and annual value
- Years remaining on current deal
- Available deals with estimated values for each
- "Negotiate" button for each deal type

### Backend Endpoints

**GET /finances/{team_id}/broadcast-status**
Returns current broadcast deal and all available options.

**POST /finances/{team_id}/broadcast-deal**
Request body: `{"deal_type": "standard|premium_cable|streaming|blackout"}`

Applies fan loyalty impacts immediately and updates broadcast deal.

### Season Advancement

At end of each season (offseason day 91):
1. Broadcast deal years decrement by 1
2. If years reach 0, deal expires and resets to "standard" with 3-year term
3. Fan loyalty penalties from blackout deals apply (-10 per year)

---

## 2. STADIUM UPGRADES SYSTEM

### Database Schema

New columns added to `teams` table:
- `stadium_built_year INTEGER DEFAULT 2000` - Year stadium was built
- `stadium_condition INTEGER DEFAULT 85` - Condition rating (0-100)
- `stadium_upgrades_json TEXT DEFAULT '{}'` - JSON tracking purchased upgrades
- `stadium_revenue_boost INTEGER DEFAULT 0` - Annual recurring revenue from upgrades

### Available Upgrades

Each upgrade is a one-time capital purchase with recurring annual revenue:

#### Luxury Suites
- **Cost**: $15M
- **Annual Revenue**: $3M
- **Fan Loyalty Impact**: +2
- **Description**: Premium seating with club access

#### Jumbotron/Tech
- **Cost**: $8M
- **Annual Revenue**: $1.5M
- **Fan Loyalty Impact**: +5
- **Description**: Modern video displays and stadium technology

#### Concourse Renovation
- **Cost**: $12M
- **Annual Revenue**: $2M
- **Fan Loyalty Impact**: +3
- **Description**: Improved concession areas and walkways

#### Field Renovation
- **Cost**: $5M
- **Annual Revenue**: $500K
- **Fan Loyalty Impact**: +2
- **Description**: Improved playing surface and facilities

#### Retractable Roof
- **Cost**: $50M
- **Annual Revenue**: $5M
- **Fan Loyalty Impact**: +10
- **Description**: Weather control - no rain delays, enhanced experience

### Revenue Integration

Stadium upgrade revenue is added to local revenue calculation in financial model:
```
local_revenue = ticket_revenue + concession_revenue +
                merchandise_revenue + stadium_upgrade_revenue
```

This makes stadium upgrades provide sustained value throughout the season.

### Frontend UI

New "Stadium Management" card in Finances screen shows:
- Stadium name and year built
- Capacity and condition rating
- Annual revenue from purchased upgrades
- All available upgrades with:
  - Cost and annual revenue
  - Fan loyalty impact
  - "Buy" or "Owned" button

### Backend Endpoints

**GET /finances/{team_id}/stadium**
Returns current stadium status and all available upgrades.

**POST /finances/{team_id}/stadium-upgrade**
Request body: `{"upgrade_key": "luxury_suites|jumbotron|concourse|field_renovation|retractable_roof"}`

Purchase is deducted from team cash immediately. Can only purchase each upgrade once.

---

## 3. FINANCIAL INTEGRATION

### Changes to Economics Module

The broadcast deal system integrates into revenue calculation in `economics.py`:

1. **Broadcast Revenue** - Uses new `broadcast_deal_value` if available
   - Falls back to legacy `broadcast_contract_type` for backward compatibility
   - This allows gradual migration from old to new system

2. **Stadium Revenue** - Added to local revenue
   - Accumulated from all purchased upgrades
   - Provides recurring annual value

### Calculate Season Finances

Called at end of each season to:
1. Calculate all revenue sources (including broadcast and stadium)
2. Calculate expenses and profit
3. Update team cash
4. Update franchise valuation
5. Handle broadcast deal expiration

---

## 4. SEASON ADVANCEMENT INTEGRATION

### Offseason Processing

In `src/simulation/offseason.py`, added calls on offseason day 91:

```python
# Apply broadcast deal year decrement and loyalty penalties
apply_broadcast_deal_decrement(team_id, db_path)
apply_broadcast_loyalty_penalties(team_id, db_path)
```

This ensures:
- Broadcast deals count down each season
- Expired deals reset to standard
- Fan loyalty penalties accumulate for blackout deals

---

## 5. BACKWARD COMPATIBILITY

The system maintains full backward compatibility:

1. **Legacy Broadcast System**: Old `broadcast_contract_type` (normal/cable/blackout) still works
   - New broadcast deal system takes precedence if `broadcast_deal_value > 0`
   - Legacy system provides fallback for existing teams

2. **Migration**: `migrate_add_broadcast_stadium_columns()` function
   - Called on app startup if database exists
   - Adds all new columns if they don't exist
   - Runs safely even if columns already present

---

## 6. FILE CHANGES SUMMARY

### Python Files Created
- `src/financial/broadcast_stadium.py` - Complete broadcast and stadium management system

### Python Files Modified
- `src/database/schema.py` - Added new table columns to schema definition
- `src/database/db.py` - Added migration function
- `src/financial/economics.py` - Integrated broadcast deal and stadium revenue
- `src/simulation/offseason.py` - Added broadcast deal year decrements and loyalty penalties
- `src/api/routes.py` - Added 4 new endpoints
- `src/main.py` - Call migration on startup

### JavaScript Files Modified
- `static/app.js` -
  - Updated `loadFinances()` to fetch broadcast and stadium data
  - Added two new cards to Finances screen (Broadcast Rights, Stadium Management)
  - Added `negotiateBroadcastDeal()` function
  - Added `purchaseStadiumUpgrade()` function

---

## 7. TESTING NOTES

All Python files compile without errors. The system:

1. **Should initialize** on first startup (migration runs and adds columns)
2. **Should work with existing data** (backward compatible)
3. **Should calculate** broadcast revenue correctly based on market size
4. **Should apply** fan loyalty impacts when negotiating deals
5. **Should decrement** broadcast deal years at end of season
6. **Should reset** expired deals to standard
7. **Should accumulate** stadium revenue annually
8. **Should purchase** stadium upgrades with team cash

---

## 8. USAGE EXAMPLE

### For a Team Manager:

1. **Negotiate a Premium Cable Deal**:
   - Go to Finances screen
   - Find "Broadcast Rights" card
   - Click "Negotiate" next to "Premium Cable"
   - Receive +30% revenue boost for 5 years

2. **Invest in Stadium**:
   - See "Stadium Management" card
   - Click "Buy" on "Retractable Roof" ($50M)
   - Gain +$5M annual revenue and +10 fan loyalty
   - View updated "Annual Upgrade Revenue" in card

3. **Track Results**:
   - Broadcast revenue increases in Revenue card each season
   - Stadium upgrade revenue accumulates
   - At season end, broadcast deal years decrement

---

## 9. BASEBALL MOGUL INSPIRATION

These features directly mirror Baseball Mogul's owner management:
- **Dynamic deal negotiation** with revenue/restriction tradeoffs
- **Capital investment decisions** with ROI calculations
- **Trade-offs between revenue and fan loyalty** (blackout deals)
- **Long-term financial planning** (5-year Premium Cable commitment)
- **Recurring revenue sources** from capital improvements

Both systems reward strategic, long-term thinking over short-term cash grabs.
