"""本机 Agent 接管会话。仅依赖标准库与 psutil，不加载游戏、GUI 或模型。"""

from contextlib import contextmanager
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import secrets
import tempfile
import time
import uuid

import psutil

from utils.agent_decision import DecisionCancelled, MAX_RESPONSE_BYTES, validate_decision_answer


def decision_mode(cfg):
    mode = cfg.get_value("divergent_decision_mode", "auto")
    if mode == "auto":
        return "command" if cfg.get_value("divergent_decision_command", []) else "connected"
    if mode not in ("command", "connected"):
        raise ValueError("Agent 接入方式无效")
    return mode


def _read(path):
    for attempt in range(5):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(.02)


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".agent-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, allow_nan=False)
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(.02)
    finally:
        Path(temporary).unlink(missing_ok=True)


class AgentSession:
    def __init__(self, directory=None, timeout=60):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError("Agent 等待时间无效")
        self.directory = Path(directory or "logs/agent_connection").resolve()
        self.queue = self.directory / "queue"
        self.state_path = self.directory / "connection.json"
        self.ttl = max(90, timeout + 30)

    @contextmanager
    def _lock(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "connection.lock").open("a+b") as stream:
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            deadline = time.monotonic() + 2
            while True:
                try:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Agent 会话正在被其他进程操作")
                    time.sleep(.01)
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _alive(pid, created):
        try:
            process = psutil.Process(pid)
            return process.is_running() and abs(process.create_time() - created) < .01
        except (psutil.Error, TypeError):
            return False

    def _active(self, state):
        return bool(state and state.get("session_id") and not state.get("revoked")
                    and time.time() < state["expires_at"]
                    and (not state.get("owner_pid") or self._alive(state["owner_pid"], state["owner_created_at"])))

    def _authenticate(self, state, session_id, token):
        if (not self._active(state) or state["session_id"] != session_id or not isinstance(token, str)
                or not hmac.compare_digest(state["token_hash"], hashlib.sha256(token.encode()).hexdigest())):
            raise ValueError("接管会话无效、已断开或已过期，请重新连接")

    def is_current(self, session_id):
        state = _read(self.state_path)
        return self._active(state) and state["session_id"] == session_id

    def _renew(self, state):
        state.update(last_activity=time.time(), expires_at=time.time() + self.ttl)
        _write(self.state_path, state)

    def connect(self, client_name, session_label="", *, owner=None):
        if (not isinstance(client_name, str) or not client_name.strip() or len(client_name) > 80
                or not isinstance(session_label, str) or len(session_label) > 160):
            raise ValueError("请提供有效的客户端名称与会话标签")
        with self._lock():
            previous = _read(self.state_path)
            if self._active(previous):
                raise ValueError("已有 Agent 接管，请先由原会话或 GUI 断开")
            token = secrets.token_urlsafe(32)
            state = {"schema": 1, "session_id": uuid.uuid4().hex,
                     "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                     "client_name": client_name.strip(), "session_label": session_label,
                     "connected_at": time.time(), "revoked": False,
                     "owner_pid": owner.pid if owner else None,
                     "owner_created_at": owner.create_time() if owner else None}
            self._renew(state)
            self._clean()
            return {"session_id": state["session_id"], "token": token, "lease_seconds": self.ttl}

    def disconnect(self, session_id=None, token=None, *, local=False):
        with self._lock():
            state = _read(self.state_path)
            if not state or (local and not state.get("session_id")):
                return {"disconnected": True}
            if not local:
                self._authenticate(state, session_id, token)
            state.update(revoked=True, last_fallback="disconnected")
            _write(self.state_path, state)
            self._clean()
            return {"disconnected": True}

    def _request_path(self, request_id):
        if not isinstance(request_id, str) or len(request_id) != 32 or any(c not in "0123456789abcdef" for c in request_id):
            raise ValueError("请求编号无效")
        return self.queue / f"{request_id}.request.json"

    def _valid_request(self, envelope, state):
        return bool(self._active(state) and envelope and envelope.get("session_id") == state["session_id"]
                    and time.time() < envelope["expires_at"]
                    and self._alive(envelope["pid"], envelope["process_created_at"]))

    def _clean(self):
        state = _read(self.state_path)
        for path in self.queue.glob("*.request.json"):
            try:
                if not self._valid_request(_read(path), state):
                    path.unlink(missing_ok=True)
                    path.with_name(path.name.replace(".request.", ".response.")).unlink(missing_ok=True)
            except (ValueError, KeyError, TypeError):
                path.unlink(missing_ok=True)
        for path in self.queue.glob("*.response.json"):
            if not path.with_name(path.name.replace(".response.", ".request.")).exists():
                path.unlink(missing_ok=True)

    def status(self):
        # 只读查询不续期，不写入令牌或伪造心跳。
        state = _read(self.state_path) or {}
        connected = self._active(state)
        pending = []
        for path in self.queue.glob("*.request.json"):
            try:
                envelope = _read(path)
                if self._valid_request(envelope, state) and not path.with_name(path.name.replace(".request.", ".response.")).exists():
                    pending.append({"request_id": envelope["request"]["request_id"],
                                    "kind": envelope["request"].get("kind"), "expires_at": envelope["expires_at"]})
            except (ValueError, KeyError, TypeError):
                continue
        result = {key: state.get(key) for key in ("client_name", "session_label", "connected_at", "last_activity", "expires_at", "last_fallback")}
        result.update(state="waiting" if connected and pending else "idle" if connected else "disconnected" if state.get("session_id") else "unclaimed",
                      pending=pending)
        return result

    def wait(self, session_id, token, wait=20, *, cancelled=lambda: False):
        if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not math.isfinite(wait) or not 0 <= wait <= 20:
            raise ValueError("单次等待必须在 0 至 20 秒之间")
        deadline = time.monotonic() + wait
        while True:
            if cancelled():
                raise ValueError("等待已取消")
            with self._lock():
                state = _read(self.state_path)
                self._authenticate(state, session_id, token)
                self._renew(state)
                self._clean()
                pending = []
                for path in sorted(self.queue.glob("*.request.json")):
                    envelope = _read(path)
                    if self._valid_request(envelope, state) and not path.with_name(path.name.replace(".request.", ".response.")).exists():
                        pending.append(envelope["request"])
            if pending or time.monotonic() >= deadline:
                return {"pending": pending, "connection": self.status()}
            time.sleep(.1)

    def _owned_request(self, state, session_id, token, request_id):
        self._authenticate(state, session_id, token)
        envelope = _read(self._request_path(request_id))
        if not self._valid_request(envelope, state):
            raise ValueError("请求已失效或不属于本次接管")
        return envelope

    def respond(self, session_id, token, request_id, decision):
        with self._lock():
            state = _read(self.state_path)
            envelope = self._owned_request(state, session_id, token, request_id)
            if not isinstance(decision, dict):
                raise ValueError("决策必须是对象")
            answer = dict(decision)
            answer.setdefault("protocol_version", 1)
            answer.setdefault("request_id", request_id)
            answer = validate_decision_answer(envelope["request"], answer)
            if len(json.dumps(answer, ensure_ascii=False).encode("utf-8")) > MAX_RESPONSE_BYTES:
                raise ValueError("决策响应过大")
            path = self.queue / f"{request_id}.response.json"
            previous = _read(path)
            if previous is not None and previous != answer:
                raise ValueError("请求已有不同回复")
            _write(path, answer)
            self._renew(state)
            return {"accepted": True, "request_id": request_id}

    def observe(self, session_id, token, request_id, observation_id):
        with self._lock():
            state = _read(self.state_path)
            envelope = self._owned_request(state, session_id, token, request_id)
            observations = envelope["request"].get("build_state", {}).get("observations", [])
            frame = next((frame for frame in observations if frame["id"] == observation_id), None)
            if frame is None:
                raise ValueError("观察编号不属于当前请求")
            path = Path(frame["image_path"]).resolve()
            allowed = (self.directory.parent / "agent_decisions").resolve()
            if not path.is_relative_to(allowed) or path.suffix.lower() != ".png":
                raise ValueError("观察不属于小助手截图目录")
            return frame, path.read_bytes()

    def request(self, timeout, request, *, cancelled=lambda: False):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError("决策超时无效")
        if cancelled():
            raise DecisionCancelled()
        deadline = time.monotonic() + timeout
        payload = dict(request, protocol_version=1, request_id=uuid.uuid4().hex, expires_at=time.time() + timeout)
        path = self._request_path(payload["request_id"])
        response_path = path.with_name(path.name.replace(".request.", ".response."))
        with self._lock():
            state = _read(self.state_path) or {}
            if not self._active(state):
                state["last_fallback"] = "not_connected"
                _write(self.state_path, state)
                return None
            owner = psutil.Process()
            envelope = {"session_id": state["session_id"], "request": payload,
                        "expires_at": payload["expires_at"], "pid": owner.pid, "process_created_at": owner.create_time()}
            _write(path, envelope)
        fallback = "timeout"
        try:
            while time.monotonic() < deadline:
                if cancelled():
                    fallback = "cancelled"
                    raise DecisionCancelled()
                with self._lock():
                    state = _read(self.state_path)
                    if not self._valid_request(envelope, state):
                        fallback = "timeout" if time.time() >= envelope["expires_at"] else "disconnected"
                        return None
                    answer = _read(response_path)
                    if answer is not None:
                        fallback = ""
                        return dict(validate_decision_answer(payload, answer), _connection_id=envelope["session_id"])
                time.sleep(.05)
            return None
        finally:
            with self._lock():
                path.unlink(missing_ok=True)
                response_path.unlink(missing_ok=True)
                if fallback:
                    state = _read(self.state_path) or {}
                    if state.get("session_id") == envelope["session_id"]:
                        state["last_fallback"] = fallback
                        _write(self.state_path, state)
