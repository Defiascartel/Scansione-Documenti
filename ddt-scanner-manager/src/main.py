"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from src.config import APP_NAME, APP_VERSION
from src.database.db import initialize_database
from src.gui.login_dialog import LoginDialog
from src.utils.logger import setup_logging, get_logger


def main() -> None:
    """Bootstrap the application."""
    setup_logging()
    logger = get_logger("main")
    logger.info("Starting %s v%s", APP_NAME, APP_VERSION)

    # Initialize DB (creates tables + default admin if needed)
    try:
        initialize_database()
    except Exception as exc:
        # Show error before Qt app is shown
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Errore Database", f"Impossibile inizializzare il database:\n{exc}")
        sys.exit(1)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # Show login dialog; exit if the user closes it without logging in
    dialog = LoginDialog()
    if dialog.exec() != LoginDialog.Accepted:
        logger.info("Login cancelled — exiting.")
        sys.exit(0)

    user = dialog.authenticated_user
    logger.info("Logged in as '%s' (role: %s).", user.username, user.role)

    # TODO Fase 4: open MainWindow(user) here
    QMessageBox.information(
        None,
        "Accesso effettuato",
        f"Benvenuto, {user.username}!\nRuolo: {user.role}\n\n(La finestra principale sarà disponibile nella Fase 4)",
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
