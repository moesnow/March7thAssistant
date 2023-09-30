from qfluentwidgets import (ComboBox, SettingCard, FluentIconBase)
from typing import Union
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon

from managers.config_manager import config


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
            if value == config.get_value(configname):
                self.comboBox.setCurrentText(key)

        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

    def _onCurrentIndexChanged(self, index: int):
        config.set_value(self.configname, self.comboBox.itemData(index))
