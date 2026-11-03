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
        self.clients_path = self.directory / "clients.json"
        self.ttl = max(90, timeout + 30)

    def _clients(self):
        try:
            clients = _read(self.clients_path) or []
            if not isinstance(clients, list):
                return []
            return [item for item in clients if isinstance(item, dict)
                    and isinstance(item.get("id"), str) and len(item["id"]) == 32
                    and isinstance(item.get("client_name"), str) and item["client_name"]
                    and isinstance(item.get("client_version"), str)
                    and type(item.get("connected_at")) in (int, float) and math.isfinite(item["connected_at"])
                    and self._alive(item.get("pid"), item.get("created_at"))]
        except (OSError, ValueError, TypeError):
            return []

    def register_client(self, client_name, client_version="", *, owner=None):
        """登记真实 MCP 握手；仅表示客户端通道存在，不接管、不续期。"""
        owner = owner or psutil.Process()
        name = str(client_name or "MCP client").strip()[:80] or "MCP client"
        entry = {"id": uuid.uuid4().hex, "client_name": name,
                 "client_version": str(client_version or "")[:80], "connected_at": time.time(),
                 "pid": owner.pid, "created_at": owner.create_time()}
        with self._lock():
            _write(self.clients_path, self._clients() + [entry])
        return entry["id"]

    def unregister_client(self, client_id):
        if client_id:
            with self._lock():
                _write(self.clients_path, [item for item in self._clients() if item["id"] != client_id])

    @contextmanager
    def _lock(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "connection.lock").open("a+b") as stream:
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
                # Windows 允许锁定 EOF 之后的范围。首字节也须在持锁后
                # 初始化，避免另一个连接已持锁时并发 flush 触发拒绝访问。
                if os.fstat(stream.fileno()).st_size == 0:
                    stream.write(b"\0")
                    stream.flush()
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
        except (psutil.Error, TypeError, ValueError):
            return False

    def _state(self):
        try:
            state = _read(self.state_path)
        except (ValueError, RecursionError):
            return {}  # 损坏的本机缓存不能授予控制权，也不能阻止重新接管。
        return state if isinstance(state, dict) else {}

    def _active(self, state):
        return bool(isinstance(state, dict) and isinstance(state.get("session_id"), str)
                    and len(state["session_id"]) == 32 and not state.get("revoked")
                    and all(c in "0123456789abcdef" for c in state["session_id"])
                    and isinstance(state.get("token_hash"), str) and len(state["token_hash"]) == 64
                    and all(c in "0123456789abcdef" for c in state["token_hash"])
                    and type(state.get("expires_at")) in (int, float) and math.isfinite(state["expires_at"])
                    and time.time() < state["expires_at"]
                    and (state.get("owner_pid") is None or self._alive(state["owner_pid"], state.get("owner_created_at"))))

    def _authenticate(self, state, session_id, token):
        if (not self._active(state) or state["session_id"] != session_id or not isinstance(token, str)
                or not hmac.compare_digest(state["token_hash"], hashlib.sha256(token.encode()).hexdigest())):
            raise ValueError("接管会话无效、已断开或已过期，请重新连接")

    def is_current(self, session_id):
        state = self._state()
        return self._active(state) and state["session_id"] == session_id

    def has_controller(self):
        """只检查有效接管，不续期或枚举客户端/请求。"""
        return self._active(self._state())

    def _renew(self, state):
        now = time.time()
        expiry = now + self.ttl
        # 已运行的 MCP 进程可能早于 GUI 修改节点超时。只在真实 Agent
        # 联系时按当前待处理节点延长租约，不能由游戏线程伪造心跳。
        for path in self.queue.glob("*.request.json"):
            try:
                request = _read(path)
                if self._valid_request(request, state):
                    expiry = max(expiry, request["expires_at"] + 30)
            except (ValueError, KeyError, TypeError):
                continue
        state.update(last_activity=now, expires_at=expiry)
        gameplay = self._gameplay()
        if gameplay and not gameplay["paused"]:
            state.update(gameplay_id=gameplay["id"], gameplay_epoch=gameplay["epoch"], last_game_activity=time.time())
        _write(self.state_path, state)

    @contextmanager
    def gameplay(self, game_pid):
        """仅由实际差分宇宙对局的作用域登记；退出、异常或进程结束均不再计时。"""
        activity = None
        try:
            game = psutil.Process(game_pid) if game_pid else None
            if game is not None and game.is_running():
                owner = psutil.Process()
                activity = {"id": uuid.uuid4().hex, "pid": owner.pid, "created_at": owner.create_time(),
                            "game_pid": game.pid, "game_created_at": game.create_time(),
                            "control_file": os.environ.get("MARCH7TH_CONTROL_FILE")}
        except psutil.Error:
            pass
        if activity is None:
            yield
            return
        path = self.directory / "gameplay.json"
        with self._lock():
            _write(path, activity)
        try:
            yield
        finally:
            with self._lock():
                current = _read(path)
                if current and current.get("id") == activity["id"]:
                    path.unlink(missing_ok=True)

    def _gameplay(self):
        try:
            activity = _read(self.directory / "gameplay.json")
        except (ValueError, RecursionError):
            return None
        if (not isinstance(activity, dict) or not isinstance(activity.get("id"), str)
                or not self._alive(activity.get("pid"), activity.get("created_at"))
                or not self._alive(activity.get("game_pid"), activity.get("game_created_at"))):
            return None
        control = activity.get("control_file")
        if control is not None and not isinstance(control, str):
            return None
        activity["epoch"] = 0
        activity["paused"] = False
        if control:
            from utils.pause import read_state, STATE_PAUSED, STATE_PAUSING, STATE_STOPPING
            if read_state(control) in (STATE_PAUSED, STATE_PAUSING, STATE_STOPPING):
                activity["paused"] = True
            try:
                activity["epoch"] = Path(control + ".state").stat().st_mtime_ns
            except FileNotFoundError:
                pass
        return activity

    def connect(self, client_name, session_label="", *, owner=None, client_id=None):
        if (not isinstance(client_name, str) or not client_name.strip() or len(client_name) > 80
                or not isinstance(session_label, str) or len(session_label) > 160):
            raise ValueError("请提供有效的客户端名称与会话标签")
        with self._lock():
            previous = self._state()
            if self._active(previous):
                raise ValueError("已有 Agent 接管，请先由原会话或 GUI 断开")
            token = secrets.token_urlsafe(32)
            state = {"schema": 1, "session_id": uuid.uuid4().hex,
                     "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                     "client_name": client_name.strip(), "session_label": session_label,
                     "client_id": client_id,
                     "connected_at": time.time(), "revoked": False,
                     "owner_pid": owner.pid if owner else None,
                     "owner_created_at": owner.create_time() if owner else None}
            self._renew(state)
            self._clean()
            return {"session_id": state["session_id"], "token": token, "lease_seconds": self.ttl}

    def disconnect(self, session_id=None, token=None, *, local=False):
        with self._lock():
            state = self._state()
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
        state = self._state()
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
        state = self._state()
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
        gameplay = self._gameplay()
        running = bool(gameplay and not gameplay["paused"])
        last_activity = (state.get("last_game_activity") if connected and running
                         and state.get("gameplay_id") == gameplay["id"]
                         and state.get("gameplay_epoch") == gameplay["epoch"] else None)
        result = {key: state.get(key) for key in ("client_name", "session_label", "connected_at", "expires_at", "last_fallback")}
        result.update(last_activity=last_activity, divergent_running=running,
                      divergent_paused=bool(gameplay and gameplay["paused"]))
        result.update(state="waiting" if connected and pending else "idle" if connected else "disconnected" if state.get("session_id") else "unclaimed",
                      pending=pending)
        result["clients"] = [dict(client_name=item["client_name"], client_version=item["client_version"],
                                  connected_at=item["connected_at"],
                                  has_control=bool(connected and state.get("client_id") == item["id"]))
                             for item in self._clients()]
        return result

    def wait(self, session_id, token, wait=20, *, cancelled=lambda: False):
        if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not math.isfinite(wait) or not 0 <= wait <= 20:
            raise ValueError("单次等待必须在 0 至 20 秒之间")
        deadline = time.monotonic() + wait
        renewed = False
        while True:
            if cancelled():
                raise ValueError("等待已取消")
            with self._lock():
                state = self._state()
                self._authenticate(state, session_id, token)
                if not renewed:
                    self._renew(state)
                    renewed = True
                self._clean()
                pending = []
                for path in sorted(self.queue.glob("*.request.json")):
                    envelope = _read(path)
                    if self._valid_request(envelope, state) and not path.with_name(path.name.replace(".request.", ".response.")).exists():
                        pending.append(envelope["request"])
            if pending or time.monotonic() >= deadline:
                with self._lock():
                    state = self._state()
                    self._authenticate(state, session_id, token)
                    self._renew(state)
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
            state = self._state()
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
            self._renew(state)
            _write(path, answer)
            return {"accepted": True, "request_id": request_id}

    def observe(self, session_id, token, request_id, observation_id):
        with self._lock():
            state = self._state()
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
            state = self._state()
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
                    state = self._state()
                    if not self._valid_request(envelope, state):
                        fallback = "timeout" if time.time() >= envelope["expires_at"] else "disconnected"
                        return None
                    answer = _read(response_path)
                    if answer is not None:
                        answer = validate_decision_answer(payload, answer)
                        state.pop("last_fallback", None)
                        # 游戏线程消费回执不是 Agent 活动，不能延长租约或更新时间。
                        _write(self.state_path, state)
                        fallback = ""
                        return dict(answer, _connection_id=envelope["session_id"])
                time.sleep(.05)
            return None
        finally:
            with self._lock():
                path.unlink(missing_ok=True)
                response_path.unlink(missing_ok=True)
                if fallback:
                    state = self._state()
                    if state.get("session_id") == envelope["session_id"]:
                        state["last_fallback"] = fallback
                        _write(self.state_path, state)
