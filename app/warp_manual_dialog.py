"""A separate, modeless editor. Every explicit Save persists one atomic snapshot."""
from copy import deepcopy
import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLabel, QWidget, QTabWidget, QTableWidgetItem,
                               QAbstractItemView, QHeaderView)
from qfluentwidgets import (LineEdit, ComboBox, SpinBox, PushButton,
                            PrimaryPushButton, TableWidget, MessageBox, FlowLayout,
                            isDarkTheme, qconfig)

from module.localization import tr
from .tools.warp_import import read_snapshot, edit_plan, save_import
from .tools.warp_manual import (MANUAL_KEY, empty_manual, manual_data, new_entry,
                                pool_names, gold_rows, record_identity, manual_count)


class WarpManualDialog(QDialog):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(tr('手动补充与更正'))
        self.resize(880, 760)
        self.setMinimumSize(540, 620)
        self._apply_theme()
        qconfig.themeChanged.connect(self._apply_theme)
        self.original, self.data = read_snapshot()
        if self.data and (self.data.get('march7th_cleared') or (not self.data['list'] and not manual_count(self.data))):
            self.data = None
        self.edit_key = None
        self._closing = False
        self._correction_baseline = 0
        self._status_state = 'hint'
        self.names = pool_names()
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        account = QHBoxLayout()
        self.uidLabel = QLabel(tr('账号 UID'), self)
        account.addWidget(self.uidLabel)
        self.uidEdit = LineEdit(self)
        self.uidEdit.setPlaceholderText(tr('请输入游戏内 UID，避免混入其他账号'))
        if self.data:
            self.uidEdit.setText(self.data['info']['uid'])
            self.uidEdit.setReadOnly(True)
        account.addWidget(self.uidEdit, 1)
        root.addLayout(account)
        self.introLabel = self._note(tr('记不清的抽数或时间可以留为未知。'))
        root.addWidget(self.introLabel)
        self.tabs = QTabWidget(self)
        root.addWidget(self.tabs, 1)
        self._build_manual()
        self._build_corrections()
        self.statusLabel = self._note(tr('每次保存立即生效；关闭窗口不会撤销已保存的内容。'))
        root.addWidget(self.statusLabel)
        footer = QHBoxLayout()
        footer.addStretch()
        self.closeBtn = PushButton(tr('关闭'), self)
        self.closeBtn.setAutoDefault(False)
        self.closeBtn.clicked.connect(self.close)
        footer.addWidget(self.closeBtn)
        root.addLayout(footer)
        self._form_baseline = self._form_value()
        self._refresh()

    def _apply_theme(self):
        background, text, border = ('#202020', '#ffffff', '#555555') if isDarkTheme() else ('#fafafa', '#202020', '#cccccc')
        self.setStyleSheet(
            f'QDialog {{background: {background}; color: {text};}} QLabel {{color: {text};}}'
            f'QTabWidget::pane {{border: 1px solid {border}; background: {background};}}'
            f'QTabBar::tab {{background: {background}; color: {text}; padding: 6px 12px;}}'
            'QTabBar::tab:selected {border-bottom: 2px solid #009faa;}')

    def _note(self, text):
        label = QLabel(text, self)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setMinimumWidth(0)
        return label

    def _table(self, headers):
        table = TableWidget(self)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setMinimumHeight(130)
        return table

    def _buttons(self, layout, specs):
        container = QWidget(self)
        flow = FlowLayout(container)
        flow.setContentsMargins(0, 0, 0, 0)
        for attr, text, slot, primary in specs:
            button = (PrimaryPushButton if primary else PushButton)(text, container)
            button.setAutoDefault(False)
            button.clicked.connect(slot)
            setattr(self, attr, button)
            flow.addWidget(button)
        layout.addWidget(container)

    def _build_manual(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        self.manualHelp = self._note(tr('有日期时按日期排序；无日期时按列表顺序排在已有明细之前。'))
        layout.addWidget(self.manualHelp)
        form = self.manualForm = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.poolBox = ComboBox(page)
        for pool, name in self.names.items():
            self.poolBox.addItem(name, userData=pool)
        self.nameEdit = LineEdit(page)
        self.nameEdit.setPlaceholderText(tr('填写五星角色或光锥名称'))
        self.pitySpin = SpinBox(page)
        self.pitySpin.setRange(0, 1000000)
        self.pitySpin.setSpecialValueText(tr('未知'))
        self.dateEdit = LineEdit(page)
        self.dateEdit.setPlaceholderText(tr('YYYY-MM-DD，留空表示未知'))
        form.addRow(tr('卡池'), self.poolBox)
        form.addRow(tr('五星物品'), self.nameEdit)
        form.addRow(tr('出金抽数'), self.pitySpin)
        form.addRow(tr('时间（可不填）'), self.dateEdit)
        layout.addLayout(form)
        self._buttons(layout, [
            ('saveBtn', tr('添加并继续'), self._save_entry, True),
            ('resetBtn', tr('取消编辑'), self._reset_form, False),
        ])
        self.manualTable = self._table([tr('顺序'), tr('卡池'), tr('名称'), tr('出金抽数'), tr('时间')])
        self.manualTable.setColumnWidth(0, 65)
        self.manualTable.setColumnWidth(1, 190)
        self.manualTable.setColumnWidth(2, 160)
        self.manualTable.setColumnWidth(3, 110)
        self.manualTable.itemDoubleClicked.connect(lambda _: self._edit_selected())
        self.manualTable.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.manualTable, 1)
        self._buttons(layout, [
            ('editBtn', tr('编辑'), self._edit_selected, False),
            ('deleteBtn', tr('删除'), self._delete_selected, False),
            ('upBtn', tr('上移'), lambda: self._move(-1), False),
            ('downBtn', tr('下移'), lambda: self._move(1), False),
        ])
        self.tabs.addTab(page, tr('手动补充'))

    def _build_corrections(self):
        page = QWidget(self)
        layout = QVBoxLayout(page)
        self.correctionHelp = self._note(tr('只更正已有五星的出金抽数，不修改或删除原始记录。首个五星的原始抽数可能只是历史截断后的下限。'))
        layout.addWidget(self.correctionHelp)
        self.realTable = self._table([tr('卡池'), tr('名称'), tr('时间'), tr('原始抽数'), tr('更正后')])
        self.realTable.setColumnWidth(0, 170)
        self.realTable.setColumnWidth(1, 135)
        self.realTable.setColumnWidth(2, 165)
        self.realTable.setColumnWidth(3, 100)
        self.realTable.itemSelectionChanged.connect(self._real_selection_changed)
        layout.addWidget(self.realTable, 1)
        self.realNote = self._note('')
        layout.addWidget(self.realNote)
        form = self.correctionForm = QFormLayout()
        self.correctionSpin = SpinBox(page)
        self.correctionSpin.setRange(0, 1000000)
        self.correctionSpin.setSpecialValueText(tr('未知'))
        form.addRow(tr('更正为'), self.correctionSpin)
        layout.addLayout(form)
        self._buttons(layout, [
            ('correctBtn', tr('保存更正'), self._correct, True),
            ('undoBtn', tr('撤销更正'), self._undo, False),
        ])
        self.tabs.addTab(page, tr('已有五星抽数'))

    def _manual(self):
        return manual_data(self.data) if self.data else empty_manual()

    def retranslateUi(self):
        """Change labels, never reload disk or discard an unfinished edit."""
        self.setWindowTitle(tr('手动补充与更正'))
        self.uidLabel.setText(tr('账号 UID'))
        self.uidEdit.setPlaceholderText(tr('请输入游戏内 UID，避免混入其他账号'))
        self.introLabel.setText(tr('记不清的抽数或时间可以留为未知。'))
        self.manualHelp.setText(tr('有日期时按日期排序；无日期时按列表顺序排在已有明细之前。'))
        self.correctionHelp.setText(tr('只更正已有五星的出金抽数，不修改或删除原始记录。首个五星的原始抽数可能只是历史截断后的下限。'))
        self.tabs.setTabText(0, tr('手动补充'))
        self.tabs.setTabText(1, tr('已有五星抽数'))
        self.nameEdit.setPlaceholderText(tr('填写五星角色或光锥名称'))
        self.dateEdit.setPlaceholderText(tr('YYYY-MM-DD，留空表示未知'))
        self.pitySpin.setSpecialValueText(tr('未知'))
        self.correctionSpin.setSpecialValueText(tr('未知'))
        for field, text in [(self.poolBox, tr('卡池')), (self.nameEdit, tr('五星物品')),
                            (self.pitySpin, tr('出金抽数')), (self.dateEdit, tr('时间（可不填）'))]:
            self.manualForm.labelForField(field).setText(text)
        self.correctionForm.labelForField(self.correctionSpin).setText(tr('更正为'))
        self.manualTable.setHorizontalHeaderLabels([tr('顺序'), tr('卡池'), tr('名称'), tr('出金抽数'), tr('时间')])
        self.realTable.setHorizontalHeaderLabels([tr('卡池'), tr('名称'), tr('时间'), tr('原始抽数'), tr('更正后')])
        for button, text in [(self.saveBtn, tr('保存修改') if self.edit_key else tr('添加并继续')),
                             (self.resetBtn, tr('取消编辑')), (self.editBtn, tr('编辑')),
                             (self.deleteBtn, tr('删除')), (self.upBtn, tr('上移')),
                             (self.downBtn, tr('下移')), (self.correctBtn, tr('保存更正')),
                             (self.undoBtn, tr('撤销更正')), (self.closeBtn, tr('关闭'))]:
            button.setText(text)
        if self._status_state == 'hint':
            self.statusLabel.setText(tr('每次保存立即生效；关闭窗口不会撤销已保存的内容。'))
        elif self._status_state == 'saved':
            self.statusLabel.setText(tr('已保存。可继续添加，或关闭窗口查看统计。'))
        pool = self.poolBox.currentData()
        self.names = pool_names()
        self.poolBox.clear()
        for key, name in self.names.items():
            self.poolBox.addItem(name, userData=key)
        self.poolBox.setCurrentIndex(self.poolBox.findData(pool))
        correction = self.correctionSpin.value()
        self._refresh()
        self.correctionSpin.setValue(correction)

    def _refresh(self):
        pending = self.correctionSpin.value()
        pending_changed = pending != self._correction_baseline
        previous_row = self.realTable.currentRow()
        previous_id = (self.real_rows[previous_row]['record']['id']
                       if hasattr(self, 'real_rows') and 0 <= previous_row < len(self.real_rows) else None)
        previous_baseline = self._correction_baseline
        entries = self._manual()['entries']
        self.manualTable.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [str(row + 1), self.names[entry['pool']], entry['name'],
                      str(entry['pity']) if entry['pity'] else tr('未知'), entry['date'] or tr('未知')]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.manualTable.setItem(row, col, cell)
        self.real_rows = gold_rows(self.data, include_orphans=True) if self.data else []
        self.realTable.setRowCount(len(self.real_rows))
        for row, item in enumerate(self.real_rows):
            record = item['record']
            observed = tr('原记录已变化') if item['orphan'] else ('≥' if item['bounded'] else '') + str(item['observed'])
            corrected = (str(item['pity']) if item['pity'] else tr('未知')) + ' · ' + tr('手填') if item['corrected'] else '—'
            for col, value in enumerate([self.names[record['gacha_type']], record['name'], record['time'], observed, corrected]):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                self.realTable.setItem(row, col, cell)
        self._selection_changed()
        self._real_selection_changed()
        row = self.realTable.currentRow()
        if (pending_changed and 0 <= row < len(self.real_rows)
                and self.real_rows[row]['record']['id'] == previous_id
                and self._correction_baseline == previous_baseline):
            self.correctionSpin.setValue(pending)

    def _selection_changed(self):
        row = self.manualTable.currentRow()
        selected = 0 <= row < len(self._manual()['entries'])
        for button in (self.editBtn, self.deleteBtn):
            button.setEnabled(selected)
        self.upBtn.setEnabled(selected and row > 0)
        self.downBtn.setEnabled(selected and row < len(self._manual()['entries']) - 1)

    def _real_selection_changed(self):
        row = self.realTable.currentRow()
        item = self.real_rows[row] if 0 <= row < len(self.real_rows) else None
        self.correctBtn.setEnabled(item is not None and not item['orphan'])
        self.undoBtn.setEnabled(item is not None and item['corrected'])
        self.correctionSpin.setEnabled(item is not None and not item['orphan'])
        self.correctionSpin.setValue((item['pity'] or 0) if item else 0)
        self._correction_baseline = self.correctionSpin.value()
        if item and item['orphan']:
            note = tr('原始记录已变化，此更正未参与统计。可撤销后重新核对。')
        elif item:
            observed = ('≥' if item['bounded'] else '') + str(item['observed'])
            effective = (str(item['pity']) if item['pity'] else tr('未知')) if item['corrected'] else '—'
            note = (item['record']['name'] + ' · ' + item['record']['time'] + '\n'
                    + tr('原始抽数') + ': ' + observed + ' · ' + tr('更正后') + ': ' + effective)
        else:
            note = tr('选择一条五星记录后更正；没有明细时，仍可在“手动补充”中添加。')
        self.realNote.setText(note)

    def _form_value(self):
        return (self.poolBox.currentData(), self.nameEdit.text(), self.pitySpin.value(), self.dateEdit.text())

    def _confirm_discard(self):
        if self._form_value() == self._form_baseline and self.correctionSpin.value() == self._correction_baseline:
            return True
        return self._confirm(tr('放弃未保存的填写内容？'), tr('已经保存的内容不会受影响。'))

    def _confirm(self, title, text):
        box = MessageBox(title, text, self)
        box.yesButton.setText(tr('确认'))
        box.cancelButton.setText(tr('取消'))
        box.cancelButton.setFocus()
        return bool(box.exec())

    def _reset_form(self, checked=False, force=False):
        if not force and not self._confirm_discard():
            return
        self.edit_key = None
        self.nameEdit.clear()
        self.pitySpin.setValue(0)
        self.dateEdit.clear()
        self.saveBtn.setText(tr('添加并继续'))
        self._form_baseline = self._form_value()
        self.nameEdit.setFocus()

    def _persist(self, manual):
        try:
            if not self.data and not (self.uidEdit.text().strip().isascii() and self.uidEdit.text().strip().isdigit()):
                raise ValueError(tr('请输入游戏内 UID，避免混入其他账号'))
            data = deepcopy(self.data) if self.data else {
                'info': {'uid': self.uidEdit.text().strip(), 'lang': 'zh-cn',
                         'region_time_zone': 8, 'srgf_version': 'v1.0'}, 'list': []}
            data[MANUAL_KEY] = manual
            plan = edit_plan(data, self.original)
            save_import(plan)
            self.data = plan.data
            # Use the bytes we wrote, not a newer writer's snapshot/account.
            self.original = json.dumps(plan.data, ensure_ascii=False, indent=4).encode('utf-8')
            if not self.data['list'] and not manual_count(self.data):
                self.data = None
            self.uidEdit.setReadOnly(self.data is not None)
            self._status_state = 'saved'
            self.statusLabel.setText(tr('已保存。可继续添加，或关闭窗口查看统计。'))
            self._refresh()
            self.changed.emit()
            return True
        except Exception as exc:
            self._status_state = None
            self.statusLabel.setText(str(exc))
            return False

    def _save_entry(self):
        try:
            entry = new_entry(self.poolBox.currentData(), self.nameEdit.text(),
                              self.pitySpin.value() or None, self.dateEdit.text().strip() or None)
            manual = deepcopy(self._manual())
            if self.edit_key:
                entry['key'] = self.edit_key
                index = next(i for i, old in enumerate(manual['entries']) if old['key'] == self.edit_key)
                manual['entries'][index] = entry
            else:
                manual['entries'].append(entry)
            if self._persist(manual):
                self._reset_form(force=True)
        except (ValueError, StopIteration) as exc:
            self._status_state = None
            self.statusLabel.setText(str(exc))

    def _edit_selected(self):
        row = self.manualTable.currentRow()
        if row < 0 or not self._confirm_discard():
            return
        entry = self._manual()['entries'][row]
        self.edit_key = entry['key']
        self.poolBox.setCurrentIndex(self.poolBox.findData(entry['pool']))
        self.nameEdit.setText(entry['name'])
        self.pitySpin.setValue(entry['pity'] or 0)
        self.dateEdit.setText(entry['date'] or '')
        self.saveBtn.setText(tr('保存修改'))
        self._form_baseline = self._form_value()

    def _delete_selected(self):
        row = self.manualTable.currentRow()
        if row < 0:
            return
        manual = deepcopy(self._manual())
        entry = manual['entries'][row]
        if not self._confirm(tr('删除手填五星？'), tr('仅删除“{name}”这条手填摘要，不影响原始记录。').format(name=entry['name'])):
            return
        del manual['entries'][row]
        if self._persist(manual) and self.edit_key == entry['key']:
            self._reset_form(force=True)

    def _move(self, direction):
        row = self.manualTable.currentRow()
        manual = deepcopy(self._manual())
        if row < 0 or not 0 <= row + direction < len(manual['entries']):
            return
        entries = manual['entries']
        entries[row], entries[row + direction] = entries[row + direction], entries[row]
        if self._persist(manual):
            self.manualTable.selectRow(row + direction)

    def _correct(self):
        row = self.realTable.currentRow()
        if row < 0 or self.real_rows[row]['orphan']:
            return
        record = self.real_rows[row]['record']
        manual = deepcopy(self._manual())
        manual['corrections'][record['id']] = {'record': record_identity(record),
                                               'pity': self.correctionSpin.value() or None}
        if self._persist(manual):
            self.realTable.selectRow(row)

    def _undo(self):
        row = self.realTable.currentRow()
        if row < 0:
            return
        manual = deepcopy(self._manual())
        manual['corrections'].pop(self.real_rows[row]['record']['id'], None)
        self._persist(manual)

    def closeEvent(self, event):
        if self._confirm_discard():
            self._closing = True
            try:
                super().closeEvent(event)
            finally:
                self._closing = False
        else:
            event.ignore()

    def reject(self):
        # Escape must follow the same unsaved-input check as the window's X.
        if self._closing or self._confirm_discard():
            super().reject()
