from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QStackedWidget, QSpacerItem, QScroller, QScrollerProperties
from qfluentwidgets import qconfig, ScrollArea, Pivot
from .common.style_sheet import StyleSheet
from module.localization import tr
import markdown
import sys


class HelpInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scrollWidget = QWidget()
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)

        self.pivot = Pivot(self)
        self.stackedWidget = QStackedWidget(self)

        self.helpLabel = QLabel(tr("帮助"), self)
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
        # Load Tutorial based on language setting
        from module.config import cfg
        tutorial_file = "./assets/docs/Tutorial.md"
        if hasattr(cfg, 'ui_language_now'):
            if cfg.ui_language_now == "ko_KR":
                import os
                ko_file = "./assets/docs/Tutorial_ko.md"
                if os.path.exists(ko_file):
                    tutorial_file = ko_file
            elif cfg.ui_language_now == "en_US":
                import os
                en_file = "./assets/docs/Tutorial_en.md"
                if os.path.exists(en_file):
                    tutorial_file = en_file
        try:
            with open(tutorial_file, 'r', encoding='utf-8') as file:
                self.content = file.read().replace('/assets/docs/Background.md', 'https://m7a.top/#/assets/docs/Background').replace('/assets/docs/Docker.md', 'https://m7a.top/#/assets/docs/Docker')
                self.content = '\n'.join(self.content.split('\n')[1:])
        except FileNotFoundError:
            sys.exit(1)
        self.tutorial_content = tutorial_style + markdown.markdown(self.content, extensions=['tables']).replace('<h2>', '<br><h2>').replace('</h2>', '</h2><hr>').replace('<br>', '', 1) + '<br>'

        if qconfig.theme.name == "DARK":
            self.tutorialLabel.setText(self.tutorial_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.tutorialLabel.setText(self.tutorial_content)
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
        # Load FAQ based on language setting
        faq_file = "./assets/docs/FAQ.md"
        if hasattr(cfg, 'ui_language_now'):
            if cfg.ui_language_now == "ko_KR":
                import os
                ko_faq_file = "./assets/docs/FAQ_ko.md"
                if os.path.exists(ko_faq_file):
                    faq_file = ko_faq_file
            elif cfg.ui_language_now == "en_US":
                import os
                en_faq_file = "./assets/docs/FAQ_en.md"
                if os.path.exists(en_faq_file):
                    faq_file = en_faq_file
        try:
            with open(faq_file, 'r', encoding='utf-8') as file:
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
        # Daily training tasks table - language based
        if hasattr(cfg, 'ui_language_now') and cfg.ui_language_now == "ko_KR":
            self.content = """
| 작업 설명                             | 활성도 | 지원 상태 |
| ----------------------------------- | -------- | -------- |
| 게임 로그인                             |   +100   |   ✅     |
| 의뢰 1회 수행                          |   +100   |   ✅     |
| 개척력 120pt 누적 소모                  |   +200   |   ✅     |
| 적 20기 누적 처치                      |   +100   |   ✅     |
| 지원 캐릭터 포함 전투 1회 승리          |   +200   |   ✅     |
| '만능 합성기' 1회 사용                  |   +100   |   ✅    |
| 임의 유물 레벨 1회 강화                  |   +100   |   ❌    |
| '차분 우주' 또는 '화폐 전쟁' 1회 완료       |   +500   |   ✅    |
| 일일 퀘스트 1개 완료                       |   +200  |   삭제됨  |
| 사진 1회 촬영                              |   +100   |   삭제됨  |
| '고치(금)' 1회 완료               |   +100  |   삭제됨  |
| '고치(적)' 1회 완료               |   +100  |   삭제됨  |
| '응결 허영' 1회 완료                    |   +100  |   삭제됨  |
| '침식된 터널' 1회 완료                    |   +100  |   삭제됨  |
| '전쟁의 여운' 1회 완료                    |   +200  |   삭제됨  |
| '망각의 정원' 1회 완료                    |   +200  |   삭제됨  |
| '시뮬레이션 우주'(임의 세계) 1개 구역 클리어   |   +200  |   삭제됨  |
| '시뮬레이션 우주' 1회 완료                    |   +500  |   삭제됨  |
| 약점 격파 효과 5회 누적 발동                |   +100  |   삭제됨  |
| 한 전투에서 3가지 속성 약점 격파 발동   |   +100  |   삭제됨  |
| 비술 2회 누적 사용                       |   +100  |   삭제됨  |
| 약점 이용 전투 진입 후 3회 승리              |   +100  |   삭제됨  |
| 파괴 가능 물체 3개 누적 파괴                   |   +200  |   삭제됨  |
| 필살기로 결정타 1회 가하기              |   +200  |   삭제됨  |
| 임의 캐릭터 레벨 1회 상승                  |   +100  |   삭제됨  |
| 임의 광추 레벨 1회 상승                  |   +100  |   삭제됨  |
| 임의 유물 1개 분해                       |   +100  |   삭제됨  |
| 소모품 1회 합성                         |   +100  |   삭제됨  |
| 재료 1회 합성                          |   +100  |   삭제됨  |
| 소모품 1개 사용                         |   +100  |   삭제됨  |
        """
        elif hasattr(cfg, 'ui_language_now') and cfg.ui_language_now == "en_US":
            self.content = """
| Task Description                      | Activity | Support  |
| ------------------------------------- | -------- | -------- |
| Log in to game                        |   +100   |   ✅     |
| Dispatch 1 assignment                 |   +100   |   ✅     |
| Consume 120 Trailblaze Power          |   +200   |   ✅     |
| Defeat 20 enemies                     |   +100   |   ✅     |
| Win 1 battle with support character   |   +200   |   ✅     |
| Use Omni-Synthesizer 1 time           |   +100   |   ✅    |
| Level up any Relic 1 time             |   +100   |   ❌    |
| Complete Divergent Universe or Currency Wars |   +500   |   ✅    |
| Complete 1 Daily Quest                |   +200  |   Removed  |
| Take 1 Photo                          |   +100   |   Removed  |
| Complete Calyx (Golden) 1 time        |   +100  |   Removed  |
| Complete Calyx (Crimson) 1 time       |   +100  |   Removed  |
| Complete Stagnant Shadow 1 time       |   +100  |   Removed  |
| Complete Cavern of Corrosion 1 time   |   +100  |   Removed  |
| Complete Echo of War 1 time           |   +200  |   Removed  |
| Complete Forgotten Hall 1 time        |   +200  |   Removed  |
| Clear 1 area in Simulated Universe    |   +200  |   Removed  |
| Complete Simulated Universe 1 time    |   +500  |   Removed  |
| Trigger Weakness Break 5 times        |   +100  |   Removed  |
| Trigger 3 different Weakness Breaks   |   +100  |   Removed  |
| Use Technique 2 times                 |   +100  |   Removed  |
| Enter battle with Weakness & win 3 times |   +100  |   Removed  |
| Destroy 3 destructible objects        |   +200  |   Removed  |
| Deal finishing blow with Ultimate 1 time |   +200  |   Removed  |
| Level up any Character 1 time         |   +100  |   Removed  |
| Level up any Light Cone 1 time        |   +100  |   Removed  |
| Salvage any Relic 1 time              |   +100  |   Removed  |
| Synthesize Consumable 1 time          |   +100  |   Removed  |
| Synthesize Material 1 time            |   +100  |   Removed  |
| Use Consumable 1 time                 |   +100  |   Removed  |
        """
        else:
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
        # Load Changelog based on language setting
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
        self.vBoxLayout.addWidget(self.stackedWidget, 0, Qt.AlignmentFlag.AlignTop)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)

        # self.vBoxLayout.addWidget(self.tutorialLabel, 0, Qt.AlignTop)
        self.addSubInterface(self.tutorialLabel, 'tutorialLabel', tr('使用教程'))
        self.addSubInterface(self.faqLabel, 'faqLabel', tr('常见问题'))
        self.addSubInterface(self.tasksLabel, 'tasksLabel', tr('每日实训'))
        self.addSubInterface(self.changelogLabel, 'changelogLabel', tr('更新日志'))

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
            self.tutorialLabel.setText(self.tutorial_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.tutorialLabel.setText(self.tutorial_content)

        if qconfig.theme.name == "DARK":
            self.tasksLabel.setText(self.tasks_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.tasksLabel.setText(self.tasks_content)
