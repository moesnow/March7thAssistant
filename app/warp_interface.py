# coding:utf-8
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFileDialog, QScroller, QScrollerProperties
from qfluentwidgets import FluentIcon as FIF
from qfluentwidgets import qconfig, ScrollArea, InfoBar, InfoBarPosition, PushButton, MessageBox, ComboBox, PrimarySplitPushButton, RoundMenu, Action, FlowLayout
from .common.style_sheet import StyleSheet
from .common.icon import UiIcon
from .tools.warp_export import warpExport, WarpExport, srgf_to_uigf_hkrpg
from .tools.warp_import import prepare_import, save_import, read_snapshot, clear_plan, save_export
from .tools.warp_manual import manual_count, standard_data, backup_data
from .warp_manual_dialog import WarpManualDialog
from utils import clipboard
import json
import os
from module.localization import tr
import time
import sys
from pathlib import Path


class WarpInterface(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.view = QWidget(self)
        self.vBoxLayout = QVBoxLayout(self.view)
        self.titleLabel = QLabel(tr("抽卡记录"), self)

        self.updateBtn = PrimarySplitPushButton(FIF.SYNC, tr("更新数据"), self)
        self.updateFullBtn = Action(FIF.SYNC, tr("更新完整数据"), self)
        update_menu = RoundMenu(parent=self.updateBtn)
        update_menu.addAction(self.updateFullBtn)
        self.updateBtn.setFlyout(update_menu)
        self.manualBtn = PushButton(FIF.EDIT, tr('手动补充与更正'), self)
        self.manualDialog = None
        self.importBtn = PushButton(UiIcon.IMPORT, tr("导入数据"), self)
        self.exportBtn = PushButton(UiIcon.EXPORT, tr("导出数据"), self)
        self.exportExcelBtn = PushButton(UiIcon.EXPORT, tr("导出Excel"), self)
        self.copyLinkBtn = PushButton(UiIcon.LINK, tr("复制链接"), self)
        self.clearBtn = PushButton(FIF.DELETE, tr("清空"), self)
        if sys.platform != 'win32':
            self.updateBtn.setEnabled(False)
            self.updateFullBtn.setEnabled(False)
            self.copyLinkBtn.setEnabled(False)

        self.warplink = None

        self.stateTooltip = None

        self.contentLabel = QLabel(parent)

        qconfig.themeChanged.connect(self.setContent)

        self.setContent()

        self.__initWidget()
        self.__connectSignalToSlot()

    def retranslateUi(self):
        StyleSheet.WARP_INTERFACE.apply(self)
        self.titleLabel.setText(tr('抽卡记录'))
        self.titleLabel.adjustSize()
        self.updateBtn.setText(tr('更新数据'))
        self.updateFullBtn.setText(tr('更新完整数据'))
        self.manualBtn.setText(tr('手动补充与更正'))
        self.importBtn.setText(tr('导入数据'))
        self.exportBtn.setText(tr('导出数据'))
        self.exportExcelBtn.setText(tr('导出Excel'))
        self.copyLinkBtn.setText(tr('复制链接'))
        self.clearBtn.setText(tr('清空'))
        self._layout_toolbar()
        # 保留 warp_thread、链接与按钮的运行状态，只刷新统计内容。
        buttons = [self.updateBtn, self.updateFullBtn, self.manualBtn, self.importBtn,
                   self.exportBtn, self.exportExcelBtn, self.copyLinkBtn, self.clearBtn]
        states = [(button, button.isEnabled()) for button in buttons]
        self.setContent()
        for button, enabled in states:
            button.setEnabled(enabled)
        if self.manualDialog is not None:
            self.manualDialog.retranslateUi()

    def __initWidget(self):
        self.titleLabel.move(36, 30)
        
        # Create button container widget for horizontal layout
        self.buttonWidget = QWidget(self)
        self.buttonWidget.move(35, 80)
        self.buttonLayout = FlowLayout(self.buttonWidget)
        self.buttonLayout.setContentsMargins(0, 0, 0, 0)
        self.buttonLayout.setHorizontalSpacing(8)
        self.buttonLayout.setVerticalSpacing(8)
        
        # Add buttons to horizontal layout
        self.buttonLayout.addWidget(self.updateBtn)
        self.buttonLayout.addWidget(self.manualBtn)
        self.buttonLayout.addWidget(self.importBtn)
        self.buttonLayout.addWidget(self.exportBtn)
        self.buttonLayout.addWidget(self.exportExcelBtn)
        self.buttonLayout.addWidget(self.copyLinkBtn)
        self.buttonLayout.addWidget(self.clearBtn)
        self.buttonWidget.adjustSize()
        
        self.copyLinkBtn.setEnabled(False)

        self.view.setObjectName('view')
        self.setViewportMargins(0, 120, 0, 20)
        self.setObjectName('warpInterface')
        self.contentLabel.setObjectName('contentLabel')
        self.titleLabel.setObjectName('warpLabel')
        StyleSheet.WARP_INTERFACE.apply(self)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.contentLabel.setWordWrap(True)
        self.contentLabel.setMaximumWidth(800)

        # self.vBoxLayout.setSpacing(8)
        # self.vBoxLayout.setAlignment(Qt.AlignTop)
        # self.vBoxLayout.addWidget(self.titleLabel, 0, Qt.AlignTop)

        # self.vBoxLayout.setSpacing(28)
        self.vBoxLayout.setContentsMargins(36, 0, 36, 0)
        self.vBoxLayout.addWidget(self.contentLabel, 0, Qt.AlignmentFlag.AlignTop)

        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.LeftMouseButtonGesture)
        scroller = QScroller.scroller(self.viewport())
        scroller_props = scroller.scrollerProperties()
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootDragDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.OvershootScrollDistanceFactor, 0.05)
        scroller_props.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.5)
        scroller.setScrollerProperties(scroller_props)

    def __connectSignalToSlot(self):
        self.updateBtn.clicked.connect(self.__onUpdateBtnClicked)
        self.updateFullBtn.triggered.connect(self.__onUpdateFullBtnClicked)
        self.manualBtn.clicked.connect(self._open_manual)
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
            path, _ = QFileDialog.getOpenFileName(self, tr("导入抽卡记录"), "", tr("UIGF / SRGF / 小助手备份 (*.json)"))
            if not path:
                return

            # Preview validates the single account first. With no existing records,
            # there is nothing to merge or overwrite, so do not interrupt the import.
            plan = prepare_import(path, mode='replace')
            if plan.existing_count or plan.existing_manual_count or plan.existing_unreadable:
                mode_dialog = MessageBox(
                    tr('选择导入方式'),
                    tr('默认合并会保留现有记录。只有希望用文件内容覆盖现有记录时，才选择强制替换。'),
                    self.window()
                )
                mode_box = ComboBox(mode_dialog.widget)
                mode_box.addItems([tr('安全合并（推荐）'), tr('强制替换现有记录')])
                mode_dialog.textLayout.addWidget(mode_box)
                mode_dialog.widget.setFixedHeight(mode_dialog.widget.height() + mode_box.sizeHint().height() + 12)
                mode_dialog.yesButton.setText(tr('下一步'))
                mode_dialog.cancelButton.setText(tr('取消'))
                if not mode_dialog.exec():
                    return
                mode = 'replace' if mode_box.currentIndex() == 1 else 'merge'
                plan = prepare_import(path, mode=mode)
                if mode == 'merge':
                    message_box = MessageBox(
                        tr("确认导入抽卡记录"),
                        tr("账号 UID：{uid}\n导入方式：保留已有记录，补充新记录，自动跳过重复内容。\n\n现有记录：{existing} 条\n文件记录：{incoming} 条\n新增记录：{added} 条\n重复记录：{duplicates} 条\n合并后：{total} 条")
                        .format(uid=plan.data['info']['uid'], existing=plan.existing_count,
                                incoming=plan.incoming_count, added=plan.added_count,
                                duplicates=plan.duplicate_count, total=len(plan.data['list'])),
                        self.window()
                    )
                else:
                    message_box = MessageBox(
                        tr('警告：替换现有抽卡记录'),
                        tr('当前账号：{existing_uid}\n导入账号：{uid}\n导入方式：替换现有记录。\n\n现有记录数量：{existing}\n替换后记录数量：{total}\n\n此操作会用导入文件中的记录替换目前保存的全部记录。原有记录不会保留在当前列表中。\n\n确定要替换吗？')
                        .format(uid=plan.data['info']['uid'], existing_uid=plan.existing_uid or tr('无法读取'),
                                existing=tr('无法统计') if plan.existing_unreadable else plan.existing_count,
                                total=len(plan.data['list'])),
                        self.window()
                    )
                if plan.existing_manual_count:
                    note = (tr('替换也会移除当前手填内容和更正，只保留导入文件中的内容。') if mode == 'replace'
                            else tr('现有手填内容和更正会保留。请自行核对新明细，避免重复统计。'))
                    message_box.contentLabel.setText(message_box.contentLabel.text() + '\n\n' + note)
                if plan.existing_manual_count or plan.incoming_manual_count:
                    message_box.contentLabel.setText(message_box.contentLabel.text() + '\n\n' +
                        tr('手填和更正：现有 {existing} 项，文件 {incoming} 项，导入后 {total} 项。').format(
                            existing=plan.existing_manual_count, incoming=plan.incoming_manual_count,
                            total=manual_count(plan.data)))
                    message_box.widget.adjustSize()
                message_box.yesButton.setText(tr('确认替换') if mode == 'replace' else tr('确认合并'))
                message_box.cancelButton.setText(tr('取消'))
                if mode == 'replace':
                    message_box.cancelButton.setFocus()
                if not message_box.exec():
                    return
            plan.data['info']['export_timestamp'] = int(time.time())
            plan.data['info']['export_app'] = "March7thAssistant"
            try:
                with open("./assets/config/version.txt", 'r', encoding='utf-8') as file:
                    plan.data['info']['export_app_version'] = file.read().strip()
            except OSError:
                plan.data['info']['export_app_version'] = ""
            save_import(plan)
        except Exception as exc:
            message_box = MessageBox(tr('导入失败'), str(exc), self.window())
            message_box.cancelButton.hide()
            message_box.yesButton.setText(tr('确定'))
            message_box.exec()
            return

        self.setContent()
        InfoBar.success(
            title=tr('导入成功(＾∀＾●)'),
            content="",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=5000,
            parent=self
        )

    def __onExportBtnClicked(self):
        try:
            with open("./warp.json", 'r', encoding='utf-8') as file:
                config = json.load(file)
            warp = WarpExport(config)
            default_name = f"UIGF_{warp.get_uid()}"

            if manual_count(config):
                warning = MessageBox(tr('导出抽卡记录'), tr('UIGF/SRGF 只能保存真实逐抽明细，不能保存手填摘要和更正。需要完整恢复时，请在保存窗口选择“小助手完整备份”。'), self.window())
                warning.yesButton.setText(tr('继续'))
                warning.cancelButton.setText(tr('取消'))
                if not warning.exec():
                    return
                default_name = f"March7th_{warp.get_uid()}.m7backup.json"
                filters = tr('小助手完整备份 (*.m7backup.json);;UIGF 格式 (*.json);;SRGF 格式 (*.srgf.json)')
            else:
                default_name += '.json'
                filters = tr('UIGF 格式 (*.json);;SRGF 格式 (*.srgf.json);;小助手完整备份 (*.m7backup.json)')
            path, selected_filter = QFileDialog.getSaveFileName(
                self, tr('导出抽卡记录'), default_name, filters)
            if not path:
                return
            self._check_export_path(path)
            is_backup = '*.m7backup.json' in selected_filter if selected_filter else path.lower().endswith('.m7backup.json')
            is_srgf = '*.srgf.json' in selected_filter if selected_filter else path.lower().endswith('.srgf.json')
            if is_backup:
                data_to_save = backup_data(config)
            elif is_srgf:
                data_to_save = standard_data(config)
            else:
                data_to_save = srgf_to_uigf_hkrpg(standard_data(config))

            save_export(data_to_save, path)

            self._start_file(os.path.dirname(path))

            InfoBar.success(
                title=tr('导出成功(＾∀＾●)'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

        except Exception as exc:
            InfoBar.warning(
                title=tr('导出失败(╥╯﹏╰╥)'),
                content=str(exc),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __onExportExcelBtnClicked(self):
        try:
            with open("./warp.json", 'r', encoding='utf-8') as file:
                config = json.load(file)

            path, _ = QFileDialog.getSaveFileName(
                self,
                tr("导出为 Excel 文件"),
                f"{tr('抽卡记录')}_{config['info'].get('uid', tr('未知'))}.xlsx",
                tr("Excel 文件 (*.xlsx)")
            )
            if not path:
                return
            self._check_export_path(path)

            from .tools.warp_excel import export_excel
            export_excel(config, path)
            self._start_file(os.path.dirname(path))

            InfoBar.success(
                title=tr('导出成功(＾∀＾●)'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

        except Exception as exc:
            InfoBar.warning(
                title=tr('导出失败(╥╯﹏╰╥)'),
                content=str(exc),
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __onCopyLinkBtnClicked(self):
        try:
            clipboard.copy(self.warplink)
            InfoBar.success(
                title=tr('复制成功(＾∀＾●)'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )
        except Exception:
            InfoBar.warning(
                title=tr('复制失败(╥╯﹏╰╥)'),
                content="",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=1000,
                parent=self
            )

    def __onClearBtnClicked(self):
        try:
            original, data = read_snapshot()
        except Exception:
            return
        if data is None:
            return
        message_box = MessageBox(
            tr("清空抽卡记录"),
            tr('清空当前账号的全部明细、手填五星和抽数更正？如需以后恢复，请先导出“小助手完整备份”。清空不会删除已导出的文件。'),
            self.window()
        )
        message_box.yesButton.setText(tr('确认'))
        message_box.cancelButton.setText(tr('取消'))
        message_box.cancelButton.setFocus()
        if message_box.exec():
            try:
                save_import(clear_plan(data, original))
                self.setContent()
                InfoBar.success(
                    title=tr('清空完成(＾∀＾●)'),
                    content="",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )
            except Exception as e:
                print(e)
                InfoBar.warning(
                    title=tr('清空失败(╥╯﹏╰╥)'),
                    content=str(e),
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=1000,
                    parent=self
                )

    def _start_file(self, path):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve())))

    def _check_export_path(self, path):
        destination, current = Path(path).resolve(), Path('warp.json').resolve()
        if destination == current or (destination.exists() and current.exists() and destination.samefile(current)):
            raise ValueError(tr('请另选导出文件名，不要覆盖小助手正在使用的抽卡记录。'))

    def setContent(self):
        try:
            with open("./warp.json", 'r', encoding='utf-8') as file:
                config = json.load(file)

            if config.get('march7th_cleared') or (not config.get('list') and not manual_count(config)):
                raise ValueError('empty')
            warp = WarpExport(config)
            if qconfig.theme.name == "DARK":
                content = warp.data_to_html("dark")
            else:
                content = warp.data_to_html("light")
            self.clearBtn.setEnabled(True)
            self.exportBtn.setEnabled(True)
            self.exportExcelBtn.setEnabled(True)
        except Exception as e:
            content = tr("抽卡记录为空。可以打开游戏内抽卡记录后更新，或导入 UIGF/SRGF 文件。\n\n只记得以前的五星？点击“手动补充与更正”即可填写，不需要先导入记录。\n\n复制链接功能可用于小程序或其他软件。")
            self.clearBtn.setEnabled(False)
            self.exportBtn.setEnabled(False)
            self.exportExcelBtn.setEnabled(False)
        self.contentLabel.setText(content)

    def _open_manual(self):
        if self.manualDialog is not None:
            self.manualDialog.show()
            self.manualDialog.raise_()
            self.manualDialog.activateWindow()
            return
        try:
            dialog = WarpManualDialog(self.window())
        except Exception as exc:
            box = MessageBox(tr('无法读取抽卡记录'), str(exc), self.window())
            box.cancelButton.hide()
            box.exec()
            return
        self.manualDialog = dialog
        dialog.changed.connect(self.setContent)
        dialog.destroyed.connect(lambda: setattr(self, 'manualDialog', None))
        dialog.show()

    def _layout_toolbar(self):
        if not hasattr(self, 'buttonWidget'):
            return
        width = max(1, self.width() - 70)
        height = self.buttonLayout.heightForWidth(width)
        self.buttonWidget.setGeometry(35, 80, width, height)
        self.setViewportMargins(0, 90 + height, 0, 20)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_toolbar()
