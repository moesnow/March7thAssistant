from PySide6.QtWidgets import QFileDialog
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox
from app.common.icon import UiIcon
from app.card.comboboxsettingcard2 import ComboBoxSettingCard2
from app.card.switchsettingcard1 import SwitchSettingCard1
from app.card.game_path_setting_card import GamePathSettingCard
from app.card.adb_setting_cards import AdbDeviceCard, AdbEnvironmentCard, AdbStatusCard, AdbAdvancedCard
from app.card.rangesettingcard1 import RangeSettingCard1
from app.card.pushsettingcard1 import PushSettingCardEval
from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard, ExpandableComboBoxSettingCard
from module.config import cfg
from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.localization import tr
from app.content.backend import block_while_running


def build(host):
    def choose_game_path():
        game_path, _ = QFileDialog.getOpenFileName(
            host.card_parent,
            tr("选择游戏路径"),
            "",
            tr("脚本或可执行文件 (*.exe *.bat *.cmd *.ps1)")
        )
        if not game_path or cfg.game_path == game_path:
            return
        cfg.set_value("game_path", game_path)
        host.gamePathCard.setContent(game_path)

    def confirm_local_mode(value):
        """切换到后台模式前说明限制；确认后才写入配置，取消则保留原模式。"""
        if value != 'background':
            return True
        confirm = MessageBox(
            tr("启用后台模式前请确认"),
            tr("后台模式下，任务运行时你可以继续使用电脑，但仍有以下限制：\n\n"
               "• 点击和拖动会短暂借用鼠标，完成后归还；你正在移动鼠标时，任务会等鼠标停下再操作。\n"
               "• 在大世界中按键时，光标会被短暂锁定在游戏窗口中央。\n"
               "• 游戏窗口可以放在其他窗口后面，但不能最小化；运行期间请保持系统解锁。\n"
               "• 锄大地、第三方模拟宇宙等独立程序不受此设置影响，仍需前台运行。\n\n"
               "设置在下次启动任务时生效，自动对话需重新开启。完整说明见使用文档“后台运行”。"),
            host.window
        )
        confirm.yesButton.setText(tr("我已了解，启用后台模式"))
        confirm.cancelButton.setText(tr("取消"))
        add_mascot(confirm, Mascot.SERIOUS)
        return bool(confirm.exec())

    host.gamePathCard = GamePathSettingCard(parent=host.card_parent)
    host.autoSetGamePathEnableCard = SwitchSettingCard1(
        FIF.GAME,
        tr('启用自动配置游戏路径'),
        tr("通过快捷方式、官方启动器、运行中的游戏进程等方式尝试自动配置游戏路径（支持国服和国际服）"),
        "auto_set_game_path_enable",
        parent=host.card_parent,
    )
    host.useBackgroundScreenshotCard = SwitchSettingCard1(
        FIF.CAMERA,
        tr('优先使用后台截图'),
        tr("默认开启，可以避免悬浮窗等干扰"),
        "use_background_screenshot",
        parent=host.card_parent,
    )
    host.localControlModeCard = ExpandableComboBoxSettingCard(
        'local_control_mode', FIF.GAME, tr('本地操作模式'),
        tr('后台操作遇到鼠标干扰时会等待并重试；下次启动任务生效。'),
        texts={tr('前台'): 'foreground', tr('后台'): 'background'},
        confirm=confirm_local_mode,
        parent=host.card_parent,
    )
    host.backgroundMouseProtectionCard = SwitchSettingCard1(
        FIF.GAME, tr('重试失败时短暂锁定鼠标'),
        tr('仅保护必要的鼠标操作，保留键盘和暂停热键。'),
        'background_mouse_protection',
        parent=host.card_parent,
    )
    host.browserTypeCard = ExpandableComboBoxSettingCard(
        "browser_type",
        FIF.GLOBE,
        tr("浏览器类型"),
        tr("建议保持默认的“集成（Chrome For Testing）”效果最好"),
        {tr("集成（Chrome For Testing）"): "integrated", tr("Chrome"): "chrome", tr("Edge"): "edge"},
        parent=host.card_parent,
    )
    host.browserDownloadUseMirrorCard = SwitchSettingCard1(
        FIF.CLOUD_DOWNLOAD,
        tr("使用国内镜像下载浏览器和驱动"),
        None,
        "browser_download_use_mirror",
        parent=host.card_parent,
    )
    host.browserPersistentCard = SwitchSettingCard1(
        FIF.DOWNLOAD,
        tr("保存浏览器数据（游戏的登录状态和本地数据）"),
        None,
        "browser_persistent_enable",
        parent=host.card_parent,
    )
    host.browserScaleCard = ComboBoxSettingCard2(
        "browser_scale_factor",
        FIF.ZOOM,
        tr("浏览器画面缩放（DPI）"),
        tr("非 1920x1080 屏幕下，云游戏画面无法铺满屏幕，可以调整这个值改变画面缩放"),
        texts={'50%': 0.5, '67%': 0.67, '75%': 0.75, '80%': 0.80, '90%': 0.90, tr('无缩放（100%）'): 1.0,
               '110%': 1.10, '125%': 1.25, '150%': 1.5, '175%': 1.75, '200%': 2.0},
        parent=host.card_parent,
    )
    host.browserLaunchArgCard = PushSettingCardEval(
        tr("修改"),
        FIF.CODE,
        tr("浏览器启动参数"),
        "browser_launch_argument",
        parent=host.card_parent,
    )
    host.cloudGameFullScreenCard = SwitchSettingCard1(
        FIF.FULL_SCREEN,
        tr("全屏运行"),
        None,
        "cloud_game_fullscreen_enable",
        parent=host.card_parent,
    )
    host.cloudGameUsePaidTimeCard = SwitchSettingCard1(
        FIF.SHOPPING_CART,
        tr("使用付费时长"),
        tr("打开后可在使用云游戏时使用付费时长免除排队"),
        "cloud_game_use_paid_time",
        parent=host.card_parent,
    )
    host.browserHeadlessCard = ExpandableSwitchSettingCard(
        "browser_headless_enable",
        UiIcon.EYE_OFF,
        tr("启用无窗口模式（后台运行）"),
        tr("不支持模拟宇宙和锄大地"),
        parent=host.card_parent,
    )
    host.browserHeadlessRestartCard = SwitchSettingCard1(
        FIF.SYNC,
        tr("未登录时自动切换为有窗口模式"),
        tr("开启后：在无窗口模式检测到未登录时，将自动以有窗口模式重启浏览器以便登录；关闭后：将在无窗口模式下尝试二维码登录。"),
        "browser_headless_restart_on_not_logged_in",
        parent=host.card_parent,
    )
    host.cloudGameMaxQueueTimeCard = RangeSettingCard1(
        "cloud_game_max_queue_time",
        [1, 120],
        UiIcon.HOURGLASS,
        tr("最大排队等待时间（分钟）"),
        '',
        parent=host.card_parent,
    )
    host.cloudGameLoginTimeoutCard = RangeSettingCard1(
        "cloud_game_login_timeout",
        [1, 120],
        UiIcon.CLOCK,
        tr("登录超时时间（分钟）"),
        tr("等待用户完成登录的最长时间，超时后将终止运行"),
        parent=host.card_parent,
    )
    host.adbDeviceCard = AdbDeviceCard(parent=host.card_parent)
    host.adbEnvironmentCard = AdbEnvironmentCard(blocker=lambda: block_while_running(host.window, tr("环境检查会占用设备，请等任务结束后再检查")), parent=host.card_parent)
    host.adbStatusCard = AdbStatusCard(parent=host.card_parent)
    host.adbAdvancedCard = AdbAdvancedCard(parent=host.card_parent)
    def refresh_mouse_protection_option(*_args):
        host.backgroundMouseProtectionCard.setEnabled(cfg.get_value('local_control_mode') == 'background')
    host.localControlModeCard.currentIndexChanged.connect(refresh_mouse_protection_option)
    host.refresh_mouse_option = refresh_mouse_protection_option
    refresh_mouse_protection_option()
    host.gamePathCard.clicked.connect(choose_game_path)
    host.adbDeviceCard.serialChanged.connect(lambda _serial: host.adbAdvancedCard.refreshSerial())
    host.adbAdvancedCard.serialChanged.connect(host.adbDeviceCard.setSelectedSerial)
    return host.finish("run_mode", (
        ("localControlModeCard", ('backgroundMouseProtectionCard',)),
        ("browserTypeCard", ('browserDownloadUseMirrorCard', 'browserPersistentCard', 'browserScaleCard', 'browserLaunchArgCard')),
        ("browserHeadlessCard", ('browserHeadlessRestartCard',)),
    ))
