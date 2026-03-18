"""
Front Office - Records Tracking System
Tracks career and single-season records within the game universe.
Generates notifications when players approach or break records.
"""
from ..database.db import query, execute, get_connection

# ============================================================
# INITIAL REAL MLB RECORDS (baseline for the game universe)
# ============================================================
INITIAL_RECORDS = [
    # --- Single-season batting ---
    ("season", "batting", "hr", 73, "Barry Bonds", None, 2001, "San Francisco Giants", 1),
    ("season", "batting", "rbi", 191, "Hack Wilson", None, 1930, "Chicago Cubs", 1),
    ("season", "batting", "hits", 262, "Ichiro Suzuki", None, 2004, "Seattle Mariners", 1),
    ("season", "batting", "avg", 0.394, "Tony Gwynn", None, 1994, "San Diego Padres", 1),
    ("season", "batting", "obp", 0.609, "Barry Bonds", None, 2004, "San Francisco Giants", 1),
    ("season", "batting", "slg", 0.863, "Barry Bonds", None, 2001, "San Francisco Giants", 1),
    ("season", "batting", "ops", 1.422, "Barry Bonds", None, 2004, "San Francisco Giants", 1),
    ("season", "batting", "sb", 130, "Rickey Henderson", None, 1982, "Oakland Athletics", 1),
    ("season", "batting", "runs", 177, "Babe Ruth", None, 1921, "New York Yankees", 1),
    ("season", "batting", "bb", 232, "Barry Bonds", None, 2004, "San Francisco Giants", 1),
    ("season", "batting", "doubles", 67, "Earl Webb", None, 1931, "Boston Red Sox", 1),
    ("season", "batting", "triples", 36, "Chief Wilson", None, 1912, "Pittsburgh Pirates", 1),

    # --- Single-season pitching ---
    ("season", "pitching", "wins", 41, "Jack Chesbro", None, 1904, "New York Highlanders", 1),
    ("season", "pitching", "era", 1.12, "Bob Gibson", None, 1968, "St. Louis Cardinals", 1),
    ("season", "pitching", "so", 383, "Nolan Ryan", None, 1973, "California Angels", 1),
    ("season", "pitching", "saves", 62, "Francisco Rodriguez", None, 2008, "Los Angeles Angels", 1),
    ("season", "pitching", "ip", 464.0, "Ed Walsh", None, 1908, "Chicago White Sox", 1),
    ("season", "pitching", "whip", 0.737, "Pedro Martinez", None, 2000, "Boston Red Sox", 1),
    ("season", "pitching", "shutouts", 16, "Grover Alexander", None, 1916, "Philadelphia Phillies", 1),
    ("season", "pitching", "complete_games", 48, "Jack Chesbro", None, 1904, "New York Highlanders", 1),

    # --- Career batting ---
    ("career", "batting", "hr", 762, "Barry Bonds", None, None, None, 1),
    ("career", "batting", "rbi", 2297, "Hank Aaron", None, None, None, 1),
    ("career", "batting", "hits", 4256, "Pete Rose", None, None, None, 1),
    ("career", "batting", "avg", 0.366, "Ty Cobb", None, None, None, 1),
    ("career", "batting", "sb", 1406, "Rickey Henderson", None, None, None, 1),
    ("career", "batting", "runs", 2295, "Rickey Henderson", None, None, None, 1),
    ("career", "batting", "bb", 2558, "Barry Bonds", None, None, None, 1),
    ("career", "batting", "games", 3562, "Pete Rose", None, None, None, 1),

    # --- Career pitching ---
    ("career", "pitching", "wins", 511, "Cy Young", None, None, None, 1),
    ("career", "pitching", "era", 1.82, "Ed Walsh", None, None, None, 1),
    ("career", "pitching", "so", 5714, "Nolan Ryan", None, None, None, 1),
    ("career", "pitching", "saves", 652, "Mariano Rivera", None, None, None, 1),
    ("career", "pitching", "ip", 7356.0, "Cy Young", None, None, None, 1),
]

# Stat display names for UI and messages
STAT_DISPLAY_NAMES = {
    "hr": "Home Runs",
    "rbi": "RBI",
    "hits": "Hits",
    "avg": "Batting Average",
    "obp": "On-Base Percentage",
    "slg": "Slugging Percentage",
    "ops": "OPS",
    "sb": "Stolen Bases",
    "runs": "Runs",
    "bb": "Walks",
    "doubles": "Doubles",
    "triples": "Triples",
    "games": "Games Played",
    "wins": "Wins",
    "era": "ERA",
    "so": "Strikeouts",
    "saves": "Saves",
    "ip": "Innings Pitched",
    "whip": "WHIP",
    "shutouts": "Shutouts",
    "complete_games": "Complete Games",
}

# Career milestone thresholds (for special alerts)
CAREER_MILESTONES = {
    "batting": {
        "hr": [500, 600, 700],
        "hits": [2000, 2500, 3000, 3500, 4000],
        "rbi": [1500, 2000],
        "runs": [1500, 2000],
        "sb": [500, 750, 1000],
        "bb": [1500, 2000],
        "games": [2000, 2500, 3000],
    },
    "pitching": {
        "wins": [200, 250, 300, 350],
        "so": [2000, 2500, 3000, 3500, 4000, 5000],
        "saves": [300, 400, 500, 600],
        "ip": [3000, 4000, 5000],
    },
}

# Stats where lower is better
LOWER_IS_BETTER = {"era", "whip"}


def initialize_records(db_path=None):
    """Seed the records table with real MLB records as baselines."""
    conn = get_connection(db_path)

    # Create tables if they don't exist
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT NOT NULL,
            category TEXT NOT NULL,
            stat_name TEXT NOT NULL,
            value REAL NOT NULL,
            player_name TEXT NOT NULL,
            player_id INTEGER,
            season INTEGER,
            team_name TEXT,
            set_date TEXT,
            is_real_record INTEGER DEFAULT 1,
            UNIQUE(record_type, category, stat_name)
        );

        CREATE TABLE IF NOT EXISTS record_watch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            stat_name TEXT NOT NULL,
            record_type TEXT NOT NULL DEFAULT 'season',
            category TEXT NOT NULL DEFAULT 'batting',
            current_value REAL NOT NULL,
            record_value REAL NOT NULL,
            pace REAL NOT NULL,
            game_date TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );

        CREATE INDEX IF NOT EXISTS idx_record_watch_active
            ON record_watch(is_active, player_id, stat_name);
        CREATE INDEX IF NOT EXISTS idx_records_type
            ON records(record_type, category);
    """)
    conn.commit()

    # Only seed if the table is empty
    existing = conn.execute("SELECT COUNT(*) as cnt FROM records").fetchone()
    if existing[0] > 0:
        conn.close()
        return {"status": "already_initialized", "count": existing[0]}

    for rec in INITIAL_RECORDS:
        record_type, category, stat_name, value, player_name, player_id, season, team_name, is_real = rec
        conn.execute("""
            INSERT OR IGNORE INTO records
                (record_type, category, stat_name, value, player_name, player_id, season, team_name, is_real_record)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (record_type, category, stat_name, value, player_name, player_id, season, team_name, is_real))

    conn.commit()
    conn.close()
    return {"status": "initialized", "count": len(INITIAL_RECORDS)}


def get_all_records(record_type=None, db_path=None):
    """Return all records, optionally filtered by type ('season' or 'career')."""
    if record_type:
        rows = query("""
            SELECT * FROM records WHERE record_type=?
            ORDER BY category, stat_name
        """, (record_type,), db_path=db_path)
    else:
        rows = query("""
            SELECT * FROM records
            ORDER BY record_type, category, stat_name
        """, db_path=db_path)

    # Add display name for each record
    for r in rows:
        r["stat_display"] = STAT_DISPLAY_NAMES.get(r["stat_name"], r["stat_name"])

    return rows


def get_record_watch(db_path=None):
    """Return current active record watch items."""
    rows = query("""
        SELECT rw.*, r.value as record_value_current, r.player_name as record_holder
        FROM record_watch rw
        LEFT JOIN records r ON r.record_type = rw.record_type
            AND r.category = rw.category AND r.stat_name = rw.stat_name
        WHERE rw.is_active = 1
        ORDER BY rw.pace DESC
    """, db_path=db_path)

    for r in rows:
        r["stat_display"] = STAT_DISPLAY_NAMES.get(r["stat_name"], r["stat_name"])
        pct = 0
        if r["record_value"] and r["record_value"] != 0:
            if r["stat_name"] in LOWER_IS_BETTER:
                pct = round(r["record_value"] / r["pace"] * 100, 1) if r["pace"] > 0 else 0
            else:
                pct = round(r["pace"] / r["record_value"] * 100, 1)
        r["pace_pct"] = pct

    return rows


def _get_season_info(db_path=None):
    """Get current season and game date info."""
    state = query("SELECT * FROM game_state WHERE id=1", db_path=db_path)
    if not state:
        return None, None, None, 0

    from datetime import date
    current_date = date.fromisoformat(state[0]["current_date"])
    season = state[0]["season"]

    # Estimate season progress (162-game season, roughly April 1 to Sep 30)
    season_start = date(season, 4, 1)
    season_end = date(season, 9, 30)
    total_days = (season_end - season_start).days
    elapsed_days = (current_date - season_start).days
    season_pct = max(0.01, min(1.0, elapsed_days / total_days)) if total_days > 0 else 0.01

    return season, current_date, state[0], season_pct


def _compute_batting_rates(row):
    """Compute rate stats from raw counting stats."""
    ab = row.get("ab", 0)
    pa = row.get("pa", 0)
    hits = row.get("hits", 0)
    bb = row.get("bb", 0)
    hbp = row.get("hbp", 0)
    sf = row.get("sf", 0)
    hr = row.get("hr", 0)
    doubles = row.get("doubles", 0)
    triples = row.get("triples", 0)

    avg = hits / ab if ab > 0 else 0
    obp = (hits + bb + hbp) / pa if pa > 0 else 0
    tb = hits + doubles + 2 * triples + 3 * hr
    slg = tb / ab if ab > 0 else 0
    ops = obp + slg

    return {"avg": round(avg, 3), "obp": round(obp, 3), "slg": round(slg, 3), "ops": round(ops, 3)}


def _compute_pitching_rates(row):
    """Compute rate stats from raw pitching stats."""
    ip_outs = row.get("ip_outs", 0)
    ip = ip_outs / 3.0 if ip_outs > 0 else 0
    er = row.get("er", 0)
    hits_allowed = row.get("hits_allowed", 0)
    bb = row.get("bb", 0)

    era = (er * 9 / ip) if ip > 0 else 99.99
    whip = (hits_allowed + bb) / ip if ip > 0 else 99.99

    return {"era": round(era, 2), "whip": round(whip, 3), "ip": round(ip, 1)}


def check_record_watch(game_date, db_path=None):
    """
    Check all active players against records.
    Called periodically (1st and 15th of each month).
    Returns list of record watch items and broken records.
    """
    season, current_date, state, season_pct = _get_season_info(db_path)
    if not season or season_pct < 0.1:
        return []

    results = {"watch_items": [], "broken_records": []}

    # Deactivate old watch items
    execute("UPDATE record_watch SET is_active = 0 WHERE game_date < ?",
            (game_date,), db_path=db_path)

    # Get current records
    records = query("SELECT * FROM records", db_path=db_path)
    record_map = {}
    for r in records:
        key = (r["record_type"], r["category"], r["stat_name"])
        record_map[key] = r

    # --- Check single-season batting records ---
    batting_stats = query("""
        SELECT bs.*, p.first_name, p.last_name, p.id as pid, t.name as team_name,
               t.city as team_city, t.id as tid
        FROM batting_stats bs
        JOIN players p ON bs.player_id = p.id
        JOIN teams t ON bs.team_id = t.id
        WHERE bs.season = ? AND bs.level = 'MLB' AND bs.is_postseason = 0
        AND bs.pa >= 50
    """, (season,), db_path=db_path)

    season_batting_stats = ["hr", "rbi", "hits", "sb", "runs", "bb", "doubles", "triples"]
    season_batting_rate_stats = ["avg", "obp", "slg", "ops"]

    for row in batting_stats:
        player_name = f"{row['first_name']} {row['last_name']}"
        player_id = row["pid"]
        team_full = f"{row['team_city']} {row['team_name']}"

        # Check counting stats with pace projection
        for stat in season_batting_stats:
            value = row.get(stat, 0)
            if value == 0:
                continue

            projected = value / season_pct if season_pct > 0 else value
            rec_key = ("season", "batting", stat)
            record = record_map.get(rec_key)
            if not record:
                continue

            record_val = record["value"]

            # Check if broken (end of season or already exceeded)
            if value > record_val:
                _handle_record_broken(
                    "season", "batting", stat, value, player_name, player_id,
                    season, team_full, game_date, record, db_path
                )
                results["broken_records"].append({
                    "stat": stat, "value": value, "player": player_name,
                    "old_record": record_val, "old_holder": record["player_name"]
                })
            elif projected >= record_val * 0.80:
                _add_watch_item(
                    player_id, player_name, stat, "season", "batting",
                    value, record_val, projected, game_date, db_path
                )
                results["watch_items"].append({
                    "stat": stat, "player": player_name, "current": value,
                    "pace": round(projected, 1), "record": record_val
                })

        # Check rate stats (only with enough PA)
        if row.get("pa", 0) >= 200:
            rates = _compute_batting_rates(row)
            for stat in season_batting_rate_stats:
                value = rates[stat]
                if value == 0:
                    continue

                rec_key = ("season", "batting", stat)
                record = record_map.get(rec_key)
                if not record:
                    continue

                record_val = record["value"]

                if value > record_val and season_pct >= 0.8:
                    _handle_record_broken(
                        "season", "batting", stat, value, player_name, player_id,
                        season, team_full, game_date, record, db_path
                    )
                    results["broken_records"].append({
                        "stat": stat, "value": value, "player": player_name,
                        "old_record": record_val, "old_holder": record["player_name"]
                    })
                elif value > record_val * 0.90 and row.get("pa", 0) >= 300:
                    _add_watch_item(
                        player_id, player_name, stat, "season", "batting",
                        value, record_val, value, game_date, db_path
                    )
                    results["watch_items"].append({
                        "stat": stat, "player": player_name, "current": value,
                        "pace": value, "record": record_val
                    })

    # --- Check single-season pitching records ---
    pitching_stats = query("""
        SELECT ps.*, p.first_name, p.last_name, p.id as pid, t.name as team_name,
               t.city as team_city, t.id as tid
        FROM pitching_stats ps
        JOIN players p ON ps.player_id = p.id
        JOIN teams t ON ps.team_id = t.id
        WHERE ps.season = ? AND ps.level = 'MLB' AND ps.is_postseason = 0
        AND ps.ip_outs >= 30
    """, (season,), db_path=db_path)

    season_pitching_count = ["wins", "so", "saves", "shutouts", "complete_games"]

    for row in pitching_stats:
        player_name = f"{row['first_name']} {row['last_name']}"
        player_id = row["pid"]
        team_full = f"{row['team_city']} {row['team_name']}"
        rates = _compute_pitching_rates(row)

        # Counting stats
        for stat in season_pitching_count:
            value = row.get(stat, 0)
            if value == 0:
                continue

            projected = value / season_pct if season_pct > 0 else value
            rec_key = ("season", "pitching", stat)
            record = record_map.get(rec_key)
            if not record:
                continue

            record_val = record["value"]

            if value > record_val:
                _handle_record_broken(
                    "season", "pitching", stat, value, player_name, player_id,
                    season, team_full, game_date, record, db_path
                )
                results["broken_records"].append({
                    "stat": stat, "value": value, "player": player_name,
                    "old_record": record_val, "old_holder": record["player_name"]
                })
            elif projected >= record_val * 0.80:
                _add_watch_item(
                    player_id, player_name, stat, "season", "pitching",
                    value, record_val, projected, game_date, db_path
                )
                results["watch_items"].append({
                    "stat": stat, "player": player_name, "current": value,
                    "pace": round(projected, 1), "record": record_val
                })

        # IP as a counting stat
        ip_val = rates["ip"]
        if ip_val > 0:
            projected_ip = ip_val / season_pct if season_pct > 0 else ip_val
            rec_key = ("season", "pitching", "ip")
            record = record_map.get(rec_key)
            if record:
                record_val = record["value"]
                if ip_val > record_val:
                    _handle_record_broken(
                        "season", "pitching", "ip", ip_val, player_name, player_id,
                        season, team_full, game_date, record, db_path
                    )
                    results["broken_records"].append({
                        "stat": "ip", "value": ip_val, "player": player_name,
                        "old_record": record_val, "old_holder": record["player_name"]
                    })
                elif projected_ip >= record_val * 0.80:
                    _add_watch_item(
                        player_id, player_name, "ip", "season", "pitching",
                        ip_val, record_val, projected_ip, game_date, db_path
                    )

        # ERA and WHIP (lower is better, need min IP)
        if row.get("ip_outs", 0) >= 300:  # ~100 IP minimum
            for stat in ["era", "whip"]:
                value = rates[stat]
                if value <= 0:
                    continue

                rec_key = ("season", "pitching", stat)
                record = record_map.get(rec_key)
                if not record:
                    continue

                record_val = record["value"]

                if value < record_val and season_pct >= 0.8:
                    _handle_record_broken(
                        "season", "pitching", stat, value, player_name, player_id,
                        season, team_full, game_date, record, db_path
                    )
                    results["broken_records"].append({
                        "stat": stat, "value": value, "player": player_name,
                        "old_record": record_val, "old_holder": record["player_name"]
                    })
                elif value < record_val * 1.15 and row.get("ip_outs", 0) >= 400:
                    _add_watch_item(
                        player_id, player_name, stat, "season", "pitching",
                        value, record_val, value, game_date, db_path
                    )
                    results["watch_items"].append({
                        "stat": stat, "player": player_name, "current": value,
                        "pace": value, "record": record_val
                    })

    # --- Check career records ---
    _check_career_records(game_date, record_map, results, db_path)

    return results


def _check_career_records(game_date, record_map, results, db_path=None):
    """Check career totals against career records."""
    # Career batting: aggregate all seasons
    career_batting = query("""
        SELECT p.id as pid, p.first_name, p.last_name,
               SUM(bs.games) as games, SUM(bs.hr) as hr, SUM(bs.rbi) as rbi,
               SUM(bs.hits) as hits, SUM(bs.sb) as sb, SUM(bs.runs) as runs,
               SUM(bs.bb) as bb, SUM(bs.ab) as ab,
               t.name as team_name, t.city as team_city
        FROM batting_stats bs
        JOIN players p ON bs.player_id = p.id
        JOIN teams t ON p.team_id = t.id
        WHERE bs.level = 'MLB' AND bs.is_postseason = 0
        AND p.roster_status IN ('active', 'minors')
        GROUP BY p.id
        HAVING SUM(bs.games) >= 100
    """, db_path=db_path)

    career_batting_stats = ["hr", "rbi", "hits", "sb", "runs", "bb", "games"]

    for row in (career_batting or []):
        player_name = f"{row['first_name']} {row['last_name']}"
        player_id = row["pid"]
        team_full = f"{row['team_city']} {row['team_name']}"

        for stat in career_batting_stats:
            value = row.get(stat, 0)
            if value == 0:
                continue

            rec_key = ("career", "batting", stat)
            record = record_map.get(rec_key)
            if not record:
                continue

            record_val = record["value"]

            if value > record_val:
                _handle_record_broken(
                    "career", "batting", stat, value, player_name, player_id,
                    None, team_full, game_date, record, db_path
                )
                results["broken_records"].append({
                    "stat": stat, "value": value, "player": player_name,
                    "old_record": record_val, "old_holder": record["player_name"]
                })
            elif value >= record_val * 0.90:
                _add_watch_item(
                    player_id, player_name, stat, "career", "batting",
                    value, record_val, value, game_date, db_path
                )
                results["watch_items"].append({
                    "stat": stat, "player": player_name, "current": value,
                    "pace": value, "record": record_val, "type": "career"
                })

        # Career batting average
        if row.get("ab", 0) >= 1000:
            career_avg = round(row["hits"] / row["ab"], 3) if row["ab"] > 0 else 0
            rec_key = ("career", "batting", "avg")
            record = record_map.get(rec_key)
            if record and career_avg > record["value"]:
                _handle_record_broken(
                    "career", "batting", "avg", career_avg, player_name, player_id,
                    None, team_full, game_date, record, db_path
                )

    # Career pitching
    career_pitching = query("""
        SELECT p.id as pid, p.first_name, p.last_name,
               SUM(ps.wins) as wins, SUM(ps.so) as so, SUM(ps.saves) as saves,
               SUM(ps.ip_outs) as ip_outs, SUM(ps.er) as er,
               SUM(ps.hits_allowed) as hits_allowed, SUM(ps.bb) as bb,
               t.name as team_name, t.city as team_city
        FROM pitching_stats ps
        JOIN players p ON ps.player_id = p.id
        JOIN teams t ON p.team_id = t.id
        WHERE ps.level = 'MLB' AND ps.is_postseason = 0
        AND p.roster_status IN ('active', 'minors')
        GROUP BY p.id
        HAVING SUM(ps.ip_outs) >= 300
    """, db_path=db_path)

    career_pitching_stats = ["wins", "so", "saves"]

    for row in (career_pitching or []):
        player_name = f"{row['first_name']} {row['last_name']}"
        player_id = row["pid"]
        team_full = f"{row['team_city']} {row['team_name']}"

        for stat in career_pitching_stats:
            value = row.get(stat, 0)
            if value == 0:
                continue

            rec_key = ("career", "pitching", stat)
            record = record_map.get(rec_key)
            if not record:
                continue

            record_val = record["value"]

            if value > record_val:
                _handle_record_broken(
                    "career", "pitching", stat, value, player_name, player_id,
                    None, team_full, game_date, record, db_path
                )
                results["broken_records"].append({
                    "stat": stat, "value": value, "player": player_name,
                    "old_record": record_val, "old_holder": record["player_name"]
                })
            elif value >= record_val * 0.90:
                _add_watch_item(
                    player_id, player_name, stat, "career", "pitching",
                    value, record_val, value, game_date, db_path
                )

        # Career IP
        ip_val = round(row.get("ip_outs", 0) / 3.0, 1)
        rec_key = ("career", "pitching", "ip")
        record = record_map.get(rec_key)
        if record and ip_val > record["value"]:
            _handle_record_broken(
                "career", "pitching", "ip", ip_val, player_name, player_id,
                None, team_full, game_date, record, db_path
            )

        # Career ERA (lower is better)
        if row.get("ip_outs", 0) >= 3000:
            ip = row["ip_outs"] / 3.0
            career_era = round(row["er"] * 9 / ip, 2) if ip > 0 else 99.99
            rec_key = ("career", "pitching", "era")
            record = record_map.get(rec_key)
            if record and career_era < record["value"]:
                _handle_record_broken(
                    "career", "pitching", "era", career_era, player_name, player_id,
                    None, team_full, game_date, record, db_path
                )


def _handle_record_broken(record_type, category, stat_name, value, player_name,
                           player_id, season, team_name, game_date, old_record, db_path=None):
    """Update the record and send notifications when a record is broken."""
    stat_display = STAT_DISPLAY_NAMES.get(stat_name, stat_name)
    old_holder = old_record["player_name"]
    old_value = old_record["value"]

    # Format values for display
    if stat_name in ("avg", "obp", "slg", "ops", "whip"):
        new_display = f"{value:.3f}"
        old_display = f"{old_value:.3f}"
    elif stat_name == "era":
        new_display = f"{value:.2f}"
        old_display = f"{old_value:.2f}"
    elif stat_name == "ip":
        new_display = f"{value:.1f}"
        old_display = f"{old_value:.1f}"
    else:
        new_display = str(int(value))
        old_display = str(int(old_value))

    # Update the record
    execute("""
        UPDATE records SET value=?, player_name=?, player_id=?, season=?,
            team_name=?, set_date=?, is_real_record=0
        WHERE record_type=? AND category=? AND stat_name=?
    """, (value, player_name, player_id, season, team_name, game_date,
          record_type, category, stat_name), db_path=db_path)

    # Send notification to all teams (but especially user's team)
    type_label = "Single-Season" if record_type == "season" else "Career"
    subject = f"RECORD BROKEN: {player_name} - {type_label} {stat_display}"
    body = (
        f"{player_name} has broken the all-time {type_label.lower()} "
        f"{stat_display.lower()} record!\n\n"
        f"New Record: {new_display}\n"
        f"Previous Record: {old_display} ({old_holder})"
    )
    if season and record_type == "season":
        body += f"\nSeason: {season}"
    if team_name:
        body += f"\nTeam: {team_name}"

    # Send to user's team
    from ..transactions.messages import send_message
    user_state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
    if user_state and user_state[0].get("user_team_id"):
        send_message(
            user_state[0]["user_team_id"], "milestone", subject, body,
            game_date=game_date, priority="urgent", db_path=db_path
        )

    # Generate beat writer article about the record
    try:
        from ..ai.beat_writers import generate_article
        # Find which team the player is on
        player_team = query(
            "SELECT team_id FROM players WHERE id=?", (player_id,), db_path=db_path
        ) if player_id else []
        if player_team:
            generate_article(player_team[0]["team_id"], "column", context={
                "player_name": player_name,
                "sentiment_context": "positive",
                "headline_override": subject,
            })
    except Exception:
        pass  # Don't let article errors block record tracking


def _add_watch_item(player_id, player_name, stat_name, record_type, category,
                     current_value, record_value, pace, game_date, db_path=None):
    """Add or update a record watch item."""
    # Check if already watching this player/stat
    existing = query("""
        SELECT id FROM record_watch
        WHERE player_id=? AND stat_name=? AND record_type=? AND is_active=1
    """, (player_id, stat_name, record_type), db_path=db_path)

    if existing:
        execute("""
            UPDATE record_watch SET current_value=?, pace=?, game_date=?
            WHERE id=?
        """, (current_value, pace, game_date, existing[0]["id"]), db_path=db_path)
    else:
        execute("""
            INSERT INTO record_watch
                (player_id, player_name, stat_name, record_type, category,
                 current_value, record_value, pace, game_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (player_id, player_name, stat_name, record_type, category,
              current_value, record_value, pace, game_date), db_path=db_path)

        # Send "record watch" notification for user's team player
        from ..transactions.messages import send_message
        stat_display = STAT_DISPLAY_NAMES.get(stat_name, stat_name)
        type_label = "Single-Season" if record_type == "season" else "Career"

        # Check if this player is on user's team
        user_state = query("SELECT user_team_id FROM game_state WHERE id=1", db_path=db_path)
        if user_state and user_state[0].get("user_team_id"):
            player_team = query("SELECT team_id FROM players WHERE id=?",
                                (player_id,), db_path=db_path)
            if player_team and player_team[0]["team_id"] == user_state[0]["user_team_id"]:
                if stat_name in ("avg", "obp", "slg", "ops", "whip"):
                    pace_display = f"{pace:.3f}"
                elif stat_name == "era":
                    pace_display = f"{pace:.2f}"
                else:
                    pace_display = str(int(pace))

                send_message(
                    user_state[0]["user_team_id"], "milestone",
                    f"Record Watch: {player_name} - {stat_display}",
                    f"{player_name} is on pace for {pace_display} {stat_display.lower()}, "
                    f"putting them on {type_label.lower()} record watch!",
                    game_date=game_date, priority="important", db_path=db_path
                )


def check_career_milestones(player_id, db_path=None):
    """Check if a player is approaching career milestones."""
    alerts = []

    player = query("SELECT * FROM players WHERE id=?", (player_id,), db_path=db_path)
    if not player:
        return alerts
    player = player[0]
    player_name = f"{player['first_name']} {player['last_name']}"

    # Check batting milestones
    batting_career = query("""
        SELECT SUM(hr) as hr, SUM(hits) as hits, SUM(rbi) as rbi,
               SUM(runs) as runs, SUM(sb) as sb, SUM(bb) as bb,
               SUM(games) as games
        FROM batting_stats
        WHERE player_id=? AND level='MLB' AND is_postseason=0
    """, (player_id,), db_path=db_path)

    if batting_career and batting_career[0]["games"]:
        stats = batting_career[0]
        for stat_name, thresholds in CAREER_MILESTONES.get("batting", {}).items():
            value = stats.get(stat_name, 0) or 0
            for threshold in thresholds:
                # Alert when within 10% of milestone
                if value >= threshold * 0.90 and value < threshold:
                    remaining = threshold - value
                    stat_display = STAT_DISPLAY_NAMES.get(stat_name, stat_name)
                    alerts.append({
                        "player_id": player_id,
                        "player_name": player_name,
                        "stat_name": stat_name,
                        "stat_display": stat_display,
                        "current_value": value,
                        "milestone": threshold,
                        "remaining": remaining,
                        "message": f"{player_name} needs {remaining} more {stat_display.lower()} "
                                   f"to reach {threshold:,}!"
                    })
                elif value >= threshold:
                    # Already passed this milestone, skip
                    continue

    # Check pitching milestones
    pitching_career = query("""
        SELECT SUM(wins) as wins, SUM(so) as so, SUM(saves) as saves,
               SUM(ip_outs) as ip_outs
        FROM pitching_stats
        WHERE player_id=? AND level='MLB' AND is_postseason=0
    """, (player_id,), db_path=db_path)

    if pitching_career and pitching_career[0]["wins"] is not None:
        stats = pitching_career[0]
        stats["ip"] = round(stats.get("ip_outs", 0) / 3.0, 1)
        for stat_name, thresholds in CAREER_MILESTONES.get("pitching", {}).items():
            value = stats.get(stat_name, 0) or 0
            for threshold in thresholds:
                if value >= threshold * 0.90 and value < threshold:
                    remaining = threshold - value
                    stat_display = STAT_DISPLAY_NAMES.get(stat_name, stat_name)
                    if stat_name == "ip":
                        remaining = round(remaining, 1)
                    alerts.append({
                        "player_id": player_id,
                        "player_name": player_name,
                        "stat_name": stat_name,
                        "stat_display": stat_display,
                        "current_value": value,
                        "milestone": threshold,
                        "remaining": remaining,
                        "message": f"{player_name} needs {remaining} more {stat_display.lower()} "
                                   f"to reach {threshold:,}!"
                    })

    return alerts
