import os
import sys

import markdown
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QStackedWidget, QScroller, QScrollerProperties, QSizePolicy
from qfluentwidgets import qconfig, ScrollArea, Pivot, TextBrowser, setCustomStyleSheet
from .common.style_sheet import StyleSheet
from module.localization import tr


class HelpInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.pivot = Pivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.helpLabel = QLabel(tr("帮助"), self)
        self.tutorialLabel = TextBrowser(parent)
        self.workflowLabel = TextBrowser(parent)
        self.faqLabel = TextBrowser(parent)
        self.tasksLabel = TextBrowser(parent)
        self.changelogLabel = TextBrowser(parent)

        self.__initWidget()
        self.__initCard()
        self.__initLayout()

    def __initWidget(self):
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 140, 0, 5)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.setObjectName('helpInterface')
        self.scrollWidget.setObjectName('scrollWidget')
        self.helpLabel.setObjectName('helpLabel')
        StyleSheet.HELP_INTERFACE.apply(self)

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __initCard(self):
        tutorial_style = """
<style>
a {
    color: #f18cb9;
    font-weight: bold;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th, td {
  border: 1px solid black;
  padding: 1px 30px 1px 30px;
  text-align: left;
  font-size: 15px;
}
</style>
"""
        from module.config import cfg
        tutorial_file = self._get_localized_doc_path("Tutorial")
        try:
            with open(tutorial_file, 'r', encoding='utf-8') as file:
                self.content = file.read().replace('/assets/docs/Background.md', 'https://m7a.top/#/assets/docs/Background').replace('/assets/docs/Docker.md',
                                                                                                                                     'https://m7a.top/#/assets/docs/Docker').replace('/assets/docs/Termux.md', 'https://m7a.top/#/assets/docs/Termux').replace('/assets/docs/Workflow.md', 'https://m7a.top/#/assets/docs/Workflow')
                self.content = '\n'.join(self.content.split('\n')[1:])
        except FileNotFoundError:
            sys.exit(1)
        self.tutorial_content = tutorial_style + markdown.markdown(self.content, extensions=['tables']).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'

        if qconfig.theme.name == "DARK":
            self.tutorialLabel.setText(self.tutorial_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.tutorialLabel.setText(self.tutorial_content)
        self.tutorialLabel.setOpenExternalLinks(True)
        self.tutorialLabel.anchorClicked.connect(self.open_url)

        workflow_file = self._get_localized_doc_path("Workflow")
        try:
            with open(workflow_file, 'r', encoding='utf-8') as file:
                self.content = file.read()
                self.content = '\n'.join(self.content.split('\n')[1:])
        except FileNotFoundError:
            sys.exit(1)
        self.workflow_content = tutorial_style + markdown.markdown(self.content, extensions=['tables']).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'

        if qconfig.theme.name == "DARK":
            self.workflowLabel.setText(self.workflow_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.workflowLabel.setText(self.workflow_content)
        self.workflowLabel.setOpenExternalLinks(True)
        self.workflowLabel.anchorClicked.connect(self.open_url)

        faq_style = """
<style>
a {
    color: #f18cb9;
    font-weight: bold;
}
</style>
"""
        faq_file = self._get_localized_doc_path("FAQ")
        try:
            with open(faq_file, 'r', encoding='utf-8') as file:
                self.content = file.read()
                self.content = '\n'.join(self.content.split('\n')[2:])
        except FileNotFoundError:
            sys.exit(1)
        faq_content = faq_style + markdown.markdown(self.content).replace('<h3>', '<br><h3>').replace('</h3>', '</h3><hr>').replace('<br>', '', 1) + '<br>'
        self.faqLabel.setText(faq_content)
        self.faqLabel.setOpenExternalLinks(True)
        self.faqLabel.anchorClicked.connect(self.open_url)

        qconfig.themeChanged.connect(self.__themeChanged)
        tasks_style = """
<style>
table {
  border-collapse: collapse;
  width: 100%;
}

th, td {
  border: 1px solid black;
  padding: 1px 30px 1px 30px;
  text-align: left;
  font-size: 15px;
}
</style>
"""
        # Daily training tasks table - 多语言文档（assets/docs/TasksTable*.md，缺失时回退中文）
        tasks_file = self._get_localized_doc_path("TasksTable")
        try:
            with open(tasks_file, 'r', encoding='utf-8') as file:
                self.content = file.read()
                self.content = '\n'.join(self.content.split('\n')[1:])
        except FileNotFoundError:
            sys.exit(1)
        self.tasks_content = tasks_style + markdown.markdown(self.content, extensions=['tables'])

        if qconfig.theme.name == "DARK":
            self.tasksLabel.setText(self.tasks_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.tasksLabel.setText(self.tasks_content)

        changelog_style = """
<style>
a {
    color: #f18cb9;
    font-weight: bold;
}
</style>
"""
        changelog_file = self._get_localized_doc_path("Changelog")
        try:
            with open(changelog_file, 'r', encoding='utf-8') as file:
                self.content = file.read()
                self.content = '\n'.join(self.content.split('\n')[1:])
        except FileNotFoundError:
            sys.exit(1)
        changelog_content = changelog_style + markdown.markdown(self.content).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'
        self.changelogLabel.setText(changelog_content)
        self.changelogLabel.setOpenExternalLinks(True)
        self.changelogLabel.anchorClicked.connect(self.open_url)

    def __initLayout(self):
        self.helpLabel.move(36, 30)
        self.pivot.move(40, 80)

        self.stackedWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.vBoxLayout.addWidget(self.stackedWidget, 1)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        # self.vBoxLayout.addWidget(self.tutorialLabel, 0, Qt.AlignTop)
        self.addSubInterface(self.tutorialLabel, 'tutorialLabel', tr('使用教程'))
        self.addSubInterface(self.workflowLabel, 'workflowLabel', tr('流程编排'))
        self.addSubInterface(self.faqLabel, 'faqLabel', tr('常见问题'))
        self.addSubInterface(self.tasksLabel, 'tasksLabel', tr('每日实训'))
        self.addSubInterface(self.changelogLabel, 'changelogLabel', tr('更新日志'))

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName())

    def addSubInterface(self, widget: TextBrowser, objectName, text):
        widget.setObjectName(objectName)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        widget.document().setDocumentMargin(10)

        custom_scrollbar_qss = """
            QTextBrowser {
                background: transparent;
                border: none;
                selection-background-color: #f18cb9;
            }
            QTextBrowser:hover {
                background: transparent;
                border: none;
                selection-background-color: #f18cb9;
            }
            QTextBrowser:focus {
                background: transparent;
                border: none;
                selection-background-color: #f18cb9;
            }
            
            QScrollBar:vertical {
                background: transparent;
                width: 12px;
                margin: 0px;
            }
            
            QScrollBar::handle:vertical {
                background: rgba(128, 128, 128, 150);
                border-radius: 5px;
                border-width: 1px;
                width: 10px;
                min-height: 30px;
                margin: 2px 1px 2px 1px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: rgba(128, 128, 128, 200);
                border-radius: 5px;
            }
            
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
            }
            
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """
        setCustomStyleSheet(widget, custom_scrollbar_qss, custom_scrollbar_qss)

        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(
            routeKey=objectName,
            text=text,
            onClick=lambda: self.stackedWidget.setCurrentWidget(widget)
        )

    def onCurrentIndexChanged(self, index):
        widget = self.stackedWidget.widget(index)
        self.pivot.setCurrentItem(widget.objectName())

        self.verticalScrollBar().setValue(0)

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def _get_localized_doc_path(self, base_name: str) -> str:
        from module.localization.languages import localized_doc_path
        return localized_doc_path(base_name)

    def __themeChanged(self):
        if qconfig.theme.name == "DARK":
            self.tutorialLabel.setText(self.tutorial_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.tutorialLabel.setText(self.tutorial_content)

        if qconfig.theme.name == "DARK":
            self.workflowLabel.setText(self.workflow_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.workflowLabel.setText(self.workflow_content)

        if qconfig.theme.name == "DARK":
            self.tasksLabel.setText(self.tasks_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.tasksLabel.setText(self.tasks_content)
