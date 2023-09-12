# coding:utf-8
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

from qfluentwidgets import ScrollArea

import markdown


class FQAInterface(ScrollArea):
    """ Home interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.titleLabel = QLabel(self.tr("常见问题"), self)
        self.contentLabel = QLabel("html_content", parent)
        try:
            with open(".\\assets\\docs\\FQA.md", 'r', encoding='utf-8') as file:
                self.content = file.read()
        except FileNotFoundError:
            exit(1)
        html_content = markdown.markdown(self.content)
        self.contentLabel.setText(html_content)
        self.contentLabel.setOpenExternalLinks(True)
        self.contentLabel.linkActivated.connect(self.open_url)

        self.__initWidget()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('FQAsInterface')
        self.contentLabel.setObjectName('contentLabel')
        self.titleLabel.setObjectName('FQAsLabel')
        self.setStyleSheet("""
#view {
    background-color: transparent;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QLabel#contentLabel {
    font: 14px 'Microsoft YaHei Light';
}
                           
QLabel#FQAsLabel {
    font: 28px 'Microsoft YaHei Light';
    background-color: transparent;
}
        """)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(36, 8, 36, 36)
        self.vBoxLayout.setSpacing(8)
        self.vBoxLayout.setAlignment(Qt.AlignTop)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))
