from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import FluentIcon as FIF
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import (
    ComboBoxSettingCard2,
    ComboBoxSettingCardLanguage,
    ComboBoxSettingCardTheme,
)
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.pushsettingcard1 import DualPushSettingCard
from module.config import cfg
from module.localization import tr
from module.localization.languages import AUTO_LANGUAGE, available_languages
from module.overview.cards import background_path


def build(host):
    def choose_background():
        path, _ = QFileDialog.getOpenFileName(host.card_parent, tr('选择图片'), '', 'Images (*.png *.jpg *.jpeg *.webp *.bmp)')
        if path:
            set_background(path)

    def set_background(path):
        cfg.set_value('banner_path', path)
        host.overviewBackgroundCard.setContent(path or tr('星轨背景'))

    host.overviewBackgroundCard = DualPushSettingCard(
        tr('选择图片'), tr('恢复默认'), FIF.PHOTO, tr('问候区背景图'),
        background_path(cfg) or tr('星轨背景'),
        parent=host.card_parent,
    )
    host.overviewMascotCard = SwitchSettingCard1(
        UiIcon.PERSON, tr('显示 Q 版小人'), None, 'overview_show_mascot',
        parent=host.card_parent,
    )
    host.themeCard = ComboBoxSettingCardTheme(host.window)
    host.themeCard.setParent(host.card_parent)
    host.closeWindowActionCard = ComboBoxSettingCard2(
        "close_window_action",
        FIF.CLOSE,
        tr('关闭窗口时'),
        tr('选择关闭窗口时的默认行为，也可以在关闭时由对话框询问'),
        texts={tr('询问'): 'ask', tr('最小化到托盘'): 'minimize', tr('关闭程序'): 'close'},
        parent=host.card_parent,
    )
    host.windowMemoryCard = ComboBoxSettingCard2(
        "window_memory",
        FIF.LAYOUT,
        tr('窗口记忆'),
        tr('选择启动时恢复的窗口状态'),
        texts={tr('记忆窗口大小'): 'size', tr('记忆窗口位置'): 'position', tr('记忆窗口大小和位置'): 'size_and_position', tr('都不记忆'): 'none'},
        parent=host.card_parent,
    )
    host.languageCard = ComboBoxSettingCardLanguage(
        "ui_language",
        FIF.LANGUAGE,
        '界面语言 / 界面語言 / 日本語 / 인터페이스 언어 / UI Language',
        '切换后即时生效 / 切換後即時生效 / 切り替え後すぐ適用 / 변경 즉시 적용 / Takes effect immediately',
        texts={tr('自动'): AUTO_LANGUAGE, **available_languages()},
        parent=host.card_parent,
    )
    host.overviewBackgroundCard.leftClicked.connect(choose_background)
    host.overviewBackgroundCard.rightClicked.connect(lambda: set_background(''))
    return host.finish("appearance")
