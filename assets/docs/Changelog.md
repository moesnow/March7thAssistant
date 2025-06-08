# 更新日志

## v2025.6.9

- 支持 3.3 版本新增关卡和角色 [#580](https://github.com/moesnow/March7thAssistant/pull/580)
- 支持将抽卡记录导出为 Excel 文件 [#574](https://github.com/moesnow/March7thAssistant/pull/574)
- 支持在配置文件中修改每次拟造花萼使用多少体力 [#545](https://github.com/moesnow/March7thAssistant/pull/545)
- 模拟宇宙（Auto_Simulated_Universe）v8.04
- 模拟宇宙支持通过 Mirror酱 进行更新

## v2025.4.18

- 适配二周年活动图标
- 支持遐蝶 [#548](https://github.com/moesnow/March7thAssistant/pull/548)
- 支持配置从周几后开始执行历战余响（周本） [#479](https://github.com/moesnow/March7thAssistant/pull/479)
- 当遗器数量达到上限时，将会先执行分解四星遗器 [#524](https://github.com/moesnow/March7thAssistant/pull/524)
- OneBot 支持同时发送私聊消息和群消息 [#540](https://github.com/moesnow/March7thAssistant/pull/540)
- 锄大地增加翁法洛斯优先级设置项 [#547](https://github.com/moesnow/March7thAssistant/pull/547)
- 优化 Mirror酱 使用体验，增加CDK过期等错误提示
- 修复 飞书、Gotify、OneBot 推送 [#520](https://github.com/moesnow/March7thAssistant/pull/520) [#517](https://github.com/moesnow/March7thAssistant/pull/517)
- 修复未完成全部日常任务时可能无法正确领取奖励
- 修复系统不支持自动主题时导致的闪退 [#525](https://github.com/moesnow/March7thAssistant/pull/525)
- 修复定时任务时间读取本地区域设置导致的闪退 [#512](https://github.com/moesnow/March7thAssistant/pull/512)

## v2025.3.7

- 模拟宇宙（Auto_Simulated_Universe）适配新版本差分宇宙
- 支持 3.1 版本新增关卡和角色 [#486](https://github.com/moesnow/March7thAssistant/pull/486)
- 支持任务完成后运行指定程序或脚本 [#453](https://github.com/moesnow/March7thAssistant/pull/453)
- 支持每周优先运行一次差分宇宙（设置-宇宙）
- 接入 Mirror酱 第三方应用分发平台（关于 → 更新源）
- 修复设置培养目标后部分副本异常
- 修复无法进入经典模拟宇宙界面
- 修复无法正常合成消耗品 [#482](https://github.com/moesnow/March7thAssistant/issues/482)
- 触屏模式暂不可用 [#487](https://github.com/moesnow/March7thAssistant/issues/487)

## v2025.1.20

- 支持 3.0 版本新增关卡和角色 [#442](https://github.com/moesnow/March7thAssistant/pull/442)
- 支持 “Matrix” 推送方式 [#440](https://github.com/moesnow/March7thAssistant/pull/440)
- 修改开拓力上限至300 [#447](https://github.com/moesnow/March7thAssistant/pull/447)
- 修复无法识别沉浸器数量 [#441](https://github.com/moesnow/March7thAssistant/issues/441)
- 修复无法更新抽卡记录
- 部分代码规范性优化 [#443](https://github.com/moesnow/March7thAssistant/pull/443)

## v2024.12.18

### 更新
- "启用位面分裂"开启后，存在双倍次数时体力优先「饰品提取」
- 支持在图形界面中开关所有的推送方式，并修改对应的配置项
- 优化了“解锁帧率”和“触屏模式”的报错提示（需要将游戏图像质量修改为自定义）
- “启用自动战斗检测”开启后，会在启动游戏前尝试检查并修改对应的注册表值

## v2024.12.12

### 更新
- 支持 “触屏模式（云游戏移动端 UI）” 启动游戏（工具箱）
- “领取沉浸奖励” 选项更改为 “领取沉浸奖励/执行饰品提取”（领取积分奖励后将自动执行饰品提取）
- 修复更换新壁纸 “愿今夜无梦” 后无法进入邮箱
- 修复无法识别并跳过末日幻影快速挑战提示框 [#406](https://github.com/moesnow/March7thAssistant/issues/406) 

## v2.7.0

### 新功能
- 支持 “星期日” 、 “灵砂”
- 支持末日幻影 [#397](https://github.com/moesnow/March7thAssistant/pull/397) 
- 支持开机后自动运行（设置—杂项）
- 循环模式每次启动前会重新加载配置文件
- 增加 “在多显示器上进行截屏” 选项（设置—杂项） [#392](https://github.com/moesnow/March7thAssistant/pull/392) 
- 支持自动获取通过米哈游启动器安装游戏的路径
- 优化主程序缺失后的报错信息

### 修复
- “日常任务” 会在每次启动时被错误清空
- “自动对话” 状态不会变化和速度过慢
- 降低角色头像匹配阈值 [#356](https://github.com/moesnow/March7thAssistant/issues/356)

## v2.6.3

### 新功能
- 支持 2.6 版本新增关卡和角色（乱破）
- “副本名称” 配置项支持手动输入
- 阵亡导致挑战失败后支持自动重试 [#385](https://github.com/moesnow/March7thAssistant/pull/385)
- 支持自动批量使用兑换码（工具箱）
- “抽卡记录” 支持 “更新完整数据”（用于修复错误的抽卡数据）
- 循环模式支持 “根据开拓力”（原有模式） 和 “定时任务”（指定时间）
- 支持 “Server酱3” 推送方式 [#377](https://github.com/moesnow/March7thAssistant/pull/377)

### 修复
- 更换抽卡记录 API
- 手动修改配置文件会被图形界面覆盖 [#341](https://github.com/moesnow/March7thAssistant/issues/341) [#379](https://github.com/moesnow/March7thAssistant/issues/379)
- 游戏窗口位于多显示器副屏时截图内容全黑或坐标偏移 [#378](https://github.com/moesnow/March7thAssistant/pull/378) [#384](https://github.com/moesnow/March7thAssistant/pull/384)
- 暗黑主题下首次启动程序后账号列表背景色异常
- 存在“花藏繁生”活动但未启用的情况下进入死循环

## v2.5.4

### 新功能
- 支持 2.5 版本新增关卡
- 支援功能重做（支持指定好友的指定角色且支持饰品提取使用，需重新配置）
- 支持 “翡翠” 、 “椒丘” 、“飞霄” 、 “貊泽”
- 支持B服启动后自动点击 “登录” [#321](https://github.com/moesnow/March7thAssistant/discussions/321)
- “任务完成后” 新增 “重启” 选项

### 修复
- 部分文字 OCR 识别异常
- 自动登录检测异常 [#336](https://github.com/moesnow/March7thAssistant/issues/336)
- 支援功能在高分屏下异常 [#329](https://github.com/moesnow/March7thAssistant/issues/329)
- 修复拟造花萼（赤）错行 [#328](https://github.com/moesnow/March7thAssistant/issues/328)
- 延长逐光捡金等待场景加载的时间 [#322](https://github.com/moesnow/March7thAssistant/issues/322)
- 优化饰品提取开始挑战的逻辑 [#325](https://github.com/moesnow/March7thAssistant/issues/325)
- 优化 “启动失败” 的报错提示

## v2.4.0

### 新功能
- 支持差分宇宙和饰品提取
- 支持 “智识之蕾•匹诺康尼大剧院” 关卡
- 支持 “云璃” 、 “三月七（虚数）” 、 “开拓者（虚数）”
- 飞书 支持发送截图 [#310](https://github.com/moesnow/March7thAssistant/pull/310)

### 修复
- 新版材料合成页面卡住的问题 [#231](https://github.com/moesnow/March7thAssistant/issues/231)

## v2.3.0

### 新功能
- 适配模拟宇宙新入口（需先解锁差分宇宙）
- 支持 2.3 版本新增关卡 [#277](https://github.com/moesnow/March7thAssistant/pull/277)
- 支持B服 [#269](https://github.com/moesnow/March7thAssistant/pull/269)
- 支持国际服账号操作 [#268](https://github.com/moesnow/March7thAssistant/pull/268)
- 支持逐光捡金和支援角色选择 “流萤”
- 支持判断米哈游启动器默认安装路径

### 修复
- 支持位于城市沙盘时正确进入地图界面
- 混沌回忆刷新后的弹窗有概率导致失败
- PAC错误 [#276](https://github.com/moesnow/March7thAssistant/pull/276)

## v2.2.0

### 新功能
- 支持 2.2 版本新增关卡
- 支持逐光捡金和支援角色选择 “砂金” 和 “知更鸟”
- 支持在设置配置模拟宇宙的命途和难度 [#223](https://github.com/moesnow/March7thAssistant/pull/223)
- 支持在设置配置锄大地的购买选项 [#238](https://github.com/moesnow/March7thAssistant/pull/238)
- 设置内新增多账户管理功能 [#224](https://github.com/moesnow/March7thAssistant/pull/224)
- 支持登录过期时尝试自动登录 [#237](https://github.com/moesnow/March7thAssistant/pull/237)
- 默认将模板图片缓存到内存中 [#244](https://github.com/moesnow/March7thAssistant/pull/244)
- 抽卡记录新增 “清空” 按钮
- 适配支援角色界面的新样式

### 修复
- 无法切换到 “漫游签证” 和 “委托” 界面 [#247](https://github.com/moesnow/March7thAssistant/pull/247)
- 最新一期虚构叙事中部分角色开怪失败 [#242](https://github.com/moesnow/March7thAssistant/pull/242)
- 无法领取 “支援” 和 “巡星之礼” 奖励
- 特殊情况下抽卡记录无法正常显示和闪退

## v2.1.1

### 新功能
- 自动对话适配手柄界面 [#208](https://github.com/moesnow/March7thAssistant/pull/208)
- Telegram 推送方式支持配置代理或使用PAC [#219](https://github.com/moesnow/March7thAssistant/pull/219) [#222](https://github.com/moesnow/March7thAssistant/pull/222)
- 邮件推送方式支持 outlook [#220](https://github.com/moesnow/March7thAssistant/pull/220)

### 修复
- 源码运行锄大地 [#211](https://github.com/moesnow/March7thAssistant/pull/211)
- 部分文字 OCR 识别异常

## v2.1.0

### 新功能
- 支持2.1新增副本和活动
- 委托奖励更改为一键领取
- “拟造花萼（赤）”改为通过地点进行查找
- 签到活动开关合并
- 支持逐光捡金和支援角色选择 “黄泉”和“加拉赫”

### 修复
- 红点会导致逐光捡金判断第二间失败
- 合成任务因界面变化而无法完成
- “拟造花萼（赤）”向后兼容

## v2.0.7

### 新功能
- 支持自定义消息推送格式
- 混沌回忆检测到角色阵亡自动重试
- 优化部分执行逻辑
- 完整运行结束推送剩余开拓力和预计恢复时间（未开启循环时） [#197](https://github.com/moesnow/March7thAssistant/pull/197)

### 修复
- 手机菜单点击图标异常

## v2.0.6

### 新功能
- 支持自定义每日合成沉浸器的个数 [#165](https://github.com/moesnow/March7thAssistant/pull/165)
- 新增快捷查看日志按钮 [#150](https://github.com/moesnow/March7thAssistant/pull/150)
- 在 “完整运行” 清体力前增加一次 “委托奖励检测” [#171](https://github.com/moesnow/March7thAssistant/pull/171)

### 修复
- 降低查找副本时的滚动速度
- 部分用户报错 “'cmd' 不是内部或外部命令...” 导致无法启动游戏
- 部分分辨率全屏状态判断异常 [#183](https://github.com/moesnow/March7thAssistant/pull/183)

### 其他
- 主页点击模拟宇宙快速启动现在也会领取每周奖励
- 移除设置内锄大地和模拟宇宙更新等按钮（请改从主页运行相应功能）

## v2.0.5

### 新功能
- “任务完成后” 新增 “注销” 选项
- 工具箱新增帧率解锁 [#161](https://github.com/moesnow/March7thAssistant/pull/161)
- “启用自动修改分辨率” 选项更改为 “启用自动修改分辨率并关闭自动 HDR” [#156](https://github.com/moesnow/March7thAssistant/pull/156)
- 新增 [OneBot](https://onebot.dev) 推送方式（QQ 机器人）
- 企业微信应用推送方式支持发送图片

### 修复
- 部分情况下解锁帧率失败
- 部分情况下无法正常发送 gotify 通知
- 任务追踪图标导致地图界面无法识别
- 多个红点导致模拟宇宙领取每周奖励失败
- 快速解锁教学动画导致虚构叙事异常
- 主页三月七背景在高缩放率下模糊的问题
- 某启动器修改分辨率注册表项后会导致注册表读取错误

## v2.0.4

### 新功能
- 抽卡记录导出与简单分析（支持 [SRGF](https://uigf.org/zh/standards/SRGF.html) 数据格式导入和导出）
- 支持逐光捡金和支援角色选择 “花火”

### 修复
- 特殊情况会导致下载失败

## v2.0.3

### 新功能
- 支持所有手机壁纸
- “自动剧情” 更名 “自动对话”
- 副本名称新增 “无（跳过）” 选项
- 支持大于等于 1920*1080 的 16:9 分辨率（实验性功能）

### 修复
- 地图界面判断失败
- “自动修改分辨率” 失效
- 关闭 “启用自动修改分辨率” 选项会导致无法启动游戏

## v2.0.2

### 新功能
- 配队界面优化
- 主页部分模块支持多选项（锄大地、模拟宇宙、逐光捡金）
- 支持重置锄大地和模拟宇宙的配置文件
- 新增 “游戏刷新时间”、“启用自动修改分辨率”、“启用自动配置游戏路径” 选项
- 部分界面支持断网重连

### 修复
- 支持识别3D地图界面
- 适配混沌回忆刷新后首次进入的新弹窗

## v2.0.1

### 新功能
- 新增遗器副本完成后“自动分解四星及以下遗器”功能（默认关闭）
- 新增“自动剧情”功能（侧栏工具箱内开启）
- 新增“启动游戏”按钮（你可以将小助手当作启动器来用了）
- 支持自动修改分辨率，并在启动游戏后恢复原分辨率
- 支持自定义推送方式 [#136](https://github.com/moesnow/March7thAssistant/pull/136)

### 修复
- 更新程序覆盖失败
- 异常状态下历战余响不会打满3次
- 路径中含有空格导致更新会跳转到浏览器
- 更新程序会错误删除 Fhoe-Rail\map 目录（遇到此问题手动点一次单独更新即可）

## v2.0.0

### 新功能
- 支持 2.0 版本新增关卡
- 支持 “限时提前解锁” 关卡
- 支持选择 “拟造花萼（金）偏好地区”
- 支持忘却之庭和支援角色选择 “真理医生”、“黑天鹅”、“米沙”

### 修复
- 部分设备 “焦炙之形” 关卡 OCR 识别异常
- 降低 “拟造花萼（赤）” 阈值要求
- “使用1次「万能合成机」” 合成材料更改为 “微光原核”
- 版本更新后切换到 “回忆” 异常
- 版本更新后切换到 “逐光捡金” 异常
- 签到活动读取图片失败

## v1.7.7

### 新功能
- SMTP 支持发送截图 [#114](https://github.com/moesnow/March7thAssistant/pull/114)
- 支持 gotify 推送方式 [#112](https://github.com/moesnow/March7thAssistant/pull/112)
- 新增“启用使用支援角色”选项（默认开启） [#121](https://github.com/moesnow/March7thAssistant/issues/121)
- 修改“指定好友的支援角色”说明（填写用户名和UID都是支持的）

### 修复
- 远程桌面多开会错误终止其他用户的游戏进程 [#113](https://github.com/moesnow/March7thAssistant/pull/113) [#35](https://github.com/moesnow/March7thAssistant/issues/35)
- 部分文字 OCR 识别异常（如 RapidOCR 的拟造花萼相关问题）
- 路径中含有英文括号导致解压失败
- 模拟宇宙完成后无法正常领取奖励

## v1.7.6

### 新功能
- 支持活动花藏繁生、异器盈界、位面分裂（默认关闭）

## v1.7.5

### 新功能
- 支持虚构叙事（默认关卡范围 3-4）

## v1.7.4

### 新功能
- 支持更新时下载完整包（默认开启，设置→关于）
- 支持加入预览版更新渠道（设置→关于）
- 更新时支持调用 aria2 进行多线程下载（速度更快同时减少了下载中断的情况）
- 更新时不再使用系统临时目录（方便添加杀毒软件白名单 [#86](https://github.com/moesnow/March7thAssistant/discussions/86#discussioncomment-7966897)）

### 修复
- 重复挑战副本运行异常

## v1.7.3

### 新功能
- 支持忘却之庭和支援角色选择“银枝”
- 支持关闭“启用自动战斗检测”（设置→按键）
- “自动战斗检测”时间更改为无限制（临时修复 [#96](https://github.com/moesnow/March7thAssistant/pull/96)）

### 修复
- 忘却之庭交换队伍后未交换秘技释放顺序
- 忘却之庭挑战失败后会尝试挑战下一层

## v1.7.2

### 新功能
- 支持关闭每日实训（可搭配每天一次模拟宇宙来完成500活跃度）
- 支持新历战余响「蛀星的旧靥」
- 支持忘却之庭和支援角色选择“阮·梅”

### 修复
- 传送忘却之庭小概率错误点击成信用点图标 [#91](https://github.com/moesnow/March7thAssistant/pull/91)

## v1.7.1


### 修复
- 锄大地和模拟宇宙运行异常

## v1.7.0

### 新功能
- 适配每日实训新任务
- 适配混沌回忆新界面（首次通关7层后需要手动完成教学动画）
- 混沌回忆选角色界面支持滚动查找
- 混沌回忆挑战失败后自动交换队伍
- 混沌回忆默认关卡范围更改为 7-12
- 支持的队伍编号更改为 3-7
- 支持忘却之庭和支援角色选择“寒鸦”和“雪衣”
- 钉钉推送默认配置添加 secret 参数

### 修复
- 混沌回忆完成后领取奖励失败

## v1.6.9

### 新功能
- 适配混沌回忆1-5层更改为单个BOSS

### 修复
- 滚动后缺少延迟导致部分界面识别位置产生偏移（再一次）
- 移除部分测试代码

## v1.6.8


### 修复
- 模拟宇宙运行频率配置名错误

## v1.6.7

### 新功能
- 支持开拓力优先合成沉浸器（默认关闭）
- 模拟宇宙支持修改运行频率（默认每周一次）

### 修复
- 滚动后缺少延迟导致部分界面识别位置产生偏移

## v1.6.6

### 新功能
- 支持单独运行“每日实训”和“清体力”任务
- 更新 Fhoe-Rail 前会自动删除旧的 map 文件夹

### 修复
- 自动保存阵容导致“回忆”和“混沌回忆”无法正常运行
- 部分含生僻字的副本名称小概率识别错误

## v1.6.5

### 新功能
- 支持使用集成模式运行模拟宇宙（默认）
- 支持忘却之庭和支援角色选择“托帕&账账”、“桂乃芬”和“藿藿”
- 添加副本“幽府之形”和“幽冥之径”
- 支持拟造花萼体力小于60的情况 [#31](https://github.com/moesnow/March7thAssistant/pull/31)
- 支持从"开始菜单"的快捷方式获取游戏路径 [#29](https://github.com/moesnow/March7thAssistant/pull/29)

### 修复
- 自动从启动器获取游戏路径
- “使用消耗品”选中失败后重试逻辑错误 [#41](https://github.com/moesnow/March7thAssistant/pull/41)

## v1.6.4

### 新功能
- 支持自定义模拟宇宙每周运行次数
- 支持完成“通关「模拟宇宙」（任意世界）的1个区域”
- 增加模拟宇宙完整性检测 [#27](https://github.com/moesnow/March7thAssistant/pull/27)
- 支持“开拓者（穹）•毁灭”和“开拓者（穹）•存护” [#26](https://github.com/moesnow/March7thAssistant/pull/26)

### 修复
- 修复“游戏退出失败”的问题（回退实验性改动）

## v1.6.3

### 新功能
- 支持通过“姬子试用”完成部分每日实训（实验性）
- 支持通过“回忆一”完成部分每日实训（实验性）
- Python 3.12.0 强力驱动
- 适配 Fhoe-Rail 的最新改动

### 修复
- “超时时间”修改为小数会导致图形界面启动崩溃
- 无法领取巡光之礼和巡星之礼最后一天的奖励
### 其他
- 优化了现有功能的稳定性
- 现在只会停止当前用户下的游戏进程（实验性）

## v1.6.2

### 新功能
- 支持使用“后备开拓力”和“燃料”
- 支持领取活动“巡光之礼”奖励
- go-cqhttp 支持发送截图 [#21](https://github.com/moesnow/March7thAssistant/pull/21)

### 修复
- 有极小概率将开拓力识别成“米”字
### 其他
- 移除 power_total、dispatch_count、ocr_path 配置项
- 使用消耗品前会先筛选类别避免背包物品太多
- 升级 [PaddleOCR-json_v.1.3.1](https://github.com/hiroi-sora/PaddleOCR-json/releases/tag/v1.3.1)，兼容 Win7 x64
- 支持 [RapidOCR-json_v0.2.0](https://github.com/hiroi-sora/RapidOCR-json/releases/download/v0.2.0/RapidOCR-json_v0.2.0.7z)，兼容没有 AVX2 指令集的 CPU（自动判断）

## v1.6.1

### 新功能
- 预设“副本名称”（包含解释）
- 支持“镜流”和“开拓者（星）•毁灭”
- 支持领取活动“巡星之礼”奖励
- 支持识别“开启无名勋礼”界面

### 修复
- PushPlus推送 [#14](https://github.com/moesnow/March7thAssistant/pull/14)
### 其他
- 支持判断手机壁纸状态
- 支持判断是否购买了“无名客的荣勋”
- 配置队伍改为从手机界面进入而不是按键

## v1.6.0

### 新功能
- 完成混沌回忆后自动领取星琼奖励
- 支持使用集成模式运行锄大地（默认）
- 图形界面新增测试消息推送的功能
- 补全了大部分推送方式所需的配置项（推荐Bark、Server酱、邮箱Smtp）
- 支持从官方启动器获取游戏路径 [#10](https://github.com/moesnow/March7thAssistant/pull/10)

### 修复
- Windows终端高版本提示 “错误 2147942402 (0x80070002)” [#12](https://github.com/moesnow/March7thAssistant/pull/12)
- 低配置电脑检测委托状态偶尔异常
- 优化了 “发生错误: None” 的错误提示
- 开启系统设置 “显示强调色” 导致图形界面显示异常 [#11](https://github.com/moesnow/March7thAssistant/pull/11)
### 其他
- 使用多线程大大缩短了图形界面的加载时间 [#11](https://github.com/moesnow/March7thAssistant/pull/11)
- 优化Python版本检测和依赖安装
- 内置“使用教程”，网页版效果更佳

## v1.5.0

### 新功能
- 优化了“副本名称”、“今日实训”在图形界面的显示方式
- 尝试支持国际服启动界面（简体中文）
- 合并 “退出游戏”、“自动关机” 等功能为 “任务完成后”，默认 “无”
- 循环运行4点启动现在会随机延迟0-10分钟执行

### 修复
- 更新时不会自动关闭图形界面（文件占用导致更新失败）
- 工作目录不正确无法运行（常见于使用任务计划程序）
### 其他
- 自动测速并选择最快的镜像源
- 现在“超时”功能可以正确强制停止“锄大地”、“模拟宇宙”子任务
- 优先使用 Windows Terminal 而不是 conhost
- 弃用 “python_path”、“pip_mirror”、“github_mirror” 等设置项

## v1.4.2

### 新功能
- 内置 [Fhoe-Rail](https://github.com/linruowuyin/Fhoe-Rail) 自动锄大地项目，支持在设置界面单独更新，欢迎给作者点个 Star
- 调整了目录结构，推荐手动进行本次更新，自动更新不会移除不再使用的文件

## v1.4.1.1


### 修复
- 偶尔无法正常领取月卡
- 从环境变量自动获取Python路径失败
- pushplus推送问题（再一次）

## v1.4.1

### 新功能
- 支持忘却之庭和支援角色选择“符玄”和“玲可”
- 增加选项用于开关实训“完成1次「忘却之庭」”（默认关闭）
- 支持任务完成后播放声音提示（默认关闭）
- 支持Windows原生通知（默认开启）
- 优化部分错误提示

### 修复
- 锄大地原版启动报错
- pushplus推送问题

## v1.4.0

### 新功能
- 支持任务完成后自动关机（默认关闭）
- 图形界面导航栏优化
- 图形界面支持深色模式

### 修复
- 延长了点击传送副本后的等待时间

## v1.3.5

### 新功能
- 支持图形界面中修改秘技按键 [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- 支持图形界面中导入配置文件 [#4](https://github.com/moesnow/March7thAssistant/pull/4)
- 支持使用指定好友的支援角色 [#5](https://github.com/moesnow/March7thAssistant/pull/5)
- 下载过程支持显示进度条

### 修复
- 更换手机壁纸，导致委托检测失败

## v1.3.4.2

### 新功能
- 配置文件中新增修改秘技按键 [#3](https://github.com/moesnow/March7thAssistant/pull/3)

### 修复
- 位面分裂活动横幅导致无法自动进入黑塔办公室
- 在图形界面中隐藏“副本所需开拓力”设置项避免误修改
- 尝试解决卡在日常任务“完成1次「忘却之庭」”的问题
- 尝试解决自动战斗未自动开启的问题

## v1.3.4.1


### 修复
- 修改 powershell 命令改用 cmd 运行
- 自动安装 Python 的一些问题，现在可以正常安装（实验性）

## v1.3.4

### 新功能
- 支持忘却之庭和支援角色选择 “丹恒•饮月”
- 支持在设置中打开模拟宇宙和锄大地的原版图形界面（用于设置命途等）
- 支持自动下载安装 Python、PaddleOCR-json （实验性）
- 优化三月七小助手和模拟宇宙的更新功能（实验性）

### 修复
- 非4K分辨率下窗口运行游戏导致功能异常

## v1.3.3.1

### 新功能
- 支持在游戏启动后自动检测并保存游戏路径
- 更新常见问题（FQA）

## v1.3.3

### 新功能
- 支持设置是否领取无名勋礼奖励（默认关闭）
- 添加了更多的错误检测
- 更新常见问题（FQA）

## v1.3.2

### 新功能
- 支持自动开启“自动战斗”
- 支持识别锄大地和模拟宇宙运行状态
- 支持识别游戏更新所导致的需要重启
- 支持在官方启动器打开的情况下启动游戏
- 锄大地和模拟宇宙的脚本遇到错误现在会立即终止

### 修复
- 运行任务后且图形界面未关闭，修改配置会导致时间和日常状态被覆盖
- 启动游戏后未处于主界面判定启动失败（现支持任意已知界面）

## v1.3.1

### 新功能
- 支持模拟宇宙“领取沉浸奖励”，在设置中开启，默认关闭
- 支持单独更新模拟宇宙版本（实验性）
- 图形界面支持自动更新版本（实验性）
- 图形界面支持手动检测更新
- 图形界面增加“更新日志”、“常见问题”等子页面

### 修复
- 优化模拟宇宙完成后的通知截图

## v1.3.0.2

### 新功能
- 恢复 v1.3.0 中移除的使用支援角色（borrow_character_enable）选项
- 副本名称设置为"无"代表即使有对应的实训任务也不会去完成

### 修复
- v1.3.0 混沌回忆星数检测异常

## v1.3.0.1


### 修复
- v1.3.0 通过图形界面生成的配置文件不正确

## v1.3.0

### 新功能
- 支持识别每日实训内容并尝试完成，而不是全部做一遍 [点击查看支持任务](https://github.com/moesnow/March7thAssistant#%E6%AF%8F%E6%97%A5%E5%AE%9E%E8%AE%AD)
- 新增选项每周优先完成三次「历战余响」（默认关闭）
- 副本名称（instance_names）更改为根据副本类型单独设置，同时也会用于“完成1次xxx”的实训任务中
- 移除“使用支援角色”、“强制使用支援角色”、“启用每日拍照”和“启用每日合成/使用 材料/消耗品”配置选项
- 每周模拟宇宙运行前先检查一遍可领取的奖励

### 修复
- 尝试解决低概率下识别副本名称失败
- 彻底解决每日实训是否全部完成检测不可信

## v1.2.6

### 新功能
- 支持更多副本类型：侵蚀隧洞、凝滞虚影、拟造花萼（金）、拟造花萼（赤）
- 设置中的捕获截图功能支持OCR识别文字，可用于复制副本名称

## v1.2.5

### 新功能
- 内置锄大地命令


### 修复
- 开拓力偶尔识别成“1240”而不是“/240”
- 每日实训是否全部完成检测失败

## v1.2.4

### 新功能
- 图形界面支持显示更新日志
- 更新模拟宇宙 [Auto_Simulated_Universe  v5.30](https://github.com/CHNZYX/Auto_Simulated_Universe/tree/f17c5db33a42d7f6e6204cb3e6e83ec2fd208e5e)


### 修复
- 1.3版本的各种UI变化导致的异常

## v1.2.3

### 新功能
- 混沌回忆支持检测每关星数
- 副本名称支持简写，例如【睿治之径】


### 修复
- 偶尔点击速度过快导致领取实训奖励失败
- 鼠标位于屏幕左上角触发安全策略导致点击失效
- 偶尔界面切换速度太慢导致消耗品识别点击位置偏移
- 检测无名勋礼奖励模板图片错误
- 降低部分阈值要求，提高操作成功率
- 移除部分多余的界面检测，提高速度

## v1.2.2

### Features
- feat: add Bailu and Kafka
适配白露和卡芙卡
- feat: forgottenhall support melee character
混沌回忆支持近战角色开怪
- feat: add take_screenshot to gui
图形界面设置中新增捕获截图功能
- feat: add check update to gui
图形界面启动时检测更新
- feat: add tip when start

### Fixes
- fix: use consumables when repeat
消耗品效果未过期导致无法使用
- fix: check_update option not available
更新检测开关不可用
- fix: avoid trailblaze_power overflow
模拟宇宙前后清一次体力避免溢出
- fix: space cause text ocr fail
偶尔会识别出空格导致判断文字失败
- fix: exit function

## v1.2.1

### Features
- feat: auto change team
在打副本和锄大地前可以自动切换队伍
- feat: add submodule Auto_Simulated_Universe
添加模拟宇宙子模块

### Fixes
- fix: switch window problem
游戏窗口偶尔无法切换到前台
- fix: same borrow character
支援角色和原队伍角色相同

## v1.2.0

### Features
- feat: graphical user interface
增加图形用户界面
