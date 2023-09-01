<p align="center">
    <img src="./assets/logo/March7th.ico">
</p>

<h1 align="center">
三月七小助手<br>
March7thAssistant
</h1>

崩坏：星穹铁道 自动日常任务｜自动锄大地/模拟宇宙/忘却之庭｜图形界面｜消息推送｜7×24小时运行

## 功能简介

> 注意：锄大地调用的非开源项目，在群文件内提供补丁包

自动刷副本｜借支援｜领派遣、邮件、实训等奖励｜拍照、合用材料消耗品｜锄大地、模拟宇宙、混沌回忆

详情见 [配置文件](assets/config/config.example.yaml) 或下载后打开设置查看｜🌟喜欢就点击右上角给个**星星**吧|･ω･) 🌟｜群号 855392201

## 界面展示

![README](assets/screenshot/README1.png)

## 注意事项

- 支持 `1920*1080` 分辨率窗口或全屏运行游戏
- 使用锄大地和模拟宇宙功能需要安装 `Python`
- 如遇到错误请在 [Issue](https://github.com/moesnow/March7thAssistant/issues) 反馈，欢迎 [PR](https://github.com/moesnow/March7thAssistant/pulls)
- **蓝色文字**都是超链接，可以点击

## 下载安装

前往 [Releases](https://github.com/moesnow/March7thAssistant/releases) 下载后解压双击 `March7th Assistant.exe` 直接运行，

如果速度缓慢可以右键复制链接后通过 [https://ghproxy.com](https://ghproxy.com) 加速。

## 源码运行

如果你是完全不懂的小白，请通过上面的方式下载安装，不用往下看了。

```cmd
# 注意需要添加 --recurse-submodules 参数同时 clone 子模块
git clone https://github.com/moesnow/March7thAssistant --recurse-submodules
cd March7thAssistant
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
python app.py
```

```cmd
# 可选方式，使用 venv 创建虚拟环境，避免依赖冲突
python -m venv .venv
.venv\Scripts\activate
```

## 相关项目

- 模拟宇宙自动化 [https://github.com/CHNZYX/Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe)

- 自动锄大地 [https://github.com/Night-stars-1/Auto_Star_Rail](https://github.com/Night-stars-1/Auto_Star_Rail)

- 星铁副驾驶 [https://github.com/LmeSzinc/StarRailCopilot](https://github.com/LmeSzinc/StarRailCopilot)

## 星光历程

[![星光历程](https://starchart.cc/moesnow/March7thAssistant.svg)](https://starchart.cc/moesnow/March7thAssistant)
