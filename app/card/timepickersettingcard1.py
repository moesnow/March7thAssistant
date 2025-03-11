from qfluentwidgets import (TimePicker, SettingCard, FluentIconBase)
from typing import Union
from PyQt5.QtCore import Qt, QTime
from PyQt5.QtGui import QIcon

from module.config import cfg


class TimePickerSettingCard1(SettingCard):
    """ Setting card with a TimePicker """

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase], title, content=None, texts=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.timePicker = TimePicker(self)
        self.hBoxLayout.addWidget(self.timePicker, 0, Qt.AlignRight)

        time_str = cfg.get_value(configname)
        time_parts = list(map(int, time_str.split(":")))  # 分割小时和分钟
        qtime = QTime(*time_parts)  # 创建 QTime 对象
        self.timePicker.setTime(qtime)

        self.timePicker.timeChanged.connect(self._onTimeChanged)

    def _onTimeChanged(self, time: QTime):
        cfg.set_value(self.configname, time.toString("HH:mm"))  # 保存24小时制的时间到配置文件
