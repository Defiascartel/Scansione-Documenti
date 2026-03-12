"""Unit tests for file_manager utilities."""

import json
from pathlib import Path

import pytest

from src.utils.file_manager import move_to_confirmed, move_to_discarded


@pytest.fixture()
def scan_file(tmp_path: Path) -> Path:
    """Create a fake scanned image in a source folder."""
    source_dir = tmp_path / "acquisti"
    source_dir.mkdir()
    f = source_dir / "ddt_001.jpg"
    f.write_bytes(b"\xff\xd8\xff")
    return f


def test_move_to_confirmed_moves_file(scan_file: Path):
    dest = move_to_confirmed(scan_file, barcodes=["123456"], username="mario", store_id=1)
    assert dest.exists()
    assert dest.parent.name == "acquisti_confermati"
    assert not scan_file.exists()


def test_move_to_confirmed_creates_sidecar(scan_file: Path):
    dest = move_to_confirmed(scan_file, barcodes=["ABC", "DEF"], username="mario", store_id=1)
    sidecar = dest.with_suffix(".json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["barcodes"] == ["ABC", "DEF"]
    assert data["operator"] == "mario"
    assert data["action"] == "confirmed"
    assert data["store_id"] == 1


def test_move_to_discarded_moves_file(scan_file: Path):
    dest = move_to_discarded(scan_file, username="luigi", store_id=2)
    assert dest.exists()
    assert dest.parent.name == "acquisti_scartati"
    assert not scan_file.exists()


def test_move_to_discarded_creates_sidecar(scan_file: Path):
    dest = move_to_discarded(scan_file, username="luigi", store_id=2)
    sidecar = dest.with_suffix(".json")
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert data["action"] == "discarded"
    assert data["barcodes"] == []


def test_collision_resolved_with_timestamp(tmp_path: Path):
    source_dir = tmp_path / "resi"
    source_dir.mkdir()

    # Pre-create a file with the same name in _confermati
    confirmed_dir = tmp_path / "resi_confermati"
    confirmed_dir.mkdir()
    (confirmed_dir / "ddt.jpg").write_bytes(b"existing")

    f = source_dir / "ddt.jpg"
    f.write_bytes(b"\xff\xd8\xff")

    dest = move_to_confirmed(f, barcodes=[], username="test", store_id=1)
    # Name should differ from original due to timestamp suffix
    assert dest.name != "ddt.jpg"
    assert dest.exists()


def test_missing_source_raises(tmp_path: Path):
    missing = tmp_path / "acquisti" / "ghost.jpg"
    with pytest.raises(FileNotFoundError):
        move_to_confirmed(missing, barcodes=[], username="u", store_id=1)


def test_destination_dir_created_automatically(tmp_path: Path):
    source_dir = tmp_path / "altro"
    source_dir.mkdir()
    f = source_dir / "doc.png"
    f.write_bytes(b"\x89PNG")

    dest = move_to_confirmed(f, barcodes=[], username="u", store_id=1)
    assert (tmp_path / "altro_confermati").is_dir()
    assert dest.exists()
