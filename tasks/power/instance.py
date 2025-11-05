from module.screen import screen
from module.automation import auto
from module.logger import log
from module.config import cfg
from tasks.base.base import Base
from tasks.base.team import Team
from .character import Character
from .relicset import Relicset
import time
import json


class Instance:
    @staticmethod
    def run(instance_type, instance_name, power_need, runs, from_failure=False, runs_completed=0):
        if not Instance.validate_instance(instance_type, instance_name):
            return False

        # 若是任务失败后的重新运行, 则改变运行逻辑
        if from_failure:
            log.hr(f"复活后重新进入副本{instance_type} - {instance_name}，剩余{runs - runs_completed}轮", 2)
        else:
            if "拟造花萼" in instance_type or "凝滞虚影" in instance_type or "侵蚀隧洞" in instance_type:
                instances_power = {
                    "拟造花萼（金）": 10,
                    "拟造花萼（赤）": 10,
                    "凝滞虚影": 30,
                    "侵蚀隧洞": 40
                    # "历战余响": 30
                }
                instance_power_min = instances_power[instance_type]
                log.hr(f"开始刷{instance_type} - {instance_name}，总计{runs}轮，每轮包含{power_need // instance_power_min}次", 2)
            else:
                log.hr(f"开始刷{instance_type} - {instance_name}，总计{runs}轮", 2)

            if cfg.instance_team_enable and "饰品提取" not in instance_type:
                Team.change_to(cfg.instance_team_number)

        if not Instance.prepare_instance(instance_type, instance_name):
            return False

        if not Instance.start_instance(instance_type, power_need):
            return False

        try:
            for i in range(runs_completed, runs):
                fight_result = Instance.wait_fight(i + 1)

                # 如果战斗失败则重新运行, 并记录成功运行次数
                if not fight_result:
                    if "拟造花萼" in instance_type or "凝滞虚影" in instance_type or "侵蚀隧洞" in instance_type:
                        auto.click_element("./assets/images/zh_CN/fight/fight_fail.png", "image", 0.9, max_retries=10)
                        return "Failed"
                    else:
                        auto.click_element("./assets/images/zh_CN/fight/fight_fail.png", "image", 0.9, max_retries=10)
                        time.sleep(2)
                        Instance.run(instance_type, instance_name, power_need, runs, from_failure=True, runs_completed=i)
                        break

                if i < runs - 1:
                    Instance.start_instance_again(instance_type)
        except RuntimeError:
            return False

        # 若是任务失败后的重新运行, 则不再重复这些逻辑
        if not from_failure:
            Instance.complete_run(instance_type)
            log.info("副本任务完成")

        return True

    @staticmethod
    def validate_instance(instance_type, instance_name):
        if instance_name == "无":
            log.info(f"{instance_type}未开启")
            return False
        return True

    @staticmethod
    def prepare_instance(instance_type, instance_name):
        screen.change_to('guide3')
        time.sleep(1)

        instance_type_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)

        if not auto.click_element(instance_type, "text", crop=instance_type_crop):
            if auto.click_element("凝滞虚影", "text", max_retries=10, crop=instance_type_crop):
                auto.mouse_scroll(12, -1)
                # 等待界面完全停止
                time.sleep(1)
                auto.click_element(instance_type, "text", crop=instance_type_crop)
        # 等待界面切换
        time.sleep(1)

        # 传送
        instance_name_crop = (686.0 / 1920, 287.0 / 1080, 980.0 / 1920, 650.0 / 1080)
        # if "拟造花萼（金）" in instance_type:
        #     auto.click_element(f"./assets/images/share/calyx/golden/{cfg.calyx_golden_preference}.png", "image")
        #     # 等待界面切换
        #     time.sleep(1)
        auto.click_element("./assets/images/screen/guide/power.png", "image", max_retries=10)

        Flag = False
        # if "拟造花萼（赤）" in instance_type:
        #     crimson_images = {
        #         "毁灭之蕾": "./assets/images/share/calyx/crimson/destruction1.png",
        #         "存护之蕾": "./assets/images/share/calyx/crimson/preservation1.png",
        #         "巡猎之蕾": "./assets/images/share/calyx/crimson/hunt1.png",
        #         "丰饶之蕾": "./assets/images/share/calyx/crimson/abundance1.png",
        #         "智识之蕾": "./assets/images/share/calyx/crimson/erudition1.png",
        #         "同谐之蕾": "./assets/images/share/calyx/crimson/harmony1.png",
        #         "虚无之蕾": "./assets/images/share/calyx/crimson/nihility1.png",
        #         "毁灭之蕾2": "./assets/images/share/calyx/crimson/destruction2.png",
        #         "虚无之蕾2": "./assets/images/share/calyx/crimson/nihility2.png",
        #         "同谐之蕾2": "./assets/images/share/calyx/crimson/harmony2.png",
        #     }
        #     # 临时解决方案
        #     if instance_name in crimson_images:
        #         def func(): return auto.click_element(("传送", "进入", "追踪"), "min_distance_text", crop=instance_name_crop, include=True, source=crimson_images[instance_name], source_type="image")
        #     else:
        #         def func(): return auto.click_element(("传送", "进入", "追踪"), "min_distance_text", crop=instance_name_crop, include=True, source=instance_name, source_type="text")

        if "拟造花萼（赤）" in instance_type:
            def func(): return auto.click_element(("传送", "进入", "追踪"), "min_distance_text", crop=instance_name_crop, include=True, source=instance_name, source_type="text", position="top_right")
        else:
            def func(): return auto.click_element(("传送", "进入", "追踪"), "min_distance_text", crop=instance_name_crop, include=True, source=instance_name, source_type="text")

        for i in range(10):
            if func():
                if auto.matched_text == "追踪":
                    time.sleep(2)
                    Base.send_notification_with_screenshot(cfg.notify_template['InstanceNotCompleted'].format(error="指定副本未解锁"))
                    auto.press_key("esc")
                    auto.press_key("esc")
                    screen.wait_for_screen_change('guide3')
                    return False
                Flag = True
                # 临时解决方案
                if "拟造花萼（赤）" in instance_type:
                    with open("./assets/config/instance_names.json", 'r', encoding='utf-8') as file:
                        template = json.load(file)
                    if instance_name in template[instance_type]:
                        instance_name = template[instance_type][instance_name]
                break
            auto.mouse_scroll(12, -1)
            # 等待界面完全停止
            time.sleep(1)
        if not Flag:
            Base.send_notification_with_screenshot(cfg.notify_template['InstanceNotCompleted'].format(error="未找到指定副本"))
            return False
        # 验证传送是否成功
        if "饰品提取" in instance_type:
            if not auto.find_element(instance_name, "text", max_retries=120, include=True, crop=(591.0 / 1920, 98.0 / 1080, 594.0 / 1920, 393.0 / 1080)):
                Base.send_notification_with_screenshot(cfg.notify_template['InstanceNotCompleted'].format(error="传送可能失败"))
                return False
        else:
            if not auto.find_element(instance_name.replace("2", ""), "text", max_retries=120, include=True, crop=(1172.0 / 1920, 5.0 / 1080, 742.0 / 1920, 636.0 / 1080)):
                Base.send_notification_with_screenshot(cfg.notify_template['InstanceNotCompleted'].format(error="传送可能失败"))
                return False

        return True

    @staticmethod
    def start_instance(instance_type, power_need):

        if "饰品提取" in instance_type:
            time.sleep(1)

            # 选择角色
            # 待后续更新支持

            Character.borrow("ornament")

            if auto.click_element("开始挑战", "text", max_retries=10, crop=(1558.0 / 1920, 939.0 / 1080, 216.0 / 1920, 70.0 / 1080)):
                # 快速连续检测多次，增加捕获瞬间提示的概率
                time.sleep(0.5)

                # 判断点击开始挑战是否成功，可能因缺少角色或背包满导致失败
                if auto.find_element("仍有角色位空缺", "text", max_retries=1, crop=(481.0 / 1920, 361.0 / 1080, 955.0 / 1920, 356.0 / 1080), include=True):
                    auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                    time.sleep(0.5)

                # 检测遗器背包已满的提示
                for _ in range(5):  # 连续快速检测5次
                    if auto.find_element("背包内遗器持有数量已达上限", "text", max_retries=1, include=True, threshold=0.7):
                        log.info("检测到背包内遗器已满，准备进行分解")
                        auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                        time.sleep(0.5)
                        # 执行分解四星遗器的操作
                        Relicset.run()

                        # 简化的界面恢复逻辑
                        log.info("遗器分解完成")

                        # 直接回到指南界面，减少中间步骤
                        log.info("切换到指南界面")
                        screen.change_to('guide3', max_retries=3)
                        time.sleep(1)

                        # 重新准备副本并开始挑战
                        # 通过instance_type获取对应的副本名称
                        instance_name = Instance.get_current_instance_name(instance_type)
                        if Instance.prepare_instance(instance_type, instance_name):
                            return Instance.start_instance(instance_type, power_need)
                        return False
                    time.sleep(0.1)

                if auto.find_element("./assets/images/purefiction/prepare_fight.png", "image", 10000, max_retries=60, crop=(0 / 1920, 0 / 1080, 300.0 / 1920, 300.0 / 1080)):
                    time.sleep(1)

                    # 使用秘技
                    # 待后续更新支持

                    # 靠近怪物
                    auto.press_key("w", 3)
                    for _ in range(3):
                        auto.press_mouse()
                        time.sleep(1)
                    return True
                elif auto.find_element("开始挑战", "text", max_retries=1, crop=(1558.0 / 1920, 939.0 / 1080, 216.0 / 1920, 70.0 / 1080)):
                    Base.send_notification_with_screenshot(cfg.notify_template['InstanceNotCompleted'].format(error="无法开始挑战"))
                    auto.press_key("esc")
                    time.sleep(2)
                    auto.press_key("esc")
                    screen.wait_for_screen_change('main')
                    return False
        else:
            if "拟造花萼" in instance_type or "凝滞虚影" in instance_type or "侵蚀隧洞" in instance_type:
                # 选择挑战次数
                instances_power = {
                    "拟造花萼（金）": 10,
                    "拟造花萼（赤）": 10,
                    "凝滞虚影": 30,
                    "侵蚀隧洞": 40
                    # "历战余响": 30
                }
                # challenges_count_max = {
                #     "拟造花萼（金）": 24,
                #     "拟造花萼（赤）": 24,
                #     "凝滞虚影": 8,
                #     "侵蚀隧洞": 6
                #     # "历战余响": 3
                # }
                instance_power_min = instances_power[instance_type]
                # challenge_count_max = challenges_count_max[instance_type]
                count = power_need // instance_power_min - 1
                # if not 0 <= count <= challenge_count_max - 1:
                #     Base.send_notification_with_screenshot(cfg.notify_template['InstanceNotCompleted'].format(error="连续挑战次数错误"))
                #     return False
                result = auto.find_element("./assets/images/screen/guide/plus.png", "image", 0.8, max_retries=10, crop=(1174.0 / 1920, 775.0 / 1080, 738.0 / 1920, 174.0 / 1080))
                if result:
                    for i in range(count):
                        auto.click_element_with_pos(result)
                        time.sleep(0.5)
                time.sleep(1)

            if auto.click_element("挑战", "text", max_retries=10, need_ocr=True):
                if instance_type == "历战余响":
                    time.sleep(1)
                    auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)

                Character.borrow()

                if auto.click_element("开始挑战", "text", max_retries=10, crop=(1518 / 1920, 960 / 1080, 334 / 1920, 61 / 1080)):
                    # 检测遗器背包已满的提示
                    if "侵蚀隧洞" in instance_type or "历战余响" in instance_type:
                        for _ in range(5):  # 连续快速检测5次
                            if auto.find_element("背包内遗器持有数量已达上限", "text", max_retries=1, include=True, threshold=0.7):
                                log.info("检测到背包内遗器已满，准备进行分解")
                                auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                                time.sleep(0.5)
                                # 执行分解四星遗器的操作
                                Relicset.run()

                                # 简化的界面恢复逻辑
                                log.info("遗器分解完成")

                                log.info("切换到指南界面")
                                screen.change_to('guide3', max_retries=3)  # 增加重试次数
                                time.sleep(1)

                                # 重新准备副本并开始挑战
                                instance_name = Instance.get_current_instance_name(instance_type)
                                if Instance.prepare_instance(instance_type, instance_name):
                                    return Instance.start_instance(instance_type, power_need)
                                return False
                            time.sleep(0.1)

                    # 版本更新后不再需要开怪
                    # if instance_type == "凝滞虚影":
                    #     time.sleep(2)
                    #     for i in range(3):
                    #         auto.press_mouse()

                    return True

        return False

    @staticmethod
    def start_instance_again(instance_type):
        auto.click_element("./assets/images/zh_CN/fight/fight_again.png", "image", 0.9, max_retries=10)
        if instance_type == "历战余响":
            time.sleep(1)
            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)

    @staticmethod
    def complete_run(instance_type):
        # 速度太快，点击按钮无效
        time.sleep(1)
        auto.click_element("./assets/images/zh_CN/fight/fight_exit.png", "image", 0.9, max_retries=10)
        time.sleep(4)
        # 版本更新后挑战不需要传送，但要按一次esc返回主界面
        auto.press_key("esc")
        time.sleep(2)
        screen.wait_for_screen_change('main')
        # 从副本返回主界面后，按esc太快无效
        time.sleep(2)

        if ("侵蚀隧洞" in instance_type or "饰品提取" in instance_type or "历战余响" in instance_type) and cfg.break_down_level_four_relicset:
            Relicset.run()

    @staticmethod
    def wait_fight(num, timeout=1800):
        log.info("进入战斗")
        time.sleep(5)

        start_time = time.time()
        while time.time() - start_time < timeout:
            if auto.find_element("./assets/images/zh_CN/fight/fight_again.png", "image", 0.9):
                log.info("战斗完成")
                log.info(f"第{num}次副本完成")
                return True
            elif auto.find_element("./assets/images/zh_CN/fight/fight_fail.png", "image", 0.9):
                log.info("战斗失败")
                log.info(f"获取剩余体力并重新计算轮次")
                return False
            elif cfg.auto_battle_detect_enable and auto.find_element("./assets/images/share/base/not_auto.png", "image", 0.9, crop=(0.0 / 1920, 903.0 / 1080, 144.0 / 1920, 120.0 / 1080)):
                log.info("尝试开启自动战斗")
                auto.press_key("v")
            elif auto.find_element("已处于无法战斗状态", "text", max_retries=1, include=True, threshold=0.7):
                log.info("队伍中存在无法战斗的角色，尝试继续战斗。")
                auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
            # 检测遗器背包已满的提示
            # 每次战斗检测循环中进行多次快速检测
            for _ in range(3):
                if auto.find_element("背包内遗器持有数量已达上限", "text", max_retries=1, include=True, threshold=0.7):
                    log.info("检测到背包内遗器已满，准备进行分解")
                    auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9)
                    time.sleep(0.5)
                    # 执行分解四星遗器的操作
                    Relicset.run()

                    # 简化处理：直接返回失败允许重试
                    log.info("战斗中检测到遗器已满并完成分解，返回战斗失败状态")

                    # 直接返回失败，让上层逻辑处理重新开始战斗
                    return False

                time.sleep(0.1)

            time.sleep(2)

        log.error("战斗超时")
        raise RuntimeError("战斗超时")

    @staticmethod
    def get_current_instance_name(instance_type):
        """获取当前副本类型对应的副本名称"""
        if instance_type in cfg.instance_names:
            return cfg.instance_names[instance_type]
        return "默认副本"  # 如果找不到，返回默认值
