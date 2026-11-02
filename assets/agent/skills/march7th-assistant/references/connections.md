# 连接并接管当前聊天

用户要求连接、接管或监管时阅读。连接不启动游戏，不代表聊天结束后仍有 Agent 常驻。

## 先确认接入方式

读取安装目录的 `m7a.exe --status`，查看 `agent_connection`。支持内置连接的版本，GUI「设置 → 差分宇宙 → Agent 辅助决策 → 配置」可选「内置 Agent 连接」。旧的自定义程序仍可使用，其连接状态不可推断为已接管。

内置 STDIO MCP 服务的入口是安装目录的 `m7a.exe --agent-mcp`。无需额外 Python 或独立 Agent CLI。GUI 可复制 Codex TOML 或通用 JSON 接入配置；在所用客户端添加并重新加载 MCP 后，使用下列工具。客户端名称来自 MCP 客户端元信息，会话标签由当前 Agent 准确提供；不推断模型、聊天标题或其他会话身份。

## MCP 工具

- `agent_connect(session_label)`：用户授权后接管，返回 `session_id`、`token` 与 `lease_seconds`。凭据只在当前操作中保存，不写攻略、公开日志或向用户展示。
- `agent_status()`：只读连接摘要；不续期。
- `agent_wait(session_id, token, wait=20)`：等待本会话的请求，单次 0～20 秒；无请求时按本次授权继续等待。
- `agent_observe(session_id, token, request_id, observation_id)`：读取请求内已有的 PNG 与 OCR，不接受任意路径。
- `agent_respond(session_id, token, request_id, decision)`：回复候选、查看、返回或 decline，并可附理由和 memory；沿用 `decisions.md` 与 `strategy.md`。
- `agent_disconnect(session_id, token)`：结束接管，游戏后续使用原策略。

接管后按 `strategy.md` 阅读队伍与构筑证据，再持续执行“等待 → 判断/查看 → 回复”。`accepted` 只表示提交，实际确认以日志为准。用户只要求连接时不自动开始新对局；游戏运行仍使用既有 GUI 或 `m7a.exe` 任务命令。

任务结束、用户要求停止监管，或即将结束聊天回复时主动断开。不能把 MCP 进程、文件桥进程存活或安装 Skill 描述为 Agent 正在监管。状态查询和图片读取不续期；只有实际连接、等待与回复续期。租约为 `max(90, 节点超时+30)` 秒。

## 当前客户端尚未加载 MCP 时

任何能执行本地命令的 Agent 都可用 `m7a.exe --agent-session`：标准输入为 UTF-8 JSON，标准输出为一个 JSON 对象，失败返回非零退出码。它与 MCP 共享同一接管状态，不需要额外服务。

```json
{"action":"connect","client_name":"实际客户端名称","session_label":"由当前 Agent 提供的准确标签"}
```

后续动作保留返回的 `session_id` 和 `token`：

```json
{"action":"wait","session_id":"...","token":"...","wait":20}
{"action":"respond","session_id":"...","token":"...","request_id":"...","decision":{"candidate_id":"text-2","reason":"实际取舍依据","memory":{}}}
{"action":"observe","session_id":"...","token":"...","request_id":"...","observation_id":"frame-1"}
{"action":"disconnect","session_id":"...","token":"..."}
{"action":"status"}
```

`observe` 返回 `observation`、`image_base64`、`mime_type`；有视觉工具时按其支持的方式读取。不要把 Base64 图片或接管凭据打印到聊天中。CLI 客户端名称是调用者自报信息，不是经平台验证的身份。

## 断连与更换 Agent

同一安装同时只有一个接管者，另一个连接不会覆盖有效会话。需要更换时先由原会话断开，或由用户在 GUI 点击「断开」。租约到期或 MCP 客户端关闭后接管失效。

未接管的节点直接使用原策略；等待中断连及时回退，超时也回退。重连只处理新请求，旧回复、旧会话不能补发选择。若查看页面不能确认返回，程序停止保留现场，不从未知页面继续操作。

`agent_connection` 与 GUI 显示未接管、已接管空闲、等待决策、已断开，以及客户端、会话标签、最近活动和最近回退原因；不会输出凭据。高级自定义程序显示连接状态未知。
