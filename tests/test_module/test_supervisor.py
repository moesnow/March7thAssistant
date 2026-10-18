import json
import threading
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from module.supervisor import Supervisor, _handler_class


@pytest.fixture
def api_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler_class("test-token"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()
    server.server_close()


def request_json(url, path, method="GET", payload=None, authorized=True):
    headers = {}
    data = None
    if authorized:
        headers["Authorization"] = "Bearer test-token"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url + path, data=data, headers=headers, method=method)
    try:
        response = urlopen(request)
    except HTTPError as error:
        response = error
    return response.status, json.loads(response.read())


def test_api_requires_token(api_server):
    status, body = request_json(api_server, "/api/status", authorized=False)
    assert status == 401
    assert body["error"] == "未授权"


def test_api_lists_tasks(api_server):
    status, body = request_json(api_server, "/api/tasks")
    assert status == 200
    assert "daily" in body["tasks"]


def test_config_patch_rejects_unknown_keys(api_server):
    status, body = request_json(api_server, "/api/config", method="PATCH", payload={"not_a_setting": True})
    assert status == 400
    assert body["keys"] == ["not_a_setting"]


def test_start_requires_exactly_one_mode():
    manager = Supervisor(start_worker=False)
    with pytest.raises(ValueError):
        manager.enqueue()
    with pytest.raises(ValueError):
        manager.enqueue(task="daily", workflow_name="anything")
    with pytest.raises(ValueError):
        manager.enqueue(task="not-a-task")


def test_queue_accepts_id_and_cancels_pending(monkeypatch):
    manager = Supervisor(start_worker=False)
    monkeypatch.setattr("module.workflow.list_workflow_names", lambda: [])
    item = manager.enqueue(task="daily", task_id="test-1")
    assert item["id"] == "test-1"
    assert item["status"] == "queued"
    cancelled = manager.cancel("test-1")
    assert cancelled["status"] == "cancelled"
    assert manager.cancel("test-1") is None


def test_queue_rejects_duplicate_id(monkeypatch):
    manager = Supervisor(start_worker=False)
    monkeypatch.setattr("module.workflow.list_workflow_names", lambda: [])
    manager.enqueue(task="daily", task_id="duplicate")
    with pytest.raises(ValueError, match="已存在"):
        manager.enqueue(task="power", task_id="duplicate")


def test_startup_task_is_queued_immediately(monkeypatch):
    manager = Supervisor(start_worker=False)
    item = manager.enqueue_startup_task()
    assert item["task"] == "main"
    assert item["id"] == "startup-main"
    assert item["scheduled_at"] is None
    assert manager.status()["queue"][0]["id"] == "startup-main"


def test_startup_task_can_be_delayed(monkeypatch):
    manager = Supervisor(start_worker=False)
    monkeypatch.setattr(Supervisor, "_seconds_until_scheduled_time", staticmethod(lambda: 3600))
    item = manager.enqueue_startup_task(no_run_immediately=True)
    assert item["scheduled_at"] is not None
    assert datetime.fromisoformat(item["scheduled_at"]) > datetime.now(timezone.utc)


def test_api_returns_all_tasks_and_config_key(api_server, monkeypatch):
    from utils.tasks import AVAILABLE_TASKS
    from module.supervisor import supervisor

    monkeypatch.setattr(supervisor, "enqueue", lambda **kwargs: kwargs)
    status, body = request_json(api_server, "/api/tasks")
    assert status == 200
    assert body["tasks"] == AVAILABLE_TASKS
    assert len(body["tasks"]) == len(AVAILABLE_TASKS)

    status, body = request_json(api_server, "/api/start", method="POST", payload={"task": "daily", "id": "ps-check"})
    assert status == 202
    assert body["id"] == "ps-check"

    status, body = request_json(api_server, "/api/config?key=log_level")
    assert status == 404
    assert body["key"] == "log_level"


def test_config_key_can_be_queried(api_server, monkeypatch):
    from module.config import cfg

    monkeypatch.setitem(cfg.config, "log_level", "INFO")
    status, body = request_json(api_server, "/api/config/log_level")
    assert status == 200
    assert body == {"key": "log_level", "value": "INFO"}


def test_cancel_queued_item_endpoint(api_server, monkeypatch):
    from module.supervisor import supervisor

    monkeypatch.setattr(supervisor, "cancel", lambda task_id: {"id": task_id, "status": "cancelled"})
    status, body = request_json(api_server, "/api/queue/queued-1", method="DELETE")
    assert status == 200
    assert body["status"] == "cancelled"
