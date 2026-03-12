"""Right panel — editable barcode list with confirm/discard actions."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.logger import get_logger

logger = get_logger("gui.barcode_editor")


class BarcodeEditor(QWidget):
    """Panel that shows detected barcodes and lets the operator edit/confirm them.

    Signals:
        confirmed: Emitted with the final list of barcode strings when the
                   operator clicks "Conferma".
        discarded: Emitted when the operator clicks "Scarta".
    """

    confirmed: Signal = Signal(list)   # list[str]
    discarded: Signal = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_barcodes(self, barcodes: list[str]) -> None:
        """Populate the list with detected barcode values.

        Args:
            barcodes: List of barcode strings to display.
        """
        self._loading_label.setVisible(False)
        self._list.setVisible(True)
        self._list.clear()
        for value in barcodes:
            item = QListWidgetItem(value)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._list.addItem(item)
        self._update_count_label()

    def get_barcodes(self) -> list[str]:
        """Return the current (possibly edited) list of barcode values.

        Returns:
            Non-empty stripped strings from the list.
        """
        return [
            self._list.item(i).text().strip()
            for i in range(self._list.count())
            if self._list.item(i).text().strip()
        ]

    def set_loading(self, loading: bool) -> None:
        """Show/hide a 'scanning…' placeholder while OCR is running.

        Args:
            loading: True to show the loading message.
        """
        self._loading_label.setVisible(loading)
        self._list.setVisible(not loading)
        if loading:
            self._count_label.setText("Analisi in corso…")
        self._set_action_buttons_enabled(not loading)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable all interactive controls.

        Args:
            enabled: True to enable.
        """
        self._list.setEnabled(enabled)
        self._add_btn.setEnabled(enabled)
        self._remove_btn.setEnabled(enabled)
        self._set_action_buttons_enabled(enabled)

    def clear(self) -> None:
        """Reset the panel to its initial empty state."""
        self._list.clear()
        self._loading_label.setVisible(False)
        self._list.setVisible(True)
        self._count_label.setText("")
        self.set_enabled(False)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        # Header
        header = QLabel("Barcode rilevati")
        header_font = QFont()
        header_font.setBold(True)
        header.setFont(header_font)
        header.setStyleSheet("padding: 2px; color: #333;")
        layout.addWidget(header)

        self._count_label = QLabel("")
        self._count_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._count_label)

        # Loading placeholder
        self._loading_label = QLabel("Analisi in corso…")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._loading_label.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
        self._loading_label.setVisible(False)
        layout.addWidget(self._loading_label)

        # Barcode list
        self._list = QListWidget()
        self._list.setEditTriggers(
            QListWidget.EditTrigger.DoubleClicked |
            QListWidget.EditTrigger.SelectedClicked
        )
        self._list.model().rowsInserted.connect(self._update_count_label)
        self._list.model().rowsRemoved.connect(self._update_count_label)
        layout.addWidget(self._list)

        # Add / Remove row
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("+ Aggiungi")
        self._remove_btn = QPushButton("− Rimuovi")
        for btn in (self._add_btn, self._remove_btn):
            btn.setStyleSheet(
                "QPushButton { border: 1px solid #bbb; border-radius: 3px; padding: 4px 8px; }"
                "QPushButton:hover { background: #eee; }"
                "QPushButton:disabled { color: #aaa; }"
            )
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._remove_btn)
        layout.addLayout(btn_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Confirm button (green, prominent)
        self._confirm_btn = QPushButton("✓   Conferma")
        self._confirm_btn.setMinimumHeight(44)
        self._confirm_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; font-weight: bold;"
            " border-radius: 5px; font-size: 14px; }"
            "QPushButton:hover { background-color: #2ecc71; }"
            "QPushButton:pressed { background-color: #1e8449; }"
            "QPushButton:disabled { background-color: #b2dfcb; color: #fff; }"
        )
        layout.addWidget(self._confirm_btn)

        # Discard button (red, secondary)
        self._discard_btn = QPushButton("✗   Scarta")
        self._discard_btn.setMinimumHeight(32)
        self._discard_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; border-radius: 5px; }"
            "QPushButton:hover { background-color: #e95f4f; }"
            "QPushButton:pressed { background-color: #c0392b; }"
            "QPushButton:disabled { background-color: #f1a9a0; color: #fff; }"
        )
        layout.addWidget(self._discard_btn)

        self.set_enabled(False)

        # Connections
        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn.clicked.connect(self._on_remove)
        self._confirm_btn.clicked.connect(self._on_confirm)
        self._discard_btn.clicked.connect(self.discarded.emit)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_add(self) -> None:
        text, ok = QInputDialog.getText(self, "Aggiungi barcode", "Valore barcode:")
        if ok and text.strip():
            item = QListWidgetItem(text.strip())
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self._list.addItem(item)

    def _on_remove(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))

    def _on_confirm(self) -> None:
        self.confirmed.emit(self.get_barcodes())

    def _update_count_label(self) -> None:
        count = self._list.count()
        if count == 0:
            self._count_label.setText("Nessun barcode")
        elif count == 1:
            self._count_label.setText("1 barcode")
        else:
            self._count_label.setText(f"{count} barcode")

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        self._confirm_btn.setEnabled(enabled)
        self._discard_btn.setEnabled(enabled)
