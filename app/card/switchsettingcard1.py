from qfluentwidgets import (SettingCard, FluentIconBase, SwitchButton, IndicatorPosition, ComboBox)
from typing import Union
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon

from module.config import cfg


class SwitchSettingCard1(SettingCard):
    """ Setting card with switch button """

    checkedChanged = pyqtSignal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.switchButton = SwitchButton(
            self.tr('关'), self, IndicatorPosition.RIGHT)

        self.setValue(cfg.get_value(self.configname))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        cfg.set_value(self.configname, isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(self.tr('开') if isChecked else self.tr('关'))


class SwitchSettingCardTeam(SettingCard):
    """ Setting card with switch button """

    checkedChanged = pyqtSignal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, configname2: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.configname2 = configname2

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(10)

        texts = ['3', '4', '5', '6', '7']
        for text, option in zip(texts, texts):
            self.comboBox.addItem(text, userData=option)

        self.comboBox.setCurrentText(cfg.get_value(configname2))
        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

        self.switchButton = SwitchButton(self.tr('关'), self, IndicatorPosition.RIGHT)

        self.setValue(cfg.get_value(self.configname))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        cfg.set_value(self.configname, isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(self.tr('开') if isChecked else self.tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value(self.configname2, self.comboBox.itemData(index))


class SwitchSettingCardImmersifier(SettingCard):
    """ Setting card with switch button """

    checkedChanged = pyqtSignal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(10)

        texts = ['1', '2', '3', '4', '5', '6', '7', '8']
        for text, option in zip(texts, texts):
            self.comboBox.addItem(text, userData=option)

        self.comboBox.setCurrentText(cfg.get_value("merge_immersifier_limit"))
        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

        self.switchButton = SwitchButton(self.tr('关'), self, IndicatorPosition.RIGHT)

        self.setValue(cfg.get_value(self.configname))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        cfg.set_value(self.configname, isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(self.tr('开') if isChecked else self.tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value("merge_immersifier_limit", self.comboBox.itemData(index))


class SwitchSettingCardGardenofplenty(SettingCard):
    """ Setting card with switch button """

    checkedChanged = pyqtSignal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, configname: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname

        self.comboBox = ComboBox(self)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(10)

        texts = ['拟造花萼（金）', '拟造花萼（赤）']
        for text, option in zip(texts, texts):
            self.comboBox.addItem(text, userData=option)

        self.comboBox.setCurrentText(cfg.get_value("activity_gardenofplenty_instance_type"))
        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

        self.switchButton = SwitchButton(self.tr('关'), self, IndicatorPosition.RIGHT)

        self.setValue(cfg.get_value(self.configname))

        # add switch button to layout
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)

    def __onCheckedChanged(self, isChecked: bool):
        """ switch button checked state changed slot """
        self.setValue(isChecked)
        cfg.set_value(self.configname, isChecked)

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(self.tr('开') if isChecked else self.tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        cfg.set_value("activity_gardenofplenty_instance_type", self.comboBox.itemData(index))
