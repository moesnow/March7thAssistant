from qfluentwidgets import (ComboBox, SettingCard, FluentIconBase)
from typing import Union
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QPushButton

from module.config import cfg
import os
from ..tools.check_update import checkUpdate


class ComboBoxSettingCard2(SettingCard):
    """ Setting card with a combo box """

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase], title, content=None, texts=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignRight)
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
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignRight)
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

        self.button = QPushButton("打开日志文件夹", self)
        self.button.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button.clicked.connect(self._onClicked)

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

        for key, value in texts.items():
            self.comboBox.addItem(key, userData=value)
            if value == cfg.get_value(configname):
                self.comboBox.setCurrentText(key)

        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value(self.configname, self.comboBox.itemData(index))

    def _onClicked(self):
        os.startfile(os.path.abspath("./logs"))
