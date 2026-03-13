"""Shared PDF page rendering via QPdfDocument."""

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtPdf import QPdfDocument

from src.utils.logger import get_logger

logger = get_logger("utils.pdf_renderer")

_PDF_BASE_DPI = 72  # 1 PDF point = 1/72 inch


def render_page_to_qimage(
    doc: QPdfDocument, page_num: int, dpi: int = 150,
) -> Optional[QImage]:
    """Render a single PDF page to a white-background QImage.

    Args:
        doc: Already-loaded QPdfDocument.
        page_num: Zero-based page index.
        dpi: Target rendering resolution.

    Returns:
        RGB888 QImage composited onto white, or *None* on failure.
    """
    page_size = doc.pagePointSize(page_num)
    scale = dpi / _PDF_BASE_DPI
    w = max(1, int(page_size.width() * scale))
    h = max(1, int(page_size.height() * scale))

    rendered = doc.render(page_num, QSize(w, h))
    if rendered.isNull():
        return None

    bg = QImage(w, h, QImage.Format.Format_RGB888)
    bg.fill(0xFFFFFF)
    painter = QPainter(bg)
    painter.drawImage(0, 0, rendered)
    painter.end()
    return bg


def render_page_to_pil(
    doc: QPdfDocument, page_num: int, dpi: int = 300,
) -> Optional[Image.Image]:
    """Render a single PDF page to a PIL RGB Image.

    Args:
        doc: Already-loaded QPdfDocument.
        page_num: Zero-based page index.
        dpi: Target rendering resolution.

    Returns:
        PIL RGB Image, or *None* on failure.
    """
    qimage = render_page_to_qimage(doc, page_num, dpi)
    if qimage is None:
        return None

    w, h = qimage.width(), qimage.height()
    bpl = qimage.bytesPerLine()
    arr = np.frombuffer(qimage.bits(), dtype=np.uint8).reshape((h, bpl))
    arr = arr[:, : w * 3].reshape((h, w, 3)).copy()
    return Image.fromarray(arr, "RGB")


def open_pdf(path: Path) -> Optional[QPdfDocument]:
    """Open a PDF file and return the document, or *None* on error.

    The caller is responsible for calling ``doc.close()`` when done.

    Args:
        path: Path to the PDF file.

    Returns:
        Loaded QPdfDocument, or *None* on failure.
    """
    doc = QPdfDocument(None)
    error = doc.load(str(path))
    if error != QPdfDocument.Error.None_:
        logger.error("Cannot open PDF '%s': %s", path, error)
        doc.close()
        return None
    if doc.pageCount() == 0:
        logger.warning("PDF is empty: '%s'", path)
        doc.close()
        return None
    return doc
