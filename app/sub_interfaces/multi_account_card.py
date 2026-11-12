from html import escape

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLayout,
    QLabel, QTableWidgetItem, QVBoxLayout, QWidget,
)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import LineEdit, PushButton, ScrollArea, TableWidget, ToolButton

from app.card.expandable_switch_setting_card import ExpandableSwitchSettingCard
from app.common.icon import UiIcon
from module.config import cfg
from module.config.accounts import add_account, profile_path
from module.localization import tr
from utils.desktop import open_path


class AccountTable(TableWidget):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.FocusIn and obj.property("account_row") is not None:
            return False
        return super().eventFilter(obj, event)


class MultiAccountCard(ExpandableSwitchSettingCard):
    sizeChanged = Signal()
    configureRequested = Signal(object)
    accountHelpRequested = Signal()

    def __init__(self, parent=None):
        super().__init__("multi_account_enable", UiIcon.PEOPLE_SWAP,
                         tr("启用多账号自动运行"), parent=parent)
        self.viewLayout.setContentsMargins(16, 8, 16, 16)

        self.details = QWidget(self.view)
        details = QVBoxLayout(self.details)
        details.setContentsMargins(0, 8, 0, 0)
        self.accountScrollArea = ScrollArea(self.details)
        self.accountScrollArea.setWidgetResizable(True)
        self.accountScrollArea.setFixedHeight(320)
        self.accountScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.accountScrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.accountScrollArea.setStyleSheet("QScrollArea { background: transparent; }")
        self.accountScrollWidget = QWidget()
        self.accountScrollLayout = QVBoxLayout(self.accountScrollWidget)
        self.accountScrollLayout.setContentsMargins(0, 0, 12, 0)
        self.accountScrollLayout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.accountScrollLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.accountScrollArea.setWidget(self.accountScrollWidget)
        self.accountScrollWidget.setAutoFillBackground(False)
        details.addWidget(self.accountScrollArea)
        self.table = AccountTable(self)
        self.table.setMouseTracking(False)
        self.table.entered.disconnect()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([tr("启用"), tr("备注"), tr("账号ID"), "UID"])
        self.table.verticalHeader().hide()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.accountScrollLayout.addWidget(self.table)
        self.pathLabel = QLabel(self)
        self.pathLabel.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.pathLabel.setWordWrap(True)
        self.pathLabel.linkActivated.connect(self._open_profile_location)
        details.addWidget(self.pathLabel)
        buttons = QHBoxLayout()
        self.addButton = ToolButton(FIF.ADD, self)
        self.addButton.setToolTip(tr("添加账号"))
        self.addButton.setAccessibleName(tr("添加账号"))
        self.removeButton = ToolButton(FIF.REMOVE, self)
        self.removeButton.setToolTip(tr("删除账号"))
        self.removeButton.setAccessibleName(tr("删除账号"))
        self.configureButton = PushButton(tr("配置选中账号的任务"), self)
        buttons.addWidget(self.addButton)
        buttons.addWidget(self.removeButton)
        buttons.addStretch()
        buttons.addWidget(self.configureButton)
        details.addLayout(buttons)
        self.accountScrollLayout.addSpacing(8)
        self.helpLink = QLabel(f'<a href="account-help">{tr("查看账号管理教程")}</a>', self)
        self.helpLink.linkActivated.connect(lambda _: self.accountHelpRequested.emit())
        self.accountScrollLayout.addWidget(self.helpLink)
        self.accountScrollLayout.addStretch()
        self.viewLayout.addWidget(self.details)
        self.accounts = cfg.get_value("multi_accounts", [])
        self._populate()
        self.table.itemChanged.connect(self._save)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.addButton.clicked.connect(self._add)
        self.removeButton.clicked.connect(self._remove)
        self.configureButton.clicked.connect(self._configure)
        self.expandAni.valueChanged.connect(lambda _: self.sizeChanged.emit())

    def _populate(self):
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.accounts))
        for row, account in enumerate(self.accounts):
            if row == 0:
                name_placeholder = tr("三月七")
            elif row == 1:
                name_placeholder = tr("长夜月")
            else:
                name_placeholder = tr("账号{number}").format(number=row + 1)
            placeholders = (name_placeholder, tr("账号ID(必填)"), "UID")
            enabled = QTableWidgetItem()
            enabled.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            enabled.setCheckState(Qt.CheckState.Checked if account["enabled"] else Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, enabled)
            for column, key in enumerate(("name", "login_name", "uid"), 1):
                item = QTableWidgetItem(str(account[key]))
                item.setForeground(Qt.GlobalColor.transparent)
                self.table.setItem(row, column, item)
                editor = LineEdit(self.table)
                editor.setText(str(account[key]))
                editor.setPlaceholderText(placeholders[column - 1])
                editor.setProperty("account_row", row)
                editor.installEventFilter(self)
                editor.editingFinished.connect(
                    lambda r=row, c=column, field=editor: self.table.item(r, c).setText(field.text().strip()))
                self.table.setCellWidget(row, column, editor)
        self.table.blockSignals(False)
        row_count = max(len(self.accounts), 1)
        table_height = (self.table.horizontalHeader().sizeHint().height()
                        + row_count * self.table.verticalHeader().defaultSectionSize()
                        + self.table.frameWidth() * 2 + 4)
        self.table.setFixedHeight(table_height)
        self._selection_changed()

    def _selection_changed(self):
        selected = self.table.currentRow() >= 0
        self.removeButton.setEnabled(selected)
        self.configureButton.setEnabled(selected)
        if selected:
            account = self.accounts[self.table.currentRow()]
            path = profile_path(account).resolve()
            link = f'<a href="{escape(path.parent.as_uri())}">{escape(str(path))}</a>'
            self.pathLabel.setText(tr("配置文件：{path}").format(path=link))
        else:
            self.pathLabel.clear()
        self._update_height()

    def _update_height(self):
        self.accountScrollLayout.activate()
        self.accountScrollArea.setFixedHeight(min(self.accountScrollLayout.sizeHint().height(), 320))
        self.details.layout().activate()
        self.details.updateGeometry()
        self.viewLayout.invalidate()
        self.viewLayout.activate()
        self._adjustViewSize()
        self.sizeChanged.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._update_height()

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
                and obj.property("account_row") is not None):
            self.table.selectRow(obj.property("account_row"))
        return super().eventFilter(obj, event)

    def _open_profile_location(self):
        account = self.accounts[self.table.currentRow()]
        open_path(profile_path(account).resolve().parent)

    def _save(self):
        for row, account in enumerate(self.accounts):
            account["enabled"] = self.table.item(row, 0).checkState() == Qt.CheckState.Checked
            for column, key in enumerate(("name", "login_name", "uid"), 1):
                account[key] = self.table.item(row, column).text().strip()
        cfg.set_value("multi_accounts", self.accounts)

    def _add(self):
        self.accounts.append(add_account(cfg))
        self._populate()
        self.table.selectRow(len(self.accounts) - 1)
        self._save()
        self.table.cellWidget(len(self.accounts) - 1, 1).setFocus()
        self.accountScrollArea.ensureWidgetVisible(self.table.cellWidget(len(self.accounts) - 1, 1), 0, 8)

    def _remove(self):
        account = self.accounts.pop(self.table.currentRow())
        self._populate()
        self._save()
        profile_path(account).unlink(missing_ok=True)

    def _configure(self):
        row = self.table.currentRow()
        for column in (1, 2, 3):
            field = self.table.cellWidget(row, column)
            self.table.item(row, column).setText(field.text().strip())
        account = dict(self.accounts[row])
        account['display_name'] = (account['name'] or account['login_name'] or account['uid']
                                   or self.table.cellWidget(row, 1).placeholderText())
        self.configureRequested.emit(account)
