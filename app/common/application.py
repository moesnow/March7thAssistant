from PySide6.QtWidgets import QApplication


def create_application(argv):
    app = QApplication(argv)
    # 对话框关闭后保留托盘任务，退出由主窗口显式调用 quit。
    app.setQuitOnLastWindowClosed(False)
    return app
