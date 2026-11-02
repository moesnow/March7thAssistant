import base64
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

from PIL import Image
import pytest

from utils.agent_decision import DecisionCancelled
from utils.agent_session import AgentSession, _read, _write, decision_mode
from utils.agent_service import dispatch


@pytest.fixture
def store(tmp_path):
    return AgentSession(tmp_path / "connection", timeout=120)


def credentials(store):
    value = store.connect("Test Agent", "current chat")
    return {key: value[key] for key in ("session_id", "token")}


def find_request(store, auth):
    return store.wait(**auth, wait=2)["pending"][0]


def test_connection_status_does_not_renew_or_expose_credentials(store):
    assert store.status()["state"] == "unclaimed"
    auth = credentials(store)
    original = _read(store.state_path)
    assert original["expires_at"] - original["last_activity"] == pytest.approx(150)
    for _ in range(3):
        state = store.status()
        assert state["state"] == "idle"
        assert "token" not in json.dumps(state)
        assert auth["session_id"] not in json.dumps(state)
    assert _read(store.state_path) == original


def test_concurrent_connections_have_one_owner(store):
    def connect(_):
        try:
            return credentials(store)
        except ValueError:
            return None
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(connect, range(8)))
    assert len([value for value in results if value]) == 1


def test_cross_process_connections_have_one_owner(store):
    code = ("import json; from utils.agent_session import AgentSession; "
            + "store=AgentSession(" + repr(str(store.directory)) + "); "
            + "print(json.dumps(store.connect('process')))" )
    def connect(_):
        return subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, timeout=10).returncode
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(connect, range(4)))
    assert results.count(0) == 1


def test_foreign_session_cannot_disconnect_or_reply(store):
    auth = credentials(store)
    with pytest.raises(ValueError):
        store.disconnect(auth["session_id"], "wrong token")
    assert store.status()["state"] == "idle"
    store.disconnect(local=True)
    with pytest.raises(ValueError):
        store.wait(**auth, wait=0)
    fresh = credentials(store)
    assert fresh["session_id"] != auth["session_id"]


def test_lease_expiry_requires_new_connection(store):
    auth = credentials(store)
    state = _read(store.state_path)
    state["expires_at"] = time.time() - 1
    _write(store.state_path, state)
    assert store.status()["state"] == "disconnected"
    with pytest.raises(ValueError):
        store.wait(**auth, wait=0)
    assert credentials(store)["session_id"] != auth["session_id"]


def test_unclaimed_node_falls_back_without_waiting(store):
    started = time.monotonic()
    assert store.request(120, {"candidates": [{"id": "a"}]}) is None
    assert time.monotonic() - started < .5
    assert store.status()["last_fallback"] == "not_connected"


def test_live_request_response_and_bounded_observation(store, tmp_path):
    auth = credentials(store)
    image = tmp_path / "agent_decisions/session/frame.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (80, 60)).save(image)
    packet = {"kind": "blessing", "candidates": [{"id": "a", "text": "test"}],
              "build_state": {"observations": [{"id": "frame-1", "image_path": str(image)}]}}
    with ThreadPoolExecutor() as pool:
        future = pool.submit(store.request, 5, packet)
        request = find_request(store, auth)
        assert store.status()["state"] == "waiting"
        frame, data = store.observe(**auth, request_id=request["request_id"], observation_id="frame-1")
        assert data.startswith(b"\x89PNG")
        assert frame["id"] == "frame-1"
        with pytest.raises(ValueError):
            store.observe(**auth, request_id=request["request_id"], observation_id="../../secret")
        store.respond(**auth, request_id=request["request_id"], decision={"candidate_id": "a", "reason": "fits team", "memory": {"goal": "team"}})
        assert future.result(timeout=3)["memory"] == {"goal": "team"}
    assert not list(store.queue.glob("*.json"))


def test_disconnect_during_request_returns_promptly_and_rejects_old_reply(store):
    auth = credentials(store)
    with ThreadPoolExecutor() as pool:
        future = pool.submit(store.request, 120, {"candidates": [{"id": "a"}]})
        request = find_request(store, auth)
        store.disconnect(local=True)
        fresh = credentials(store)
        assert future.result(timeout=2) is None
        for account in (auth, fresh):
            with pytest.raises(ValueError):
                store.respond(**account, request_id=request["request_id"], decision={"candidate_id": "a"})
    assert store.status()["state"] == "idle"


def test_timeout_and_cancellation_clear_requests(store):
    auth = credentials(store)
    assert store.request(.15, {"candidates": [{"id": "a"}]}) is None
    assert store.status()["last_fallback"] == "timeout"
    cancel = [False]
    with ThreadPoolExecutor() as pool:
        future = pool.submit(store.request, 5, {"candidates": [{"id": "a"}]}, cancelled=lambda: cancel[0])
        find_request(store, auth)
        cancel[0] = True
        with pytest.raises(DecisionCancelled):
            future.result(timeout=2)
    assert not list(store.queue.glob("*.json"))


def test_mcp_owner_death_marks_connection_disconnected(store):
    owner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    import psutil
    try:
        store.connect("MCP", owner=psutil.Process(owner.pid))
        assert store.status()["state"] == "idle"
    finally:
        owner.kill()
        owner.wait()
    assert store.status()["state"] == "disconnected"


def test_dispatch_uses_same_core_without_mcp(store):
    auth = dispatch(store, {"action": "connect", "client_name": "Desktop", "session_label": "this chat"})
    result = dispatch(store, dict(auth, action="wait", wait=0))
    assert result["pending"] == []
    assert dispatch(store, {"action": "status"})["client_name"] == "Desktop"
    assert dispatch(store, dict(auth, action="disconnect"))["disconnected"]


@pytest.mark.parametrize("values,expected", [({}, "connected"),
    ({"divergent_decision_command": ["legacy"]}, "command"),
    ({"divergent_decision_mode": "connected", "divergent_decision_command": ["legacy"]}, "connected")])
def test_legacy_mode_resolution(values, expected):
    assert decision_mode(SimpleNamespace(get_value=lambda key, default=None: values.get(key, default))) == expected


def test_cli_session_stdout_is_json_without_gui_imports():
    result = subprocess.run([sys.executable, "-B", "main.py", "--agent-session"], input='{"action":"status"}',
                            capture_output=True, text=True, encoding="utf-8", timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["state"] in ("unclaimed", "idle", "waiting", "disconnected")
    assert "Fluent" not in result.stdout
