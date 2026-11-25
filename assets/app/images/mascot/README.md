# Q 版三月七

三月七小助手项目自有的 Q 版形象，由项目作者提供。请勿换用游戏官方立绘或来源不明的图片。

| 文件 | 姿势 | 使用位置 |
|---|---|---|
| chibi_full.webp | 全身站立 | 问候区就绪、已停止，首次配置向导，关于页 |
| chibi_typing.webp | 敲电脑 | 问候区运行中 |
| chibi_wave.webp | 挥手 | 问候区今日全部完成，首次配置向导，关闭程序确认 |
| chibi_lost.webp | 拿地图发懵 | 问候区运行失败 |
| chibi_ok.webp | 探头比OK | 问候区还没配好，首次配置向导，账号页和运行记录为空 |
| chibi_camera.webp | 举相机 | 工具箱的游戏截图卡 |
| chibi_gift.webp | 抱礼盒 | 发现新版本 |
| chibi_serious.webp | 认真 | 帮助页「没找到答案？」，首次配置向导，账号密码，启用多账号，免 UAC、后台模式、临时降低画质、关闭更新检测、模拟宇宙、触屏模式的确认 |
| chibi_search.webp | 放大镜 | 抽卡记录为空，搜索无结果，首次配置向导 |
| chibi_viewfinder.webp | 取景器 | 首次配置向导识别游戏路径 |
| chibi_cloud.webp | 云端 | 首次配置向导选云·星穹铁道时 |
| chibi_dizzy.webp | 眼花 | 连点 LOGO 的提示 |
| chibi_later.webp | 下次一定 | 赞赏 |
| chibi_stamp.webp | 盖章 | 首次配置向导完成，数据已恢复、已导入 |
| chibi_startled.webp | 吓一跳 | 抽卡记录、流程导入导出失败 |
| chibi_box.webp | 抱纸箱 | 删除账号、清除登录信息，清空和替换抽卡记录，清空兑换码，删除定时计划和流程 |

用 alpha > 8 的内容范围向外留 6 个原图像素，以 LANCZOS 将长边缩至 512 px，保存带透明通道的 WebP（quality 88，method 6）。建议逻辑高度为问候区 170～200 px、空状态 220～250 px、对话框 96～120 px、帮助小卡约 100 px。

在仓库根目录用安装了 Pillow 的 Python 执行以下命令。原图名为表中「姿势」加 `.png`，长夜月的原图前面再加 `长夜月_`。

```powershell
python assets/scripts/prepare_mascot.py --source "D:\素材\Q版"
python assets/scripts/prepare_mascot.py --source "D:\素材\长夜月" --evernight
```

## 长夜月

`evernight/` 里是长夜主题用的 Q 版长夜月，由项目作者提供，文件名和规格与三月七相同，共 5 个姿势：全身站立、敲电脑、挥手、拿地图发懵、探头比OK，用于问候区、账号页和运行记录的空页面、关于页和关闭程序确认。其他位置没有对应的图，自动显示三月七；首次配置向导只有部分姿势有图，全程用三月七。

长夜月的原图单独放在一个目录，可以只放要更新的几张。
