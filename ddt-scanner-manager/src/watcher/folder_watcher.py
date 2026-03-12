"""Folder monitoring service using watchdog + periodic polling fallback."""

import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileMovedEvent
from watchdog.observers import Observer

from src.utils.logger import get_logger

logger = get_logger("watcher.folder_watcher")

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".pdf"}
POLLING_INTERVAL = 30  # seconds
FILE_SETTLE_DELAY = 2.5  # seconds — wait after event before queuing (scanner may still write)


@dataclass
class FileEvent:
    """A new file detected in a watched folder."""

    path: Path
    folder_type: str
    store_id: int


@dataclass
class WatchedFolder:
    """Internal representation of a folder being monitored."""

    path: Path
    folder_type: str
    store_id: int


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class _DDTEventHandler(FileSystemEventHandler):
    """Handles filesystem events for a single watched directory."""

    def __init__(
        self,
        watched: WatchedFolder,
        work_queue: "queue.Queue[FileEvent]",
        seen: set[Path],
        seen_lock: threading.Lock,
    ) -> None:
        super().__init__()
        self._watched = watched
        self._queue = work_queue
        self._seen = seen
        self._seen_lock = seen_lock

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory:
            self._maybe_enqueue(Path(event.src_path))

    def on_moved(self, event: FileMovedEvent) -> None:
        # Handles scanners that write to a temp name then rename
        if not event.is_directory:
            self._maybe_enqueue(Path(event.dest_path))

    def _maybe_enqueue(self, path: Path) -> None:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        with self._seen_lock:
            if path in self._seen:
                return
            self._seen.add(path)

        # Delay to let the scanner finish writing
        def _delayed():
            time.sleep(FILE_SETTLE_DELAY)
            if path.exists():
                self._queue.put(
                    FileEvent(path=path, folder_type=self._watched.folder_type,
                              store_id=self._watched.store_id)
                )
                logger.info("Queued: %s", path)
            else:
                with self._seen_lock:
                    self._seen.discard(path)

        threading.Thread(target=_delayed, daemon=True).start()


# ---------------------------------------------------------------------------
# Watcher service
# ---------------------------------------------------------------------------

class FolderWatcher:
    """Monitors a set of folders and feeds a work queue with new files.

    Usage::

        watcher = FolderWatcher()
        watcher.add_folder(path, folder_type, store_id)
        watcher.start()

        while True:
            event = watcher.get(timeout=1)   # blocks up to 1 s
            if event:
                process(event)

        watcher.stop()
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[FileEvent] = queue.Queue()
        self._folders: list[WatchedFolder] = []
        self._observer: Optional[Observer] = None
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._seen: set[Path] = set()
        self._seen_lock = threading.Lock()
        self._lock = threading.Lock()  # protects _folders list

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_folder(self, path: str | Path, folder_type: str, store_id: int) -> None:
        """Register a folder to monitor.

        Args:
            path: Absolute path of the folder.
            folder_type: Descriptive type (e.g. 'acquisti').
            store_id: Associated store id.
        """
        resolved = Path(path)
        wf = WatchedFolder(path=resolved, folder_type=folder_type, store_id=store_id)
        with self._lock:
            # Avoid duplicates
            if any(f.path == resolved for f in self._folders):
                logger.debug("Folder already watched: %s", resolved)
                return
            self._folders.append(wf)

        if self._observer and self._observer.is_alive():
            self._schedule_watchdog(wf)
            logger.info("Dynamically added watch: %s", resolved)

    def remove_folder(self, path: str | Path) -> None:
        """Stop monitoring a folder.

        Args:
            path: Absolute path of the folder to remove.
        """
        resolved = Path(path)
        with self._lock:
            self._folders = [f for f in self._folders if f.path != resolved]
        # Watchdog does not support unscheduling individual watches easily;
        # a full restart would be needed. For now we just drop from the list
        # so the polling fallback ignores it too.
        logger.info("Removed watch: %s", resolved)

    def start(self) -> None:
        """Start the watchdog observer and the polling fallback thread."""
        self._stop_event.clear()
        self._start_watchdog()
        self._start_polling()
        logger.info("FolderWatcher started (%d folder(s)).", len(self._folders))

    def stop(self) -> None:
        """Stop all monitoring threads."""
        self._stop_event.set()
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
        logger.info("FolderWatcher stopped.")

    def get(self, timeout: float = 0) -> Optional[FileEvent]:
        """Retrieve the next file event from the queue.

        Args:
            timeout: Seconds to wait for an event (0 = non-blocking).

        Returns:
            FileEvent or None if queue is empty within the timeout.
        """
        try:
            return self._queue.get(timeout=timeout) if timeout > 0 else self._queue.get_nowait()
        except queue.Empty:
            return None

    def queue_size(self) -> int:
        """Return the current number of pending file events."""
        return self._queue.qsize()

    # ------------------------------------------------------------------
    # Internal — watchdog
    # ------------------------------------------------------------------

    def _start_watchdog(self) -> None:
        self._observer = Observer()
        with self._lock:
            folders_snapshot = list(self._folders)
        for wf in folders_snapshot:
            self._schedule_watchdog(wf)
        self._observer.start()

    def _schedule_watchdog(self, wf: WatchedFolder) -> None:
        if not wf.path.exists():
            logger.warning("Watch path does not exist (skipped): %s", wf.path)
            return
        handler = _DDTEventHandler(wf, self._queue, self._seen, self._seen_lock)
        self._observer.schedule(handler, str(wf.path), recursive=False)

    # ------------------------------------------------------------------
    # Internal — polling fallback
    # ------------------------------------------------------------------

    def _start_polling(self) -> None:
        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="FolderWatcher-poll", daemon=True
        )
        self._poll_thread.start()

    def _poll_loop(self) -> None:
        """Periodically scan all watched folders for files missed by watchdog."""
        while not self._stop_event.wait(POLLING_INTERVAL):
            try:
                with self._lock:
                    folders_snapshot = list(self._folders)
                for wf in folders_snapshot:
                    self._poll_folder(wf)
            except Exception as exc:
                logger.error("Unexpected error in poll loop: %s", exc, exc_info=True)

    def _poll_folder(self, wf: WatchedFolder) -> None:
        if not wf.path.exists():
            return
        try:
            for entry in wf.path.iterdir():
                if entry.is_file() and entry.suffix.lower() in SUPPORTED_EXTENSIONS:
                    with self._seen_lock:
                        if entry in self._seen:
                            continue
                        self._seen.add(entry)
                    self._queue.put(
                        FileEvent(path=entry, folder_type=wf.folder_type,
                                  store_id=wf.store_id)
                    )
                    logger.info("Polling queued: %s", entry)
        except PermissionError as exc:
            logger.warning("Permission error polling '%s': %s", wf.path, exc)
        except OSError as exc:
            logger.warning("OS error polling '%s': %s", wf.path, exc)
