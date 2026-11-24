from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import PushSettingCard
from app.common.icon import UiIcon
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.expandable_switch_setting_card import ExpandableComboBoxSettingCard
from module.config import cfg
from module.localization import tr


def build(host):
    def choose_script():
        script_path, _ = QFileDialog.getOpenFileName(
            host.card_parent,
            tr("脚本或程序路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not script_path or cfg.script_path == script_path:
            return
        cfg.set_value("script_path", script_path)
        host.ScriptPathCard.setContent(script_path)

    host.pauseAfterSuccess = SwitchSettingCard1(
        FIF.SYNC,
        tr('成功后暂停程序'),
        tr("如果勾选，除非循环模式，执行成功后暂停程序。"),
        "pause_after_success",
        parent=host.card_parent,
    )
    host.exitAfterFailure = SwitchSettingCard1(
        FIF.SYNC,
        tr('失败后直接退出'),
        tr("如果勾选，那么失败后直接退出，否则失败后暂停程序。"),
        "exit_after_failure",
        parent=host.card_parent,
    )
    host.afterFinishCard = ExpandableComboBoxSettingCard(
        "after_finish",
        FIF.POWER_BUTTON,
        tr('任务完成后'),
        tr('“退出”会关闭游戏。需要定时运行时，请打开「运行」页的「定时计划」。'),
        texts={tr('无'): 'None', tr('退出'): 'Exit', tr('关机'): 'Shutdown', tr('睡眠'): 'Sleep', tr('休眠'): 'Hibernate', tr('重启'): 'Restart', tr('注销'): 'Logoff', tr('关闭显示器'): 'TurnOffDisplay', tr('运行脚本'): 'RunScript', tr('循环'): 'Loop'},
        parent=host.card_parent,
    )
    host.ScriptPathCard = PushSettingCard(
        tr('修改'),
        FIF.CODE,
        tr("脚本或程序路径(选择运行脚本时生效)"),
        cfg.script_path,
        parent=host.card_parent,
    )
    host.exitAppAfterSuccess = SwitchSettingCard1(
        FIF.POWER_BUTTON,
        tr('任务全部成功后关闭助手'),
        tr('任务链全部成功后延迟 5 秒关闭，可与退出游戏组合。\n启用按时任务或等待完成后操作时保持运行。'),
        "exit_app_after_success",
        parent=host.card_parent,
    )
    host.playAudioCard = SwitchSettingCard1(
        UiIcon.SPEAKER,
        tr('声音提示'),
        tr('任务完成后列车长唱歌提示帕！'),
        "play_audio",
        parent=host.card_parent,
    )
    host.ScriptPathCard.clicked.connect(choose_script)
    return host.finish("after_run", (
        ("afterFinishCard", ('ScriptPathCard',)),
    ))
