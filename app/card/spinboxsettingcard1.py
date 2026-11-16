from typing import Union

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import SettingCard, FluentIconBase

from app.components.ascii_spin_box import AsciiSpinBox
from module.config import cfg


class SpinBoxSettingCard1(SettingCard):
    """设置卡片：右侧整数输入框，改动即写回配置。"""

    valueChanged = Signal(int)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase], title, content=None,
                 *, minimum: int = 0, maximum: int = 1440, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.spinBox = AsciiSpinBox(self)
        self.spinBox.setRange(minimum, maximum)
        self.spinBox.setMinimumWidth(120)
        self.hBoxLayout.addWidget(self.spinBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.spinBox.setValue(self.__normalize(cfg.get_value(configname)))
        self.spinBox.valueChanged.connect(self.__onValueChanged)

    def __normalize(self, value) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = self.spinBox.minimum()
        return max(self.spinBox.minimum(), min(self.spinBox.maximum(), value))

    def __onValueChanged(self, value: int) -> None:
        cfg.set_value(self.configname, int(value))
        self.valueChanged.emit(int(value))
