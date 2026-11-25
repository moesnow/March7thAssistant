# coding:utf-8
from copy import deepcopy

from PySide6.QtCore import Qt, QTime, QSize
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QFileDialog, QToolButton, QWidget
from qfluentwidgets import TimePicker, BodyLabel, PushButton, MessageBox
from qfluentwidgets import LineEdit, ComboBox, CheckBox
from app.components.ascii_spin_box import AsciiSpinBox
from qfluentwidgets import InfoBar, InfoBarPosition
from qfluentwidgets import FluentIcon as FIF
from utils.tasks import TASK_NAMES, supported_tasks, task_is_supported, UNSUPPORTED_TASK
from app.tools.adb_service import display_connection
from module.overview.schedule import schedule_conflict
from module.workflow import load_workflows
import uuid
import os
import json
from module.config import cfg
from module.localization import tr
from app.pages.common import is_evernight, style_primary
from app.common.schedule import (parse_schedule_time, task_timeout_seconds, task_trigger_mode,
                                 task_weekdays, schedule_weekday_labels, format_task_weekdays)


def _strip_jsonc_comments(text: str) -> str:
    """Strip // and /* */ comments while preserving string literals."""
    out = []
    i = 0
    in_str = False
    str_ch = ''
    escape = False
    in_line = False
    in_block = False
    n = len(text)

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ''

        if in_line:
            if ch == '\n':
                in_line = False
                out.append(ch)
            i += 1
            continue

        if in_block:
            if ch == '*' and nxt == '/':
                in_block = False
                i += 2
            else:
                i += 1
            continue

        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == '\\':
                escape = True
            elif ch == str_ch:
                in_str = False
            i += 1
            continue

        if ch in ('"', "'"):
            in_str = True
            str_ch = ch
            out.append(ch)
            i += 1
            continue

        if ch == '/' and nxt == '/':
            in_line = True
            i += 2
            continue

        if ch == '/' and nxt == '*':
            in_block = True
            i += 2
            continue

        out.append(ch)
        i += 1

    return ''.join(out)


# 从 assets/config/special_programs.json 加载特殊程序定义（若存在）
SPECIAL_PROGRAMS = []
_SPECIAL_BY_DISPLAY = {}
_SPECIAL_BY_EXEC = {}
try:
    cfg_path = "./assets/config/special_programs.jsonc"
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            raw = f.read()
            data = json.loads(_strip_jsonc_comments(raw))
            SPECIAL_PROGRAMS = data.get('special_programs', []) or []
            for p in SPECIAL_PROGRAMS:
                _SPECIAL_BY_DISPLAY[p.get('display_name')] = p
                _SPECIAL_BY_EXEC[p.get('executable', '').lower()] = p
except Exception:
    SPECIAL_PROGRAMS = []


class AddEditScheduleDialog(MessageBox):
    """基于 MessageBox 的添加/编辑定时任务弹窗"""

    def __init__(self, parent=None, task=None, scheduled_tasks=None, title=None):
        # 使用 MessageBox 的风格初始化（不显示默认内容）
        super().__init__(title or (tr("编辑定时计划") if task else tr("添加定时计划")), "", parent)
        self.task = deepcopy(task) if task else {}
        self._editing_task = task
        self._timeout_edited = False
        # 用于校验时间重复的现有任务列表（可能包含当前正在编辑的任务）
        self.existing_tasks = scheduled_tasks or []

        # 移除默认内容 Label 并使用 textLayout 添加自定义表单
        try:
            self.textLayout.removeWidget(self.contentLabel)
            self.contentLabel.clear()
        except Exception:
            pass

        # 调整按钮文本与宽度
        self.yesButton.setText(tr('确认'))
        self.cancelButton.setText(tr('取消'))
        self.buttonGroup.setMinimumWidth(480)
        style_primary(self.yesButton, is_evernight())

        # 名称
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText(tr("例如：完整运行"))

        # 时间
        self.time_picker = TimePicker(self)
        # 默认时间设置为 04:00
        self.time_picker.setTime(QTime(4, 0))

        # 程序类型（本体、流程编排或外部程序）
        self.program_type_combo = ComboBox(self)
        # 程序类型：本体、流程编排、外部程序，以及来自配置的特殊程序
        self.program_type_combo.addItem(tr('本体'), userData='self')
        connection = display_connection(cfg)
        if task_is_supported('workflow', connection):
            self.program_type_combo.addItem(tr('流程编排'), userData='workflow')
        elif str((task or {}).get('program', '')).strip().lower() == 'workflow':
            self.program_type_combo.addItem(f"{tr('流程编排')}（{tr(UNSUPPORTED_TASK)}）", userData='workflow')
        self.program_type_combo.addItem(tr('外部程序'), userData='external')
        for sp in SPECIAL_PROGRAMS:
            self.program_type_combo.addItem(tr(sp.get('display_name')), userData=sp.get('key'))

        # 可选的外部程序路径（仅当选择外部程序时启用）
        self.program_path_edit = LineEdit(self)
        self.program_path_edit.setMinimumWidth(400)
        self.program_path_edit.setPlaceholderText(tr("外部程序或脚本的完整路径"))
        self.prog_btn = PushButton(tr("选择程序"), self)
        self.prog_btn.clicked.connect(self._choose_program)

        prog_layout = QHBoxLayout()
        prog_layout.addWidget(self.program_type_combo)
        prog_layout.addWidget(self.program_path_edit)
        prog_layout.addWidget(self.prog_btn)

        # 启动参数（外部程序使用）或任务选择（本体使用）
        self.args_edit = LineEdit(self)
        self.args_edit.setPlaceholderText(tr("外部程序启动参数（可选）"))
        self.args_combo = ComboBox(self)
        # 显示本地化任务名，但保存时保留对应的任务ID（TASK_NAMES 存的是中文原文）
        # 保持 TASK_NAMES 的原始顺序（插入顺序）
        task_items = list(supported_tasks(connection).items())
        self._task_keys = [k for k, v in task_items]
        self._task_labels = [tr(v) for k, v in task_items]
        self.args_combo.addItems(self._task_labels)
        self.args_combo.setVisible(True)
        # 当用户选择内置任务时，自动填写任务名称（仅在用户操作时触发）
        self.args_combo.activated.connect(self._on_args_activated)

        self.workflow_combo = ComboBox(self)
        self.workflow_names = []
        self._workflows_loaded = False
        self.workflow_combo.setVisible(False)
        self.workflow_combo.activated.connect(self._on_workflow_activated)

        # 超时强制停止，默认60分钟，单位分钟
        self.timeout_spin = AsciiSpinBox(self)
        self.timeout_spin.setRange(0, 24 * 60)
        self.timeout_spin.setSuffix(tr(" 分钟（0 表示不启用）"))

        # 启动方式：按时启动或链式启动
        self._trigger_mode_items = [
            ('time', tr('按时启动')),
            ('chain', tr('链式启动')),
        ]
        self.trigger_mode_combo = ComboBox(self)
        for key, label in self._trigger_mode_items:
            self.trigger_mode_combo.addItem(label, userData=key)
        self.trigger_mode_combo.currentIndexChanged.connect(self._on_trigger_mode_changed)
        self.trigger_mode_help_btn = QToolButton(self)
        self.trigger_mode_help_btn.setIcon(FIF.INFO.icon())
        self.trigger_mode_help_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.trigger_mode_help_btn.setAutoRaise(True)
        self.trigger_mode_help_btn.setFixedSize(28, 28)
        self.trigger_mode_help_btn.setIconSize(QSize(16, 16))
        self.trigger_mode_help_btn.setToolTip(tr('启动方式说明'))
        self.trigger_mode_help_btn.clicked.connect(self._show_trigger_mode_help)

        # 初始显示状态：默认选择本体
        self.program_type_combo.setCurrentIndex(0)
        # 连接信号，在后面创建 args_label 后再触发一次以确保文本正确
        self.program_type_combo.currentTextChanged.connect(self._on_program_type_changed)
        # 连接 activated 信号，用于检测用户手动选择以应用默认参数（仅用户触发）
        self.program_type_combo.activated.connect(self._on_program_type_activated)

        # 完成后是否推送通知（布尔值）
        self.notify_check = CheckBox(tr("完成后推送通知"), self)
        self.notify_check.setChecked(False)

        # 任务完成后操作（显示为本地化标签，内部保存 key）
        self.post_action_combo = ComboBox(self)
        # keys 与 labels 对应
        self._post_action_items = [
            ("None", tr("无操作")),
            ("Shutdown", tr("关机")),
            ("Sleep", tr("睡眠")),
            ("Hibernate", tr("休眠")),
            ("Restart", tr("重启")),
            ("Logoff", tr("注销")),
            ("TurnOffDisplay", tr("关闭显示器")),
        ]
        self._post_action_keys = [k for k, l in self._post_action_items]
        self._post_action_labels = [l for k, l in self._post_action_items]
        self.post_action_combo.addItems(self._post_action_labels)

        # 完成后推送通知（默认：否）
        # 注意：字段名为 notify，布尔值，true 表示发送通知，false 不发送
        # 启用
        self.enable_check = CheckBox(tr("启用"), self)
        self.enable_check.setChecked(True)

        # 组合表单并添加到 textLayout（标签与控件左右排列）
        form = QVBoxLayout()
        # 各语言共用同一列，给当前语言最长的表单标签留出宽度。
        labels = (tr("任务名称："), tr("执行星期："), tr("程序路径："), tr("选择任务："), tr("选择流程："),
                  tr("启动参数："), tr("账号："), tr("超时强制停止："), tr("完成后终止进程："), tr("完成后推送通知："))
        metrics = self.enable_check.fontMetrics()
        label_width = max(116, *(metrics.horizontalAdvance(text) + 4 for text in labels))

        # 启用（顶部左对齐）
        top_row = QHBoxLayout()
        top_row.addWidget(self.enable_check)
        top_row.addStretch()
        mode_label = BodyLabel(tr('启动方式：'))
        mode_label.setFixedWidth(90)
        top_row.addWidget(mode_label)
        top_row.addWidget(self.trigger_mode_combo)
        top_row.addWidget(self.trigger_mode_help_btn)
        form.addLayout(top_row)

        # 名称与时间同一行
        row = QHBoxLayout()
        label = BodyLabel(tr("任务名称："))
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.name_edit, 1)
        # 时间放在同一行的右侧
        self.time_label = BodyLabel(tr("启动时间："))
        self.time_label.setFixedWidth(90)
        row.addWidget(self.time_label)
        row.addWidget(self.time_picker)
        form.addLayout(row)

        self.weekday_row = QWidget(self)
        weekday_layout = QHBoxLayout(self.weekday_row)
        weekday_layout.setContentsMargins(0, 0, 0, 0)
        weekday_layout.setSpacing(12)
        weekday_label = BodyLabel(tr('执行星期：'))
        weekday_label.setFixedWidth(label_width)
        weekday_layout.addWidget(weekday_label)
        self.weekday_checks = {}
        for day, text in enumerate(schedule_weekday_labels(), 1):
            checkbox = CheckBox(text, self.weekday_row)
            checkbox.setChecked(True)
            self.weekday_checks[day] = checkbox
            weekday_layout.addWidget(checkbox)
        weekday_layout.addStretch()
        self.weekday_row.setToolTip(tr('按电脑本地日期判断执行星期'))
        form.addWidget(self.weekday_row)

        # 程序路径行
        row = QHBoxLayout()
        label = BodyLabel(tr("程序路径："))
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addLayout(prog_layout)
        form.addLayout(row)

        # 启动参数 / 任务行（使用可变 label，随程序类型切换）
        row = QHBoxLayout()
        self.args_label = BodyLabel(tr("启动参数 或 选择任务："))
        self.args_label.setFixedWidth(label_width)
        row.addWidget(self.args_label)
        row.addWidget(self.args_edit)
        row.addWidget(self.args_combo)
        row.addWidget(self.workflow_combo)
        form.addLayout(row)

        self.account_row = QWidget(self)
        account_layout = QHBoxLayout(self.account_row)
        account_layout.setContentsMargins(0, 0, 0, 0)
        account_layout.setSpacing(12)
        account_label = BodyLabel(tr("账号："))
        account_label.setFixedWidth(label_width)
        account_layout.addWidget(account_label)
        self.account_combo = ComboBox(self)
        self.account_combo.addItem(tr("全部账号轮流"), userData="all")
        model = getattr(parent, "accountModel", None)
        self._show_accounts = bool(model and model.active() and model.accounts())
        if self._show_accounts:
            for info in model.accounts():
                self.account_combo.addItem(info.name, userData=info.uid)
        uid = self.task.get("account") or "all"
        if self.account_combo.findData(uid) < 0:
            self.account_combo.addItem(tr("指定的账号不可用"), userData=uid)
        self.account_combo.setCurrentIndex(self.account_combo.findData(uid))
        account_layout.addWidget(self.account_combo, 1)
        form.addWidget(self.account_row)

        # 超时与任务完成后操作同一行
        row = QHBoxLayout()
        label = BodyLabel(tr("超时强制停止："))
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.timeout_spin)
        # 间隔
        spacer = QLabel("")
        spacer.setFixedWidth(16)
        row.addWidget(spacer)
        post_label = BodyLabel(tr("任务完成后操作："))
        post_label.setFixedWidth(120)
        row.addWidget(post_label)
        row.addWidget(self.post_action_combo)
        form.addLayout(row)

        # 完成后终止进程（可填写多个，逗号分隔）
        row = QHBoxLayout()
        label = BodyLabel(tr("完成后终止进程："))
        label.setFixedWidth(label_width)
        self.kill_processes_edit = LineEdit(self)
        self.kill_processes_edit.setPlaceholderText(tr("例如：StarRail.exe, YuanShen.exe（逗号分隔多个进程）"))
        row.addWidget(label)
        row.addWidget(self.kill_processes_edit)
        form.addLayout(row)

        # 完成后推送通知（左对齐）
        row = QHBoxLayout()
        label = BodyLabel(tr("完成后推送通知："))
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.notify_check)
        row.addStretch()
        form.addLayout(row)

        self.textLayout.addLayout(form, 0)

        # 确保 args_label 文本正确（首次打开时 program_type 已设为默认）
        self._on_program_type_changed(self.program_type_combo.currentText())
        self._set_trigger_mode('time')

        # 如果是编辑，填充数据
        if self.task:
            self._load_task(self.task)
        else:
            self._on_trigger_mode_changed()

        self.timeout_spin.valueChanged.connect(self._on_timeout_changed)

        # 当程序类型改变时切换参数输入模式
        # 已在构造中连接：self.program_type_combo.currentTextChanged -> _on_program_type_changed

    def accept(self):
        """在确认前执行字段校验：名称非空，时间不重复，外部程序路径非空。"""
        name = self.name_edit.text().strip()
        if not name:
            m = MessageBox(tr('错误'), tr('任务名称不能为空'), self)
            m.cancelButton.hide()
            m.yesButton.setText(tr('确认'))
            m.exec()
            return

        # 时间重复校验（跳过与当前编辑任务相同的 id）
        if self._current_trigger_mode() == 'time':
            content = schedule_conflict(self.existing_tasks, self.time_picker.time.toPython(),
                                        self._selected_weekdays(), self._editing_task)
            if content:
                message = MessageBox(tr('错误'), content, self)
                message.cancelButton.hide()
                message.yesButton.setText(tr('确认'))
                message.exec()
                return

        # 程序路径不能为空（非本体类型都要求路径）
        if self._current_program_type() != 'self':
            prog = self.program_path_edit.text().strip()
            if self._current_program_type() == 'workflow':
                if self.workflow_combo.currentText().strip() not in self.workflow_names:
                    m = MessageBox(tr('错误'), tr('请选择要运行的流程编排'), self)
                    m.cancelButton.hide()
                    m.yesButton.setText(tr('确认'))
                    m.exec()
                    return
            elif not prog:
                m = MessageBox(tr('错误'), tr('程序路径不能为空'), self)
                m.cancelButton.hide()
                m.yesButton.setText(tr('确认'))
                m.exec()
                return

        # 其他字段（启动参数、消息）可为空，校验通过
        try:
            super().accept()
        except Exception:
            # 兼容性回退
            self.close()

    def _choose_program(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("选择程序或脚本"), "", tr("可执行文件 (*.exe *.bat *.ps1);;所有文件 (*.*)"))
        if path:
            # 将选择的路径填写到外部程序路径控件
            self.program_path_edit.setText(path)

    def _current_program_type(self):
        return self.program_type_combo.itemData(self.program_type_combo.currentIndex())

    def _set_program_type(self, program_key):
        for index in range(self.program_type_combo.count()):
            if self.program_type_combo.itemData(index) == program_key:
                self.program_type_combo.setCurrentIndex(index)
                return

    def _load_workflow_choices(self):
        if self._workflows_loaded:
            return
        self.workflow_names = [workflow.get('name', '') for workflow in load_workflows() if workflow.get('name')]
        self.workflow_combo.addItems(self.workflow_names)
        self._workflows_loaded = True

    def _on_timeout_changed(self, _value):
        self._timeout_edited = True

    def _current_trigger_mode(self):
        idx = self.trigger_mode_combo.currentIndex() if self.trigger_mode_combo.count() > 0 else 0
        try:
            mode = self.trigger_mode_combo.itemData(idx)
        except Exception:
            mode = None
        return mode if mode in ('time', 'chain') else 'time'

    def _selected_weekdays(self):
        return [day for day, checkbox in self.weekday_checks.items() if checkbox.isChecked()]

    def _set_trigger_mode(self, mode):
        target = mode if mode in ('time', 'chain') else 'time'
        for i in range(self.trigger_mode_combo.count()):
            if self.trigger_mode_combo.itemData(i) == target:
                self.trigger_mode_combo.setCurrentIndex(i)
                return
        if self.trigger_mode_combo.count() > 0:
            self.trigger_mode_combo.setCurrentIndex(0)

    def _on_trigger_mode_changed(self, _index=None):
        is_time_mode = self._current_trigger_mode() == 'time'
        self.time_label.setVisible(is_time_mode)
        self.time_picker.setVisible(is_time_mode)
        self.weekday_row.setVisible(is_time_mode)

    def _show_trigger_mode_help(self):
        content = tr(
            '按时启动：在选中的星期到达设定时间后，直接启动当前任务，星期按电脑本地日期判断。\n'
            '链式启动：不会单独按时间触发，需要放在前一个任务后面；当前一个任务正常结束后，会按列表顺序立即启动，不单独判断星期。\n'
            '立即运行：不受星期限制，从当前任务开始，后面连续的链式任务也会跟随执行。'
        )
        box = MessageBox(tr('启动方式说明'), content, self)
        box.cancelButton.hide()
        box.yesButton.setText(tr('确认'))
        box.exec()

    def _on_program_type_changed(self, text):
        """根据程序类型调整界面：本体 -> 显示任务下拉；外部程序 -> 显示路径与参数输入，并修改标签文本"""
        program_type = self._current_program_type()
        self.account_row.setVisible(self._show_accounts and program_type == 'self')
        if program_type == 'self':
            self.program_path_edit.setVisible(False)
            self.prog_btn.setVisible(False)
            self.args_edit.setVisible(False)
            self.args_combo.setVisible(True)
            self.workflow_combo.setVisible(False)
            # 更新标签为任务选择
            try:
                self.args_label.setText(tr('选择任务：'))
            except Exception:
                pass
        elif program_type == 'workflow':
            self._load_workflow_choices()
            self.program_path_edit.setVisible(False)
            self.prog_btn.setVisible(False)
            self.args_edit.setVisible(False)
            self.args_combo.setVisible(False)
            self.workflow_combo.setVisible(True)
            try:
                self.args_label.setText(tr('选择流程：'))
            except Exception:
                pass
        elif program_type == 'external':
            self.program_path_edit.setVisible(True)
            self.prog_btn.setVisible(True)
            self.args_edit.setVisible(True)
            self.args_combo.setVisible(False)
            self.workflow_combo.setVisible(False)
            # 更新标签为启动参数
            try:
                self.args_label.setText(tr('启动参数：'))
                self.program_path_edit.setPlaceholderText(tr('外部程序或脚本的完整路径'))
            except Exception:
                pass
        else:
            # 检查是否为配置中的特殊程序（使用 display_name 的 tr 版本比较）
            found = None
            for sp in SPECIAL_PROGRAMS:
                if program_type == sp.get('key'):
                    found = sp
                    break
            if found:
                self.program_path_edit.setVisible(True)
                self.prog_btn.setVisible(True)
                self.args_edit.setVisible(True)
                self.args_combo.setVisible(False)
                self.workflow_combo.setVisible(False)
                try:
                    self.args_label.setText(tr('启动参数：'))
                    # 显示可执行文件示例作为 placeholder
                    exe = found.get('executable', '')
                    self.program_path_edit.setPlaceholderText(tr("{exe} 的完整路径").format(exe=exe))
                except Exception:
                    pass
            else:
                # fallback
                self.program_path_edit.setVisible(True)
                self.prog_btn.setVisible(True)
                self.args_edit.setVisible(True)
                self.args_combo.setVisible(False)
                try:
                    self.args_label.setText(tr('启动参数：'))
                except Exception:
                    pass

    def _on_program_type_activated(self, index):
        """仅在用户手动选择时应用默认参数（若参数为空）"""
        # 本体/流程编排/外部程序手动选择 -> 清空名称与参数（让用户填写）
        program_type = self._current_program_type()
        if program_type in ('self', 'workflow', 'external'):
            self.name_edit.setText('')
            self.args_edit.setText('')
            self.kill_processes_edit.setText('')
            if program_type == 'workflow' and self.workflow_combo.count() > 0:
                self._on_workflow_activated(self.workflow_combo.currentIndex())
            return
        # 特殊程序：查找配置并应用 short_name 与默认 args（仅当 args 为空时）
        for sp in SPECIAL_PROGRAMS:
            if program_type == sp.get('key'):
                try:
                    self.name_edit.setText(sp.get('short_name', ''))
                    self.args_edit.setText(sp.get('default_args', ''))
                    # 自动填充完成后终止的进程
                    try:
                        kp = sp.get('kill_processes', []) or []
                        self.kill_processes_edit.setText(', '.join(kp))
                    except Exception:
                        pass
                except Exception:
                    pass
                return

    def _on_args_activated(self, index):
        """用户在选择内置任务时同步更新任务名称为对应标签（仅用户触发）"""
        try:
            label = self.args_combo.itemText(index)
        except Exception:
            label = self.args_combo.currentText()
        # 直接设置名称以反映当前选中的内置任务
        self.name_edit.setText(label)

    def _on_workflow_activated(self, index):
        try:
            name = self.workflow_combo.itemText(index)
        except Exception:
            name = self.workflow_combo.currentText()
        if name:
            self.name_edit.setText(f"{tr('流程编排')} - {name}")

    def _load_task(self, task):
        self._set_trigger_mode(task_trigger_mode(task))
        self.name_edit.setText(task.get('name', ''))
        self.time_picker.setTime(parse_schedule_time(task.get('time', '04:00')) or QTime(4, 0))
        selected_days = task_weekdays(task)
        for day, checkbox in self.weekday_checks.items():
            checkbox.setChecked(day in selected_days)

        prog = task.get('program', 'self')
        if isinstance(prog, str) and prog.strip().lower() == 'self':
            # 本体任务
            self._set_program_type('self')
            # 找到对应 task key 在 self._task_keys 中的索引
            args_key = task.get('args', 'main')
            try:
                idx = self._task_keys.index(args_key)
            except ValueError:
                # 备用：如果 args 是中文 label，就尝试匹配标签
                try:
                    idx = self._task_labels.index(args_key)
                except ValueError:
                    self._task_keys.append(args_key)
                    label = f"{tr(TASK_NAMES.get(args_key, str(args_key)))}（{tr(UNSUPPORTED_TASK)}）"
                    self._task_labels.append(label)
                    self.args_combo.addItem(label)
                    idx = len(self._task_keys) - 1
            self.args_combo.setCurrentIndex(idx)
        elif isinstance(prog, str) and prog.strip().lower() == 'workflow':
            self._set_program_type('workflow')
            workflow_name = task.get('workflow_name') or task.get('args', '')
            if workflow_name in self.workflow_names:
                self.workflow_combo.setCurrentIndex(self.workflow_names.index(workflow_name))
            elif workflow_name:
                self.workflow_combo.addItem(workflow_name)
                self.workflow_combo.setCurrentIndex(self.workflow_combo.count() - 1)
            self.name_edit.setText(task.get('name') or f"{tr('流程编排')} - {workflow_name}")
        else:
            # 外部程序或特定外部类型
            self.program_path_edit.setText(str(prog))
            lower = str(prog).lower()
            # 如果文件名匹配特定的可识别 exe，则自动选择对应类型并填充默认参数（若无）
            basename = os.path.basename(lower)
            sp = _SPECIAL_BY_EXEC.get(basename.lower())
            if sp:
                # 找到配置中的特殊程序，设置为对应 display_name（tr 并显示）
                self._set_program_type(sp.get('key'))
                self.args_edit.setText(task.get('args', ''))
            else:
                self._set_program_type('external')
                self.args_edit.setText(task.get('args', ''))

        # task['timeout'] 存储为秒，UI 使用分钟单位，因此先转换
        try:
            self.timeout_spin.setValue(task_timeout_seconds(task) // 60)
        except Exception:
            self.timeout_spin.setValue(0)
        # 完成后是否推送通知 -> 新字段 notify
        try:
            self.notify_check.setChecked(bool(task.get('notify', False)))
        except Exception:
            self.notify_check.setChecked(False)

        # 完成后终止进程（列表或逗号分隔字符串均兼容）
        try:
            kp = task.get('kill_processes', [])
            if isinstance(kp, list):
                self.kill_processes_edit.setText(', '.join(kp))
            else:
                self.kill_processes_edit.setText(str(kp) if kp else '')
        except Exception:
            self.kill_processes_edit.setText('')
        # 兼容旧值：task['post_action'] 可能为 key 或为标签
        post_val = task.get('post_action', 'None')
        idx = 0
        if post_val in self._post_action_keys:
            idx = self._post_action_keys.index(post_val)
        else:
            try:
                idx = self._post_action_labels.index(post_val)
            except ValueError:
                idx = 0
        self.post_action_combo.setCurrentIndex(idx)
        self.enable_check.setChecked(task.get('enabled', True))
        self._on_program_type_changed(self.program_type_combo.currentText())
        self._on_trigger_mode_changed()

    def get_task(self):
        task = deepcopy(self.task)
        task['id'] = self.task.get('id') if self.task and self.task.get('id') else str(uuid.uuid4())
        task['name'] = self.name_edit.text().strip() or tr('未命名')
        task['trigger_mode'] = self._current_trigger_mode()
        # TimePicker.time is a QTime *object* (not a callable), so access property directly
        task['time'] = self.time_picker.time.toString('HH:mm')
        task['weekdays'] = self._selected_weekdays()

        # 根据程序类型保存 program 字段：'self' 或 外部程序路径
        program_type = self._current_program_type()
        if program_type == 'self':
            task['program'] = 'self'
            # args 保存为任务 id（key）而不是中文 label
            idx = self.args_combo.currentIndex() if self.args_combo.count() > 0 else 0
            task['args'] = self._task_keys[idx] if idx >= 0 and idx < len(self._task_keys) else 'main'
        elif program_type == 'workflow':
            task['program'] = 'workflow'
            workflow_name = self.workflow_combo.currentText().strip()
            task['args'] = workflow_name
            task['workflow_name'] = workflow_name
        else:
            task['program'] = self.program_path_edit.text().strip() or ''
            task['args'] = self.args_edit.text().strip()

        if program_type == "self" and self._show_accounts:
            task["account"] = self.account_combo.currentData()
        elif program_type != "self":
            task.pop("account", None)
        if program_type != 'workflow':
            task.pop('workflow_name', None)
            task.pop('workflow_step_path', None)

        # 存储为秒（与现有运行/超时逻辑兼容）
        task['timeout'] = int(self.timeout_spin.value()) * 60 if self._timeout_edited else task_timeout_seconds(self.task)
        # 完成后是否推送通知（布尔值）
        task['notify'] = bool(self.notify_check.isChecked())
        # 保存为 key（与 _post_action_keys 对应）
        pa_idx = self.post_action_combo.currentIndex() if self.post_action_combo.count() > 0 else 0
        task['post_action'] = self._post_action_keys[pa_idx] if pa_idx >= 0 and pa_idx < len(self._post_action_keys) else 'None'
        task['enabled'] = bool(self.enable_check.isChecked())

        # 完成后终止的进程名，存储为进程名列表（去除空项与空白）
        kp_text = self.kill_processes_edit.text().strip()
        if kp_text:
            kp_list = [p.strip() for p in kp_text.split(',') if p.strip()]
        else:
            kp_list = []
        task['kill_processes'] = kp_list

        return task
