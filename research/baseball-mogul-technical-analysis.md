# Baseball Mogul Technical Analysis
## Complete Research from Clay Dreslough's Blog (thegamedesigner.blogspot.com)
### Compiled 2026-03-15

This document extracts every technical detail from 20+ years of Clay Dreslough's blog posts about Baseball Mogul's design and implementation. Organized by system for reference when building a competing game.

---

## Table of Contents
1. [Simulation Engine Architecture](#1-simulation-engine-architecture)
2. [Player Rating System](#2-player-rating-system)
3. [Pitch Physics & Strike Zone Model](#3-pitch-physics--strike-zone-model)
4. [Scouting & Player Evaluation](#4-scouting--player-evaluation)
5. [Trade AI ("Tradezilla")](#5-trade-ai-tradezilla)
6. [Contract & Financial Model](#6-contract--financial-model)
7. [Player Development & Aging](#7-player-development--aging)
8. [Minor League System](#8-minor-league-system)
9. [GM AI & Roster Management](#9-gm-ai--roster-management)
10. [Win Expectancy & Analytics](#10-win-expectancy--analytics)
11. [Schedule & League Structure](#11-schedule--league-structure)
12. [Data Architecture & File Formats](#12-data-architecture--file-formats)
13. [Difficulty & Balance Philosophy](#13-difficulty--balance-philosophy)
14. [Design Philosophy & Lessons Learned](#14-design-philosophy--lessons-learned)

---

## 1. Simulation Engine Architecture

### Evolution Timeline

**1995-2006: Lookup Table Era**
- Original engine used plate-appearance-level simulation with probability lookup tables
- Combined batter and pitcher stats to calculate outcome probabilities
- Example formula: "If Manny Ramirez hits a HR in 5.68% of PAs, and Bartolo Colon allows 17% fewer HRs than league average, then Manny has a 4.71% chance of a HR"
- Adjustment factors applied on top:
  - **Platoon differential**: ~27 points of batting average
  - **Stadium effects**: e.g., right-handers hit 22% more HRs in certain parks
  - **Result normalization**: tables adjusted when percentages didn't sum to 100%
- Player abilities were abstract statistical constructs like "Avoid Strikeouts" -- divorced from actual baseball mechanics
- System couldn't model realistic pitcher-batter tactical interaction

**2007: Hybrid Era (Player Mode)**
- Baseball Mogul 2007 introduced "Player Mode" with physics-based pitch simulation
- Modeled: velocity, spin rates, pitcher accuracy targeting strike zones, batter contact ability
- BUT: Created architectural inconsistency -- pitch-by-pitch mode used physics while standard sim retained lookup tables
- Two fundamentally different engines coexisted in the same product

**2012-2013: Full Physics Rewrite**
- Complete conversion to pitch-by-pitch simulation for ALL modes
- Decision rationale: chose full physics conversion over reverting to "1950s-era dice-based mechanics"
- Resolved the architectural split from 2007

### Physics Model Components (Post-2012)

The simulation calculates four primary physical elements per pitch:

1. **Pitch Dynamics**: Velocity and trajectory path (comparable to PITCHf/x data)
2. **Batter Response**: Timing and velocity of bat swing execution
3. **Bat Mechanics**: Swing plane and sweet spot location
4. **Contact Results**: Resulting launch angle and exit velocity

### Player Ability Decomposition

Instead of abstract stats, the physics engine models:
- **Pitcher Skills**: Velocity control, spin characteristics, location precision, execution success rates
- **Batter Skills**: Pitch recognition, swing decisions that vary by count, contact ability, adaptive aggression levels

**Count-dependent behavior is emergent, not scripted:**
- Batters are more aggressive in favorable counts (3-0), more defensive in unfavorable (0-2)
- This produces realistic count-specific stats without explicit programming

### Validation Data (2006-2010 MLB comparison)

| Count | Sim BABIP | MLB BABIP | Sim AVG | MLB AVG |
|-------|-----------|-----------|---------|---------|
| 3-0   | .349      | .343      | .402    | .401    |
| 0-2   | .271      | .282      | .163    | .167    |

Dreslough: "an incredible amount of realism emerges from calculating the results of each pitch"

### Pitch Repertoire

As of 2012, the engine modeled **38+ distinct pitch types**, each with individual spin and velocity characteristics. Added pitch types include:
- Standard Knuckleball
- Slow Knuckler
- "Angry Knuckler" (R.A. Dickey's power knuckleball at ~77-80 MPH with reduced movement but higher velocity)
- Submarine delivery animations (cosmetic but modeled)

### Performance Note
The physics-based sim was fast enough for bulk season simulation, not just play-by-play mode. This was a critical engineering achievement.

---

## 2. Player Rating System

### Rating Scale Evolution

| Version | Average | Std Dev | Notes |
|---------|---------|---------|-------|
| Original (1999) | 75 | — | Designed as academic "C" grade |
| By Diamond (2014) | 82 | — | "Rating creep" -- half of players clumped 81-86 |
| BM 2016 (v1) | 75 | 7 | Reset to original intent |
| BM 2016 (v19.16+) | 80 | — | Shifted up 5 points for user comfort |

### The Rating Creep Problem

Over years of development, the average MLB player rating drifted from 75 to ~82. This caused:
- More than half of all players clustered between 81-86
- Impossible to differentiate average players from very good players
- Different ratings had inconsistent meanings: "a pitcher with 83 Control was in the top 40% of major leaguers, but a pitcher with 84 Power was actually below average"

### Calibration System (2016)

**Core Method**: Apply league and stadium adjustments to every stat before calculating ratings (similar to OPS+ methodology, where 100 = league average).

**Key Innovation**: Unlike OPS+, the system allows specifying both the center AND the distribution shape:
- Set desired mean (75, later 80)
- Set desired standard deviation (7 points)
- Fit to normal "bell curve" distribution

**Result**: About two-thirds of ratings fall between 68-82 (with 75 center). Any rating of 90+ = top 2% of MLB talent.

**Era Normalization**: A pitcher one standard deviation above league average in strikeout rate always gets an 82 Power rating, whether playing in 1927 or 2027.

### Historical Rating Problem (Pre-2016)

Strikeout rates rose 65% over 25 years, causing Power ratings to vary wildly by era:
- 1981 average pitcher Power: 70
- 2015 average pitcher Power: 83
- 1969 database: only 7 of 40 elite (90+) players were batters (17%) -- massive pitcher/hitter imbalance

**Exploit**: In 1969, computer GMs overvalued pitchers due to inflated pitcher ratings. Humans could trade away below-average pitchers for above-average hitters and sign those hitters at lower salaries.

### Available Rating Display Scales

| Scale | MLB Average | Style |
|-------|------------|-------|
| 50-100 | 80 | Default (v19.16+) |
| 25-100 | 75 | Earlier BM2016 |
| 20-80 | 50 | Professional MLB scouting standard |
| 1-20 | 13 | Football Manager/Championship Manager style |
| 25-95 | — | Art of Baseball style |

### Overall Rating Tiers (2017)

Ratings grouped into 10 categories with roster implications:
- Players rated 77-78 occupy roster spots #16-20 on an average team
- They aren't starting lineup/rotation quality but have bench/bullpen value
- The system defines expected player counts per tier across a 30-team league

### Per-Season Recalibration

Ratings are "constantly adjusted every [season] to ensure that these definitions remain meaningful over multiple seasons." This prevents future drift.

---

## 3. Pitch Physics & Strike Zone Model

### Coefficient of Restitution (COR) Bat Model

- Parabolic function along the bat's hitting surface
- COR peaks at the bat's sweet spot
- Different COR values assigned to each point on the bat
- The sweet spot traces a line through the strike zone as the batter swings (arms pivot on shoulder)

### Strike Zone Geometry

**Individual strike zones per batter**: "Albert Pujols is not only bigger than Dustin Pedroia, his strike zone is also bigger (vertically), making it slightly easier to get a pitch over for a strike."

**Sweet spot tilt**: "It's easier to reach the high outside corner with the heart of the bat than it is to reach the high inside corner" -- the sweet spot path through the zone is tilted, not horizontal.

### Heat Map Validation

- System records data for every pitch throughout a season
- Generated BABIP heat maps match real MLB patterns
- Key validation: "BABIP is slightly higher in the lower part of the strike zone, because low pitches lead to more ground balls"
- The simulation reproduced this pattern from pure physics, not from coded-in rules

### PITCHf/x Data Integration (2017)

- 600,000+ lines of PITCHf/x pitch data
- Velocity and usage patterns for every MLB season 2002-2016
- Hand-edited pitch data for 6,000+ pitchers spanning 1881-2017

---

## 4. Scouting & Player Evaluation

### Three Scouting Modes

**1. Traditional Scouting (Original)**
- Ratings reflect "true" underlying player abilities
- Basically omniscient knowledge -- players could see exact peak potential
- Made the game too easy: just draft players with highest peak ratings

**2. Variable Scouting (BM2014)**
- Enhancement to Traditional: "it's more difficult to scout young amateur players than it is to scout major league veterans"
- Young players get INCREASED uncertainty in ratings
- Veterans get DECREASED uncertainty
- Prevents trivial draft exploitation

**3. Stat-Based / Realistic Scouting (BM2014, default)**
- Ratings derived entirely from accumulated statistics
- System translates each player's stats into Major League Equivalencies (MLEs)
- Combines MLEs to create single-season projections
- Ratings represent SCOUT ASSESSMENTS, not true abilities
- Matches information available to real GMs

### Major League Equivalencies (MLEs)

- Automatically analyzes each player's career at all levels (majors + minors)
- Converts to MLB-equivalent performance
- Example: ".300 batting average with Pawtucket Red Sox might translate to .273 at the major league level"
- Applied to 1.2 million lines of minor league stats in the database

### Player Projections

- Single-season statistical forecasts calculated from past performance
- Adjusted for player age and position
- Available in Lineup, Defense, Pitching, Free Agents, Leaders dialogs
- Accessible without Commissioner Mode

### DICE (Defense Independent Component ERA)

Custom metric used internally:
```
DICE = 3.00 + (3*(BB + HBP) + 13*HR - 2*K) / IP
```
Isolates pitcher performance from defensive factors. Used for more accurate pitcher evaluation in the simulation.

---

## 5. Trade AI ("Tradezilla")

### Original System & Its Failure

**Architecture**: Used "an artificial life simulator" that analyzed millions of simulated seasons to derive player valuations.

**What it did well**: Evaluated individual player value accurately.

**What it failed at**: "Couldn't identify personnel weaknesses and then actively construct trades to improve the team."

**The exploit**: Players could repeatedly offer minor leaguers to AI teams until securing lopsided trades. The AI couldn't recognize it was being systematically exploited.

### 2014 Rewrite

**Research basis**: Analyzed 1,000+ real MLB trades and contract signings spanning a decade.

**Implementation**: 4,000 lines of new code creating "a completely new module that controls player signings, player trades, and roster management."

**Goal**: "Better match our studies of real-life GM behavior" rather than pure mathematical optimization.

### Diamond (2014) Further Fixes

**Problem persisted**: AI teams would sign star players only to bench them due to position conflicts. Poor salary and cash management.

**Solution**: Additional rewrites to Tradezilla for roster-aware decision-making.

---

## 6. Contract & Financial Model

### Real Contract Analysis (516 Players)

Dreslough analyzed MLB 40-man rosters to calibrate the game's contract model:

| Duration | % of Contracts | Avg Salary | Avg Age | Avg Overall Rating |
|----------|---------------|-----------|---------|-------------------|
| Arbitration (1yr) | 21.9% | $4.41M | 28.6 | 78.9 |
| 1 Year (non-arb) | 30.8% | $2.24M | 33.1 | 79.9 |
| 2 Years | 24.4% | $4.86M | 31.4 | 81.4 |
| 3 Years | 6.6% | $7.80M | 29.7 | 84.7 |
| 4 Years | 4.3% | $9.45M | 28.9 | 85.6 |
| 5 Years | 3.9% | $10.16M | 28.5 | 85.0 |
| 6 Years | 5.0% | $13.01M | 28.7 | 88.2 |
| 7+ Years | 3.2% | $19.18M | 30.1 | 90.7 |

**Key findings**:
- 53% of all contracts are 1-year deals
- 42% of 1-year contracts are arbitration awards
- "Steady downward trend" in signing age for longer contracts -- smarter teams sign younger talent to extensions
- Rating 90.7 average for 7+ year deals vs 78.9 for arbitration

### Free Agent Compensation (Diamond)

- Teams losing free agents after offering qualifying contracts receive draft pick compensation
- Follows CBA rules
- Customizable via "Roster Rules" dialog
- Helps small-market teams remain competitive

### Difficulty-Based Financial Adjustments

- Revenue multipliers: -10% at highest difficulty, +5% at lowest
- This is the ONLY score-adjacent manipulation -- no catch-up code in the simulation itself

### Contract Negotiation UX

- Skip button allows returning to players later during free agency
- Display of expiring contract payroll for budget planning

---

## 7. Player Development & Aging

### Defensive Spectrum Aging Model (Diamond/2014)

Players shift positions as they age, moving from difficult to easier defensive positions:

**Spectrum (easiest to hardest)**: DH → 1B → 3B → LF → CF → RF → 2B → SS

**Real examples encoded into the model**:
- Rod Carew: 2B until age 29, then 1B
- Craig Biggio: Catcher → 2B at 24 → Outfield at 36
- David Ortiz: 1B with gradual DH increase from ~15% to 97%

### Position-Specific Maturation Curves (2017)

- Each defensive ability at each position has its own maturation curve
- These curves change over time from 1890 through 2017
- Derived from comprehensive historical and minor league datasets

### Position Flexibility

"Players can switch positions back and forth without permanently harming their skills" -- fixing a previous bug where position changes caused permanent rating damage.

### Pythagorean Win Value

Used for player valuation:
```
Projected Win% = RS² / (RS² + RA²)
```
- ~10 additional runs = 1 additional win
- Run values per play: double ≈ 0.85 runs, HR ≈ 1.40 runs
- Underpins WAR calculations in the game

---

## 8. Minor League System

### Database Scale

- 1.9 million+ lines of minor league stats (1880-2016)
- Covers every level: AAA, AA, A-Advanced, A, Short-Season A, down to historical "C" and "D" leagues
- Lefty-righty splits for all players back to 1950 (via Retrosheet)

### Minor League Park Factors

Five-year park factors (2008-2012) calculated for every minor league stadium across 11+ league classifications:
- California League, Carolina League, Eastern League, Florida State League
- International League, Midwest League, New York-Penn League
- Northwest League, Pacific Coast League, South Atlantic League, Southern League

**Seven factor dimensions per park**: H, 2B, 3B, HR, BB, K, R

**Factor range**: 0.94 to 1.36 (1.0 = neutral)

### MLE Integration

Minor league stats automatically converted to Major League Equivalencies for:
- Player rating calculations
- AI roster decisions (e.g., promoting prospects)
- Draft evaluation
- "Much more accurate projections for each player, regardless of which year you start your simulation"

---

## 9. GM AI & Roster Management

### AI Philosophy

The AI does NOT use catch-up code or score-based manipulation. Dreslough explicitly states: "There isn't a single line of code in the game that looks at the score (or the standings) and then adjusts the results accordingly."

He worked on Madden NFL which had "strong catch-up code" but deliberately avoided it in Baseball Mogul.

### What Difficulty Affects

- Computer GM trading bias (favorable to human on "Fan," unfavorable on "Mogul")
- Revenue multipliers only (-10% to +5%)
- NOT simulation outcomes

### Individual Player Strategy

Managers adjust strategies per player:
- Separate steal aggression levels per player
- Pitcher pitch count limits per pitcher
- Manager AI adapts pitching usage to historical patterns

### Baserunning AI

The physics-based sim enabled realistic baserunning:
- Improved stolen base logic
- Sacrifice bunting: 85% success rate with appropriate bunters
- These behaviors are emergent from the physics, not scripted

### Roster Management Improvements (Diamond)

- AI no longer signs stars only to bench them
- Better salary and cash management
- Free agent compensation helps small-market AI teams

---

## 10. Win Expectancy & Analytics

### Win Expectancy Calculation

Displayed after each play, based on four variables:
- Current inning
- Score differential
- Number of outs
- Base runner configuration

Mirrors FanGraphs.com methodology. Always reported from home team perspective. Ranges 0-100%.

### Head-to-Head Tracking

Since 2007, tracks:
- Player-vs-player matchup results
- Player-vs-team results
- Career performance in specific matchups
- Available in Scouting Reports, pre-game lineup screen, and live play-by-play

### Charts & Pitch Tracking (2013)

Multi-dimensional filtering on recorded pitch data:
- **Pitch type**: Fastballs, sliders, all pitch classifications
- **Situation**: Two-out, RISP, close-and-late
- **Opponent**: Specific teams or individual players
- **Date range**: Custom season ranges
- **Metrics**: BABIP, slugging, batting average, etc.

### WAR Implementation

Wins Above Replacement calculated for both season and career. Was bugged in initial 2013 release, fixed in v15.07 patch.

---

## 11. Schedule & League Structure

### Schedule File Format

Filename convention: `[games]-[balance]-[league1]-[league2]-[interleague]-[year].txt`

Example: `162-U-555-555-I-2017.txt`
- 162: games per season
- U: unbalanced (more division play) / B: balanced
- 555/555: division team counts (AL: 5-5-5, NL: 5-5-5)
- I: interleague / L: league-only
- 2017: optional year (omit for template mode)

**Date format**: `"XXX M/D/Y"` (day-of-week and year ignored, only month/day processed)

**Team identification**: Two methods:
1. Numerical indexing (0-29), alphabetical within divisions (East→West), leagues (AL→NL)
2. Three-letter abbreviations (e.g., `SFG @ ARI`)

**Constraints**:
- No doubleheaders supported
- Template randomization shuffles within divisions only
- Optional "-N" suffix disables 3-day All-Star break

### League Builder

- Build leagues with any team from 1901-present
- 4 to 30 teams
- Cross-era team mixing allowed
- Can create 30 versions of same franchise to compare eras

### Expansion Draft

- Existing teams protect 15 players in round 1
- Protect 3 additional in each subsequent round
- Players drafted in last 3 seasons: exempt from protection
- Under-22 players cannot be selected
- Auto-generates second expansion team for balance
- Teams can leave high-contract players unprotected as salary dumps

---

## 12. Data Architecture & File Formats

### Database Export

- Save as text files instead of compressed format
- Generates folder with CSV files
- Primary file: "YBY.csv" (Year-By-Year stats for every player)
- Files are editable in Excel/LibreOffice and re-importable
- Enables third-party tool development (e.g., Box Score Parser)

### Stadium Art Format

Two files per stadium:
1. **Image**: JPG, resized to 640 x 480 pixels
2. **Config (.ini)**: Seven coordinate pairs (home, 1B, 2B, 3B, LF corner, CF wall, RF corner)
- Coordinates from upper-left origin (0,0), X right, Y down
- Comments allowed after `//`
- Both files go in game's 'Stadiums' folder

### Player Skin Tone Database

1-9 ordinal scale, stored as CSV with Lahman database IDs:
```
playerid,skintone
aaronha01,9
abbotje01,1
```
Creative Commons licensed for public research.

### Historical Data Sources

- Retrosheet.com: Lefty-righty splits back to 1950
- PITCHf/x: 600K+ lines, 2002-2016
- Lahman database: Player identification
- Hand-edited pitch data: 6,000+ pitchers, 1881-2017
- 1.9M+ lines of minor league stats, 1880-2016

---

## 13. Difficulty & Balance Philosophy

### No Catch-Up Code

Dreslough is emphatic: the simulation is clean. Perceived "cheating" by the AI is statistical variance, not coded manipulation. This was a deliberate philosophical choice based on his experience with Madden NFL's catch-up code.

### Difficulty Levers (ONLY these)

1. Trade bias: AI more/less favorable in negotiations
2. Revenue multiplier: -10% to +5% on human team revenue
3. Scouting accuracy: Variable scouting makes prospects harder to evaluate

### The "Too Easy" Problem

Pre-2014, the game was exploitable via:
1. Trading minor leaguers repeatedly until getting lopsided deals
2. Using scouting to gain "psychic powers" about player potential
3. Exploiting era-based rating imbalances

All three were systematically addressed in BM2014.

---

## 14. Design Philosophy & Lessons Learned

### Core Principle: Restraint Over Complexity

"The desire to 'improve' games by adding complexity" is usually wrong. Dreslough advocates allowing natural game mechanics to resolve edge cases rather than adding rules.

### "Baseball Mogul is a computer game, but it doesn't have to feel like a simulation"

Balance between:
- Convenient gameplay mechanics
- Maintaining strategic decision-making realism
- Accessibility for casual players AND stat nerds AND franchise management fans

### Rating Shock Management

When recalibrating ratings (dropping everyone ~8 points), Dreslough noted that code changes to revenue, ticket sales, or pitcher usage generate zero complaints, but visible rating drops feel like "your employer suddenly cut your pay by 8%." The underlying talent is unchanged -- it's purely perception. Lesson: visible numbers carry emotional weight far beyond their mechanical impact.

### Emergent vs. Scripted Behavior

The physics-based sim's biggest win: count-specific batting behavior, baserunning decisions, and pitch effectiveness all EMERGE from the physics model rather than being scripted. This produces more realistic edge cases and avoids the "uncanny valley" of scripted interactions.

### Evolution Over 20+ Years

Key technical milestones:
- 1995: Lookup tables (Strat-O-Matic digital)
- 2007: Hybrid physics/lookup (architectural mistake)
- 2012: Full physics rewrite (correct but enormous effort)
- 2014: Scouting/trade overhaul (gameplay balance)
- 2016: Rating calibration system (consistency across eras)
- 2017: Historical normalization per stat/season/position/stadium

The pattern: each major version tackled ONE systemic problem. The game improved through focused iteration, not feature bloat.

---

## Source Posts (All from thegamedesigner.blogspot.com)

| Date | Post | Primary Topic |
|------|------|---------------|
| 2005-11-25 | Will The Real Guillermo Mota Please Stand Up? | DICE formula |
| 2008-07-16 | Over-Active Game Design | Design philosophy |
| 2012-03-01 | Under The Hood, Part 1 | Physics sim architecture |
| 2012-03-10 | Under The Hood, Part 2 | Database export format |
| 2012-03-20 | Pitch Tracking and Charts Tab | Analytics/filtering |
| 2012-03-22 | Strike Zone Heat Maps | COR bat model, validation |
| 2012-03-25 | Win Expectancy | WE calculation |
| 2012-05-23 | Version 15.07 | Bug fixes, L/R splits |
| 2012-05-29 | Pythagoras Explained | Win formula, WAR basis |
| 2012-05-30 | Simulation Engine | Engine evolution history |
| 2012-06-23 | Baseball Contract Analysis | Contract model data |
| 2012-07-11 | Dickey's Angry Knuckleball | Pitch type system |
| 2013-02-01 | The Skin Color Project | Player data representation |
| 2013-02-16 | Fixing The Game Part 1 | Trade AI failures |
| 2013-02-22 | Submarine Pitcher | Animation system |
| 2013-02-24 | Fixing The Game Part 2 | Scouting system redesign |
| 2013-02-28 | Minor League Stats | MLE system |
| 2013-03-01 | Baseball Mogul 2014 | Feature overview |
| 2013-03-05 | Minor League Park Factors | Park factor methodology |
| 2013-03-24 | 2014 New Features | Comprehensive feature list |
| 2014-04-17 | Expansion Team Creation | Draft/roster mechanics |
| 2014-12-06 | Baseball Mogul Diamond | Aging model, FA compensation |
| 2014-12-09 | Head-to-Head Stats | Matchup tracking since 2007 |
| 2015-02-16 | League Builder | Custom league creation |
| 2015-03-29 | Head-to-Head Records | Team vs team tracking |
| 2016-04-05 | Rating Calibration | Rating normalization system |
| 2016-09-20 | Rating Update | Rating scale options |
| 2017-03-19 | "Horse Shit" Post | No catch-up code, difficulty |
| 2017-03-25 | Stadium Art | File format specs |
| 2017-04-05 | Schedule File Formats | Schedule file specification |
| 2017-04-07 | Improvements to BM 2017 | Maturation curves, PITCHf/x |
| 2017-07-18 | Overall Ratings | Rating tier definitions |
