from module.translate.translate import Translate
from managers.config_manager import config

translate = Translate(config.get_value('locales'))
_ = translate.gettext
