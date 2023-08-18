<p align="center">
    <img src="./assets/logo/March7th.png">
</p>

<h1 align="center">
三月七小助手<br>
March7thAssistant
</h1>

崩坏：星穹铁道 日常/任务/实训/体力自动化｜忘却之庭/混沌回忆自动化｜锄大地/模拟宇宙自动化｜为7×24小时运行设计

## 免责声明

本软件是一个外部工具旨在自动化崩坏星轨的游戏玩法。它被设计成仅通过现有用户界面与游戏交互,并遵守相关法律法规。该软件包旨在提供简化和用户通过功能与游戏交互,并且它不打算以任何方式破坏游戏平衡或提供任何不公平的优势。该软件包不会以任何方式修改任何游戏文件或游戏代码。

This software is open source, free of charge and for learning and exchange purposes only. The developer team has the final right to interpret this project. All problems arising from the use of this software are not related to this project and the developer team. If you encounter a merchant using this software to practice on your behalf and charging for it, it may be the cost of equipment and time, etc. The problems and consequences arising from this software have nothing to do with it.

本软件开源、免费，仅供学习交流使用。开发者团队拥有本项目的最终解释权。使用本软件产生的所有问题与本项目与开发者团队无关。若您遇到商家使用本软件进行代练并收费，可能是设备与时间等费用，产生的问题及后果与本软件无关。

请注意，根据MiHoYo的 [崩坏:星穹铁道的公平游戏宣言](https://sr.mihoyo.com/news/111246?nav=news&type=notice):

    "严禁使用外挂、加速器、脚本或其他破坏游戏公平性的第三方工具。"
    "一经发现，米哈游（下亦称“我们”）将视违规严重程度及违规次数，采取扣除违规收益、冻结游戏账号、永久封禁游戏账号等措施。"

## 功能

见 [配置文件](config.yaml)

锄大地和模拟宇宙因为调用的其他项目，涉及到开源相关的问题，可以加群获取完整版，或自己设置启动命令

## 使用

只保证支持 Python 3.11.4 可用


### 一键运行

    # 如移动项目需要手动删除 .venv 文件夹
    双击 one-key-run.exe

### 手动运行

以管理员身份打开 `cmd` 或者 `powershell`，使用 `cd` 命令进入项目根目录

```cmd
pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
python main.py
```

```cmd
# 更推荐的方式
python -m venv .venv
.venv\Scripts\activate
python -m pip install -i https://mirrors.aliyun.com/pypi/simple/ --upgrade pip
pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
python main.py
```

## 运行截图

![screenshot](assets/screenshot/screenshot.png)

## 相关项目

- 模拟宇宙自动化 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe)

- 自动锄大地 [https://github.com/Starry-Wind/StarRailAssistant](https://github.com/Starry-Wind/StarRailAssistant)

- 星铁副驾驶 [https://github.com/LmeSzinc/StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot)