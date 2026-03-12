"""Barcode extraction from image and PDF files."""

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol

from src.utils.logger import get_logger

logger = get_logger("ocr.barcode_reader")

# Supported input extensions
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".pdf"}


@dataclass
class BarcodeResult:
    """A single decoded barcode."""

    value: str
    barcode_type: str
    bounding_box: tuple[int, int, int, int]  # (left, top, width, height)


@dataclass
class ScanResult:
    """Result of scanning one image/page."""

    barcodes: list[BarcodeResult] = field(default_factory=list)
    page: int = 0
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def read_barcodes(file_path: str | Path) -> list[ScanResult]:
    """Extract barcodes from an image or PDF file.

    Supports jpg, jpeg, png, tiff, bmp, pdf.
    For PDFs every page is processed; results are returned per-page.

    Args:
        file_path: Path to the file to scan.

    Returns:
        List of ScanResult (one per page/image).
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {ext}")

    if ext == ".pdf":
        return _scan_pdf(path)
    else:
        return [_scan_image_file(path, page=0)]


# ---------------------------------------------------------------------------
# PDF handling
# ---------------------------------------------------------------------------

def _scan_pdf(path: Path) -> list[ScanResult]:
    """Convert each PDF page to an image and scan for barcodes.

    Args:
        path: Path to the PDF file.

    Returns:
        List of ScanResult, one per page.
    """
    try:
        import pdf2image  # optional dependency; imported lazily
    except ImportError:
        logger.error("pdf2image not installed — cannot process PDF files.")
        return [ScanResult(error="pdf2image non installato. Installare con: pip install pdf2image")]

    try:
        pages = pdf2image.convert_from_path(str(path), dpi=200)
    except Exception as exc:
        logger.error("Failed to convert PDF '%s': %s", path, exc)
        return [ScanResult(error=f"Errore conversione PDF: {exc}")]

    results: list[ScanResult] = []
    for page_num, pil_image in enumerate(pages, start=1):
        result = _scan_pil_image(pil_image, page=page_num)
        results.append(result)
        logger.debug("PDF page %d/%d — found %d barcode(s).", page_num, len(pages), len(result.barcodes))

    return results


# ---------------------------------------------------------------------------
# Image scanning
# ---------------------------------------------------------------------------

def _scan_image_file(path: Path, page: int) -> ScanResult:
    """Load an image file and scan it for barcodes.

    Args:
        path: Path to the image file.
        page: Page index (0 for single-image files).

    Returns:
        ScanResult with detected barcodes.
    """
    try:
        pil_image = Image.open(path)
    except Exception as exc:
        logger.error("Cannot open image '%s': %s", path, exc)
        return ScanResult(error=f"Impossibile aprire l'immagine: {exc}")

    return _scan_pil_image(pil_image, page=page)


def _scan_pil_image(pil_image: Image.Image, page: int) -> ScanResult:
    """Scan a PIL Image for barcodes using multiple pre-processing strategies.

    Args:
        pil_image: PIL Image to scan.
        page: Page index for the result.

    Returns:
        ScanResult with detected barcodes.
    """
    # Convert PIL → OpenCV (BGR)
    cv_image = _pil_to_cv2(pil_image)

    barcodes: list[BarcodeResult] = []
    seen_values: set[str] = set()

    # Try each pre-processing strategy in order; stop when barcodes are found
    for strategy in (_preprocess_original, _preprocess_grayscale,
                     _preprocess_adaptive_threshold, _preprocess_enhanced):
        processed = strategy(cv_image)
        raw_barcodes = _decode_cv2(processed)

        for rb in raw_barcodes:
            if rb.value not in seen_values:
                seen_values.add(rb.value)
                barcodes.append(rb)

        if barcodes:
            logger.debug("Strategy '%s' found %d barcode(s).", strategy.__name__, len(barcodes))
            break

    if not barcodes:
        logger.debug("No barcodes found on page %d.", page)

    return ScanResult(barcodes=barcodes, page=page)


# ---------------------------------------------------------------------------
# Pre-processing strategies
# ---------------------------------------------------------------------------

def _preprocess_original(image: np.ndarray) -> np.ndarray:
    """Return the image as-is (already BGR)."""
    return image


def _preprocess_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert to grayscale."""
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _preprocess_adaptive_threshold(image: np.ndarray) -> np.ndarray:
    """Grayscale + adaptive threshold to handle uneven illumination."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )


def _preprocess_enhanced(image: np.ndarray) -> np.ndarray:
    """Sharpen + OTSU threshold for low-contrast scans."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Sharpen with unsharp mask
    blurred = cv2.GaussianBlur(gray, (0, 0), 3)
    sharpened = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)
    _, binary = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


# ---------------------------------------------------------------------------
# Decode with pyzbar
# ---------------------------------------------------------------------------

def _decode_cv2(image: np.ndarray) -> list[BarcodeResult]:
    """Run pyzbar on a cv2 image array.

    Args:
        image: Grayscale or BGR numpy array.

    Returns:
        List of BarcodeResult.
    """
    # pyzbar works best with a PIL image
    if len(image.shape) == 2:
        pil = Image.fromarray(image)
    else:
        pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

    try:
        decoded = pyzbar.decode(pil)
    except Exception as exc:
        logger.warning("pyzbar decode error: %s", exc)
        return []

    results: list[BarcodeResult] = []
    for item in decoded:
        try:
            value = item.data.decode("utf-8")
        except UnicodeDecodeError:
            value = item.data.decode("latin-1", errors="replace")

        rect = item.rect
        results.append(
            BarcodeResult(
                value=value,
                barcode_type=item.type,
                bounding_box=(rect.left, rect.top, rect.width, rect.height),
            )
        )

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
    """Convert a PIL Image to an OpenCV BGR numpy array.

    Args:
        pil_image: Source PIL Image.

    Returns:
        BGR numpy array.
    """
    # Ensure RGB mode (handles RGBA, palette, etc.)
    rgb = pil_image.convert("RGB")
    arr = np.array(rgb)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
