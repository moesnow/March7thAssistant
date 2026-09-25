from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox

from app.card.pushsettingcard1 import PushSettingCardKey
from app.common.scroll_dialog import (SplitFadeDialogMixin, available_host_size,
                                      build_scroll_area)
from module.config import cfg
from module.localization import tr


class HotkeyInterface(SplitFadeDialogMixin, MessageBox):
    """ Hotkey configuration interface """

    def __init__(self, parent=None):
        configlist = {
            tr("秘技（只对清体力和逐光捡金场景生效）"): "hotkey_technique",
            tr("地图"): "hotkey_map",
            tr("跃迁"): "hotkey_warp",
            tr("自动战斗"): "hotkey_auto_battle",
            tr("停止任务（全局热键，支持后台）"): "hotkey_stop_task",
            tr("暂停/继续任务（全局热键，支持后台）"): "hotkey_pause_task",
            tr("自动对话（全局热键，支持后台）"): "hotkey_toggle_autoplot"
        }

        super().__init__(tr("按键设置"), "", parent)
        self.configlist = configlist
        self._scroll = None

        self.backup_config = {}
        for config in self.configlist.values():
            self.backup_config[config] = cfg.get_value(config)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText(tr('确认'))
        self.cancelButton.setText(tr('取消'))

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(10)
        self.textLayout.setSpacing(4)

        # 按键列表放进可滚动容器：弹窗高度以屏幕可用高度为上限，
        # 避免条目增多后超出屏幕、底部确认/取消按钮不可见
        list_container = QWidget(self)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(4)

        self.pushButton_dict = {}
        for name, config in self.configlist.items():
            if config == "hotkey_technique":
                icon = FIF.LEAF
            elif config == "hotkey_map":
                icon = FIF.LEAF
            elif config == "hotkey_warp":
                icon = FIF.LEAF
            elif config == "hotkey_auto_battle":
                icon = FIF.GAME
            elif config == "hotkey_pause_task":
                icon = FIF.PAUSE
            elif config == "hotkey_toggle_autoplot":
                icon = FIF.DEVELOPER_TOOLS
            else:
                icon = FIF.SETTING

            pushButton = PushSettingCardKey(
                tr('按住以修改'),
                icon,
                name,
                config,
            )
            pushButton.setFont(font)

            list_layout.addWidget(pushButton, 0, Qt.AlignmentFlag.AlignTop)
            self.pushButton_dict[config] = pushButton

        # 添加提示标签：交互 F / 角色详细 C 不允许修改
        hint_label = QLabel(tr("注意：交互（F）和角色详细（C）按键不允许修改，请保持游戏内默认设置。"))
        hint_font = QFont()
        hint_font.setPointSize(9)
        hint_label.setFont(hint_font)
        hint_label.setStyleSheet("color: gray;")
        hint_label.setWordWrap(True)
        list_layout.addWidget(hint_label, 0, Qt.AlignmentFlag.AlignTop)
        list_layout.addStretch(1)

        # 按键列表装进限高滚动区：弹窗必须装进父窗口（遮罩尺寸跟随父窗口而非屏幕），
        # 条目超出上限时列表内部滚动，保证确认/取消按钮始终可见可点。
        # 尺寸与背景处理的细节统一收在 app.common.scroll_dialog。
        host_width, host_height = available_host_size(parent)
        # 非列表部分的高度：文本布局上下边距 + 标题 + 间距 + 按钮区 + 余量
        chrome = (self.textLayout.contentsMargins().top()
                  + self.textLayout.contentsMargins().bottom()
                  + self.titleLabel.sizeHint().height()
                  + self.textLayout.spacing()
                  + self.buttonGroup.height()
                  + 24)
        scroll = build_scroll_area(list_container, host_width, host_height, chrome, min_height=240)
        self.textLayout.addWidget(scroll, 1)
        self._scroll = scroll

        self.yesButton.clicked.connect(self._onConfirmClicked)
        self.cancelButton.clicked.connect(self._onCancelClicked)

    def _onConfirmClicked(self):
        """ 确认按钮点击处理 - 保存配置 """
        self.accept()

    def _onCancelClicked(self):
        """ 取消按钮点击处理 - 恢复备份配置

        仅恢复真正被改动的项并一次性落盘：`save_config` 带 fsync，
        逐项 `set_value`（每项还会保存两次）会造成取消后弹窗迟迟不关闭。
        """
        restore = {}
        for config, value in self.backup_config.items():
            if cfg.get_value(config) != value:
                restore[config] = value
        if restore:
            cfg.set_values(restore)
        self.reject()
