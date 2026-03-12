"""Main application window — 3-panel layout with controller logic."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QThread

from src.config import APP_NAME, APP_VERSION
from src.database.db import (
    User,
    list_stores,
    list_watched_folders,
    log_operation,
)
from src.gui.barcode_editor import BarcodeEditor
from src.gui.document_viewer import DocumentViewer
from src.gui.queue_panel import QueuePanel
from src.ocr.barcode_reader import read_barcodes
from src.utils.file_manager import move_to_confirmed, move_to_discarded
from src.watcher.folder_watcher import FileEvent, FolderWatcher
from src.utils.logger import get_logger

logger = get_logger("gui.main_window")

_POLL_INTERVAL_MS = 500  # queue poll frequency


# ---------------------------------------------------------------------------
# Background OCR worker
# ---------------------------------------------------------------------------

class _OcrWorker(QThread):
    """Runs barcode detection in a background thread."""

    finished: Signal = Signal(list)   # list[str] — deduplicated barcode values
    error: Signal = Signal(str)

    def __init__(self, path: Path, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._path = path

    def run(self) -> None:
        try:
            scan_results = read_barcodes(self._path)
            seen: set[str] = set()
            values: list[str] = []
            for sr in scan_results:
                for br in sr.barcodes:
                    if br.value not in seen:
                        seen.add(br.value)
                        values.append(br.value)
            self.finished.emit(values)
        except Exception as exc:
            logger.error("OCR error for '%s': %s", self._path, exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """3-panel main window: queue | viewer | barcode editor."""

    def __init__(self, user: User, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._user = user
        self._current_event: Optional[FileEvent] = None
        self._ocr_worker: Optional[_OcrWorker] = None
        self._watcher = FolderWatcher()

        self._setup_ui()
        self._setup_watcher()
        self._setup_poll_timer()

        logger.info("MainWindow opened for user '%s'.", user.username)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self._queue_panel = QueuePanel()
        self._queue_panel.setMinimumWidth(200)

        self._document_viewer = DocumentViewer()

        self._barcode_editor = BarcodeEditor()
        self._barcode_editor.setMinimumWidth(220)
        self._barcode_editor.setMaximumWidth(340)

        splitter.addWidget(self._queue_panel)
        splitter.addWidget(self._document_viewer)
        splitter.addWidget(self._barcode_editor)
        splitter.setSizes([240, 720, 280])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        root_layout.addWidget(splitter)

        self._setup_menu()
        self._setup_status_bar()

        # Connections
        self._queue_panel.file_selected.connect(self._on_file_selected)
        self._barcode_editor.confirmed.connect(self._on_confirmed)
        self._barcode_editor.discarded.connect(self._on_discarded)

    def _setup_menu(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        logout_action = file_menu.addAction("Disconnetti")
        logout_action.triggered.connect(self._on_logout)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("Esci")
        quit_action.triggered.connect(QApplication.quit)

        # Settings (admin only)
        if self._user.role == "admin":
            settings_menu = menu_bar.addMenu("Impostazioni")
            admin_action = settings_menu.addAction("Pannello Admin")
            admin_action.triggered.connect(self._on_open_admin)

        # Info menu
        info_menu = menu_bar.addMenu("?")
        about_action = info_menu.addAction("Informazioni")
        about_action.triggered.connect(self._on_about)

    def _setup_status_bar(self) -> None:
        sb = self.statusBar()

        store_text = ""
        if self._user.store_id:
            stores = {s.id: s for s in list_stores()}
            store = stores.get(self._user.store_id)
            if store:
                store_text = f"  |  Negozio: {store.name} ({store.code})"

        self._status_user_label = QLabel(
            f"  Utente: {self._user.username} ({self._user.role}){store_text}  "
        )
        self._status_msg_label = QLabel("")
        sb.addPermanentWidget(self._status_user_label)
        sb.addWidget(self._status_msg_label)

    # ------------------------------------------------------------------
    # Watcher & polling
    # ------------------------------------------------------------------

    def _setup_watcher(self) -> None:
        if self._user.store_id:
            self._add_store_folders(self._user.store_id)
        elif self._user.role == "admin":
            for store in list_stores():
                self._add_store_folders(store.id)

        self._watcher.start()

    def _add_store_folders(self, store_id: int) -> None:
        for folder in list_watched_folders(store_id):
            if folder.is_active:
                self._watcher.add_folder(folder.source_path, folder.folder_type, store_id)

    def _setup_poll_timer(self) -> None:
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_watcher)
        self._poll_timer.start()

    def _poll_watcher(self) -> None:
        while True:
            event = self._watcher.get()
            if event is None:
                break
            self._queue_panel.add_file(event)
            count = self._queue_panel.total_count()
            self._set_status(f"Nuovo file: {event.path.name}  |  In coda: {count}")

    # ------------------------------------------------------------------
    # File workflow
    # ------------------------------------------------------------------

    def _on_file_selected(self, event: FileEvent) -> None:
        self._current_event = event
        self._document_viewer.load_file(event.path)
        self._barcode_editor.clear()
        self._barcode_editor.set_loading(True)
        self._set_status(f"Analisi in corso: {event.path.name}…")

        # Abort previous worker if still running
        if self._ocr_worker and self._ocr_worker.isRunning():
            self._ocr_worker.quit()
            self._ocr_worker.wait(1000)

        self._ocr_worker = _OcrWorker(event.path)
        self._ocr_worker.finished.connect(self._on_ocr_finished)
        self._ocr_worker.error.connect(self._on_ocr_error)
        self._ocr_worker.start()

    def _on_ocr_finished(self, barcodes: list[str]) -> None:
        self._barcode_editor.set_loading(False)
        self._barcode_editor.set_barcodes(barcodes)
        self._barcode_editor.set_enabled(True)
        if barcodes:
            self._set_status(f"{len(barcodes)} barcode trovati")
        else:
            self._set_status("Nessun barcode rilevato — inserimento manuale possibile")

    def _on_ocr_error(self, message: str) -> None:
        self._barcode_editor.set_loading(False)
        self._barcode_editor.set_enabled(True)
        self._set_status(f"Errore OCR: {message}")

    def _on_confirmed(self, barcodes: list[str]) -> None:
        if not self._current_event:
            return
        event = self._current_event
        try:
            dest = move_to_confirmed(
                event.path,
                barcodes=barcodes,
                username=self._user.username,
                store_id=self._user.store_id,
            )
            log_operation(
                user_id=self._user.id,
                store_id=event.store_id,
                source_path=str(event.path.parent),
                dest_path=str(dest.parent),
                filename=event.path.name,
                barcodes=barcodes,
                action="confirmed",
            )
            self._finalize_action(event, f"Confermato: {event.path.name}  |  {len(barcodes)} barcode")
        except Exception as exc:
            logger.error("Confirm error: %s", exc)
            QMessageBox.warning(self, "Errore", f"Impossibile spostare il file:\n{exc}")

    def _on_discarded(self) -> None:
        if not self._current_event:
            return
        event = self._current_event
        try:
            dest = move_to_discarded(
                event.path,
                username=self._user.username,
                store_id=self._user.store_id,
            )
            log_operation(
                user_id=self._user.id,
                store_id=event.store_id,
                source_path=str(event.path.parent),
                dest_path=str(dest.parent),
                filename=event.path.name,
                barcodes=[],
                action="discarded",
            )
            self._finalize_action(event, f"Scartato: {event.path.name}")
        except Exception as exc:
            logger.error("Discard error: %s", exc)
            QMessageBox.warning(self, "Errore", f"Impossibile spostare il file:\n{exc}")

    def _finalize_action(self, event: FileEvent, status_msg: str) -> None:
        self._queue_panel.remove_file(event.path)
        self._document_viewer.clear()
        self._barcode_editor.clear()
        self._current_event = None
        self._set_status(status_msg)

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _on_logout(self) -> None:
        self._shutdown()
        self.close()
        # Re-open login dialog
        from src.gui.login_dialog import LoginDialog
        dialog = LoginDialog()
        if dialog.exec() == LoginDialog.Accepted:
            user = dialog.authenticated_user
            window = MainWindow(user)
            window.show()

    def _on_open_admin(self) -> None:
        QMessageBox.information(
            self,
            "Pannello Admin",
            "Il pannello admin sarà disponibile nella Fase 5.",
        )

    def _on_about(self) -> None:
        QMessageBox.about(
            self,
            f"Informazioni — {APP_NAME}",
            f"{APP_NAME}\nVersione {APP_VERSION}\n\nUnieuro S.p.A.",
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._shutdown()
        super().closeEvent(event)

    def _shutdown(self) -> None:
        self._poll_timer.stop()
        self._watcher.stop()
        if self._ocr_worker and self._ocr_worker.isRunning():
            self._ocr_worker.quit()
            self._ocr_worker.wait(2000)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        self._status_msg_label.setText(f"  {message}")
