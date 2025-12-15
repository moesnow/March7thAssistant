# coding: utf-8
from PyQt5.QtCore import QObject, pyqtSignal


class SignalBus(QObject):
    """ Signal bus """

    switchToSampleCard = pyqtSignal(str, int)
    micaEnableChanged = pyqtSignal(bool)
    supportSignal = pyqtSignal()

    # 任务相关信号
    startTaskSignal = pyqtSignal(str)  # 启动任务信号，参数为任务命令
    hotkeyChangedSignal = pyqtSignal()  # 热键配置改变信号


signalBus = SignalBus()
