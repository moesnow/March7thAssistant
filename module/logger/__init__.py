from module.config import cfg
from utils.logger.logger import Logger

log = Logger(cfg.get_value('log_level'), cfg.get_value('log_retention_days', 30))

# app.py 在导入日志之前就加载界面语言，补写这段时间里的翻译目录提示。
from module.localization import flush_catalog_notices  # noqa: E402

flush_catalog_notices()
