# coding:utf-8
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QLabel, QFrame, QVBoxLayout, QHBoxLayout, QPushButton
from qframelesswindow import FramelessDialog

from qfluentwidgets import LineEdit, TextWrap, FluentStyleSheet, PrimaryPushButton,EditableComboBox

from .mask_dialog_base import MaskDialogBase


class Ui_MessageBox:
    """ Ui of message box """

    yesSignal = pyqtSignal()
    cancelSignal = pyqtSignal()

    def _setUpUi(self, title, content, parent):
        self.content = content
        self.titleLabel = QLabel(title, parent)
        # self.contentLabel = QLabel(content, parent)
        self.content_count = len(content)

        font = QFont()
        font.setPointSize(15)


        self.label0 = "拟造花萼（金）"
        self.titleLabel0 = QLabel(f"{self.label0}", parent)
        self.titleLabel0.setFont(font)
        self.comboBox0 = EditableComboBox()
        self.Items0 = [
            "回忆之蕾（角色经验）",
            "以太之蕾（武器经验）",
            "藏珍之蕾（信用点）",
        ]
        self.comboBox0.addItems(self.Items0)
        self.content0 = next((item for item in self.Items0 if self.content[self.label0] in item), self.content[self.label0])
        self.comboBox0.setText(self.content0)
        self.comboBox0._onTextEdited(self.content0)


        self.label1 = "拟造花萼（赤）"
        self.titleLabel1 = QLabel(f"{self.label1}", parent)
        self.titleLabel1.setFont(font)
        self.comboBox1 = EditableComboBox()
        self.Items1 = [
            "毁灭之蕾（行迹）",
            "存护之蕾（行迹）",
            "巡猎之蕾（行迹）",
            "丰饶之蕾（行迹）",
            "智识之蕾（行迹）",
            "同谐之蕾（行迹）",
            "虚无之蕾（行迹）",
        ]
        self.comboBox1.addItems(self.Items1)
        self.content1 = next((item for item in self.Items1 if self.content[self.label1] in item), self.content[self.label1])
        self.comboBox1.setText(self.content1)
        self.comboBox1._onTextEdited(self.content1)


        self.label2 = "凝滞虚影"
        self.titleLabel2 = QLabel(f"{self.label2}", parent)
        self.titleLabel2.setFont(font)
        self.comboBox2 = EditableComboBox()
        self.Items2 = [
            "空海之形（希儿 / 银狼 / 青雀）",
            "巽风之形（布洛妮娅 / 丹恒 / 桑博）",
            "鸣雷之形（白露 / 停云 / 希露瓦 / 阿兰）",
            "炎华之形（姬子 / 艾丝妲 / 虎克）",
            "锋芒之形（克拉拉 / 素裳 / 娜塔莎 / 卢卡）",
            "霜晶之形（杰帕德 / 三月七 / 佩拉 / 黑塔）",
            "幻光之形（罗刹 / 瓦尔特 / 驭空）",
            "冰棱之形（镜流 / 彦卿）",
            "震厄之形（景元 / 卡芙卡）",
            "偃偶之形（丹恒·饮月）",
            "孽兽之形（符玄 / 玲可）",
            "天人之形（刃 / 藿藿）",
            "燔灼之形（托帕&账账 / 桂乃芬）",
        ]
        self.comboBox2.addItems(self.Items2)
        self.content2 = next((item for item in self.Items2 if self.content[self.label2] in item), self.content[self.label2])
        self.comboBox2.setText(self.content2)
        self.comboBox2._onTextEdited(self.content2)

    
        self.label3 = "侵蚀隧洞"
        self.titleLabel3 = QLabel(f"{self.label3}", parent)
        self.titleLabel3.setFont(font)
        self.comboBox3 = EditableComboBox()
        self.Items3 = [
            "霜风之径（冰套+风套）",
            "迅拳之径（物理套+击破套）",
            "漂泊之径（治疗套+快枪手）",
            "睿治之径（铁卫套+量子套）",
            "圣颂之径（防御套+雷套）",
            "野焰之径（火套+虚数套）",
            "药使之径（生命套+速度套）",
        ]
        self.comboBox3.addItems(self.Items3)
        self.content3 = next((item for item in self.Items3 if self.content[self.label3] in item), self.content[self.label3])
        self.comboBox3.setText(self.content3)
        self.comboBox3._onTextEdited(self.content3)


        self.label4 = "历战余响"
        self.titleLabel4 = QLabel(f"{self.label4}", parent)
        self.titleLabel4.setFont(font)
        self.comboBox4 = EditableComboBox()
        self.Items4 = [
            "毁灭的开端（末日兽）",
            "寒潮的落幕（可可利亚）",
            "不死的神实（幻胧）",
        ]
        self.comboBox4.addItems(self.Items4)
        self.content4 = next((item for item in self.Items4 if self.content[self.label4] in item), self.content[self.label4])
        self.comboBox4.setText(self.content4)
        self.comboBox4._onTextEdited(self.content4)

        self.titleLabel5 = QLabel("说明：清体力是根据选择的副本类型来判断的,\n此处设置的副本名称也会用于完成每日实训对应的任务,\n如果即使有对应的任务,你也不希望完成,可以手动修改对应的副本名称为“无”", parent)

        self.buttonGroup = QFrame(parent)
        self.yesButton = PrimaryPushButton(self.tr('确认'), self.buttonGroup)
        self.cancelButton = QPushButton(self.tr('取消'), self.buttonGroup)

        self.vBoxLayout = QVBoxLayout(parent)
        self.textLayout = QVBoxLayout()
        self.buttonLayout = QHBoxLayout(self.buttonGroup)

        self.__initWidget()

    def __initWidget(self):
        self.__setQss()
        self.__initLayout()

        # fixes https://github.com/zhiyiYo/PyQt-Fluent-Widgets/issues/19
        self.yesButton.setAttribute(Qt.WA_LayoutUsesWidgetRect)
        self.cancelButton.setAttribute(Qt.WA_LayoutUsesWidgetRect)

        self.yesButton.setFocus()
        self.buttonGroup.setFixedHeight(81)

        self._adjustText()

        self.yesButton.clicked.connect(self.__onYesButtonClicked)
        self.cancelButton.clicked.connect(self.__onCancelButtonClicked)

    def _adjustText(self):
        if self.isWindow():
            if self.parent():
                w = max(self.titleLabel.width(), self.parent().width())
                chars = max(min(w / 9, 140), 30)
            else:
                chars = 100
        else:
            w = max(self.titleLabel.width(), self.window().width())
            chars = max(min(w / 9, 100), 30)

        # self.contentLabel.setText(TextWrap.wrap(self.content, chars, False)[0])

    def __initLayout(self):
        self.vBoxLayout.setSpacing(0)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.addLayout(self.textLayout, 1)
        self.vBoxLayout.addWidget(self.buttonGroup, 0, Qt.AlignBottom)
        self.vBoxLayout.setSizeConstraint(QVBoxLayout.SetMinimumSize)

        self.textLayout.setSpacing(12)
        self.textLayout.setContentsMargins(24, 24, 24, 24)
        self.textLayout.addWidget(self.titleLabel, 0, Qt.AlignTop)
        # self.textLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)

        self.textLayout.addWidget(self.titleLabel0, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.comboBox0, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.titleLabel1, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.comboBox1, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.titleLabel2, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.comboBox2, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.titleLabel3, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.comboBox3, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.titleLabel4, 0, Qt.AlignTop)
        self.textLayout.addWidget(self.comboBox4, 0, Qt.AlignTop)
        
        self.textLayout.addWidget(self.titleLabel5, 0, Qt.AlignTop)

        self.buttonLayout.setSpacing(12)
        self.buttonLayout.setContentsMargins(24, 24, 24, 24)
        self.buttonLayout.addWidget(self.yesButton, 1, Qt.AlignVCenter)
        self.buttonLayout.addWidget(self.cancelButton, 1, Qt.AlignVCenter)

    def __onCancelButtonClicked(self):
        self.reject()
        self.cancelSignal.emit()

    def __onYesButtonClicked(self):
        self.accept()
        self.yesSignal.emit()

    def __setQss(self):
        self.titleLabel.setObjectName("titleLabel")
        # self.contentLabel.setObjectName("contentLabel")
        self.buttonGroup.setObjectName('buttonGroup')
        self.cancelButton.setObjectName('cancelButton')

        FluentStyleSheet.DIALOG.apply(self)

        self.yesButton.adjustSize()
        self.cancelButton.adjustSize()


class Dialog(FramelessDialog, Ui_MessageBox):
    """ Dialog box """

    yesSignal = pyqtSignal()
    cancelSignal = pyqtSignal()

    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent=parent)
        self._setUpUi(title, content, self)

        self.windowTitleLabel = QLabel(title, self)

        self.setResizeEnabled(False)
        self.resize(240, 192)
        self.titleBar.hide()

        self.vBoxLayout.insertWidget(0, self.windowTitleLabel, 0, Qt.AlignTop)
        self.windowTitleLabel.setObjectName('windowTitleLabel')
        FluentStyleSheet.DIALOG.apply(self)
        self.setFixedSize(self.size())

    def setTitleBarVisible(self, isVisible: bool):
        self.windowTitleLabel.setVisible(isVisible)


class MessageBoxInstanceNames(MaskDialogBase, Ui_MessageBox):
    """ Message box """

    yesSignal = pyqtSignal()
    cancelSignal = pyqtSignal()

    def __init__(self, title: str, content: dict, parent=None):
        super().__init__(parent=parent)
        self._setUpUi(title, content, self.widget)

        self.setShadowEffect(60, (0, 10), QColor(0, 0, 0, 50))
        self.setMaskColor(QColor(0, 0, 0, 76))
        self._hBoxLayout.removeWidget(self.widget)
        self._hBoxLayout.addWidget(self.widget, 1, Qt.AlignCenter)

        self.buttonGroup.setMinimumWidth(480)

    def eventFilter(self, obj, e: QEvent):
        if obj is self.window():
            if e.type() == QEvent.Resize:
                self._adjustText()

        return super().eventFilter(obj, e)
