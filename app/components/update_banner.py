"""「发现新版本」对话框顶部的横幅：标题、版本变化和抱礼盒的小人。"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import TitleLabel, isDarkTheme

from app.common.mascot import Mascot, load_mascot
from app.overview.star_track import paint_background, paint_star_track
from app.overview.style import text_color
from app.overview.widgets import Pill
from app.pages.common import is_evernight

RADIUS = 9  # 与对话框的圆角对齐


class Arrow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 16)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(text_color(secondary=True), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                            Qt.PenJoinStyle.RoundJoin))
        painter.drawLine(QPointF(2, 8), QPointF(17, 8))
        painter.drawPolyline(QPolygonF([QPointF(12, 3), QPointF(17, 8), QPointF(12, 13)]))


class UpdateBanner(QWidget):
    def __init__(self, title, parent=None, *, height=116):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.titleLabel = TitleLabel(title, self)
        self.currentPill = Pill(self, height=26)
        self.arrow = Arrow(self)
        self.targetPill = Pill(self, height=26, strong=True)
        self.versions = QWidget(self)
        row = QHBoxLayout(self.versions)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        for widget in (self.currentPill, self.arrow, self.targetPill):
            row.addWidget(widget)
        row.addStretch(1)
        self.versions.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 0, 170, 0)
        layout.setSpacing(8)
        layout.addStretch(1)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.versions)
        layout.addStretch(1)

    def setVersions(self, current, target):
        evernight = is_evernight()
        surface = QColor(0, 0, 0, 72) if isDarkTheme() or evernight else QColor(255, 255, 255, 235)
        self.currentPill.setPill(current, "neutral", evernight=evernight, surface=surface)
        self.targetPill.setPill(target, "accent", evernight=evernight, surface=surface)
        self.versions.setVisible(bool(current and target))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())
        evernight = is_evernight()
        mode = "evernight" if evernight else "dark" if isDarkTheme() else "light"
        path = QPainterPath()
        path.moveTo(0, rect.height())
        path.lineTo(0, RADIUS)
        path.arcTo(0, 0, RADIUS * 2, RADIUS * 2, 180, -90)
        path.lineTo(rect.width() - RADIUS, 0)
        path.arcTo(rect.width() - RADIUS * 2, 0, RADIUS * 2, RADIUS * 2, 90, -90)
        path.lineTo(rect.width(), rect.height())
        path.closeSubpath()
        painter.setClipPath(path)
        center = rect.width() - 96
        paint_background(painter, rect, mode)
        paint_star_track(painter, rect, mode, center, fade_from=min(rect.width() * 0.42, 300))
        ratio = self.devicePixelRatioF()
        pixmap = load_mascot(Mascot.GIFT, self.height() - 8, ratio, evernight=evernight)
        width, height = pixmap.width() / ratio, pixmap.height() / ratio
        painter.drawPixmap(QPointF(center - width / 2, rect.height() - height), pixmap)
