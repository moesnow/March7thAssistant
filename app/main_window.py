from utils.game_options import game_option_enabled
from PySide6.QtCore import Qt, QSize, QPoint, QFileSystemWatcher, Signal, QObject, QTimer, QThread, QSignalBlocker
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QLabel

from qfluentwidgets import NavigationItemPosition, MSFluentWindow, SplashScreen, setThemeColor, NavigationBarPushButton, setTheme, Theme, themeColor, qconfig
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, InfoBarPosition, SystemTrayMenu
from app.tools.game_starter import GameStartStatus, GameLaunchThread

from .home_interface import HomeInterface
from .help_interface import HelpInterface
# from .changelog_interface import ChangelogInterface
from .warp_interface import WarpInterface
from .tools_interface import ToolsInterface
from .workflow_interface import WorkflowInterface
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

        log.debug(f"[config-watch] 文件变化事件: {path}")

        # 配置保存采用临时文件原子替换，替换后旧的监视句柄可能失效，需要重新挂载
        try:
            if os.path.exists(self.config_path) and self.config_path not in self.watcher.files():
                self.watcher.addPath(self.config_path)
                log.debug("[config-watch] 监视句柄失效，已重新挂载")
        except Exception:
            pass

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
        exists = os.path.exists(self.config_path)
        if exists and cfg.is_config_changed():
            log.info("[config-watch] 检测到配置文件被外部修改，准备重载界面")
            self.config_changed.emit()
        else:
            log.debug(f"[config-watch] 无需重载: exists={exists}")


class ClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return

        super().mousePressEvent(event)


class MainWindow(MSFluentWindow):
    TASK_EXIT_DELAY_MS = 5000

    def __init__(self, task=None, exit_on_complete=False, start_minimized_to_tray=False):
        super().__init__()
        self._pending_ui_language = None
        self._navigation_animation_running = False
        self.stackedWidget.view.aniStart.connect(lambda: setattr(self, '_navigation_animation_running', True))
        self.stackedWidget.view.aniFinished.connect(lambda: setattr(self, '_navigation_animation_running', False))
        self._language_change_timer = QTimer(self)
        self._language_change_timer.setSingleShot(True)
        self._language_change_timer.timeout.connect(self._rebuild_interfaces_for_language)
        self._config_reload_timer = QTimer(self)
        self._config_reload_timer.setSingleShot(True)
        self._config_reload_timer.timeout.connect(self._on_config_file_changed)
        self.startup_task = task  # 保存启动时要执行的任务
        self.exit_on_complete = exit_on_complete  # 命令行指定的单次退出请求
        self._task_exit_pending = False
        self._task_exit_requested_by_cli = False
        self._task_exit_timer = QTimer(self)
        self._task_exit_timer.setSingleShot(True)
        self._task_exit_timer.timeout.connect(self._quitAfterTask)
        self.start_minimized_to_tray = start_minimized_to_tray
        self._defer_startup_checks = False  # 静默启动时推迟的启动检查（检查更新/公告）
        self.detected_update_version = None
        self.updateVersionBadge = None
        qconfig.themeChanged.connect(self._on_theme_changed)

        self.initWindow()

        self.initInterface()
        self.initNavigation()
        self.initSystemTray()

        if self.start_minimized_to_tray:
            self.hide()

        # 初始化配置文件监视器
        self.config_watcher = ConfigWatcher(os.path.abspath(cfg.config_path), self)
        self.config_watcher.config_changed.connect(self._on_config_file_changed)

        # 如果有启动任务，延迟执行
        if self.startup_task:
            QTimer.singleShot(1000, self._executeStartupTask)
        elif self.start_minimized_to_tray:
            # 最小化到托盘启动：不弹出任何窗口，检查更新与公告推迟到主窗口首次显示
            self._defer_startup_checks = True
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

        window_memory = cfg.get_value('window_memory', 'size')
        # 从配置文件读取窗口尺寸，确保不低于最小值
        if window_memory in ('size', 'size_and_position'):
            saved_width = cfg.get_value('window_width', min_width)
            saved_height = cfg.get_value('window_height', min_height)
            window_width = max(saved_width, min_width)
            window_height = max(saved_height, min_height)
            self.resize(window_width, window_height)
        else:
            self.resize(min_width, min_height)

        self.setWindowIcon(QIcon('./assets/logo/March7th.ico'))
        self.setWindowTitle("March7th Assistant")
        # 分离系统窗口标题与应用内标题栏文本
        self._refreshWindowTitleBar()

        # 创建启动画面
        self.splashScreen = SplashScreen(self.windowIcon(), self)
        self.splashScreen.setIconSize(QSize(128, 128))
        self.splashScreen.titleBar.maxBtn.setHidden(True)
        self.splashScreen.raise_()

        primary_screen = QApplication.primaryScreen().availableGeometry()
        w, h = primary_screen.width(), primary_screen.height()

        saved_x = cfg.get_value('window_x', None)
        saved_y = cfg.get_value('window_y', None)

        if window_memory in ('position', 'size_and_position') and saved_x is not None and saved_y is not None:
            # 尝试找到保存位置所在的屏幕，找不到则回退到主屏幕
            target_screen = QApplication.screenAt(QPoint(int(saved_x), int(saved_y)))
            screen = target_screen.availableGeometry() if target_screen else primary_screen
            max_x = max(screen.left(), screen.right() - self.width())
            max_y = max(screen.top(), screen.bottom() - self.height())
            restored_x = max(screen.left(), min(int(saved_x), max_x))
            restored_y = max(screen.top(), min(int(saved_y), max_y))
            self.move(restored_x, restored_y)
        else:
            self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        # 记录期望的窗口几何（尺寸与位置）
        target_geometry = self.geometry()

        # 根据配置决定窗口显示方式
        if self.start_minimized_to_tray:
            # 最小化到托盘启动：不显示主窗口与启动画面（SplashScreen 是主窗口子控件，随父窗口隐藏），直接进托盘
            self.hide()
        elif window_memory in ('size', 'size_and_position') and cfg.get_value('window_maximized', False):
            self.showMaximized()
        else:
            self.show()

        QApplication.processEvents()

        if self.start_minimized_to_tray:
            # 托盘启动跳过了 show() 的几何同步：构造期堆积的窗口几何事件会在 processEvents 中被处理，
            # 把窗口尺寸打回原生默认值（500x500），导致从托盘恢复后窗口异常变小，需重新应用一次几何
            self.setGeometry(target_geometry)

    def _baseTitleBarText(self):
        return f"March7th Assistant {cfg.version}"

    def _ensureUpdateVersionBadge(self):
        if self.updateVersionBadge is not None:
            return self.updateVersionBadge

        if not hasattr(self, 'titleBar') or not hasattr(self.titleBar, 'hBoxLayout'):
            return None

        badge = ClickableLabel(self.titleBar)
        badge.hide()
        badge.setStyleSheet(f"color: {themeColor().name()}; font-weight: 700;")
        badge.setCursor(Qt.CursorShape.PointingHandCursor)
        badge.clicked.connect(self._on_update_version_badge_clicked)
        try:
            self.titleBar.hBoxLayout.insertWidget(4, badge, 0, Qt.AlignmentFlag.AlignVCenter)
        except Exception:
            self.titleBar.hBoxLayout.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.updateVersionBadge = badge
        return badge

    def _refreshWindowTitleBar(self):
        if hasattr(self, 'titleBar') and hasattr(self.titleBar, 'setTitle'):
            self.titleBar.setTitle(self._baseTitleBarText())

        badge = self._ensureUpdateVersionBadge()
        if badge is None:
            return

        badge.setStyleSheet(f"color: {themeColor().name()}; font-weight: 700;")
        if self.detected_update_version:
            badge.setText(tr('检测到新版本：{version}').format(version=self.detected_update_version))
            badge.show()
        else:
            badge.hide()

    def setDetectedUpdateVersion(self, version: str | None):
        self.detected_update_version = version or None
        self._refreshWindowTitleBar()
        if hasattr(self, 'logInterface') and self.logInterface:
            try:
                self.logInterface.setDetectedUpdateVersion(self.detected_update_version)
            except Exception:
                pass

    def _on_theme_changed(self):
        self._refreshWindowTitleBar()

    def _on_update_version_badge_clicked(self):
        if self.detected_update_version:
            checkUpdate(self)

    def initInterface(self):
        self.homeInterface = HomeInterface(self)
        self.helpInterface = HelpInterface(self)
        # self.changelogInterface = ChangelogInterface(self)
        self.warpInterface = WarpInterface(self)
        self.toolsInterface = ToolsInterface(self)
        self.workflowInterface = WorkflowInterface(self)
        self.logInterface = LogInterface(self)
        self.settingInterface = SettingInterface(self)

        # 连接任务启动信号
        signalBus.startTaskSignal.connect(self._onStartTask)
        # 连接热键配置改变信号
        signalBus.hotkeyChangedSignal.connect(self._onHotkeyChanged)
        # 连接 UI 语言改变信号
        signalBus.uiLanguageChanged.connect(self._on_ui_language_changed)
        # 连接任务完成信号
        self.logInterface.taskSequenceFinished.connect(self._onTaskFinished)
        self.logInterface.taskStarted.connect(self._cancelTaskExit)
        # 连接自动对话切换信号
        self.logInterface.autoplotToggleRequested.connect(self._onAutoplotToggleRequested)

    def initNavigation(self):
        self.addSubInterface(self.homeInterface, FIF.HOME, tr('主页'))
        self.addSubInterface(self.helpInterface, FIF.BOOK_SHELF, tr('帮助'))
        # self.addSubInterface(self.changelogInterface, FIF.UPDATE, '更新日志')
        self.addSubInterface(self.warpInterface, FIF.SHARE, tr('抽卡记录'))
        self.addSubInterface(self.toolsInterface, FIF.DEVELOPER_TOOLS, tr('工具箱'))
        self.addSubInterface(self.workflowInterface, FIF.CODE, tr('流程编排'))

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

        # 回调每次读取当前实例，替换设置页时不删除导航项或污染导航历史。
        self.settingInterface.setProperty('isStackedTransparent', False)
        self.stackedWidget.addWidget(self.settingInterface)
        self.navigationInterface.addItem(
            routeKey=self.settingInterface.objectName(), icon=FIF.SETTING, text=tr('设置'),
            onClick=lambda: self.switchTo(self.settingInterface), position=NavigationItemPosition.BOTTOM
        )

        self.splashScreen.finish()

        # 免责声明可能退出进程，要先于后台线程：线程运行时退出会触发 Qt Fatal 中止
        if not cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
            disclaimer(self)

        self.themeListener = checkThemeChange(self)

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

        self._tray_actions = (show_action, run_action, setting_action, quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        if sys.platform == 'win32':
            self.tray_icon.activated.connect(self.onTrayIconActivated)
        self.tray_icon.show()

    def is_minimized_to_tray(self) -> bool:
        """是否处于最小化到托盘状态（主窗口隐藏且托盘图标可见）"""
        try:
            return not self.isVisible() and self.tray_icon.isVisible()
        except Exception:
            return False

    def showEvent(self, event):
        """主窗口显示时补做静默启动推迟的启动检查（检查更新/公告）"""
        super().showEvent(event)
        if self._defer_startup_checks:
            self._defer_startup_checks = False
            checkUpdate(self, flag=True)
            checkAnnouncement(self)

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
        # 静默检查更新
        checkUpdate(self, silent=True)
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
        if hasattr(self, 'toolsInterface'):
            self.toolsInterface.automaticPlotCard.updateHotkeyHint()

    def _onAutoplotToggleRequested(self):
        """处理自动对话切换请求（全局热键触发）"""
        if hasattr(self, 'toolsInterface'):
            self.toolsInterface.toggleAutoPlot()

    def _on_ui_language_changed(self, lang_code: str):
        """合并连续选择；等下拉菜单退出回调后再刷新，不主动导航。"""
        self._pending_ui_language = lang_code
        self._language_change_timer.start(0)

    def _can_replace_settings(self):
        # 导航动画保存的是页面索引，运行期间不能增删页面。
        # 模态编辑和 QQ 绑定回调也必须结束，避免丢失编辑或销毁运行中的 QThread。
        return not (
            self._navigation_animation_running
            or QApplication.activeModalWidget()
            or QApplication.activePopupWidget()
            or getattr(self.settingInterface, '_qqbotBindPending', False)
            or any(thread.isRunning() for thread in self.settingInterface.findChildren(QThread))
        )

    def _replace_settings_interface(self, replacement, state):
        """新页面已成功构建后才替换旧页，期间不发出导航事件。"""
        old = self.settingInterface
        was_current = self.stackedWidget.currentWidget() is old
        replacement.setProperty('isStackedTransparent', False)
        replacement.resize(old.size())
        animation_enabled = self.stackedWidget.isAnimationEnabled()
        try:
            with QSignalBlocker(self.stackedWidget):
                self.stackedWidget.setAnimationEnabled(False)
                self.stackedWidget.addWidget(replacement)
                try:
                    if was_current:
                        # 绕过 Fluent 的 switchTo，它会清零滚动位置。
                        self.stackedWidget.view.setCurrentWidget(replacement)
                    replacement.restoreViewState(state)
                except Exception:
                    if was_current:
                        self.stackedWidget.view.setCurrentWidget(old)
                    self.stackedWidget.removeWidget(replacement)
                    raise
                self.stackedWidget.removeWidget(old)
                self.settingInterface = replacement
            self._updateStackedBackground()
        finally:
            self.stackedWidget.setAnimationEnabled(animation_enabled)
        old.hide()
        old.deleteLater()

    def _retranslate_persistent_interfaces(self):
        for interface in (self.homeInterface, self.helpInterface, self.warpInterface,
                          self.toolsInterface, self.workflowInterface, self.logInterface):
            position = interface.verticalScrollBar().value()
            interface.retranslateUi()
            interface.verticalScrollBar().setValue(position)
        labels = {
            'homeInterface': tr('主页'), 'helpInterface': tr('帮助'),
            'warpInterface': tr('抽卡记录'), 'toolsInterface': tr('工具箱'),
            'workflowInterface': tr('流程编排'), 'logInterface': tr('日志'),
            'settingInterface': tr('设置'), 'startGameButton': tr('启动游戏'), 'avatar': tr('赞赏'),
        }
        for route, text in labels.items():
            self.navigationInterface.widget(route).setText(text)
        for action, text in zip(self._tray_actions, [tr('显示主界面'), tr('完整运行'), tr('设置'), tr('退出')]):
            action.setText(text)
        self._refreshWindowTitleBar()

    def _reinstall_fluent_translator(self, lang_code: str):
        """重新安装 FluentTranslator 以使 Qt 内置组件翻译同步更新"""
        from app.common.translator import create_fluent_translator
        app = QApplication.instance()
        if hasattr(self, '_fluent_translator') and self._fluent_translator:
            try:
                app.removeTranslator(self._fluent_translator)
            except Exception:
                pass
        self._fluent_translator = create_fluent_translator(lang_code)
        app.installTranslator(self._fluent_translator)

    def _rebuild_interfaces_for_language(self):
        """状态型页面原位翻译；设置页先构建，再在原位置无动画替换。"""
        if self._pending_ui_language is None:
            return
        if not self._can_replace_settings():
            self._language_change_timer.start(100)
            return

        from module.localization import load_language, detect_lang, get_current_language
        lang_code = self._pending_ui_language
        self._pending_ui_language = None
        previous_lang = get_current_language()
        previous_setting = cfg.get_value('ui_language', 'auto')
        replacement = None
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if lang_code != previous_setting:
                cfg.set_value('ui_language', lang_code)
            actual_lang = detect_lang() if lang_code == 'auto' else lang_code
            cfg.ui_language_now = actual_lang
            load_language(actual_lang)
            self._reinstall_fluent_translator(actual_lang)
            state = self.settingInterface.captureViewState()
            # 不提前移除旧页，也不调用 processEvents：构造失败时旧页仍完整可用，
            # 任务/热键/配置回调不会在半替换状态下重入。
            replacement = SettingInterface(self)
            self._retranslate_persistent_interfaces()
            self._replace_settings_interface(replacement, state)
            replacement = None
            InfoBar.success(
                title=tr('更新成功'), content='', orient=Qt.Horizontal,
                isClosable=True, position=InfoBarPosition.TOP, duration=1500, parent=self
            )
        except Exception as e:
            # 原位回滚运行时语言、持久配置及旧页面的选择，允许重选同一语言。
            cfg.ui_language_now = previous_lang
            load_language(previous_lang)
            import traceback
            log.error(f'切换界面语言失败: {e}\n{traceback.format_exc()}')
            try:
                if cfg.get_value('ui_language', 'auto') != previous_setting:
                    cfg.set_value('ui_language', previous_setting)
            except Exception:
                log.error(f'还原界面语言配置失败\n{traceback.format_exc()}')
            combo = self.settingInterface.languageCard.comboBox
            with QSignalBlocker(combo):
                combo.setCurrentIndex(combo.findData(previous_setting))
            try:
                self._reinstall_fluent_translator(previous_lang)
                self._retranslate_persistent_interfaces()
            except Exception:
                log.error(f'还原界面文案失败\n{traceback.format_exc()}')
            InfoBar.warning(
                title=tr('语言切换失败'), content=str(e), orient=Qt.Horizontal,
                isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self
            )
        finally:
            if replacement is not None:
                replacement.hide()
                replacement.deleteLater()
            QApplication.restoreOverrideCursor()

    def _cancelTaskExit(self):
        self._task_exit_timer.stop()
        self._task_exit_pending = False
        self._task_exit_requested_by_cli = False

    def _onTaskFinished(self, exit_code):
        """仅在整次运行全部成功、没有需要保留的后台工作时关闭助手。"""
        self._cancelTaskExit()
        requested_by_cli = bool(self.exit_on_complete and self.startup_task)
        self.exit_on_complete = False
        if exit_code != 0:
            return
        if not requested_by_cli and not cfg.get_value('exit_app_after_success', False):
            return
        reason = self.logInterface.autoCloseBlockReason(preserve_schedule=not requested_by_cli)
        if reason:
            self.logInterface.appendLog(f"本次不自动关闭助手：{reason}。\n")
            return
        self._task_exit_requested_by_cli = requested_by_cli
        self._task_exit_pending = True
        self.logInterface.appendLog("全部任务已成功完成，5 秒后关闭助手；启动新任务可取消。\n")
        self._task_exit_timer.start(self.TASK_EXIT_DELAY_MS)

    def _quitAfterTask(self):
        # stop() 不能撤回已经排队的回调，因此还需检查请求是否仍有效。
        if not self._task_exit_pending:
            return
        requested_by_cli = self._task_exit_requested_by_cli
        self._cancelTaskExit()
        if not requested_by_cli and not cfg.get_value('exit_app_after_success', False):
            return
        reason = self.logInterface.autoCloseBlockReason(preserve_schedule=not requested_by_cli)
        if reason:
            self.logInterface.appendLog(f"已取消自动关闭助手：{reason}。\n")
            return
        self.quitApp()

    def quitApp(self):
        """退出应用程序"""
        self._do_quit()

    def _saveWindowState(self):
        """保存窗口尺寸、位置和最大化状态到配置文件（批量一次落盘）"""
        try:
            is_maximized = self.isMaximized()
            log.debug(f"[config-save] 退出保存窗口状态开始: maximized={is_maximized}")

            # 只在非最大化状态下保存窗口尺寸和位置
            values = {'window_maximized': is_maximized}
            if not is_maximized:
                window_memory = cfg.get_value('window_memory', 'size')
                if window_memory in ('size', 'size_and_position'):
                    values['window_width'] = self.width()
                    values['window_height'] = self.height()
                if window_memory in ('position', 'size_and_position'):
                    values['window_x'] = self.x()
                    values['window_y'] = self.y()
            # 批量一次落盘：逐项 set_value 会保存多次，放大与更新器并发写的冲突窗口
            cfg.set_values(values)
            log.debug("[config-save] 退出保存窗口状态完成")
        except Exception as e:
            import traceback
            log.error(f"[config-save] 退出保存窗口状态失败: {e}\n{traceback.format_exc()}")

    def _on_config_file_changed(self):
        """重新加载配置文件并刷新界面"""
        replacement = None
        try:
            if not self._can_replace_settings() or self._pending_ui_language is not None:
                self._config_reload_timer.start(100)
                return
            self._config_reload_timer.stop()

            # 重新加载配置
            log.info("[config-watch] 重新加载配置文件并刷新界面")
            cfg._load_config(None, save=False)

            # 重新初始化通知器
            try:
                from module.notification import init_notifiers
                init_notifiers()
            except Exception:
                pass

            # 更新日志界面的热键与日志悬浮窗开关
            if hasattr(self, 'logInterface'):
                self.logInterface.reloadConfigState()

            state = self.settingInterface.captureViewState()
            replacement = SettingInterface(self)
            self._replace_settings_interface(replacement, state)
            replacement = None

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
        finally:
            if replacement is not None:
                replacement.hide()
                replacement.deleteLater()

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
        self._cancelTaskExit()
        # 保存窗口尺寸和最大化状态
        log.info(f"[config-save] 主程序退出，保存窗口状态 PID={os.getpid()}（更新期间此处会与更新器并发写配置）")
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
        if game.is_game_running():
            InfoBar.warning(
                title=tr('游戏已在运行'),
                content=tr('无需重复启动游戏'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            if start_game_button:
                start_game_button.setEnabled(True)
            return
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
            if game_option_enabled(cfg, "auto_battle_detect_enable"):
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
                content=tr("请在“设置”→“程序”中配置"),
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
