from qfluentwidgets import (ComboBox, SettingCard, FluentIcon, FluentIconBase)
from typing import Union
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton

from module.config import cfg
from module.localization import tr
from utils.desktop import open_log_folder
from ..tools.check_theme_change import applyTheme, current_theme_preference
from ..components.evey_decoration import EveyControlDecoration
from app.common.signal_bus import signalBus


class ComboBoxSettingCard2(SettingCard):
    """ Setting card with a combo box """

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase], title, content=None, texts=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        for key, value in texts.items():
            self.comboBox.addItem(key, userData=value)
            if value == cfg.get_value(configname):
                self.comboBox.setCurrentText(key)

        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value(self.configname, self.comboBox.itemData(index))


class ComboBoxSettingCardTheme(ComboBoxSettingCard2):
    """Include Evernight in the theme list once unlocked."""

    def __init__(self, window):
        self._window = window if hasattr(window, '_evernight') else None
        super().__init__(
            'ui_theme', FluentIcon.BRUSH, tr('界面主题'), tr('选择应用的显示主题'),
            texts={tr('跟随系统'): 'auto', tr('浅色'): 'light', tr('深色'): 'dark'},
        )
        self.eveyDecoration = EveyControlDecoration(
            self.comboBox, 'evey-decoration-wide.png', (-52, -15, 14, 15))
        if self._window is None:
            return
        self.setEvernightMode(window._evernight_active)
        if window._evernight.unlocked:
            self.showEvernightOption()

    def showEvernightOption(self):
        with QSignalBlocker(self.comboBox):
            index = self.comboBox.findData('evernight')
            if index < 0:
                self.comboBox.addItem(tr('长夜'), userData='evernight')
                index = self.comboBox.count() - 1
            if self._window._evernight.selected:
                self.comboBox.setCurrentIndex(index)

    def setEvernightMode(self, active):
        self.eveyDecoration.setActive(active)

    def _onCurrentIndexChanged(self, index):
        if self._window is None:
            super()._onCurrentIndexChanged(index)
            applyTheme(None)
        elif not self._window.set_ui_theme(self.comboBox.itemData(index)):
            previous = self.comboBox.findData(current_theme_preference(self._window))
            with QSignalBlocker(self.comboBox):
                self.comboBox.setCurrentIndex(max(0, previous))


class ComboBoxSettingCardLog(SettingCard):
    """ Setting card with a combo box """

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase], title, content=None, texts=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname

        self.button = QPushButton(tr("打开日志文件夹"), self)
        self.button.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button.clicked.connect(self._onClicked)

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        for key, value in texts.items():
            self.comboBox.addItem(key, userData=value)
            if value == cfg.get_value(configname):
                self.comboBox.setCurrentText(key)

        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value(self.configname, self.comboBox.itemData(index))

    def _onClicked(self):
        open_log_folder()


class ComboBoxSettingCardLanguage(ComboBoxSettingCard2):
    """Combo box setting card specialized for UI language changes.

    Requests an in-place language refresh after the popup has closed.
    """

    def _onCurrentIndexChanged(self, index: int):
        new_val = self.comboBox.itemData(index)
        # 由主窗口在刷新事务中保存配置，失败时才能恢复原值（包括 auto）。
        # 不与已保存值比较：等待期间选回原语言，也必须覆盖之前的请求。
        signalBus.uiLanguageChanged.emit(new_val)
