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

        self.helpLabel = QLabel("도움말", self)
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
        # 일일 훈련 임무 목록 (한국어 번역)
        self.content = """
| 임무 설명                             | 활약도 | 지원 여부 |
| ----------------------------------- | -------- | -------- |
| 게임 로그인                             |   +100   |   ✅     |
| 의뢰 1회 파견                          |   +100   |   ✅     |
| 개척력 120pt 누적 소모                  |   +200   |   ✅     |
| 적 20기 누적 처치                      |   +100   |   ✅     |
| 지원 캐릭터를 사용하여 전투 1회 승리      |   +200   |   ✅     |
| 「만능 합성기」 1회 사용                 |   +100   |   ✅    |
| 임의의 유물 레벨 1회 강화               |   +100   |   ❌    |
| 「차분화 우주」 또는 「화폐 전쟁」 1회 완료 |   +500   |   ✅    |
| 일일 임무 1개 완료                      |   +200  |   제거됨  |
| 사진 촬영 1회                          |   +100   |   제거됨  |
| 「고치(금)」 1회 완료                    |   +100  |   제거됨  |
| 「고치(적)」 1회 완료                    |   +100  |   제거됨  |
| 「정체된 허영」 1회 완료                 |   +100  |   제거됨  |
| 「침식된 터널」 1회 완료                 |   +100  |   제거됨  |
| 「전쟁의 여운」 1회 완료                 |   +200  |   제거됨  |
| 「망각의 정원」 1회 완료                 |   +200  |   제거됨  |
| 「시뮬레이션 우주」(임의의 세계) 1개 구역 통과 |   +200  |   제거됨  |
| 「시뮬레이션 우주」 1회 완료              |   +500  |   제거됨  |
| 약점 격파 효과 5회 누적 발동            |   +100  |   제거됨  |
| 단일 전투에서 서로 다른 속성의 약점 격파 3회 발동 |   +100  |   제거됨  |
| 비술 2회 누적 발동                      |   +100  |   제거됨  |
| 약점을 이용하여 전투 진입 및 승리 3회    |   +100  |   제거됨  |
| 파괴 가능한 물체 3개 누적 파괴          |   +200  |   제거됨  |
| 필살기를 발동해 제승의 일격 1회 가하기   |   +200  |   제거됨  |
| 임의의 캐릭터 레벨 1회 강화             |   +100  |   제거됨  |
| 임의의 광추 레벨 1회 강화               |   +100  |   제거됨  |
| 임의의 유물 1개 분해                    |   +100  |   제거됨  |
| 소모품 1회 합성                        |   +100  |   제거됨  |
| 재료 1회 합성                          |   +100  |   제거됨  |
| 소모품 1개 사용                        |   +100  |   제거됨  |
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
        self.addSubInterface(self.tutorialLabel, 'tutorialLabel', '사용 튜토리얼')
        self.addSubInterface(self.faqLabel, 'faqLabel', '자주 묻는 질문')
        self.addSubInterface(self.tasksLabel, 'tasksLabel', '일일 훈련')
        self.addSubInterface(self.changelogLabel, 'changelogLabel', '업데이트 내역')

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