# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFileDialog, QScroller, QScrollerProperties
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import qconfig, ScrollArea, PrimaryPushButton, InfoBar, InfoBarPosition, PushButton, MessageBox
from .common.style_sheet import StyleSheet
from .tools.warp_export import warpExport, WarpExport, detect_format, uigf_to_srgf_hkrpg, srgf_to_uigf_hkrpg
import pyperclip
import json
import markdown
import os
import pandas as pd
import openpyxl
from openpyxl.styles import Font
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
import time


class WarpInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.titleLabel = QLabel("抽卡记录", self)

        self.updateBtn = PrimaryPushButton(FIF.SYNC, "更新数据", self)
        self.updateFullBtn = PushButton(FIF.SYNC, "更新完整数据", self)
        self.importBtn = PushButton(FIF.PENCIL_INK, "导入数据", self)
        self.exportBtn = PushButton(FIF.SAVE_COPY, "导出数据", self)
        self.exportExcelBtn = PushButton(FIF.SAVE_COPY, "导出Excel", self)
        self.copyLinkBtn = PushButton(FIF.SHARE, "复制链接", self)
        self.clearBtn = PushButton(FIF.DELETE, "清空", self)
        self.warplink = None

        self.stateTooltip = None

        self.contentLabel = QLabel(parent)

        qconfig.themeChanged.connect(self.setContent)

        self.setContent()

        self.__initWidget()
        self.__connectSignalToSlot()

    def __initWidget(self):
        self.titleLabel.move(36, 30)
        self.updateBtn.move(35, 80)
        self.updateFullBtn.move(150, 80)
        self.importBtn.move(293, 80)
        self.exportBtn.move(408, 80)
        self.exportExcelBtn.move(523, 80)
        self.copyLinkBtn.move(638, 80)
        self.copyLinkBtn.setEnabled(False)
        self.clearBtn.move(753, 80)

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

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __connectSignalToSlot(self):
        self.updateBtn.clicked.connect(self.__onUpdateBtnClicked)
        self.updateFullBtn.clicked.connect(self.__onUpdateFullBtnClicked)
        self.importBtn.clicked.connect(self.__onImportBtnClicked)
        self.exportBtn.clicked.connect(self.__onExportBtnClicked)
        self.exportExcelBtn.clicked.connect(self.__onExportExcelBtnClicked)
        self.copyLinkBtn.clicked.connect(self.__onCopyLinkBtnClicked)
        self.clearBtn.clicked.connect(self.__onClearBtnClicked)

    def __onUpdateBtnClicked(self):
        warpExport(self)

    def __onUpdateFullBtnClicked(self):
        warpExport(self, "full")

    def __onImportBtnClicked(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "导入抽卡记录", "", "UIGF / SRGF 格式 (*.json)")
            if not path:
                return

            with open(path, 'r', encoding='utf-8') as file:
                config = json.load(file)
                fmt = detect_format(config)
                if fmt == "uigf":
                    config = uigf_to_srgf_hkrpg(config)
                elif fmt == "neither":
                    raise ValueError("Invalid format")
            warp = WarpExport(config)
            warp.info['export_timestamp'] = int(time.time())
            warp.info['export_app'] = "March7thAssistant"
            try:
                with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                    version = file.read()
            except Exception:
                version = ""
            warp.info['export_app_version'] = version
            config = warp.export_data()
            with open("./warp.json", 'w', encoding='utf-8') as file:
                json.dump(config, file, ensure_ascii=False, indent=4)

            self.setContent()

            InfoBar.success(
                title='导入成功(＾∀＾●)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        except Exception:
            InfoBar.warning(
                title='导入失败(╥╯﹏╰╥)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __onExportBtnClicked(self):
        try:
            with open("./warp.json", 'r', encoding='utf-8') as file:
                config = json.load(file)
            warp = WarpExport(config)
            default_name = f"UIGF_{warp.get_uid()}"

            path, _ = QFileDialog.getSaveFileName(
                self,
                "导出抽卡记录",
                f"{default_name}",
                "UIGF 格式 (*.json);;SRGF 格式 (*.srgf.json)"
            )
            if not path:
                return

            is_srgf = path.lower().endswith(".srgf.json")

            if is_srgf:
                data_to_save = config
            else:
                # SRGF → UIGF
                data_to_save = srgf_to_uigf_hkrpg(config)

            with open(path, 'w', encoding='utf-8') as file:
                json.dump(data_to_save, file, ensure_ascii=False, indent=4)

            os.startfile(os.path.dirname(path))

            InfoBar.success(
                title='导出成功(＾∀＾●)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

        except Exception:
            InfoBar.warning(
                title='导出失败(╥╯﹏╰╥)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __onExportExcelBtnClicked(self):
        try:
            with open("./warp.json", 'r', encoding='utf-8') as file:
                config = json.load(file)
            records = config.get("list", [])
            df = pd.DataFrame(records)
            df = df[["time", "name", "item_type", "rank_type", "gacha_type"]]
            gacha_map = {
                "11": "角色活动跃迁",
                "12": "光锥活动跃迁",
                "21": "角色联动跃迁",
                "22": "光锥联动跃迁",
                "1": "常驻跃迁",
                "2": "新手跃迁",
            }
            df["gacha_type"] = df["gacha_type"].map(gacha_map).fillna("未知")
            df.rename(columns={
                "time": "时间",
                "name": "名称",
                "item_type": "类别",
                "rank_type": "星级",
                "gacha_type": "卡池",
            }, inplace=True)
            df["总次数"] = range(1, len(df) + 1)
            df["保底内"] = 0
            pity_counters = {}
            for idx, row in df.iterrows():
                pool = row["卡池"]
                star = row["星级"]
                if pool not in pity_counters:
                    pity_counters[pool] = 0
                pity_counters[pool] += 1
                df.at[idx, "保底内"] = pity_counters[pool]
                if star == "5":
                    pity_counters[pool] = 0
            path, _ = QFileDialog.getSaveFileName(
                self,
                "导出为 Excel 文件",
                f"抽卡记录_{config['info'].get('uid', '未知')}.xlsx",
                "Excel 文件 (*.xlsx)"
            )
            if not path:
                return

            df.to_excel(path, index=False)
            wb = load_workbook(path)
            ws = wb.active
            for row in range(2, ws.max_row + 1):
                star_cell = ws[f"D{row}"]
                try:
                    star = star_cell.value
                    if star == "5":
                        for col in ws[row]:
                            col.font = Font(color="FFA500")
                    elif star == "4":
                        for col in ws[row]:
                            col.font = Font(color="800080")
                except:
                    continue

            for column_cells in ws.columns:
                max_width = 0
                col_letter = get_column_letter(column_cells[0].column)
                for cell in column_cells:
                    try:
                        value = str(cell.value) if cell.value else ""
                        width = 0
                        for ch in value:
                            if u'\u4e00' <= ch <= u'\u9fff':
                                width += 2
                            else:
                                width += 1
                        if width > max_width:
                            max_width = width
                    except:
                        pass
                ws.column_dimensions[col_letter].width = max_width + 2

            wb.save(path)
            os.startfile(os.path.dirname(path))

            InfoBar.success(
                title='导出成功(＾∀＾●)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

        except Exception:
            InfoBar.warning(
                title='导出失败(╥╯﹏╰╥)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __onCopyLinkBtnClicked(self):
        try:
            pyperclip.copy(self.warplink)
            InfoBar.success(
                title='复制成功(＾∀＾●)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        except Exception:
            InfoBar.warning(
                title='复制失败(╥╯﹏╰╥)',
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __onClearBtnClicked(self):
        message_box = MessageBox(
            "清空抽卡记录",
            "确定要清空抽卡记录吗？此操作不可撤销。",
            self.window()
        )
        message_box.yesButton.setText('确认')
        message_box.cancelButton.setText('取消')
        if message_box.exec():
            try:
                os.remove("./warp.json")
                self.setContent()
                InfoBar.success(
                    title='清空完成(＾∀＾●)',
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
            except Exception as e:
                print(e)
                InfoBar.warning(
                    title='清空失败(╥╯﹏╰╥)',
                    content="",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )

    def setContent(self):
        try:
            with open("./warp.json", 'r', encoding='utf-8') as file:
                config = json.load(file)

            warp = WarpExport(config)
            if qconfig.theme.name == "DARK":
                content = warp.data_to_html("dark")
            else:
                content = warp.data_to_html("light")
            self.clearBtn.setEnabled(True)
            self.exportBtn.setEnabled(True)
            self.exportExcelBtn.setEnabled(True)
        except Exception as e:
            content = "抽卡记录为空，请先打开游戏内抽卡记录，再点击更新数据即可。\n\n你也可以从其他支持 UIGF/SRGF 数据格式的应用导入数据，例如 StarRail Warp Export 或 Starward 等。\n\n复制链接功能可用于小程序或其他软件。"
            self.clearBtn.setEnabled(False)
            self.exportBtn.setEnabled(False)
            self.exportExcelBtn.setEnabled(False)
        self.contentLabel.setText(content)
