import time

from module.automation import auto
from module.logger import log
from .receipt import RewardError, close_item_reward, confirm_item_reward
from .rewardtemplate import RewardTemplate


RECEIVE_CROP = (1194 / 1920, 866 / 1080, 610 / 1920, 156 / 1080)
STATUS_CROP = (1180 / 1920, 355 / 1080, 671 / 1920, 670 / 1080)
DISPATCH_RUNNING = ("委托正在进行中", "委托派遣中，每小时可持续获得奖励帕！")
DISPATCH_STATUS = ("委托正在进行中", "委托派遣中", "每小时可持续获得奖励", "未派遣")


class Dispatch(RewardTemplate):
    def run(self):
        # 标题可能先于内容出现，慢速机器需要留出委托面板加载时间。
        auto.find_element("专属材料", "text", max_retries=10,
                          crop=(163 / 1920, 99 / 1080, 1115 / 1920, 118 / 1080))
        for attempt in range(10):
            button = auto.find_element("领取奖励", "text", crop=RECEIVE_CROP)
            if button:
                if not auto.click_element_with_pos(button):
                    raise RewardError("无法点击委托的领取奖励按钮")
                confirm_item_reward("委托奖励")
                close_item_reward()
                return True
            if auto.find_element(DISPATCH_RUNNING, "text", include=True, take_screenshot=False, need_ocr=False):
                break
            if attempt < 9:
                time.sleep(1)
        else:
            if not auto.find_element(DISPATCH_STATUS, "text", include=True, crop=STATUS_CROP, max_retries=3):
                raise RewardError("未确认委托奖励状态")

        log.info("委托暂无可领取奖励")
        return False
