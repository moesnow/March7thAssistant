"""逐光捡金的星启队伍配置。"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget
from qfluentwidgets import (
    MessageBox, BodyLabel, ComboBox, EditableComboBox, Pivot,
    SettingCard, PushButton, CheckBox, InfoBar, InfoBarPosition,
)

from app.card.messagebox_custom import setup_completer, _cleanup_infobars
from app.common.scroll_dialog import SplitFadeDialogMixin, available_host_size, build_scroll_area
from app.components.ascii_spin_box import AsciiSpinBox
from module.config import cfg
from module.localization import tr, get_character_names


class ChallengeConfigDialog(SplitFadeDialogMixin, MessageBox):
    def __init__(self, title, prefix, highest_level, parent=None):
        super().__init__(title, "", parent)
        self.prefix = prefix
        self.highest_level = highest_level
        self.template = get_character_names()
        self.techniques = {
            -1: tr("秘技 / 开怪"), 0: tr("无操作"),
            1: tr("秘技 1 次"), 2: tr("秘技 2 次"),
        }
        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.hide()
        self.yesButton.setText(tr("保存"))
        self.cancelButton.setText(tr("取消"))

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        level_row = QHBoxLayout()
        level_row.addWidget(BodyLabel(tr("关卡范围"), content))
        level_row.addStretch()
        self.first_level = AsciiSpinBox(content)
        self.last_level = AsciiSpinBox(content)
        levels = cfg.get_value(f"{prefix}_level", [highest_level, highest_level])
        for box, value in zip((self.first_level, self.last_level), levels):
            box.setRange(1, highest_level)
            box.setValue(value)
            box.setMinimumWidth(100)
        level_row.addWidget(self.first_level)
        level_row.addWidget(BodyLabel(tr("至"), content))
        level_row.addWidget(self.last_level)
        layout.addLayout(level_row)

        self.stellar_enable = None
        if prefix == "purefiction":
            self.stellar_enable = CheckBox(tr("启用星启模式"), content)
            self.stellar_enable.setChecked(bool(cfg.get_value("purefiction_stellar_enable", False)))
            layout.addWidget(self.stellar_enable)

        self.tabs = Pivot(content)
        self.pages = QStackedWidget(content)
        self.tabs.currentItemChanged.connect(self._on_team_changed)
        self.team_rows = []
        for index in range(3):
            page = QWidget(content)
            rows = []
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 8, 0, 8)
            if index == 2 and self.stellar_enable is not None:
                page_layout.addWidget(BodyLabel(tr("队伍三仅用于星启模式"), page))
            team = cfg.get_value(f"{prefix}_team{index + 1}", []) or []
            if index == 2 and not team:
                team = [["DanHeng", -1]]
            for slot in range(4):
                row = QHBoxLayout()
                row.addWidget(BodyLabel(tr("{index}号位").format(index=slot + 1), page))
                character = EditableComboBox(page)
                character.setMinimumWidth(180)
                character.addItems([""] + list(self.template.values()))
                raw, count = team[slot] if slot < len(team) else ("", 0)
                character.setCurrentText(self.template.get(raw, raw))
                setup_completer(character, list(self.template.values()))
                technique = ComboBox(page)
                technique.setMinimumWidth(135)
                for value, text in self.techniques.items():
                    technique.addItem(text, userData=value)
                technique.setCurrentIndex(technique.findData(count))
                row.addWidget(character, 1)
                row.addWidget(technique)
                page_layout.addLayout(row)
                rows.append((character, technique))
            self.team_rows.append(rows)
            self.pages.addWidget(page)
            self.tabs.addItem(
                routeKey=f"team{index + 1}", text=tr("队伍{index}").format(index=index + 1),
            )
        layout.addWidget(self.tabs)
        layout.addWidget(self.pages)
        self.swap = ComboBox(content)
        self.swap.addItem(tr("交换队伍"), userData=None)
        for first, second in ((0, 1), (0, 2), (1, 2)):
            self.swap.addItem(
                tr("队伍{first} ↔ 队伍{second}").format(first=first + 1, second=second + 1),
                userData=(first, second),
            )
        self.swap.currentIndexChanged.connect(self._swap_selected)
        layout.addWidget(self.swap, alignment=Qt.AlignmentFlag.AlignLeft)
        notice = BodyLabel(tr("每个队伍只允许一名角色配置为“秘技 / 开怪”"), content)
        notice.setWordWrap(True)
        layout.addWidget(notice)
        self.select_team(0)

        width, height = available_host_size(parent)
        self._scroll = build_scroll_area(content, width, height, chrome_height=170)
        self.textLayout.addWidget(self._scroll)

    def select_team(self, index):
        self.tabs.setCurrentItem(f"team{index + 1}")

    def _on_team_changed(self, route_key):
        self.pages.setCurrentIndex(int(route_key.removeprefix('team')) - 1)

    def _swap_selected(self, index):
        pair = self.swap.itemData(index)
        if pair is None:
            return
        for left, right in zip(self.team_rows[pair[0]], self.team_rows[pair[1]]):
            character, technique = left
            other_character, other_technique = right
            raw, count = character.text(), technique.currentIndex()
            character.setCurrentText(other_character.text())
            technique.setCurrentIndex(other_technique.currentIndex())
            other_character.setCurrentText(raw)
            other_technique.setCurrentIndex(count)
        self.swap.setCurrentIndex(0)

    def values(self):
        reverse = {value: key for key, value in self.template.items()}
        values = {f"{self.prefix}_level": [self.first_level.value(), self.last_level.value()]}
        if self.stellar_enable is not None:
            values["purefiction_stellar_enable"] = self.stellar_enable.isChecked()
        for index, rows in enumerate(self.team_rows, 1):
            team = [[reverse.get(character.text(), character.text()), technique.currentData()]
                    for character, technique in rows if character.text().strip()]
            values[f"{self.prefix}_team{index}"] = team
        return values

    def validate_inputs(self):
        error = None
        if self.first_level.value() > self.last_level.value():
            error = tr("关卡范围的起始值不能大于结束值。")
        seen = set()
        team_count = 3 if (self.stellar_enable is not None and self.stellar_enable.isChecked()
                           and self.last_level.value() == self.highest_level) else 2
        for index, rows in enumerate(self.team_rows[:team_count], 1):
            selected_rows = [(character, technique) for character, technique in rows if character.text().strip()]
            characters = [character.text() for character, _ in selected_rows]
            if not characters or any(c not in self.template.values() for c in characters):
                error = tr("请为队伍{index}选择1至4名有效角色。").format(index=index)
                break
            if len(set(characters)) != len(characters) or seen.intersection(characters):
                error = tr("出战队伍不能重复使用同一角色。")
                break
            if sum(technique.currentData() == -1 for _, technique in selected_rows) > 1:
                error = tr("每个队伍只允许一名角色配置为“秘技 / 开怪”")
                break
            seen.update(characters)
        if error:
            InfoBar.error(title=tr("输入错误"), content=error, orient=Qt.Horizontal,
                          isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self)
            return False
        return True

    def accept(self):
        if self.validate_inputs():
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        _cleanup_infobars(self)
        super().reject()


class ChallengeConfigCard(SettingCard):
    def __init__(self, icon, title, prefix, highest_level, parent=None):
        self.prefix = prefix
        self.highest_level = highest_level
        self.dialog_title = title
        super().__init__(icon, title, "", parent)
        self.button = PushButton(tr("配置"), self)
        self.hBoxLayout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.button.clicked.connect(self._edit)
        self.refresh()

    def refresh(self):
        first, last = cfg.get_value(f"{self.prefix}_level", [self.highest_level, self.highest_level])
        description = f"{tr('关卡范围')} {first}–{last}"
        if self.prefix == "purefiction":
            mode = tr("星启模式") if cfg.get_value("purefiction_stellar_enable", False) else tr("常规模式")
            description += f" · {mode}"
        self.contentLabel.setText(description)

    def _edit(self):
        dialog = ChallengeConfigDialog(self.dialog_title, self.prefix, self.highest_level, self.window())
        if dialog.exec():
            values = dialog.values()
            range_changed = values[f"{self.prefix}_level"] != cfg.get_value(
                f"{self.prefix}_level", [self.highest_level, self.highest_level])
            mode_changed = (self.prefix == "purefiction" and
                            values["purefiction_stellar_enable"] != bool(cfg.get_value("purefiction_stellar_enable", False)))
            if range_changed or mode_changed:
                values[f"{self.prefix}_timestamp"] = 0
            cfg.set_values(values)
            self.refresh()
