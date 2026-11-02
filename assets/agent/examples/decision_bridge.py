"""将标准输入/输出决策协议桥接到本地文件，供当前桌面 Agent 读取和回复。"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time

import psutil


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        os.replace(temporary, path)
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
            or response["protocol_version"] != 1 or response.get("request_id") != request["request_id"]
            or "candidate_id" not in response):
        raise ValueError("响应与请求不匹配")
    choice = response["candidate_id"]
    if choice is not None and (not isinstance(choice, str) or choice not in ids):
        raise ValueError("候选项无效")
    return response


def serve(directory, timeout):
    request = json.load(sys.stdin)
    if request.get("protocol_version") != 1 or not request.get("candidates"):
        raise ValueError("不支持的决策请求")
    pending = request_path(directory, request["request_id"])
    response_path = pending.with_name(f"{request['request_id']}.response.json")
    owner = psutil.Process()
    envelope = {"request": request, "pid": owner.pid, "process_created_at": owner.create_time(),
                "expires_at": time.time() + timeout}
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


def respond(directory, request_id, candidate_id):
    path = request_path(directory, request_id)
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if not active(envelope):
        raise ValueError("请求已经过期或任务已取消")
    response = {"protocol_version": 1, "request_id": request_id, "candidate_id": candidate_id}
    validate_response(envelope["request"], response)
    atomic_json(path.with_name(f"{request_id}.response.json"), response)
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
    args = parser.parse_args()
    if not 0 < args.timeout <= 300 or not 0 <= args.wait <= 60:
        parser.error("等待时间超出范围")
    if args.action == "respond" and (not args.request_id or not (args.candidate_id or args.decline)):
        parser.error("回复需要请求编号，以及候选编号或 --decline")
    directory = args.directory.resolve()
    try:
        if args.action == "serve":
            serve(directory, args.timeout)
        elif args.action == "pending":
            pending_requests(directory, args.wait)
        else:
            respond(directory, args.request_id, args.candidate_id)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"决策桥接失败：{type(error).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    # 独立运行时也固定 UTF-8，避免 Windows 控制台编码影响 JSON。
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
