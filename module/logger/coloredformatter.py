from colorama import init
import logging

# 初始化colorama以支持在不同平台上的颜色显示
init(autoreset=True)


class ColoredFormatter(logging.Formatter):
    """
    一个自定义的日志格式化器，用于给不同级别的日志信息添加颜色。
    这可以帮助用户更快地识别日志级别。
    """

    # 定义日志级别与颜色代码的映射关系
    COLORS = {
        'DEBUG': '\033[94m',  # 蓝色
        'INFO': '\033[92m',   # 绿色
        'WARNING': '\033[93m',  # 黄色
        'ERROR': '\033[91m',   # 红色
        'CRITICAL': '\033[95m',  # 紫色
        'RESET': '\033[0m'   # 重置颜色，用于在日志文本后重置颜色，避免影响后续文本
    }

    def format(self, record):
        """
        重写父类的format方法，用于在格式化日志记录之前添加颜色。
        :param record: 日志记录
        :return: 带颜色的日志字符串
        """
        # 获取日志级别，用于确定使用哪种颜色
        log_level = record.levelname
        # 根据日志级别获取相应的颜色代码，如果找不到则使用重置颜色
        color_start = self.COLORS.get(log_level, self.COLORS['RESET'])
        # 获取重置颜色代码
        color_end = self.COLORS['RESET']
        # 将颜色代码应用到日志级别上，以便在输出中显示颜色
        record.levelname = f"{color_start}{log_level}{color_end}"
        # 调用父类的format方法进行最终的格式化
        return super().format(record)
