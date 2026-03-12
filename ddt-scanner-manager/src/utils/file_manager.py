"""File movement and sidecar JSON creation."""

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger("utils.file_manager")

_MOVE_MAX_ATTEMPTS = 4
_MOVE_RETRY_DELAY = 1.5  # seconds between retries (file may still be locked by scanner)


def _destination_root(source_folder: Path) -> Path:
    """Derive the confirmed destination root from a source folder path.

    Appends ``_confermati`` to the source folder name.

    Args:
        source_folder: Source directory path.

    Returns:
        Destination directory path.
    """
    return source_folder.parent / (source_folder.name + "_confermati")


def _discarded_root(source_folder: Path) -> Path:
    """Derive the discarded destination root from a source folder path.

    Args:
        source_folder: Source directory path.

    Returns:
        Discarded directory path.
    """
    return source_folder.parent / (source_folder.name + "_scartati")


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
    elif action == "confirmed":
        resolved_dir = _destination_root(source.parent)
    else:
        resolved_dir = _discarded_root(source.parent)

    resolved_dir.mkdir(parents=True, exist_ok=True)

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
