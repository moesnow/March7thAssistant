# coding:utf-8
"""免 UAC 运行设置卡片（Windows）。

- 开启前弹窗说明这项功能会带来的变化和风险，用户确认后才注册计划任务（见 utils/uac_free.py）；关闭即删除计划任务。
- 开关状态以计划任务为准：任务不存在、被禁用或指向其他安装目录时都显示为关闭，重新开启会改为指向本安装。
"""

from typing import Union

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import (
    FluentIconBase,
    IndicatorPosition,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    SettingCard,
    SwitchButton,
)

from module.localization import tr
from utils import uac_free


class UacFreeSettingCard(SettingCard):
    """免 UAC 运行开关：开启前确认风险"""

    checkedChanged = Signal(bool)

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.switchButton.checkedChanged.connect(self.__onCheckedChanged)
        self.setValue(uac_free.is_enabled())

    def setValue(self, isChecked: bool):
        """同步开关显示状态（程序化同步不触发开启/关闭）"""
        self.switchButton.blockSignals(True)
        self.switchButton.setChecked(bool(isChecked))
        self.switchButton.setText(tr('开') if isChecked else tr('关'))
        self.switchButton.blockSignals(False)

    def confirmEnable(self) -> bool:
        """开启前用通俗的话说明变化与风险，用户确认后才开启"""
        confirm = MessageBox(
            tr("开启免 UAC 运行前请确认"),
            tr("开启后，AI 助手或脚本通过 m7a.exe 运行任务时，不会再弹出“你要允许此应用对你的设备进行更改吗？”的确认窗口。"
               "你不在电脑前时，也能让 AI 助手帮你远程运行任务。\n\n"
               "这个确认窗口原本是 Windows 的一道安全防线，开启前请了解：\n\n"
               "• 这台电脑上以你的账户运行的其他程序（包括 AI 助手执行的命令），也能借助小助手获得管理员权限，不再需要你点“是”。\n"
               "• 如果电脑中了病毒，或者有人冒用你的 AI 助手，造成的损害可能会更大。\n"
               "• 只对当前 Windows 账户和当前安装目录生效；更新小助手后不用重新开启，移动安装目录后需要重新开启。\n"
               "• 远程运行时，电脑需要保持开机、已登录并且没有锁屏。\n\n"
               "建议只在自己的电脑上、并且信任所用的 AI 助手时开启。不需要时，随时可以回到这里关闭。"),
            self.window()
        )
        confirm.yesButton.setText(tr("我已了解，继续开启"))
        confirm.cancelButton.setText(tr("取消"))
        return bool(confirm.exec())

    def __onCheckedChanged(self, isChecked: bool):
        if isChecked and not self.confirmEnable():
            self.setValue(False)
            return
        ok = uac_free.enable() if isChecked else uac_free.disable()
        if not ok:
            self.setValue(not isChecked)
            InfoBar.error(
                title=tr('免 UAC 运行设置失败'),
                content=tr('请确认小助手以管理员权限运行，并且没有被安全软件拦截'),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self.window()
            )
            return
        self.setValue(isChecked)
        self.checkedChanged.emit(isChecked)
        if isChecked:
            InfoBar.success(
                title=tr('免 UAC 运行已开启'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self.window()
            )
        else:
            InfoBar.info(
                title=tr('免 UAC 运行已关闭'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self.window()
            )
