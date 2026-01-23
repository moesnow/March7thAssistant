# FAQ

Video Tutorial: [https://search.bilibili.com/all?keyword=三月七小助手](https://search.bilibili.com/all?keyword=%E4%B8%89%E6%9C%88%E4%B8%83%E5%B0%8F%E5%8A%A9%E6%89%8B)

### Q: The assistant always fails to update or the download speed is slow.

A: March7thAssistant is integrated with the third-party service [MirrorChyan](https://mirrorchyan.com/?source=m7a-faq) (a platform for paid content distribution for the open-source community).

It provides us with a free update check interface, but downloading is a paid service.

However, even if you don't purchase MirrorChyan's download service, you can choose to download from an overseas source (GitHub) in the settings after an update is detected.

If you purchase and enter a CDK, you won't have to worry about your network environment during updates, and downloads will be faster and more stable!

The CDK can also be used for other projects integrated with MirrorChyan, such as MAA.

[Click here for high-speed download from MirrorChyan](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-faq)

### Q: The assistant starts slowly / executable not found / Error 2147942402 / always deleted by antivirus.

A: Please add the `Assistant Folder` to your antivirus software's exclusions/allowlist/trust list, then re-extract and overwrite the files.

Windows Defender: `Virus & threat protection` → `Manage settings` → `Exclusions` → `Add or remove exclusions`. See illustration in [#373](https://github.com/moesnow/March7thAssistant/issues/373).

(You may also need to go to `App & browser control` → `Smart App Control settings` → `Off`)

Huorong Security: `Main Interface` → `Menu (top right)` → `Trust List`. See [Tutorial](https://cs.xunyou.com/html/282/15252.shtml).

### Q: Recognition issues or other problems with Dual (Multi) Monitors.

A: Try toggling **Settings - Misc - Screenshot on multi-monitor**.

Related discussions: [#383](https://github.com/moesnow/March7thAssistant/issues/383) [#710](https://github.com/moesnow/March7thAssistant/issues/710)

### Q: Auto-battle does not work.

A: Check in-game **Settings - Battle - Retain Auto-Battle Setting** and set it to **"Yes"**.

### Q: Missing newly added dungeons? "Chase the Light" missing new characters?

A: You can manually enter the name in the `Dungeon Name` interface, or edit the `assets\config\instance_names.json` file to add it manually.

For characters, in the "Forgotten Hall" interface, use the `Capture Screenshot` function in the Assistant's Toolbox. Check the character avatar and click `Save Selected Screenshot`.

Place it in `assets\images\share\character` and modify the `assets\config\character_names.json` file.

You are also welcome to upload `uncompressed` files (e.g., zip) to [Issues](https://github.com/moesnow/March7thAssistant/issues) or submit a [PR](https://github.com/moesnow/March7thAssistant/pulls).

### Q: What does "Full Run" do?

A: It executes tasks in the following order: `Daily` → `Energy (Dungeons)` → `Field Farming` → `Simulated Universe` → `Chase the Light` → `Claim Rewards`.

Tasks judged as completed will not be repeated. "Daily" and "Field Farming" reset at 4:00 AM daily.

"Simulated Universe" and "Chase the Light" reset at 4:00 AM every Monday.

### Q: Can I not move the keyboard/mouse or switch to the background after starting?

A: Yes, the script needs control. If you need it to run in the background, please try [Remote Local Multi-user Desktop](https://m7a.top/#/assets/docs/Background).

### Q: How to add custom notifications?

A: The GUI only supports enabling `Windows Native Notifications`. For other notifications, please enable them in `config.yaml`.

### Q: How to change the World, Character, Path, and Difficulty for Simulated Universe?

A: World and Character are set by entering and exiting them once in the game.  
Path and Difficulty can be modified in the GUI by finding "Simulated Universe" in Settings, clicking "Run Original", and changing them there.

### Q: Other Simulated Universe issues.

A: Quick Start Guide: [Project Documentation](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md)

Encounters problems? Check [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md) before asking.

### Q: Field Farming gets stuck or doesn't run properly.

A: Please check for unlocked Teleport Points, Map Doors, or unfinished Cycrane puzzles.

### Q: Field Farming was interrupted. How to run from a specific map?

A: Find "Field Farming" in Settings, click "Run Original", select "Debug Mode", and you can choose the map to start from.
