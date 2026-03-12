"""Center panel — zoomable/pannable/rotatable document viewer."""

from io import BytesIO
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QTransform, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.logger import get_logger

logger = get_logger("gui.document_viewer")


class DocumentViewer(QWidget):
    """Displays a scanned document with zoom, pan and rotation support.

    Supported formats: JPG, JPEG, PNG, TIFF, BMP (via Qt) and PDF first-page
    (via pdf2image if installed).
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._rotation: int = 0
        self._base_pixmap: Optional[QPixmap] = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_file(self, path: Path) -> None:
        """Load and display a file.

        Args:
            path: Absolute path to the image or PDF file.
        """
        self._rotation = 0
        self._filename_label.setText(path.name)

        ext = path.suffix.lower()
        try:
            if ext == ".pdf":
                pixmap = self._load_pdf_first_page(path)
            else:
                pixmap = QPixmap(str(path))
        except Exception as exc:
            logger.error("Unexpected error loading '%s': %s", path, exc)
            pixmap = None

        if pixmap and not pixmap.isNull():
            self._base_pixmap = pixmap
            self._apply_rotation()
        else:
            logger.warning("Failed to load pixmap for: %s", path)
            self._scene.clear()
            self._filename_label.setText(f"{path.name}  ⚠ anteprima non disponibile")

    def clear(self) -> None:
        """Clear the viewer."""
        self._scene.clear()
        self._base_pixmap = None
        self._filename_label.setText("")
        self._rotation = 0

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        self._zoom_in_btn = self._make_tool_btn("+", "Zoom avanti")
        self._zoom_out_btn = self._make_tool_btn("−", "Zoom indietro")
        self._rotate_btn = self._make_tool_btn("↻", "Ruota 90°")
        self._fit_btn = self._make_tool_btn("[ ]", "Adatta alla finestra")

        for btn in (self._zoom_in_btn, self._zoom_out_btn, self._rotate_btn, self._fit_btn):
            toolbar.addWidget(btn)

        toolbar.addStretch()

        self._filename_label = QLabel("")
        self._filename_label.setStyleSheet("color: #555; font-size: 11px; padding-right: 4px;")
        toolbar.addWidget(self._filename_label)

        layout.addLayout(toolbar)

        # Graphics view
        self._scene = QGraphicsScene()
        self._view = _ZoomableGraphicsView(self._scene)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._view.setRenderHint(self._view.renderHints())
        layout.addWidget(self._view)

        # Connections
        self._zoom_in_btn.clicked.connect(lambda: self._view.zoom(1.2))
        self._zoom_out_btn.clicked.connect(lambda: self._view.zoom(1 / 1.2))
        self._rotate_btn.clicked.connect(self._rotate_cw)
        self._fit_btn.clicked.connect(self._fit_to_window)

    @staticmethod
    def _make_tool_btn(text: str, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(32, 28)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(
            "QPushButton { border: 1px solid #ccc; border-radius: 3px; background: #f5f5f5; }"
            "QPushButton:hover { background: #e0e0e0; }"
        )
        return btn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_pdf_first_page(self, path: Path) -> Optional[QPixmap]:
        try:
            import pdf2image  # optional dependency

            pages = pdf2image.convert_from_path(
                str(path), dpi=150, first_page=1, last_page=1
            )
            if not pages:
                return None

            buf = BytesIO()
            pages[0].save(buf, format="PNG")
            buf.seek(0)
            pixmap = QPixmap()
            pixmap.loadFromData(buf.read())
            return pixmap if not pixmap.isNull() else None

        except ImportError:
            logger.warning("pdf2image not installed — cannot render PDF preview.")
            return None
        except Exception as exc:
            logger.error("PDF render error for '%s': %s", path, exc)
            return None

    def _apply_rotation(self) -> None:
        if self._base_pixmap is None:
            return
        transform = QTransform().rotate(self._rotation)
        rotated = self._base_pixmap.transformed(
            transform, Qt.TransformationMode.SmoothTransformation
        )
        self._scene.clear()
        self._scene.addPixmap(rotated)
        self._scene.setSceneRect(QRectF(rotated.rect()))
        self._fit_to_window()

    def _rotate_cw(self) -> None:
        self._rotation = (self._rotation + 90) % 360
        self._apply_rotation()

    def _fit_to_window(self) -> None:
        if self._scene.items():
            self._view.fitInView(
                self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )


class _ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView with mouse-wheel zoom."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom(factor)

    def zoom(self, factor: float) -> None:
        self.scale(factor, factor)
