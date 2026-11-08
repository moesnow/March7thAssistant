import logging
import sys

from .colorcodefilter import ColorCodeFilter


def _enable_windows_ansi() -> bool:
    """
    在 Windows 控制台启用 ANSI 转义序列（虚拟终端处理），替代 colorama 的初始化。

    :return: True 表示可直接输出 ANSI 颜色（非 Windows 平台、Windows 10+ 控制台，
             或输出被重定向到文件/管道时原样透传）；False 表示旧版控制台不支持，
             需要省略颜色代码以避免乱码。
    """
    if not sys.platform.startswith('win'):
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        enable_processed_output = 0x0001
        enable_virtual_terminal_processing = 0x0004
        std_output_handle = -11
        std_error_handle = -12

        for std_handle in (std_output_handle, std_error_handle):
            handle = kernel32.GetStdHandle(std_handle)
            if not handle or handle == -1:
                # 无控制台（如 pythonw），无需处理
                continue
            mode = ctypes.c_uint()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                # 输出被重定向到文件/管道，ANSI 代码原样透传
                continue
            new_mode = mode.value | enable_processed_output | enable_virtual_terminal_processing
            if not kernel32.SetConsoleMode(handle, new_mode):
                # 旧版控制台不支持虚拟终端处理
                return False
        return True
    except Exception:
        return False


ANSI_SUPPORTED = _enable_windows_ansi()


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
        formatted = super().format(record)
        if not ANSI_SUPPORTED:
            # 旧版控制台不支持 ANSI：移除颜色代码，保证输出不乱码
            formatted = ColorCodeFilter.color_pattern.sub('', formatted)
        return formatted
