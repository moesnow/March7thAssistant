# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

from qfluentwidgets import ScrollArea, qconfig, darkdetect, isDarkTheme
from .common.style_sheet import StyleSheet

import markdown


class TasksInterface(ScrollArea):
    """ Home interface """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.titleLabel = QLabel(self.tr("每日实训"), self)
        self.contentLabel = QLabel("html_content", parent)
        qconfig.themeChanged.connect(self.__themeChanged)
        html_style = """
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
| 任务描述                             | 支持情况 | 完成方式  |
| ----------------------------------- | -------- | -------- |
| 完成1个日常任务                      |   ❌     |          |
| 完成1次「拟造花萼（金）」             |   ✅      |          |
| 完成1次「拟造花萼（赤）」             |   ✅      |          |
| 完成1次「凝滞虚影」                  |   ✅      |          |
| 完成1次「侵蚀隧洞」                  |   ✅      |          |
| 单场战斗中，触发3种不同属性的弱点击破  |   ✅      |  回忆一   |
| 累计触发弱点击破效果5次               |   ✅      |  回忆一   |
| 累计消灭20个敌人                     |   ✅      |  回忆一   |
| 利用弱点进入战斗并获胜3次             |   ✅      |  回忆一   |
| 累计施放2次秘技                      |   ✅      | 姬子试用 |
| 派遣1次委托                         |   ✅      |          |
| 拍照1次                             |   ✅      |          |
| 累计击碎3个可破坏物                  |   ✅      | 姬子试用 |
| 完成1次「忘却之庭」                  |   ✅      |  回忆一   |
| 完成1次「历战余响」                  |   ✅     |          |
| 通关「模拟宇宙」（任意世界）的1个区域 |   ✅     |           |
| 使用支援角色并获得战斗胜利1次         |   ✅      |  清体力   |
| 施放终结技造成制胜一击1次            |   ✅      |  回忆一   |
| 将任意角色等级提升1次                |   ❌     |          |
| 将任意光锥等级提升1次                |   ❌     |          |
| 将任意遗器等级提升1次                |   ❌     |          |
| 分解任意1件遗器                     |   ❌      |          |
| 合成1次消耗品                       |   ✅      |          |
| 合成1次材料                         |   ✅      |          |
| 使用1件消耗品                       |   ✅      |          |
        """
        self.html_content = html_style + markdown.markdown(self.content, extensions=['tables'])

        if qconfig.theme.name == "DARK":
            self.contentLabel.setText(self.html_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.contentLabel.setText(self.html_content)

        self.__initWidget()

    def __themeChanged(self):
        if qconfig.theme.name == "DARK":
            self.contentLabel.setText(self.html_content.replace("border: 1px solid black;", "border: 1px solid white;"))
        else:
            self.contentLabel.setText(self.html_content)

    def __initWidget(self):
        self.view.setObjectName('view')
        self.setObjectName('tasksInterface')
        self.contentLabel.setObjectName('contentLabel')
        self.titleLabel.setObjectName('tasksLabel')
        StyleSheet.TASKS_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)

        self.vBoxLayout.setContentsMargins(36, 18, 36, 0)
        self.vBoxLayout.setSpacing(18)
        self.vBoxLayout.setAlignment(Qt.AlignTop)
        self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignTop)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)
