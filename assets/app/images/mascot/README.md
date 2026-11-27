# Q 版三月七

三月七小助手项目自有的 Q 版形象，由项目作者提供。请勿换用游戏官方立绘或来源不明的图片。

| 文件 | 姿势 | 使用位置 |
|---|---|---|
| chibi_full.webp | 全身站立 | 问候区就绪、已停止，首次配置向导，关于页 |
| chibi_typing.webp | 敲电脑 | 问候区运行中 |
| chibi_wave.webp | 挥手 | 问候区今日全部完成，首次配置向导，关闭程序确认 |
| chibi_lost.webp | 拿地图发懵 | 问候区运行失败 |
| chibi_ok.webp | 探头比OK | 首次配置向导，账号页和运行记录为空 |
| overview/chibi_ok.webp | 全身比OK | 默认主题问候区「还差一步就能开始」 |
| chibi_camera.webp | 举相机 | 工具箱的游戏截图卡 |
| chibi_gift.webp | 抱礼盒 | 发现新版本 |
| chibi_serious.webp | 认真 | 帮助页「没找到答案？」，首次配置向导，账号密码，启用多账号，免 UAC、后台模式、临时降低画质、关闭更新检测、模拟宇宙、触屏模式的确认 |
| chibi_search.webp | 放大镜 | 抽卡记录为空，搜索无结果，首次配置向导 |
| chibi_viewfinder.webp | 取景器 | 首次配置向导识别游戏路径 |
| chibi_cloud.webp | 云端 | 首次配置向导选云·星穹铁道时 |
| chibi_dizzy.webp | 眼花 | 连点 LOGO 或总览小人的提示 |
| chibi_later.webp | 下次一定 | 赞赏 |
| chibi_stamp.webp | 盖章 | 首次配置向导完成，数据已恢复、已导入 |
| chibi_startled.webp | 吓一跳 | 抽卡记录、流程导入导出失败 |
| chibi_box.webp | 抱纸箱 | 删除账号、清除登录信息，清空和替换抽卡记录，清空兑换码，删除定时计划和流程 |

用 alpha > 8 的内容范围向外留 6 个原图像素，以 LANCZOS 将长边缩至 512 px，保存带透明通道的 WebP（quality 88，method 6）。建议逻辑高度为问候区 170～200 px、空状态 220～250 px、对话框 96～120 px、帮助小卡约 100 px。

在仓库根目录用安装了 Pillow 的 Python 执行以下命令。原图名为表中「姿势」加 `.png`，长夜月的原图前面再加 `长夜月_`。默认主题原图目录中可附加 `全身比OK.png`，用于导出总览专图。

```powershell
python assets/scripts/prepare_mascot.py --source "D:\素材\Q版"
python assets/scripts/prepare_mascot.py --source "D:\素材\长夜月" --evernight
```

## 长夜月

`evernight/` 下的插画与默认主题的文件一一对应。同一张三月七插画出现在哪里，就在相同位置显示对应的长夜月。首次配置向导全程显示三月七。缺少对应插画的场景沿用默认图。

| 使用位置 | 原图文件名 | 相对于 `evernight/` 的输出 |
|---|---|---|
| 总览就绪、已停止、读取状态失败，关于页 | 长夜月_全身站立.png | chibi_full.webp |
| 任务运行中 | 长夜月_查看终端.png | chibi_typing.webp |
| 今天的任务都做完了，关闭窗口确认 | 长夜月_单手撑黑伞.png | chibi_wave.webp |
| 任务需要处理 | 长夜月_检查任务单.png | chibi_lost.webp |
| 还差一步就能开始（默认主题为全身比 OK） | 长夜月_托起忆灵.png | overview/chibi_ok.webp |
| 账号页与运行历史为空（两种主题均为半身构图） | 长夜月_半身手持空相框.png | chibi_ok.webp |
| 帮助侧栏提示，账号密码及设置确认 | 长夜月_帮助提示.png | chibi_serious.webp |
| 帮助搜索无结果，全局搜索初始和无结果，抽卡记录为空 | 长夜月_放大镜.png | chibi_search.webp |
| 工具箱的游戏截图卡 | 长夜月_举相机取景.png | chibi_camera.webp |
| 侧栏赞赏弹窗 | 长夜月_提裙致谢.png | chibi_later.webp |
| 发现新版本的横幅 | 长夜月_递出礼盒.png | chibi_gift.webp |
| 删除账号、通知渠道、计划和流程，清除登录、兑换码，清空或替换抽卡记录 | 长夜月_收纳记忆匣.png | chibi_box.webp |
| 数据恢复或导入成功 | 长夜月_封存印记.png | chibi_stamp.webp |
| 抽卡记录或流程导入、导出失败 | 长夜月_察看断片.png | chibi_startled.webp |

长夜月的原图单独放在一个目录，可以只放要更新的几张；仍可用原来的文件名导出。若同一输出同时有新旧两张原图，以上表的原图为准。
