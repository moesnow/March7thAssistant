"""外部决策 JSON 协议；不导入游戏、GUI 或模型 SDK。"""

import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import uuid

import psutil


PROTOCOL_VERSION = 1
MAX_RESPONSE_BYTES = 64 * 1024


class DecisionCancelled(Exception):
    """暂停或停止使当前请求失效，调用者应重新识别界面。"""


def _terminate(process):
    """外部程序可能启动模型 CLI；取消时同时回收其子进程。"""
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
        psutil.wait_procs(children + [parent], timeout=2)
    except psutil.NoSuchProcess:
        pass
    finally:
        process.wait(timeout=3)


def validate_decision_command(command, *, require_available=False):
    """GUI 与运行时共用参数列表校验，校验时不执行程序。"""
    if (not isinstance(command, (list, tuple)) or not command
            or len(command) > 32
            or any(not isinstance(arg, str) or not arg or '\0' in arg or len(arg) > 4096 for arg in command)):
        raise ValueError("外部决策命令必须是非空的参数列表")
    if not command[0].strip():
        raise ValueError("外部决策程序不能为空")
    if os.name == "nt" and os.path.splitext(command[0])[1].lower() in (".bat", ".cmd"):
        raise ValueError("请直接指定可执行文件，不使用批处理命令")
    if require_available:
        resolved = shutil.which(command[0])
        if not resolved:
            raise ValueError("外部决策程序不存在或不可执行")
        return os.path.abspath(resolved)
    return command[0]


def request_decision(command, timeout, request, *, cancelled=lambda: False):
    """同步等待一个候选 ID；失败抛 ValueError/OSError，绝不执行模型返回的命令。"""
    validate_decision_command(command)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError("外部决策超时必须在 0 到 300 秒之间")

    deadline = time.monotonic() + timeout
    payload = dict(request, protocol_version=PROTOCOL_VERSION, request_id=uuid.uuid4().hex,
                   expires_at=time.time() + timeout)
    candidate_ids = {candidate["id"] for candidate in payload["candidates"]}
    if not candidate_ids:
        return None
    if cancelled():
        raise DecisionCancelled()

    # 使用临时文件避免子进程不读取 stdin 或大量输出时阻塞任务线程。
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as output:
        source.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        source.seek(0)
        kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {"start_new_session": True}
        process = subprocess.Popen(list(command), stdin=source, stdout=output, stderr=subprocess.DEVNULL,
                                   shell=False, **kwargs)
        try:
            while process.poll() is None:
                if cancelled():
                    raise DecisionCancelled()
                if time.monotonic() >= deadline:
                    raise TimeoutError("外部决策超时")
                if os.fstat(output.fileno()).st_size > MAX_RESPONSE_BYTES:
                    raise ValueError("外部决策响应过大")
                time.sleep(0.05)
            if cancelled():
                raise DecisionCancelled()
            if time.monotonic() >= deadline:
                raise TimeoutError("外部决策超时")
            if process.returncode:
                raise ValueError("外部决策程序执行失败")
            output.seek(0)
            raw = output.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError("外部决策响应过大")
            answer = json.loads(raw)
            if (not isinstance(answer, dict)
                    or type(answer.get("protocol_version")) is not int
                    or answer["protocol_version"] != PROTOCOL_VERSION
                    or answer.get("request_id") != payload["request_id"]
                    or "candidate_id" not in answer):
                raise ValueError("外部决策协议或请求编号不匹配")
            selected = answer.get("candidate_id")
            if selected is not None and (not isinstance(selected, str) or selected not in candidate_ids):
                raise ValueError("外部决策返回了未知候选项")
            return selected
        finally:
            if process.poll() is None:
                _terminate(process)
