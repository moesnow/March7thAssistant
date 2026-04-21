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
🌟 点一下右上角的 Star，Github 主页就能收到软件更新通知了哦~
</div>

<div align="center">
    <img src="assets/screenshot/star.gif" alt="Star" width="186" height="60">
  </a>
</div>

<br/>

<div align="center">

**简体中文** | [繁體中文](./README_TW.md) | [English](./README_EN.md) | [日本語](./README_JA.md) | [한국어](./README_KR.md)

快速上手，请访问：[使用教程](https://m7a.top/#/assets/docs/Tutorial)

遇到问题，请在提问前查看：[FAQ](https://m7a.top/#/assets/docs/FAQ)

</div>

## 功能简介

- **日常**：清体力、每日实训、领取奖励、委托、锄大地
- **周常**：历战余响、货币战争、模拟宇宙、忘却之庭
- **抽卡记录导出**：支持 [UIGF](https://uigf.org/zh/standards/uigf.html)/[SRGF](https://uigf.org/zh/standards/srgf.html) 标准、**自动对话**
- 每日实训等任务的完成情况支持**消息推送**
- 任务刷新或体力恢复到指定值后**自动启动**
- 任务完成后**声音提示、自动关闭游戏或关机等**

> 其中模拟宇宙调用的 [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) 项目，锄大地调用的 [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 项目

详情见 [配置文件](assets/config/config.example.yaml) 或图形界面设置 ｜QQ群 [点击跳转](https://qm.qq.com/q/C3IryUWCQw) TG群 [点击跳转](https://t.me/+ZgH5zpvFS8o0NGI1)

## 界面展示

![README](assets/screenshot/README.png)

## 注意事项

- 必须使用**PC端** `1920*1080` 分辨率窗口或全屏运行游戏（不支持HDR）
- 支持 **macOS** 和 **Linux**（仅云游戏模式），也支持 [Docker 部署](https://m7a.top/#/assets/docs/Docker)
- 模拟宇宙相关 [项目文档](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md)  [Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)
- 需要后台运行或多显示器可以尝试 [远程本地多用户桌面](https://m7a.top/#/assets/docs/Background)
- 遇到错误请在 [Issue](https://github.com/moesnow/March7thAssistant/issues) 反馈，提问讨论可以在 [Discussions](https://github.com/moesnow/March7thAssistant/discussions) ，群聊随缘看
- 欢迎 [PR](https://github.com/moesnow/March7thAssistant/pulls)，提交前请先阅读 [贡献指南](CONTRIBUTING.md)

## 下载安装

前往 [Releases](https://github.com/moesnow/March7thAssistant/releases/latest) 下载后解压双击三月七图标的 `March7th Launcher.exe` 打开图形界面

如果需要使用 **任务计划程序** 定时运行或直接执行 **完整运行**，可以使用终端图标的 `March7th Assistant.exe`

检测更新可以点击图形界面设置最底下的按钮，或双击 `March7th Updater.exe`

### 命令行参数

图形界面 `March7th Launcher.exe` 支持命令行参数，可以在启动时自动执行指定任务：

```bash
# 查看帮助
March7th Launcher.exe -h

# 列出所有可用任务
March7th Launcher.exe -l

# 启动图形界面并执行完整运行
March7th Launcher.exe main

# 启动图形界面并执行每日实训
March7th Launcher.exe daily

# 任务正常完成后自动退出（需配合任务参数）
March7th Launcher.exe main -e
```

<details>
<summary>可用任务列表</summary>

| 任务名称 | 说明 |
|---------|------|
| main | 完整运行 |
| daily | 每日实训 |
| power | 清体力 |
| currencywars | 货币战争 |
| currencywarsloop | 货币战争循环 |
| fight | 锄大地 |
| universe | 模拟宇宙 |
| forgottenhall | 混沌回忆 |
| purefiction | 虚构叙事 |
| apocalyptic | 末日幻影 |
| redemption | 兑换码 |
| universe_gui | 模拟宇宙原生界面 |
| fight_gui | 锄大地原生界面 |
| universe_update | 模拟宇宙更新 |
| fight_update | 锄大地更新 |
| game | 启动游戏 |
| notify | 测试消息推送 |

</details>

## 源码运行

如果你是完全不懂的小白，请通过上面的方式下载安装，可以不用往下看了。

推荐使用 Python 3.12 或更高版本。

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

如果使用 `uv`，推荐直接使用项目自带的 `pyproject.toml` 工作流：

```cmd
# Installation (using uv)
git clone --recurse-submodules https://github.com/moesnow/March7thAssistant
cd March7thAssistant
uv sync

# 启动图形界面
uv run python app.py

# 查看命令行帮助
uv run python main.py -h

# 执行完整运行
uv run python main.py

# 执行每日实训
uv run python main.py daily
```

<details>
<summary>开发相关</summary>

获取 crop 参数表示的裁剪坐标可以通过小助手工具箱内的捕获截图功能

</details>

---

如果喜欢本项目，可以微信赞赏送作者一杯咖啡☕

您的支持就是作者开发和维护项目的动力🚀

![sponsor](assets/app/images/sponsor.jpg)

---

## 相关项目

March7thAssistant 离不开以下开源项目的帮助：

- 模拟宇宙自动化 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe)

- 锄大地自动化 [https://github.com/linruowuyin/Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail)

- OCR文字识别 [https://github.com/RapidAI/RapidOCR](https://github.com/RapidAI/RapidOCR)

- 图形界面组件库 [https://github.com/zhiyiYo/PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)


## Contributors
<a href="https://github.com/moesnow/March7thAssistant/graphs/contributors">

  <img src="https://contrib.rocks/image?repo=moesnow/March7thAssistant" />

</a>

## Stargazers over time

[![Star History](https://starchart.cc/moesnow/March7thAssistant.svg?variant=adaptive)](https://starchart.cc/moesnow/March7thAssistant)
