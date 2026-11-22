"""Session accents shared by Fluent controls and embedded HTML."""
from PySide6.QtGui import QColor
from qfluentwidgets import qconfig, themeColor
from qfluentwidgets.common.style_sheet import getStyleSheet, styleSheetManager

from .design_tokens import EVERNIGHT_RED, MARCH7TH_PINK


def set_accent_color(color):
    """Change the accent without repolishing unchanged parent style sheets."""
    qconfig.set(qconfig.themeColor, QColor(color), save=False)
    for widget, source in list(styleSheetManager.items()):
        try:
            if widget.visibleRegion().isNull():
                # Fluent's existing paint watcher refreshes hidden controls on demand.
                widget.setProperty('dirty-qss', True)
            else:
                style = getStyleSheet(source)
                widget.setProperty('dirty-qss', False)
                if widget.styleSheet().rstrip() != style.rstrip():
                    widget.setStyleSheet(style)
                widget.update()  # Navigation icons and indicators read themeColor in paintEvent.
        except RuntimeError:
            # Match Fluent's handling of widgets whose C++ objects have been deleted.
            styleSheetManager.deregister(widget)


def accent_color(default=MARCH7TH_PINK):
    # Keep ordinary rich text unchanged; use Fluent's readable red in Long Night.
    return (themeColor().name() if qconfig.get(qconfig.themeColor).name() == EVERNIGHT_RED
            else default)


def accent_html(content):
    color = QColor(accent_color())
    return content.replace(MARCH7TH_PINK, color.name()).replace(
        'rgba(241, 140, 185,', f'rgba({color.red()}, {color.green()}, {color.blue()},')
