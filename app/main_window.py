from utils.game_options import game_option_enabled
from utils.desktop_twin import in_desktop_twin
from PySide6.QtCore import (QAbstractAnimation, QEasingCurve, QEvent, QFileSystemWatcher, QObject, QPoint, QSignalBlocker,
                            QSize, QThread, QTimer, Qt, Signal, QVariantAnimation)
from PySide6.QtGui import QAction, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QAbstractScrollArea, QApplication, QGraphicsEffect, QHBoxLayout, QLabel, QStackedWidget,
                               QSystemTrayIcon, QVBoxLayout, QWidget)

from .components.evey_decoration import EveyControlDecoration, EveyTitleDecoration
from .common.accent import MARCH7TH_PINK, EVERNIGHT_RED, set_accent_color

from qfluentwidgets import NavigationItemPosition, FluentWindow, SplashScreen, isDarkTheme, setThemeColor, themeColor, qconfig
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, InfoBarIcon, InfoBarPosition, PrimaryPushButton, SystemTrayMenu, ToolTipFilter, ToolTipPosition
from app.tools.game_starter import GameStartStatus, GameLaunchThread

from .overview_interface import OverviewInterface
from .overview_model import OverviewModel
from .help_interface import HelpInterface
from .warp_interface import WarpInterface
from .tools_interface import ToolsInterface
from .workflow_interface import WorkflowInterface
from .setting_interface import SettingInterface
from .task_interface import TaskInterface
from .accounts_interface import AccountsInterface
from .pages.nav_search import NavigationSearchBox
from .content.run_controller import RunController
from .content.setup_model import SetupModel
from .run_interface import RunInterface
from .common.signal_bus import signalBus
from .common.evernight import EvernightEasterEgg
from .common.evernight_artwork import evernight_artwork
from .common.theme_assets import application_icon_path, application_name, sponsor_image_path
from .common.window_icon import set_application_icon
from .components.evey_animation import EveyAnimation

from .card.messagebox_custom import MessageBoxSupport
from .tools.check_update import checkUpdate
from .tools.check_theme_change import checkThemeChange, applyTheme
from .tools.announcement import checkAnnouncement
from .tools.disclaimer import disclaimer

from module.config import cfg
from app.tools.adb_service import display_connection
from module.automation import auto
from module.logger import log
from module.game import get_game_controller
from module.localization import tr
from module.screen import screen
from tasks.tool import stop_plot
import base64
import os
import sys


def fit_menu_width(menu):
    """按当前菜单项文字重新计算 Fluent 菜单宽度。

    qfluentwidgets 调整列表尺寸时用 setFixedSize 锁住了最小宽度，之后只会变宽：
    菜单项文字改短（例如“桌面分身（运行中）”恢复为“桌面分身”）后要先放开再重算。
    """
    view = getattr(menu, 'view', None)
    if view is None:
        return
    view.setMinimumWidth(0)
    view.adjustSize()
    menu.adjustSize()


def _lazy_interface(name):
    """把页面属性改成「取用时才构建」。

    启动时先只建总览，其余页面等第一次显示或第一次被访问时再构造；构建前的
    赋值（例如语言切换时替换设置页）直接写进页面表，不会触发多余构建。
    """

    def fget(self):
        page = self.ensurePage(name)
        if page is None:
            raise AttributeError(name)
        return page

    def fset(self, widget):
        self._pages[name] = widget

    return property(fget, fset)


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
            self.watcher.fileChanged.connect(self.request_check)

    def request_check(self, path):
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


class LogoShakeEffect(QGraphicsEffect):
    """Rotate only the artwork, keeping the logo's layout and hit area fixed."""
    def __init__(self, parent):
        super().__init__(parent)
        self.angle = 0.0
        self.timeline = QVariantAnimation(self)
        self.timeline.setDuration(440)
        self.timeline.setKeyValues([(0.0, 0.0), (0.16, -14.0), (0.34, 12.0),
                                    (0.54, -8.0), (0.74, 5.0), (1.0, 0.0)])
        self.timeline.valueChanged.connect(self._advance)

    def shake(self):
        self.timeline.stop()
        self.timeline.start()

    def _advance(self, angle):
        self.angle = angle
        self.update()

    def boundingRectFor(self, rect):
        return rect.adjusted(-4, -4, 4, 4)

    def draw(self, painter):
        offset = QPoint()
        pixmap = self.sourcePixmap(Qt.CoordinateSystem.LogicalCoordinates, offset,
                                   QGraphicsEffect.PixmapPadMode.NoPad)
        center = self.sourceBoundingRect().center()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(center)
        painter.rotate(self.angle)
        painter.translate(-center)
        painter.drawPixmap(offset, pixmap)
        painter.restore()


class EasterEggClickFilter(QObject):
    clicked = Signal()

    def __init__(self, logo):
        super().__init__(logo)
        self.logo = logo
        self.shake_effect = LogoShakeEffect(logo)
        logo.setGraphicsEffect(self.shake_effect)
        self.hit_target = QWidget(logo.parentWidget())
        self.hit_target.setObjectName('logoClickTarget')
        self.hit_target.setFixedSize(48, 48)
        self.hit_target.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hit_target.installEventFilter(self)
        logo.installEventFilter(self)
        self._position_target()

    def _position_target(self):
        self.hit_target.move(max(0, self.logo.x() - (self.hit_target.width() - self.logo.width()) // 2),
                             max(0, self.logo.y() - (self.hit_target.height() - self.logo.height()) // 2))
        self.hit_target.raise_()

    def eventFilter(self, obj, event):
        if obj is self.logo and event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            self._position_target()
        if (event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick,
                             QEvent.Type.MouseButtonRelease)
                and event.button() == Qt.MouseButton.LeftButton):
            # 只记录完整点击；吞掉双击，避免快速连点 LOGO 使窗口最大化。
            if (event.type() == QEvent.Type.MouseButtonRelease
                    and obj.rect().contains(event.position().toPoint())):
                self.shake_effect.shake()
                self.clicked.emit()
            return True
        if event.type() == QEvent.Type.MouseMove and event.buttons() & Qt.MouseButton.LeftButton:
            return True
        return super().eventFilter(obj, event)


# 所有设置卡和任务卡都能完整显示的最小窗口尺寸。
MIN_WINDOW_WIDTH = 1320
MIN_WINDOW_HEIGHT = 640
DEFAULT_WINDOW_HEIGHT = 758


class NavIconDecoration(EveyControlDecoration):
    """侧栏展开后按钮变宽，装饰只贴着图标那一格。"""

    def _position(self):
        rect = self._control.geometry()
        rect.setWidth(min(rect.width(), 40))
        self.setGeometry(rect.adjusted(*self._outsets))


class MainWindow(FluentWindow):
    TASK_EXIT_DELAY_MS = 5000
    # 这些页面启动时先放占位页，取用时才真正构造（见 _lazy_interface）。
    taskInterface = _lazy_interface('taskInterface')
    settingInterface = _lazy_interface('settingInterface')
    warpInterface = _lazy_interface('warpInterface')
    toolsInterface = _lazy_interface('toolsInterface')
    workflowInterface = _lazy_interface('workflowInterface')
    helpInterface = _lazy_interface('helpInterface')

    def __init__(self, task=None, exit_on_complete=False, start_minimized_to_tray=False):
        super().__init__()
        self._pages = {}  # 已构建的页面，键是页面属性名
        self._page_slots = {}  # 未构建页面的占位控件，占住导航和堆栈位置
        self._page_builders = {}
        self._desktop_twin_hosting = False
        self._desktop_twin_tray_action = None
        self._desktop_twin_notice = None
        self._desktop_twin_badge = None
        self._backend_connection = display_connection(cfg)
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
        self._startup_checks_timer = QTimer(self)
        self._startup_checks_timer.setSingleShot(True)
        self._startup_checks_timer.timeout.connect(self._runStartupChecks)
        self.startup_task = task  # 保存启动时要执行的任务
        self.exit_on_complete = exit_on_complete  # 命令行指定的单次退出请求
        self._task_exit_pending = False
        self._task_exit_requested_by_cli = False
        self._task_exit_timer = QTimer(self)
        self._task_exit_timer.setSingleShot(True)
        self._task_exit_timer.timeout.connect(self._quitAfterTask)
        self.start_minimized_to_tray = start_minimized_to_tray
        self._defer_startup_checks = False  # 静默启动时推迟的启动检查（检查更新/公告）
        self._setup_dialog = None
        self._setup_model = None
        self._setup_checks_pending = False
        self._reload_after_setup = False
        self.detected_update_version = None
        self.updateVersionBadge = None
        self._evernight = EvernightEasterEgg()
        self._evey_animation = None
        self._evernight.selected = self._load_evernight_selection()
        self._evernight_active = self._evernight.selected

        self.initWindow()

        self.config_watcher = ConfigWatcher(os.path.abspath(cfg.config_path), self)
        self.config_watcher.config_changed.connect(self._on_config_file_changed)
        self.initInterface()
        self.initNavigation()
        self.initSystemTray()
        qconfig.themeChanged.connect(self._on_theme_changed)
        if self._evernight.selected:
            self._on_theme_changed()

        if self.start_minimized_to_tray:
            self.hide()

        self._finishStartup()

    def _finishStartup(self):
        # 记住的自动对话是后台功能，不能依赖用户打开工具箱。
        if (sys.platform == 'win32' and cfg.get_value('autoplot_remember_enable', False)
                and cfg.get_value('autoplot_enable', False)):
            QTimer.singleShot(0, self, self._restoreAutoPlot)
        # 如果有启动任务，延迟执行
        if self.startup_task:
            QTimer.singleShot(1000, self._executeStartupTask)
        elif self.start_minimized_to_tray:
            # 最小化到托盘启动：不弹出任何窗口，检查更新与公告推迟到主窗口首次显示
            self._defer_startup_checks = True
        elif self._shouldOpenSetup():
            self._setup_checks_pending = True
            QTimer.singleShot(0, self, self._openInitialSetup)
        else:
            self._scheduleStartupChecks()

    def _restoreAutoPlot(self):
        # 复用工具箱既有的平台、连接状态及选项检查；已创建时不会再次启动。
        if self._desktop_twin_hosting or not (cfg.get_value('autoplot_remember_enable', False)
                                              and cfg.get_value('autoplot_enable', False)):
            return
        try:
            self.ensurePage('toolsInterface')
        except Exception as exc:
            log.error(f'恢复自动对话失败，请打开工具箱检查自动对话状态：{type(exc).__name__}: {exc}')

    def _scheduleStartupChecks(self, delay=200):
        """首帧渲染之后再检查更新和公告。

        两者都会起线程跑网络请求，放在窗口构造末尾会和首帧的排版、绘制抢资源；
        推迟一拍不影响用户看到界面，提示出现也只是晚了一瞬。用可取消的定时器，
        首次配置向导打开期间要取消，避免向导还没结束就弹出更新提示。
        """
        self._startup_checks_timer.start(delay)

    def _runStartupChecks(self):
        try:
            checkUpdate(self, flag=True)
            checkAnnouncement(self)
        except Exception as exc:
            log.warning(f'启动检查更新或公告失败：{type(exc).__name__}: {exc}')

    @property
    def setupModel(self):
        if self._setup_model is None:
            self._setup_model = SetupModel(self)
        return self._setup_model

    def _shouldOpenSetup(self):
        return (not self.startup_task and not self.start_minimized_to_tray
                and SetupModel.pending(cfg) and not self.setupModel.blocked_reason()
                and not self.runController.isTaskRunning())

    def _openInitialSetup(self):
        if not self._shouldOpenSetup() or not self.openSetup(automatic=True):
            self._finishSetupChecks()

    def _finishSetupChecks(self):
        if self._setup_checks_pending:
            self._setup_checks_pending = False
            self._scheduleStartupChecks()

    def _executeStartupTask(self):
        """执行启动时指定的任务"""
        if self.startup_task:
            from tasks.base.tasks import start_task
            start_task({"program": "self", "args": self.startup_task, "trigger": "startup", "account": "all"})

    def initWindow(self):
        # 开启 “在标题栏和窗口边框上显示强调色” 后，会导致窗口顶部出现异色横条 bug 已经修复
        # https://github.com/zhiyiYo/PyQt-Frameless-Window/pull/186
        # 要求 PySideSix-Frameless-Window>=0.7.0
        # self.setMicaEffectEnabled(False)

        setThemeColor(EVERNIGHT_RED if self._evernight_active else MARCH7TH_PINK, lazy=True)
        applyTheme(self)

        # 禁用最大化
        # self.titleBar.maxBtn.setHidden(True)
        # self.titleBar.maxBtn.setDisabled(True)
        # self.titleBar.setDoubleClickEnabled(False)
        # self.setResizeEnabled(False)

        # self.setWindowFlags(Qt.WindowCloseButtonHint)
        # self.setWindowFlags(Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)

        # 设置最小尺寸：侧栏常驻展开后，这是所有设置卡和任务卡都能完整显示的最小宽度。
        # 屏幕比它还窄时（如 1080p 屏幕 150% 缩放）以屏幕为准，卡片说明会省略显示，按钮不会溢出。
        available = QApplication.primaryScreen().availableGeometry()
        min_width = min(MIN_WINDOW_WIDTH, available.width())
        min_height = min(MIN_WINDOW_HEIGHT, available.height())
        self.setMinimumWidth(min_width)
        self.setMinimumHeight(min_height)

        window_memory = cfg.get_value('window_memory', 'size')
        # 从配置文件读取窗口尺寸，确保不低于最小值
        if window_memory in ('size', 'size_and_position'):
            saved_width = cfg.get_value('window_width', min_width)
            saved_height = cfg.get_value('window_height', DEFAULT_WINDOW_HEIGHT)
            window_width = max(saved_width, min_width)
            window_height = max(saved_height, min_height)
            self.resize(window_width, window_height)
        else:
            self.resize(min_width, min_height)

        # 标题栏从窗口最左边开始，给图标留出和侧栏一致的左边距。
        self.titleBar.hBoxLayout.setContentsMargins(14, 0, 0, 0)
        easter_egg_click = EasterEggClickFilter(self.titleBar.iconLabel)
        easter_egg_click.clicked.connect(self._on_logo_clicked)
        set_application_icon(self, application_icon_path(self._evernight_active), self._assistant_name())
        self.setWindowTitle(self._assistant_name())
        # 分离系统窗口标题与应用内标题栏文本
        self._refreshWindowTitleBar()

        self._evey_title_decoration = EveyTitleDecoration(self.titleBar)

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
        return f"{self._assistant_name()} {cfg.version}"

    def _assistant_name(self):
        return application_name(self._evernight_active)

    def _refreshDesktopTwinBadge(self):
        """分身内的小助手在标题栏标出身份，透过分身画面也能和主桌面的小助手区分开。"""
        if not in_desktop_twin() or not hasattr(getattr(self, 'titleBar', None), 'hBoxLayout'):
            return
        if self._desktop_twin_badge is None:
            from .components.pill_label import PillLabel
            badge = PillLabel(parent=self.titleBar)
            badge.installEventFilter(ToolTipFilter(badge, 300, ToolTipPosition.BOTTOM))
            layout = self.titleBar.hBoxLayout
            index = layout.indexOf(self.titleBar.titleLabel) + 1
            layout.insertWidget(index, badge, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.insertSpacing(index + 1, 8)
            self._desktop_twin_badge = badge
        self._desktop_twin_badge.setText(tr('桌面分身'))
        self._desktop_twin_badge.setToolTip(
            tr('这是运行在桌面分身中的小助手。分身内固定使用前台模式，不调整画质和分辨率，也不执行任务完成后的关机等操作'))

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
        # 紧跟在标题后面。Fluent 标题栏把窗口按钮放在布局末尾，固定下标会排到关闭按钮右侧。
        layout = self.titleBar.hBoxLayout
        title = getattr(self.titleBar, 'titleLabel', None)
        index = layout.indexOf(title) + 1 if title is not None else 0
        if index > 0:
            layout.insertSpacing(index, 12)
            layout.insertWidget(index + 1, badge, 0, Qt.AlignmentFlag.AlignVCenter)
        else:
            layout.insertWidget(max(0, layout.count() - 1), badge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.updateVersionBadge = badge
        return badge

    def _refreshWindowTitleBar(self):
        if hasattr(self, 'titleBar') and hasattr(self.titleBar, 'setTitle'):
            self.titleBar.setTitle(self._baseTitleBarText())

        badge = self._ensureUpdateVersionBadge()
        # 更新徽章先插入，分身徽章再插到标题后面，两者依次排列
        self._refreshDesktopTwinBadge()
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
        if hasattr(self, 'runController') and self.runController:
            try:
                self.runController.setDetectedUpdateVersion(self.detected_update_version)
            except Exception:
                pass

    @staticmethod
    def _prepare_evernight():
        try:
            evernight_artwork()
        except OSError as error:
            log.warning(f'无法加载长夜主题：{error}')
            return False
        return True

    def _load_evernight_selection(self):
        if not self._evernight.unlocked and cfg.get_value('evernight_unlocked') is True:
            self._evernight = EvernightEasterEgg(unlocked=True)
        return (self._evernight.unlocked and cfg.get_value('ui_theme') == 'evernight'
                and self._prepare_evernight())

    def _apply_ui_theme(self, evernight_selected):
        selection_changed = evernight_selected != self._evernight.selected
        previous_palette = qconfig.theme
        self._evernight.selected = evernight_selected
        applyTheme(self)
        # 深色和长夜共用调色板，切换时 Qt 可能不发出 themeChanged。
        if selection_changed and qconfig.theme == previous_palette:
            self._on_theme_changed()

    def set_ui_theme(self, preference, *, unlock_evernight=False):
        if cfg.writes_suspended:
            return False
        selected = preference == 'evernight'
        if selected and (not self._evernight.unlocked or not self._prepare_evernight()):
            return False

        values = {'ui_theme': preference}
        if unlock_evernight:
            values['evernight_unlocked'] = True
        previous = {key: cfg.config[key] for key in values if key in cfg.config}
        try:
            if unlock_evernight:
                cfg.set_values(values)
            else:
                cfg.set_value('ui_theme', preference)
        except OSError as error:
            for key in values.keys() - previous.keys():
                cfg.config.pop(key, None)
            cfg.config.update(previous)
            log.warning(f'无法保存界面主题：{error}')
            return False

        self._apply_ui_theme(selected)
        return True

    def _on_theme_changed(self):
        selected = self._evernight.selected
        if not selected and self._evey_animation is not None:
            self._evey_animation.close()  # closed 回调按当前主题统一刷新。
            return
        # 首次动画到中点时替换角色，动画继续；之后随主题即时切换。
        active = (selected and self._evernight.animation_played
                  and (self._evey_animation is None
                       or self._evey_animation.timeline.currentValue() >= 0.5))
        if active != self._evernight_active:
            self._evernight_active = active
            set_accent_color(EVERNIGHT_RED if active else MARCH7TH_PINK)
            self.setWindowTitle(self._assistant_name())
            self._refreshDesktopTwinIndicators()
            set_application_icon(self, application_icon_path(active), self._assistant_name())
        self._evey_title_decoration.setActive(active)
        self.settingInterface.themeCard.setEvernightMode(active)
        self._evey_settings_decoration.setActive(active)
        self.homeInterface.setEvernightMode(active, animate=self._evey_animation is not None)
        self._refreshWindowTitleBar()
        # 先让深色三月七界面重绘，再播放首次替换动画。
        if selected and not self._evernight.animation_played:
            QTimer.singleShot(0, self._play_evey_animation)

    def _on_logo_clicked(self):
        self._on_easter_egg_click('logo')

    def _on_mascot_clicked(self):
        self._on_easter_egg_click('mascot')

    def _on_easter_egg_click(self, source):
        result = self._evernight.record_click(source)
        if result == 'warning':
            self.homeInterface.playLogoHint(source)
            return
        if result != 'unlocked':
            return
        self.homeInterface.dismissLogoHint()
        if not self.set_ui_theme('evernight', unlock_evernight=True):
            self._evernight.unlocked = False
            return
        self.settingInterface.themeCard.showEvernightOption()

    def _play_evey_animation(self):
        if not self.isVisible() or self.isMinimized():
            return
        if not self._evernight.consume_animation(self._evernight.selected):
            return
        animation = EveyAnimation(self)
        self._evey_animation = animation
        animation.midpointReached.connect(self._on_theme_changed)
        animation.closed.connect(self._on_evey_animation_closed)
        if animation.sprite.isNull():
            animation.close()  # A missing intro alone need not prevent the prepared theme from working.
        else:
            animation.play()

    def _on_evey_animation_closed(self):
        self._evey_animation = None
        if not self._evernight_active or not self._evernight.selected:
            self._on_theme_changed()

    def _on_update_version_badge_clicked(self):
        if self.detected_update_version:
            checkUpdate(self)

    def initInterface(self):
        from app.content.account_model import AccountModel
        self.accountModel = AccountModel(self)
        self.homeInterface = OverviewInterface(self)
        self.homeInterface.mascotClicked.connect(self._on_mascot_clicked)
        self.runController = RunController(self)
        self.logInterface = RunInterface(self)
        self.homeInterface.attachModel(OverviewModel(self, config_changed=self.config_watcher.request_check))
        from module.search import SearchIndex
        self._search_popup = None
        self.searchIndex = SearchIndex(cfg)
        self.destroyed.connect(self.searchIndex.close)
        self.accountsInterface = AccountsInterface(self)
        # 设置页和任务页原本在构造时顺手创建这两个模型，页面改为按需构建后由
        # 主窗口先建好，向导模型和搜索在启动阶段就会用到它们。
        from .content.notify_model import NotifyModel
        from .content.task_model import TaskModel
        from .pages.common import shared
        self.notifyModel = shared(self, 'notifyModel', lambda: NotifyModel(self))
        self.taskModel = shared(self, 'taskModel', lambda: TaskModel(self))
        # 其余页面在首次显示或首次被访问时构造：十个分类/任务全建要 1 秒以上，
        # 而启动后只会显示总览。
        self._page_builders = {
            'taskInterface': lambda: TaskInterface(self),
            'settingInterface': lambda: SettingInterface(self),
            'warpInterface': lambda: WarpInterface(self),
            'toolsInterface': lambda: ToolsInterface(self),
            'workflowInterface': lambda: WorkflowInterface(self),
            'helpInterface': lambda: HelpInterface(self),
        }
        self.accountModel.bindingChanged.connect(self._accountBindingChanged)
        self.accountModel.changed.connect(self.homeInterface.model.request_refresh)
        self.accountModel.changed.connect(self.runController.changed)
        self.accountModel.changed.connect(self.scheduleModel.changed)
        self.runHistory.changed.connect(self.accountModel.refresh)
        self.runController.taskFinished.connect(self.accountModel.refresh)
        self.runController.sync_records()

        # 连接任务启动信号
        signalBus.startTaskSignal.connect(self._onStartTask)
        # 连接热键配置改变信号
        signalBus.hotkeyChangedSignal.connect(self._onHotkeyChanged)
        # 连接 UI 语言改变信号
        signalBus.uiLanguageChanged.connect(self._on_ui_language_changed)
        # 连接任务完成信号
        self.runController.taskSequenceFinished.connect(self._onTaskFinished)
        self.runController.taskStarted.connect(self._cancelTaskExit)
        # 连接自动对话切换信号
        self.runController.autoplotToggleRequested.connect(self._onAutoplotToggleRequested)

    def _addLazySubInterface(self, name, icon, text, position):
        """先放一个占位页占住导航和堆栈位置，页面在取用时才真正构造。"""
        slot = QWidget(self)
        slot.setObjectName(name)
        slot.setProperty('isStackedTransparent', False)
        self.stackedWidget.addWidget(slot)
        self._page_slots[name] = slot
        self.navigationInterface.addItem(
            routeKey=name, icon=icon, text=text,
            onClick=lambda: self.openPage(name), position=position,
        )

    def builtPage(self, name):
        """已构建的页面；未构建返回 None，不会触发构建。"""
        return self._pages.get(name)

    def ensurePage(self, name):
        """构建页面并顶替占位页；已构建则直接返回。"""
        page = self._pages.get(name)
        if page is not None:
            return page
        builder = self._page_builders.get(name)
        if builder is None:
            return None
        page = builder()
        # 构造成功后才摘除构建器：构造失败时下次访问仍会重试，不会把页面变成死键。
        self._page_builders.pop(name, None)
        page.setProperty('isStackedTransparent', False)
        if self._desktop_twin_hosting and name in ('taskInterface', 'settingInterface',
                                                    'workflowInterface', 'warpInterface'):
            # 桌面分身接管期间新建的页面同样要禁用，否则会出现可操作窗口期。
            page.setDisabled(True)
        slot = self._page_slots.pop(name, None)
        if slot is not None:
            self._swap_slot(slot, page)
        self._pages[name] = page
        return page

    def _swap_slot(self, slot, page):
        """用真正的页面顶替占位页，过程中不发出导航事件。"""
        view = self.stackedWidget.view
        was_current = self.stackedWidget.currentWidget() is slot
        index = view.indexOf(slot)
        with QSignalBlocker(self.stackedWidget), QSignalBlocker(view):
            view.addWidget(page)
            # Fluent 的 addWidget 会同步创建动画信息；将新页面和对应动画一起移回
            # 占位页的位置，避免正在运行的导航动画持有的目标索引发生变化。
            info = view.aniInfos.pop()
            view.removeWidget(slot)
            QStackedWidget.removeWidget(view, page)
            QStackedWidget.insertWidget(view, index, page)
            view.aniInfos.insert(index, info)
            if was_current:
                # 绕过 Fluent 的 switchTo，它会清零滚动位置。
                view.setCurrentWidget(page)
        slot.deleteLater()
        self._updateStackedBackground()

    def openPage(self, name):
        """导航项点击入口：确保页面已构建再切换。"""
        page = self.ensurePage(name)
        if page is None:
            return False
        self.switchTo(page)
        return True

    def switchTo(self, interface):
        # 和 Fluent 的页面切换一样，打开整页滚动区域时先回到顶部。
        if isinstance(interface, QAbstractScrollArea):
            interface.verticalScrollBar().setValue(0)
        self.stackedWidget.view.setCurrentWidget(interface, duration=150)

    @staticmethod
    def _speedUpNavigationIndicator(navigation):
        motion = navigation.panel.indicator.scaleSlideAni

        def shorten(state, _previous):
            if state != QAbstractAnimation.State.Running:
                return
            # Fluent 每次启动都会重设时长和曲线，所以在动画组开始时调整。
            for animation in (motion.slidePosAni1, motion.slideLengthAni1):
                animation.setDuration(55)
                animation.setEasingCurve(QEasingCurve.Type.OutQuad)
            for animation in (motion.slidePosAni2, motion.slideLengthAni2):
                animation.setDuration(105)
            for animation in (motion.crossPosAni, motion.crossLenAni):
                animation.setDuration(160)

        motion.slideAniGroup.stateChanged.connect(shorten)
        motion.crossAniGroup.stateChanged.connect(shorten)

    def initNavigation(self):
        navigation = self.navigationInterface
        self._speedUpNavigationIndicator(navigation)
        navigation.setReturnButtonVisible(False)
        # 侧栏常驻展开：只看图标很难分辨页面。标题栏占满窗口宽度，侧栏从标题栏下方开始。
        navigation.setMenuButtonVisible(False)
        navigation.setExpandWidth(240)
        navigation.panel.vBoxLayout.insertSpacing(0, 42)
        from .accounts.nav_card import AccountNavCard
        self.accountNavCard = AccountNavCard(self)
        navigation.addWidget("accountsInterface", self.accountNavCard,
                             lambda: self.openAccountSwitcher(self.accountNavCard), NavigationItemPosition.TOP)
        self.accountModel.changed.connect(self._refreshAccountNavigation)
        self.searchBox = NavigationSearchBox(self)
        navigation.addWidget('searchBox', self.searchBox, self.openSearch, NavigationItemPosition.TOP)
        self.addSubInterface(self.homeInterface, FIF.HOME, tr('总览'))
        self._addLazySubInterface('taskInterface', FIF.CHECKBOX, tr('任务'), NavigationItemPosition.TOP)
        self.addSubInterface(self.logInterface, FIF.COMMAND_PROMPT, tr('运行'))
        self._addLazySubInterface('warpInterface', FIF.SHARE, tr('抽卡记录'), NavigationItemPosition.TOP)
        self._addLazySubInterface('toolsInterface', FIF.DEVELOPER_TOOLS, tr('工具箱'), NavigationItemPosition.TOP)
        self._addLazySubInterface('workflowInterface', FIF.CODE, tr('流程编排'), NavigationItemPosition.TOP)
        navigation.addSeparator()
        self._addLazySubInterface('helpInterface', FIF.BOOK_SHELF, tr('帮助'), NavigationItemPosition.TOP)
        # self.addSubInterface(self.changelogInterface, FIF.UPDATE, '更新日志')

        navigation.addItem('startGameButton', FIF.PLAY, tr('启动游戏'), self.startGame, selectable=False,
                           position=NavigationItemPosition.BOTTOM)

        # self.navigationInterface.addWidget(
        #     'refreshButton',
        #     NavigationBarPushButton(FIF.SYNC, '刷新', isSelectable=False),
        #     self._on_config_file_changed,
        #     NavigationItemPosition.BOTTOM)

        navigation.addItem(
            'avatar', FIF.HEART, tr('赞赏'),
            lambda: MessageBoxSupport(
                tr('支持作者🥰'),
                tr('此程序为免费开源项目，如果你付了钱请立刻退款\n如果喜欢本项目，可以微信赞赏送作者一杯咖啡☕\n您的支持就是作者开发和维护项目的动力🚀'),
                sponsor_image_path(self._evernight_active, isDarkTheme()),
                self
            ).exec(),
            selectable=False, position=NavigationItemPosition.BOTTOM
        )
        self.stackedWidget.addWidget(self.accountsInterface)
        self._refreshAccountNavigation()

        # 回调每次读取当前实例，替换设置页时不删除导航项或污染导航历史。
        self._addLazySubInterface('settingInterface', FIF.SETTING, tr('设置'), NavigationItemPosition.BOTTOM)
        self._evey_settings_decoration = NavIconDecoration(
            self.navigationInterface.widget('settingInterface'),
            'evey-decoration-upright.png', (-4, -9, 4, 3))
        self._searchShortcut = QShortcut(QKeySequence('Ctrl+K'), self)
        self._searchShortcut.activated.connect(self.openSearch)
        navigation.setCollapsible(False)

        self.splashScreen.finish()

        # 免责声明可能退出进程，要先于后台线程：线程运行时退出会触发 Qt Fatal 中止
        if not cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8")):
            disclaimer(self)

        self.themeListener = checkThemeChange(self)

    def initSystemTray(self):
        """初始化系统托盘"""
        from .tools.macos_tray import patch_macos_tray

        patch_macos_tray()
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.windowIcon())
        self.tray_icon.setToolTip(self._assistant_name())

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

        if sys.platform == "win32" and not in_desktop_twin():
            self._desktop_twin_tray_action = QAction(tr("桌面分身"), self)
            self._desktop_twin_tray_action.triggered.connect(lambda: self.toolsInterface.openDesktopTwin())
            tray_menu.addAction(self._desktop_twin_tray_action)

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

    def navigate(self, link: str) -> bool:
        from app.navigation import navigate
        return navigate(self, link)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # 侧栏常驻展开，标题栏从窗口最左边开始（FluentWindow 默认给收起按钮让出 46 像素）。
        self.titleBar.move(0, 0)
        self.titleBar.resize(self.width(), self.titleBar.height())

    def openSetup(self, *, automatic=False):
        if reason := self.setupModel.blocked_reason():
            InfoBar.warning(tr("首次配置向导"), reason, parent=self)
            return False
        if self._setup_dialog is not None:
            self._setup_dialog.raise_()
            return True
        try:
            from app.setup.dialog import SetupDialog
            self.setupModel.begin(automatic)
            dialog = SetupDialog(self.setupModel, self)
        except Exception as error:
            log.error(f"打开首次配置向导失败：{type(error).__name__}: {error}")
            InfoBar.error(tr("无法打开首次配置向导"), str(error), parent=self)
            return False
        self._setup_dialog = dialog
        # 向导还没走完时不要弹更新提示。
        self._startup_checks_timer.stop()
        actions = []

        def after_close(action):
            if self._setup_dialog is dialog:
                actions.append(action)
            else:
                QTimer.singleShot(0, self, action)

        def closed(completed):
            if self._setup_dialog is not dialog:
                return
            self._setup_dialog = None
            if self._reload_after_setup:
                self._reload_after_setup = False
                self._config_reload_timer.start(0)
            if not self.setupModel.close_result.ok:
                InfoBar.error(tr("无法保存设置"), self.setupModel.close_result.text, parent=self)
            elif automatic and not completed:
                InfoBar.info(tr("首次配置向导"), tr("可以在「设置 › 高级」重新打开向导"), duration=6000, parent=self)
            for action in actions:
                QTimer.singleShot(0, self, action)
            actions.clear()
            QTimer.singleShot(0, self, self._finishSetupChecks)

        dialog.closed.connect(closed)
        dialog.runRequested.connect(lambda: after_close(self.startFullTask))
        dialog.linkRequested.connect(lambda link: after_close(lambda: self.navigate(link)))
        dialog.open()
        return True

    def openSearch(self, *_):
        if self._setup_dialog is not None:
            return
        if self._search_popup is None:
            from .search_popup import SearchPopup
            self._search_popup = SearchPopup(self)
        self._search_popup.open()

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
            self._scheduleStartupChecks()
        if self._evernight.unlocked and not self._evernight.animation_played:
            QTimer.singleShot(0, self._play_evey_animation)

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
        if self._desktop_twin_hosting:
            # 快捷方式或其他实例转来的任务请求不能静默丢弃
            InfoBar.warning(
                title=tr('桌面分身运行中'),
                content=tr('主界面暂停期间无法启动任务，请在分身内的小助手中运行'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM,
                duration=5000,
                parent=self
            )
            return
        # 检查是否有任务正在运行
        if self.runController.isTaskRunning():
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
        self.runController.startTask(command)

    def startFullTask(self):
        """启动完整运行任务"""
        from tasks.base.tasks import start_task
        start_task("main")

    def _refreshAccountNavigation(self):
        self.accountNavCard.setAccount(*self.accountModel.card())

    def _accountBindingChanged(self):
        try:
            self.taskInterface.rebuild(account_changed=True)
        except Exception as exc:
            # 切账号后重建任务页失败不应该让绑定流程整体失败。
            log.warning(f'切换账号后刷新任务页失败：{type(exc).__name__}: {exc}')
        self.searchIndex.invalidate()
        self.homeInterface.model.request_refresh()

    def openAccountSwitcher(self, target):
        from .accounts.switcher import AccountSwitcher
        self.accountModel.refresh()
        switcher = AccountSwitcher(self.accountModel)
        def select(uid):
            if self.accountModel.active():
                result = self.accountModel.set_current(uid)
                show = InfoBar.success if result.ok else InfoBar.warning
                name = next((a.name for a in self.accountModel.accounts() if a.uid == uid), "")
                show(tr("切换账号"), result.text or tr("正在查看「{name}」").format(name=name), parent=self)
            else:
                self.switchTo(self.accountsInterface)
                self.accountsInterface.showAccount(uid)
        def add():
            self.switchTo(self.accountsInterface)
            self.accountsInterface.addAccount()
        switcher.accountClicked.connect(select)
        switcher.addClicked.connect(add)
        switcher.manageClicked.connect(lambda: self.switchTo(self.accountsInterface))
        return switcher.open(target)

    def refreshBackendTasks(self):
        connection = display_connection(cfg)
        changed = connection != self._backend_connection
        if changed:
            stop_plot()
            if connection.error is None:
                auto.reload_connection()
                screen.reload_profile()
            self._backend_connection = connection
        self.accountModel.refresh()
        self.homeInterface.refreshBackendTasks()
        try:
            self.toolsInterface.refreshBackendTasks(connection_changed=changed)
        except Exception as exc:
            log.warning(f'刷新工具箱失败：{type(exc).__name__}: {exc}')

    def _onHotkeyChanged(self):
        """处理热键配置改变信号"""
        if hasattr(self, 'runController'):
            self.runController.updateHotkey()
        if hasattr(self, 'toolsInterface'):
            self.toolsInterface.automaticPlotCard.updateHotkeyHint()

    def _onAutoplotToggleRequested(self):
        """处理自动对话切换请求（全局热键触发）"""
        if not self._desktop_twin_hosting and hasattr(self, 'toolsInterface'):
            self.toolsInterface.toggleAutoPlot()

    def checkDesktopTwinReady(self):
        from utils.runs import read_active_run

        game_launch = getattr(self, "game_launch_thread", None)
        if (self.runController.autoCloseBlockReason(preserve_schedule=False) or read_active_run()
                or (game_launch is not None and game_launch.isRunning())):
            raise RuntimeError(tr("请先结束主桌面的任务再连接分身"))

    def setDesktopTwinHosting(self, active):
        """把定时和共享设置的写入权交给分身 GUI，注销后恢复主界面。"""
        self._desktop_twin_hosting = active
        cfg.writes_suspended = active
        self._cancelTaskExit()
        self.runController.setDesktopTwinHosting(active)
        self.accountNavCard.setDisabled(active)
        for page in (self.homeInterface, self.builtPage('taskInterface'), self.builtPage('settingInterface'),
                     self.builtPage('workflowInterface'), self.builtPage('warpInterface'),
                     self.accountsInterface):
            if page is not None:
                page.setDisabled(active)
        self.logInterface.setDesktopTwinHosting(active)
        start_game = self.navigationInterface.widget('startGameButton')
        if start_game is not None:
            start_game.setDisabled(active)
        for action in self._tray_actions[1:3]:
            action.setDisabled(active)
        # 页面整体变灰时要说明原因，并给出回到分身窗口的入口
        notice = self._ensureDesktopTwinNotice() if active else self._desktop_twin_notice
        if notice is not None:
            notice.setVisible(active)
        self._refreshDesktopTwinIndicators()
        if not active and cfg.is_config_changed():
            self._on_config_file_changed()
        self.toolsInterface.setDesktopTwinHosting(active)

    def _ensureDesktopTwinNotice(self):
        """在页面区域上方插入提示条，挤开页面而不是盖住页面顶部的标题和标签页。"""
        if self._desktop_twin_notice is not None:
            return self._desktop_twin_notice
        from .components.notice_bar import NoticeBar

        notice = NoticeBar(InfoBarIcon.INFORMATION, self, accent=True)
        notice.openButton = PrimaryPushButton(notice)
        notice.openButton.clicked.connect(self.toolsInterface.openDesktopTwin)
        notice.addWidget(notice.openButton)
        notice.hide()
        noticeRow = QHBoxLayout()
        noticeRow.setContentsMargins(0, 0, 12, 10)
        noticeRow.addWidget(notice)
        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        index = self.widgetLayout.indexOf(self.stackedWidget)
        self.widgetLayout.removeWidget(self.stackedWidget)
        column.addLayout(noticeRow)
        column.addWidget(self.stackedWidget, 1)
        self.widgetLayout.insertLayout(index, column, 1)
        self._desktop_twin_notice = notice
        self._refreshDesktopTwinIndicators()
        return notice

    def _refreshDesktopTwinIndicators(self):
        hosting = self._desktop_twin_hosting
        if self._desktop_twin_tray_action is not None:
            self._desktop_twin_tray_action.setText(tr("桌面分身（运行中）") if hosting else tr("桌面分身"))
        if hasattr(self, 'tray_icon'):
            self.tray_icon.setToolTip(
                f"{self._assistant_name()}\n{tr('桌面分身运行中')}" if hosting else self._assistant_name())
            fit_menu_width(self.tray_icon.contextMenu())
        notice = self._desktop_twin_notice
        if notice is not None:
            notice.setTitle(tr("桌面分身运行中"))
            notice.setContent(tr("任务、定时和设置已交给分身内的小助手。为避免冲突，主界面暂停操作，注销分身后自动恢复。"))
            notice.openButton.setText(tr("打开分身窗口"))

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
            or getattr(getattr(self, 'notifyModel', None), 'binding_pending', False)
            or any(thread.isRunning() for thread in self.settingInterface.findChildren(QThread))
        )

    def _replace_settings_interface(self, replacement, state):
        """新页面已成功构建后才替换旧页，期间不发出导航事件。"""
        old = self.settingInterface
        was_current = self.stackedWidget.currentWidget() is old
        replacement.setProperty('isStackedTransparent', False)
        replacement.resize(old.size())
        replacement.setDisabled(self._desktop_twin_hosting)
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
        for interface in (self.homeInterface, self.toolsInterface, self.workflowInterface):
            position = interface.verticalScrollBar().value()
            interface.retranslateUi()
            interface.verticalScrollBar().setValue(position)
        # 帮助页按小节保存和恢复阅读位置：换语言后文档长度不同，不能沿用像素位置。
        self.runController.retranslateOverlay()
        self.accountModel.refresh()
        self.runHistory.refresh()
        self.logInterface.retranslateUi()
        self.helpInterface.retranslateUi()
        # 抽卡记录页的页头固定，统计和明细各自滚动、保留位置。
        self.warpInterface.retranslateUi()
        labels = {
            'homeInterface': tr('总览'), 'taskInterface': tr('任务'), 'helpInterface': tr('帮助'),
            'warpInterface': tr('抽卡记录'), 'toolsInterface': tr('工具箱'),
            'workflowInterface': tr('流程编排'), 'logInterface': tr('运行'), 'accountsInterface': tr('账号'),
            'settingInterface': tr('设置'), 'startGameButton': tr('启动游戏'), 'avatar': tr('赞赏'),
        }
        for route, text in labels.items():
            self.navigationInterface.widget(route).setText(text)
        self.searchBox.setText(tr('搜索功能、设置、帮助'))
        self.searchBox.setToolTip(tr('搜索（Ctrl+K）'))
        if self._search_popup is not None:
            self._search_popup.retranslateUi()
        self.taskInterface.rebuild()
        self.accountsInterface.retranslateUi()
        for action, text in zip(self._tray_actions, [tr('显示主界面'), tr('完整运行'), tr('设置'), tr('退出')]):
            action.setText(text)
        self._refreshDesktopTwinIndicators()
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
            self.refreshBackendTasks()
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
        if exit_code != 0 or self.runController._finish_skipped:
            return
        if not requested_by_cli and not cfg.get_value('exit_app_after_success', False):
            return
        reason = self.runController.autoCloseBlockReason(preserve_schedule=not requested_by_cli)
        if reason:
            self.runController.appendLog(f"本次不自动关闭助手：{reason}。\n")
            return
        self._task_exit_requested_by_cli = requested_by_cli
        self._task_exit_pending = True
        self.runController.appendLog("全部任务已成功完成，5 秒后关闭助手；启动新任务可取消。\n")
        self._task_exit_timer.start(self.TASK_EXIT_DELAY_MS)
        self.runController.changed.emit()

    def _quitAfterTask(self):
        # stop() 不能撤回已经排队的回调，因此还需检查请求是否仍有效。
        if not self._task_exit_pending:
            return
        requested_by_cli = self._task_exit_requested_by_cli
        self._cancelTaskExit()
        if not requested_by_cli and not cfg.get_value('exit_app_after_success', False):
            return
        reason = self.runController.autoCloseBlockReason(preserve_schedule=not requested_by_cli)
        if reason:
            self.runController.appendLog(f"已取消自动关闭助手：{reason}。\n")
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
        if self._desktop_twin_hosting:
            return
        replacement = None
        try:
            if self._setup_dialog is not None:
                # 向导继续显示已编辑的草稿，侧栏和其他页的卡片照常接收配置变化。
                self._config_reload_timer.stop()
                self._reload_after_setup = True
                cfg._load_config(None, save=False)
                return
            if not self._can_replace_settings() or self._pending_ui_language is not None:
                self._config_reload_timer.start(100)
                return
            self._config_reload_timer.stop()

            # 重新加载配置
            log.info("[config-watch] 重新加载配置文件并刷新界面")
            cfg._load_config(None, save=False)
            self.homeInterface.model.request_refresh()
            self._apply_ui_theme(self._load_evernight_selection())

            # 重新初始化通知器
            try:
                from module.notification import init_notifiers
                init_notifiers()
            except Exception:
                pass

            # 更新日志界面的热键与日志悬浮窗开关
            if hasattr(self, 'runController'):
                self.runController.reloadConfigState()

            state = self.settingInterface.captureViewState()
            replacement = SettingInterface(self)
            self.taskInterface.rebuild()
            self._replace_settings_interface(replacement, state)
            replacement = None
            if self._search_popup is not None and self._search_popup.isVisible():
                self._search_popup.open(self._search_popup.input.text())
            if display_connection(cfg) != self._backend_connection:
                self.refreshBackendTasks()

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
        if hasattr(self, "runController"):
            self.runController.stopOwnedTasksOnExit()

    def _do_quit(self, e=None):
        """执行退出前的清理并退出程序
        e: 可选的 QCloseEvent，用于调用 e.accept()
        """
        close_twin = getattr(self.builtPage('toolsInterface'), "closeDesktopTwin", None)
        if close_twin and not close_twin():
            if e is not None:
                e.ignore()
            return
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
        if hasattr(self, 'runController'):
            try:
                self.runController.cleanup()
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
        if self._desktop_twin_hosting:
            return
        connection = display_connection(cfg)
        if connection.error:
            InfoBar.warning(title=tr('启动失败'), content=connection.error, orient=Qt.Horizontal,
                            position=InfoBarPosition.TOP, duration=5000, parent=self)
            return
        if connection.control_backend == "adb":
            # 设备会话属于任务进程，在界面进程里启动游戏会一直占着设备端服务。
            InfoBar.info(
                title=tr('Android 设备不需要单独启动游戏'),
                content=tr('运行任务时会自动在设备上启动游戏'),
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            return
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
        account = self.accountModel.editing()
        if account and connection.control_backend == "local":
            from copy import copy
            from utils.registry import gameaccount
            path = account.game_path or cfg.game_path
            if gameaccount.server_for_path(path) != account.server:
                if start_game_button:
                    start_game_button.setEnabled(True)
                InfoBar.warning(tr("启动失败"), tr("请为这个账号设置同一服务器的游戏路径"), parent=self)
                return
            game = copy(game)
            game.game_path = path
            if str(gameaccount.gamereg_uid(path)) != account.uid:
                if start_game_button:
                    start_game_button.setEnabled(True)
                outcome = self.accountModel.prepare_login(account.uid, after=self.startGame)
                if not outcome.ok:
                    InfoBar.warning(tr("启动失败"), outcome.text, parent=self)
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
            # 桌面分身与主桌面共用游戏设置，手动启动游戏也不改写自动战斗和二倍速。
            if not in_desktop_twin() and game_option_enabled(cfg, "auto_battle_detect_enable"):
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
                content=tr("请在「设置 → 运行方式 → 游戏路径」中选择正确的游戏文件"),
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
