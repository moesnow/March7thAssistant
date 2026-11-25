"""向导左侧：标题、五个步骤和 Q 版三月七。"""
from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QAbstractButton, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, isDarkTheme, qconfig, setFont

from app.overview.greeting import MascotWidget
from app.overview.star_track import COLORS, paint_star_track
from app.pages import style
from app.pages.common import is_evernight, secondary

WIDTH = 252
MASCOT_MAX_WIDTH = 220  # 压扁变宽时也不超出左栏
RADIUS = 12
ART_HEIGHT = 214


class StepRow(QAbstractButton):
    """一个步骤：编号或结果、名称和一句话。走到过的步骤可以点回去。"""
    HEIGHT = 50

    def __init__(self, number, parent=None):
        super().__init__(parent)
        self._number = number
        self._state = "todo"
        self._note = ""
        self._kind = "neutral"
        self._hover = False
        self.setFixedHeight(self.HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def setStep(self, title, note, state, kind):
        """state：todo / current / done；kind：success / warning / neutral。"""
        self.setText(title)
        self._note, self._state, self._kind = note, state, kind
        self.setEnabled(state != "todo")
        self.setCursor(Qt.CursorShape.PointingHandCursor if state == "done" else Qt.CursorShape.ArrowCursor)
        self.setAccessibleName(f"{title} {note}".strip())
        self.setToolTip("")
        self.update()

    def state(self):
        return self._state

    def note(self):
        return self._note

    def sizeHint(self):
        return QSize(WIDTH, self.HEIGHT)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        if self._hover and self._state == "done":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.hover_fill())
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(8, 1, -8, -1), 6, 6)
        circle = QRectF(20, (self.HEIGHT - 28) / 2, 28, 28)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._state == "current":
            background, foreground = style.solid()
        else:
            kind = self._kind if self._state == "done" else "neutral"
            background, foreground = style.status_colors(kind)
        painter.setBrush(background)
        painter.drawEllipse(circle)
        if self._state == "done":
            style.glyph(painter, "alert" if self._kind == "warning" else "check", circle.adjusted(7, 7, -7, -7), foreground)
        else:
            painter.setFont(style.strong(13))
            painter.setPen(foreground)
            painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, str(self._number))
        left, width = 60, self.width() - 60 - 16
        title_font = style.strong(14)
        painter.setFont(title_font)
        painter.setPen(style.link() if self._state == "current" else style.muted() if self._state == "todo" else style.primary())
        painter.drawText(QRectF(left, 5, width, 20), Qt.AlignmentFlag.AlignVCenter,
                         QFontMetrics(title_font).elidedText(self.text(), Qt.TextElideMode.ElideRight, width))
        note_font = style.font(12)
        painter.setFont(note_font)
        painter.setPen(style.muted())
        painter.drawText(QRectF(left, 25, width, 18), Qt.AlignmentFlag.AlignVCenter,
                         QFontMetrics(note_font).elidedText(self._note, Qt.TextElideMode.ElideRight, width))


class StepRail(QWidget):
    stepClicked = Signal(int)

    def __init__(self, count, parent=None):
        super().__init__(parent)
        self.setFixedWidth(WIDTH)
        self._art = (None, QPixmap())
        self.titleLabel = BodyLabel(self)
        setFont(self.titleLabel, 18, QFont.Weight.DemiBold)
        self.titleLabel.setWordWrap(True)
        self.textLabel = secondary(CaptionLabel(self))
        self.textLabel.setWordWrap(True)
        self.rows = []
        head = QVBoxLayout()
        head.setContentsMargins(20, 0, 16, 0)
        head.setSpacing(4)
        head.addWidget(self.titleLabel)
        head.addWidget(self.textLabel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 24, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(head)
        layout.addSpacing(14)
        for index in range(count):
            row = StepRow(index + 1, self)
            row.clicked.connect(lambda _=False, i=index: self._clicked(i))
            self.rows.append(row)
            layout.addWidget(row)
        layout.addStretch(1)
        self.mascot = MascotWidget(self, max_width=MASCOT_MAX_WIDTH)
        qconfig.themeChanged.connect(self.restyle)
        qconfig.themeColorChanged.connect(self.restyle)

    def restyle(self, *_):
        self._art = (None, QPixmap())
        self.update()

    def setHeading(self, title, text):
        self.titleLabel.setText(title)
        self.textLabel.setText(text)

    def setPose(self, pose, *, bounce=False):
        """长夜月缺几个姿势，向导全程用三月七。"""
        if self.mascot.pose() is not pose:
            self.mascot.setPose(pose)
            if bounce:
                self.mascot.bounce()
        elif self.mascot.imageSize().isEmpty():
            self.mascot.setPose(pose)
        self._place()

    def _clicked(self, index):
        if self.rows[index].state() == "done":
            self.stepClicked.emit(index)

    def _place(self):
        """窗口太矮、放不下插画时不显示，不挡步骤。"""
        self.mascot.move((self.width() - self.mascot.width()) // 2, self.height() - self.mascot.height() + 2)
        bottom = max((row.geometry().bottom() for row in self.rows), default=0)
        self.mascot.setVisible(self.mascot.y() >= bottom - 6)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def showEvent(self, event):
        super().showEvent(event)
        self._place()

    def _mode(self):
        return "evernight" if is_evernight() else "dark" if isDarkTheme() else "light"

    def _background(self):
        ratio = self.devicePixelRatioF() or 1.0
        key = (self.size(), ratio, self._mode())
        if self._art[0] != key:
            pixmap = QPixmap(round(self.width() * ratio), round(self.height() * ratio))
            pixmap.setDevicePixelRatio(ratio)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect())
            stops = COLORS[self._mode()]["stops"]
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, QColor(stops[0]))
            gradient.setColorAt(0.55, QColor(stops[1]))
            gradient.setColorAt(1.0, QColor(stops[2]))
            painter.fillRect(rect, gradient)
            painter.drawPixmap(0, round(rect.height() - ART_HEIGHT), self._starTrack(ratio))
            painter.end()
            self._art = (key, pixmap)
        return self._art[1]

    def _starTrack(self, ratio):
        """星轨的光晕比这块区域高，上沿淡出，免得露出一条边。"""
        layer = QPixmap(round(self.width() * ratio), round(ART_HEIGHT * ratio))
        layer.setDevicePixelRatio(ratio)
        layer.fill(Qt.GlobalColor.transparent)
        rect = QRectF(0, 0, self.width(), ART_HEIGHT)
        painter = QPainter(layer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        paint_star_track(painter, rect, self._mode(), rect.width() / 2)
        fade = QLinearGradient(0, 0, 0, 72)
        fade.setColorAt(0.0, QColor(0, 0, 0, 0))
        fade.setColorAt(1.0, QColor(0, 0, 0, 255))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.fillRect(rect, fade)
        painter.end()
        return layer

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect.adjusted(0, 0, RADIUS * 2, 0), RADIUS, RADIUS)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, self._background())
