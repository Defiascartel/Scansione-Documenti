"""Unit tests for the barcode reader module."""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image, ImageDraw

from src.ocr.barcode_reader import (
    BarcodeResult,
    ScanResult,
    _decode_cv2,
    _pil_to_cv2,
    _preprocess_adaptive_threshold,
    _preprocess_enhanced,
    _preprocess_grayscale,
    _preprocess_original,
    read_barcodes,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _white_image(width: int = 200, height: int = 100) -> Image.Image:
    """Create a plain white PIL image."""
    return Image.new("RGB", (width, height), color=(255, 255, 255))


# ---------------------------------------------------------------------------
# read_barcodes input validation
# ---------------------------------------------------------------------------

def test_unsupported_extension_raises(tmp_path: Path):
    fake = tmp_path / "test.xyz"
    fake.write_bytes(b"data")
    with pytest.raises(ValueError, match="Unsupported file extension"):
        read_barcodes(fake)


def test_missing_file_returns_error(tmp_path: Path):
    missing = tmp_path / "missing.jpg"
    results = read_barcodes(missing)
    assert len(results) == 1
    assert results[0].error is not None


# ---------------------------------------------------------------------------
# Pre-processing pipelines (smoke tests — no crash)
# ---------------------------------------------------------------------------

def test_preprocess_original_returns_array():
    img = _white_image()
    cv = _pil_to_cv2(img)
    out = _preprocess_original(cv)
    assert out.shape == cv.shape


def test_preprocess_grayscale_is_2d():
    img = _white_image()
    cv = _pil_to_cv2(img)
    out = _preprocess_grayscale(cv)
    assert len(out.shape) == 2


def test_preprocess_adaptive_threshold_is_2d():
    img = _white_image()
    cv = _pil_to_cv2(img)
    out = _preprocess_adaptive_threshold(cv)
    assert len(out.shape) == 2


def test_preprocess_enhanced_is_2d():
    img = _white_image()
    cv = _pil_to_cv2(img)
    out = _preprocess_enhanced(cv)
    assert len(out.shape) == 2


# ---------------------------------------------------------------------------
# pil_to_cv2
# ---------------------------------------------------------------------------

def test_pil_to_cv2_rgba():
    """RGBA images should be converted without error."""
    rgba = Image.new("RGBA", (50, 50), (10, 20, 30, 128))
    cv = _pil_to_cv2(rgba)
    assert cv.shape == (50, 50, 3)


def test_pil_to_cv2_palette():
    """Palette images should be converted without error."""
    pal = Image.new("P", (50, 50))
    cv = _pil_to_cv2(pal)
    assert cv.shape[2] == 3


# ---------------------------------------------------------------------------
# _decode_cv2 with mocked pyzbar
# ---------------------------------------------------------------------------

def _make_mock_decoded(value: bytes, barcode_type: str):
    mock = MagicMock()
    mock.data = value
    mock.type = barcode_type
    rect = MagicMock()
    rect.left, rect.top, rect.width, rect.height = 10, 20, 100, 40
    mock.rect = rect
    return mock


def test_decode_cv2_returns_barcode_results():
    img = _white_image()
    cv = _pil_to_cv2(img)

    mock_item = _make_mock_decoded(b"123456789", "CODE128")
    with patch("src.ocr.barcode_reader.pyzbar.decode", return_value=[mock_item]):
        results = _decode_cv2(cv)

    assert len(results) == 1
    assert results[0].value == "123456789"
    assert results[0].barcode_type == "CODE128"
    assert results[0].bounding_box == (10, 20, 100, 40)


def test_decode_cv2_deduplicates_via_caller():
    """_decode_cv2 itself does NOT deduplicate; dedup is in _scan_pil_image."""
    img = _white_image()
    cv = _pil_to_cv2(img)

    mock_item = _make_mock_decoded(b"DUP", "EAN13")
    with patch("src.ocr.barcode_reader.pyzbar.decode", return_value=[mock_item, mock_item]):
        results = _decode_cv2(cv)

    # Two identical items returned by pyzbar → _decode_cv2 returns both
    assert len(results) == 2


def test_decode_cv2_handles_latin1_fallback():
    img = _white_image()
    cv = _pil_to_cv2(img)

    mock_item = _make_mock_decoded(b"\xff\xfe", "QRCODE")
    with patch("src.ocr.barcode_reader.pyzbar.decode", return_value=[mock_item]):
        results = _decode_cv2(cv)

    assert len(results) == 1  # should not raise


def test_decode_cv2_pyzbar_exception_returns_empty():
    img = _white_image()
    cv = _pil_to_cv2(img)

    with patch("src.ocr.barcode_reader.pyzbar.decode", side_effect=Exception("boom")):
        results = _decode_cv2(cv)

    assert results == []


# ---------------------------------------------------------------------------
# _scan_pil_image deduplication
# ---------------------------------------------------------------------------

def test_scan_pil_image_deduplicates():
    from src.ocr.barcode_reader import _scan_pil_image

    img = _white_image()
    mock_item = _make_mock_decoded(b"UNIQUE", "CODE128")

    # Return the same barcode from every strategy call
    with patch("src.ocr.barcode_reader.pyzbar.decode", return_value=[mock_item]):
        result = _scan_pil_image(img, page=0)

    # Despite multiple strategies, dedup keeps only one entry
    assert len(result.barcodes) == 1
    assert result.barcodes[0].value == "UNIQUE"


# ---------------------------------------------------------------------------
# PDF handling
# ---------------------------------------------------------------------------

def test_pdf_without_pdf2image_returns_error(tmp_path: Path):
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with patch.dict("sys.modules", {"pdf2image": None}):
        results = read_barcodes(pdf)

    assert len(results) == 1
    assert results[0].error is not None


def test_pdf_conversion_error_returns_error(tmp_path: Path):
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"not a real pdf")

    mock_pdf2image = MagicMock()
    mock_pdf2image.convert_from_path.side_effect = Exception("conversion failed")

    with patch.dict("sys.modules", {"pdf2image": mock_pdf2image}):
        results = read_barcodes(pdf)

    assert len(results) == 1
    assert results[0].error is not None


def test_pdf_multi_page_returns_one_result_per_page(tmp_path: Path):
    pdf = tmp_path / "multi.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    pages = [_white_image(), _white_image(), _white_image()]
    mock_pdf2image = MagicMock()
    mock_pdf2image.convert_from_path.return_value = pages

    with patch.dict("sys.modules", {"pdf2image": mock_pdf2image}):
        with patch("src.ocr.barcode_reader.pyzbar.decode", return_value=[]):
            results = read_barcodes(pdf)

    assert len(results) == 3
    assert [r.page for r in results] == [1, 2, 3]


# ---------------------------------------------------------------------------
# ScanResult and BarcodeResult dataclasses
# ---------------------------------------------------------------------------

def test_scan_result_defaults():
    sr = ScanResult()
    assert sr.barcodes == []
    assert sr.page == 0
    assert sr.error is None


def test_barcode_result_fields():
    br = BarcodeResult(value="ABC", barcode_type="CODE39", bounding_box=(0, 0, 50, 20))
    assert br.value == "ABC"
    assert br.barcode_type == "CODE39"
    assert br.bounding_box == (0, 0, 50, 20)
