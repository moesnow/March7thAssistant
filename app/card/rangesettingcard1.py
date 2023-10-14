from typing import Union

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter
from PyQt5.QtWidgets import (QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QPushButton)
from qfluentwidgets import (SettingCard, FluentIconBase, SwitchButton, IndicatorPosition, Slider)

from managers.config_manager import config


class RangeSettingCard1(SettingCard):
    """ Setting card with a slider """

    valueChanged = pyqtSignal(int)

    def __init__(self, configname: str, Range: dict, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        """
        Parameters
        ----------
        configItem: RangeConfigItem
            configuration item operated by the card

        icon: str | QIcon | FluentIconBase
            the icon to be drawn

        title: str
            the title of card

        content: str
            the content of card

        parent: QWidget
            parent widget
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.slider = Slider(Qt.Horizontal, self)
        self.valueLabel = QLabel(self)
        self.slider.setMinimumWidth(268)

        self.slider.setSingleStep(1)
        self.slider.setRange(Range[0], Range[1])
        self.slider.setValue(int(config.get_value(self.configname)))
        self.valueLabel.setNum(int(config.get_value(self.configname)))

        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.addWidget(self.valueLabel, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(6)
        self.hBoxLayout.addWidget(self.slider, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.valueLabel.setObjectName('valueLabel')
        # configname.valueChanged.connect(self.setValue)
        self.slider.valueChanged.connect(self.__onValueChanged)

    def __onValueChanged(self, value: int):
        """ slider value changed slot """
        self.setValue(value)
        self.valueChanged.emit(value)

    def setValue(self, value):
        config.set_value(self.configname, value)
        self.valueLabel.setNum(value)
        self.valueLabel.adjustSize()
        self.slider.setValue(value)
