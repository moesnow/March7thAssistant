"""差分宇宙外部决策的开关与接入配置，不在界面进程中运行外部程序。"""

import os
import time

from PySide6.QtCore import Qt, QSignalBlocker, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QApplication
from qfluentwidgets import (
    SettingCard, SwitchButton, IndicatorPosition, PushButton, MessageBox,
    BodyLabel, LineEdit, TextEdit, FluentIcon, ComboBox,
)

from app.common.scroll_dialog import SplitFadeDialogMixin, available_host_size, build_scroll_area
from app.components.ascii_spin_box import AsciiSpinBox
from module.config import cfg
from module.localization import tr
from utils.agent_decision import validate_decision_command
from utils.agent_session import AgentSession, decision_mode
from utils.agent_service import connection_config


def connection_text(mode=None, compact=False):
    if (mode or decision_mode(cfg)) == "command":
        return tr("高级自定义程序：连接状态未知")
    state = AgentSession().status()
    labels = {"unclaimed": tr("未接管"), "idle": tr("已接管空闲"),
              "waiting": tr("等待决策"), "disconnected": tr("已断开")}
    text = labels[state["state"]]
    if state.get("client_name"):
        text += " · " + state["client_name"][:16 if compact else 32]
        if state.get("session_label"):
            text += ("\n" if compact else " · ") + state["session_label"][:20 if compact else 40]
        text += " · " + tr("最近活动：{seconds} 秒前").format(seconds=max(0, int(time.time() - state["last_activity"])))
    reasons = {"not_connected": tr("未接管，使用原策略"), "timeout": tr("等待超时，使用原策略"),
               "disconnected": tr("连接断开，使用原策略"), "cancelled": tr("请求已取消")}
    if state.get("last_fallback"):
        text += "\n" + reasons.get(state["last_fallback"], state["last_fallback"])
    return text


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
        notice = BodyLabel(tr("先在 Agent 聊天中接管，再运行任务。已配置接口不代表 Agent 已接管；断连或超时使用原策略。"), content)
        notice.setWordWrap(True)
        layout.addWidget(notice)

        layout.addWidget(BodyLabel(tr("接入方式"), content))
        self.modeComboBox = ComboBox(content)
        self.modeComboBox.addItem(tr("内置 Agent 连接"), userData="connected")
        self.modeComboBox.addItem(tr("高级自定义程序"), userData="command")
        self.modeComboBox.setCurrentIndex(1 if decision_mode(cfg) == "command" else 0)
        layout.addWidget(self.modeComboBox)
        self.statusLabel = BodyLabel("", content)
        self.statusLabel.setWordWrap(True)
        layout.addWidget(self.statusLabel)
        connection_row = QHBoxLayout()
        self.configFormat = ComboBox(content)
        self.configFormat.addItems([tr("Codex（TOML）"), tr("通用（JSON）")])
        self.copyConfigButton = PushButton(tr("复制接入配置"), content)
        self.copyPromptButton = PushButton(tr("复制聊天接管指令"), content)
        self.disconnectButton = PushButton(tr("断开"), content)
        for widget in (self.configFormat, self.copyConfigButton, self.copyPromptButton, self.disconnectButton):
            if widget in (self.configFormat, self.copyConfigButton):
                connection_row.addWidget(widget)
        layout.addLayout(connection_row)
        prompt_row = QHBoxLayout()
        prompt_row.addWidget(self.copyPromptButton)
        prompt_row.addWidget(self.disconnectButton)
        layout.addLayout(prompt_row)
        self.copyConfigButton.clicked.connect(self._copy_config)
        self.copyPromptButton.clicked.connect(self._copy_prompt)
        self.disconnectButton.clicked.connect(self._disconnect)

        self.commandPanel = QWidget(content)
        command_layout = QVBoxLayout(self.commandPanel)
        command_layout.setContentsMargins(0, 0, 0, 0)
        command = cfg.get_value("divergent_decision_command", [])
        if not isinstance(command, (list, tuple)) or any(not isinstance(arg, str) for arg in command):
            command = []
        command_layout.addWidget(BodyLabel(tr("接入程序"), content))
        program_row = QHBoxLayout()
        self.programEdit = LineEdit(content)
        self.programEdit.setPlaceholderText(tr("选择可执行文件，例如 Python 或你的接入程序"))
        self.programEdit.setText(command[0] if command else "")
        self.browseButton = PushButton(tr("浏览"), content)
        self.browseButton.clicked.connect(self._browse)
        program_row.addWidget(self.programEdit, 1)
        program_row.addWidget(self.browseButton)
        command_layout.addLayout(program_row)

        command_layout.addWidget(BodyLabel(tr("启动参数（每行一个，不需要加引号）"), content))
        self.argumentsEdit = TextEdit(content)
        self.argumentsEdit.setAcceptRichText(False)
        self.argumentsEdit.setFixedHeight(110)
        self.argumentsEdit.setPlainText("\n".join(command[1:]))
        command_layout.addWidget(self.argumentsEdit)
        layout.addWidget(self.commandPanel)
        self.modeComboBox.currentIndexChanged.connect(self._mode_changed)
        self._mode_changed()

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
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)
        self._refresh()

    def _mode_changed(self, *_):
        advanced = self.modeComboBox.currentData() == "command"
        self.commandPanel.setVisible(advanced)
        for widget in (self.configFormat, self.copyConfigButton, self.copyPromptButton, self.disconnectButton):
            widget.setVisible(not advanced)

    def _refresh(self):
        try:
            self.statusLabel.setText(connection_text(self.modeComboBox.currentData()))
            self.disconnectButton.setEnabled(AgentSession().status()["state"] in ("idle", "waiting"))
        except (OSError, ValueError, TypeError, KeyError):
            self.statusLabel.setText(tr("连接状态暂不可用"))
            self.disconnectButton.setEnabled(False)

    def _copy_config(self):
        QApplication.clipboard().setText(connection_config()[self.configFormat.currentIndex()])

    def _copy_prompt(self):
        QApplication.clipboard().setText(tr("连接位于 {path} 的三月七并监管差分宇宙；未启动任务时等待，不启动新对局；任务结束后断开接管。").format(path=os.path.abspath(os.getcwd())))

    def _disconnect(self):
        try:
            AgentSession().disconnect(local=True)
        except (OSError, ValueError, TypeError, KeyError):
            self.statusLabel.setText(tr("连接状态暂不可用"))
        else:
            self._refresh()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("选择接入程序"), self.programEdit.text())
        if path:
            self.programEdit.setText(path)

    def values(self):
        # 逐行传参，不使用 shell / eval，也不按空格切分含空格的路径。
        mode = self.modeComboBox.currentData()
        command = cfg.get_value("divergent_decision_command", [])
        if mode == "command":
            command = [self.programEdit.text().strip()] + self.argumentsEdit.toPlainText().splitlines()
            command[0] = validate_decision_command(command, require_available=True)
        context = self.contextEdit.toPlainText()
        if len(context) > 8000:
            raise ValueError("context")
        return {
            "divergent_decision_mode": mode,
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
        self.setFixedHeight(132)
        self.contentLabel.setWordWrap(True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)
        self._refresh()

    def _refresh(self):
        try:
            status = connection_text(compact=True)
        except (OSError, ValueError, TypeError, KeyError):
            status = tr("连接状态暂不可用")
        self.setContent(status + "\n" + tr("需要 Agent 持续回复；断连或超时使用原策略。"))

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
                if decision_mode(cfg) == "command":
                    validate_decision_command(cfg.get_value("divergent_decision_command", []), require_available=True)
                elif cfg.get_value("divergent_decision_mode", "auto") == "auto":
                    raise ValueError("需要首次配置连接")
            except ValueError:
                # 首次打开时引导配置；取消不保存一个无法工作的启用状态。
                self.setValue(False)
                if not self._configure():
                    return
        cfg.set_value(self.configname, enabled)
        self.setValue(enabled)
