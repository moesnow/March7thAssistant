# 下载与安装（Windows）

只在用户明确要求安装时才下载和写盘；用户只是问「怎么下载」时，给出 [官方 Releases](https://github.com/moesnow/March7thAssistant/releases/latest) 并说明：下载 `March7thAssistant_full.zip`，解压后双击 `March7th Launcher.exe`。

## 先确认是否已经安装

- 读 `%LOCALAPPDATA%\March7thAssistant\installs.json`，再看用户给出的路径与少数常见位置；不要全盘搜索，也不要因为存在 `python.exe` 就认定已安装。
- 已有安装：报告路径与版本（`assets\config\version.txt`），直接复用；要更新就用小助手自带的更新（`m7a.exe app_update` 或图形界面），**不要用完整包覆盖已有目录**。
- 源码目录（有 `main.py`、`app.py`）不是成品包。除非用户要求从源码运行，否则安装成品版，不要为此安装 Python、Git 或开发依赖。

## 选择下载源

- 默认使用 GitHub 最新正式版：`https://api.github.com/repos/moesnow/March7thAssistant/releases/latest`。以接口返回为准，不要猜版本号。
- 全新安装下载 `March7thAssistant_full.zip`（Windows 自带解压）；用户已有 7-Zip 且想省流量时可选 `March7thAssistant_full.7z`。
  **`update.7z` 是更新包，不能用于全新安装**；GitHub 自动生成的 Source code 压缩包也不是成品。
- 下载前核对附件的 `digest`（`sha256:...`），下载后用 `Get-FileHash -Algorithm SHA256` 比对，一致才解压。
- GitHub 访问困难时，可以告诉用户有 [Mirror酱](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-agent) 这个可选的付费高速下载渠道（支持项目维护）。
  由用户自己决定是否使用；不要索要、记录或在命令中写入 CDK。

## 安装位置

选择当前用户可写、**尚不存在**的目录，默认 `~\Games\March7thAssistant`。
不要装进 `C:\Program Files`（之后修改配置需要管理员权限），不要覆盖或删除已有目录。

## PowerShell 参考流程

下面的流程只下载、校验并解压到新目录：不会启动游戏或图形界面，也不会改动已有安装。先按用户意愿决定 `$target`。

```powershell
$ErrorActionPreference = 'Stop'
$target = Join-Path $env:USERPROFILE 'Games\March7thAssistant'   # 按用户指定修改
if (Test-Path -LiteralPath $target) { throw "目标目录已存在，请先核实或换一个新目录：$target" }

$headers = @{ 'User-Agent' = 'March7thAssistant-Agent'; 'Accept' = 'application/vnd.github+json' }
$release = Invoke-RestMethod -Uri 'https://api.github.com/repos/moesnow/March7thAssistant/releases/latest' -Headers $headers -TimeoutSec 30
if ($release.draft -or $release.prerelease) { throw '接口返回的不是正式版' }
$asset = @($release.assets | Where-Object { $_.name -ceq 'March7thAssistant_full.zip' -and $_.state -eq 'uploaded' })
if ($asset.Count -ne 1) { throw '正式版中没有唯一的完整 ZIP 附件' }
$asset = $asset[0]
if ($asset.digest -notmatch '^sha256:([a-fA-F0-9]{64})$') { throw '缺少官方 SHA-256 摘要，请改为手动从官方页面下载' }
$expected = $Matches[1].ToLowerInvariant()

$parent = Split-Path $target -Parent
New-Item -ItemType Directory -Path $parent -Force | Out-Null
$work = Join-Path $parent ('.m7a-install-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
$archive = Join-Path $work 'full.zip'
$unpacked = Join-Path $work 'unpacked'
$ok = $false
try {
    Invoke-WebRequest -Uri $asset.browser_download_url -Headers @{ 'User-Agent' = 'March7thAssistant-Agent' } -OutFile $archive -UseBasicParsing
    if ((Get-Item -LiteralPath $archive).Length -ne [long]$asset.size) { throw '下载大小与官方附件不一致' }
    $actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw 'SHA-256 校验失败，不要解压或运行' }
    Expand-Archive -LiteralPath $archive -DestinationPath $unpacked
    $roots = @(Get-ChildItem -LiteralPath $unpacked -File -Recurse -Filter 'March7th Launcher.exe' |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.DirectoryName 'assets\config\config.example.yaml') })
    if ($roots.Count -ne 1) { throw '解压后没有找到唯一的程序目录' }
    if (Test-Path -LiteralPath $target) { throw '目标目录在安装过程中出现，拒绝覆盖' }
    Move-Item -LiteralPath $roots[0].DirectoryName -Destination $target
    $ok = $true
    "安装目录：$target"
    "版本：$($release.tag_name)（SHA-256 已校验）"
} finally {
    if ($ok) { Remove-Item -LiteralPath $work -Recurse -Force }
    else { Write-Warning "安装未完成，临时文件保留在：$work" }
}
```

## 安装之后

1. 运行 `March7th Launcher.exe` 打开图形界面（会弹 UAC）。首次启动会显示免责声明，**请用户本人阅读并确认**，不要代为点击。
2. 在图形界面里确认游戏路径（多数情况下会自动识别），或使用云游戏。
3. 之后就可以用 `.\m7a.exe --status` 检查状态并运行任务。

汇报时区分：已有安装 / 已下载 / 已校验 / 已解压 / 已打开图形界面 / 用户已完成首次确认。没有亲自验证的项目如实说明。
