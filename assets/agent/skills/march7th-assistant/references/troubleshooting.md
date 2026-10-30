# 排查说明

## 先看运行记录

每次运行都会在 `logs\runs\` 下留下：

| 文件 | 内容 |
|---|---|
| `<运行编号>.json` | `status`（success / failed / blocked / stopped / interrupted / running）、`reason`、`error`、`exit_code`、`screenshot`、起止时间、发起方 `invoker`、运行锁 `lock`（acquired / forced / busy / unavailable） |
| `<运行编号>.log` | 本次运行的完整输出 |

`.\m7a.exe --follow latest` 会显示最近一次运行的末尾输出与结论。记录显示 running 但进程已经不在时，`--status` / `--follow` 会报告为 aborted：
通常是控制台窗口被关闭或进程被结束，不代表任务完成。

当天的完整日志在 `logs\<日期>.log`（图形界面启动的任务也写在这里），`logs\config_diag.log` 记录配置文件读写。

## 常见情况

| 现象 | 处理 |
|---|---|
| 退出码 3 / `reason: first_run_required` | 打开 `March7th Launcher.exe`，请用户本人阅读并确认免责声明 |
| 退出码 4 / `reason: busy` | 已有任务在操控游戏（`--status` 的 `active_run`）。等它结束，或询问用户后用 `--control current stop` 停止 |
| 退出码 5 | UAC 被取消或无法弹出：请用户在电脑前点「是」；无人值守需求改用定时任务 |
| 日志警告「运行锁不可用」/ `lock: unavailable` | `logs\runs\` 无法读写（权限、磁盘已满、杀毒软件拦截等，原因见 `lock_error`）。任务仍会运行，但不会检查是否有其他任务同时在操控游戏：先用 `--status` 确认没有其他运行，再修复目录权限 |
| 找不到游戏 / 启动游戏失败 | 检查 `--status` 的 `game_path_exists`，修正 `game_path`；使用启动器或云游戏时检查对应配置 |
| 提示切换界面失败、识别失败 | 常见原因是滤镜、帧率显示、HDR、非 16:9 分辨率或窗口被遮挡，见 FAQ「开了滤镜、帧率显示…」一节，并查看 `screenshot` |
| 未找到可执行文件、程序被删除 | 杀毒软件误删：请用户把小助手目录加入排除项后重新解压（FAQ 有说明） |
| 中文输出有个别乱码 | PowerShell 先执行 `[Console]::OutputEncoding = [Text.Encoding]::UTF8`，或直接读取 `logs\runs\<运行编号>.log`（UTF-8） |
| 任务结束后电脑关机 / 睡眠 | 配置中的 `after_finish` 生效了；Agent 发起的运行请带 `--after-finish None` |

更多问题见 `assets/docs/FAQ.md`。给出结论时把「日志里看到的事实」和「推测」分开说明。

## 停止与暂停

- `.\m7a.exe --control current pause` / `resume`：在下一次键鼠操作前停住或恢复，不会对游戏做任何额外操作。
- `.\m7a.exe --control current stop`：任务在下一次键鼠操作前结束（退出码 6）；长时间等待中的任务最迟约 60 秒后强制结束。游戏本身保持打开。

## 旧版本（没有 m7a.exe）

旧版本只有 `March7th Assistant.exe`，它在清单里要求管理员权限：普通权限的终端直接运行会报「需要提升」，
提权后又在新窗口中运行，看不到输出，也拿不到退出码。可以这样替代：

```powershell
$dir = 'D:\March7thAssistant'   # 安装目录
$p = Start-Process -FilePath (Join-Path $dir 'March7th Assistant.exe') -ArgumentList 'daily' -WorkingDirectory $dir -Verb RunAs -PassThru -Wait
$p.ExitCode   # 旧版本在未确认免责声明等情况下也可能返回 0，需要结合日志判断
Get-Content (Join-Path $dir ("logs\" + (Get-Date -Format 'yyyy-MM-dd') + '.log')) -Encoding utf8 -Tail 40
```

注意旧版本默认在结束时等待「按回车键关闭窗口」（配置 `pause_after_success` / `exit_after_failure`），没有人按回车时 `-Wait` 会一直等待。
建议用户更新到包含 `m7a.exe` 的新版本。
