from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import PrimaryPushSettingCard
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.pushsettingcard1 import PushSettingCardNotifyTemplate
from module.notification import init_notifiers
from module.localization import tr
from tasks.base.tasks import start_task


def build(host):
    host.notifyMasterEnableCard = SwitchSettingCard1(
        FIF.RINGER, tr("启用消息推送"), tr("消息推送总开关"), "notification_enable",
        parent=host.card_parent,
    )
    host.testNotifyCard = PrimaryPushSettingCard(
        tr("发送消息"),
        FIF.SEND,
        tr("测试消息推送"),
        "",
        parent=host.card_parent,
    )
    host.notifyLevelCard = ComboBoxSettingCard2(
        "notify_level",
        UiIcon.FILTER,
        tr('通知级别'),
        '',
        texts={tr('推送所有通知'): 'all', tr('仅推送错误通知'): 'error'},
        parent=host.card_parent,
    )
    host.notifyMergeCard = SwitchSettingCard1(
        UiIcon.MERGE,
        tr('通知合并'),
        tr('开启后，完整运行结束时将所有通知合并为一条发送'),
        "notify_merge",
        parent=host.card_parent,
    )
    host.notifyImageEnableCard = SwitchSettingCard1(
        FIF.CAMERA,
        tr('推送图片'),
        tr('关闭后推送消息时不再发送截图'),
        "notify_send_images",
        parent=host.card_parent,
    )
    host.notifyTemplateCard = PushSettingCardNotifyTemplate(
        tr('修改'),
        FIF.FONT_SIZE,
        tr("消息推送格式"),
        "notify_template",
        parent=host.card_parent,
    )
    def refresh_notifiers(*_):
        init_notifiers()
    host.notifyMasterEnableCard.switchButton.checkedChanged.connect(refresh_notifiers)
    host.testNotifyCard.clicked.connect(lambda: start_task("notify"))
    return host.finish("notify")
