# Feature Usage Guide

Quick reference for using the four new features in Front Office.

## 1. Depth Chart Screen

### Access
- Click "Depth Chart" in the main navigation (between Lineup and Standings)

### Usage
- View all players organized by position
- Each position shows:
  - ★ Starting player (highest rating)
  - ▲ Backup players
  - ◆ Prospect/minor league players
- Click any player name to open their detail modal
- Color-coded ratings:
  - Green (65+): Elite
  - Yellow (50-64): Good
  - Red (<50): Below average

### Information Displayed per Player
- Name and position
- Age
- Overall rating (average of key abilities)
- Roster status (active, minors, etc.)
- Handedness (bats/throws)

---

## 2. Commissioner Mode

### Enable/Disable
1. Click the settings gear icon (⚙️) in top bar
2. Toggle "Commissioner Mode" button
3. Button shows "ON" or "OFF" state

### Edit a Player
1. With Commissioner Mode ON, go to any player screen
2. Click the "Edit" button on the player modal
3. Modify any field:
   - Ratings (contact, power, speed, fielding, arm, stuff, control, stamina)
   - Personality (ego, leadership, work ethic, clutch, morale, etc.)
   - Age, position, secondary positions
4. Click "Save Changes"
5. You'll see a confirmation toast

### Edit a Team
1. With Commissioner Mode ON, view a team page
2. Click the "Edit" button (if available on team panel)
3. Modify fields:
   - Cash balance
   - Franchise value
   - Fan loyalty (1-100)
   - Budget allocations (farm, medical, scouting)
4. Click "Save Changes"

### Force a Trade
1. Go to Trade Center screen
2. Select players from both teams
3. With Commissioner Mode ON, click "Force Trade" button
4. Trade executes immediately without AI approval
5. Transaction is logged

### Force-Sign a Free Agent
1. Go to Free Agents screen
2. Select a free agent player
3. With Commissioner Mode ON, click "Force Sign"
4. Specify: Team, salary, contract years
5. Player is immediately signed

### Field Validation
All fields are automatically clamped to valid ranges:
- Ability ratings: 20-80
- Personality traits: 1-100
- Age: 18-45
- Budgets: Non-negative integers

---

## 3. Customizable Stat Columns

### Configure Batting Stats
1. Click settings gear icon (⚙️)
2. Click "Edit Batting Columns"
3. Check/uncheck columns you want to display
4. Click "Save"

### Configure Pitching Stats
1. Click settings gear icon (⚙️)
2. Click "Edit Pitching Columns"
3. Check/uncheck columns you want to display
4. Click "Save"

### Available Batting Columns (choose any)
name, pos, team, age, G, AB, R, H, 2B, 3B, HR, RBI, BB, SO, SB, CS, AVG, OBP, SLG, OPS

### Available Pitching Columns (choose any)
name, pos, team, age, G, GS, W, L, SV, HLD, IP, H, ER, BB, SO, HR, ERA, WHIP, K/9, BB/9

### Column Selection Tips
- Minimum 2-3 columns recommended for readability
- Always include "name" and "team" for context
- Default selection includes the most common stats

---

## 4. CSV Export

### Export Team Roster
1. Go to Roster screen
2. Look for "Export CSV" button (or use JavaScript console)
3. In console: `exportCSV('roster')`
4. Browser downloads: `roster.csv`

Columns exported: ID, Name, Position, Age, Status, Overall, Contact, Power, Speed, Fielding, Arm, Stuff, Control, Stamina, Salary, Years Remaining

### Export Batting Statistics
1. Go to Leaders screen
2. Use JavaScript console: `exportCSV('batting-stats', {season: 2026})`
3. Browser downloads: `batting-stats-2026.csv`

Columns exported: Name, Team, G, AB, R, H, 2B, 3B, HR, RBI, BB, SO, SB, CS, AVG, OBP, SLG, OPS

### Export Pitching Statistics
1. Go to Leaders screen
2. Use JavaScript console: `exportCSV('pitching-stats', {season: 2026})`
3. Browser downloads: `pitching-stats-2026.csv`

Columns exported: Name, Team, G, GS, W, L, SV, HLD, IP, H, ER, BB, SO, HR, ERA, WHIP, K/9, BB/9

### Export Financial History
1. Go to Finances screen
2. Use JavaScript console: `exportCSV('financials')`
3. Browser downloads: `financials.csv`

Columns exported: Season, Ticket Revenue, Concession Revenue, Broadcast Revenue, Merchandise Revenue, Total Revenue, Payroll, Farm Expenses, Medical Expenses, Scouting Expenses, Stadium Expenses, Owner Dividends, Total Expenses, Profit, Attendance Total, Avg Attendance

### Using Browser Console
1. Open browser Developer Tools (F12)
2. Go to Console tab
3. Type: `exportCSV('roster')`
4. Press Enter

---

## API Endpoints Reference

### Depth Chart
- `GET /team/{team_id}/depth-chart` - Get all positions with players

### Commissioner Mode
- `POST /settings/commissioner-mode` - Toggle on/off
- `GET /settings/commissioner-mode` - Get current state
- `POST /commissioner/edit-player/{player_id}` - Edit player
- `POST /commissioner/edit-team/{team_id}` - Edit team
- `POST /commissioner/force-trade` - Execute trade
- `POST /commissioner/force-sign/{player_id}` - Sign free agent
- `POST /commissioner/set-record/{team_id}` - Set record

### Stat Columns
- `GET /settings/stat-columns` - Get configuration
- `POST /settings/stat-columns` - Save configuration

### CSV Export
- `GET /export/roster/{team_id}` - Download roster CSV
- `GET /export/batting-stats?season=2026` - Download batting CSV
- `GET /export/pitching-stats?season=2026` - Download pitching CSV
- `GET /export/financials/{team_id}` - Download financials CSV

---

## Keyboard Shortcuts

- Press `Ctrl+K` for global search (existing)
- Gear icon or `Alt+S` for settings (new)

---

## Tips & Tricks

### Depth Chart
- Use for quick roster analysis
- Identify weaknesses by position
- Plan trades and call-ups

### Commissioner Mode
- Use for testing and experimentation
- Balance teams for competitive play
- Create custom scenarios

### Stat Columns
- Customize for your analysis style
- Create lightweight displays for mobile
- Save different configs for different uses

### CSV Export
- Use for external analysis tools
- Create season reports
- Track financial performance
- Build custom analytics

---

## Troubleshooting

### Commissioner Mode not working?
- Make sure it's toggled ON (button should show "ON")
- Check browser console for errors (F12)
- Try refreshing the page

### Stat columns not saving?
- Check network tab in developer tools
- Verify at least one column is selected
- Try a different browser

### CSV export not downloading?
- Check if pop-ups are blocked
- Try using browser console: `exportCSV('roster')`
- Check Downloads folder for file

### Depth chart shows no players?
- Make sure team has players in roster
- Check that players are in "active" or "minors" status
- Verify team_id is correct

