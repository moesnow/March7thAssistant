"""兑换码：编辑、获取和执行。"""
import re
import sys

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox

from app.card.messagebox_custom import MessageBoxEditCode
from app.common.mascot import Mascot
from app.components.mascot_dialog import add_mascot
from module.config import cfg
from module.localization import tn, tr
from tasks.base.tasks import start_task
from .cards import ToolCard


class _FetchSignals(QObject):
    finished = Signal(list, str)


class FetchLatestCodesWorker(QRunnable):
    def __init__(self, server):
        super().__init__()
        self.server = server
        self.signals = _FetchSignals()

    def run(self):
        try:
            from tasks.daily.redemption import valid_codes_for_server
            codes = valid_codes_for_server(self.server)
        except Exception as exc:
            self.signals.finished.emit([], str(exc))
        else:
            self.signals.finished.emit(codes, "")


class RedemptionCodeCard(ToolCard):
    configname = "redemption_code"

    def __init__(self, icon, parent=None):
        super().__init__(icon, parent)
        self.page = parent
        self.clicked.connect(self._open)

    # ===================== 主入口 =====================

    def _open(self):
        codes = cfg.get_value(self.configname) or []
        self.message_box = MessageBoxEditCode(
            tr('兑换码'),
            '\n'.join(codes),
            self.window()
        )
        mb = self.message_box
        self._fetch_job = None
        mb.fetchButton.clicked.connect(self._fetch_latest)
        mb.viewUsedButton.clicked.connect(self._show_used)
        mb.clearUsedButton.clicked.connect(self._clear_used)
        try:
            if mb.exec():
                self._save_codes()
        finally:
            self._fetch_job = None
            self.message_box = None
            mb.deleteLater()

    def _fetch_latest(self):
        mb = self.message_box
        if self._fetch_job is not None:
            self._info_warning(tr('正在获取'), tr('请等待当前获取完成'), mb)
            return
        server = self._get_server()
        if not server:
            return
        self._fetch_job = FetchLatestCodesWorker(server)
        self._fetch_job.signals.finished.connect(self._on_fetch_finished)
        mb.fetchButton.setEnabled(False)
        QThreadPool.globalInstance().start(self._fetch_job)
        self._info_success(tr('开始获取'), tr('正在获取最新兑换码...'), mb)

    @Slot(list, str)
    def _on_fetch_finished(self, codes, err):
        # 旧弹窗关闭后，迟到的结果不能覆盖新弹窗中正在编辑的内容。
        if self._fetch_job is None or self.sender() is not self._fetch_job.signals:
            return
        self._fetch_job = None
        mb = self.message_box
        mb.fetchButton.setEnabled(True)
        used = cfg.get_value("already_used_codes") or []
        codes = [code for code in codes if code not in used]
        if err:
            self._info_warning(tr('获取最新兑换码失败'), err, mb)
        elif not codes:
            self._info_warning(tr('未获取到兑换码'), '', mb)
        else:
            mb.textEdit.setText('\n'.join(codes))
            self._info_success(
                tr('获取成功'),
                tn('已获取 {count} 个兑换码', len(codes)),
                mb
            )

    # ===================== 已使用兑换码 =====================

    def _show_used(self):
        used = cfg.get_value('already_used_codes') or []
        if not used:
            self._info_warning(tr('暂无已使用兑换码'), '', self.message_box)
            return

        mb = MessageBoxEditCode(
            tr('已使用兑换码'),
            '\n'.join(used),
            self.window()
        )
        mb.yesButton.setText(tr('关闭'))
        mb.cancelButton.hide()
        mb.fetchButton.hide()
        mb.viewUsedButton.hide()
        mb.clearUsedButton.hide()
        mb.textEdit.setReadOnly(True)
        mb.exec()
        mb.deleteLater()

    def _clear_used(self):
        confirm = MessageBox(
            tr('确认清空已使用兑换码'),
            tr('此操作不可撤销，是否继续？'),
            self.window()
        )
        confirm.yesButton.setText(tr('确认'))
        confirm.cancelButton.setText(tr('取消'))
        add_mascot(confirm, Mascot.BOX)

        if confirm.exec():
            cfg.set_value('already_used_codes', [])
            self._info_success('', tr('已清空已使用兑换码'), self.message_box)
        confirm.deleteLater()

    # ===================== 保存兑换码 =====================

    def _save_codes(self):
        text = self.message_box.getText()
        code = [
            line.strip()
            for line in (
                ''.join(re.findall(r'[A-Za-z0-9\u4e00-\u9fff]', l))
                for l in text.splitlines()
            )
            if line.strip()
        ]

        cfg.set_value(self.configname, code)

        if code:
            start_task("redemption")
        else:
            self._info_warning(tr('兑换码为空'), '', self.page)

    # ===================== 工具方法 =====================

    def _get_server(self):
        try:
            # 如果云游戏启用，默认使用国服
            if cfg.cloud_game_enable:
                return 'cn'
            if sys.platform == 'win32':
                from utils.registry.star_rail_setting import get_server_by_registry
                server = get_server_by_registry()
                if not server:
                    self._info_warning(
                        tr('无法判断服务器类型'),
                        tr('无法获取最新兑换码'),
                        self.message_box
                    )
            else:
                server = 'cn'  # 云游戏默认国服
            return server
        except Exception as e:
            self._info_warning(tr('获取服务器信息失败'), str(e), self.message_box)
            return None

    def _info_warning(self, title, content, parent):
        """title / content 由调用方负责翻译（这里只负责弹 InfoBar）。"""
        InfoBar.warning(
            title,
            content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1500,
            parent=parent
        )

    def _info_success(self, title, content, parent):
        """title / content 由调用方负责翻译（这里只负责弹 InfoBar）。"""
        InfoBar.success(
            title,
            content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=1500,
            parent=parent
        )
