---
name: march7th-assistant
description: 操作「三月七小助手 / March7thAssistant / M7A」（崩坏：星穹铁道 Honkai Star Rail 自动化工具）：查找或安装小助手、查询状态、运行完整运行 / 每日实训 / 清体力 / 差分宇宙 / 货币战争 / 锄大地等任务、修改配置与定时任务、查看运行日志并排查失败，导出角色面板并按账号情况推荐混沌回忆 / 虚构叙事 / 末日幻影的配队和打法。用户提到三月七、小助手、M7A，或星铁、崩铁的日常 / 体力 / 自动化 / 配队 / 深渊时使用。
license: GPL-3.0
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

`m7a.exe` 不需要管理员权限：查询类命令直接返回；运行任务需要管理员权限，默认会弹出一次 UAC 由用户点「是」，
用户开启了「免 UAC 运行」时不弹（见第 5 节）。任务在最小化的管理员窗口中执行，
**输出会实时转回你的终端，结束后返回任务的真实退出码**。

| 命令（在安装目录执行） | 作用 |
|---|---|
| `.\m7a.exe --status` | 版本、首次使用是否已确认、游戏路径是否有效、图形界面是否在运行、运行任务是否会弹 UAC、正在运行的任务、最近 5 次运行（JSON） |
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
| 5 | 没有获得管理员权限（UAC 被取消，或免 UAC 运行没能启动任务） | 看输出里的原因：UAC 被取消就告诉用户需要在弹窗中点「是」；免 UAC 运行失败就请用户在图形界面把开关关掉再打开 |
| 6 | 任务被停止指令中止 | 按用户意图决定是否重跑 |

## 3. 运行任务前先确认

1. 执行 `--status`：
   - `first_run_completed` 为 false：小助手要求用户先在图形界面阅读并确认免责声明（其中包含使用自动化工具的账号风险提示）。**由用户本人完成，不要代为确认，也不要用修改文件之类的方式绕过。**
   - `game_path_exists` 为 false 且 `cloud_game_enable` 为 false：先修正 `config.yaml` 的 `game_path`（找 `StarRail.exe` 或问用户）。
   - `active_run` 不为空：已有任务在操控游戏，不要再启动第二个。
   - `elevation`：运行任务时怎样获得管理员权限。`uac` 会弹出 UAC，需要用户在电脑前点「是」；
     `task` 表示用户已开启免 UAC 运行，不会弹窗；`admin` 表示你本身就在管理员权限下运行。
2. **默认加 `--after-finish None`**：用户配置里的「完成后操作」可能是关机、睡眠或运行脚本，只在用户明确要求时才去掉。
3. 运行期间小助手会操控键盘鼠标并切换到游戏窗口，提醒用户不要同时操作电脑。
4. 耗时参考：`daily` 几分钟，`main`（完整运行）常见 10～40 分钟，模拟宇宙 / 锄大地可能数小时。
   你的命令有超时限制时用 `--detach`，再用 `--follow` 或 `--status` 跟进；命令超时不会中断任务。
5. 用户不在电脑前时：`elevation` 为 `task` 或 `admin` 可以照常运行；为 `uac` 时没人能点 UAC，任务无法启动，见第 5 节。

常用任务 ID：`main` 完整运行、`daily` 每日实训（含领奖励）、`power` 清体力、`routine` 日常、`divergent` 差分宇宙、
`currencywars` 货币战争、`universe` 模拟宇宙、`fight` 锄大地、`forgottenhall` 混沌回忆、`purefiction` 虚构叙事、
`apocalyptic` 末日幻影、`character_export` 角色面板导出、`redemption` 兑换码、`game` 启动游戏、`app_update` 更新小助手。
每个任务做什么见 `assets/docs/TasksTable.md`。

## 4. 修改配置

- 直接编辑安装目录的 `config.yaml`（YAML）。改之前先在 `assets/config/config.example.yaml` 里找到同名配置项，读它的注释与可选值。
- 只改需要改的键，保留其余内容和注释，不要整份重写。图形界面会自动重新加载被外部修改的配置；**正在运行的任务不一定读取新值**，下次运行生效。
- 推送令牌、Mirror酱 CDK、账号等敏感值不要显示在对话中；需要填写时让用户在图形界面里输入。
- 常见修改（体力计划、副本、定时任务、消息推送、云游戏）见 [配置说明](references/config.md)。

## 5. 定时与无人值守

- 优先用小助手自己的定时：`config.yaml` 的 `scheduled_tasks`（可按星期、可链式执行），由**图形界面**执行，图形界面需要保持运行（最小化到托盘即可）；开机自启在图形界面「设置 → 杂项」配置。
- 不要让自己充当调度器，也不要另建 Windows 计划任务，除非用户明确要求。

### 免 UAC 运行（用户不在电脑前时）

用户在外面远程让你运行任务时，UAC 弹窗没人能点，任务无法启动。小助手为此提供了可选的「免 UAC 运行」：

- **作用**：开启后，`m7a.exe` 运行任务时由计划任务 `March7thAssistantNoUAC` 以管理员权限启动，不弹 UAC。
  命令、参数、输出和退出码都与平时相同，你不需要改变任何用法。
- **只能由用户本人开启**：在图形界面「设置 → 杂项 → 免 UAC 运行」打开开关，阅读风险说明后确认。
  这是用户自己的安全决定：**不要代为开启，不要替用户点确认，也不要自己创建计划任务、修改 UAC 设置或用其他方式绕过 UAC。**
- **向用户说明风险**（用自己的话转述）：开启后，这台电脑上以用户账户运行的其他程序（包括你执行的命令）
  也能借助小助手获得管理员权限，不再需要用户确认；电脑中了病毒或 AI 助手被他人冒用时，损害可能更大。
  建议只在自己的电脑上、并且信任所用的 AI 助手时开启，不需要时随时可以关闭。
- **确认是否生效**：`--status` 的 `elevation` 为 `task`。`uac_free` 为 `other` 表示开关是在另一个安装目录开启的
  （或移动过安装目录），为 `disabled` 表示计划任务在任务计划程序中被禁用，这两种情况都请用户在当前目录的图形界面中重新打开开关。
  更新小助手后不需要重新开启。
- **远程运行的前提**：电脑保持开机、已登录且没有锁屏（锁屏时任务能启动，但小助手无法操作游戏）。
  仍然默认加 `--after-finish None`：关机、睡眠会让你和用户都无法再操作这台电脑。

## 6. 按账号情况推荐高难关卡打法

用户问混沌回忆、虚构叙事、末日幻影怎么打、怎么配队时，先看用户的账号再回答，不要只给通用攻略。

1. **导出角色面板**：运行 `.\m7a.exe character_export --after-finish None`，运行前按第 3 节确认。
   后台模式实测 57 个角色约 13 分钟，角色多时按第 3 节用 `--detach`。目前只支持简体中文游戏客户端。
   已有 `characters.json`、`exported_at` 之后用户也没有换过遗器和光锥、没有抽到新角色时，可以直接用，不必重新导出。
2. **读安装目录的 `characters.json`**：每个角色约 5 KB，不要整份读进对话，先用脚本筛出需要的角色和字段。
   - `complete` 为 false 或 `failed` 不为空时结果不完整，要告诉用户缺了哪些角色。任务中途停止时，这次的结果在 `characters.partial.json`，`characters.json` 还是上一次的。
   - `characters` 每项的字段：`name`、`path`（命途）、`element`（属性）、`level`、`eidolon`（星魂）、`stats`（面板属性）、
     `light_cone`（光锥，`superimposition` 是叠影）、`skills`（技能等级）、`relics`（`sets` 是套装，`pieces` 是每件的主词条和副词条）、
     `warnings`（重读后仍未解决的问题，相关数值不要全信）。百分数按游戏显示值保存，`81.1` 表示 `81.1%`。
   - 文件里没有的内容：背包里未装备的遗器、单件遗器的名字、行迹的额外能力和属性加成，主角和三月七也只有当前命途。需要这些信息时问用户，不要猜。
3. **联网查当期关卡**：BOSS、弱点和增益每期都变，不要凭记忆回答；查不到就告诉用户。
4. **给方案**：只用 `characters` 里有的角色，每队说明为什么这样配、依据哪些面板数值；先给不花资源的调整，再给需要养成或合成的；事实和推测分开说。
5. **让小助手按方案打**（用户同意后）：把队伍写进 `config.yaml` 的 `forgottenhall_team1`、`purefiction_team1`、`apocalyptic_team1` 等配置项，
   格式和秘技次数的含义见 `assets/config/config.example.yaml`；这里要写角色英文名，对照表是 `assets/config/character_names.json`。
   星启模式默认关闭（`forgottenhall_stellar_enable` 等），多数玩家用常规模式就能拿满常规奖励，用户没有明确要求时不要打开。

## 7. 排查失败

1. `.\m7a.exe --follow latest` 查看最近一次运行的末尾输出与结论；或看 `--status` 的 `recent_runs`。
2. 运行记录 `logs\runs\<运行编号>.json`：`status`、`reason`、`error`、`screenshot`（失败时的游戏截图，可以直接查看图片）。
3. 完整输出 `logs\runs\<运行编号>.log`；当天全部日志 `logs\<日期>.log`（含图形界面启动的任务）。
4. 对照 `assets/docs/FAQ.md` 与 [排查说明](references/troubleshooting.md)。确认原因、修正配置后再重跑；不确定时把证据和推测分开告诉用户。

## 8. 更新与其他

- 更新小助手：`.\m7a.exe app_update` 或在图形界面检查更新；不要用完整包覆盖已有安装。
- 这份说明复制到技能目录后，小助手启动时会自动更新副本，不需要你处理。`--status` 的 `agent_skill_copies` 列出各副本的状态：`updated` 表示刚更新过，重新读一遍再继续；`modified` 表示副本被改过，不会自动覆盖，由用户决定是否换成随包版本。
- 这里写的与 `--help` 或实际行为不符时，以 `--status` 的 `agent_skill` 指向的随包说明为准。
- 打开图形界面：运行 `March7th Launcher.exe`（会弹 UAC）。
- Mirror酱 是可选的付费下载加速（支持项目维护），只在 GitHub 下载困难时提及，不要索要或代填 CDK。
