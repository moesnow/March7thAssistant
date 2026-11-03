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


def validate_decision_answer(request, answer):
    """只接受当前候选/导航控件及有界的文字状态，不接收坐标、按键或代码。"""
    try:
        encoded = json.dumps(answer, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError("外部决策必须是有效且有限的 JSON") from error
    if len(encoded) > MAX_RESPONSE_BYTES:
        raise ValueError("外部决策响应过大")
    if (not isinstance(answer, dict) or type(answer.get("protocol_version")) is not int
            or answer["protocol_version"] != PROTOCOL_VERSION
            or answer.get("request_id") != request["request_id"]):
        raise ValueError("外部决策协议或请求编号不匹配")
    action = answer.get("action", "choose" if answer.get("candidate_id") is not None else "decline")
    if action == "choose":
        if not isinstance(answer.get("candidate_id"), str) or answer["candidate_id"] not in {item["id"] for item in request["candidates"]}:
            raise ValueError("外部决策返回了未知候选项")
        if not request.get("can_choose", True):
            raise ValueError("请先返回选择界面")
    elif action == "inspect":
        if not isinstance(answer.get("control_id"), str) or answer["control_id"] not in {item["id"] for item in request.get("controls", [])}:
            raise ValueError("外部决策返回了未知查看控件")
    elif action == "back":
        if not request.get("can_go_back", False):
            raise ValueError("当前没有可返回的查看页面")
    elif action != "decline":
        raise ValueError("不支持的决策动作")
    if "action" not in answer and "candidate_id" not in answer:
        raise ValueError("外部决策缺少动作")
    if not isinstance(answer.get("reason", ""), str) or len(answer.get("reason", "")) > 2000:
        raise ValueError("决策理由过长或类型无效")
    memory = answer.get("memory", {})
    if not isinstance(memory, dict) or len(json.dumps(memory, ensure_ascii=False)) > 16000:
        raise ValueError("构筑记录过大或类型无效")
    return dict(answer, action=action)


def request_action(command, timeout, request, *, cancelled=lambda: False):
    """交换一次决策/查看请求；执行动作仍由游戏适配器验证后完成。"""
    validate_decision_command(command)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError("外部决策超时必须在 0 到 300 秒之间")

    deadline = time.monotonic() + timeout
    payload = dict(request, protocol_version=PROTOCOL_VERSION, request_id=uuid.uuid4().hex,
                   expires_at=time.time() + timeout)
    if not payload["candidates"]:
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
            try:
                answer = json.loads(raw)
                return validate_decision_answer(payload, answer)
            except (RecursionError, TypeError) as error:
                raise ValueError("外部决策响应格式无效") from error
        finally:
            if process.poll() is None:
                _terminate(process)


def request_decision(command, timeout, request, *, cancelled=lambda: False):
    """兼容只交换候选 ID 的既有接入。"""
    answer = request_action(command, timeout, request, cancelled=cancelled)
    if answer is None or answer["action"] == "decline":
        return None
    if answer["action"] != "choose":
        raise ValueError("此接入不支持查看动作")
    return answer["candidate_id"]
