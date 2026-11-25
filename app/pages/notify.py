"""设置 › 消息推送：已添加的渠道、添加渠道，以及渠道的编辑对话框。数据来自 NotifyModel。"""
import json
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, FluentIcon, IconWidget, InfoBar, LineEdit,
                            MessageBox, MessageBoxBase, PasswordLineEdit, PlainTextEdit, PushButton, ScrollArea,
                            SimpleCardWidget, StrongBodyLabel, SubtitleLabel, ToolButton, getFont, isDarkTheme, qconfig)

from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from app.overview.style import accent, format_when, text_color, tone
from app.overview.widgets import IconTile, LinkButton
from module.channel_catalog import CHANNEL_BY_ID
from module.localization import tr
from .common import Divider, bare_switch, border_color, icon_of, is_evernight, secondary, style_primary, surface_color

VISIBLE_TILES = 11


def _delivery_time(at):
    try:
        moment = datetime.fromisoformat(at).astimezone()
    except (TypeError, ValueError):
        return ""
    return format_when(moment.replace(tzinfo=None), datetime.now())


class ChannelRow(QWidget):
    testRequested = Signal(str)
    editRequested = Signal(str)
    removeRequested = Signal(str)
    enableRequested = Signal(str, bool)

    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.channelId = row.channel.id
        self.tile = IconTile(self, size=36, icon_size=18)
        self.tile.setIcon(icon_of(row.channel.icon), "neutral")
        self.nameLabel = StrongBodyLabel(tr(row.channel.name), self)
        self.statusIcon = IconWidget(self)
        self.statusIcon.setFixedSize(12, 12)
        self.statusLabel = CaptionLabel(self)
        self.statusLabel.setWordWrap(True)
        self.testButton = PushButton(FluentIcon.SEND, tr("测试"), self)
        self.editButton = PushButton(FluentIcon.EDIT, tr("编辑"), self)
        self.removeButton = ToolButton(FluentIcon.DELETE, self)
        self.removeButton.setToolTip(tr("删除渠道"))
        self.switch = bare_switch(self)
        status = QHBoxLayout()
        status.setSpacing(4)
        status.addWidget(self.statusIcon, 0, Qt.AlignmentFlag.AlignTop)
        status.addWidget(self.statusLabel, 1)
        column = QVBoxLayout()
        column.setSpacing(2)
        column.addWidget(self.nameLabel)
        column.addLayout(status)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)
        layout.addWidget(self.tile)
        layout.addLayout(column, 1)
        layout.addWidget(self.testButton)
        layout.addWidget(self.editButton)
        layout.addWidget(self.removeButton)
        layout.addSpacing(6)
        layout.addWidget(self.switch)
        self.testButton.clicked.connect(lambda: self.testRequested.emit(self.channelId))
        self.editButton.clicked.connect(lambda: self.editRequested.emit(self.channelId))
        self.removeButton.clicked.connect(lambda: self.removeRequested.emit(self.channelId))
        self.switch.checkedChanged.connect(lambda on: self.enableRequested.emit(self.channelId, on))
        self.setRow(row)

    def setRow(self, row):
        self.row = row
        self.switch.blockSignals(True)
        self.switch.setChecked(bool(row.enabled))
        self.switch.blockSignals(False)
        last = row.last
        if last is None:
            kind, icon, text = "neutral", None, row.summary
        elif last.success:
            when = _delivery_time(last.at)
            kind, icon = "success", FluentIcon.ACCEPT
            text = tr("上次发送成功") + (f" · {when}" if when else "")
        else:
            kind, icon = "error", FluentIcon.INFO
            text = tr("上次发送失败：{reason}").format(reason=last.reason)
        if not row.enabled:
            kind = "neutral"
            text = tr("已停用") + (f" · {text}" if text else "")
        color = tone(kind)[1] if kind != "neutral" else text_color(secondary=True)
        self.statusLabel.setTextColor(color, color)
        self.statusLabel.setText(text)
        self.statusLabel.setToolTip(text)
        self.statusIcon.setVisible(icon is not None)
        if icon is not None:
            self.statusIcon.setIcon(icon.icon(color=color))

    def setTesting(self, testing):
        self.testButton.setEnabled(not testing)
        self.testButton.setText(tr("正在测试") if testing else tr("测试"))


class ProviderTile(QWidget):
    clicked = Signal(str)

    def __init__(self, key, icon, text, parent=None, *, accentText=False):
        super().__init__(parent)
        self.key = key
        self._icon = icon
        self._text = text
        self._added = False
        self._hover = False
        self._accent = accentText
        self.setFixedHeight(70)
        self.setMinimumWidth(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setAdded(self, added):
        self._added = bool(added)
        self.setToolTip(tr("已添加，点击编辑") if added else "")
        self.update()

    def setText(self, text):
        self._text = text
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self.key)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(border_color(), 1))
        painter.setBrush(surface_color(self._hover))
        painter.drawRoundedRect(rect, 6, 6)
        if self._added:
            painter.setOpacity(0.55)
        color = accent(is_evernight()) if self._accent else text_color()
        size = 20
        self._icon.icon(color=color).paint(painter, int((self.width() - size) / 2), 14, size, size)
        painter.setPen(color)
        painter.setFont(getFont(12))
        painter.drawText(QRectF(4, 40, self.width() - 8, 20), Qt.AlignmentFlag.AlignCenter,
                         painter.fontMetrics().elidedText(self._text, Qt.TextElideMode.ElideRight, self.width() - 8))
        if self._added:
            painter.setOpacity(1)
            painter.setFont(getFont(10))
            painter.setPen(tone("success")[1])
            painter.drawText(QRectF(0, 4, self.width() - 6, 14), Qt.AlignmentFlag.AlignRight, tr("已添加"))


class ChannelPanel(QWidget):
    """已添加的渠道列表和添加渠道的图标格。"""

    def __init__(self, window, model, parent=None):
        super().__init__(parent)
        self.window_, self.model = window, model
        self._expanded = False
        self._pendingTests = set()
        self.rows = {}
        self.tiles = {}
        self.listCard = SimpleCardWidget(self)
        self.listCard.setBorderRadius(6)
        self.listLayout = QVBoxLayout(self.listCard)
        self.listLayout.setContentsMargins(0, 2, 0, 2)
        self.listLayout.setSpacing(0)
        self.emptyLabel = secondary(BodyLabel(
            tr("还没有添加渠道。从下面选一个你常用的，填好后点「测试」确认能收到。"), self.listCard))
        self.emptyLabel.setWordWrap(True)
        self.emptyLabel.setContentsMargins(16, 14, 16, 14)
        self.addTitle = StrongBodyLabel(tr("添加渠道"), self)
        self.gridCard = SimpleCardWidget(self)
        self.gridCard.setBorderRadius(6)
        self.grid = QGridLayout(self.gridCard)
        self.grid.setContentsMargins(12, 12, 12, 12)
        self.grid.setSpacing(8)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.listCard)
        layout.addSpacing(10)
        layout.addWidget(self.addTitle)
        layout.addWidget(self.gridCard)
        model.changed.connect(self.refresh)
        model.testFinished.connect(self._tested)
        qconfig.themeChanged.connect(self._themeChanged)
        self.refresh()

    def _clearList(self):
        while self.listLayout.count():
            widget = self.listLayout.takeAt(0).widget()
            if widget is not None and widget is not self.emptyLabel:
                widget.hide()
                widget.deleteLater()

    def refresh(self):
        rows = self.model.added()
        self._clearList()
        self.rows = {}
        for index, row in enumerate(rows):
            if index:
                self.listLayout.addWidget(Divider(self.listCard, inset=64))
            widget = ChannelRow(row, self.listCard)
            widget.testRequested.connect(self._test)
            widget.editRequested.connect(self._edit)
            widget.removeRequested.connect(self._remove)
            widget.enableRequested.connect(self._enable)
            widget.setTesting(row.channel.id in self._pendingTests)
            self.rows[row.channel.id] = widget
            self.listLayout.addWidget(widget)
        self.emptyLabel.setVisible(not rows)
        if not rows:
            self.listLayout.addWidget(self.emptyLabel)
        self._refreshTiles({row.channel.id for row in rows})

    def _refreshTiles(self, added):
        for tile in self.tiles.values():
            self.grid.removeWidget(tile)
            tile.hide()
            tile.deleteLater()
        self.tiles = {}
        channels = list(self.model.available())
        hidden = max(0, len(channels) - VISIBLE_TILES)
        shown = channels if self._expanded or hidden <= 1 else channels[:VISIBLE_TILES]
        for index, channel in enumerate(shown):
            tile = ProviderTile(channel.id, icon_of(channel.icon), tr(channel.name), self.gridCard)
            tile.setAdded(channel.id in added)
            tile.clicked.connect(self._edit)
            self.tiles[channel.id] = tile
            self.grid.addWidget(tile, index // 6, index % 6)
            tile.show()
        if hidden > 1:
            text = tr("收起") if self._expanded else tr("更多 {count} 个").format(count=hidden)
            more = ProviderTile("__more__", FluentIcon.UP if self._expanded else FluentIcon.ADD, text,
                                self.gridCard, accentText=True)
            more.clicked.connect(self._toggleMore)
            self.tiles["__more__"] = more
            index = len(shown)
            self.grid.addWidget(more, index // 6, index % 6)

    def _toggleMore(self, *_):
        self._expanded = not self._expanded
        self._refreshTiles({row.channel.id for row in self.model.added()})

    def _themeChanged(self, *_):
        for widget in self.rows.values():
            widget.setRow(widget.row)

    def _test(self, channel_id):
        if self.model.test(channel_id, {}):
            self._pendingTests.add(channel_id)
            if channel_id in self.rows:
                self.rows[channel_id].setTesting(True)

    def _tested(self, channel_id, success, message):
        if channel_id not in self._pendingTests:
            return
        self._pendingTests.discard(channel_id)
        if channel_id in self.rows:
            self.rows[channel_id].setTesting(False)
        name = tr(CHANNEL_BY_ID[channel_id].name)
        if success:
            InfoBar.success(tr("{name} 测试消息已发出").format(name=name), tr("请到对应应用里确认是否收到"),
                            duration=3000, parent=self.window_)
        else:
            InfoBar.error(tr("{name} 测试失败").format(name=name), message, duration=6000, parent=self.window_)

    def _edit(self, channel_id):
        dialog = ChannelDialog(self.model, channel_id, self.window_)
        dialog.exec()
        dialog.deleteLater()

    def _remove(self, channel_id):
        channel = CHANNEL_BY_ID[channel_id]
        name = tr(channel.name)
        text = tr("填写的内容会一起清除，以后要用得重新填写。") if channel.fields else tr("以后要用可以重新添加。")
        text += "\n" + tr("只是暂时不用的话，关掉开关就行。")
        box = MessageBox(tr("删除渠道「{name}」？").format(name=name), text, self.window_)
        box.yesButton.setText(tr("删除渠道"))
        box.cancelButton.setText(tr("取消"))
        add_mascot(box, Mascot.BOX)
        box.cancelButton.setFocus()
        confirmed = box.exec()
        box.deleteLater()
        if not confirmed:
            return
        errors = self.model.remove(channel_id)
        if errors:
            InfoBar.error(tr("无法删除这个渠道"), "\n".join(errors.values()), duration=5000, parent=self.window_)
        else:
            InfoBar.success(tr("已删除"), name, duration=2500, parent=self.window_)

    def _enable(self, channel_id, enabled):
        errors = self.model.set_enabled(channel_id, enabled)
        if errors:
            InfoBar.error(tr("无法启用这个渠道") if enabled else tr("无法停用这个渠道"), "\n".join(errors.values()),
                          duration=5000, parent=self.window_)
            self.refresh()

    def locateWidget(self, channel_id):
        if channel_id in self.rows:
            return self.rows[channel_id]
        if channel_id not in self.tiles and not self._expanded:
            self._toggleMore()
        return self.tiles.get(channel_id)

    def enabledCount(self):
        return sum(1 for row in self.model.added() if row.enabled)


class ChannelDialog(MessageBoxBase):
    """添加或编辑一个渠道：字段表单、发送测试，保存前逐项校验。"""

    def __init__(self, model, channel_id, parent=None):
        super().__init__(parent)
        self.model, self.channelId = model, channel_id
        self.channel = channel = CHANNEL_BY_ID[channel_id]
        values = model.form(channel_id)
        added = channel_id in {row.channel.id for row in model.added()}
        self.editors, self.errors = {}, {}
        tile = IconTile(self.widget, size=36, icon_size=18)
        tile.setIcon(icon_of(channel.icon), "accent", evernight=is_evernight())
        title = SubtitleLabel((tr("编辑 {name}") if added else tr("添加 {name}")).format(name=tr(channel.name)), self.widget)
        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(tile)
        header.addWidget(title, 1)
        if channel.tutorial:
            tutorial = LinkButton(tr("查看教程"), self.widget, size=13)
            tutorial.setEvernight(is_evernight())
            tutorial.clicked.connect(lambda: self.model.tutorial(channel_id))
            header.addWidget(tutorial)
        self.viewLayout.addLayout(header)
        if channel.description:
            description = secondary(CaptionLabel(tr(channel.description), self.widget))
            description.setWordWrap(True)
            self.viewLayout.addWidget(description)
        form = QWidget()
        formLayout = QVBoxLayout(form)
        formLayout.setContentsMargins(0, 4, 8, 4)
        formLayout.setSpacing(12)
        if not channel.fields:
            formLayout.addWidget(secondary(BodyLabel(tr("这个渠道不需要填写任何内容。"), form)))
        for field in channel.fields:
            formLayout.addLayout(self._field(field, values.get(field.key), form))
        if channel_id == "qqbot":
            bind = QHBoxLayout()
            for mode, text in (("user", tr("自动绑定单聊用户")), ("group", tr("自动绑定群聊"))):
                button = PushButton(FluentIcon.SYNC, text, form)
                button.clicked.connect(lambda _=False, m=mode: self.model.bind_qq(m, self.draft()))
                bind.addWidget(button)
            bind.addStretch(1)
            formLayout.addLayout(bind)
        formLayout.addStretch(1)
        scroll = ScrollArea(self.widget)
        form.setObjectName("view")
        form.setStyleSheet("#view{background: transparent}")
        scroll.setWidget(form)
        scroll.setWidgetResizable(True)
        scroll.enableTransparentBackground()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form.adjustSize()
        scroll.setFixedHeight(min(400, max(80, form.sizeHint().height() + 8)))
        self.viewLayout.addWidget(scroll)
        self.formError = CaptionLabel(self.widget)
        self.formError.setWordWrap(True)
        self.formError.hide()
        self.viewLayout.addWidget(self.formError)
        test = QHBoxLayout()
        test.setSpacing(10)
        self.testButton = PushButton(FluentIcon.SEND, tr("发送测试"), self.widget)
        self.testButton.clicked.connect(self._test)
        self.testResult = CaptionLabel(self.widget)
        self.testResult.setWordWrap(True)
        test.addWidget(self.testButton)
        test.addWidget(self.testResult, 1)
        self.viewLayout.addLayout(test)
        self.yesButton.setText(tr("保存"))
        style_primary(self.yesButton, is_evernight())
        self.cancelButton.setText(tr("取消"))
        self.widget.setMinimumWidth(540)
        model.testFinished.connect(self._tested)
        model.bound.connect(self._bound)

    def _field(self, field, value, parent):
        layout = QVBoxLayout()
        layout.setSpacing(4)
        label = BodyLabel(tr(field.label) + (" *" if field.required else ""), parent)
        kind = field.kind
        if kind == "switch":
            editor = bare_switch(parent)
            editor.setChecked(bool(value))
            row = QHBoxLayout()
            row.addWidget(label, 1)
            row.addWidget(editor)
            layout.addLayout(row)
        else:
            if kind == "secret" and not field.kind == "multiline":
                editor = PasswordLineEdit(parent)
                editor.setText("" if value is None else str(value))
            elif kind == "choice":
                editor = ComboBox(parent)
                editor.addItems([str(choice) for choice in field.choices])
                if value is not None and str(value) in field.choices:
                    editor.setCurrentText(str(value))
            elif kind == "multiline":
                editor = PlainTextEdit(parent)
                text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) if value else ""
                editor.setPlainText(text)
                editor.setFixedHeight(96)
            else:
                editor = LineEdit(parent)
                editor.setText("" if value is None else str(value))
            if field.placeholder and hasattr(editor, "setPlaceholderText"):
                editor.setPlaceholderText(tr(field.placeholder))
            layout.addWidget(label)
            layout.addWidget(editor)
        if field.description:
            description = secondary(CaptionLabel(tr(field.description), parent))
            description.setWordWrap(True)
            layout.addWidget(description)
        error = CaptionLabel(parent)
        error.setWordWrap(True)
        error.hide()
        layout.addWidget(error)
        self.editors[field.key] = (field, editor)
        self.errors[field.key] = error
        return layout

    def draft(self):
        values = {}
        for key, (field, editor) in self.editors.items():
            if field.kind == "switch":
                values[key] = editor.isChecked()
            elif field.kind == "choice":
                values[key] = editor.currentText()
            elif field.kind == "multiline":
                values[key] = editor.toPlainText()
            else:
                values[key] = editor.text().strip()
        return values

    def _showErrors(self, errors):
        color = tone("error")[1]
        for key, label in self.errors.items():
            message = errors.get(key, "")
            label.setTextColor(color, color)
            label.setText(message)
            label.setVisible(bool(message))
        general = errors.get("", "") or "\n".join(m for k, m in errors.items() if k and k not in self.errors)
        self.formError.setTextColor(color, color)
        self.formError.setText(general)
        self.formError.setVisible(bool(general))

    def validate(self):
        errors = self.model.save(self.channelId, self.draft())
        self._showErrors(errors or {})
        return not errors

    def _test(self):
        self._showErrors({})
        if self.model.test(self.channelId, self.draft()):
            self.testButton.setEnabled(False)
            secondary(self.testResult)
            self.testResult.setText(tr("正在发送测试消息……"))

    def _tested(self, channel_id, success, message):
        if channel_id != self.channelId:
            return
        self.testButton.setEnabled(True)
        color = tone("success" if success else "error")[1]
        self.testResult.setTextColor(color, color)
        self.testResult.setText(tr("测试消息已发出，请确认是否收到") if success else message)

    def _bound(self, success, key, value):
        if success and key in self.editors:
            self.editors[key][1].setText(value)
        elif not success:
            color = tone("error")[1]
            self.formError.setTextColor(color, color)
            self.formError.setText(value)
            self.formError.show()
