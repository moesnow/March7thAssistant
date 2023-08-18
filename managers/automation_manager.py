from module.automation.automation import Automation
from managers.config_manager import config

auto = Automation(config.get_value('game_title_name'))
