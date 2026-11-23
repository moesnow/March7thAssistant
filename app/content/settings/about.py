from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, InfoBarPosition, PrimaryPushSettingCard
from app.common.icon import BrandIcon
from module.config import cfg
from module.localization import tr
from app.tools.check_update import checkUpdate
from app.tools.agent_prompt import build_agent_prompt
from utils import clipboard
import sys
import platform


def build(host):
    def copy_prompt():
        try:
            clipboard.copy(build_agent_prompt())
            InfoBar.success(
                title=tr('复制成功(＾∀＾●)'),
                content=tr("粘贴给你的 AI 助手即可"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=host.card_parent
            )
        except Exception:
            InfoBar.warning(
                title=tr('复制失败(╥╯﹏╰╥)'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=host.card_parent
            )

    host.githubCard = PrimaryPushSettingCard(
        tr('项目主页'),
        FIF.GITHUB,
        tr('项目主页'),
        "https://github.com/moesnow/March7thAssistant",
        parent=host.card_parent,
    )
    host.agentPromptCard = PrimaryPushSettingCard(
        tr('复制提示词'),
        FIF.ROBOT,
        tr('AI 助手'),
        tr('复制一段提示词发给 DeepSeek Harness、Codex、Claude Code 等 AI 助手，让它学会操作三月七小助手'),
        parent=host.card_parent,
    )
    host.bilibiliCard = PrimaryPushSettingCard(
        tr('立即前往'),
        BrandIcon.BILIBILI,
        tr('哔哩哔哩'),
        tr('欢迎关注我们的B站账号，获取最新动态和教程'),
        parent=host.card_parent,
    )
    host.qqGroupCard = PrimaryPushSettingCard(
        tr('加入群聊'),
        BrandIcon.QQ,
        tr('QQ群'),
        "",
        parent=host.card_parent,
    )
    host.aboutCard = PrimaryPushSettingCard(
        tr('检查更新'),
        FIF.INFO,
        tr('关于'),
        tr('当前版本：') + " " + cfg.version + " | Python " + sys.version.split()[0] + " | " + platform.system() + " " + platform.machine(),
        parent=host.card_parent,
    )
    host.githubCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/moesnow/March7thAssistant")))
    host.agentPromptCard.clicked.connect(copy_prompt)
    host.qqGroupCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://qm.qq.com/q/C3IryUWCQw")))
    host.bilibiliCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://space.bilibili.com/3706960664857075")))
    host.aboutCard.clicked.connect(lambda: checkUpdate(host.window))
    return host.finish("about")
