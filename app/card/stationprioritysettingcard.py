# coding:utf-8
from typing import Union
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QFrame, QScrollArea)
from qfluentwidgets import (SettingCard, FluentIconBase, SwitchButton, IndicatorPosition,
                            MessageBox, PushButton, BodyLabel)
from module.config import cfg
from module.localization import tr


# 固定站点（优先级0），不允许用户操作
FIXED_STATIONS = {"首领": 0, "休整": 0, "转化": 0}

# 默认可配置站点优先级
DEFAULT_STATION_PRIORITY = {
    "战斗": 1,
    "精英": 1,
    "事件": 2,
    "奖励": 2,
    "异常": 2,
    "铸造": 2,
    "空白": 3,
    "商店": 3,
    "财富": 3,
}

# 默认禁用站点列表
DEFAULT_STATION_DISABLED = []


class StationRow(QFrame):
    """单行站点显示，包含名称、优先级、上下移动按钮和启用/禁用开关"""

    moved = Signal()
    toggled = Signal()

    def __init__(self, name: str, priority: int, enabled: bool = True, parent=None):
        super().__init__(parent)
        self.station_name = name
        self.priority = priority
        self.enabled = enabled

        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)

        self.nameLabel = BodyLabel(name, self)
        self.nameLabel.setFixedWidth(60)
        layout.addWidget(self.nameLabel)

        self.priorityLabel = BodyLabel(str(priority), self)
        self.priorityLabel.setFixedWidth(30)
        self.priorityLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.priorityLabel)

        layout.addStretch(1)

        self.upButton = QPushButton("↑", self)
        self.upButton.setFixedSize(28, 28)
        self.upButton.clicked.connect(self._on_up)
        layout.addWidget(self.upButton)

        self.downButton = QPushButton("↓", self)
        self.downButton.setFixedSize(28, 28)
        self.downButton.clicked.connect(self._on_down)
        layout.addWidget(self.downButton)

        layout.addSpacing(10)

        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)
        self.switchButton.setChecked(enabled)
        self.switchButton.setText(tr('开') if enabled else tr('关'))
        self.switchButton.checkedChanged.connect(self._on_toggled)
        layout.addWidget(self.switchButton)

        self._update_style()

    def _on_up(self):
        self._move_dir = -1
        self.moved.emit()

    def _on_down(self):
        self._move_dir = 1
        self.moved.emit()

    def _on_toggled(self, checked):
        self.enabled = checked
        self.switchButton.setText(tr('开') if checked else tr('关'))
        self._update_style()
        self.toggled.emit()

    def set_priority(self, priority: int):
        self.priority = priority
        self.priorityLabel.setText(str(priority))

    def _update_style(self):
        if not self.enabled:
            self.nameLabel.setStyleSheet("color: gray;")
            self.priorityLabel.setStyleSheet("color: gray;")
        else:
            self.nameLabel.setStyleSheet("")
            self.priorityLabel.setStyleSheet("")


class MessageBoxStationPriority(MessageBox):
    """站点优先级配置对话框"""

    def __init__(self, station_priority: dict, disabled_stations: list, parent=None):
        super().__init__(tr('站点优先级配置'), '', parent)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText(tr('确认'))
        self.cancelButton.setText(tr('取消'))

        # 提示信息
        self.hintLabel = BodyLabel(
            tr("调整站点优先级顺序，数字越小优先级越高。\n没有重抽次数后仍会选择禁用的站点。"),
            self
        )
        self.hintLabel.setWordWrap(True)
        self.textLayout.addWidget(self.hintLabel, 0, Qt.AlignmentFlag.AlignTop)

        # 固定站点提示
        fixedLabel = BodyLabel(
            tr("固定站点（始终最高优先级）：首领、休整、转化"),
            self
        )
        fixedLabel.setStyleSheet("color: gray;")
        self.textLayout.addWidget(fixedLabel, 0, Qt.AlignmentFlag.AlignTop)

        # 分隔线
        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.textLayout.addWidget(separator)

        # 表头
        headerLayout = QHBoxLayout()
        headerLayout.setContentsMargins(12, 0, 12, 0)
        nameHeader = BodyLabel(tr("站点"), self)
        nameHeader.setFixedWidth(60)
        headerLayout.addWidget(nameHeader)
        priorityHeader = BodyLabel(tr("优先级"), self)
        priorityHeader.setFixedWidth(40)
        priorityHeader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headerLayout.addWidget(priorityHeader)
        headerLayout.addStretch(1)
        moveHeader = BodyLabel(tr("排序"), self)
        moveHeader.setFixedWidth(66)
        moveHeader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        headerLayout.addWidget(moveHeader)
        headerLayout.addSpacing(10)
        enableHeader = BodyLabel(tr("启用"), self)
        headerLayout.addWidget(enableHeader)
        headerWidget = QWidget(self)
        headerWidget.setLayout(headerLayout)
        self.textLayout.addWidget(headerWidget)

        # 站点行容器（放入滚动区域，防止站点过多时对话框过长）
        self.rowContainer = QVBoxLayout()
        self.rowContainer.setSpacing(2)
        self.rowContainer.setContentsMargins(0, 0, 0, 0)
        rowWidget = QWidget(self)
        rowWidget.setLayout(self.rowContainer)

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setWidget(rowWidget)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setMinimumHeight(280)
        # self.scrollArea.setMaximumHeight(630)

        self.textLayout.addWidget(self.scrollArea)

        # 恢复默认按钮
        self.resetButton = PushButton(tr('恢复默认'), self)
        self.resetButton.clicked.connect(self._reset_to_default)
        self.textLayout.addWidget(self.resetButton, 0, Qt.AlignmentFlag.AlignLeft)

        self.buttonGroup.setMinimumWidth(480)

        # 按优先级排序站点
        self.rows = []
        sorted_stations = sorted(station_priority.items(), key=lambda x: x[1])
        for name, priority in sorted_stations:
            if name in FIXED_STATIONS:
                continue
            enabled = name not in disabled_stations
            self._add_row(name, priority, enabled)

        self._update_priorities()
        self._update_buttons()

    def _add_row(self, name: str, priority: int, enabled: bool = True):
        row = StationRow(name, priority, enabled, self)
        row.moved.connect(lambda r=row: self._on_row_moved(r))
        row.toggled.connect(self._update_priorities)
        self.rows.append(row)
        self.rowContainer.addWidget(row)

    def _on_row_moved(self, row: StationRow):
        idx = self.rows.index(row)
        direction = row._move_dir
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.rows):
            return

        # 交换
        self.rows[idx], self.rows[new_idx] = self.rows[new_idx], self.rows[idx]

        # 重新布局
        for i in range(self.rowContainer.count()):
            self.rowContainer.takeAt(0)
        for r in self.rows:
            self.rowContainer.addWidget(r)

        self._update_priorities()
        self._update_buttons()

    def _update_priorities(self):
        """根据当前顺序重新分配优先级（从1开始）"""
        for i, row in enumerate(self.rows):
            row.set_priority(i + 1)

    def _update_buttons(self):
        """更新上下移动按钮的可用状态"""
        for i, row in enumerate(self.rows):
            row.upButton.setEnabled(i > 0)
            row.downButton.setEnabled(i < len(self.rows) - 1)

    def _reset_to_default(self):
        """恢复默认优先级"""
        # 清除所有行
        for row in self.rows:
            self.rowContainer.removeWidget(row)
            row.deleteLater()
        self.rows.clear()

        # 重新创建默认行
        sorted_stations = sorted(DEFAULT_STATION_PRIORITY.items(), key=lambda x: x[1])
        for name, priority in sorted_stations:
            self._add_row(name, priority, True)

        self._update_priorities()
        self._update_buttons()

    def get_station_priority(self) -> dict:
        """获取当前站点优先级配置"""
        result = {}
        for row in self.rows:
            result[row.station_name] = row.priority
        return result

    def get_disabled_stations(self) -> list:
        """获取禁用的站点列表"""
        return [row.station_name for row in self.rows if not row.enabled]


class StationPrioritySettingCard(SettingCard):
    """差分宇宙站点优先级设置卡片"""

    def __init__(self, icon: Union[str, QIcon, FluentIconBase], title, content=None, parent=None):
        super().__init__(icon, title, content, parent)

        self.configButton = QPushButton(tr("配置"), self)
        self.hBoxLayout.addWidget(self.configButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.configButton.clicked.connect(self._on_config_clicked)

        self.switchButton = SwitchButton(tr('关'), self, IndicatorPosition.RIGHT)
        self.setValue(cfg.get_value("divergent_station_priority_enable"))

        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self.switchButton.checkedChanged.connect(self._on_checked_changed)

        self._update_content_text()

    def _on_checked_changed(self, isChecked: bool):
        self.setValue(isChecked)
        cfg.set_value("divergent_station_priority_enable", isChecked)
        self._update_content_text()

    def setValue(self, isChecked: bool):
        self.switchButton.setChecked(isChecked)
        self.switchButton.setText(tr('开') if isChecked else tr('关'))

    def _update_content_text(self):
        self.contentLabel.show()
        if cfg.get_value("divergent_station_priority_enable"):
            disabled = cfg.get_value("divergent_station_disabled")
            if disabled:
                self.contentLabel.setText(tr("已启用自定义优先级，{} 个站点已禁用").format(len(disabled)))
            else:
                self.contentLabel.setText(tr("已启用自定义优先级"))
        else:
            self.contentLabel.setText(tr("使用默认优先级"))

    def _on_config_clicked(self):
        station_priority = cfg.get_value("divergent_station_priority")
        disabled_stations = cfg.get_value("divergent_station_disabled")

        dialog = MessageBoxStationPriority(station_priority, disabled_stations, self.window())
        if dialog.exec():
            new_priority = dialog.get_station_priority()
            new_disabled = dialog.get_disabled_stations()
            cfg.set_value("divergent_station_priority", new_priority)
            cfg.set_value("divergent_station_disabled", new_disabled)
            self._update_content_text()
