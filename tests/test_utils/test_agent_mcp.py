from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp_types import Implementation
from PIL import Image

from utils.agent_session import AgentSession


def test_real_mcp_initialize_owner_observe_reply_and_client_close(tmp_path):
    directory = tmp_path / "connection"
    store = AgentSession(directory)
    image = tmp_path / "agent_decisions/session/frame.png"
    image.parent.mkdir(parents=True)
    Image.new("RGB", (40, 30)).save(image)
    code = "from utils.agent_service import run_mcp; from utils.agent_session import AgentSession; run_mcp(AgentSession(" + repr(str(directory)) + "))"
    params = StdioServerParameters(command=sys.executable, args=["-B", "-c", code], cwd=str(Path.cwd()))

    def unpack(result):
        assert not result.is_error, result
        return json.loads(next(content.text for content in result.content if content.type == "text"))

    async def scenario():
        async with stdio_client(params) as streams:
            async with ClientSession(*streams, client_info=Implementation(name="SDK test", version="1")) as client:
                await client.initialize()
                tools = await client.list_tools()
                assert {tool.name for tool in tools.tools} == {"agent_connect", "agent_status", "agent_wait", "agent_observe", "agent_respond", "agent_disconnect"}
                assert store.status()["state"] == "unclaimed"  # 初始化不是接管。
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
        assert store.status()["state"] == "disconnected"

    anyio.run(scenario)
