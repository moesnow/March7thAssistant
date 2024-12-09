from utils.command import subprocess_with_stdout
import subprocess
import sys
import os


def is_windows_terminal_available():
    """
    检查 Windows Terminal (wt.exe) 是否可用。
    """
    return subprocess_with_stdout(["where", "wt.exe"]) is not None


def execute_command_in_new_environment(command, use_windows_terminal=False):
    """
    在新的环境中执行给定的命令。
    """
    if getattr(sys, 'frozen', False):
        if not os.path.exists("./March7th Assistant.exe"):
            exception = Exception("未找到可执行文件：March7th Assistant.exe，\n请将`小助手文件夹`加入杀毒软件排除项/信任区后，\n使用 March7th Updater.exe 更新或手动更新一次")
            raise exception

    executable_path = os.path.abspath("./March7th Assistant.exe") if getattr(sys, 'frozen', False) else sys.executable
    main_script = [] if getattr(sys, 'frozen', False) else ["main.py"]

    if use_windows_terminal:
        # 尝试使用 Windows Terminal 执行命令
        try:
            subprocess.Popen(["wt", executable_path] + main_script + [command], creationflags=subprocess.DETACHED_PROCESS)
        except:
            # 如果执行失败，则回退到创建新控制台的方式执行
            subprocess.Popen([executable_path] + main_script + [command], creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        # 直接在新的控制台中执行命令
        subprocess.Popen([executable_path] + main_script + [command], creationflags=subprocess.CREATE_NEW_CONSOLE)


def start_task(command):
    """
    根据当前环境，启动任务。
    """
    # 检查 Windows Terminal 的可用性
    wt_available = is_windows_terminal_available()

    # 根据条件执行命令
    execute_command_in_new_environment(command, use_windows_terminal=wt_available)
