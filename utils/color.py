def black(text):
    """将文本颜色设置为黑色"""
    return f"\033[30m{text}\033[0m"


def grey(text):
    """将文本颜色设置为灰色"""
    return f"\033[90m{text}\033[0m"


def red(text):
    """将文本颜色设置为红色"""
    return f"\033[91m{text}\033[0m"


def green(text):
    """将文本颜色设置为绿色"""
    return f"\033[92m{text}\033[0m"


def yellow(text):
    """将文本颜色设置为黄色"""
    return f"\033[93m{text}\033[0m"


def blue(text):
    """将文本颜色设置为蓝色"""
    return f"\033[94m{text}\033[0m"


def purple(text):
    """将文本颜色设置为紫色"""
    return f"\033[95m{text}\033[0m"


def cyan(text):
    """将文本颜色设置为青色"""
    return f"\033[96m{text}\033[0m"


def white(text):
    """将文本颜色设置为白色"""
    return f"\033[97m{text}\033[0m"


def default(text):
    """将文本颜色设置回默认颜色"""
    return f"\033[39m{text}\033[0m"
