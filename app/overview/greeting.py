"""总览顶部的问候区：状态胶囊、标题、说明、运行阶段、操作按钮，右侧是 Q 版小人和星轨背景。"""
import math

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, \
    QVariantAnimation, Signal
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPainterPathStroker, QPen, \
    QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, DropDownPushButton, FluentIcon as FIF, PrimaryPushButton, PushButton, \
    isDarkTheme, setCustomStyleSheet

from app.common.mascot import Mascot, load_mascot
from app.components.image_crossfade import ImageCrossFade
from module.localization import tr
from module.overview.snapshot import PHASE_NAMES

from .star_track import COLORS, paint_background, paint_star_track, rgba
from .style import GREETING_TONES, accent, animations_enabled, primary_button_qss, tinted_button_qss, with_alpha
from .widgets import PHASES, ElidedTitleLabel, LinkButton, PhaseProgress, Pill

MASCOT_HEIGHT = 172
MASCOT_MAX_WIDTH = 236
# 点小人的形变和安卓端首页一致：70 毫秒压到底，再由弹簧弹回。
SQUASH_WIDTH, SQUASH_HEIGHT = 0.14, 0.22
PRESS_MS, BOUNCE_MS = 70, 660
PRESS_CURVE = QEasingCurve(QEasingCurve.Type.BezierSpline)
PRESS_CURVE.addCubicBezierSegment(QPointF(0.4, 0.0), QPointF(0.2, 1.0), QPointF(1.0, 1.0))
SPRING_DAMPING, SPRING_STIFFNESS = 0.30, 700.0
SPRING_DECAY = SPRING_DAMPING * math.sqrt(SPRING_STIFFNESS)
SPRING_SPEED = math.sqrt(SPRING_STIFFNESS) * math.sqrt(1 - SPRING_DAMPING ** 2)
STRETCH = math.exp(-math.pi * SPRING_DECAY / SPRING_SPEED)  # 第一次弹起的幅度，相对压到底
LINK_ACTIONS = {"view_run", "view_result", "view_reason"}
SECONDARY_ACTIONS = {"choose_task", "toggle_pause"}
ICONS = {"start_full": FIF.PLAY, "continue": FIF.PLAY, "retry_step": FIF.SYNC, "start_task": FIF.SYNC,
         "configure": FIF.SETTING}


def squash_amount(elapsed, start=0.0):
    """点击后 elapsed 毫秒时的形变：1 是压到底，0 是原样，负数是弹起时拉长。start 是点击那一刻的形变。"""
    if elapsed < PRESS_MS:
        return start + (1.0 - start) * PRESS_CURVE.valueForProgress(elapsed / PRESS_MS)
    if elapsed >= BOUNCE_MS:
        return 0.0
    t = (elapsed - PRESS_MS) / 1000
    swing = math.cos(SPRING_SPEED * t) + SPRING_DECAY / SPRING_SPEED * math.sin(SPRING_SPEED * t)
    return math.exp(-SPRING_DECAY * t) * swing


class MascotWidget(QWidget):
    """Q 版小人。点一下会压扁再弹回，连点时从当前的形变继续。"""

    def __init__(self, parent=None, *, max_width=MASCOT_MAX_WIDTH):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._max_width = max_width
        self._pose = Mascot.FULL
        self._override = None
        self._evernight = False
        self._ratio = 0.0
        self._pixmap = QPixmap()
        self._squash = self._squash_start = 0.0
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(float(BOUNCE_MS))
        self.animation.setDuration(BOUNCE_MS)
        self.animation.valueChanged.connect(self._advance)

    def setPose(self, pose, *, evernight=False):
        if (pose, evernight) != (self._pose, self._evernight) or self._pixmap.isNull():
            self._pose, self._evernight = pose, evernight
            self._reload()

    def setOverride(self, pose):
        if pose != self._override:
            self._override = pose
            self._reload()

    def pose(self):
        return self._override or self._pose

    def _reload(self):
        pose = self.pose()
        ratio = self.devicePixelRatioF() or 1.0
        self._ratio = ratio
        pixmap = load_mascot(pose, MASCOT_HEIGHT, ratio, evernight=self._evernight)
        if not pixmap.isNull() and pixmap.width() / ratio > self._max_width:
            height = int(MASCOT_HEIGHT * self._max_width / (pixmap.width() / ratio))
            pixmap = load_mascot(pose, height, ratio, evernight=self._evernight)
        self._pixmap = pixmap
        # 压扁时变宽，弹起时变高，两侧和上方留出余量。
        self.setFixedSize(self.imageSize().width() + 2 * self._sideRoom(),
                          math.ceil(MASCOT_HEIGHT * (1 + SQUASH_HEIGHT * STRETCH)) + 2)
        self.update()

    def _sideRoom(self):
        return math.ceil(self.imageSize().width() * SQUASH_WIDTH / 2) + 2

    def imageSize(self):
        if self._pixmap.isNull():
            return QSize(0, 0)
        ratio = self._pixmap.devicePixelRatio() or 1.0
        return QSize(round(self._pixmap.width() / ratio), round(self._pixmap.height() / ratio))

    def imageRect(self):
        """没有形变时插画在控件里的位置。"""
        size = self.imageSize()
        return QRect(QPoint(self._sideRoom(), self.height() - 2 - size.height()), size)

    def bounce(self):
        if not animations_enabled():
            return
        self._squash_start = self._squash
        self.animation.stop()
        self.animation.start()

    def _advance(self, elapsed):
        self._squash = squash_amount(elapsed, self._squash_start)
        self.update()

    def _scale(self):
        return 1 + SQUASH_WIDTH * self._squash, 1 - SQUASH_HEIGHT * self._squash

    def showEvent(self, event):
        super().showEvent(event)
        if abs((self.devicePixelRatioF() or 1.0) - self._ratio) > 0.01:
            self._reload()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.bounce()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)
        size = self.imageSize()
        sx, sy = self._scale()
        painter.translate(self.width() / 2, self.height() - 2)
        painter.scale(sx, sy)
        painter.drawPixmap(QPointF(-size.width() / 2, -size.height()), self._pixmap)


class LogoHint(QLabel):
    """连点 LOGO 时的提示，从小人左侧往上飘（沿用旧主页横幅上的写法）。"""

    def __init__(self, parent, anchor):
        super().__init__(parent)
        self._anchor = anchor
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet('color: #ff91c1; font-family: "Sans Serif Collection", "Microsoft YaHei UI", '
                           '"PingFang SC", "Noto Sans CJK SC", sans-serif; font-size: 18px; font-weight: 600;')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._progress = 0.0
        self._text_path = QPainterPath()
        self._outline_path = QPainterPath()
        self._shadow_path = QPainterPath()
        self._motion = QEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(5000)
        self.animation.valueChanged.connect(self._advance)
        self.animation.finished.connect(self.hide)
        parent.installEventFilter(self)
        self.retranslateUi()
        self.hide()

    def retranslateUi(self):
        text = tr('别晃啦！本姑娘头好晕( ꩜ ᯅ ꩜;)')
        if text != self.text():
            self.setText(text)
            if self.animation.state() != QAbstractAnimation.State.Stopped:
                self._prepareText()
                self.update()

    def _prepareText(self):
        self.ensurePolished()
        path = QPainterPath()
        path.addText(0, 0, self.font(), self.text())
        bounds = path.boundingRect()
        self._text_path = path.translated(-bounds.left(), -bounds.top())
        stroke = QPainterPathStroker()
        stroke.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        stroke.setWidth(2.3)
        self._outline_path = stroke.createStroke(self._text_path)
        stroke.setWidth(4.0)
        self._shadow_path = stroke.createStroke(self._text_path).united(self._text_path).translated(0, 2.0)

    def play(self):
        self.animation.stop()
        self.retranslateUi()
        self._prepareText()
        self.setGeometry(self.parentWidget().rect())
        self._advance(0.0)
        self.show()
        self.raise_()
        self.animation.start()

    def dismiss(self):
        self.animation.stop()
        self.hide()

    def _advance(self, progress):
        self._progress = float(progress)
        self.update()

    def textRect(self):
        bounds = self._text_path.boundingRect()
        travel = self._motion.valueForProgress(self._progress)
        start_y, end_y = self.height() * 0.80, self.height() * 0.16
        center_y = start_y + (end_y - start_y) * travel
        right = self._anchor()
        x = (self.width() - bounds.width()) / 2 if right is None else right - bounds.width()
        x = max(12.0, min(x, self.width() - bounds.width() - 12.0))
        return QRectF(x, max(0.0, center_y - bounds.height() / 2), bounds.width(), bounds.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 - self._progress)
        painter.translate(self.textRect().topLeft())
        painter.fillPath(self._shadow_path, QColor(30, 10, 25, 115))
        painter.fillPath(self._outline_path, QColor('#622640'))
        painter.fillPath(self._text_path, QColor('#ff91c1'))

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)


class GreetingCard(QWidget):
    actionTriggered = Signal(object, object)  # Button、被点的控件
    menuRequested = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("overviewGreeting")
        self._evernight = False
        self._background_path = None
        self._background = QImage()
        self._cover = (QSize(), QImage())
        self._buttons_key = None
        self._buttons = []
        self._state = "ready"

        self.pill = Pill(self, dot=True, strong=True, height=24)
        self.titleLabel = ElidedTitleLabel(self)
        self.descriptionLabel = BodyLabel(self)
        self.descriptionLabel.setWordWrap(True)
        self.descriptionLabel.setTextColor(QColor(66, 66, 66), QColor(222, 222, 222))
        self.descriptionLabel.setMaximumWidth(640)
        self.phaseBox = QWidget(self)
        phaseLayout = QVBoxLayout(self.phaseBox)
        phaseLayout.setContentsMargins(0, 12, 0, 0)
        self.phaseProgress = PhaseProgress(self.phaseBox)
        self.phaseProgress.setMaximumWidth(560)
        phaseLayout.addWidget(self.phaseProgress)
        self.buttonBox = QWidget(self)
        self.buttonLayout = QHBoxLayout(self.buttonBox)
        self.buttonLayout.setContentsMargins(0, 0, 0, 0)
        self.buttonLayout.setSpacing(8)
        self.mascot = MascotWidget(self)
        self.crossfade = ImageCrossFade(self)
        self.logoHint = LogoHint(self, self._hintRight)
        self.logoHint.animation.finished.connect(lambda: self.mascot.setOverride(None))

        self.vBox = QVBoxLayout(self)
        self.vBox.setContentsMargins(28, 20, 28, 20)
        self.vBox.setSpacing(0)
        self.vBox.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignLeft)
        self.vBox.addSpacing(8)
        self.vBox.addWidget(self.titleLabel)
        self.vBox.addSpacing(2)
        self.vBox.addWidget(self.descriptionLabel)
        self.vBox.addWidget(self.phaseBox)
        self.vBox.addSpacing(16)
        self.vBox.addWidget(self.buttonBox, 0, Qt.AlignmentFlag.AlignLeft)
        self.vBox.addStretch(1)
        self.setMinimumHeight(188)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.menuRequested.emit(self.mapToGlobal(pos)))

    # ---------- 数据 ----------
    def render(self, greeting, *, show_mascot=True, background="", evernight=False):
        self._evernight = evernight
        if greeting is None:
            state, badge, title, description, pose, buttons, phase = (
                "ready", tr("总览"), tr("暂时读不到运行状态"), tr("稍后会自动重试。"), "chibi_full", (), None)
        else:
            state, badge, title, description = greeting.state, greeting.badge, greeting.title, greeting.description
            pose, buttons, phase = greeting.mascot, greeting.buttons, greeting.phase
        self._state = state
        surface = QColor(0, 0, 0, 72) if (isDarkTheme() or evernight) else QColor(255, 255, 255, 235)
        self.pill.setPill(badge, GREETING_TONES.get(state, "neutral"), evernight=evernight, surface=surface)
        self.titleLabel.setFullText(title)
        self.descriptionLabel.setText(description)
        running = state == "running" and phase in PHASES
        self.phaseBox.setVisible(running)
        if running:
            self.phaseProgress.setPhase(phase, [tr(PHASE_NAMES[name]) for name in PHASES], evernight=evernight)
        self._setButtons(tuple(buttons))
        self.mascot.setVisible(show_mascot)
        try:
            pose = Mascot(pose)
        except ValueError:
            pose = Mascot.FULL
        self.mascot.setPose(pose, evernight=evernight)
        self._setBackground(background)
        self._relayout()
        self.update()

    def _setBackground(self, path):
        path = path or ""
        if path == self._background_path:
            return
        self._background_path = path
        self._background = QImage(path) if path else QImage()
        self._cover = (QSize(), QImage())

    @staticmethod
    def _category(action, has_button):
        if action in LINK_ACTIONS:
            return "link" if has_button else "secondary"
        if action == "stop":
            return "danger"
        if action in SECONDARY_ACTIONS:
            return "secondary"
        return "primary"

    def _setButtons(self, buttons):
        key = (tuple((b.id, b.text, b.link, b.target) for b in buttons), self._evernight)
        if key == self._buttons_key:
            for widget in self._buttons:
                if isinstance(widget, LinkButton):
                    widget.refreshStyle()
            return
        self._buttons_key = key
        for widget in self._buttons:
            self.buttonLayout.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self._buttons = []
        has_button = any(button.id not in LINK_ACTIONS for button in buttons)
        order = {"primary": 0, "danger": 0, "secondary": 1, "link": 2}
        for button in sorted(buttons, key=lambda b: order[self._category(b.id, has_button)]):
            widget = self._makeButton(button, self._category(button.id, has_button))
            widget.clicked.connect(lambda _=False, b=button, w=widget: self.actionTriggered.emit(b, w))
            self.buttonLayout.addWidget(widget)
            self._buttons.append(widget)
        self.buttonBox.setVisible(bool(self._buttons))

    def _makeButton(self, button, category):
        parent = self.buttonBox
        if category == "link":
            widget = LinkButton(button.text + " ›", parent, size=14)
            widget.setEvernight(self._evernight)
            widget.setFixedHeight(32)
            return widget
        if button.id == "choose_task":
            return DropDownPushButton(button.text, parent)
        if button.id == "start_all":
            return PushButton(FIF.PEOPLE, button.text, parent)
        if button.id == "toggle_pause":
            icon = FIF.PLAY if button.text == tr("继续任务") else FIF.PAUSE
            return PushButton(icon, button.text, parent)
        if category == "secondary":
            return PushButton(button.text, parent)
        if category == "danger":
            light, dark = tinted_button_qss(self._evernight)
            color = QColor("#ba3032" if self._evernight else "#c93a76")
            dark_color = QColor("#e0656d" if self._evernight else "#f5a3c7")
            widget = PushButton(FIF.CLOSE.colored(color, dark_color), button.text, parent)
            setCustomStyleSheet(widget, light, dark)
            return widget
        widget = PrimaryPushButton(ICONS.get(button.id, FIF.PLAY), button.text, parent)
        light, dark = primary_button_qss(self._evernight)
        setCustomStyleSheet(widget, light, dark)
        return widget

    # ---------- 长夜与彩蛋 ----------
    def setEvernightMode(self, active, animate=False):
        if animate and self.isVisible() and active != self._evernight:
            previous = self._surfaceImage()
            self._evernight = active
            self.crossfade.play(previous, self._clipPath())
            self.mascot.bounce()
        else:
            self.crossfade.finish()
            self._evernight = active
        self.update()

    def playLogoHint(self):
        if not self.mascot.isHidden():
            self.mascot.setOverride(Mascot.DIZZY)
        self.logoHint.play()

    def dismissLogoHint(self):
        self.logoHint.dismiss()
        self.mascot.setOverride(None)

    # ---------- 布局与绘制 ----------
    def _hintRight(self):
        """提示文字的右端贴着小人左侧，像是她在说话；没有小人时居中。"""
        if not self.mascot.isHidden():
            return self.mascot.x() + self.mascot.imageRect().x() - 4
        return None

    def _mascotCenter(self):
        if not self.mascot.isHidden():
            return self.mascot.x() + self.mascot.width() / 2
        return self.width() - 150

    def _relayout(self):
        if not self.mascot.isHidden():
            image = self.mascot.imageRect()
            self.mascot.move(self.width() - 32 - image.width() - image.x(), self.height() - self.mascot.height())
            right = image.width() + 56
        else:
            right = 28
        if self.vBox.contentsMargins().right() != right:
            self.vBox.setContentsMargins(28, 20, right, 20)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _mode(self):
        if self._evernight:
            return "evernight"
        return "dark" if isDarkTheme() else "light"

    def _clipPath(self):
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        return path

    def _coverImage(self):
        size = self.size()
        if self._cover[0] != size:
            image = self._background.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                            Qt.TransformationMode.SmoothTransformation)
            x = max(0, (image.width() - size.width()) // 2)
            y = max(0, (image.height() - size.height()) // 2)
            self._cover = (QSize(size), image.copy(x, y, size.width(), size.height()))
        return self._cover[1]

    def _paintSurface(self, painter):
        rect = QRectF(self.rect())
        mode = self._mode()
        if not self._background.isNull():
            painter.drawImage(rect.topLeft(), self._coverImage())
            veil = QLinearGradient(rect.topLeft(), rect.topRight())
            base = QColor(255, 255, 255) if mode == "light" else QColor(24, 22, 30)
            veil.setColorAt(0.0, with_alpha(base, 0.88))
            veil.setColorAt(0.5, with_alpha(base, 0.62))
            veil.setColorAt(1.0, with_alpha(base, 0.05))
            painter.fillRect(rect, veil)
            return
        paint_background(painter, rect, mode)
        paint_star_track(painter, rect, mode, self._mascotCenter(), fade_from=min(rect.width() * 0.46, 520))

    def _surfaceImage(self):
        ratio = self.devicePixelRatioF() or 1.0
        image = QImage(max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio)),
                       QImage.Format.Format_ARGB32_Premultiplied)
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.setClipPath(self._clipPath())
        self._paintSurface(painter)
        painter.end()
        return image

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        path = self._clipPath()
        painter.save()
        painter.setClipPath(path)
        self._paintSurface(painter)
        painter.restore()
        painter.setPen(QPen(rgba(COLORS[self._mode()]["border"]), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
