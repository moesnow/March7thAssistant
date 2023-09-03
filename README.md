<p align="center">
    <img src="./assets/logo/March7th.ico">
</p>

<h1 align="center">
三月七小助手<br>
March7thAssistant
</h1>

崩坏：星穹铁道 自动日常/清体力｜自动锄大地/模拟宇宙/忘却之庭｜图形界面｜消息推送｜7×24小时运行

## 功能简介

> 注意：锄大地调用的非开源项目，在群文件内提供补丁包

- 完成每日实训
- 领取各种奖励
- 指定副本自动清体力
- 每周三次历战余响
- 锄大地、模拟宇宙、忘却之庭

详情见 [配置文件](assets/config/config.example.yaml) 或下载后打开设置查看｜🌟喜欢就点击右上角给个**星星**吧|･ω･) 🌟｜群号 855392201

## 界面展示

![README](assets/screenshot/README1.png)

## 注意事项

- 支持 `1920*1080` 分辨率窗口或全屏运行游戏
- 使用锄大地和模拟宇宙功能需要安装 `Python`
- 如遇到错误请在 [Issue](https://github.com/moesnow/March7thAssistant/issues) 反馈，欢迎 [PR](https://github.com/moesnow/March7thAssistant/pulls)
- **蓝色文字**都是超链接，可以点击

## 下载安装

前往 [Releases](https://github.com/moesnow/March7thAssistant/releases/latest) 下载后解压双击 `March7th Assistant.exe` 直接运行，

如果速度缓慢可以右键复制链接后通过 [https://ghproxy.com](https://ghproxy.com) 加速。

## 每日实训

> v1.3.0以后支持识别实训任务，暂未发布正式版

| 任务描述                             | 支持情况 | 完成方式  |
| ----------------------------------- | -------- | -------- |
| 完成1个日常任务                      |   ❌     |          |
| 完成1次「拟造花萼（金）」             |   ✔      |          |
| 完成1次「拟造花萼（赤）」             |   ✔      |          |
| 完成1次「凝滞虚影」                  |   ✔      |          |
| 完成1次「侵蚀隧洞」                  |   ✔      |          |
| 单场战斗中，触发3种不同属性的弱点击破  |   ✔      |  锄大地   |
| 累计触发弱点击破效果5次               |   ✔      |  锄大地   |
| 累计消灭20个敌人                     |   ✔      |  锄大地   |
| 利用弱点进入战斗并获胜3次             |   ✔      |  锄大地   |
| 累计施放2次秘技                      |   ✔      |  锄大地   |
| 派遣1次委托                         |   ✔      |          |
| 拍照1次                             |   ✔      |          |
| 累计击碎3个可破坏物                  |   ✔      |  锄大地   |
| 完成1次「忘却之庭」                  |   ✔      |  回忆一   |
| 完成1次「历战余响」                  |   ✔     |          |
| 通关「模拟宇宙」（任意世界）的1个区域 |   ❌     |          |
| 使用支援角色并获得战斗胜利1次         |   ✔      |  清体力   |
| 施放终结技造成制胜一击1次            |   ✔      |  锄大地   |
| 将任意角色等级提升1次                |   ❌     |          |
| 将任意光锥等级提升1次                |   ❌     |          |
| 将任意遗器等级提升1次                |   ❌     |          |
| 分解任意1件遗器                     |   ❌      |          |
| 合成1次消耗品                       |   ✔      |          |
| 合成1次材料                         |   ✔      |          |
| 使用1件消耗品                       |   ✔      |          |

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
