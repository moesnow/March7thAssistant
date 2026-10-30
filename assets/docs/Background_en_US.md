# Background Running

> This document was translated from the Simplified Chinese version using AI. Last updated: 2026-10-31. If anything differs, the Simplified Chinese version takes precedence.

To keep using your computer while the assistant runs tasks, choose one of the following three approaches:

| Approach | For | Your keyboard and mouse | Setup |
|------|------|-----------|---------|
| Windows background mode (recommended) | Local game on Windows | Briefly borrows the mouse for clicks and returns it | Switch in settings |
| Cloud Honkai: Star Rail | Cloud game | Not used | Enable in settings |
| Remote local multi-user desktop (advanced) | Local game on Windows | Does not use your current desktop | Requires modifying system components |

## Windows Background Mode (Recommended)

The game window stays behind your other windows and the assistant operates the game through window messages, so you can keep using your computer while tasks run. Foreground mode remains the default; background mode has to be turned on manually.

### How to Enable

In `Settings → Miscellaneous → Local control mode`, select `Background`, then read and confirm the notice that appears; it takes effect the next time a task starts. Turn Auto Dialogue off and on again to apply it there.

You can also edit the configuration file directly:

```yaml
local_control_mode: background
background_mouse_protection: false
```

The cloud game uses its own input method and is not affected by this setting.

### Requirements

- The game window can stay behind other windows but **must not be minimized**: a minimized window cannot be captured and does not process input.
- **Keep the system unlocked** while tasks run: while the lock screen or a secure desktop such as UAC is shown, the cursor cannot be read or moved, and background operation stops with an explanation.
- If the game runs with administrator privileges, the assistant needs the same privileges (a normally started assistant requests them automatically).
- Background mode always uses window capture; if window capture fails, recognition stops instead of falling back to a desktop screenshot that might include other applications.

### Effects on Your Mouse and Keyboard

- **Clicks and drags** briefly borrow the real cursor and return it to its original position afterwards. If you keep moving the mouse meanwhile, that movement is carried back too: the cursor returns to your area and keeps moving there instead of staying at the click point. When an absolute pointing device such as a pen tablet, touch screen, or remote desktop has already put the cursor back where you are, the cursor is not moved again.
- Before operating, the assistant **waits for the mouse to be idle**: if interference occurs before pressing, it retries up to three times, then shows "Waiting for the mouse to be idle. The task will resume automatically." and waits. The task resumes automatically and can still be paused or stopped as usual. Slight jitter within 3 pixels does not count as interference.
- **Key presses** do not take over the foreground window or keyboard focus, but the game only accepts keys while it is "active", so each background key press briefly makes the game believe it is active. In the open-world view, the game locks the cursor to the center of the window during that moment; the lock is released when the key press ends and the cursor is returned.
- **Scrolling**: when the game is not in the foreground, the banner "Scrolling temporarily brings the game to the foreground" appears, the game is briefly brought to the front to scroll, and your previous window and cursor are restored afterwards. If you switch windows yourself during this time, the remaining scrolling for that step stops, your window choice is kept, and focus is not pulled back to the old window. When the game is already in the foreground, it scrolls directly.
- **Mouse protection** (optional): expand "Local control mode" to turn on "Temporarily protect the mouse after retries fail" (off by default). It only blocks the physical mouse briefly after repeated conflicts and keeps the keyboard and the pause/stop hotkeys available; each lock lasts at most two seconds and is released immediately when the action ends, pauses, stops, or fails. A protected long press or drag that lasts longer than two seconds releases the held button, and the task checks the screen again.
- A normal attack without coordinates recognizes the cursor lock of the open-world view and presses and releases at the current point, without reusing the click position from a previous screen.
- Auto Dialogue runs inside the GUI: while the mouse is in use or the window is temporarily unavailable, it only waits briefly and leaves the work to the next check, so the interface does not freeze.

### Window State Changes

- **Switching windows**: bringing the game to the front or switching to another window is normal and does not end the task with an error. If it happens in the middle of an input, the keys, mouse button, and temporary protection held by that input are released first, and the task then recognizes the game screen again; keys, text, clicks, and drags that were already sent are not replayed automatically.
- **Minimized or temporarily invisible**: no input is sent; screenshots and input wait up to 60 seconds and prompt you to restore the game window. Once it is restored, the task continues automatically (the input put on hold during the wait returns as not completed and is not sent later); on timeout the task stops with the reason, for example the log message "游戏窗口已最小化（已等待 60 秒）" (the game window is minimized; waited 60 seconds). Within one period of unavailability the wait happens only once, and time spent paused does not count. The program never restores or activates the game window by itself.
- **Game process exited**: reported immediately as "游戏进程已退出" (the game process has exited) without waiting, and without asking you to restore the window. During game startup, the game is closed and restarted as in foreground mode; in the middle of a task, it ends as a normal error.
- **Game window not found while the process is still running** (for example while the game is starting or recreating its window): the assistant also waits up to 60 seconds, and a timeout is handled as a normal error.
- **Game busy loading**: if the game does not process a mouse message within 0.5 seconds, the input is released and returned as not completed, and the task checks the screen again instead of ending.
- If the window moves or changes size, or the coordinates fall outside the game view during an input, the input is likewise released and returned as not completed.

"Not completed" only means that the input was not fully sent. An operation that was fully sent and only ran into a window switch or pause while finishing still returns success, so the task does not repeat a click or key press that already took effect.

### Pause and Stop

Pausing and stopping first release the keys and mouse held by the backend and end any temporary foreground operation, then acknowledge the state. After resuming from a pause, interrupted long presses or drags are not replayed; check the current screen before continuing. When you stop a task from the GUI, a stop command is sent first and the GUI waits for the "input released" acknowledgement before ending the process; if no acknowledgement arrives in time, the original forced termination is still used and logged. The command-line `--control <run ID> stop` uses the same command.

### Known Limitations

- The launcher and standalone programs such as Fhoe-Rail and third-party Simulated Universe tools do not gain background capability; run them in the foreground as they require.
- While you keep using the mouse, steps that need clicks keep waiting for the mouse to become idle; mouse protection only blocks the physical mouse and cannot guarantee that clicks complete while you keep operating it.
- Text input clicks the most recently located input box again within the same activation session and then sends the characters; IME candidates and appending text in arbitrary editors are not supported.
- Currency Wars reward orbs are collected with short sweeps that release the mouse after each segment; if a step is not completed, the current stage is kept and checked again in the next round instead of going straight to purchasing or deploying.
- If you run into recognition or operation problems, switch back to foreground mode first to confirm whether the problem is related to background mode, then report it with the logs.

## Cloud Honkai: Star Rail

With `Cloud Honkai: Star Rail` enabled, tasks such as spending Trailblaze Power, Daily Training, Currency Wars, and Divergent Universe no longer require a fixed window; they support background running and can also run headless. Field farming and Simulated Universe still require the game to stay fullscreen in the foreground.

The cloud game does not depend on a local game window and can also run on macOS, Linux, [Docker](/assets/docs/Docker.md), and [Termux on Android](/assets/docs/Termux.md); see the [Usage Guide](/assets/docs/Tutorial_en_US.md) for how to enable it.

## Remote Local Multi-User Desktop (Advanced)

> On the same computer (no second computer needed), sign in to another Windows user session through local Remote Desktop and let the game and the assistant run there in foreground mode, without using the keyboard and mouse of your current desktop at all. This requires patching the system to allow multiple simultaneous sign-ins, the setup is more involved, and the patch may stop working after system updates. In most cases, try Windows background mode first.

 * Emulators have many drawbacks such as stuttering and high resource usage; running directly on the PC costs less than an emulator
 * We recommend the Remote Desktop service built into Windows
 * Tutorials for enabling multi-user Remote Desktop on Windows (in Chinese):
   * [Detailed tutorial by_Rin](https://www.bilibili.com/read/cv24286313/) (⭐Recommended⭐)
   * [RDPWrap method](https://blog.sena.moe/win10-multiple-RDP/)
   * [File modification method](https://www.wyr.me/post/701)
 * All files used in the [detailed tutorial by_Rin](https://www.bilibili.com/read/cv24286313/): [download link](https://github.com/CHNZYX/asu_version_latest/releases/download/RDP/LocalRemoteDesktop1.191_by_lin.zip)
   * Alternative links
     * [Baidu Netdisk](https://pan.baidu.com/s/13aoll4n1gmKlPT9WwNYeEw?pwd=jbha) extraction code: jbha
     * [GitHub mirror](https://github.kotori.top/https://github.com/CHNZYX/asu_version_latest/releases/download/RDP/LocalRemoteDesktop1.191_by_lin.zip)

While the assistant runs in the remote session, keep the Remote Desktop connection open and do not disconnect the session. By default, the remote session stops drawing when the Remote Desktop window is minimized, which may make screenshots fail; if you need to minimize it, create a DWORD value `RemoteDesktop_SuppressWhenMinimized` with data `2` under `HKEY_CURRENT_USER\Software\Microsoft\Terminal Server Client` for your current user, then reopen the Remote Desktop connection.

### For Windows 11 Users

The `SuperRDP` tool mentioned in the [detailed tutorial by_Rin](https://www.bilibili.com/read/cv24286313/) may no longer work; we recommend [TermsrvPatcher](https://github.com/fabianosrc/TermsrvPatcher) instead. In mainland China you can also download it from the alternative link: [Lanzou Cloud](https://wwsj.lanzout.com/i4V8u2np8dna).

**Note:** This method only covers step `4. 多用户同时登陆补丁` (the multi-user simultaneous sign-in patch) of the [detailed tutorial by_Rin](https://www.bilibili.com/read/cv24286313/); follow the original tutorial for the remaining steps.

**Usage:**

1. Clone the repository with `git clone`, or download the archive directly.
2. After downloading, extract the archive, right-click `TermsrvPatcher.ps1`, and choose "Run"; the script completes everything automatically.

If you prefer to modify the file manually, see the blog post [File modification method](https://www.wyr.me/post/701). Note that some steps in that post may not apply to Windows 11:

- **String to search for in Windows 11 (regex):**
   `39 81 3C 06 00 00 0F (?:[0-9A-F]{2} ){4}00` (in practice, searching for `39 81 3C 06 00 00 0F` is enough; modify it only if the remaining hex bytes match the regex)
- **Replace with:**
   `8B 81 38 06 00 00 39 81 3C 06 00 00 75`
