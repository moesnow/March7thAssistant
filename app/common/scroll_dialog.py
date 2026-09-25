# coding:utf-8
"""对话框滚动内容与开关动画的公共实现。

两个被反复踩坑的事实（修复依据，勿删）：

1. 遮罩对话框（qfluentwidgets MaskDialogBase）的窗口尺寸跟随父窗口而非屏幕，
   内容高度预算必须按父窗口计算，否则底部按钮会被裁出可视区域；
   QScrollArea 的 sizeHint 远小于实际内容，弹窗按最小尺寸收缩，
   必须显式以内容尺寸为下限撑开，超高的部分才内部滚动。
2. 基类把 QGraphicsOpacityEffect 整窗挂在对话框上，该效果无法正确栅格化
   QScrollArea 视口内容，表现为「外框淡入淡出、滚动内容在动画结束时突兀闪现」。
   需要拆分到各内容部件上分别挂效果并同步驱动（SplitFadeDialogMixin）。
"""
from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsOpacityEffect, QScrollArea


def build_scroll_area(container, host_width, host_height, chrome_height, min_height=120):
    """把内容容器包装为限高滚动区（内容少时紧凑、超高时内部滚动）。

    :param container: 内容容器 QWidget（由调用方组装好子部件）。
    :param host_width: 可用宽度（父窗口宽度），用于限制最小宽度。
    :param host_height: 可用高度（父窗口高度），内容必须装进这个高度。
    :param chrome_height: 除滚动区之外的弹窗高度（标题/固定卡片/按钮区/边距）。
    :param min_height: 滚动区高度下限，防止极端小窗口塌缩成一条。
    """
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(container)

    # 弹窗按最小尺寸收缩，而 QScrollArea 的 sizeHint 远小于实际内容，
    # 因此显式以内容尺寸为下限撑开弹窗；超出上限的部分内部滚动。
    max_height = max(min_height, host_height - chrome_height)
    content_min = container.minimumSizeHint()
    scroll.setMinimumHeight(min(content_min.height(), max_height))
    scroll.setMaximumHeight(max_height)
    # 宽度为内容下限 + 滚动条占位，避免纵向滚动条出现后内容被横向裁切
    scroll.setMinimumWidth(min(content_min.width() + 20, host_width - 120))

    # 背景一律透出面板底色，保证与外框同色（浅/深主题通用）：
    # 内容容器默认会以调色板色自填底，与面板割裂；
    # 视口的样式规则用 objectName 限定选择器，避免级联影响子部件配色。
    container.setAutoFillBackground(False)
    scroll.viewport().setObjectName("dialogScrollViewport")
    scroll.viewport().setStyleSheet("#dialogScrollViewport { background: transparent; }")
    scroll.setStyleSheet("QScrollArea{background: transparent; border: none;}")
    return scroll


def available_host_size(parent):
    """遮罩对话框的可用区域 = 父窗口尺寸（遮罩跟随父窗口），无父窗口时退化为屏幕。"""
    if parent is not None:
        return parent.width(), parent.height()
    screen = QApplication.primaryScreen().availableGeometry()
    return screen.width(), screen.height()


class SplitFadeDialogMixin:
    """开关动画拆分混入：供含滚动区的 MaskDialogBase 系对话框使用。

    用法：``class Foo(SplitFadeDialogMixin, MessageBox)``，
    并在组装布局后设置 ``self._scroll``（QScrollArea，可选，无滚动区时留 None）。
    会覆盖基类 showEvent/done 的整窗透明度动画。
    """

    FADE_IN_MS = 200
    FADE_OUT_MS = 100

    def _fade_targets(self):
        targets = [self.windowMask, self.widget]
        scroll = getattr(self, '_scroll', None)
        if scroll is not None and scroll.widget() is not None:
            targets.append(scroll.widget())
        return targets

    def _clear_fade_effects(self):
        """移除透明度效果并恢复内容框的投影效果。"""
        for target in self._fade_targets():
            target.setGraphicsEffect(None)
        # setGraphicsEffect(None) 后原投影效果已被替换，重新挂回基类默认投影
        self.setShadowEffect()

    def _stop_fade(self):
        group = getattr(self, '_fade_group', None)
        if group is not None:
            # stop() 不会触发 finished，需手动清理后重挂新效果
            group.stop()
            group.deleteLater()
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
        # 跳过基类的整窗淡入，改用分体淡入
        from PySide6.QtWidgets import QDialog
        QDialog.showEvent(self, e)
        self._start_fade(0.0, 1.0, self.FADE_IN_MS, self._finish_fade_in)

    def _finish_fade_in(self):
        self._fade_group = None
        self._clear_fade_effects()

    def done(self, code):
        # 跳过基类的整窗淡出，改用分体淡出；动画结束后真正关闭
        if getattr(self, '_fading_out', False):
            return  # 淡出进行中，忽略重复的关闭请求（淡入中可直接转入淡出）
        self._result_code = code
        self._fading_out = True
        self._start_fade(1.0, 0.0, self.FADE_OUT_MS, self._finish_fade_out)

    def _finish_fade_out(self):
        self._fade_group = None
        self._fading_out = False
        self._clear_fade_effects()
        from PySide6.QtWidgets import QDialog
        QDialog.done(self, self._result_code)
