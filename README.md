<p align="center">
    <img src="./assets/logo/March7th.png">
</p>

<h1 align="center">
三月七小助手<br>
March7thAssistant
</h1>

崩坏：星穹铁道 日常/任务/实训/体力自动化｜忘却之庭/混沌回忆自动化｜锄大地/模拟宇宙自动化｜7×24小时运行

## 功能

见 [配置文件](config.yaml) 🌟喜欢就给个星星吧|･ω･) 🌟 群号 855392201

锄大地和模拟宇宙因为调用的其他项目，担心涉及到开源相关的问题，请加群获取完整版，或自己设置启动命令

## 使用

支持 1920*1080 窗口或全屏，只保证 Python 3.11.4 可用


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