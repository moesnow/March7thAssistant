# coding:utf-8
from PyQt5.QtCore import Qt, QTime, QDateTime
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
                             QWidget, QFileDialog, QHeaderView, QComboBox,
                             QSpinBox, QCheckBox, QAbstractItemView)
from qfluentwidgets import TimePicker, BodyLabel, PushButton, TableWidget, MaskDialogBase, MessageBox, Dialog
from qfluentwidgets import LineEdit, ComboBox, CheckBox, SpinBox
from qfluentwidgets import InfoBar, InfoBarPosition
from utils.tasks import TASK_NAMES
import uuid
import os
import json
from module.config import cfg

# 从 assets/config/special_programs.json 加载特殊程序定义（若存在）
SPECIAL_PROGRAMS = []
_SPECIAL_BY_DISPLAY = {}
_SPECIAL_BY_EXEC = {}
try:
    cfg_path = "./assets/config/special_programs.json"
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
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
        super().__init__("添加/编辑定时任务", "", parent)
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
        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')
        self.buttonGroup.setMinimumWidth(480)

        # 名称
        self.name_edit = LineEdit(self)
        self.name_edit.setPlaceholderText("例如：完整运行")

        # 时间
        self.time_picker = TimePicker(self)
        # 默认时间设置为 04:00
        self.time_picker.setTime(QTime(4, 0))

        # 程序类型（'本体' 表示启动程序自身，'外部程序' 表示选择可执行文件）
        self.program_type_combo = ComboBox(self)
        # 程序类型：本体、外部程序，以及来自配置的特殊程序
        items = ['本体', '外部程序']
        for sp in SPECIAL_PROGRAMS:
            # display_name 可能包含空格等，本地化时使用 tr(display_name)
            items.append(self.tr(sp.get('display_name')))
        self.program_type_combo.addItems(items)

        # 可选的外部程序路径（仅当选择外部程序时启用）
        self.program_path_edit = LineEdit(self)
        self.program_path_edit.setMinimumWidth(400)
        self.program_path_edit.setPlaceholderText("外部程序或脚本的完整路径")
        self.prog_btn = PushButton("选择程序", self)
        self.prog_btn.clicked.connect(self._choose_program)

        prog_layout = QHBoxLayout()
        prog_layout.addWidget(self.program_type_combo)
        prog_layout.addWidget(self.program_path_edit)
        prog_layout.addWidget(self.prog_btn)

        # 启动参数（外部程序使用）或任务选择（本体使用）
        self.args_edit = LineEdit(self)
        self.args_edit.setPlaceholderText("外部程序启动参数（可选）")
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
        self.timeout_spin.setSuffix(" 分钟（0 表示不启用）")

        # 初始显示状态：默认选择本体
        self.program_type_combo.setCurrentText('本体')
        # 连接信号，在后面创建 args_label 后再触发一次以确保文本正确
        self.program_type_combo.currentTextChanged.connect(self._on_program_type_changed)
        # 连接 activated 信号，用于检测用户手动选择以应用默认参数（仅用户触发）
        self.program_type_combo.activated.connect(self._on_program_type_activated)

        # 完成后是否推送通知（布尔值）
        self.notify_check = CheckBox("完成后推送通知", self)
        self.notify_check.setChecked(False)

        # 任务完成后操作（显示为本地化标签，内部保存 key）
        self.post_action_combo = ComboBox(self)
        # keys 与 labels 对应
        self._post_action_items = [
            ("None", "无操作"),
            ("Shutdown", "关机"),
            ("Sleep", "睡眠"),
            ("Hibernate", "休眠"),
            ("Restart", "重启"),
            ("Logoff", "注销"),
            ("TurnOffDisplay", "关闭显示器"),
        ]
        self._post_action_keys = [k for k, l in self._post_action_items]
        self._post_action_labels = [l for k, l in self._post_action_items]
        self.post_action_combo.addItems(self._post_action_labels)

        # 完成后推送通知（默认：否）
        # 注意：字段名为 notify，布尔值，true 表示发送通知，false 不发送
        # 启用
        self.enable_check = CheckBox("启用", self)
        self.enable_check.setChecked(True)

        # 组合表单并添加到 textLayout（标签与控件左右排列）
        form = QVBoxLayout()
        label_width = 100

        # 启用（顶部左对齐）
        top_row = QHBoxLayout()
        top_row.addWidget(self.enable_check)
        top_row.addStretch()
        form.addLayout(top_row)

        # 名称与时间同一行
        row = QHBoxLayout()
        label = BodyLabel("任务名称:")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.name_edit, 1)
        # 时间放在同一行的右侧
        time_label = BodyLabel("启动时间:")
        time_label.setFixedWidth(90)
        row.addWidget(time_label)
        row.addWidget(self.time_picker)
        form.addLayout(row)

        # 程序路径行
        row = QHBoxLayout()
        label = BodyLabel("程序路径:")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addLayout(prog_layout)
        form.addLayout(row)

        # 启动参数 / 任务行（使用可变 label，随程序类型切换）
        row = QHBoxLayout()
        self.args_label = BodyLabel("启动参数 或 选择任务:")
        self.args_label.setFixedWidth(label_width)
        row.addWidget(self.args_label)
        row.addWidget(self.args_edit)
        row.addWidget(self.args_combo)
        form.addLayout(row)

        # 超时与任务完成后操作同一行
        row = QHBoxLayout()
        label = BodyLabel("超时强制停止:")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.timeout_spin)
        # 间隔
        spacer = QLabel("")
        spacer.setFixedWidth(16)
        row.addWidget(spacer)
        post_label = BodyLabel("任务完成后操作:")
        post_label.setFixedWidth(120)
        row.addWidget(post_label)
        row.addWidget(self.post_action_combo)
        form.addLayout(row)

        # 完成后终止进程（可填写多个，逗号分隔）
        row = QHBoxLayout()
        label = BodyLabel("完成后终止进程:")
        label.setFixedWidth(label_width)
        self.kill_processes_edit = LineEdit(self)
        self.kill_processes_edit.setPlaceholderText("例如: StarRail.exe, YuanShen.exe（逗号分隔多个进程）")
        row.addWidget(label)
        row.addWidget(self.kill_processes_edit)
        form.addLayout(row)

        # 完成后推送通知（左对齐）
        row = QHBoxLayout()
        label = BodyLabel("完成后推送通知:")
        label.setFixedWidth(label_width)
        row.addWidget(label)
        row.addWidget(self.notify_check)
        row.addStretch()
        form.addLayout(row)

        self.textLayout.addLayout(form, 0)

        # 确保 args_label 文本正确（首次打开时 program_type 已设为默认）
        self._on_program_type_changed(self.program_type_combo.currentText())

        # 如果是编辑，填充数据
        if self.task:
            self._load_task(self.task)

        # 当程序类型改变时切换参数输入模式
        # 已在构造中连接：self.program_type_combo.currentTextChanged -> _on_program_type_changed

    def exec_(self):
        """兼容旧调用：返回 QDialog.Accepted 或 QDialog.Rejected"""
        result = super().exec()
        return QDialog.Accepted if result else QDialog.Rejected

    def accept(self):
        """在确认前执行字段校验：名称非空，时间不重复，外部程序路径非空。"""
        name = self.name_edit.text().strip()
        if not name:
            m = MessageBox('错误', '任务名称不能为空', self)
            m.cancelButton.hide()
            m.yesButton.setText('确认')
            m.exec()
            return

        # 时间重复校验（跳过与当前编辑任务相同的 id）
        time_str = self.time_picker.time.toString('HH:mm')
        for t in (self.existing_tasks or []):
            if self.task and t.get('id') == self.task.get('id'):
                continue
            if t.get('time') == time_str:
                m = MessageBox('错误', '已存在相同时间的任务，请选择其他时间', self)
                m.cancelButton.hide()
                m.yesButton.setText('确认')
                m.exec()
                return

        # 程序路径不能为空（非本体类型都要求路径）
        if self.program_type_combo.currentText() != '本体':
            prog = self.program_path_edit.text().strip()
            if not prog:
                m = MessageBox('错误', '程序路径不能为空', self)
                m.cancelButton.hide()
                m.yesButton.setText('确认')
                m.exec()
                return

        # 其他字段（启动参数、消息）可为空，校验通过
        try:
            super().accept()
        except Exception:
            # 兼容性回退
            self.close()

    def _choose_program(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择程序或脚本", "", "可执行文件 (*.exe *.bat *.ps1);;所有文件 (*.*)")
        if path:
            # 将选择的路径填写到外部程序路径控件
            self.program_path_edit.setText(path)

    def _on_program_type_changed(self, text):
        """根据程序类型调整界面：本体 -> 显示任务下拉；外部程序 -> 显示路径与参数输入，并修改标签文本"""
        if text == '本体':
            self.program_path_edit.setVisible(False)
            self.prog_btn.setVisible(False)
            self.args_edit.setVisible(False)
            self.args_combo.setVisible(True)
            # 更新标签为任务选择
            try:
                self.args_label.setText('选择任务:')
            except Exception:
                pass
        elif text == '外部程序':
            self.program_path_edit.setVisible(True)
            self.prog_btn.setVisible(True)
            self.args_edit.setVisible(True)
            self.args_combo.setVisible(False)
            # 更新标签为启动参数
            try:
                self.args_label.setText('启动参数:')
                self.program_path_edit.setPlaceholderText('外部程序或脚本的完整路径')
            except Exception:
                pass
        else:
            # 检查是否为配置中的特殊程序（使用 display_name 的 tr 版本比较）
            found = None
            for sp in SPECIAL_PROGRAMS:
                if text == self.tr(sp.get('display_name')):
                    found = sp
                    break
            if found:
                self.program_path_edit.setVisible(True)
                self.prog_btn.setVisible(True)
                self.args_edit.setVisible(True)
                self.args_combo.setVisible(False)
                try:
                    self.args_label.setText('启动参数:')
                    # 显示可执行文件示例作为 placeholder
                    exe = found.get('executable', '')
                    self.program_path_edit.setPlaceholderText(self.tr(f'{exe} 的完整路径'))
                except Exception:
                    pass
            else:
                # fallback
                self.program_path_edit.setVisible(True)
                self.prog_btn.setVisible(True)
                self.args_edit.setVisible(True)
                self.args_combo.setVisible(False)
                try:
                    self.args_label.setText('启动参数:')
                except Exception:
                    pass

    def _on_program_type_activated(self, index):
        """仅在用户手动选择时应用默认参数（若参数为空）"""
        try:
            text = self.program_type_combo.itemText(index)
        except Exception:
            text = self.program_type_combo.currentText()
        # 本体/外部程序 手动选择 -> 清空名称与 args（让用户填写）
        if text == '本体' or text == '外部程序':
            self.name_edit.setText('')
            self.args_edit.setText('')
            self.kill_processes_edit.setText('')
            return
        # 特殊程序：查找配置并应用 short_name 与默认 args（仅当 args 为空时）
        for sp in SPECIAL_PROGRAMS:
            if text == self.tr(sp.get('display_name')):
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
        self.name_edit.setText(task.get('name', ''))
        t = task.get('time', '04:00')
        parts = list(map(int, t.split(':')))
        self.time_picker.setTime(QTime(*parts))

        prog = task.get('program', 'self')
        if isinstance(prog, str) and prog.strip().lower() == 'self':
            # 本体任务
            self.program_type_combo.setCurrentText('本体')
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
                self.program_type_combo.setCurrentText(self.tr(sp.get('display_name')))
                self.args_edit.setText(task.get('args', ''))
            else:
                self.program_type_combo.setCurrentText('外部程序')
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

    def get_task(self):
        task = {}
        task['id'] = self.task.get('id') if self.task and self.task.get('id') else str(uuid.uuid4())
        task['name'] = self.name_edit.text().strip() or '未命名'
        # TimePicker.time is a QTime *object* (not a callable), so access property directly
        task['time'] = self.time_picker.time.toString('HH:mm')

        # 根据程序类型保存 program 字段：'self' 或 外部程序路径
        if self.program_type_combo.currentText() == '本体':
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
        super().__init__('定时任务配置', "", parent)
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
        self.cancelButton.setText('关闭')
        self.buttonGroup.setMinimumWidth(480)

        # 表格
        self.table = TableWidget(self)
        # 新增一列：完成后终止进程
        self.table.setColumnCount(7)
        # 列顺序：启用, 名称, 时间, 程序, 参数/任务, 推送通知, 终止进程
        self.table.setHorizontalHeaderLabels(['启用', '名称', '时间', '程序', '参数/任务', '通知', '终止进程'])
        # self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 50)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 90)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 70)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 150)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 50)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setMinimumWidth(800)
        self.table.setMinimumHeight(350)
        # 只读表格设定：禁止直接编辑，整行选择，单选模式（只能通过按钮编辑）
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)

        # 操作按钮行（添加/编辑/删除）
        btn_layout = QHBoxLayout()
        self.add_btn = PushButton('添加', self)
        self.edit_btn = PushButton('编辑', self)
        self.del_btn = PushButton('删除', self)
        self.run_btn = PushButton('立即运行', self)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.del_btn)
        btn_layout.addWidget(self.run_btn)

        # 冲突处理：当定时任务触发且已有任务在运行时如何处理（skip/stop）
        conflict_label = BodyLabel('冲突处理:')
        # conflict_label.setFixedWidth(90)
        self.conflict_combo = ComboBox(self)
        # options: key, label
        self._conflict_options = [('skip', '跳过需要运行的任务'), ('stop', '停止正在运行的任务')]
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

        btn_layout.addWidget(conflict_label)
        btn_layout.addWidget(self.conflict_combo)
        btn_layout.addStretch()

        # 插入到 textLayout
        self.textLayout.addWidget(self.table, 0, Qt.AlignTop)
        self.textLayout.addLayout(btn_layout)

        # 连接
        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn.clicked.connect(self._on_edit)
        self.del_btn.clicked.connect(self._on_delete)
        self.run_btn.clicked.connect(self._on_run_now)
        # 双击行打开编辑（等价于按编辑按钮）
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)

        # 加载数据
        self._reload_table()

    def exec_(self):
        """兼容旧调用"""
        result = super().exec()
        return QDialog.Accepted if result else QDialog.Rejected

    def _reload_table(self):
        self.table.setRowCount(len(self.scheduled_tasks))
        for i, t in enumerate(self.scheduled_tasks):
            # 启用（第一列）
            enabled_item = QTableWidgetItem('是' if t.get('enabled', True) else '否')
            self.table.setItem(i, 0, enabled_item)
            # 名称
            self.table.setItem(i, 1, QTableWidgetItem(t.get('name', '')))
            # 时间
            self.table.setItem(i, 2, QTableWidgetItem(t.get('time', '')))
            # 程序（本体显示“本体”，否则显示路径或文件名）
            prog = t.get('program', '')
            if prog == 'self':
                prog_display = '本体'
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
            self.table.setItem(i, 4, QTableWidgetItem(args_display))
            notify_item = QTableWidgetItem('是' if t.get('notify', False) else '否')
            self.table.setItem(i, 5, notify_item)
            # 完成后终止进程显示（第 6 列，索引 6）
            kp = t.get('kill_processes', [])
            if isinstance(kp, list):
                kp_display = ', '.join(kp)
            else:
                kp_display = str(kp) if kp else ''
            self.table.setItem(i, 6, QTableWidgetItem(kp_display))

    def _on_add(self):
        dlg = AddEditScheduleDialog(self, scheduled_tasks=self.scheduled_tasks)
        if dlg.exec_() == QDialog.Accepted:
            task = dlg.get_task()
            self.scheduled_tasks.append(task)
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _on_edit(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox('提示', '请先选择要编辑的任务', self)
            m.cancelButton.hide()
            m.yesButton.setText('确认')
            m.exec()
            return
        task = self.scheduled_tasks[row]
        dlg = AddEditScheduleDialog(self, task=task, scheduled_tasks=self.scheduled_tasks)
        if dlg.exec_() == QDialog.Accepted:
            self.scheduled_tasks[row] = dlg.get_task()
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox('提示', '请先选择要删除的任务', self)
            m.cancelButton.hide()
            m.yesButton.setText('确认')
            m.exec()
            return
        m = MessageBox('确认', '确认删除选中的定时任务？', self)
        m.yesButton.setText('确认')
        m.cancelButton.setText('取消')
        if m.exec():
            self.scheduled_tasks.pop(row)
            self._reload_table()
            if self.save_callback:
                self.save_callback(self.scheduled_tasks)

    def _on_run_now(self):
        """立即运行所选任务（带确认），触发流程与 _checkScheduledTime 保持一致。"""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.scheduled_tasks):
            m = MessageBox('提示', '请先选择要运行的任务', self)
            m.cancelButton.hide()
            m.yesButton.setText('确认')
            m.exec()
            return
        t = self.scheduled_tasks[row]
        # 确认
        m = MessageBox('确认', self.tr(f'确认立即运行任务 "{t.get("name", "")}" 吗？'), self)
        m.yesButton.setText('确认')
        m.cancelButton.setText('取消')
        if not m.exec():
            return

        # 构建与 _checkScheduledTime 一致的任务字典
        task_for_start = {
            'program': t.get('program', 'self'),
            'args': t.get('args', ''),
            'timeout': int(t.get('timeout', 0) or 0),
            'name': t.get('name', ''),
            'notify': bool(t.get('notify', False)),
            'post_action': t.get('post_action', 'None'),
            'id': t.get('id'),
        }

        try:
            parent = self.parent()
            # 记录 pending meta 与触发时间戳（避免与定时器冲突）
            now_ts = QDateTime.currentDateTime().toSecsSinceEpoch()
            try:
                if hasattr(parent, '_pending_task_meta'):
                    parent._pending_task_meta = t
            except Exception:
                pass
            try:
                if hasattr(parent, '_last_triggered_ts') and t.get('id'):
                    parent._last_triggered_ts[t.get('id')] = now_ts
            except Exception:
                pass

            # 写日志（如果父组件支持）
            try:
                if hasattr(parent, 'appendLog'):
                    parent.appendLog(f"\n========== 定时任务手动触发 ({t.get('name', '未命名')} @ {t.get('time', '')}) ==========")
            except Exception:
                pass

            # 启动任务
            if hasattr(parent, 'startTask'):
                # 检查是否有任务正在运行
                if parent.isTaskRunning():
                    InfoBar.warning(
                        title='任务正在运行',
                        content="请先停止当前任务后再启动新任务",
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
                    parent.startTask(task_for_start)
                    try:
                        self.close()
                    except Exception:
                        pass
            else:
                info = MessageBox('错误', '无法运行任务：父组件不支持 startTask', self)
                info.cancelButton.hide()
                info.yesButton.setText('确认')
                info.exec()
        except Exception as e:
            m = MessageBox('错误', self.tr(f'启动任务失败: {e}'), self)
            m.cancelButton.hide()
            m.yesButton.setText('确认')
            m.exec()

    def _on_row_double_clicked(self, row: int, column: int):
        """双击表格任意单元格时触发编辑（等效于按编辑按钮）。"""
        # 保护性检查
        if row < 0 or row >= self.table.rowCount():
            return
        # 选中该行并打开编辑对话框
        self.table.selectRow(row)
        self.table.setCurrentCell(row, 0)
        self._on_edit()
