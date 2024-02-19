from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

from contextlib import redirect_stdout
with redirect_stdout(None):
    from qfluentwidgets import NavigationItemPosition, MSFluentWindow, SplashScreen, setThemeColor, NavigationBarPushButton, toggleTheme, setTheme, Theme
    from qfluentwidgets import FluentIcon as FIF
    from qfluentwidgets import InfoBar, InfoBarPosition

from .home_interface import HomeInterface
from .setting_interface import SettingInterface
from .tasks_interface import TasksInterface
from .changelog_interface import ChangelogInterface
from .tools_interface import ToolsInterface
from .faq_interface import FAQInterface
from .tutorial_interface import TutorialInterface

from .card.messagebox_custom import MessageBoxSupport
from .tools.check_update import checkUpdate
from .tools.disclaimer import disclaimer

from managers.config_manager import config
import subprocess


class MainWindow(MSFluentWindow):
    def __init__(self):
        super().__init__()
        self.initWindow()

        # create sub interface
        self.homeInterface = HomeInterface(self)
        self.tasksInterface = TasksInterface(self)
        self.settingInterface = SettingInterface(self)
        self.faqInterface = FAQInterface(self)
        self.tutorialInterface = TutorialInterface(self)
        self.changelogInterface = ChangelogInterface(self)
        self.toolsInterface = ToolsInterface(self)

        self.initNavigation()
        self.splashScreen.finish()

        # 免责申明
        if not config.agreed_to_disclaimer:
            disclaimer(self)

        # 检查更新
        checkUpdate(self, flag=True)

    def initWindow(self):
        setThemeColor('#f18cb9')
        setTheme(Theme.AUTO, lazy=True)
        self.setMicaEffectEnabled(False)

        # 禁用最大化
        self.titleBar.maxBtn.setHidden(True)
        self.titleBar.maxBtn.setDisabled(True)
        self.titleBar.setDoubleClickEnabled(False)
        self.setResizeEnabled(False)
        self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)

        self.resize(960, 750)
        self.setWindowIcon(QIcon('./assets/logo/March7th.ico'))
        self.setWindowTitle("March7th Assistant")

        # 创建启动画面
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(128, 128))
        self.splashScreen.raise_()

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        self.show()
        QApplication.processEvents()

    def initNavigation(self):
        # add navigation items
        self.addSubInterface(self.homeInterface, FIF.HOME, self.tr('主页'))
        self.addSubInterface(self.tasksInterface, FIF.LABEL, self.tr('每日实训'))
        self.addSubInterface(self.tutorialInterface, FIF.BOOK_SHELF, self.tr('使用教程'))
        self.addSubInterface(self.faqInterface, FIF.CHAT, self.tr('常见问题'))
        self.addSubInterface(self.changelogInterface, FIF.UPDATE, self.tr('更新日志'))
        self.addSubInterface(self.toolsInterface, FIF.DEVELOPER_TOOLS, self.tr('工具箱'))

        self.navigationInterface.addWidget(
            'startGameButton',
            NavigationBarPushButton(FIF.PLAY, '启动游戏', isSelectable=False),
            self.startGame,
            NavigationItemPosition.BOTTOM)

        self.navigationInterface.addWidget(
            'themeButton',
            NavigationBarPushButton(FIF.BRUSH, '主题', isSelectable=False),
            self.toggleTheme,
            NavigationItemPosition.BOTTOM)

        self.navigationInterface.addWidget(
            'avatar',
            NavigationBarPushButton(FIF.HEART, '赞赏', isSelectable=False),
            self.onSupport,
            NavigationItemPosition.BOTTOM
        )

        self.addSubInterface(self.settingInterface, FIF.SETTING, self.tr('设置'), position=NavigationItemPosition.BOTTOM)

    def startGame(self):
        try:
            subprocess.Popen(config.game_path, creationflags=subprocess.DETACHED_PROCESS)
            InfoBar.success(
                title=self.tr('启动成功(＾∀＾●)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        except Exception:
            InfoBar.warning(
                title=self.tr('启动失败(╥╯﹏╰╥)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def toggleTheme(self):
        toggleTheme(lazy=True)

    def onSupport(self):
        MessageBoxSupport(
            '支持作者🥰',
            '此程序为免费开源项目，如果你付了钱请立刻退款\n如果喜欢本项目，可以微信赞赏送作者一杯咖啡☕\n您的支持就是作者开发和维护项目的动力🚀',
            './assets/app/images/sponsor.jpg',
            self
        ).exec()
