"""File movement, format conversion, and sidecar JSON creation."""

import io
import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import img2pdf
from PIL import Image

from src.config import PDF_EXTENSIONS, TIF_EXTENSIONS
from src.database.db import get_setting
from src.utils.logger import get_logger
from src.utils.pdf_renderer import open_pdf, render_page_to_pil

logger = get_logger("utils.file_manager")

_MOVE_MAX_ATTEMPTS = 4
_MOVE_RETRY_DELAY = 1.5  # seconds between retries (file may still be locked by scanner)


def _derived_root(source_folder: Path, suffix: str) -> Path:
    """Derive an output directory by appending *suffix* to the source folder name.

    Args:
        source_folder: Source directory path.
        suffix: String to append (e.g. ``"_confermati"``, ``"_scartati"``).

    Returns:
        Destination directory path.
    """
    return source_folder.parent / (source_folder.name + suffix)


def _resolve_dest_path(dest_dir: Path, filename: str) -> Path:
    """Return a non-colliding destination path.

    If ``filename`` already exists in ``dest_dir``, a timestamp suffix is
    appended before the extension.

    Args:
        dest_dir: Target directory.
        filename: Original file name.

    Returns:
        Non-colliding Path inside dest_dir.
    """
    dest = dest_dir / filename
    if not dest.exists():
        return dest

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return dest_dir / f"{stem}_{timestamp}{suffix}"


def _write_sidecar(dest_file: Path, barcodes: list[str], username: str,
                   store_id: Optional[int], action: str) -> None:
    """Write a JSON sidecar file next to the moved document.

    Args:
        dest_file: Path of the moved file.
        barcodes: List of confirmed barcode values.
        username: Username of the operator.
        store_id: Store id.
        action: 'confirmed' or 'discarded'.
    """
    sidecar_path = dest_file.with_suffix(".json")
    payload = {
        "filename": dest_file.name,
        "action": action,
        "barcodes": barcodes,
        "operator": username,
        "store_id": store_id,
        "processed_at": datetime.now().isoformat(),
    }
    sidecar_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.debug("Sidecar written: %s", sidecar_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def move_to_confirmed(
    source_file: str | Path,
    barcodes: list[str],
    username: str,
    store_id: Optional[int] = None,
    dest_dir: str | Path | None = None,
) -> Path:
    """Move a file to the confirmed folder and write a sidecar JSON.

    Args:
        source_file: Absolute path of the file to move.
        barcodes: Confirmed barcode values.
        username: Operator username.
        store_id: Store id for the sidecar.
        dest_dir: Explicit destination directory (OUT). Falls back to
                  ``{source_folder}_confermati`` if not provided.

    Returns:
        Final path of the moved file.
    """
    return _move_file(source_file, action="confirmed",
                      barcodes=barcodes, username=username, store_id=store_id,
                      dest_dir=dest_dir)


def move_to_discarded(
    source_file: str | Path,
    username: str,
    store_id: Optional[int] = None,
    dest_dir: str | Path | None = None,
) -> Path:
    """Move a file to the discarded folder and write a sidecar JSON.

    Args:
        source_file: Absolute path of the file to move.
        username: Operator username.
        store_id: Store id for the sidecar.
        dest_dir: Explicit destination directory (OUT). Falls back to
                  ``{source_folder}_scartati`` if not provided.

    Returns:
        Final path of the moved file.
    """
    return _move_file(source_file, action="discarded",
                      barcodes=[], username=username, store_id=store_id,
                      dest_dir=dest_dir)


# ---------------------------------------------------------------------------
# Format conversion
# ---------------------------------------------------------------------------

_CONVERT_DPI = 300  # render resolution for PDF → image conversion


def _convert_if_needed(source: Path, target_format: str) -> Path:
    """Convert *source* to *target_format* if necessary.

    Args:
        source: Path to the original file.
        target_format: ``"same"``, ``"pdf"`` or ``"tif"``.

    Returns:
        Path to the (possibly converted) file.  If no conversion is needed
        the original *source* is returned unchanged.  Converted files are
        written next to the source with the new extension.
    """
    if target_format == "same":
        return source

    ext = source.suffix.lower()

    if target_format == "pdf":
        if ext in PDF_EXTENSIONS:
            return source  # already PDF
        return _convert_to_pdf(source)

    if target_format == "tif":
        if ext in TIF_EXTENSIONS:
            return source  # already TIF
        return _convert_to_tif(source)

    logger.warning("Unknown target format '%s' — skipping conversion.", target_format)
    return source


def _convert_to_pdf(source: Path) -> Path:
    """Convert an image or TIFF file to PDF using img2pdf (lossless).

    Args:
        source: Path to the image/TIFF file.

    Returns:
        Path to the generated PDF (next to source).
    """
    dest = source.with_suffix(".pdf")
    ext = source.suffix.lower()

    # For multi-page TIFF, extract all frames first
    if ext in TIF_EXTENSIONS:
        frames = _tiff_frames_as_jpeg_bytes(source)
    else:
        # Single image — img2pdf handles jpg/png/bmp directly
        frames = [source.read_bytes()]

    pdf_bytes = img2pdf.convert(frames)
    dest.write_bytes(pdf_bytes)
    logger.info("Converted '%s' → '%s'.", source.name, dest.name)
    source.unlink(missing_ok=True)
    return dest


def _tiff_frames_as_jpeg_bytes(source: Path) -> list[bytes]:
    """Extract all frames from a TIFF as JPEG byte strings for img2pdf."""
    pil = Image.open(source)
    frames: list[bytes] = []
    frame_idx = 0
    while True:
        try:
            pil.seek(frame_idx)
        except EOFError:
            break
        buf = io.BytesIO()
        pil.copy().convert("RGB").save(buf, format="JPEG", quality=95)
        frames.append(buf.getvalue())
        frame_idx += 1
    return frames


def _convert_to_tif(source: Path) -> Path:
    """Convert a PDF or image file to multi-page TIFF.

    Args:
        source: Path to the file.

    Returns:
        Path to the generated TIFF.
    """
    ext = source.suffix.lower()
    dest = source.with_suffix(".tif")

    if ext in PDF_EXTENSIONS:
        pages = _pdf_pages_as_pil(source)
    else:
        # Single image
        pages = [Image.open(source).convert("RGB")]

    if not pages:
        logger.error("No pages extracted from '%s' — skipping conversion.", source.name)
        return source

    pages[0].save(
        dest, format="TIFF", compression="tiff_deflate",
        save_all=True, append_images=pages[1:],
    )

    logger.info("Converted '%s' → '%s'.", source.name, dest.name)
    source.unlink(missing_ok=True)
    return dest


def _pdf_pages_as_pil(source: Path) -> list[Image.Image]:
    """Render each PDF page to a PIL Image."""
    doc = open_pdf(source)
    if doc is None:
        return []

    pages: list[Image.Image] = []
    for page_num in range(doc.pageCount()):
        pil = render_page_to_pil(doc, page_num, dpi=_CONVERT_DPI)
        if pil is not None:
            pages.append(pil)

    doc.close()
    return pages


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _move_file(
    source_file: str | Path,
    action: str,
    barcodes: list[str],
    username: str,
    store_id: Optional[int],
    dest_dir: str | Path | None = None,
) -> Path:
    source = Path(source_file)
    if not source.exists():
        raise FileNotFoundError(f"Source file not found: {source}")

    if dest_dir:
        resolved_dir = Path(dest_dir)
    else:
        suffix = "_confermati" if action == "confirmed" else "_scartati"
        resolved_dir = _derived_root(source.parent, suffix)

    # Organise into a date-based subfolder (YYYYMMDD)
    date_folder = datetime.now().strftime("%Y%m%d")
    resolved_dir = resolved_dir / date_folder

    resolved_dir.mkdir(parents=True, exist_ok=True)

    # Convert file format if the admin configured a target format
    output_format = get_setting("output_format", "same")
    source = _convert_if_needed(source, output_format)

    # Confirmed files are renamed to their barcode values
    if action == "confirmed" and barcodes:
        new_name = "_".join(barcodes) + source.suffix
    else:
        new_name = source.name
    dest_file = _resolve_dest_path(resolved_dir, new_name)

    _move_with_retry(source, dest_file)
    logger.info("File %s → %s (%s)", source.name, dest_file, action)

    _write_sidecar(dest_file, barcodes=barcodes, username=username,
                   store_id=store_id, action=action)

    return dest_file


def _move_with_retry(source: Path, dest: Path) -> None:
    """Move *source* to *dest* with retry on PermissionError (file locked).

    Args:
        source: Source path.
        dest: Destination path.

    Raises:
        PermissionError: If all attempts fail.
        OSError: For other OS-level errors.
    """
    for attempt in range(1, _MOVE_MAX_ATTEMPTS + 1):
        try:
            shutil.move(str(source), str(dest))
            return
        except PermissionError as exc:
            if attempt == _MOVE_MAX_ATTEMPTS:
                logger.error(
                    "Cannot move '%s' after %d attempts (file locked): %s",
                    source.name, _MOVE_MAX_ATTEMPTS, exc,
                )
                raise
            logger.warning(
                "File '%s' locked (attempt %d/%d) — retrying in %.1fs…",
                source.name, attempt, _MOVE_MAX_ATTEMPTS, _MOVE_RETRY_DELAY,
            )
            time.sleep(_MOVE_RETRY_DELAY)
