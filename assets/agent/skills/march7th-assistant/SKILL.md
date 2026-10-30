---
name: march7th-assistant
description: 操作「三月七小助手 / March7thAssistant / M7A」（崩坏：星穹铁道 Honkai Star Rail 自动化工具）：查找或安装小助手、查询状态、运行完整运行 / 每日实训 / 清体力 / 差分宇宙 / 货币战争 / 锄大地等任务、修改配置与定时任务、查看运行日志并排查失败。用户提到三月七、小助手、M7A、星铁或崩铁的日常 / 体力 / 自动化时使用。
license: GPL-3.0
metadata:
  version: "1"
---

# 三月七小助手（March7thAssistant）

三月七小助手是开源的《崩坏：星穹铁道》自动化工具：识别游戏画面并完成日常、清体力、各类周常玩法。
游戏操作全部由小助手完成；你的工作是**查找 / 安装、运行任务、修改配置、读结果和排查问题**。

**这份说明只提供知识，不限制你使用任何工具。** 这里没写到的，直接读文件、执行命令：
`m7a.exe --help`、`assets/config/config.example.yaml`（每个配置项都有中文注释）、`assets/docs/`（教程、FAQ、任务表）。

## 1. 找到安装位置

1. 读 `%LOCALAPPDATA%\March7thAssistant\installs.json`：小助手每次启动都会登记安装路径与版本，最近使用的排在最前。
2. 用户给出的路径。
3. 少数常见位置（如 `~\Games\March7thAssistant`、`D:\March7thAssistant`）。**不要全盘搜索**；找不到就问用户。

安装目录里有 `March7th Launcher.exe`（图形界面）、`March7th Assistant.exe`（命令行，需要管理员权限）、
`m7a.exe`（给脚本与 AI 用的命令行）、`config.yaml`、`logs\`。
源码目录（有 `main.py`、`app.py`）用 `python main.py` 代替 `m7a.exe`，参数完全相同。
还没安装：按 [安装说明](references/install.md) 操作。

## 2. 用 m7a.exe 操作

`m7a.exe` 不需要管理员权限：查询类命令直接返回；运行任务时会弹出一次 UAC，由用户点「是」，
任务在最小化的管理员窗口中执行，**输出会实时转回你的终端，结束后返回任务的真实退出码**。

| 命令（在安装目录执行） | 作用 |
|---|---|
| `.\m7a.exe --status` | 版本、首次使用是否已确认、游戏路径是否有效、图形界面是否在运行、正在运行的任务、最近 5 次运行（JSON） |
| `.\m7a.exe --list --json` | 全部任务 ID 与名称 |
| `.\m7a.exe <任务ID> --after-finish None` | 运行任务并等待结束 |
| `.\m7a.exe --workflow-name "流程名称"` | 运行用户在「流程编排」里建好的流程（`--list-workflows` 查看名称） |
| `.\m7a.exe <任务ID> --after-finish None --detach` | 启动后立即返回运行编号，不等待（长任务用） |
| `.\m7a.exe --follow latest` | 跟随最近一次运行的输出直到结束（也可写运行编号） |
| `.\m7a.exe --control current pause` | 暂停 / 继续 / 停止正在运行的任务（`pause` / `resume` / `stop`），图形界面启动的任务也可以 |

- 运行类命令加 `--json`，最后一行输出完整运行记录；所有 JSON 输出只含 ASCII，中文以 `\uXXXX` 转义。
- PowerShell 读取中文输出前先执行 `[Console]::OutputEncoding = [Text.Encoding]::UTF8`，否则可能出现个别乱码字符。
- 安装目录里**没有 `m7a.exe`** 说明是旧版本：见 [排查说明](references/troubleshooting.md#旧版本没有-m7aexe) 的替代做法，并建议用户更新。

| 退出码 | 含义 | 该怎么做 |
|---|---|---|
| 0 | 成功 | 汇报结果 |
| 1 | 任务失败 | 看运行记录的 `error` 与日志，按 [排查说明](references/troubleshooting.md) 处理 |
| 2 | 参数错误 | 看 `--help` 修正参数 |
| 3 | 首次使用尚未确认 | 打开 `March7th Launcher.exe`，请用户**本人**阅读并确认免责声明 |
| 4 | 已有任务在运行，本次未执行 | 等它结束（`--follow current`）或询问用户；确需同时运行才加 `--force` |
| 5 | 没有获得管理员权限（UAC 被取消） | 告诉用户需要在弹窗中点「是」 |
| 6 | 任务被停止指令中止 | 按用户意图决定是否重跑 |

## 3. 运行任务前先确认

1. 执行 `--status`：
   - `first_run_completed` 为 false：小助手要求用户先在图形界面阅读并确认免责声明（其中包含使用自动化工具的账号风险提示）。**由用户本人完成，不要代为确认，也不要用修改文件之类的方式绕过。**
   - `game_path_exists` 为 false 且 `cloud_game_enable` 为 false：先修正 `config.yaml` 的 `game_path`（找 `StarRail.exe` 或问用户）。
   - `active_run` 不为空：已有任务在操控游戏，不要再启动第二个。
2. **默认加 `--after-finish None`**：用户配置里的「完成后操作」可能是关机、睡眠或运行脚本，只在用户明确要求时才去掉。
3. 运行期间小助手会操控键盘鼠标并切换到游戏窗口，提醒用户不要同时操作电脑。
4. 耗时参考：`daily` 几分钟，`main`（完整运行）常见 10～40 分钟，模拟宇宙 / 锄大地可能数小时。
   你的命令有超时限制时用 `--detach`，再用 `--follow` 或 `--status` 跟进；命令超时不会中断任务。
5. 用户不在电脑前时没人能点 UAC：这种需求改用小助手自己的定时任务（见第 5 节）。

常用任务 ID：`main` 完整运行、`daily` 每日实训（含领奖励）、`power` 清体力、`routine` 日常、`divergent` 差分宇宙、
`currencywars` 货币战争、`universe` 模拟宇宙、`fight` 锄大地、`forgottenhall` 混沌回忆、`purefiction` 虚构叙事、
`apocalyptic` 末日幻影、`redemption` 兑换码、`game` 启动游戏、`app_update` 更新小助手。
每个任务做什么见 `assets/docs/TasksTable.md`。

## 4. 修改配置

- 直接编辑安装目录的 `config.yaml`（YAML）。改之前先在 `assets/config/config.example.yaml` 里找到同名配置项，读它的注释与可选值。
- 只改需要改的键，保留其余内容和注释，不要整份重写。图形界面会自动重新加载被外部修改的配置；**正在运行的任务不一定读取新值**，下次运行生效。
- 推送令牌、Mirror酱 CDK、账号等敏感值不要显示在对话中；需要填写时让用户在图形界面里输入。
- 常见修改（体力计划、副本、定时任务、消息推送、云游戏）见 [配置说明](references/config.md)。

## 5. 定时与无人值守

- 优先用小助手自己的定时：`config.yaml` 的 `scheduled_tasks`（可按星期、可链式执行），由**图形界面**执行，图形界面需要保持运行（最小化到托盘即可）；开机自启在图形界面「设置 → 杂项」配置。
- 不要让自己充当调度器，也不要另建 Windows 计划任务，除非用户明确要求。

## 6. 排查失败

1. `.\m7a.exe --follow latest` 查看最近一次运行的末尾输出与结论；或看 `--status` 的 `recent_runs`。
2. 运行记录 `logs\runs\<运行编号>.json`：`status`、`reason`、`error`、`screenshot`（失败时的游戏截图，可以直接查看图片）。
3. 完整输出 `logs\runs\<运行编号>.log`；当天全部日志 `logs\<日期>.log`（含图形界面启动的任务）。
4. 对照 `assets/docs/FAQ.md` 与 [排查说明](references/troubleshooting.md)。确认原因、修正配置后再重跑；不确定时把证据和推测分开告诉用户。

## 7. 更新与其他

- 更新小助手：`.\m7a.exe app_update` 或在图形界面检查更新；不要用完整包覆盖已有安装。
- 打开图形界面：运行 `March7th Launcher.exe`（会弹 UAC）。
- Mirror酱 是可选的付费下载加速（支持项目维护），只在 GitHub 下载困难时提及，不要索要或代填 CDK。
