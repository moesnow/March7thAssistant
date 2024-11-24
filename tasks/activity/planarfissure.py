from tasks.power.power import Power
from .doubleactivity import DoubleActivity


class PlanarFissure(DoubleActivity):
    def _run_instances(self, reward_count):
        # 暂未支持自动刷取模拟宇宙领取奖励
        Power.merge("immersifier")

        return True
