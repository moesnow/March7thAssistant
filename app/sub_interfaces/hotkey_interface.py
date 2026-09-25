from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QGraphicsOpacityEffect,
                               QLabel, QScrollArea, QVBoxLayout, QWidget)
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import MessageBox

from app.card.pushsettingcard1 import PushSettingCardKey
from module.config import cfg
from module.localization import tr


class HotkeyInterface(MessageBox):
    """ Hotkey configuration interface """

    # 开关动画时长（毫秒），与 qfluentwidgets MaskDialogBase 的默认动画保持一致
    FADE_IN_MS = 200
    FADE_OUT_MS = 100

    def __init__(self, parent=None):
        configlist = {
            tr("秘技（只对清体力和逐光捡金场景生效）"): "hotkey_technique",
            tr("地图"): "hotkey_map",
            tr("跃迁"): "hotkey_warp",
            tr("自动战斗"): "hotkey_auto_battle",
            tr("停止任务（全局热键，支持后台）"): "hotkey_stop_task",
            tr("暂停/继续任务（全局热键，支持后台）"): "hotkey_pause_task",
            tr("自动对话（全局热键，支持后台）"): "hotkey_toggle_autoplot"
        }

        super().__init__(tr("按键设置"), "", parent)
        self.configlist = configlist
        self._scroll = None
        self._fade_group = None
        self._fading_out = False
        self._result_code = 0

        self.backup_config = {}
        for config in self.configlist.values():
            self.backup_config[config] = cfg.get_value(config)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText(tr('确认'))
        self.cancelButton.setText(tr('取消'))

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(10)
        self.textLayout.setSpacing(4)

        # 按键列表放进可滚动容器：弹窗高度以屏幕可用高度为上限，
        # 避免条目增多后超出屏幕、底部确认/取消按钮不可见
        list_container = QWidget(self)
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(4)

        self.pushButton_dict = {}
        for name, config in self.configlist.items():
            if config == "hotkey_technique":
                icon = FIF.LEAF
            elif config == "hotkey_map":
                icon = FIF.LEAF
            elif config == "hotkey_warp":
                icon = FIF.LEAF
            elif config == "hotkey_auto_battle":
                icon = FIF.GAME
            elif config == "hotkey_pause_task":
                icon = FIF.PAUSE
            elif config == "hotkey_toggle_autoplot":
                icon = FIF.DEVELOPER_TOOLS
            else:
                icon = FIF.SETTING

            pushButton = PushSettingCardKey(
                tr('按住以修改'),
                icon,
                name,
                config,
            )
            pushButton.setFont(font)

            list_layout.addWidget(pushButton, 0, Qt.AlignmentFlag.AlignTop)
            self.pushButton_dict[config] = pushButton

        # 添加提示标签：交互 F / 角色详细 C 不允许修改
        hint_label = QLabel(tr("注意：交互（F）和角色详细（C）按键不允许修改，请保持游戏内默认设置。"))
        hint_font = QFont()
        hint_font.setPointSize(9)
        hint_label.setFont(hint_font)
        hint_label.setStyleSheet("color: gray;")
        hint_label.setWordWrap(True)
        list_layout.addWidget(hint_label, 0, Qt.AlignmentFlag.AlignTop)
        list_layout.addStretch(1)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(list_container)
        # 弹窗按最小尺寸收缩，而 QScrollArea 的 sizeHint 远小于实际内容，
        # 因此这里显式以内容尺寸为下限撑开弹窗；超出上限的部分内部滚动。
        # 注意：遮罩弹窗的尺寸跟随父窗口（而非屏幕），内容必须装进父窗口，
        # 否则会被父窗口下沿裁掉、底部按钮不可见。
        if parent is not None:
            host_width, host_height = parent.width(), parent.height()
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            host_width, host_height = screen.width(), screen.height()
        # 非列表部分的高度：文本布局上下边距 + 标题 + 间距 + 按钮区 + 余量
        chrome = (self.textLayout.contentsMargins().top()
                  + self.textLayout.contentsMargins().bottom()
                  + self.titleLabel.sizeHint().height()
                  + self.textLayout.spacing()
                  + self.buttonGroup.height()
                  + 24)
        max_height = max(240, host_height - chrome)
        content_min = list_container.minimumSizeHint()
        scroll.setMinimumHeight(min(content_min.height(), max_height))
        scroll.setMaximumHeight(max_height)
        # 宽度为内容下限 + 滚动条占位，避免纵向滚动条出现后卡片被横向裁切
        scroll.setMinimumWidth(min(content_min.width() + 20, host_width - 120))
        # 滚动区背景一律透出面板底色，保证与外框同色（浅/深主题通用）：
        # 内容容器会以调色板色自填底（#1e1e1e），把半透明卡片染脏、与外框割裂。
        # 视口的样式规则用 objectName 限定选择器，避免级联影响卡片自身配色。
        list_container.setAutoFillBackground(False)
        scroll.viewport().setObjectName("hotkeyScrollViewport")
        scroll.viewport().setStyleSheet("#hotkeyScrollViewport { background: transparent; }")
        scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")
        self.textLayout.addWidget(scroll, 1)
        self._scroll = scroll

        self.yesButton.clicked.connect(self._onConfirmClicked)
        self.cancelButton.clicked.connect(self._onCancelClicked)

    # ---------- 开关动画 ----------
    #
    # 基类 MaskDialogBase 把 QGraphicsOpacityEffect 整窗挂在对话框上，
    # 该效果无法正确栅格化 QScrollArea 视口内容，表现为
    # 「外框淡入淡出、列表内容在动画结束时瞬间出现/消失」。
    # 因此这里改为对遮罩、外壳（标题/按钮区）、滚动区内的列表内容
    # 分别挂透明度效果，并用同一动画组同步驱动，保证整体均匀渐变。

    def _fade_targets(self):
        targets = [self.windowMask, self.widget]
        if self._scroll is not None and self._scroll.widget() is not None:
            targets.append(self._scroll.widget())
        return targets

    def _clear_fade_effects(self):
        """移除透明度效果并恢复内容框的投影效果。"""
        for target in self._fade_targets():
            target.setGraphicsEffect(None)
        # setGraphicsEffect(None) 后原投影效果已被替换，重新挂回基类默认投影
        self.setShadowEffect()

    def _stop_fade(self):
        if self._fade_group is not None:
            # stop() 不会触发 finished，需手动清理后重挂新效果
            self._fade_group.stop()
            self._fade_group.deleteLater()
            self._fade_group = None
        self._clear_fade_effects()

    def _start_fade(self, start, end, duration, on_finished):
        self._stop_fade()
        group = QParallelAnimationGroup(self)
        for target in self._fade_targets():
            effect = QGraphicsOpacityEffect(target)
            effect.setOpacity(start)
            target.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b'opacity')
            anim.setDuration(duration)
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.setEasingCurve(
                QEasingCurve.Type.InSine if end > start else QEasingCurve.Type.OutSine
            )
            group.addAnimation(anim)
        if on_finished is not None:
            group.finished.connect(on_finished)
        self._fade_group = group
        group.start()

    def showEvent(self, e):
        # 跳过基类的整窗淡入，改用分体淡入（见上方说明）
        QDialog.showEvent(self, e)
        self._start_fade(0.0, 1.0, self.FADE_IN_MS, self._finish_fade_in)

    def _finish_fade_in(self):
        self._fade_group = None
        self._clear_fade_effects()

    def done(self, code):
        # 跳过基类的整窗淡出，改用分体淡出；动画结束后真正关闭
        if self._fading_out:
            return  # 淡出进行中，忽略重复的关闭请求（淡入中可直接转入淡出）
        self._result_code = code
        self._fading_out = True
        self._start_fade(1.0, 0.0, self.FADE_OUT_MS, self._finish_fade_out)

    def _finish_fade_out(self):
        self._fade_group = None
        self._fading_out = False
        self._clear_fade_effects()
        QDialog.done(self, self._result_code)

    def _onConfirmClicked(self):
        """ 确认按钮点击处理 - 保存配置 """
        self.accept()

    def _onCancelClicked(self):
        """ 取消按钮点击处理 - 恢复备份配置

        仅恢复真正被改动的项并一次性落盘：`save_config` 带 fsync，
        逐项 `set_value`（每项还会保存两次）会造成取消后弹窗迟迟不关闭。
        """
        restore = {}
        for config, value in self.backup_config.items():
            if cfg.get_value(config) != value:
                restore[config] = value
        if restore:
            cfg.set_values(restore)
        self.reject()
