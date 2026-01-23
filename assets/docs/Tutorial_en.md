# User Guide

## Hardware Requirements

| Platform | Local Game | Cloud Game |
|----------|------------|------------|
| Windows  | ✅          | ✅          |
| macOS    | ❌          | ✅          |
| Linux    | ❌          | ✅          |

To run locally, you must use the PC client with a 1920*1080 resolution window (or full screen if windowed is not available),

and close any software that might affect the game display, such as FPS monitoring HUDs, MSI Afterburner, GamePP, HDR, or NVIDIA Game Filters.

**macOS / Linux Users**: You can use Cloud Game mode via source code execution, or use [Docker Deployment](/assets/docs/Docker.md).

> **Why use the PC client?** Unlike mobile-only games, Honkai: Star Rail on PC can better utilize computer hardware performance.
>
> Simulators suffer from lag and high performance consumption. You wouldn't want to update two clients like a fool every time there's a version update, right?
>
> If you need to run in the background, you can use [Remote Local Multi-User Desktop](/assets/docs/Background.md) to enable multiple desktops on one computer simultaneously.

## Platform Support

## Download

Click [Releases](https://github.com/moesnow/March7thAssistant/releases/latest) to open the download page and scroll to the bottom.

Find the file named like `March7thAssistant_full.zip(7z)` and click to download.

> March7thAssistant integrates the third-party service [Mirrorchyan](https://mirrorchyan.com/?source=m7a-faq) (a platform for paid content distribution for the open-source community).
>
> If downloading is slow in Mainland China, you can try [Click here to go to Mirrorchyan high-speed download](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-faq)

## Unzip

Find the downloaded file named like `March7thAssistant_full.zip(7z)`, right-click and select "Extract All".

> If you installed third-party decompression software, the operation might be named "Extract".

## Run

Find the unzipped folder named like `March7thAssistant` and double-click to open it. It should contain at least the following files (folders):

- `March7th Launcher.exe`
- `March7th Assistant.exe`
- `March7th Updater.exe`
- `assets`
- `libraries`

Double-click `March7th Launcher.exe` to open the graphical interface and agree to the "Disclaimer".

> This program is a free open-source project. If you paid for it, please request a refund immediately!!!
>
> This project has been seriously threatened by reselling behaviors. Please help us!!!
>
> Resellers serve no good! Every penny you pay to resellers makes open-source automation harder. Please refund and report the merchant!!!

## Tasks

### Full Run

Executes in the order of `Daily` → `Power` → `Fhoe-Rail` → `Simulated Universe` → `Gold and Gears` → `Claim Rewards`.

Tasks judged as completed will not be run repeatedly. Daily and Fhoe-Rail reset at 4 AM every day,

while Simulated Universe and Gold and Gears reset at 4 AM every Monday.

### Fhoe-Rail

Invokes the [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) project. Runs independently and does not check if it has been completed today.

Please unlock all anchors beforehand and complete all tasks that interfere with image recognition teleportation on the map, including Cycranes and doors that need unlocking.

Adult female models (ranged attacks with no displacement) are best for map running, such as Asta and March 7th. Melee characters may cause anomalies. Characters like Acheron can select the dedicated farming mode.

> Lighting quality is recommended to be set to Medium or higher, 60 FPS. Other graphics settings do not affect operation.

### Simulated Universe

Invokes the [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) project. Runs independently and does not check if it has been completed this week.

It will stop only after running 34 times per week. Progress is saved even if closed midway. If 'Claim Immersion Rewards' is enabled, it will only use Immersifiers and will not consume Trailblaze Power.

Default World: For example, if your current Simulated Universe default world is 4, but you want to automate World 6, please enter World 6 once manually to change the default world.

### Gold and Gears

Runs independently and does not check if it has been completed this week. Automatically recognizes star counts and skips execution if full stars are achieved.

## Settings

Click `Settings` in the bottom left corner to enter the Assistant settings interface.

### Program

#### Log Level

Generally, keep the default `Info`. Switch to `Debug` if you encounter anomalies to facilitate troubleshooting.

#### Game Screenshot

Can be used to self-judge if the image acquired by the program is correct. Also supports OCR text recognition after selection, which can be used to copy some rare characters in dungeon names.

#### After Mission Completed

Some operations to perform after the task is completed. `Exit` means exiting the game.

`Loop` refers to running the program unattended 7x24 hours based on Trailblaze Power recovery (only effective for Full Run).

`Shutdown`, `Hibernate`, `Sleep`, and `Log off` will prompt and wait for 1 minute before executing.

#### Trailblaze Power Required for Loop Run Restart

This option only takes effect when `After Mission Completed` is set to `Loop`.

The program will run again after Trailblaze Power recovers to the preset value. 4 AM priority is higher than Trailblaze Power.

### Game

#### Game Path

Running the game and then the assistant will automatically configure this option.

If configuring manually, be careful not to select the launcher `Star Rail\launcher.exe`.

`Star Rail\Game\StarRail.exe` is the game executable.

### Power

#### Dungeon Type

The type of dungeon to farm when clearing power. Automatically calculates runs based on Trailblaze Power.

#### Dungeon Name

Besides clearing power, when a task like `Complete 1 time of "XXXX"` appears in Daily Training,

the dungeon set here will be run to complete the task. If you don't want to complete it even if the task exists, please change it to `None`.

#### Enable Support Character

Usually, a support character is used only once when the task `Use support character and win 1 battle` appears in Daily Training.

Enabling this option will use a support character for every dungeon run.

#### Enable Echo of War

Supports automatic judgment of remaining Echo of War runs. Priority is higher than clearing power. Reset time is 4 AM every Monday.

### Fhoe-Rail

Invokes the [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) project.

To continue running from an interrupted map, click `Original Run` to open Fhoe-Rail's own interface, then select Debug Mode.

The `Update Fhoe-Rail` button can update to the latest version with one click.

### Simulated Universe

Invokes the [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) project.

Quick Start, please visit: [Project Documentation](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md)

If you encounter problems, please check before asking: [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)

The assistant uses `Command Line Usage`. Please ensure Python environment variables are configured correctly.

To modify Path and Difficulty, click `Original Run` to open the Auto_Simulated_Universe graphical interface.

The `Update Simulated Universe` button can update to the latest version with one click.

### Forgotten Hall

Numbers represent the number of times the technique is used. `-1` represents the last character to use the technique and basic attack (i.e., the character that starts the battle).

Corresponding English names for characters can be viewed in `March7thAssistant\assets\images\character`.

### Push

Currently supports:

- Telegram
- Serverchan/Turbo
- Bark
- SMTP (Email)
- Dingtalk
- Pushplus
- WeChatworkapp (Enterprise WeChat App Notification)
- WeChatworkbot (Enterprise WeChat Robot Notification)
- OneBot (QQ Robot)
- Go-cqhttp (QQ Robot)
- Gotify
- Discord
- Pushdeer
- Lark
- Custom
- MeoW

> Telegram, SMTP, OneBot, etc., support sending screenshots. PRs adapting other push methods are welcome.

### Hotkey

Hotkey settings only take effect in the built-in functions of the assistant, such as Gold and Gears.

If you need to modify Simulated Universe and Fhoe-Rail, please check the relevant project tutorials.

Simulated Universe `Auto_Simulated_Universe` keys can be modified in `info.yml`.

Fhoe-Rail's source code mode has a `py` file with a name containing `modified keys` in the `utils` directory where `E` and `F` are swapped.

## Update

When a new version popup appears, click download, or manually double-click `March7th Updater.exe`.

For manual update, please download the file named like `March7thAssistant.zip(7z)`,

unzip it, copy all files, and paste them into the old version directory to overwrite.
