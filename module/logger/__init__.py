from module.config import cfg
from utils.logger.logger import Logger

log = Logger(cfg.get_value('log_level'), cfg.get_value('log_retention_days', 30))
log.hr('欢迎使用 March7th Assistant\nhttps://github.com/moesnow/March7thAssistant\n\n此程序为免费开源项目 如果你付了钱请立刻退款', 0, False)
