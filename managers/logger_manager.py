from module.logger.logger import Logger
from managers.config_manager import config
from managers.translate_manager import _
import base64

logger = Logger(config.get_value('log_level')).get_logger()
logger.hr(_("{bCqCXzkKOEEZHJEc2CEg} {p6LqXENrR1AWA9rVW6mH}\n{mPxo756ANmcTn55VL89U}{s8osWU36ynHUQ9BnSsf3}").format(p6LqXENrR1AWA9rVW6mH=base64.b64decode("TWFyY2g3dGggQXNzaXN0YW50").decode("utf-8"),mPxo756ANmcTn55VL89U=base64.b64decode("aHR0cHM6Ly9naXRodWIuY29tL21vZXNub3cvTWFyY2g3dGhBc3Npc3RhbnQ=").decode("utf-8"),bCqCXzkKOEEZHJEc2CEg=base64.b64decode("5qyi6L+O5L2/55So" if config.get_value('locales') == "zh_CN" else "V2VsY29tZSB0byB1c2U=").decode("utf-8"),s8osWU36ynHUQ9BnSsf3=base64.b64decode("CgrmraTnqIvluo/kuLrlhY3otLnlvIDmupDpobnnm64g5aaC5p6c5L2g5LuY5LqG6ZKx6K+356uL5Yi76YCA5qy+" if config.get_value('locales') == "zh_CN" else "").decode("utf-8")),0)
