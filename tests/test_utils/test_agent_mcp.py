from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp_types import Implementation
from PIL import Image
import pytest

from utils.agent_session import AgentSession
from utils.agent_service import connection_config, session_store

ROOT = Path(__file__).resolve().parents[2]


def unpack(result):
    assert not result.is_error, result
    return json.loads(next(content.text for content in result.content if content.type == "text"))


def test_client_close_during_pending_decision_releases_without_waiting_for_timeout(tmp_path):
    store = AgentSession(tmp_path / "connection")
    code = "from utils.agent_service import run_mcp; from utils.agent_session import AgentSession; run_mcp(AgentSession(" + repr(str(store.directory)) + "))"
    params = StdioServerParameters(command=sys.executable, args=["-B", "-c", code], cwd=str(Path.cwd()))
    async def scenario():
        with ThreadPoolExecutor() as pool:
            async with stdio_client(params) as streams:
                async with ClientSession(*streams, client_info=Implementation(name="Closing client", version="1")) as client:
                    await client.initialize()
                    result = await client.call_tool("agent_connect", {"session_label": "pending shutdown"})
                    assert not result.is_error
                    claim = json.loads(result.content[0].text)
                    auth = {k: claim[k] for k in ("session_id", "token")}
                    future = pool.submit(store.request, 30, {"kind": "shutdown_test", "candidates": [{"id": "ack"}]})
                    waiting = await client.call_tool("agent_wait", dict(auth, wait=2))
                    assert json.loads(waiting.content[0].text)["pending"]
                    assert store.status()["state"] == "waiting"
            assert future.result(timeout=2) is None
            assert store.status()["state"] == "disconnected"
            assert store.status()["clients"] == []
    anyio.run(scenario)


def test_real_mcp_initialize_owner_observe_reply_and_client_close(tmp_path):
    directory = tmp_path / "connection"
    store = AgentSession(directory)
    image = tmp_path / "agent_decisions/session/frame.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (40, 30)).save(image)
    code = "from utils.agent_service import run_mcp; from utils.agent_session import AgentSession; run_mcp(AgentSession(" + repr(str(directory)) + "))"
    params = StdioServerParameters(command=sys.executable, args=["-B", "-c", code], cwd=str(Path.cwd()))

    async def scenario():
        async with stdio_client(params) as streams:
            async with ClientSession(*streams, client_info=Implementation(name="SDK test", version="1")) as client:
                await client.initialize()
                tools = await client.list_tools()
                assert {tool.name for tool in tools.tools} == {"agent_connect", "agent_status", "agent_wait", "agent_observe", "agent_respond", "agent_disconnect"}
                assert store.status()["state"] == "unclaimed"  # 初始化不是接管。
                assert store.status()["clients"][0]["client_name"] == "SDK test"
                assert not store.status()["clients"][0]["has_control"]
                auth = unpack(await client.call_tool("agent_connect", {"session_label": "this test"}))
                assert store.status()["client_name"] == "SDK test"
                auth = {key: auth[key] for key in ("session_id", "token")}
                with ThreadPoolExecutor() as pool:
                    future = pool.submit(store.request, 15, {"kind": "connection_test", "candidates": [{"id": "ack"}],
                                         "build_state": {"observations": [{"id": "frame-1", "image_path": str(image)}]}})
                    pending = unpack(await client.call_tool("agent_wait", dict(auth, wait=2)))["pending"][0]
                    request_id = pending["request_id"]
                    picture = await client.call_tool("agent_observe", dict(auth, request_id=request_id, observation_id="frame-1"))
                    assert not picture.is_error
                    assert any(content.type == "image" for content in picture.content)
                    accepted = unpack(await client.call_tool("agent_respond", dict(auth, request_id=request_id,
                                                    decision={"candidate_id": "ack", "reason": "test, no game action"})))
                    assert accepted["accepted"]
                    assert future.result(timeout=3)["candidate_id"] == "ack"
                unpack(await client.call_tool("agent_disconnect", auth))
                unpack(await client.call_tool("agent_connect", {"session_label": "reconnected chat"}))
                assert store.status()["state"] == "idle"
        assert store.status()["state"] == "disconnected"
        assert store.status()["clients"] == []

    anyio.run(scenario)


def test_different_mcp_clients_share_service_and_report_actual_owner(tmp_path):
    """通用客户端不靠 GUI 品牌选项接入，身份来自各自 initialize 元信息。"""
    store = AgentSession(tmp_path / "connection")
    code = "from utils.agent_service import run_mcp; from utils.agent_session import AgentSession; run_mcp(AgentSession(" + repr(str(store.directory)) + "))"
    params = StdioServerParameters(command=sys.executable, args=["-B", "-c", code], cwd=str(Path.cwd()))

    async def scenario():
        async with stdio_client(params) as streams_a, stdio_client(params) as streams_b:
            async with ClientSession(*streams_a, client_info=Implementation(name="Example Agent A", version="1")) as a, ClientSession(*streams_b, client_info=Implementation(name="自定义 Agent B", version="2")) as b:
                await a.initialize()
                await b.initialize()
                await a.list_tools()
                await b.list_tools()
                assert store.status()["state"] == "unclaimed"
                assert {c["client_name"] for c in store.status()["clients"]} == {"Example Agent A", "自定义 Agent B"}
                assert not any(c["has_control"] for c in store.status()["clients"])
                owner_a = unpack(await a.call_tool("agent_connect", {"session_label": "first chat"}))
                assert unpack(await b.call_tool("agent_status"))["client_name"] == "Example Agent A"
                rejected = await b.call_tool("agent_connect", {"session_label": "second chat"})
                assert rejected.is_error
                assert store.status()["client_name"] == "Example Agent A"
                credentials_a = {key: owner_a[key] for key in ("session_id", "token")}
                unpack(await a.call_tool("agent_disconnect", credentials_a))
                assert len(store.status()["clients"]) == 2
                assert not any(c["has_control"] for c in store.status()["clients"])
                owner_b = unpack(await b.call_tool("agent_connect", {"session_label": "second chat"}))
                status = unpack(await a.call_tool("agent_status"))
                assert status["client_name"] == "自定义 Agent B"
                assert status["session_label"] == "second chat"
                assert [c["client_name"] for c in status["clients"] if c["has_control"]] == ["自定义 Agent B"]
                credentials_b = {key: owner_b[key] for key in ("session_id", "token")}
                unpack(await b.call_tool("agent_wait", dict(credentials_b, wait=0)))
                unpack(await b.call_tool("agent_disconnect", credentials_b))
        assert store.status()["state"] == "disconnected"
        assert store.status()["clients"] == []

    anyio.run(scenario)


def test_pip_and_uv_both_install_mcp():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    expected = next(dep for dep in project["project"]["dependencies"] if dep.startswith("mcp=="))
    assert expected in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("raw", ["[]", "0", "false", "", "wrong: [unterminated"])
def test_invalid_configuration_is_reported_without_rewriting(tmp_path, monkeypatch, raw):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "config.yaml"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError, match="config.yaml"):
        session_store()
    assert path.read_text(encoding="utf-8") == raw


def test_config_export_uses_installation_not_callers_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, generic = connection_config()
    config = json.loads(generic)["mcpServers"]["march7th_assistant"]
    assert str(ROOT / "main.py") in config["args"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "新 安装目录" / "March7th Launcher.exe"))
    toml, generic = connection_config()
    parsed = json.loads(generic)["mcpServers"]["march7th_assistant"]
    assert Path(parsed["command"]) == tmp_path / "新 安装目录/m7a.exe"
    assert parsed["args"] == ["--agent-mcp"]
    assert tomllib.loads(toml)["mcp_servers"]["march7th_assistant"]["command"] == parsed["command"]


@pytest.fixture
def fresh_install(tmp_path):
    install = tmp_path / "其他用户 全新目录"
    (install / "utils").mkdir(parents=True)
    shutil.copyfile(ROOT / "main.py", install / "main.py")
    for name in ("__init__.py", "agent_session.py", "agent_service.py", "agent_decision.py", "console.py"):
        shutil.copyfile(ROOT / "utils" / name, install / "utils" / name)
    guides = Path("assets/agent/skills/march7th-assistant/references")
    (install / guides).mkdir(parents=True)
    for name in ("connections.md", "decisions.md", "strategy.md"):
        shutil.copyfile(ROOT / guides / name, install / guides / name)
    return install


def test_fresh_mcp_works_from_foreign_cwd_with_no_game_gui_or_local_file_tools(fresh_install, tmp_path):
    caller = tmp_path / "caller"
    caller.mkdir()
    params = StdioServerParameters(command=sys.executable, args=[str(fresh_install / "main.py"), "--agent-mcp"], cwd=str(caller))
    async def scenario():
        async with stdio_client(params) as streams:
            name = "Generic MCP client " + "x" * 100
            async with ClientSession(*streams, client_info=Implementation(name=name, version="1")) as client:
                await client.initialize()
                status = unpack(await client.call_tool("agent_status"))
                assert status["decision_enabled"] is False  # 未启用时明确说明，连接不擅自改设置。
                assert status["decision_mode"] == "connected"
                resources = await client.list_resources()
                assert {str(r.uri) for r in resources.resources} == {f"m7a://guides/{g}" for g in ("connections", "strategy", "decisions")}
                strategy = await client.read_resource("m7a://guides/strategy")
                assert "agent_respond" in strategy.contents[0].text
                auth = unpack(await client.call_tool("agent_connect", {"session_label": "fresh install"}))
                assert "guides" in auth and "agent_respond" in auth["guides"]["strategy"]
                assert len(unpack(await client.call_tool("agent_status"))["client_name"]) == 80
                credentials = {k: auth[k] for k in ("session_id", "token")}
                reply = unpack(await client.call_tool("agent_wait", dict(credentials, wait=0)))
                assert reply["pending"] == []
                unpack(await client.call_tool("agent_disconnect", credentials))
    anyio.run(scenario)
    assert not (fresh_install / "config.yaml").exists()
    assert not (caller / "logs").exists()
    assert not (fresh_install / "logs/runs").exists()


@pytest.mark.parametrize("raw_request", ['{"action":"status","invalid":NaN}', '[' * 1500 + ']' * 1500])
def test_bad_session_input_is_json_error_without_traceback(fresh_install, tmp_path, raw_request):
    result = subprocess.run([sys.executable, str(fresh_install / "main.py"), "--agent-session"], input=raw_request,
                            capture_output=True, text=True, cwd=tmp_path, timeout=15)
    assert result.returncode == 1
    assert "error" in json.loads(result.stdout)
    assert "Traceback" not in result.stderr


def test_mcp_can_diagnose_bad_configuration_without_claiming(fresh_install):
    config = fresh_install / "config.yaml"
    config.write_text("wrong: [unfinished", encoding="utf-8")
    params = StdioServerParameters(command=sys.executable, args=[str(fresh_install / "main.py"), "--agent-mcp"])
    async def scenario():
        async with stdio_client(params) as streams:
            async with ClientSession(*streams, client_info=Implementation(name="Config diagnostic", version="1")) as client:
                await client.initialize()
                result = await client.call_tool("agent_status")
                assert not result.is_error
                status = json.loads(next(c.text for c in result.content if c.type == "text"))
                assert "configuration_error" in status
                assert status["state"] == "unclaimed"
                assert (await client.call_tool("agent_connect", {"session_label": "invalid config"})).is_error
    anyio.run(scenario)
    assert config.read_text(encoding="utf-8") == "wrong: [unfinished"


def test_missing_guides_do_not_leave_an_orphaned_controller(tmp_path, monkeypatch):
    import utils.agent_service as service
    monkeypatch.setattr(service, "installation_directory", lambda: tmp_path)
    store = AgentSession(tmp_path / "connection")
    with pytest.raises(ValueError, match="完整安装包"):
        service.connect_session(store, "New Agent", "missing assets")
    assert not store.has_controller()


@pytest.mark.parametrize("reported_name", ["Modern MCP client", None])
def test_modern_mcp_client_uses_same_tools_and_reported_identity(fresh_install, reported_name):
    from mcp import Client
    params = StdioServerParameters(command=sys.executable, args=[str(fresh_install / "main.py"), "--agent-mcp"])
    async def scenario():
        info = Implementation(name=reported_name, version="1") if reported_name else None
        async with Client(params, mode="2026-07-28", client_info=info) as client:
            status = await client.call_tool("agent_status", {})
            assert not status.is_error
            data = json.loads(next(c.text for c in status.content if c.type == "text"))
            assert len(data["clients"]) == 1
            assert data["clients"][0]["client_name"] == (reported_name or "mcp")  # SDK 的默认上报名称。
            auth_result = await client.call_tool("agent_connect", {"session_label": "modern protocol"})
            assert not auth_result.is_error
            auth = json.loads(next(c.text for c in auth_result.content if c.type == "text"))
            assert "guides" in auth
            state = await client.call_tool("agent_status", {})
            assert json.loads(state.content[0].text)["clients"][0]["has_control"]
            await client.call_tool("agent_disconnect", {k: auth[k] for k in ("session_id", "token")})
    anyio.run(scenario)
