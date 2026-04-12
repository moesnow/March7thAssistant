from module.automation import auto
from .rewardtemplate import RewardTemplate
from module.logger import log
from module.notification.notification import NotificationLevel
from module.screen import screen
from tasks.base.base import Base
import time


class Message(RewardTemplate):
    _CHAT_OPTION_POS = [(980 / 1920, 720 / 1080), (1080 / 1920, 720 / 1080), (1190 / 1920, 720 / 1080)]

    _NOTIFY_LIST_CROP = (328 / 1920, 262 / 1080, 90 / 1920, 600 / 1080)
    _UNREAD_MESSAGE_MARK = "./assets/images/share/base/RedExclamationMark.png"
    _UNREAD_MESSAGE_ICON = "./assets/images/share/reward/message/unread_incoming_message_icon.png"

    _MAX_SCROLL_RETRIES = 4  # 滚动列表寻找未读消息的最大次数（列表到底时终止）
    _MAX_ERROR_RETRIES = 4  # 对话/领奖异常时的最大容错次数（连续失败时终止）
    _MAX_MSG_LIST_ROUNDS = 30  # 外层消息列表的最大尝试次数
    _MAX_DIALOG_ROUNDS = 30  # 单次对话的最大等待轮次

    def run(self):
        scroll_retries = self._MAX_SCROLL_RETRIES
        error_retries = self._MAX_ERROR_RETRIES
        message_counter = 0
        reward_counter = 0
        msg_icon_pos_crop = None

        for attempt in range(self._MAX_MSG_LIST_ROUNDS):

            # 终止检查
            if scroll_retries <= 0:
                log.info("消息列表已滚动至底部，未发现更多未读消息，流程结束")
                break
            if error_retries <= 0:
                log.info(f"异常重试次数已耗尽（{attempt} 次），终止流程")
                break

            # 返回消息列表
            if msg_icon_pos_crop is not None:
                if not auto.click_element(msg_icon_pos_crop, "crop"):
                    log.error("点击返回消息列表失败")
                    break
                msg_icon_pos_crop = None

            # 1. 在列表中寻找未读消息
            unread_msg_pos = auto.find_element(self._UNREAD_MESSAGE_MARK, "image", 0.8, max_retries=2, crop=self._NOTIFY_LIST_CROP) or auto.find_element(
                self._UNREAD_MESSAGE_ICON, "image", 0.8, max_retries=2, crop=self._NOTIFY_LIST_CROP
            )
            if not unread_msg_pos:
                log.info(f"未检测到未读消息，滚动列表继续查找（剩余 {scroll_retries} 次）")
                auto.mouse_scroll(16)
                scroll_retries -= 1
                continue

            # 2. 点击进入对话界面，并开始对话循环
            if not auto.click_element_with_pos(unread_msg_pos):
                log.error("点击进入对话界面失败")
                break

            # 根据未读消息的位置，计算图标局部裁剪区域，用于后续检测对话是否结束
            (left, top), (right, bottom) = unread_msg_pos
            w, h = right - left, bottom - top
            msg_icon_pos_crop = auto.calculate_crop_with_pos((left - 0.5 * w, top - 0.3 * h), (w * 2.0, h * 1.6))

            for dialog_attempt in range(self._MAX_DIALOG_ROUNDS):
                time.sleep(2)
                log.debug(f"正在进行对话，等待对话完成...（剩余 {self._MAX_DIALOG_ROUNDS - dialog_attempt} 轮）")
                for option_pos in self._CHAT_OPTION_POS:
                    if auto.find_element(self._UNREAD_MESSAGE_ICON, "image", 0.8, crop=msg_icon_pos_crop):
                        auto.click_element((option_pos[0], option_pos[1], 0, 0), "crop")
                    else:
                        break
                else:
                    continue
                message_counter += 1
                log.info("对话完成")
                break
            else:
                log.warning("对话超时，准备重试")
                error_retries -= 1
                continue

            # 3. 尝试领取奖励
            if auto.click_element(["空白", "关闭"], "text", include=True, max_retries=5, crop=(704 / 1920, 284 / 1080, 512 / 1920, 512 / 1080)):
                reward_counter += 1
                error_retries = self._MAX_ERROR_RETRIES
                log.info("成功领取一次对话奖励")
                time.sleep(2)
            else:
                log.warning("未检测到奖励，可能对话未完成或无奖励，继续处理")
                error_retries -= 1

        if message_counter or reward_counter:
            Base.send_notification_with_screenshot(
                f"完成短信奖励领取，共处理 {message_counter} 个短信，" f"成功领取了 {reward_counter} 次奖励",
                level=NotificationLevel.ALL,
            )
