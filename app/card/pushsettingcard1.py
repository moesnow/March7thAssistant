from PyQt5.QtCore import Qt, pyqtSignal, QUrl
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QDesktopServices
from qfluentwidgets import SettingCard, FluentIconBase, InfoBar, InfoBarPosition
from .messagebox_custom import MessageBoxEdit, MessageBoxEditMultiple, MessageBoxDate, MessageBoxInstance, MessageBoxInstanceChallengeCount, MessageBoxNotifyTemplate, MessageBoxTeam, MessageBoxFriends
from tasks.base.tasks import start_task
from module.config import cfg
from typing import Union
import datetime
import json
import re
from ..tools.check_update import checkUpdate


class PushSettingCard(SettingCard):
    clicked = pyqtSignal()

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, configvalue, parent=None):
        super().__init__(icon, title, configvalue, parent)
        self.title = title
        self.configname = configname
        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)


class PushSettingCardStr(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue, parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window())
        if message_box.exec():
            cfg.set_value(self.configname, message_box.getText())
            self.contentLabel.setText(message_box.getText())
            self.configvalue = message_box.getText()


class PushSettingCardMirrorchyan(SettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, update_callback, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        self.update_callback = update_callback
        super().__init__(icon, title, "", parent)

        self.title = title
        self.configname = configname

        self.button3 = QPushButton("交流反馈", self)
        self.button3.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button3, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button3.clicked.connect(self.__onclicked3)

        self.button2 = QPushButton("获取 CDK", self)
        self.button2.setObjectName('primaryButton')
        self.hBoxLayout.addWidget(self.button2, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.button2.clicked.connect(self.__onclicked2)

        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window())
        if message_box.exec():
            cfg.set_value(self.configname, message_box.getText())
            self.contentLabel.setText(message_box.getText())
            self.configvalue = message_box.getText()
            checkUpdate(self.update_callback)

    def __onclicked2(self):
        QDesktopServices.openUrl(QUrl("https://mirrorchyan.com/?source=m7a-app"))

    def __onclicked3(self):
        QDesktopServices.openUrl(QUrl("https://pd.qq.com/g/MirrorChyan"))


class PushSettingCardCode(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = '\n'.join(cfg.get_value(configname))
        self.parent = parent
        super().__init__(text, icon, title, configname, "批量使用兑换码，每行一个，自动过滤空格等无效字符", parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEditMultiple(self.title, self.configvalue, self.window())
        if message_box.exec():
            text = message_box.getText()
            code = [line.strip() for line in [''.join(re.findall(r'[A-Za-z0-9]', line)) for line in text.split('\n')] if line.strip()]
            # code = [''.join(re.findall(r'[A-Za-z0-9]', line.strip())) for line in text.split('\n') if line.strip()]
            cfg.set_value(self.configname, code)
            self.configvalue = '\n'.join(code)
            if code != []:
                start_task("redemption")
            else:
                InfoBar.warning(
                    self.tr('兑换码为空'),
                    self.tr(''),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self.parent
                )


class PushSettingCardEval(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue, parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxEdit(self.title, self.configvalue, self.window())
        if message_box.exec():
            cfg.set_value(self.configname, eval(message_box.getText()))
            self.contentLabel.setText(message_box.getText())


class PushSettingCardDate(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = datetime.datetime.fromtimestamp(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue.strftime('%Y-%m-%d %H:%M'), parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxDate(self.title, self.configvalue, self.window())
        if message_box.exec():
            time = message_box.getDateTime()
            cfg.set_value(self.configname, time.timestamp())
            self.contentLabel.setText(time.strftime('%Y-%m-%d %H:%M'))


class PushSettingCardKey(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = str(cfg.get_value(configname))
        super().__init__(text, icon, title, configname, self.configvalue, parent)
        self.button.pressed.connect(self.__onpressed)
        self.button.released.connect(self.__onreleased)

    def __onpressed(self):
        self.button.setText("按下要绑定的按键")

    def __onreleased(self):
        self.button.setText("按住以修改")

    def keyPressEvent(self, e: QKeyEvent):
        if self.button.isDown():
            key_name = self._get_key_name(e)
            if key_name:
                cfg.set_value(self.configname, key_name)
                self.contentLabel.setText(key_name)
                self.button.setText(f"已改为 {key_name}")

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


class PushSettingCardInstance(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, configtemplate, parent=None):
        self.configtemplate = configtemplate
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, str(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxInstance(self.title, self.configvalue, self.configtemplate, self.window())
        if message_box.exec():
            for type, combobox in message_box.comboBox_dict.items():
                self.configvalue[type] = combobox.text().split('（')[0]
            cfg.set_value(self.configname, self.configvalue)
            self.contentLabel.setText(str(self.configvalue))


class PushSettingCardInstanceChallengeCount(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, str(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        message_box = MessageBoxInstanceChallengeCount(self.title, self.configvalue, self.window())
        if message_box.exec():
            for type, slider in message_box.slider_dict.items():
                self.configvalue[type] = slider.value()
            cfg.set_value(self.configname, self.configvalue)
            self.contentLabel.setText(str(self.configvalue))


class PushSettingCardNotifyTemplate(PushSettingCard):
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


class PushSettingCardTeam(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        with open("./assets/config/character_names.json", 'r', encoding='utf-8') as file:
            self.template = json.load(file)
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, self.translate_to_chinese(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def translate_to_chinese(self, configvalue):
        text = str(configvalue)
        for key, value in self.template.items():
            text = text.replace(key, value)
        return text

    def __onclicked(self):
        def get_key(val, map):
            for key, value in map.items():
                if value == val:
                    return key
            return None

        message_box = MessageBoxTeam(self.title, self.configvalue, self.template, self.window())
        if message_box.exec():
            self.newConfigValue = []
            for comboboxs in message_box.comboBox_list:
                char = get_key(comboboxs[0].text(), message_box.template)
                tech = get_key(comboboxs[1].text(), message_box.tech_map)
                self.newConfigValue.append([char, tech])
            self.configvalue = self.newConfigValue
            cfg.set_value(self.configname, self.newConfigValue)
            self.contentLabel.setText(self.translate_to_chinese(self.newConfigValue))


class PushSettingCardFriends(PushSettingCard):
    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname, parent=None):
        with open("./assets/config/character_names.json", 'r', encoding='utf-8') as file:
            self.template = json.load(file)
            self.template = {'None': '无', **self.template}
        self.configvalue = cfg.get_value(configname)
        super().__init__(text, icon, title, configname, self.translate_to_chinese(self.configvalue), parent)
        self.button.clicked.connect(self.__onclicked)

    def translate_to_chinese(self, configvalue):
        text = str(configvalue)
        for key, value in self.template.items():
            text = text.replace(key, value)
        return text

    def __onclicked(self):
        def get_key(val, map):
            for key, value in map.items():
                if value == val:
                    return key
            return None

        message_box = MessageBoxFriends(self.title, self.configvalue, self.template, self.window())
        if message_box.exec():
            self.newConfigValue = []
            for comboboxs in message_box.comboBox_list:
                char = get_key(comboboxs[0].text(), message_box.template)
                # tech = get_key(comboboxs[1].text(), message_box.tech_map)
                name = comboboxs[1].text()
                self.newConfigValue.append([char, name])
            self.configvalue = self.newConfigValue
            cfg.set_value(self.configname, self.newConfigValue)
            self.contentLabel.setText(self.translate_to_chinese(self.newConfigValue))
