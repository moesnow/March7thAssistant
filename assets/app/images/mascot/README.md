# Q 版三月七

三月七小助手项目自有的 Q 版形象，由项目作者提供。请勿换用游戏官方立绘或来源不明的图片。

| 文件 | 姿势 | 使用位置 |
|---|---|---|
| chibi_full.webp | 全身站立 | 问候区就绪、已停止，关于页 |
| chibi_typing.webp | 敲电脑 | 问候区运行中 |
| chibi_wave.webp | 挥手 | 问候区今日全部完成，关闭程序确认 |
| chibi_lost.webp | 拿地图发懵 | 问候区运行失败，界面切换失败提示 |
| chibi_ok.webp | 探头比OK | 问候区还没配好，首次配置向导欢迎页，运行记录为空 |
| chibi_camera.webp | 举相机 | 工具箱游戏截图空状态 |
| chibi_gift.webp | 抱礼盒 | 发现新版本对话框 |
| chibi_serious.webp | 认真 | 帮助页「没找到答案？」，免 UAC、解锁帧率、自动登录风险确认 |
| chibi_search.webp | 放大镜 | 抽卡记录为空，搜索无结果 |
| chibi_viewfinder.webp | 取景器 | 向导识别游戏路径 |
| chibi_cloud.webp | 云端 | 云游戏运行方式、排队等待 |
| chibi_dizzy.webp | 眼花 | 滤镜、HDR、帧率悬浮窗等识别异常提示 |
| chibi_later.webp | 下次一定 | 更新提醒「稍后再说」 |
| chibi_stamp.webp | 盖章 | 向导设置完成，应用内完成提示 |
| chibi_startled.webp | 吓一跳 | 任务意外中断，严重错误对话框 |
| chibi_box.webp | 抱纸箱 | 删除账号、清空全部数据的确认 |

用 alpha > 8 的内容范围向外留 6 个原图像素，以 LANCZOS 将长边缩至 512 px，保存带透明通道的 WebP（quality 88，method 6）。建议逻辑高度为问候区 170～200 px、空状态 220～250 px、对话框 96～120 px、帮助小卡约 100 px。

在仓库根目录用安装了 Pillow 的 Python 执行以下命令。原图名为表中「姿势」加 `.png`。

```powershell
python assets/scripts/prepare_mascot.py --source "D:\素材\Q版"
python assets/scripts/prepare_mascot.py --source "D:\素材\长夜月" --evernight
```

长夜月原图单独放在一个目录，可逐张提供全身站立、敲电脑、挥手、拿地图发懵、探头比OK。脚本将同名 WebP 放入 `evernight/`。这五个问候姿势缺图时自动显示三月七，补入后即可使用。其他页面照常用三月七。
