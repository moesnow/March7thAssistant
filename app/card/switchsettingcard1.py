from qfluentwidgets import (SettingCard, FluentIconBase, SwitchButton, IndicatorPosition)
from typing import Union
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from managers.config_manager import config


class SwitchSettingCard1(SettingCard):
    """ Setting card with switch button """

    checkedChanged = pyqtSignal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.switchButton = SwitchButton(
            self.tr('关'), self, IndicatorPosition.RIGHT)

        self.setValue(config.get_value(self.configname))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        config.set_value(self.configname, isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(self.tr('开') if isChecked else self.tr('关'))
