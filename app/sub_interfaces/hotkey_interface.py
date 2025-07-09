from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox

from app.card.pushsettingcard1 import PushSettingCardKey
from module.config import cfg


class HotkeyInterface(MessageBox):
    """ Hotkey configuration interface """

    def __init__(self, parent=None):
        configlist = {
            "秘技（只对清体力和逐光捡金场景生效）": "hotkey_technique",
            "地图": "hotkey_map", 
            "跃迁": "hotkey_warp"
        }
        
        super().__init__("按键设置", "", parent)
        self.configlist = configlist
        
        self.backup_config = {}
        for config in self.configlist.values():
            self.backup_config[config] = cfg.get_value(config)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(10)
        self.textLayout.setSpacing(4)

        self.pushButton_dict = {}
        for name, config in self.configlist.items():
            if config == "hotkey_technique":
                icon = FIF.LEAF
            elif config == "hotkey_map":
                icon = FIF.LEAF
            elif config == "hotkey_warp":
                icon = FIF.LEAF
            else:
                icon = FIF.SETTING

            pushButton = PushSettingCardKey(
                '按住以修改',
                icon,
                name,
                config,
            )
            pushButton.setFont(font)

            self.textLayout.addWidget(pushButton, 0, Qt.AlignmentFlag.AlignTop)
            self.pushButton_dict[config] = pushButton

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
