"""非提权 Agent 入口；MCP 和一次性命令共享会话核心。"""

import base64
import json
import os
from pathlib import Path
import sys

from utils.agent_session import AgentSession
from utils.agent_session import decision_mode


def session_store():
    from ruamel.yaml import YAML
    path = Path("config.yaml")
    values = YAML(typ="safe").load(path) if path.exists() else {}
    values = values or {}
    from types import SimpleNamespace
    store = AgentSession(timeout=values.get("divergent_decision_timeout", 60))
    store.mode = decision_mode(SimpleNamespace(get_value=values.get))
    return store


def dispatch(store, message):
    if not isinstance(message, dict):
        raise ValueError("请求必须是 JSON 对象")
    action = message.get("action")
    if action == "connect":
        if getattr(store, "mode", "connected") != "connected":
            raise ValueError("请先在 GUI 保存内置 Agent 连接方式")
        return store.connect(message.get("client_name"), message.get("session_label", ""))
    if action == "status":
        return store.status()
    credentials = {key: message.get(key) for key in ("session_id", "token")}
    if action == "wait":
        return store.wait(**credentials, wait=message.get("wait", 20))
    if action == "disconnect":
        return store.disconnect(**credentials)
    if action == "respond":
        return store.respond(**credentials, request_id=message.get("request_id"), decision=message.get("decision"))
    if action == "observe":
        frame, data = store.observe(**credentials, request_id=message.get("request_id"), observation_id=message.get("observation_id"))
        return {"observation": frame, "image_base64": base64.b64encode(data).decode("ascii"), "mime_type": "image/png"}
    raise ValueError("不支持的 Agent 会话操作")


def session_main():
    try:
        raw = sys.stdin.buffer.read(65537)
        if len(raw) > 65536:
            raise ValueError("请求过大")
        result = dispatch(session_store(), json.loads(raw.decode("utf-8-sig")))
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=True))
        return 1


def run_mcp(store=None):
    import asyncio
    import threading
    import psutil
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context, Image
    from mcp_types import CallToolResult, TextContent

    configured = store is None
    store = store or session_store()
    owned = []
    server = MCPServer("march7th-assistant", instructions=(
        "仅在用户要求接管时调用 agent_connect；连接不启动游戏。接管后持续调用 agent_wait，读取 strategy Skill、观察和候选，"
        "按实际队伍取舍，通过 agent_respond 回复并继续等待。不要结束回复后声称仍在监管。任务结束或用户停止监管时 agent_disconnect。"
        "名称与会话标签须准确，未知不猜测；不使用 Computer Use。MCP 启动本身不代表 Agent 已接管。"), log_level="WARNING")

    @server.tool()
    async def agent_connect(session_label: str, ctx: Context) -> dict:
        """接管此安装的决策队列。标签由当前 Agent 提供，不推断聊天标题。不启动游戏。"""
        nonlocal store
        if configured:
            store = session_store()
            if store.mode != "connected":
                raise ValueError("请先在 GUI 保存内置 Agent 连接方式")
        params = ctx.session.client_params
        info = getattr(params, "client_info", None) or getattr(params, "clientInfo", None)
        result = store.connect(getattr(info, "name", None) or "MCP client", session_label, owner=psutil.Process())
        owned.append(result)
        return result

    @server.tool()
    async def agent_status() -> dict:
        """只读查询连接状态，不续期。"""
        return store.status()

    @server.tool()
    async def agent_wait(session_id: str, token: str, wait: float = 20) -> dict:
        """等待当前会话的选择请求，单次最多 20 秒；无请求时继续等待，监管结束时断开。"""
        cancelled = threading.Event()
        try:
            return await asyncio.to_thread(store.wait, session_id, token, wait, cancelled=cancelled.is_set)
        finally:
            cancelled.set()

    @server.tool()
    async def agent_observe(session_id: str, token: str, request_id: str, observation_id: str) -> CallToolResult:
        """读取当前请求已有的游戏观察 PNG 与 OCR；不接受任意文件路径。"""
        frame, data = store.observe(session_id, token, request_id, observation_id)
        return CallToolResult(content=[TextContent(type="text", text=json.dumps(frame, ensure_ascii=False)),
                                       Image(data=data, format="png").to_image_content()])

    @server.tool()
    async def agent_respond(session_id: str, token: str, request_id: str, decision: dict) -> dict:
        """提交候选/查看/返回/放弃建议及理由、memory；accepted 不代表游戏已确认。"""
        return store.respond(session_id, token, request_id, decision)

    @server.tool()
    async def agent_disconnect(session_id: str, token: str) -> dict:
        """结束接管；等待中的游戏决策及时交回原策略。"""
        return store.disconnect(session_id, token)

    try:
        server.run(transport="stdio")
    finally:
        for credentials in owned:
            try:
                store.disconnect(credentials["session_id"], credentials["token"])
            except (OSError, ValueError):
                pass


def connection_config(install=None):
    install = Path(install or os.getcwd()).resolve()
    command = str(install / "m7a.exe") if getattr(sys, "frozen", False) else sys.executable
    args = ["--agent-mcp"] if getattr(sys, "frozen", False) else [str(install / "main.py"), "--agent-mcp"]
    # JSON 字符串是合法 TOML 基本字符串；不涉及 shell 拼接。
    toml = ("[mcp_servers.march7th_assistant]\ncommand = " + json.dumps(command, ensure_ascii=False)
            + "\nargs = " + json.dumps(args, ensure_ascii=False) + "\ncwd = "
            + json.dumps(str(install), ensure_ascii=False) + "\nstartup_timeout_sec = 30\ntool_timeout_sec = 45\n")
    generic = json.dumps({"mcpServers": {"march7th_assistant": {"command": command, "args": args}}}, ensure_ascii=False, indent=2)
    return toml, generic
