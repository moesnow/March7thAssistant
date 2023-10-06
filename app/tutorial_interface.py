# coding:utf-8
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

from qfluentwidgets import ScrollArea
from .common.style_sheet import StyleSheet

import markdown
import sys


class TutorialInterface(ScrollArea):
    """ Home interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        # self.titleLabel = QLabel(self.tr("常见问题"), self)
        self.contentLabel = QLabel("html_content", parent)
        html_style = """
<style>
a {
    color: #f18cb9;
    font-weight: bold;
}
</style>
"""
        try:
            with open(".\\assets\\docs\\Tutorial.md", 'r', encoding='utf-8') as file:
                self.content = file.read()
        except FileNotFoundError:
            sys.exit(1)
        html_content = html_style + markdown.markdown("## 点击跳转 [网页版](https://moesnow.github.io/March7thAssistant/#/assets/docs/Tutorial) 排版更美观")+markdown.markdown(self.content)
        self.contentLabel.setText(html_content)
        self.contentLabel.setOpenExternalLinks(True)
        self.contentLabel.linkActivated.connect(self.open_url)

        self.__initWidget()

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('TutorialsInterface')
        self.contentLabel.setObjectName('contentLabel')
        # self.titleLabel.setObjectName('FQAsLabel')
        StyleSheet.Tutorial_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(36, 8, 36, 36)
        self.vBoxLayout.setSpacing(8)
        self.vBoxLayout.setAlignment(Qt.AlignTop)
        # self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))
