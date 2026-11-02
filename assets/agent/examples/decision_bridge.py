"""将标准输入/输出决策协议桥接到本地文件，供当前桌面 Agent 读取和回复。"""

import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time

import psutil


def atomic_json(path, value, *, replace=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        if replace:
            os.replace(temporary, path)
        elif os.name == "nt":
            os.rename(temporary, path)  # Windows rename 原子提交且不会覆盖已有回复。
        else:
            os.link(temporary, path)  # POSIX rename 会覆盖；同目录硬链接提交确保只有一个回复胜出。
    finally:
        Path(temporary).unlink(missing_ok=True)


def request_path(directory, request_id):
    if not re.fullmatch(r"[0-9a-f]{32}", request_id):
        raise ValueError("请求编号无效")
    return directory / f"{request_id}.request.json"


def active(envelope):
    if time.time() >= envelope["expires_at"]:
        return False
    try:
        owner = psutil.Process(envelope["pid"])
        return owner.is_running() and abs(owner.create_time() - envelope["process_created_at"]) < .01
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def validate_response(request, response):
    ids = {item["id"] for item in request["candidates"]}
    if (not isinstance(response, dict) or type(response.get("protocol_version")) is not int
            or response["protocol_version"] != 1 or response.get("request_id") != request["request_id"]):
        raise ValueError("响应与请求不匹配")
    if "action" not in response and "candidate_id" not in response:
        raise ValueError("响应缺少动作")
    choice = response.get("candidate_id")
    action = response.get("action", "choose" if choice is not None else "decline")
    if action == "choose":
        if not isinstance(choice, str) or choice not in ids or not request.get("can_choose", True):
            raise ValueError("候选项无效或当前不在选择页")
    elif action == "inspect":
        if not isinstance(response.get("control_id"), str) or response["control_id"] not in {item["id"] for item in request.get("controls", [])}:
            raise ValueError("查看控件无效")
    elif action == "back":
        if not request.get("can_go_back", False):
            raise ValueError("没有可返回的查看页面")
    elif action != "decline":
        raise ValueError("动作无效")
    if not isinstance(response.get("reason", ""), str) or len(response.get("reason", "")) > 2000:
        raise ValueError("理由无效")
    memory = response.get("memory", {})
    if not isinstance(memory, dict) or len(json.dumps(memory, ensure_ascii=False)) > 16000:
        raise ValueError("构筑记录无效")
    return dict(response, action=action)


def serve(directory, timeout):
    request = json.load(sys.stdin)
    if request.get("protocol_version") != 1 or not request.get("candidates"):
        raise ValueError("不支持的决策请求")
    pending = request_path(directory, request["request_id"])
    response_path = pending.with_name(f"{request['request_id']}.response.json")
    owner = psutil.Process()
    expires_at = request.get("expires_at", time.time() + timeout)
    if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)) or not math.isfinite(expires_at):
        raise ValueError("请求有效期无效")
    envelope = {"request": request, "pid": owner.pid, "process_created_at": owner.create_time(),
                "expires_at": min(time.time() + timeout, expires_at)}
    atomic_json(pending, envelope)
    try:
        while time.time() < envelope["expires_at"]:
            if response_path.is_file():
                response = validate_response(request, json.loads(response_path.read_text(encoding="utf-8")))
                print(json.dumps(response, ensure_ascii=False))
                return
            time.sleep(.1)
        print(json.dumps({"protocol_version": 1, "request_id": request["request_id"], "candidate_id": None}))
    finally:
        pending.unlink(missing_ok=True)
        response_path.unlink(missing_ok=True)


def pending_requests(directory, wait):
    deadline = time.monotonic() + wait
    while True:
        # 回复和取消可能同时发生；清理请求已消失后才提交的孤立回复。
        for response in directory.glob("*.response.json"):
            request_id = response.name.removesuffix(".response.json")
            try:
                if not request_path(directory, request_id).exists():
                    response.unlink(missing_ok=True)
            except (OSError, ValueError):
                continue
        found = []
        for path in sorted(directory.glob("*.request.json")):
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                response = path.with_name(path.name.replace(".request.", ".response."))
                if not active(envelope):
                    # 强制取消不会执行 serve 的 finally；只清理本桥接生成的请求文件。
                    request_id = envelope["request"]["request_id"]
                    if path == request_path(directory, request_id):
                        path.unlink(missing_ok=True)
                        response.unlink(missing_ok=True)
                elif not response.exists():
                    found.append(envelope)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if found or time.monotonic() >= deadline:
            print(json.dumps({"pending": found}, ensure_ascii=False))
            return
        time.sleep(.1)


def respond(directory, request_id, candidate_id, decision=None):
    path = request_path(directory, request_id)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if not active(envelope):
        raise ValueError("请求已经过期或任务已取消")
    response = dict(decision or {})
    response.setdefault("protocol_version", 1)
    response.setdefault("request_id", request_id)
    response.setdefault("candidate_id", candidate_id)
    response = validate_response(envelope["request"], response)
    destination = path.with_name(f"{request_id}.response.json")
    try:
        atomic_json(destination, response, replace=False)
    except FileExistsError:
        if json.loads(destination.read_text(encoding="utf-8")) != response:
            raise ValueError("请求已有不同回复，不覆盖先前选择")
    print(json.dumps({"request_id": request_id, "accepted": True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("serve", "pending", "respond"))
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=55)
    parser.add_argument("--wait", type=float, default=0)
    parser.add_argument("--request-id")
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--candidate-id")
    choice.add_argument("--decline", action="store_true")
    choice.add_argument("--inspect", metavar="CONTROL_ID")
    choice.add_argument("--back", action="store_true")
    choice.add_argument("--decision-file", type=Path)
    parser.add_argument("--reason", default="")
    args = parser.parse_args()
    if not 0 < args.timeout <= 300 or not 0 <= args.wait <= 60:
        parser.error("等待时间超出范围")
    if args.action == "respond" and (not args.request_id or not (args.candidate_id or args.decline or args.inspect or args.back or args.decision_file)):
        parser.error("回复需要请求编号及选择、查看、返回或决策文件")
    directory = args.directory.resolve()
    try:
        if args.action == "serve":
            serve(directory, args.timeout)
        elif args.action == "pending":
            pending_requests(directory, args.wait)
        else:
            decision = None
            if args.decision_file:
                decision = json.loads(args.decision_file.read_text(encoding="utf-8-sig"))
                if not isinstance(decision, dict):
                    raise ValueError("决策文件必须是对象")
            elif args.inspect:
                decision = {"action": "inspect", "control_id": args.inspect, "reason": args.reason}
            elif args.back:
                decision = {"action": "back", "reason": args.reason}
            elif args.reason:
                decision = {"reason": args.reason}
            respond(directory, args.request_id, args.candidate_id, decision)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"决策桥接失败：{type(error).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # 独立运行时也固定 UTF-8，避免 Windows 控制台编码影响 JSON。
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
