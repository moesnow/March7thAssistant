# coding:utf-8
"""开机自启设置卡片与配置对话框（Windows）。

- 检测到旧版（计划任务固定执行完整运行）开机启动时，卡片显示「升级到新版」按钮：
  点击后删除旧的计划任务（不会中断它已启动的程序），卡片切换为新版的开/关 + 配置按钮。
- 新版开机启动由登录触发的计划任务静默提权承载（见 utils/autostart.py），
  「配置」按钮用于设置启动后是否打开图形界面、是否最小化、以及自动执行的任务。
"""

from typing import Union

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QScrollArea, QWidget
from qfluentwidgets import (
    BodyLabel,
    CheckBox,
    ComboBox,
    FluentIconBase,
    IndicatorPosition,
    InfoBar,
    InfoBarPosition,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    SettingCard,
    SubtitleLabel,
    SwitchButton,
)

from module.config import cfg
from module.localization import tr
from utils import autostart
from utils.tasks import AVAILABLE_TASKS


class AutostartConfigDialog(MessageBoxBase):
    """开机启动配置对话框：是否打开图形界面、是否最小化、自动执行的任务"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(tr("开机启动设置"), self.widget)

        # 显示本地化任务名，保存时保留任务ID（AVAILABLE_TASKS 存的是中文原文）
        self._task_ids = list(AVAILABLE_TASKS.keys())
        self._task_labels = [tr(name) for name in AVAILABLE_TASKS.values()]

        # 启动后是否打开图形界面
        self.openGuiCheck = CheckBox(tr("登录后打开图形界面"), self.widget)
        self.openGuiCheck.setChecked(bool(cfg.get_value("autostart_open_gui", True)))

        # 打开图形界面后是否最小化
        self.minimizeCheck = CheckBox(tr("打开图形界面后最小化到托盘"), self.widget)
        self.minimizeCheck.setChecked(bool(cfg.get_value("autostart_minimize", False)))

        # 打开图形界面后是否启动某一个任务（可不执行）
        self.guiTaskLabel = BodyLabel(tr("打开图形界面后自动执行的任务："), self.widget)
        self.guiTaskCombo = ComboBox(self.widget)
        self.guiTaskCombo.addItem(tr("不执行"))
        self.guiTaskCombo.addItems(self._task_labels)
        gui_task = cfg.get_value("autostart_gui_task") or ""
        self.guiTaskCombo.setCurrentIndex(self._task_ids.index(gui_task) + 1 if gui_task in self._task_ids else 0)

        # 不打开图形界面时必须选择一项任务
        self.headlessTaskLabel = BodyLabel(tr("不打开图形界面时执行的任务："), self.widget)
        self.headlessTaskCombo = ComboBox(self.widget)
        self.headlessTaskCombo.addItems(self._task_labels)
        headless_task = cfg.get_value("autostart_headless_task") or "main"
        self.headlessTaskCombo.setCurrentIndex(self._task_ids.index(headless_task) if headless_task in self._task_ids else 0)
        self.headlessHintLabel = BodyLabel(
            tr("不打开图形界面时必须选择一项任务，将以命令行窗口执行，与手动运行命令行版一致"), self.widget)

        self.hintLabel = BodyLabel(tr("请选择要执行的任务"), self.widget)
        self.hintLabel.setStyleSheet("color: #e74c3c;")
        self.hintLabel.setVisible(False)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.openGuiCheck)
        self.viewLayout.addWidget(self.minimizeCheck)
        self.viewLayout.addWidget(self.guiTaskLabel)
        self.viewLayout.addWidget(self.guiTaskCombo)
        self.viewLayout.addWidget(self.headlessTaskLabel)
        self.viewLayout.addWidget(self.headlessTaskCombo)
        self.viewLayout.addWidget(self.headlessHintLabel)
        self.viewLayout.addWidget(self.hintLabel)
        self.viewLayout.setSpacing(8)
        self.widget.setMinimumWidth(420)
        self.yesButton.setText(tr("保存"))
        self.cancelButton.setText(tr("取消"))

        self.openGuiCheck.stateChanged.connect(self._updateModeVisibility)
        self._updateModeVisibility()

    def _updateModeVisibility(self):
        """打开图形界面时配置最小化与自动任务，否则必须选择一项任务"""
        open_gui = self.openGuiCheck.isChecked()
        self.minimizeCheck.setVisible(open_gui)
        self.guiTaskLabel.setVisible(open_gui)
        self.guiTaskCombo.setVisible(open_gui)
        self.headlessTaskLabel.setVisible(not open_gui)
        self.headlessTaskCombo.setVisible(not open_gui)
        self.headlessHintLabel.setVisible(not open_gui)
        if open_gui:
            self.hintLabel.setVisible(False)

    def validate(self) -> bool:
        if not self.openGuiCheck.isChecked() and self.headlessTaskCombo.currentIndex() < 0:
            self.hintLabel.setVisible(True)
            return False
        self.hintLabel.setVisible(False)
        return True

    def accept(self):
        gui_task = ""
        if self.guiTaskCombo.currentIndex() > 0:
            gui_task = self._task_ids[self.guiTaskCombo.currentIndex() - 1]
        headless_task = "main"
        if self.headlessTaskCombo.currentIndex() >= 0:
            headless_task = self._task_ids[self.headlessTaskCombo.currentIndex()]
        cfg.set_values({
            "autostart_open_gui": self.openGuiCheck.isChecked(),
            "autostart_minimize": self.minimizeCheck.isChecked(),
            "autostart_gui_task": gui_task,
            "autostart_headless_task": headless_task,
        })
        super().accept()


class AutostartSettingCard(SettingCard):
    """开机自启设置卡片：旧版显示「升级到新版」按钮，新版为开/关 + 配置按钮"""

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self._syncing = False
        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)
        self.configButton = PushButton(tr('配置'), self)
        self.upgradeButton = PrimaryPushButton(tr('升级到新版'), self)

        # 按钮统一放进容器，隐藏时布局自动收缩
        self.buttonWidget = QWidget(self)
        self.buttonLayout = QHBoxLayout(self.buttonWidget)
        self.buttonLayout.setContentsMargins(0, 0, 16, 0)
        self.buttonLayout.setSpacing(10)
        self.buttonLayout.addWidget(self.upgradeButton)
        self.buttonLayout.addWidget(self.configButton)
        self.buttonLayout.addWidget(self.switchButton)
        self.hBoxLayout.addWidget(self.buttonWidget, 0, Qt.AlignmentFlag.AlignRight)

        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)
        self.configButton.clicked.connect(self.__onConfigClicked)
        self.upgradeButton.clicked.connect(self.__onUpgradeClicked)

        self.refreshState()

    def setValue(self, isChecked: bool):
        """同步开关显示状态（程序化同步不触发 checkedChanged，避免误弹提示/重复写配置）"""
        self._syncing = True
        try:
            self.switchButton.blockSignals(True)
            self.switchButton.setChecked(bool(isChecked))
            self.switchButton.setText(tr('开') if isChecked else tr('关'))
            self.switchButton.blockSignals(False)
        finally:
            self._syncing = False

    def refreshState(self):
        """按旧版/新版切换卡片形态，并同步开/关状态（保持页面滚动位置不动）"""
        legacy = autostart.is_legacy_task_enabled()
        scroll_bar = self._enclosing_scroll_bar()
        saved_scroll = scroll_bar.value() if scroll_bar is not None else None

        # 焦点所在的按钮即将被隐藏时先清除焦点，并先显示新按钮再隐藏旧按钮，
        # 避免 Qt 把焦点交给页面远处的控件并把页面滚动过去（看起来像“跳”了一格）
        focused = QApplication.focusWidget()
        if focused is not None and focused in (self.upgradeButton, self.configButton, self.switchButton):
            focused.clearFocus()

        self.configButton.setVisible(not legacy)
        self.switchButton.setVisible(not legacy)
        self.upgradeButton.setVisible(legacy)
        if not legacy:
            self.setValue(autostart.is_enabled())

        if scroll_bar is not None and saved_scroll is not None:
            scroll_bar.setValue(saved_scroll)
            # 布局/焦点引发的滚动可能是延迟的，稍后再恢复一次
            def _restore(bar=scroll_bar, value=saved_scroll):
                try:
                    bar.setValue(value)
                except Exception:
                    pass
            QTimer.singleShot(0, _restore)

    def _enclosing_scroll_bar(self):
        """找到包含本卡片的滚动条（设置页面），用于保持切换状态时页面不滚动"""
        w = self.parentWidget()
        while w is not None:
            if isinstance(w, QScrollArea):
                return w.verticalScrollBar()
            w = w.parentWidget()
        return None

    def __onCheckedChanged(self, isChecked: bool):
        if self._syncing:
            return
        ok = autostart.enable() if isChecked else autostart.disable()
        if ok:
            self.setValue(isChecked)
            self.checkedChanged.emit(isChecked)
            if isChecked:
                InfoBar.success(
                    title=tr('开机启动已开启'),
                    content="",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self.window()
                )
            else:
                InfoBar.info(
                    title=tr('开机启动已关闭'),
                    content="",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self.window()
                )
        else:
            self.setValue(not isChecked)
            InfoBar.error(
                title=tr('开机启动设置失败'),
                content=tr('请以管理员权限运行后重试'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window()
            )

    def __onConfigClicked(self):
        dialog = AutostartConfigDialog(self.window())
        if dialog.exec():
            self.refreshState()
            InfoBar.success(
                title=tr('开机启动设置已保存'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self.window()
            )

    def __onUpgradeClicked(self):
        if autostart.remove_legacy_task():
            self.refreshState()
            InfoBar.success(
                title=tr('已升级到新版开机启动'),
                content=tr('旧的计划任务已删除，请按需配置并重新开启开关'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window()
            )
        else:
            InfoBar.error(
                title=tr('升级到新版失败'),
                content=tr('删除旧的计划任务失败，请重试'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window()
            )
