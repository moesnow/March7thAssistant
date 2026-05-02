# coding:utf-8
from PySide6.QtCore import Qt, QTime, QDateTime, QSize
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QTableWidgetItem, QFileDialog, QHeaderView,
                               QToolButton, QWidget,
                               QAbstractItemView)
from qfluentwidgets import TimePicker, BodyLabel, PushButton, PrimaryPushButton, TableWidget, MaskDialogBase, MessageBox, Dialog
from qfluentwidgets import LineEdit, ComboBox, CheckBox, SpinBox
from qfluentwidgets import InfoBar, InfoBarPosition
from qfluentwidgets import FluentIcon as FIF
from utils.tasks import TASK_NAMES
import uuid
import os
import json
from module.config import cfg
from module.localization import tr


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

    def __init__(self, parent=None, task=None, scheduled_tasks=None):
        # 使用 MessageBox 的风格初始化（不显示默认内容）
        super().__init__(tr("添加/编辑定时任务"), "", parent)
        self.task = task or {}
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

        # 名称
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText(tr("例如：完整运行"))

        # 时间
        self.time_picker = TimePicker(self)
        # 默认时间设置为 04:00
        self.time_picker.setTime(QTime(4, 0))

        # 程序类型（'本体' 表示启动程序自身，'外部程序' 表示选择可执行文件）
        self.program_type_combo = ComboBox(self)
        # 程序类型：本体、外部程序，以及来自配置的特殊程序
        items = [tr('本体'), tr('外部程序')]
        for sp in SPECIAL_PROGRAMS:
            # display_name 可能包含空格等，本地化时使用 tr(display_name)
            items.append(tr(sp.get('display_name')))
        self.program_type_combo.addItems(items)

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
        # 使用中文显示任务名称，但保存时保留对应的任务ID
        # 保持 TASK_NAMES 的原始顺序（插入顺序）
        task_items = list(TASK_NAMES.items())
        self._task_keys = [k for k, v in task_items]
        self._task_labels = [v for k, v in task_items]
        self.args_combo.addItems(self._task_labels)
        self.args_combo.setVisible(True)
        # 当用户选择内置任务时，自动填写任务名称（仅在用户操作时触发）
        self.args_combo.activated.connect(self._on_args_activated)

        # 超时强制停止，默认60分钟，单位分钟
        self.timeout_spin = SpinBox(self)
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
        self.program_type_combo.setCurrentText('本体')
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
        label_width = 100

        # 启用（顶部左对齐）
        top_row = QHBoxLayout()
        top_row.addWidget(self.enable_check)
        top_row.addStretch()
        mode_label = BodyLabel(tr('启动方式:'))
        mode_label.setFixedWidth(90)
        top_row.addWidget(mode_label)
        top_row.addWidget(self.trigger_mode_combo)
        top_row.addWidget(self.trigger_mode_help_btn)
        form.addLayout(top_row)

        # 名称与时间同一行
        row = QHBoxLayout()
        label = BodyLabel(tr("任务名称:"))
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.name_edit, 1)
        # 时间放在同一行的右侧
        self.time_label = BodyLabel(tr("启动时间:"))
        self.time_label.setFixedWidth(90)
        row.addWidget(self.time_label)
        row.addWidget(self.time_picker)
        form.addLayout(row)

        # 程序路径行
        row = QHBoxLayout()
        label = BodyLabel(tr("程序路径:"))
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addLayout(prog_layout)
        form.addLayout(row)

        # 启动参数 / 任务行（使用可变 label，随程序类型切换）
        row = QHBoxLayout()
        self.args_label = BodyLabel(tr("启动参数 或 选择任务:"))
        self.args_label.setFixedWidth(label_width)
        row.addWidget(self.args_label)
        row.addWidget(self.args_edit)
        row.addWidget(self.args_combo)
        form.addLayout(row)

        # 超时与任务完成后操作同一行
        row = QHBoxLayout()
        label = BodyLabel(tr("超时强制停止:"))
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.timeout_spin)
        # 间隔
        spacer = QLabel("")
        spacer.setFixedWidth(16)
        row.addWidget(spacer)
        post_label = BodyLabel(tr("任务完成后操作:"))
        post_label.setFixedWidth(120)
        row.addWidget(post_label)
        row.addWidget(self.post_action_combo)
        form.addLayout(row)

        # 完成后终止进程（可填写多个，逗号分隔）
        row = QHBoxLayout()
        label = BodyLabel(tr("完成后终止进程:"))
        label.setFixedWidth(label_width)
        self.kill_processes_edit = LineEdit(self)
        self.kill_processes_edit.setPlaceholderText(tr("例如: StarRail.exe, YuanShen.exe（逗号分隔多个进程）"))
        row.addWidget(label)
        row.addWidget(self.kill_processes_edit)
        form.addLayout(row)

        # 完成后推送通知（左对齐）
        row = QHBoxLayout()
        label = BodyLabel(tr("完成后推送通知:"))
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
            time_str = self.time_picker.time.toString('HH:mm')
            for t in (self.existing_tasks or []):
                if self.task and t.get('id') == self.task.get('id'):
                    continue
                if str(t.get('trigger_mode', 'time')).lower() != 'time':
                    continue
                if t.get('time') == time_str:
                    m = MessageBox(tr('错误'), tr('已存在相同时间的任务，请选择其他时间'), self)
                    m.cancelButton.hide()
                    m.yesButton.setText(tr('确认'))
                    m.exec()
                    return

        # 程序路径不能为空（非本体类型都要求路径）
        if self.program_type_combo.currentText() != tr('本体'):
            prog = self.program_path_edit.text().strip()
            if not prog:
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

    def _current_trigger_mode(self):
        idx = self.trigger_mode_combo.currentIndex() if self.trigger_mode_combo.count() > 0 else 0
        try:
            mode = self.trigger_mode_combo.itemData(idx)
        except Exception:
            mode = None
        return mode if mode in ('time', 'chain') else 'time'

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

    def _show_trigger_mode_help(self):
        content = tr(
            '按时启动：到达设定时间后，直接启动当前任务。\n'
            '链式启动：不会单独按时间触发，需要放在前一个任务后面；当前一个任务正常结束后，会按列表顺序立即启动。\n'
            '立即运行：从当前任务开始，后面连续的链式任务也会跟随执行。'
        )
        box = MessageBox(tr('启动方式说明'), content, self)
        box.cancelButton.hide()
        box.yesButton.setText(tr('确认'))
        box.exec()

    def _on_program_type_changed(self, text):
        """根据程序类型调整界面：本体 -> 显示任务下拉；外部程序 -> 显示路径与参数输入，并修改标签文本"""
        if text == tr('本体'):
            self.program_path_edit.setVisible(False)
            self.prog_btn.setVisible(False)
            self.args_edit.setVisible(False)
            self.args_combo.setVisible(True)
            # 更新标签为任务选择
            try:
                self.args_label.setText(tr('选择任务:'))
            except Exception:
                pass
        elif text == tr('外部程序'):
            self.program_path_edit.setVisible(True)
            self.prog_btn.setVisible(True)
            self.args_edit.setVisible(True)
            self.args_combo.setVisible(False)
            # 更新标签为启动参数
            try:
                self.args_label.setText(tr('启动参数:'))
                self.program_path_edit.setPlaceholderText(tr('外部程序或脚本的完整路径'))
            except Exception:
                pass
        else:
            # 检查是否为配置中的特殊程序（使用 display_name 的 tr 版本比较）
            found = None
            for sp in SPECIAL_PROGRAMS:
                if text == tr(sp.get('display_name')):
                    found = sp
                    break
            if found:
                self.program_path_edit.setVisible(True)
                self.prog_btn.setVisible(True)
                self.args_edit.setVisible(True)
                self.args_combo.setVisible(False)
                try:
                    self.args_label.setText(tr('启动参数:'))
                    # 显示可执行文件示例作为 placeholder
                    exe = found.get('executable', '')
                    self.program_path_edit.setPlaceholderText(tr("{} 的完整路径").format(exe))
                except Exception:
                    pass
            else:
                # fallback
                self.program_path_edit.setVisible(True)
                self.prog_btn.setVisible(True)
                self.args_edit.setVisible(True)
                self.args_combo.setVisible(False)
                try:
                    self.args_label.setText(tr('启动参数:'))
                except Exception:
                    pass

    def _on_program_type_activated(self, index):
        """仅在用户手动选择时应用默认参数（若参数为空）"""
        try:
            text = self.program_type_combo.itemText(index)
        except Exception:
            text = self.program_type_combo.currentText()
        # 本体/外部程序 手动选择 -> 清空名称与 args（让用户填写）
        if text == tr('本体') or text == tr('外部程序'):
            self.name_edit.setText('')
            self.args_edit.setText('')
            self.kill_processes_edit.setText('')
            return
        # 特殊程序：查找配置并应用 short_name 与默认 args（仅当 args 为空时）
        for sp in SPECIAL_PROGRAMS:
            if text == tr(sp.get('display_name')):
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

    def _load_task(self, task):
        self._set_trigger_mode(str(task.get('trigger_mode', 'time')).lower())
        self.name_edit.setText(task.get('name', ''))
        t = task.get('time', '04:00')
        parts = list(map(int, t.split(':')))
        self.time_picker.setTime(QTime(*parts))

        prog = task.get('program', 'self')
        if isinstance(prog, str) and prog.strip().lower() == 'self':
            # 本体任务
            self.program_type_combo.setCurrentText(tr('本体'))
            # 找到对应 task key 在 self._task_keys 中的索引
            args_key = task.get('args', 'main')
            try:
                idx = self._task_keys.index(args_key)
            except ValueError:
                # 备用：如果 args 是中文 label，就尝试匹配标签
                try:
                    idx = self._task_labels.index(args_key)
                except ValueError:
                    idx = 0
            self.args_combo.setCurrentIndex(idx)
        else:
            # 外部程序或特定外部类型
            self.program_path_edit.setText(str(prog))
            lower = str(prog).lower()
            # 如果文件名匹配特定的可识别 exe，则自动选择对应类型并填充默认参数（若无）
            basename = os.path.basename(lower)
            sp = _SPECIAL_BY_EXEC.get(basename.lower())
            if sp:
                # 找到配置中的特殊程序，设置为对应 display_name（tr 并显示）
                self.program_type_combo.setCurrentText(tr(sp.get('display_name')))
                self.args_edit.setText(task.get('args', ''))
            else:
                self.program_type_combo.setCurrentText(tr('外部程序'))
                self.args_edit.setText(task.get('args', ''))

        # task['timeout'] 存储为秒，UI 使用分钟单位，因此先转换
        try:
            self.timeout_spin.setValue(int(task.get('timeout', 0)) // 60)
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
        task = {}
        task['id'] = self.task.get('id') if self.task and self.task.get('id') else str(uuid.uuid4())
        task['name'] = self.name_edit.text().strip() or tr('未命名')
        task['trigger_mode'] = self._current_trigger_mode()
        # TimePicker.time is a QTime *object* (not a callable), so access property directly
        task['time'] = self.time_picker.time.toString('HH:mm')

        # 根据程序类型保存 program 字段：'self' 或 外部程序路径
        if self.program_type_combo.currentText() == tr('本体'):
            task['program'] = 'self'
            # args 保存为任务 id（key）而不是中文 label
            idx = self.args_combo.currentIndex() if self.args_combo.count() > 0 else 0
            task['args'] = self._task_keys[idx] if idx >= 0 and idx < len(self._task_keys) else 'main'
        else:
            task['program'] = self.program_path_edit.text().strip() or ''
            task['args'] = self.args_edit.text().strip()

        # 存储为秒（与现有运行/超时逻辑兼容）
        task['timeout'] = int(self.timeout_spin.value()) * 60
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


class ScheduleManagerDialog(MessageBox):
    """基于 MessageBox 的定时任务管理对话框"""

    def __init__(self, parent=None, scheduled_tasks=None, save_callback=None):
        super().__init__(tr('定时任务配置'), "", parent)
        self.scheduled_tasks = scheduled_tasks or []
        self.save_callback = save_callback

        # 清理默认内容
        try:
            self.textLayout.removeWidget(self.contentLabel)
            self.contentLabel.clear()
        except Exception:
            pass

        # 按钮调整（只显示一个关闭按钮）
        self.yesButton.hide()
        self.cancelButton.setText(tr('关闭'))
        self.buttonGroup.setMinimumWidth(480)

        # 表格
        self.table = TableWidget(self)
        self.table.setColumnCount(6)
        # 列顺序：启用, 名称, 时间/链式启动, 程序, 参数/任务, 推送通知
        self.table.setHorizontalHeaderLabels([tr('启用'), tr('名称'), tr('时间'), tr('程序'), tr('参数/任务'), tr('通知')])
        # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 60)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 160)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 90)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 150)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 60)
        self.table.setMinimumWidth(760)
        self.table.setMinimumHeight(350)
        # 只读表格设定：禁止直接编辑，整行选择，单选模式（只能通过按钮编辑）
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        # 操作按钮行（添加/编辑/删除）
        btn_layout = QHBoxLayout()
        self.add_btn = PushButton(tr('添加'), self)
        self.edit_btn = PushButton(tr('编辑'), self)
        self.move_up_btn = PushButton(tr('上移'), self)
        self.del_btn = PushButton(tr('删除'), self)
        self.run_btn = PrimaryPushButton(tr('立即运行'), self)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.move_up_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.run_btn)

        # 冲突处理：当定时任务触发且已有任务在运行时如何处理（skip/stop）
        conflict_label = BodyLabel(tr('冲突:'))
        # conflict_label.setFixedWidth(90)
        self.conflict_combo = ComboBox(self)
        # options: key, label
        self._conflict_options = [('skip', tr('跳过需要运行的任务')), ('stop', tr('停止正在运行的任务'))]
        for key, label in self._conflict_options:
            self.conflict_combo.addItem(label, userData=key)
        # 设定为配置里保存的值（默认 skip）
        try:
            cur = cfg.get_value('scheduled_on_conflict', 'skip')
            for i in range(self.conflict_combo.count()):
                if self.conflict_combo.itemData(i) == cur:
                    self.conflict_combo.setCurrentIndex(i)
                    break
        except Exception:
            pass
        # 保存设置到配置（用户更改时即时保存）
        try:
            self.conflict_combo.currentIndexChanged.connect(lambda i: cfg.set_value('scheduled_on_conflict', self.conflict_combo.itemData(i) or 'skip'))
        except Exception:
            pass

        chain_failure_label = BodyLabel(tr('链式失败后:'))
        self.chain_failure_combo = ComboBox(self)
        self._chain_failure_options = [
            (True, tr('继续后续任务')),
            (False, tr('停止后续任务')),
        ]
        for value, label in self._chain_failure_options:
            self.chain_failure_combo.addItem(label, userData=value)
        try:
            cur = cfg.get_value('scheduled_chain_continue_on_failure', True)
            if isinstance(cur, str):
                cur = cur.strip().lower() not in ('false', '0', 'no', 'stop')
            else:
                cur = bool(cur)
            for i in range(self.chain_failure_combo.count()):
                if self.chain_failure_combo.itemData(i) == cur:
                    self.chain_failure_combo.setCurrentIndex(i)
                    break
        except Exception:
            pass
        try:
            self.chain_failure_combo.currentIndexChanged.connect(
                lambda i: cfg.set_value(
                    'scheduled_chain_continue_on_failure',
                    self.chain_failure_combo.itemData(i) if self.chain_failure_combo.itemData(i) is not None else True,
                )
            )
        except Exception:
            pass

        btn_layout.addWidget(conflict_label)
        btn_layout.addWidget(self.conflict_combo)
        btn_layout.addWidget(chain_failure_label)
        btn_layout.addWidget(self.chain_failure_combo)
        btn_layout.addStretch()

        # 插入到 textLayout
        self.textLayout.addWidget(self.table, 0, Qt.AlignmentFlag.AlignTop)
        self.textLayout.addLayout(btn_layout)

        # 连接
        self.add_btn.clicked.connect(self._on_add)
        self.move_up_btn.clicked.connect(self._on_move_up)
        self.edit_btn.clicked.connect(lambda _checked=False: self._on_edit())
        self.del_btn.clicked.connect(self._on_delete)
        self.run_btn.clicked.connect(self._on_run_now)
        # 双击行打开编辑（等价于按编辑按钮）
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)

        # 加载数据
        self._reload_table()

    def _reload_table(self):
        self.table.clearContents()
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.scheduled_tasks))
        chain_visuals = self._build_chain_visuals()
        for i, t in enumerate(self.scheduled_tasks):
            trigger_mode = str(t.get('trigger_mode', 'time')).lower()
            chain_role = chain_visuals.get(i)
            # 启用（第一列）
            enabled_widget = QWidget()
            enabled_layout = QHBoxLayout(enabled_widget)
            enabled_layout.setContentsMargins(0, 0, 0, 0)
            enabled_layout.setSpacing(0)
            enabled_widget.setContentsMargins(0, 0, 0, 0)
            enabled_check = CheckBox('', enabled_widget)
            enabled_check.setChecked(bool(t.get('enabled', True)))
            enabled_check.stateChanged.connect(lambda _state, row=i: self._on_enabled_toggled(row))
            enabled_layout.addWidget(enabled_check, 0, Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(i, 0, enabled_widget)
            # 名称
            name_display = t.get('name', '')
            if chain_role == 'child':
                name_display = f"-> {name_display}"
            name_item = QTableWidgetItem(name_display)
            self.table.setItem(i, 1, name_item)
            # 时间列：按时任务显示时间，链式任务显示启动方式
            time_display = t.get('time', '') if trigger_mode == 'time' else tr('链式启动')
            time_item = QTableWidgetItem(time_display)
            self.table.setItem(i, 2, time_item)
            # 程序（本体显示“本体”，否则显示路径或文件名）
            prog = t.get('program', '')
            if prog == 'self':
                prog_display = tr('本体')
                prog_item = QTableWidgetItem(prog_display)
            else:
                prog_str = str(prog)
                # 判断是否为路径格式（绝对路径或包含路径分隔符），若是则仅显示文件名并在 tooltip 显示完整路径
                if os.path.isabs(prog_str) or ('\\' in prog_str) or ('/' in prog_str):
                    prog_display = os.path.basename(prog_str) or prog_str
                    prog_item = QTableWidgetItem(prog_display)
                    prog_item.setToolTip(prog_str)
                else:
                    prog_display = prog_str
                    prog_item = QTableWidgetItem(prog_display)
            self.table.setItem(i, 3, prog_item)
            # 参数/任务（如果是本体，显示本地化任务名）
            args = t.get('args', '')
            if prog == 'self':
                args_display = TASK_NAMES.get(args, args)
            else:
                args_display = args
            args_item = QTableWidgetItem(args_display)
            self.table.setItem(i, 4, args_item)
            notify_item = QTableWidgetItem(tr('是') if t.get('notify', False) else tr('否'))
            self.table.setItem(i, 5, notify_item)

            if trigger_mode == 'time':
                self._apply_time_task_visual_style(
                    [name_item, time_item, prog_item, args_item, notify_item]
                )

        self.table.resizeRowsToContents()
        self.table.doItemsLayout()
        self.table.viewport().update()

    def _build_chain_visuals(self):
        visuals = {}
        row = 0
        total = len(self.scheduled_tasks)

        while row < total:
            trigger_mode = str(self.scheduled_tasks[row].get('trigger_mode', 'time')).lower()
            if trigger_mode != 'time':
                row += 1
                continue

            end_row = row + 1
            while end_row < total:
                next_mode = str(self.scheduled_tasks[end_row].get('trigger_mode', 'time')).lower()
                if next_mode != 'chain':
                    break
                end_row += 1

            if end_row - row >= 2:
                visuals[row] = 'root'
                for child_row in range(row + 1, end_row):
                    visuals[child_row] = 'child'

            row = end_row

        return visuals

    def _apply_time_task_visual_style(self, items):
        for item in items:
            if item is None:
                continue
            font = item.font()
            font.setBold(True)
            item.setFont(font)

    def _on_enabled_toggled(self, row: int):
        if row < 0 or row >= len(self.scheduled_tasks):
            return
        enabled_widget = self.table.cellWidget(row, 0)
        if enabled_widget is None:
            return
        enabled_check = enabled_widget.findChild(CheckBox)
        if enabled_check is None:
            return
        self.scheduled_tasks[row]['enabled'] = bool(enabled_check.isChecked())
        if self.save_callback:
            self.save_callback(self.scheduled_tasks)

    def _on_add(self):
        dlg = AddEditScheduleDialog(self, scheduled_tasks=self.scheduled_tasks)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            task = dlg.get_task()
            self.scheduled_tasks.append(task)
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _move_task(self, row: int, target_row: int):
        if row < 0 or row >= len(self.scheduled_tasks):
            return False
        if target_row < 0 or target_row >= len(self.scheduled_tasks):
            return False
        if row == target_row:
            return False

        task = self.scheduled_tasks.pop(row)
        self.scheduled_tasks.insert(target_row, task)
        self._reload_table()
        self.table.selectRow(target_row)
        self.table.setCurrentCell(target_row, 1)
        if self.save_callback:
            self.save_callback(self.scheduled_tasks)
        return True

    def _on_move_up(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox(tr('提示'), tr('请先选择要上移的任务'), self)
            m.cancelButton.hide()
            m.yesButton.setText(tr('确认'))
            m.exec()
            return
        if row == 0:
            m = MessageBox(tr('提示'), tr('当前任务已经位于最上方'), self)
            m.cancelButton.hide()
            m.yesButton.setText(tr('确认'))
            m.exec()
            return
        self._move_task(row, row - 1)

    def _on_edit(self, row=None):
        if isinstance(row, bool):
            row = None
        if row is None:
            row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox(tr('提示'), tr('请先选择要编辑的任务'), self)
            m.cancelButton.hide()
            m.yesButton.setText(tr('确认'))
            m.exec()
            return
        task = self.scheduled_tasks[row]
        dlg = AddEditScheduleDialog(self, task=task, scheduled_tasks=self.scheduled_tasks)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.scheduled_tasks[row] = dlg.get_task()
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox(tr('提示'), tr('请先选择要删除的任务'), self)
            m.cancelButton.hide()
            m.yesButton.setText(tr('确认'))
            m.exec()
            return
        m = MessageBox(tr('确认'), tr('确认删除选中的定时任务？'), self)
        m.yesButton.setText(tr('确认'))
        m.cancelButton.setText(tr('取消'))
        if m.exec():
            self.scheduled_tasks.pop(row)
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _on_run_now(self):
        """立即运行所选任务（带确认），触发流程与 _checkScheduledTime 保持一致。"""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox(tr('提示'), tr('请先选择要运行的任务'), self)
            m.cancelButton.hide()
            m.yesButton.setText(tr('确认'))
            m.exec()
            return
        t = self.scheduled_tasks[row]
        # 确认
        m = MessageBox(tr('确认'), tr('确认立即运行任务 "{}" 吗？').format(t.get("name", "")), self)
        m.yesButton.setText(tr('确认'))
        m.cancelButton.setText(tr('取消'))
        if not m.exec():
            return

        try:
            parent = self.parent()
            # 启动任务
            if hasattr(parent, 'runScheduledTask'):
                # 检查是否有任务正在运行
                if parent.isTaskRunning():
                    InfoBar.warning(
                        title=tr('任务正在运行'),
                        content=tr("请先停止当前任务后再启动新任务"),
                        orient=Qt.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=parent
                    )
                    # 切换到日志界面
                    try:
                        self.close()
                    except Exception:
                        pass
                else:
                    if parent.runScheduledTask(t, tasks=self.scheduled_tasks, manual=True):
                        try:
                            self.close()
                        except Exception:
                            pass
            else:
                info = MessageBox(tr('错误'), tr('无法运行任务：父组件不支持 runScheduledTask'), self)
                info.cancelButton.hide()
                info.yesButton.setText(tr('确认'))
                info.exec()
        except Exception as e:
            m = MessageBox(tr('错误'), tr('启动任务失败: {}').format(e), self)
            m.cancelButton.hide()
            m.yesButton.setText(tr('确认'))
            m.exec()

    def _on_row_double_clicked(self, row: int, column: int):
        """双击表格任意单元格时触发编辑（等效于按编辑按钮）。"""
        # 保护性检查
        if row < 0 or row >= self.table.rowCount():
            return
        # 选中该行并打开编辑对话框
        self.table.selectRow(row)
        self.table.setCurrentCell(row, 1)
        self._on_edit(row)
