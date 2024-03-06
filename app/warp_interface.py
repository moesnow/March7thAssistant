# coding:utf-8
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QFileDialog
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import qconfig, ScrollArea, PrimaryPushButton, InfoBar, InfoBarPosition, PushButton
from .common.style_sheet import StyleSheet
from .tools.warp_export import warpExport, WarpExport
import pyperclip
import json
import markdown
import os


class WarpInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.titleLabel = QLabel(self.tr("抽卡记录"), self)

        self.updateBtn = PrimaryPushButton(FIF.SYNC, "更新数据", self)
        self.importBtn = PushButton(FIF.PENCIL_INK, "导入数据", self)
        self.exportBtn = PushButton(FIF.SAVE_COPY, "导出数据", self)
        self.copyLinkBtn = PushButton(FIF.SHARE, "复制链接", self)
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
        self.importBtn.move(150, 80)
        self.exportBtn.move(265, 80)
        self.copyLinkBtn.move(380, 80)
        self.copyLinkBtn.setEnabled(False)

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
        self.importBtn.clicked.connect(self.__onImportBtnClicked)
        self.exportBtn.clicked.connect(self.__onExportBtnClicked)
        self.copyLinkBtn.clicked.connect(self.__onCopyLinkBtnClicked)

    def __onUpdateBtnClicked(self):
        warpExport(self)

    def __onImportBtnClicked(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "支持 SRGF 数据格式导入", "", "星穹铁道抽卡记录文件 (*.json)")
            if not path:
                return

            with open(path, 'r', encoding='utf-8') as file:
                config = json.load(file)
            warp = WarpExport(config)
            config = warp.export_data()
            with open("./warp.json", 'w', encoding='utf-8') as file:
                json.dump(config, file, ensure_ascii=False, indent=4)

            self.setContent()

            InfoBar.success(
                title=self.tr('导入成功(＾∀＾●)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        except Exception:
            InfoBar.warning(
                title=self.tr('导入失败(╥╯﹏╰╥)'),
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
            path, _ = QFileDialog.getSaveFileName(self, "支持 SRGF 数据格式导出", f"SRGF_{warp.get_uid()}.json", "星穹铁道抽卡记录文件 (*.json)")
            if not path:
                return

            with open(path, 'w', encoding='utf-8') as file:
                json.dump(config, file, ensure_ascii=False, indent=4)

            os.startfile(os.path.dirname(path))

            InfoBar.success(
                title=self.tr('导出成功(＾∀＾●)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

        except Exception:
            InfoBar.warning(
                title=self.tr('导出失败(╥╯﹏╰╥)'),
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
                title=self.tr('复制成功(＾∀＾●)'),
                content="",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        except Exception:
            InfoBar.warning(
                title=self.tr('复制失败(╥╯﹏╰╥)'),
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
        except Exception as e:
            content = "抽卡记录为空，请先打开游戏内抽卡记录，再点击更新数据即可。\n\n你也可以从其他支持 SRGF 数据格式的应用导入数据，例如 StarRail Warp Export 或 Starward 等。\n\n复制链接功能可用于小程序或其他软件。"
        self.contentLabel.setText(content)
