from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabBar, QInputDialog
from PySide6.QtWidgets import QFrame
from qfluentwidgets import FluentStyleSheet
from qfluentwidgets import FluentIcon as FIF
from app.card.pushsettingcard1 import PushSettingCard
from app.card.switchsettingcard1 import SwitchSettingCard1
from module.config import cfg


class PushToolsBox(QWidget):
    def __init__(self, parent: QWidget | None = ..., flags: Qt.WindowFlags | Qt.WindowType = ...):
        super().__init__(parent=parent)
        self.windowPushCard = WindowsPushCard(parent=self)
        self.telegramPushCard = TelegramPushCard(parent=self)
        self.smtpPushCard = SmtpPushCard(parent=self)
        self.pushCars = [self.windowPushCard, self.telegramPushCard, self.smtpPushCard]
        style_sheet = """
            QTabBar::tab {
                background-color: #0078d4;
                color: white;
                padding: 8px 20px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #0078d4;
            }
            QTabBar::tab:!selected {
                margin-top: 2px;
            }
            QTabBar::tab:first:selected {
                margin-left: 0;
            }
            QTabBar::tab:last:selected {
                margin-right: 0;
            }
        """
        self.tabBar = QTabBar(parent=self)
        self.tabBar.setStyleSheet(style_sheet)
        FluentStyleSheet.TAB_VIEW.apply(self.tabBar)
        self.tabBar.addTab('Windows')
        self.tabBar.addTab('Telegram')
        self.tabBar.addTab('Smtp')
        self.vLayout = QVBoxLayout()
        self.vLayout.addWidget(self.tabBar)
        for card in self.pushCars:
            self.vLayout.addWidget(card)
            card.hide()
        self.windowPushCard.show()
        _self = self

        def currentChanged(self):
            for card in _self.pushCars:
                if (card.isVisible()):
                    hCard = card
            idx = _self.tabBar.currentIndex()
            _self.pushCars[idx].show()
            hCard.hide()
            _self.adjustSize()
            _self.parent().adjustSize()
        self.tabBar.currentChanged.connect(currentChanged)
        self.setLayout(self.vLayout)
        self.adjustSize()


class WindowsPushCard(QWidget):
    def __init__(self, parent: QWidget | None = ..., flags: Qt.WindowFlags | Qt.WindowType = ...):
        super().__init__(parent=parent)
        self.winotifyEnableCard = SwitchSettingCard1(
            FIF.BACK_TO_WINDOW,
            '启用 Windows 通知',
            None,
            "notify_winotify_enable"
        )
        self.vLayout = QVBoxLayout()
        self.vLayout.addWidget(self.winotifyEnableCard)
        self.setLayout(self.vLayout)


class TelegramPushCard(QWidget):
    def __init__(self, parent: QWidget | None = ..., flags: Qt.WindowFlags | Qt.WindowType = ...):
        super().__init__(parent=parent)
        self.winotifyEnableCard = SwitchSettingCard1(
            FIF.BACK_TO_WINDOW,
            '启用 Telegram 通知',
            None,
            "notify_telegram_enable"
        )
        self.telegramTokenCard = PushSettingCard(
            '修改',
            FIF.GAME,
            "Telegram Token",
            "notify_telegram_token",
            cfg.notify_telegram_token,
            self,
        )
        self.telegramTokenCard.clicked.connect(self.inputToken)
        self.vLayout = QVBoxLayout()
        self.vLayout.addWidget(self.winotifyEnableCard)
        self.vLayout.addWidget(self.telegramTokenCard)
        self.setLayout(self.vLayout)

    def inputToken(self):
        token = QInputDialog.getText(self, "输入 Telegram Token", "Token")
        if not token is None:
            cfg.set_value("notify_telegram_token", token)
            self.telegramTokenCard.setContent(token)


class SmtpPushCard(QFrame):
    def __init__(self, parent: QWidget | None = ..., flags: Qt.WindowFlags | Qt.WindowType = ...):
        super().__init__(parent=parent)
        self.winotifyEnableCard = SwitchSettingCard1(
            FIF.BACK_TO_WINDOW,
            '启用 Smtp 通知',
            None,
            "notify_smtp_enable"
        )
        self.vLayout = QVBoxLayout()
        self.vLayout.addWidget(self.winotifyEnableCard)
        self.setLayout(self.vLayout)
