"""帮助：原生文档阅读器。

左侧是文档列表、本页目录和「没找到答案？」卡片，右侧是排好版的正文。文档由 module.docs 解析成块，
这里只负责排版、跳转、搜索和阅读位置；切换主题只重建样式，不重新解析文档。
"""
from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ScrollArea, SearchLineEdit, TitleLabel, qconfig

from app.content.help_state import ChangelogBadge, open_link
from app.help.page import DocPage
from app.help.search import HelpSearchPage
from app.help.side import DocList, SidePanel, SupportCard, TocView
from app.pages.common import secondary
from module.docs.catalog import DOCUMENTS, SIDEBAR, source_for
from module.docs.model import Link, SettingPath
from module.docs.reader import load_document, resolve_anchor
from module.docs.search import HelpResults, search_help
from module.localization import tr
from module.logger import log

DEFAULT_DOCUMENT = "Tutorial"
HISTORY_LIMIT = 20


class HelpInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("helpInterface")
        self.window_ = parent
        self.pages = {}
        self.current = None
        self._history = []
        self.badge = ChangelogBadge(self)

        self.sidePanel = SidePanel(self)
        self.sidePanel.setFixedWidth(228)
        self.titleLabel = TitleLabel(tr("帮助"), self.sidePanel)
        self.searchBox = SearchLineEdit(self.sidePanel)
        self.searchBox.setPlaceholderText(tr("搜索帮助文档"))
        self.docList = DocList(SIDEBAR, self.sidePanel)
        self.tocLabel = secondary(CaptionLabel(tr("本页目录"), self.sidePanel))
        self.toc = TocView()
        self.tocScroll = ScrollArea(self.sidePanel)
        self.tocScroll.setWidget(self.toc)
        self.tocScroll.setWidgetResizable(True)
        self.tocScroll.enableTransparentBackground()
        self.tocScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tocScroll.setMinimumHeight(52)
        self.toc.setStyleSheet("background: transparent")
        self.supportCard = SupportCard(self.sidePanel)
        side = QVBoxLayout(self.sidePanel)
        side.setContentsMargins(16, 14, 10, 12)
        side.setSpacing(0)
        side.addWidget(self.titleLabel)
        side.addSpacing(10)
        side.addWidget(self.searchBox)
        side.addSpacing(10)
        side.addWidget(self.docList)
        side.addSpacing(14)
        side.addWidget(self.tocLabel)
        side.addSpacing(4)
        side.addWidget(self.tocScroll, 1)
        side.addSpacing(10)
        side.addWidget(self.supportCard)

        self.stack = QStackedWidget(self)
        self.searchPage = HelpSearchPage(self)
        self.stack.addWidget(self.searchPage)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidePanel)
        layout.addWidget(self.stack, 1)

        self._searchTimer = QTimer(self)
        self._searchTimer.setSingleShot(True)
        self._searchTimer.setInterval(180)
        self._searchTimer.timeout.connect(self._search)
        self.searchBox.textChanged.connect(self._scheduleSearch)
        self.searchBox.searchSignal.connect(self._searchNow)
        self.searchBox.returnPressed.connect(self._openFirstHit)
        self.docList.currentChanged.connect(self._listSelected)
        self.toc.entryClicked.connect(self._tocClicked)
        self.toc.currentMoved.connect(self._ensureTocVisible)
        self.supportCard.faqClicked.connect(lambda: self.showDocument("FAQ", remember=True))
        self.supportCard.qqClicked.connect(self._openQQ)
        self.supportCard.logsClicked.connect(self._openLogs)
        self.searchPage.hitClicked.connect(self.openHit)
        self.searchPage.suggestionClicked.connect(self.searchBox.setText)
        self.badge.changed.connect(self._refreshBadge)
        qconfig.themeChanged.connect(self._restyle)
        qconfig.themeColorChanged.connect(self._restyle)
        self._refreshBadge()

    # 打开文档 -----------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if self.current is None:
            # 跳转链接会紧接着打开别的文档，稍后再决定是否打开默认的使用教程。
            QTimer.singleShot(0, self, self._showDefault)

    def _showDefault(self):
        if self.current is None:
            self.showDocument(DEFAULT_DOCUMENT, flash=False)

    @staticmethod
    def _canonical(doc_id):
        text = str(doc_id or "").strip()
        return next((name for name in DOCUMENTS if name.casefold() == text.casefold()), None)

    def _page(self, doc_id):
        page = self.pages.get(doc_id)
        if page is None:
            try:
                page = DocPage(self, load_document(doc_id))
            except Exception as exc:
                log.warning(f"帮助文档无法打开：{doc_id}，{type(exc).__name__}: {exc}")
                return None
            page.anchorChanged.connect(self.toc.setCurrent)
            self.pages[doc_id] = page
            self.stack.addWidget(page)
        elif page.dirty:
            page.restyle()
        return page

    def currentPage(self):
        return self.pages.get(self.current)

    def showDocument(self, doc_id, anchor="", *, flash=True, remember=False, keep_position=False):
        doc_id = self._canonical(doc_id)
        if doc_id is None:
            return False
        previous = self.currentPage()
        if remember and previous is not None:
            self._history.append((previous.doc.id, previous.doc.language, previous.captureState()))
            del self._history[:-HISTORY_LIMIT]
        page = self._page(doc_id)
        if page is None:
            return False
        self._leaveSearch()
        self.stack.setCurrentWidget(page)
        self.current = doc_id
        self.docList.setCurrent(doc_id)
        self.toc.setEntries(page.tocEntries())
        self.tocLabel.setVisible(bool(page.tocEntries()))
        page.meta.backButton.setVisible(bool(self._history))
        target = ""
        if anchor:
            try:
                target = resolve_anchor(source_for(page.doc.id, page.doc.language), anchor)
            except Exception as exc:
                log.warning(f"帮助文档的位置无法识别：{doc_id}#{anchor}，{exc}")
        if not (target and page.scrollToAnchor(target, flash=flash)) and not keep_position:
            page.scrollToTop()
        self.toc.setCurrent(page.currentAnchor())
        if doc_id == "Changelog":
            self.badge.mark_seen()
        return True

    def _listSelected(self, doc_id):
        self._history.clear()
        if not self.showDocument(doc_id, keep_position=True):
            self.docList.setCurrent(self.current)

    def _tocClicked(self, anchor):
        page = self.currentPage()
        if page is not None and self.stack.currentWidget() is page:
            page.scrollToAnchor(anchor, flash=False, smooth=True)
            self.toc.setCurrent(anchor)

    def _ensureTocVisible(self, y, height):
        self.tocScroll.ensureVisible(0, y + height // 2, 0, height)

    def goBack(self):
        if not self._history:
            return
        doc_id, language, state = self._history.pop()
        if self.showDocument(doc_id, flash=False, keep_position=True):
            self.currentPage().restoreState(state, language)

    # 链接 ---------------------------------------------------------------

    def _window(self):
        return self.window_ if self.window_ is not None else self.window()

    def activate(self, target):
        from app.navigation import navigate
        from module.navigation import parse_link
        try:
            if isinstance(target, SettingPath):
                navigate(self._window(), target.target)
            elif isinstance(target, Link) and target.kind == "doc":
                route = parse_link(target.target)
                if route is not None:
                    self.showDocument(route[1], route[2], remember=True)
            elif isinstance(target, Link) and target.kind == "file":
                QDesktopServices.openUrl(QUrl.fromLocalFile(target.target))
            elif isinstance(target, Link):
                open_link(self._window(), target)
        except Exception as exc:
            log.warning(f"帮助文档的链接无法打开：{target}，{exc}")

    def _openQQ(self):
        from module.docs.support import QQ_GROUP_URL
        QDesktopServices.openUrl(QUrl(QQ_GROUP_URL))

    def _openLogs(self):
        try:
            from module.docs.support import support_actions
            folder = support_actions().log_folder
        except Exception as exc:
            log.warning(f"找不到日志文件夹：{exc}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    # 搜索 ---------------------------------------------------------------

    def _scheduleSearch(self, *_):
        self._searchTimer.start()

    def _searchNow(self, *_):
        self._searchTimer.stop()
        self._search()

    def _search(self):
        query = self.searchBox.text().strip()
        if not query:
            self._leaveSearch()
            return
        try:
            results = search_help(query, limit=30)
        except Exception as exc:
            log.warning(f"帮助搜索失败：{type(exc).__name__}: {exc}")
            results = HelpResults((), ())
        self.searchPage.setResults(query, results)
        self.stack.setCurrentWidget(self.searchPage)
        # 搜索结果跨文档，左侧不再显示某一篇的目录。
        self.toc.setEntries(())
        self.tocLabel.hide()

    def _leaveSearch(self):
        if self.stack.currentWidget() is self.searchPage:
            page = self.currentPage()
            if page is not None:
                self.stack.setCurrentWidget(page)
                self.toc.setEntries(page.tocEntries())
                self.tocLabel.setVisible(bool(page.tocEntries()))
                self.toc.setCurrent(page.currentAnchor())

    def _openFirstHit(self):
        self._searchNow()
        rows = self.searchPage.rows
        if self.stack.currentWidget() is self.searchPage and rows:
            self.openHit(rows[0].hit)

    def openHit(self, hit):
        self.searchBox.blockSignals(True)
        self.searchBox.clear()
        self.searchBox.blockSignals(False)
        self._searchTimer.stop()
        self._history.clear()
        self.showDocument(hit.section.doc_id, hit.section.anchor)

    # 状态 ---------------------------------------------------------------

    def _refreshBadge(self, *_):
        self.docList.setBadge("Changelog", tr("新") if self.badge.is_new else "")

    def _restyle(self, *_):
        current = self.stack.currentWidget()
        for page in self.pages.values():
            if page is current:
                page.restyle()
            else:
                page.dirty = True
        self.searchPage.restyle()
        self.supportCard.restyle()
        self.docList.update()
        for item in self.docList.items.values():
            item.update()
        self.toc.update()

    def captureViewState(self):
        page = self.currentPage()
        state = {"doc": self.current, "search": self.searchBox.text()}
        if page is not None:
            state.update(page.captureState(), language=page.doc.language)
        return state

    def restoreViewState(self, state):
        if not state or not state.get("doc"):
            return
        if not self.showDocument(state["doc"], flash=False):
            return
        self.currentPage().restoreState(state, state.get("language"))
        if state.get("search"):
            self.searchBox.setText(state["search"])
            self._searchNow()

    def retranslateUi(self):
        state = self.captureViewState()
        self.titleLabel.setText(tr("帮助"))
        self.searchBox.setPlaceholderText(tr("搜索帮助文档"))
        self.tocLabel.setText(tr("本页目录"))
        self.docList.retranslate()
        self.supportCard.retranslate()
        self._refreshBadge()
        # 换语言后文档文件也换了：丢掉旧页面，按保存的位置重新打开。
        for page in self.pages.values():
            self.stack.removeWidget(page)
            page.hide()
            page.deleteLater()
        self.pages.clear()
        self.current = None
        self._history.clear()
        if state.get("doc"):
            self.restoreViewState(state)
        elif self.isVisible():
            self._showDefault()
