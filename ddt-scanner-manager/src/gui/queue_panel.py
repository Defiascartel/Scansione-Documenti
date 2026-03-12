"""Left panel — queue of files waiting to be processed."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.watcher.folder_watcher import FileEvent
from src.utils.logger import get_logger

logger = get_logger("gui.queue_panel")

# Item data roles
_ROLE_EVENT = Qt.ItemDataRole.UserRole
_ROLE_FOLDER_BASE = Qt.ItemDataRole.UserRole + 1


class QueuePanel(QWidget):
    """Displays pending files grouped by source folder.

    Signals:
        file_selected: Emitted when the user clicks on a file item.
                       Carries the corresponding FileEvent.
    """

    file_selected: Signal = Signal(object)  # FileEvent

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._events: dict[Path, FileEvent] = {}
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_file(self, event: FileEvent) -> None:
        """Add a new file to the queue.

        Args:
            event: FileEvent describing the new file.
        """
        if event.path in self._events:
            return  # already present
        self._events[event.path] = event

        folder_name = event.path.parent.name
        folder_item = self._get_or_create_folder(folder_name)

        file_item = QTreeWidgetItem(folder_item)
        file_item.setText(0, event.path.name)
        file_item.setData(0, _ROLE_EVENT, event)
        file_item.setToolTip(0, str(event.path))

        self._refresh_folder_label(folder_item)
        folder_item.setExpanded(True)
        logger.debug("Queued in panel: %s", event.path.name)

    def remove_file(self, path: Path) -> None:
        """Remove a file from the queue (after confirm/discard).

        Args:
            path: Path of the file to remove.
        """
        self._events.pop(path, None)
        root = self._tree.invisibleRootItem()
        for fi in range(root.childCount()):
            folder_item = root.child(fi)
            for ci in range(folder_item.childCount()):
                child = folder_item.child(ci)
                event: Optional[FileEvent] = child.data(0, _ROLE_EVENT)
                if event and event.path == path:
                    folder_item.removeChild(child)
                    if folder_item.childCount() == 0:
                        root.removeChild(folder_item)
                    else:
                        self._refresh_folder_label(folder_item)
                    return

    def highlight_file(self, path: Path) -> None:
        """Bold-highlight the item for *path* to show it is being worked on.

        Args:
            path: Path of the file currently in the viewer.
        """
        root = self._tree.invisibleRootItem()
        bold = QFont()
        bold.setBold(True)
        normal = QFont()
        for fi in range(root.childCount()):
            folder_item = root.child(fi)
            for ci in range(folder_item.childCount()):
                child = folder_item.child(ci)
                event: Optional[FileEvent] = child.data(0, _ROLE_EVENT)
                if event:
                    child.setFont(0, bold if event.path == path else normal)

    def total_count(self) -> int:
        """Return total number of files currently in the queue."""
        return len(self._events)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("Coda documenti")
        header_font = QFont()
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet("padding: 4px 2px; color: #333;")
        layout.addWidget(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.setAnimated(True)
        self._tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create_folder(self, folder_name: str) -> QTreeWidgetItem:
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, _ROLE_FOLDER_BASE) == folder_name:
                return item
        item = QTreeWidgetItem(self._tree)
        item.setData(0, _ROLE_FOLDER_BASE, folder_name)
        folder_font = QFont()
        folder_font.setBold(True)
        item.setFont(0, folder_font)
        item.setForeground(0, QColor("#2c3e50"))
        return item

    def _refresh_folder_label(self, folder_item: QTreeWidgetItem) -> None:
        base: str = folder_item.data(0, _ROLE_FOLDER_BASE) or ""
        count = folder_item.childCount()
        folder_item.setText(0, f"{base}  ({count})")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        event: Optional[FileEvent] = item.data(0, _ROLE_EVENT)
        if event:
            self.file_selected.emit(event)
            self.highlight_file(event.path)
