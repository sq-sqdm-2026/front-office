"""
Front Office - Database Schema
All SQLite table definitions for the baseball universe simulation.
"""

SCHEMA_SQL = """
-- ============================================================
-- GAME STATE
-- ============================================================
CREATE TABLE IF NOT EXISTS game_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    current_date TEXT NOT NULL DEFAULT '2026-02-15',  -- Pre-Spring Training 2026
    season INTEGER NOT NULL DEFAULT 2026,
    phase TEXT NOT NULL DEFAULT 'spring_training',  -- spring_training, regular_season, postseason, offseason
    user_team_id INTEGER,
    difficulty TEXT NOT NULL DEFAULT 'manager',  -- fan, coach, manager, mogul
    scouting_mode TEXT NOT NULL DEFAULT 'traditional',  -- traditional, stat_based, variable
    current_hour INTEGER NOT NULL DEFAULT 8,  -- Game hour: 8 AM to 11 PM (8-23)
    commissioner_mode INTEGER NOT NULL DEFAULT 0,  -- 0=off, 1=on
    stat_display_config_json TEXT DEFAULT NULL,  -- JSON: {batting: [...], pitching: [...]}
    rating_scale TEXT NOT NULL DEFAULT '20-80',  -- 20-80, 50-100, 1-20, 1-100, letter
    auto_sim_enabled INTEGER NOT NULL DEFAULT 0,
    auto_sim_speed INTEGER NOT NULL DEFAULT 120000,  -- ms between advances
    auto_sim_last_tick TEXT DEFAULT NULL,  -- ISO timestamp of last tick
    FOREIGN KEY (user_team_id) REFERENCES teams(id)
);

-- ============================================================
-- TEAMS
-- ============================================================
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    city TEXT NOT NULL,
    name TEXT NOT NULL,
    abbreviation TEXT NOT NULL UNIQUE,
    league TEXT NOT NULL,  -- AL or NL
    division TEXT NOT NULL,  -- East, Central, West
    stadium_name TEXT NOT NULL,
    stadium_capacity INTEGER NOT NULL DEFAULT 40000,
    -- Stadium dimensions (feet from home plate)
    lf_distance INTEGER NOT NULL DEFAULT 330,
    lcf_distance INTEGER NOT NULL DEFAULT 370,
    cf_distance INTEGER NOT NULL DEFAULT 400,
    rcf_distance INTEGER NOT NULL DEFAULT 370,
    rf_distance INTEGER NOT NULL DEFAULT 330,
    -- Stadium properties
    is_dome INTEGER NOT NULL DEFAULT 0,
    surface TEXT NOT NULL DEFAULT 'grass',  -- grass, turf
    altitude INTEGER NOT NULL DEFAULT 0,
    foul_territory TEXT NOT NULL DEFAULT 'average',  -- small, average, large
    -- Market/financial
    market_size INTEGER NOT NULL DEFAULT 3,  -- 1-5 scale
    region_population INTEGER NOT NULL DEFAULT 3000000,
    per_capita_income INTEGER NOT NULL DEFAULT 55000,
    fan_base INTEGER NOT NULL DEFAULT 50,  -- 1-100, permanent enthusiasm
    fan_loyalty INTEGER NOT NULL DEFAULT 50,  -- 1-100, fluctuates with performance
    -- Budget
    cash INTEGER NOT NULL DEFAULT 50000000,
    franchise_value INTEGER NOT NULL DEFAULT 1500000000,
    ticket_price_pct INTEGER NOT NULL DEFAULT 100,  -- % of league average
    concession_price_pct INTEGER NOT NULL DEFAULT 100,
    farm_system_budget INTEGER NOT NULL DEFAULT 10000000,
    medical_staff_budget INTEGER NOT NULL DEFAULT 10000000,
    scouting_staff_budget INTEGER NOT NULL DEFAULT 10000000,
    team_strategy_json TEXT NOT NULL DEFAULT '{}',
    lineup_json TEXT DEFAULT NULL,
    rotation_json TEXT DEFAULT NULL,
    trading_block_json TEXT NOT NULL DEFAULT '{"players": [], "offers": []}',
    -- Broadcast contract
    broadcast_contract_type TEXT NOT NULL DEFAULT 'normal',  -- normal, cable, blackout
    broadcast_contract_years_remaining INTEGER NOT NULL DEFAULT 3,
    -- TV Broadcast rights deal (new system)
    broadcast_deal_type TEXT DEFAULT 'standard',  -- standard, premium_cable, streaming, blackout
    broadcast_deal_value INTEGER DEFAULT 0,  -- annual value in dollars
    broadcast_deal_years_remaining INTEGER DEFAULT 3,
    -- Stadium upgrades
    stadium_built_year INTEGER DEFAULT 2000,
    stadium_condition INTEGER DEFAULT 85,  -- 0-100 condition rating
    stadium_upgrades_json TEXT DEFAULT '{}',  -- JSON tracking purchased upgrades
    stadium_revenue_boost INTEGER DEFAULT 0  -- cumulative revenue from upgrades in dollars
);

-- ============================================================
-- PLAYERS
-- ============================================================
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    -- Bio
    age INTEGER NOT NULL,
    birth_country TEXT NOT NULL DEFAULT 'USA',
    bats TEXT NOT NULL DEFAULT 'R',  -- L, R, S (switch)
    throws TEXT NOT NULL DEFAULT 'R',  -- L, R
    position TEXT NOT NULL,  -- C, 1B, 2B, 3B, SS, LF, CF, RF, DH, SP, RP
    secondary_positions TEXT DEFAULT '',  -- comma-separated
    -- Ratings (20-80 scouting scale)
    contact_rating INTEGER NOT NULL DEFAULT 50,
    power_rating INTEGER NOT NULL DEFAULT 50,
    speed_rating INTEGER NOT NULL DEFAULT 50,
    fielding_rating INTEGER NOT NULL DEFAULT 50,
    arm_rating INTEGER NOT NULL DEFAULT 50,
    eye_rating INTEGER NOT NULL DEFAULT 50,  -- plate discipline: walks, chase rate
    -- Pitching ratings (only meaningful for pitchers)
    stuff_rating INTEGER NOT NULL DEFAULT 20,  -- pitch quality/movement
    control_rating INTEGER NOT NULL DEFAULT 20,  -- ability to throw strikes
    stamina_rating INTEGER NOT NULL DEFAULT 20,  -- endurance/pitch count
    -- Potential (ceiling rating, 20-80)
    contact_potential INTEGER NOT NULL DEFAULT 50,
    power_potential INTEGER NOT NULL DEFAULT 50,
    speed_potential INTEGER NOT NULL DEFAULT 50,
    fielding_potential INTEGER NOT NULL DEFAULT 50,
    arm_potential INTEGER NOT NULL DEFAULT 50,
    eye_potential INTEGER NOT NULL DEFAULT 50,
    stuff_potential INTEGER NOT NULL DEFAULT 20,
    control_potential INTEGER NOT NULL DEFAULT 20,
    stamina_potential INTEGER NOT NULL DEFAULT 20,
    -- Personality traits (1-100)
    ego INTEGER NOT NULL DEFAULT 50,
    leadership INTEGER NOT NULL DEFAULT 50,
    work_ethic INTEGER NOT NULL DEFAULT 50,
    clutch INTEGER NOT NULL DEFAULT 50,
    durability INTEGER NOT NULL DEFAULT 50,  -- injury resistance
    loyalty INTEGER NOT NULL DEFAULT 50,  -- attachment to current team
    greed INTEGER NOT NULL DEFAULT 50,  -- money vs winning priority
    composure INTEGER NOT NULL DEFAULT 50,  -- handles pressure/media
    intelligence INTEGER NOT NULL DEFAULT 50,  -- baseball IQ, learning speed
    aggression INTEGER NOT NULL DEFAULT 50,  -- plays hard, fights, intensity
    sociability INTEGER NOT NULL DEFAULT 50,  -- teammate bonds, clubhouse presence
    morale INTEGER NOT NULL DEFAULT 50,  -- current morale (0-100)
    -- Status
    roster_status TEXT NOT NULL DEFAULT 'active',  -- active, minors_aaa, minors_aa, minors_high_a, minors_low, minors_rookie, injured_dl, free_agent, retired
    is_injured INTEGER NOT NULL DEFAULT 0,
    injury_type TEXT DEFAULT NULL,
    injury_days_remaining INTEGER DEFAULT 0,
    il_tier TEXT DEFAULT NULL,  -- 10-day, 15-day, 60-day
    on_forty_man INTEGER NOT NULL DEFAULT 1,
    option_years_remaining INTEGER NOT NULL DEFAULT 3,
    service_years REAL NOT NULL DEFAULT 0.0,
    -- Development
    peak_age INTEGER NOT NULL DEFAULT 27,
    development_rate REAL NOT NULL DEFAULT 1.0,  -- multiplier for improvement speed
    is_bust INTEGER NOT NULL DEFAULT 0,  -- 1 if player busted during development
    is_late_bloomer INTEGER NOT NULL DEFAULT 0,  -- 1 if late bloomer triggered
    -- Platoon splits: JSON format {"vs_lhp": {"contact": +5, "power": +8}, "vs_rhp": {"contact": -3, "power": -5}}
    platoon_split_json TEXT DEFAULT NULL,
    -- Pitch repertoire for pitchers: JSON format [{"type": "4SFB", "rating": 65, "usage": 0.35}, ...]
    pitch_repertoire_json TEXT DEFAULT NULL,
    -- Physical attributes
    height_inches INTEGER DEFAULT NULL,  -- player height in inches for strike zone modeling
    -- Scouted ratings cache: JSON format {"season": 2026, "scouted": {"contact": 55, "power": 48, ...}, "mode": "traditional"}
    scouted_ratings_json TEXT DEFAULT NULL,
    -- External IDs (for real players imported from MLB API)
    mlb_id INTEGER DEFAULT NULL,  -- MLB Stats API player ID (for headshot photos)
    -- Player narrative / backstory fields
    backstory TEXT DEFAULT NULL,  -- 3-5 sentence generated backstory
    nickname TEXT DEFAULT NULL,  -- colorful player nickname
    quirks TEXT DEFAULT NULL,  -- JSON array of personality quirks
    origin_story TEXT DEFAULT NULL,  -- how they were discovered/drafted
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- CONTRACTS
-- ============================================================
CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    total_years INTEGER NOT NULL,
    years_remaining INTEGER NOT NULL,
    annual_salary INTEGER NOT NULL,  -- dollars
    signing_bonus INTEGER NOT NULL DEFAULT 0,
    no_trade_clause INTEGER NOT NULL DEFAULT 0,  -- 0=none, 1=full, 2=partial (10-team list)
    opt_out_year INTEGER DEFAULT NULL,  -- year player can opt out
    team_option_year INTEGER DEFAULT NULL,
    player_option_year INTEGER DEFAULT NULL,
    is_arb_eligible INTEGER NOT NULL DEFAULT 0,
    signed_date TEXT NOT NULL,
    -- Contract complexity features
    vesting_option_json TEXT DEFAULT NULL,  -- {"year": 2028, "condition": "500_pa", "salary": 15000000}
    incentives_json TEXT DEFAULT NULL,  -- [{"type": "all_star", "bonus": 500000}, ...]
    deferred_pct INTEGER NOT NULL DEFAULT 0,  -- % of salary deferred to future years
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- SEASON SCHEDULE
-- ============================================================
CREATE TABLE IF NOT EXISTS schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    game_date TEXT NOT NULL,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    game_number INTEGER NOT NULL DEFAULT 1,  -- for doubleheaders
    is_played INTEGER NOT NULL DEFAULT 0,
    home_score INTEGER,
    away_score INTEGER,
    is_postseason INTEGER NOT NULL DEFAULT 0,
    series_type TEXT,  -- WC, DS, CS, WS
    series_game_number INTEGER,
    FOREIGN KEY (home_team_id) REFERENCES teams(id),
    FOREIGN KEY (away_team_id) REFERENCES teams(id)
);

-- ============================================================
-- GAME RESULTS (box score data)
-- ============================================================
CREATE TABLE IF NOT EXISTS game_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    innings_json TEXT NOT NULL,  -- JSON: [[home_runs_per_inning], [away_runs_per_inning]]
    play_by_play_json TEXT,  -- JSON: key plays from the game
    weather_json TEXT DEFAULT NULL,  -- JSON: {temp, wind_direction, wind_speed, humidity, is_day_game}
    winning_pitcher_id INTEGER,
    losing_pitcher_id INTEGER,
    save_pitcher_id INTEGER,
    attendance INTEGER,
    game_duration_minutes INTEGER,
    FOREIGN KEY (schedule_id) REFERENCES schedule(id),
    FOREIGN KEY (winning_pitcher_id) REFERENCES players(id),
    FOREIGN KEY (losing_pitcher_id) REFERENCES players(id),
    FOREIGN KEY (save_pitcher_id) REFERENCES players(id)
);

-- ============================================================
-- BATTING LINES (per-game stats for each batter)
-- ============================================================
CREATE TABLE IF NOT EXISTS batting_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    batting_order INTEGER NOT NULL,
    position_played TEXT NOT NULL,
    ab INTEGER NOT NULL DEFAULT 0,
    runs INTEGER NOT NULL DEFAULT 0,
    hits INTEGER NOT NULL DEFAULT 0,
    doubles INTEGER NOT NULL DEFAULT 0,
    triples INTEGER NOT NULL DEFAULT 0,
    hr INTEGER NOT NULL DEFAULT 0,
    rbi INTEGER NOT NULL DEFAULT 0,
    bb INTEGER NOT NULL DEFAULT 0,
    so INTEGER NOT NULL DEFAULT 0,
    sb INTEGER NOT NULL DEFAULT 0,
    cs INTEGER NOT NULL DEFAULT 0,
    hbp INTEGER NOT NULL DEFAULT 0,
    sf INTEGER NOT NULL DEFAULT 0,
    -- Fielding stats
    putouts INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (schedule_id) REFERENCES schedule(id),
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- PITCHING LINES (per-game stats for each pitcher)
-- ============================================================
CREATE TABLE IF NOT EXISTS pitching_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    pitch_order INTEGER NOT NULL,  -- 1=starter, 2+=relievers in order
    ip_outs INTEGER NOT NULL DEFAULT 0,  -- outs recorded (3 per full inning)
    hits_allowed INTEGER NOT NULL DEFAULT 0,
    runs_allowed INTEGER NOT NULL DEFAULT 0,
    er INTEGER NOT NULL DEFAULT 0,
    bb INTEGER NOT NULL DEFAULT 0,
    so INTEGER NOT NULL DEFAULT 0,
    hr_allowed INTEGER NOT NULL DEFAULT 0,
    pitches INTEGER NOT NULL DEFAULT 0,
    is_starter INTEGER NOT NULL DEFAULT 0,
    decision TEXT,  -- W, L, S, H, BS, NULL
    FOREIGN KEY (schedule_id) REFERENCES schedule(id),
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- SEASON STATS (cumulative, updated after each game)
-- ============================================================
CREATE TABLE IF NOT EXISTS batting_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    level TEXT NOT NULL DEFAULT 'MLB',  -- MLB, AAA, AA, LOW
    games INTEGER NOT NULL DEFAULT 0,
    pa INTEGER NOT NULL DEFAULT 0,
    ab INTEGER NOT NULL DEFAULT 0,
    runs INTEGER NOT NULL DEFAULT 0,
    hits INTEGER NOT NULL DEFAULT 0,
    doubles INTEGER NOT NULL DEFAULT 0,
    triples INTEGER NOT NULL DEFAULT 0,
    hr INTEGER NOT NULL DEFAULT 0,
    rbi INTEGER NOT NULL DEFAULT 0,
    bb INTEGER NOT NULL DEFAULT 0,
    so INTEGER NOT NULL DEFAULT 0,
    sb INTEGER NOT NULL DEFAULT 0,
    cs INTEGER NOT NULL DEFAULT 0,
    hbp INTEGER NOT NULL DEFAULT 0,
    sf INTEGER NOT NULL DEFAULT 0,
    is_postseason INTEGER NOT NULL DEFAULT 0,  -- 0=regular season, 1=playoffs
    UNIQUE(player_id, team_id, season, level),
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS pitching_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    level TEXT NOT NULL DEFAULT 'MLB',
    games INTEGER NOT NULL DEFAULT 0,
    games_started INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    saves INTEGER NOT NULL DEFAULT 0,
    holds INTEGER NOT NULL DEFAULT 0,
    blown_saves INTEGER NOT NULL DEFAULT 0,
    ip_outs INTEGER NOT NULL DEFAULT 0,  -- total outs recorded
    hits_allowed INTEGER NOT NULL DEFAULT 0,
    runs_allowed INTEGER NOT NULL DEFAULT 0,
    er INTEGER NOT NULL DEFAULT 0,
    bb INTEGER NOT NULL DEFAULT 0,
    so INTEGER NOT NULL DEFAULT 0,
    hr_allowed INTEGER NOT NULL DEFAULT 0,
    pitches INTEGER NOT NULL DEFAULT 0,
    complete_games INTEGER NOT NULL DEFAULT 0,
    shutouts INTEGER NOT NULL DEFAULT 0,
    quality_starts INTEGER NOT NULL DEFAULT 0,
    is_postseason INTEGER NOT NULL DEFAULT 0,  -- 0=regular season, 1=playoffs
    UNIQUE(player_id, team_id, season, level),
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- GM CHARACTERS
-- ============================================================
CREATE TABLE IF NOT EXISTS gm_characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER NOT NULL DEFAULT 45,
    -- Philosophy & style
    philosophy TEXT NOT NULL DEFAULT 'balanced',  -- analytics, old_school, balanced, moneyball
    risk_tolerance INTEGER NOT NULL DEFAULT 50,  -- 1-100
    ego INTEGER NOT NULL DEFAULT 50,
    negotiation_style TEXT NOT NULL DEFAULT 'fair',  -- aggressive, fair, passive, desperate
    competence INTEGER NOT NULL DEFAULT 50,  -- 1-100
    patience INTEGER NOT NULL DEFAULT 50,  -- willingness to rebuild
    -- Emotional state
    job_security INTEGER NOT NULL DEFAULT 70,  -- 1-100, how safe they feel
    emotional_state TEXT NOT NULL DEFAULT 'neutral',  -- confident, nervous, desperate, angry, neutral
    -- Personality JSON (extended traits for LLM prompts)
    personality_json TEXT NOT NULL DEFAULT '{}',
    -- Memory
    memory_log TEXT NOT NULL DEFAULT '[]',  -- JSON array of significant events
    -- Relationships with other GMs: JSON {gm_id: score}
    relationships_json TEXT NOT NULL DEFAULT '{}',
    contract_years_remaining INTEGER NOT NULL DEFAULT 3,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- OWNER CHARACTERS
-- ============================================================
CREATE TABLE IF NOT EXISTS owner_characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL UNIQUE,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER NOT NULL DEFAULT 60,
    -- Archetype
    archetype TEXT NOT NULL DEFAULT 'balanced',
    -- win_now, budget_conscious, patient_builder, ego_meddler, legacy_inheritor, competitive_small_market
    budget_willingness INTEGER NOT NULL DEFAULT 50,  -- 1-100
    patience INTEGER NOT NULL DEFAULT 50,
    meddling INTEGER NOT NULL DEFAULT 30,  -- how much they interfere
    -- Objectives JSON: [{type, description, deadline, met}]
    objectives_json TEXT NOT NULL DEFAULT '[]',
    personality_json TEXT NOT NULL DEFAULT '{}',
    memory_log TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- TRANSACTIONS LOG
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_date TEXT NOT NULL,
    transaction_type TEXT NOT NULL,  -- trade, free_agent_signing, release, dfa, waiver_claim, draft_pick, call_up, option, extension
    -- For trades: JSON with full details
    details_json TEXT NOT NULL DEFAULT '{}',
    -- Teams involved
    team1_id INTEGER,
    team2_id INTEGER,
    -- Players involved (comma-separated IDs)
    player_ids TEXT DEFAULT '',
    FOREIGN KEY (team1_id) REFERENCES teams(id),
    FOREIGN KEY (team2_id) REFERENCES teams(id)
);

-- ============================================================
-- DRAFT PROSPECTS (generated each year)
-- ============================================================
CREATE TABLE IF NOT EXISTS draft_prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER NOT NULL DEFAULT 18,
    position TEXT NOT NULL,
    bats TEXT NOT NULL DEFAULT 'R',
    throws TEXT NOT NULL DEFAULT 'R',
    -- Scouting ratings (with uncertainty)
    contact_floor INTEGER NOT NULL DEFAULT 30,
    contact_ceiling INTEGER NOT NULL DEFAULT 60,
    power_floor INTEGER NOT NULL DEFAULT 30,
    power_ceiling INTEGER NOT NULL DEFAULT 60,
    speed_floor INTEGER NOT NULL DEFAULT 30,
    speed_ceiling INTEGER NOT NULL DEFAULT 60,
    fielding_floor INTEGER NOT NULL DEFAULT 30,
    fielding_ceiling INTEGER NOT NULL DEFAULT 60,
    arm_floor INTEGER NOT NULL DEFAULT 30,
    arm_ceiling INTEGER NOT NULL DEFAULT 60,
    stuff_floor INTEGER NOT NULL DEFAULT 20,
    stuff_ceiling INTEGER NOT NULL DEFAULT 20,
    control_floor INTEGER NOT NULL DEFAULT 20,
    control_ceiling INTEGER NOT NULL DEFAULT 20,
    -- Draft status
    overall_rank INTEGER,
    is_drafted INTEGER NOT NULL DEFAULT 0,
    drafted_by_team_id INTEGER,
    draft_round INTEGER,
    draft_pick INTEGER,
    scouting_report TEXT DEFAULT '',
    FOREIGN KEY (drafted_by_team_id) REFERENCES teams(id)
);

-- ============================================================
-- DRAFT PICK OWNERSHIP
-- ============================================================
CREATE TABLE IF NOT EXISTS draft_pick_ownership (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    round INTEGER NOT NULL,
    pick_number INTEGER NOT NULL,
    original_team_id INTEGER NOT NULL,
    current_owner_team_id INTEGER NOT NULL,
    traded_date TEXT,  -- when it was last traded, NULL if not traded
    UNIQUE(season, round, pick_number),
    FOREIGN KEY (original_team_id) REFERENCES teams(id),
    FOREIGN KEY (current_owner_team_id) REFERENCES teams(id)
);

-- ============================================================
-- INTERNATIONAL FREE AGENTS
-- ============================================================
CREATE TABLE IF NOT EXISTS international_prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    birth_country TEXT NOT NULL,
    position TEXT NOT NULL,
    bats TEXT NOT NULL DEFAULT 'R',
    throws TEXT NOT NULL DEFAULT 'R',
    contact_floor INTEGER NOT NULL DEFAULT 30,
    contact_ceiling INTEGER NOT NULL DEFAULT 60,
    power_floor INTEGER NOT NULL DEFAULT 30,
    power_ceiling INTEGER NOT NULL DEFAULT 60,
    speed_floor INTEGER NOT NULL DEFAULT 30,
    speed_ceiling INTEGER NOT NULL DEFAULT 60,
    fielding_floor INTEGER NOT NULL DEFAULT 30,
    fielding_ceiling INTEGER NOT NULL DEFAULT 60,
    arm_floor INTEGER NOT NULL DEFAULT 30,
    arm_ceiling INTEGER NOT NULL DEFAULT 60,
    scouting_report TEXT DEFAULT '',
    is_signed INTEGER NOT NULL DEFAULT 0,
    signed_by_team_id INTEGER,
    signing_bonus INTEGER,
    signed_date TEXT,
    FOREIGN KEY (signed_by_team_id) REFERENCES teams(id)
);

-- ============================================================
-- CHAT / MESSAGE HISTORY
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_date TEXT NOT NULL,
    sender_type TEXT NOT NULL,  -- gm, owner, agent, scout, reporter, system
    sender_id INTEGER,  -- FK to appropriate character table
    sender_name TEXT NOT NULL,
    recipient_type TEXT NOT NULL,  -- user, gm, owner
    recipient_id INTEGER,
    subject TEXT,
    body TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    requires_response INTEGER NOT NULL DEFAULT 0,
    response_options_json TEXT DEFAULT NULL,  -- JSON array of possible responses
    priority TEXT NOT NULL DEFAULT 'normal',  -- urgent, important, normal, low
    category TEXT NOT NULL DEFAULT 'general',  -- trade_offer, injury, transaction, etc.
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- FINANCIAL HISTORY (per-season snapshots)
-- ============================================================
CREATE TABLE IF NOT EXISTS financial_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    ticket_revenue INTEGER NOT NULL DEFAULT 0,
    concession_revenue INTEGER NOT NULL DEFAULT 0,
    broadcast_revenue INTEGER NOT NULL DEFAULT 0,
    merchandise_revenue INTEGER NOT NULL DEFAULT 0,
    total_revenue INTEGER NOT NULL DEFAULT 0,
    payroll INTEGER NOT NULL DEFAULT 0,
    farm_expenses INTEGER NOT NULL DEFAULT 0,
    medical_expenses INTEGER NOT NULL DEFAULT 0,
    scouting_expenses INTEGER NOT NULL DEFAULT 0,
    stadium_expenses INTEGER NOT NULL DEFAULT 0,
    owner_dividends INTEGER NOT NULL DEFAULT 0,
    total_expenses INTEGER NOT NULL DEFAULT 0,
    profit INTEGER NOT NULL DEFAULT 0,
    attendance_total INTEGER NOT NULL DEFAULT 0,
    attendance_avg INTEGER NOT NULL DEFAULT 0,
    UNIQUE(team_id, season),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- WAIVER CLAIMS
-- ============================================================
CREATE TABLE IF NOT EXISTS waiver_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    original_team_id INTEGER,
    dfa_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    claiming_team_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, claimed, cleared
    FOREIGN KEY (player_id) REFERENCES players(id)
);

-- ============================================================
-- PLAYER RELATIONSHIPS (Friends, Rivals, Mentors)
-- ============================================================
CREATE TABLE IF NOT EXISTS player_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id_1 INTEGER NOT NULL,
    player_id_2 INTEGER NOT NULL,
    relationship_type TEXT NOT NULL,  -- friend, rival, mentor
    strength INTEGER NOT NULL DEFAULT 50,  -- 1-100, intensity of relationship
    created_date TEXT NOT NULL,
    UNIQUE(player_id_1, player_id_2),
    FOREIGN KEY (player_id_1) REFERENCES players(id),
    FOREIGN KEY (player_id_2) REFERENCES players(id)
);

-- ============================================================
-- TEAM CHEMISTRY TRACKING
-- ============================================================
CREATE TABLE IF NOT EXISTS team_chemistry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL UNIQUE,
    chemistry_score INTEGER NOT NULL DEFAULT 50,  -- 0-100
    last_updated TEXT NOT NULL,
    recent_trade_count INTEGER NOT NULL DEFAULT 0,  -- within 30 days
    win_streak INTEGER NOT NULL DEFAULT 0,  -- positive for wins, negative for losses
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- PLAYOFF BRACKET
-- ============================================================
CREATE TABLE IF NOT EXISTS playoff_bracket (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    round TEXT NOT NULL,  -- 'wild_card', 'division_series', 'championship_series', 'world_series'
    series_id TEXT NOT NULL,  -- e.g. 'al_wc1', 'nl_ds2', 'al_cs', 'ws'
    higher_seed_id INTEGER REFERENCES teams(id),
    lower_seed_id INTEGER REFERENCES teams(id),
    higher_seed_wins INTEGER DEFAULT 0,
    lower_seed_wins INTEGER DEFAULT 0,
    winner_id INTEGER REFERENCES teams(id),
    is_complete INTEGER DEFAULT 0,
    home_field TEXT DEFAULT 'higher',  -- who has home field
    UNIQUE(season, series_id)
);

-- ============================================================
-- SEASON AWARDS
-- ============================================================
CREATE TABLE IF NOT EXISTS awards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    award_type TEXT NOT NULL,  -- 'mvp', 'cy_young', 'roy', 'gold_glove'
    league TEXT NOT NULL,  -- 'AL', 'NL'
    player_id INTEGER REFERENCES players(id),
    team_id INTEGER REFERENCES teams(id),
    position TEXT,  -- relevant for gold glove
    vote_points REAL,
    finish INTEGER,  -- 1st, 2nd, 3rd, etc.
    UNIQUE(season, award_type, league, player_id)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
CREATE INDEX IF NOT EXISTS idx_players_status ON players(roster_status);
CREATE INDEX IF NOT EXISTS idx_schedule_date ON schedule(game_date);
CREATE INDEX IF NOT EXISTS idx_schedule_season ON schedule(season);
CREATE INDEX IF NOT EXISTS idx_batting_lines_game ON batting_lines(schedule_id);
CREATE INDEX IF NOT EXISTS idx_pitching_lines_game ON pitching_lines(schedule_id);
CREATE INDEX IF NOT EXISTS idx_batting_stats_player ON batting_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_pitching_stats_player ON pitching_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_contracts_player ON contracts(player_id);
CREATE INDEX IF NOT EXISTS idx_contracts_team ON contracts(team_id);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(game_date);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_waiver_claims_status ON waiver_claims(status, expiry_date);
CREATE INDEX IF NOT EXISTS idx_draft_pick_ownership_season ON draft_pick_ownership(season);
CREATE INDEX IF NOT EXISTS idx_draft_pick_ownership_owner ON draft_pick_ownership(current_owner_team_id);
CREATE INDEX IF NOT EXISTS idx_international_prospects_season ON international_prospects(season);
CREATE INDEX IF NOT EXISTS idx_international_prospects_signed ON international_prospects(is_signed);
CREATE INDEX IF NOT EXISTS idx_player_relationships_player1 ON player_relationships(player_id_1);
CREATE INDEX IF NOT EXISTS idx_player_relationships_player2 ON player_relationships(player_id_2);
CREATE INDEX IF NOT EXISTS idx_team_chemistry_team ON team_chemistry(team_id);
CREATE INDEX IF NOT EXISTS idx_playoff_bracket_season ON playoff_bracket(season);
CREATE INDEX IF NOT EXISTS idx_playoff_bracket_round ON playoff_bracket(round);
CREATE INDEX IF NOT EXISTS idx_awards_season ON awards(season);
CREATE INDEX IF NOT EXISTS idx_awards_type_league ON awards(award_type, league);
CREATE INDEX IF NOT EXISTS idx_awards_player ON awards(player_id);

-- ============================================================
-- PODCAST EPISODES
-- ============================================================
CREATE TABLE IF NOT EXISTS podcast_episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_number INTEGER NOT NULL,
    game_date TEXT NOT NULL,  -- date of recording
    title TEXT NOT NULL,
    hosts TEXT NOT NULL,  -- JSON array of host names
    script TEXT NOT NULL,  -- full podcast script
    duration_estimate INTEGER NOT NULL DEFAULT 5,  -- estimated minutes
    season INTEGER NOT NULL,
    topics TEXT,  -- JSON array of topics covered
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_podcast_episodes_season ON podcast_episodes(season);
CREATE INDEX IF NOT EXISTS idx_podcast_episodes_date ON podcast_episodes(game_date);

-- ============================================================
-- TV ANALYST CHARACTERS
-- ============================================================
CREATE TABLE IF NOT EXISTS tv_analysts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    network TEXT NOT NULL,  -- ESPN, MLB Network, Fox Sports, TBS, local
    show_name TEXT,  -- "Baseball Tonight", "MLB Now", "Hot Stove", etc.
    analyst_type TEXT NOT NULL DEFAULT 'commentator',  -- commentator, insider, hot_take_artist, stat_guru, former_player, former_gm
    origin TEXT,  -- "Former GM of [Team]", "15-year MLB veteran", "Award-winning journalist"
    personality TEXT NOT NULL DEFAULT 'balanced',  -- balanced, homer, contrarian, stat_nerd, old_school, provocateur
    credibility INTEGER NOT NULL DEFAULT 60,  -- 1-100
    hot_take_tendency REAL NOT NULL DEFAULT 0.3,  -- 0-1
    favorite_team_id INTEGER,  -- bias toward a team
    catchphrase TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (favorite_team_id) REFERENCES teams(id)
);

-- TV SEGMENTS / HOT TAKES
CREATE TABLE IF NOT EXISTS tv_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analyst_id INTEGER NOT NULL,
    game_date TEXT NOT NULL,
    segment_type TEXT NOT NULL,  -- hot_take, trade_grade, power_rankings, player_spotlight, weekly_recap, debate
    headline TEXT NOT NULL,
    content TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (analyst_id) REFERENCES tv_analysts(id)
);

CREATE INDEX IF NOT EXISTS idx_tv_segments_date ON tv_segments(game_date);
CREATE INDEX IF NOT EXISTS idx_tv_segments_analyst ON tv_segments(analyst_id);
CREATE INDEX IF NOT EXISTS idx_tv_analysts_active ON tv_analysts(is_active);

-- ============================================================
-- MINOR LEAGUE STANDINGS
-- ============================================================
CREATE TABLE IF NOT EXISTS milb_standings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    level TEXT NOT NULL,  -- AAA, AA, A
    season INTEGER NOT NULL,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    runs_scored INTEGER NOT NULL DEFAULT 0,
    runs_allowed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (team_id) REFERENCES teams(id),
    UNIQUE(team_id, level, season)
);

-- MINOR LEAGUE BATTING STATS
CREATE TABLE IF NOT EXISTS milb_batting_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    level TEXT NOT NULL,
    season INTEGER NOT NULL,
    games INTEGER NOT NULL DEFAULT 0,
    ab INTEGER NOT NULL DEFAULT 0,
    hits INTEGER NOT NULL DEFAULT 0,
    doubles INTEGER NOT NULL DEFAULT 0,
    triples INTEGER NOT NULL DEFAULT 0,
    hr INTEGER NOT NULL DEFAULT 0,
    rbi INTEGER NOT NULL DEFAULT 0,
    bb INTEGER NOT NULL DEFAULT 0,
    so INTEGER NOT NULL DEFAULT 0,
    sb INTEGER NOT NULL DEFAULT 0,
    cs INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (team_id) REFERENCES teams(id),
    UNIQUE(player_id, level, season)
);

-- MINOR LEAGUE PITCHING STATS
CREATE TABLE IF NOT EXISTS milb_pitching_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    team_id INTEGER NOT NULL,
    level TEXT NOT NULL,
    season INTEGER NOT NULL,
    games INTEGER NOT NULL DEFAULT 0,
    games_started INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    saves INTEGER NOT NULL DEFAULT 0,
    ip_outs INTEGER NOT NULL DEFAULT 0,
    hits_allowed INTEGER NOT NULL DEFAULT 0,
    er INTEGER NOT NULL DEFAULT 0,
    bb INTEGER NOT NULL DEFAULT 0,
    so INTEGER NOT NULL DEFAULT 0,
    hr_allowed INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (team_id) REFERENCES teams(id),
    UNIQUE(player_id, level, season)
);

CREATE INDEX IF NOT EXISTS idx_milb_standings_team ON milb_standings(team_id, season);
CREATE INDEX IF NOT EXISTS idx_milb_batting_stats_player ON milb_batting_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_milb_batting_stats_team ON milb_batting_stats(team_id, level, season);
CREATE INDEX IF NOT EXISTS idx_milb_pitching_stats_player ON milb_pitching_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_milb_pitching_stats_team ON milb_pitching_stats(team_id, level, season);

-- ============================================================
-- PLAYER STRATEGY (per-player tactical settings)
-- ============================================================
CREATE TABLE IF NOT EXISTS player_strategy (
    player_id INTEGER PRIMARY KEY,
    steal_aggression INTEGER NOT NULL DEFAULT 3,  -- 1-5 scale (1=never, 3=normal, 5=very aggressive)
    bunt_tendency INTEGER NOT NULL DEFAULT 3,     -- 1-5 scale
    hit_and_run INTEGER NOT NULL DEFAULT 3,       -- 1-5 scale
    pitch_count_limit INTEGER DEFAULT NULL,       -- NULL = use team setting
    FOREIGN KEY (player_id) REFERENCES players(id)
);

-- ============================================================
-- MATCHUP STATS (batter vs pitcher head-to-head)
-- ============================================================
CREATE TABLE IF NOT EXISTS matchup_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batter_id INTEGER NOT NULL,
    pitcher_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    pa INTEGER NOT NULL DEFAULT 0,
    ab INTEGER NOT NULL DEFAULT 0,
    h INTEGER NOT NULL DEFAULT 0,
    doubles INTEGER NOT NULL DEFAULT 0,
    triples INTEGER NOT NULL DEFAULT 0,
    hr INTEGER NOT NULL DEFAULT 0,
    rbi INTEGER NOT NULL DEFAULT 0,
    bb INTEGER NOT NULL DEFAULT 0,
    so INTEGER NOT NULL DEFAULT 0,
    hbp INTEGER NOT NULL DEFAULT 0,
    UNIQUE(batter_id, pitcher_id, season),
    FOREIGN KEY (batter_id) REFERENCES players(id),
    FOREIGN KEY (pitcher_id) REFERENCES players(id)
);

CREATE INDEX IF NOT EXISTS idx_matchup_stats_batter ON matchup_stats(batter_id, season);
CREATE INDEX IF NOT EXISTS idx_matchup_stats_pitcher ON matchup_stats(pitcher_id, season);

-- ============================================================
-- PLAYER AGENTS (negotiation personalities)
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    agency_name TEXT,
    personality TEXT NOT NULL DEFAULT 'collaborative',  -- aggressive, collaborative, passive, shark, player_first
    negotiation_style TEXT NOT NULL DEFAULT 'fair',  -- hardball, fair, flexible, theatrical
    greed_factor REAL NOT NULL DEFAULT 1.0,  -- multiplier on salary demands (0.8 = discount, 1.3 = premium)
    loyalty_to_client REAL NOT NULL DEFAULT 0.7,  -- 0-1, how much they push for client wishes vs money
    market_knowledge INTEGER NOT NULL DEFAULT 70,  -- 1-100, how well they know player values
    bluff_tendency REAL NOT NULL DEFAULT 0.3,  -- 0-1, how often they bluff about other offers
    patience INTEGER NOT NULL DEFAULT 50,  -- 1-100, how long they'll wait for better offers
    reputation INTEGER NOT NULL DEFAULT 50,  -- 1-100, league-wide reputation
    num_clients INTEGER NOT NULL DEFAULT 0,
    notable_deals TEXT DEFAULT NULL,  -- JSON array of past deal highlights
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Link players to their agents
CREATE TABLE IF NOT EXISTS player_agents (
    player_id INTEGER PRIMARY KEY,
    agent_id INTEGER NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (agent_id) REFERENCES agent_characters(id)
);

CREATE INDEX IF NOT EXISTS idx_player_agents_agent ON player_agents(agent_id);

-- ============================================================
-- PITCH LOG (per-pitch tracking data)
-- ============================================================
CREATE TABLE IF NOT EXISTS pitch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER,
    inning INTEGER,
    at_bat_num INTEGER,
    pitch_num INTEGER,
    pitcher_id INTEGER,
    batter_id INTEGER,
    pitch_type TEXT,
    velocity REAL,
    result TEXT,  -- ball, called_strike, swinging_strike, foul, in_play
    zone INTEGER,  -- 1-9 for strike zone quadrants, 11-14 for chase zones
    count_balls INTEGER,
    count_strikes INTEGER,
    outs INTEGER,
    runners_on INTEGER,  -- bitmask: 1=1st, 2=2nd, 4=3rd
    score_diff INTEGER,
    season INTEGER,
    FOREIGN KEY (game_id) REFERENCES schedule(id),
    FOREIGN KEY (pitcher_id) REFERENCES players(id),
    FOREIGN KEY (batter_id) REFERENCES players(id)
);

CREATE INDEX IF NOT EXISTS idx_pitch_log_pitcher ON pitch_log(pitcher_id, season);
CREATE INDEX IF NOT EXISTS idx_pitch_log_batter ON pitch_log(batter_id, season);
CREATE INDEX IF NOT EXISTS idx_pitch_log_game ON pitch_log(game_id);

-- ============================================================
-- OWNER OBJECTIVES & JOB SECURITY
-- ============================================================
CREATE TABLE IF NOT EXISTS owner_objectives (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    objective_type TEXT NOT NULL,  -- win_division, make_playoffs, rebuild, cut_payroll, develop_prospects, win_ws
    target_value TEXT,  -- e.g., "90" for 90 wins, "$150M" for payroll target
    priority INTEGER NOT NULL DEFAULT 1,  -- 1=critical, 2=important, 3=nice-to-have
    status TEXT NOT NULL DEFAULT 'active',  -- active, met, failed
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE TABLE IF NOT EXISTS gm_job_security (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    team_id INTEGER NOT NULL,
    security_score INTEGER NOT NULL DEFAULT 70,  -- 0-100, below 20 = fired
    owner_patience INTEGER NOT NULL DEFAULT 50,  -- 0-100
    consecutive_losing_seasons INTEGER NOT NULL DEFAULT 0,
    playoff_appearances INTEGER NOT NULL DEFAULT 0,
    owner_mood TEXT NOT NULL DEFAULT 'neutral',  -- elated, happy, neutral, concerned, angry, furious
    last_evaluation_date TEXT,
    warnings_given INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_owner_objectives_team ON owner_objectives(team_id, season);
CREATE INDEX IF NOT EXISTS idx_owner_objectives_status ON owner_objectives(status);

-- ============================================================
-- SEASON HISTORY (multi-season franchise tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS season_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    season INTEGER NOT NULL,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    playoff_result TEXT,  -- none, wc_loss, ds_loss, lcs_loss, ws_loss, ws_win
    division_finish INTEGER,  -- 1-5
    payroll INTEGER,
    attendance INTEGER,
    mvp_name TEXT,
    cy_young_name TEXT,
    notable_events TEXT,  -- JSON array
    gm_rating INTEGER,  -- end-of-season GM performance rating
    FOREIGN KEY (team_id) REFERENCES teams(id),
    UNIQUE(team_id, season)
);

CREATE INDEX IF NOT EXISTS idx_season_history_team ON season_history(team_id);
CREATE INDEX IF NOT EXISTS idx_season_history_season ON season_history(season);

-- ============================================================
-- COACHING STAFF
-- ============================================================
CREATE TABLE IF NOT EXISTS coaching_staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    role TEXT NOT NULL,  -- manager, hitting_coach, pitching_coach, bench_coach, bullpen_coach, first_base_coach, third_base_coach, development_coordinator
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    age INTEGER NOT NULL DEFAULT 50,
    experience INTEGER NOT NULL DEFAULT 5,  -- years of coaching experience
    skill_rating INTEGER NOT NULL DEFAULT 50,  -- 1-100 coaching ability
    philosophy TEXT DEFAULT 'balanced',  -- aggressive, balanced, conservative, analytics
    specialty TEXT DEFAULT NULL,  -- player_development, game_strategy, pitching_mechanics, hitting_approach
    salary INTEGER NOT NULL DEFAULT 1000000,
    contract_years INTEGER NOT NULL DEFAULT 2,
    is_available INTEGER NOT NULL DEFAULT 0,  -- 1 = free agent coach
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- CHARACTER CAREERS (dynamic NPC career arcs)
-- ============================================================
CREATE TABLE IF NOT EXISTS character_careers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    character_type TEXT NOT NULL,  -- scouting, coaching, media, agent
    name TEXT NOT NULL,
    current_role TEXT NOT NULL,  -- Scout, GM, TV Analyst, Manager, etc.
    current_team_id INTEGER,
    reputation INTEGER NOT NULL DEFAULT 50,  -- 0-100
    personality_json TEXT NOT NULL DEFAULT '{}',
    career_history_json TEXT NOT NULL DEFAULT '[]',  -- JSON array of past roles
    created_date TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    FOREIGN KEY (current_team_id) REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_character_careers_type ON character_careers(character_type);
CREATE INDEX IF NOT EXISTS idx_character_careers_team ON character_careers(current_team_id);
CREATE INDEX IF NOT EXISTS idx_character_careers_role ON character_careers(current_role);

-- ============================================================
-- PROACTIVE MESSAGE LOG (cooldown tracking for AI character messages)
-- ============================================================
CREATE TABLE IF NOT EXISTS proactive_message_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_type TEXT NOT NULL,  -- owner, rival_gm, agent, coach, beat_writer
    character_id TEXT NOT NULL,  -- identifier (e.g. agent id, team id, coach name)
    trigger_type TEXT NOT NULL,  -- losing_streak, payroll_over_budget, prospect_ready, etc.
    team_id INTEGER NOT NULL,
    game_date TEXT NOT NULL,
    cooldown_until TEXT NOT NULL,  -- don't send same trigger from same character until this date
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_proactive_msg_cooldown
    ON proactive_message_log(character_type, character_id, trigger_type, team_id);

-- ============================================================
-- BEAT WRITERS (journalist characters)
-- ============================================================
CREATE TABLE IF NOT EXISTS beat_writers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER,
    name TEXT NOT NULL,
    outlet TEXT NOT NULL,
    personality TEXT NOT NULL DEFAULT 'analyst',
    writing_style TEXT NOT NULL DEFAULT 'narrative',
    credibility INTEGER NOT NULL DEFAULT 70,
    access_level INTEGER NOT NULL DEFAULT 50,
    bias REAL NOT NULL DEFAULT 0.0,
    follower_count INTEGER NOT NULL DEFAULT 50000,
    is_active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- ============================================================
-- ARTICLES (generated news articles)
-- ============================================================
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    writer_id INTEGER,
    game_date TEXT NOT NULL,
    headline TEXT NOT NULL,
    body TEXT NOT NULL,
    article_type TEXT NOT NULL DEFAULT 'news',
    sentiment TEXT NOT NULL DEFAULT 'neutral',
    team_id INTEGER,
    player_id INTEGER,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (writer_id) REFERENCES beat_writers(id),
    FOREIGN KEY (team_id) REFERENCES teams(id),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(game_date);
CREATE INDEX IF NOT EXISTS idx_articles_team ON articles(team_id);
CREATE INDEX IF NOT EXISTS idx_articles_type ON articles(article_type);
CREATE INDEX IF NOT EXISTS idx_articles_writer ON articles(writer_id);

-- ============================================================
-- FAN SENTIMENT (per-team fan mood tracking)
-- ============================================================
CREATE TABLE IF NOT EXISTS fan_sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL UNIQUE,
    sentiment_score INTEGER NOT NULL DEFAULT 50,
    excitement INTEGER NOT NULL DEFAULT 50,
    attendance_modifier REAL NOT NULL DEFAULT 1.0,
    social_media_buzz INTEGER NOT NULL DEFAULT 50,
    trust_in_gm INTEGER NOT NULL DEFAULT 50,
    top_concern TEXT,
    reaction_text TEXT,
    last_updated TEXT,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_fan_sentiment_team ON fan_sentiment(team_id);

-- ============================================================
-- SCOUTING ASSIGNMENTS (asymmetric information system)
-- ============================================================
CREATE TABLE IF NOT EXISTS scouting_assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    scout_quality INTEGER NOT NULL DEFAULT 50,
    started_date TEXT NOT NULL,
    info_level INTEGER NOT NULL DEFAULT 2,  -- maps to InformationLevel enum
    FOREIGN KEY (team_id) REFERENCES teams(id),
    FOREIGN KEY (player_id) REFERENCES players(id)
);

CREATE INDEX IF NOT EXISTS idx_scouting_assignments_team ON scouting_assignments(team_id);
CREATE INDEX IF NOT EXISTS idx_scouting_assignments_player ON scouting_assignments(team_id, player_id);

-- ============================================================
-- INTELLIGENCE REPORTS (asymmetric information system)
-- ============================================================
CREATE TABLE IF NOT EXISTS intelligence_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL,
    subject_type TEXT NOT NULL DEFAULT 'player',  -- player, team, trade
    subject_id INTEGER NOT NULL,
    info_level INTEGER NOT NULL DEFAULT 0,
    report_data TEXT,  -- JSON blob with report details
    source TEXT NOT NULL DEFAULT 'scout',  -- scout, beat_writer, agent, gm
    game_date TEXT NOT NULL,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_intelligence_reports_team ON intelligence_reports(team_id);
CREATE INDEX IF NOT EXISTS idx_intelligence_reports_subject ON intelligence_reports(subject_type, subject_id);
"""
