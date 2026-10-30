# coding:utf-8
"""命令行入口中无需管理员权限的部分：状态查询、跟随运行输出、发送控制指令，以及提权运行任务。

供 main.py（源码运行）与 m7a.exe（打包后的非提权命令行入口）共用。

March7th Assistant.exe 在清单里要求管理员权限，未提权的终端、脚本或 AI Agent 无法直接运行它；
即使通过 UAC 启动，任务也在新开的控制台窗口里执行，调用方既看不到输出，也拿不到退出码。
这里把任务交给管理员进程执行，同时跟随 logs/runs/<运行编号>.log 把输出转发到当前终端，
结束后返回任务的真实退出码。所有结构化输出（JSON）都只含 ASCII 字符，不受终端编码影响。
"""
import codecs
import json
import os
import sys
import tempfile
import time

from utils.pause import (COMMAND_PAUSE, COMMAND_RESUME, COMMAND_STOP, STATE_PAUSED, STATE_PAUSING,
                         STATE_RUNNING, STATE_STOPPING, STOP_GRACE_SECONDS, read_state, write_command)
from utils.runs import (EXIT_ELEVATION_FAILED, EXIT_FAILED, EXIT_OK, LOCK_UNAVAILABLE, STATUS_RUNNING,
                        effective_status, is_valid_run_id, list_run_ids, load_run, new_run_id, read_active_run,
                        recent_runs, run_file, runs_dir)

# 仅由非提权入口处理、不转交给管理员进程的参数
FRONTEND_ONLY_FLAGS = ("--detach", "--json")

# 跟随已有运行时，先回显的末尾行数（避免长任务的完整输出刷屏）
FOLLOW_TAIL_LINES = 40

STATUS_LABELS = {
    "running": "运行中",
    "success": "成功",
    "failed": "失败",
    "blocked": "未执行",
    "stopped": "已停止",
    "interrupted": "已中断",
    "aborted": "异常结束（进程已不在，可能是窗口被关闭或进程被结束）",
}

REASON_LABELS = {
    "first_run_required": "首次使用需要先打开图形界面 March7th Launcher，由用户本人阅读并确认免责声明",
    "busy": "已有任务正在运行",
}

_SKILL_PATH = os.path.join("assets", "agent", "skills", "march7th-assistant", "SKILL.md")


def _say(out, message):
    """输出一行入口自身的提示（加 [m7a] 前缀，与任务输出区分）。"""
    try:
        out.write(f"[m7a] {message}\n")
        out.flush()
    except (OSError, ValueError):
        pass


def _print_json(out, data, indent=None):
    try:
        out.write(json.dumps(data, ensure_ascii=True, indent=indent) + "\n")
        out.flush()
    except (OSError, ValueError):
        # 调用方提前关闭了管道（如只读取前几行）：不再输出，也不报错
        pass


def entry_hint() -> str:
    """当前入口的调用方式，用于提示后续命令。"""
    if getattr(sys, "frozen", False):
        name = os.path.basename(sys.executable)
        return f'"{name}"' if " " in name else name
    return "python main.py"


def read_version() -> str:
    try:
        with open(os.path.join("assets", "config", "version.txt"), "r", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "unknown"


# ---------- 状态 ----------

def _brief(record) -> dict:
    keys = ("run_id", "task", "workflow", "invoker", "exit_code", "reason", "error",
            "started_at", "ended_at", "log_file", "screenshot")
    brief = {key: record.get(key) for key in keys}
    brief["status"] = record.get("effective_status") or effective_status(record)
    return brief


def _dir_writable(path: str) -> bool:
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix=".m7a_write_test_", delete=True):
            pass
        return True
    except OSError:
        return False


def _entrypoints(install_dir: str) -> dict:
    if getattr(sys, "frozen", False):
        names = {"gui": "March7th Launcher.exe", "cli": "March7th Assistant.exe", "agent_cli": "m7a.exe"}
        return {key: os.path.join(install_dir, name) for key, name in names.items()
                if os.path.exists(os.path.join(install_dir, name))}
    return {
        "gui": f'"{sys.executable}" "{os.path.join(install_dir, "app.py")}"',
        "cli": f'"{sys.executable}" "{os.path.join(install_dir, "main.py")}"',
    }


def collect_status() -> dict:
    """汇总安装、配置与运行状态。只读：以只读方式加载配置，不写 config.yaml。"""
    import base64

    os.environ["MARCH7TH_CONFIG_READONLY"] = "1"
    from module.config import cfg
    from utils.admin import is_user_admin
    from utils.install_registry import is_gui_running, registry_path

    install_dir = os.path.abspath(os.getcwd())
    config_path = os.path.abspath("config.yaml")
    game_path = cfg.get_value("game_path") or ""
    status = {
        "schema": 1,
        "version": cfg.version,
        "install_dir": install_dir,
        "frozen": bool(getattr(sys, "frozen", False)),
        "platform": sys.platform,
        "is_admin": is_user_admin(),
        "entrypoints": _entrypoints(install_dir),
        "config_file": config_path,
        "config_exists": os.path.exists(config_path),
        "config_writable": _dir_writable(install_dir),
        "config_reference": os.path.abspath(os.path.join("assets", "config", "config.example.yaml")),
        "first_run_completed": bool(cfg.get_value(base64.b64decode("YXV0b191cGRhdGU=").decode("utf-8"))),
        "cloud_game_enable": bool(cfg.get_value("cloud_game_enable", False)),
        "game_path": game_path,
        "game_path_exists": bool(game_path) and os.path.exists(game_path),
        "after_finish": cfg.get_value("after_finish"),
        "gui_running": is_gui_running(install_dir),
        "active_run": read_active_run(),
        "recent_runs": [_brief(record) for record in recent_runs(5)],
        "logs_dir": os.path.abspath("logs"),
        "runs_dir": runs_dir(),
        "install_registry": registry_path(),
        "agent_skill": os.path.abspath(_SKILL_PATH) if os.path.exists(_SKILL_PATH) else None,
    }
    return status


def print_status(out=None) -> int:
    _print_json(out or sys.stdout, collect_status(), indent=2)
    return EXIT_OK


# ---------- 跟随输出 ----------

class LogFollower:
    """增量读取运行日志并转发到 out（按字节偏移读取，UTF-8 增量解码）。"""

    def __init__(self, path: str, out):
        self.path = path
        self.out = out
        self.offset = 0
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def _write(self, text):
        try:
            self.out.write(text)
            self.out.flush()
        except (OSError, ValueError):
            pass

    def start_from_tail(self, lines: int):
        """只回显末尾 lines 行，之后从文件末尾继续跟随。"""
        try:
            with open(self.path, "rb") as f:
                data = f.read()
        except OSError:
            return
        self.offset = len(data)
        text = data.decode("utf-8", errors="replace")
        all_lines = text.splitlines(keepends=True)
        if len(all_lines) > lines:
            _say(self.out, f"（省略前 {len(all_lines) - lines} 行，完整输出见 {self.path}）")
            all_lines = all_lines[-lines:]
        self._write("".join(all_lines))

    def pump(self) -> bool:
        """读取并转发新内容，有新内容时返回 True。"""
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read()
        except OSError:
            return False
        if not chunk:
            return False
        self.offset += len(chunk)
        text = self._decoder.decode(chunk)
        if text:
            self._write(text)
        return True


def _print_summary(out, record, exit_code=None):
    if record is None:
        _say(out, f"任务进程已退出（退出码 {exit_code}），但没有生成运行记录；请查看 logs 目录下当天的日志")
        return
    status = effective_status(record)
    label = STATUS_LABELS.get(status, status)
    code = record.get("exit_code") if record.get("exit_code") is not None else exit_code
    code_text = f"（退出码 {code}）" if code is not None else ""
    _say(out, f"运行结束：{label}{code_text}。运行记录：{run_file(record['run_id'], '.json')}")
    if record.get("reason"):
        _say(out, f"原因：{REASON_LABELS.get(record['reason'], record['reason'])}")
    if record.get("lock") == LOCK_UNAVAILABLE:
        _say(out, f"注意：运行锁不可用（{record.get('lock_error')}），本次没有检查是否有其他任务同时在运行")
    if record.get("error"):
        _say(out, f"错误：{record['error']}")
    if record.get("screenshot"):
        _say(out, f"错误截图：{record['screenshot']}")


def _normalize_exit_code(code) -> int:
    """进程退出码转成命令行可用的 0~255；窗口被关闭等异常结束（如 0xC000013A）统一视为失败。"""
    if isinstance(code, int) and 0 <= code <= 255:
        return code
    return EXIT_FAILED


# ---------- 提权运行 ----------

def worker_command(argv, run_id: str) -> list:
    """管理员进程的完整命令行：去掉仅入口处理的参数，附加运行编号与非交互模式。"""
    args = [arg for arg in argv if arg not in FRONTEND_ONLY_FLAGS]
    args += ["--run-id", run_id]
    if "--non-interactive" not in args:
        args.append("--non-interactive")
    if getattr(sys, "frozen", False):
        worker = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "March7th Assistant.exe")
        if not os.path.exists(worker):
            worker = os.path.abspath(sys.executable)
        return [worker, *args]
    return [sys.executable, os.path.abspath("main.py"), *args]


def _launch_elevated(cmd):
    from utils.admin import SW_SHOWMINNOACTIVE, start_as_admin
    # 管理员窗口最小化且不抢焦点：输出已转发到当前终端，窗口仍可在任务栏中查看或关闭
    return start_as_admin(cmd, show_cmd=SW_SHOWMINNOACTIVE, cwd=os.getcwd())


def run_task_elevated(argv, json_output=False, detach=False, launcher=None, out=None, poll_interval=0.2) -> int:
    """以管理员身份运行任务，跟随输出并返回任务的退出码（detach 时启动后立即返回）。"""
    from utils.admin import ERROR_CANCELLED

    out = out or sys.stdout
    run_id = new_run_id()
    cmd = worker_command(argv, run_id)
    _say(out, f"运行任务需要管理员权限，请在 UAC 弹窗中选择「是」。运行编号 {run_id}")
    try:
        process = (launcher or _launch_elevated)(cmd)
    except OSError as e:
        if getattr(e, "winerror", None) == ERROR_CANCELLED:
            _say(out, "已取消管理员授权（UAC），任务未运行")
        else:
            _say(out, f"无法以管理员身份启动任务：{e}")
        if json_output:
            _print_json(out, {"run_id": run_id, "status": "not_started", "exit_code": EXIT_ELEVATION_FAILED, "error": str(e)})
        return EXIT_ELEVATION_FAILED

    log_path = run_file(run_id, ".log")
    if detach:
        _say(out, f"任务已在管理员窗口中启动（进程 {process.pid}），输出写入 {log_path}")
        _say(out, f"跟随输出：{entry_hint()} --follow {run_id}    查询状态：{entry_hint()} --status")
        if json_output:
            _print_json(out, {"run_id": run_id, "status": STATUS_RUNNING, "pid": process.pid,
                              "log_file": log_path, "record_file": run_file(run_id, ".json")})
        process.close()
        return EXIT_OK

    follower = LogFollower(log_path, out)
    try:
        while True:
            code = process.poll(poll_interval)
            follower.pump()
            if code is not None:
                follower.pump()
                break
    except KeyboardInterrupt:
        _say(out, f"已停止跟随输出，任务仍在管理员窗口中运行；继续查看：{entry_hint()} --follow {run_id}")
        return 130
    record = load_run(run_id)
    _print_summary(out, record, code)
    if json_output:
        _print_json(out, record if record is not None else {"run_id": run_id, "status": "unknown", "exit_code": code})
    return _normalize_exit_code(code)


# ---------- 跟随已有运行 / 发送控制指令 ----------

def resolve_run(spec: str):
    """把 latest / current / 运行编号 解析成运行记录，返回 (记录, 错误说明)。"""
    if spec == "current":
        # 优先取持有运行锁的运行；循环模式等待下一轮时会让出运行锁，再找最近一次仍在运行的
        holder = read_active_run()
        if holder is not None:
            spec = holder.get("run_id")
        else:
            running = [record for record in recent_runs(20) if record.get("effective_status") == STATUS_RUNNING]
            if not running:
                return None, "当前没有正在运行的任务"
            spec = running[0]["run_id"]
    elif spec == "latest":
        run_ids = list_run_ids()
        if not run_ids:
            return None, "还没有任何运行记录"
        spec = run_ids[-1]
    if not is_valid_run_id(spec):
        return None, f"无效的运行编号：{spec}（格式如 20261030-193512-4f2a，也可以用 latest / current）"
    record = load_run(spec)
    if record is None:
        return None, f"找不到运行记录：{spec}"
    return record, None


def follow_command(spec: str, json_output=False, out=None, poll_interval=0.5) -> int:
    """跟随某次运行直到结束，退出码与该运行一致。"""
    out = out or sys.stdout
    record, error = resolve_run(spec)
    if record is None:
        _say(out, error)
        return EXIT_FAILED
    run_id = record["run_id"]
    follower = LogFollower(record.get("log_file") or run_file(run_id, ".log"), out)
    follower.start_from_tail(FOLLOW_TAIL_LINES)
    try:
        while effective_status(record) == STATUS_RUNNING:
            time.sleep(poll_interval)
            follower.pump()
            record = load_run(run_id) or record
    except KeyboardInterrupt:
        _say(out, "已停止跟随输出，任务仍在运行")
        return 130
    follower.pump()
    _print_summary(out, record)
    if json_output:
        record["effective_status"] = effective_status(record)
        _print_json(out, record)
    if effective_status(record) == "aborted":
        return EXIT_FAILED
    return _normalize_exit_code(record.get("exit_code"))


_CONTROL_COMMANDS = {"pause": COMMAND_PAUSE, "resume": COMMAND_RESUME, "stop": COMMAND_STOP}


def control_command(spec: str, action: str, json_output=False, out=None, wait_seconds=10.0) -> int:
    """向运行中的任务发送 pause / resume / stop，并等待任务回执。"""
    out = out or sys.stdout
    command = _CONTROL_COMMANDS.get(action)
    if command is None:
        _say(out, f"不支持的操作：{action}（可选 pause / resume / stop）")
        return EXIT_FAILED
    record, error = resolve_run(spec)
    if record is None:
        _say(out, error)
        return EXIT_FAILED
    run_id = record["run_id"]
    if effective_status(record) != STATUS_RUNNING:
        _say(out, f"运行 {run_id} 已经结束（{STATUS_LABELS.get(effective_status(record), effective_status(record))}）")
        return EXIT_FAILED
    control_path = record.get("control_file")
    if not control_path:
        _say(out, f"运行 {run_id} 不支持暂停 / 停止控制")
        return EXIT_FAILED
    write_command(control_path, command)

    # 目标回执，以及可以视为「已收到指令」的回执（暂停中 = 已收到、尚未走到卡点）
    target = {COMMAND_PAUSE: STATE_PAUSED, COMMAND_RESUME: STATE_RUNNING, COMMAND_STOP: STATE_STOPPING}[command]
    acknowledged = {COMMAND_PAUSE: (STATE_PAUSED, STATE_PAUSING), COMMAND_RESUME: (STATE_RUNNING,),
                    COMMAND_STOP: (STATE_STOPPING,)}[command]
    deadline = time.time() + wait_seconds
    state = read_state(control_path)
    while state != target and time.time() < deadline:
        time.sleep(0.2)
        state = read_state(control_path)
    if command == COMMAND_STOP and state == STATE_STOPPING:
        # 已确认收到：再等一会儿任务结束（走到下一个卡点即结束，最长约 STOP_GRACE_SECONDS 秒后强制结束）
        end_deadline = time.time() + wait_seconds
        while time.time() < end_deadline and effective_status(load_run(run_id) or record) == STATUS_RUNNING:
            time.sleep(0.2)

    ok = state in acknowledged
    final = load_run(run_id) or record
    if command == COMMAND_PAUSE:
        if state == STATE_PAUSED:
            message = "任务已暂停，不会再发出键鼠操作"
        elif state == STATE_PAUSING:
            message = "任务已收到暂停指令，将在下一步操作前暂停"
        else:
            message = "已发送暂停指令，但任务尚未回执"
    elif command == COMMAND_RESUME:
        message = "任务已恢复运行" if ok else "已发送继续指令，但任务尚未回执"
    elif effective_status(final) != STATUS_RUNNING:
        message = f"任务已停止（{STATUS_LABELS.get(effective_status(final), effective_status(final))}）"
    elif ok:
        message = f"任务已收到停止指令，将在下一步操作前结束（最长约 {STOP_GRACE_SECONDS} 秒后强制结束）"
    else:
        message = "已发送停止指令，但任务尚未回执"
    _say(out, f"{message}。运行编号 {run_id}")
    if json_output:
        _print_json(out, {"run_id": run_id, "action": action, "acknowledged": ok, "state": state,
                          "status": effective_status(final)})
    return EXIT_OK if ok else EXIT_FAILED
