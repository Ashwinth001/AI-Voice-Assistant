# -*- coding: utf-8 -*-
"""
Avatar overlay: stylized face (glowing, dotted), speaking mouth, reactions.
Minimizes when another app is in focus; expands on hover.
"""

import sys
import math
import config.settings as settings

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
    from PyQt6.QtCore import Qt, QRect, QRectF, QPointF, QTimer
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QRadialGradient,
        QPainterPath, QFont, QLinearGradient
    )
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

# Windows: detect foreground window to minimize when user is in another app
def _get_foreground_hwnd():
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        return user32.GetForegroundWindow()
    except Exception:
        return None


class AvatarOverlayWidget(QWidget if PYQT_AVAILABLE else object):
    """Floating avatar: holographic dotted face, speaking mouth, reactions. Minimizes when other app focused."""

    SIZE_EXPANDED = (200, 260)
    SIZE_MINIMIZED = (56, 56)
    DOT_RADIUS = 2.2
    DOT_SPACING = 8
    MOUTH_ANIM_MS = 120

    def __init__(self):
        if not PYQT_AVAILABLE:
            return
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setMouseTracking(True)
        # State
        self._minimized = False
        self._reaction = "idle"  # idle, listening, thinking, speaking, happy, confused
        self._speaking = False
        self._mouth_phase = 0.0  # 0 = closed, 1 = open (for animation)
        self._blink = 0.0  # 0 = open, 1 = closed
        self._status_text = ""
        self._line_text = ""
        # Colors (cyan/light blue ethereal)
        self._face_color = QColor(100, 200, 255, 200)
        self._glow_color = QColor(80, 220, 255, 120)
        self._dot_color = QColor(150, 230, 255, 220)
        self._dot_color_dim = QColor(80, 180, 220, 160)
        # Size
        self._expanded_w, self._expanded_h = self.SIZE_EXPANDED
        self._min_w, self._min_h = self.SIZE_MINIMIZED
        self.setFixedSize(self._expanded_w, self._expanded_h)
        # Labels (when expanded)
        self._status_label = QLabel("", self)
        self._status_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Normal))
        self._status_label.setStyleSheet("color: rgba(220, 240, 255, 240); background: transparent;")
        self._status_label.setWordWrap(True)
        self._status_label.adjustSize()
        self._text_label = QLabel("", self)
        self._text_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Normal))
        self._text_label.setStyleSheet("color: rgba(200, 220, 240, 220); background: transparent;")
        self._text_label.setWordWrap(True)
        self._text_label.setMaximumWidth(self._expanded_w - 24)
        self._text_label.setMaximumHeight(44)
        self._layout_labels()
        # Timers
        self._mouth_timer = QTimer(self)
        self._mouth_timer.timeout.connect(self._tick_mouth)
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._tick_blink)
        self._focus_timer = QTimer(self)
        self._focus_timer.timeout.connect(self._check_foreground)
        self._focus_timer.start(450)
        self._blink_timer.start(2800)
        self._position_window()

    def _layout_labels(self):
        self._status_label.setGeometry(12, self._expanded_h - 72, self._expanded_w - 24, 20)
        self._text_label.setGeometry(12, self._expanded_h - 50, self._expanded_w - 24, 38)

    def _check_foreground(self):
        try:
            if not self.isVisible():
                return
            hwnd = _get_foreground_hwnd()
            if hwnd is None:
                return
            my_id = self.winId()
            if my_id is None:
                return
            try:
                my_hwnd = int(my_id)
            except (TypeError, ValueError):
                return
            if hwnd != my_hwnd and not self._minimized:
                self._set_minimized(True)
        except Exception:
            pass

    def _set_minimized(self, mini: bool):
        self._minimized = mini
        if mini:
            self.setFixedSize(self._min_w, self._min_h)
            self._status_label.hide()
            self._text_label.hide()
        else:
            self.setFixedSize(self._expanded_w, self._expanded_h)
            self._layout_labels()
            self._status_label.show()
            self._text_label.show()
        self._position_window()
        self.update()

    def enterEvent(self, event):
        if PYQT_AVAILABLE and self._minimized:
            self._set_minimized(False)
        super().enterEvent(event) if PYQT_AVAILABLE else None

    def _tick_mouth(self):
        if self._speaking:
            self._mouth_phase += 0.35
            if self._mouth_phase > 1.0:
                self._mouth_phase = 0.0
        else:
            self._mouth_phase = 0.0
        self.update()

    def _tick_blink(self):
        if self._blink > 0:
            self._blink = 0.0
        else:
            self._blink = 1.0
        self.update()

    def set_speaking(self, speaking: bool):
        self._speaking = speaking
        if speaking:
            self._reaction = "speaking"
            if not self._mouth_timer.isActive():
                self._mouth_timer.start(self.MOUTH_ANIM_MS)
        else:
            self._mouth_timer.stop()
            self._mouth_phase = 0.0
        self.update()

    def set_reaction(self, reaction: str):
        if reaction in ("idle", "listening", "thinking", "speaking", "happy", "confused"):
            self._reaction = reaction
        self.update()

    def set_status(self, text: str):
        self._status_text = text or ""
        if hasattr(self, "_status_label") and self._status_label:
            self._status_label.setText(self._status_text[:60])
        # Map status to reaction
        t = (text or "").lower()
        name = getattr(settings, "ASSISTANT_NAME", "Jarvis")
        if not text or (text.strip() == name):
            self.set_reaction("idle")
        elif "thinking" in t:
            self.set_reaction("thinking")
        elif "owner voice" in t or "listening" in t or "heard" in t:
            self.set_reaction("listening")
        elif "security" in t or "not recognized" in t:
            self.set_reaction("confused")
        elif text and not self._speaking:
            self.set_reaction("happy")

    def set_line(self, text: str):
        self._line_text = (text or "")[:120]
        if hasattr(self, "_text_label") and self._text_label:
            self._text_label.setText(self._line_text + ("..." if len(text or "") > 120 else ""))

    def _position_window(self):
        if not PYQT_AVAILABLE:
            return
        try:
            screen = QApplication.primaryScreen().geometry()
        except Exception:
            return
        margin = getattr(settings, "OVERLAY_MARGIN", 16)
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
        self.move(int(x), int(y))

    def paintEvent(self, event):
        if not PYQT_AVAILABLE:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        w, h = self.width(), self.height()
        if self._minimized:
            self._paint_face(painter, w, h, is_small=True)
        else:
            self._paint_face(painter, w, h, is_small=False)
        painter.end()

    def _paint_face(self, painter: "QPainter", w: int, h: int, is_small: bool):
        cx = w / 2.0
        # Face vertical center (slightly above geometric center for head)
        if is_small:
            face_h = h * 0.88
            cy = h * 0.5
            face_w = w * 0.85
        else:
            face_h = h * 0.52
            cy = h * 0.42
            face_w = w * 0.7
        # Glow behind face
        glow_r = max(face_w, face_h) * 0.7
        grad = QRadialGradient(cx, cy, glow_r)
        grad.setColorAt(0, self._glow_color)
        grad.setColorAt(0.5, QColor(60, 180, 220, 50))
        grad.setColorAt(1, QColor(40, 120, 180, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)
        # Face base (semi-transparent ellipse)
        face_rect = QRectF(cx - face_w / 2, cy - face_h / 2, face_w, face_h)
        lin = QLinearGradient(face_rect.left(), face_rect.top(), face_rect.right(), face_rect.bottom())
        lin.setColorAt(0, QColor(120, 210, 255, 180))
        lin.setColorAt(0.5, QColor(90, 190, 240, 200))
        lin.setColorAt(1, QColor(70, 160, 210, 160))
        painter.setBrush(QBrush(lin))
        painter.setPen(QPen(QColor(120, 200, 255, 100), 1))
        painter.drawEllipse(face_rect)
        # Dotted overlay (holographic effect)
        spacing = self.DOT_SPACING if not is_small else self.DOT_SPACING * 0.6
        r_dot = self.DOT_RADIUS if not is_small else self.DOT_RADIUS * 0.8
        rx, ry = face_w / 2, face_h / 2
        for i in range(-int(rx / spacing), int(rx / spacing) + 1):
            for j in range(-int(ry / spacing), int(ry / spacing) + 1):
                x = cx + i * spacing
                y = cy + j * spacing
                if (x - cx) ** 2 / (rx ** 2) + (y - cy) ** 2 / (ry ** 2) <= 1.0:
                    # Vary opacity for depth
                    d = math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max(rx, ry)
                    alpha = 200 - int(d * 80)
                    col = QColor(self._dot_color.red(), self._dot_color.green(), self._dot_color.blue(), min(255, max(80, alpha)))
                    painter.setBrush(QBrush(col))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(QPointF(x, y), r_dot, r_dot)
        # Eyes
        eye_y = cy - face_h * 0.12
        eye_dx = face_w * 0.2
        eye_w = face_w * 0.12
        eye_h = face_h * 0.06 if self._blink < 0.5 else face_h * 0.02
        if self._reaction == "thinking":
            eye_h *= 0.7
        for s in (-1, 1):
            ex = cx + s * eye_dx
            painter.setBrush(QBrush(QColor(40, 80, 120, 220)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(ex, eye_y), eye_w, eye_h)
        # Mouth
        mouth_y = cy + face_h * 0.22
        mouth_w = face_w * 0.25
        mouth_h = face_h * 0.06
        if self._speaking and self._mouth_phase > 0.3:
            # Open mouth (oval)
            open_h = mouth_h * (0.5 + 0.5 * self._mouth_phase)
            painter.setBrush(QBrush(QColor(60, 100, 140, 200)))
            painter.setPen(QPen(QColor(80, 140, 180, 180), 1))
            painter.drawEllipse(QPointF(cx, mouth_y), mouth_w * 0.7, open_h)
        else:
            # Closed: line or smile
            path = QPainterPath()
            if self._reaction == "happy":
                path.moveTo(cx - mouth_w, mouth_y)
                path.quadTo(cx, mouth_y + mouth_h * 1.5, cx + mouth_w, mouth_y)
            else:
                path.moveTo(cx - mouth_w * 0.8, mouth_y)
                path.lineTo(cx + mouth_w * 0.8, mouth_y)
            painter.setPen(QPen(QColor(60, 120, 160, 220), 2 if not is_small else 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

    def show_overlay(self):
        if PYQT_AVAILABLE:
            self.showNormal()
            self.show()
            self.raise_()

    def close_overlay(self):
        if PYQT_AVAILABLE:
            self._focus_timer.stop()
            self._mouth_timer.stop()
            self._blink_timer.stop()
            self.close()


def create_avatar_overlay():
    """Create QApplication and avatar overlay. Returns (app, overlay) or (None, None)."""
    if not PYQT_AVAILABLE:
        return None, None
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    overlay = AvatarOverlayWidget()
    return app, overlay
