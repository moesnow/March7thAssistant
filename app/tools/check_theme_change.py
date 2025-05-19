# check_theme_change.py 修改如下
from qfluentwidgets import setTheme, Theme, qconfig
from PyQt5.QtCore import QThread, pyqtSignal
import darkdetect
import sys

class SystemThemeListener(QThread):
    systemThemeChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._isSupported = False  # 初始设为不支持

    def run(self):
        # 运行时检测监听能力
        try:
            # 测试性调用检测实际支持情况
            darkdetect.listener(lambda _: None)
            self._isSupported = True
        except NotImplementedError:
            return

        # 正式注册监听（仅当支持时）
        darkdetect.listener(self._onThemeChanged)

    def _onThemeChanged(self, theme: str):
        theme = Theme.DARK if theme.lower() == "dark" else Theme.LIGHT
        if qconfig.themeMode.value != Theme.AUTO or theme == qconfig.theme:
            return
        qconfig.theme = Theme.AUTO
        qconfig._cfg.themeChanged.emit(Theme.AUTO)
        self.systemThemeChanged.emit()


def checkThemeChange(self):
    def handle_theme_change():
        setTheme(Theme.AUTO, lazy=True)

    # 先创建监听器（总是创建以保持接口一致）
    self.themeListener = SystemThemeListener(self)
    
    # 仅在检测到支持时启用
    if self.themeListener.isRunning():  # 通过运行状态判断
        self.themeListener.systemThemeChanged.connect(handle_theme_change)
    else:
        # 自动降级为手动模式
        # qconfig.set(qconfig.themeMode, Theme.LIGHT)  # 或从配置读取
        self.themeListener = None  # 释放无效监听器
    
    return self.themeListener