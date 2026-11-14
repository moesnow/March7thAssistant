from module.config import cfg
from utils.logger.logger import Logger

log = Logger(cfg.get_value('log_level'), cfg.get_value('log_retention_days', 30))
