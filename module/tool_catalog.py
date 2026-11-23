from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    id: str
    name: str
    description: str
    widget: str
    icon: str


TOOLS = (
    Tool("autoplot", "自动对话", "进入剧情页面后自动开始运行，支持大于等于 1920*1080 的 16:9 分辨率，不支持云·星穹铁道", "automaticPlotCard", "FIF.CHAT"),
    Tool("screenshot", "游戏截图", "检查程序获取的图像是否正确，支持OCR识别文字（可用于自行排查异常）", "gameScreenshotCard", "FIF.CAMERA"),
    Tool("unlock_fps", "解锁帧率", "通过修改注册表解锁120帧率，如已解锁，再次点击将恢复60帧率（支持国服和国际服）", "unlockfpsCard", "FIF.SPEED_HIGH"),
    Tool("redemption", "兑换码", "批量使用兑换码，每行一个，自动过滤空格等无效字符", "redemptionCodeCard", "UiIcon.TICKET"),
    Tool("cloud_touch", "触屏模式", "以云游戏移动端 UI 的方式启动游戏，可搭配 UU远程 平板触控模式，启动后会将命令复制到剪贴板内", "cloudTouchCard", "UiIcon.TAP"),
    Tool("desktop_twin", "桌面分身", "在独立的 Windows 桌面中运行小助手和游戏", "desktopTwinCard", "FIF.APPLICATION"),
    Tool("character_export", "角色面板导出", "导出角色的属性、光锥、星魂、技能和遗器。", "characterExportCard", "FIF.PEOPLE"),
    Tool("screen_test", "界面可切换性测试", "以最短路径遍历所有可达界面，验证界面切换是否正常", "screenTestCard", "UiIcon.BEAKER"),
)
TOOL_BY_ID = {tool.id: tool for tool in TOOLS}
