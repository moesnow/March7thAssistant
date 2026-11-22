"""Desktop design tokens from the UI redesign palette and 4 px grid."""
from dataclasses import dataclass


MARCH7TH_PINK = '#f18cb9'
EVERNIGHT_RED = '#ba3032'


@dataclass(frozen=True)
class Palette:
    brand_pink: str
    deep_pink: str
    sky_blue: str
    success: str
    warning: str
    error: str
    info: str
    chart_series: str
    evernight_accent: str
    evernight_button: str


LIGHT = Palette(
    brand_pink=MARCH7TH_PINK, deep_pink='#c93a76', sky_blue='#64b5ec',
    success='#0f7b0f', warning='#9d5d00', error='#c42b1c', info='#005fb8',
    chart_series='#d4508c', evernight_accent=EVERNIGHT_RED, evernight_button=EVERNIGHT_RED,
)
DARK = Palette(
    brand_pink='#f5a3c7', deep_pink='#f5a3c7', sky_blue='#7cc3f2',
    success='#6ccb5f', warning='#fce100', error='#ff99a4', info='#99c9ff',
    chart_series='#dc6299', evernight_accent='#e0656d', evernight_button='#ec8087',
)

GRID = 4
PAGE_MARGIN = 32
CARD_SPACING = 12
CARD_PADDING = 16
SETTING_ROW_MIN_HEIGHT = 52

CARD_RADIUS = 8
GREETING_RADIUS = 12
CONTROL_RADIUS = 5
PILL_RADIUS_MIN = 11
PILL_RADIUS_MAX = 16
DIALOG_RADIUS = 12
