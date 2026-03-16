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
