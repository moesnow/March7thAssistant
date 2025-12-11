from PyQt5.QtCore import Qt, QUrl, QSize
from PyQt5.QtWidgets import QLabel, QHBoxLayout, QSpinBox, QVBoxLayout, QPushButton, QToolButton, QCompleter
from PyQt5.QtGui import QPixmap, QDesktopServices, QFont
from qfluentwidgets import (MessageBox, LineEdit, ComboBox, EditableComboBox, DateTimeEdit,
                            BodyLabel, FluentStyleSheet, TextEdit, Slider, FluentIcon, qconfig,
                            isDarkTheme, PrimaryPushSettingCard, InfoBar, InfoBarPosition, PushButton, SpinBox)
from qfluentwidgets import FluentIcon as FIF
from typing import Optional
from module.config import cfg
import datetime
import json
import time
import base64


def _cleanup_infobars(widget):
    """Safely hide/close/delete any InfoBar children of `widget`.

    This helps avoid QPainter warnings when a parent widget is closing
    while an InfoBar is still animating/painting.
    """
    try:
        for bar in widget.findChildren(InfoBar):
            try:
                bar.hide()
            except Exception:
                pass
            try:
                bar.close()
            except Exception:
                pass
            try:
                bar.deleteLater()
            except Exception:
                pass
    except Exception:
        pass


def setup_completer(combo_box, items):
    """
    为 EditableComboBox 设置自动补全器
    :param combo_box: EditableComboBox 实例
    :param items: 选项列表
    """
    completer = QCompleter(items)
    completer.setCaseSensitivity(Qt.CaseInsensitive)  # 设置大小写不敏感
    completer.setFilterMode(Qt.MatchContains)  # 设置匹配模式为包含（支持部分匹配）
    combo_box.setCompleter(completer)


class SliderWithSpinBox(QHBoxLayout):
    def __init__(self, min_value: int, max_value: int, step: int = 1, parent=None):
        super().__init__()

        font = QFont()
        font.setPointSize(11)

        # 创建滑块
        self.slider = Slider(Qt.Horizontal, parent)
        self.slider.setRange(min_value, max_value)
        self.slider.setSingleStep(step)
        self.slider.setMinimumWidth(268)  # 与 RangeSettingCard1 保持一致

        # 创建数字显示
        self.valueLabel = QLabel(parent)
        self.valueLabel.setFont(font)
        self.valueLabel.setNum(min_value)
        self.valueLabel.setObjectName('valueLabel')

        # 创建加减按钮
        self.minusButton = QToolButton(parent)
        self.plusButton = QToolButton(parent)

        # 设置按钮样式
        self.updateButtonStyle()

        self.minusButton.setFixedSize(28, 28)
        self.plusButton.setFixedSize(28, 28)
        self.minusButton.setIconSize(QSize(12, 12))
        self.plusButton.setIconSize(QSize(12, 12))

        # 布局
        self.addStretch(1)
        self.addWidget(self.valueLabel)
        self.addSpacing(10)
        self.addWidget(self.minusButton)
        self.addSpacing(4)
        self.addWidget(self.slider)
        self.addSpacing(4)
        self.addWidget(self.plusButton)
        self.addSpacing(16)

        # 监听主题变化
        qconfig.themeChanged.connect(self.updateButtonStyle)

        # 连接信号
        self.slider.valueChanged.connect(self.__onValueChanged)
        self.minusButton.clicked.connect(self.decreaseValue)
        self.plusButton.clicked.connect(self.increaseValue)

    def __onValueChanged(self, value: int):
        self.valueLabel.setNum(value)
        self.valueLabel.adjustSize()

    def setValue(self, value: int):
        self.slider.setValue(value)
        self.valueLabel.setNum(value)
        self.valueLabel.adjustSize()

    def value(self) -> int:
        return self.slider.value()

    def decreaseValue(self):
        value = self.slider.value()
        if value > self.slider.minimum():
            self.slider.setValue(value - 1)

    def increaseValue(self):
        value = self.slider.value()
        if value < self.slider.maximum():
            self.slider.setValue(value + 1)

    def updateButtonStyle(self):
        """根据当前主题更新按钮样式"""
        style = '''
            QToolButton {
                background-color: transparent;
                border: 1px solid %s;
                border-radius: 5px;
            }
            QToolButton:hover {
                background-color: %s;
            }
            QToolButton:pressed {
                background-color: %s;
            }
        '''

        if isDarkTheme():
            # 深色主题
            border_color = '#424242'
            hover_color = '#424242'
            pressed_color = '#333333'
        else:
            # 浅色主题
            border_color = '#E5E5E5'
            hover_color = '#E5E5E5'
            pressed_color = '#DDDDDD'

        self.minusButton.setStyleSheet(style % (border_color, hover_color, pressed_color))
        self.plusButton.setStyleSheet(style % (border_color, hover_color, pressed_color))

        # 更新图标
        self.minusButton.setIcon(FluentIcon.REMOVE.icon())
        self.plusButton.setIcon(FluentIcon.ADD.icon())


class MessageBoxImage(MessageBox):
    def __init__(self, title: str, content: str, image: Optional[str | QPixmap], parent=None):
        super().__init__(title, content, parent)
        if image is not None:
            self.imageLabel = QLabel(parent)
            if isinstance(image, QPixmap):
                self.imageLabel.setPixmap(image)
            elif isinstance(image, str):
                self.imageLabel.setPixmap(QPixmap(image))
            else:
                raise ValueError("Unsupported image type.")
            self.imageLabel.setScaledContents(True)

            imageIndex = self.vBoxLayout.indexOf(self.textLayout) + 1
            self.vBoxLayout.insertWidget(imageIndex, self.imageLabel, 0, Qt.AlignCenter)


class MessageBoxSupport(MessageBoxImage):
    def __init__(self, title: str, content: str, image: str, parent=None):
        super().__init__(title, content, image, parent)

        self.yesButton.setText('下次一定')
        self.cancelButton.setHidden(True)


class MessageBoxAnnouncement(MessageBoxImage):
    def __init__(self, title: str, content: str, image: Optional[str | QPixmap], parent=None):
        super().__init__(title, content, image, parent)

        self.yesButton.setText('收到')
        self.cancelButton.setHidden(True)
        self.setContentCopyable(True)


class MessageBoxHtml(MessageBox):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.buttonLayout.removeWidget(self.yesButton)
        self.buttonLayout.removeWidget(self.cancelButton)
        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.contentLabel = BodyLabel(content, parent)
        self.contentLabel.setObjectName("contentLabel")
        self.contentLabel.setOpenExternalLinks(True)
        self.contentLabel.linkActivated.connect(self.open_url)
        self.contentLabel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        FluentStyleSheet.DIALOG.apply(self.contentLabel)

        self.buttonLayout.addWidget(self.cancelButton, 1, Qt.AlignVCenter)
        self.buttonLayout.addWidget(self.yesButton, 1, Qt.AlignVCenter)
        self.textLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))


class MessageBoxHtmlUpdate(MessageBox):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.buttonLayout.removeWidget(self.yesButton)
        self.buttonLayout.removeWidget(self.cancelButton)
        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.contentLabel = BodyLabel(content, parent)
        self.contentLabel.setObjectName("contentLabel")
        self.contentLabel.setOpenExternalLinks(True)
        self.contentLabel.linkActivated.connect(self.open_url)
        self.contentLabel.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.contentLabel.setMinimumWidth(500)
        FluentStyleSheet.DIALOG.apply(self.contentLabel)

        self.buttonLayout.addWidget(self.cancelButton, 1, Qt.AlignVCenter)
        self.buttonLayout.addWidget(self.yesButton, 1, Qt.AlignVCenter)
        self.textLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)

        self.githubUpdateCard = PrimaryPushSettingCard(
            self.tr('立即更新'),
            FIF.GITHUB,
            self.tr('开源渠道'),
            "直接从 GitHub 下载并更新"
        )

        self.mirrorchyanUpdateCard = PrimaryPushSettingCard(
            self.tr('立即更新'),
            FIF.CLOUD,
            self.tr('Mirror酱 服务 ⚡'),
            "Mirror酱 用户可以通过 CDK 高速更新（支持任意版本间增量更新）"
        )
        self.textLayout.addWidget(self.githubUpdateCard, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.mirrorchyanUpdateCard, 0, Qt.AlignTop)

        # self.githubUpdateCard.clicked.connect(self._githubupdate())

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))


class MessageBoxUpdate(MessageBoxHtmlUpdate):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.yesButton.setText('手动下载')
        self.cancelButton.setText('好的')


class MessageBoxDisclaimer(MessageBoxHtml):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.yesButton.setText('退出')
        self.cancelButton.setText('我已知晓')
        self.setContentCopyable(True)
        self._opened_at: float | None = time.time()
        self._min_confirm_seconds = 10

    def exec(self):
        """记录打开时间后再阻塞式显示。"""
        self._opened_at = time.time()
        return super().exec()

    def _confirm_waited_long_enough(self) -> bool:
        return self._opened_at is not None and (time.time() - self._opened_at) >= self._min_confirm_seconds

    def _show_fast_warning(self):
        InfoBar.error(
            title=base64.b64decode("6ZiF6K+75pe26Ze05aSq55+t5LqG77yM5aSa5YGc55WZ5LiA5Lya5ZCnKO+8vuKIgO+8vuKXjyk=").decode("utf-8"),
            content="",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def accept(self):
        # if not self._confirm_waited_long_enough():
        #     self._show_fast_warning()
        #     return
        _cleanup_infobars(self)
        super().accept()

    def reject(self):
        if not self._confirm_waited_long_enough():
            self._show_fast_warning()
            self._opened_at = time.time()
            return
        _cleanup_infobars(self)
        super().reject()


class MessageBoxEdit(MessageBox):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.lineEdit = LineEdit(self)
        self.lineEdit.setText(self.content)
        self.textLayout.addWidget(self.lineEdit, 0, Qt.AlignTop)

        self.buttonGroup.setMinimumWidth(480)

    def getText(self):
        return self.lineEdit.text()


class MessageBoxEditMultiple(MessageBox):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.textEdit = TextEdit(self)
        self.textEdit.setFixedHeight(250)
        self.textEdit.setText(self.content)
        self.textLayout.addWidget(self.textEdit, 0, Qt.AlignTop)

        self.buttonGroup.setMinimumWidth(480)

    def getText(self):
        return self.textEdit.toPlainText()


class MessageBoxDate(MessageBox):
    def __init__(self, title: str, content: datetime, parent=None):
        super().__init__(title, "", parent)

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.datePicker = DateTimeEdit(self)
        self.datePicker.setDateTime(content)

        self.textLayout.addWidget(self.datePicker, 0, Qt.AlignTop)

        self.buttonGroup.setMinimumWidth(480)

    def getDateTime(self):
        return self.datePicker.dateTime().toPyDateTime()


class MessageBoxInstance(MessageBox):
    def __init__(self, title: str, content: dict, configtemplate: str, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(11)

        with open(configtemplate, 'r', encoding='utf-8') as file:
            self.template = json.load(file)

        self.comboBox_dict = {}
        for type, names in self.template.items():
            horizontalLayout = QHBoxLayout()

            titleLabel = QLabel(type, parent)
            # titleLabel.setFont(font)
            # titleLabel.setMinimumWidth(100)
            horizontalLayout.addWidget(titleLabel)

            # comboBox = ComboBox()
            comboBox = EditableComboBox()

            has_default = False
            item_list = []
            for name, info in names.items():
                item_name = f"{name}（{info}）"
                comboBox.addItem(item_name)
                item_list.append(item_name)
                if self.content[type] == name:
                    comboBox.setCurrentText(item_name)
                    has_default = True
            if not has_default:
                comboBox.setText(self.content[type])

            # 设置自动补全
            setup_completer(comboBox, item_list)

            horizontalLayout.addWidget(comboBox)
            self.textLayout.addLayout(horizontalLayout)
            self.comboBox_dict[type] = comboBox

        self.titleLabelInfo = QLabel("说明：清体力是根据选择的副本类型来判断，副本名称也会用于双倍活动", parent)
        self.titleLabelInfo.setFont(font)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)

    def validate_inputs(self):
        """验证所有输入是否匹配可选项"""
        for type, comboBox in self.comboBox_dict.items():
            input_text = comboBox.text()

            # 构建有效选项列表（包含完整的"名称（信息）"格式）
            valid_options = set()
            for name, info in self.template[type].items():
                valid_options.add(f"{name}（{info}）")
                # 也允许只输入名称部分（向后兼容）
                valid_options.add(name)

            # 检查输入是否匹配任一有效选项
            if input_text not in valid_options:
                InfoBar.error(
                    title='输入错误',
                    content=f'"{type}"的输入"{input_text}"不在可选项中，请重新选择',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

        return True

    def accept(self):
        """重写accept方法以添加验证并在关闭前清理 InfoBar，避免 QPainter 冲突"""
        if self.validate_inputs():
            # 在对话框真正关闭前，清理任何还存在的 InfoBar
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        """在拒绝/取消时也清理 InfoBar，避免在销毁期间 InfoBar 仍在绘制。"""
        _cleanup_infobars(self)
        try:
            super().reject()
        except Exception:
            try:
                self.close()
            except Exception:
                pass


class MessageBoxInstanceChallengeCount(MessageBox):
    def __init__(self, title: str, content: dict, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.buttonGroup.setMinimumWidth(300)

        font = QFont()
        font.setPointSize(11)

        self.template = {
            "拟造花萼（金）": 24,
            "拟造花萼（赤）": 24,
            "凝滞虚影": 8,
            "侵蚀隧洞": 6,
            "饰品提取": 6,
            "历战余响": 3
        }
        self.slider_dict = {}
        for type, count in self.template.items():
            horizontalLayout = QHBoxLayout()
            horizontalLayout.setContentsMargins(24, 8, 24, 8)  # 增加边距使布局更加美观

            # 创建标签
            titleLabel = QLabel(type, parent)
            titleLabel.setFont(font)
            horizontalLayout.addWidget(titleLabel)

            # 创建滑块组件
            sliderLayout = SliderWithSpinBox(1, count, 1, self)
            sliderLayout.setValue(self.content[type])
            horizontalLayout.addLayout(sliderLayout)
            self.slider_dict[type] = sliderLayout

            self.textLayout.addLayout(horizontalLayout)


class MessageBoxNotify(MessageBox):
    def __init__(self, title: str, configlist: dict, parent=None):
        super().__init__(title.capitalize(), "", parent)
        self.configlist = configlist

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(10)
        lineEditFont = QFont()
        lineEditFont.setPointSize(9)
        self.textLayout.setSpacing(4)

        self.lineEdit_dict = {}
        for name, config in self.configlist.items():
            titleLabel = QLabel(name.capitalize(), parent)
            titleLabel.setFont(font)
            self.textLayout.addWidget(titleLabel, 0, Qt.AlignTop)

            lineEdit = LineEdit(self)
            lineEdit.setText(str(cfg.get_value(config)))
            lineEdit.setFont(lineEditFont)
            lineEdit.setFixedHeight(22)

            self.textLayout.addWidget(lineEdit, 0, Qt.AlignTop)
            self.lineEdit_dict[config] = lineEdit


class MessageBoxNotifyTemplate(MessageBox):
    def __init__(self, title: str, content: dict, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.buttonGroup.setMinimumWidth(480)

        font = QFont()
        font.setPointSize(9)
        self.textLayout.setSpacing(4)

        self.lineEdit_dict = {}
        for id, template in self.content.items():
            lineEdit = LineEdit(self)
            lineEdit.setText(template.replace("\n", r"\n"))
            lineEdit.setFont(font)

            lineEdit.setFixedHeight(22)
            self.buttonLayout.setContentsMargins(24, 10, 24, 10)
            self.textLayout.setContentsMargins(24, 24, 24, 6)
            self.textLayout.addWidget(lineEdit, 0, Qt.AlignTop)

            self.lineEdit_dict[id] = lineEdit

        self.titleLabelInfo = QLabel("说明：{ } 中的内容会在实际发送时被替换，\\n 代表换行", parent)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)


class MessageBoxTeam(MessageBox):
    def __init__(self, title: str, content: dict, template: dict, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.buttonGroup.setMinimumWidth(400)

        font = QFont()
        font.setPointSize(11)

        self.template = template

        self.tech_map = {
            -1: "秘技 / 开怪",
            0: "无操作",
            1: "秘技 1 次",
            2: "秘技 2 次",
        }

        self.comboBox_list = []
        for i in range(1, 5):
            # 将 titleLabel 与两个下拉框放在同一行
            horizontalLayout = QHBoxLayout()

            titleLabel = QLabel(f"{i}号位", parent)
            titleLabel.setFont(font)
            # titleLabel.setMinimumWidth(60)
            titleLabel.setAlignment(Qt.AlignVCenter)
            horizontalLayout.addWidget(titleLabel)

            charComboBox = EditableComboBox()
            charComboBox.setMinimumWidth(130)
            charComboBox.addItems(self.template.values())
            charComboBox.setCurrentText(self.template[self.content[i - 1][0]])
            setup_completer(charComboBox, list(self.template.values()))
            horizontalLayout.addWidget(charComboBox)

            techComboBox = ComboBox()
            techComboBox.setMinimumWidth(130)
            techComboBox.addItems(self.tech_map.values())
            techComboBox.setCurrentText(self.tech_map[self.content[i - 1][1]])
            horizontalLayout.addWidget(techComboBox)

            self.textLayout.addLayout(horizontalLayout)

            self.comboBox_list.append((charComboBox, techComboBox))

        self.titleLabelInfo = QLabel("每个队伍只允许一名角色配置为“秘技 / 开怪”", parent)
        self.titleLabelInfo.setFont(font)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)

    def validate_inputs(self):
        """验证所有输入是否匹配可选项"""
        valid_chars = set(self.template.values())
        valid_techs = set(self.tech_map.values())

        for i, (charComboBox, techComboBox) in enumerate(self.comboBox_list, 1):
            char_text = charComboBox.text()
            tech_text = techComboBox.currentText()

            if char_text not in valid_chars:
                InfoBar.error(
                    title='输入错误',
                    content=f'第{i}号位角色"{char_text}"不在可选项中，请重新选择',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

            if tech_text not in valid_techs:
                InfoBar.error(
                    title='输入错误',
                    content=f'第{i}号位秘技"{tech_text}"不在可选项中，请重新选择',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

        return True

    def accept(self):
        """重写accept方法以添加验证并在关闭前清理 InfoBar"""
        if self.validate_inputs():
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        _cleanup_infobars(self)
        try:
            super().reject()
        except Exception:
            try:
                self.close()
            except Exception:
                pass


class MessageBoxFriends(MessageBox):
    def __init__(self, title: str, content: dict, template: dict, parent=None):
        super().__init__(title, "", parent)
        self.content = content

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.buttonGroup.setMinimumWidth(400)

        font = QFont()
        font.setPointSize(12)

        self.template = template

        self.comboBox_list = []
        for i in range(1, 7):

            charComboBox = EditableComboBox()
            charComboBox.setMaximumWidth(150)
            charComboBox.addItems(self.template.values())
            charComboBox.setCurrentText(self.template[self.content[i - 1][0]])
            setup_completer(charComboBox, list(self.template.values()))

            nameLineEdit = LineEdit()
            nameLineEdit.setMaximumWidth(150)
            nameLineEdit.setText(self.content[i - 1][1])

            horizontalLayout = QHBoxLayout()
            horizontalLayout.addWidget(charComboBox)
            horizontalLayout.addWidget(nameLineEdit)
            self.textLayout.addLayout(horizontalLayout)

            self.comboBox_list.append((charComboBox, nameLineEdit))

        self.titleLabelInfo = QLabel("说明：左侧选择角色后，在右侧对应的文本框中填写好友名称。\n例如好友名称为“持明上網”，填写“持明上”也可以匹配成功，\n若好友名称留空则只查找选择的角色。", parent)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)

    def validate_inputs(self):
        """验证所有输入是否匹配可选项"""
        valid_chars = set(self.template.values())

        for i, (charComboBox, nameLineEdit) in enumerate(self.comboBox_list, 1):
            char_text = charComboBox.text()

            if char_text not in valid_chars:
                InfoBar.error(
                    title='输入错误',
                    content=f'第{i}个好友角色"{char_text}"不在可选项中，请重新选择',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

        return True

    def accept(self):
        """重写accept方法以添加验证并在关闭前清理 InfoBar"""
        if self.validate_inputs():
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        _cleanup_infobars(self)
        try:
            super().reject()
        except Exception:
            try:
                self.close()
            except Exception:
                pass


class MessageBoxPowerPlan(MessageBox):
    """体力计划配置对话框"""

    def __init__(self, title: str, content: list, configtemplate: str, parent=None):
        super().__init__(title, "", parent)
        self.content = content if content else []

        self.textLayout.removeWidget(self.contentLabel)
        self.contentLabel.clear()

        self.yesButton.setText('确认')
        self.cancelButton.setText('取消')

        self.buttonGroup.setMinimumWidth(500)

        font = QFont()
        font.setPointSize(11)

        # 加载副本模板
        with open(configtemplate, 'r', encoding='utf-8') as file:
            self.template = json.load(file)

        # 副本类型列表
        blacklist_type = ["历战余响"]
        self.instance_types = list(self.template.keys())
        for btype in blacklist_type:
            if btype in self.instance_types:
                self.instance_types.remove(btype)

        # 存储所有计划行的控件
        self.plan_rows = []

        # 添加说明
        self.titleLabelInfo = QLabel("体力计划会在清体力前优先执行，完成后自动从列表中删除", parent)
        self.titleLabelInfo.setFont(font)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)

        # 计划列表容器
        self.planLayout = QVBoxLayout()
        self.textLayout.addLayout(self.planLayout)

        # 根据已有内容添加计划行
        for plan in self.content:
            if len(plan) == 3:
                self.add_plan_row(plan[0], plan[1], plan[2])

        # 添加按钮
        addButtonLayout = QHBoxLayout()
        self.addButton = PushButton("添加计划", self)
        self.addButton.clicked.connect(self.add_plan_row)
        addButtonLayout.addWidget(self.addButton)
        addButtonLayout.addStretch(1)
        self.textLayout.addLayout(addButtonLayout)

    def add_plan_row(self, instance_type=None, instance_name=None, count=1):
        """添加一行体力计划配置"""
        # 检查是否已达到最大数量限制
        if len(self.plan_rows) >= 8:
            InfoBar.warning(
                title='无法添加',
                content='已达到最大计划数量',
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        horizontalLayout = QHBoxLayout()

        # 副本类型下拉框
        typeComboBox = ComboBox()
        typeComboBox.setMinimumWidth(140)
        typeComboBox.addItems(self.instance_types)
        if instance_type and instance_type in self.instance_types:
            typeComboBox.setCurrentText(instance_type)
        else:
            typeComboBox.setCurrentIndex(0)

        # 副本名称下拉框
        nameComboBox = EditableComboBox()
        nameComboBox.setMinimumWidth(320)

        # 次数输入框
        countSpinBox = SpinBox()
        countSpinBox.setMinimum(1)
        countSpinBox.setMaximum(999)
        countSpinBox.setValue(count if count else 1)
        countSpinBox.setMinimumWidth(120)

        # 删除按钮
        deleteButton = PushButton("删除", self)
        deleteButton.setMaximumWidth(60)

        # 更新副本名称选项的函数
        def update_instance_names(selected_type):
            nameComboBox.clear()
            if selected_type in self.template:
                item_list = []
                for name, info in self.template[selected_type].items():
                    item_name = f"{name}（{info}）"
                    nameComboBox.addItem(item_name)
                    item_list.append(item_name)
                setup_completer(nameComboBox, item_list)

        # 初始化副本名称
        current_type = typeComboBox.currentText()
        update_instance_names(current_type)
        if instance_name:
            # 如果instance_name已包含括号说明，直接使用；否则尝试匹配并格式化
            if "（" in instance_name and "）" in instance_name:
                nameComboBox.setCurrentText(instance_name)
            else:
                # 查找对应的说明并格式化
                if current_type in self.template and instance_name in self.template[current_type]:
                    formatted_name = f"{instance_name}（{self.template[current_type][instance_name]}）"
                    nameComboBox.setCurrentText(formatted_name)
                else:
                    nameComboBox.setText(instance_name)

        # 连接副本类型改变信号
        typeComboBox.currentTextChanged.connect(update_instance_names)

        # 删除按钮功能
        def delete_row():
            # 从界面移除
            horizontalLayout.setParent(None)
            for i in reversed(range(horizontalLayout.count())):
                widget = horizontalLayout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()

            # 从列表中移除
            if (typeComboBox, nameComboBox, countSpinBox, deleteButton) in self.plan_rows:
                self.plan_rows.remove((typeComboBox, nameComboBox, countSpinBox, deleteButton))

        deleteButton.clicked.connect(delete_row)

        # 添加到布局
        horizontalLayout.addWidget(QLabel("类型:"))
        horizontalLayout.addWidget(typeComboBox)
        horizontalLayout.addWidget(QLabel("名称:"))
        horizontalLayout.addWidget(nameComboBox)
        horizontalLayout.addWidget(QLabel("次数:"))
        horizontalLayout.addWidget(countSpinBox)
        horizontalLayout.addWidget(deleteButton)

        self.planLayout.addLayout(horizontalLayout)

        # 保存到列表
        self.plan_rows.append((typeComboBox, nameComboBox, countSpinBox, deleteButton))

    def get_plans(self):
        """获取所有计划"""
        plans = []
        for typeCombo, nameCombo, countSpin, _ in self.plan_rows:
            instance_type = typeCombo.currentText()
            instance_name = nameCombo.text()

            # 如果输入包含括号说明，提取实际名称
            if "（" in instance_name and "）" in instance_name:
                instance_name = instance_name.split("（")[0]

            count = countSpin.value()
            if instance_type and instance_name and count > 0:
                plans.append([instance_type, instance_name, count])
        return plans

    def validate_inputs(self):
        """验证所有输入是否匹配可选项"""
        for i, (typeCombo, nameCombo, countSpin, _) in enumerate(self.plan_rows, 1):
            instance_type = typeCombo.currentText()
            input_text = nameCombo.text()

            if not instance_type or instance_type not in self.template:
                InfoBar.error(
                    title='输入错误',
                    content=f'第{i}个计划的副本类型无效',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

            # 构建有效选项列表
            valid_options = set()
            for name, info in self.template[instance_type].items():
                valid_options.add(f"{name}（{info}）")
                valid_options.add(name)

            # 检查输入是否匹配任一有效选项
            if input_text not in valid_options:
                InfoBar.error(
                    title='输入错误',
                    content=f'第{i}个计划的副本名称"{input_text}"不在可选项中，请重新选择',
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
                return False

        return True

    def accept(self):
        """确认并保存"""
        if self.validate_inputs():
            _cleanup_infobars(self)
            super().accept()

    def reject(self):
        """取消"""
        _cleanup_infobars(self)
        try:
            super().reject()
        except Exception:
            try:
                self.close()
            except Exception:
                pass
