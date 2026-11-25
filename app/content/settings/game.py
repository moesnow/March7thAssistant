from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import PushSettingCard, MessageBox
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.rangesettingcard1 import RangeSettingCard1
from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
from module.config import cfg
from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.localization import tr
import sys
from app.content.keys import build_keys


def build(host):
    def choose_launcher_path():
        launcher_path, _ = QFileDialog.getOpenFileName(
            host.card_parent,
            tr("选择启动器路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not launcher_path or cfg.launcher_path == launcher_path:
            return
        cfg.set_value("launcher_path", launcher_path)
        host.launcherPathCard.setContent(launcher_path)

    def confirm_graphics(enabled):
        if not enabled:
            return True
        confirm = MessageBox(
            tr("启用临时降低画质前请确认"),
            tr("此功能仅在执行任务时，由助手启动 Windows 本地游戏才生效；云游戏和已经运行的游戏不会调整。\n\n"
               "目前仅支持已知版本的自定义画质，请先在游戏内将图像质量设为自定义并保存。不会降低帧率、渲染比例或修改抗锯齿。\n\n"
               "任务结束会恢复原有配置，但运行中的游戏不会立即恢复画面，重启游戏后才会应用原画质。助手不会为此自动重启游戏。\n\n"
               "异常退出的备份会在下次启动助手时尝试恢复；如果检测到其它来源修改了设置，将保留备份并提示，避免覆盖你的新配置。"),
            host.window,
        )
        confirm.yesButton.setText(tr("我已了解，继续开启"))
        confirm.cancelButton.setText(tr("取消"))
        add_mascot(confirm, Mascot.SERIOUS)
        return bool(confirm.exec())

    host.startGameTimeoutCard = RangeSettingCard1(
        "start_game_timeout",
        [10, 60],
        UiIcon.CLOCK,
        tr("启动游戏超时时间（分）"),
        "",
        parent=host.card_parent,
    )
    host.refreshHourEnableCard = RangeSettingCard1(
        "refresh_hour",
        [0, 23],
        FIF.DATE_TIME,
        tr("游戏刷新时间"),
        tr("用于判断游戏每日刷新及任务状态，默认凌晨四点"),
        parent=host.card_parent,
    )
    host.updateViaLauncherEnableCard = ExpandableSwitchSettingCard(
        "update_via_launcher",
        FIF.UPDATE,
        tr('通过启动器更新游戏'),
        "",
        parent=host.card_parent,
    )
    host.launcherPathCard = PushSettingCard(
        tr('修改'),
        FIF.GAME,
        tr("启动器路径"),
        cfg.launcher_path,
        parent=host.card_parent,
    )
    host.launcherType = ComboBoxSettingCard2(
        "launcher_title_name",
        FIF.GAME,
        tr('启动器类型'),
        '',
        texts={tr('米哈游启动器'): '米哈游启动器', tr('HoYoPlay'): 'HoYoPlay'},
        parent=host.card_parent,
    )
    host.updateGameTimeoutCard = RangeSettingCard1(
        "update_game_timeout",
        [1, 24],
        UiIcon.CLOCK,
        tr("更新游戏超时时间（时）"),
        "",
        parent=host.card_parent,
    )
    host.autoSetResolutionEnableCard = SwitchSettingCard1(
        FIF.FULL_SCREEN,
        tr('启用自动修改分辨率并关闭自动 HDR'),
        tr("通过软件启动游戏会自动修改 1920x1080 分辨率并关闭自动 HDR，不影响手动启动游戏（支持国服和国际服）"),
        "auto_set_resolution_enable",
        parent=host.card_parent,
    )
    host.autoLowerGraphicsCard = SwitchSettingCard1(
        FIF.SPEED_HIGH,
        tr("任务期间自动降低画质"),
        tr("默认关闭，仅调整助手启动的 Windows 本地游戏；恢复的画质在重启游戏后生效"),
        "auto_lower_graphics_enable",
        confirm=confirm_graphics,
        parent=host.card_parent,
    )
    host.gameOptimizationCard = SwitchSettingCard1(
        FIF.GAME, tr("启用游戏优化"),
        tr("控制自动战斗检测及本地游戏的分辨率与画质调整"),
        "game_optimization_enable",
        parent=host.card_parent,
    )
    host.autoBattleDetectEnableCard = SwitchSettingCard1(
        FIF.ROBOT,
        tr('启用自动战斗和二倍速检测'),
        tr("战斗时检测并补开自动战斗和二倍速"),
        "auto_battle_detect_enable",
        parent=host.card_parent,
    )
    def refresh_game_optimization_options(*_args):
        enabled = host.gameOptimizationCard.switchButton.isChecked()
        host.autoBattleDetectEnableCard.setEnabled(enabled)
        host.autoSetResolutionEnableCard.setEnabled(enabled)
        host.autoLowerGraphicsCard.setEnabled(enabled and sys.platform == 'win32')
    host.gameOptimizationCard.switchButton.checkedChanged.connect(refresh_game_optimization_options)
    refresh_game_optimization_options()
    host.launcherPathCard.clicked.connect(choose_launcher_path)
    build_keys(host, "game")
    def refresh_options():
        refresh_game_optimization_options()
        host.refresh_detected_keys(host.auto_detect_game_hotkeys_enableCard.switchButton.isChecked())

    host.refresh_options = refresh_options
    return host.finish("game", (
        ("updateViaLauncherEnableCard", ('launcherPathCard', 'launcherType', 'updateGameTimeoutCard')),
    ))
