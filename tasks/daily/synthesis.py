from module.config import cfg
from module.screen import screen
from module.automation import auto
from module.logger import log
import time


class Synthesis:

    @staticmethod
    def material():
        if cfg.daily_material_enable:
            try:
                log.hr("准备合成材料", 2)
                screen.change_to('material')
                # 筛选规则
                time.sleep(2)
                if auto.click_element("./assets/images/share/synthesis/filter.png", "image", 0.9, max_retries=10):
                    # 等待筛选界面弹出
                    time.sleep(2)
                    if auto.click_element("通用培养材料", "text", max_retries=10, crop=(478.0 / 1920, 350.0 / 1080, 981.0 / 1920, 399.0 / 1080)):
                        time.sleep(2)
                        if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                            time.sleep(2)
                            # 多次重试避免选中没反应
                            for _ in range(4):
                                auto.click_element("./assets/images/share/synthesis/nuclear.png", "image", 0.85, max_retries=10)
                                time.sleep(2)
                                if auto.find_element("./assets/images/share/synthesis/nuclear_selected.png", "image", 0.85, max_retries=10):
                                    if auto.click_element("./assets/images/zh_CN/synthesis/synthesis_button.png", "image", 0.9, max_retries=10):
                                        time.sleep(2)
                                        if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                                            time.sleep(2)
                                            if auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10):
                                                time.sleep(2)
                                                log.info("合成材料完成")
                                                return True
                                    break
                log.error("合成材料失败")
            except Exception as e:
                log.error(f"合成材料失败: {e}")
        return False

    @staticmethod
    def consumables():
        try:
            log.hr("准备合成消耗品", 2)
            screen.change_to('consumables')
            # 筛选规则
            if auto.click_element("./assets/images/share/synthesis/filter.png", "image", 0.9, max_retries=10):
                # 等待筛选界面弹出
                time.sleep(2)
                if auto.click_element("防御类消耗品", "text", max_retries=10, crop=(472.0 / 1920, 347.0 / 1080, 970.0 / 1920, 268.0 / 1080)):
                    if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                        time.sleep(2)
                        # 多次重试避免选中没反应
                        for _ in range(4):
                            auto.click_element("./assets/images/share/synthesis/defensive_medicine.png", "image", 0.8, max_retries=10)
                            if auto.find_element("./assets/images/share/synthesis/defensive_medicine_selected.png", "image", 0.8, max_retries=10):
                                if auto.click_element("./assets/images/zh_CN/synthesis/synthesis_button.png", "image", 0.9, max_retries=10):
                                    if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                                        if auto.click_element("./assets/images/zh_CN/base/click_close.png", "image", 0.8, max_retries=10):
                                            log.info("合成消耗品完成")
                                            return True
                                break
            log.error("合成消耗品失败")
        except Exception as e:
            log.error(f"合成消耗品失败: {e}")
        return False

    @staticmethod
    def use_consumables(recursion=True):
        try:
            log.hr("准备使用消耗品", 2)
            screen.change_to('bag_consumables')
            # 筛选规则
            if auto.click_element("./assets/images/share/synthesis/filter.png", "image", 0.9, max_retries=10):
                # 等待筛选界面弹出
                time.sleep(2)
                if auto.click_element("防御类消耗品", "text", max_retries=10, crop=(472.0 / 1920, 347.0 / 1080, 970.0 / 1920, 268.0 / 1080)):
                    if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                        time.sleep(2)
                        # 多次重试避免选中没反应
                        for _ in range(4):
                            if auto.click_element("./assets/images/share/synthesis/defensive_medicine.png", "image", 0.8, max_retries=10):
                                if auto.find_element("./assets/images/share/bag/defensive_medicine_selected.png", "image", 0.8, max_retries=10):
                                    if auto.click_element("./assets/images/zh_CN/base/use.png", "image", 0.9, max_retries=10):
                                        if auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=10):
                                            auto.click_element("./assets/images/zh_CN/base/confirm.png", "image", 0.9, max_retries=2)
                                            if auto.find_element("./assets/images/screen/bag/bag_consumables.png", "image", 0.9, max_retries=10):
                                                log.info("使用消耗品完成")
                                                return True
                                    break
                                continue
                            elif recursion:
                                log.info("没有可用的消耗品，尝试合成")
                                if Synthesis.consumables():
                                    return Synthesis.use_consumables(False)
                                else:
                                    break
                            else:
                                break
            log.error("使用消耗品失败")
        except Exception as e:
            log.error(f"使用消耗品失败: {e}")
        return False

    @staticmethod
    def lc3star_superimpose():
        try:
            log.hr("准备3星光锥自动叠加", 2)
            screen.change_to("bag_lc")
            log.info("点击排序按钮")
            if auto.click_element(
                "./assets/images/share/synthesis/filter.png",
                "image",
                0.9,
                offset=(150, 0),
            ):
                time.sleep(1)
                log.info("按稀有度排序")
                if auto.click_element(
                    "./assets/images/zh_CN/lc/rarity.png", "image", 0.9
                ):
                    log.info("升序排序光锥")
                    auto.click_element(
                        "./assets/images/share/synthesis/descend.png",
                        "image",
                        0.9,
                    )
                    log.hr("开始叠加3星光锥")
                    not_find_times = 0
                    while not_find_times < 5:
                        target_id = ["four", "three", "two", "one"]
                        find_target = False
                        for tid in target_id:
                            targets = auto.find_element(
                                f"./assets/images/share/lc/{tid}.png",
                                "image_with_multiple_targets",
                                0.82,
                            )
                            t = None
                            for tgt in targets:
                                log.info(f"检测到光锥位置: {tgt}")
                                auto.click_element_with_pos(tgt)
                                ((left, top), (right, bottom)) = tgt
                                left_new = left
                                top_new = bottom + 30
                                size = (80, 60)
                                crop_box = auto.calculate_crop_with_pos(
                                    (left_new, top_new), size
                                )

                                image_detail_three = auto.find_element(
                                    f"./assets/images/share/lc/three_rarity.png",
                                    "image",
                                    threshold=0.85,
                                    crop=crop_box,
                                )
                                image_detail_four = auto.find_element(
                                    f"./assets/images/share/lc/four_rarity.png",
                                    "image",
                                    threshold=0.85,
                                    crop=crop_box,
                                )

                                image_detail_five = auto.find_element(
                                    f"./assets/images/share/lc/five_rarity.png",
                                    "image",
                                    threshold=0.86,
                                    crop=crop_box,
                                )
                                log.info(
                                    f"光锥详情检测结果: 3星:{image_detail_three}, 4星:{image_detail_four}, 5星:{image_detail_five}"
                                )
                                if image_detail_four or image_detail_five:
                                    log.info("跳过4星、5星光锥")
                                    continue
                                if image_detail_three:
                                    t = tgt
                                    break

                            if t is not None:
                                find_target = True
                                log.info(f"找到3星光锥位置: {t}")
                                auto.click_element_with_pos(t)
                                if auto.click_element(
                                    "./assets/images/zh_CN/lc/detail.png",
                                    "image",
                                    0.9,
                                ):
                                    time.sleep(3)
                                    if auto.click_element(
                                        "./assets/images/share/lc/superimpose.png",
                                        "image",
                                        0.9,
                                    ):
                                        time.sleep(2)
                                        if auto.click_element(
                                            "./assets/images/zh_CN/lc/auto_superimpose.png",
                                            "image",
                                            0.9,
                                        ):
                                            time.sleep(2)
                                            if auto.click_element(
                                                "./assets/images/zh_CN/lc/superimpose.png",
                                                "image",
                                                0.9,
                                            ):
                                                time.sleep(2)
                                                is_superimposed = auto.click_element(
                                                    "./assets/images/zh_CN/lc/close.png",
                                                    "image",
                                                    0.9,
                                                )
                                                time.sleep(2)
                                                auto.press_key("esc", wait_time=3)
                                                if not is_superimposed:
                                                    log.info("没有进行叠加")
                                                    auto.click_element_with_pos(t)
                                                    auto.mouse_scroll(
                                                        5, direction=-1, pause=True
                                                    )
                                                log.info("3星光锥叠加完成，继续查找")
                                                break
                                        else:
                                            time.sleep(2)
                                            auto.press_key("esc", wait_time=3)
                                            auto.click_element_with_pos(t)
                                            auto.mouse_scroll(
                                                5, direction=-1, pause=True
                                            )

                        if not find_target:
                            auto.mouse_scroll(25, direction=-1, pause=True)
                            not_find_times += 1
                        else:
                            not_find_times = 0

        except Exception as e:
            log.error(f"3星光锥自动叠加失败: {e}")
        return False

    # @staticmethod
    # def asset_special_pass_exchange():
    #     try:
    #         log.hr("准备自动兑换专票", 2)
    #     except Exception as e:
    #         log.error(f"专票自动兑换失败: {e}")
    #     return False
