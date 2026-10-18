import copy
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse


class Supervisor:
    def __init__(self, start_worker=True):
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.process = None
        self.current = None
        self.queue = deque()
        self.started_at = None
        self.last_exit_code = None
        self.stopping = False
        self.worker = None
        if start_worker:
            self.worker = threading.Thread(target=self._run, daemon=True)
            self.worker.start()

    def status(self):
        with self.lock:
            running = self.process is not None and self.process.poll() is None
            return {
                "running": running,
                "current": dict(self.current) if running and self.current else None,
                "pid": self.process.pid if running else None,
                "started_at": self.started_at if running else None,
                "exit_code": self.process.returncode if self.process is not None and not running else self.last_exit_code,
                "queue": [dict(item) for item in self.queue],
            }

    def enqueue(self, task=None, workflow_name=None, workflow_step_path=None, task_id=None):
        if bool(task) == bool(workflow_name):
            raise ValueError("必须且只能指定 task 或 workflow_name")
        if task is not None and not isinstance(task, str):
            raise ValueError("task 必须是字符串")
        if workflow_name is not None and not isinstance(workflow_name, str):
            raise ValueError("workflow_name 必须是字符串")
        if workflow_step_path is not None and not isinstance(workflow_step_path, str):
            raise ValueError("workflow_step_path 必须是字符串")
        from utils.tasks import AVAILABLE_TASKS
        from module.workflow import list_workflow_names

        if task and task not in AVAILABLE_TASKS:
            raise ValueError("未知任务")
        if workflow_name and workflow_name not in list_workflow_names():
            raise ValueError("未知工作流")
        if task_id is not None and (not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", task_id)):
            raise ValueError("id 只能包含字母、数字、下划线和连字符，长度不超过 64")
        if workflow_step_path and any(not part.isdigit() for part in workflow_step_path.split("/")):
            raise ValueError("workflow_step_path 格式应为数字路径，例如 0/1/2")
        with self.lock:
            identifier = task_id or uuid.uuid4().hex
            if identifier == (self.current or {}).get("id") or any(item["id"] == identifier for item in self.queue):
                raise ValueError("任务 id 已存在")
            item = {
                "id": identifier,
                "task": task,
                "workflow_name": workflow_name,
                "workflow_step_path": workflow_step_path,
                "status": "queued",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "scheduled_at": None,
            }
            self.queue.append(item)
            self.changed.notify_all()
            return dict(item)

    def enqueue_startup_task(self, task="main", no_run_immediately=False):
        from utils.tasks import AVAILABLE_TASKS
        if task not in AVAILABLE_TASKS:
            raise ValueError("未知启动任务")
        with self.changed:
            if any(entry["id"] == "startup-main" for entry in self.queue):
                raise ValueError("启动任务已排入队列")
            scheduled_at = None
            if no_run_immediately:
                delay = self._seconds_until_scheduled_time()
                scheduled_at = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
            item = {
                "id": "startup-main",
                "task": task,
                "workflow_name": None,
                "workflow_step_path": None,
                "status": "queued",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "scheduled_at": scheduled_at,
            }
            self.queue.append(item)
            self.changed.notify_all()
        return dict(item)

    @staticmethod
    def _seconds_until_scheduled_time():
        from module.config import cfg
        scheduled_time = str(cfg.get_value("scheduled_time", "04:00"))
        match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", scheduled_time)
        if not match:
            raise ValueError("scheduled_time 必须使用 HH:mm 格式")
        now = datetime.now()
        target = now.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return max(1, (target - now).total_seconds())

    def cancel(self, task_id):
        with self.lock:
            for item in self.queue:
                if item["id"] == task_id:
                    self.queue.remove(item)
                    item["status"] = "cancelled"
                    self.changed.notify_all()
                    return item
            return None

    def _start_process(self, item):
        root = os.path.dirname(os.path.dirname(__file__))
        command = [sys.executable, os.path.join(root, "main.py")]
        if item["task"]:
            command.append(item["task"])
        else:
            command.extend(["--workflow-name", item["workflow_name"]])
            if item["workflow_step_path"]:
                command.extend(["--workflow-step-path", item["workflow_step_path"]])
        env = os.environ.copy()
        env["MARCH7TH_DOCKER_STARTED"] = "true"
        env["MARCH7TH_SUPERVISED"] = "true"
        env["MARCH7TH_AFTER_FINISH"] = "Exit"
        try:
            from module.config import cfg
            item["loop_enabled"] = item["task"] == "main" and cfg.get_value("after_finish") == "Loop"
        except Exception:
            item["loop_enabled"] = False
        self.process = subprocess.Popen(command, env=env, cwd=root)
        self.current = item
        self.current["status"] = "running"
        self.started_at = datetime.now(timezone.utc).isoformat()

    def _loop_delay(self, item):
        try:
            from module.config import cfg
            if not item or not item.get("loop_enabled"):
                return None
            return self._seconds_until_scheduled_time()
        except Exception:
            return None

    def _run(self):
        while True:
            with self.changed:
                while not self.queue and self.process is None:
                    self.changed.wait()
                if self.process is None:
                    now = datetime.now(timezone.utc)
                    due_index = next((index for index, entry in enumerate(self.queue)
                                      if not entry.get("scheduled_at") or datetime.fromisoformat(entry["scheduled_at"]) <= now), None)
                    if due_index is None:
                        due_time = min(datetime.fromisoformat(entry["scheduled_at"]) for entry in self.queue)
                        self.changed.wait(timeout=min(0.5, max(0.1, (due_time - now).total_seconds())))
                        continue
                    item = self.queue[due_index]
                    del self.queue[due_index]
                    try:
                        self._start_process(item)
                    except Exception:
                        item["status"] = "failed"
                        self.current = item
                        self.last_exit_code = -1
                        continue
                process = self.process
            while process.poll() is None:
                with self.changed:
                    self.changed.wait(timeout=0.5)
                    if self.stopping:
                        break
            with self.lock:
                exit_code = process.poll()
                if exit_code is None:
                    try:
                        exit_code = process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        exit_code = process.wait()
                self.last_exit_code = exit_code
                finished = self.current
                self.process = None
                self.current = None
                should_loop = exit_code == 0 and not self.stopping and finished and finished.get("task") == "main"
                self.stopping = False
            delay = self._loop_delay(finished) if should_loop else None
            if delay is not None and finished:
                finished["status"] = "queued"
                finished["scheduled_at"] = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
                with self.changed:
                    self.queue.appendleft(finished)
                    self.changed.notify_all()

    def stop(self):
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                return False
            self.stopping = True
            self.process.terminate()
            self.changed.notify_all()
            return True

    def shutdown(self):
        self.stop()
        with self.changed:
            self.queue.clear()
            self.changed.notify_all()


supervisor = Supervisor()


def _handler_class(token):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self):
            return not token or self.headers.get("Authorization") == f"Bearer {token}"

        def _body(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024 * 1024:
                raise ValueError("请求体不能超过 1 MiB")
            data = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("请求体必须是 JSON 对象")
            return data

        def do_GET(self):
            if urlparse(self.path).path != "/health" and not self._authorized():
                return self._send(401, {"error": "未授权"})
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/health":
                return self._send(200, {"status": "ok"})
            if path == "/api/status":
                return self._send(200, supervisor.status())
            if path == "/api/tasks":
                from utils.tasks import AVAILABLE_TASKS
                return self._send(200, {"tasks": AVAILABLE_TASKS})
            if path == "/api/modes":
                return self._send(200, {
                    "modes": ["api", "cli"],
                    "default": "api",
                    "startup_task": os.environ.get("MARCH7TH_SUPERVISOR_STARTUP_TASK", "main"),
                    "no_run_immediately": os.environ.get("MARCH7TH_SUPERVISOR_NO_RUN_IMMEDIATELY", "false").lower() in ("1", "true", "yes"),
                    "startup_task_id": os.environ.get("MARCH7TH_SUPERVISOR_STARTUP_TASK", "main"),
                })
            if path == "/api/workflows":
                from module.workflow import list_workflow_names
                return self._send(200, {"workflows": list_workflow_names()})
            if path == "/api/config":
                from module.config import cfg
                key = parse_qs(parsed.query).get("key", [None])[0]
                if key is not None:
                    if key not in cfg.config:
                        return self._send(404, {"error": "配置项不存在", "key": key})
                    return self._send(200, {"key": key, "value": cfg.get_value(key)})
                return self._send(200, {"config": copy.deepcopy(cfg.config)})
            if path.startswith("/api/config/"):
                from module.config import cfg
                key = unquote(path.removeprefix("/api/config/"))
                if key not in cfg.config:
                    return self._send(404, {"error": "配置项不存在", "key": key})
                return self._send(200, {"key": key, "value": cfg.get_value(key)})
            if path == "/api/config-keys":
                from module.config import cfg
                return self._send(200, {"keys": sorted(cfg.config)})
            if path == "/api/queue":
                return self._send(200, {"queue": supervisor.status()["queue"]})
            return self._send(404, {"error": "接口不存在"})

        def do_POST(self):
            if not self._authorized():
                return self._send(401, {"error": "未授权"})
            try:
                body = self._body()
                if urlparse(self.path).path == "/api/start":
                    item = supervisor.enqueue(
                        task=body.get("task"),
                        workflow_name=body.get("workflow_name"),
                        workflow_step_path=body.get("workflow_step_path"),
                        task_id=body.get("id"),
                    )
                    return self._send(202, item)
                if urlparse(self.path).path == "/api/queue":
                    item = supervisor.enqueue(
                        task=body.get("task"),
                        workflow_name=body.get("workflow_name"),
                        workflow_step_path=body.get("workflow_step_path"),
                        task_id=body.get("id"),
                    )
                    return self._send(202, item)
                if urlparse(self.path).path == "/api/stop":
                    stopped = supervisor.stop()
                    return self._send(200, {"stopped": stopped})
                return self._send(404, {"error": "接口不存在"})
            except ValueError as error:
                return self._send(400, {"error": str(error)})
            except RuntimeError as error:
                return self._send(409, {"error": str(error)})

        def do_DELETE(self):
            if not self._authorized():
                return self._send(401, {"error": "未授权"})
            path = urlparse(self.path).path
            if not path.startswith("/api/queue/"):
                return self._send(404, {"error": "接口不存在"})
            item = supervisor.cancel(unquote(path.removeprefix("/api/queue/")))
            if item is None:
                return self._send(404, {"error": "任务不在等待队列中"})
            return self._send(200, item)

        def do_PATCH(self):
            if not self._authorized():
                return self._send(401, {"error": "未授权"})
            try:
                if urlparse(self.path).path != "/api/config":
                    return self._send(404, {"error": "接口不存在"})
                values = self._body()
                from module.config import cfg
                if "key" in values:
                    key = values["key"]
                    if not isinstance(key, str) or key not in cfg.config:
                        return self._send(404, {"error": "配置项不存在", "key": key})
                    return self._send(200, {"key": key, "value": cfg.get_value(key)})
                if not values:
                    return self._send(400, {"error": "请求体不能为空"})
                unknown = set(values) - set(cfg.config)
                if unknown:
                    return self._send(400, {"error": "包含未知配置项", "keys": sorted(unknown)})
                cfg.set_values(values)
                return self._send(200, {"updated": sorted(values)})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                return self._send(400, {"error": str(error)})

        def log_message(self, format, *args):
            return

    return Handler


def run(argv=None):
    parser = argparse.ArgumentParser(prog="supervisor", description="March7th Assistant 监管程序")
    no_run_immediately = os.environ.get("MARCH7TH_SUPERVISOR_NO_RUN_IMMEDIATELY", "false").lower() in ("1", "true", "yes")
    parser.add_argument("--startup-task", default=os.environ.get("MARCH7TH_SUPERVISOR_STARTUP_TASK", "main"),
                        help="监管程序启动时自动排入的任务 ID，默认 main；空字符串表示不自动启动")
    parser.add_argument("--no-run-immediately", dest="no_run_immediately", action="store_true",
                        help="首轮任务延迟到配置项 scheduled_time")
    parser.add_argument("--run-immediately", dest="no_run_immediately", action="store_false",
                        help="首轮任务立即运行")
    parser.set_defaults(no_run_immediately=no_run_immediately)
    args = parser.parse_args(argv)
    host = os.environ.get("MARCH7TH_API_HOST", "127.0.0.1")
    port = int(os.environ.get("MARCH7TH_API_PORT", "8765"))
    token = os.environ.get("MARCH7TH_API_TOKEN", "")
    if host not in ("127.0.0.1", "localhost", "::1", "localhost") and not token:
        raise RuntimeError("API 绑定非本机地址时必须设置 MARCH7TH_API_TOKEN")
    if args.startup_task:
        supervisor.enqueue_startup_task(args.startup_task, args.no_run_immediately)
    server = ThreadingHTTPServer((host, port), _handler_class(token))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        supervisor.shutdown()
        server.server_close()
