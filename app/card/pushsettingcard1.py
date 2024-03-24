from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5.QtWidgets import QPushButton
from qfluentwidgets import SettingCard, FluentIconBase
from .messagebox_custom import MessageBoxEdit, MessageBoxDate, MessageBoxInstance, MessageBoxNotifyTemplate, MessageBoxTeam
from module.config import cfg
from typing import Union
import datetime
import json


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
        if (self.button.isDown()):
            cfg.set_value(self.configname, e.text())
            self.contentLabel.setText(e.text())
            self.button.setText(f"已改为 {e.text()}")


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
                name = get_key(comboboxs[0].text(), message_box.template)
                tech = get_key(comboboxs[1].text(), message_box.tech_map)
                self.newConfigValue.append([name, tech])
            self.configvalue = self.newConfigValue
            cfg.set_value(self.configname, self.newConfigValue)
            self.contentLabel.setText(self.translate_to_chinese(self.newConfigValue))
