"""Barcode extraction from image and PDF files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPdf import QPdfDocument

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
    """Convert each PDF page to an image via QPdfDocument and scan for barcodes.

    Args:
        path: Path to the PDF file.

    Returns:
        List of ScanResult, one per page.
    """
    doc = QPdfDocument(None)
    error = doc.load(str(path))
    if error != QPdfDocument.Error.None_:
        logger.error("QPdfDocument failed to load '%s': %s", path, error)
        return [ScanResult(error=f"Errore apertura PDF: {error}")]

    page_count = doc.pageCount()
    if page_count == 0:
        return [ScanResult(error="PDF vuoto o non leggibile.")]

    results: list[ScanResult] = []
    for page_num in range(page_count):
        page_size = doc.pagePointSize(page_num)
        scale = 400 / 72  # 400 dpi — match original scan resolution
        w = max(1, int(page_size.width() * scale))
        h = max(1, int(page_size.height() * scale))

        qimage = doc.render(page_num, QSize(w, h))
        if qimage.isNull():
            results.append(ScanResult(error=f"Impossibile renderizzare pagina {page_num + 1}", page=page_num + 1))
            continue

        # Composite onto white background (PDF may have transparent areas → black in RGB)
        bg = QImage(w, h, QImage.Format.Format_RGB888)
        bg.fill(0xFFFFFF)
        painter = QPainter(bg)
        painter.drawImage(0, 0, qimage)
        painter.end()

        bytes_per_line = bg.bytesPerLine()
        arr = np.frombuffer(bg.bits(), dtype=np.uint8).reshape((h, bytes_per_line))
        arr = arr[:, : w * 3].reshape((h, w, 3)).copy()
        pil_image = Image.fromarray(arr, "RGB")

        result = _scan_pil_image(pil_image, page=page_num + 1)
        results.append(result)
        logger.debug(
            "PDF page %d/%d — found %d barcode(s).", page_num + 1, page_count, len(result.barcodes)
        )

    doc.close()
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


# Fraction of the image height to scan first (barcode is in the top third of DDT docs)
_BARCODE_ROI_TOP_FRACTION = 1 / 3

# Symbol types accepted for DDT barcodes; Code128 is standard, QR added as fallback
_ACCEPTED_SYMBOLS = [ZBarSymbol.CODE128, ZBarSymbol.QRCODE]


def _scan_pil_image(pil_image: Image.Image, page: int) -> ScanResult:
    """Scan a PIL Image for barcodes using multiple pre-processing strategies.

    Scanning is attempted first on the top third of the image (where the
    barcode is located on Unieuro DDT documents), then on the full image
    as a fallback.

    Args:
        pil_image: PIL Image to scan.
        page: Page index for the result.

    Returns:
        ScanResult with detected barcodes.
    """
    w, h = pil_image.size
    roi_h = max(1, int(h * _BARCODE_ROI_TOP_FRACTION))
    roi_image = pil_image.crop((0, 0, w, roi_h))

    # First pass: top-third ROI only
    barcodes = _run_strategies(roi_image)

    # Second pass: full image (fallback — covers edge cases)
    if not barcodes:
        logger.debug("ROI pass found nothing on page %d — retrying full image.", page)
        barcodes = _run_strategies(pil_image)

    if not barcodes:
        logger.debug("No barcodes found on page %d.", page)

    return ScanResult(barcodes=barcodes, page=page)


def _run_strategies(pil_image: Image.Image) -> list[BarcodeResult]:
    """Try each pre-processing strategy in order and return the first non-empty result."""
    cv_image = _pil_to_cv2(pil_image)
    seen_values: set[str] = set()
    barcodes: list[BarcodeResult] = []

    for strategy in (
        _preprocess_original,
        _preprocess_grayscale,
        _preprocess_adaptive_threshold,
        _preprocess_enhanced,
    ):
        processed = strategy(cv_image)
        for rb in _decode_cv2(processed):
            if rb.value not in seen_values:
                seen_values.add(rb.value)
                barcodes.append(rb)

        if barcodes:
            logger.debug("Strategy '%s' found %d barcode(s).", strategy.__name__, len(barcodes))
            break

    return barcodes


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
# Decode — primary: cv2.barcode.BarcodeDetector, fallback: pyzbar
# ---------------------------------------------------------------------------

_cv_barcode_detector = cv2.barcode.BarcodeDetector()


def _decode_cv2(image: np.ndarray) -> list[BarcodeResult]:
    """Decode barcodes using OpenCV BarcodeDetector.

    Args:
        image: Grayscale or BGR numpy array.

    Returns:
        List of BarcodeResult.
    """
    return _decode_opencv(image)


_CROP_PADDING = 30  # px padding around detected barcode region before pyzbar decode


def _decode_opencv(image: np.ndarray) -> list[BarcodeResult]:
    """Detect barcode regions with OpenCV, then decode each crop with pyzbar.

    OpenCV BarcodeDetector is reliable at *locating* Code128 barcodes even
    when it cannot fully decode them. pyzbar is then run on the tight crop,
    where it performs much better than on the full-page image.
    """
    gray = image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    img_h, img_w = gray.shape[:2]

    try:
        _ok, decoded_info, points, decoded_type = _cv_barcode_detector.detectAndDecodeMulti(gray)
    except Exception as exc:
        logger.warning("cv2.BarcodeDetector error: %s", exc)
        return []

    if points is None or len(points) == 0:
        return []

    results: list[BarcodeResult] = []
    for i, pts in enumerate(points):
        xs, ys = pts[:, 0], pts[:, 1]
        bx = int(xs.min())
        by = int(ys.min())
        bw = int(xs.max()) - bx
        bh = int(ys.max()) - by

        # If OpenCV decoded it directly, use that value
        if decoded_info and i < len(decoded_info) and decoded_info[i]:
            btype = decoded_type[i] if decoded_type is not None and i < len(decoded_type) else "CODE_128"
            results.append(BarcodeResult(value=decoded_info[i], barcode_type=btype, bounding_box=(bx, by, bw, bh)))
            continue

        # OpenCV found but couldn't decode — crop and hand off to pyzbar
        x1 = max(0, bx - _CROP_PADDING)
        y1 = max(0, by - _CROP_PADDING)
        x2 = min(img_w, bx + bw + _CROP_PADDING)
        y2 = min(img_h, by + bh + _CROP_PADDING)
        crop = gray[y1:y2, x1:x2]

        for item in _pyzbar_decode_gray(crop):
            results.append(
                BarcodeResult(
                    value=item[0],
                    barcode_type=item[1],
                    bounding_box=(x1 + item[2], y1 + item[3], item[4], item[5]),
                )
            )

    return results


def _pyzbar_decode_gray(gray: np.ndarray) -> list[tuple]:
    """Run pyzbar on a grayscale array; returns list of (value, type, x, y, w, h)."""
    pil = Image.fromarray(gray)
    try:
        decoded = pyzbar.decode(pil, symbols=_ACCEPTED_SYMBOLS)
    except Exception as exc:
        logger.warning("pyzbar decode error: %s", exc)
        return []

    out = []
    for item in decoded:
        try:
            value = item.data.decode("utf-8")
        except UnicodeDecodeError:
            value = item.data.decode("latin-1", errors="replace")
        r = item.rect
        out.append((value, item.type, r.left, r.top, r.width, r.height))
    return out


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
