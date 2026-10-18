# 监管程序与管理 API

监管程序是 Docker 环境下的主程序入口，负责提供管理 API，并按请求启动或停止一个任务进程。它不直接执行游戏自动化任务，任务仍由现有的 `main.py` 执行。

## 功能概览

- 以 `supervisor.py` 作为 Docker 默认入口。
- 提供健康检查、运行状态、任务列表、工作流列表和配置管理 API。
- 支持启动内置任务或指定工作流。
- 同一时间只允许一个任务进程运行。
- 支持停止任务，任务无法在 10 秒内退出时会强制终止。
- API 默认绑定本机地址；绑定远程地址时必须设置访问令牌。
- 支持通过 `MARCH7TH_MODE=cli` 保留原来的直接 CLI 启动方式。

## 工作模式

### API 模式

API 模式是 Docker 默认模式。监管程序启动后默认自动将 `main` 放入队列并立即运行，同时提供管理 API。若只想启动 API，可将 `MARCH7TH_SUPERVISOR_STARTUP_TASK` 设为空。

```bash
docker compose up -d
curl http://127.0.0.1:8765/health
```

### CLI 模式

CLI 模式直接执行 `main.py`，适用于定时任务、一次性任务或不需要远程管理 API 的场景。

```bash
MARCH7TH_MODE=cli MARCH7TH_TASK=daily docker compose up
```

在 PowerShell 中可以使用：

```powershell
$env:MARCH7TH_MODE = "cli"
$env:MARCH7TH_TASK = "daily"
docker compose up
```

`MARCH7TH_TASK` 可以填写 `/api/tasks` 返回的任务 ID。未设置时，CLI 模式执行 `python main.py`，即完整运行。

### 监管器首轮任务启动策略

默认情况下，监管程序启动时自动排入 `main`，并立即开始完整运行。要让首轮任务像 `--no-run-immediately` 一样等待到配置项 `scheduled_time` 的下一个本地时间点，可使用命令行参数：

```powershell
python .\supervisor.py --no-run-immediately
```

或设置环境变量：

```powershell
$env:MARCH7TH_SUPERVISOR_NO_RUN_IMMEDIATELY = "true"
python .\supervisor.py
```

要改变监管程序启动时自动排入的任务，可使用 `--startup-task daily` 或设置 `MARCH7TH_SUPERVISOR_STARTUP_TASK=daily`。设置为空字符串可禁用自动启动任务、只运行 API。`--run-immediately` 可覆盖环境变量并立即执行首轮任务。

> **注意**：默认启动行为会运行真实的 `main` 游戏自动化任务。在 Windows 本机只验证 API 时，使用 `python .\supervisor.py --startup-task ""`；Docker Compose 中将 `MARCH7TH_SUPERVISOR_STARTUP_TASK` 设为空。

### Windows PowerShell 本机运行

不安装 Docker 也可以直接从源码启动监管 API。在仓库根目录打开 PowerShell，使用项目的 `uv` 环境安装依赖并启动服务：

```powershell
uv sync
uv run python .\supervisor.py
```

如果 PowerShell 提示找不到 `uv`，可以不安装 `uv`，改用 Python 自带的虚拟环境：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\supervisor.py
```

如果已激活虚拟环境，也可以将最后一条命令简写为 `python .\supervisor.py`。请从仓库根目录运行，监管程序会使用当前目录下的配置和资源文件。

服务默认监听 `127.0.0.1:8765`，终端保持运行。另开一个 PowerShell 窗口测试健康检查和只读接口：

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
Invoke-RestMethod http://127.0.0.1:8765/api/status
Invoke-RestMethod http://127.0.0.1:8765/api/modes
Invoke-RestMethod http://127.0.0.1:8765/api/tasks
```

PowerShell 会将 JSON 映射格式化成表格，控制台可能只显示部分内容；要展开完整任务列表：

```powershell
$response = Invoke-RestMethod http://127.0.0.1:8765/api/tasks
$response.tasks | ConvertTo-Json -Depth 10
```

如果未安装 `uv`，也可以在已安装项目依赖的 Python 环境中运行：

```powershell
python .\supervisor.py
```

要在本机验证 API 测试，可在仓库根目录运行：

```powershell
uv sync --group dev
uv run pytest tests\test_module\test_supervisor.py -v
```

使用上面的 Python 虚拟环境时，先安装测试依赖再运行：

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest tests\test_module\test_supervisor.py -v
```

按 `Ctrl+C` 停止监管程序。只读 API 测试不会运行游戏任务。Windows 下如果调用 `/api/start`，现有 `main.py` 可能触发 UAC 管理员权限提示；通过提示后才会启动任务。若只验证 API 连通性，不要调用 `/api/start`。

## Docker 配置

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `MARCH7TH_MODE` | 启动模式，可选 `api` 或 `cli` | `api` |
| `MARCH7TH_TASK` | CLI 模式下传给 `main.py` 的任务 ID | 空 |
| `MARCH7TH_API_HOST` | API 监听地址 | `0.0.0.0`（Dockerfile） |
| `MARCH7TH_API_PORT` | API 监听端口 | `8765` |
| `MARCH7TH_API_TOKEN` | API Bearer 认证令牌 | 空 |
| `MARCH7TH_API_BIND` | Compose 主机端口绑定地址 | `127.0.0.1` |
| `MARCH7TH_SUPERVISOR_STARTUP_TASK` | 监管程序启动时自动排入的任务 ID；空值禁用 | `main` |
| `MARCH7TH_SUPERVISOR_NO_RUN_IMMEDIATELY` | 首轮是否延迟到 `scheduled_time`；支持 `true`/`false` | `false` |

Compose 默认将容器端口 `8765` 绑定到主机的 `127.0.0.1:8765`。如果需要从其他机器访问：

1. 设置 `MARCH7TH_API_BIND=0.0.0.0` 或指定实际网卡地址。
2. 同时设置足够复杂的 `MARCH7TH_API_TOKEN`。
3. 通过 `Authorization: Bearer <token>` 发送所有受保护请求。

示例：

```bash
MARCH7TH_API_BIND=0.0.0.0 \
MARCH7TH_API_TOKEN=change-this-token \
docker compose up -d
```

> **注意**：如果 API 绑定非本机地址但没有设置 `MARCH7TH_API_TOKEN`，监管程序会拒绝启动。

## API 认证

`GET /health` 是公开的健康检查接口，其他接口都需要认证。

启用令牌后，请求头格式如下：

```http
Authorization: Bearer change-this-token
```

未认证或令牌错误时返回：

```json
{
  "error": "未授权"
}
```

## API 接口

### 健康检查

```http
GET /health
```

返回：

```json
{
  "status": "ok"
}
```

### 查看运行状态

```http
GET /api/status
```

任务运行时示例：

```json
{
  "running": true,
  "current": {
    "id": "task-123",
    "task": "daily",
    "status": "running"
  },
  "pid": 123,
  "started_at": "2026-10-14T08:00:00+00:00",
  "exit_code": null,
  "queue": []
}
```

任务结束后，`running` 为 `false`，`current` 和 `pid` 为 `null`，`exit_code` 保存最近一次任务进程的退出码。`queue` 是等待运行的任务数组。

### 查看启动模式

```http
GET /api/modes
```

返回当前支持的启动模式：

```json
{
  "modes": ["api", "cli"],
  "default": "api"
}
```

### 查看内置任务

```http
GET /api/tasks
```

返回任务 ID 与任务名称映射。启动任务时使用任务 ID，例如 `daily`、`power` 或 `currencywars`。

PowerShell 中使用 `$response.tasks | ConvertTo-Json -Depth 10` 可以展开完整映射。

### 查看工作流

```http
GET /api/workflows
```

返回当前配置目录中可用的工作流名称。

### 启动内置任务

```http
POST /api/start
Content-Type: application/json

{
  "id": "daily-001",
  "task": "daily"
}
```

启动请求会进入 FIFO 等待队列。请求可传入可选 `id`，用于之后取消尚未启动的队列项；不传时由服务生成唯一 ID。响应中的 `id` 是队列项 ID，不是内置任务 ID。

### 启动工作流

```http
POST /api/start
Content-Type: application/json

{
  "workflow_name": "工作流名称"
}
```

也可以指定工作流步骤路径：

```json
{
  "workflow_name": "工作流名称",
  "workflow_step_path": "0/1/2"
}
```

`workflow_step_path` 只能由数字和 `/` 组成。

`task` 与 `workflow_name` 必须二选一，不能同时为空或同时填写。调用方指定的任务 ID 只能包含字母、数字、下划线和连字符，长度不超过 64，且不能与队列中的 ID 重复。任务运行期间收到的新请求会进入队列，不会返回冲突。

### 查看和取消等待任务

```http
GET /api/queue
DELETE /api/queue/daily-001
```

DELETE 成功返回被取消的队列项及 `status: "cancelled"`。任务已经开始或不存在时返回 `404`。`POST /api/stop` 只停止当前运行任务，不会清空其他等待项。

### 停止任务

```http
POST /api/stop
Content-Type: application/json

{}
```

返回：

```json
{
  "stopped": true
}
```

没有运行中的任务时返回 `stopped: false`。

### 查询配置

```http
GET /api/config
```

返回当前配置文件中的配置对象。该接口可能包含账号、通知或运行参数等敏感信息，应只在受信任的网络中使用。

查询单个配置项可使用 `GET /api/config?key=log_level` 或 `GET /api/config/log_level`；只获取可用配置键名使用 `GET /api/config-keys`。

### 更新配置

```http
PATCH /api/config
Content-Type: application/json

{
  "log_level": "DEBUG",
  "cloud_game_use_paid_time": false
}
```

接口会一次性保存请求中的多个配置项，并返回更新成功的键名：

```json
{
  "updated": ["cloud_game_use_paid_time", "log_level"]
}
```

只允许更新配置文件中已经存在的键。未知键会返回 HTTP `400`，不会写入配置文件。配置环境变量覆盖的优先级仍高于配置文件，因此通过 API 修改被环境变量覆盖的选项后，运行时可能仍以环境变量的值为准。

PowerShell 查询任务及单项配置示例：

```powershell
$response = Invoke-RestMethod http://127.0.0.1:8765/api/tasks
$response.tasks | ConvertTo-Json -Depth 10
Invoke-RestMethod "http://127.0.0.1:8765/api/config?key=log_level"
```

### 监管器循环调度

当队列中的任务为内置 `main` 且 `after_finish` 为 `Loop` 时，任务成功完成后由监管程序按本地 `scheduled_time`（`HH:mm`）安排下一轮。循环任务在等待期间保留在队列中；期间提交的新启动请求会先于尚未到期的循环任务运行。其他任务和工作流不会自动循环，失败退出或调用 `/api/stop` 也不会安排下一轮。将 `after_finish` 设置为非 `Loop` 可关闭完整运行循环。

## curl 示例

设置令牌后，可以将令牌保存到当前终端变量中：

```bash
export API_TOKEN=change-this-token
```

查看任务列表：

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  http://127.0.0.1:8765/api/tasks
```

提交每日实训到监管队列：

```bash
curl -X POST \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"id":"daily-001","task":"daily"}' \
  http://127.0.0.1:8765/api/start
```

查看队列并取消尚未启动的请求：

```bash
curl -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8765/api/queue
curl -X DELETE -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8765/api/queue/daily-001
```

查询单个配置值：

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  "http://127.0.0.1:8765/api/config?key=log_level"
```

查看状态：

```bash
curl -H "Authorization: Bearer $API_TOKEN" \
  http://127.0.0.1:8765/api/status
```

停止任务：

```bash
curl -X POST \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://127.0.0.1:8765/api/stop
```

## 测试流程

### 1. 启动监管程序

先准备 Docker 配置和持久化目录，再启动容器：

```bash
cp assets/config/config.example.yaml config.yaml
docker compose up -d --build
docker compose ps
```

如果使用发布镜像而不是本地构建，将 Compose 中的 `build: .` 换成对应的 `image` 配置。确认容器状态为 `Up` 后继续。

### 2. 测试健康检查和 API 鉴权

健康检查不需要令牌：

```bash
curl -i http://127.0.0.1:8765/health
```

预期状态码为 `200`，响应为 `{"status":"ok"}`。检查未认证请求应被拒绝：

```bash
curl -i http://127.0.0.1:8765/api/status
```

未设置 `MARCH7TH_API_TOKEN` 时，受保护接口允许无令牌访问；设置了令牌时，此请求预期返回 `401`。带正确令牌查看状态：

```bash
curl -i -H "Authorization: Bearer $API_TOKEN" \
  http://127.0.0.1:8765/api/status
```

预期返回 `200`，初始状态中 `running` 为 `false`。

### 3. 测试只读管理接口

```bash
curl -sS -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8765/api/modes
curl -sS -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8765/api/tasks
curl -sS -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8765/api/workflows
curl -sS -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8765/api/config
```

预期分别返回支持的启动模式、内置任务、可用工作流和当前配置。配置响应可能包含敏感运行信息，请勿将其粘贴到公开日志或工单。

也可以测试无效配置键不会被保存：

```bash
curl -i -X PATCH \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"not_a_setting":true}' \
  http://127.0.0.1:8765/api/config
```

预期状态码为 `400`，响应列出未知键。

### 4. 测试任务生命周期

> **注意**：此步骤会启动真实游戏自动化任务。先确认云游戏账号已登录、配置正确，并选择适合在当前环境运行的任务。测试期间不要同时从 GUI 或其他容器启动任务。

启动一个预期运行时间较长、便于观察的任务，例如 `daily`：

```bash
curl -i -X POST \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"id":"daily-001","task":"daily"}' \
  http://127.0.0.1:8765/api/start
```

预期返回 `202`，响应包含队列项 `id` 和 `status`。随后查询状态：

```bash
curl -sS -H "Authorization: Bearer $API_TOKEN" \
  http://127.0.0.1:8765/api/status
```

当前任务运行时再次提交任务，预期仍返回 `202` 并进入等待队列，不会并发启动。确认一个请求仍处于等待状态后，可按其 ID 取消：

```bash
curl -X DELETE -H "Authorization: Bearer $API_TOKEN" \
  http://127.0.0.1:8765/api/queue/daily-001
```

然后停止当前任务：

```bash
curl -i -X POST \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}' \
  http://127.0.0.1:8765/api/stop
```

预期返回 `200` 和 `{"stopped":true}`。等待进程退出后再次查询状态，预期 `running` 为 `false`，并显示最近任务的 `exit_code`。任务日志可通过以下命令查看：

```bash
docker compose logs -f
```

### 5. 清理测试环境

确认任务已停止后退出日志跟踪并停止容器：

```bash
docker compose down
```

如果需要保留容器以便继续管理，不要执行 `down`；可改用 `docker compose stop` 暂停服务。

## 持久化目录

监管程序继续使用原有 Docker 挂载目录：

| 宿主机路径 | 容器路径 | 用途 |
|---|---|---|
| `./config.yaml` | `/m7a/config.yaml` | 游戏和运行配置 |
| `./logs` | `/m7a/logs` | 日志、二维码和诊断文件 |
| `./3rdparty/WebBrowser/UserProfile` | `/m7a/3rdparty/WebBrowser/UserProfile` | 浏览器登录状态和用户数据 |

镜像构建阶段会删除镜像内的 `config.yaml`。CLI 模式启动时，如果挂载的配置文件不存在或为空，`entrypoint.sh` 会从 `assets/config/config.example.yaml` 创建默认配置；API 模式不会因为缺少配置文件而主动创建任务配置，任务启动后仍需有可用配置文件。

## 错误状态码

| HTTP 状态码 | 含义 |
|---|---|
| `200` | 请求成功 |
| `202` | 任务启动请求已接受 |
| `400` | 请求参数、JSON 或配置键无效 |
| `401` | 缺少或错误的 Bearer 令牌 |
| `404` | API 路径、配置键或待取消队列项不存在 |

## 运维建议

- 远程管理时必须配置 `MARCH7TH_API_TOKEN`，不要把空令牌的 API 暴露到公网。
- 生产环境建议将 API 端口限制在管理网络或通过反向代理提供 HTTPS。
- 使用 `GET /health` 作为容器健康检查，不要用需要认证的接口作为基础存活检查。
- 使用 `GET /api/status` 判断任务是否正在运行，使用 `docker compose logs -f` 查看任务详细日志。
- 配置 API 会直接写入挂载的 `config.yaml`，不要让多个监管程序实例同时管理同一个配置文件。
- 监管程序只管理一个任务进程，不提供任务队列或并发执行能力。

## 相关文件

- [Docker 部署](/assets/docs/Docker.md)
- [流程编排](/assets/docs/Workflow.md)
- [配置示例](/assets/config/config.example.yaml)
- [监管程序入口](../../supervisor.py)
