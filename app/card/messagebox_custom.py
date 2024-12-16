from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QLabel, QHBoxLayout
from PyQt5.QtGui import QPixmap, QDesktopServices, QFont
from qfluentwidgets import MessageBox, LineEdit, ComboBox, EditableComboBox, DateTimeEdit, BodyLabel, FluentStyleSheet, TextEdit
from typing import Optional
from module.config import cfg
import datetime
import json


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


class MessageBoxUpdate(MessageBoxHtml):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.yesButton.setText('下载')
        self.cancelButton.setText('好的')


class MessageBoxDisclaimer(MessageBoxHtml):
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(title, content, parent)

        self.yesButton.setText('退出')
        self.cancelButton.setText('我已知晓')
        self.setContentCopyable(True)


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
            titleLabel = QLabel(type, parent)
            titleLabel.setFont(font)
            self.textLayout.addWidget(titleLabel, 0, Qt.AlignTop)

            # comboBox = ComboBox()
            comboBox = EditableComboBox()

            has_default = False
            for name, info in names.items():
                item_name = f"{name}（{info}）"
                comboBox.addItem(item_name)
                if self.content[type] == name:
                    comboBox.setCurrentText(item_name)
                    has_default = True
            if not has_default:
                comboBox.setText(self.content[type])

            self.textLayout.addWidget(comboBox, 0, Qt.AlignTop)
            self.comboBox_dict[type] = comboBox

        self.titleLabelInfo = QLabel("说明：未更新副本支持手动输入名称，清体力是根据选择的副本类型来判断的,\n此处设置的副本名称也会用于完成活动或每日实训对应的任务,\n如果即使有对应的任务,你也不希望完成,可以将对应的副本名称改为“无”", parent)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)


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
        self.textLayout.setSpacing(4)

        self.lineEdit_dict = {}
        for name, config in self.configlist.items():
            titleLabel = QLabel(name.capitalize(), parent)
            titleLabel.setFont(font)
            self.textLayout.addWidget(titleLabel, 0, Qt.AlignTop)

            lineEdit = LineEdit(self)
            lineEdit.setText(str(cfg.get_value(config)))
            lineEdit.setFont(font)

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
        font.setPointSize(12)

        self.template = template

        self.tech_map = {
            -1: "秘技 / 开怪",
            0: "无操作",
            1: "秘技 1 次",
            2: "秘技 2 次",
        }

        self.comboBox_list = []
        for i in range(1, 5):
            titleLabel = QLabel(f"{i}号位", parent)
            titleLabel.setFont(font)
            self.textLayout.addWidget(titleLabel, 0, Qt.AlignTop)

            charComboBox = ComboBox()
            charComboBox.setMaximumWidth(150)
            charComboBox.addItems(self.template.values())
            charComboBox.setCurrentText(self.template[self.content[i - 1][0]])

            techComboBox = ComboBox()
            techComboBox.setMaximumWidth(150)
            techComboBox.addItems(self.tech_map.values())
            techComboBox.setCurrentText(self.tech_map[self.content[i - 1][1]])

            horizontalLayout = QHBoxLayout()
            horizontalLayout.addWidget(charComboBox)
            horizontalLayout.addWidget(techComboBox)
            self.textLayout.addLayout(horizontalLayout)

            self.comboBox_list.append((charComboBox, techComboBox))

        self.titleLabelInfo = QLabel("说明：每个队伍中只允许一名角色配置为“秘技 / 开怪”，\n数字代表秘技使用次数，其中-1代表最后一个放秘技并开怪的角色", parent)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)


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

            charComboBox = ComboBox()
            charComboBox.setMaximumWidth(150)
            charComboBox.addItems(self.template.values())
            charComboBox.setCurrentText(self.template[self.content[i - 1][0]])

            nameLineEdit = LineEdit()
            nameLineEdit.setMaximumWidth(150)
            nameLineEdit.setText(self.content[i - 1][1])

            horizontalLayout = QHBoxLayout()
            horizontalLayout.addWidget(charComboBox)
            horizontalLayout.addWidget(nameLineEdit)
            self.textLayout.addLayout(horizontalLayout)

            self.comboBox_list.append((charComboBox, nameLineEdit))

        self.titleLabelInfo = QLabel("说明：左侧选择角色后，在右侧对应的文本框中填写好友名称。\n例如好友名称为“持明上網”，填写“持明上”也可以匹配成功", parent)
        self.textLayout.addWidget(self.titleLabelInfo, 0, Qt.AlignTop)
