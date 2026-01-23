# coding:utf-8
from typing import Union, List
from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from qfluentwidgets import ExpandSettingCard, FluentIconBase, SwitchButton, IndicatorPosition, SettingCard, ComboBox, PrimaryPushButton
from module.localization import tr


class ExpandableSwitchSettingCard(ExpandSettingCard):
    """ 可展开的开关设置卡片 - 通用实现

    这是一个通用的可展开开关卡片，可以包含任意子设置卡片。
    用户点击卡片可以展开/收起子选项，右侧的开关控制功能启用/禁用。
    """

    switchChanged = Signal(bool)
    expandStateChanged = Signal(bool)  # 新增信号：展开状态改变时发出，参数为是否展开

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
        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)

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
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

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


class ExpandablePushSettingCard(ExpandSettingCard):
    """可展开的按钮设置卡片 - 用于测试通知等操作"""

    expandStateChanged = Signal(bool)
    clicked = Signal()

    def __init__(self, title: str, icon: Union[str, QIcon, FluentIconBase],
                 content: str = None, button_text: str = "Click", parent=None):
        """
        参数:
        - title: 标题
        - icon: 图标
        - content: 内容描述
        - button_text: 按钮文字
        - parent: 父组件
        """
        super().__init__(icon, title, content, parent)

        # Push button
        self.pushButton = PrimaryPushButton(button_text, self)
        self.card.addWidget(self.pushButton)

        # Connect signals
        self.pushButton.clicked.connect(self.clicked.emit)

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


class ExpandableComboBoxSettingCard(ExpandSettingCard):
    """可展开的下拉菜单设置卡片 - 通用实现"""

    expandStateChanged = Signal(bool)
    currentIndexChanged = Signal(int)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, content: str = None, texts: dict = None, parent=None):
        """
        参数:
        - configname: 配置项名称
        - icon: 图标
        - title: 标题
        - content: 内容描述
        - texts: 下拉菜单选项 {'显示名': '值'}
        - parent: 父组件
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname

        # ComboBox
        self.comboBox = ComboBox(self)
        self.card.addWidget(self.comboBox)

        # Import config here to avoid circular import
        from module.config import cfg
        self.cfg = cfg

        # Set combo box items
        if texts:
            for key, value in texts.items():
                self.comboBox.addItem(key, userData=value)
                if value == self.cfg.get_value(configname):
                    self.comboBox.setCurrentText(key)

        # Connect signals
        self.comboBox.currentIndexChanged.connect(self.__onComboBoxChanged)

    def __onComboBoxChanged(self, index: int):
        """ComboBox changed slot"""
        self.cfg.set_value(self.configname, self.comboBox.itemData(index))
        self.currentIndexChanged.emit(index)

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


class ExpandableComboBoxSettingCardUpdateSource(ExpandSettingCard):
    """可展开的下拉菜单设置卡片 - 用于更新源选择"""

    expandStateChanged = Signal(bool)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, update_callback, content: str = None, texts: dict = None, parent=None):
        """
        参数:
        - configname: 配置项名称
        - icon: 图标
        - title: 标题
        - update_callback: 更新回调函数
        - content: 内容描述
        - texts: 下拉菜单选项 {'显示名': '值'}
        - parent: 父组件
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname
        self.update_callback = update_callback

        # ComboBox
        self.comboBox = ComboBox(self)
        self.card.addWidget(self.comboBox)

        # Import config here to avoid circular import
        from module.config import cfg
        from app.tools.check_update import checkUpdate
        self.cfg = cfg
        self.checkUpdate = checkUpdate

        # Set combo box items
        if texts:
            for key, value in texts.items():
                self.comboBox.addItem(key, userData=value)
                if value == self.cfg.get_value(configname):
                    self.comboBox.setCurrentText(key)

        # Connect signals
        self.comboBox.currentIndexChanged.connect(self.__onComboBoxChanged)

    def __onComboBoxChanged(self, index: int):
        """ComboBox changed slot"""
        self.cfg.set_value(self.configname, self.comboBox.itemData(index))
        self.checkUpdate(self.update_callback)

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

    def addSettingCard(self, card: SettingCard):
        """添加子设置卡片到可展开区域"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """批量添加子设置卡片到可展开区域"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()


class ExpandableComboBoxSettingCard1(ExpandSettingCard):
    """可展开的下拉菜单设置卡片 - 用于 ComboBoxSettingCard1 类型"""

    expandStateChanged = Signal(bool)
    currentIndexChanged = Signal(int)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, content: str = None, texts: list = None, parent=None):
        """
        参数:
        - configname: 配置项名称
        - icon: 图标
        - title: 标题
        - content: 内容描述
        - texts: 下拉菜单选项列表
        - parent: 父组件
        """
        super().__init__(icon, title, content, parent)
        self.configname = configname

        # ComboBox
        self.comboBox = ComboBox(self)
        self.card.addWidget(self.comboBox)

        # Import config here to avoid circular import
        from module.config import cfg
        self.cfg = cfg

        # Set combo box items
        if texts:
            if isinstance(texts, list):
                # 如果是列表，直接添加
                for item in texts:
                    self.comboBox.addItem(item)
                # 尝试从配置中设置当前项
                current_value = self.cfg.get_value(configname)
                if current_value and current_value in texts:
                    self.comboBox.setCurrentText(current_value)
            else:
                # 如果是字典，按照字典方式处理
                for key, value in texts.items():
                    self.comboBox.addItem(key, userData=value)
                    if value == self.cfg.get_value(configname):
                        self.comboBox.setCurrentText(key)

        # Connect signals
        self.comboBox.currentIndexChanged.connect(self.__onComboBoxChanged)

    def __onComboBoxChanged(self, index: int):
        """ComboBox changed slot"""
        self.cfg.set_value(self.configname, self.comboBox.currentText())
        self.currentIndexChanged.emit(index)

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

    def addSettingCard(self, card: SettingCard):
        """添加子设置卡片到可展开区域"""
        self.viewLayout.addWidget(card)
        self._adjustViewSize()

    def addSettingCards(self, cards: List[SettingCard]):
        """批量添加子设置卡片到可展开区域"""
        for card in cards:
            self.viewLayout.addWidget(card)
        self._adjustViewSize()


class ExpandableSwitchSettingCardEchoofwar(ExpandSettingCard):
    """可展开的历战余响开关设置卡片，带周几开始执行的下拉框"""

    switchChanged = Signal(bool)
    expandStateChanged = Signal(bool)
    currentIndexChanged = Signal(int)

    def __init__(self, configname: str, icon: Union[str, QIcon, FluentIconBase],
                 title: str, content: str = None, parent=None):
        super().__init__(icon, title, content, parent)
        self.configname = configname

        # 下拉框：选择从周几开始执行历战余响
        self.comboBox = ComboBox(self)
        self.card.addWidget(self.comboBox)

        # 配置读取
        from module.config import cfg
        self.cfg = cfg

        texts = [tr('周一'), tr('周二'), tr('周三'), tr('周四'), tr('周五'), tr('周六'), tr('周日')]
        options = [1, 2, 3, 4, 5, 6, 7]
        for text, option in zip(texts, options):
            self.comboBox.addItem(text, userData=option)

        # 安全设置当前值，默认回退到第一项
        current_day = self.cfg.get_value("echo_of_war_start_day_of_week")
        if isinstance(current_day, int) and 1 <= current_day <= 7:
            self.comboBox.setCurrentText(texts[current_day - 1])
        else:
            self.comboBox.setCurrentText(texts[0])

        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

        # 开关按钮
        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)
        self.card.addWidget(self.switchButton)

        self.setValue(self.cfg.get_value(self.configname))
        self.switchButton.checkedChanged.connect(self.__onSwitchChanged)

    def __onSwitchChanged(self, isChecked: bool):
        """开关状态改变槽函数"""
        self.setValue(isChecked)
        self.cfg.set_value(self.configname, isChecked)
        self.switchChanged.emit(isChecked)

    def setValue(self, isChecked: bool):
        """设置开关状态"""
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _onCurrentIndexChanged(self, index: int):
        self.cfg.set_value("echo_of_war_start_day_of_week", self.comboBox.itemData(index))
        self.currentIndexChanged.emit(index)

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

        if is_expanding:
            self.expandStateChanged.emit(True)

        super().setExpand(isExpand)

        if not is_expanding:
            self.expandAni.finished.connect(lambda: self._onCollapseFinished())

    def _onCollapseFinished(self):
        """收起动画完成后的回调"""
        try:
            self.expandAni.finished.disconnect()
        except Exception:
            pass
        self.expandStateChanged.emit(False)
