from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox

from app.card.pushsettingcard1 import PushSettingCardKey
from module.config import cfg
from module.localization import tr


class HotkeyInterface(MessageBox):
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

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(list_container)
        # 为标题、布局边距与按钮区（81px）预留空间，保证整个弹窗在屏幕内完整可见
        screen_height = QApplication.primaryScreen().availableGeometry().height()
        scroll.setMaximumHeight(max(240, screen_height - 320))
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")
        self.textLayout.addWidget(scroll, 1)

        self.yesButton.clicked.connect(self._onConfirmClicked)
        self.cancelButton.clicked.connect(self._onCancelClicked)

    def _onConfirmClicked(self):
        """ 确认按钮点击处理 - 保存配置 """
        self.accept()

    def _onCancelClicked(self):
        """ 取消按钮点击处理 - 恢复备份配置 """
        for config, value in self.backup_config.items():
            cfg.set_value(config, value)

        self.reject()
