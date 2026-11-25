"""自动对话：卡片上的开关和「选项」浮层。"""
from PySide6.QtCore import QEvent, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout
from qfluentwidgets import (CaptionLabel, CheckBox, FluentIcon as FIF, Flyout, FlyoutAnimationManager,
                            FlyoutAnimationType, FlyoutViewBase)

from app.common.signal_bus import signalBus
from app.pages.common import bare_switch, secondary
from module.config import cfg
from module.localization import tr
from .cards import ToolCard

HINT_WIDTH = 400


class AutoPlotOptions(FlyoutViewBase):
    """自动对话的选项，勾选后立即生效。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rememberStateCheckBox = CheckBox(self)
        self.rememberStateHintLabel = secondary(CaptionLabel(self))
        self.rememberStateHintLabel.setWordWrap(True)
        self.rememberStateHintLabel.setFixedWidth(HINT_WIDTH)
        self.autoSkipCheckBox = CheckBox(self)
        self.autoClickCheckBox = CheckBox(self)
        self.autoBattleDetectCheckBox = CheckBox(self)
        self.autoPhoneDetectCheckBox = CheckBox(self)
        self.heroChronicleCheckBox = CheckBox(self)
        self.hotkeyToggleCheckBox = CheckBox(self)
        self.hotkeyHintLabel = secondary(CaptionLabel(self))
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(20, 18, 20, 18)
        self.vBoxLayout.setSpacing(12)
        for widget, hint in ((self.rememberStateCheckBox, self.rememberStateHintLabel), (self.autoSkipCheckBox, None),
                             (self.autoClickCheckBox, None), (self.autoBattleDetectCheckBox, None),
                             (self.autoPhoneDetectCheckBox, None), (self.heroChronicleCheckBox, None),
                             (self.hotkeyToggleCheckBox, self.hotkeyHintLabel)):
            column = QVBoxLayout()
            column.setSpacing(4)
            column.addWidget(widget)
            if hint is not None:
                row = QHBoxLayout()
                row.setContentsMargins(30, 0, 0, 0)
                row.addWidget(hint)
                column.addLayout(row)
            self.vBoxLayout.addLayout(column)


class AutoPlotCard(ToolCard):
    """开关在右上角，选项收进浮层。"""
    switchChanged = Signal(bool)
    optionsChanged = Signal(dict)

    def __init__(self, icon, parent=None):
        self._flyout = None
        super().__init__(icon, parent)
        self.switchButton = bare_switch(self)
        self.head.addWidget(self.switchButton)
        self.button.setIcon(FIF.SETTING)
        self.hotkeyLabel = secondary(CaptionLabel(self))
        self.actions.insertWidget(1, self.hotkeyLabel)
        self.options = AutoPlotOptions(self)
        self.options.hide()
        for name in ("rememberStateCheckBox", "rememberStateHintLabel", "autoSkipCheckBox", "autoClickCheckBox",
                     "autoBattleDetectCheckBox", "autoPhoneDetectCheckBox", "heroChronicleCheckBox",
                     "hotkeyToggleCheckBox", "hotkeyHintLabel"):
            setattr(self, name, getattr(self.options, name))
        self.rememberStateCheckBox.setChecked(bool(cfg.get_value("autoplot_remember_enable", False)))
        self.autoSkipCheckBox.setChecked(bool(cfg.get_value("autoplot_skip_enable", True)))
        self.autoClickCheckBox.setChecked(bool(cfg.get_value("autoplot_click_enable", True)))
        self.autoBattleDetectCheckBox.setChecked(bool(cfg.get_value("autoplot_battle_detect_enable", True)))
        self.autoPhoneDetectCheckBox.setChecked(bool(cfg.get_value("autoplot_phone_detect_enable", True)))
        self.heroChronicleCheckBox.setChecked(bool(cfg.get_value("autoplot_hero_chronicle_enable", False)))
        self.hotkeyToggleCheckBox.setChecked(bool(cfg.get_value("hotkey_toggle_autoplot_enable", False)))
        # 恢复开关状态；此时尚未连接信号，实际启动由工具箱界面负责。
        self.setValue(self.rememberStateCheckBox.isChecked() and bool(cfg.get_value("autoplot_enable", False)))
        self.retranslateUi()

        self.switchButton.checkedChanged.connect(self.switchChanged)
        self.rememberStateCheckBox.stateChanged.connect(self._rememberChanged)
        for box in (self.autoSkipCheckBox, self.autoClickCheckBox, self.autoBattleDetectCheckBox,
                    self.autoPhoneDetectCheckBox, self.heroChronicleCheckBox):
            box.stateChanged.connect(self._optionChanged)
        self.hotkeyToggleCheckBox.stateChanged.connect(self._hotkeyToggled)
        self.clicked.connect(self.showOptions)

    def restyle(self, *_):
        super().restyle()
        if hasattr(self, "hotkeyLabel"):
            self.hotkeyLabel.setTextColor(self.contentLabel.lightColor, self.contentLabel.darkColor)
        if self._flyout is not None:
            self._flyout.setShadowEffect()

    def showOptions(self):
        if self._flyout is None:
            self._flyout = Flyout(self.options, self, isDeleteOnClose=False)
            self._flyout.aniManager = FlyoutAnimationManager.make(FlyoutAnimationType.DROP_DOWN, self._flyout)
            self.window().installEventFilter(self)
            self.options.show()
        self._flyout.adjustSize()
        self._flyout.show()
        manager = self._flyout.aniManager
        manager.aniGroup.stop()
        manager.exec(manager.position(self.button))

    def eventFilter(self, watched, event):
        if (self._flyout is not None and watched is self.window()
                and event.type() == QEvent.Type.WindowStateChange and watched.isMinimized()):
            self._flyout.close()
        return super().eventFilter(watched, event)

    def hideEvent(self, event):
        if self._flyout is not None:
            self._flyout.close()
        super().hideEvent(event)

    def _rememberChanged(self):
        enabled = self.rememberStateCheckBox.isChecked()
        cfg.set_values({
            "autoplot_remember_enable": enabled,
            "autoplot_enable": enabled and self.getSwitchState(),
        })

    def _optionChanged(self):
        # 批量写入：set_value 每次都会 load+save 落盘，一次勾选只需落盘一次
        cfg.set_values({
            "autoplot_skip_enable": self.autoSkipCheckBox.isChecked(),
            "autoplot_click_enable": self.autoClickCheckBox.isChecked(),
            "autoplot_battle_detect_enable": self.autoBattleDetectCheckBox.isChecked(),
            "autoplot_phone_detect_enable": self.autoPhoneDetectCheckBox.isChecked(),
            "autoplot_hero_chronicle_enable": self.heroChronicleCheckBox.isChecked(),
        })
        self.optionsChanged.emit(self.getOptions())

    def _hotkeyToggled(self):
        cfg.set_value("hotkey_toggle_autoplot_enable", self.hotkeyToggleCheckBox.isChecked())
        self.updateHotkeyHint()
        signalBus.hotkeyChangedSignal.emit()

    def setValue(self, checked):
        self.switchButton.setChecked(checked)

    def getSwitchState(self):
        return self.switchButton.isChecked()

    def getOptions(self):
        return {
            'auto_skip': self.autoSkipCheckBox.isChecked(),
            'auto_click': self.autoClickCheckBox.isChecked(),
            'auto_battle_detect_enable': self.autoBattleDetectCheckBox.isChecked(),
            'auto_phone_detect_enable': self.autoPhoneDetectCheckBox.isChecked(),
            'hero_chronicle_enable': self.heroChronicleCheckBox.isChecked(),
        }

    def retranslateUi(self):
        self.switchButton.setAccessibleName(tr('自动对话'))
        self.rememberStateCheckBox.setText(tr('记住自动对话开关状态'))
        self.rememberStateHintLabel.setText(tr('开启后，下次启动小助手时将恢复自动对话的开关状态。游戏未在前台时仅进行低频窗口检测。'))
        self.autoSkipCheckBox.setText(tr('自动跳过 (当出现跳过按钮时自动点击)'))
        self.autoClickCheckBox.setText(tr('自动选择 (自动选择任意对话选项)'))
        self.autoBattleDetectCheckBox.setText(tr('自动战斗检测 (检测到未自动战斗时按V开启)'))
        self.autoPhoneDetectCheckBox.setText(tr('自动短信 (自动点击关闭手机短信页面)'))
        self.heroChronicleCheckBox.setText(tr('自动阅读翁法罗斯英雄纪（请先打开该书目录，非 .exe 版）'))
        self.hotkeyToggleCheckBox.setText(tr('启用快捷键切换自动对话'))
        self.updateHotkeyHint()

    def updateHotkeyHint(self):
        """快捷键改动后更新卡片和浮层里的提示。"""
        hotkey = cfg.get_value("hotkey_toggle_autoplot", "f9").upper()
        enabled = self.hotkeyToggleCheckBox.isChecked()
        self.hotkeyHintLabel.setText(tr("快捷键：{hotkey}（可在设置中修改）").format(hotkey=hotkey))
        self.hotkeyHintLabel.setVisible(enabled)
        self.hotkeyLabel.setText(tr("快捷键 {hotkey}").format(hotkey=hotkey))
        self.hotkeyLabel.setVisible(enabled)
        if self._flyout is not None:
            self.options.layout().activate()
            self.options.adjustSize()
            self._flyout.adjustSize()
            if self._flyout.isVisible():
                popup = self._flyout
                screen = self.button.screen().availableGeometry()
                pos = popup.pos()
                pos.setX(max(screen.left(), min(pos.x(), screen.right() + 1 - popup.width())))
                pos.setY(max(screen.top(), min(pos.y(), screen.bottom() + 1 - popup.height())))
                if pos != popup.pos():
                    popup.aniManager.aniGroup.stop()
                    popup.setWindowOpacity(1)
                    popup.move(pos)
