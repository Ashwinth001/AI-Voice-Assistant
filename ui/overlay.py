# -*- coding: utf-8 -*-
"""System overlay: faded, always-on-top UI that does not interfere with other apps."""

import sys
import config.settings as settings

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
    from PyQt6.QtCore import Qt, QPoint
    from PyQt6.QtGui import QFont, QColor, QPalette
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False


class OverlayWindow(QWidget if PYQT_AVAILABLE else object):
    """Faded overlay in a corner; shows status and last line. Does not steal focus."""

    def __init__(self):
        if not PYQT_AVAILABLE:
            return
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        w, h = settings.OVERLAY_WIDTH, settings.OVERLAY_HEIGHT
        self.setFixedSize(w, h)
        self._opacity = min(0.85, max(0.5, getattr(settings, "OVERLAY_OPACITY", 0.35)))
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(self._opacity)
        self.setGraphicsEffect(self._opacity_effect)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.setStyleSheet("background-color: rgba(30, 30, 45, 230); border-radius: 8px;")
        self._status_label = QLabel("Assistant")
        self._status_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Normal))
        self._status_label.setStyleSheet("color: rgb(220, 220, 240); background: transparent;")
        self._status_label.setWordWrap(True)
        self._text_label = QLabel("")
        self._text_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        self._text_label.setStyleSheet("color: rgb(200, 200, 220); background: transparent;")
        self._text_label.setWordWrap(True)
        self._text_label.setMaximumHeight(48)
        layout.addWidget(self._status_label)
        layout.addWidget(self._text_label)
        self._position_window()

    def _position_window(self) -> None:
        if not PYQT_AVAILABLE:
            return
        screen = QApplication.primaryScreen().geometry()
        margin = settings.OVERLAY_MARGIN
        w, h = self.width(), self.height()
        corner = getattr(settings, "OVERLAY_CORNER", "bottom_right")
        if corner == "top_left":
            x, y = margin, margin
        elif corner == "top_right":
            x, y = screen.width() - w - margin, margin
        elif corner == "bottom_left":
            x, y = margin, screen.height() - h - margin
        else:
            x, y = screen.width() - w - margin, screen.height() - h - margin
        self.move(x, y)

    def set_status(self, text: str) -> None:
        if PYQT_AVAILABLE and hasattr(self, "_status_label"):
            self._status_label.setText(text)

    def set_line(self, text: str) -> None:
        if PYQT_AVAILABLE and hasattr(self, "_text_label"):
            self._text_label.setText(text[:120] + ("..." if len(text) > 120 else ""))

    def show_overlay(self) -> None:
        if PYQT_AVAILABLE:
            self.showNormal()
            self.show()
            self.raise_()
            self.activateWindow()

    def close_overlay(self) -> None:
        if PYQT_AVAILABLE:
            self.close()


def create_overlay_app():
    """Create QApplication and overlay window. Returns (app, overlay) or (None, None) if PyQt not available."""
    if not PYQT_AVAILABLE:
        return None, None
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    overlay = OverlayWindow()
    return app, overlay
