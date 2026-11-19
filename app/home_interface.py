# coding:utf-8
import copy

from PySide6.QtCore import QEvent, QEasingCurve, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QImage, QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsDropShadowEffect, QFileDialog, QDialog

from qfluentwidgets import ScrollArea, FluentIcon, RoundMenu, PushButton, isDarkTheme

from .common.style_sheet import StyleSheet
from .common.evernight_artwork import evernight_artwork
from .common.theme_assets import portrait_artwork
from .components.image_crossfade import ImageCrossFade
from .card.samplecardview1 import SampleCardView1
from .card.card_edit_dialog import DEFAULT_CARDS, HOME_EXTRA_TASKS, CardEditDialog, display_label, migrate_home_cards
from .tools.adb_service import display_connection
from utils.tasks import supported_tasks
from tasks.base.tasks import start_task

from module.config import cfg
from module.localization import get_current_language, tr

from PIL import Image
import numpy as np
import os
import sys


class FloatingLogoHint(QLabel):
    """Float above the banner without changing the page layout."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet('color: #ff91c1; font-family: "Sans Serif Collection", "Microsoft YaHei UI", '
                           '"PingFang SC", "Noto Sans CJK SC", sans-serif; font-size: 18px; font-weight: 600;')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._progress = 0.0
        self._text_path = QPainterPath()
        self._outline_path = QPainterPath()
        self._shadow_path = QPainterPath()
        self._motion = QEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(5000)
        self.animation.valueChanged.connect(self._advance)
        self.animation.finished.connect(self.hide)
        parent.installEventFilter(self)
        self.retranslateUi()
        self.hide()

    def retranslateUi(self):
        text = tr('别晃啦！本姑娘头好晕( ꩜ ᯅ ꩜;)')
        if text != self.text():
            self.setText(text)
            if self.animation.state() != self.animation.State.Stopped:
                self._prepareText()
                self.update()  # preserve both progress and the second click deadline

    def _prepareText(self):
        self.ensurePolished()
        path = QPainterPath()
        path.addText(0, 0, self.font(), self.text())
        bounds = path.boundingRect()
        self._text_path = path.translated(-bounds.left(), -bounds.top())
        # Cache the rounded edge and low-offset shadow once, not on animation frames.
        stroke = QPainterPathStroker()
        stroke.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        stroke.setWidth(2.3)
        self._outline_path = stroke.createStroke(self._text_path)
        stroke.setWidth(4.0)
        self._shadow_path = stroke.createStroke(self._text_path).united(self._text_path).translated(0, 2.0)

    def play(self):
        self.animation.stop()
        self.retranslateUi()
        self._prepareText()
        self.setGeometry(self.parentWidget().rect())
        self._advance(0.0)
        self.show()
        self.raise_()
        self.animation.start()

    def dismiss(self):
        self.animation.stop()
        self.hide()

    def _advance(self, progress):
        self._progress = float(progress)
        self.update()

    def textRect(self):
        bounds = self._text_path.boundingRect()
        travel = self._motion.valueForProgress(self._progress)
        start_y = self.height() * 0.82
        # The banner is scaled to its width and cropped vertically; eye level
        # therefore follows the width, rather than the visible cropped height.
        eye_y = min(self.width() * 0.10, self.height() * 0.5)
        center_y = start_y + (eye_y - start_y) * travel
        return QRectF((self.width() - bounds.width()) / 2,
                      max(0.0, center_y - bounds.height() / 2), bounds.width(), bounds.height())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(1.0 - self._progress)
        painter.translate(self.textRect().topLeft())
        painter.fillPath(self._shadow_path, QColor(30, 10, 25, 115))
        painter.fillPath(self._outline_path, QColor('#622640'))
        painter.fillPath(self._text_path, QColor('#ff91c1'))

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(watched.rect())
        return super().eventFilter(watched, event)


class BannerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._evernight_active = False
        self.menu = RoundMenu(parent=self)
        self.menu.addAction(QAction(tr("更换背景图片"), self, triggered=lambda: on_change_banner_image()))

        self.default_banner_path = "./assets/app/images/bg37.jpg"
        banner_path = cfg.get_value("banner_path", self.default_banner_path)
        if not os.path.exists(banner_path):
            banner_path = self.default_banner_path
        if os.path.abspath(banner_path) != os.path.abspath(self.default_banner_path):
            self.menu.addAction(QAction(tr("恢复默认图片"), self, triggered=lambda: on_restore_default_banner_image()))
        with Image.open(banner_path) as image:
            self._regular_banner_image = image.convert('RGB')
        self.banner_image = self._regular_banner_image
        min_height = min(self.parent().parent().height() - 271 - 49, (self.parent().parent().width() - 73) * self.banner_image.height // self.banner_image.width)
        self.setFixedHeight(min_height)

        self.vBoxLayout = QVBoxLayout(self)
        self.galleryLabel = QLabel(self)
        self.retranslateTitle()
        self.galleryLabel.setStyleSheet("color: white;font-size: 30px; font-weight: 600;")

        # 创建阴影效果
        # 修复 PySide6 阴影不生效的问题参考了 “[PySide6 练习笔记] 添加阴影及动画效果”
        # https://medium.com/@benson890720/pyside6%E7%B7%B4%E7%BF%92%E7%AD%86%E8%A8%98-%E6%B7%BB%E5%8A%A0%E9%99%B0%E5%BD%B1%E5%8F%8A%E5%8B%95%E7%95%AB%E6%95%88%E6%9E%9C-83f1d2f888d
        self.galleryLabel.shadow = QGraphicsDropShadowEffect()
        self.galleryLabel.shadow.setBlurRadius(20)  # 阴影模糊半径
        self.galleryLabel.shadow.setColor(Qt.GlobalColor.black)  # 阴影颜色
        self.galleryLabel.shadow.setOffset(1.2, 1.2)     # 阴影偏移量

        # 将阴影效果应用于小部件
        self.galleryLabel.setGraphicsEffect(self.galleryLabel.shadow)
        # 设置手型光标以提示用户该标签可点击
        self.galleryLabel.setCursor(Qt.CursorShape.PointingHandCursor)

        self.banner = None
        self.path = None
        self.parent_height = 0
        self.parent_width = 0

        # 点击标签可以选择新的背景图片
        def _on_gallery_label_clicked(event):
            self.menu.exec(event.globalPos(), ani=True)

        def on_change_banner_image():
            file_path, _ = QFileDialog.getOpenFileName(self, tr("选择图片"), os.getcwd(), "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)")
            if file_path:
                if os.path.abspath(file_path) != os.path.abspath(self.default_banner_path):
                    # 如果没有恢复默认按钮，添加一个
                    has_restore_action = any(action.text() == tr("恢复默认图片") for action in self.menu.actions())
                    if not has_restore_action:
                        self.menu.addAction(QAction(tr("恢复默认图片"), self, triggered=lambda: on_restore_default_banner_image()))
                try:
                    with Image.open(file_path) as image:
                        self._regular_banner_image = image.convert('RGB')
                    if not self._evernight_active:
                        self.banner_image = self._regular_banner_image
                    cfg.set_value("banner_path", file_path)
                except Exception:
                    return
                self.banner = None
                self.path = None
                self.update()

        def on_restore_default_banner_image():
            try:
                with Image.open(self.default_banner_path) as image:
                    self._regular_banner_image = image.convert('RGB')
                if not self._evernight_active:
                    self.banner_image = self._regular_banner_image
                cfg.set_value("banner_path", self.default_banner_path)
            except Exception:
                return
            self.banner = None
            self.path = None
            # 移除恢复默认按钮
            for action in self.menu.actions():
                if action.text() == tr("恢复默认图片"):
                    self.menu.removeAction(action)
                    break
            self.update()

        self._on_gallery_label_clicked = _on_gallery_label_clicked
        self.galleryLabel.mousePressEvent = self._on_gallery_label_clicked

        self.galleryLabel.setObjectName('galleryLabel')

        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 20, 0, 10)
        self.vBoxLayout.addWidget(self.galleryLabel)
        self.vBoxLayout.addStretch(1)  # 添加弹性空间，将下方任务卡片推到底部
        self.logoHint = FloatingLogoHint(self)
        self.imageTransition = ImageCrossFade(self)

    def retranslateTitle(self):
        title = tr('长夜月小助手') if self._evernight_active else tr('三月七小助手')
        if get_current_language() in ('zh_CN', 'zh_TW'):
            title += '\nEvernightAssistant' if self._evernight_active else '\nMarch7thAssistant'
        self.galleryLabel.setText(title)

    def setEvernightMode(self, active, animate=False):
        if animate:
            self.imageTransition.play(self.banner, self.path)
        else:
            self.imageTransition.finish()
        self._evernight_active = active
        self.banner_image = evernight_artwork().banner if active else self._regular_banner_image
        self.retranslateTitle()
        self.banner = None
        self.path = None
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | QPainter.RenderHint.Antialiasing)

        if not self.banner or not self.path or self.parent_height != self.parent().parent().height() or self.parent_width != self.parent().parent().width():
            self.parent_height = self.parent().parent().height()
            self.parent_width = self.parent().parent().width()
            min_height = min(self.parent().parent().height() - 271, self.width() * self.banner_image.height // self.banner_image.width)
            self.setFixedHeight(min_height)
            image_height = self.banner_image.width * self.height() // self.width()
            crop_area = (0, 0, self.banner_image.width, image_height)  # (left, upper, right, lower)
            cropped_img = self.banner_image.crop(crop_area).convert("RGB")
            img_data = np.array(cropped_img)  # Convert PIL Image to numpy array
            height, width, channels = img_data.shape
            bytes_per_line = channels * width
            # The cached QImage must own its pixels after the temporary numpy array is released.
            self.banner = QImage(img_data.data, width, height, bytes_per_line, QImage.Format.Format_RGB888).copy()

            path = QPainterPath()
            path.addRoundedRect(0, 0, width + 50, height + 50, 10, 10)  # 10 is the radius for corners
            self.path = path.simplified()

        painter.setClipPath(self.path)
        painter.drawImage(self.rect(), self.banner)


class HomeInterface(ScrollArea):
    """ Home interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._evernight_active = False
        self._task_cards = []
        self._task_icon_transitions = {}
        self.banner = BannerWidget(self)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)

        self.__initWidget()
        self.loadSamples()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('homeInterface')
        StyleSheet.HOME_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(25)
        self.vBoxLayout.addWidget(self.banner)
        self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def loadSamples(self):
        self.basicInputView = SampleCardView1(
            tr("任务 >"), self.view)

        # 添加编辑按钮到标题栏
        self.editButton = PushButton(FluentIcon.EDIT, tr("编辑"))
        self.editButton.setFixedHeight(30)
        self.editButton.clicked.connect(self._on_edit_cards)
        self.basicInputView.headerLayout.addWidget(self.editButton)

        self.refreshBackendTasks()
        self.vBoxLayout.addWidget(self.basicInputView)

    def retranslateUi(self):
        StyleSheet.HOME_INTERFACE.apply(self)
        self.banner.retranslateTitle()
        self.banner.logoHint.retranslateUi()
        actions = self.banner.menu.actions()
        actions[0].setText(tr('更换背景图片'))
        if len(actions) > 1:
            actions[1].setText(tr('恢复默认图片'))
        self.basicInputView.titleLabel.setText(tr('任务 >'))
        self.editButton.setText(tr('编辑'))
        self.refreshBackendTasks()

    def setEvernightMode(self, active, animate=False):
        animate = animate and active and active != self._evernight_active
        if active != self._evernight_active:
            self._evernight_active = active
            self.banner.setEvernightMode(active, animate=animate)
        self._refresh_task_icons(animate=animate)

    def _refresh_task_icons(self, animate=False):
        for widget, original_icon, full_run in self._task_cards:
            transition = self._task_icon_transitions.get(widget)
            if transition is not None:
                if animate:
                    # Cache the small rendered portrait once: bundled PNGs contain
                    # transparency, so raw old pixels would reveal the new image early.
                    transition.play(widget.iconWidget.grab().toImage())
                elif not self._evernight_active:
                    transition.finish()
            pixmap = (evernight_artwork().avatar if self._evernight_active and full_run
                      else portrait_artwork(original_icon, isDarkTheme()))
            widget.iconWidget.setPixmap(pixmap)

    def _build_card_action(self, card_data):
        """根据卡片配置数据构建动作"""
        if card_data.get("action_type") == "single":
            task_id = card_data.get("task_id", "main")
            if task_id in HOME_EXTRA_TASKS:
                return self._get_extra_task_action(task_id)
            return lambda tid=task_id: start_task(tid)
        else:
            result = {}
            for item in card_data.get("menu_items", []):
                task_id = item.get("task_id", "")
                # 同上：内置菜单项存中文原文，显示时按当前语言解析
                label = display_label(item.get("label", ""))
                if task_id in HOME_EXTRA_TASKS:
                    result[label] = self._get_extra_task_action(task_id)
                else:
                    result[label] = lambda tid=task_id: start_task(tid)
            return result

    def _load_home_cards(self):
        """读取主页卡片配置；旧版本写进配置的译文一次性还原为中文原文并写回。"""
        cards_data = cfg.get_value("home_cards")
        if cards_data is None:
            return copy.deepcopy(DEFAULT_CARDS)
        if migrate_home_cards(cards_data):
            cfg.set_value("home_cards", cards_data)
        return cards_data

    @staticmethod
    def _get_extra_task_action(task_id):
        """获取特殊主页操作的 lambda"""
        if task_id == "_reset_universe_config":
            return lambda: [os.remove(p) for p in map(lambda f: os.path.join(cfg.universe_path, f), ["info.yml", "info_old.yml"]) if os.path.exists(p)]
        elif task_id == "_open_universe_dir":
            return lambda: os.startfile(cfg.universe_path)
        elif task_id == "_open_universe_homepage":
            return lambda: os.startfile("https://github.com/CHNZYX/Auto_Simulated_Universe")
        elif task_id == "_reset_fight_config":
            return lambda: os.path.exists(os.path.join(cfg.fight_path, "config.json")) and os.remove(os.path.join(cfg.fight_path, "config.json"))
        elif task_id == "_open_fight_dir":
            return lambda: os.startfile(cfg.fight_path)
        elif task_id == "_open_fight_homepage":
            return lambda: os.startfile("https://github.com/linruowuyin/Fhoe-Rail")
        return lambda: None

    def _on_edit_cards(self):
        """打开卡片编辑对话框"""
        cards_data = self._load_home_cards()

        dialog = CardEditDialog(cards_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_cards is not None:
            # 检查是否与默认配置相同，如果相同则不保存（清除自定义配置）
            if dialog.result_cards == DEFAULT_CARDS:
                cfg.set_value("home_cards", None)
            else:
                cfg.set_value("home_cards", dialog.result_cards)
            self.refreshBackendTasks()

    def refreshBackendTasks(self):
        """重建卡片视图"""
        self._task_cards.clear()
        self._task_icon_transitions.clear()
        self.basicInputView.clearCards()

        tasks = supported_tasks(display_connection(cfg))
        if "fight" in tasks:
            tasks.update(HOME_EXTRA_TASKS)

        for card in self._load_home_cards():
            if card.get("action_type") == "single":
                if card.get("task_id", "main") not in tasks:
                    continue
            else:
                items = [item for item in card.get("menu_items", []) if item.get("task_id") in tasks]
                if not items:
                    continue
                card = {**card, "menu_items": items}
            action = self._build_card_action(card)
            widget = self.basicInputView.addSampleCard(
                icon=card.get("icon", ""),
                # 内置卡片存的是中文原文，这里按当前语言显示；用户自定义标题原样显示
                title=display_label(card.get("title", "")),
                action=action
            )
            full_run = card.get('action_type') == 'single' and card.get('task_id', 'main') == 'main'
            if full_run:
                self._task_icon_transitions[widget] = ImageCrossFade(widget.iconWidget)
            self._task_cards.append((widget, card.get('icon', ''), full_run))
        self._refresh_task_icons()
