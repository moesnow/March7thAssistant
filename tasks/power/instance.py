from managers.screen_manager import screen
from managers.automation_manager import auto
from managers.logger_manager import logger
from managers.config_manager import config
from managers.translate_manager import _
from tasks.base.base import Base
from tasks.base.team import Team
from tasks.power.character import Character
import time


class Instance:
    @staticmethod
    def run(instance_type, instance_name, power_need, runs):
        if not Instance.validate_instance(instance_type, instance_name):
            return False

        logger.hr(_("开始刷{type} - {name}，总计{number}次").format(
            type=instance_type, name=instance_name, number=runs), 2)

        instance_name = Instance.process_instance_name(instance_name)

        if config.instance_team_enable:
            Team.change_to(config.instance_team_number)

        if not Instance.prepare_instance(instance_type, instance_name):
            return False

        if not Instance.start_instance(instance_type, power_need):
            return False

        for i in range(runs - 1):
            Instance.wait_fight(i + 1)
            Instance.start_instance_again(instance_type)
        Instance.wait_fight(runs)

        Instance.complete_run()

        logger.info(_("副本任务完成"))
        return True

    @staticmethod
    def validate_instance(instance_type, instance_name):
        if instance_name == "无":
            logger.info(_("{type}未开启").format(type=instance_type))
            return False
        return True

    @staticmethod
    def prepare_instance(instance_type, instance_name):
        screen.change_to('guide3')
        instance_type_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)
        if not auto.click_element(instance_type, "text", crop=instance_type_crop):
            if auto.click_element("侵蚀隧洞", "text", max_retries=10, crop=instance_type_crop):
                auto.mouse_scroll(12, -1)
                # 等待界面完全停止
                time.sleep(1)
                auto.click_element(instance_type, "text", crop=instance_type_crop)
        # 等待界面切换
        time.sleep(1)

        # 传送
        instance_name_crop = (686.0 / 1920, 287.0 / 1080, 980.0 / 1920, 650.0 / 1080)
        if "拟造花萼（金）" in instance_type:
            auto.click_element(f"./assets/images/share/calyx/golden/{config.calyx_golden_preference}.png", "image")
            # 等待界面切换
            time.sleep(1)
        auto.click_element("./assets/images/screen/guide/power.png", "image", max_retries=10)

        Flag = False
        if "拟造花萼（赤）" in instance_type:
            crimson_images = {
                "毁灭之蕾": "./assets/images/share/calyx/crimson/destruction1.png",
                "存护之蕾": "./assets/images/share/calyx/crimson/preservation1.png",
                "巡猎之蕾": "./assets/images/share/calyx/crimson/hunt1.png",
                "丰饶之蕾": "./assets/images/share/calyx/crimson/abundance1.png",
                "智识之蕾": "./assets/images/share/calyx/crimson/erudition1.png",
                "同谐之蕾": "./assets/images/share/calyx/crimson/harmony1.png",
                "虚无之蕾": "./assets/images/share/calyx/crimson/nihility1.png",
                "毁灭之蕾2": "./assets/images/share/calyx/crimson/destruction2.png",
                "虚无之蕾2": "./assets/images/share/calyx/crimson/nihility2.png",
                "同谐之蕾2": "./assets/images/share/calyx/crimson/harmony2.png",
            }
            def func(): return auto.click_element(("传送", "进入", "追踪"), "min_distance_text", crop=instance_name_crop, include=True, source=crimson_images[instance_name], source_type="image")
        else:
            def func(): return auto.click_element(("传送", "进入", "追踪"), "min_distance_text", crop=instance_name_crop, include=True, source=instance_name, source_type="text")

        for i in range(6):
            if func():
                Flag = True
                break
            auto.mouse_scroll(18, -1)
            # 等待界面完全停止
            time.sleep(1)
        if not Flag:
            Base.send_notification_with_screenshot(_("⚠️刷副本未完成 - 没有找到指定副本名称⚠️"))
            return False
        # 验证传送是否成功
        if not auto.find_element(instance_name.replace("2", ""), "text", max_retries=60, include=True, crop=(1172.0 / 1920, 5.0 / 1080, 742.0 / 1920, 636.0 / 1080)):
            Base.send_notification_with_screenshot(_("⚠️刷副本未完成 - 传送可能失败⚠️"))
            return False

        return True

    @staticmethod
    def start_instance(instance_type, power_need):
        if "拟造花萼" in instance_type:
            count = power_need // 10 - 1
            if not 0 <= count <= 5:
                Base.send_notification_with_screenshot(_("⚠️刷副本未完成 - 拟造花萼次数错误⚠️"))
                return False
            result = auto.find_element("./assets/images/screen/guide/plus.png", "image", 0.9, max_retries=10,
                                       crop=(1174.0 / 1920, 775.0 / 1080, 738.0 / 1920, 174.0 / 1080))
            for i in range(count):
                auto.click_element_with_pos(result)
                time.sleep(0.5)
            # time.sleep(1)

        if auto.click_element("挑战", "text", max_retries=10, need_ocr=True):
            if instance_type == "历战余响":
                time.sleep(1)
                auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)

            Character.borrow()

            if auto.click_element("开始挑战", "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                if instance_type == "凝滞虚影":
                    time.sleep(2)
                    for i in range(3):
                        auto.press_mouse()

                return True

        return False

    @staticmethod
    def start_instance_again(instance_type):
        auto.click_element("./assets/images/zh_CN/fight/fight_again.png", "image", 0.9, max_retries=10)
        if instance_type == "历战余响":
            time.sleep(1)
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)

    @staticmethod
    def complete_run():
        # 速度太快，点击按钮无效
        time.sleep(1)
        auto.click_element("./assets/images/zh_CN/fight/fight_exit.png", "image", 0.9, max_retries=10)
        time.sleep(2)

    @staticmethod
    def process_instance_name(instance_name):
        replacements = {
            "巽风之形": "风之形",
            "翼风之形": "风之形",
            "偃偶之形": "偶之形",
            "孽兽之形": "兽之形",
            "燔灼之形": "灼之形",
            "潘灼之形": "灼之形",
            "熠灼之形": "灼之形",
            "蛀星的旧靥": "蛀星的旧"
        }

        for key, value in replacements.items():
            instance_name = instance_name.replace(key, value)

        return instance_name

    @staticmethod
    def wait_fight(num):
        logger.info(_("进入战斗"))
        time.sleep(2)
        # for i in range(20):
        #     if auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.95, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
        #         logger.info(_("尝试开启自动战斗"))
        #         auto.press_key("v")
        #     elif auto.find_element("./assets/images/zh_CN/base/auto.png", "image", 0.95, take_screenshot=False):
        #         logger.info(_("自动战斗已开启"))
        #         break
        #     time.sleep(0.5)
        # logger.info(_("等待战斗"))

        def check_fight():
            if auto.find_element("./assets/images/zh_CN/fight/fight_again.png", "image", 0.9):
                return True

            elif config.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.95, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
                logger.info(_("尝试开启自动战斗"))
                auto.press_key("v")

            return False

        if not auto.retry_with_timeout(lambda: check_fight(), 30 * 60, 1):
            logger.error(_("战斗超时"))
            raise Exception(_("战斗超时"))

        logger.info(_("战斗完成"))
        logger.info(_("第{num}次副本完成").format(num=num))
