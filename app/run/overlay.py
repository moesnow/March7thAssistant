"""游戏内的只读日志悬浮窗。"""

import ctypes
import re
import sys
from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel
from qfluentwidgets import qconfig

from app.common.accent import accent_html
from module.config import cfg
from module.localization import tr

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


class GameLogOverlay(QWidget):
    """显示在游戏窗口左下角的只读日志悬浮窗。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.detected_update_version = None
        self._lines = deque(maxlen=14)
        self._pending_line = ""
        self._ansi_escape_re = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
        self._margin = 14

        self._initWidget()

    def _initWidget(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            pass
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        rootLayout = QVBoxLayout(self)
        rootLayout.setContentsMargins(0, 0, 0, 0)

        self.panel = QFrame(self)
        self.panel.setObjectName('gameLogOverlayPanel')
        self._panel_style = """
            QFrame#gameLogOverlayPanel {
                background-color: rgba(16, 20, 28, 186);
                border: 1px solid rgba(255, 255, 255, 38);
                border-radius: 16px;
            }
            QLabel#gameLogOverlayTitle {
                color: rgba(255, 244, 250, 240);
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#gameLogOverlayBadge {
                color: rgb(41, 22, 34);
                background-color: rgba(241, 140, 185, 220);
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#gameLogOverlayUpdateBadge {
                color: rgba(255, 244, 250, 240);
                background-color: rgba(241, 140, 185, 70);
                border: 1px solid rgba(241, 140, 185, 190);
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#gameLogOverlayPauseBadge {
                color: rgb(52, 36, 8);
                background-color: rgba(255, 196, 84, 235);
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#gameLogOverlayBody {
                color: rgba(244, 247, 252, 235);
                background-color: transparent;
            }
            QLabel#gameLogOverlayHotkey {
                color: rgba(255, 244, 250, 240);
                font-size: 12px;
                background-color: transparent;
            }
        """
        self._updateAccent()
        qconfig.themeColorChanged.connect(self._updateAccent)
        qconfig.themeChanged.connect(self._updateAccent)

        panelLayout = QVBoxLayout(self.panel)
        panelLayout.setContentsMargins(16, 14, 16, 14)
        panelLayout.setSpacing(10)

        headerLayout = QHBoxLayout()
        headerLayout.setContentsMargins(0, 0, 0, 0)
        headerLayout.setSpacing(8)

        self.titleLabel = QLabel(tr('任务日志'), self.panel)
        self.titleLabel.setObjectName('gameLogOverlayTitle')

        self.liveBadge = QLabel(cfg.version, self.panel)
        self.liveBadge.setObjectName('gameLogOverlayBadge')
        self.liveBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.updateBadge = QLabel(self.panel)
        self.updateBadge.setObjectName('gameLogOverlayUpdateBadge')
        self.updateBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.updateBadge.setTextFormat(Qt.TextFormat.PlainText)
        self.updateBadge.hide()

        self.pauseBadge = QLabel(tr('已暂停'), self.panel)
        self.pauseBadge.setObjectName('gameLogOverlayPauseBadge')
        self.pauseBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pauseBadge.setTextFormat(Qt.TextFormat.PlainText)
        self.pauseBadge.hide()

        stop_hotkey = cfg.get_value('hotkey_stop_task', 'F10').upper()
        self.hotkeyLabel = QLabel('', self.panel)
        self.hotkeyLabel.setObjectName('gameLogOverlayHotkey')
        self.hotkeyLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # 默认仅提示停止快捷键；任务启动后由 RunController 按任务是否支持暂停刷新提示
        self.update_hotkey_hint(stop_hotkey, None)

        headerLayout.addWidget(self.titleLabel)
        headerLayout.addWidget(self.liveBadge)
        headerLayout.addWidget(self.updateBadge)
        headerLayout.addWidget(self.pauseBadge)
        headerLayout.addStretch()
        headerLayout.addWidget(self.hotkeyLabel)

        self.logLabel = QLabel('', self.panel)
        self.logLabel.setObjectName('gameLogOverlayBody')
        self.logLabel.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.logLabel.setTextFormat(Qt.TextFormat.PlainText)
        self.logLabel.setWordWrap(False)
        if sys.platform == 'win32':
            self.logLabel.setFont(QFont('NSimSun', 10))
        else:
            self.logLabel.setFont(QFont('DejaVu Sans Mono', 10))

        panelLayout.addLayout(headerLayout)
        panelLayout.addWidget(self.logLabel, 1)
        rootLayout.addWidget(self.panel)

        self.resize(420, 188)
        self.hide()

    def _updateAccent(self):
        self.panel.setStyleSheet(accent_html(self._panel_style))

    def retranslateUi(self):
        """刷新现有浮窗的文案，不重建窗口或清空任务日志。"""
        self.titleLabel.setText(tr('任务日志'))
        self.pauseBadge.setText(tr('已暂停'))
        self.setDetectedUpdateVersion(self.detected_update_version)

    def setDetectedUpdateVersion(self, version: str | None):
        self.detected_update_version = version or None
        if self.detected_update_version:
            self.updateBadge.setText(tr('检测到新版本：{version}').format(version=self.detected_update_version))
            self.updateBadge.show()
        else:
            self.updateBadge.hide()

    def set_paused(self, paused: bool):
        """显示/隐藏暂停状态徽章。"""
        self.pauseBadge.setVisible(bool(paused))

    def update_hotkey_hint(self, stop_hotkey: str, pause_hotkey: str | None, paused: bool = False):
        """更新快捷键提示；不支持暂停的任务只显示停止快捷键。

        任务已暂停时暂停快捷键的作用变为继续，提示文案随之从「暂停」改为「继续」。
        """
        if pause_hotkey:
            template = tr('按下 {stop} 停止 · {pause} 继续') if paused else tr('按下 {stop} 停止 · {pause} 暂停')
            self.hotkeyLabel.setText(template.format(stop=stop_hotkey, pause=pause_hotkey))
        else:
            self.hotkeyLabel.setText(
                tr('按下 {stop} 停止任务').format(stop=stop_hotkey)
            )

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_click_through()

    def _apply_click_through(self):
        if sys.platform != 'win32':
            return
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex_style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style)
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )
        except Exception:
            pass

    def clear_logs(self):
        self._lines.clear()
        self._pending_line = ''
        self.logLabel.setText('')

    def append_log(self, text: str):
        if not text:
            return
        normalized = self._ansi_escape_re.sub('', str(text))
        normalized = normalized.replace('\r\n', '\n').replace('\r', '\n')
        combined = self._pending_line + normalized
        parts = combined.split('\n')

        if normalized.endswith('\n'):
            self._pending_line = ''
        else:
            self._pending_line = parts.pop() if parts else combined

        for line in parts:
            self._lines.append(line)

        preview_lines = list(self._lines)
        if self._pending_line:
            preview_lines.append(self._pending_line)
        self.logLabel.setText('\n'.join(preview_lines[-self._lines.maxlen:]))

    def update_geometry(self, left: int, top: int, right: int, bottom: int):
        # Win32 API 返回物理像素，Qt move/resize 使用逻辑像素，需要按 DPI 缩放转换
        from PySide6.QtWidgets import QApplication
        dpr = 1.0
        try:
            screen = QApplication.screenAt(self.pos()) or QApplication.primaryScreen()
            if screen:
                dpr = screen.devicePixelRatio() or 1.0
        except Exception:
            pass

        phys_w = right - left
        phys_h = bottom - top
        # width = max(360, min(560, int(phys_w * 0.34 / dpr)))
        # height = max(172, min(240, int(phys_h * 0.26 / dpr)))
        width = int(phys_w * 0.34 / dpr)
        height = int(phys_h * 0.26 / dpr)

        if self.width() != width or self.height() != height:
            self.resize(width, height)

        x = int((left + self._margin) / dpr)
        y = int(max(top + self._margin, bottom - self.height() * dpr - self._margin) / dpr)
        if self.x() != x or self.y() != y:
            self.move(x, y)

    def show_overlay(self):
        self._apply_click_through()
        if not self.isVisible():
            self.show()

    def hide_overlay(self):
        if self.isVisible():
            self.hide()
