# coding:utf-8
"""免 UAC 运行（Windows）：m7a.exe 通过计划任务以管理员权限启动任务，不再弹出 UAC。

设计说明：
- 由用户在图形界面「设置 → 杂项」中自行开启：已提权的图形界面注册一个没有触发器、以最高权限运行的
  计划任务，操作为 ``March7th Assistant.exe $(Arg0)``（源码运行时为 ``python main.py $(Arg0)``）。
- 任务的安全描述符只给当前用户读取与执行权限：未提权的 m7a.exe 可以按需启动它，但不能修改它；
  其他 Windows 账户无法使用。
- m7a.exe 运行任务时，若该任务存在、已启用且指向本安装，就把本次参数替换进 $(Arg0) 启动它，
  再按运行记录（logs/runs/）跟随输出、取得退出码；否则照旧通过 UAC 提权（见 utils/cli_entry.py）。
- 任务只记录程序路径：小助手更新是原地覆盖，更新后无需重新开启；移动安装目录后需要重新开启。
- 是否开启只以计划任务为准，不另存配置，避免两处状态不一致。
"""
import ntpath
import os
import sys
import time
from subprocess import list2cmdline

from utils.runs import EXIT_FAILED, STATUS_RUNNING, effective_status, load_run

IS_WINDOWS = sys.platform == "win32"

TASK_NAME = "March7thAssistantNoUAC"
# 任务操作参数中的占位符：启动任务时替换为本次运行的参数
ARGS_PLACEHOLDER = "$(Arg0)"
# 启动任务后等待运行记录出现的最长时间（程序冷启动、杀毒软件扫描都可能较慢）
START_TIMEOUT_SECONDS = 60

STATE_ON = "on"              # 已开启，且指向本安装
STATE_OFF = "off"            # 未开启
STATE_DISABLED = "disabled"  # 计划任务在任务计划程序中被禁用
STATE_OTHER = "other"        # 计划任务指向其他安装（移动过安装目录，或在另一份安装中开启）


class LaunchError(OSError):
    """已开启免 UAC 运行，但没能通过计划任务启动任务。"""


def task_action() -> tuple:
    """本安装对应的任务操作（程序路径, 参数模板）。

    打包后直接启动 ``March7th Assistant.exe``；源码运行时为 ``python main.py``。
    """
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "March7th Assistant.exe"), ARGS_PLACEHOLDER
    return sys.executable, f"{list2cmdline([os.path.abspath('main.py')])} {ARGS_PLACEHOLDER}"


def _same_text(a, b) -> bool:
    """按 Windows 路径规则比较（不区分大小写、统一分隔符；任务计划里的路径总是 Windows 路径）。"""
    return ntpath.normcase((a or "").strip()) == ntpath.normcase((b or "").strip())


def state():
    """免 UAC 运行的状态：(STATE_*, 计划任务信息或 None)。读取失败按未开启处理。"""
    if not IS_WINDOWS:
        return STATE_OFF, None
    try:
        from utils.schedule import get_task_info
        info = get_task_info(TASK_NAME)
    except Exception:
        return STATE_OFF, None
    if info is None:
        return STATE_OFF, None
    program, arguments = task_action()
    if not (_same_text(info.get("path"), program) and _same_text(info.get("arguments"), arguments)):
        return STATE_OTHER, info
    if not info.get("enabled"):
        return STATE_DISABLED, info
    return STATE_ON, info


def is_enabled() -> bool:
    """免 UAC 运行是否对本安装生效。"""
    return state()[0] == STATE_ON


def current_user_sid() -> str:
    """当前用户的 SID 字符串（提权前后相同）。"""
    import win32api
    import win32con
    import win32security
    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()
    return win32security.ConvertSidToStringSid(sid)


def task_sddl(user_sid: str) -> str:
    """任务的安全描述符：系统与管理员完全控制；当前用户只能读取和运行（未提权的 m7a.exe 要能启动它，但不能改它）。"""
    return f"D:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FRFX;;;{user_sid})"


def enable() -> bool:
    """开启免 UAC 运行：注册（或覆盖）计划任务。需要管理员权限，由已提权的图形界面调用。"""
    if not IS_WINDOWS:
        return False
    try:
        from utils.schedule import create_on_demand_task
        program, arguments = task_action()
        if not os.path.exists(program):
            return False
        create_on_demand_task(
            task_name=TASK_NAME,
            program_path=program,
            program_args=arguments,
            working_dir=os.getcwd(),
            description="三月七小助手：供 m7a.exe 免 UAC 以管理员权限运行任务（在图形界面「设置 → 杂项」中开启或关闭）",
            sddl=task_sddl(current_user_sid()),
        )
        return is_enabled()
    except Exception:
        return False


def disable() -> bool:
    """关闭免 UAC 运行：删除计划任务。"""
    if not IS_WINDOWS:
        return False
    try:
        from utils.schedule import delete_task
        delete_task(TASK_NAME)
        return state()[0] == STATE_OFF
    except Exception:
        return False


def describe_error(error) -> str:
    """把计划任务接口的错误整理成一行：COM 错误显示为「说明（0x错误码）」。"""
    hresult = getattr(error, "hresult", None)
    if not isinstance(hresult, int):
        return str(error)
    text = getattr(error, "strerror", None) or ""
    excepinfo = getattr(error, "excepinfo", None)
    # 经 IDispatch 调用时真正的错误在 excepinfo 里：(wCode, 来源, 说明, 帮助文件, 帮助编号, 错误码)，
    # 说明常为空，此时按错误码查系统说明（外层的「发生意外。」没有参考价值）
    if excepinfo and len(excepinfo) > 5 and excepinfo[5]:
        hresult = excepinfo[5]
        text = excepinfo[2] or _system_message(hresult) or text
    return f"{str(text).strip()}（0x{hresult & 0xFFFFFFFF:08X}）"


def _system_message(code: int) -> str:
    try:
        import win32api
        return win32api.FormatMessage(code & 0xFFFFFFFF).strip()
    except Exception:
        return ""


class TaskRun:
    """由计划任务启动的管理员进程（接口与 utils.admin.ElevatedProcess 相同）。

    拿不到进程句柄：按运行记录判断是否结束，退出码取自运行记录；
    记录仍为运行中、进程却已不在（窗口被关闭等）时按失败处理。
    """

    def __init__(self, record):
        self.run_id = record["run_id"]
        self.pid = record.get("pid")

    def _exit_code(self):
        record = load_run(self.run_id)
        if record is None or effective_status(record) == STATUS_RUNNING:
            return None
        code = record.get("exit_code")
        return code if code is not None else EXIT_FAILED

    def poll(self, timeout: float = 0):
        """等待最多 timeout 秒；运行已结束时返回退出码，否则返回 None。"""
        code = self._exit_code()
        if code is None and timeout > 0:
            time.sleep(timeout)
            code = self._exit_code()
        return code

    def close(self):
        """没有需要释放的句柄。"""


def launch(args, run_id: str, timeout: float = START_TIMEOUT_SECONDS, poll_interval: float = 0.2) -> TaskRun:
    """通过计划任务启动管理员进程（args 为它的参数，须含 --run-id run_id），等到运行记录出现后返回。

    :raises LaunchError: 启动计划任务失败，或超过 timeout 秒仍没有生成运行记录。
    """
    from utils.schedule import get_task_info, run_task
    try:
        run_task(TASK_NAME, list2cmdline(list(args)))
    except Exception as e:
        raise LaunchError(f"启动计划任务 {TASK_NAME} 失败：{describe_error(e)}") from e
    deadline = time.time() + timeout
    while True:
        record = load_run(run_id)
        if record is not None:
            return TaskRun(record)
        if time.time() >= deadline:
            break
        time.sleep(poll_interval)
    detail = ""
    try:
        last_result = (get_task_info(TASK_NAME) or {}).get("last_result")
        if isinstance(last_result, int):
            detail = f"（任务上次运行结果 0x{last_result & 0xFFFFFFFF:08X}）"
    except Exception:
        pass
    raise LaunchError(f"已启动计划任务 {TASK_NAME}，但 {timeout:g} 秒内任务没有开始运行{detail}")
