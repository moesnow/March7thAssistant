"""总览里的快捷启动编辑器。只有“保存”会提交当前草稿。"""
from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QTreeWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action, BodyLabel, ComboBox, DropDownPushButton, FluentIcon as FIF, InfoBar, InfoBarPosition,
    LineEdit, MessageBoxBase, PushButton, RoundMenu, SubtitleLabel, ToolButton, TreeWidget,
)

from module.config import cfg
from module.localization import tr
from module.overview.shortcuts import (
    ACTIONS, ICONS, MENU_NAMES, ShortcutEditor, available_actions, display_name, icon_for, stored_label,
)
from module.overview.types import Shortcut, ShortcutAction
from utils.tasks import UNSUPPORTED_TASK
from .style import resolve_icon


def _icon_names():
    return {
        "FIF.CAMERA": tr("相机"), "FIF.PLAY": tr("运行"), "UiIcon.BATTERY_CHARGE": tr("开拓力"),
        "UiIcon.CLIPBOARD_TASK": tr("任务清单"), "UiIcon.COIN_STACK": tr("货币战争"),
        "UiIcon.PLANET": tr("宇宙"), "UiIcon.MAP": tr("地图"), "UiIcon.TROPHY": tr("奖杯"),
        "UiIcon.TICKET": tr("兑换码"), "UiIcon.EXPORT": tr("导出"), "UiIcon.COMPASS": tr("指南针"),
        "UiIcon.PEOPLE_CHAT": tr("自动对话"), "UiIcon.SEND": tr("发送"), "UiIcon.REFRESH": tr("刷新"),
        "UiIcon.CLOUD_DOWNLOAD": tr("下载"), "UiIcon.TOOLBOX": tr("工具箱"), "UiIcon.GIFT": tr("礼物"),
        "UiIcon.LIST": tr("列表"), "UiIcon.STAR": tr("星星"),
    }


class ShortcutEditDialog(MessageBoxBase):
    def __init__(self, parent):
        super().__init__(parent)
        self.editor = ShortcutEditor(cfg)
        self.actions = available_actions(cfg)
        self.viewLayout.addWidget(SubtitleLabel(tr("编辑快捷启动"), self.widget))
        self.widget.setMinimumWidth(min(780, parent.width() - 32))
        self.yesButton.setText(tr("保存"))
        self.cancelButton.setText(tr("取消"))

        self.tree = TreeWidget(self.widget)
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumHeight(min(360, max(150, parent.height() - 300)))
        self.tree.currentItemChanged.connect(self._show_selection)
        self.addButton = self._add_menu(tr("添加"), self._add_shortcut)
        self.upButton = self._tool(FIF.UP, tr("上移"), lambda: self._move(-1))
        self.downButton = self._tool(FIF.DOWN, tr("下移"), lambda: self._move(1))
        self.removeButton = self._tool(FIF.DELETE, tr("删除"), self._remove)
        toolbar = QHBoxLayout()
        for button in (self.addButton, self.upButton, self.downButton, self.removeButton):
            toolbar.addWidget(button)
        toolbar.addStretch()
        left = QVBoxLayout()
        left.addWidget(self.tree, 1)
        left.addLayout(toolbar)

        self.fields = QWidget(self.widget)
        form = self.form = QFormLayout(self.fields)
        form.setContentsMargins(0, 0, 0, 0)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.nameEdit = LineEdit(self.fields)
        self.typeCombo = ComboBox(self.fields)
        self.typeCombo.addItems([tr("单个任务"), tr("任务菜单")])
        self.actionCombo = ComboBox(self.fields)
        self.iconCombo = ComboBox(self.fields)
        names = _icon_names()
        for key in ICONS:
            self.iconCombo.addItem(names[key], resolve_icon(key), key)
        self.childButton = self._add_menu(tr("添加菜单项"), self._add_child)
        for label, widget in ((tr("名称"), self.nameEdit), (tr("操作类型"), self.typeCombo),
                              (tr("任务"), self.actionCombo), (tr("图标"), self.iconCombo)):
            form.addRow(BodyLabel(label, self.fields), widget)
        form.addRow(self.childButton)
        self.nameEdit.textEdited.connect(self._rename)
        self.typeCombo.activated.connect(self._change_type)
        self.actionCombo.activated.connect(self._change_action)
        self.iconCombo.activated.connect(lambda: self._update(icon=self.iconCombo.currentData()))

        content = QHBoxLayout()
        content.setSpacing(16)
        content.addLayout(left, 1)
        content.addWidget(self.fields, 1, Qt.AlignmentFlag.AlignTop)
        self.viewLayout.addLayout(content)
        reset = PushButton(FIF.SYNC, tr("恢复默认"), self.widget)
        reset.clicked.connect(self._reset)
        self.buttonLayout.insertWidget(0, reset)
        self._rebuild(0)

    def _tool(self, icon, label, callback):
        button = ToolButton(icon, self.widget)
        button.setAccessibleName(label)
        button.setToolTip(label)
        button.clicked.connect(callback)
        return button

    def _add_menu(self, label, callback):
        button = DropDownPushButton(FIF.ADD, label, self.widget)
        menu = RoundMenu(parent=button)
        for key, text in self.actions.items():
            menu.addAction(Action(resolve_icon(icon_for(key)), text, parent=menu,
                                  triggered=lambda checked=False, action=key: callback(action)))
        button.setMenu(menu)
        return button

    def _position(self):
        node = self.tree.currentItem()
        if node is None:
            return -1, None
        parent = node.parent()
        if parent is None:
            return self.tree.indexOfTopLevelItem(node), None
        return self.tree.indexOfTopLevelItem(parent), parent.indexOfChild(node)

    @staticmethod
    def _paint_node(node, item):
        icon = item.icon if isinstance(item, Shortcut) else icon_for(item.id)
        node.setIcon(0, resolve_icon(icon).icon())
        node.setText(0, display_name(item.name))

    def _rebuild(self, index, child=None):
        with QSignalBlocker(self.tree):
            self.tree.clear()
            for item in self.editor.items:
                node = QTreeWidgetItem(self.tree)
                self._paint_node(node, item)
                for entry in item.menu:
                    self._paint_node(QTreeWidgetItem(node), entry)
                node.setExpanded(True)
            if self.editor.items:
                node = self.tree.topLevelItem(min(index, len(self.editor.items) - 1))
                self.tree.setCurrentItem(node if child is None else node.child(child))
        self._show_selection()

    def _show_selection(self):
        index, child = self._position()
        selected = index >= 0
        self.fields.setVisible(selected)
        self.removeButton.setEnabled(selected)
        self.upButton.setEnabled(False)
        self.downButton.setEnabled(False)
        if not selected:
            return
        item = self.editor.items[index]
        top = child is None
        pos, length = (index, len(self.editor.items)) if top else (child, len(item.menu))
        self.upButton.setEnabled(pos > 0)
        self.downButton.setEnabled(pos + 1 < length)
        entry = item if top else item.menu[child]
        menu = entry.id == "menu"
        self._source_name = entry.name
        self.nameEdit.setText(display_name(entry.name))
        self.typeCombo.setCurrentIndex(int(menu))
        self.iconCombo.setCurrentIndex(self.iconCombo.findData(item.icon))
        self.form.setRowVisible(self.typeCombo, top)
        self.form.setRowVisible(self.actionCombo, not menu)
        self.form.setRowVisible(self.iconCombo, top)
        self.form.setRowVisible(self.childButton, menu)
        self.actionCombo.clear()
        if not menu:
            for key, text in self.actions.items():
                self.actionCombo.addItem(text, userData=key)
            if entry.id not in self.actions:
                self.actionCombo.addItem(f"{tr(ACTIONS[entry.id])} ({tr(UNSUPPORTED_TASK)})", userData=entry.id)
            self.actionCombo.setCurrentIndex(self.actionCombo.findData(entry.id))

    def _update(self, **changes):
        index, child = self._position()
        item = self.editor.items[index]
        if child is None:
            entry = item = replace(item, **changes)
        else:
            menu = list(item.menu)
            entry = menu[child] = replace(menu[child], **changes)
            item = replace(item, menu=tuple(menu))
        self.editor.replace(index, item)
        self._paint_node(self.tree.currentItem(), entry)

    def _rename(self, text):
        self._update(name=stored_label(text, self._source_name))

    def _change_action(self):
        key = self.actionCombo.currentData()
        index, child = self._position()
        item = self.editor.items[index]
        entry = item if child is None else item.menu[child]
        changes = {"id": key}
        if entry.name in (ACTIONS[entry.id], MENU_NAMES.get(entry.id)):
            changes["name"] = ACTIONS[key]
        self._update(**changes)
        self._show_selection()

    def _change_type(self, selected):
        index, _ = self._position()
        item = self.editor.items[index]
        if bool(selected) == (item.id == "menu"):
            return
        if selected:
            child = ShortcutAction(item.id, ACTIONS[item.id])
            self.editor.replace(index, replace(item, id="menu", menu=(child,)))
        else:
            key = item.menu[0].id if item.menu else next(iter(self.actions))
            self.editor.replace(index, replace(item, id=key, menu=()))
        self._rebuild(index)

    def _add_shortcut(self, key):
        self.editor.add(Shortcut(key, ACTIONS[key], icon_for(key)))
        self._rebuild(len(self.editor.items) - 1)

    def _add_child(self, key):
        index, _ = self._position()
        item = self.editor.items[index]
        self.editor.replace(index, replace(item, menu=(*item.menu, ShortcutAction(key, ACTIONS[key]))))
        self._rebuild(index, len(item.menu))

    def _move(self, offset):
        index, child = self._position()
        if child is None:
            self.editor.move(index, index + offset)
            self._rebuild(index + offset)
        else:
            item = self.editor.items[index]
            menu = list(item.menu)
            menu.insert(child + offset, menu.pop(child))
            self.editor.replace(index, replace(item, menu=tuple(menu)))
            self._rebuild(index, child + offset)

    def _remove(self):
        index, child = self._position()
        if child is None:
            self.editor.remove(index)
        else:
            item = self.editor.items[index]
            self.editor.replace(index, replace(item, menu=item.menu[:child] + item.menu[child + 1:]))
        self._rebuild(index)

    def _reset(self):
        self.editor.reset()
        self._rebuild(0)

    def validate(self):
        try:
            self.editor.save()
        except (ValueError, OSError) as error:
            InfoBar.error(tr("保存失败"), str(error), position=InfoBarPosition.TOP, parent=self)
            return False
        return True
