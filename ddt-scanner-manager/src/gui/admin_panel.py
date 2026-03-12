"""Admin panel — 4-tab dialog for managing stores, users, folders and log."""

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.database.db import (
    Store,
    User,
    WatchedFolder,
    create_store,
    create_user,
    delete_store,
    list_operation_log,
    list_stores,
    list_users,
    list_watched_folders,
    add_watched_folder,
    remove_watched_folder,
    update_store,
    update_user,
)
from src.watcher.folder_watcher import FolderWatcher
from src.utils.logger import get_logger

logger = get_logger("gui.admin_panel")

_COL_BOLD_FONT = QFont()
_COL_BOLD_FONT.setBold(True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_table(headers: list[str]) -> QTableWidget:
    """Create a read-only, non-editable QTableWidget with given headers."""
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.verticalHeader().setVisible(False)
    table.setAlternatingRowColors(True)
    return table


def _set_cell(table: QTableWidget, row: int, col: int, text: str,
               bold: bool = False, color: Optional[QColor] = None) -> None:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if bold:
        item.setFont(_COL_BOLD_FONT)
    if color:
        item.setForeground(color)
    table.setItem(row, col, item)


def _action_buttons(*labels: str) -> tuple[QHBoxLayout, list[QPushButton]]:
    layout = QHBoxLayout()
    layout.setSpacing(6)
    buttons = []
    for label in labels:
        btn = QPushButton(label)
        btn.setMaximumWidth(130)
        layout.addWidget(btn)
        buttons.append(btn)
    layout.addStretch()
    return layout, buttons


# ---------------------------------------------------------------------------
# Sub-dialogs
# ---------------------------------------------------------------------------

class _StoreDialog(QDialog):
    def __init__(self, store: Optional[Store] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Negozio" if store else "Nuovo negozio")
        self.setFixedWidth(320)

        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self._code_edit = QLineEdit(store.code if store else "")
        self._code_edit.setPlaceholderText("es. 001")
        self._name_edit = QLineEdit(store.name if store else "")
        self._name_edit.setPlaceholderText("es. Bologna Centro")

        layout.addRow("Codice:", self._code_edit)
        layout.addRow("Nome:", self._name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def code(self) -> str:
        return self._code_edit.text().strip()

    @property
    def name(self) -> str:
        return self._name_edit.text().strip()

    def _validate(self) -> None:
        if not self.code:
            QMessageBox.warning(self, "Errore", "Il codice è obbligatorio.")
            return
        if not self.name:
            QMessageBox.warning(self, "Errore", "Il nome è obbligatorio.")
            return
        self.accept()


class _UserDialog(QDialog):
    def __init__(self, stores: list[Store], user: Optional[User] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Utente" if user else "Nuovo utente")
        self.setFixedWidth(360)
        self._is_edit = user is not None

        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self._username_edit = QLineEdit(user.username if user else "")
        layout.addRow("Username:", self._username_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Lascia vuoto per non cambiare" if user else "")
        layout.addRow("Password:", self._password_edit)

        self._role_combo = QComboBox()
        self._role_combo.addItems(["operator", "admin"])
        if user:
            self._role_combo.setCurrentText(user.role)
        self._role_combo.currentTextChanged.connect(self._on_role_changed)
        layout.addRow("Ruolo:", self._role_combo)

        self._store_combo = QComboBox()
        self._store_combo.addItem("— nessuno —", None)
        for s in stores:
            self._store_combo.addItem(f"{s.name} ({s.code})", s.id)
        if user and user.store_id:
            idx = self._store_combo.findData(user.store_id)
            if idx >= 0:
                self._store_combo.setCurrentIndex(idx)
        layout.addRow("Negozio:", self._store_combo)

        self._active_check = QCheckBox("Utente attivo")
        self._active_check.setChecked(user.is_active if user else True)
        layout.addRow("", self._active_check)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._on_role_changed(self._role_combo.currentText())

    @property
    def username(self) -> str:
        return self._username_edit.text().strip()

    @property
    def password(self) -> str:
        return self._password_edit.text()

    @property
    def role(self) -> str:
        return self._role_combo.currentText()

    @property
    def store_id(self) -> Optional[int]:
        return self._store_combo.currentData()

    @property
    def is_active(self) -> bool:
        return self._active_check.isChecked()

    def _on_role_changed(self, role: str) -> None:
        self._store_combo.setEnabled(role == "operator")

    def _validate(self) -> None:
        if not self.username:
            QMessageBox.warning(self, "Errore", "Lo username è obbligatorio.")
            return
        if not self._is_edit and not self.password:
            QMessageBox.warning(self, "Errore", "La password è obbligatoria per i nuovi utenti.")
            return
        self.accept()


class _FolderDialog(QDialog):
    def __init__(self, stores: list[Store], preselect_store_id: Optional[int] = None,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aggiungi cartella monitorata")
        self.setFixedWidth(480)

        layout = QFormLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        self._store_combo = QComboBox()
        for s in stores:
            self._store_combo.addItem(f"{s.name} ({s.code})", s.id)
        if preselect_store_id:
            idx = self._store_combo.findData(preselect_store_id)
            if idx >= 0:
                self._store_combo.setCurrentIndex(idx)
        layout.addRow("Negozio:", self._store_combo)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText(r"\\server\scansioni\negozio_001\acquisti")
        self._browse_btn = QPushButton("…")
        self._browse_btn.setFixedWidth(30)
        self._browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(self._browse_btn)
        layout.addRow("Percorso:", path_row)

        self._type_edit = QLineEdit()
        self._type_edit.setPlaceholderText("es. acquisti, resi, altro")
        layout.addRow("Tipo cartella:", self._type_edit)

        self._warn_label = QLabel("")
        self._warn_label.setStyleSheet("color: #e67e22; font-size: 11px;")
        layout.addRow("", self._warn_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @property
    def store_id(self) -> Optional[int]:
        return self._store_combo.currentData()

    @property
    def path(self) -> str:
        return self._path_edit.text().strip()

    @property
    def folder_type(self) -> str:
        return self._type_edit.text().strip()

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Seleziona cartella")
        if folder:
            self._path_edit.setText(folder)

    def _validate(self) -> None:
        if not self.path:
            QMessageBox.warning(self, "Errore", "Il percorso è obbligatorio.")
            return
        if not self.folder_type:
            QMessageBox.warning(self, "Errore", "Il tipo cartella è obbligatorio.")
            return
        if self.store_id is None:
            QMessageBox.warning(self, "Errore", "Seleziona un negozio.")
            return
        p = Path(self.path)
        if not p.exists():
            reply = QMessageBox.question(
                self, "Percorso non trovato",
                f"Il percorso non esiste al momento:\n{self.path}\n\nAggiungere comunque?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        self.accept()


# ---------------------------------------------------------------------------
# Tab widgets
# ---------------------------------------------------------------------------

class _StoresTab(QWidget):
    stores_changed: Signal = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        btn_layout, (self._add_btn, self._edit_btn, self._del_btn) = _action_buttons(
            "+ Aggiungi", "✎ Modifica", "✕ Elimina"
        )
        layout.addLayout(btn_layout)

        self._table = _make_table(["ID", "Codice", "Nome", "Creato il"])
        layout.addWidget(self._table)

        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn.clicked.connect(self._on_edit)
        self._del_btn.clicked.connect(self._on_delete)

    def refresh(self) -> None:
        stores = list_stores()
        self._table.setRowCount(len(stores))
        for row, s in enumerate(stores):
            _set_cell(self._table, row, 0, str(s.id))
            _set_cell(self._table, row, 1, s.code, bold=True)
            _set_cell(self._table, row, 2, s.name)
            _set_cell(self._table, row, 3, "")
        self._table.resizeColumnsToContents()

    def _selected_store_id(self) -> Optional[int]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _on_add(self) -> None:
        dlg = _StoreDialog(parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                create_store(dlg.code, dlg.name)
                self.refresh()
                self.stores_changed.emit()
            except Exception as exc:
                QMessageBox.warning(self, "Errore", str(exc))

    def _on_edit(self) -> None:
        sid = self._selected_store_id()
        if sid is None:
            QMessageBox.information(self, "Selezione", "Seleziona un negozio da modificare.")
            return
        stores = {s.id: s for s in list_stores()}
        store = stores.get(sid)
        if store is None:
            QMessageBox.warning(self, "Errore", "Negozio non trovato. Aggiornare la lista.")
            self.refresh()
            return
        dlg = _StoreDialog(store=store, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                update_store(sid, code=dlg.code, name=dlg.name)
                self.refresh()
                self.stores_changed.emit()
            except Exception as exc:
                QMessageBox.warning(self, "Errore", str(exc))

    def _on_delete(self) -> None:
        sid = self._selected_store_id()
        if sid is None:
            QMessageBox.information(self, "Selezione", "Seleziona un negozio da eliminare.")
            return
        reply = QMessageBox.question(
            self, "Conferma eliminazione",
            "Eliminare il negozio selezionato?\n"
            "Attenzione: verranno eliminate anche le cartelle associate.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_store(sid)
                self.refresh()
                self.stores_changed.emit()
            except Exception as exc:
                QMessageBox.warning(self, "Errore", str(exc))


class _UsersTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        btn_layout, (self._add_btn, self._edit_btn) = _action_buttons(
            "+ Aggiungi", "✎ Modifica"
        )
        layout.addLayout(btn_layout)

        self._table = _make_table(["ID", "Username", "Ruolo", "Negozio", "Attivo"])
        layout.addWidget(self._table)

        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn.clicked.connect(self._on_edit)

    def refresh(self) -> None:
        users = list_users()
        stores = {s.id: s for s in list_stores()}
        self._table.setRowCount(len(users))
        for row, u in enumerate(users):
            _set_cell(self._table, row, 0, str(u.id))
            _set_cell(self._table, row, 1, u.username, bold=True)
            role_color = QColor("#8e44ad") if u.role == "admin" else QColor("#2c3e50")
            _set_cell(self._table, row, 2, u.role, color=role_color)
            store_name = stores[u.store_id].name if u.store_id and u.store_id in stores else "—"
            _set_cell(self._table, row, 3, store_name)
            active_text = "Sì" if u.is_active else "No"
            active_color = QColor("#27ae60") if u.is_active else QColor("#e74c3c")
            _set_cell(self._table, row, 4, active_text, color=active_color)
        self._table.resizeColumnsToContents()

    def _selected_user_id(self) -> Optional[int]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _on_add(self) -> None:
        stores = list_stores()
        dlg = _UserDialog(stores=stores, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                create_user(dlg.username, dlg.password, role=dlg.role, store_id=dlg.store_id)
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(self, "Errore", str(exc))

    def _on_edit(self) -> None:
        uid = self._selected_user_id()
        if uid is None:
            QMessageBox.information(self, "Selezione", "Seleziona un utente da modificare.")
            return
        users = {u.id: u for u in list_users()}
        user = users.get(uid)
        if user is None:
            QMessageBox.warning(self, "Errore", "Utente non trovato. Aggiornare la lista.")
            self.refresh()
            return
        stores = list_stores()
        dlg = _UserDialog(stores=stores, user=user, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                kwargs: dict = {
                    "username": dlg.username,
                    "role": dlg.role,
                    "store_id": dlg.store_id,
                    "is_active": dlg.is_active,
                }
                if dlg.password:
                    kwargs["password"] = dlg.password
                update_user(uid, **kwargs)
                self.refresh()
            except Exception as exc:
                QMessageBox.warning(self, "Errore", str(exc))


class _FoldersTab(QWidget):
    folders_changed: Signal = Signal()

    def __init__(self, watcher: FolderWatcher, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._watcher = watcher
        self._setup_ui()
        self._refresh_stores()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Store selector
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Negozio:"))
        self._store_combo = QComboBox()
        self._store_combo.setMinimumWidth(220)
        self._store_combo.currentIndexChanged.connect(self._on_store_changed)
        selector_row.addWidget(self._store_combo)
        selector_row.addStretch()
        layout.addLayout(selector_row)

        btn_layout, (self._add_btn, self._remove_btn) = _action_buttons(
            "+ Aggiungi cartella", "✕ Rimuovi"
        )
        layout.addLayout(btn_layout)

        self._table = _make_table(["ID", "Percorso", "Tipo", "Attiva"])
        layout.addWidget(self._table)

        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn.clicked.connect(self._on_remove)

    def refresh_stores(self) -> None:
        """Called externally when stores list changes."""
        self._refresh_stores()

    def _refresh_stores(self) -> None:
        current_id = self._store_combo.currentData()
        self._store_combo.blockSignals(True)
        self._store_combo.clear()
        for s in list_stores():
            self._store_combo.addItem(f"{s.name} ({s.code})", s.id)
        # Try to restore selection
        if current_id is not None:
            idx = self._store_combo.findData(current_id)
            if idx >= 0:
                self._store_combo.setCurrentIndex(idx)
        self._store_combo.blockSignals(False)
        self._refresh_folders()

    def _refresh_folders(self) -> None:
        store_id = self._store_combo.currentData()
        if store_id is None:
            self._table.setRowCount(0)
            return
        folders = list_watched_folders(store_id)
        self._table.setRowCount(len(folders))
        for row, f in enumerate(folders):
            _set_cell(self._table, row, 0, str(f.id))
            _set_cell(self._table, row, 1, f.source_path)
            _set_cell(self._table, row, 2, f.folder_type, bold=True)
            active_text = "Sì" if f.is_active else "No"
            _set_cell(self._table, row, 3, active_text,
                      color=QColor("#27ae60") if f.is_active else QColor("#e74c3c"))
        self._table.resizeColumnsToContents()

    def _on_store_changed(self) -> None:
        self._refresh_folders()

    def _selected_folder_id(self) -> Optional[int]:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return int(item.text()) if item else None

    def _on_add(self) -> None:
        stores = list_stores()
        if not stores:
            QMessageBox.information(self, "Nessun negozio", "Crea prima almeno un negozio.")
            return
        dlg = _FolderDialog(stores=stores,
                            preselect_store_id=self._store_combo.currentData(),
                            parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            try:
                add_watched_folder(dlg.store_id, dlg.path, dlg.folder_type)
                # Reload watcher dynamically
                self._watcher.add_folder(dlg.path, dlg.folder_type, dlg.store_id)
                self._refresh_folders()
                self.folders_changed.emit()
                logger.info("Admin added watched folder: %s", dlg.path)
            except Exception as exc:
                QMessageBox.warning(self, "Errore", str(exc))

    def _on_remove(self) -> None:
        fid = self._selected_folder_id()
        if fid is None:
            QMessageBox.information(self, "Selezione", "Seleziona una cartella da rimuovere.")
            return
        # Find path before deleting
        store_id = self._store_combo.currentData()
        folders = {f.id: f for f in list_watched_folders(store_id)} if store_id else {}
        folder = folders.get(fid)

        reply = QMessageBox.question(
            self, "Conferma rimozione",
            "Rimuovere la cartella dal monitoraggio?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            remove_watched_folder(fid)
            if folder:
                self._watcher.remove_folder(folder.source_path)
            self._refresh_folders()
            self.folders_changed.emit()


class _LogTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Filters
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Negozio:"))

        self._store_filter = QComboBox()
        self._store_filter.setMinimumWidth(180)
        filter_row.addWidget(self._store_filter)

        filter_row.addSpacing(16)
        self._refresh_btn = QPushButton("↻ Aggiorna")
        self._refresh_btn.clicked.connect(self.refresh)
        filter_row.addWidget(self._refresh_btn)
        filter_row.addStretch()

        layout.addLayout(filter_row)

        self._table = _make_table(
            ["Data/Ora", "Operatore", "Negozio", "File", "Azione", "Barcode"]
        )
        layout.addWidget(self._table)

        # Connect filter once here — NOT inside refresh()
        self._store_filter.currentIndexChanged.connect(self._on_filter_changed)

    def _on_filter_changed(self) -> None:
        self._load_entries()

    def refresh(self) -> None:
        """Refresh store filter list and reload log entries."""
        current_store_id = self._store_filter.currentData()
        self._store_filter.blockSignals(True)
        self._store_filter.clear()
        self._store_filter.addItem("Tutti i negozi", None)
        try:
            for s in list_stores():
                self._store_filter.addItem(f"{s.name} ({s.code})", s.id)
        except Exception as exc:
            logger.warning("Failed to load stores in log tab: %s", exc)
        if current_store_id is not None:
            idx = self._store_filter.findData(current_store_id)
            if idx >= 0:
                self._store_filter.setCurrentIndex(idx)
        self._store_filter.blockSignals(False)
        self._load_entries()

    def _load_entries(self) -> None:
        """Load log entries from DB and populate the table."""
        store_id = self._store_filter.currentData()
        try:
            entries = list_operation_log(store_id=store_id, limit=500)
        except Exception as exc:
            logger.error("Failed to load operation log: %s", exc)
            QMessageBox.warning(self, "Errore", f"Impossibile caricare il log:\n{exc}")
            return

        self._table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            try:
                barcodes = json.loads(e.barcodes_json)
                barcodes_text = ", ".join(barcodes) if barcodes else "—"
            except Exception:
                barcodes_text = e.barcodes_json

            action_color = QColor("#27ae60") if e.action == "confirmed" else QColor("#e74c3c")
            action_label = "Confermato" if e.action == "confirmed" else "Scartato"

            _set_cell(self._table, row, 0, e.processed_at)
            _set_cell(self._table, row, 1, e.username)
            _set_cell(self._table, row, 2, e.store_name)
            _set_cell(self._table, row, 3, e.filename, bold=True)
            _set_cell(self._table, row, 4, action_label, color=action_color)
            _set_cell(self._table, row, 5, barcodes_text)

        self._table.resizeColumnsToContents()


# ---------------------------------------------------------------------------
# Main admin panel dialog
# ---------------------------------------------------------------------------

class AdminPanel(QDialog):
    """Full-screen admin dialog with tabs for stores, users, folders and log.

    Args:
        user: Currently logged-in admin user.
        watcher: Active FolderWatcher (for dynamic reload).
        parent: Parent widget.
    """

    def __init__(self, user: User, watcher: FolderWatcher,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._user = user
        self._watcher = watcher
        self.setWindowTitle("Pannello Amministrazione")
        self.resize(900, 600)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._tabs = QTabWidget()

        self._stores_tab = _StoresTab()
        self._users_tab = _UsersTab()
        self._folders_tab = _FoldersTab(watcher=self._watcher)
        self._log_tab = _LogTab()

        self._tabs.addTab(self._stores_tab, "Negozi")
        self._tabs.addTab(self._users_tab, "Utenze")
        self._tabs.addTab(self._folders_tab, "Cartelle")
        self._tabs.addTab(self._log_tab, "Log Operazioni")

        layout.addWidget(self._tabs)

        close_btn = QPushButton("Chiudi")
        close_btn.setMaximumWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # When stores change, refresh dependent tabs
        self._stores_tab.stores_changed.connect(self._users_tab.refresh)
        self._stores_tab.stores_changed.connect(self._folders_tab.refresh_stores)
        self._stores_tab.stores_changed.connect(self._log_tab.refresh)

        # Refresh log when switching to its tab
        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.widget(index) is self._log_tab:
            self._log_tab.refresh()
