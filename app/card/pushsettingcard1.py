from PySide6.QtCore import Qt, Signal, QUrl, QThread
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import SettingCard, FluentIconBase, InfoBar, InfoBarPosition, SwitchButton, IndicatorPosition
from .messagebox_custom import MessageBoxEdit, MessageBoxDate, MessageBoxInstance, MessageBoxInstanceChallengeCount, MessageBoxNotifyTemplate, MessageBoxTeam, MessageBoxFriends, MessageBoxPowerPlan, MessageBoxInstanceTeam
from module.config import cfg
from module.config.game_hotkeys import manual_game_hotkey
from typing import Union
import datetime
from module.update.version_check import validate_mirrorchyan_cdk
from module.localization import tr, tn, get_character_names, instance_display_to_raw
from utils.game_key_templates import key_prompt_path


def get_key_from_value(val, map):
    """Helper function to get key from value in a dictionary"""
    for key, value in map.items():
        if value == val:
            return key
    return None


class CustomPushSettingCard(SettingCard):
    clicked = Signal()

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, configvalue, parent=None):
        super().__init__(icon, title, configvalue, parent)
        self.title = title
        self.configname = configname
        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class DualPushSettingCard(SettingCard):
    leftClicked = Signal()
    rightClicked = Signal()

    def __init__(self, left_text, right_text, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)

        self.leftButton = QPushButton(left_text, self)
        self.rightButton = QPushButton(right_text, self)

        for button in (self.leftButton, self.rightButton):
            button.setObjectName('primaryButton')

        self.hBoxLayout.addWidget(self.leftButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.hBoxLayout.addWidget(self.rightButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.leftButton.clicked.connect(self.leftClicked.emit)
        self.rightButton.clicked.connect(self.rightClicked.emit)


class PushSettingCardStr(CustomPushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname,
                 parent=None, empty_content=None, *, password=False):
        self.empty_content = empty_content
        self.password = password
        self.configvalue = str(cfg.get_value(configname) or "")
        super().__init__(text, icon, title, configname, self._display_value(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def _display_value(self, value):
        if self.password:
            return ""
        if value == "" and self.empty_content is not None:
            return self.empty_content
        return value

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window(), password=self.password)
        if message_box.exec():
            value = message_box.getText()
            if self.password:
                value = value.strip()
            cfg.set_value(self.configname, value)
            self.configvalue = value
            self.contentLabel.setText(self._display_value(self.configvalue))


class _CdkValidationThread(QThread):
    validationFinished = Signal(bool, str)

    def __init__(self, cdk, parent=None):
        super().__init__(parent)
        self.cdk = cdk

    def run(self):
        try:
            cdk_expired_time = validate_mirrorchyan_cdk(self.cdk)
            self.validationFinished.emit(True, str(cdk_expired_time))
        except Exception as e:
            self.validationFinished.emit(False, str(e))


class PushSettingCardMirrorchyan(SettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, source_card, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        self.source_card = source_card
        super().__init__(icon, title, "", parent)

        self.title = title
        self.configname = configname
        self._validation_thread = None
        self.destroyed.connect(self._cleanup_validation_thread)

        self.button4 = QPushButton(tr("查询天数"), self)
        self.button4.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button4, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button4.clicked.connect(self.__onclicked4)

        self.button3 = QPushButton(tr("交流反馈"), self)
        self.button3.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button3, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button3.clicked.connect(self.__onclicked3)

        self.button2 = QPushButton(tr("获取 CDK"), self)
        self.button2.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button2, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button2.clicked.connect(self.__onclicked2)

        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window())
        if message_box.exec():
            cdk = message_box.getText()
            cfg.set_value(self.configname, cdk)
            self.contentLabel.setText(cdk)
            self.configvalue = cdk
            if cdk:
                self._start_cdk_validation(cdk)

    def _cleanup_validation_thread(self):
        thread = self._validation_thread
        if thread is not None:
            if thread.isRunning():
                thread.wait(11000)
            thread.deleteLater()
            self._validation_thread = None

    def _start_cdk_validation(self, cdk):
        existing = self._validation_thread
        if existing is not None:
            if existing.isRunning():
                return
            existing.deleteLater()
            self._validation_thread = None

        thread = _CdkValidationThread(cdk, self)
        thread.validationFinished.connect(self._on_cdk_validated)
        self._validation_thread = thread
        thread.start()
        InfoBar.info(
            title=tr("正在查询 CDK 剩余天数…"),
            content="",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1500,
            parent=self.window(),
        )

    def _on_cdk_validated(self, success, result):
        if success:
            cdk_expired_time = float(result)
            expired_dt = datetime.datetime.fromtimestamp(cdk_expired_time, tz=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            remaining = expired_dt - now
            days = remaining.days
            if days > 0:
                content = tn("剩余 {count} 天", days)
            else:
                content = tr("今天到期")
            InfoBar.success(
                title=tr("CDK 有效 (＾∀＾●)"),
                content=content,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window(),
            )
            source_card = self.source_card
            for i in range(source_card.comboBox.count()):
                if source_card.comboBox.itemData(i) == "MirrorChyan":
                    source_card.comboBox.setCurrentIndex(i)
                    break
        else:
            InfoBar.warning(
                title=tr("CDK 验证失败 (╥╯﹏╰╥)"),
                content=result,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self.window(),
            )

    def __onclicked2(self):
        QDesktopServices.openUrl(QUrl("https://mirrorchyan.com/?source=m7a-app"))

    def __onclicked3(self):
        QDesktopServices.openUrl(QUrl("https://pd.qq.com/g/MirrorChyan"))

    def __onclicked4(self):
        if not self.configvalue:
            InfoBar.warning(
                title=tr("尚未填写 CDK (╥╯﹏╰╥)"),
                content=tr('请先点击“修改”填写 Mirror 酱 CDK'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self.window(),
            )
            return
        self._start_cdk_validation(self.configvalue)


class PushSettingCardEval(CustomPushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue, parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window())
        if message_box.exec():
            cfg.set_value(self.configname, eval(message_box.getText()))
            self.contentLabel.setText(message_box.getText())


def choose_timestamp(title, current, parent):
    dialog = MessageBoxDate(title, current, parent)
    if not dialog.exec():
        return None
    time = dialog.getDateTime()
    # Make naive datetime explicit to local timezone to avoid negative timestamps on Windows
    if time.tzinfo is None or time.tzinfo.utcoffset(time) is None:
        local_offset = datetime.datetime.now().astimezone().utcoffset() or datetime.timedelta()
        time = time.replace(tzinfo=datetime.timezone(local_offset))
    try:
        timestamp = time.timestamp()
        display_time = time
    except (OSError, OverflowError, ValueError):
        timestamp = 0
        display_time = datetime.datetime.fromtimestamp(timestamp)
        InfoBar.warning(
            tr('时间无效'),
            tr('所选时间无法转换为时间戳，已使用默认时间'),
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=parent
        )
    return timestamp, display_time


class PushSettingCardKey(CustomPushSettingCard):
    keyChanged = Signal()

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None,
                 *, requires_key_template=False):
        self.configvalue = str(manual_game_hotkey(cfg, configname))
        self.requires_key_template = requires_key_template
        super().__init__(text, icon, title, configname, self._format_key_display(self.configvalue), parent)
        self.button.pressed.connect(self.__onpressed)
        self.button.released.connect(self.__onreleased)

    def set_detected_key(self, key: str | None):
        self.configvalue = str(manual_game_hotkey(cfg, self.configname))
        self.contentLabel.setText(self._format_key_display(key if key is not None else self.configvalue))
        self.button.setVisible(key is None)

    def __onpressed(self):
        self.button.setText(tr("按下要绑定的按键"))

    def __onreleased(self):
        self.button.setText(tr("按住以修改"))

    def keyPressEvent(self, e: QKeyEvent):
        if self.button.isDown():
            key_name = self._get_key_name(e)
            if self.requires_key_template and (
                e.modifiers() & Qt.KeyboardModifier.KeypadModifier or not key_prompt_path(key_name)
            ):
                self.button.setText(tr("该按键暂无识别模板"))
                return
            if key_name:
                cfg.set_value(self.configname, key_name)
                self.keyChanged.emit()
                self.contentLabel.setText(self._format_key_display(key_name))
                self.button.setText(tr("已改为 {key}").format(key=self._format_key_display(key_name)))

    @staticmethod
    def _format_key_display(key_name: str) -> str:
        """将存储的小写键名格式化为显示用的大写/首字母大写形式。"""
        if not key_name:
            return key_name
        special_names = {
            "capslock": "Caps Lock",
            "shiftleft": "Left Shift",
            "shiftright": "Right Shift",
            "ctrlleft": "Left Ctrl",
            "ctrlright": "Right Ctrl",
            "altright": "Right Alt",
            "divide": "Num /",
            "multiply": "Num *",
            "subtract": "Num -",
            "add": "Num +",
            "decimal": "Num .",
        }
        if len(key_name) == 4 and key_name.startswith("num") and key_name[3].isdigit():
            return f"Num {key_name[3]}"
        return special_names.get(key_name, key_name[0].upper() + key_name[1:])

    def _get_key_name(self, event):
        function_keys = {
            Qt.Key_F1: "f1",
            Qt.Key_F2: "f2",
            Qt.Key_F3: "f3",
            Qt.Key_F4: "f4",
            Qt.Key_F5: "f5",
            Qt.Key_F6: "f6",
            Qt.Key_F7: "f7",
            Qt.Key_F8: "f8",
            Qt.Key_F9: "f9",
            Qt.Key_F10: "f10",
            Qt.Key_F11: "f11",
            Qt.Key_F12: "f12",
        }

        special_keys = {
            Qt.Key_Escape: "esc",
            Qt.Key_Tab: "tab",
            Qt.Key_Space: "space",
            Qt.Key_Return: "enter",
            Qt.Key_Enter: "enter",
            Qt.Key_Backspace: "backspace",
            Qt.Key_Delete: "delete",
            Qt.Key_Insert: "insert",
            Qt.Key_Home: "home",
            Qt.Key_End: "end",
            Qt.Key_PageUp: "pageup",
            Qt.Key_PageDown: "pagedown",
            Qt.Key_Up: "up",
            Qt.Key_Down: "down",
            Qt.Key_Left: "left",
            Qt.Key_Right: "right",
            Qt.Key_Shift: "shift",
            Qt.Key_Control: "ctrl",
            Qt.Key_Alt: "alt",
        }

        key = event.key()

        if key in function_keys:
            return function_keys[key]

        if key in special_keys:
            return special_keys[key]

        text = event.text()
        if text and text.isprintable() and len(text) == 1:
            return text.lower()

        return None


class PushSettingCardInstance(CustomPushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, tr("说明：清体力是根据选择的副本类型来判断，副本名称也会用于双倍活动"), parent)
        # super().__init__(text, icon, title, configname, "", parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxInstance(self.title, self.configvalue, self.window())
        if message_box.exec():
            new_config = {}
            for type, combobox in message_box.comboBox_dict.items():
                raw_type, raw_name = instance_display_to_raw(type, combobox.text())
                new_config[raw_type] = raw_name
            self.configvalue = new_config
            cfg.set_value(self.configname, self.configvalue)
            # self.contentLabel.setText(str(self.configvalue))


class PushSettingCardInstanceChallengeCount(CustomPushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = cfg.get_value(configname)
        # super().__init__(text, icon, title, configname, str(self.configvalue), parent)
        super().__init__(text, icon, title, configname, "", parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxInstanceChallengeCount(self.title, self.configvalue, self.window())
        if message_box.exec():
            for type, slider in message_box.slider_dict.items():
                self.configvalue[type] = slider.value()
            cfg.set_value(self.configname, self.configvalue)
            # self.contentLabel.setText(str(self.configvalue))


class PushSettingCardNotifyTemplate(CustomPushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, "", parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxNotifyTemplate(self.title, self.configvalue, self.window())
        if message_box.exec():
            for id, lineedit in message_box.lineEdit_dict.items():
                self.configvalue[id] = lineedit.text().replace(r"\n", "\n")
            cfg.set_value(self.configname, self.configvalue)


class PushSettingCardTeam(CustomPushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.template = get_character_names()
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, self.translate_to_chinese(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def translate_to_chinese(self, configvalue):
        text = str(configvalue)
        for key, value in self.template.items():
            text = text.replace(key, value)
        return text

    def __onclicked(self):
        message_box = MessageBoxTeam(self.title, self.configvalue, self.template, self.window())
        if message_box.exec():
            self.newConfigValue = []
            for comboboxs in message_box.comboBox_list:
                char = get_key_from_value(comboboxs[0].text(), message_box.template)
                tech = get_key_from_value(comboboxs[1].text(), message_box.tech_map)
                self.newConfigValue.append([char, tech])
            self.configvalue = self.newConfigValue
            cfg.set_value(self.configname, self.newConfigValue)
            self.contentLabel.setText(self.translate_to_chinese(self.newConfigValue))


class PushSettingCardFriends(CustomPushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        # include 'None' mapping for friends list
        self.template = get_character_names(include_none=True)
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, self.translate_to_chinese(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def translate_to_chinese(self, configvalue):
        text = str(configvalue)
        for key, value in self.template.items():
            text = text.replace(key, value)
        return text

    def __onclicked(self):
        message_box = MessageBoxFriends(self.title, self.configvalue, self.template, self.window())
        if message_box.exec():
            self.newConfigValue = []
            for comboboxs in message_box.comboBox_list:
                char = get_key_from_value(comboboxs[0].text(), message_box.template)
                # tech = get_key_from_value(comboboxs[1].text(), message_box.tech_map)
                name = comboboxs[1].text()
                self.newConfigValue.append([char, name])
            self.configvalue = self.newConfigValue
            cfg.set_value(self.configname, self.newConfigValue)
            self.contentLabel.setText(self.translate_to_chinese(self.newConfigValue))


class PushSettingCardPowerPlan(CustomPushSettingCard):
    """体力计划设置卡片"""

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, self._get_display_text(), parent)
        self.button.clicked.connect(self.__onclicked)

    def _get_display_text(self):
        """获取显示文本"""
        if not self.configvalue:
            return tr("暂无计划")
        return tn("已配置 {count} 项计划", len(self.configvalue))

    def __onclicked(self):
        message_box = MessageBoxPowerPlan(
            self.title,
            self.configvalue,
            self.window(),
            keep_plan=cfg.get_value("power_plan_keep", False),
            continue_after_plan=cfg.get_value("power_plan_continue", True),
        )
        if message_box.exec():
            plans = message_box.get_plans()
            self.configvalue = plans
            cfg.set_values({
                self.configname: plans,
                "power_plan_keep": message_box.should_keep_plan(),
                "power_plan_continue": message_box.should_continue_after_plan(),
            })
            self.contentLabel.setText(self._get_display_text())


class InstanceTeamSettingCard(SettingCard):
    """副本队伍设置卡片"""

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.card_title = title

        self.configButton = QPushButton(tr("配置"), self)
        self.hBoxLayout.addWidget(self.configButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.configButton.clicked.connect(self.__onConfigClicked)

        self.switchButton = SwitchButton(tr("关"), self, IndicatorPosition.RIGHT)
        self.setValue(cfg.get_value("instance_team_enable"))

        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

        self._update_content_text()

    def __onCheckedChanged(self, isChecked: bool):
        self.setValue(isChecked)
        cfg.set_value("instance_team_enable", isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(bool(isChecked))
        self.switchButton.setText(tr("开") if isChecked else tr("关"))

    def _update_content_text(self):
        self.contentLabel.show()

        teams = cfg.get_value("instance_teams")
        if teams:
            self.contentLabel.setText(tn("已配置 {count} 项规则", len(teams)))
        else:
            self.contentLabel.setText(tr("为特定的副本配置队伍"))

    def __onConfigClicked(self):
        """打开配置对话框"""
        default_team = int(cfg.get_value("instance_team_number", 3))
        teams = cfg.get_value("instance_teams", [])

        message_box = MessageBoxInstanceTeam(self.card_title, default_team, teams, self.window())

        if message_box.exec():
            new_default_team = message_box.get_default_team()
            new_teams = message_box.get_rules()
            cfg.set_values({
                "instance_team_number": str(new_default_team),
                "instance_teams": new_teams,
            })

            self._update_content_text()
