# 三月七小助手（March7thAssistant）

这里是「三月七小助手」的安装目录，一个开源的《崩坏：星穹铁道》自动化工具。
如果你是 AI Agent，请先阅读 `assets/agent/skills/march7th-assistant/SKILL.md`：
它说明了如何查询状态、运行任务、修改配置和排查问题。这份说明只提供知识，不限制你使用任何工具。

最常用的命令（在本目录执行；`m7a.exe` 不需要管理员权限，运行任务时会弹出一次 UAC，输出与退出码会转回当前终端）：

```powershell
.\m7a.exe --status                          # 安装、配置与运行状态（JSON）
.\m7a.exe --list --json                     # 全部任务
.\m7a.exe daily --after-finish None         # 运行每日实训；--after-finish None 避免执行配置里的关机等操作
.\m7a.exe --follow latest                   # 查看最近一次运行的输出与结果
```

- 配置文件是 `config.yaml`，每个配置项的说明在 `assets/config/config.example.yaml`；直接编辑即可，图形界面会自动重新加载。
- 首次使用必须由用户本人打开 `March7th Launcher.exe` 并确认免责声明，不要代为确认或绕过。
- 运行记录与日志在 `logs/runs/` 和 `logs/`。
