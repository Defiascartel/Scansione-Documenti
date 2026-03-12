"""Unit tests for FolderWatcher."""

import time
from pathlib import Path

import pytest

from src.watcher.folder_watcher import FILE_SETTLE_DELAY, FolderWatcher


@pytest.fixture()
def watcher():
    w = FolderWatcher()
    yield w
    w.stop()


def test_add_and_remove_folder(watcher, tmp_path):
    watcher.add_folder(tmp_path, "acquisti", store_id=1)
    assert len(watcher._folders) == 1
    watcher.remove_folder(tmp_path)
    assert len(watcher._folders) == 0


def test_duplicate_folder_not_added(watcher, tmp_path):
    watcher.add_folder(tmp_path, "acquisti", store_id=1)
    watcher.add_folder(tmp_path, "acquisti", store_id=1)
    assert len(watcher._folders) == 1


def test_queue_size_starts_at_zero(watcher):
    assert watcher.queue_size() == 0


def test_get_returns_none_when_empty(watcher):
    assert watcher.get() is None


def test_polling_picks_up_existing_file(tmp_path):
    """Files already present when watcher starts should be queued by polling."""
    img = tmp_path / "scan001.jpg"
    img.write_bytes(b"\xff\xd8\xff")  # minimal JPEG header

    w = FolderWatcher()
    w.add_folder(tmp_path, "resi", store_id=2)
    w.start()

    # Poll thread fires after POLLING_INTERVAL; force a direct poll instead
    w._poll_folder(w._folders[0])

    event = w.get(timeout=2)
    w.stop()

    assert event is not None
    assert event.path == img
    assert event.folder_type == "resi"
    assert event.store_id == 2


def test_polling_ignores_unsupported_extensions(tmp_path):
    txt = tmp_path / "readme.txt"
    txt.write_text("hello")

    w = FolderWatcher()
    w.add_folder(tmp_path, "acquisti", store_id=1)
    w._poll_folder(w._folders[0])

    assert w.get() is None
    w.stop()


def test_polling_ignores_already_seen_files(tmp_path):
    img = tmp_path / "dup.png"
    img.write_bytes(b"\x89PNG")

    w = FolderWatcher()
    w.add_folder(tmp_path, "acquisti", store_id=1)

    # First poll — should queue
    w._poll_folder(w._folders[0])
    assert w.queue_size() == 1

    # Second poll — should NOT queue again
    w._poll_folder(w._folders[0])
    assert w.queue_size() == 1

    w.stop()


def test_polling_handles_missing_folder(tmp_path):
    missing = tmp_path / "nonexistent"
    w = FolderWatcher()
    w.add_folder(missing, "acquisti", store_id=1)
    # Should not raise
    w._poll_folder(w._folders[0])
    w.stop()
