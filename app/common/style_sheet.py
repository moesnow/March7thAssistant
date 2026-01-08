# coding: utf-8
import sys
from enum import Enum
from qfluentwidgets import StyleSheetBase, Theme, isDarkTheme, qconfig


class StyleSheet(StyleSheetBase, Enum):
    """ Style sheet  """

    LINK_CARD = "link_card"
    SAMPLE_CARD = "sample_card"
    HOME_INTERFACE = "home_interface"
    ICON_INTERFACE = "icon_interface"
    VIEW_INTERFACE = "view_interface"
    SETTING_INTERFACE = "setting_interface"
    GALLERY_INTERFACE = "gallery_interface"
    NAVIGATION_VIEW_INTERFACE = "navigation_view_interface"

    Tutorial_INTERFACE = "tutorial_interface"
    HELP_INTERFACE = "help_interface"
    CHANGELOGS_INTERFACE = "changelogs_interface"
    WARP_INTERFACE = "warp_interface"
    TOOLS_INTERFACE = "tools_interface"
    LOG_INTERFACE = "log_interface"
    PIVOT = "pivot"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return f"./assets/app/qss/{theme.value.lower()}/{self.value}.qss"

    def content(self, theme=Theme.AUTO):
        """重写 content 方法以支持跨平台字体替换"""
        qss_content = super().content(theme)

        # 根据操作系统替换字体
        if sys.platform == 'darwin':
            # 替换 Microsoft YaHei 系列字体为 macOS 系统字体
            qss_content = qss_content.replace("'Microsoft YaHei Light'", "'PingFang SC', '.AppleSystemUIFont'")
            qss_content = qss_content.replace("'Microsoft YaHei SemiBold'", "'PingFang SC', '.AppleSystemUIFont'")
            qss_content = qss_content.replace('"Microsoft YaHei"', '"PingFang SC", ".AppleSystemUIFont"')
            qss_content = qss_content.replace("'Microsoft YaHei'", "'PingFang SC', '.AppleSystemUIFont'")

            # 替换 Segoe UI 系列字体
            qss_content = qss_content.replace('"Segoe UI SemiBold"', '"PingFang SC", "BlinkMacSystemFont"')
            qss_content = qss_content.replace("'Segoe UI SemiBold'", "'PingFang SC', 'BlinkMacSystemFont'")
            qss_content = qss_content.replace('"Segoe UI"', '"PingFang SC", "BlinkMacSystemFont"')
            qss_content = qss_content.replace("'Segoe UI'", "'PingFang SC', 'BlinkMacSystemFont'")

        elif sys.platform == 'linux':
            # 替换为 Linux 常见中文字体
            qss_content = qss_content.replace("'Microsoft YaHei Light'", "'Noto Sans CJK SC', 'WenQuanYi Micro Hei', sans-serif")
            qss_content = qss_content.replace("'Microsoft YaHei SemiBold'", "'Noto Sans CJK SC Bold', 'WenQuanYi Micro Hei', sans-serif")
            qss_content = qss_content.replace('"Microsoft YaHei"', '"Noto Sans CJK SC", "WenQuanYi Micro Hei", sans-serif')
            qss_content = qss_content.replace("'Microsoft YaHei'", "'Noto Sans CJK SC', 'WenQuanYi Micro Hei', sans-serif")

            # 替换 Segoe UI 系列字体
            qss_content = qss_content.replace('"Segoe UI SemiBold"', '"Ubuntu", "Noto Sans", sans-serif')
            qss_content = qss_content.replace("'Segoe UI SemiBold'", "'Ubuntu', 'Noto Sans', sans-serif")
            qss_content = qss_content.replace('"Segoe UI"', '"Ubuntu", "Noto Sans", sans-serif')
            qss_content = qss_content.replace("'Segoe UI'", "'Ubuntu', 'Noto Sans', sans-serif")

        # Windows 保持原样，不需要替换

        return qss_content
