"""Application entry point."""

import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from src.config import APP_NAME, APP_VERSION, BASE_DIR
from src.database.db import initialize_database
from src.gui.login_dialog import LoginDialog
from src.gui.main_window import MainWindow
from src.gui.styles import APP_STYLESHEET
from src.utils.logger import setup_logging, get_logger


def main() -> None:
    """Bootstrap the application."""
    setup_logging()
    logger = get_logger("main")
    logger.info("Starting %s v%s", APP_NAME, APP_VERSION)

    # Create QApplication once, before any QWidget or QMessageBox
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(APP_STYLESHEET)

    icon_path = BASE_DIR / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Initialize DB (creates tables + default admin if needed)
    try:
        initialize_database()
    except Exception as exc:
        logger.critical("Database initialization failed: %s", exc)
        QMessageBox.critical(None, "Errore Database", f"Impossibile inizializzare il database:\n{exc}")
        sys.exit(1)

    # Show login dialog; exit if the user closes it without logging in
    dialog = LoginDialog()
    if dialog.exec() != LoginDialog.Accepted:
        logger.info("Login cancelled — exiting.")
        sys.exit(0)

    user = dialog.authenticated_user
    if user is None:
        logger.error("Login accepted but authenticated_user is None.")
        sys.exit(1)

    logger.info("Logged in as '%s' (role: %s).", user.username, user.role)

    window = MainWindow(user)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
