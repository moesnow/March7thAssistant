from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox
from app.common.icon import UiIcon
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.pushsettingcard1 import PushSettingCardMirrorchyan, PushSettingCardStr
from app.card.expandable_switch_setting_card import ExpandableComboBoxSettingCardUpdateSource
from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.localization import tr


def build(host):
    host._ignoreCheckUpdateCardSwitchChanged = False
    def confirm_updates(isChecked: bool):
        if host._ignoreCheckUpdateCardSwitchChanged:
            host._ignoreCheckUpdateCardSwitchChanged = False
            return

        if isChecked:
            return

        confirm = MessageBox(
            tr("关闭更新检测前请确认"),
            tr("仍然建议保留“启动时检测更新”。\n\n它不会在后台偷偷自动更新软件。开启后，仅会在你手动启动软件时检查一次更新，并在发现新版本后提醒你，不会自行安装，也不会影响循环运行。\n\n这类基于图像识别的工具对游戏界面变化非常敏感。游戏更新后，界面、按钮或布局只要发生变化，旧版本就更容易出现识别失败、流程异常等问题。\n\n很多看似“突然不能用了”的情况，本质上都是版本过旧导致的。若你已经了解这些影响，再继续关闭更新检测。"),
            host.window
        )
        confirm.yesButton.setText(tr("我已了解，继续关闭"))
        confirm.cancelButton.setText(tr("取消"))
        add_mascot(confirm, Mascot.SERIOUS)

        if confirm.exec():
            return

        host._ignoreCheckUpdateCardSwitchChanged = True
        host.checkUpdateCard.switchButton.setChecked(True)

    host.updateSourceCard = ExpandableComboBoxSettingCardUpdateSource(
        "update_source",
        UiIcon.CLOUD_SYNC,
        tr('更新源'),
        host.window,
        "",
        texts={tr('海外源'): 'GitHub', tr('Mirror 酱'): 'MirrorChyan'},
        secondary_configname="update_prerelease_enable",
        secondary_texts={tr('正式版'): False, tr('公测版'): True},
        parent=host.card_parent,
    )
    host.checkUpdateCard = SwitchSettingCard1(
        FIF.SYNC,
        tr('启动时检测更新'),
        "",
        "check_update",
        parent=host.card_parent,
    )
    host.updateFullEnableCard = SwitchSettingCard1(
        UiIcon.CLOUD_DOWNLOAD,
        tr('更新时下载完整包'),
        tr("更新将包含依赖组件，建议保持开启。若关闭此选项，需自行手动更新依赖组件，可能会导致出现不可预期的错误。"),
        "update_full_enable",
        parent=host.card_parent,
    )
    host.updateDownloadProxyCard = PushSettingCardStr(
        tr('修改'),
        FIF.GLOBE,
        tr("下载代理"),
        "update_download_proxy",
        empty_content=tr("留空则使用系统代理；支持 http:// 和 socks5://"),
        parent=host.card_parent,
    )
    host.githubTokenCard = PushSettingCardStr(
        tr('修改'),
        UiIcon.KEY,
        tr('GitHub Token'),
        'github_token',
        password=True,
        parent=host.card_parent,
    )
    host.mirrorchyanCdkCard = PushSettingCardMirrorchyan(
        tr('修改'),
        UiIcon.KEY,
        tr("Mirror 酱 CDK"),
        host.updateSourceCard,
        "mirrorchyan_cdk",
        parent=host.card_parent,
    )
    host.checkUpdateCard.switchButton.checkedChanged.connect(confirm_updates)
    return host.finish("update", (
        ("updateSourceCard", ('checkUpdateCard', 'updateFullEnableCard', 'updateDownloadProxyCard', 'githubTokenCard')),
    ))
