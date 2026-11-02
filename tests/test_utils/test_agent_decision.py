import importlib.util
import json
from pathlib import Path
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import psutil
import pytest

from utils.agent_decision import DecisionCancelled, request_decision


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = ROOT / "assets/agent/examples/decision_bridge.py"
SPEC = importlib.util.spec_from_file_location("decision_bridge_under_test", BRIDGE_PATH)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)
REQUEST = {"kind": "blessing", "candidates": [{"id": "text-1", "text": "防御"}, {"id": "text-2", "text": "终结技"}]}


def worker(tmp_path, body):
    path = tmp_path / "worker.py"
    path.write_text("import json, sys, time\nrequest = json.load(sys.stdin)\n" + body, encoding="utf-8")
    return [sys.executable, str(path)]


def test_real_file_bridge_round_trip(tmp_path):
    """真实子进程等待候选，任意外部 Agent 通过同一文件接口回复。"""
    queue = tmp_path / "queue"
    command = [sys.executable, str(BRIDGE_PATH), "serve", "--directory", str(queue), "--timeout", "5"]
    with ThreadPoolExecutor() as pool:
        future = pool.submit(request_decision, command, 8, REQUEST)
        deadline = time.monotonic() + 5
        paths = []
        while not paths and time.monotonic() < deadline:
            paths = list(queue.glob("*.request.json"))
            time.sleep(.02)
        assert paths, "桥接程序没有发布请求"
        envelope = json.loads(paths[0].read_text(encoding="utf-8"))
        assert bridge.active(envelope)
        assert envelope["request"]["candidates"] == REQUEST["candidates"]
        bridge.respond(queue, envelope["request"]["request_id"], "text-2")
        assert future.result(timeout=5) == "text-2"
    assert not list(queue.glob("*.json"))


@pytest.mark.parametrize("answer", [
    "[]", "{'protocol_version': True, 'request_id': request['request_id'], 'candidate_id': 'text-1'}",
    "{'protocol_version': 2, 'request_id': request['request_id'], 'candidate_id': 'text-1'}",
    "{'protocol_version': 1, 'request_id': 'stale', 'candidate_id': 'text-1'}",
    "{'protocol_version': 1, 'request_id': request['request_id'], 'candidate_id': 'unknown'}",
    "{'protocol_version': 1, 'request_id': request['request_id'], 'candidate_id': 1}",
    "{'protocol_version': 1, 'request_id': request['request_id']}",
])
def test_invalid_response_rejected(tmp_path, answer):
    command = worker(tmp_path, f"print(json.dumps({answer}))\n")
    with pytest.raises(ValueError):
        request_decision(command, 3, REQUEST)


def test_explicit_decline(tmp_path):
    command = worker(tmp_path, "print(json.dumps(dict(protocol_version=1, request_id=request['request_id'], candidate_id=None)))\n")
    assert request_decision(command, 3, REQUEST) is None


@pytest.mark.parametrize("body", ["print('not json')\n", "print('x' * 70000)\n", "sys.exit(1)\n"])
def test_failed_or_oversized_output_rejected(tmp_path, body):
    with pytest.raises(ValueError):
        request_decision(worker(tmp_path, body), 3, REQUEST)


def test_timeout_terminates_program(tmp_path):
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        request_decision(worker(tmp_path, "time.sleep(30)\n"), .15, REQUEST)
    assert time.monotonic() - started < 4


def test_cancel_terminates_descendants(tmp_path):
    child_record = tmp_path / "child.json"
    body = (
        "import subprocess, psutil\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"open({str(child_record)!r}, 'w').write(json.dumps([child.pid, psutil.Process(child.pid).create_time()]))\n"
        "time.sleep(30)\n"
    )
    with pytest.raises(DecisionCancelled):
        request_decision(worker(tmp_path, body), 8, REQUEST, cancelled=child_record.exists)
    child_pid, created = json.loads(child_record.read_text())
    try:
        child = psutil.Process(child_pid)
        assert child.create_time() != created or not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        pass


@pytest.mark.parametrize("command,timeout", [("echo", 2), ([], 2), (["python"], 0), (["python"], float('nan'))])
def test_invalid_configuration_does_not_start_process(command, timeout):
    with pytest.raises(ValueError):
        request_decision(command, timeout, REQUEST)


def test_expired_request_cannot_be_answered(tmp_path):
    request_id = "a" * 32
    bridge.atomic_json(bridge.request_path(tmp_path, request_id), {"expires_at": 0, "request": dict(REQUEST, request_id=request_id)})
    with pytest.raises(ValueError):
        bridge.respond(tmp_path, request_id, "text-1")
    assert not list(tmp_path.glob("*.response.json"))


def test_request_id_cannot_escape_queue(tmp_path):
    with pytest.raises(ValueError):
        bridge.request_path(tmp_path, "../../other-file")


def test_pending_cleans_cancelled_requests(tmp_path, capsys):
    request_id = "b" * 32
    pending = bridge.request_path(tmp_path, request_id)
    response = tmp_path / f"{request_id}.response.json"
    bridge.atomic_json(pending, {"expires_at": 0, "request": dict(REQUEST, request_id=request_id)})
    bridge.atomic_json(response, {"candidate_id": "text-1"})
    bridge.pending_requests(tmp_path, 0)
    assert json.loads(capsys.readouterr().out) == {"pending": []}
    assert not pending.exists()
    assert not response.exists()
