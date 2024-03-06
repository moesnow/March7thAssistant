from module.automation import Automation
from managers.config import config
from managers.logger import logger

auto = Automation(config.get_value('game_title_name'), logger)
