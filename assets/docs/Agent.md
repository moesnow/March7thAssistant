# AI 助手

三月七小助手可以交给 AI 助手来操作。Claude Code、Codex、DeepSeek Harness 等能执行命令的 AI 助手，读完随程序发布的使用说明（Skill）后，就能帮你安装小助手、运行任务、修改设置、查看日志和排查问题。

> AI 助手只是多了一种使用方式。不用 AI，图形界面同样可以完成所有操作。

## 开始使用

### 还没有安装

把下面这句话发给 AI 助手：

```text
帮我安装三月七小助手，说明见 https://m7a.top/assets/agent/skills/march7th-assistant/SKILL.md
```

AI 助手会从 GitHub 下载最新正式版，核对官方 SHA-256 后解压到一个新目录（默认 `~\Games\March7thAssistant`），不会覆盖或删除已有的安装。

安装完成后，请你本人打开 `March7th Launcher.exe`，阅读并确认免责声明，之后就可以让 AI 助手运行任务了。

### 已经安装

打开小助手，进入「设置 → 关于 → 社区与工具 → AI 助手」，点击「复制提示词」，粘贴给 AI 助手即可。提示词里带有本机的安装目录和版本号。

在安装目录中直接启动 AI 助手时，它会读取根目录的 `AGENTS.md`，自动找到这份说明。

### 把 Skill 装进 AI 助手

支持 Skill（技能）的 AI 助手，可以把安装目录下的 `assets\agent\skills\march7th-assistant` 文件夹复制到它的用户级技能目录（例如 `~/.claude/skills/` 或 `~/.agents/skills/`，以你所用 AI 助手的说明为准）。

之后直接说「帮我清体力」「看看昨天为什么失败了」就行，不用每次提供说明。

复制之后不用再管它：小助手更新后再次启动时，会把技能目录里的这份副本自动更新到当前版本。它只更新已经装好的副本，不会给其他 AI 助手新增 Skill，删除后也不会恢复；如果你改过副本的内容，它会保持原样，想跟随更新时重新复制一次即可。

## 它能帮你做什么

| 你可以这样说 | AI 助手会做的事 |
| --- | --- |
| 帮我跑一下每日实训 | 先检查小助手状态，再运行每日实训，把输出和结果告诉你 |
| 清体力改成刷遗器副本 | 对照配置说明修改体力计划，下次运行生效 |
| 每天早上 5 点自动做日常 | 修改小助手自己的定时任务（需要图形界面保持运行，最小化到托盘即可） |
| 让主号和小号依次清体力 | 查询参与轮流的账号，按列表顺序运行并分别汇报结果 |
| 昨天的完整运行为什么失败了？ | 读取运行记录、日志和失败截图，对照常见问题分析原因 |
| 帮我更新小助手 | 运行小助手自带的更新，不会用完整包覆盖安装目录 |

## 由你决定的事

AI 助手按照说明操作，下面这些始终由你本人决定：

- **免责声明**：首次使用必须由你本人在图形界面中阅读并确认，AI 助手不会代为点击，也不会用修改文件等方式绕过。
- **管理员权限**：默认每次运行任务都会弹出一次 UAC，需要你点「是」。想在不在电脑前时让 AI 助手远程运行任务，可以自己开启「免 UAC 运行」（见下文），AI 助手不会替你开启。
- **完成后操作**：AI 助手运行任务时默认加上 `--after-finish None`，不会执行你配置的关机、睡眠等操作，除非你明确要求。
- **敏感信息**：Mirror酱 CDK、推送令牌、账号等不会出现在对话中；需要填写时，请在图形界面里输入。

运行期间小助手会操控键盘鼠标并切换到游戏窗口，请不要同时操作电脑。

## 远程运行：免 UAC 运行

如果 AI 助手装在家里的电脑上，你在外面也想让它帮你清日常、刷本，会遇到一个问题：运行任务时弹出的 UAC 窗口（“你要允许此应用对你的设备进行更改吗？”）没人能点，任务就启动不了。

这时可以开启「免 UAC 运行」：

1. 打开小助手，进入「设置 → 高级」，打开「免 UAC 运行」。
2. 阅读弹出的说明，确认后开启。

开启后，AI 助手运行任务时不再弹出 UAC 窗口，其余用法完全不变。想关闭时，回到同一位置关掉开关即可。

开启前请了解：

- UAC 窗口原本是 Windows 的一道安全防线。开启后，这台电脑上以你的账户运行的其他程序（包括 AI 助手执行的命令）也能借助小助手获得管理员权限，不再需要你点「是」。如果电脑中了病毒，或者有人冒用你的 AI 助手，造成的损害可能会更大。建议只在自己的电脑上、并且信任所用的 AI 助手时开启。
- 只对当前 Windows 账户和当前安装目录生效。更新小助手后不用重新开启；移动安装目录后需要重新开启。
- 远程运行时，电脑需要保持开机、已登录并且没有锁屏：锁屏时任务虽然能启动，但小助手无法操作游戏。
- 删除小助手前，请先关闭这个开关。

它的实现是一个名为 `March7thAssistantNoUAC` 的计划任务：没有定时触发，只在 `m7a.exe` 运行任务时启动，并且只有你的账户能启动它。

## 命令行入口 m7a.exe

AI 助手使用的是安装目录里的 `m7a.exe`。它和 `March7th Assistant.exe` 是同一份程序、参数相同，但不需要以管理员身份启动：查询类命令直接返回；运行任务时默认弹出一次 UAC（开启免 UAC 运行后不弹），输出实时转回当前终端，结束后返回任务的真实退出码。你也可以在自己的脚本里使用它。

```powershell
.\m7a.exe --status                           # 安装、配置与运行状态（JSON）
.\m7a.exe --list --json                      # 全部任务
.\m7a.exe daily --after-finish None          # 运行每日实训，不执行完成后操作
.\m7a.exe main --after-finish None --detach  # 启动完整运行后立即返回运行编号
.\m7a.exe --follow latest                    # 跟随最近一次运行的输出直到结束
.\m7a.exe --control current stop             # 暂停 / 继续 / 停止正在运行的任务（pause / resume / stop）
```

| 退出码 | 含义 |
| --- | --- |
| 0 | 成功 |
| 1 | 任务失败 |
| 2 | 参数错误 |
| 3 | 首次使用，尚未确认免责声明 |
| 4 | 已有任务在运行，本次未执行 |
| 5 | 没有获得管理员权限（UAC 被取消，或免 UAC 运行没能启动任务） |
| 6 | 任务被停止指令中止 |

运行 `m7a.exe --status` 可查到数据目录 `data_dir`、配置文件 `config_file` 和日志目录 `logs_dir`。每次运行在 `runs_dir` 指向的目录留下记录：`<运行编号>.log` 是完整输出，`<运行编号>.json` 是状态、原因、错误与失败截图。

抽卡记录按 UID 分文件保存。默认或自定义数据目录使用 `<data_dir>/gacha/<UID>.json`，旧布局使用 `<logs_dir>/gacha/<UID>.json`。在桌面端的「抽卡记录」页打开「更多操作」可找到当前数据文件夹。

### 指定账号与轮流

查询 `--status` 的 `accounts`。`enabled` 是已保存的开关，`effective` 表示本次环境可按账号运行。`current` 是界面当前查看的 UID，`list` 按顺序列出 `uid`、`name` 和是否参与轮流的 `rotate`。Windows 主桌面的本地客户端启用多账号后，可以使用以下命令。

```powershell
.\m7a.exe daily --account "开拓者 · 主号" --after-finish None
.\m7a.exe main --account all --after-finish None --detach
.\m7a.exe --control <父运行编号> skip
```

将尖括号中的编号换成启动时返回的编号。名称重复时用 UID；省略 `--account` 会沿用当前登录。轮流按参与顺序逐个启动子运行，`skip` 跳过当前账号，`stop` 停止整轮。在 `runs_dir` 里打开父编号的 JSON，读取 `rotation.accounts` 每项的 `status`、`reason` 和子 `run_id`。子记录的 `parent_run_id` 指回父记录，`steps`、`detail` 和同编号日志说明这个账号执行到哪一步。

遇到 `account_login_expired`，请账号持有人重新登录并保存快照。`account_mismatch` 表示 UID 核对失败，`account_server_mismatch` 表示客户端选错服务器。`account_no_login`、`account_switch_failed` 分别表示缺少可用登录或切换失败。`account_unsupported` 或 `account_not_found` 要先核对运行方式、开关和账号标识。`account_timeout` 表示该账号超时。`child_crashed`、`child_error`、`child_failed`、`child_record_missing` 指向子运行，`rotation_parent_lost`、`rotation_finish_failed` 指向整轮。先看对应记录的 `error` 和日志，再决定是否重试。

AI 助手可只对本次命令设置环境变量 `M7A_RUN_TRIGGER=ai`，让运行记录标出 AI 来源。计划和启动任务会记录各自的触发方式。

全部参数见 `.\m7a.exe --help`，给 AI 助手看的完整说明见 [SKILL.md](https://github.com/moesnow/March7thAssistant/blob/main/assets/agent/skills/march7th-assistant/SKILL.md)。

## 常见问题

### 安装目录里没有 m7a.exe

说明小助手的版本较旧，`m7a.exe` 与「复制提示词」随 AI 助手功能一起加入。请先在图形界面中检查更新；更新前 AI 助手也能按说明里的替代做法运行任务，只是看不到实时输出，退出码也不可靠，需要结合日志判断结果。

### 提示需要先确认免责声明（退出码 3）

首次使用必须由你本人打开 `March7th Launcher.exe` 并确认免责声明，确认后再让 AI 助手运行任务。

### UAC 弹窗被取消（退出码 5）

运行任务需要管理员权限，请在弹窗中点「是」。如果你经常不在电脑前，可以使用图形界面里的定时任务，或者开启「免 UAC 运行」。

如果已经开启了免 UAC 运行，仍然弹出 UAC 或返回退出码 5，请在「设置 → 高级」中把「免 UAC 运行」关掉再打开；仍然失败时，检查是否被安全软件拦截。

### AI 助手找不到小助手

小助手每次启动都会在 `%LOCALAPPDATA%\March7thAssistant\installs.json` 登记安装位置。如果还从没启动过，直接把安装目录告诉 AI 助手即可。
