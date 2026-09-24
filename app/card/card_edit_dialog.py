# coding:utf-8
import copy
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QScrollArea, QWidget, QFileDialog, QFrame)
from PySide6.QtGui import QPixmap

from qfluentwidgets import (PushButton, PrimaryPushButton, LineEdit, ComboBox,
                            FluentIcon, InfoBar, InfoBarPosition, isDarkTheme)

from utils.tasks import AVAILABLE_TASKS
from module.localization import tr
from app.common.style_sheet import StyleSheet

# 仅主页可用的特殊操作（不在 AVAILABLE_TASKS 中）
HOME_EXTRA_TASKS = {
    "_reset_universe_config": "重置模拟宇宙配置文件",
    "_open_universe_dir": "打开模拟宇宙目录",
    "_open_universe_homepage": "打开模拟宇宙项目主页",
    "_reset_fight_config": "重置锄大地配置文件",
    "_open_fight_dir": "打开锄大地程序目录",
    "_open_fight_homepage": "打开锄大地项目主页",
}

# 合并所有可选任务（值为中文原文 msgid，显示时再 tr()）
ALL_TASKS = {**AVAILABLE_TASKS, **HOME_EXTRA_TASKS}


DEFAULT_CARDS = [
    {
        "icon": "./assets/app/images/March7th.jpg",
        "title": "完整运行",
        "action_type": "single",
        "task_id": "main",
        "menu_items": []
    },
    {
        "icon": "./assets/app/images/JingYuan.jpg",
        "title": "日常",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "日常", "task_id": "routine"},
            {"label": "每日实训", "task_id": "daily"},
            {"label": "清体力", "task_id": "power"}
        ]
    },
    {
        "icon": "./assets/app/images/Yanqing.jpg",
        "title": "货币战争",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "运行一次", "task_id": "currencywars"},
            {"label": "循环运行", "task_id": "currencywarsloop"}
        ]
    },
    {
        "icon": "./assets/app/images/Herta.jpg",
        "title": "差分宇宙",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "差分宇宙运行一次 ⭐", "task_id": "divergent"},
            {"label": "差分宇宙循环运行 ⭐", "task_id": "divergentloop"},
            {"label": "差分宇宙中途接管", "task_id": "divergenttemp"},
            {"label": "模拟宇宙快速启动（停止维护）", "task_id": "universe"},
            {"label": "模拟宇宙原版运行（停止维护）", "task_id": "universe_gui"},
            {"label": "更新模拟宇宙（停止维护）", "task_id": "universe_update"},
            {"label": "重置模拟宇宙配置文件（停止维护）", "task_id": "_reset_universe_config"},
            {"label": "打开模拟宇宙目录（停止维护）", "task_id": "_open_universe_dir"},
            {"label": "打开模拟宇宙项目主页（停止维护）", "task_id": "_open_universe_homepage"},
        ]
    },
    {
        "icon": "./assets/app/images/SilverWolf.jpg",
        "title": "锄大地",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "快速启动 ⭐", "task_id": "fight"},
            {"label": "原版运行", "task_id": "fight_gui"},
            {"label": "更新锄大地", "task_id": "fight_update"},
            {"label": "重置配置文件", "task_id": "_reset_fight_config"},
            {"label": "打开程序目录", "task_id": "_open_fight_dir"},
            {"label": "打开项目主页", "task_id": "_open_fight_homepage"},]
    },
    {
        "icon": "./assets/app/images/Bronya.jpg",
        "title": "逐光捡金",
        "action_type": "menu",
        "task_id": "",
        "menu_items": [
            {"label": "混沌回忆", "task_id": "forgottenhall"},
            {"label": "虚构叙事", "task_id": "purefiction"},
            {"label": "末日幻影", "task_id": "apocalyptic"}
        ]
    },
]

# 内置文案的中文原文集合：这些值可以被翻译，用户自定义文案则原样显示。
# 同时包含任务名（菜单项会自动填入任务名），持久化时把界面文案还原成中文原文，
# 保证 config.yaml 里存的是语言无关的键，切语言/重启后依然正确。
BUILTIN_LABELS = frozenset(
    [card["title"] for card in DEFAULT_CARDS]
    + [item["label"] for card in DEFAULT_CARDS for item in card["menu_items"]]
    + list(ALL_TASKS.values())
)


def display_label(text: str) -> str:
    """按当前语言显示卡片/菜单项文案：内置文案走 tr()，用户自定义文案原样返回。"""
    if not text:
        return text
    return tr(text) if text in BUILTIN_LABELS else text


def stored_label(text: str, msgid: str | None) -> str:
    """把界面上的文案还原成可持久化的键。

    :param text:  界面上当前的文案（可能是译文，也可能被用户改过）
    :param msgid: 该控件原本承载的中文原文；用户新建的控件传 None

    只做「正向」比较：文案仍等于该 msgid 的当前语言显示时，存回 msgid。
    这样 config.yaml 里存的是语言无关的键，切语言/重启后依然正确。
    注意不能按译文反查 msgid —— 不同原文可能有相同译文（如日文的「更新锄大地」与
    「锄大地更新」），反查会串味。
    """
    if msgid and text == display_label(msgid):
        return msgid
    return text


def legacy_label_map() -> dict:
    """旧版本配置遗留的「译文 -> 中文原文」还原表（仅内置文案闭集）。

    旧版本在非中文界面保存卡片时会把译文写进 config.yaml；这里按 5 语言目录反查还原。
    **歧义译文（多个内置文案同译）不收录**——如日文里「更新锄大地」与「锄大地更新」同译，
    反查会串味，宁可原样保留交由用户重新选择。
    """
    from module.localization import translations_of

    reverse: dict[str, str] = {}
    ambiguous: set[str] = set()
    for msgid in sorted(BUILTIN_LABELS):
        for translated in translations_of(msgid).values():
            # 同文、或译文本身就是某个内置原文的值无需还原（display_label 已能识别）
            if not translated or translated == msgid or translated in BUILTIN_LABELS:
                continue
            if translated in reverse and reverse[translated] != msgid:
                ambiguous.add(translated)
            else:
                reverse[translated] = msgid
    for text in ambiguous:
        reverse.pop(text, None)
    return reverse


def migrate_home_cards(cards, reverse=None) -> bool:
    """把旧版本写进配置的译文还原为中文原文（原地修改、幂等）。

    识别范围仅限「等于内置文案某个译文」的遗留值；用户自定义文案与歧义译文不动。
    返回是否有改动，供调用方决定是否写回配置。
    """
    if not isinstance(cards, list):
        return False
    if reverse is None:
        reverse = legacy_label_map()
    changed = False
    for card in cards:
        if not isinstance(card, dict):
            continue
        title = card.get("title", "")
        if isinstance(title, str) and title in reverse:
            card["title"] = reverse[title]
            changed = True
        for item in card.get("menu_items") or []:
            if not isinstance(item, dict):
                continue
            label = item.get("label", "")
            if isinstance(label, str) and label in reverse:
                item["label"] = reverse[label]
                changed = True
    return changed


class MenuItemRow(QWidget):
    """菜单项编辑行"""

    def __init__(self, label="", task_id="", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 2, 0, 2)

        self._task_keys = list(ALL_TASKS.keys())
        self._task_msgids = list(ALL_TASKS.values())
        self._task_labels = [display_label(v) for v in self._task_msgids]
        # 标记：如果 label 为空，说明是新增的，需要自动填写
        self._auto_fill = not label
        # 该控件原本承载的中文原文（用户自定义文案为 None），保存时据此还原
        self._label_msgid = label if label in BUILTIN_LABELS else None

        self.label_edit = LineEdit()
        self.label_edit.setPlaceholderText(tr("菜单项名称"))

        self.task_combo = ComboBox()
        self.task_combo.addItems(self._task_labels)
        if task_id in self._task_keys:
            self.task_combo.setCurrentIndex(self._task_keys.index(task_id))

        # 自动填写名称：新增时用任务名称填写，切换任务时也自动更新
        if self._auto_fill:
            self._apply_task_name()
        else:
            self.label_edit.setText(display_label(label))

        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        # 用户手动编辑过名称后，停止自动填写
        self.label_edit.textEdited.connect(self._on_label_edited)

        self.remove_btn = PushButton("×")
        self.remove_btn.setFixedWidth(36)

        layout.addWidget(QLabel(tr("名称：")))
        layout.addWidget(self.label_edit, 1)
        layout.addWidget(QLabel(tr("任务：")))
        layout.addWidget(self.task_combo, 1)
        layout.addWidget(self.remove_btn)

    def _apply_task_name(self):
        """把当前选中任务的名称填入名称框，并记住对应的中文原文。"""
        idx = self.task_combo.currentIndex()
        if 0 <= idx < len(self._task_msgids):
            self._label_msgid = self._task_msgids[idx]
            self.label_edit.setText(self._task_labels[idx])

    def _on_task_changed(self, index):
        if self._auto_fill:
            self._apply_task_name()

    def _on_label_edited(self, text):
        self._auto_fill = False

    def get_data(self):
        idx = self.task_combo.currentIndex()
        return {
            # 还原成中文原文，避免把译文写进 config.yaml
            "label": stored_label(self.label_edit.text(), self._label_msgid),
            "task_id": self._task_keys[idx] if 0 <= idx < len(self._task_keys) else ""
        }


class CardEditorWidget(QFrame):
    """单个卡片的编辑器组件"""

    def __init__(self, card_data, dialog, parent=None):
        super().__init__(parent)
        self.dialog = dialog
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # 第一行：图标 + 标题 + 操作按钮
        top_layout = QHBoxLayout()

        self.icon_path = card_data.get("icon", "")
        # 该卡片原本承载的中文原文（用户自定义标题为 None），保存时据此还原
        raw_title = card_data.get("title", "")
        self._title_msgid = raw_title if raw_title in BUILTIN_LABELS else None
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(60, 60)
        self.icon_label.setScaledContents(True)
        self._update_icon()

        icon_btn = PushButton(tr("图标"))
        icon_btn.setFixedWidth(60)
        icon_btn.clicked.connect(self._choose_icon)

        icon_container = QVBoxLayout()
        icon_container.setSpacing(2)
        icon_container.addWidget(self.icon_label, alignment=Qt.AlignmentFlag.AlignCenter)
        icon_container.addWidget(icon_btn)
        top_layout.addLayout(icon_container)

        # 标题输入
        title_container = QVBoxLayout()
        title_container.addWidget(QLabel(tr("标题：")))
        self.title_edit = LineEdit()
        self.title_edit.setText(display_label(card_data.get("title", "")))
        self.title_edit.setPlaceholderText(tr("卡片标题"))
        title_container.addWidget(self.title_edit)
        title_container.addStretch()
        top_layout.addLayout(title_container, 1)

        # 上移、下移、删除按钮
        btn_container = QVBoxLayout()
        btn_row = QHBoxLayout()
        up_btn = PushButton("↑")
        up_btn.setFixedWidth(36)
        up_btn.clicked.connect(lambda: self.dialog.move_card(self, -1))
        down_btn = PushButton("↓")
        down_btn.setFixedWidth(36)
        down_btn.clicked.connect(lambda: self.dialog.move_card(self, 1))
        del_btn = PushButton("×")
        del_btn.setFixedWidth(36)
        del_btn.clicked.connect(lambda: self.dialog.remove_card(self))
        btn_row.addWidget(up_btn)
        btn_row.addWidget(down_btn)
        btn_row.addWidget(del_btn)
        btn_container.addLayout(btn_row)
        btn_container.addStretch()
        top_layout.addLayout(btn_container)

        main_layout.addLayout(top_layout)

        # 第二行：操作类型 + 单任务选择
        action_layout = QHBoxLayout()
        action_layout.addWidget(QLabel(tr("操作类型：")))
        self.type_combo = ComboBox()
        self.type_combo.addItems([tr("单个任务"), tr("任务菜单")])
        if card_data.get("action_type") == "menu":
            self.type_combo.setCurrentIndex(1)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        action_layout.addWidget(self.type_combo)

        self.single_task_label = QLabel(tr("任务："))
        action_layout.addWidget(self.single_task_label)
        self.task_combo = ComboBox()
        self._task_keys = list(ALL_TASKS.keys())
        self._task_labels = [tr(v) for v in ALL_TASKS.values()]
        self.task_combo.addItems(self._task_labels)
        task_id = card_data.get("task_id", "")
        if task_id in self._task_keys:
            self.task_combo.setCurrentIndex(self._task_keys.index(task_id))
        action_layout.addWidget(self.task_combo, 1)

        main_layout.addLayout(action_layout)

        # 第三行：菜单项编辑区域
        self.menu_widget = QWidget()
        menu_main_layout = QVBoxLayout(self.menu_widget)
        menu_main_layout.setContentsMargins(0, 0, 0, 0)
        menu_main_layout.setSpacing(2)
        self.menu_items_layout = QVBoxLayout()
        self.menu_items_layout.setSpacing(2)
        menu_main_layout.addLayout(self.menu_items_layout)

        add_item_btn = PushButton(FluentIcon.ADD, tr("添加菜单项"))
        add_item_btn.clicked.connect(self._add_menu_item)
        menu_main_layout.addWidget(add_item_btn)

        main_layout.addWidget(self.menu_widget)

        # 加载已有菜单项
        self.menu_item_rows = []
        for item in card_data.get("menu_items", []):
            self._add_menu_item_row(item.get("label", ""), item.get("task_id", ""))

        # 根据操作类型显示/隐藏
        self._on_type_changed(self.type_combo.currentIndex())

    def _update_icon(self):
        if self.icon_path and os.path.exists(self.icon_path):
            pixmap = QPixmap(self.icon_path)
            self.icon_label.setPixmap(pixmap)
        else:
            self.icon_label.setText("?")
            self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            border_color = "rgba(255, 255, 255, 0.4)" if isDarkTheme() else "gray"
            self.icon_label.setStyleSheet(f"border: 1px dashed {border_color}; font-size: 24px;")

    def _choose_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("选择图标"), os.getcwd(),
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)")
        if file_path:
            self.icon_path = file_path
            self.icon_label.setStyleSheet("")
            self._update_icon()

    def _on_type_changed(self, index):
        is_menu = index == 1
        self.single_task_label.setVisible(not is_menu)
        self.task_combo.setVisible(not is_menu)
        self.menu_widget.setVisible(is_menu)

    def _add_menu_item(self):
        self._add_menu_item_row("", "main")

    def _add_menu_item_row(self, label, task_id):
        row = MenuItemRow(label, task_id, self)
        row.remove_btn.clicked.connect(lambda: self._remove_menu_item(row))
        self.menu_item_rows.append(row)
        self.menu_items_layout.addWidget(row)

    def _remove_menu_item(self, row):
        if row in self.menu_item_rows:
            self.menu_item_rows.remove(row)
            row.setParent(None)
            row.deleteLater()

    def get_data(self):
        is_menu = self.type_combo.currentIndex() == 1
        task_idx = self.task_combo.currentIndex()
        return {
            "icon": self.icon_path,
            # 还原成中文原文，避免把译文写进 config.yaml
            "title": stored_label(self.title_edit.text(), self._title_msgid),
            "action_type": "menu" if is_menu else "single",
            "task_id": self._task_keys[task_idx] if not is_menu and 0 <= task_idx < len(self._task_keys) else "",
            "menu_items": [row.get_data() for row in self.menu_item_rows] if is_menu else []
        }


class CardEditDialog(QDialog):
    """编辑主页卡片的对话框"""

    def __init__(self, cards_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("编辑主页卡片"))
        self.setMinimumSize(700, 500)
        self.resize(750, 600)
        self.result_cards = None

        StyleSheet.CARD_EDIT_DIALOG.apply(self)

        main_layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel(tr("编辑主页卡片"))
        title_label.setStyleSheet("font-size: 20px; font-weight: 600; padding: 8px 0;")
        main_layout.addWidget(title_label)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_widget = QWidget()
        # QScrollArea.setWidget 会强制 autoFillBackground，滚动内容默认用系统 palette
        # 填充背景，深色模式下会露出浅灰底，需由 qss 按主题覆盖
        self.scroll_widget.setObjectName("cardEditScrollWidget")
        self.cards_layout = QVBoxLayout(self.scroll_widget)
        self.cards_layout.setSpacing(8)
        scroll.setWidget(self.scroll_widget)
        main_layout.addWidget(scroll, 1)

        # 加载卡片编辑器
        self.card_editors = []
        for card in cards_data:
            self._create_card_editor(card)
        self._rebuild_layout()

        # 底部按钮
        btn_layout = QHBoxLayout()
        add_btn = PushButton(FluentIcon.ADD, tr("添加卡片"))
        add_btn.clicked.connect(self._add_card)
        restore_btn = PushButton(FluentIcon.SYNC, tr("恢复默认"))
        restore_btn.clicked.connect(self._restore_defaults)

        ok_btn = PrimaryPushButton(tr("确定"))
        ok_btn.clicked.connect(self._on_ok)
        cancel_btn = PushButton(tr("取消"))
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(restore_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)

        main_layout.addLayout(btn_layout)

    def _create_card_editor(self, card_data):
        editor = CardEditorWidget(card_data, self, self.scroll_widget)
        self.card_editors.append(editor)
        return editor

    def _add_card(self):
        new_card = {
            "icon": "./assets/app/images/March7th.jpg",
            "title": "",
            "action_type": "single",
            "task_id": "main",
            "menu_items": []
        }
        self._create_card_editor(new_card)
        self._rebuild_layout()

    def _restore_defaults(self):
        for editor in self.card_editors:
            editor.setParent(None)
            editor.deleteLater()
        self.card_editors.clear()

        for card in DEFAULT_CARDS:
            self._create_card_editor(copy.deepcopy(card))
        self._rebuild_layout()

    def move_card(self, editor, direction):
        idx = self.card_editors.index(editor)
        new_idx = idx + direction
        if 0 <= new_idx < len(self.card_editors):
            self.card_editors[idx], self.card_editors[new_idx] = \
                self.card_editors[new_idx], self.card_editors[idx]
            self._rebuild_layout()

    def remove_card(self, editor):
        if editor in self.card_editors:
            self.card_editors.remove(editor)
            editor.setParent(None)
            editor.deleteLater()

    def _rebuild_layout(self):
        while self.cards_layout.count():
            self.cards_layout.takeAt(0)
        for editor in self.card_editors:
            self.cards_layout.addWidget(editor)
        self.cards_layout.addStretch()

    def _on_ok(self):
        self.result_cards = [editor.get_data() for editor in self.card_editors]
        for i, card in enumerate(self.result_cards):
            if not card["title"].strip():
                InfoBar.error(
                    tr("保存失败"),
                    tr("卡片标题不能为空"),
                    duration=3000,
                    position=InfoBarPosition.TOP,
                    parent=self
                )
                self.result_cards = None
                return
            if card["action_type"] == "menu":
                for item in card["menu_items"]:
                    if not item["label"].strip():
                        InfoBar.error(
                            tr("保存失败"),
                            tr("任务菜单中的菜单项名称不能为空"),
                            duration=3000,
                            position=InfoBarPosition.TOP,
                            parent=self
                        )
                        self.result_cards = None
                        return
        self.accept()
