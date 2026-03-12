"""Main application window — 3-panel layout with controller logic."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSplitter,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from src.config import APP_NAME, APP_VERSION, BASE_DIR
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

_POLL_INTERVAL_MS = 500        # queue poll frequency
_NOTIFY_DEBOUNCE_MS = 2000     # batch notification debounce


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
        self._pending_notify_count: int = 0  # for batched tray notifications

        self._setup_ui()
        self._setup_tray()
        self._setup_watcher()
        self._setup_poll_timer()

        logger.info("MainWindow opened for user '%s'.", user.username)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 720)

        # App icon
        icon_path = BASE_DIR / "assets" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

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
    # System tray
    # ------------------------------------------------------------------

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray: Optional[QSystemTrayIcon] = None
            return

        self._tray = QSystemTrayIcon(self)
        icon_path = BASE_DIR / "assets" / "icon.ico"
        if icon_path.exists():
            self._tray.setIcon(QIcon(str(icon_path)))
        else:
            self._tray.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon
            ))
        self._tray.setToolTip(APP_NAME)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("Mostra finestra")
        show_action.triggered.connect(self._bring_to_front)
        tray_menu.addSeparator()
        quit_action = tray_menu.addAction("Esci")
        quit_action.triggered.connect(QApplication.quit)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        # Debounce timer: fires once after _NOTIFY_DEBOUNCE_MS with batch count
        self._notify_timer = QTimer(self)
        self._notify_timer.setSingleShot(True)
        self._notify_timer.setInterval(_NOTIFY_DEBOUNCE_MS)
        self._notify_timer.timeout.connect(self._send_batch_notification)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._bring_to_front()

    def _bring_to_front(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_notify(self, title: str, message: str) -> None:
        if self._tray and self._tray.isVisible():
            self._tray.showMessage(
                title, message,
                QSystemTrayIcon.MessageIcon.Information,
                4000,
            )

    def _schedule_batch_notification(self) -> None:
        """Increment pending count and (re)start the debounce timer."""
        self._pending_notify_count += 1
        self._notify_timer.start()

    def _send_batch_notification(self) -> None:
        count = self._pending_notify_count
        self._pending_notify_count = 0
        if count == 1:
            self._tray_notify("DDT Scanner", "1 nuovo documento in coda")
        elif count > 1:
            self._tray_notify("DDT Scanner", f"{count} nuovi documenti in coda")

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
                self._watcher.add_folder(folder.source_path, folder.folder_type, store_id,
                                         dest_path=folder.dest_path)

    def _setup_poll_timer(self) -> None:
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_watcher)
        self._poll_timer.start()

    def _poll_watcher(self) -> None:
        new_files = 0
        while True:
            event = self._watcher.get()
            if event is None:
                break
            self._queue_panel.add_file(event)
            new_files += 1

        if new_files:
            count = self._queue_panel.total_count()
            self._set_status(f"In coda: {count} documento/i")
            # Schedule a debounced tray notification
            for _ in range(new_files):
                self._schedule_batch_notification()

    # ------------------------------------------------------------------
    # File workflow
    # ------------------------------------------------------------------

    def _on_file_selected(self, event: FileEvent) -> None:
        self._current_event = event
        self._document_viewer.load_file(event.path)
        self._barcode_editor.clear()
        self._barcode_editor.set_loading(True)
        self._set_status(f"Analisi in corso: {event.path.name}…")

        # Abort previous worker: disconnect signals first to avoid stale callbacks
        if self._ocr_worker:
            try:
                self._ocr_worker.finished.disconnect()
                self._ocr_worker.error.disconnect()
            except RuntimeError:
                pass  # already disconnected
            if self._ocr_worker.isRunning():
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
        logger.warning("OCR failed: %s", message)

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
                dest_dir=event.dest_path if event.dest_path else None,
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
            self._finalize_action(
                event, f"Confermato: {event.path.name}  |  {len(barcodes)} barcode"
            )
        except PermissionError:
            QMessageBox.warning(
                self, "File bloccato",
                "Il file è ancora bloccato dallo scanner.\n"
                "Attendere qualche secondo e riprovare.",
            )
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
                dest_dir=event.dest_path if event.dest_path else None,
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
        except PermissionError:
            QMessageBox.warning(
                self, "File bloccato",
                "Il file è ancora bloccato dallo scanner.\n"
                "Attendere qualche secondo e riprovare.",
            )
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
        from src.gui.login_dialog import LoginDialog
        dialog = LoginDialog()
        if dialog.exec() == LoginDialog.Accepted:
            user = dialog.authenticated_user
            window = MainWindow(user)
            window.show()

    def _on_open_admin(self) -> None:
        from src.gui.admin_panel import AdminPanel
        dlg = AdminPanel(user=self._user, watcher=self._watcher, parent=self)
        dlg.exec()

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
        # If tray is active, minimize to tray instead of quitting
        if self._tray and self._tray.isVisible():
            self.hide()
            self._tray_notify(APP_NAME, "L'applicazione è ancora attiva nella barra delle applicazioni.")
            event.ignore()
            return
        self._shutdown()
        super().closeEvent(event)

    def _shutdown(self) -> None:
        self._poll_timer.stop()
        if hasattr(self, "_notify_timer"):
            self._notify_timer.stop()
        self._watcher.stop()
        if self._ocr_worker:
            try:
                self._ocr_worker.finished.disconnect()
                self._ocr_worker.error.disconnect()
            except RuntimeError:
                pass
            if self._ocr_worker.isRunning():
                self._ocr_worker.quit()
                if not self._ocr_worker.wait(2000):
                    logger.warning("OCR worker did not stop within timeout.")
        if self._tray:
            self._tray.hide()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, message: str) -> None:
        self._status_msg_label.setText(f"  {message}")
