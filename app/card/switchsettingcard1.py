from qfluentwidgets import SettingCard, FluentIconBase, SwitchButton, IndicatorPosition, ComboBox, PushButton
from typing import Union
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton
from .messagebox_custom import MessageBoxNotify
from module.config import cfg
from module.localization import tr
from utils.schedule import create_task, is_task_exists, delete_task
import os


class StartMarch7thAssistantSwitchSettingCard(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.switchButton = SwitchButton(
            tr('关'), self, IndicatorPosition.RIGHT)

        self.task_name = "StartMarch7thAssistant"
        self.program_path = os.path.abspath("./March7th Launcher.exe")
        self.program_args = "main"

        self.setValue(is_task_exists(self.task_name))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        if isChecked:
            create_task(task_name=self.task_name, program_path=self.program_path, program_args=self.program_args)
        else:
            delete_task(task_name=self.task_name)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))


class SwitchSettingCard1(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.switchButton = SwitchButton(
            tr('关'), self, IndicatorPosition.RIGHT)

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
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))


class SwitchSettingCardNotify(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, name, configname: str = None, parent=None):
        super().__init__(icon, title, None, parent)
        self.name = name
        self.configname = configname

        self.config_list = {}
        for key, _ in cfg.config.items():
            if key.startswith(f"notify_{name}") and (not key.endswith("_enable")):
                config_name = key[len(f"notify_{name}_"):]
                self.config_list[config_name] = key

        if len(self.config_list) > 0:
            self.button = PushButton(tr("配置"), self)
            self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
            self.hBoxLayout.addSpacing(10)
            self.button.clicked.connect(self._onClicked)

        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)

        self.setValue(cfg.get_value(self.configname))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def _onClicked(self):
        def process_lineedit_text(input_text):
            try:
                # 尝试通过 eval 转换
                result = eval(input_text)
            except (SyntaxError, NameError, ValueError):
                # 如果转换失败，返回原字符串
                result = input_text
            return result
        message_box = MessageBoxNotify(self.name, self.config_list, self.window())
        if message_box.exec():
            for config, lineedit in message_box.lineEdit_dict.items():
                cfg.set_value(config, process_lineedit_text(lineedit.text()))
            # 配置修改后重新初始化通知器以应用变更
            try:
                from module.notification import init_notifiers
                init_notifiers()
            except Exception:
                pass

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        cfg.set_value(self.configname, isChecked)
        # 启用/禁用切换后重新初始化通知器
        try:
            from module.notification import init_notifiers
            init_notifiers()
        except Exception:
            pass

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))


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

        texts = ['3', '4', '5', '6', '7']
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
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value(self.configname2, self.comboBox.itemData(index))


class SwitchSettingCardImmersifier(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)

        texts = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
        for text, option in zip(texts, texts):
            self.comboBox.addItem(text, userData=option)

        self.comboBox.setCurrentText(cfg.get_value("merge_immersifier_limit"))
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
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value("merge_immersifier_limit", self.comboBox.itemData(index))


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
            self.comboBox.addItem(text, userData=option)

        self.comboBox.setCurrentText(cfg.get_value("activity_gardenofplenty_instance_type"))
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
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value("activity_gardenofplenty_instance_type", self.comboBox.itemData(index))


class SwitchSettingCardEchoofwar(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)

        texts = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        options = [1, 2, 3, 4, 5, 6, 7]
        for text, option in zip(texts, options):
            self.comboBox.addItem(text, userData=option)

        self.comboBox.setCurrentText(texts[cfg.get_value("echo_of_war_start_day_of_week") - 1])
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
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value("echo_of_war_start_day_of_week", self.comboBox.itemData(index))


class SwitchSettingCardHotkey(SettingCard):
    """ Setting card with configure button for hotkey settings """

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)

        self.button = QPushButton(tr("配置"), self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.clicked.connect(self._onClicked)

    def _onClicked(self):
        from app.sub_interfaces.hotkey_interface import HotkeyInterface
        from app.common.signal_bus import signalBus
        hotkey_interface = HotkeyInterface(self.window())
        if hotkey_interface.exec():
            # 用户点击确认，发送热键更新信号
            signalBus.hotkeyChangedSignal.emit()


class SwitchSettingCardCloudGameStatus(SettingCard):
    """ Setting card with switch button """

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, configname2: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.configname2 = configname2

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)

        texts = {'简洁': 'brief', '详细': 'verbose'}
        for text, option in texts.items():
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
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value(self.configname2, self.comboBox.itemData(index))
