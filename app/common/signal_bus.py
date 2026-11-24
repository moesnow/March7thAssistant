# coding: utf-8
from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """ Signal bus """

    switchToSampleCard = Signal(str, int)
    micaEnableChanged = Signal(bool)
    supportSignal = Signal()

    adbDevicesChanged = Signal(object)  # 最近一次设备卡刷新结果
    autostartChanged = Signal(object)  # Windows 登录启动任务发生变化

    # 任务相关信号
    startTaskSignal = Signal(str)  # 启动任务信号，参数为任务命令
    hotkeyChangedSignal = Signal()  # 热键配置改变信号
    uiLanguageChanged = Signal(str)  # UI 语言变更信号，参数为语言代码


signalBus = SignalBus()
