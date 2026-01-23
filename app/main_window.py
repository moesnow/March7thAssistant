from PySide6.QtCore import Qt, QSize, QFileSystemWatcher, Signal, QObject
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from qfluentwidgets import NavigationItemPosition, MSFluentWindow, SplashScreen, setThemeColor, NavigationBarPushButton, setTheme, Theme
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, InfoBarPosition, SystemTrayMenu
from app.tools.game_starter import GameStartStatus, GameLaunchThread

from .home_interface import HomeInterface
from .help_interface import HelpInterface
# from .changelog_interface import ChangelogInterface
from .warp_interface import WarpInterface
from .tools_interface import ToolsInterface
from .setting_interface import SettingInterface
from .log_interface import LogInterface
from .common.signal_bus import signalBus

from .card.messagebox_custom import MessageBoxSupport
from .tools.check_update import checkUpdate
from .tools.check_theme_change import checkThemeChange
from .tools.announcement import checkAnnouncement
from .tools.disclaimer import disclaimer

from module.config import cfg
from module.logger import log
from module.game import get_game_controller
from module.localization import tr
import base64
import os
import sys


class ConfigWatcher(QObject):
    """配置文件监视器"""
    config_changed = Signal()

    def __init__(self, config_path, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.watcher = QFileSystemWatcher()
        self.debounce_timer = None

        # 监视配置
        if os.path.exists(self.config_path):
            self.watcher.addPath(self.config_path)
            self.watcher.fileChanged.connect(self._on_config_changed)

    def _on_config_changed(self, path):
        """检测到文件变化，延迟处理避免频繁触发"""
        from PySide6.QtCore import QTimer

        # 清除之前的定时器
        if self.debounce_timer:
            self.debounce_timer.stop()
            self.debounce_timer.deleteLater()

        # 创建新的定时器，延迟1秒处理（避免文件写入过程中多次触发）
        self.debounce_timer = QTimer()
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self._emit_change)
        self.debounce_timer.start(1000)

    def _emit_change(self):
        """检查文件是否真的改变，然后发送信号"""
        if os.path.exists(self.config_path) and cfg.is_config_changed():
            self.config_changed.emit()


class MainWindow(MSFluentWindow):
    def __init__(self, task=None, exit_on_complete=False):
        super().__init__()
        self.startup_task = task  # 保存启动时要执行的任务
        self.exit_on_complete = exit_on_complete  # 任务完成后是否退出

        self.initWindow()

        self.initInterface()
        self.initNavigation()
        self.initSystemTray()

        # 初始化配置文件监视器
        self.config_watcher = ConfigWatcher(os.path.abspath(cfg.config_path), self)
        self.config_watcher.config_changed.connect(self._on_config_file_changed)

        # 如果有启动任务，延迟执行
        if self.startup_task:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(1000, self._executeStartupTask)
        else:
            # 检查更新
            checkUpdate(self, flag=True)
            checkAnnouncement(self)

    def _executeStartupTask(self):
        """执行启动时指定的任务"""
        if self.startup_task:
            from tasks.base.tasks import start_task
            start_task(self.startup_task)

    def initWindow(self):
        # 开启 “在标题栏和窗口边框上显示强调色” 后，会导致窗口顶部出现异色横条 bug 已经修复
        # https://github.com/zhiyiYo/PyQt-Frameless-Window/pull/186
        # 要求 PySideSix-Frameless-Window>=0.7.0
        # self.setMicaEffectEnabled(False)

        setThemeColor('#f18cb9', lazy=True)
        setTheme(Theme.AUTO, lazy=True)

        # 禁用最大化
        # self.titleBar.maxBtn.setHidden(True)
        # self.titleBar.maxBtn.setDisabled(True)
        # self.titleBar.setDoubleClickEnabled(False)
        # self.setResizeEnabled(False)

        # self.setWindowFlags(Qt.WindowCloseButtonHint)
        # self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)

        # 设置最小尺寸
        min_width = 960
        min_height = 640
        self.setMinimumWidth(min_width)
        self.setMinimumHeight(min_height)

        # 从配置文件读取窗口尺寸，确保不低于最小值
        saved_width = cfg.get_value('window_width', min_width)
        saved_height = cfg.get_value('window_height', min_height)
        window_width = max(saved_width, min_width)
        window_height = max(saved_height, min_height)
        self.resize(window_width, window_height)

        self.setWindowIcon(QIcon('./assets/logo/March7th.ico'))
        self.setWindowTitle("March7th Assistant")

        # 创建启动画面
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(128, 128))
        self.splashScreen.titleBar.maxBtn.setHidden(True)
        self.splashScreen.raise_()

        screen = QApplication.primaryScreen().availableGeometry()
        w, h = screen.width(), screen.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        # 根据配置决定窗口显示方式
        if cfg.get_value('window_maximized', False):
            self.showMaximized()
        else:
            self.show()

        QApplication.processEvents()

    def initInterface(self):
        self.homeInterface = HomeInterface(self)
        self.helpInterface = HelpInterface(self)
        # self.changelogInterface = ChangelogInterface(self)
        self.warpInterface = WarpInterface(self)
        self.toolsInterface = ToolsInterface(self)
        self.logInterface = LogInterface(self)
        self.settingInterface = SettingInterface(self)

        # 连接任务启动信号
        signalBus.startTaskSignal.connect(self._onStartTask)
        # 连接热键配置改变信号
        signalBus.hotkeyChangedSignal.connect(self._onHotkeyChanged)
        # 连接 UI 语言改变信号（用于提示重启生效）
        signalBus.uiLanguageChanged.connect(self._on_ui_language_changed)
        # 连接任务完成信号
        self.logInterface.taskFinished.connect(self._onTaskFinished)

    def initNavigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, tr('主页'))
        self.addSubInterface(self.helpInterface, FIF.BOOK_SHELF, tr('帮助'))
        # self.addSubInterface(self.changelogInterface, FIF.UPDATE, '更新日志')
        self.addSubInterface(self.warpInterface, FIF.SHARE, tr('抽卡记录'))
        self.addSubInterface(self.toolsInterface, FIF.DEVELOPER_TOOLS, tr('工具箱'))

        self.navigationInterface.addWidget(
            'startGameButton',
            NavigationBarPushButton(FIF.PLAY, tr('启动游戏'), isSelectable=False),
            self.startGame,
            NavigationItemPosition.BOTTOM)

        self.addSubInterface(self.logInterface, FIF.COMMAND_PROMPT, tr('日志'), position=NavigationItemPosition.BOTTOM)

        # self.navigationInterface.addWidget(
        #     'refreshButton',
        #     NavigationBarPushButton(FIF.SYNC, '刷新', isSelectable=False),
        #     self._on_config_file_changed,
        #     NavigationItemPosition.BOTTOM)

        # self.navigationInterface.addWidget(
        #     'themeButton',
        #     NavigationBarPushButton(FIF.BRUSH, '主题', isSelectable=False),
        #     lambda: toggleTheme(lazy=True),
        #     NavigationItemPosition.BOTTOM)

        self.navigationInterface.addWidget(
            'avatar',
            NavigationBarPushButton(FIF.HEART, tr('赞赏'), isSelectable=False),
            lambda: MessageBoxSupport(
                tr('支持作者🥰'),
                tr('此程序为免费开源项目，如果你付了钱请立刻退款\n如果喜欢本项目，可以微信赞赏送作者一杯咖啡☕\n您的支持就是作者开发和维护项目的动力🚀'),
                './assets/app/images/sponsor.jpg',
                self
            ).exec(),
            NavigationItemPosition.BOTTOM
        )

        self.addSubInterface(self.settingInterface, FIF.SETTING, tr('设置'), position=NavigationItemPosition.BOTTOM)

        self.splashScreen.finish()
        self.themeListener = checkThemeChange(self)

        if not cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
            disclaimer(self)

    def initSystemTray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon('./assets/logo/March7th.ico'))
        self.tray_icon.setToolTip('March7th Assistant')

        # 创建托盘菜单
        tray_menu = SystemTrayMenu(parent=self)
        tray_menu.aboutToShow.connect(self._on_tray_menu_about_to_show)

        # 显示主界面
        show_action = QAction(tr('显示主界面'), self)
        show_action.triggered.connect(self._show_main_window)
        tray_menu.addAction(show_action)

        # 完整运行
        run_action = QAction(tr('完整运行'), self)
        run_action.triggered.connect(self.startFullTask)
        tray_menu.addAction(run_action)

        tray_menu.addSeparator()

        # 打开设置界面
        setting_action = QAction(tr('设置'), self)

        def _open_settings():
            try:
                self.showNormal()
                self.activateWindow()
                if hasattr(self, 'settingInterface'):
                    self.switchTo(self.settingInterface)
            except Exception:
                pass
        setting_action.triggered.connect(_open_settings)
        tray_menu.addAction(setting_action)

        # 退出程序
        quit_action = QAction(tr('退出'), self)
        quit_action.triggered.connect(self.quitApp)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        if sys.platform == 'win32':
            self.tray_icon.activated.connect(self.onTrayIconActivated)
        self.tray_icon.show()

    def _show_main_window(self):
        """显示主界面，macOS 下确保窗口置顶"""
        self.showNormal()
        try:
            if sys.platform == 'darwin':
                self.raise_()
                self.activateWindow()
                QApplication.setActiveWindow(self)
            else:
                self.activateWindow()
        except Exception:
            pass

    def onTrayIconActivated(self, reason):
        """托盘图标被激活时的处理"""
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def handle_external_activate(self, task=None, exit_on_complete=False):
        """响应来自其他实例的激活请求：置顶窗口并根据需要启动任务或设置退出行为"""
        from PySide6.QtCore import QTimer
        try:
            # 显示并置顶窗口
            self.showNormal()
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

        # 如果指定了任务，延迟执行以保证界面初始化完成
        if task:
            self.startup_task = task
            QTimer.singleShot(200, self._executeStartupTask)

        # 设置任务完成后是否退出的标志
        if exit_on_complete:
            self.exit_on_complete = exit_on_complete

    def _on_tray_menu_about_to_show(self):
        """托盘菜单即将显示时激活窗口，解决 Windows 上点击外部区域无法关闭菜单的问题"""
        self.activateWindow()

    def _onStartTask(self, command):
        """处理任务启动信号"""
        # 检查是否有任务正在运行
        if self.logInterface.isTaskRunning():
            InfoBar.warning(
                title=tr('任务正在运行'),
                content=tr("请先停止当前任务后再启动新任务"),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            # 切换到日志界面
            self.switchTo(self.logInterface)
            return
        # 切换到日志界面
        self.switchTo(self.logInterface)
        # 启动任务
        self.logInterface.startTask(command)

    def startFullTask(self):
        """启动完整运行任务"""
        from tasks.base.tasks import start_task
        start_task("main")

    def _onHotkeyChanged(self):
        """处理热键配置改变信号"""
        if hasattr(self, 'logInterface'):
            self.logInterface.updateHotkey()

    def _on_ui_language_changed(self, lang_code: str):
        """处理 UI 语言改变信号：显示需要重启的提示"""
        try:
            InfoBar.success(
                title=tr('更新成功'),
                content=tr('配置在重启软件后生效'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        except Exception:
            pass

    def _onTaskFinished(self, exit_code):
        """处理任务完成信号"""
        # 如果是启动任务且设置了完成后退出，则在任务成功完成时退出程序
        if self.exit_on_complete and self.startup_task and exit_code == 0:
            from PySide6.QtCore import QTimer
            # 延迟一小段时间让用户看到完成状态
            QTimer.singleShot(5000, self.quitApp)
        else:
            # 任务失败或未指定退出时，清除自动退出标记
            self.exit_on_complete = False

    def quitApp(self):
        """退出应用程序"""
        self._do_quit()

    def _saveWindowState(self):
        """保存窗口尺寸和最大化状态到配置文件"""
        try:
            is_maximized = self.isMaximized()
            cfg.set_value('window_maximized', is_maximized)

            # 只在非最大化状态下保存窗口尺寸
            if not is_maximized:
                cfg.set_value('window_width', self.width())
                cfg.set_value('window_height', self.height())
        except Exception:
            pass

    def _on_config_file_changed(self):
        """重新加载配置文件并刷新界面"""
        try:
            # 检查当前是否在设置界面
            is_in_setting_interface = self.stackedWidget.currentWidget() == self.settingInterface

            # 重新加载配置
            cfg._load_config(None, save=False)

            # 重新初始化通知器
            try:
                from module.notification import init_notifiers
                init_notifiers()
            except Exception:
                pass

            # 更新日志界面的热键
            if hasattr(self, 'logInterface'):
                self.logInterface.updateHotkey()

            # 保存旧的设置界面引用
            old_setting_interface = self.settingInterface
            route_key = old_setting_interface.objectName()

            # 创建新的设置界面
            self.settingInterface = SettingInterface(self)

            # 必须先把旧的导航栏隐藏，否则会导致最后的高度增加（bug）
            self.navigationInterface.items[route_key].hide()

            # 移除旧的设置界面
            self.removeInterface(old_setting_interface, isDelete=True)

            # 添加新的设置界面
            self.addSubInterface(self.settingInterface, FIF.SETTING, '设置', position=NavigationItemPosition.BOTTOM)

            # 只有在重新加载配置前是在设置界面时，才切换到新的设置界面
            if is_in_setting_interface:
                self.switchTo(self.settingInterface)

            # 只有在窗口可见时才显示提示
            if self.isVisible():
                InfoBar.success(
                    title=tr('配置已更新'),
                    content=tr("检测到配置文件变化，已自动重新加载"),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
        except Exception as e:
            # 只有在窗口可见时才显示提示
            if self.isVisible():
                InfoBar.warning(
                    title=tr('配置加载失败'),
                    content=str(e),
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

    def _stopThemeListener(self):
        """停止主题监听线程"""
        if hasattr(self, 'themeListener') and self.themeListener:
            self.themeListener.stop()
            self.themeListener = None

    def _stopRunningTask(self):
        """停止正在运行的任务"""
        if hasattr(self, 'logInterface') and self.logInterface.isTaskRunning():
            self.logInterface.stopTask()
            # 等待进程结束
            if self.logInterface.process:
                self.logInterface.process.waitForFinished(3000)
                # 如果还没结束，强制结束
                if self.logInterface.process.state() != 0:  # QProcess.NotRunning
                    self.logInterface.process.kill()
                    self.logInterface.process.waitForFinished(1000)

    def _do_quit(self, e=None):
        """执行退出前的清理并退出程序
        e: 可选的 QCloseEvent，用于调用 e.accept()
        """
        # 保存窗口尺寸和最大化状态
        self._saveWindowState()

        try:
            self.hide()
            self.tray_icon.hide()
            QApplication.processEvents()
        except Exception:
            pass

        # 停止运行任务和主题监听
        self._stopRunningTask()
        self._stopThemeListener()

        # 可选地清理日志界面资源
        if hasattr(self, 'logInterface'):
            try:
                self.logInterface.cleanup()
            except Exception:
                pass

        # 如果传入了事件，接受它
        if e is not None:
            try:
                e.accept()
            except Exception:
                pass

        QApplication.quit()

    def closeEvent(self, e):
        """关闭窗口时根据配置执行对应操作"""
        from .card.messagebox_custom import MessageBoxCloseWindow

        close_action = cfg.get_value('close_window_action', 'ask')

        if close_action == 'ask':
            # 弹出询问对话框
            dialog = MessageBoxCloseWindow(self)
            dialog.exec()

            if dialog.action == 'minimize':
                # 最小化到托盘
                e.ignore()
                self.hide()
                self.tray_icon.showMessage(
                    'March7th Assistant',
                    tr('程序已最小化到托盘'),
                    QSystemTrayIcon.Information,
                    2000
                )
                # 若用户选择记住，则刷新设置界面以同步显示
                try:
                    if dialog.rememberCheckBox.isChecked():
                        self._on_config_file_changed()
                except Exception:
                    pass
            elif dialog.action == 'close':
                # 关闭程序
                self._do_quit(e)
            else:
                # 用户取消操作（例如点击了 X 按钮）
                e.ignore()
        elif close_action == 'minimize':
            # 直接最小化到托盘
            e.ignore()
            self.hide()
            # self.tray_icon.showMessage(
            #     'March7th Assistant',
            #     '程序已最小化到托盘',
            #     QSystemTrayIcon.Information,
            #     2000
            # )
        elif close_action == 'close':
            # 直接关闭程序
            self._do_quit(e)
        else:
            # 默认行为：最小化到托盘
            e.ignore()
            self.hide()
            self.tray_icon.showMessage(
                'March7th Assistant',
                tr('程序已最小化到托盘'),
                QSystemTrayIcon.Information,
                2000
            )

    def startGame(self):
        start_game_button = self.navigationInterface.widget('startGameButton')
        if start_game_button:
            start_game_button.setEnabled(False)
        game = get_game_controller()
        if cfg.cloud_game_enable and cfg.browser_type == "integrated" and not game.is_integrated_browser_downloaded():
            InfoBar.warning(
                title=tr('正在下载内置浏览器(ง •̀_•́)ง'),
                content=tr("下载成功后，将自动启动云·星穹铁道"),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=10000,
                parent=self
            )
        elif cfg.cloud_game_enable:
            InfoBar.warning(
                title=tr('正在启动游戏(❁´◡`❁)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        else:
            from tasks.game.starrailcontroller import StarRailController
            starrail = StarRailController(cfg=cfg, logger=log)
            if cfg.auto_battle_detect_enable:
                starrail.change_auto_battle(True)

        self.game_launch_thread = GameLaunchThread(game, cfg)
        self.game_launch_thread.finished_signal.connect(self.on_game_launched)
        self.game_launch_thread.start()

    def on_game_launched(self, result):
        if result == GameStartStatus.SUCCESS:
            InfoBar.success(
                title=tr('启动成功(＾∀＾●)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
        elif result == GameStartStatus.BROWSER_DOWNLOAD_FAIL:
            InfoBar.warning(
                title=tr('浏览器或驱动下载失败 (╥╯﹏╰╥)'),
                content=tr("请检查网络连接是否正常"),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        elif result == GameStartStatus.BROWSER_LAUNCH_FAIL:
            InfoBar.warning(
                title=tr('云游戏启动失败(╥╯﹏╰╥)'),
                content=tr("请检查所选浏览器是否存在，网络连接是否正常"),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        elif result == GameStartStatus.LOCAL_LAUNCH_FAIL:
            InfoBar.warning(
                title=tr('游戏路径配置错误(╥╯﹏╰╥)'),
                content=tr("请在“设置”-->“程序”中配置"),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        else:
            InfoBar.warning(
                title=tr('启动失败'),
                content=str(self.game_launch_thread.error_msg),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
        start_game_button = self.navigationInterface.widget('startGameButton')
        if start_game_button:
            start_game_button.setEnabled(True)
