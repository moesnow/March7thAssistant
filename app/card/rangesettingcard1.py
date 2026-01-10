from typing import Union

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QToolButton
from qfluentwidgets import (SettingCard, FluentIconBase, SwitchButton, IndicatorPosition,
                            Slider, FluentIcon, qconfig, isDarkTheme, Theme)

from module.config import cfg


class RangeSettingCard1(SettingCard):
    """ Setting card with a slider """

    valueChanged = Signal(int)

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

        self.minusButton = QToolButton()  # 新增减按钮
        self.plusButton = QToolButton()   # 新增加按钮

        # 设置按钮样式和图标
        self.updateButtonStyle()

        self.minusButton.setFixedSize(28, 28)   # 设置按钮大小
        self.plusButton.setFixedSize(28, 28)    # 设置按钮大小
        self.minusButton.setIconSize(QSize(12, 12))  # 图标大小
        self.plusButton.setIconSize(QSize(12, 12))   # 图标大小

        self.slider.setSingleStep(1)

        # 监听主题变化
        qconfig.themeChanged.connect(self.updateButtonStyle)
        self.slider.setRange(Range[0], Range[1])
        self.slider.setValue(int(cfg.get_value(self.configname)))
        self.valueLabel.setNum(int(cfg.get_value(self.configname)))

        self.hBoxLayout.addStretch(1)
        self.hBoxLayout.addWidget(self.valueLabel, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.hBoxLayout.addWidget(self.minusButton, 0, Qt.AlignmentFlag.AlignRight)  # 加入减号按钮
        self.hBoxLayout.addSpacing(4)  # 在减号按钮和滑块之间增加4像素间隔
        self.hBoxLayout.addWidget(self.slider, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(4)  # 在滑块和加号按钮之间增加4像素间隔
        self.hBoxLayout.addWidget(self.plusButton, 0, Qt.AlignmentFlag.AlignRight)   # 加入加号按钮
        self.hBoxLayout.addSpacing(16)

        self.valueLabel.setObjectName('valueLabel')
        # configname.valueChanged.connect(self.setValue)
        self.slider.valueChanged.connect(self.__onValueChanged)
        self.minusButton.clicked.connect(self.decreaseValue)        # 连接按钮信号
        self.plusButton.clicked.connect(self.increaseValue)        # 连接按钮信号

    def __onValueChanged(self, value: int):
        """ slider value changed slot """
        self.setValue(value)
        self.valueChanged.emit(value)

    def setValue(self, value):
        cfg.set_value(self.configname, value)
        self.valueLabel.setNum(value)
        self.valueLabel.adjustSize()
        self.slider.setValue(value)

    def decreaseValue(self):
        value = self.slider.value()
        if value > self.slider.minimum():
            self.slider.setValue(value - 1)

    def increaseValue(self):
        value = self.slider.value()
        if value < self.slider.maximum():
            self.slider.setValue(value + 1)

    def updateButtonStyle(self):
        """根据当前主题更新按钮样式"""
        style = '''
            QToolButton {
                background-color: transparent;
                border: 1px solid %s;
                border-radius: 5px;
            }
            QToolButton:hover {
                background-color: %s;
            }
            QToolButton:pressed {
                background-color: %s;
            }
        '''

        if isDarkTheme():
            # 深色主题
            border_color = '#424242'
            hover_color = '#424242'
            pressed_color = '#333333'
        else:
            # 浅色主题
            border_color = '#E5E5E5'
            hover_color = '#E5E5E5'
            pressed_color = '#DDDDDD'

        self.minusButton.setStyleSheet(style % (border_color, hover_color, pressed_color))
        self.plusButton.setStyleSheet(style % (border_color, hover_color, pressed_color))

        # 更新图标
        self.minusButton.setIcon(FluentIcon.REMOVE.icon())
        self.plusButton.setIcon(FluentIcon.ADD.icon())
