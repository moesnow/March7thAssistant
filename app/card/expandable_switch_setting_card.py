# coding:utf-8
from typing import Union, List
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget
from qfluentwidgets import ExpandSettingCard, FluentIconBase, SwitchButton, IndicatorPosition, SettingCard


class ExpandableSwitchSettingCard(ExpandSettingCard):
    """ 可展开的开关设置卡片 - 通用实现

    这是一个通用的可展开开关卡片，可以包含任意子设置卡片。
    用户点击卡片可以展开/收起子选项，右侧的开关控制功能启用/禁用。
    """

    switchChanged = pyqtSignal(bool)
    expandStateChanged = pyqtSignal(bool)  # 新增信号：展开状态改变时发出，参数为是否展开

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, content: str = None, parent=None):
        """
        参数:
        - configname: 配置项名称
        - icon: 图标
        - title: 标题
        - content: 内容描述
        - parent: 父组件
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname

        # Switch button
        self.switchButton = SwitchButton(self.tr('关'), self, IndicatorPosition.RIGHT)

        # Add switch button to card layout using addWidget method
        self.card.addWidget(self.switchButton)

        # Import config here to avoid circular import
        from module.config import cfg
        self.cfg = cfg

        # Set initial value
        self.setValue(self.cfg.get_value(self.configname))

        # Connect signals
        self.switchButton.checkedChanged.connect(self.__onSwitchChanged)

    def __onSwitchChanged(self, isChecked: bool):
        """Switch button checked state changed slot"""
        self.setValue(isChecked)
        self.cfg.set_value(self.configname, isChecked)
        self.switchChanged.emit(isChecked)

    def setValue(self, isChecked: bool):
        """Set switch button state"""
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(self.tr('开') if isChecked else self.tr('关'))

    def getSwitchState(self) -> bool:
        """Get current switch state"""
        return self.switchButton.isChecked()

    def addSettingCard(self, card: SettingCard):
        """添加子设置卡片到可展开区域"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """批量添加子设置卡片到可展开区域"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def setExpand(self, isExpand: bool):
        """重写展开/收起方法，在动画前/后发送信号调整父容器高度"""
        is_expanding = not self.isExpand

        # 如果是展开操作，在动画前发送信号（需要提前扩大容器）
        if is_expanding:
            self.expandStateChanged.emit(True)

        # 调用父类方法执行动画
        super().setExpand(isExpand)

        # 如果是收起操作，在动画完成后发送信号（等动画播放完再缩小容器）
        if not is_expanding:
            # 连接动画完成信号
            self.expandAni.finished.connect(lambda: self._onCollapseFinished())

    def _onCollapseFinished(self):
        """收起动画完成后的回调"""
        # 断开信号，避免重复连接
        try:
            self.expandAni.finished.disconnect()
        except:
            pass
        # 发送收起信号
        self.expandStateChanged.emit(False)
