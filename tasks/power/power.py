from module.screen import screen
from module.automation import auto
from module.logger import log
from module.config import cfg
from module.ocr import ocr
from tasks.power.instance import Instance, CalyxInstance
from tasks.weekly.universe import Universe
import time
import json

class Power:
    @staticmethod
    def run():
        """
        主入口，自动根据配置选择体力消耗方式（饰品提取、拟造花萼或常规副本）。
        """
        Power.preprocess()

        #
        #添加对配置文件的分析，若有必要，扫描培养计划并制定临时计划
        #
        #Power.getplan()

        instance_type = cfg.instance_type
        instance_name = cfg.instance_names[cfg.instance_type]
        max_calyx_per_round_num_of_attempts = cfg.max_calyx_per_round_num_of_attempts

        if not Instance.validate_instance(instance_type, instance_name):
            return False

        log.hr("开始清体力", 0)

        if "饰品提取" in instance_type:
            power = Power.get()
            Power.process_ornament(instance_type, instance_name, power)
        elif "拟造花萼" in instance_type:
            Power.process_calyx(instance_type, instance_name, max_calyx_per_round_num_of_attempts)
        else:
            power = Power.get()
            Power.process_standard(instance_type, instance_name, power)

        log.hr("完成", 2)

    @staticmethod
    def preprocess():
        """
        预处理操作，优先合成沉浸器（如配置开启）。
        """
        # 优先合成沉浸器
        if cfg.merge_immersifier:
            Power.merge("immersifier")

    @staticmethod
    def process_ornament(instance_type, instance_name, power):
        """
        处理饰品提取副本的体力消耗流程，包括检测存档和沉浸器数量。
        """
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
    def process_calyx(instance_type, instance_name, max_calyx_per_round_num_of_attempts):
        """
        处理拟造花萼副本的体力消耗流程，自动分批消耗体力。
        """
        # 处理拟造花萼的体力消耗
        instance_power_min = 10
        if (max_calyx_per_round_num_of_attempts >= 1 and max_calyx_per_round_num_of_attempts <= 6):
            instance_power_max = max_calyx_per_round_num_of_attempts * 10
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
        """
        处理常规副本（如凝滞虚影、侵蚀隧洞、历战余响）的体力消耗流程。
        """
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
    #     """
    #     自定义副本运行流程（已注释）。
    #     """
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
        """
        获取当前开拓力值，并根据配置自动补充体力（后备开拓力或燃料）。
        """
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
        """
        合成沉浸器，自动判断数量与体力是否足够。
        """
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
    def wait_until(condition, timeout, period=1):
        """等待直到条件满足或超时"""
        end_time = time.time() + timeout
        while time.time() < end_time:
            if condition():
                return True
            time.sleep(period)
        return False

    def _get_instance_names():
        if not Power.wait_until(lambda: not auto.find_element("培养目标", "text", max_retries=1, crop=(280 / 1920, 280 / 1080, 460 / 1920, 360 / 1080)), 10):
            log.error("未找到材料详细界面")
            return None, None
        auto.mouse_move(960, 540)
        auto.mouse_scroll(12, -1)
        # 等待界面完全停止
        time.sleep(1)
        screenshot, _, _ = auto.take_screenshot()
        result = ocr.recognize_multi_lines(screenshot)
        if not result:
            auto.click_element_with_pos(coordinates=((1800, 580), (1800, 580)))
            time.sleep(1)
            return None, None
        with open("./assets/config/instance_names.json", 'r', encoding='utf-8') as file:
            template = json.load(file)
        '''if instance_name in template[instance_type]:
            instance_name = template[instance_type][instance_name]'''
        #遍历template的instance_name中每个元素以及instance_name本身，检查是否被包含在result中。template格式为[instance_type][instance_name]，若是则返回instance_type和instance_name，否则持续循环
        for instance_type in template:
            for instance_name in template[instance_type]:
                if instance_name != '无' and (any(instance_name in box[1][0] for box in result) or any(template[instance_type][instance_name] in box[1][0] for box in result)):
                    log.debug(f"找到实例: {instance_type} - {instance_name}")
                    auto.click_element_with_pos(coordinates=((1800, 580), (1800, 580)))
                    time.sleep(1)
                    return instance_type, instance_name
            if any(instance_type in box[1][0] for box in result):
                log.debug(f"找到实例: {instance_type} - 无")
                if auto.click_element(instance_type, "text", max_retries=10, include=True):
                    Power.wait_until(lambda: auto.find_element("介绍", "text", max_retries=1), 30)
                    screenshot, _, _ = auto.take_screenshot()
                    result = ocr.recognize_multi_lines(screenshot)
                    for instance_name in template[instance_type]:
                        if instance_name != '无' and (any(instance_name in box[1][0] for box in result) or any(template[instance_type][instance_name] in box[1][0] for box in result)):
                            log.debug(f"找到实例: {instance_type} - {instance_name}")
                            auto.press_key('esc')
                            time.sleep(1)
                            auto.click_element_with_pos(coordinates=((1800, 580), (1800, 580)))
                            time.sleep(1)
                            return instance_type, instance_name
                    else:
                        log.warning(f"查询失败")
                        auto.press_key('esc')
                        time.sleep(1)
                else:
                    log.warning(f"未找到 {instance_type} 对应资源")
        else:
            log.warning("未找到实例")
        auto.click_element_with_pos(coordinates=((1800, 580), (1800, 580)))
        time.sleep(1)
        return None, None
        #return [box[1][0] for box in result if len(box[1][0]) >= 4]
    
    
    def get_all_transfer_positions(crop=(0, 0, 1, 1)):
        """
        截图并获取所有“传送”文本的坐标。
        返回: [(top_left, bottom_right), ...]
        """
        auto.take_screenshot(crop)
        auto.perform_ocr()
        positions = []
        for box, (text, confidence) in auto.ocr_result:
            if "进入" in text:
                (left, top), (right, bottom) = auto.calculate_text_position(box, relative=False)
                
                positions.append(((left-790, top), (right-790, bottom)))
        log.debug(f"找到 {len(positions)} 个材料位置: {positions}")
        return positions
        #找到 3 个传送位置: [((1532, 444), (1582, 476)), ((1532, 579), (1582, 611)), ((1532, 714), (1582, 746))]
        #crop=(726.0 / 1920, 419.0 / 1080, 84.0 / 1920, 86.0 / 1080)#1532 - 742 = 790
    @staticmethod
    def getplan():
        log.hr("正在动态分配任务")
        
        screen.change_to("guide3")
        if not auto.click_element("培养目标", "text", max_retries=10, crop=(280 / 1920, 280 / 1080, 460 / 1920, 360 / 1080)):
            log.error("找不到培养目标")
            return
                
        

        time.sleep(2)
        all_ned = []
        log.info("存在培养目标")
        positions = Power.get_all_transfer_positions()
        #print(cfg.instance_type, cfg.instance_names)
        for i in positions:
            #如果元素的坐标为((100, 200), (150, 250))，偏移量为(10, -5)，则返回(125, 245)
            #auto.click_element_with_pos(coordinates=((760 / 1920, i / 1080), (760 / 1920, i / 1080)))
            auto.click_element_with_pos(coordinates=i)
            time.sleep(2.5)
            instance_type, instance_name = Power._get_instance_names()
            if instance_type and instance_name:
                log.info(f"开始覆盖配置 {instance_type} 为 {instance_name}")
                #cfg.instance_type = instance_type
                #cfg.set_value('instance_names', instance_type, instance_name)
                #cfg.instance_names[cfg.instance_type] = instance_name
                cfg.config['instance_names'][instance_type] = instance_name
                #cfg.save_config()
                #print('\n',cfg.instance_names[cfg.instance_type])
                #print(cfg.instance_type, cfg.instance_names,'\n')
                if(instance_type != '历战余响'):
                    all_ned.append(instance_type)
                
                #print(cfg.config)
        log.info(f"开始覆盖配置 饰品提取 为 饰品提取")
        cfg.config['instance_names']['饰品提取'] = '饰品提取'
        cfg.save_config()
        #cfg.set_value('instance_names', '饰品提取', '饰品提取')
        if all_ned != []:
                    all_ned.append('饰品提取')
                    #cfg.instance_type = all_ned[0]
                    cfg.set_value('instance_type', all_ned[0])
                    if cfg.instance_type == '侵蚀隧洞' and cfg.plan_face_mode == '饰品提取':
                        #cfg.instance_type = '饰品提取'
                        cfg.set_value('instance_type', '饰品提取')

                    log.debug(f"已在{all_ned}中设置实例类型: {cfg.instance_type}")
        #print(cfg.instance_type, cfg.instance_names)
        
        log.hr("完成", 2)
        
            
            