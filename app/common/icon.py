# coding: utf-8
from enum import Enum

from qfluentwidgets import FluentIconBase, getIconColor, Theme


class UiIcon(FluentIconBase, Enum):
    """通用 UI 图标，补充 qfluentwidgets 内置 FluentIcon 未覆盖的语义。

    图标来自 Fluent UI System Icons（Microsoft，MIT），由 assets/scripts/fetch_icons.py
    下载并生成黑白双版，明亮/暗色主题自动切换。
    """

    FLASH = "flash"
    BATTERY_CHARGE = "battery-charge"
    DROP = "drop"
    BEAKER = "beaker"
    REPEAT = "arrow-repeat-all"
    REFRESH = "arrow-clockwise"
    PEOPLE = "people"
    PEOPLE_CHECKMARK = "people-checkmark"
    PEOPLE_LIST = "people-list"
    PEOPLE_LINK = "people-link"
    PEOPLE_SWAP = "people-swap"
    PEOPLE_TEAM = "people-team"
    PEOPLE_CHAT = "people-chat"
    TARGET = "target"
    TARGET_ARROW = "target-arrow"
    DIAMOND = "diamond"
    CUBE = "cube"
    PLANET = "planet"
    GIFT = "gift"
    SEND = "send"
    SEND_COPY = "send-copy"
    CLIPBOARD_TASK = "clipboard-task"
    CROWN = "crown"
    TROPHY = "trophy"
    TICKET = "ticket-horizontal"
    SPARKLE = "sparkle"
    BOX = "box"
    STACK = "stack"
    COIN = "coin-multiple"
    COIN_STACK = "coin-stack"
    MONEY = "money"
    WAND = "wand"
    OPTIONS = "options"
    GAUGE = "gauge"
    ROCKET = "rocket"
    CLOCK = "clock"
    TIMER = "timer"
    HOURGLASS = "hourglass"
    FILTER = "filter"
    MERGE = "merge"
    CLOUD = "cloud"
    CLOUD_DOWNLOAD = "cloud-arrow-down"
    CLOUD_SYNC = "cloud-sync"
    EYE_OFF = "eye-off"
    KEYBOARD = "keyboard"
    KEY = "key"
    CHART = "chart-multiple"
    SPEAKER = "speaker-2"
    MEGAPHONE = "megaphone"
    MEGAPHONE_CIRCLE = "megaphone-circle"
    MEGAPHONE_LOUD = "megaphone-loud"
    MIC = "mic"
    SOUND_WAVE = "sound-wave-circle"
    PLUG = "plug-connected"
    LIST = "list"
    PIN = "pin"
    LEAF = "leaf-two"
    COMPASS = "compass-true-north"
    MAP = "map"
    FOOD = "food"
    BOOKMARK = "bookmark"
    SERVER = "server"
    QUESTION = "question"
    TOOLBOX = "toolbox"
    HISTORY = "history"
    LINK = "link"
    TAP = "tap-single"
    PERSON = "person"
    STAR = "star"
    IMPORT = "arrow-import"
    EXPORT = "arrow-export"
    SELECT_ALL = "select-all-on"

    def path(self, theme=Theme.AUTO):
        return f"./assets/app/images/icons/ui/{self.value}_{getIconColor(theme)}.svg"


class BrandIcon(FluentIconBase, Enum):
    """品牌 logo，仅用于标识对应产品/服务。

    来源：Simple Icons（CC0-1.0）、Tabler Icons（MIT）、TDesign Icons（MIT）、
    IconPark Outline（Apache-2.0），由 assets/scripts/fetch_icons.py 下载并生成黑白双版。
    商标权归属各公司，请勿改作他用。
    """

    WINDOWS = "windows"
    TELEGRAM = "telegram"
    MATRIX = "matrix"
    DISCORD = "discord"
    QQ = "qq"
    BILIBILI = "bilibili"
    DINGTALK = "dingtalk"
    WECOM = "wecom"
    LARK = "lark"

    def path(self, theme=Theme.AUTO):
        return f"./assets/app/images/icons/brand/{self.value}_{getIconColor(theme)}.svg"
