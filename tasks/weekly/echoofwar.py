from datetime import date

from module.config import cfg
from module.overview.plan import echo_day_due
from module.logger import log
from tasks.daily.buildtarget import BuildTarget
from tasks.power.policy import ECHO
from tasks.power.power import Power


class Echoofwar:
    @staticmethod
    def start(*, support=None):
        if not echo_day_due(cfg, date.today()):
            log.info(f"历战余响设为周{cfg.echo_of_war_start_day_of_week}开始，跳过本次")
            return True
        target = BuildTarget.get_target_echo_instance() if cfg.build_target_enable else None
        name = target[1] if target else cfg.instance_names.get(ECHO)
        Power.process(ECHO, name, support=support)
        return True
