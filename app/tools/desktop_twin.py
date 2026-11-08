"""桌面分身的连接、显示和子会话 GUI 生命周期。"""

import ctypes
import os
import time
from ctypes import wintypes

import win32con
import win32gui
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, Dialog, HyperlinkButton, IconWidget, IndeterminateProgressRing, InfoBarIcon,
                            PrimaryPushButton, PushButton, SubtitleLabel, TextWrap, ToolTipFilter, ToolTipPosition,
                            isDarkTheme, qconfig)
from qfluentwidgets import FluentIcon as FIF

from app.common.icon import UiIcon
from app.common.local_instance import notify_existing_instance
from app.common.style_sheet import StyleSheet
from app.components.notice_bar import NoticeBar
from app.components.pill_label import PillLabel, pill_colors
from app.tools.process_audio import ProcessAudioMuter
from app.tools.rdp_control import DESKTOP_SIZE, RdpControl
from module.localization import tr
from utils.admin import is_user_admin
from utils.desktop_twin import (
    ScheduledLauncher, check_child_available, check_parent_session, claim_child_session,
    launcher_server_key, logoff_owned_session, owned_session_info, reserve_connection, session_exists,
)
from utils.windows_session import child_sessions_enabled, enable_child_sessions, process_session_id, session_info


_DESKTOP_ASPECT = DESKTOP_SIZE[0] / DESKTOP_SIZE[1]
_INTRO_WIDTH = 580
_DOCS_URL = "https://m7a.top/docs/#/assets/docs/{doc}"
# 内容区底色，与 assets/app/qss/*/desktop_twin.qss 一致；系统标题栏用同一颜色
_SURFACE_COLOR = {False: QColor(255, 255, 255), True: QColor(43, 43, 43)}
# WinUI 状态色 (浅色, 深色)
_STATUS_COLORS = {
    "idle": ("#8a8a8a", "#9d9d9d"),
    "ok": ("#0f7b0f", "#6ccb5f"),
    "warn": ("#9d5d00", "#fce100"),
    "error": ("#c42b1c", "#ff99a4"),
}
_ALTERNATIVE = 2  # 确认窗口第三个按钮的返回值


def docs_url():
    """按界面语言打开对应译本，没有译本时回退到简体中文文档。"""
    from module.localization.languages import localized_doc_path

    doc = os.path.splitext(os.path.basename(localized_doc_path("DesktopTwin")))[0]
    return _DOCS_URL.format(doc=doc)


def _set_frame_theme(hwnd, dark):
    """系统标题栏跟随应用主题，并与内容区同色。"""
    dwmapi = ctypes.windll.dwmapi
    enabled = ctypes.c_int(int(dark))
    # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE；Windows 10 2004 之前为 19
    if dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(enabled), ctypes.sizeof(enabled)):
        dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(enabled), ctypes.sizeof(enabled))
    color = _SURFACE_COLOR[dark]
    colorref = wintypes.DWORD(color.red() | color.green() << 8 | color.blue() << 16)
    # 35 = DWMWA_CAPTION_COLOR，仅 Windows 11 支持，旧系统会忽略
    dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(colorref), ctypes.sizeof(colorref))
    win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, win32con.SWP_FRAMECHANGED | win32con.SWP_NOMOVE
                          | win32con.SWP_NOSIZE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)


class _HeroIcon(QWidget):
    """说明页的主题色图标块。"""

    def __init__(self, icon, parent=None):
        super().__init__(parent)
        self._icon = icon
        self.setFixedSize(48, 48)
        qconfig.themeChanged.connect(self._onThemeChanged)

    def _onThemeChanged(self):
        self.update()

    def paintEvent(self, e):
        text, background, border = pill_colors(isDarkTheme())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        self._icon.render(painter, QRectF(12, 12, 24, 24), fill=text.name())


class _StatusIndicator(QWidget):
    """状态圆点；进行中的状态改为转圈，按钮暂时变灰时不会像是卡住了。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._level = "idle"
        self._ring = IndeterminateProgressRing(self, start=False)
        self._ring.setFixedSize(16, 16)
        self._ring.setStrokeWidth(2)
        self._ring.hide()
        qconfig.themeChanged.connect(self._onThemeChanged)

    def level(self):
        return self._level

    def setLevel(self, level):
        if level == self._level:
            return
        self._level = level
        busy = level == "busy"
        self._ring.setVisible(busy)
        if busy:
            self._ring.start()
        else:
            self._ring.stop()
        self.update()

    def _onThemeChanged(self):
        self.update()

    def paintEvent(self, e):
        if self._level == "busy":
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(_STATUS_COLORS[self._level][isDarkTheme()]))
        painter.drawEllipse(QRectF(4, 4, 8, 8))


class _StatusLabel(BodyLabel):
    """单行显示，放不下时省略，悬停查看全文。底栏高度固定，分身画面才能保持 16:9。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fullText = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(64)
        self.installEventFilter(ToolTipFilter(self, 300, ToolTipPosition.TOP))

    def fullText(self):
        return self._fullText

    def setFullText(self, text):
        self._fullText = text
        self._elide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def _elide(self):
        shown = self.fontMetrics().elidedText(self._fullText, Qt.TextElideMode.ElideRight, self.width())
        if shown != self.text():
            self.setText(shown)
        self.setToolTip(self._fullText if shown != self._fullText else "")


class DesktopTwinDialog(QDialog):
    hostingChanged = Signal(bool)

    def __init__(self, parent, log_page, check_ready=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setObjectName("desktopTwinDialog")
        self.setWindowIcon(QIcon("./assets/logo/March7th.ico"))
        self._log = log_page
        self._check_ready = check_ready
        self._lease = None
        self._child_lease = None
        self._session = None
        self._connected = False
        self._connect_until = None
        self._launcher = None
        self._launch_until = None
        self._quit_until = None
        self._logoff_until = None
        self._error = ""
        # 分身的声音由本进程里的 RDP 控件播放，窗口看不见时静音
        self._audio = ProcessAudioMuter(marker=os.path.abspath(os.path.join("temp", "desktop_twin_muted")))
        self._audio_check_at = 0.0
        self._audio_error = ""

        self._intro = self._createIntro()

        # RDP 控件是原生子窗口，会盖住同区域的 Qt 控件，所以外框和底栏都放在它的四周。
        self._screen = QWidget(self)
        self._screenFrame = QFrame(self._screen)
        self._screenFrame.setObjectName("screenFrame")
        self._rdp = RdpControl(self._screenFrame)
        self._rdp.setMinimumSize(360, 202)
        self._rdp.hide()
        frameLayout = QVBoxLayout(self._screenFrame)
        frameLayout.setContentsMargins(1, 1, 1, 1)
        frameLayout.addWidget(self._rdp)
        screenLayout = QVBoxLayout(self._screen)
        screenLayout.setContentsMargins(12, 12, 12, 12)
        screenLayout.addWidget(self._screenFrame)
        self._screen.hide()

        self._footerBar = QFrame(self)
        self._footerBar.setObjectName("footerBar")
        self._indicator = _StatusIndicator(self._footerBar)
        self._status = _StatusLabel(self._footerBar)
        self._docs_button = HyperlinkButton(self._footerBar)
        self._docs_button.setIcon(FIF.HELP)
        self._connect_button = PrimaryPushButton(self._footerBar)
        self._assistant_button = PushButton(QIcon("./assets/logo/March7th.ico"), "", self._footerBar)
        self._hide_button = PushButton(FIF.HIDE, "", self._footerBar)
        self._logoff_button = PushButton(FIF.POWER_BUTTON, "", self._footerBar)
        for button in (self._docs_button, self._connect_button, self._assistant_button,
                       self._hide_button, self._logoff_button):
            button.installEventFilter(ToolTipFilter(button, 300, ToolTipPosition.TOP))

        self._footer = QHBoxLayout(self._footerBar)
        self._footer.setContentsMargins(16, 12, 16, 12)
        self._footer.setSpacing(8)
        self._footer.addWidget(self._indicator, 0, Qt.AlignmentFlag.AlignVCenter)
        self._footer.addWidget(self._status, 1)
        self._footer.addWidget(self._docs_button)
        self._footer.addSpacing(4)
        for button in (self._connect_button, self._assistant_button, self._hide_button, self._logoff_button):
            self._footer.addWidget(button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._intro, 1)
        layout.addWidget(self._screen, 1)
        layout.addWidget(self._footerBar)

        self._connect_button.clicked.connect(self._toggle_connection)
        self._assistant_button.clicked.connect(self._open_assistant)
        self._hide_button.clicked.connect(self.hide)
        self._logoff_button.clicked.connect(self.close)
        StyleSheet.DESKTOP_TWIN.apply(self)
        qconfig.themeChanged.connect(self._applyFrameTheme)
        self._timer = QTimer(self, interval=250)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self.retranslateUi()
        self._set_screen_visible(False)

    def _createIntro(self):
        intro = QWidget(self)
        self._heroIcon = _HeroIcon(FIF.APPLICATION, intro)
        self._titleLabel = SubtitleLabel(intro)
        self._experimentalPill = PillLabel(parent=intro)
        self._descLabel = BodyLabel(intro)
        self._descLabel.setWordWrap(True)
        self._descLabel.setTextColor(QColor(96, 96, 96), QColor(206, 206, 206))

        self._pointsCard = QFrame(intro)
        self._pointsCard.setObjectName("pointsCard")
        pointsLayout = QVBoxLayout(self._pointsCard)
        pointsLayout.setContentsMargins(16, 14, 16, 14)
        pointsLayout.setSpacing(10)
        self._pointLabels = []
        for icon in (UiIcon.PERSON, FIF.GAME, UiIcon.PEOPLE_SWAP, FIF.POWER_BUTTON):
            iconWidget = IconWidget(icon, self._pointsCard)
            iconWidget.setFixedSize(16, 16)
            label = BodyLabel(self._pointsCard)
            label.setWordWrap(True)
            iconLayout = QVBoxLayout()
            iconLayout.setContentsMargins(0, 2, 0, 0)
            iconLayout.addWidget(iconWidget)
            iconLayout.addStretch(1)
            row = QHBoxLayout()
            row.setSpacing(12)
            row.addLayout(iconLayout)
            row.addWidget(label, 1)
            pointsLayout.addLayout(row)
            self._pointLabels.append(label)

        # 错误放在说明页里完整显示；连接后画面区域固定，改由底栏显示
        self._errorHolder = QWidget(intro)
        self._errorBar = NoticeBar(InfoBarIcon.ERROR, self._errorHolder, closable=True)
        self._errorBar.closed.connect(self._dismiss_error)
        errorLayout = QVBoxLayout(self._errorHolder)
        errorLayout.setContentsMargins(0, 12, 0, 0)
        errorLayout.addWidget(self._errorBar)
        self._errorHolder.hide()

        titleRow = QHBoxLayout()
        titleRow.setSpacing(10)
        titleRow.addWidget(self._titleLabel)
        titleRow.addWidget(self._experimentalPill, 0, Qt.AlignmentFlag.AlignVCenter)
        titleRow.addStretch(1)
        headText = QVBoxLayout()
        headText.setSpacing(4)
        headText.addLayout(titleRow)
        headText.addWidget(self._descLabel)
        header = QHBoxLayout()
        header.setSpacing(16)
        header.addWidget(self._heroIcon, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(headText, 1)

        layout = QVBoxLayout(intro)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(0)
        layout.addLayout(header)
        layout.addSpacing(20)
        layout.addWidget(self._pointsCard)
        layout.addWidget(self._errorHolder)
        layout.addStretch(1)
        return intro

    @property
    def active(self):
        return self._lease is not None

    def _screen_chrome(self):
        """分身画面以外占用的 (宽, 高)：外边距、1px 描边和底栏。"""
        outer = self._screen.layout().contentsMargins()
        border = self._screenFrame.layout().contentsMargins()
        width = outer.left() + outer.right() + border.left() + border.right()
        height = (outer.top() + outer.bottom() + border.top() + border.bottom()
                  + self._footerBar.sizeHint().height())
        return width, height

    def _height_for_desktop(self, width):
        chrome_width, chrome_height = self._screen_chrome()
        return round((width - chrome_width) / _DESKTOP_ASPECT) + chrome_height

    def _set_screen_visible(self, visible):
        """在说明页和分身画面之间切换，按内容调整窗口大小并保持窗口中心不动。"""
        center = self.frameGeometry().center() if self.isVisible() else None
        self._intro.setVisible(not visible)
        self._screen.setVisible(visible)
        self._rdp.setVisible(visible)
        if visible:
            area = self.screen().availableGeometry()
            chrome_width, chrome_height = self._screen_chrome()
            caption = max(self.frameGeometry().height() - self.height(), 32)
            fit_width = int((area.height() - 48 - caption - chrome_height) * _DESKTOP_ASPECT) + chrome_width
            width = max(self.minimumSizeHint().width(), min(960, area.width() - 48, fit_width))
            self.resize(width, self._height_for_desktop(width))
        else:
            self.resize(_INTRO_WIDTH, self._intro_height(_INTRO_WIDTH))
        if center is not None:
            self._keep_center(center)

    def _intro_height(self, width):
        layout = self.layout()
        height = layout.totalHeightForWidth(width) if layout.hasHeightForWidth() else -1
        return max(height, layout.totalMinimumSize().height())

    def _fit_intro(self):
        if self._rdp.isHidden() and self.isVisible():
            self.resize(self.width(), self._intro_height(self.width()))

    def _keep_center(self, center):
        frame = self.frameGeometry()
        frame.moveCenter(center)
        area = self.screen().availableGeometry()
        x = min(max(frame.left(), area.left()), area.right() - frame.width() + 1)
        y = min(max(frame.top(), area.top()), area.bottom() - frame.height() + 1)
        self.move(x, y)

    def nativeEvent(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == win32con.WM_SIZING and not self._rdp.isHidden():
                self._constrain_desktop_resize(msg)
                return True, 1
        return super().nativeEvent(event_type, message)

    def _constrain_desktop_resize(self, msg):
        # WM_SIZING 的矩形含系统边框，Qt 布局尺寸使用逻辑像素。
        left, top, right, bottom = win32gui.GetWindowRect(msg.hWnd)
        _, _, client_width, client_height = win32gui.GetClientRect(msg.hWnd)
        rect = wintypes.RECT.from_address(msg.lParam)
        edge = msg.wParam
        horizontal_edge = edge in (win32con.WMSZ_LEFT, win32con.WMSZ_RIGHT)
        vertical_edge = edge in (win32con.WMSZ_TOP, win32con.WMSZ_BOTTOM)
        width_change = (rect.right - rect.left) - (right - left)
        width_from_height = ((rect.bottom - rect.top) - (bottom - top)) * _DESKTOP_ASPECT
        if vertical_edge or (not horizontal_edge and abs(width_from_height) > abs(width_change)):
            width_change = width_from_height

        scale = self.devicePixelRatioF()
        width = max(self.minimumWidth(), round((client_width + width_change) / scale))
        frame_width = round(width * scale) + (right - left) - client_width
        frame_height = round(self._height_for_desktop(width) * scale) + (bottom - top) - client_height

        if vertical_edge:
            rect.left = (rect.left + rect.right - frame_width) // 2
            rect.right = rect.left + frame_width
        elif edge in (win32con.WMSZ_LEFT, win32con.WMSZ_TOPLEFT, win32con.WMSZ_BOTTOMLEFT):
            rect.left = rect.right - frame_width
        else:
            rect.right = rect.left + frame_width

        if horizontal_edge:
            rect.top = (rect.top + rect.bottom - frame_height) // 2
            rect.bottom = rect.top + frame_height
        elif edge in (win32con.WMSZ_TOP, win32con.WMSZ_TOPLEFT, win32con.WMSZ_TOPRIGHT):
            rect.top = rect.bottom - frame_height
        else:
            rect.bottom = rect.top + frame_height

    def showEvent(self, e):
        super().showEvent(e)
        self._applyFrameTheme()
        self._restore_audio()

    def hideEvent(self, e):
        super().hideEvent(e)
        # 包括主窗口最小化时随之隐藏；连接中隐藏也要静音，避免连上后直接出声
        if self._session is not None or self._connect_until:
            self._mute_audio()

    def _mute_audio(self):
        try:
            self._audio.mute()
        except Exception as error:
            self._audio_failed(error)

    def _restore_audio(self):
        try:
            self._audio.restore()
        except Exception as error:
            self._audio_failed(error)

    def _check_audio(self, now):
        """隐藏期间补静音新出现的会话；显示时解除上次异常退出遗留的静音。"""
        if now < self._audio_check_at:
            return
        self._audio_check_at = now + 1
        try:
            if self._audio.muting:
                self._audio.mute()
            elif self._audio.stale and self._connected and self.isVisible():
                self._audio.clear_stale()
        except Exception as error:
            self._audio_failed(error)

    def _audio_failed(self, error):
        if str(error) != self._audio_error:
            self._audio_error = str(error)
            self._log.appendLog(f"桌面分身：无法切换分身声音（{error}）\n")

    def _applyFrameTheme(self):
        if not self.isVisible():
            return
        try:
            _set_frame_theme(int(self.winId()), isDarkTheme())
        except Exception:
            pass

    def retranslateUi(self):
        self.setWindowTitle(tr("桌面分身（实验）"))
        self._titleLabel.setText(tr("桌面分身"))
        self._experimentalPill.setText(tr("实验性"))
        self._descLabel.setText(tr("在独立的 Windows 桌面中运行游戏和小助手，执行任务时不占用你的鼠标和键盘。"))
        points = (
            tr("分身以当前 Windows 账户登录，首次使用需要允许系统开启本地子会话"),
            tr("游戏同一时间只能在一个桌面运行，连接前请先关闭主桌面中的游戏"),
            tr("运行期间，任务、定时和设置交给分身内的小助手，主界面暂停操作"),
            tr("注销分身会关闭其中的游戏和所有应用"),
        )
        for label, text in zip(self._pointLabels, points):
            label.setText(text)
        self._docs_button.setText(tr("使用文档"))
        self._docs_button.setUrl(docs_url())
        self._docs_button.setToolTip(tr("在浏览器中打开桌面分身的使用文档"))

        closing = self._quit_until is not None or self._logoff_until is not None
        if self._connect_until:
            connect_text, connect_icon = tr("取消连接"), FIF.CLOSE
        elif self._session:
            connect_text, connect_icon = tr("重新连接"), FIF.SYNC
        else:
            connect_text, connect_icon = tr("启动分身"), FIF.PLAY
        self._connect_button.setText(connect_text)
        self._connect_button.setIcon(connect_icon)
        self._connect_button.setVisible(not self._connected)
        self._connect_button.setEnabled(not closing)
        self._connect_button.setToolTip(tr("创建或连接本机的分身桌面") if not self._connect_until else "")
        self._assistant_button.setText(tr("打开小助手"))
        self._assistant_button.setToolTip(tr("在分身中打开小助手，已打开时切换到它"))
        self._assistant_button.setVisible(self._connected)
        self._assistant_button.setEnabled(not closing and self._launcher is None)
        self._hide_button.setText(tr("隐藏"))
        self._hide_button.setToolTip(tr("隐藏此窗口并静音分身，分身继续在后台运行。可从托盘菜单或工具箱重新打开"))
        self._hide_button.setVisible(self._connected)
        self._hide_button.setEnabled(not closing)
        self._logoff_button.setText(tr("注销分身"))
        self._logoff_button.setToolTip(tr("退出分身中的小助手并注销分身，其中的游戏和应用都会关闭"))
        self._logoff_button.setVisible(self._session is not None)
        self._logoff_button.setEnabled(not closing)

        screen_visible = not self._rdp.isHidden()
        if self._error and screen_visible:
            level, status = "error", self._error
        elif closing:
            level, status = "busy", tr("正在注销分身…")
        elif self._launcher:
            level, status = "busy", tr("正在启动小助手…")
        elif self._connect_until:
            level, status = "busy", tr("正在连接分身…")
        elif self._connected:
            level, status = "ok", tr("已连接")
        elif self._session:
            level, status = "warn", tr("分身连接已断开")
        else:
            level, status = "idle", tr("未连接")
        if (level == "error") != (self._indicator.level() == "error") or not self._status.fullText():
            light, dark = _STATUS_COLORS["error"] if level == "error" else ("#606060", "#cecece")
            self._status.setTextColor(QColor(light), QColor(dark))
        self._indicator.setLevel(level)
        self._status.setFullText(status)

        show_error = bool(self._error) and not screen_visible
        error_changed = show_error != (not self._errorHolder.isHidden())
        if show_error:
            self._errorBar.setContent(self._error)
            self._errorBar.show()
        self._errorHolder.setVisible(show_error)
        if error_changed:
            self._fit_intro()

    def _dismiss_error(self):
        self._error = ""
        self.retranslateUi()

    def _report(self, error):
        self._error = str(error)
        self._log.appendLog(f"桌面分身：{error}\n")
        self.retranslateUi()

    def _ask(self, title, content, accept_text, alternative_text=None):
        """独立的确认窗口：遮罩式 MessageBox 会被 RDP 原生画面挡住。

        返回 "accept"、"alternative" 或 None（取消）。
        """
        box = Dialog(title, content, self)
        box.setTitleBarVisible(False)
        box.setContentCopyable(True)
        box.contentLabel.setText(TextWrap.wrap(content, 56, False)[0])
        box.yesButton.setText(accept_text)
        box.cancelButton.setText(tr("取消"))
        if alternative_text:
            alternative = QPushButton(alternative_text, box.buttonGroup)
            alternative.setObjectName("cancelButton")  # 沿用对话框次要按钮的样式
            alternative.setAttribute(Qt.WidgetAttribute.WA_LayoutUsesWidgetRect)
            alternative.clicked.connect(lambda: box.done(_ALTERNATIVE))
            box.buttonLayout.insertWidget(1, alternative, 1, Qt.AlignmentFlag.AlignVCenter)
        box.setMinimumSize(0, 0)
        box.setMaximumSize(16777215, 16777215)
        box.adjustSize()
        box.setFixedSize(box.size())
        try:
            result = box.exec()
        finally:
            box.deleteLater()
        if result == QDialog.DialogCode.Accepted:
            return "accept"
        return "alternative" if result == _ALTERNATIVE else None

    def _toggle_connection(self):
        self._error = ""
        if self._connect_until:
            if self._rdp.logged_on and self._rdp.error is None:
                self._poll_connection(time.monotonic())
            else:
                self._cancel_connection()
            return
        try:
            if self._session is None:
                if self._check_ready:
                    self._check_ready()
                check_parent_session()
                check_child_available()
                self._lease = reserve_connection()
                self.hostingChanged.emit(True)
            elif owned_session_info(self._session) is None:
                raise RuntimeError(tr("会话身份已变化，请在 Windows 中检查分身"))
            self._rdp.prepare()
            if not child_sessions_enabled():
                if not is_user_admin():
                    raise RuntimeError(tr("请以管理员身份运行小助手"))
                if self._ask(
                    tr("开启本地子会话"),
                    tr("桌面分身依赖 Windows 的本地子会话功能。开启后这项系统设置会一直保留，关闭分身也不会自动还原。"),
                    tr("开启"),
                ) != "accept":
                    self._cancel_connection()
                    return
                enable_child_sessions()
            if self._session is None:
                check_child_available()
                self._login_started_at = session_info(process_session_id()).current_time
            self._set_screen_visible(True)
            self._connect_until = time.monotonic() + 90
            self._rdp.connect_child()
        except Exception as error:
            self._cancel_connection()
            self._report(error)
        self.retranslateUi()

    def _cancel_connection(self):
        self._connect_until = None
        self._connected = False
        try:
            self._rdp.dispose()
        except Exception as error:
            self._report(error)
        if self._session is None:
            if self._child_lease is not None:
                self._child_lease.Close()
                self._child_lease = None
            if self._lease is not None:
                self._lease.Close()
                self._lease = None
                self.hostingChanged.emit(False)
            # 分身已经结束，不再有需要静音的声音
            self._restore_audio()
        self._set_screen_visible(False)
        self.retranslateUi()

    def _poll_connection(self, now, *, auto_launch=True):
        if self._rdp.error is not None:
            error = tr("分身连接失败（RDP {code}）").format(code=self._rdp.error)
        elif self._rdp.logged_on:
            first_connection = self._session is None
            try:
                if first_connection:
                    self._session = claim_child_session(self._login_started_at)
                    self._child_lease = reserve_connection(self._session.session_id)
                else:
                    info = owned_session_info(self._session)
                    if info is None or not info.active:
                        raise RuntimeError(tr("会话身份已变化，请在 Windows 中检查分身"))
            except Exception as exc:
                error = exc
            else:
                self._connect_until = None
                self._connected = True
                if first_connection and auto_launch:
                    self._open_assistant()
                self.retranslateUi()
                return
        elif now >= self._connect_until:
            error = tr("连接分身超时")
        else:
            return
        self._cancel_connection()
        self._report(error)

    def _contact_assistant(self, payload=None):
        if owned_session_info(self._session) is None:
            return False
        return notify_existing_instance(launcher_server_key(self._session.session_id), payload, timeout=40)

    def _open_assistant(self):
        if not self._connected or self._launcher or self._quit_until or self._logoff_until:
            return
        self._error = ""
        try:
            if self._child_lease is None:
                self._child_lease = reserve_connection(self._session.session_id)
            if not self._contact_assistant(b'{"action":"activate"}'):
                self._launcher = ScheduledLauncher()
                self._launcher.start(self._session)
                self._launch_until = time.monotonic() + 45
        except Exception as error:
            self._finish_launch()
            self._report(error)
        self.retranslateUi()

    def _finish_launch(self, *, cancel=False):
        launcher = self._launcher
        self._launcher = None
        self._launch_until = None
        if launcher is None:
            return
        try:
            if cancel:
                launcher.cancel_launch()
        except Exception as error:
            self._report(error)
        finally:
            try:
                launcher.remove_registration()
            except Exception as error:
                self._report(error)

    def _poll(self):
        now = time.monotonic()
        self._check_audio(now)
        try:
            if self._logoff_until:
                if not session_exists(self._session):
                    self._session = None
                    self._logoff_until = None
                    self.close()
                elif now >= self._logoff_until:
                    self._logoff_until = None
                    self._report(tr("等待分身注销超时"))
                return
            if self._connect_until:
                self._poll_connection(now)
            elif self._connected and self._rdp.error is not None:
                self._cancel_connection()
            if self._launcher:
                if self._contact_assistant():
                    self._finish_launch()
                    self.retranslateUi()
                elif now >= self._launch_until:
                    self._finish_launch(cancel=True)
                    self._report(tr("等待分身中的小助手启动超时"))
            if self._quit_until:
                if now >= self._quit_until or not self._contact_assistant():
                    self._start_logoff()
            elif self._session and not self._connected and not self._connect_until and not session_exists(self._session):
                self._finish_launch(cancel=True)
                self._session = None
                self._cancel_connection()
        except Exception as error:
            if str(error) != self._error:
                self._report(error)

    def _start_logoff(self):
        self._quit_until = None
        self._finish_launch(cancel=True)
        self._error = ""
        try:
            if not logoff_owned_session(self._session) and session_exists(self._session):
                raise RuntimeError(tr("会话身份已变化，请在 Windows 中检查分身"))
            self._logoff_until = time.monotonic() + 20
        except Exception as error:
            self._report(error)
        self.retranslateUi()

    def reject(self):
        self.close()

    def closeEvent(self, event):
        if self._connect_until and self._rdp.logged_on and self._rdp.error is None:
            self._poll_connection(time.monotonic(), auto_launch=False)
        if self._session is None:
            self._timer.stop()
            self._cancel_connection()
            event.accept()
            return
        event.ignore()
        if self._quit_until or self._logoff_until:
            return
        choice = self._ask(
            tr("注销桌面分身？"),
            tr("分身中的小助手会先停止任务并退出，随后注销分身，其中打开的游戏和应用都会关闭。"
               "只是不想看到这个窗口的话，可以选择“隐藏窗口”，分身会在后台继续运行。"),
            tr("注销分身"),
            tr("隐藏窗口"),
        )
        if choice == "alternative":
            self.hide()
            return
        if choice != "accept":
            return
        self._error = ""
        # 先让分身 GUI 按正常退出路径停止任务，随后由 Windows 注销会话。
        try:
            notified = self._contact_assistant(b'{"action":"quit-desktop-twin"}')
        except Exception as error:
            self._report(error)
            return
        if notified:
            self._quit_until = time.monotonic() + 12
            self.retranslateUi()
        else:
            self._start_logoff()
