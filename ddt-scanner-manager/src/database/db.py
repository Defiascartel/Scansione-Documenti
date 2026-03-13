"""Database connection and CRUD operations."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import bcrypt

from src.config import DB_PATH, DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD
from src.database.models import create_tables
from src.utils.logger import get_logger

logger = get_logger("database.db")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class User:
    id: int
    username: str
    role: str
    store_id: Optional[int]
    is_active: bool


@dataclass
class Store:
    id: int
    code: str
    name: str


@dataclass
class WatchedFolder:
    id: int
    store_id: int
    source_path: str
    dest_path: str
    folder_type: str
    is_active: bool


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Open and return a SQLite connection with row_factory set.

    Returns:
        SQLite connection with Row factory.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database() -> None:
    """Create tables and seed default admin user on first run."""
    with get_connection() as conn:
        create_tables(conn)
        _seed_admin(conn)


def _seed_admin(conn: sqlite3.Connection) -> None:
    """Insert default admin user if no users exist.

    Args:
        conn: Open SQLite connection.
    """
    row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
    if row[0] == 0:
        password_hash = bcrypt.hashpw(
            DEFAULT_ADMIN_PASSWORD.encode(), bcrypt.gensalt()
        ).decode()
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'admin')",
            (DEFAULT_ADMIN_USERNAME, password_hash),
        )
        conn.commit()
        logger.info("Default admin user created (username: %s).", DEFAULT_ADMIN_USERNAME)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate(username: str, password: str) -> Optional[User]:
    """Verify credentials and return the User if valid, else None.

    Args:
        username: Plaintext username.
        password: Plaintext password.

    Returns:
        User dataclass on success, None on failure.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role, store_id, is_active "
            "FROM users WHERE username = ?",
            (username,),
        ).fetchone()

    if row is None:
        logger.warning("Login attempt for unknown user '%s'.", username)
        return None

    if not row["is_active"]:
        logger.warning("Login attempt for disabled user '%s'.", username)
        return None

    if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        logger.warning("Wrong password for user '%s'.", username)
        return None

    logger.info("User '%s' authenticated successfully.", username)
    return User(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        store_id=row["store_id"],
        is_active=bool(row["is_active"]),
    )


# ---------------------------------------------------------------------------
# Users CRUD
# ---------------------------------------------------------------------------

def create_user(
    username: str,
    password: str,
    role: str = "operator",
    store_id: Optional[int] = None,
) -> int:
    """Create a new user.

    Args:
        username: Unique username.
        password: Plaintext password (will be hashed).
        role: 'admin' or 'operator'.
        store_id: Associated store id (required for operators).

    Returns:
        New user id.
    """
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role, store_id) VALUES (?, ?, ?, ?)",
            (username, password_hash, role, store_id),
        )
        conn.commit()
        logger.info("User '%s' created with role '%s'.", username, role)
        return cursor.lastrowid


def list_users() -> list[User]:
    """Return all users.

    Returns:
        List of User dataclasses.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, username, role, store_id, is_active FROM users"
        ).fetchall()
    return [
        User(id=r["id"], username=r["username"], role=r["role"],
             store_id=r["store_id"], is_active=bool(r["is_active"]))
        for r in rows
    ]


def update_user(
    user_id: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    role: Optional[str] = None,
    store_id: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> None:
    """Update mutable fields of a user.

    Args:
        user_id: Target user id.
        username: New username (optional).
        password: New plaintext password (optional, will be hashed).
        role: New role (optional).
        store_id: New store id (optional).
        is_active: New active state (optional).
    """
    fields: list[str] = []
    values: list = []

    if username is not None:
        fields.append("username = ?")
        values.append(username)
    if password is not None:
        fields.append("password_hash = ?")
        values.append(bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
    if role is not None:
        fields.append("role = ?")
        values.append(role)
    if store_id is not None:
        fields.append("store_id = ?")
        values.append(store_id)
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(int(is_active))

    if not fields:
        return

    values.append(user_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        logger.info("User id=%d updated.", user_id)


# ---------------------------------------------------------------------------
# Stores CRUD
# ---------------------------------------------------------------------------

def create_store(code: str, name: str) -> int:
    """Create a new store.

    Args:
        code: Unique store code (e.g. '001').
        name: Human-readable store name.

    Returns:
        New store id.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO stores (code, name) VALUES (?, ?)", (code, name)
        )
        conn.commit()
        logger.info("Store '%s' (%s) created.", name, code)
        return cursor.lastrowid


def list_stores() -> list[Store]:
    """Return all stores.

    Returns:
        List of Store dataclasses.
    """
    with get_connection() as conn:
        rows = conn.execute("SELECT id, code, name FROM stores").fetchall()
    return [Store(id=r["id"], code=r["code"], name=r["name"]) for r in rows]


def update_store(store_id: int, code: Optional[str] = None, name: Optional[str] = None) -> None:
    """Update a store's fields.

    Args:
        store_id: Target store id.
        code: New code (optional).
        name: New name (optional).
    """
    fields: list[str] = []
    values: list = []
    if code is not None:
        fields.append("code = ?")
        values.append(code)
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if not fields:
        return
    values.append(store_id)
    with get_connection() as conn:
        conn.execute(f"UPDATE stores SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()


def delete_store(store_id: int) -> None:
    """Delete a store by id.

    Args:
        store_id: Target store id.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM stores WHERE id = ?", (store_id,))
        conn.commit()
        logger.info("Store id=%d deleted.", store_id)


# ---------------------------------------------------------------------------
# Watched Folders CRUD
# ---------------------------------------------------------------------------

def add_watched_folder(store_id: int, source_path: str, dest_path: str, folder_type: str) -> int:
    """Add a monitored folder for a store.

    Args:
        store_id: Associated store id.
        source_path: Absolute path of the folder to watch (IN).
        dest_path: Absolute path of the destination folder (OUT).
        folder_type: Descriptive type (e.g. 'acquisti', 'resi').

    Returns:
        New watched_folder id.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO watched_folders (store_id, source_path, dest_path, folder_type) VALUES (?, ?, ?, ?)",
            (store_id, source_path, dest_path, folder_type),
        )
        conn.commit()
        return cursor.lastrowid


def list_watched_folders(store_id: int) -> list[WatchedFolder]:
    """Return all active watched folders for a store.

    Args:
        store_id: Target store id.

    Returns:
        List of WatchedFolder dataclasses.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, store_id, source_path, dest_path, folder_type, is_active "
            "FROM watched_folders WHERE store_id = ?",
            (store_id,),
        ).fetchall()
    return [
        WatchedFolder(
            id=r["id"], store_id=r["store_id"], source_path=r["source_path"],
            dest_path=r["dest_path"], folder_type=r["folder_type"],
            is_active=bool(r["is_active"])
        )
        for r in rows
    ]


def remove_watched_folder(folder_id: int) -> None:
    """Delete a watched folder entry.

    Args:
        folder_id: Target watched_folder id.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM watched_folders WHERE id = ?", (folder_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# Operation Log
# ---------------------------------------------------------------------------

def log_operation(
    user_id: int,
    store_id: int,
    source_path: str,
    dest_path: str,
    filename: str,
    barcodes: list[str],
    action: str,
) -> None:
    """Persist an operation record.

    Args:
        user_id: User who performed the action.
        store_id: Store the file belongs to.
        source_path: Original file directory.
        dest_path: Destination file directory.
        filename: File name.
        barcodes: List of confirmed barcode values.
        action: 'confirmed' or 'discarded'.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO operation_log "
            "(user_id, store_id, source_path, dest_path, filename, barcodes_json, action) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, store_id, source_path, dest_path, filename,
             json.dumps(barcodes), action),
        )
        conn.commit()


@dataclass
class OperationLogEntry:
    id: int
    username: str
    store_name: str
    filename: str
    action: str
    barcodes_json: str
    processed_at: str


def list_operation_log(
    store_id: Optional[int] = None,
    user_id: Optional[int] = None,
    limit: int = 500,
) -> list[OperationLogEntry]:
    """Return operation log entries with optional filters.

    Args:
        store_id: Filter by store (optional).
        user_id: Filter by user (optional).
        limit: Maximum number of rows to return.

    Returns:
        List of OperationLogEntry sorted newest-first.
    """
    query = (
        "SELECT ol.id, COALESCE(u.username, '?') AS username, "
        "COALESCE(s.name, '?') AS store_name, "
        "ol.filename, ol.action, ol.barcodes_json, ol.processed_at "
        "FROM operation_log ol "
        "LEFT JOIN users u ON ol.user_id = u.id "
        "LEFT JOIN stores s ON ol.store_id = s.id "
        "WHERE 1=1"
    )
    params: list = []
    if store_id is not None:
        query += " AND ol.store_id = ?"
        params.append(store_id)
    if user_id is not None:
        query += " AND ol.user_id = ?"
        params.append(user_id)
    query += " ORDER BY ol.processed_at DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        OperationLogEntry(
            id=r["id"],
            username=r["username"],
            store_name=r["store_name"],
            filename=r["filename"],
            action=r["action"],
            barcodes_json=r["barcodes_json"] or "[]",
            processed_at=r["processed_at"],
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read a setting value from the settings table.

    Args:
        key: Setting key.
        default: Value to return if the key does not exist.

    Returns:
        The setting value, or *default* if not found.
    """
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    """Insert or update a setting in the settings table.

    Args:
        key: Setting key.
        value: Setting value.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
