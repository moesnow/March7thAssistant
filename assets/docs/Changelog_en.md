# Changelog

## v2026.1.21
- Support automatically using **Deep Immersifier** after claiming **Currency Wars** points
- Added **MeoW** push notification support [#850](https://github.com/moesnow/March7thAssistant/pull/850) @pboymt
- Optimized performance and stability, fixed several known issues
- **Note**: Due to a bug in v2026.1.18, please [Manually Download](https://github.com/moesnow/March7thAssistant/releases/tag/v2026.1.21) to update!!!
- [Fast download for Mirror Chan CDK users](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-release)

## v2026.1.19
- Comprehensive upgrade and optimization of the **GUI**
- Added **Auto 2x Speed** detection before starting the game
- Source code run supports **macOS/Linux** and [Docker Deployment](https://m7a.top/#/assets/docs/Docker)
- Added **Settings** option to Tray right-click menu
- **Cloud Game** headless mode supports QR code login
- Added estimated waiting time for Cloud Game queue
- Upgraded OCR inference engine and models
- Optimized error message for "Executable not found" [Solution](https://m7a.top/#/assets/docs/FAQ)
- Fixed **Power Plan** executing Ornament Extraction when resources are insufficient
- Fixed abnormal OCR recognition for some text
- Fixed blank log window when restoring from tray
- Fixed QR code not refreshing correctly after expiration [#843](https://github.com/moesnow/March7thAssistant/pull/843) @eloay

## v2025.12.31
- Support auto-updating game via **HoYoPlay Launcher** (Enable in "Settings -> Program")
- **Scheduled Task** supports pre-downloading game via launcher
- Only one GUI instance allowed per path
- Fixed more OCR recognition issues [#828](https://github.com/moesnow/March7thAssistant/pull/828) @loader3229
- Fixed Cloud Game not selecting queue correctly [#830](https://github.com/moesnow/March7thAssistant/pull/830) @loader3229
- Fixed window focus issue
- Fixed GUI reload issue after theme switch from tray

## v2025.12.26
- **Scheduled Run** supports multiple tasks and external programs
- Optimized logic when no redemption codes are found
- Adjusted max queue time range for Cloud Game
- Fixed Bilibili Server login UI change check
- Fixed false negative for Daily Training reward claim [#820](https://github.com/moesnow/March7thAssistant/pull/820) @g60cBQ
- Fixed Build Target continuing execution when dungeon not identified [#819](https://github.com/moesnow/March7thAssistant/pull/819) @g60cBQ

## v2025.12.21
- Support **The Herta** and **March 7th (The Herta)** [#813](https://github.com/moesnow/March7thAssistant/pull/813) @loader3229
- Added **Achievement Reward** claim function [#811](https://github.com/moesnow/March7thAssistant/pull/811) @g60cBQ
- Added Auto Redemption Code claim function
- Restored Touch Mode support
- Optimized Scheduled Run trigger logic
- Optimized Currency Wars unfinished match handling
- Full package now includes Cloud Game dedicated browser [#815](https://github.com/moesnow/March7thAssistant/pull/815) @Patrick16262
- Fixed Returnee event page recognition
- Fixed Power Plan execution logic error
- Fixed dungeon continuous challenge count error with Build Target enabled
- Fixed Cloud Game clipboard issue in headless mode [#816](https://github.com/moesnow/March7thAssistant/pull/816) @Patrick16262
- Fixed Fhoe-Rail fast start issue with Cloud Game

## v2025.12.16
- New **Log Interface** and optimized task execution
- Added **Touch Scroll** support to GUI [#799](https://github.com/moesnow/March7thAssistant/pull/799) @g60cBQ
- GUI supports **Minimize to Tray**
- Cloud Game download uses domestic mirror acceleration [#792](https://github.com/moesnow/March7thAssistant/pull/792) @Patrick16262
- Optimized and fixed Cloud Game issues [#800](https://github.com/moesnow/March7thAssistant/pull/800) [#804](https://github.com/moesnow/March7thAssistant/pull/804) @Patrick16262
- Optimized WebHook push with more config options
- Fixed Auto Theme function
- Fixed Divergent Universe point reward category selection
- Fixed Log Interface display issue in non-Chinese languages

## v2025.12.13
- Support **Power Plan**
- Optimized Settings Interface
- Double drops support reading Build Target [#751](https://github.com/moesnow/March7thAssistant/pull/751) @g60cBQ
- Immediately claim rewards after Daily Training completion
- Default to first team if no character configured for Ornament Extraction [#788](https://github.com/moesnow/March7thAssistant/pull/788) @g60cBQ
- FPS Unlocker and Auto Resolution support for Global Server
- GUI auto-reloads on config change

## v2025.12.10
- Optimized and fixed Currency Wars issues
- Dungeon Name and Team Character support manual input and realtime autocomplete
- Support **Notification Level** config (e.g., Error only)
- Compress screenshots before push notification
- Added **KOOK**, **WebHook** push support
- Added **Bark** encryption support
- Added auto-deletion of log files older than 30 days

## v2025.12.8
- Support **Currency Wars**
- Fix Currency Wars issues
- Gacha Records support **UIGF** format import/export
- Teleport to random anchor before clearing power [#760](https://github.com/moesnow/March7thAssistant/pull/760) @Xuan-cc
- Customize Cloud Game issues [#763](https://github.com/moesnow/March7thAssistant/pull/763) @Patrick16262
- Added "Turn off Monitor" option after task completion
- Added confirmation dialog for clearing Gacha Records
- Fixed Build Target Calyx info extraction failure [#764](https://github.com/moesnow/March7thAssistant/pull/764) @g60cBQ
- Fixed script execution failure after task completion [#759](https://github.com/moesnow/March7thAssistant/pull/759) @0frostmourne0

## v2025.12.1
- Support **Cloud · Honkai: Star Rail** [#750](https://github.com/moesnow/March7thAssistant/pull/750)
- Support selecting dungeon dynamically based on **Build Target** [#751](https://github.com/moesnow/March7thAssistant/pull/751)
- Daily Training checks task completion and adjusts execution [#753](https://github.com/moesnow/March7thAssistant/pull/753)
- WeChat Work Robot supports sending images [#742](https://github.com/moesnow/March7thAssistant/pull/742)
- Fixed Immortal Game character selection issue [#747](https://github.com/moesnow/March7thAssistant/pull/747)
- Fixed crash when selecting script after task completion
- Fixed game process termination failure
- Fixed Divergent/Simulated Universe auto-battle detection
- Optimized task order in Full Run
- Optimized Updater
- Optimized Auto Login

## v2025.11.11
- "Run Divergent Universe once" cycle changed to every two weeks
- SMTP supports no username [#730](https://github.com/moesnow/March7thAssistant/pull/730) [#738](https://github.com/moesnow/March7thAssistant/pull/738)
- Fixed v3.7 new Weekly Boss recognition [#728](https://github.com/moesnow/March7thAssistant/pull/728)
- Fixed redemption code entry recognition [#734](https://github.com/moesnow/March7thAssistant/pull/734)
- Fixed Support Character selection click issue

## v2025.11.6
- Support **v3.7** new stages and characters [#725](https://github.com/moesnow/March7thAssistant/pull/725)
- Support continuous challenge for some dungeons
- Refactored **Auto Dialogue** with config options [#720](https://github.com/moesnow/March7thAssistant/pull/720)
- Added multi-monitor FAQ
- Fixed Multi-account login freeze [#723](https://github.com/moesnow/March7thAssistant/pull/723)
- Fixed Simulated Universe UI change issue
- Fixed Event UI change issue
- Fixed Divergent Universe Support UI change issue
- Fixed Echo of War day display error in settings
- Optimized GUI layout

## v2025.10.15
- Support **v3.6** new characters
- Optimized Auto Login and Global Server support [#706](https://github.com/moesnow/March7thAssistant/pull/706)
- Support continue challenge when character dies [#705](https://github.com/moesnow/March7thAssistant/pull/705)
- Optimized timeouts for HDD [#701](https://github.com/moesnow/March7thAssistant/pull/701)
- Added "Pause after success" and "Exit directly after failure" options [#704](https://github.com/moesnow/March7thAssistant/pull/704) [#709](https://github.com/moesnow/March7thAssistant/pull/709)
- Fixed download issues for some users
- Optimized downloader to use system proxy
- Optimized reset config error message

## v2025.9.25
- Support **v3.6** new stages and characters
- Optimized Daily "Synthesize Material" (can be disabled in settings)
- Support usage of empty name in "Support List" to search only for character
- Fixed "Sunday" support character recognition issue
- Fixed crash when updating Gacha Records
- Optimized "Start on User Login" description
- Fixed multiple dungeon name recognition errors

## v2025.9.10
- Support **v3.5** new stages and characters [#687](https://github.com/moesnow/March7thAssistant/pull/687)
- Fixed multiple dungeon name recognition errors
- Fixed mail recognition issue

## v2025.8.13
- Support **v3.5** new stages and characters [#671](https://github.com/moesnow/March7thAssistant/pull/671)
- Fixed multiple dungeon name recognition errors

## v2025.7.20
- Support **Fate** collab characters [#640](https://github.com/moesnow/March7thAssistant/pull/640)
- Gacha Records support collab banner
- Support customizing Map/Warp hotkeys [#635](https://github.com/moesnow/March7thAssistant/pull/635)
- "Auto Dialogue" supports "skip dialogue" [#639](https://github.com/moesnow/March7thAssistant/pull/639)
- Multi-account management supports clearing registry [#636](https://github.com/moesnow/March7thAssistant/pull/636)
- Fixed Planar Fissure event error [#643](https://github.com/moesnow/March7thAssistant/pull/643)
- Fixed exit Simulated Universe error
- Fixed Auto dialogue option issue

## v2025.7.8
- Support **v3.4** new stages and characters [#616](https://github.com/moesnow/March7thAssistant/pull/616)
- Fixed "Shape of Rime" dungeon entry issue

## v2025.6.14
- Support **v3.3** new stages and characters [#580](https://github.com/moesnow/March7thAssistant/pull/580) [#597](https://github.com/moesnow/March7thAssistant/pull/597)
- Support exporting Gacha Records to Excel [#574](https://github.com/moesnow/March7thAssistant/pull/574)
- Support changing Calyx attempts per round [#592](https://github.com/moesnow/March7thAssistant/pull/592)
- Added finer control buttons to sliders in Settings [#591](https://github.com/moesnow/March7thAssistant/pull/591)
- Fixed Divergent Universe pause image [#594](https://github.com/moesnow/March7thAssistant/pull/594)
- Fixed Gacha export crash on abnormal data
- Fixed GUI crash on some options
- Fixed Gotify push exception
- Auto_Simulated_Universe v8.04
- Simulated Universe supports update via Mirror Chan

## v2025.4.18
- Adapted to 2nd Anniversary event icon
- Support **Seele? (Butterfly)** [#548](https://github.com/moesnow/March7thAssistant/pull/548)
- Support configuring "Echo of War" start day [#479](https://github.com/moesnow/March7thAssistant/pull/479)
- Auto breakdown 4-star relics when limit reached [#524](https://github.com/moesnow/March7thAssistant/pull/524)
- OneBot supports sending private and group messages simultaneously [#540](https://github.com/moesnow/March7thAssistant/pull/540)
- Added Omphalos priority setting for Fhoe-Rail [#547](https://github.com/moesnow/March7thAssistant/pull/547)
- Optimized Mirror Chan experience
- Fixed Feishu, Gotify, OneBot push [#520](https://github.com/moesnow/March7thAssistant/pull/520) [#517](https://github.com/moesnow/March7thAssistant/pull/517)
- Fixed reward claim issue when daily missions incomplete
- Fixed crash when system does not support Auto Theme [#525](https://github.com/moesnow/March7thAssistant/pull/525)
- Fixed Scheduled Run crash due to locale time settings [#512](https://github.com/moesnow/March7thAssistant/pull/512)

## v2025.3.7
- Auto_Simulated_Universe adapted to new Divergent Universe
- Support **v3.1** new stages and characters [#486](https://github.com/moesnow/March7thAssistant/pull/486)
- Support running script/program after task completion [#453](https://github.com/moesnow/March7thAssistant/pull/453)
- Support running Divergent Universe once weekly (Settings-Universe)
- Integrated **Mirror Chan** app distribution (About -> Update Source)
- Fixed dungeon exception after setting Build Target
- Fixed Classic Simulated Universe entry issue
- Fixed Consumable synthesis issue [#482](https://github.com/moesnow/March7thAssistant/issues/482)
- Touch mode disabled temporarily [#487](https://github.com/moesnow/March7thAssistant/issues/487)

## v2025.1.20
- Support **v3.0** new stages and characters [#442](https://github.com/moesnow/March7thAssistant/pull/442)
- Support **Matrix** push [#440](https://github.com/moesnow/March7thAssistant/pull/440)
- Changed Trailblaze Power cap to **300** [#447](https://github.com/moesnow/March7thAssistant/pull/447)
- Fixed Immersifier count recognition [#441](https://github.com/moesnow/March7thAssistant/issues/441)
- Fixed Gacha record update failure
- Optimized code standards [#443](https://github.com/moesnow/March7thAssistant/pull/443)

## v2024.12.18
### Updates
- "Enable Planar Fissure" now prioritizes Ornament Extraction when double drops available
- Support toggling all push methods in GUI
- Optimized "Unlock FPS" and "Touch Mode" error messages
- "Auto Battle Detect" now checks/modifies registry before game start

## v2024.12.12
### Updates
- Support launching game in **Touch Mode** (Cloud Game mobile UI)
- "Claim Immersion Reward" changed to "Claim/Extract" (Auto extract after claiming points)
- Fixed mailbox entry issue with "Dreamless Night" wallpaper
- Fixed Apocalyptic Shadow fast challenge dialog skip [#406](https://github.com/moesnow/March7thAssistant/issues/406)

## v2.7.0
### New Features
- Support **Sunday**, **Lingsha**
- Support **Apocalyptic Shadow** [#397](https://github.com/moesnow/March7thAssistant/pull/397)
- Support **Run on Startup** (Settings - Misc)
- Loop mode reloads config on each start
- Added **Screenshot on Multi-monitor** option (Settings - Misc) [#392](https://github.com/moesnow/March7thAssistant/pull/392)
- Support auto-detecting game path from HoYoPlay
- Optimized missing main program error
### Fixes
- Daily Tasks cleared on startup
- Auto Dialogue state issue
- Lowered character icon match threshold [#356](https://github.com/moesnow/March7thAssistant/issues/356)

## v2.6.3
### New Features
- Support **v2.6** new stages and characters (**Rappa**)
- "Dungeon Name" supports manual input
- Support auto-retry after defeat [#385](https://github.com/moesnow/March7thAssistant/pull/385)
- Support batch redemption codes (Toolbox)
- Gacha Records support "Update Full Data"
- Loop mode supports "By Power" and "Scheduled"
- Support **ServerChan3** push [#377](https://github.com/moesnow/March7thAssistant/pull/377)
### Fixes
- Changed Gacha Record API
- Manual config change overwritten by GUI [#341](https://github.com/moesnow/March7thAssistant/issues/341)
- Black screenshot on secondary monitor [#378](https://github.com/moesnow/March7thAssistant/pull/378)
- Account list background color issue in Dark Mode
- Infinite loop when "Garden of Plenty" event exists but disabled

## v2.5.4
### New Features
- Support **v2.5** new stages
- Reworked **Support** function (Specific friend's specific character, supports Ornament Extraction)
- Support **Jade**, **Jiaoqiu**, **Feixiao**, **Moze**
- Support Bilibili Server auto-click Login [#321](https://github.com/moesnow/March7thAssistant/discussions/321)
- Added "Restart" to "After Task Completion"
### Fixes
- OCR issues
- Auto login detection [#336](https://github.com/moesnow/March7thAssistant/issues/336)
- Support function high-DPI issue [#329](https://github.com/moesnow/March7thAssistant/issues/329)
- Calyx (Crimson) wrong line [#328](https://github.com/moesnow/March7thAssistant/issues/328)
- Extend wait time for Immortal Game scene load [#322](https://github.com/moesnow/March7thAssistant/issues/322)
- Optimize Ornament Extraction start logic [#325](https://github.com/moesnow/March7thAssistant/issues/325)
- Optimized "Launch Failed" error message

## v2.4.0
### New Features
- Support **Divergent Universe** and **Ornament Extraction**
- Support "Calyx (Golden): Penacony Grand Theater"
- Support **Yunli**, **March 7th (Imaginary)**, **Trailblazer (Imaginary)**
- Feishu supports sending screenshots [#310](https://github.com/moesnow/March7thAssistant/pull/310)
### Fixes
- New Material Synthesis page freeze [#231](https://github.com/moesnow/March7thAssistant/issues/231)

## v2.3.0
### New Features
- Adapted to new Simulated Universe entrance
- Support **v2.3** new stages [#277](https://github.com/moesnow/March7thAssistant/pull/277)
- Support Bilibili Server [#269](https://github.com/moesnow/March7thAssistant/pull/269)
- Support Global Server account operations [#268](https://github.com/moesnow/March7thAssistant/pull/268)
- Support **Firefly**
- detect HoYoPlay default install path
### Fixes
- Correctly enter map when in City Sandpit
- Memory of Chaos refresh popup issue
- PAC error [#276](https://github.com/moesnow/March7thAssistant/pull/276)

## v2.2.0
### New Features
- Support **v2.2** new stages
- Support **Aventurine**, **Robin**
- Support configuring SU Path and Difficulty in Settings [#223](https://github.com/moesnow/March7thAssistant/pull/223)
- Support configuring Fhoe-Rail buying options in Settings [#238](https://github.com/moesnow/March7thAssistant/pull/238)
- Multi-account management in Settings [#224](https://github.com/moesnow/March7thAssistant/pull/224)
- Auto-login check when login expired [#237](https://github.com/moesnow/March7thAssistant/pull/237)
- Cache template images to memory [#244](https://github.com/moesnow/March7thAssistant/pull/244)
- "Clear" button for Gacha Records
- Adapted to new Support Character UI
### Fixes
- Unable to switch to "Travel Log" and "Assignment" [#247](https://github.com/moesnow/March7thAssistant/pull/247)
- Pure Fiction start failure [#242](https://github.com/moesnow/March7thAssistant/pull/242)
- "Support" and "Gift of the Odyssey" claim failure
- Gacha Record crash

## v2.1.1
### New Features
- Auto Dialogue supports Gamepad UI [#208](https://github.com/moesnow/March7thAssistant/pull/208)
- Telegram Push supports Proxy/PAC [#219](https://github.com/moesnow/March7thAssistant/pull/219)
- Email Push supports Outlook [#220](https://github.com/moesnow/March7thAssistant/pull/220)
### Fixes
- Source run Fhoe-Rail [#211](https://github.com/moesnow/March7thAssistant/pull/211)
- Text OCR issues

## v2.1.0
### New Features
- Support v2.1 new dungeons and events
- Changes Assignment reward claim to "Claim All"
- Calyx (Crimson) changed to search by location
- Merged Check-in event switches
- Support **Acheron**, **Gallagher**
### Fixes
- Red dot check failure in Immortal Game 2nd room
- Synthesis task failure due to UI change
- Calyx (Crimson) backwards compatibility

## v2.0.7
### New Features
- Support Custom Push Notification Format
- Auto-retry MoC on defeat
- Optimized execution logic
- Push remaining power and recovery time after Full Run [#197](https://github.com/moesnow/March7thAssistant/pull/197)
### Fixes
- Phone menu icon click issue

## v2.0.6
### New Features
- Customize Immersion count [#165](https://github.com/moesnow/March7thAssistant/pull/165)
- Quick Log button [#150](https://github.com/moesnow/March7thAssistant/pull/150)
- Added "Assignment Reward Check" before clearing power in Full Run [#171](https://github.com/moesnow/March7thAssistant/pull/171)
### Fixes
- Reduced scroll speed in dungeon search
- "cmd not found" error
- Fullscreen check on some resolutions [#183](https://github.com/moesnow/March7thAssistant/pull/183)
### Other
- Clicking Simulated Universe on home now claims weekly rewards
- Removed Fhoe-Rail/SU update buttons from settings (Use home buttons)

## v2.0.5
### New Features
- Added "Logoff" to After Task Completion
- FPS Unlocker in Toolbox [#161](https://github.com/moesnow/March7thAssistant/pull/161)
- "Auto Resolution" changed to "Auto Resolution & Disable Auto HDR" [#156](https://github.com/moesnow/March7thAssistant/pull/156)
- Added **OneBot** push (QQ Robot)
- WeChat Work App push supports images
### Fixes
- FPS unlock failure
- Gotify push failure
- Task tracker icon interfering with map recognition
- Multiple red dots causing SU reward claim failure
- Quick unlock tutorial causing Pure Fiction error
- Home wallpaper blur on high scaling
- Registry read error after launch modification

## v2.0.4
### New Features
- Gacha Record Export & Analysis (Support **SRGF**)
- Support **Sparkle**
### Fixes
- Download failure in special cases

## v2.0.3
### New Features
- Support all Phone Wallpapers
- "Auto Story" renamed to "Auto Dialogue"
- Dungeon Name supports "None (Skip)"
- Support >1080p 16:9 resolutions (Experimental)
### Fixes
- Map UI judgment failure
- "Auto Resolution" failure
- Game launch failure when Auto Resolution disabled

## v2.0.2
### New Features
- Optimized Team UI
- Home modules support multiple options
- Support resetting Fhoe-Rail/SU configs
- Added "Game Refresh Time", "Auto Resolution", "Auto Game Path" options
- Reconnect support for some interfaces
### Fixes
- Support 3D Map UI
- Adapted to new MoC popup

## v2.0.1
### New Features
- Auto salvage 4-star relics (Default off)
- "Auto Dialogue" (in Toolbox)
- "Launch Game" button
- Auto Resolution support
- Custom Push support [#136](https://github.com/moesnow/March7thAssistant/pull/136)
### Fixes
- Updater overwrite failure
- Echo of War not doing 3 runs
- Path with spaces update issue
- Updater wrongly deleting map folder

## v2.0.0
### New Features
- Support **v2.0** new stages
- Support "Limited Time Early Access" stages
- Support "Calyx (Golden) Preferred Region"
- Support **Dr. Ratio**, **Black Swan**, **Misha**
### Fixes
- "Shape of Roast" OCR issue
- Lowered Calyx (Crimson) threshold
- Changed "Use Omni-Synthesizer" material to "Glimmering Core"
- "Memory" switch issue
- "Immortal Game" switch issue
- Check-in event image load failure


## v1.7.7
### New Features
- SMTP supports sending screenshots [#114](https://github.com/moesnow/March7thAssistant/pull/114)
- Support **Gotify** push [#112](https://github.com/moesnow/March7thAssistant/pull/112)
- Added "Enable use of Support Character" option (Default on) [#121](https://github.com/moesnow/March7thAssistant/issues/121)
- Modified "Specific Support Character" instruction (Supports Username and UID)
### Fixes
- Remote Desktop multi-instance issue wrongly terminating other user's game process [#113](https://github.com/moesnow/March7thAssistant/pull/113) [#35](https://github.com/moesnow/March7thAssistant/issues/35)
- Text OCR recognition issues (e.g. RapidOCR Calyx issues)
- Unzip failure when path contains parentheses
- Failure to claim rewards after Simulated Universe completion

## v1.7.6
### New Features
- Support "Garden of Plenty", "Realm of the Strange", "Planar Fissure" events (Default off)

## v1.7.5
### New Features
- Support **Pure Fiction** (Default range 3-4)

## v1.7.4
### New Features
- Support downloading **Full Package** during update (Default on, Settings -> About)
- Support joining **Pre-release** update channel (Settings -> About)
- Support **aria2** multi-thread downloading for updates (Faster and more stable)
- No longer use system temp directory for updates (Easier to allowlist in Antivirus [#86](https://github.com/moesnow/March7thAssistant/discussions/86#discussioncomment-7966897))
### Fixes
- Repeated dungeon challenge execution exception

## v1.7.3
### New Features
- Support **Argenti**
- Support disabling "Auto Battle Detect" (Settings -> Keybinds)
- "Auto Battle Detect" time changed to unlimited (Temp fix [#96](https://github.com/moesnow/March7thAssistant/pull/96))
### Fixes
- Forgotten Hall technique swap order issue
- Forgotten Hall fails to retry next floor on failure

## v1.7.2
### New Features
- Support disabling **Daily Training** (Can combine with daily SU to reach 500 activity)
- Support new Echo of War: "**Borehole Planet's Old Crater**"
- Support **Ruan Mei**
### Fixes
- Echo of War teleport misclick on Credit icon [#91](https://github.com/moesnow/March7thAssistant/pull/91)

## v1.7.1
### Fixes
- Fhoe-Rail and Simulated Universe execution exceptions

## v1.7.0
### New Features
- Adapted to new **Daily Training** missions
- Adapted to new **Memory of Chaos** UI (Manual tutorial required after Stage 7)
- MoC character selection supports scroll search
- MoC auto swap team on failure
- MoC default range changed to **7-12**
- Supported Team Index changed to **3-7**
- Support **Hanya**, **Xueyi**
- Dingtalk push default config added `secret` parameter
### Fixes
- MoC reward claim failure

## v1.6.9
### New Features
- Adapted to MoC 1-5 change to Single Boss
### Fixes
- Scroll delay missing caused offset (Again)
- Removed some test code

## v1.6.8
### Fixes
- Simulated Universe frequency config name error

## v1.6.7
### New Features
- Support prioritizing **Immersifier Synthesis** (Default off)
- Simulated Universe supports modifying **Frequency** (Default Weekly)
### Fixes
- Scroll delay missing caused offset

## v1.6.6
### New Features
- Support running "Daily Training" and "Clear Power" separately
- Auto delete old `map` folder when updating Fhoe-Rail
### Fixes
- Auto save lineup caused "Memory" and "MoC" issues
- Rare character name OCR error

## v1.6.5
### New Features
- Support **Integrated Mode** for Simulated Universe (Default)
- Support **Topaz & Numby**, **Guinaifen**, **Huohuo**
- Added dungeons "Shape of Scorch" and "Path of Darkness"
- Support Calyx with <60 power [#31](https://github.com/moesnow/March7thAssistant/pull/31)
- Support getting game path from Start Menu shortcut [#29](https://github.com/moesnow/March7thAssistant/pull/29)
### Fixes
- Auto getting game path from Launcher
- "Use Consumable" retry logic error [#41](https://github.com/moesnow/March7thAssistant/pull/41)

## v1.6.4
### New Features
- Support customizing Simulated Universe weekly run count
- Support completing "Clear Simulated Universe World (Any) 1 Area"
- Added Simulated Universe integrity check [#27](https://github.com/moesnow/March7thAssistant/pull/27)
- Support **Trailblazer (Destruction)** and **Trailblazer (Preservation)** [#26](https://github.com/moesnow/March7thAssistant/pull/26)
### Fixes
- Fixed "Game Exit Failed" (Reverted experimental change)

## v1.6.3
### New Features
- Support completing Daily via "Himeko Trial" (Experimental)
- Support completing Daily via "Memory 1" (Experimental)
- Powered by **Python 3.12.0**
- Adapted to latest Fhoe-Rail changes
### Fixes
- Float timeout value causing GUI crash
- "Gift of Odyssey" last day claim failure
### Other
- Optimized stability
- Now only terminates game process of current user (Experimental)

## v1.6.2
### New Features
- Support **Reserved Trailblaze Power** and **Fuel**
- Support claiming "Gift of Odyssey" rewards
- go-cqhttp supports sending screenshots [#21](https://github.com/moesnow/March7thAssistant/pull/21)
### Fixes
- Rare OCR error identifying power as "Rice" (Chinese char)
### Other
- Removed `power_total`, `dispatch_count`, `ocr_path` configs
- Filter consumable category before usage
- Upgraded [PaddleOCR-json_v.1.3.1](https://github.com/hiroi-sora/PaddleOCR-json/releases/tag/v1.3.1)
- Support [RapidOCR-json_v0.2.0](https://github.com/hiroi-sora/RapidOCR-json/releases/download/v0.2.0/RapidOCR-json_v0.2.0.7z)

## v1.6.1
### New Features
- Pre-set "Dungeon Names" (with explanations)
- Support **Jingliu**, **Trailblazer (Destruction)**
- Support claiming "Gift of Odyssey" rewards
- Support detecting "Nameless Honor" unlock interface
### Fixes
- PushPlus push [#14](https://github.com/moesnow/March7thAssistant/pull/14)
### Other
- Support Phone Wallpaper status detection
- Support detecting "Nameless Glory" purchase
- Team config via Phone menu

## v1.6.0
### New Features
- Auto claim Stellar Jade after MoC completion
- Support Integrated Mode for Fhoe-Rail (Default)
- GUI Test Push function
- Completed push config items (Bark, ServerChan, SMTP recommended)
- Support getting game path from Official Launcher [#10](https://github.com/moesnow/March7thAssistant/pull/10)
### Fixes
- Windows Terminal "Error 2147942402" [#12](https://github.com/moesnow/March7thAssistant/pull/12)
- Low spec PC delegation check exception
- Optimized "Error: None" message
- GUI display issue when System Accent Color enabled [#11](https://github.com/moesnow/March7thAssistant/pull/11)
### Other
- Optimized GUI load time with multi-threading [#11](https://github.com/moesnow/March7thAssistant/pull/11)
- Optimized Python check and dependency install
- Built-in "Tutorial"

## v1.5.0
### New Features
- Optimized "Dungeon Name" and "Daily Training" display in GUI
- Attempt to support Global Server launcher (Simplified Chinese)
- Merged "Exit Game"/"Shutdown" to "After Task", default "None"
- Loop Run 4 AM start now has random delay 0-10 mins
### Fixes
- Update failing due to file lock (GUI not closing)
- CWD issue causing run failure
### Other
- Auto select fastest mirror
- "Timeout" now correctly stops subtasks
- Prioritize Windows Terminal over conhost
- Deprecated `python_path`, `pip_mirror`, `github_mirror`

## v1.4.2
### New Features
- Built-in [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) project
- Adjusted directory structure

## v1.4.1.1
### Fixes
- Occasional Monthly Card claim failure
- Python path from env failure
- pushplus push issue

## v1.4.1
### New Features
- Support **Fu Xuan**, **Lynx**
- Option to toggle "Complete MoC 1 time" (Default off)
- Sound notification after task (Default off)
- Windows Native Notification (Default on)
- Optimized error messages
### Fixes
- Fhoe-Rail startup error
- pushplus push issue

## v1.4.0
### New Features
- Auto Shutdown after task (Default off)
- GUI Navigation optimization
- GUI Dark Moode
### Fixes
- Increased teleport wait time

## v1.3.5
### New Features
- GUI Modify Technique Key [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- GUI Import Config [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- Support Specific Support User [#5](https://github.com/moesnow/March7thAssistant/pull/5)
- Download Progress Bar
### Fixes
- Wallpaper change causing Assignment check failure

## v1.3.4.2
### New Features
- Config Technique Key [#3](https://github.com/moesnow/March7thAssistant/pull/3)
### Fixes
- Planar Fissure banner blocking Herta's Office entry
- Hide "Required Power" in GUI
- Fix Daily "Complete MoC 1 time" stuck
- Fix Auto Battle not enabling

## v1.3.4.1
### Fixes
- Use cmd instead of powershell
- Auto Install Python issues

## v1.3.4
### New Features
- Support **Dan Heng • Imbibitor Lunae**
- Open SU/Fhoe-Rail GUI from Settings
- Auto Install Python/PaddleOCR-json
- Optimize Updater
### Fixes
- Non-4K resolution windowed mode issue

## v1.3.3.1
### New Features
- Auto detect and save game path on launch
- Update FAQ

## v1.3.3
### New Features
- Support setting whether to claim Nameless Honor rewards (Default off)
- More error checks
- Update FAQ

## v1.3.2
### New Features
- Auto enable "Auto Battle"
- Detect Fhoe-Rail/SU status
- Detect Game Update needing restart
- Start game with official launcher open
- Terminate scripts on error
### Fixes
- Config verify overwriting time/daily status if GUI open
- Launch failure check

## v1.3.1
### New Features
- Siumulated Universe "Claim Immersion Reward" (Settings, Default off)

## v1.3.0.2
### New Features
- Restored "Use Support Character" option
- "None" dungeon name skips task
### Fixes
- MoC star check exception

## v1.3.0.1
### Fixes
- GUI config generation incorrect

## v1.3.0
### New Features
- Identify Daily Training contents and attempt completion
- Weekly prioritize "Echo of War" 3 times (Default off)
- Dungeon Names separate per type
- Removed unused options
- Check SU rewards before run
### Fixes
- Dungeon Name recognition failure
- Daily Training completion check failure

## v1.2.6
### New Features
- Support Cavern of Corrosion, Stagnant Shadow, Calyx
- Capture Screenshot with OCR in Settings

## v1.2.5
### New Features
- Built-in Fhoe-Rail command
### Fixes
- Power OCR recognition issue (1240)
- Daily Training check failure

## v1.2.4
### New Features
- GUI Show Changelog
- Update Auto_Simulated_Universe v5.30
### Fixes
- v1.3 UI changes exceptions

## v1.2.3
### New Features
- MoC star detection
- Dungeon name abbreviations
### Fixes
- Click speed too fast
- Mouse safety trigger
- Consumable click offset
- Nameless Honor template error
- Lowered thresholds
- Remove redundant checks

## v1.2.2
### Features
- Support Bailu and Kafka
- MoC support melee character start
- GUI capture screenshot
- GUI check update
### Fixes
- Use consumables check
- Check update option
- Trailblaze power overflow
- OCR space issue
- Exit function

## v1.2.1
### Features
- Auto change team
- Add submodule Auto_Simulated_Universe
### Fixes
- Switch window problem
- Same borrow character

## v1.2.0
### Features
- Graphical User Interface
