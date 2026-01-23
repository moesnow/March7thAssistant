# coding:utf-8
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from qfluentwidgets import ScrollArea
from .common.style_sheet import StyleSheet
from module.localization import tr

import markdown
import sys


class ChangelogInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.titleLabel = QLabel(tr("更新日志"), self)
        self.contentLabel = QLabel("html_content", parent)
        html_style = """
<style>
a {
    color: #f18cb9;
    font-weight: bold;
}
</style>
"""
        from module.config import cfg
        changelog_file = "./assets/docs/Changelog.md"
        if hasattr(cfg, 'ui_language_now'):
            if cfg.ui_language_now == "ko_KR":
                import os
                ko_changelog_file = "./assets/docs/Changelog_ko.md"
                if os.path.exists(ko_changelog_file):
                    changelog_file = ko_changelog_file
            elif cfg.ui_language_now == "en_US":
                import os
                en_changelog_file = "./assets/docs/Changelog_en.md"
                if os.path.exists(en_changelog_file):
                    changelog_file = en_changelog_file
        try:
            with open(changelog_file, 'r', encoding='utf-8') as file:
                self.content = file.read()
                self.content = '\n'.join(self.content.split('\n')[2:])
        except FileNotFoundError:
            sys.exit(1)
        html_content = html_style + markdown.markdown(self.content).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'
        self.contentLabel.setText(html_content)
        self.contentLabel.setOpenExternalLinks(True)
        self.contentLabel.linkActivated.connect(self.open_url)

        self.__initWidget()

    def __initWidget(self):
        self.titleLabel.move(36, 30)
        self.view.setObjectName('view')
        self.setViewportMargins(0, 80, 0, 20)
        self.setObjectName('changelogsInterface')
        self.contentLabel.setObjectName('contentLabel')
        self.titleLabel.setObjectName('changelogsLabel')
        StyleSheet.CHANGELOGS_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        # self.vBoxLayout.setSpacing(8)
        # self.vBoxLayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        # self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignmentFlag.AlignTop)

        # self.vBoxLayout.setSpacing(28)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignmentFlag.AlignTop)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))
