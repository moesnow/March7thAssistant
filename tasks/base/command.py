import subprocess
import sys


def run_command(command):
    try:
        # 使用subprocess运行命令并捕获标准输出
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # 检查命令是否成功执行
        if result.returncode == 0:
            # 返回标准输出的内容
            return result.stdout.strip()
        return None
    except Exception:
        return None


def start_task(command):
    # 检查是否是 PyInstaller 打包的可执行文件
    if getattr(sys, 'frozen', False):
        # 检查是否安装了 Windows Terminal
        if run_command(["where", "wt.exe"]) is not None:
            # 因为 https://github.com/microsoft/terminal/issues/10276 问题
            # 管理员模式下，始终优先使用控制台主机而不是新终端
            subprocess.check_call(f"wt ./\"March7th Assistant.exe\" {command}", shell=True)
        else:
            subprocess.check_call(f"start ./\"March7th Assistant.exe\" {command}", shell=True)
    else:
        subprocess.check_call(f"start python main.py {command}", shell=True)
