"""Login dialog window."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.database.db import User, authenticate
from src.utils.logger import get_logger

logger = get_logger("gui.login_dialog")


class LoginDialog(QDialog):
    """Modal dialog that collects credentials and authenticates the user."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._user: Optional[User] = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def authenticated_user(self) -> Optional[User]:
        """Return the authenticated User after a successful login, else None."""
        return self._user

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("Accesso — DDT Scanner Manager")
        self.setFixedSize(380, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        # Title
        title = QLabel("DDT Scanner Manager")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel("Inserisci le credenziali per accedere")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666;")
        root.addWidget(subtitle)

        # Form
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setSpacing(10)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("Username")
        self._username_edit.setMinimumHeight(30)
        form.addRow("Utente:", self._username_edit)

        self._password_edit = QLineEdit()
        self._password_edit.setPlaceholderText("Password")
        self._password_edit.setEchoMode(QLineEdit.Password)
        self._password_edit.setMinimumHeight(30)
        form.addRow("Password:", self._password_edit)

        root.addLayout(form)

        # Error label (hidden by default)
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setStyleSheet("color: #c0392b; font-weight: bold;")
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._login_btn = QPushButton("Accedi")
        self._login_btn.setMinimumWidth(100)
        self._login_btn.setMinimumHeight(32)
        self._login_btn.setDefault(True)
        self._login_btn.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; border-radius: 4px; }"
            "QPushButton:hover { background-color: #3498db; }"
            "QPushButton:pressed { background-color: #1a5276; }"
        )
        btn_row.addWidget(self._login_btn)

        root.addLayout(btn_row)

        # Connections
        self._login_btn.clicked.connect(self._on_login)
        self._password_edit.returnPressed.connect(self._on_login)
        self._username_edit.returnPressed.connect(self._password_edit.setFocus)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_login(self) -> None:
        """Validate credentials and accept/reject the dialog."""
        username = self._username_edit.text().strip()
        password = self._password_edit.text()

        if not username:
            self._show_error("Inserisci il nome utente.")
            self._username_edit.setFocus()
            return

        if not password:
            self._show_error("Inserisci la password.")
            self._password_edit.setFocus()
            return

        self._login_btn.setEnabled(False)
        self._login_btn.setText("Verifica in corso…")

        user = authenticate(username, password)

        self._login_btn.setEnabled(True)
        self._login_btn.setText("Accedi")

        if user is None:
            self._show_error("Credenziali non valide.")
            self._password_edit.clear()
            self._password_edit.setFocus()
            logger.warning("Failed login attempt for username '%s'.", username)
            return

        self._user = user
        self._error_label.setVisible(False)
        logger.info("User '%s' logged in via dialog.", username)
        self.accept()

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)
