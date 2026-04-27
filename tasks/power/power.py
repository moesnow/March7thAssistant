from module.screen import screen
from module.automation import auto
from module.logger import log
from module.config import cfg
from tasks.power.instance import Instance
from tasks.daily.buildtarget import BuildTarget
import time


class Power:
    @staticmethod
    def run():
        Power.preprocess()

        # 优先执行体力计划
        Power.execute_power_plan()

        log.hr("开始清体力", 0)

        instance_type = cfg.instance_type
        instance_name = cfg.instance_names[instance_type]

        try:
            if cfg.build_target_enable and (target := BuildTarget.get_target_instance()):
                instance_type, instance_name = target
                log.info(f"使用培养目标副本: {instance_type} - {instance_name}")
        except Exception as e:
            log.error(f"获取培养目标副本失败: {e}")

        if not Instance.validate_instance(instance_type, instance_name):
            log.hr("完成", 2)
            return False

        Power.process(instance_type, instance_name)

        log.hr("完成", 2)

    @staticmethod
    def execute_power_plan():
        """执行体力计划"""
        power_plan = cfg.get_value("power_plan", [])
        if not power_plan:
            return False

        log.hr("开始执行体力计划", 0)

        # 副本体力消耗配置
        instances_power = {
            "拟造花萼（金）": 10,
            "拟造花萼（赤）": 10,
            "凝滞虚影": 30,
            "侵蚀隧洞": 40,
            "历战余响": 30,
            "饰品提取": 40
        }

        # 执行计划
        updated_plan = []
        has_executed = False

        for i, plan in enumerate(power_plan):
            if len(plan) != 3:
                log.warning(f"体力计划格式错误，跳过: {plan}")
                continue

            instance_type, instance_name, count = plan

            # 验证副本
            if not Instance.validate_instance(instance_type, instance_name):
                log.warning(f"副本验证失败: {instance_type} - {instance_name}，保留该计划")
                updated_plan.append(plan)
                continue

            log.info(f"执行体力计划 [{i + 1}/{len(power_plan)}]: {instance_type} - {instance_name}, 计划次数: {count}")

            try:
                # 执行副本
                executed_count = Power.process(instance_type, instance_name, planned_attempts = count)

                if executed_count > 0:
                    has_executed = True
                    # 更新剩余次数
                    remaining_count = count - executed_count
                    if remaining_count > 0:
                        updated_plan.append([instance_type, instance_name, remaining_count])
                        log.info(f"体力计划剩余: {instance_type} - {instance_name}, 剩余次数: {remaining_count}")
                    else:
                        log.info(f"体力计划已完成: {instance_type} - {instance_name}")
                else:
                    # 体力不足或执行失败，保留该计划及后续所有计划
                    log.info(f"无法执行: {instance_type} - {instance_name}，保留该计划")
                    for j in range(i, len(power_plan)):
                        remaining_plan = power_plan[j]
                        if len(remaining_plan) == 3:
                            updated_plan.append(remaining_plan)
                    break

            except Exception as e:
                log.error(f"执行体力计划时出错: {e}，保留该计划")
                updated_plan.append(plan)

        # 保存更新后的计划
        cfg.set_value("power_plan", updated_plan)

        if has_executed:
            log.info(f"体力计划执行完成，剩余计划数: {len(updated_plan)}")
        else:
            log.info("体力不足，无法执行任何体力计划")
            log.hr("完成", 2)
            return False

        log.hr("完成", 2)
        return True

    @staticmethod
    def preprocess():
        # 优先合成沉浸器
        if cfg.merge_immersifier:
            Power.merge("immersifier")

    @staticmethod
    def process(instance_type: str, instance_name: str, planned_attempts: int = 0, immersifier_only: bool = False):
        instances_power = {
            "拟造花萼（金）": 10,
            "拟造花萼（赤）": 10,
            "凝滞虚影": 30,
            "侵蚀隧洞": 40,
            "饰品提取": 40,
            "历战余响": 30
        }
        attempts_per_run_max = {
            "拟造花萼（金）": 24,
            "拟造花萼（赤）": 24,
            "凝滞虚影": 8,
            "侵蚀隧洞": 6,
            "饰品提取": 6,
            "历战余响": 3
        }
        instance_power_min = instances_power[instance_type]
        attempts_per_run = cfg.instance_names_challenge_count[instance_type]
        if not 0 < attempts_per_run <= attempts_per_run_max[instance_type]:
            attempts_per_run = attempts_per_run_max[instance_type]
            log.warning(f"{instance_type} 挑战次数设置错误，已自动调整为 {attempts_per_run}")
        
        
        executed_attempts = 0
        failed_runs = 0
        FAILED_LIMIT = 3
        while failed_runs < FAILED_LIMIT:
            
            
            
            if "饰品提取" in instance_type:
                
                # 进入“生存索引”界面后，（经个人测试）默认优先处于“培养目标”/“饰品提取”标签，都可获取沉浸器数量，无需切换。如果因此产生bug则取消此段注释
                # screen.change_to('guide3')
                # instance_type_crop = (262.0 / 1920, 289.0 / 1080, 422.0 / 1920, 624.0 / 1080)

                # auto.click_element(instance_type, "text", crop=instance_type_crop)
                # # 等待界面完全停止
                # time.sleep(1)

                # immersifier_crop = (1623.0 / 1920, 40.0 / 1080, 162.0 / 1920, 52.0 / 1080)
                # text = auto.get_single_line_text(crop=immersifier_crop, blacklist=['+', '米'], max_retries=3)
                # if "/12" not in text:
                #     log.error("沉浸器数量识别失败")
                #     return True

                immersifier_count = Power.get_immersifier_count()
                if immersifier_only:
                    attempts = immersifier_count
                    log.info(f"只使用沉浸器进行 {attempts} 次挑战")
                else:
                    power = Power.get()
                    attempts = power // instance_power_min
                    attempts += immersifier_count
                    log.info(f"开拓力: {power} + 沉浸器: {immersifier_count} = {attempts} 次挑战")
            else:
                power = Power.get()
                attempts = power // instance_power_min
                log.info(f"开拓力: {power} = {attempts} 次挑战")
                
            if attempts == 0:
                log.info(f"开拓力 < {instance_power_min}")
                break
            
            if planned_attempts - executed_attempts > 0:
                attempts = min(attempts, planned_attempts - executed_attempts)
                log.info(f"剩余计划挑战次数: {planned_attempts - executed_attempts}，实际可挑战次数调整为: {attempts}")
            elif planned_attempts > 0:
                    log.info(f"该计划挑战次数已完成")
                    break
            else:
                log.info(f"未设置计划挑战次数，按照当前开拓力可挑战次数: {attempts}")

            
            full_runs = attempts // attempts_per_run
            if full_runs >= 1:
                result = Instance.run(instance_type, instance_name, attempts_per_run, full_runs)
                if result == True:
                    executed_attempts += full_runs * attempts_per_run
                else:
                    failed_runs += 1
                    log.error(f"检测到该次副本未正常运行，重试：{failed_runs}/{FAILED_LIMIT}")
                    continue

            remain_attempts = attempts % attempts_per_run
            if remain_attempts >= 1:
                result = Instance.run(instance_type, instance_name, remain_attempts, 1)
                if result == True:
                    executed_attempts += remain_attempts
                else:
                    failed_runs += 1
                    log.error(f"检测到该次副本未正常运行，重试：{failed_runs}/{FAILED_LIMIT}")
                    continue
            break
        return executed_attempts
    
    @staticmethod
    def get_immersifier_count():
        screen.change_to('guide3')
        immersifier_crop = (1623.0 / 1920, 40.0 / 1080, 162.0 / 1920, 52.0 / 1080)
        text = auto.get_single_line_text(crop=immersifier_crop, blacklist=['+', '米'], max_retries=3)
        if "/12" not in text:
            log.error("沉浸器数量识别失败")
            return 0

        immersifier_count = int(text.split("/")[0])
        log.info(f"沉浸器: {immersifier_count}/12")
        return immersifier_count
    
    
    @staticmethod
    def get(use_supplement=True):
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
                result = auto.find_element("./assets/images/share/power/trailblaze_power/button.png", "image", 0.9, max_retries=10)
                if result:
                    auto.click_element_with_pos(result, action="down")
                    time.sleep(0.5)
                    result = auto.find_element("./assets/images/share/power/trailblaze_power/plus.png", "image", 0.9)
                    if result:
                        auto.click_element_with_pos(result, action="move")
                        time.sleep(0.5)
                        auto.mouse_up()
                        if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                            time.sleep(1)
                            auto.press_key("esc")
                            if screen.check_screen("map"):
                                return True
                    else:
                        auto.mouse_up()
                else:
                    auto.mouse_up()
            return False

        trailblaze_power_crop = (1588.0 / 1920, 35.0 / 1080, 198.0 / 1920, 56.0 / 1080)

        if use_supplement and (cfg.use_reserved_trailblaze_power or cfg.use_fuel):
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

        log.info(f"开拓力: {trailblaze_power}/300")
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
            log.info(f"沉浸器: {immersifier_count}/12")
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
