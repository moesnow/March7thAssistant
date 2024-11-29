# coding: utf-8
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
    PIVOT = "pivot"

    def path(self, theme=Theme.AUTO):
        theme = qconfig.theme if theme == Theme.AUTO else theme
        return f"./assets/app/qss/{theme.value.lower()}/{self.value}.qss"
