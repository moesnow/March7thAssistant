# coding:utf-8
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel

from qfluentwidgets import ScrollArea, PrimaryPushButton, StateToolTip
from .common.style_sheet import StyleSheet
from .tools.warp_export import warpExport

from datetime import datetime
import json
import markdown
import random
import sys


class WarpInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.titleLabel = QLabel(self.tr("抽卡记录"), self)

        self.updateBtn = PrimaryPushButton("更新数据", self)
        self.stateTooltip = None

        self.content = ""
        self.contentLabel = QLabel(parent)

        try:
            path = "./warp1.json"
            with open(path, 'r', encoding='utf-8') as file:
                config = json.load(file)
            self.__warpToHtml(config)
        except:
            self.content = "### 抽卡记录为空"

        self.contentLabel.setText(markdown.markdown(self.content))

        self.__initWidget()
        self.__connectSignalToSlot()

    def __warpToHtml(self, data):
        self.content = ""
        info = data.get("info")
        list = data.get("list")

        uid = info.get("uid")
        export_time = datetime.fromtimestamp(info['export_timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        map = {
            "11": "角色活动跃迁",
            "12": "光锥活动跃迁",
            "1": "常驻跃迁",
            "2": "新手跃迁",
        }

        gacha_data = {
            "11": ["角色活动跃迁", []],
            "12": ["光锥活动跃迁", []],
            "1": ["常驻跃迁", []],
            "2": ["新手跃迁", []],
        }
        for item in list:
            type = item["gacha_type"]
            gacha_data[type][1].append(item)

        def warp_analyze(value):
            start_time = datetime.strptime(value[0]["time"], "%Y-%m-%d %H:%M:%S").strftime('%Y-%m-%d')
            end_time = datetime.strptime(value[-1]["time"], "%Y-%m-%d %H:%M:%S").strftime('%Y-%m-%d')
            self.content += f"{start_time} - {end_time}\n\n"
            sum = len(value)
            rank_type = {
                "5": 0,
                "4": 0,
                "3": 0
            }
            rank_5 = []
            count = 0
            for item in value:
                count += 1
                type = item["rank_type"]
                name = item["name"]
                rank_type[type] = rank_type.get(type, 0) + 1
                if type == "5":
                    rank_5.append([name, count])
                    count = 0

            self.content += f"一共 <font color=blue>{sum}</font> 抽 已累计 <font color=green>{count}</font> 抽未出5星\n\n"
            # for key, value in rank_type.items():
            #     self.content += f"{key}星: {value:<4d} [{value/sum*100:.2f}%]\n\n"
            self.content += f"<font color=Orange>5星: {rank_type['5']:<4d} [{rank_type['5']/sum*100:.2f}%]</font>\n\n"
            self.content += f"<font color=DarkOrchid>4星: {rank_type['4']:<4d} [{rank_type['4']/sum*100:.2f}%]</font>\n\n"
            self.content += f"<font color=blue>3星: {rank_type['3']:<4d} [{rank_type['3']/sum*100:.2f}%]</font>\n\n"
            rank_5_str = ""
            rank_5_avg = ""
            rank_5_sum = 0
            colors = ['Red', 'Orange', 'Khaki', 'Green', 'DarkTurquoise', 'DodgerBlue', 'Magenta', 'Crimson', 'Coral', 'Gold', 'PaleGreen', 'DeepSkyBlue', 'RoyalBlue', 'DarkOrchid']
            previous_color = None
            for key, value in rank_5:
                current_color = random.choice([color for color in colors if color != previous_color])
                rank_5_str += f"<font color={current_color}>{key}[{value}]</font> "
                rank_5_sum += value
            rank_5_avg = rank_5_sum / len(rank_5)
            self.content += f"5星历史记录: {rank_5_str}\n\n"
            self.content += f"五星平均出货次数为: <font color=green>{rank_5_avg:.2f}</font>\n\n<hr>"

        for key, value in gacha_data.items():
            self.content += f"## <font color=#f18cb9>{value[0]}</font>\n\n"
            warp_analyze(value[1])

    def __initWidget(self):
        self.titleLabel.move(36, 30)
        self.updateBtn.move(40, 80)
        self.view.setObjectName('view')
        self.setViewportMargins(0, 120, 0, 20)
        self.setObjectName('warpInterface')
        self.contentLabel.setObjectName('contentLabel')
        self.titleLabel.setObjectName('warpLabel')
        StyleSheet.WARP_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setMaximumWidth(800)

        # self.vBoxLayout.setSpacing(8)
        # self.vBoxLayout.setAlignment(Qt.AlignTop)
        # self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignTop)

        # self.vBoxLayout.setSpacing(28)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignTop)

    def __connectSignalToSlot(self):
        self.updateBtn.clicked.connect(self.__onUpdateBtnClicked)

    def __onUpdateBtnClicked(self):
        warpExport(self)
