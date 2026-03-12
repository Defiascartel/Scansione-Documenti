"""SQLite database schema creation."""

import sqlite3
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger("database.models")

DDL = """
CREATE TABLE IF NOT EXISTS stores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    UNIQUE NOT NULL,
    name        TEXT    NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'operator',
    store_id      INTEGER REFERENCES stores(id),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watched_folders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id    INTEGER NOT NULL REFERENCES stores(id),
    source_path TEXT    NOT NULL,
    folder_type TEXT    NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS operation_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER REFERENCES users(id),
    store_id       INTEGER REFERENCES stores(id),
    source_path    TEXT    NOT NULL,
    dest_path      TEXT    NOT NULL,
    filename       TEXT    NOT NULL,
    barcodes_json  TEXT,
    action         TEXT    NOT NULL,
    processed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all application tables if they do not exist.

    Args:
        conn: Open SQLite connection.
    """
    conn.executescript(DDL)
    conn.commit()
    logger.debug("Database tables ensured.")
