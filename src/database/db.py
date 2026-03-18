"""
Front Office - Database Connection
SQLite connection management and query helpers.
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "front_office.db"


def get_connection(db_path: str = None) -> sqlite3.Connection:
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = None):
    from .schema import SCHEMA_SQL
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def migrate_add_eye_rating(db_path: str = None):
    """Add eye_rating, eye_potential, fielding stats, and postseason flags."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(players)")
    columns = {row[1] for row in cursor.fetchall()}

    if "eye_rating" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN eye_rating INTEGER NOT NULL DEFAULT 50")
    if "eye_potential" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN eye_potential INTEGER NOT NULL DEFAULT 50")

    # Add fielding columns to batting_lines
    cursor.execute("PRAGMA table_info(batting_lines)")
    bl_columns = {row[1] for row in cursor.fetchall()}
    for col in ["putouts", "assists", "errors"]:
        if col not in bl_columns:
            conn.execute(f"ALTER TABLE batting_lines ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")

    # Add postseason flag to stats tables
    cursor.execute("PRAGMA table_info(batting_stats)")
    bs_columns = {row[1] for row in cursor.fetchall()}
    if "is_postseason" not in bs_columns:
        conn.execute("ALTER TABLE batting_stats ADD COLUMN is_postseason INTEGER NOT NULL DEFAULT 0")

    cursor.execute("PRAGMA table_info(pitching_stats)")
    ps_columns = {row[1] for row in cursor.fetchall()}
    if "is_postseason" not in ps_columns:
        conn.execute("ALTER TABLE pitching_stats ADD COLUMN is_postseason INTEGER NOT NULL DEFAULT 0")

    conn.commit()
    conn.close()


def migrate_add_broadcast_stadium_columns(db_path: str = None):
    """Add broadcast deal and stadium upgrade columns if they don't exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Check if columns exist
    cursor.execute("PRAGMA table_info(teams)")
    columns = {row[1] for row in cursor.fetchall()}

    migrations = [
        ("broadcast_deal_type", "TEXT DEFAULT 'standard'"),
        ("broadcast_deal_value", "INTEGER DEFAULT 0"),
        ("broadcast_deal_years_remaining", "INTEGER DEFAULT 3"),
        ("stadium_built_year", "INTEGER DEFAULT 2000"),
        ("stadium_condition", "INTEGER DEFAULT 85"),
        ("stadium_upgrades_json", "TEXT DEFAULT '{}'"),
        ("stadium_revenue_boost", "INTEGER DEFAULT 0"),
    ]

    for col_name, col_type in migrations:
        if col_name not in columns:
            conn.execute(f"ALTER TABLE teams ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()


def migrate_add_player_development_columns(db_path: str = None):
    """Add is_bust and is_late_bloomer columns for non-linear development."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(players)")
    columns = {row[1] for row in cursor.fetchall()}

    if "is_bust" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN is_bust INTEGER NOT NULL DEFAULT 0")
    if "is_late_bloomer" not in columns:
        conn.execute("ALTER TABLE players ADD COLUMN is_late_bloomer INTEGER NOT NULL DEFAULT 0")

    conn.commit()
    conn.close()


def migrate_add_proactive_message_log(db_path: str = None):
    """Add proactive_message_log table for AI character messaging cooldowns."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS proactive_message_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_type TEXT NOT NULL,
            character_id TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            team_id INTEGER NOT NULL,
            game_date TEXT NOT NULL,
            cooldown_until TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (team_id) REFERENCES teams(id)
        );
        CREATE INDEX IF NOT EXISTS idx_proactive_msg_cooldown
            ON proactive_message_log(character_type, character_id, trigger_type, team_id);
    """)
    conn.commit()
    conn.close()


def query(sql: str, params: tuple = (), db_path: str = None) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(sql, params).fetchall()
    result = [dict(r) for r in rows]
    conn.close()
    return result


def execute(sql: str, params: tuple = (), db_path: str = None) -> int:
    conn = get_connection(db_path)
    cursor = conn.execute(sql, params)
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id


def executemany(sql: str, params_list: list, db_path: str = None):
    conn = get_connection(db_path)
    conn.executemany(sql, params_list)
    conn.commit()
    conn.close()


def migrate_phase1_gap_closing(db_path: str = None):
    """Add new tables and columns for Phase 1 gap-closing features.

    Adds: player_strategy, matchup_stats, pitch_log tables,
    height_inches column, rating_scale setting.
    """
    import random
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # New tables (CREATE IF NOT EXISTS is safe to re-run)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS player_strategy (
            player_id INTEGER PRIMARY KEY,
            steal_aggression INTEGER NOT NULL DEFAULT 3,
            bunt_tendency INTEGER NOT NULL DEFAULT 3,
            hit_and_run INTEGER NOT NULL DEFAULT 3,
            pitch_count_limit INTEGER DEFAULT NULL,
            FOREIGN KEY (player_id) REFERENCES players(id)
        );
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
            result TEXT,
            zone INTEGER,
            count_balls INTEGER,
            count_strikes INTEGER,
            outs INTEGER,
            runners_on INTEGER,
            score_diff INTEGER,
            season INTEGER,
            FOREIGN KEY (game_id) REFERENCES schedule(id),
            FOREIGN KEY (pitcher_id) REFERENCES players(id),
            FOREIGN KEY (batter_id) REFERENCES players(id)
        );
        CREATE INDEX IF NOT EXISTS idx_matchup_stats_batter ON matchup_stats(batter_id, season);
        CREATE INDEX IF NOT EXISTS idx_matchup_stats_pitcher ON matchup_stats(pitcher_id, season);
        CREATE INDEX IF NOT EXISTS idx_pitch_log_pitcher ON pitch_log(pitcher_id, season);
        CREATE INDEX IF NOT EXISTS idx_pitch_log_batter ON pitch_log(batter_id, season);
        CREATE INDEX IF NOT EXISTS idx_pitch_log_game ON pitch_log(game_id);
    """)

    # Add height_inches to players if missing
    cursor.execute("PRAGMA table_info(players)")
    player_cols = {row[1] for row in cursor.fetchall()}
    if "height_inches" not in player_cols:
        conn.execute("ALTER TABLE players ADD COLUMN height_inches INTEGER DEFAULT NULL")
        # Seed heights for existing players based on position
        HEIGHT_RANGES = {
            'C': (70, 74), '1B': (72, 77), '2B': (68, 73), '3B': (72, 77),
            'SS': (68, 73), 'LF': (70, 76), 'CF': (70, 76), 'RF': (70, 76),
            'DH': (71, 76), 'SP': (72, 78), 'RP': (72, 78),
        }
        players = conn.execute("SELECT id, position FROM players WHERE height_inches IS NULL").fetchall()
        for p in players:
            pos = p[1] if p[1] in HEIGHT_RANGES else 'RF'
            low, high = HEIGHT_RANGES[pos]
            height = random.randint(low, high)
            conn.execute("UPDATE players SET height_inches = ? WHERE id = ?", (height, p[0]))

    # Add rating_scale to game_state if missing
    cursor.execute("PRAGMA table_info(game_state)")
    gs_cols = {row[1] for row in cursor.fetchall()}
    if "rating_scale" not in gs_cols:
        conn.execute("ALTER TABLE game_state ADD COLUMN rating_scale TEXT NOT NULL DEFAULT '20-80'")

    conn.commit()
    conn.close()


def migrate_add_beat_writers_articles_fan_sentiment(db_path: str = None):
    """Add beat_writers, articles, and fan_sentiment tables if they don't exist."""
    conn = get_connection(db_path)
    conn.executescript("""
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
    """)

    # Add trust_in_gm column if missing from existing fan_sentiment table
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(fan_sentiment)")
    fs_cols = {row[1] for row in cursor.fetchall()}
    for col, col_type in [
        ("trust_in_gm", "INTEGER NOT NULL DEFAULT 50"),
        ("top_concern", "TEXT"),
        ("reaction_text", "TEXT"),
    ]:
        if col not in fs_cols:
            try:
                conn.execute(f"ALTER TABLE fan_sentiment ADD COLUMN {col} {col_type}")
            except Exception:
                pass

    conn.commit()
    conn.close()
