# 常见问题

视频教程 [https://search.bilibili.com/all?keyword=三月七小助手](https://search.bilibili.com/all?keyword=%E4%B8%89%E6%9C%88%E4%B8%83%E5%B0%8F%E5%8A%A9%E6%89%8B)

### Q：小助手总是更新失败/下载速度缓慢 怎么办？

A：March7thAssistant 接入了第三方服务 [Mirror酱](https://mirrorchyan.com/?source=m7a-faq)（一个给开源社区做有偿内容分发的平台）。

它为我们提供了免费的检查更新接口，但它的下载是有偿的，需要用户付费使用。

不过，即使不购买 Mirror 酱的下载服务，你也可以在检测到更新后，在设置里选择从海外源（GitHub）下载~

如果你购买并填写了 CDK，更新时就再也不用和自己的网络环境斗智斗勇咯，下载更快更稳定！

同时 CDK 也可以用于其他接入 Mirror酱 的项目，例如 MAA 等。

[首次下载可点我前往 Mirror酱 高速下载](https://mirrorchyan.com/zh/download?rid=March7thAssistant&os=&arch=&channel=stable&source=m7a-faq)

### Q：小助手启动慢/未找到可执行文件/出现错误 2147942402/总是被杀毒软件删除 怎么办？

A：请将`小助手文件夹`加入杀毒软件排除项/白名单/信任区，然后重新解压覆盖一次。

Windows Defender：`病毒和威胁防护` → `管理设置` → `添加或删除排除项` 可以参考 [#373](https://github.com/moesnow/March7thAssistant/issues/373) 图示操作

（可能还需要将 `应用和浏览器控制` → `智能应用控制设置` → `切换为关闭` ）

火绒安全软件：`主界面` → `右上角菜单` → `信任区` 可以参考 [教程](https://cs.xunyou.com/html/282/15252.shtml) 图示操作

### Q：双（多）显示器导致识别异常等其他问题

A：尝试开关选项 设置-杂项-在多显示器上进行截屏

相关讨论见：[#383](https://github.com/moesnow/March7thAssistant/issues/383) [#710](https://github.com/moesnow/March7thAssistant/issues/710)

### Q：不会自动战斗

A：检查游戏内设置-战斗功能-是否沿用自动战斗设置，修改为“是”

### Q：缺少新增加的副本？逐光捡金缺少新角色？

A：在`副本名称`界面手动输入名称，或编辑 `assets\config\instance_names.json` 文件手动添加。

在忘却之庭的界面，用小助手工具箱中的`捕获截图`功能，勾选角色头像，点击`保存所选截图`后，

放入 `assets\images\share\character` ，并修改 `assets\config\character_names.json` 文件。

同时欢迎用`未压缩`的方式上传到 [Issue](https://github.com/moesnow/March7thAssistant/issues)，比如压缩包，或者 [PR](https://github.com/moesnow/March7thAssistant/pulls) 也可以。

### Q：完整运行的作用是什么

A：按照 `日常`→`清体力`→`锄大地`→`模拟宇宙`→`逐光捡金`→`领取奖励` 的顺序依次执行

已经判断为完成的任务不会重复运行，其中日常和锄大地的重置时间为每天凌晨4点，

模拟宇宙和逐光捡金的重置时间为每周一凌晨4点。

### Q：开始运行后就不能移动键盘鼠标和切换到后台了吗

A：是的，如果需要后台运行，请尝试 [远程本地多用户桌面](https://m7a.top/#/assets/docs/Background)

### Q：添加自定义通知的方式

A：图形界面内只支持启用`Windows原生通知`，需要其他通知请在 `config.yaml` 中开启。

### Q：模拟宇宙能修改第几个世界、角色、命途以及难度吗？

A：选好世界和角色进入一次再退出即可，命途和难度可以在设置中找到模拟宇宙，点击原版运行，在图形界面内修改

### Q：模拟宇宙其他问题

A：快速上手，请访问：[项目文档](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/index.md) 

遇到问题，请在提问前查看：[Q&A](https://github.com/Night-stars-1/Auto_Simulated_Universe_Docs/blob/docs/docs/guide/qa.md)

### Q：锄大地卡住不动，总是就是不正常运行

A：请检查是否存在未解锁的传送点、地图大门，未完成的机巧鸟等任务。

### Q：锄大地中途中断了，怎么从指定地图运行呢

A：在设置中找到锄大地，点击原版运行，选择调试模式就可以选地图。
