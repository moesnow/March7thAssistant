<div align="center">
  <h1 align="center">
    <img src="./assets/screenshot/March7th.png" width="200">
    <br/>
    March7thAssistant
  </h1>
  <a href="https://trendshift.io/repositories/3892" target="_blank"><img src="https://trendshift.io/api/badge/repositories/3892" alt="moesnow%2FMarch7thAssistant | Trendshift" style="width: 200px; height: 46px;" width="250" height="46"/></a>
</div>

<br/>

<div align="center">
🌟 Click the Star in the upper-right corner to get update notifications for this project on GitHub.
</div>

<div align="center">
    <img src="assets/screenshot/star.gif" alt="Star" width="186" height="60">
</div>

<br/>

<div align="center">

[简体中文](./README.md) | [繁體中文](./README_TW.md) | **English** | [日本語](./README_JA.md) | [한국어](./README_KR.md)

**This document was translated from the Simplified Chinese version using AI. Last updated: 2026-04-24. If anything differs, the Simplified Chinese version takes precedence.**

**The in-game language currently supports Simplified Chinese only.**

Quick start: [Tutorial](https://m7a.top/#/assets/docs/Tutorial_en)

Before asking for help, please check: [FAQ](https://m7a.top/#/assets/docs/FAQ_en)

</div>

## Feature Overview

- **Daily**: Spend Trailblaze Power, Daily Training, claim rewards, dispatch, field farming
- **Weekly**: Echo of War, Currency Wars, Divergent Universe, Memory of Chaos, Pure Fiction, Apocalyptic Shadow
- **Cloud Honkai: Star Rail**: Supports background execution, headless execution, and Docker deployment
- **Gacha record export**: Supports the [UIGF](https://uigf.org/zh/standards/uigf.html) / [SRGF](https://uigf.org/zh/standards/srgf.html) standards
- **Toolbox**: Auto dialogue, FPS unlock, redemption codes
- Task results such as Daily Training support **push notifications**
- Supports **automatic start** after task refresh or when Trailblaze Power recovers to a specified value
- Supports **sound alerts, automatic game exit, shutdown, and more** after tasks finish

For details, see the GUI settings or the [configuration file](assets/config/config.example.yaml) | QQ group [Join here](https://qm.qq.com/q/C3IryUWCQw) TG group [Join here](https://t.me/+ZgH5zpvFS8o0NGI1) Bilibili [Visit here](https://space.bilibili.com/3706960664857075)

## Interface Preview

![README](assets/screenshot/README.png)

## Notes

- If you encounter problems, please report them in [Issues](https://github.com/moesnow/March7thAssistant/issues). Questions and discussions belong in [Discussions](https://github.com/moesnow/March7thAssistant/discussions). Chat groups are checked only occasionally.
- Pull requests are welcome. Please read the [contribution guide](CONTRIBUTING.md) before submitting.

## Download and Installation

Download the latest release from [Releases](https://github.com/moesnow/March7thAssistant/releases/latest), extract it, and double-click `March7th Launcher.exe` with the March 7th icon to open the GUI.

## Running from Source

If you are completely new to this, use the packaged release above. You can ignore the rest of this section.

Python 3.12 or newer is recommended.

On Windows, if you launch from a terminal, it is recommended to open PowerShell, Windows Terminal, or CMD as Administrator. On Windows 11 24H2 or later, you can also use [Sudo for Windows](https://learn.microsoft.com/zh-cn/windows/advanced-settings/sudo/).

```cmd
# Installation (using venv is recommended)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
pip install -r requirements.txt
python app.py
python main.py

# Update
git pull
git submodule update --init --recursive
```

If you use `uv`, it is recommended to use the built-in `pyproject.toml` workflow directly:

```cmd
# Installation (using uv)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
uv sync

# Launch the GUI
uv run python app.py

# Show CLI help
uv run python main.py -h

# Run the full workflow
uv run python main.py

# Run Daily Training
uv run python main.py daily
```

<details>
<summary>Development Notes</summary>

To obtain the crop coordinates used by crop parameters, you can use the capture screenshot feature in the toolbox.

</details>

---

If you like this project, you can support the author with a coffee via WeChat ☕

Your support helps keep the project developed and maintained.

![sponsor](assets/app/images/sponsor.jpg)

---

## Related Projects

March7thAssistant depends on the following open-source projects and runtime dependencies. Thanks to all maintainers and contributors.

- Simulated Universe automation [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe): provides Simulated Universe related capabilities
- Field farming automation [https://github.com/linruowuyin/Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail): provides field farming related capabilities
- OCR text recognition [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR): provides in-game text recognition
- GUI component library [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets): provides the main interface components and interaction experience
- MirrorChyan [https://github.com/MirrorChyan/docs](https://github.com/MirrorChyan/docs): provides update checking, download distribution, and CDN acceleration related capabilities
- Image processing and automation related dependencies `OpenCV`, `PyAutoGUI`, and others: provide screenshot capture, image processing, and foundational automation capabilities
- Inference acceleration related dependencies `ONNX Runtime`, `OpenVINO`: provide CPU / GPU acceleration for OCR and model inference

Additionally, `requirements.txt` contains many lower-level dependencies that are not listed one by one here. Thanks as well to those projects for supporting this project.

## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg?variant=adaptive)](https://starchart.cc/moesnow/March7thAssistant)
