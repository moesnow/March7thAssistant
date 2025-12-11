# coding:utf-8
from typing import Union
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QLabel, QButtonGroup, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    ExpandSettingCard,
    FluentIconBase,
    IndicatorPosition,
    RadioButton,
    SpinBox,
    SwitchButton,
    CheckBox,
    isDarkTheme,
    qconfig,
)


class AutoPlotSettingCard(ExpandSettingCard):
    """ Setting card for auto plot with switch and expandable options """

    switchChanged = pyqtSignal(bool)
    optionsChanged = pyqtSignal(dict)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)

        # Switch button
        self.switchButton = SwitchButton(self.tr('关'), self, IndicatorPosition.RIGHT)

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

        # Dialog mode
        mode_widget = QWidget(self.view)
        mode_layout = QHBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self.modeLabel = QLabel(self.tr("对话模式:"), mode_widget)
        self.modeButtonGroup = QButtonGroup(self.view)
        self.periodModeButton = RadioButton(self.tr("固定间隔"), self.view)
        self.adaptiveModeButton = RadioButton(self.tr("自适应"), self.view)
        self.modeButtonGroup.addButton(self.periodModeButton)
        self.modeButtonGroup.addButton(self.adaptiveModeButton)
        self.periodModeButton.setChecked(True)
        mode_layout.addWidget(self.modeLabel)
        mode_layout.addWidget(self.periodModeButton)
        mode_layout.addWidget(self.adaptiveModeButton)
        mode_layout.addStretch(1)
        self.viewLayout.addWidget(mode_widget)

        # Auto skip checkbox
        self.autoSkipCheckBox = CheckBox(self.tr("自动跳过 (当出现跳过按钮时自动点击)"), self.view)
        self.autoSkipCheckBox.setChecked(True)
        self.viewLayout.addWidget(self.autoSkipCheckBox)

        # Auto click dialog options checkbox
        self.autoClickCheckBox = CheckBox(self.tr("自动选择 (自动选择任意对话选项)"), self.view)
        self.autoClickCheckBox.setChecked(True)
        self.viewLayout.addWidget(self.autoClickCheckBox)

        # Adaptive delay (for adaptive mode)
        adaptive_widget = QWidget(self.view)
        adaptive_layout = QHBoxLayout(adaptive_widget)
        adaptive_layout.setContentsMargins(0, 0, 0, 0)
        self.adaptiveDelayLabel = QLabel(self.tr("阅读延迟:"), adaptive_widget)
        self.adaptiveDelaySpinBox = SpinBox(adaptive_widget)
        self.adaptiveDelaySpinBox.setRange(100, 5000)
        self.adaptiveDelaySpinBox.setSingleStep(100)
        self.adaptiveDelaySpinBox.setValue(10)
        self.adaptiveUnitLabel = QLabel(self.tr("毫秒"), adaptive_widget)
        adaptive_layout.addWidget(self.adaptiveDelayLabel)
        adaptive_layout.addWidget(self.adaptiveDelaySpinBox)
        adaptive_layout.addWidget(self.adaptiveUnitLabel)
        adaptive_layout.addStretch(1)
        self.adaptiveDelayWidget = adaptive_widget
        self.viewLayout.addWidget(adaptive_widget)

        # Period interval (for period mode)
        period_widget = QWidget(self.view)
        period_layout = QHBoxLayout(period_widget)
        period_layout.setContentsMargins(0, 0, 0, 0)
        self.periodIntervalLabel = QLabel(self.tr("点击间隔:"), period_widget)
        self.periodIntervalSpinBox = SpinBox(period_widget)
        self.periodIntervalSpinBox.setRange(10, 5000)
        self.periodIntervalSpinBox.setSingleStep(10)
        self.periodIntervalSpinBox.setValue(50)
        self.periodUnitLabel = QLabel(self.tr("毫秒"), period_widget)
        period_layout.addWidget(self.periodIntervalLabel)
        period_layout.addWidget(self.periodIntervalSpinBox)
        period_layout.addWidget(self.periodUnitLabel)
        period_layout.addStretch(1)
        self.periodIntervalWidget = period_widget
        self.viewLayout.addWidget(period_widget)

        # Connect all option changes
        self.modeButtonGroup.buttonClicked.connect(self._onModeChanged)
        self.autoSkipCheckBox.stateChanged.connect(self._emit_options_changed)
        self.autoClickCheckBox.stateChanged.connect(self._emit_options_changed)
        self.adaptiveDelaySpinBox.valueChanged.connect(self._emit_options_changed)
        self.periodIntervalSpinBox.valueChanged.connect(self._emit_options_changed)
        qconfig.themeChanged.connect(self._updateLabelColors)

        self._onModeChanged()  # Set initial visibility
        self._updateLabelColors()

        # Adjust view size
        self._adjustViewSize()

    def _onModeChanged(self):
        """Handle mode change to show/hide relevant options"""
        is_adaptive = self.adaptiveModeButton.isChecked()
        self.adaptiveDelayWidget.setVisible(is_adaptive)
        self.periodIntervalWidget.setVisible(not is_adaptive)
        self._adjustViewSize()
        self._emit_options_changed()

    def __onSwitchChanged(self, isChecked: bool):
        """Switch button checked state changed slot"""
        self.setValue(isChecked)
        self.switchChanged.emit(isChecked)

    def setValue(self, isChecked: bool):
        """Set switch button state"""
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(self.tr('开') if isChecked else self.tr('关'))

    def getSwitchState(self) -> bool:
        """Get current switch state"""
        return self.switchButton.isChecked()

    def getOptions(self) -> dict:
        """Get current configuration options"""
        return {
            'mode': 'adaptive' if self.adaptiveModeButton.isChecked() else 'period',
            'auto_skip': self.autoSkipCheckBox.isChecked(),
            'auto_click': self.autoClickCheckBox.isChecked(),
            'adaptive_delay': self.adaptiveDelaySpinBox.value(),
            'period_interval': self.periodIntervalSpinBox.value()
        }

    def _emit_options_changed(self):
        """Emit options changed signal"""
        self.optionsChanged.emit(self.getOptions())

    def _updateLabelColors(self):
        """Update label colors based on current theme"""
        color = "#FFFFFF" if isDarkTheme() else "#000000"
        for label in (
            self.modeLabel,
            self.adaptiveDelayLabel,
            self.adaptiveUnitLabel,
            self.periodIntervalLabel,
            self.periodUnitLabel,
        ):
            label.setStyleSheet(f"color: {color};")
