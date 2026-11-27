from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import InfoBar, InfoBarPosition, PushSettingCard
from app.common.icon import BrandIcon
from app.pages.about import AboutHeader
from module.config import cfg
from module.docs.support import QQ_GROUP_URL
from module.localization import tr
from app.tools.check_update import checkUpdate
from app.tools.agent_prompt import build_agent_prompt
from utils import clipboard


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

    def prompt_description(name):
        return tr("复制一段提示词发给 DeepSeek Harness、Codex、Claude Code 等 AI 助手，让它学会操作{name}").format(name=name)

    host.aboutCard = AboutHeader(cfg.version, host.card_parent)
    host.agentPromptCard = PushSettingCard(
        tr('复制提示词'),
        FIF.ROBOT,
        tr('AI 助手'),
        prompt_description(host.aboutCard.titleLabel.text()),
        parent=host.card_parent,
    )
    host.aboutCard.nameChanged.connect(lambda name: host.agentPromptCard.setContent(prompt_description(name)))
    host.bilibiliCard = PushSettingCard(
        tr('立即前往'),
        BrandIcon.BILIBILI,
        tr('哔哩哔哩'),
        tr('欢迎关注我们的B站账号，获取最新动态和教程'),
        parent=host.card_parent,
    )
    host.qqGroupCard = PushSettingCard(
        tr('加入群聊'),
        BrandIcon.QQ,
        tr('QQ群'),
        "",
        parent=host.card_parent,
    )
    host.aboutCard.homeClicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/moesnow/March7thAssistant")))
    host.aboutCard.changelogClicked.connect(lambda: host.window.navigate("doc:Changelog"))
    host.agentPromptCard.clicked.connect(copy_prompt)
    host.qqGroupCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(QQ_GROUP_URL)))
    host.bilibiliCard.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://space.bilibili.com/3706960664857075")))
    host.aboutCard.updateClicked.connect(lambda: checkUpdate(host.window))
    return host.finish("about")
