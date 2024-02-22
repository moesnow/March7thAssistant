from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.translate_manager import _
from tasks.base.base import Base
from .rewardtemplate import RewardTemplate
import time


class SRPass(RewardTemplate):
    def run(self):
        if auto.click_element("./assets/images/zh_CN/reward/pass/one_key_receive.png", "image", 0.9):
            # 等待可能出现的升级动画
            time.sleep(2)

        # 判断是否解锁了"无名客的荣勋"
        screen.change_to('pass1')
        if auto.find_element("./assets/images/share/reward/pass/lock.png", "image", 0.9):
            # 若没解锁则领取奖励
            if auto.click_element("./assets/images/zh_CN/reward/pass/one_key_receive.png", "image", 0.9):
                auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10)

        # 判断是否满级
        if auto.find_element("./assets/images/share/reward/pass/50.png", "image", 0.9):
            Base.send_notification_with_screenshot(_("🎉当前版本无名勋礼已满级🎉"))
