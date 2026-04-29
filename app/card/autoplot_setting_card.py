# coding:utf-8
from typing import Union
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import (
    ExpandSettingCard,
    FluentIconBase,
    IndicatorPosition,
    SwitchButton,
    CheckBox,
)
from module.localization import tr


class AutoPlotSettingCard(ExpandSettingCard):
    """ Setting card for auto plot with switch and expandable options """

    switchChanged = Signal(bool)
    optionsChanged = Signal(dict)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)

        # Switch button
        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)

        # Add switch button to card layout using addWidget method
        self.card.addWidget(self.switchButton)

        # Configuration options
        self._init_options()

        # Connect signals
        self.switchButton.checkedChanged.connect(self.__onSwitchChanged)

    def _init_options(self):
        """Initialize configuration options in the expandable view"""
        # Create widgets container
        self.viewLayout.setSpacing(19)
        self.viewLayout.setContentsMargins(48, 18, 48, 18)

        # Auto skip checkbox
        self.autoSkipCheckBox = CheckBox(tr("自动跳过 (当出现跳过按钮时自动点击)"), self.view)
        self.autoSkipCheckBox.setChecked(True)
        self.viewLayout.addWidget(self.autoSkipCheckBox)

        # Auto click dialog options checkbox
        self.autoClickCheckBox = CheckBox(tr("自动选择 (自动选择任意对话选项)"), self.view)
        self.autoClickCheckBox.setChecked(True)
        self.viewLayout.addWidget(self.autoClickCheckBox)

        # Auto battle detect checkbox
        self.autoBattleDetectCheckBox = CheckBox(tr("自动战斗检测 (检测到未自动战斗时按V开启)"), self.view)
        self.autoBattleDetectCheckBox.setChecked(True)
        self.viewLayout.addWidget(self.autoBattleDetectCheckBox)

        # Auto phone dialog detect checkbox
        self.autoPhoneDetectCheckBox = CheckBox(tr("自动短信 (自动点击关闭手机短信页面)"), self.view)
        self.autoPhoneDetectCheckBox.setChecked(True)
        self.viewLayout.addWidget(self.autoPhoneDetectCheckBox)

        # Connect all option changes
        self.autoSkipCheckBox.stateChanged.connect(self._emit_options_changed)
        self.autoClickCheckBox.stateChanged.connect(self._emit_options_changed)
        self.autoBattleDetectCheckBox.stateChanged.connect(self._emit_options_changed)
        self.autoPhoneDetectCheckBox.stateChanged.connect(self._emit_options_changed)

        # Adjust view size
        self._adjustViewSize()

    def __onSwitchChanged(self, isChecked: bool):
        """Switch button checked state changed slot"""
        self.setValue(isChecked)
        self.switchChanged.emit(isChecked)

    def setValue(self, isChecked: bool):
        """Set switch button state"""
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def getSwitchState(self) -> bool:
        """Get current switch state"""
        return self.switchButton.isChecked()

    def getOptions(self) -> dict:
        """Get current configuration options"""
        return {
            'auto_skip': self.autoSkipCheckBox.isChecked(),
            'auto_click': self.autoClickCheckBox.isChecked(),
            'auto_battle_detect_enable': self.autoBattleDetectCheckBox.isChecked(),
            'auto_phone_detect_enable': self.autoPhoneDetectCheckBox.isChecked(),
        }

    def _emit_options_changed(self):
        """Emit options changed signal"""
        self.optionsChanged.emit(self.getOptions())
