"""差分宇宙外部决策的开关与接入配置，不在界面进程中运行外部程序。"""

import os
import shutil

from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
from qfluentwidgets import (
    SettingCard, SwitchButton, IndicatorPosition, PushButton, MessageBox,
    BodyLabel, LineEdit, TextEdit, FluentIcon,
)

from app.common.scroll_dialog import SplitFadeDialogMixin, available_host_size, build_scroll_area
from app.components.ascii_spin_box import AsciiSpinBox
from module.config import cfg
from module.localization import tr
from utils.agent_decision import validate_decision_command


class AgentDecisionDialog(SplitFadeDialogMixin, MessageBox):
    def __init__(self, parent=None):
        super().__init__(tr("Agent 辅助决策配置"), "", parent)
        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.hide()
        self.yesButton.setText(tr("保存"))
        self.cancelButton.setText(tr("取消"))

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        notice = BodyLabel(tr("由当前 Agent 处理选择请求；仅打开开关不会启动 AI。超时或无有效回复时使用原有策略。"), content)
        notice.setWordWrap(True)
        layout.addWidget(notice)

        command = cfg.get_value("divergent_decision_command", [])
        if not isinstance(command, (list, tuple)) or any(not isinstance(arg, str) for arg in command):
            command = []
        layout.addWidget(BodyLabel(tr("接入程序"), content))
        program_row = QHBoxLayout()
        self.programEdit = LineEdit(content)
        self.programEdit.setPlaceholderText(tr("选择可执行文件，例如 Python 或你的接入程序"))
        self.programEdit.setText(command[0] if command else "")
        self.browseButton = PushButton(tr("浏览"), content)
        self.browseButton.clicked.connect(self._browse)
        program_row.addWidget(self.programEdit, 1)
        program_row.addWidget(self.browseButton)
        layout.addLayout(program_row)

        layout.addWidget(BodyLabel(tr("启动参数（每行一个，不需要加引号）"), content))
        self.argumentsEdit = TextEdit(content)
        self.argumentsEdit.setAcceptRichText(False)
        self.argumentsEdit.setFixedHeight(110)
        self.argumentsEdit.setPlainText("\n".join(command[1:]))
        layout.addWidget(self.argumentsEdit)

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(BodyLabel(tr("单次等待时间（秒）"), content))
        timeout_row.addStretch()
        self.timeoutSpinBox = AsciiSpinBox(content)
        self.timeoutSpinBox.setRange(1, 300)
        timeout = cfg.get_value("divergent_decision_timeout", 60)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 300:
            timeout = 60
        self.timeoutSpinBox.setValue(max(1, round(timeout)))
        timeout_row.addWidget(self.timeoutSpinBox)
        layout.addLayout(timeout_row)

        layout.addWidget(BodyLabel(tr("队伍与构筑偏好（可选）"), content))
        self.contextEdit = TextEdit(content)
        self.contextEdit.setAcceptRichText(False)
        self.contextEdit.setFixedHeight(80)
        self.contextEdit.setPlainText(str(cfg.get_value("divergent_decision_context", "") or ""))
        layout.addWidget(self.contextEdit)
        self.errorLabel = BodyLabel("", content)
        self.errorLabel.setWordWrap(True)
        self.errorLabel.hide()
        layout.addWidget(self.errorLabel)

        width, height = available_host_size(parent)
        self._scroll = build_scroll_area(content, width, height, chrome_height=170)
        self._scroll.setMinimumWidth(min(520, max(280, width - 120)))
        self.textLayout.addWidget(self._scroll)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("选择接入程序"), self.programEdit.text())
        if path:
            self.programEdit.setText(path)

    def values(self):
        # 逐行传参，不使用 shell / eval，也不按空格切分含空格的路径。
        command = [self.programEdit.text().strip()] + self.argumentsEdit.toPlainText().splitlines()
        validate_decision_command(command)
        if not (os.path.isfile(command[0]) or shutil.which(command[0])):
            raise ValueError("program")
        context = self.contextEdit.toPlainText()
        if len(context) > 8000:
            raise ValueError("context")
        return {
            "divergent_decision_command": command,
            "divergent_decision_timeout": self.timeoutSpinBox.value(),
            "divergent_decision_context": context,
        }

    def accept(self):
        try:
            self.values()
        except ValueError:
            self.errorLabel.setText(tr("请检查接入程序是否存在、参数是否为空或过长；不支持批处理文件，偏好最多 8000 字。"))
            self.errorLabel.show()
            self.setEnabled(True)
            return
        super().accept()


class AgentDecisionSettingCard(SettingCard):
    def __init__(self, parent=None):
        super().__init__(
            FluentIcon.CHAT, tr("启用 Agent 辅助决策"),
            tr("祝福、方程、奇物与下一站由 Agent 选择，战斗保持自动。\n需要 Agent 持续回复；超时回退原策略，下次任务生效。"), parent,
        )
        self.configname = "divergent_decision_enable"
        self.configButton = PushButton(tr("配置"), self)
        self.switchButton = SwitchButton(tr("关"), self, IndicatorPosition.RIGHT)
        self.hBoxLayout.addWidget(self.configButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(10)
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)
        self.setValue(cfg.get_value(self.configname, False) is True)
        self.configButton.clicked.connect(self._configure)
        self.switchButton.checkedChanged.connect(self._on_checked)

    def setValue(self, enabled):
        with QSignalBlocker(self.switchButton):
            self.switchButton.setChecked(bool(enabled))
            self.switchButton.setText(tr("开") if enabled else tr("关"))

    def _configure(self):
        dialog = AgentDecisionDialog(self.window())
        if dialog.exec():
            cfg.set_values(dialog.values())
            return True
        return False

    def _on_checked(self, enabled):
        if enabled:
            try:
                validate_decision_command(cfg.get_value("divergent_decision_command", []))
            except ValueError:
                # 首次打开时引导配置；取消不保存一个无法工作的启用状态。
                self.setValue(False)
                if not self._configure():
                    return
        cfg.set_value(self.configname, enabled)
        self.setValue(enabled)
