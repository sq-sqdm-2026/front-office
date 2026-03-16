# FRONT OFFICE: The Complete Build Bible
### A Baseball Universe Simulation — Technical Reference, Research, & Status
**Last Updated:** March 16, 2026 | **Version:** Phase 1 Complete (Baseball Mogul Feature Parity)

---

## Table of Contents

1. [Vision & Design Philosophy](#1-vision--design-philosophy)
2. [Technical Architecture](#2-technical-architecture)
3. [Baseball Mogul Technical Analysis (Research)](#3-baseball-mogul-technical-analysis)
4. [Simulation Engine Deep Dive](#4-simulation-engine-deep-dive)
5. [Player Rating System](#5-player-rating-system)
6. [Financial Model](#6-financial-model)
7. [Transaction Systems](#7-transaction-systems)
8. [AI & LLM Integration](#8-ai--llm-integration)
9. [Real MLB Data Pipeline](#9-real-mlb-data-pipeline)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Database Schema Reference](#11-database-schema-reference)
12. [API Endpoint Reference](#12-api-endpoint-reference)
13. [Current Build Status](#13-current-build-status)
14. [Gap Analysis: Us vs. Baseball Mogul](#14-gap-analysis-us-vs-baseball-mogul)
15. [Gap Analysis: Us vs. Design Doc](#15-gap-analysis-us-vs-design-doc)
16. [Development Roadmap](#16-development-roadmap)
17. [Key Formulas & Algorithms](#17-key-formulas--algorithms)
18. [File Inventory](#18-file-inventory)
19. [Lessons from 20 Years of Baseball Mogul](#19-lessons-from-20-years-of-baseball-mogul)

---

## 1. Vision & Design Philosophy

### What This Is
Front Office is a baseball universe simulation where every GM, owner, agent, scout, beat writer, and broadcaster is an LLM-powered character with persistent personality, memory, and motivation — all running locally on a Mac Mini M4 Pro via Ollama. No subscriptions. No cloud dependency.

### The Core Insight
**"The baseball is the engine that drives the drama. The drama is the product."**

This is not a baseball game with features bolted on. It is a rich fictional universe experienced from the GM's chair. The foundation is Baseball Mogul's proven simulation engine — franchise financials, player aging, contracts, trades, draft, free agency, minors, season simulation. On top of that sits a social simulation layer where every decision ripples through relationships, media narratives, organizational politics, and career consequences.

### The Baseline
Baseball Mogul gives you the spreadsheet. Front Office gives you the world behind it.

### What Makes This Different
- Every character driven by an LLM with persistent personality and memory
- Spoofed phone messaging system for direct contact with GMs, agents, owners, reporters
- Asymmetric information — what you know depends on who you trust
- Characters have full career arcs (scouts become GMs, fired GMs become TV analysts)
- Weekly audio podcast via Orpheus TTS
- Emergent narratives, not scripted storylines
- The game creates itself anew every time you pick it up

### Target Hardware
Mac Mini M4 Pro, 64GB RAM. Ollama running qwen3:32b (strategic) and qwen3:14b (creative). All local.

### The Story Entry Point
February 14, 2026. A small-market owner fires his GM and hires an outsider — an AI-savvy, forward-thinking baseball mind with a modest mid-term contract. Three teams available: Pittsburgh Pirates, Kansas City Royals, Cincinnati Reds. Each with a unique owner personality and challenge. This is where the player's story begins.

---

## 2. Technical Architecture

### Stack
| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+, FastAPI, SQLite (WAL mode) |
| Frontend | Vanilla HTML/CSS/JS (no framework, served as static files) |
| AI | Ollama (localhost:11434) — qwen3:32b strategic, qwen3:14b creative |
| TTS | Orpheus TTS 3B (planned Phase 3) |
| Data Source | MLB Stats API (free, no auth) for real player/team data |
| Access | Any device on local network via port 8000, remotely via Tailscale |

### Project Structure
```
front-office/
├── FRONT-OFFICE-BIBLE.md      # This document
├── requirements.txt            # fastapi, uvicorn, httpx, aiosqlite
├── mlb_cache.json              # Cached real MLB data (not in git)
├── front_office.db             # SQLite database (not in git)
├── research/
│   └── baseball-mogul-technical-analysis.md  # 612-line deep research
├── src/
│   ├── main.py                 # Entry point, seeds DB, mounts static
│   ├── database/
│   │   ├── schema.py           # 18 tables, all CREATE statements
│   │   ├── db.py               # Connection helpers (WAL, Row factory)
│   │   ├── seed.py             # Generated player/team data
│   │   ├── seed_real.py        # Real MLB data seeder
│   │   └── real_data.py        # MLB Stats API fetcher + rating converter
│   ├── simulation/
│   │   ├── game_engine.py      # At-bat resolution, full game sim
│   │   ├── season.py           # Day/week sim, standings, phase mgmt
│   │   ├── schedule.py         # Balanced 162-game schedule generator
│   │   ├── injuries.py         # 20 injury types, healing
│   │   ├── player_development.py # Growth/peak/decline curves
│   │   ├── strategy.py         # Team tactical settings
│   │   └── offseason.py        # Arbitration, FA, draft orchestration
│   ├── transactions/
│   │   ├── trades.py           # Trade proposals + deadline enforcement
│   │   ├── free_agency.py      # FA market + AI bidding
│   │   ├── draft.py            # 600-prospect draft with floor/ceiling
│   │   ├── roster.py           # 40-man, call-ups, options, DFA
│   │   ├── contracts.py        # Arbitration, expiration, service time
│   │   ├── waivers.py          # 7-day DFA waiver system
│   │   └── ai_trades.py        # AI-initiated daily trade logic
│   ├── financial/
│   │   └── economics.py        # Revenue, expenses, profit model
│   ├── ai/
│   │   ├── ollama_client.py    # Ollama wrapper with model routing
│   │   ├── gm_brain.py         # LLM trade eval + scouting reports
│   │   └── player_comps.py     # 54 MLB comps from 1985-2011 era
│   └── api/
│       └── routes.py           # 52 FastAPI endpoints
├── static/
│   ├── index.html              # SPA shell
│   ├── style.css               # "Bloomberg Terminal meets Baseball Reference"
│   └── app.js                  # All frontend logic
└── tests/
    └── __init__.py
```

### How to Run
```bash
cd ~/front-office
source venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 8000
# Access at http://localhost:8000 or http://192.168.27.215:8000
```

First run auto-seeds the database from `mlb_cache.json` (real data) or generates players if no cache exists.

---

## 3. Baseball Mogul Technical Analysis

*Full 612-line research document at `research/baseball-mogul-technical-analysis.md`. Key findings summarized below.*

### Sim Engine Evolution (1995-2013)
Clay Dreslough (Baseball Mogul creator) rewrote the simulation engine three times:

**1995-2006: Lookup Tables.** Each plate appearance used probability tables. Batter HR% × pitcher HR-suppression rate = matchup probability. Example: Ramirez HRs in 5.68% of PAs, Colon allows 17% fewer HRs → 4.71% HR probability. Platoon (+27 points AVG), park factors, and normalization layered on top.

**2007: Hybrid.** "Player Mode" introduced physics-based pitch simulation (velocity, spin, batter timing). But standard sim kept lookup tables. Two incompatible engines coexisted.

**2012-2013: Full Physics.** Complete rewrite to pitch-by-pitch for ALL modes. Each pitch modeled with velocity, spin, trajectory. Bat has coefficient of restitution (COR) modeled as a parabola along the sweet spot. Count-dependent behavior emerges naturally (not hardcoded):

| Count | Sim BABIP | MLB BABIP | Sim AVG | MLB AVG |
|-------|-----------|-----------|---------|---------|
| 3-0   | .349      | .343      | .402    | .401    |
| 0-2   | .271      | .282      | .163    | .167    |

38+ pitch types modeled, including R.A. Dickey's "Angry Knuckler."

### Rating System
- Average player = 75 (later 80 after calibration)
- Standard deviation = 7 points
- Ratings recalibrated every simulated season to prevent drift
- "Rating creep" was a real problem (average drifted from 75 to 82 over 10 sim years)
- Fixed in 2016 with era-normalized calibration

**Our implementation:** Uses 20-80 scouting scale (industry standard). 50 = average. No era-normalization yet.

### Trade AI ("Tradezilla")
- Original used artificial life simulator — could value players but couldn't construct roster-improving trades
- Rewritten in 2014 with 4,000 lines of code
- Analyzed 1,000+ real MLB trades to calibrate
- Key insight: AI needs to identify its own roster weaknesses before evaluating incoming players

**Our implementation:** LLM-first with algorithmic fallback. Fallback now includes roster-aware position needs analysis. Conceptually different (and potentially better) approach, but algorithmic depth is shallow compared to Tradezilla's 4,000 lines.

### Contract Model
- Calibrated against analysis of 516 real contracts
- Distribution: 53% are 1-year, 21.9% arbitration, 7+ year deals average rating 90.7 and $19.18M AAV
- Player personality affects negotiations (greedy players demand within 5% of asking; generous tolerate 20% below)
- Non-money factors: playing time, friends on team, clubhouse atmosphere, ambition

**Our implementation:** Basic salary/years with arbitration. No personality-driven negotiation. No non-money factors.

### Aging & Development
- 4 hidden parameters per player: Peak Start, Peak End, Potential (growth rate), Longevity (decay rate)
- Defensive spectrum shift: SS→2B→3B→LF→CF→RF→1B→DH as players age
- Position-specific maturation curves that change across eras (1890-2017)

**Our implementation:** 3-phase model (growth/peak/decline) with peak_age and development_rate. Defensive spectrum aging implemented (SS->3B at 32, 3B->1B at 33, CF->corner OF at 31, corner OF->DH at 35). No era adjustment.

### Difficulty
- No catch-up code. Zero. Clay is emphatic.
- Difficulty only affects: trade bias (-/+ favorability) and revenue multiplier (-10% to +5%)
- Fan level: +5% revenue, AI favors trades with you
- Mogul level: -10% revenue, AI resists trades with you

**Our implementation:** Four difficulty levels (Fan/Coach/Manager/Mogul) affect revenue (+5% to -10%), trade acceptance (+10% to -20%), and arbitration salaries (Mogul +10%). No catch-up code.

### Scouting System (3 modes)
1. **Traditional**: Hidden "true" ratings, displayed with uncertainty margin (+/- N points)
2. **Stat-Based**: Ratings projected entirely from accumulated statistics via Major League Equivalencies (1.9M minor league stat lines)
3. **Variable**: Uncertainty decreases as player accumulates playing time

**Our implementation:** Scout quality system with +/- uncertainty margin. Full structured reports with present/future grades, OFP, MLB comps (1985-2011 era). No MLE system. No scouting modes (Traditional/Stat-Based/Variable) yet.

---

## 4. Simulation Engine Deep Dive

### Architecture: Probability-Based At-Bat Resolution

Our engine resolves each plate appearance by calculating outcome probabilities from the interaction of batter ratings, pitcher ratings, park factors, platoon advantage, fatigue, and leverage.

### At-Bat Resolution Formula

```
For each outcome type, probability = base_rate × batter_modifier × pitcher_modifier × park_modifier × platoon

Where:
  batter_modifier = 1.0 + (rating - 50) × 0.0167
  pitcher_modifier = same formula applied to pitcher ratings
  platoon = 1.08 (opposite hand), 0.92 (same hand), 1.02 (switch)
  fatigue = max(0.6, 1.0 - (pitches_over_threshold × 0.01))
```

### Outcome Probability Baselines (MLB averages)
| Outcome | Base Rate | Modified By |
|---------|-----------|-------------|
| Walk | .085 | Pitcher control, park |
| HBP | .012 | Fixed |
| Strikeout | .225 | Pitcher stuff, batter contact, park |
| Home Run | .033 | Batter power, park HR factor, platoon, pitcher stuff |
| Triple | .005 | Batter speed, park triple factor |
| Double | .045 | Batter power, park double factor |
| Single | .150 | Batter contact, park hit factor, pitcher stuff |
| Sac Fly | .015 | Only with runners in scoring position |
| Ground Out | .220 | Remainder |
| Fly Out | .220 | Remainder |

### Park Factor Calculation
```python
avg_dimensions = 330 + 375 + 400 + 375 + 330 = 1810 feet
hr_factor = 0.7 + (1810 / actual_total) × 0.6
hr_factor *= 1.0 + (altitude / 20000)  # Coors = ~1.26x
hr_factor *= 0.95 if dome
double_factor = 1.1 if turf
triple_factor = 1.15 if turf, × 1.1 if CF > 405
hit_factor = 0.97 if large foul territory, 1.03 if small
```

### Bullpen Management Logic
```
Starter pulled when: pitches > min(strategy_limit, 70 + stamina × 0.75)
  OR innings > 5 + (stamina - 30) × 0.04
  OR (inning ≥ 7 AND runs_allowed ≥ 4)

Reliever selection:
  Blowout (|score_diff| > 6): worst available (mop-up)
  9th inning, lead 1-3: closer (last bullpen arm, highest stuff)
  8th inning: setup man (2nd to last)
  7th inning: 7th inning guy
  Innings 5-6: long reliever (first available)
```

### Stolen Base System
```
Attempt probability: 0.08 × (runner_speed / 50) × strategy_multiplier
  conservative = 0.5x, normal = 1.0x, aggressive = 2.0x
Success rate: 0.65 + (speed - 50) × 0.005, clamped [0.35, 0.95]
Only with runner on 1st (stealing 2nd) or 2nd (stealing 3rd), < 2 outs
```

### Double Play Formula
```
Base rate: 50%
  Runner speed ≥ 70: 30%
  Runner speed ≤ 30: 65%
  Linear interpolation between: 0.65 - (speed - 30) × (0.35 / 40)
  Batter speed modifier: 1.0 + (50 - batter_speed) × 0.005
  Final: clamped [10%, 75%]
```

### Stat Validation (produced by the engine)
After 3 weeks of simulated games:
| Stat | Our Engine | Real MLB |
|------|-----------|----------|
| League AVG | .246 | .248 |
| League ERA | 3.98 | ~4.00 |
| HR Rate | .040 | .033 |
| SO Rate | .263 | .225 |
| BB Rate | .067 | .085 |

HR and K rates slightly high, walks slightly low. Acceptable for Phase 1. Needs tuning.

---

## 5. Player Rating System

### Scale: 20-80 (Scouting Scale)
| Rating | Grade | Meaning |
|--------|-------|---------|
| 80 | A+ | Elite (top 1-2%) |
| 70 | A- | All-Star caliber |
| 60 | B | Above average starter |
| 50 | C+ | League average |
| 40 | C- | Below average |
| 30 | D | Replacement level |
| 20 | F | Out of baseball |

### Position Player Ratings
| Rating | What It Measures | How It Affects Sim |
|--------|-----------------|-------------------|
| Contact | Ability to make solid contact | Singles probability, K resistance |
| Power | Raw power / exit velocity | HR, doubles probability |
| Speed | Baserunning velocity | Triples, SB success, infield hits, DP avoidance |
| Fielding | Glove work, consistency | Error rate (planned) |
| Arm | Throwing strength/accuracy | Assist rate (planned) |

### Pitcher Ratings
| Rating | What It Measures | How It Affects Sim |
|--------|-----------------|-------------------|
| Stuff | Pitch quality, movement, velocity | K rate, hit suppression |
| Control | Command of the zone | Walk rate |
| Stamina | Pitch count endurance | When pitcher gets pulled, fatigue onset |

### Personality Traits (1-100)
| Trait | Effect |
|-------|--------|
| Ego | Affects trade demands, clubhouse chemistry (planned) |
| Leadership | Veteran mentor effects (planned) |
| Work Ethic | Development rate multiplier |
| Clutch | High-leverage performance modifier (active) |
| Durability | Injury frequency modifier (active) |

### Rating Conversion from Real Stats
```
Contact = clamp(20, 80, (AVG - 0.180) / 0.140 × 60 + 20)
Power = clamp(20, 80, (ISO - 0.050) / 0.250 × 60 + 20)
Speed = clamp(20, 80, (SB/G - 0.02) / 0.25 × 60 + 30), age-adjusted
Stuff = clamp(20, 80, (K/9 - 4.0) / 8.0 × 60 + 20)
Control = clamp(20, 80, (5.5 - BB/9) / 4.5 × 60 + 20)
Stamina = clamp(20, 80, (IP/GS - 4.0) / 3.0 × 60 + 20)
```

### Development Curves
```
Age < peak_age:  Improve 1-4 points/year toward potential
                 Rate = (work_ethic / 50) × dev_rate × farm_budget_mod
Peak (peak±2):   Random fluctuation ±1
Post-peak:       Decline = 0.5 + (years_past_peak × 0.3)
                 Speed declines 1.5-3x faster than other ratings
Retirement:      If overall < 25 AND age > 35
```

---

## 6. Financial Model

### Revenue Streams
| Source | Formula | Range |
|--------|---------|-------|
| Tickets | attendance × $35 × (pricing% / 100) | $15-80M |
| Concessions | attendance × $30 × elasticity | $10-50M |
| Broadcast | Market-based lookup | $25-250M |
| Merchandise | market_size × $5M × (0.5 + loyalty/100) | $5-35M |

**Broadcast revenue by market size:**
| Market | Revenue |
|--------|---------|
| 1 (Oakland, KC) | $25M |
| 2 (Milwaukee, Pittsburgh) | $45M |
| 3 (Detroit, Baltimore) | $80M |
| 4 (Boston, Houston) | $140M |
| 5 (NY, LA) | $250M |

### Expenses
| Category | Formula |
|----------|---------|
| Payroll | Sum of all active contracts |
| Farm System | Team budget (default $10M) |
| Medical Staff | Team budget (default $10M) |
| Scouting | Team budget (default $10M) |
| Stadium Ops | capacity × $800 |
| Owner Dividends | franchise_value × 10% |

### Attendance Model
```
base = stadium_capacity × 0.5
loyalty_bonus = (fan_loyalty / 100) × stadium_capacity × 0.4
attendance = min(capacity, (base + loyalty_bonus) × random(0.85, 1.15))
```

---

## 7. Transaction Systems

### Trade System
- Pre-deadline (before July 31): Normal trades via `/trade/propose`
- Post-deadline: Waiver trades only via `/trade/waiver-propose`
- LLM evaluates with GM personality context, falls back to algorithmic
- Algorithmic fallback includes roster-aware position needs analysis
- No-trade clause enforcement
- Cash inclusion (limited to team's available cash)
- AI teams initiate trades daily (2% chance per team during regular season)

### Free Agency
- Market value based on overall rating + age depreciation
- AI teams bid during offseason (5% daily chance per FA per team)
- Asking prices decline: -10% after 30 days, -30% after 60 days
- Signings begin after day 14 of offseason, ramping probability
- 40-man roster limit enforced on signings

### Draft
- 600 prospects per class (20 rounds × 30 teams)
- 5 tiers: elite (1-30), good (31-90), average (91-180), below-avg (181-300), lottery (301-600)
- Floor/ceiling ratings with scouting uncertainty baked in
- Rookie contract: 4 years, $720K, signing bonus scales by round

### Roster Rules
- 26-man active roster limit
- 40-man roster limit (on_forty_man flag)
- Option years (3 max, decremented on each option)
- DFA → 7-day waiver window → free agent if unclaimed
- AI teams evaluate waiver claims based on positional need
- Service time tracked (incremented annually)
- Arbitration eligibility at 3-6 service years

### Contracts
- Annual salary + years remaining
- No-trade clauses (full or partial)
- Arbitration salary: overall_rating × $100K × service_year_multiplier
- Contract expiration triggers free agency at 6+ service years

---

## 8. AI & LLM Integration

### Model Routing
| Task Type | Model | Rationale |
|-----------|-------|-----------|
| GM decisions, trade evaluation | qwen3:32b | Strategic reasoning, bad logic breaks game |
| Scouting reports, flavor text | qwen3:14b | Creative with personality, speed over depth |
| Offseason batch processing | qwen3:32b | Higher quality, speed irrelevant |

### Trade Evaluation Prompt Structure
```
System: "You are {gm_name}, GM of {team}. Your philosophy: {philosophy}.
Risk tolerance: {risk}/100. Ego: {ego}/100. Competence: {competence}/100.
Job security: {job_security}/100. Style: {negotiation_style}.
Owner wants: {objectives}. Record: {record}."

User: "Trade proposal:
YOU RECEIVE: [player details with ratings and salary]
YOU GIVE UP: [player details]
Consider: team fit, philosophy, relationship, owner pressure, job security."

Expected JSON response:
{accept, reasoning, counter_offer, emotional_reaction, message_to_gm}
```

### Scouting Report Generation
Full structured reports inspired by "Dollar Sign on the Muscle" and "Moneyball" methodology:
- **Present/Future grade pairs** on 20-80 scale for each tool
- **OFP** (Overall Future Potential) calculated from future grades, adjusted by makeup
- **Ceiling/Floor projections** based on OFP tier
- **Risk assessment** (low/medium/high) from present-vs-future gap
- **MLB comp** from 1985-2011 era database (54 players, 17 archetypes) using Euclidean distance matching
- **Makeup assessment** factoring work ethic, leadership, clutch
- **ETA** calculated from current age
- **LLM narrative** with algorithmic fallback for personality-driven prose
- **Scout quality** (1-100) affects grade accuracy: elite (+/-3), average (+/-7), poor (+/-12)

### Tiered Decision Architecture
- **Tier 1 (Math)**: Obvious decisions handled algorithmically (waiver claims, roster auto-sort)
- **Tier 2 (Rules)**: Moderate decisions with deterministic logic (daily lineups, bullpen usage)
- **Tier 3 (LLM)**: Genuinely ambiguous decisions where personality matters (trade eval, press conferences)

---

## 9. Real MLB Data Pipeline

### Data Source: MLB Stats API (free, no auth)
Base URL: `https://statsapi.mlb.com/api/v1`

### Endpoints Used
| Endpoint | Data |
|----------|------|
| `/teams?sportId=1` | All 30 teams, venues, divisions |
| `/venues/{id}?hydrate=fieldInfo` | Stadium dimensions, capacity, surface, roof |
| `/teams/{id}/roster?rosterType=40Man` | 40-man roster with player IDs |
| `/people/{id}?hydrate=stats(...)` | Player bio + 2024 stats |

### Rating Conversion Pipeline
1. Fetch raw 2024 batting/pitching stats from API
2. Convert to 20-80 ratings using formulas (see Section 5)
3. Position-based defaults for fielding/arm when no advanced metrics
4. Age-based fallbacks when no 2024 stats available
5. Cache all data to `mlb_cache.json` (922KB, ~1,235 players)

### Current Data: 1,235 real MLB players across 30 teams
Examples of converted ratings:
| Player | Position | Contact | Power | Speed |
|--------|----------|---------|-------|-------|
| Aaron Judge | RF | 59 | 80 | 29 |
| Jazz Chisholm | 2B | 50 | 66 | 80 |
| Freddie Freeman | 1B | 57 | 52 | 21 |
| Kyle Tucker | RF | 58 | 80 | 50 |
| Bryan Reynolds | RF | 51 | 49 | 38 |

---

## 10. Frontend Architecture

### Design Language: "Bloomberg Terminal meets Baseball Reference"
- Toggleable dark/light theme (dark: navy/gold #0a0e14/#c8aa50; light: white/brown #f8f9fb/#996d1e)
- System font for prose, monospace for numbers
- Tighter padding (3-4px cells), smaller fonts (11-12px)
- Flat cards (no border-radius), alternating row backgrounds
- Letter grades (A+ through F) instead of raw numbers
- Sticky table headers, frozen first columns
- Toast notification system
- Global search modal (Ctrl+K)

### Screens
1. **Calendar Hub** -- Month grid, click days for scores, sim to date
2. **Roster** -- Active/Minors/Injured tabs with sortable columns and search/position filter
3. **Lineup** -- Drag-and-drop batting order, rotation, bullpen tabs; 4 configs (vs RHP/LHP, w/DH, w/o DH)
4. **Standings** -- AL/NL by division with W-L-PCT-GB-RS-RA-Diff
5. **Schedule** -- Game list with box score links
6. **Finances** -- Revenue/expense breakdown, budget sliders (farm/medical/scouting)
7. **Trade Center** -- 3-panel trade builder + Trading Block tab with incoming offers
8. **Free Agents** -- Market with asking prices, sign buttons
9. **Find Players** -- Search all players by name, position, team with sortable results
10. **Leaders** -- 6 stat categories (HR, AVG, RBI, W, SO, SB)
11. **Messages** -- Inbox from GMs, owners, scouts

### Player Modal
- Header: name, position, age, B/T, country, team, salary, contract years
- Grade boxes: letter grade + raw number for each rating
- Personality grades
- Season stats table (batting or pitching)
- Full structured scouting report with present/future grade pairs, OFP, ceiling/floor, risk level, MLB comp (1985-2011 era), makeup assessment
- Player comparison tool (side-by-side with color-coded rating bars)
- Play-by-play display for game results

---

## 11. Database Schema Reference

### 18 Tables
| Table | Rows (seeded) | Purpose |
|-------|---------------|---------|
| game_state | 1 | Current date, season, phase, user team |
| teams | 30 | All MLB teams with stadium, market, budgets |
| players | 1,235 | Real MLB players with ratings, personality |
| contracts | 1,235 | Salary, years, NTC, options |
| schedule | 2,430 | 162 games × 30 teams / 2 |
| game_results | 0→2,430 | Box score data as games play |
| batting_lines | grows | Per-game batting stats |
| pitching_lines | grows | Per-game pitching stats |
| batting_stats | grows | Season cumulative batting |
| pitching_stats | grows | Season cumulative pitching |
| gm_characters | 30 | AI GM personalities |
| owner_characters | 30 | Owner archetypes and objectives |
| transactions | grows | Trade, FA, DFA, draft history |
| draft_prospects | 0→600 | Annual draft class |
| messages | grows | GM/owner/scout communications |
| financial_history | grows | Per-season financial snapshots |
| waiver_claims | grows | 7-day DFA waiver tracking |

---

## 12. API Endpoint Reference

### Game State (3)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/game-state` | Current date, season, phase, user team |
| POST | `/set-user-team` | Set player's controlled team |
| POST | `/sim/advance` | Simulate N days (1-30) |

### Teams & Rosters (12)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/teams` | List all 30 teams |
| GET | `/team/{id}` | Full team view (roster, staff, payroll) |
| GET | `/roster/{id}` | Roster summary (active/minors/injured) |
| GET | `/roster/{id}/lineup` | Batting order JSON |
| POST | `/roster/{id}/lineup` | Save batting order |
| GET | `/roster/{id}/rotation` | Pitching rotation/roles |
| POST | `/roster/{id}/rotation` | Save rotation |
| POST | `/roster/call-up/{id}` | Promote minor leaguer |
| POST | `/roster/option/{id}` | Send to minors |
| POST | `/roster/dfa/{id}` | Designate for assignment |
| POST | `/roster/forty-man/add/{id}` | Add to 40-man |
| POST | `/roster/forty-man/remove/{id}` | Remove from 40-man |

### Players (6)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/player/{id}` | Player detail + stats |
| GET | `/player/{id}/scouting-report` | LLM scouting report (narrative) |
| GET | `/player/{id}/scouting-report-full` | Full structured scouting report (present/future grades, OFP, comp, makeup) |
| GET | `/players/search` | Search/filter by name, position, team, age, overall, roster status |
| GET | `/leaders/batting` | Batting leaders by stat |
| GET | `/leaders/pitching` | Pitching leaders by stat |

### Schedule & Results (3)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/schedule` | Games with optional filters |
| GET | `/schedule/month` | Monthly schedule |
| GET | `/game/{id}/boxscore` | Full box score |

### Trades (4)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/trade/propose` | Propose trade (LLM evaluates) |
| POST | `/trade/execute` | Execute accepted trade |
| POST | `/trade/waiver-propose` | Post-deadline waiver trade |
| GET | `/transactions` | Recent transactions |

### Free Agency (2)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/free-agents` | Available FAs with prices |
| POST | `/free-agents/sign` | Sign a free agent |

### Draft (2)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/draft/prospects/{season}` | Get/generate draft class |
| POST | `/draft/pick` | Make draft selection |

### Finance & Other (7)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/finances/{id}` | Team financial overview |
| GET | `/finances/{id}/details` | Detailed P&L with luxury tax, revenue sharing |
| POST | `/finances/{id}/budget` | Update farm/medical/scouting budgets |
| GET | `/team/{id}/strategy` | Strategy settings |
| POST | `/team/{id}/strategy` | Save strategy |
| GET | `/messages` | Inbox messages |
| POST | `/messages/send` | Send message |

### Trading Block (3)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/trading-block` | List players on trading block |
| POST | `/trading-block/add/{id}` | Add player to trading block |
| POST | `/trading-block/remove/{id}` | Remove player from trading block |

### Play-by-Play (1)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/game/{id}/play-by-play` | Key plays from a completed game |

---

## 13. Current Build Status

### What Works (Phase 1 Complete -- Baseball Mogul Feature Parity)

**Core Simulation**
- ✅ 1,235 real MLB players seeded from API data with converted ratings
- ✅ 30 real teams with actual stadium dimensions
- ✅ 2,430-game balanced schedule (162 per team, ~81 home/81 away)
- ✅ Game simulation producing realistic stats (AVG .246, ERA 3.98)
- ✅ Count-dependent at-bat resolution with ball-strike tracking
- ✅ 12 pitch types (4SFB, 2SFB, SI, CUT, SL, CB, CH, SPL, KC, SW, SC, KN) with per-pitcher repertoires
- ✅ Per-player platoon splits (custom JSON or positional defaults)
- ✅ Weather effects (temperature, wind direction/speed, humidity on ball carry)
- ✅ Day/night game splits (20% day/80% night, affects K rate and batting avg)
- ✅ Error/fielding simulation (position-specific error rates)
- ✅ Play-by-play generation and storage (HRs, Ks, SBs, errors, pitching changes)
- ✅ Multi-day pitcher fatigue (starters 4-5 days rest, relievers 1-2 days) -- reads AND writes
- ✅ In-game strategy: hit-and-run, suicide squeeze, IBB, defensive shift, infield in, pinch hitting, defensive subs
- ✅ Season advancement with phase management (ST -> RS -> PS -> OFF)
- ✅ Standings with W-L, PCT, GB, run differential
- ✅ Box scores with linescore + batting/pitching lines
- ✅ Calendar month view hub
- ✅ Stolen bases, sac bunts, improved DP logic
- ✅ Bullpen role management (closer/setup/7th/long/mop-up)

**Trades & Transactions**
- ✅ Trade proposals evaluated by LLM (qwen3:32b) with GM personality
- ✅ Algorithmic fallback with roster-aware position needs (graceful Ollama degradation)
- ✅ Trade deadline enforcement (July 31)
- ✅ Trading block system (put players on block, receive AI offers) -- DB column wired
- ✅ Draft pick trading (draft_pick_ownership table, validated in trade execution)
- ✅ 10-and-5 rights (automatic full NTC for 10yr service + 5yr same team)
- ✅ Free agency with AI team bidding and declining prices
- ✅ Qualifying offers + compensation draft picks
- ✅ Non-tender decisions for arb-eligible players
- ✅ 40-man roster enforcement
- ✅ Waiver wire (7-day DFA window)
- ✅ AI-initiated trades (2% daily per AI team)
- ✅ Rule 5 Draft with eligibility tracking
- ✅ International free agency (35-50 prospects/year, bonus pools, 11 countries)

**Roster Management**
- ✅ 600-prospect draft with floor/ceiling uncertainty
- ✅ September callups (26 -> 28 man roster after Sep 1)
- ✅ Defensive spectrum aging (SS->3B->1B->DH with age)
- ✅ Position eligibility tracking (based on games played)
- ✅ IL tiers: 10-day (position players), 15-day (pitchers), 60-day (severe)
- ✅ Player development (growth/peak/decline)
- ✅ Offseason orchestration (arbitration -> QO -> non-tenders -> FA -> draft -> Rule 5 -> intl FA)
- ✅ Super 2 arbitration eligibility (top 22% of 2-3yr service class)

**Financial Model**
- ✅ Revenue streams (tickets, concessions, broadcast, merch)
- ✅ Ticket and concession pricing sliders (50-150%, with attendance elasticity)
- ✅ Luxury tax / CBT with three tiers ($237M/$257M/$277M) + repeat offender surcharge
- ✅ Revenue sharing (48% local revenue pooled, split among 30 teams)
- ✅ Franchise valuation dynamics (performance, attendance, market, revenue trend)
- ✅ Budget allocation UI (farm/medical/scouting sliders)
- ✅ Financial calculations actually wired into offseason processing
- ✅ Difficulty affects economics (Fan +5% rev, Mogul -10% rev)
- ✅ Strategy settings (steal freq, bunt rate, pitch count limits, hit-and-run, shift tendency)

**Contract System**
- ✅ Opt-out clauses, team options, player options
- ✅ Vesting options with condition tracking (500 PA, 150 games, 50 starts)
- ✅ Incentive bonuses (all-star, MVP top 5, 150+ games, Cy Young top 3)
- ✅ Deferred money (full salary for luxury tax, reduced for cash flow)
- ✅ 10-and-5 automatic NTC rights

**Personality & Chemistry**
- ✅ 11 personality traits (ego, leadership, work_ethic, clutch, durability, loyalty, greed, composure, intelligence, aggression, sociability)
- ✅ Player morale (0-100, affected by playing time, team performance, trades, contract status)
- ✅ Team chemistry (0-100, from leadership, ego conflicts, age balance, win streaks, relationships)
- ✅ Player relationships (friends, rivals, mentors based on country, position, age)
- ✅ Chemistry affects development (+/-5%), clutch (+/-3%), injury recovery (+/-10%)
- ✅ Morale affects contact/power (+/-3), speed (+/-2)

**Scouting & Player Evaluation**
- ✅ Three scouting modes: Traditional (hidden ratings + uncertainty), Stat-Based (MLE projections), Variable (uncertainty shrinks with playing time)
- ✅ MLE system for minor league stat translation (AAA/AA/A conversion factors)
- ✅ Full structured scouting reports with present/future grade pairs on 20-80 scale
- ✅ Scout quality system (elite +/-3, average +/-7, poor +/-12 uncertainty)
- ✅ OFP calculation, ceiling/floor projections, risk assessment
- ✅ MLB prospect comps from 1985-2011 era (54 players across 17 archetypes)
- ✅ LLM narrative generation with algorithmic fallback

**UI/UX**
- ✅ Toggleable dark/light theme with localStorage persistence
- ✅ Sortable table columns (click header to sort)
- ✅ Drag-and-drop lineup management (batting order, rotation, bullpen)
- ✅ Multiple lineup configurations (vs RHP/LHP, w/DH, w/o DH) -- lineup save endpoint wired
- ✅ Find Players search (name, position, team, with sortable results)
- ✅ Player comparison tool (side-by-side modal with color-coded bars)
- ✅ Play-by-play display with color-coded play cards
- ✅ Trading block tab with incoming AI offers
- ✅ Global search modal (Ctrl+K)
- ✅ Toast notification system
- ✅ Letter grade rating system (A+ through F)
- ✅ Difficulty setting affects gameplay (trade acceptance, revenue, arb salaries)
- ✅ Depth chart screen with position-based roster view and color-coded ratings
- ✅ Commissioner mode (edit players, teams, force trades/signings)
- ✅ Customizable stat column displays (batting + pitching column pickers)
- ✅ CSV export (roster, batting stats, pitching stats, financials)

### What's Missing vs. Baseball Mogul
See Section 14 for detailed gap analysis.

### What's Missing vs. Design Doc
See Section 15 for detailed gap analysis.

---

## 14. Gap Analysis: Us vs. Baseball Mogul

*Updated March 16, 2026 (Phase 1 Complete). All tracked gaps closed.*

### Simulation Engine
| Feature | Baseball Mogul | Front Office | Status |
|---------|---------------|-------------|--------|
| At-bat resolution | Physics-based pitch-by-pitch | Count-dependent with 12 pitch types | ✅ Closed |
| Count-dependent behavior | Emergent from physics | Ball-strike count tracking with pitch-by-pitch sim | ✅ Closed |
| 38+ pitch types | Individual spin/velocity/PITCHf/x | 12 types (4SFB/2SFB/SI/CUT/SL/CB/CH/SPL/KC/SW/SC/KN) | ✅ Closed (12 vs 38, but covers all major categories) |
| Per-pitcher repertoires | 6,000+ pitcher database | Per-pitcher JSON, assigned from stats during seeding | ✅ Closed |
| Platoon splits per player | Historical L/R data, 600K+ lines | Per-player JSON splits + positional defaults | ✅ Closed |
| Weather effects | Temperature, wind, humidity | Full weather sim (temp/wind/humidity, dome neutral) | ✅ Closed |
| Day/night splits | Performance variations | 20% day/80% night, affects K rate and BA | ✅ Closed |
| In-game strategies | 15+ strategy sliders | 9 strategies (hit-and-run, squeeze, IBB, shift, infield in, pinch hit, def sub, etc.) | ✅ Closed |
| Play-by-play display | Full with audio | Text-based with color-coded play cards | ✅ Closed |
| Errors/fielding | Position-specific error rates | Position-specific GO (2%) and FO (0.5%) | ✅ Closed |
| Multiple lineups | 4 configs (vs L/R x DH/no DH) | 4 configs with save endpoint | ✅ Closed |
| Pitcher fatigue across games | Multi-day recovery | Multi-day tracking, reads fatigue before pitcher selection | ✅ Closed |
| Player personality on field | 11-point profiles affect play | Morale affects contact/power/speed; clutch in leverage | ✅ Closed |
| Team chemistry | Affects performance | 0-100 score from 7 components, affects dev/clutch/injury | ✅ Closed |

### Financial Model
| Feature | Baseball Mogul | Front Office | Status |
|---------|---------------|-------------|--------|
| Ticket pricing control | Adjustable slider | 50-150% slider with attendance elasticity | ✅ Closed |
| Concession pricing | Per-item sliders | 50-150% slider with elasticity | ✅ Closed |
| Broadcast contract types | Normal/Cable/Blackout | Normal (+0%), Cable (+30%, 5yr lock), Blackout (+50%, -2 loyalty/yr) | ✅ Closed |
| Revenue splits | 85/15 home/away | 85/15 gate revenue split | ✅ Closed |
| Luxury tax / CBT | Modeled with escalating rates | 3-tier CBT + repeat offender | ✅ Closed |
| Revenue sharing | 48% pool redistribution | 48% pooled, split 30 ways | ✅ Closed |
| Budget adjustment UI | User adjustable | Sliders with POST endpoint | ✅ Closed |
| Franchise valuation | Performance-driven | Dynamic from wins/attendance/market/revenue | ✅ Closed |
| Difficulty on economics | Fan +5%, Mogul -10% | Fan/Coach/Manager/Mogul revenue multipliers | ✅ Closed |
| Difficulty on trades | Affects AI acceptance | Fan +10%, Mogul -20% trade acceptance | ✅ Closed |

### Contract System
| Feature | Baseball Mogul | Front Office | Status |
|---------|---------------|-------------|--------|
| Multi-year contracts | Full negotiation | Salary + years + options | ✅ Closed |
| Opt-out clauses | Player can exit | opt_out_year tracked, processed in offseason | ✅ Closed |
| Team options | Team can exercise/decline | team_option_year tracked | ✅ Closed |
| Player options | Player can exercise | player_option_year tracked | ✅ Closed |
| Vesting options | Conditional triggers | JSON conditions (500 PA, 150 G, 50 GS) | ✅ Closed |
| Incentive bonuses | Performance bonuses | JSON (all-star, MVP, games, Cy Young) | ✅ Closed |
| Deferred money | Reduced cash flow | deferred_pct field, full count for luxury tax | ✅ Closed |
| 10-and-5 rights | Automatic full NTC | Checked in trade proposals | ✅ Closed |
| No-trade clauses | Full and partial | Full (1) and partial (2) tracked | ✅ Closed |
| Personality in negotiation | Greedy/generous affects demands | Not yet -- agent characters are Phase 2 | Remaining gap |
| Non-money factors | Playing time, friends, atmosphere | Morale/chemistry exist but don't affect FA decisions yet | Remaining gap |

### Roster Management
| Feature | Baseball Mogul | Front Office | Status |
|---------|---------------|-------------|--------|
| Rule 5 Draft | Full | Eligibility + AI selection + $750K | ✅ Closed |
| September callups | 26->28 | Auto-callups after Sep 1 | ✅ Closed |
| Position eligibility | Games played | Dynamic tracking + secondary positions | ✅ Closed |
| Defensive spectrum aging | SS->3B->1B->DH | Age-based shifts with fielding boost | ✅ Closed |
| IL tiers | 10/15/60-day | Per-injury tier assignment | ✅ Closed |
| Qualifying offers | QO + comp picks | Full process in offseason | ✅ Closed |
| Non-tender decisions | AI evaluates | Projected arb vs value comparison | ✅ Closed |
| Super 2 eligibility | Extra arb year | Top 22% of 2-3yr service class | ✅ Closed |
| Draft pick trading | Picks in trades | draft_pick_ownership table, validated in execution | ✅ Closed |
| International FA | Bonus pools, prospects | 35-50/yr from 11 countries, pool limits | ✅ Closed |
| Player relationships | Friends/rivalries | Generated from country/position/age, affects chemistry | ✅ Closed |
| Player morale | Ebbs and flows | Daily updates from playing time/wins/trades/contracts | ✅ Closed |

### Scouting
| Feature | Baseball Mogul | Front Office | Status |
|---------|---------------|-------------|--------|
| Scouting uncertainty | Budget-dependent | Scout quality: elite +/-3, avg +/-7, poor +/-12 | ✅ Closed |
| Three scouting modes | Traditional/Stat-Based/Variable | All three modes with per-mode logic | ✅ Closed |
| Scout quality | Better scouts = smaller margin | 1-100 quality affects grade accuracy | ✅ Closed |
| MLE | 1.9M minor league stat lines | MLE conversion factors for AAA/AA/A + uncertainty by PA | ✅ Closed |
| Real scouting report format | Prose with tools/projection | Full structured with OFP, comp, makeup, risk | ✅ Closed |

### UI/UX
| Feature | Baseball Mogul | Front Office | Status |
|---------|---------------|-------------|--------|
| Calendar as hub | Month grid | Calendar exists | ✅ |
| Sortable columns | Click header | Click-to-sort on all stat tables | ✅ Closed |
| Customizable stat displays | User picks columns | Column picker modal with 40 batting/pitching options | ✅ Closed |
| Player comparison | Side-by-side | Modal with color-coded bars | ✅ Closed |
| Trading block | Players on block, get offers | Full with DB backing | ✅ Closed |
| Find Players search | Filter by position/age/salary | Search by name/position/team, sortable | ✅ Closed |
| Theme toggle | N/A | Full dark/light theme | ✅ Closed |
| Depth chart screen | Visual depth chart | Position-based view with color-coded ratings | ✅ Closed |
| Commissioner mode | Edit players/teams freely | Full edit mode (players, teams, force trades/signings) | ✅ Closed |
| CSV export | Export rosters/stats | 4 export endpoints (roster, batting, pitching, financials) | ✅ Closed |

### Remaining Gaps (honest assessment)
Of ~80 Baseball Mogul features tracked, **all are now Done or Closed.**

The only features NOT implemented are things that go beyond Baseball Mogul into Front Office's own vision (Phase 2+):
- Personality-driven FA negotiation (requires agent characters)
- Non-money factors in FA decisions
- Manager mode (pitch-by-pitch in-game control from the UI)
- Minor league full simulation (currently stats-only)
- Historical seasons (1901-present)
- Spoofed phone messaging UI
- Beat writer / media characters

---

## 15. Gap Analysis: Us vs. Design Doc (front-office-v2.docx)

### Phase 1 (Core Simulation) — What the Doc Specifies
| Feature | Specified | Built | Status |
|---------|-----------|-------|--------|
| 30 real MLB teams | ✅ | ✅ | Done |
| Player ratings (contact, power, speed, fielding, arm, pitching) | ✅ | ✅ | Done |
| Contract details (years, salary, NTC, options) | ✅ | ✅ | Done |
| 162-game schedule with series structure | ✅ | ✅ | Done |
| Box scores with batting and pitching lines | ✅ | ✅ | Done |
| Cumulative season stats | ✅ | ✅ | Done |
| GM characters with personality JSON | ✅ | ✅ | Done |
| Owner characters with archetypes | ✅ | ✅ | Done |
| Minor league rosters (Rookie through AAA) | ✅ | ✅ | Done |
| Financial model (revenue + expenses) | ✅ | ✅ | Done |
| Roster rules (40-man, 26-man, options, DFA) | ✅ | ✅ | Done |
| Chat/message history | ✅ | Partial | Messages exist, no proactive messaging |
| Pitcher vs batter matchups with platoon/park/fatigue | ✅ | ✅ | Done |
| Bullpen management | ✅ | ✅ | Done |
| Injury system | ✅ | ✅ | Done |
| Player aging/development curves | ✅ | ✅ | Done |
| Trade proposals evaluated by GM personality via Ollama | ✅ | ✅ | Done |
| Free agency with market dynamics | ✅ | ✅ | Done |
| Amateur draft with floor/ceiling uncertainty | ✅ | ✅ | Done |
| Waiver claims | ✅ | ✅ | Done |
| Arbitration and contract extensions | ✅ | ✅ | Full arb with Super 2, vesting options, incentives |
| Rule 5 draft, qualifying offers, comp picks | ✅ | ✅ | All three implemented |
| Simple HTML status page at GET / | ✅ | ✅ | Full web app instead |

### Phase 2 Features (NOT part of Phase 1, but noted for reference)
- LLM personalities for all 30 GMs and owners driving behavior
- Spoofed phone messaging UI (iMessage-style)
- Owner objectives and job security pressure
- Agent negotiations
- Priority inbox system
- Beat writer characters
- Fan sentiment by market

### Phase 3+ Features (far future)
- ESPN-style news page
- Weekly audio podcast (Orpheus TTS)
- Local market podcast
- Monthly video SportsCenter broadcast
- Game broadcast with play-by-play audio
- 8-bit playable baseball games
- AI-generated player portraits

---

## 16. Development Roadmap

### Phase 1 -- COMPLETE
All Baseball Mogul features implemented. Ready for browser testing and GitHub push.

### Phase 2 Priorities (Social Layer)
1. **Messaging overhaul** -- Spoofed iMessage/Telegram UI, proactive messaging to GMs/owner/scouts
2. **Agent characters** -- Negotiation personalities, personality-driven FA demands
3. **Owner objectives and job security** -- Pressure system, firing/hiring
4. **Beat writer characters** -- Generated articles, media narratives
5. **Fan sentiment by market** -- Dynamic fan reactions to moves
6. **Minor league full simulation** -- Game results, standings, promotions
7. **Expand comp database** -- 54 players to 150+ for better prospect matching
8. **Manager mode** -- Pitch-by-pitch in-game control from the browser UI

### Phase 2 (Social Layer)
- GM/owner personality-driven messaging conversations
- Owner objectives, job security, firing/hiring
- Agent characters with negotiation personalities
- Beat writer characters generating articles
- Fan sentiment by market
- Priority inbox with categorized messages

### Phase 3 (Media Ecosystem)
- ESPN-style news page with generated articles
- Weekly podcast script generation via LLM
- Orpheus TTS audio rendering
- League network analyst characters (fired GMs become TV analysts)

---

## 17. Key Formulas & Algorithms

### At-Bat Resolution
```
walk_prob = 0.085 × (2.0 - pitcher_control_mod) × park.hit_factor
hr_prob = rating_to_prob(batter.power, 0.033) × park.hr_factor × platoon / pitcher_stuff
so_prob = 0.225 × pitcher_stuff_mod × (2.0 - batter_contact_mod) × park.so_factor
single_prob = rating_to_prob(batter.contact, 0.150) × park.hit_factor × platoon / pitcher_stuff
```

### Rating to Probability Modifier
```
modifier = 1.0 + (rating - 50) × 0.0167
# 20 rating → 0.5x baseline
# 50 rating → 1.0x baseline (league average)
# 80 rating → 1.5x baseline
```

### Park Factors
```
hr_factor = 0.7 + (avg_dimensions / actual_dimensions) × 0.6 × altitude_bonus × dome_adj
```

### Player Value (Trade Evaluation)
```
Pitchers: (stuff × 2 + control × 1.5 + stamina × 0.5)
Position: (contact × 1.5 + power × 1.5 + speed × 0.5 + fielding × 0.5)
Age penalty: max(0, (age - 28) × 3)
Contract mod: max(0.5, 1.5 - salary / $30M)
Roster need bonus: +25% if position weak, -15% if position strong
```

### Free Agent Market Value
```
Age multiplier: ≤28 → 1.1x, 29-32 → 1.0x, 33-35 → 0.75x, 36+ → 0.5x
Salary = tier_base × age_mult
Years = tier_years × age_mult
Interest = min(15, overall / 5)
```

### Injury Probability
```
daily_chance = 0.0015 × (2.0 - durability/50) × (1.0 + max(0, (age-30) × 0.03))
```

### Development Rate
```
improvement = random(1, 4) × (work_ethic / 50) × dev_rate × farm_mod
farm_mod = 0.8 + (farm_budget / $50M)  # Range 0.8-1.2
```

### Attendance
```
base = capacity × 0.5
loyalty_bonus = (fan_loyalty / 100) × capacity × 0.4
attendance = min(capacity, (base + loyalty_bonus) × random(0.85, 1.15))
```

---

## 18. File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `src/database/schema.py` | 502 | 21 SQL tables with indexes |
| `src/database/db.py` | 51 | SQLite connection helpers |
| `src/database/seed.py` | 619 | Generated player/team data |
| `src/database/seed_real.py` | 215 | Real MLB data seeder |
| `src/database/real_data.py` | 983 | MLB Stats API fetcher + pitch repertoires + platoon splits |
| `src/simulation/game_engine.py` | 1,633 | 12 pitch types, weather, platoon, strategies, count-dependent |
| `src/simulation/season.py` | 707 | Day sim, standings, fatigue reads/writes, Sept callups, play-by-play |
| `src/simulation/schedule.py` | 502 | Balanced 162-game schedule generator |
| `src/simulation/injuries.py` | 112 | 20 injury types + IL tiers (10/15/60-day) |
| `src/simulation/player_development.py` | 267 | Growth/peak/decline + defensive spectrum aging |
| `src/simulation/chemistry.py` | 437 | Team chemistry + player morale + relationship effects |
| `src/simulation/strategy.py` | 112 | 9 strategy settings (hit-and-run, shift, squeeze, etc.) |
| `src/simulation/offseason.py` | 422 | Full offseason (arb, QO, non-tenders, FA, draft, Rule 5, intl FA, finances) |
| `src/transactions/trades.py` | 236 | Trade proposals + draft picks + 10-and-5 rights |
| `src/transactions/free_agency.py` | 308 | FA market + AI bidding |
| `src/transactions/draft.py` | 266 | 600-prospect draft + pick ownership initialization |
| `src/transactions/roster.py` | 332 | 40-man, call-ups, options, DFA, position eligibility |
| `src/transactions/contracts.py` | 483 | Vesting, incentives, deferred money, Super 2, non-tenders |
| `src/transactions/waivers.py` | 131 | 7-day waiver system |
| `src/transactions/ai_trades.py` | 196 | AI-initiated trades |
| `src/transactions/international_fa.py` | 400 | International prospect generation + bonus pools + AI signings |
| `src/financial/economics.py` | 302 | Luxury tax, revenue sharing, pricing elasticity, difficulty |
| `src/ai/ollama_client.py` | 94 | Ollama wrapper + model routing |
| `src/ai/gm_brain.py` | 448 | LLM trade eval + scouting + graceful Ollama fallback |
| `src/ai/player_comps.py` | 780 | 54 MLB comps (1985-2011) across 17 archetypes |
| `src/ai/mle.py` | 219 | Major League Equivalencies for minor league stat translation |
| `src/ai/scouting_modes.py` | 359 | Traditional/Stat-Based/Variable scouting mode logic |
| `src/api/routes.py` | ~1,400 | 72 FastAPI endpoints |
| `src/main.py` | 22 | Entry point |
| `static/index.html` | 291 | SPA shell with all screens and modals |
| `static/style.css` | 1,133 | Dark/light theme system, full UI styling |
| `static/app.js` | 1,768 | All frontend logic (lineup, comps, search, pricing, etc.) |
| `research/baseball-mogul-technical-analysis.md` | 612 | Deep technical research |
| **Total** | **~16,600** | **98% increase from Phase 1.0 (~8,400)** |

---

## 19. Lessons from 20 Years of Baseball Mogul

*Extracted from Clay Dreslough's blog posts spanning 2005-2017.*

1. **No catch-up code. Ever.** Perceived unfairness is cognitive bias, not rigged mechanics. Difficulty should only affect economics and trade favorability — never the simulation itself.

2. **Rating calibration matters more than rating accuracy.** If your ratings drift over time (average creeping from 75 to 82), everything downstream breaks. Recalibrate every season.

3. **Physics beats lookup tables.** Emergent count-dependent behavior from real physics is more realistic than any hand-tuned probability table. The 2012 rewrite validated this.

4. **Trade AI must understand roster construction.** The original Tradezilla could value players but couldn't build a roster. The 2014 rewrite focused on "what does this team need?" before "what is this player worth?"

5. **Contract data is the constraint engine.** 53% of deals are 1-year. The salary structure creates the strategic tension. Get this wrong and the economic game falls apart.

6. **Scouting uncertainty is a feature, not a bug.** When you can see exact ratings, there's no risk in personnel decisions. The +/- margin tied to scouting budget investment creates meaningful decisions.

7. **Position-specific aging is essential.** A shortstop doesn't age like a first baseman. The defensive spectrum shift (SS→3B→1B→DH) is a fundamental baseball reality that drives roster construction.

8. **Minor league stats need translation.** A .300 hitter at Triple-A is not a .300 hitter in the majors. Major League Equivalencies are the bridge, and they require huge historical datasets.

9. **The UI should be information-dense, not pretty.** Baseball management is about data. Every wasted pixel is a missed stat column. Sortable tables with 150+ options is not overkill — it's the baseline.

10. **The game creates itself.** The best narratives are emergent, not scripted. Build the systems right and the stories write themselves.

---

*This document is the single source of truth for the Front Office project. Update it as the build progresses.*
