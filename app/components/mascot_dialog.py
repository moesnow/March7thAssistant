"""给确认和提示对话框加 Q 版小人。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.common.mascot import load_mascot
from app.common.scroll_dialog import build_scroll_area
from app.pages.common import is_evernight, style_primary

MASCOT_HEIGHT = 108
MIN_WIDTH = 420


def add_mascot(box, pose, *, height=MASCOT_HEIGHT):
    """小人放在文字右侧，站在按钮栏上沿。长夜主题里有对应的图时是长夜月。"""
    text = getattr(box, "textLayout", None)
    if not isinstance(text, QVBoxLayout):
        return box
    evernight = is_evernight()
    ratio = box.devicePixelRatioF() or 1.0
    pixmap = load_mascot(pose, height, ratio, evernight=evernight)
    width = round(pixmap.width() / ratio)
    box.mascotLabel = QLabel(box.widget)
    box.mascotLabel.setPixmap(pixmap)
    box.mascotLabel.setAlignment(Qt.AlignmentFlag.AlignBottom)
    box.mascotLabel.setFixedHeight(height + 20)
    # 异常详情可能包含多行路径。只让过长的文字滚动，留出按钮和插画的位置。
    chrome = box.vBoxLayout.sizeHint().height() - text.sizeHint().height() + 20
    overflow = text.sizeHint().height() > box.height() - chrome
    box.vBoxLayout.removeItem(text)
    text.setParent(None)
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 24, 0)
    row.setSpacing(0)
    if overflow:
        container = QWidget()
        container.setLayout(text)
        scroll = build_scroll_area(container, box.width() - width - 24, box.height(), chrome)
        row.addWidget(scroll, 1)
    else:
        row.addLayout(text, 1)
    row.addWidget(box.mascotLabel, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
    box.vBoxLayout.insertLayout(0, row, 1)
    box.buttonGroup.setMinimumWidth(max(MIN_WIDTH, box.buttonGroup.minimumWidth()))
    size = box.widget.size()
    box.widget.setFixedSize(max(MIN_WIDTH, size.width() + width + 24),
                            max(size.height(), height + 20 + box.buttonGroup.maximumHeight()))
    style_primary(box.yesButton, evernight)
    return box
