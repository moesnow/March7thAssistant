# FAQ

> This document was translated from the Simplified Chinese version using AI. Last updated: 2026-04-24. If anything differs, the Simplified Chinese version takes precedence.

[Follow our Bilibili account for updates and tutorials](https://space.bilibili.com/3706960664857075)

### Q: The assistant often fails to update or downloads very slowly. What should I do?

A: March7thAssistant integrates the third-party service [MirrorChyan](https://mirrorchyan.com/?source=m7a-faq), a paid content distribution platform for open-source projects.

It provides us with a free update-check API, but the actual download service is paid.

Even if you do not buy MirrorChyan download service, you can still switch the download source to the overseas source (GitHub) in settings after an update is detected.

If you purchased and entered a CDK, updates no longer depend as much on your own network conditions and downloads will usually be faster and more stable.

The same CDK can also be used for other projects that integrate MirrorChyan, such as MAA.

[First-time download from MirrorChyan high-speed channel](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-faq)

### Q: The assistant starts slowly / cannot find an executable / shows error 2147942402 / keeps getting deleted by antivirus. What should I do?

A: Add the `assistant folder` to your antivirus exclusions / allowlist / trust zone, then extract the package again and overwrite the old files.

Windows Defender: `Virus & threat protection` → `Manage settings` → `Add or remove exclusions`. You can refer to the illustrations in [#373](https://github.com/moesnow/March7thAssistant/issues/373).

(You may also need to set `App & browser control` → `Smart App Control settings` → `Off`.)

Huorong Security: `Main screen` → `top-right menu` → `Trust Zone`. You can refer to this [tutorial](https://cs.xunyou.com/html/282/15252.shtml).

### Q: After enabling filters, FPS overlays, or performance-monitoring tools, why does recognition keep failing or why do I get “failed to switch to interface”?

A: These tools add extra text or visual effects on top of the game image, which can break the assistant’s image recognition and OCR checks.

Common troublemakers include `NVIDIA Freestyle filters`, `HDR`, `FPS monitoring HUDs`, `MSI Afterburner`, `RTSS`, `GamePP`,

as well as any floating overlay that shows `FPS / CPU / GPU` information.

Some laptop or motherboard vendor utilities can also cause similar issues, such as `Eye Care Mode`, `Vivid Mode`, `Game Enhancement`, `Color Optimization`, or `Scene Mode`.

Even if they do not show obvious overlays, they may still change color, brightness, or contrast in the captured image.

Completely disable these filters, monitoring utilities, and enhancement tools first, then try again.

Sometimes the hardest thing to notice is the filter you already got used to. If you do not see many other users reporting the same error, you should usually investigate your own PC environment first.

If the log shows something like `detected suspected monitoring overlay text`, this is almost certainly the cause.

You can also open `Toolbox → Game Screenshot` and inspect whether the image captured by the assistant is clean or blocked by overlays.

### Q: Why does Divergent Universe / Simulated Universe / planar extraction fail to choose a team, or automatically choose a certain character? How do I change it?

A: These features use the team remembered by the game itself. If a required character is missing, the assistant will automatically try `Team 1`.

To change the team, manually set the desired team in game, enter the corresponding interface once, then leave and check whether the game’s remembered team has updated.

### Q: Why doesn’t auto-battle work, why doesn’t it interact with the portal, or why is the character running around randomly?

A: In most cases, this is caused by your key bindings not matching the assistant’s default assumptions. Check in this order:

1. First, check whether you changed the default in-game keys, especially auto-battle (`V`), interact (`F`), and movement (`WASD`). If you changed them, restore the default key bindings and test again.

2. Then check whether `Settings → Miscellaneous → Enable auto battle and 2x speed detection` is turned on in the assistant.

3. If the issue only affects auto-battle, also check in game whether `Settings → Battle Features → Retain auto-battle setting` is set to `Yes`. If necessary, enable auto-battle manually once and try again.

### Q: After starting a task, can I no longer use the keyboard or mouse or switch to the background?

A: In local game mode, most automation still depends on the current desktop image and input state. It is not recommended to take over the keyboard or mouse, and it is also not recommended to switch the game to the background.

If you need background execution, prefer `Cloud Honkai: Star Rail`. Tasks such as spending Trailblaze Power, Daily Training, Currency Wars, and Divergent Universe currently support background running.

Field farming and Simulated Universe still require the game to stay fullscreen in the foreground.

If you need background for local mode, you can also try [Remote Local Multi-User Desktop](https://m7a.top/#/assets/docs/Background).

### Q: What does Full Workflow do?

A: `Full Workflow` automatically handles currently enabled and refreshed content. It usually includes:

redeem codes, Daily Training, activities, Echo of War, spending Trailblaze Power, Currency Wars score rewards, Divergent Universe score rewards,

field farming, Simulated Universe / Divergent Universe, Memory of Chaos, Pure Fiction, Apocalyptic Shadow, and finally reward collection.

Completed tasks or tasks that have not refreshed yet are skipped automatically. The default daily refresh time is 4:00 AM, and weekly content usually refreshes every Monday at 4:00 AM.

### Q: What should I do if the prompt window cannot be found?

A: Check whether the in-game language is set to Simplified Chinese.

### Q: Newly added instances are missing? Treasures Lightward is missing new characters?

A: First make sure you are on the latest version. If instances are still missing, edit `assets\config\instance_names.json` and add them manually.

If new characters are missing from `Memory of Chaos / Pure Fiction / Apocalyptic Shadow / Support`,

go to the corresponding interface, use `Capture Screenshot` from the toolbox, select the character avatar, click `Save Selected Screenshot`,

put the image into `assets\images\share\character`, and update `assets\config\character_names.json`.

You are also welcome to upload the files in an `uncompressed` form to [Issues](https://github.com/moesnow/March7thAssistant/issues), for example as a zip archive, or submit a [PR](https://github.com/moesnow/March7thAssistant/pulls).

### Q: What should I do if memory usage keeps rising during runtime, the game suddenly freezes or crashes, or the whole system restarts?

A: If memory usage becomes abnormally high, the program crashes unexpectedly, or the game image becomes unstable during execution, first check OCR acceleration compatibility.

By default, the assistant uses ONNXRuntime DirectML GPU acceleration on Windows 10 build 18362 or later.

On environments that do not support DirectML, such as Linux or some ARM devices, it will use OpenVINO CPU inference automatically if OpenVINO is detected.

**OpenVINO can show continuously increasing memory usage on some machines**. The assistant periodically rebuilds the inference engine to release memory,

and automatically falls back to ONNXRuntime CPU when available physical memory drops below 4 GB. However, if the machine itself has little memory, you may still notice obvious fluctuations.

**It is recommended to switch OCR acceleration mode manually to `CPU (ONNXRuntime)` first** (`Settings → Miscellaneous → OCR Acceleration Mode`).

After switching, run the assistant again and observe whether memory behavior and stability improve. If the problem disappears, it means the previous mode is incompatible with your environment and you can keep using ONNXRuntime CPU.

If DirectML GPU acceleration causes crashes or recognition issues, it is also recommended to fall back to `CPU (ONNXRuntime)` first.

### Q: What should I do if the window flashes and closes right after double-clicking launch, the GUI never opens, or the terminal window closes immediately when running commands?

A: These symptoms can usually be investigated together.

If you directly double-click `March7th Launcher.exe` or another executable and the terminal flashes then disappears or the GUI never opens,

switch to starting it from a terminal so you can actually see the error message.

Open PowerShell, Windows Terminal, or CMD as administrator, then navigate to the assistant folder and run the corresponding command.

For example:

PowerShell:

```powershell
& '.\March7th Launcher.exe' -S
```

CMD:

```cmd
"March7th Launcher.exe" -S
```

If your system supports [Sudo for Windows](https://learn.microsoft.com/zh-cn/windows/advanced-settings/sudo/), you can also use `sudo`.

According to Microsoft documentation, `Sudo for Windows` is only available on Windows 11 version 24H2 or later, and it must also be enabled in system settings first.

If the terminal shows an error after launching this way, troubleshoot based on the actual error first.

Common causes are still insufficient permissions, antivirus deleting files, blocked dependencies, or an incorrect working directory.
