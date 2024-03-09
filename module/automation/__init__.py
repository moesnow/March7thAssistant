from module.automation.automation import Automation
from module.config import cfg
from module.logger import log

auto = Automation(cfg.get_value('game_title_name'), log)
