# coding: utf-8
import sys
from enum import Enum
from qfluentwidgets import StyleSheetBase, Theme, isDarkTheme, qconfig


def _is_korean_language():
    """한국어 설정 여부 확인"""
    try:
        from module.config import cfg
        return hasattr(cfg, 'ui_language_now') and cfg.ui_language_now == "ko_KR"
    except Exception:
        return False


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
        is_korean = _is_korean_language()

        # 根据操作系统替换字体
        if sys.platform == 'darwin':
            if is_korean:
                # macOS 한국어: Apple SD Gothic Neo 사용
                qss_content = qss_content.replace("'Microsoft YaHei Light'", "'Apple SD Gothic Neo', 'PingFang SC'")
                qss_content = qss_content.replace("'Microsoft YaHei SemiBold'", "'Apple SD Gothic Neo', 'PingFang SC'")
                qss_content = qss_content.replace('"Microsoft YaHei"', '"Apple SD Gothic Neo", "PingFang SC"')
                qss_content = qss_content.replace("'Microsoft YaHei'", "'Apple SD Gothic Neo', 'PingFang SC'")
            else:
                # macOS 기본: PingFang SC
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
            if is_korean:
                # Linux 한국어: Noto Sans CJK KR 사용
                qss_content = qss_content.replace("'Microsoft YaHei Light'", "'Noto Sans CJK KR', 'Noto Sans CJK SC', sans-serif")
                qss_content = qss_content.replace("'Microsoft YaHei SemiBold'", "'Noto Sans CJK KR', 'Noto Sans CJK SC', sans-serif")
                qss_content = qss_content.replace('"Microsoft YaHei"', '"Noto Sans CJK KR", "Noto Sans CJK SC", sans-serif')
                qss_content = qss_content.replace("'Microsoft YaHei'", "'Noto Sans CJK KR', 'Noto Sans CJK SC', sans-serif")
            else:
                # Linux 기본: Noto Sans CJK SC
                qss_content = qss_content.replace("'Microsoft YaHei Light'", "'Noto Sans CJK SC', 'WenQuanYi Micro Hei', sans-serif")
                qss_content = qss_content.replace("'Microsoft YaHei SemiBold'", "'Noto Sans CJK SC Bold', 'WenQuanYi Micro Hei', sans-serif")
                qss_content = qss_content.replace('"Microsoft YaHei"', '"Noto Sans CJK SC", "WenQuanYi Micro Hei", sans-serif')
                qss_content = qss_content.replace("'Microsoft YaHei'", "'Noto Sans CJK SC', 'WenQuanYi Micro Hei', sans-serif")

            # 替换 Segoe UI 系列字体
            qss_content = qss_content.replace('"Segoe UI SemiBold"', '"Ubuntu", "Noto Sans", sans-serif')
            qss_content = qss_content.replace("'Segoe UI SemiBold'", "'Ubuntu', 'Noto Sans', sans-serif")
            qss_content = qss_content.replace('"Segoe UI"', '"Ubuntu", "Noto Sans", sans-serif')
            qss_content = qss_content.replace("'Segoe UI'", "'Ubuntu', 'Noto Sans', sans-serif")

        elif sys.platform == 'win32':
            # Windows: 한국어 설정 시 맑은 고딕 사용
            if is_korean:
                qss_content = qss_content.replace("'Microsoft YaHei Light'", "'Malgun Gothic'")
                qss_content = qss_content.replace("'Microsoft YaHei SemiBold'", "'Malgun Gothic'")
                qss_content = qss_content.replace('"Microsoft YaHei"', '"Malgun Gothic"')
                qss_content = qss_content.replace("'Microsoft YaHei'", "'Malgun Gothic'")

        return qss_content
