from qfluentwidgets import (SettingCard, FluentIconBase)
from PyQt5.QtWidgets import QPushButton
from typing import Union
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import (QIcon, QKeyEvent)
from managers.config_manager import config
from .messagebox1 import MessageBox1
import datetime


class PushSettingCardStr(SettingCard):
    """ Setting card with a push button """

    clicked = pyqtSignal()

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname=None, parent=None):
        super().__init__(icon, title, str(config.get_value(configname)), parent)
        self.title = title
        self.configname = configname
        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        w = MessageBox1(self.title, str(config.get_value(self.configname)), self.window())
        if w.exec():
            config.set_value(self.configname, w.getText())
            self.contentLabel.setText(w.getText())


class PushSettingCardEval(SettingCard):
    """ Setting card with a push button """

    clicked = pyqtSignal()

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname=None, parent=None):
        super().__init__(icon, title, str(config.get_value(configname)), parent)
        self.title = title
        self.configname = configname
        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        w = MessageBox1(self.title, str(config.get_value(self.configname)), self.window())
        if w.exec():
            config.set_value(self.configname, eval(w.getText()))
            self.contentLabel.setText(w.getText())


class PushSettingCardDate(SettingCard):
    """ Setting card with a push button """

    clicked = pyqtSignal()

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname=None, parent=None):
        self.date_string = datetime.datetime.fromtimestamp(config.get_value(configname)).strftime('%Y-%m-%d %H:%M:%S')
        super().__init__(icon, title, self.date_string, parent)
        self.title = title
        self.configname = configname
        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.clicked.connect(self.__onclicked)

    def __onclicked(self):
        w = MessageBox1(self.title, self.date_string, self.window())
        if w.exec():
            timestamp = datetime.datetime.strptime(w.getText(), '%Y-%m-%d %H:%M:%S').timestamp()
            config.set_value(self.configname, timestamp)
            self.contentLabel.setText(w.getText())


class PushSettingCardKey(SettingCard):
    """ Setting card with a push button """

    clicked = pyqtSignal()

    def __init__(self, text, icon: Union[str, QIcon, FluentIconBase], title, configname=None, parent=None):
        super().__init__(icon, title, str(config.get_value(configname)), parent)
        self.title = title
        self.configname = configname
        self.button = QPushButton(text, self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.pressed.connect(self.__onpressed)
        self.button.released.connect(self.__onreleased)

    def __onpressed(self):
        self.button.setText("按下要绑定的按键")

    def __onreleased(self):
        self.button.setText("按住以修改")

    def keyPressEvent(self, e: QKeyEvent):
        if(self.button.isDown()):
            config.set_value(self.configname, e.text())
            self.contentLabel.setText(e.text())
            self.button.setText(f"已改为 {e.text()}")
