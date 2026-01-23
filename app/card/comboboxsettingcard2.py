from qfluentwidgets import (ComboBox, SettingCard, FluentIconBase, InfoBar, InfoBarPosition)
from typing import Union
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton

from module.config import cfg
from module.localization import tr
import os
import sys
from ..tools.check_update import checkUpdate
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


class ComboBoxSettingCardUpdateSource(SettingCard):
    """ Setting card with a combo box """

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase], title, update_callback, content=None, texts=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.update_callback = update_callback
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
        checkUpdate(self.update_callback)


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
        if sys.platform == 'win32':
            os.startfile(os.path.abspath("./logs"))
        elif sys.platform == 'darwin':
            os.system(f'open "{os.path.abspath("./logs")}"')
        else:
            os.system(f'xdg-open "{os.path.abspath("./logs")}"')


class ComboBoxSettingCardLanguage(ComboBoxSettingCard2):
    """Combo box setting card specialized for UI language changes.

    Shows an InfoBar notifying that a restart is required when the language changes.
    """

    def _onCurrentIndexChanged(self, index: int):
        old_val = cfg.get_value(self.configname)
        new_val = self.comboBox.itemData(index)
        if old_val == new_val:
            return
        # set value (reuse base behavior)
        cfg.set_value(self.configname, new_val)
        # Emit a signal to notify top-level window to show restart InfoBar
        try:
            signalBus.uiLanguageChanged.emit(new_val)
        except Exception:
            pass
