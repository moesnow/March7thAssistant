import os
from datetime import datetime


def save_error_screenshot(logger):
    """
    保存错误截图到日志目录。
    尝试捕获当前游戏窗口的截图并保存为错误截图。

    :param logger: Logger实例，用于记录日志
    :return: 截图保存路径，如果失败则返回None。
    """
    try:
        # 延迟导入以避免循环依赖
        from module.automation import auto

        # 确保截图目录存在
        screenshot_dir = os.path.join("logs", "screenshots")
        if not os.path.exists(screenshot_dir):
            os.makedirs(screenshot_dir)

        # 生成带时间戳的文件名
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"error_{timestamp}.png"
        filepath = os.path.join(screenshot_dir, filename)

        # 尝试捕获截图
        try:
            auto.take_screenshot()
            # 验证截图是否成功捕获
            if auto.screenshot is not None:
                auto.screenshot.save(filepath)
                logger.info(f"错误截图已保存: {filepath}")
                logger.info(f"反馈问题时请附上此截图以协助诊断")
                return filepath
            else:
                logger.debug("截图对象为空，无法保存")
        except Exception as e:
            logger.debug(f"捕获游戏窗口截图失败: {e}")

    except Exception as e:
        # 静默处理截图保存失败，不影响错误处理流程
        logger.debug(f"保存错误截图失败: {e}")

    return None
