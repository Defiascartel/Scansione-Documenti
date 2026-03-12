"""Application-wide Qt stylesheet."""

APP_STYLESHEET = """
/* ── Base ─────────────────────────────────────────────── */
QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #2c3e50;
    background-color: #f5f6fa;
}

QMainWindow {
    background-color: #f5f6fa;
}

QDialog {
    background-color: #f5f6fa;
}

/* ── Menu bar ─────────────────────────────────────────── */
QMenuBar {
    background-color: #2c3e50;
    color: #ecf0f1;
    padding: 2px 4px;
    spacing: 2px;
}
QMenuBar::item {
    padding: 4px 10px;
    border-radius: 3px;
}
QMenuBar::item:selected {
    background-color: #34495e;
}

QMenu {
    background-color: #ffffff;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 4px 0;
}
QMenu::item {
    padding: 6px 24px;
}
QMenu::item:selected {
    background-color: #d5e8f5;
    color: #1a5276;
}
QMenu::separator {
    height: 1px;
    background-color: #e0e0e0;
    margin: 3px 10px;
}

/* ── Status bar ───────────────────────────────────────── */
QStatusBar {
    background-color: #ecf0f1;
    border-top: 1px solid #bdc3c7;
    color: #555;
    font-size: 12px;
}

/* ── Splitter ─────────────────────────────────────────── */
QSplitter::handle {
    background-color: #dde1e7;
    width: 2px;
    height: 2px;
}
QSplitter::handle:hover {
    background-color: #2980b9;
}

/* ── Tab widget ───────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #dde1e7;
    border-radius: 4px;
    background-color: #ffffff;
}
QTabBar::tab {
    background-color: #ecf0f1;
    border: 1px solid #dde1e7;
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    color: #555;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #2c3e50;
    font-weight: bold;
    border-bottom: 2px solid #2980b9;
}
QTabBar::tab:hover:!selected {
    background-color: #dde1e7;
}

/* ── Buttons (default) ────────────────────────────────── */
QPushButton {
    background-color: #ecf0f1;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 5px 14px;
    color: #2c3e50;
}
QPushButton:hover {
    background-color: #d5d8dc;
    border-color: #aab0b6;
}
QPushButton:pressed {
    background-color: #bdc3c7;
}
QPushButton:disabled {
    background-color: #f2f3f4;
    color: #aab7b8;
    border-color: #d5d8dc;
}

/* ── Line edit ────────────────────────────────────────── */
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: #2980b9;
    selection-color: white;
}
QLineEdit:focus {
    border-color: #2980b9;
    outline: none;
}
QLineEdit:disabled {
    background-color: #f2f3f4;
    color: #aab7b8;
}

/* ── ComboBox ─────────────────────────────────────────── */
QComboBox {
    background-color: #ffffff;
    border: 1px solid #bdc3c7;
    border-radius: 4px;
    padding: 4px 8px;
}
QComboBox:focus {
    border-color: #2980b9;
}
QComboBox::drop-down {
    border-left: 1px solid #bdc3c7;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #bdc3c7;
    selection-background-color: #d5e8f5;
    selection-color: #1a5276;
}

/* ── Tables ───────────────────────────────────────────── */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8f9fa;
    gridline-color: #e0e3e8;
    border: 1px solid #dde1e7;
    border-radius: 4px;
}
QTableWidget::item {
    padding: 4px 8px;
}
QTableWidget::item:selected {
    background-color: #d5e8f5;
    color: #1a5276;
}
QHeaderView::section {
    background-color: #ecf0f1;
    border: none;
    border-right: 1px solid #dde1e7;
    border-bottom: 1px solid #dde1e7;
    padding: 5px 8px;
    font-weight: bold;
    color: #555;
}

/* ── Tree widget (queue panel) ────────────────────────── */
QTreeWidget {
    background-color: #ffffff;
    alternate-background-color: #f8f9fa;
    border: 1px solid #dde1e7;
    border-radius: 4px;
    show-decoration-selected: 1;
}
QTreeWidget::item {
    padding: 3px 4px;
}
QTreeWidget::item:selected {
    background-color: #d5e8f5;
    color: #1a5276;
}
QTreeWidget::item:hover {
    background-color: #eaf4fb;
}
QTreeWidget::branch:has-children:closed {
    image: none;
    border: none;
}

/* ── List widget (barcode editor) ─────────────────────── */
QListWidget {
    background-color: #ffffff;
    alternate-background-color: #f8f9fa;
    border: 1px solid #dde1e7;
    border-radius: 4px;
}
QListWidget::item {
    padding: 5px 8px;
    border-bottom: 1px solid #f0f0f0;
}
QListWidget::item:selected {
    background-color: #d5e8f5;
    color: #1a5276;
}

/* ── Graphics view (document viewer) ─────────────────── */
QGraphicsView {
    background-color: #3d3d3d;
    border: 1px solid #2c2c2c;
    border-radius: 4px;
}

/* ── Scrollbars ───────────────────────────────────────── */
QScrollBar:vertical {
    background: #f0f0f0;
    width: 10px;
    margin: 0;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #bdc3c7;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #95a5a6;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: #f0f0f0;
    height: 10px;
    margin: 0;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #bdc3c7;
    border-radius: 5px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover {
    background: #95a5a6;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ── Labels ───────────────────────────────────────────── */
QLabel {
    background: transparent;
}

/* ── CheckBox ─────────────────────────────────────────── */
QCheckBox {
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #bdc3c7;
    border-radius: 3px;
    background: white;
}
QCheckBox::indicator:checked {
    background-color: #2980b9;
    border-color: #2471a3;
}

/* ── Dialog button box ────────────────────────────────── */
QDialogButtonBox QPushButton {
    min-width: 80px;
}

/* ── Form layout labels ───────────────────────────────── */
QFormLayout QLabel {
    color: #555;
}

/* ── Tool tips ────────────────────────────────────────── */
QToolTip {
    background-color: #2c3e50;
    color: white;
    border: none;
    padding: 4px 8px;
    border-radius: 3px;
    font-size: 12px;
}
"""
