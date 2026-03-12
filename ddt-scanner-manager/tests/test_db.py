"""Unit tests for database CRUD operations."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

import src.config as config_module


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path):
    """Redirect DB_PATH to a temporary file for each test."""
    db_file = tmp_path / "test.db"
    with patch.object(config_module, "DB_PATH", db_file):
        # Re-import db module so it picks up the patched path
        import importlib
        import src.database.db as db_module
        importlib.reload(db_module)
        db_module.initialize_database()
        yield db_module


def test_default_admin_created(isolated_db):
    users = isolated_db.list_users()
    assert any(u.username == config_module.DEFAULT_ADMIN_USERNAME for u in users)


def test_authenticate_success(isolated_db):
    user = isolated_db.authenticate(
        config_module.DEFAULT_ADMIN_USERNAME,
        config_module.DEFAULT_ADMIN_PASSWORD,
    )
    assert user is not None
    assert user.role == "admin"


def test_authenticate_wrong_password(isolated_db):
    result = isolated_db.authenticate(config_module.DEFAULT_ADMIN_USERNAME, "wrong")
    assert result is None


def test_authenticate_unknown_user(isolated_db):
    result = isolated_db.authenticate("nobody", "pass")
    assert result is None


def test_create_and_list_store(isolated_db):
    isolated_db.create_store("001", "Bologna Centro")
    stores = isolated_db.list_stores()
    assert len(stores) == 1
    assert stores[0].code == "001"
    assert stores[0].name == "Bologna Centro"


def test_create_operator_user(isolated_db):
    isolated_db.create_store("001", "Test Store")
    stores = isolated_db.list_stores()
    store_id = stores[0].id

    isolated_db.create_user("operatore1", "pass123", role="operator", store_id=store_id)
    user = isolated_db.authenticate("operatore1", "pass123")
    assert user is not None
    assert user.role == "operator"
    assert user.store_id == store_id


def test_watched_folders_crud(isolated_db):
    isolated_db.create_store("001", "Test")
    store_id = isolated_db.list_stores()[0].id

    fid = isolated_db.add_watched_folder(store_id, r"\\server\scansioni\001\acquisti",
                                         r"\\server\scansioni\001\acquisti_out", "acquisti")
    folders = isolated_db.list_watched_folders(store_id)
    assert len(folders) == 1
    assert folders[0].folder_type == "acquisti"
    assert folders[0].dest_path == r"\\server\scansioni\001\acquisti_out"

    isolated_db.remove_watched_folder(fid)
    assert isolated_db.list_watched_folders(store_id) == []
