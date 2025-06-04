from module.screen import screen
from module.automation import auto
from module.logger import log
from module.config import cfg
from tasks.power.instance import Instance, CalyxInstance
from tasks.weekly.universe import Universe
import time


class Power:
    @staticmethod
    def run():
        Power.preprocess()

        instance_type = cfg.instance_type
        instance_name = cfg.instance_names[cfg.instance_type]
        max_calyx_per_round_power = cfg.max_calyx_per_round_power

        if not Instance.validate_instance(instance_type, instance_name):
            return False

        log.hr("开始清体力", 0)

        if "饰品提取" in instance_type:
            power = Power.get()
            Power.process_ornament(instance_type, instance_name, power)
        elif "拟造花萼" in instance_type:
            Power.process_calyx(instance_type, instance_name, max_calyx_per_round_power)
        else:
            power = Power.get()
            Power.process_standard(instance_type, instance_name, power)

        log.hr("完成", 2)

    @staticmethod
    def preprocess():
        # 优先合成沉浸器
        if cfg.merge_immersifier:
            Power.merge("immersifier")

    @staticmethod
    def process_ornament(instance_type, instance_name, power):
        full_runs = power // 40

        screen.change_to('guide3')
        instance_type_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)

        if "饰品提取" in instance_type:
            auto.click_element(instance_type, "text", crop=instance_type_crop)
            # 等待界面完全停止
            time.sleep(1)

            # 需要判断是否有可用存档
            if auto.find_element("无可用存档", "text", crop=(688.0 / 1920, 289.0 / 1080, 972.0 / 1920, 369.0 / 1080), include=True):
                # 刷差分宇宙存档
                if Universe.start(nums=1, save=False, category="divergent"):
                    # 验证存档
                    screen.change_to('guide3')
                    auto.click_element(instance_type, "text", crop=instance_type_crop)
                    # 等待界面完全停止
                    time.sleep(1)
                    if auto.find_element("无可用存档", "text", crop=(688.0 / 1920, 289.0 / 1080, 972.0 / 1920, 369.0 / 1080), include=True):
                        log.error("暂无可用存档")
                        return
                else:
                    return

        screen.change_to("guide3")

        immersifier_crop = (1623.0 / 1920, 40.0 / 1080, 162.0 / 1920, 52.0 / 1080)
        text = auto.get_single_line_text(crop=immersifier_crop, blacklist=['+', '米'], max_retries=3)
        if "/12" not in text:
            log.error("沉浸器数量识别失败")
            return

        immersifier_count = int(text.split("/")[0])
        log.info(f"🟣沉浸器: {immersifier_count}/12")

        if immersifier_count + full_runs > 0:
            Instance.run(instance_type, instance_name, 40, immersifier_count + full_runs)

    @staticmethod
    def process_calyx(instance_type, instance_name, max_calyx_per_round_power):
        # 处理拟造花萼的体力消耗
        instance_power_min = 10
        if (max_calyx_per_round_power % 10 == 0 and max_calyx_per_round_power >= 10 and max_calyx_per_round_power <= 60):
            instance_power_max = max_calyx_per_round_power
        else:
            instance_power_max = 60
        while True:
            power = Power.get()

            if power < instance_power_min:
                log.info(f"🟣开拓力 < {instance_power_min}")
                break

            full_runs = power // instance_power_max
            if full_runs >= 1:
                result = CalyxInstance.run(instance_type, instance_name, instance_power_max, full_runs)
                if result == "Failed":
                    continue

            remain_runs = (power % instance_power_max) // instance_power_min
            if remain_runs >= 1:
                result = CalyxInstance.run(instance_type, instance_name, remain_runs * instance_power_min, 1)
                if result == "Failed":
                    continue
            break

    @staticmethod
    def process_standard(instance_type, instance_name, power):
        instance_powers = {
            "凝滞虚影": 30,
            "侵蚀隧洞": 40,
            "历战余响": 30
        }
        instance_power = instance_powers[instance_type]

        full_runs = power // instance_power
        if full_runs:
            Instance.run(instance_type, instance_name, instance_power, full_runs)
        else:
            log.info(f"🟣开拓力 < {instance_power}")

    # @staticmethod
    # def customize_run(instance_type, instance_name, power_need, runs):
    #     if not Instance.validate_instance(instance_type, instance_name):
    #         return False

    #     log.hr(f"准备{instance_type}", 2)

    #     power = Power.get()

    #     if power < power_need * runs:
    #         log.info(f"🟣开拓力 < {power_need}*{runs}")
    #         return False
    #     elif "拟造花萼" in instance_type:
    #         return CalyxInstance.run(instance_type, instance_name, power_need * runs)
    #     else:
    #         return Instance.run(instance_type, instance_name, power_need, runs)

    @staticmethod
    def get():
        def get_power(crop, type="trailblaze_power"):
            try:
                if type == "trailblaze_power":
                    result = auto.get_single_line_text(
                        crop=crop, blacklist=['+', '米', '*'], max_retries=3)
                    power = int(result.replace("1300", "/300").replace("?", "").split('/')[0])
                    return power if 0 <= power <= 999 else 0
                elif type == "reserved_trailblaze_power":
                    result = auto.get_single_line_text(
                        crop=crop, blacklist=['+', '米'], max_retries=3)
                    power = int(result[0])
                    return power if 0 <= power <= 2400 else 0
            except Exception as e:
                log.error(f"识别开拓力失败: {e}")
                return 0

        def move_button_and_confirm():
            if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                result = auto.find_element(
                    "./assets/images/share/power/trailblaze_power/button.png", "image", 0.9, max_retries=10)
                if result:
                    auto.click_element_with_pos(result, action="down")
                    time.sleep(0.5)
                    result = auto.find_element(
                        "./assets/images/share/power/trailblaze_power/plus.png", "image", 0.9)
                    if result:
                        auto.click_element_with_pos(result, action="move")
                        time.sleep(0.5)
                        auto.mouse_up()
                        if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                            time.sleep(1)
                            auto.press_key("esc")
                            if screen.check_screen("map"):
                                return True
            return False

        trailblaze_power_crop = (1588.0 / 1920, 35.0 / 1080, 198.0 / 1920, 56.0 / 1080)

        if cfg.use_reserved_trailblaze_power or cfg.use_fuel:
            screen.change_to('map')
            # 打开开拓力补充界面
            if auto.click_element("./assets/images/share/power/trailblaze_power/trailblaze_power.png", "image", 0.9, crop=trailblaze_power_crop):
                # 等待界面加载
                if auto.find_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                    # 开启使用后备开拓力
                    if cfg.use_reserved_trailblaze_power and auto.click_element("./assets/images/share/power/trailblaze_power/reserved_trailblaze_power.png", "image", 0.9, scale_range=(0.95, 0.95)):
                        move_button_and_confirm()
                    # 开启使用燃料
                    elif cfg.use_fuel and auto.click_element("./assets/images/share/power/trailblaze_power/fuel.png", "image", 0.9, scale_range=(0.95, 0.95)):
                        move_button_and_confirm()
                    # # 开启使用星琼
                    # elif config.stellar_jade and auto.click_element("./assets/images/share/power/trailblaze_power/stellar_jade.png", "image", 0.9, scale_range=(0.95, 0.95)):
                    #     pass
                    else:
                        auto.press_key("esc")

        screen.change_to('map')
        trailblaze_power = get_power(trailblaze_power_crop)

        log.info(f"🟣开拓力: {trailblaze_power}/300")
        return trailblaze_power

    @staticmethod
    def merge(type, cnt=0):
        if type == "immersifier":
            log.hr("准备合成沉浸器", 2)
            screen.change_to("menu")

            if cnt == 0:
                limit = int(cfg.merge_immersifier_limit)
            else:
                limit = cnt

            screen.change_to("guide3")

            immersifier_crop = (1623.0 / 1920, 40.0 / 1080, 162.0 / 1920, 52.0 / 1080)
            text = auto.get_single_line_text(crop=immersifier_crop, blacklist=[
                '+', '米'], max_retries=3)
            if "/12" not in text:
                log.error("沉浸器数量识别失败")
                return

            immersifier_count = int(text.split("/")[0])
            log.info(f"🟣沉浸器: {immersifier_count}/12")
            if immersifier_count >= limit:
                log.info("沉浸器已达到上限")
                return

            screen.change_to("guide3")
            power = Power.get()

            count = min(power // 40, limit - immersifier_count)
            if count <= 0:
                log.info("体力不足")
                return

            log.hr(f"准备合成 {count} 个沉浸器", 2)
            screen.change_to("guide3")

            if auto.click_element("./assets/images/share/power/immersifier/immersifier.png", "image", 0.9, crop=immersifier_crop):
                time.sleep(1)
                for i in range(count - 1):
                    auto.click_element(
                        "./assets/images/share/power/trailblaze_power/plus.png", "image", 0.9)
                    time.sleep(0.5)
                if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                    time.sleep(1)
                    auto.press_key("esc")
