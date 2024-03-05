from module.automation import Automation
from managers.config_manager import config
from managers.logger_manager import logger

auto = Automation(config.get_value('game_title_name'), logger)
