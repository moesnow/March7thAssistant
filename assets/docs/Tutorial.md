# 使用教程

## 硬件要求

必须使用PC端 1920*1080 分辨率窗口或全屏运行游戏（不支持HDR）

> **为什么使用PC端？** 星穹铁道不同于只有移动端的手游，PC端可以更好的发挥电脑硬件性能。
>
> 模拟器运行存在卡顿、性能消耗大等缺点，你也不想版本更新时像个傻宝一样更新两份客户端吧。
>
> 如果有后台运行的需求，可以使用 [远程本地多用户桌面](/assets/docs/Background.md)，在一台电脑上同时启用多个桌面。


## 下载

点击 [Releases](https://github.com/moesnow/March7thAssistant/releases/latest) 打开下载页面，滚动到底部。

找到名称类似 `March7thAssistant_full.zip(7z)` 的文件，点击下载。

> March7thAssistant 接入了第三方服务 [Mirror酱](https://mirrorchyan.com/?source=m7a-faq)（一个给开源社区做有偿内容分发的平台）。
>
> 如果中国大陆下载缓慢可以尝试 [点我前往 Mirror酱 高速下载](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-faq)

## 解压

找到下载完毕的名称类似 `March7thAssistant_full.zip(7z)` 的文件，右键选择 "全部解压缩"。

> 如果安装了第三方解压缩软件，操作名称也可能叫做"提取"

## 运行

找到解压后出现的名称类似 `March7thAssistant` 的文件夹并双击打开，里面应当至少包含以下文件（夹）：

- `March7th Launcher.exe`
- `March7th Assistant.exe`
- `March7th Updater.exe`
- `assets`
- `libraries`

双击 `March7th Launcher.exe` 打开图形界面，同意《免责声明》。

> 此程序为免费开源项目，如果你付了钱请立刻退款！！！
>
> 本项目已经因倒卖行为受到严重威胁，请帮助我们！！！
>
> 咸鱼倒狗4000+！你付给倒狗的每一分钱都会让开源自动化更艰难，请退款并举报商家！！！

## 任务

### 完整运行

按照 `日常`→`清体力`→`锄大地`→`模拟宇宙`→`逐光捡金`→`领取奖励` 的顺序依次执行

已经判断为完成的任务不会重复运行，其中日常和锄大地的重置时间为每天凌晨4点，

模拟宇宙和逐光捡金的重置时间为每周一凌晨4点。

### 锄大地

调用的 [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 项目，单独运行，不会判断本日是否完成过。

使用前请事先开完全部锚点，完成地图上干扰图片识别传送的一切任务，包括机巧鸟、需要解锁的门等。

成年女性模型（攻击为远程无位移）跑图最佳，如：艾丝妲、三月七，近战角色会出现异常，黄泉等角色可以选择专用锄地模式。

> 光照质量推荐设置为中及以上，60帧，其余画质设置没有影响

### 模拟宇宙

调用的 [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) 项目，单独运行，不会判断本周是否完成过。

每周运行34次后才会停止，中途关闭也会保存进度。启用领取沉浸奖励后，只会使用沉浸器，不会消耗体力。

默认世界：比如说如果你当前模拟宇宙默认世界4，但是想自动化世界6，那么请先进入一次世界6来改变默认世界

### 逐光捡金

单独运行，不会判断本周是否完成过。会自动识别星数，满星就会跳过执行。

## 配置

点击左下角的`设置`进入小助手设置界面。

### 程序

#### 日志等级
一般保持默认 `简洁` 即可，如果遇到异常请切换为 `详细` 方便排查问题。

#### 游戏截图

可以用于自行判断程序获取的图像是否正确，也支持框选后调用OCR识别文字，可用于复制副本名称中的一些生僻字。

#### 任务完成后

任务完成后会执行的一些操作，其中`退出`指退出游戏，

`循环`指根据开拓力7×24小时无人值守循环运行程序（仅限完整运行生效），

`关机`、`休眠`、`睡眠`、`注销`前会提示并等待1分钟再执行。

#### 循环运行再次启动所需开拓力

当`任务完成后`选项设置为`循环`后，该选项才会生效。

开拓力恢复到预设值后就会再次运行，凌晨4点优先级高于开拓力。

### 游戏

#### 游戏路径

启动游戏后再运行小助手会自动配置该选项。

如果手动配置一定要注意不要错选成启动器 `Star Rail\launcher.exe` ，

`Star Rail\Game\StarRail.exe` 才是游戏本体。

### 体力

#### 副本类型

清体力时刷的副本类型，会自动识别开拓力计算次数。

#### 副本名称

副本名称除了用于清体力外，当每日实训中出现`完成1次「XXXX」`的任务时，

就会打这里设置的副本来完成任务，如果即使有任务也不想完成，请修改为`无`

#### 启用使用支援角色

通常只有每日实训中出现`使用支援角色并获得战斗胜利1次`任务后才会使用支援角色一次，

开启此选项后，每次打副本都会使用支援角色

#### 启用历战余响

支持自动判断历战余响剩余次数，优先级高于清体力，重置时间为每周一凌晨4点

### 锄大地

调用的 [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 项目

需要从中断的地图继续运行可以点击`原版运行`，会打开锄大地自身的界面，然后选择调试模式即可

`更新锄大地`按钮可以一键更新到最新版

### 模拟宇宙

调用的 [Auto_Simulated_Universe](https://github.com/CHNZYX/Auto_Simulated_Universe) 项目

快速上手，请访问：[项目文档](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md) 

遇到问题，请在提问前查看：[Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)

小助手使用的是 `命令行使用方法`，请确保 Python 环境变量配置正确

需要修改命途和难度等可以点击`原版运行`，会打开模拟宇宙自身的图形界面

`更新模拟宇宙`按钮可以一键更新到最新版

### 忘却之庭

数字代表秘技使用次数，其中`-1`代表最后一个放秘技和普攻的角色（也就是开怪角色）

角色对应的英文名字可以在 `March7thAssistant\assets\images\character` 中查看

### 推送

目前支持：

- Telegram
- Serverchan/Turbo （Server酱·Turbo版）
- Bark
- SMTP （邮箱）
- Dingtalk （钉钉）
- Pushplus
- WeChatworkapp （企业微信应用通知）
- WeChatworkbot （企业微信机器人通知）
- OneBot （QQ 机器人）
- Go-cqhttp （QQ 机器人）
- Gotify
- Discord
- Pushdeer
- Lark（飞书）
- Custom

> 其中 Telegram、SMTP、OneBot 等支持发送截图，欢迎 PR 适配其他推送方式

### 按键

按键设置只会在小助手内置的功能中生效，例如逐光捡金。

如果你需要修改模拟宇宙和锄大地，请查看相关项目的教程。

模拟宇宙 `Auto_Simulated_Universe` 的按键可以在 `info.yml` 里面修改。

锄大地 `Fhoe-Rail` 源码模式的 `utils` 目录中有一个名称包含 `改按键` 的 `py` 文件是 `E` 和 `F` 互换的

## 更新

出现新版本弹窗后，点击下载即可，或手动双击 `March7th Updater.exe`。

手动更新请下载名称类似 `March7thAssistant.zip(7z)` 的文件，

解压后，复制所有文件，在旧版本内粘贴覆盖即可。
