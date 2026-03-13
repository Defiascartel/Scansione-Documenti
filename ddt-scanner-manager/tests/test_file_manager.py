"""Unit tests for file_manager utilities."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from src.utils.file_manager import (
    _convert_if_needed,
    move_to_confirmed,
    move_to_discarded,
)

_TODAY = datetime.now().strftime("%Y%m%d")


def _mock_get_setting(key: str, default: str | None = None) -> str | None:
    """Provide default setting values for tests without hitting the DB."""
    defaults = {"output_format": "same", "json_sidecar_enabled": "1"}
    return defaults.get(key, default)


@pytest.fixture(autouse=True)
def _mock_output_format():
    """Default settings so existing tests don't hit the DB."""
    with patch("src.utils.file_manager.get_setting", side_effect=_mock_get_setting):
        yield


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
    assert dest.parent.name == _TODAY
    assert dest.parent.parent.name == "acquisti_confermati"
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
    assert dest.parent.name == _TODAY
    assert dest.parent.parent.name == "acquisti_scartati"
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

    # Pre-create a file with the same name in _confermati/YYYYMMDD
    confirmed_dir = tmp_path / "resi_confermati" / _TODAY
    confirmed_dir.mkdir(parents=True)
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
    assert (tmp_path / "altro_confermati" / _TODAY).is_dir()
    assert dest.exists()


# ---------------------------------------------------------------------------
# Format conversion tests
# ---------------------------------------------------------------------------

def _make_test_image(path: Path, fmt: str = "JPEG") -> Path:
    """Create a small real image file for conversion tests."""
    img = Image.new("RGB", (100, 50), color="red")
    img.save(path, format=fmt)
    return path


def test_convert_same_returns_unchanged(tmp_path: Path):
    f = _make_test_image(tmp_path / "img.jpg")
    result = _convert_if_needed(f, "same")
    assert result == f
    assert result.exists()


def test_convert_jpg_to_pdf(tmp_path: Path):
    f = _make_test_image(tmp_path / "img.jpg")
    result = _convert_if_needed(f, "pdf")
    assert result.suffix == ".pdf"
    assert result.exists()
    assert not f.exists()  # original removed


def test_convert_jpg_to_tif(tmp_path: Path):
    f = _make_test_image(tmp_path / "img.jpg")
    result = _convert_if_needed(f, "tif")
    assert result.suffix == ".tif"
    assert result.exists()
    assert not f.exists()


def test_convert_tif_to_pdf(tmp_path: Path):
    f = _make_test_image(tmp_path / "img.tif", fmt="TIFF")
    result = _convert_if_needed(f, "pdf")
    assert result.suffix == ".pdf"
    assert result.exists()


def test_convert_pdf_skipped_when_already_pdf(tmp_path: Path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    result = _convert_if_needed(f, "pdf")
    assert result == f  # no conversion


def test_convert_tif_skipped_when_already_tif(tmp_path: Path):
    f = _make_test_image(tmp_path / "img.tif", fmt="TIFF")
    result = _convert_if_needed(f, "tif")
    assert result == f  # no conversion


def test_move_to_confirmed_with_format_conversion(tmp_path: Path):
    """Integration: move_to_confirmed should convert when setting is set."""
    source_dir = tmp_path / "acquisti"
    source_dir.mkdir()
    f = _make_test_image(source_dir / "ddt.jpg")

    def _pdf_settings(key: str, default: str | None = None) -> str | None:
        if key == "output_format":
            return "pdf"
        return _mock_get_setting(key, default)

    with patch("src.utils.file_manager.get_setting", side_effect=_pdf_settings):
        dest = move_to_confirmed(f, barcodes=["999"], username="u", store_id=1)

    assert dest.suffix == ".pdf"
    assert dest.exists()
