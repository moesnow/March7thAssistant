"""非提权 Agent 入口；MCP 和一次性命令共享会话核心。"""

import base64
import json
from pathlib import Path
import sys

from utils.agent_session import AgentSession
from utils.agent_session import decision_mode


GUIDE_FILES = {"connections": "connections.md", "strategy": "strategy.md", "decisions": "decisions.md"}


def installation_directory():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]


def guide_text(name):
    try:
        path = installation_directory() / "assets/agent/skills/march7th-assistant/references" / GUIDE_FILES[name]
        return path.read_text(encoding="utf-8")
    except (OSError, KeyError) as error:
        raise ValueError("缺少 Agent 使用说明，请使用包含 assets/agent 的完整安装包") from error


def session_store():
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError
    path = Path("config.yaml")
    try:
        values = YAML(typ="safe").load(path) if path.exists() else {}
    except YAMLError:
        raise ValueError("config.yaml 格式无效，请在小助手中检查配置") from None
    if values is None:
        raise ValueError("config.yaml 为空，请在小助手中检查配置")
    if not isinstance(values, dict):
        raise ValueError("config.yaml 必须是配置映射")
    from types import SimpleNamespace
    store = AgentSession(timeout=values.get("divergent_decision_timeout", 60))
    store.mode = decision_mode(SimpleNamespace(get_value=values.get))
    store.decision_enabled = values.get("divergent_decision_enable", False) is True
    return store


def service_status(store, *, configured=False):
    result = store.status()
    result["guides"] = {name: f"m7a://guides/{name}" for name in GUIDE_FILES}
    try:
        current = session_store() if configured else store
        result.update(decision_mode=getattr(current, "mode", "connected"),
                      decision_enabled=getattr(current, "decision_enabled", False))
    except (OSError, ValueError, TypeError) as error:
        result.update(decision_enabled=False, configuration_error=str(error))
    return result


def connect_session(store, client_name, session_label, **kwargs):
    # 说明必须在取得控制权之前读取，缺失资源时不能留下无凭据的接管。
    guides = {name: guide_text(name) for name in ("strategy", "decisions")}
    result = store.connect(client_name, session_label, **kwargs)
    return dict(result, guides=guides, decision_enabled=getattr(store, "decision_enabled", False))


def dispatch(store, message):
    if not isinstance(message, dict):
        raise ValueError("请求必须是 JSON 对象")
    action = message.get("action")
    if action == "connect":
        if getattr(store, "mode", "connected") != "connected":
            raise ValueError("请先在 GUI 保存内置 Agent 连接方式")
        return connect_session(store, message.get("client_name"), message.get("session_label", ""))
    if action == "status":
        return service_status(store)
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
        def reject_constant(value):
            raise ValueError("JSON 不支持非有限数字")
        result = dispatch(session_store(), json.loads(raw.decode("utf-8-sig"), parse_constant=reject_constant))
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=True))
        return 1


def run_mcp(store=None):
    import asyncio
    import threading
    import psutil
    from mcp.server import MCPServer
    from mcp.server.mcpserver import Context, Image
    from mcp_types import CallToolResult, TextContent
    from mcp_types.version import MODERN_PROTOCOL_VERSIONS

    configured = store is None
    store = store or AgentSession()
    registry = store
    client_id = None
    owned = None

    def refresh_timeout():
        if configured:
            try:
                store.ttl = session_store().ttl
            except (OSError, ValueError, TypeError):
                pass  # 临时配置读锁不能中断已有接管；状态接口另行报告错误。

    def register_client(params, *, allow_unknown=False):
        nonlocal client_id
        if client_id is None and (params is not None or allow_unknown):
            info = params.client_info if params else None
            client_id = registry.register_client(getattr(info, "name", None), getattr(info, "version", ""), owner=psutil.Process())

    async def track_client(ctx, call_next):
        # 官方 SDK 的公开 middleware 钩子，观察已完成握手的真实通道。
        # 不轮询、不替 Agent 保活，进程存活仅作为客户端连接的证据。
        if ctx.method != "initialize":
            register_client(ctx.session.client_params, allow_unknown=ctx.protocol_version in MODERN_PROTOCOL_VERSIONS)
        return await call_next(ctx)

    server = MCPServer("march7th-assistant", instructions=(
        "仅在用户要求接管时调用 agent_connect；连接不启动游戏。先用 agent_status 检查 decision_enabled；为 false 时请用户保存配置并启用 GUI 开关。"
        "agent_connect 会返回 guides 中的策略与协议全文，也可读取 m7a://guides/strategy 等 MCP 资源，无需本地文件工具。接管后持续调用 agent_wait，读取观察和候选，"
        "按实际队伍取舍，通过 agent_respond 回复并继续等待。不要结束回复后声称仍在监管。任务结束或用户停止监管时 agent_disconnect。"
        "名称与会话标签须准确，未知不猜测；不使用 Computer Use。MCP 启动本身不代表 Agent 已接管。"), log_level="WARNING", middleware=[track_client])

    @server.resource("m7a://guides/connections", mime_type="text/markdown", description="连接、接管与持续监管说明")
    def connections_guide() -> str:
        return guide_text("connections")

    @server.resource("m7a://guides/strategy", mime_type="text/markdown", description="根据实际队伍和构筑取舍的策略 Skill")
    def strategy_guide() -> str:
        return guide_text("strategy")

    @server.resource("m7a://guides/decisions", mime_type="text/markdown", description="候选、查看、返回和构筑记忆协议")
    def decisions_guide() -> str:
        return guide_text("decisions")

    @server.tool()
    async def agent_connect(session_label: str, ctx: Context) -> dict:
        """接管此安装的决策队列。标签由当前 Agent 提供，不推断聊天标题。不启动游戏。"""
        nonlocal store, owned
        if configured:
            store = session_store()
        if getattr(store, "mode", "connected") != "connected":
            raise ValueError("请先在 GUI 保存内置 Agent 连接方式")
        params = ctx.session.client_params
        info = params.client_info if params else None
        register_client(params, allow_unknown=True)
        name = str(getattr(info, "name", None) or "MCP client").strip()[:80] or "MCP client"
        result = connect_session(store, name, session_label, owner=psutil.Process(), client_id=client_id)
        owned = {key: result[key] for key in ("session_id", "token")}
        return result

    @server.tool()
    async def agent_status() -> dict:
        """只读查询连接状态，不续期。"""
        return service_status(store, configured=configured)

    @server.tool()
    async def agent_wait(session_id: str, token: str, wait: float = 20) -> dict:
        """等待当前会话的选择请求，单次最多 20 秒；无请求时继续等待，监管结束时断开。"""
        refresh_timeout()
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
        refresh_timeout()
        return store.respond(session_id, token, request_id, decision)

    @server.tool()
    async def agent_disconnect(session_id: str, token: str) -> dict:
        """结束接管；等待中的游戏决策及时交回原策略。"""
        nonlocal owned
        result = store.disconnect(session_id, token)
        owned = None
        return result

    try:
        server.run(transport="stdio")
    finally:
        if owned:
            try:
                store.disconnect(**owned)
            except (OSError, ValueError):
                pass
        try:
            registry.unregister_client(client_id)
        except (OSError, ValueError):
            pass  # 崩溃/无法清理时，状态读取仍会按进程身份剔除断开的客户端。


def connection_config(install=None):
    install = Path(install or installation_directory()).resolve()
    command = str(install / "m7a.exe") if getattr(sys, "frozen", False) else sys.executable
    args = ["--agent-mcp"] if getattr(sys, "frozen", False) else [str(install / "main.py"), "--agent-mcp"]
    # JSON 字符串是合法 TOML 基本字符串；不涉及 shell 拼接。
    toml = ("[mcp_servers.march7th_assistant]\ncommand = " + json.dumps(command, ensure_ascii=False)
            + "\nargs = " + json.dumps(args, ensure_ascii=False) + "\ncwd = "
            + json.dumps(str(install), ensure_ascii=False) + "\nstartup_timeout_sec = 30\ntool_timeout_sec = 45\n")
    generic = json.dumps({"mcpServers": {"march7th_assistant": {"command": command, "args": args}}}, ensure_ascii=False, indent=2)
    return toml, generic
