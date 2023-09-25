import os
import sys

if getattr(sys, 'frozen', False):  # 检查是否是PyInstaller打包的可执行文件
    # 获取可执行文件所在目录并设置为工作目录
    app_dir = os.path.dirname(sys.executable)
else:
    # 获取脚本所在目录并设置为工作目录
    app_dir = os.path.dirname(os.path.abspath(__file__))

os.chdir(app_dir)  # 修改工作目录


from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from app.main_window import MainWindow
import sys

# enable dpi scale
QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    w = MainWindow()
    w.show()

    sys.exit(app.exec_())
