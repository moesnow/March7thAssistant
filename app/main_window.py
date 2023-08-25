from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QSize

from qfluentwidgets import NavigationItemPosition, FluentWindow, SplashScreen, setThemeColor, InfoBar, InfoBarPosition
from qfluentwidgets import FluentIcon as FIF

from .home_interface import HomeInterface
from .setting_interface import SettingInterface

from managers.config_manager import config
import requests
import json


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.initWindow()

        # create sub interface
        self.homeInterface = HomeInterface(self)
        self.settingInterface = SettingInterface(self)

        # import time
        # time.sleep(0.5)

        self.initNavigation()
        self.checkUpdate()
        self.splashScreen.finish()

    def checkUpdate(self):
        if not config.check_update:
            return

        try:
            url = "https://api.github.com/repos/moesnow/March7thAssistant/releases/latest"
            res = requests.get(url, timeout=3)
            if res.status_code != 200:
                return

            data = json.loads(res.text)
            version = data["tag_name"]
            if version > config.version:
                # if True:
                InfoBar.warning(
                    title=self.tr(f'发现新版本：{config.version}  ——>  {version}'),
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=-1,
                    parent=self.homeInterface
                )
            else:
                InfoBar.success(
                    title=self.tr('当前是最新版本'),
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self.homeInterface
                )
        except:
            InfoBar.warning(
                title=self.tr('检测更新失败'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self.homeInterface
            )

    def initNavigation(self):
        # add navigation items
        self.addSubInterface(self.homeInterface, FIF.HOME, self.tr('主页'))
        self.addSubInterface(self.settingInterface, FIF.SETTING, self.tr('设置'), NavigationItemPosition.BOTTOM)

    def initWindow(self):
        # 禁用最大化
        self.titleBar.maxBtn.setHidden(True)
        self.titleBar.maxBtn.setDisabled(True)
        self.titleBar.setDoubleClickEnabled(False)
        self.setResizeEnabled(False)
        # self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowMaximizeButtonHint)

        setThemeColor('#f18cb9')

        self.resize(960, 780)
        self.setWindowIcon(QIcon('assets\logo\March7th.ico'))
        self.setWindowTitle("March7th Assistant")

        # create splash screen
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(128, 128))
        self.splashScreen.raise_()

        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)
        self.show()
        QApplication.processEvents()
