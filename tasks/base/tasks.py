from utils.command import subprocess_with_stdout
import subprocess
import sys
import os


def start_task(command):
    # 为什么 Windows 这么难用呢
    # 检查是否是 PyInstaller 打包的可执行文件
    if getattr(sys, 'frozen', False):
        if subprocess_with_stdout(["where", "wt.exe"]) is not None:
            # 因为 https://github.com/microsoft/terminal/issues/10276 问题
            # 管理员模式下，始终优先使用控制台主机而不是新终端
            subprocess.Popen(["wt", os.path.abspath("./March7th Assistant.exe"), command], creationflags=subprocess.DETACHED_PROCESS)
        else:
            subprocess.Popen([os.path.abspath("./March7th Assistant.exe"), command], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        if subprocess_with_stdout(["where", "wt.exe"]) is not None:
            subprocess.Popen(["wt", sys.executable, "main.py", command], creationflags=subprocess.DETACHED_PROCESS)
        else:
            subprocess.Popen([sys.executable, "main.py", command], creationflags=subprocess.CREATE_NEW_CONSOLE)
