from qfluentwidgets import SettingCard, FluentIconBase, SwitchButton, IndicatorPosition, ComboBox, PushButton
from typing import Union
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from module.config import cfg
from module.localization import tr
import datetime


def format_config_timestamp(configname: str):
    try:
        timestamp = float(cfg.get_value(configname) or 0)
    except (TypeError, ValueError):
        timestamp = 0

    if timestamp <= 0:
        return tr("未执行"), False

    try:
        return datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M'), True
    except (OSError, OverflowError, ValueError):
        return tr("未执行"), False


def build_timestamp_content(content: str, time_title: str, timestamp_configname: str):
    timestamp_text, has_timestamp = format_config_timestamp(timestamp_configname)
    lines = [content] if content else []
    lines.append(f"{time_title}：{timestamp_text}")
    return "\n".join(lines), has_timestamp


class SwitchSettingCard1(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None, *, confirm=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self._confirm = confirm
        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)

        try:
            self.setValue(cfg.get_value(self.configname))
        except Exception:
            self.setValue(False)

        self._acceptedValue = self.switchButton.isChecked()
        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        if (isChecked != self._acceptedValue and self._confirm is not None
                and not self._confirm(isChecked)):
            # 确认前不保存；取消/关闭弹窗后恢复开关且不递归弹窗。
            self.switchButton.blockSignals(True)
            try:
                self.setValue(self._acceptedValue)
            finally:
                self.switchButton.blockSignals(False)
            return
        self._acceptedValue = isChecked
        self.setValue(isChecked)
        cfg.set_value(self.configname, isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(bool(isChecked))
        self.switchButton.setText(tr('开') if isChecked else tr('关'))


class SwitchSettingCardWithAction(SwitchSettingCard1):
    actionClicked = Signal()

    def __init__(self, button_text: str, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, configname, parent)

        self.actionButton = PushButton(button_text, self)
        insert_index = max(self.hBoxLayout.count() - 2, 0)
        self.hBoxLayout.insertWidget(insert_index, self.actionButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.insertSpacing(insert_index + 1, 10)

        self.actionButton.clicked.connect(self.actionClicked.emit)


class TimestampSwitchSettingCard(SwitchSettingCard1):
    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None,
                 configname: str = None, timestamp_configname: str = None,
                 time_title: str = None, parent=None):
        self._baseContent = content or ""
        self.timestampConfigname = timestamp_configname
        self.timeTitle = time_title or ""
        timestamp_content, _ = build_timestamp_content(self._baseContent, self.timeTitle, self.timestampConfigname)
        super().__init__(icon, title, timestamp_content, configname, parent)

        self.resetButton = PushButton(tr("重置时间"), self)
        insert_index = max(self.hBoxLayout.count() - 2, 0)
        self.hBoxLayout.insertWidget(insert_index, self.resetButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.insertSpacing(insert_index + 1, 10)

        self.resetButton.clicked.connect(self._resetTimestamp)
        self.refreshTimestampContent()

    def refreshTimestampContent(self):
        timestamp_content, has_timestamp = build_timestamp_content(self._baseContent, self.timeTitle, self.timestampConfigname)
        self.contentLabel.setText(timestamp_content)
        self.contentLabel.adjustSize()
        self.resetButton.setEnabled(has_timestamp)

    def _resetTimestamp(self):
        cfg.set_value(self.timestampConfigname, 0)
        self.refreshTimestampContent()


class SwitchSettingCardTeam(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, configname2: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.configname2 = configname2

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)

        texts = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
        for text, option in zip(texts, texts):
            self.comboBox.addItem(text, userData=option)

        self.comboBox.setCurrentText(cfg.get_value(configname2))
        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)

        self.setValue(cfg.get_value(self.configname))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        cfg.set_value(self.configname, isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(bool(isChecked))
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value(self.configname2, self.comboBox.itemData(index))


class SwitchSettingCardGardenofplenty(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)

        texts = ['拟造花萼（金）', '拟造花萼（赤）']
        for text, option in zip(texts, texts):
            self.comboBox.addItem(tr(text), userData=option)

        index = self.comboBox.findData(cfg.get_value("activity_gardenofplenty_instance_type"))
        # 未配置或旧值无法匹配时，保留默认首项，避免出现空白选项。
        self.comboBox.setCurrentIndex(max(0, index))
        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)

        self.setValue(cfg.get_value(self.configname))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        cfg.set_value(self.configname, isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(bool(isChecked))
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value("activity_gardenofplenty_instance_type", self.comboBox.itemData(index))
