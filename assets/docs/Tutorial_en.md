# Tutorial

> This document was translated from the Simplified Chinese version using AI. Last updated: 2026-05-03. If anything differs, the Simplified Chinese version takes precedence.

## Before You Run

| Platform | Local Game | Cloud Game |
|------|---------|--------|
| Windows | ✅ | ✅ |
| macOS | ❌ | ✅ |
| Linux | ❌ | ✅ |
| Docker | ❌ | ✅ |

Local game mode supports Windows only. You must use the PC client and run the game in a 1920×1080 window. If windowed mode is unavailable, use fullscreen instead.

The in-game language must be set to Simplified Chinese. You should also disable FPS monitoring HUDs, MSI Afterburner, GamePP, HDR, NVIDIA Freestyle filters, and similar tools that may overlay or alter the captured image.

Cloud game mode supports Windows, macOS, and Linux. macOS and Linux users can run it from source, or use [Docker Deployment](/assets/docs/Docker.md).

> After enabling `Cloud Honkai: Star Rail`, tasks such as spending Trailblaze Power, Daily Training, and Divergent Universe no longer require a fixed window.
>
> They can run in the background. Field farming and Simulated Universe still require the game to stay fullscreen in the foreground.
>
> If you need background execution or multiple desktop sessions, you can also try [Remote Local Multi-User Desktop](/assets/docs/Background.md).

## Download and Installation

Open [Releases](https://github.com/moesnow/March7thAssistant/releases/latest) and scroll to the bottom of the page.

Download the full package named like `March7thAssistant_full.zip` or `March7thAssistant_full.7z`.

> March7thAssistant integrates the third-party service [MirrorChyan](https://mirrorchyan.com/?source=m7a-tutorial).
>
> If downloads are slow in Mainland China, you can try [MirrorChyan high-speed download](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-tutorial).

After the download finishes, right-click the archive and choose “Extract All”, or use a third-party archive tool.

The extracted directory should usually contain at least these files and folders:

- `March7th Launcher.exe`
- `March7th Assistant.exe`
- `March7th Updater.exe`
- `assets`
- `libraries`
- `3rdparty`

Double-click `March7th Launcher.exe` to open the GUI and accept the disclaimer.

If you need to work with Windows Task Scheduler, or you want to run the full workflow directly, you can also use `March7th Assistant.exe`.

### Launch from Command Line

`March7th Launcher.exe` supports command-line arguments, so you can open the GUI and start a specific task at the same time.

When launching from a terminal on Windows, use PowerShell, Windows Terminal, or CMD with administrator privileges.

If your system supports `Sudo for Windows`, you can also use `sudo`.

According to Microsoft documentation, `Sudo for Windows` is available only on Windows 11 version 24H2 or later,

and it must be enabled in system settings before use. See: [Sudo for Windows](https://learn.microsoft.com/zh-cn/windows/advanced-settings/sudo/)

Common examples:

`March7th Launcher.exe -h` (show help)

`March7th Launcher.exe daily` (launch the GUI and start Daily Training)

`March7th Launcher.exe main -e` (exit automatically after the task finishes successfully)

Common task names include: `main` (full workflow), `routine` (Daily), `daily` (Daily Training), `power` (Spend Trailblaze Power), `currencywars` (Currency Wars), and more.

If you know you want to run a task but forgot the exact task name, run `March7th Launcher.exe -l` to see the latest list.

> This program is a free open-source project. If you paid for it, request a refund immediately.
>
> This project has been seriously affected by reselling. Please help report resellers.

## Home Tasks

### Full Workflow

`Full Workflow` is the recommended entry point for unattended daily use.

Based on your current settings, the assistant runs only content that is both enabled and refreshed. In the current version, the full workflow usually handles the following in sequence:

Redeem codes, Daily Training, activities, Echo of War, spending Trailblaze Power, Currency Wars score rewards, Divergent Universe score rewards,

field farming, Simulated Universe / Divergent Universe, Memory of Chaos, Pure Fiction, Apocalyptic Shadow, and finally reward collection.

Disabled tasks are skipped automatically. Tasks already completed or not yet refreshed for the next cycle are not repeated.

The default daily refresh time is 4:00 AM. Weekly content usually refreshes every Monday at 4:00 AM.

### Daily

The `Daily` menu on the home page includes `Daily`, `Daily Training`, and `Spend Trailblaze Power`.

`Daily` ignores refresh timers for this daily slice and runs the enabled steps based on your current settings: redemption codes, cultivation target initialization, activity checks, Echo of War, spending Trailblaze Power, Daily Training, and final reward collection. Only disabled items are skipped automatically.

`Daily Training` first checks which training objectives are still unfinished, then attempts to complete them automatically. If you only want to farm stages with Trailblaze Power, use `Spend Trailblaze Power` directly.

`Spend Trailblaze Power` automatically calculates the number of runs based on the instance type and instance name you selected in settings,

and also works together with options such as Reserved Trailblaze Power, Fuel, support characters, and training targets.

If you disable `Enable Spend Power` in Power Settings, both `Full Run` and `Daily` will skip Echo of War and Spend Trailblaze Power together. Running `Spend Trailblaze Power` as a standalone task is not affected by this switch.

### Currency Wars

The current version supports `Currency Wars: Zero-Sum Game`. The home-page entry offers both `Run Once` and `Loop Run`.

If you enabled `Currency Wars score rewards` in settings, the full workflow checks weekly score rewards automatically.

If they are not finished, it will enter Currency Wars and process the weekly score.

In settings, you can further configure `Standard Match / Overclock Match`, quick presets, rank difficulty, strategy, speedrun mode,

and whether to start fast planar ornament extraction after claiming score rewards.

### Divergent Universe / Simulated Universe

The current version supports `Divergent Universe: Grove of Epiphany`. The home-page entry offers `Run Once`, `Loop Run`, and `Take Over Mid-Run`.

If you enabled `Divergent Universe score rewards` in settings, the full workflow will check the weekly score rewards automatically.

If they are not finished, it will enter Divergent Universe and complete the weekly score.

In settings, you can further configure `Ordinary Extrapolation / Cyclical Extrapolation`, difficulty level, station priority, low-performance compatibility mode,

and whether to automatically run ornament extraction after claiming score rewards.

> The `Simulated Universe / Divergent Universe` settings page is generally used to repeatedly farm relic EXP and Lost Crystal until the weekly cap of 100 elite enemies.
>
> The Simulated Universe part relies on the [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) project, which is currently in a stalled maintenance state. If you encounter problems, it is recommended to switch to Divergent Universe instead.

### Field Farming

Field farming relies on the [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) project. The home-page menu provides `Quick Start`, `Original Run`, `Update Field Farming`, `Reset Config`, `Open Program Directory`, and `Open Project Homepage`.

If you need to continue from an interrupted route, use `Original Run` to open Fhoe-Rail’s own interface, then choose the appropriate mode in that project.

Before using it, make sure all required anchors are unlocked and clear any quests that may interfere with teleporting or pathfinding.

Adult female ranged characters without displacement are usually more stable, such as Asta and March 7th. Characters like Acheron can be paired with dedicated route variants.

> 60 FPS is required. Other graphics settings usually do not matter much.
>
> All field-farming routes are recorded manually by volunteers. Optimized routes and new-version maps are always welcome.

### Treasures Lightward

The current `Treasures Lightward` section contains three challenge categories:

- `Memory of Chaos`
- `Pure Fiction`
- `Apocalyptic Shadow`

All three can be enabled independently and configured with their own stage range and two-team lineups. After the weekly reset, the full workflow processes them in order based on your switches and configuration.

If you only want to run one of them separately, you can also start it directly from the home page.

### Toolbox

The `Toolbox` in the left navigation bar provides several commonly used helper features:

- `Game Screenshot`: Check whether the program is capturing the correct game image, and also OCR selected text.
- `Auto Dialogue`: Start it after entering a story dialogue scene. Not supported in Cloud Honkai: Star Rail.
- `Redeem Code`: Execute the redemption codes currently configured.
- `FPS Unlock`: Switch between 60 / 120 FPS on supported platforms.
- `Touchscreen Mode`: Launch the game using the mobile cloud-game UI, implemented through a [third-party project](https://github.com/winTEuser/Genshin_StarRail_fps_unlocker).

If you encounter image recognition issues, the first thing to do is open `Toolbox → Game Screenshot` and confirm that the captured image is correct.

## Configuration Guide

Click `Settings` in the lower-left corner to open the settings page.

### Program Settings

#### Log Level

Usually the default `Brief` level is enough. If you encounter issues, switch to `Detailed` to help troubleshooting.

#### Game Path / Launcher Path

If you start the game before launching the assistant, the `Game Path` is usually detected automatically. If you set it manually,

do not accidentally choose the launcher `miHoYo Launcher\launcher.exe`. The actual game executable is `Star Rail Game\StarRail.exe`.

If you want to update the game or pre-download through the HoYoverse launcher, you also need to configure the `HoYoverse Launcher Path`.

#### After Task Completion

The current version supports `None`, `Exit`, `Shutdown`, `Sleep`, `Hibernate`, `Restart`, `Log off`, `Turn off display`, `Run script`, `Loop`, and more.

`Exit` means exiting the game. `Run script` requires an additional script path. Operations such as `Shutdown` and `Sleep` will show a prompt and wait for a short time so you can cancel them.

#### Scheduled Run

`Loop mode` is still kept for compatibility with older configs, but the new version recommends using `Scheduled Tasks` on the `Logs` page instead.

Scheduled tasks support:

- Starting built-in tasks such as `Full Workflow`, `Spend Trailblaze Power`, and `Currency Wars`
- Starting external programs or scripts
- Setting a timeout and force-stopping a single task
- Sending notifications after completion
- Configuring an action after completion
- Automatically terminating specified processes after completion

If you run the assistant 24/7, prefer `Scheduled Tasks` on the Logs page instead of relying on the old loop mode.

### Trailblaze Power and Daily Settings

#### Instance Type / Instance Name

These two options together determine which instance is farmed when spending Trailblaze Power. The assistant calculates the number of runs automatically.

If events such as `Planar Fissure` are detected, the assistant also prioritizes the configured instance here.

#### Use Reserved Trailblaze Power / Use Fuel

These options control whether Reserved Trailblaze Power or Fuel is consumed when spending Trailblaze Power. Each has its own single-run limit.

#### Support Character

After enabling `Use Support Character`, the assistant will try to use support when needed. After enabling `Force Use Support Character`, it will prioritize support characters for every run.

#### Training Target

After enabling `Training Target`, the assistant automatically matches trace or relic instances based on the target. If it cannot identify the target, it falls back to the default instance you configured manually.

#### Echo of War

After enabling it, the full workflow prioritizes the weekly three `Echo of War` attempts and supports configuring from which weekday they start.

### Currency Wars Settings

If you only want to automatically claim all weekly Currency Wars score rewards, just enable `Enable Currency Wars score rewards`.

Common options include:

- `Category`: Standard Match / Overclock Match
- `Quick Preset`
- `Rank Difficulty`
- `Currency Wars Strategy`
- `Restart when certain modifiers appear`
- `Enable Speedrun Mode`

### Divergent Universe / Simulated Universe Settings

If you only want to automatically claim all weekly Divergent Universe score rewards, enable `Enable Divergent Universe score rewards`.

The `Divergent Universe` page is mainly for weekly score rewards, index unlocks, and level progression,

including Ordinary Extrapolation / Cyclical Extrapolation, difficulty, low-performance compatibility mode, ornament extraction after rewards, station priority, and more.

The `Simulated Universe / Divergent Universe` page is used for farming relic EXP and Lost Crystal until the weekly cap of 100 elite enemies. Available options include:

- `Run Mode`: Integrated / Source code (Simulated Universe only)
- `Category`: Divergent Universe / Simulated Universe
- `Run Frequency`: Weekly / Daily
- `Run Count`
- `Automatically claim Simulated Universe immersion rewards`
- `Path` (Simulated Universe only)
- `Difficulty` (Simulated Universe only)
- `Enable Simulated Universe GPU acceleration` (Simulated Universe only)

If you choose `Source code` mode, make sure a usable Python environment is available on the machine.

### Field Farming Settings

Besides the enable switch, the field farming page also supports:

- `Run Mode`: Integrated / Source code
- `Auto switch team`
- `Map version`
- `Preferred planet`
- `Buy technique snacks and synthesize snacks`
- `Buy tokens and expired parcels`

If you choose `Source code` mode, make sure a usable Python environment is available on the machine.

### Treasures Lightward Settings

`Memory of Chaos`, `Pure Fiction`, and `Apocalyptic Shadow` each support configuring:

- Whether to enable it
- Stage range
- Two-team lineup
- Last run time

It is recommended to configure your teams first, then let the full workflow handle the weekly content.

### Cloud Honkai: Star Rail

After enabling `Use Cloud Honkai: Star Rail`, the assistant will control the cloud game in a browser to run tasks such as spending Trailblaze Power.

Common options include:

- `Run in fullscreen`
- `Maximum queue wait time`
- `Browser type`
- `Use domestic mirror to download browser and driver`
- `Save browser data`
- `Browser image scaling (DPI)`
- `Enable headless mode (background run)`
- `Automatically switch to windowed mode when not logged in`

Headless mode does not support Simulated Universe (not including Divergent Universe) or field farming. If you want to run daily tasks and Trailblaze Power farming in the background, this group of settings is especially important.

### Miscellaneous Settings

The `Miscellaneous` page mainly contains helper switches that improve stability and automation. Common ones include:

- `Enable auto battle and 2x speed detection`: Try to enable auto battle and 2x speed before the game starts, and keep them active during built-in combat scenes such as Trailblaze Power farming and Currency Wars.
- `Enable automatic resolution change and disable Auto HDR`: When launching the game through the assistant, automatically switch to 1920×1080 and disable Auto HDR. Recommended for local mode users.
- `Enable automatic game-path configuration`: Try to detect the path automatically from shortcuts, the official launcher, or a running game process.
- `Prefer background screenshots`: Recommended by default. It can reduce interference from overlays and floating windows.
- `Launch when user signs in`: Start through Windows Task Scheduler at sign-in. For truly unattended use, you usually also need to configure system auto-login yourself.

About `OCR Acceleration Mode`: keeping it on `Auto` is recommended first. The modes work as follows:

- `Auto` (default): On Windows 10 18362 and later, prefer ONNXRuntime (DirectML) GPU acceleration.
- Otherwise, if OpenVINO is detected, use OpenVINO CPU. If neither applies, fall back to ONNXRuntime CPU.
- `GPU (ONNXRuntime DirectML)`: Force DirectML GPU acceleration and fall back automatically if the environment is unsupported.
- `CPU (OpenVINO)`: Force OpenVINO CPU inference. On pure CPU workloads, OpenVINO is often faster than ONNXRuntime CPU,
- and the current version applies a temporary workaround for the OpenVINO CPU runtime cache issue. If available physical memory drops below 1 GB, it will automatically fall back to ONNXRuntime CPU.
- `CPU (ONNXRuntime)`: Force ONNXRuntime CPU inference. It has the best compatibility and the most stable memory behavior.
- If you encounter recognition issues, crashes, or unusually high memory usage, switch manually to `CPU (ONNXRuntime)` first.

### Notifications

The current version supports more notification channels than older versions. Common ones include:

- Windows native notification
- Telegram
- Matrix
- ServerChan Turbo
- ServerChan 3
- Bark
- SMTP (email)
- OneBot
- Go-cqhttp
- DingTalk
- Pushplus
- WeCom bot / WeCom app
- Gotify
- Discord
- Pushdeer
- Feishu
- MeoW
- KOOK
- Webhook
- Custom notification

In addition to choosing the channel, you can also configure:

- `Notification level`
- `Merge notifications`
- `Send images`
- `Notification format`

Telegram, Matrix, SMTP, OneBot, WeCom, Feishu, KOOK, Webhook, and similar channels support richer notification content.

Whether images are actually sent depends on both the selected channel and your configuration.

### Hotkey Settings

Hotkey settings are located on the `Miscellaneous` page and only affect built-in assistant functions. They can configure shortcuts such as Technique, Map, Warp, and Stop Task.

Among them, the `Technique` hotkey mainly affects built-in tasks such as Trailblaze Power farming and Treasures Lightward.

If you need to modify hotkeys for Simulated Universe or field farming, check the documentation and config files of the corresponding third-party project.

### Account Management (Windows only)

The `Account` page is shown only on Windows. It is mainly used to export and switch multiple local game accounts, and does not support `Cloud Honkai: Star Rail`.

The recommended order is:

1. Fully enter the game until you see your character standing in the overworld.
2. Click `Export current game account` to save the current account into the local list.
3. When you want to switch later, select the target account in the list and click `Import selected account`.

The account page also supports:

- `Rename account`: give the saved local account a more recognizable name
- `Delete account`: remove saved local account data
- `Refresh`: reload the local account list
- `Clear registry`: clean up related account information stored on the current machine, useful when troubleshooting account-switching issues

`Auto login` additionally stores the username and password you entered for that account, and tries to fill them in automatically when the login expires.

This feature carries some risk and should only be used when you fully understand what you are doing.

> Important: if you export an account before fully entering the game, the assistant may read the UID of the previous account, causing the saved file to mismatch the actual account.

## Update

When a new version pop-up appears, click download. You can also click `Check for updates` at the bottom of the settings page, or manually double-click `March7th Updater.exe`.

If you update manually, download the full package named like `March7thAssistant.zip` or `March7thAssistant.7z`,

then extract it and overwrite the old installation directory with all files.
