"""清体力的「刷什么」：体力计划、培养目标、默认副本按先后排成三步，每步写明按现在的设置会不会用到。"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, StrongBodyLabel, getFont, isDarkTheme

from app.content.base import setting_for
from app.overview.style import accent, text_color, tone, track_color
from app.overview.widgets import ElidedLabel, Pill
from module.localization import tr
from module.task_catalog import power_order
from .common import SectionView, is_evernight, secondary

STEP_OF = {"power_plan": "plan", "build_target_enable": "target", "instance_type": "default", "instance_names": "default"}
TONES = {"first": "accent", "then": "info", "warning": "warning"}


class OrderStep(QWidget):
    """左侧是编号和通往下一步的连线，右侧是标题、状态和这一步的设置卡。"""

    GUTTER, BADGE, GAP = 36, 24, 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self._number, self._last, self._kind = 1, True, "skip"
        self._evernight = False
        self._font = getFont(13, QFont.Weight.DemiBold)
        self.titleLabel = StrongBodyLabel(self)
        self.detailLabel = secondary(ElidedLabel(self, size=12))
        self.pill = Pill(self, height=22)
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(self.titleLabel)
        header.addWidget(self.detailLabel, 1)
        header.addWidget(self.pill)
        self.cards = []
        self.cardLayout = QVBoxLayout()
        self.cardLayout.setSpacing(3)
        self.vBox = QVBoxLayout(self)
        self.vBox.setContentsMargins(self.GUTTER, 0, 0, 0)
        self.vBox.setSpacing(7)
        self.vBox.addLayout(header)
        self.vBox.addLayout(self.cardLayout)

    def addCard(self, card):
        self.cards.append(card)
        self.cardLayout.addWidget(card)

    def setPlace(self, number, last):
        self._number, self._last = number, last
        self.vBox.setContentsMargins(self.GUTTER, 0, 0, 0 if last else self.GAP)
        self.update()

    def setState(self, state):
        self._kind, self._evernight = state.kind, is_evernight()
        self.titleLabel.setText(state.title)
        self.detailLabel.setFullText(state.detail)
        self.pill.setPill(state.text, TONES.get(state.kind, "neutral"), evernight=self._evernight)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        center = QPointF(self.BADGE / 2, self.titleLabel.geometry().center().y() + 0.5)
        badge = QRectF(center.x() - self.BADGE / 2, center.y() - self.BADGE / 2, self.BADGE, self.BADGE)
        if not self._last:
            painter.setPen(QPen(track_color(), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(center.x(), badge.bottom() + 6), QPointF(center.x(), self.height() - 3))
        if self._kind == "first":
            background, foreground = accent(self._evernight), QColor("#1b1b1b" if isDarkTheme() else "#ffffff")
        elif self._kind in ("then", "warning"):
            background, foreground = tone("accent", self._evernight)
        else:
            background, foreground = tone("neutral")[0], text_color(secondary=True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background)
        painter.drawEllipse(badge)
        painter.setPen(foreground)
        painter.setFont(self._font)
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, str(self._number))


class PowerOrderView(SectionView):
    def __init__(self, section, config, parent=None):
        super().__init__(section, parent)
        self.config = config
        hint = secondary(CaptionLabel(tr("按从上到下的顺序用开拓力：前一步用不上或刷完了，才轮到下一步"), self))
        hint.setWordWrap(True)
        self.vBoxLayout.insertWidget(1, hint)
        self.bodyLayout.setSpacing(0)
        self.bodyLayout.setContentsMargins(0, 4, 0, 0)
        self.steps = {}
        for state in power_order(config):
            step = self.steps[state.id] = OrderStep(self.body)
            self.bodyLayout.addWidget(step)
        for card in section.cards:
            self.steps[STEP_OF.get(setting_for(card).id, "default")].addCard(card)
        self.refreshOrder()

    def refresh(self):
        super().refresh()
        shown = []
        for step in self.steps.values():
            visible = any(not card.isHidden() for card in step.cards)
            step.setVisible(visible)
            if visible:
                shown.append(step)
        for number, step in enumerate(shown, 1):
            step.setPlace(number, step is shown[-1])

    def refreshOrder(self):
        for state in power_order(self.config):
            self.steps[state.id].setState(state)
