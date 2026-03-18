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
