# coding:utf-8
import copy
import os
import re
import shlex
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    BodyLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    MessageBox,
    MessageBoxBase,
    PlainTextEdit,
    PrimaryPushButton,
    PushButton,
    RoundMenu,
    ScrollArea,
    SubtitleLabel,
    TreeWidget,
    SpinBox,
    DoubleSpinBox,
    CheckBox
)

import tasks.tool as tool
from module.localization import tr
from module.game import get_game_controller
from module.workflow import (
    CONDITION_TYPE_LABELS,
    STEP_TYPE_LABELS,
    WORKFLOW_USER_INFO_KEYS,
    can_change_to_screen_from_main,
    duplicate_workflow_name,
    export_workflow_to_zip,
    get_asset_directory,
    get_current_workflow_name,
    get_switchable_screen_name,
    get_switchable_screen_targets,
    import_asset_to_workflow,
    import_workflow_from_zip,
    is_workflow_read_only,
    load_workflows,
    normalize_step,
    save_workflows,
    set_current_workflow_name,
    summarize_step,
    to_workflow_relative_path,
)

from .common.style_sheet import StyleSheet

_SEMVER_RE = re.compile(
    r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)'
    r'(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?'
    r'(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$'
)


class WorkflowInfoDialog(MessageBoxBase):
    """配置流程作者、版本号、使用说明"""

    def __init__(self, workflow: dict, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(tr("流程信息"), self.widget)
        self.authorEdit = LineEdit(self.widget)
        self.authorEdit.setPlaceholderText(tr("作者（可不填）"))
        self.authorEdit.setClearButtonEnabled(True)
        self.authorEdit.setText(workflow.get("author", ""))
        self.versionEdit = LineEdit(self.widget)
        self.versionEdit.setPlaceholderText(tr("例：1.0.0（可不填）"))
        self.versionEdit.setClearButtonEnabled(True)
        self.versionEdit.setText(workflow.get("version", "") or "1.0.0")
        self.versionHint = BodyLabel(tr("版本号格式不正确，请使用 SemVer 格式（如 1.0.0）"), self.widget)
        self.versionHint.setStyleSheet("color: #e74c3c;")
        self.versionHint.setWordWrap(True)
        self.versionHint.setVisible(False)
        self.descEdit = PlainTextEdit(self.widget)
        self.descEdit.setPlaceholderText(tr("使用说明（可不填）"))
        self.descEdit.setPlainText(workflow.get("description", ""))
        self.descEdit.setFixedHeight(100)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.setSpacing(8)
        self.viewLayout.addWidget(BodyLabel(tr("作者"), self.widget))
        self.viewLayout.addWidget(self.authorEdit)
        self.viewLayout.addWidget(BodyLabel(tr("版本号"), self.widget))
        self.viewLayout.addWidget(self.versionEdit)
        self.viewLayout.addWidget(self.versionHint)
        self.viewLayout.addWidget(BodyLabel(tr("使用说明"), self.widget))
        self.viewLayout.addWidget(self.descEdit)
        self.widget.setMinimumWidth(420)
        self.yesButton.setText(tr("保存"))
        self.cancelButton.setText(tr("取消"))

    def validate(self) -> bool:
        version = self.versionEdit.text().strip()
        if version and not _SEMVER_RE.match(version):
            self.versionHint.setVisible(True)
            return False
        self.versionHint.setVisible(False)
        return True


class InputDialog(MessageBoxBase):
    """带输入框的 Fluent 风格对话框"""

    def __init__(self, title: str, placeholder: str = "", default: str = "", parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel(title, self.widget)
        self.inputEdit = LineEdit(self.widget)
        self.inputEdit.setPlaceholderText(placeholder)
        self.inputEdit.setText(default)
        self.inputEdit.setClearButtonEnabled(True)
        self.inputEdit.returnPressed.connect(self.yesButton.click)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.inputEdit)
        self.widget.setMinimumWidth(380)
        self.yesButton.setText(tr("确定"))
        self.cancelButton.setText(tr("取消"))

    def validate(self) -> bool:
        return bool(self.inputEdit.text().strip())


class StepEditDialog(QDialog):
    STEP_TYPES = [
        "click_image",
        "click_text",
        "click_crop",
        "find_image",
        "find_text",
        "play_audio",
        "send_message",
        "switch_screen",
        "press_key",
        "wait",
        "if",
        "for",
        "while",
        "stop_workflow",
        "break",
        "continue",
    ]
    CONDITION_TYPES = [
        "image_exists",
        "image_not_exists",
        "text_exists",
        "text_not_exists",
        "last_result",
        "last_result_failed",
    ]
    CONTROL_STEP_TYPES = {"if", "for", "while"}

    def __init__(self, step=None, workflow=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("编辑步骤"))
        self.resize(640, 420)
        self.setMinimumWidth(560)

        self.original_step = normalize_step(step or {"type": "click_text"})
        self.workflow = workflow
        self.step_type_labels = [tr(STEP_TYPE_LABELS[key]) for key in self.STEP_TYPES]
        self.condition_type_labels = [tr(CONDITION_TYPE_LABELS[key]) for key in self.CONDITION_TYPES]
        self.rows = {}

        main_layout = QVBoxLayout(self)

        title_label = QLabel(tr("编辑步骤"))
        title_label.setStyleSheet("font-size: 20px; font-weight: 600; padding: 6px 0;")
        main_layout.addWidget(title_label)

        self.descriptionLabel = BodyLabel(tr("支持 if / for / while，以及图片点击、文字点击等能力。\n检测区域可先点击“采集图像模板”，再用“复制坐标”获取。"))
        self.descriptionLabel.setWordWrap(True)
        main_layout.addWidget(self.descriptionLabel)

        self.formWidget = QWidget(self)
        self.formLayout = QVBoxLayout(self.formWidget)
        self.formLayout.setContentsMargins(0, 8, 0, 0)
        self.formLayout.setSpacing(10)
        main_layout.addWidget(self.formWidget, 1)

        self.typeCombo = ComboBox(self)
        self.typeCombo.addItems(self.step_type_labels)
        self.conditionTypeCombo = ComboBox(self)
        self.conditionTypeCombo.addItems(self.condition_type_labels)
        self.templatePathEdit = LineEdit(self)
        self.templatePathEdit.setPlaceholderText(tr("选择已保存的模板图片路径"))
        self.templateBrowseButton = PushButton(FIF.FOLDER, tr("浏览"), self)
        self.textEdit = LineEdit(self)
        self.textEdit.setPlaceholderText(tr("输入文字内容（搜索、消息或点击文字）"))
        self.audioPathEdit = LineEdit(self)
        self.audioPathEdit.setPlaceholderText(tr("输入音频文件路径，默认 ./assets/audio/pa.mp3"))
        self.audioBrowseButton = PushButton(FIF.MUSIC, tr("浏览"), self)
        self.screenTargetCombo = ComboBox(self)
        self.cropEdit = LineEdit(self)
        self.cropEdit.setPlaceholderText(tr("留空表示全屏，例如 (100 / 1920, 200 / 1080, 300 / 1920, 120 / 1080)"))
        self.thresholdSpin = DoubleSpinBox(self)
        self.thresholdSpin.setRange(0.0, 1.0)
        self.thresholdSpin.setDecimals(2)
        self.thresholdSpin.setSingleStep(0.05)
        self.maxRetriesSpin = SpinBox(self)
        self.maxRetriesSpin.setRange(1, 99)
        self.secondsSpin = DoubleSpinBox(self)
        self.secondsSpin.setRange(0.0, 3600.0)
        self.secondsSpin.setDecimals(1)
        self.secondsSpin.setSingleStep(0.5)
        self.countSpin = SpinBox(self)
        self.countSpin.setRange(0, 9999)
        self.countSpin.setSpecialValueText(tr("无限"))
        self.maxIterationsSpin = SpinBox(self)
        self.maxIterationsSpin.setRange(0, 9999)
        self.maxIterationsSpin.setSpecialValueText(tr("无限"))
        self.includeCheck = CheckBox(tr("使用包含匹配"), self)
        self.withScreenshotCheck = CheckBox(tr("发送截图"), self)
        self.keyEdit = LineEdit(self)
        self.keyEdit.setPlaceholderText(tr("输入按键名，如 enter, space, a, b 等"))
        self.keyDurationSpin = DoubleSpinBox(self)
        self.keyDurationSpin.setRange(0.0, 60.0)
        self.keyDurationSpin.setDecimals(2)
        self.keyDurationSpin.setSingleStep(0.1)
        self.keyActionCombo = ComboBox(self)
        self.keyActionCombo.addItems([tr("点击"), tr("按下"), tr("松开")])
        self.clickActionCombo = ComboBox(self)
        self.clickActionCombo.addItems([tr("点击"), tr("按下"), tr("松开")])
        self.pressDurationSpin = DoubleSpinBox(self)
        self.pressDurationSpin.setRange(0.0, 60.0)
        self.pressDurationSpin.setDecimals(2)
        self.pressDurationSpin.setSingleStep(0.1)

        self._add_row(tr("步骤类型"), self.typeCombo, key="type")
        self._add_row(tr("条件类型"), self.conditionTypeCombo, key="condition")
        self._add_row(tr("模板路径"), self.templatePathEdit, self.templateBrowseButton, key="template")
        self._add_row(tr("目标文字"), self.textEdit, key="text")
        self._add_row(tr("音频路径"), self.audioPathEdit, self.audioBrowseButton, key="audio")
        self._add_row(tr("目标界面"), self.screenTargetCombo, key="target_screen")
        self._add_row(tr("检测区域"), self.cropEdit, key="crop")
        self._add_row(tr("图片阈值"), self.thresholdSpin, key="threshold")
        self._add_row(tr("重试次数"), self.maxRetriesSpin, key="retries")
        self._add_row(tr("等待秒数"), self.secondsSpin, key="seconds")
        self._add_row(tr("循环次数"), self.countSpin, key="count")
        self._add_row(tr("最大循环次数"), self.maxIterationsSpin, key="max_iterations")
        self._add_row(tr("文字匹配"), self.includeCheck, key="include")
        self._add_row(tr("发送截图"), self.withScreenshotCheck, key="with_screenshot")
        self._add_row(tr("按键名"), self.keyEdit, key="key")
        self._add_row(tr("按键时长"), self.keyDurationSpin, key="key_duration")
        self._add_row(tr("按键动作"), self.keyActionCombo, key="key_action")
        self._add_row(tr("点击动作"), self.clickActionCombo, key="click_action")
        self._add_row(tr("按下时长"), self.pressDurationSpin, key="press_duration")
        self.formLayout.addStretch(1)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.okButton = PrimaryPushButton(tr("确定"), self)
        self.cancelButton = PushButton(tr("取消"), self)
        button_layout.addWidget(self.okButton)
        button_layout.addWidget(self.cancelButton)
        main_layout.addLayout(button_layout)

        self.templateBrowseButton.clicked.connect(self._browse_template)
        self.audioBrowseButton.clicked.connect(self._browse_audio)
        self.typeCombo.currentIndexChanged.connect(self._update_visible_rows)
        self.conditionTypeCombo.currentIndexChanged.connect(self._update_visible_rows)
        self.okButton.clicked.connect(self._on_accept)
        self.cancelButton.clicked.connect(self.reject)

        self._load_screen_targets()
        self._load_original_step()
        self._update_visible_rows()

    def _add_row(self, label_text: str, *widgets, key: str):
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(label_text, row)
        label.setFixedWidth(96)
        layout.addWidget(label)
        for widget in widgets:
            stretch = 0 if isinstance(widget, PushButton) else 1
            layout.addWidget(widget, stretch)
        self.formLayout.addWidget(row)
        self.rows[key] = row

    def _load_original_step(self):
        step_type = self.original_step["type"]
        if step_type in self.STEP_TYPES:
            self.typeCombo.setCurrentIndex(self.STEP_TYPES.index(step_type))

        condition_type = self.original_step["condition_type"]
        if condition_type in self.CONDITION_TYPES:
            self.conditionTypeCombo.setCurrentIndex(self.CONDITION_TYPES.index(condition_type))

        self.templatePathEdit.setText(self.original_step["template_path"])
        self.textEdit.setText(self.original_step["text"])
        self.audioPathEdit.setText(self.original_step["audio_path"])
        self._set_screen_target(self.original_step.get("target_screen", ""))
        self.cropEdit.setText(self.original_step["crop"])
        self.thresholdSpin.setValue(self.original_step["threshold"])
        self.maxRetriesSpin.setValue(self.original_step["max_retries"])
        self.secondsSpin.setValue(self.original_step["seconds"])
        self.countSpin.setValue(self.original_step["count"])
        self.maxIterationsSpin.setValue(self.original_step["max_iterations"])
        self.includeCheck.setChecked(self.original_step["include"])
        self.withScreenshotCheck.setChecked(self.original_step.get("with_screenshot", False))
        self.keyEdit.setText(self.original_step.get("key", ""))
        self.keyDurationSpin.setValue(self.original_step.get("key_duration", 0.1))

        # 设置按键动作
        key_action = self.original_step.get("key_action", "press_and_release")
        key_action_map = {"press_and_release": 0, "press": 1, "release": 2}
        self.keyActionCombo.setCurrentIndex(key_action_map.get(key_action, 0))

        # 设置点击动作
        click_action = self.original_step.get("click_action", "press_and_release")
        click_action_map = {"press_and_release": 0, "press": 1, "release": 2}
        self.clickActionCombo.setCurrentIndex(click_action_map.get(click_action, 0))

        self.pressDurationSpin.setValue(self.original_step.get("press_duration", 0.1))

    def _current_step_type(self) -> str:
        return self.STEP_TYPES[self.typeCombo.currentIndex()]

    def _current_condition_type(self) -> str:
        return self.CONDITION_TYPES[self.conditionTypeCombo.currentIndex()]

    def _update_visible_rows(self):
        step_type = self._current_step_type()
        condition_type = self._current_condition_type()

        visible_rows = {"type"}

        if step_type == "click_image":
            visible_rows.update({"template", "threshold", "crop", "retries", "click_action", "press_duration"})
        elif step_type == "click_text":
            visible_rows.update({"text", "include", "crop", "retries", "click_action", "press_duration"})
        elif step_type == "click_crop":
            visible_rows.update({"crop", "click_action", "press_duration"})
        elif step_type == "find_image":
            visible_rows.update({"template", "threshold", "crop", "retries"})
        elif step_type == "find_text":
            visible_rows.update({"text", "include", "crop", "retries"})
        elif step_type == "play_audio":
            visible_rows.update({"audio"})
        elif step_type == "send_message":
            visible_rows.update({"text", "with_screenshot"})
        elif step_type == "switch_screen":
            visible_rows.update({"target_screen"})
        elif step_type == "press_key":
            visible_rows.update({"key", "key_duration", "key_action"})
        elif step_type == "wait":
            visible_rows.update({"seconds"})
        elif step_type == "for":
            visible_rows.update({"count"})
        elif step_type in {"if", "while"}:
            visible_rows.update({"condition"})
            if condition_type in {"image_exists", "image_not_exists"}:
                visible_rows.update({"template", "threshold", "crop"})
            elif condition_type in {"text_exists", "text_not_exists"}:
                visible_rows.update({"text", "include", "crop"})
            if step_type == "while":
                visible_rows.update({"max_iterations"})

        for key, row in self.rows.items():
            row.setVisible(key in visible_rows)

    def _browse_template(self):
        default_dir = get_asset_directory("template", self.workflow)
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("选择模板图片"),
            default_dir,
            "Image Files (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if file_path:
            self.templatePathEdit.setText(import_asset_to_workflow(file_path, "template", self.workflow))

    def _browse_audio(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("选择音频文件"),
            os.path.abspath("./assets/audio"),
            "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a);;All Files (*)"
        )
        if file_path:
            self.audioPathEdit.setText(to_workflow_relative_path(file_path, self.workflow))

    def _load_screen_targets(self):
        self.screenTargetCombo.clear()
        for screen_id, screen_name in get_switchable_screen_targets():
            self.screenTargetCombo.addItem(f"{screen_name} ({screen_id})", userData=screen_id)

    def _set_screen_target(self, target_screen: str):
        if not target_screen:
            return

        for index in range(self.screenTargetCombo.count()):
            if self.screenTargetCombo.itemData(index) == target_screen:
                self.screenTargetCombo.setCurrentIndex(index)
                return

        screen_name = get_switchable_screen_name(target_screen)
        display_name = f"{screen_name} ({target_screen})" if screen_name else target_screen
        self.screenTargetCombo.addItem(display_name, userData=target_screen)
        self.screenTargetCombo.setCurrentIndex(self.screenTargetCombo.count() - 1)

    def _validate(self) -> tuple[bool, str]:
        step_type = self._current_step_type()
        condition_type = self._current_condition_type()

        if step_type in {"click_image", "find_image"} and not self.templatePathEdit.text().strip():
            return False, tr("请选择模板图片")

        if step_type in {"click_text", "find_text"} and not self.textEdit.text().strip():
            return False, tr("请输入目标文字")

        if step_type == "click_crop" and not self.cropEdit.text().strip():
            return False, tr("点击坐标需要填写检测区域")

        if step_type == "play_audio" and not self.audioPathEdit.text().strip():
            return False, tr("请输入音频文件路径")

        if step_type == "send_message" and not self.textEdit.text().strip():
            return False, tr("请输入消息内容")

        if step_type == "switch_screen":
            target_screen = str(self.screenTargetCombo.currentData() or "").strip()
            if not target_screen:
                return False, tr("请选择目标界面")
            if not can_change_to_screen_from_main(target_screen):
                return False, tr("目标界面不可切换")

        if step_type == "press_key" and not self.keyEdit.text().strip():
            return False, tr("请输入按键名")

        if step_type in {"if", "while"}:
            if condition_type in {"image_exists", "image_not_exists"} and not self.templatePathEdit.text().strip():
                return False, tr("图片条件需要选择模板图片")
            if condition_type in {"text_exists", "text_not_exists"} and not self.textEdit.text().strip():
                return False, tr("文字条件需要填写目标文字")

        return True, ""

    def _on_accept(self):
        is_valid, message = self._validate()
        if not is_valid:
            InfoBar.error(
                title=tr("保存失败"),
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return
        self.accept()

    def get_step_data(self) -> dict:
        step_type = self._current_step_type()

        # 映射按键动作
        key_action_map = ["press_and_release", "press", "release"]
        key_action = key_action_map[self.keyActionCombo.currentIndex()]

        # 映射点击动作
        click_action_map = ["press_and_release", "press", "release"]
        click_action = click_action_map[self.clickActionCombo.currentIndex()]

        step = {
            "type": step_type,
            "text": self.textEdit.text().strip(),
            "audio_path": self.audioPathEdit.text().strip(),
            "target_screen": str(self.screenTargetCombo.currentData() or "").strip(),
            "template_path": self.templatePathEdit.text().strip(),
            "threshold": self.thresholdSpin.value(),
            "crop": self.cropEdit.text().strip(),
            "include": self.includeCheck.isChecked(),
            "max_retries": self.maxRetriesSpin.value(),
            "seconds": self.secondsSpin.value(),
            "count": self.countSpin.value(),
            "condition_type": self._current_condition_type(),
            "max_iterations": self.maxIterationsSpin.value(),
            "with_screenshot": self.withScreenshotCheck.isChecked(),
            "key": self.keyEdit.text().strip(),
            "key_duration": self.keyDurationSpin.value(),
            "key_action": key_action,
            "click_action": click_action,
            "press_duration": self.pressDurationSpin.value(),
            "children": copy.deepcopy(self.original_step.get("children", [])) if step_type in self.CONTROL_STEP_TYPES else [],
        }
        return normalize_step(step)


class WorkflowInterface(ScrollArea):
    CONTROL_STEP_TYPES = {"if", "for", "while"}

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.titleLabel = QLabel(tr("流程编排"), self)
        self.workflows = load_workflows()
        self.pathItemMap = {}
        self.treeWorkflowName = None

        self.__initWidget()
        self._refresh_workflow_combo(get_current_workflow_name())
        self._refresh_tree()

    def __initWidget(self):
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("workflowInterface")

        self.view.setObjectName("view")
        self.titleLabel.setObjectName("workflowLabel")
        StyleSheet.WORKFLOW_INTERFACE.apply(self)

        self._build_cards()
        self._build_layout()
        self._connect_signals()

    def _build_cards(self):
        self.summaryCard = CardWidget(self.view)
        self.summaryLayout = QVBoxLayout(self.summaryCard)
        self.summaryLayout.setContentsMargins(20, 20, 20, 20)
        self.summaryLayout.setSpacing(14)

        self.summaryTitle = QLabel(tr("像快捷指令一样拼流程") + " " + tr("【测试版】"), self.summaryCard)
        self.summaryTitle.setObjectName("workflowSummaryTitle")
        # self.summaryText = BodyLabel(tr("当前版本先支持 if / for / while、图片点击、文字点击，以及 OCR 判断。通过树状步骤管理子流程，适合先做稳定的基础自动化。"))
        # self.summaryText.setWordWrap(True)

        workflow_row = QHBoxLayout()
        workflow_row.setSpacing(8)
        self.workflowCombo = ComboBox(self.summaryCard)
        self.newWorkflowButton = PushButton(FIF.ADD, tr("新建流程"), self.summaryCard)
        self.renameWorkflowButton = PushButton(FIF.EDIT, tr("重命名"), self.summaryCard)
        self.deleteWorkflowButton = PushButton(FIF.DELETE, tr("删除流程"), self.summaryCard)
        self.workflowInfoButton = PushButton(FIF.INFO, tr("流程信息"), self.summaryCard)
        workflow_row.addWidget(QLabel(tr("当前流程"), self.summaryCard))
        workflow_row.addWidget(self.workflowCombo, 1)
        workflow_row.addWidget(self.newWorkflowButton)
        workflow_row.addWidget(self.renameWorkflowButton)
        workflow_row.addWidget(self.deleteWorkflowButton)
        workflow_row.addWidget(self.workflowInfoButton)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.runButton = PrimaryPushButton(FIF.PLAY, tr("运行流程"), self.summaryCard)
        self.stopButton = PushButton(FIF.CLOSE, tr("停止流程"), self.summaryCard)
        self.stopButton.setEnabled(True)
        self.captureTemplateButton = PushButton(FIF.CAMERA, tr("采集图像模板"), self.summaryCard)
        self.openTemplateDirButton = PushButton(FIF.FOLDER, tr("打开模板目录"), self.summaryCard)
        self.importWorkflowButton = PushButton(FIF.DOWNLOAD, tr("导入流程"), self.summaryCard)
        self.exportWorkflowButton = PushButton(FIF.SAVE_AS, tr("导出流程"), self.summaryCard)
        action_row.addWidget(self.runButton)
        action_row.addWidget(self.stopButton)
        action_row.addStretch(1)
        action_row.addWidget(self.captureTemplateButton)
        action_row.addWidget(self.openTemplateDirButton)
        action_row.addWidget(self.importWorkflowButton)
        action_row.addWidget(self.exportWorkflowButton)

        self.summaryLayout.addWidget(self.summaryTitle)
        # self.summaryLayout.addWidget(self.summaryText)
        self.summaryLayout.addLayout(workflow_row)
        self.summaryLayout.addLayout(action_row)

        self.editorCard = CardWidget(self.view)
        self.editorLayout = QVBoxLayout(self.editorCard)
        self.editorLayout.setContentsMargins(20, 20, 20, 20)
        self.editorLayout.setSpacing(12)

        editor_header = QHBoxLayout()
        self.editorTitle = QLabel(tr("步骤树"), self.editorCard)
        self.editorHint = BodyLabel(tr("控制节点支持添加子步骤"))
        editor_header.addWidget(self.editorTitle)
        editor_header.addSpacing(8)
        editor_header.addWidget(self.editorHint)
        editor_header.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        self.addStepButton = PushButton(FIF.ADD, tr("添加步骤"), self.editorCard)
        self.addChildButton = PushButton(FIF.ADD_TO, tr("添加子步骤"), self.editorCard)
        self.editStepButton = PushButton(FIF.EDIT, tr("编辑步骤"), self.editorCard)
        self.deleteStepButton = PushButton(FIF.DELETE, tr("删除步骤"), self.editorCard)
        self.moveUpButton = PushButton(tr("上移"), self.editorCard)
        self.moveDownButton = PushButton(tr("下移"), self.editorCard)
        button_row.addWidget(self.addStepButton)
        button_row.addWidget(self.addChildButton)
        button_row.addWidget(self.editStepButton)
        button_row.addWidget(self.deleteStepButton)
        button_row.addStretch(1)
        button_row.addWidget(self.moveUpButton)
        button_row.addWidget(self.moveDownButton)

        self.stepTree = TreeWidget(self.editorCard)
        self.stepTree.setColumnCount(2)
        self.stepTree.setHeaderLabels([tr("步骤"), tr("说明")])
        self.stepTree.setAlternatingRowColors(False)
        self.stepTree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.stepTree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.stepTree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stepTree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.stepTree.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.stepTree.setExpandsOnDoubleClick(False)
        self.stepTree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.stepTree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.stepTree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        self.editorLayout.addLayout(editor_header)
        self.editorLayout.addLayout(button_row)
        self.editorLayout.addWidget(self.stepTree)

    def _build_layout(self):
        self.titleLabel.move(36, 30)

        self.vBoxLayout.setSpacing(18)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)
        self.vBoxLayout.addWidget(self.summaryCard)
        self.vBoxLayout.addWidget(self.editorCard)
        self.vBoxLayout.addStretch(1)

    def _connect_signals(self):
        self.workflowCombo.currentIndexChanged.connect(self._on_workflow_changed)
        self.newWorkflowButton.clicked.connect(self._create_workflow)
        self.renameWorkflowButton.clicked.connect(self._rename_workflow)
        self.deleteWorkflowButton.clicked.connect(self._delete_workflow)
        self.workflowInfoButton.clicked.connect(self._edit_workflow_info)
        self.importWorkflowButton.clicked.connect(self._import_workflow)
        self.exportWorkflowButton.clicked.connect(self._export_workflow)
        self.runButton.clicked.connect(self._run_current_workflow)
        self.stopButton.clicked.connect(self._stop_current_workflow)
        self.captureTemplateButton.clicked.connect(lambda: self._start_capture("template"))
        self.openTemplateDirButton.clicked.connect(lambda: self._open_directory(get_asset_directory("template", self._current_workflow())))
        self.addStepButton.clicked.connect(self._add_step)
        self.addChildButton.clicked.connect(self._add_child_step)
        self.editStepButton.clicked.connect(self._edit_selected_step)
        self.deleteStepButton.clicked.connect(self._delete_selected_step)
        self.moveUpButton.clicked.connect(lambda: self._move_selected_step(-1))
        self.moveDownButton.clicked.connect(lambda: self._move_selected_step(1))
        self.stepTree.itemSelectionChanged.connect(self._update_workflow_action_state)
        self.stepTree.itemExpanded.connect(lambda *_: self._update_step_tree_height())
        self.stepTree.itemCollapsed.connect(lambda *_: self._update_step_tree_height())
        self.stepTree.itemDoubleClicked.connect(lambda *_: self._edit_selected_step())
        self.stepTree.customContextMenuRequested.connect(self._show_step_context_menu)

    def _update_step_tree_height(self):
        row_height = self.stepTree.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 34

        visible_rows = 0

        def count_visible_rows(item: QTreeWidgetItem):
            nonlocal visible_rows
            visible_rows += 1
            if item.isExpanded():
                for i in range(item.childCount()):
                    count_visible_rows(item.child(i))

        for i in range(self.stepTree.topLevelItemCount()):
            count_visible_rows(self.stepTree.topLevelItem(i))

        header_height = self.stepTree.header().height() if not self.stepTree.header().isHidden() else 0
        frame_height = self.stepTree.frameWidth() * 2
        content_height = header_height + frame_height + max(1, visible_rows) * row_height + 4
        self.stepTree.setFixedHeight(content_height)

    def _current_workflow(self) -> dict:
        index = max(0, self.workflowCombo.currentIndex())
        return self.workflows[index]

    def _save_workflows(self):
        save_workflows(self.workflows)

    def _current_workflow_is_read_only(self) -> bool:
        if not self.workflows:
            return False
        return is_workflow_read_only(self._current_workflow())

    def _can_add_child_to_selected_step(self, show_message: bool = False) -> bool:
        selected_path = self._selected_path()
        if selected_path is None:
            if show_message:
                InfoBar.warning(
                    title=tr("无法添加子步骤"),
                    content=tr("请先选中一个 if / for / while 节点"),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self,
                )
            return False

        if self._step_for_path(selected_path).get("type") not in self.CONTROL_STEP_TYPES:
            if show_message:
                InfoBar.warning(
                    title=tr("无法添加子步骤"),
                    content=tr("只有 if / for / while 才能包含子步骤"),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self,
                )
            return False

        return True

    def _update_workflow_action_state(self):
        if not self.workflows:
            return

        editable = not self._current_workflow_is_read_only()

        self.renameWorkflowButton.setEnabled(editable)
        self.deleteWorkflowButton.setEnabled(editable and len(self.workflows) > 1)
        self.workflowInfoButton.setEnabled(editable)
        self.importWorkflowButton.setEnabled(True)
        self.exportWorkflowButton.setEnabled(True)
        self.captureTemplateButton.setEnabled(editable)
        self.addStepButton.setEnabled(editable)
        self.addChildButton.setEnabled(editable and self._can_add_child_to_selected_step())
        self.editStepButton.setEnabled(editable)
        self.deleteStepButton.setEnabled(editable)
        self.moveUpButton.setEnabled(editable)
        self.moveDownButton.setEnabled(editable)

    def _refresh_workflow_combo(self, selected_name=None):
        self.workflows = load_workflows()
        names = [workflow["name"] for workflow in self.workflows]
        if not selected_name or selected_name not in names:
            selected_name = names[0]

        self.workflowCombo.blockSignals(True)
        self.workflowCombo.clear()
        self.workflowCombo.addItems(names)
        self.workflowCombo.setCurrentIndex(names.index(selected_name))
        self.workflowCombo.blockSignals(False)
        set_current_workflow_name(selected_name)
        self._update_workflow_action_state()

    def _refresh_tree(self, selected_path=None):
        self.treeWorkflowName = None
        self.pathItemMap = {}
        self.stepTree.clear()
        current_workflow = self._current_workflow()

        def add_items(parent_item, steps, path_prefix):
            for index, step in enumerate(steps):
                path = tuple(path_prefix + [index])
                title, detail = summarize_step(step)
                item = QTreeWidgetItem([title, detail or ""])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                if parent_item is None:
                    self.stepTree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                self.pathItemMap[path] = item
                if step.get("children"):
                    add_items(item, step["children"], list(path))
                    item.setExpanded(True)

        add_items(None, current_workflow.get("steps", []), [])
        if selected_path and tuple(selected_path) in self.pathItemMap:
            self.stepTree.setCurrentItem(self.pathItemMap[tuple(selected_path)])
        elif self.stepTree.topLevelItemCount() > 0:
            self.stepTree.setCurrentItem(self.stepTree.topLevelItem(0))
        self.treeWorkflowName = current_workflow["name"]
        self._update_step_tree_height()
        self._update_workflow_action_state()

    def _append_log(self, message: str):
        log_interface = self._get_log_interface()
        if log_interface is not None:
            log_interface.logMessage.emit(f"{message}\n")

    def _get_main_window(self):
        window = self.window()
        if hasattr(window, 'logInterface') and hasattr(window, 'switchTo'):
            return window
        return None

    def _get_log_interface(self):
        main_window = self._get_main_window()
        if main_window is None:
            return None
        return getattr(main_window, 'logInterface', None)

    def _selected_path(self):
        if not self.workflows:
            return None
        current_workflow_name = self._current_workflow()["name"]
        if self.treeWorkflowName != current_workflow_name:
            return None
        item = self.stepTree.currentItem()
        if not item:
            return None
        path_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(path_data, (list, tuple)):
            return None
        path = tuple(path_data)
        if self.pathItemMap.get(path) is not item:
            return None
        if not self._is_valid_step_path(path):
            return None
        return path

    def _is_valid_step_path(self, path) -> bool:
        if not isinstance(path, (list, tuple)) or not path:
            return False

        steps = self._current_workflow().get("steps", [])
        for depth, index in enumerate(path):
            if not isinstance(index, int) or index < 0 or index >= len(steps):
                return False
            if depth == len(path) - 1:
                return True
            steps = steps[index].get("children", [])

        return False

    def _selected_step_is_control(self) -> bool:
        selected_path = self._selected_path()
        if selected_path is None:
            return False
        return self._step_for_path(selected_path).get("type") in self.CONTROL_STEP_TYPES

    def _can_move_selected_step(self, direction: int) -> bool:
        selected_path = self._selected_path()
        if selected_path is None:
            return False
        step_list, index = self._step_list_for_path(selected_path)
        new_index = index + direction
        return 0 <= new_index < len(step_list)

    def _step_list_for_path(self, path):
        steps = self._current_workflow()["steps"]
        if len(path) == 1:
            return steps, path[0]
        for index in path[:-1]:
            steps = steps[index]["children"]
        return steps, path[-1]

    def _step_for_path(self, path):
        steps, index = self._step_list_for_path(path)
        return steps[index]

    def _on_workflow_changed(self, index):
        if index < 0 or index >= len(self.workflows):
            return
        workflow_name = self.workflows[index]["name"]
        set_current_workflow_name(workflow_name)
        self._refresh_tree()

    def _create_workflow(self):
        existing_names = {workflow["name"] for workflow in self.workflows}
        default_name = duplicate_workflow_name(tr("新建流程"), existing_names)
        dialog = InputDialog(tr("新建流程"), tr("请输入流程名称"), default_name, self)
        if not dialog.exec():
            return
        name = dialog.inputEdit.text().strip()
        name = duplicate_workflow_name(name, existing_names)
        self.workflows.append({"name": name, "steps": []})
        self._save_workflows()
        self._refresh_workflow_combo(name)
        self._refresh_tree()

    def _rename_workflow(self):
        current_workflow = self._current_workflow()
        if self._current_workflow_is_read_only():
            return
        current_name = current_workflow["name"]
        dialog = InputDialog(tr("重命名流程"), tr("请输入新的流程名称"), current_name, self)
        if not dialog.exec():
            return
        name = dialog.inputEdit.text().strip()

        existing_names = {workflow["name"] for workflow in self.workflows if workflow is not current_workflow}
        name = duplicate_workflow_name(name, existing_names)
        current_workflow["name"] = name
        self._save_workflows()
        self._refresh_workflow_combo(name)

    def _delete_workflow(self):
        if self._current_workflow_is_read_only():
            return
        if len(self.workflows) <= 1:
            InfoBar.warning(
                title=tr("无法删除"),
                content=tr("至少需要保留一个流程"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
            return

        current_workflow = self._current_workflow()
        box = MessageBox(tr("删除流程"), tr("确认删除当前流程吗？此操作会同时删除已保存的模板图片。"), self)
        box.yesButton.setText(tr("删除"))
        box.cancelButton.setText(tr("取消"))
        if not box.exec():
            return

        self.workflows.remove(current_workflow)
        self._save_workflows()
        selected_name = self.workflows[0]["name"]
        self._refresh_workflow_combo(selected_name)
        self._refresh_tree()

    def _edit_workflow_info(self):
        if self._current_workflow_is_read_only():
            return
        workflow = self._current_workflow()
        dialog = WorkflowInfoDialog(workflow, self)
        if not dialog.exec():
            return
        author = dialog.authorEdit.text().strip()
        version = dialog.versionEdit.text().strip()
        description = dialog.descEdit.toPlainText().strip()
        for key in WORKFLOW_USER_INFO_KEYS:
            workflow.pop(key, None)
        if author:
            workflow["author"] = author
        if version:
            workflow["version"] = version
        if description:
            workflow["description"] = description
        self._save_workflows()

    def _export_workflow(self):
        workflow = self._current_workflow()
        safe_name = workflow["name"].replace("/", "_").replace("\\", "_")
        default_path = os.path.join(os.path.expanduser("~"), f"{safe_name}.zip")
        file_path, _ = QFileDialog.getSaveFileName(
            self, tr("导出流程"), default_path, tr("ZIP 文件 (*.zip)")
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".zip"):
            file_path += ".zip"
        try:
            export_workflow_to_zip(workflow, file_path)
            InfoBar.success(
                title=tr("导出成功"),
                content=file_path,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=4000,
                parent=self,
            )
        except Exception as e:
            box = MessageBox(tr("导出失败"), str(e), self)
            box.cancelButton.hide()
            box.exec()

    def _import_workflow(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("导入流程"), "", tr("ZIP 文件 (*.zip)")
        )
        if not file_path:
            return
        try:
            workflow = import_workflow_from_zip(file_path)
        except Exception as e:
            box = MessageBox(tr("导入失败"), str(e), self)
            box.cancelButton.hide()
            box.exec()
            return
        existing_names = {w["name"] for w in self.workflows}
        workflow["name"] = duplicate_workflow_name(workflow["name"], existing_names)
        self.workflows.append(workflow)
        self._save_workflows()
        self._refresh_workflow_combo(workflow["name"])
        self._refresh_tree()
        description = workflow.get("description", "")
        if description:
            author = workflow.get("author", "")
            lines = []
            if author:
                lines.append(f"{tr('作者')}：{author}")
            lines.append(description)
            box = MessageBox(tr("流程说明"), "\n\n".join(lines), self)
            box.cancelButton.hide()
            box.exec()

    def _insert_step(self, step_data, as_child=False):
        if self._current_workflow_is_read_only():
            return
        selected_path = self._selected_path()
        workflow = self._current_workflow()

        if as_child:
            if not self._can_add_child_to_selected_step(show_message=True):
                return
            target_step = self._step_for_path(selected_path)
            target_step.setdefault("children", []).append(step_data)
            new_path = tuple(list(selected_path) + [len(target_step["children"]) - 1])
        else:
            if selected_path is None:
                workflow["steps"].append(step_data)
                new_path = (len(workflow["steps"]) - 1,)
            else:
                step_list, index = self._step_list_for_path(selected_path)
                step_list.insert(index + 1, step_data)
                new_path = tuple(list(selected_path[:-1]) + [index + 1])

        self._save_workflows()
        self._refresh_tree(new_path)

    def _add_step(self):
        if self._current_workflow_is_read_only():
            return
        dialog = StepEditDialog(workflow=self._current_workflow(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._insert_step(dialog.get_step_data(), as_child=False)

    def _add_child_step(self):
        if self._current_workflow_is_read_only():
            return
        if not self._can_add_child_to_selected_step(show_message=True):
            return
        dialog = StepEditDialog(workflow=self._current_workflow(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._insert_step(dialog.get_step_data(), as_child=True)

    def _show_step_context_menu(self, pos):
        item = self.stepTree.itemAt(pos)
        if item is not None:
            self.stepTree.setCurrentItem(item)
        else:
            self.stepTree.clearSelection()
            selection_model = self.stepTree.selectionModel()
            if selection_model is not None:
                selection_model.clearCurrentIndex()

        editable = not self._current_workflow_is_read_only()
        has_selected_step = self._selected_path() is not None

        menu = RoundMenu(parent=self.stepTree)

        run_selected_action = QAction(tr("执行选中步骤"), self, triggered=self._run_selected_step)
        run_selected_action.setEnabled(has_selected_step)
        menu.addAction(run_selected_action)

        run_workflow_action = QAction(tr("运行流程"), self, triggered=self._run_current_workflow)
        run_workflow_action.setEnabled(True)
        menu.addAction(run_workflow_action)

        menu.addSeparator()

        add_step_action = QAction(tr("添加步骤"), self, triggered=self._add_step)
        add_step_action.setEnabled(editable)
        menu.addAction(add_step_action)

        add_child_action = QAction(tr("添加子步骤"), self, triggered=self._add_child_step)
        add_child_action.setEnabled(editable and self._selected_step_is_control())
        menu.addAction(add_child_action)

        edit_action = QAction(tr("编辑步骤"), self, triggered=self._edit_selected_step)
        edit_action.setEnabled(editable and has_selected_step)
        menu.addAction(edit_action)

        delete_action = QAction(tr("删除步骤"), self, triggered=self._delete_selected_step)
        delete_action.setEnabled(editable and has_selected_step)
        menu.addAction(delete_action)

        menu.addSeparator()

        move_up_action = QAction(tr("上移"), self, triggered=lambda: self._move_selected_step(-1))
        move_up_action.setEnabled(editable and self._can_move_selected_step(-1))
        menu.addAction(move_up_action)

        move_down_action = QAction(tr("下移"), self, triggered=lambda: self._move_selected_step(1))
        move_down_action.setEnabled(editable and self._can_move_selected_step(1))
        menu.addAction(move_down_action)

        menu.exec(self.stepTree.viewport().mapToGlobal(pos), ani=True)

    def _edit_selected_step(self):
        if self._current_workflow_is_read_only():
            return
        selected_path = self._selected_path()
        if selected_path is None:
            return
        step_list, index = self._step_list_for_path(selected_path)
        dialog = StepEditDialog(step_list[index], self._current_workflow(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            step_list[index] = dialog.get_step_data()
            self._save_workflows()
            self._refresh_tree(selected_path)

    def _delete_selected_step(self):
        if self._current_workflow_is_read_only():
            return
        selected_path = self._selected_path()
        if selected_path is None:
            return
        box = MessageBox(tr("删除步骤"), tr("确认删除当前步骤吗？"), self)
        box.yesButton.setText(tr("删除"))
        box.cancelButton.setText(tr("取消"))
        if not box.exec():
            return
        step_list, index = self._step_list_for_path(selected_path)
        del step_list[index]
        self._save_workflows()
        fallback_index = max(0, index - 1)
        fallback_path = tuple(list(selected_path[:-1]) + [fallback_index]) if step_list else None
        self._refresh_tree(fallback_path)

    def _move_selected_step(self, direction: int):
        if self._current_workflow_is_read_only():
            return
        selected_path = self._selected_path()
        if selected_path is None:
            return
        step_list, index = self._step_list_for_path(selected_path)
        new_index = index + direction
        if new_index < 0 or new_index >= len(step_list):
            return
        step_list[index], step_list[new_index] = step_list[new_index], step_list[index]
        self._save_workflows()
        new_path = tuple(list(selected_path[:-1]) + [new_index])
        self._refresh_tree(new_path)

    def _workflow_task_display_name(self, selected_path=None) -> str:
        workflow_name = self._current_workflow()["name"]
        if not selected_path:
            return workflow_name
        title, _ = summarize_step(self._step_for_path(selected_path))
        return f"{workflow_name} - {title}"

    def _build_workflow_task(self, selected_path=None) -> dict:
        args = ["--workflow-name", self._current_workflow()["name"]]
        if selected_path:
            path_text = "/".join(str(index) for index in selected_path)
            args.extend(["--workflow-step-path", path_text])

        if getattr(sys, 'frozen', False):
            program = os.path.abspath("./March7th Assistant.exe")
            task_args = shlex.join(args)
        else:
            program = sys.executable
            main_script = os.path.abspath("main.py")
            task_args = shlex.join([main_script, *args])

        return {
            "name": f"{tr('流程编排')} - {self._workflow_task_display_name(selected_path)}",
            "program": program,
            "args": task_args,
            "timeout": 0,
        }

    def _start_workflow_execution(self, selected_path=None):
        main_window = self._get_main_window()
        log_interface = self._get_log_interface()
        game = get_game_controller()
        if log_interface is not None and log_interface.isTaskRunning():
            InfoBar.warning(
                title=tr('任务正在运行'),
                content=tr("请先停止当前任务后再启动新任务"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
            if main_window is not None:
                main_window.switchTo(log_interface)
            return

        if not game.is_game_running():
            InfoBar.warning(
                title=tr("启动游戏"),
                content=tr("无法获取游戏窗口截图，请确认游戏窗口已打开"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
            return

        if not game.switch_to_game():
            InfoBar.warning(
                title=tr("启动游戏"),
                content=tr("无法获取游戏窗口截图，请确认游戏窗口已打开"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
            return

        if log_interface is None:
            return

        if main_window is not None:
            main_window.switchTo(log_interface)
        log_interface.startTask(self._build_workflow_task(selected_path))

    def _run_current_workflow(self):
        self._start_workflow_execution()

    def _run_selected_step(self):
        selected_path = self._selected_path()
        if selected_path is None:
            return
        self._start_workflow_execution(selected_path)

    def _stop_current_workflow(self):
        log_interface = self._get_log_interface()
        if log_interface is not None:
            log_interface.stopTask()

    def _start_capture(self, kind: str):
        if self._current_workflow_is_read_only():
            return
        game = get_game_controller()
        if not game.is_game_running() or not game.switch_to_game():
            InfoBar.warning(
                title=tr("启动游戏"),
                content=tr("无法获取游戏窗口截图，请确认游戏窗口已打开"),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
            return
        tool.start_workflow_capture(kind, self._current_workflow()["name"])
        message = tr("截图窗口已打开，请框选后保存为流程素材")
        self._append_log(message)
        InfoBar.success(
            title=tr("已打开截图工具"),
            content=message,
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2500,
            parent=self,
        )

    def _open_directory(self, path: str):
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
