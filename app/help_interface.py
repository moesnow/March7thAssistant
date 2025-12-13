from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QStackedWidget, QSpacerItem, QScroller, QScrollerProperties
from qfluentwidgets import qconfig, ScrollArea, Pivot
from .common.style_sheet import StyleSheet
import markdown
import sys


class HelpInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.pivot = Pivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.helpLabel = QLabel(self.tr("帮助"), self)
        self.tutorialLabel = QLabel(parent)
        self.faqLabel = QLabel(parent)
        self.tasksLabel = QLabel(parent)
        self.changelogLabel = QLabel(parent)

        self.__initWidget()
        self.__initCard()
        self.__initLayout()

    def __initWidget(self):
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setViewportMargins(0, 140, 0, 5)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

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
</style>
"""
        try:
            with open("./assets/docs/Tutorial.md", 'r', encoding='utf-8') as file:
                self.content = file.read().replace('/assets/docs/Background.md', 'https://m7a.top/#/assets/docs/Background')
                self.content = '\n'.join(self.content.split('\n')[1:])
        except FileNotFoundError:
            sys.exit(1)
        tutorial_content = tutorial_style + markdown.markdown(self.content).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'
        self.tutorialLabel.setText(tutorial_content)
        self.tutorialLabel.setOpenExternalLinks(True)
        self.tutorialLabel.linkActivated.connect(self.open_url)

        faq_style = """
<style>
a {
    color: #f18cb9;
    font-weight: bold;
}
</style>
"""
        try:
            with open("./assets/docs/FAQ.md", 'r', encoding='utf-8') as file:
                self.content = file.read()
                self.content = '\n'.join(self.content.split('\n')[2:])
        except FileNotFoundError:
            sys.exit(1)
        faq_content = faq_style + markdown.markdown(self.content).replace('<h3>', '<br><h3>').replace('</h3>', '</h3><hr>').replace('<br>', '', 1) + '<br>'
        self.faqLabel.setText(faq_content)
        self.faqLabel.setOpenExternalLinks(True)
        self.faqLabel.linkActivated.connect(self.open_url)

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
        self.content = """
| 任务描述                             | 活跃度 | 支持情况 |
| ----------------------------------- | -------- | -------- |
| 登录游戏                             |   +100   |   ✅     |
| 派遣1次委托                          |   +100   |   ✅     |
| 累计消耗120点开拓力                   |   +200   |   ✅     |
| 累计消灭20个敌人                      |   +100   |   ✅     |
| 使用支援角色并获得战斗胜利1次          |   +200   |   ✅     |
| 使用1次「万能合成机」                  |   +100   |   ✅    |
| 将任意遗器等级提升1次                  |   +100   |   ❌    |
| 完成1次「差分宇宙」或「货币战争」       |   +500   |   ✅    |
| 完成1个日常任务                       |   +200  |   已移除  |
| 拍照1次                              |   +100   |   已移除  |
| 完成1次「拟造花萼（金）」               |   +100  |   已移除  |
| 完成1次「拟造花萼（赤）」               |   +100  |   已移除  |
| 完成1次「凝滞虚影」                    |   +100  |   已移除  |
| 完成1次「侵蚀隧洞」                    |   +100  |   已移除  |
| 完成1次「历战余响」                    |   +200  |   已移除  |
| 完成1次「忘却之庭」                    |   +200  |   已移除  |
| 通关「模拟宇宙」（任意世界）的1个区域   |   +200  |   已移除  |
| 完成1次「模拟宇宙」                    |   +500  |   已移除  |
| 累计触发弱点击破效果5次                |   +100  |   已移除  |
| 单场战斗中，触发3种不同属性的弱点击破   |   +100  |   已移除  |
| 累计施放2次秘技                       |   +100  |   已移除  |
| 利用弱点进入战斗并获胜3次              |   +100  |   已移除  |
| 累计击碎3个可破坏物                   |   +200  |   已移除  |
| 施放终结技造成制胜一击1次              |   +200  |   已移除  |
| 将任意角色等级提升1次                  |   +100  |   已移除  |
| 将任意光锥等级提升1次                  |   +100  |   已移除  |
| 分解任意1件遗器                       |   +100  |   已移除  |
| 合成1次消耗品                         |   +100  |   已移除  |
| 合成1次材料                          |   +100  |   已移除  |
| 使用1件消耗品                         |   +100  |   已移除  |
        """
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
        try:
            with open("./assets/docs/Changelog.md", 'r', encoding='utf-8') as file:
                self.content = file.read()
                self.content = '\n'.join(self.content.split('\n')[1:])
        except FileNotFoundError:
            sys.exit(1)
        changelog_content = changelog_style + markdown.markdown(self.content).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'
        self.changelogLabel.setText(changelog_content)
        self.changelogLabel.setOpenExternalLinks(True)
        self.changelogLabel.linkActivated.connect(self.open_url)

    def __initLayout(self):
        self.helpLabel.move(36, 30)
        self.pivot.move(40, 80)
        # self.vBoxLayout.addWidget(self.pivot, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.stackedWidget, 0, Qt.AlignTop)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        # self.vBoxLayout.addWidget(self.tutorialLabel, 0, Qt.AlignTop)
        self.addSubInterface(self.tutorialLabel, 'tutorialLabel', self.tr('使用教程'))
        self.addSubInterface(self.faqLabel, 'faqLabel', self.tr('常见问题'))
        self.addSubInterface(self.tasksLabel, 'tasksLabel', self.tr('每日实训'))
        self.addSubInterface(self.changelogLabel, 'changelogLabel', self.tr('更新日志'))

        self.stackedWidget.currentChanged.connect(self.onCurrentIndexChanged)
        self.pivot.setCurrentItem(self.stackedWidget.currentWidget().objectName())
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

    def addSubInterface(self, widget: QLabel, objectName, text):
        def remove_spacing(layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if isinstance(item, QSpacerItem):
                    layout.removeItem(item)
                    break

        # remove_spacing(widget.vBoxLayout)
        # widget.titleLabel.setHidden(True)

        widget.setObjectName(objectName)
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
        self.stackedWidget.setFixedHeight(self.stackedWidget.currentWidget().sizeHint().height())

    def open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))

    def __themeChanged(self):
        if qconfig.theme.name == "DARK":
            self.tasksLabel.setText(self.tasks_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.tasksLabel.setText(self.tasks_content)
