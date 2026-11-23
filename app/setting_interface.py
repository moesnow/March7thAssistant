"""设置：左侧 10 个竖向分类和设置内搜索，右侧是所选分类的设置卡。

卡片由 app.content 按分类建造；这里只负责排版、定位、搜索和界面状态。
"""
from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ExpandSettingCard, ScrollArea, SearchLineEdit, StrongBodyLabel,
                            TitleLabel, qconfig)

from app.content import PAGES, PageHost, build_page
from app.content.base import card_for
from app.content.visibility import setting_visible
from app.content.notify_model import NotifyModel
from module.localization import tr
from module.logger import log
from module.search import SearchIndex
from .pages.category_list import CategoryList
from .pages.common import NoticeStrip, SectionView, border_color, is_evernight, secondary, shared
from .pages.decorations import CardDecorations
from .pages.notify import ChannelPanel
from .pages.run_mode import RunModeChooser
from .pages.search_rows import ResultRow

DESCRIPTIONS = {
    "run_mode": "选择游戏在哪里运行，以及小助手怎样操作它。切换后从下一次任务开始生效。",
    "game": "启动游戏的方式和等待时间，以及运行期间对画面和按键的调整。",
    "after_run": "全部任务结束后要做什么，例如关机、退出小助手或运行脚本。",
    "notify": "任务完成或失败时通知你。先添加一个常用的渠道，再点「测试」确认能收到。",
    "hotkeys": "随时停止、暂停任务或切换自动对话的全局快捷键，小助手在后台时也能用。",
    "appearance": "界面语言、主题、总览的问候区，以及关闭和记忆窗口的方式。",
    "update": "检查更新的时机、下载来源和代理。",
    "data": "设置、账号、运行记录和日志都放在数据文件夹里，可以在这里备份、恢复或导出排查包。",
    "advanced": "通常不需要修改，排查问题时再来调整。",
    "about": "版本信息、项目主页和社区。",
}
CHANNEL_SECTION = "channels"


def _channel_of(setting):
    """渠道字段和启用项（notify_<渠道>_…）对应的渠道 ID。"""
    from module.channel_catalog import CHANNEL_BY_ID
    if setting.id == "qqbot_bind":
        return "qqbot"
    for key in (setting.id, *setting.keys):
        if key.startswith("notify_"):
            name = key[len("notify_"):].split("_")[0]
            if name in CHANNEL_BY_ID:
                return name
    return None


class SettingPage(ScrollArea):
    """一个分类：面包屑、标题、说明和若干组设置。"""

    def __init__(self, interface, page):
        super().__init__(interface)
        self.interface, self.page = interface, page
        window = interface.window_
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(32, 18, 30, 28)
        self.vBoxLayout.setSpacing(14)
        self.breadcrumb = secondary(CaptionLabel(tr("设置") + "  ›  " + tr(page.name), self.view))
        self.titleLabel = TitleLabel(tr(page.name), self.view)
        self.descriptionLabel = secondary(BodyLabel(tr(DESCRIPTIONS.get(page.id, "")), self.view))
        self.descriptionLabel.setWordWrap(True)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(self.breadcrumb)
        heading.addWidget(self.titleLabel)
        heading.addSpacing(2)
        heading.addWidget(self.descriptionLabel)
        self.vBoxLayout.addLayout(heading)
        self.host = PageHost(window, self.view)
        self.views = {}
        self.chooser = None
        self.channels = None
        for section in build_page(page.id, self.host):
            view = SectionView(section, self.view, showTitle=section.id != "header")
            if page.id == "run_mode" and section.id == "header":
                self.chooser = RunModeChooser(window, view)
                view.addExtra(self.chooser)
            if page.id == "notify" and section.id == CHANNEL_SECTION:
                self.channels = ChannelPanel(window, interface.notifyModel, view)
                view.addExtra(self.channels)
            self.views[section.id] = view
            self.vBoxLayout.addWidget(view)
        self.vBoxLayout.addStretch(1)
        self.decorations = CardDecorations(self.host, window)
        self.host.visibilityChanged.connect(self.refreshSections)
        self.refreshSections()

    def refreshSections(self):
        for view in self.views.values():
            view.refresh()

    def target(self, setting):
        widget = card_for(setting, self.host)
        if widget is not None:
            return widget
        if self.chooser is not None and setting.section == "header":
            return self.chooser
        if self.channels is not None:
            channel = _channel_of(setting)
            if channel:
                return self.channels.locateWidget(channel) or self.channels
        return self.views.get(setting.section)


class SearchResultsPage(ScrollArea):
    """设置页内搜索的结果，只列设置项。"""

    def __init__(self, interface):
        super().__init__(interface)
        self.interface = interface
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        self.vBoxLayout = QVBoxLayout(self.view)
        self.vBoxLayout.setContentsMargins(28, 22, 30, 28)
        self.vBoxLayout.setSpacing(4)
        self.titleLabel = StrongBodyLabel(self.view)
        self.emptyLabel = secondary(BodyLabel(self.view))
        self.emptyLabel.setWordWrap(True)
        self.vBoxLayout.addWidget(self.titleLabel)
        self.vBoxLayout.addSpacing(6)
        self.vBoxLayout.addWidget(self.emptyLabel)
        self.rows = []
        self.vBoxLayout.addStretch(1)

    def setResults(self, query, results, suggestions=()):
        for row in self.rows:
            self.vBoxLayout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        self.titleLabel.setText(tr("搜索「{query}」").format(query=query))
        self.emptyLabel.setVisible(not results)
        if not results:
            hint = tr("没有找到相关设置。")
            if suggestions:
                hint += tr("换个说法试试：{words}").format(words="、".join(suggestions))
            hint += tr(" 任务相关的内容请到「任务」页查看。")
            self.emptyLabel.setText(hint)
        for index, result in enumerate(results):
            row = ResultRow(result, query, self.view)
            row.clicked.connect(self.interface._openResult)
            self.rows.append(row)
            self.vBoxLayout.insertWidget(3 + index, row)


class SidePanel(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(QRect(self.width() - 1, 0, 1, self.height()), border_color())


class SettingInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        try:
            self._build(parent)
        except Exception:
            self.deleteLater()
            raise

    def _build(self, parent):
        self.setObjectName("settingInterface")
        self.window_ = parent
        self.notifyModel = shared(parent, "notifyModel", lambda: NotifyModel(parent))
        self.searchIndex = shared(parent, "searchIndex", lambda: SearchIndex(_config()))
        if parent is None:
            self.destroyed.connect(self.searchIndex.close)
        self.sidePanel = SidePanel(self)
        self.sidePanel.setFixedWidth(220)
        self.titleLabel = TitleLabel(tr("设置"), self.sidePanel)
        self.searchBox = SearchLineEdit(self.sidePanel)
        self.searchBox.setPlaceholderText(tr("搜索设置"))
        self.categoryList = CategoryList(self.sidePanel)
        self.hint = NoticeStrip(self.sidePanel, kind="info", stacked=True)
        self.hint.setText(tr("每个任务做什么，在「任务」页设置。"))
        self.hint.setAction(tr("前往任务页 ›"))
        self.hint.actionClicked.connect(self._openTasks)
        side = QVBoxLayout(self.sidePanel)
        side.setContentsMargins(20, 14, 16, 16)
        side.setSpacing(10)
        side.addWidget(self.titleLabel)
        side.addWidget(self.searchBox)
        side.addSpacing(4)
        side.addWidget(self.categoryList)
        side.addStretch(1)
        side.addWidget(self.hint)
        self.stack = QStackedWidget(self)
        self.pages = {}
        for page in PAGES:
            if page.kind != "setting":
                continue
            widget = SettingPage(self, page)
            self.pages[page.id] = widget
            self.stack.addWidget(widget)
            self.categoryList.addCategory(page.id, page.icon, tr(page.name))
        self.results = SearchResultsPage(self)
        self.stack.addWidget(self.results)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidePanel)
        layout.addWidget(self.stack, 1)
        appearance = self.pages.get("appearance")
        self.themeCard = getattr(appearance.host, "themeCard", None) if appearance else None
        self.languageCard = getattr(appearance.host, "languageCard", None) if appearance else None
        self._searchTimer = QTimer(self)
        self._searchTimer.setSingleShot(True)
        self._searchTimer.setInterval(150)
        self._searchTimer.timeout.connect(self._search)
        self.searchBox.textChanged.connect(lambda _: self._searchTimer.start())
        self.searchBox.searchSignal.connect(lambda _: self._search())
        self.categoryList.currentChanged.connect(self.showCategory)
        self.notifyModel.changed.connect(self._refreshHints)
        qconfig.themeColorChanged.connect(self._restyle)
        self._refreshHints()
        self._restyle()
        if self.pages:
            self.showCategory(next(iter(self.pages)))

    def _restyle(self, *_):
        self.hint.setKind("info", is_evernight())
        self.update()

    def _refreshHints(self):
        try:
            count = sum(1 for row in self.notifyModel.added() if row.enabled)
        except Exception:
            return
        self.categoryList.setHint("notify", tr("{count} 个渠道").format(count=count) if count else tr("未设置"))

    def _openTasks(self):
        window = self.window_
        if window is not None and hasattr(window, "taskInterface"):
            window.switchTo(window.taskInterface)

    def currentCategory(self):
        return self.categoryList.current()

    def showCategory(self, category_id):
        if category_id not in self.pages:
            return False
        if self.searchBox.text():
            self.searchBox.blockSignals(True)
            self.searchBox.clear()
            self.searchBox.blockSignals(False)
        self.categoryList.setCurrent(category_id)
        self.stack.setCurrentWidget(self.pages[category_id])
        return True

    def _search(self):
        query = self.searchBox.text().strip()
        if not query:
            current = self.categoryList.current()
            if current in self.pages:
                self.stack.setCurrentWidget(self.pages[current])
            return
        try:
            results = self.searchIndex.query(query, limit=40, settings_only=True)
            suggestions = () if results else self.searchIndex.suggestions()
        except Exception as exc:
            log.warning(f"设置搜索失败：{type(exc).__name__}: {exc}")
            results, suggestions = [], ()
        self.results.setResults(query, results, suggestions)
        self.stack.setCurrentWidget(self.results)

    def _openResult(self, result):
        window = self.window_
        self.searchBox.blockSignals(True)
        self.searchBox.clear()
        self.searchBox.blockSignals(False)
        if window is not None and hasattr(window, "navigate"):
            window.navigate(result.link)

    def locate(self, setting):
        if not setting_visible(setting):
            return False
        page = self.pages.get(setting.page)
        if page is None or not self.showCategory(setting.page):
            return False
        widget = page.target(setting)
        if widget is None or widget.isHidden():
            return False
        parent = widget.parentWidget()
        while parent is not None and parent is not page.view:
            if isinstance(parent, ExpandSettingCard) and not parent.isExpand:
                parent.setExpand(True)
                parent.expandAni.setCurrentTime(parent.expandAni.duration())
            if isinstance(parent, SectionView):
                if parent.isHidden():
                    return False
                if not parent.isExpanded():
                    parent.setExpanded(True)
            parent = parent.parentWidget()
        QTimer.singleShot(0, widget, lambda: self._scrollTo(page, widget))
        return True

    @staticmethod
    def _scrollTo(page, widget):
        from app.navigation import highlight
        try:
            page.view.layout().activate()
            target = getattr(widget, "card", widget) if isinstance(widget, ExpandSettingCard) else widget
            top = target.mapTo(page.view, QPoint(0, 0)).y()
            viewport = page.viewport().height()
            page.verticalScrollBar().setValue(max(0, top - max(0, (viewport - target.height()) // 2)))
            highlight(target)
        except RuntimeError:
            pass

    def captureViewState(self):
        state = {"category": self.currentCategory(), "scroll": {}, "sections": {}, "cards": {},
                 "search": self.searchBox.text()}
        for key, page in self.pages.items():
            state["scroll"][key] = page.verticalScrollBar().value()
            state["sections"][key] = {sid: view.isExpanded() for sid, view in page.views.items()}
            try:
                state["cards"][key] = page.host.capture_card_state()
            except Exception:
                pass
        return state

    def restoreViewState(self, state):
        for key, page in self.pages.items():
            for sid, expanded in state.get("sections", {}).get(key, {}).items():
                view = page.views.get(sid)
                if view is not None and view.header is not None:
                    view.setExpanded(expanded)
            if key in state.get("cards", {}):
                page.host.restore_card_state(state["cards"][key])
        if state.get("category") in self.pages:
            self.showCategory(state["category"])
        if state.get("search"):
            self.searchBox.setText(state["search"])
            self._search()
        scroll = state.get("scroll", {})
        for key, page in self.pages.items():
            page.view.layout().activate()
            page.verticalScrollBar().setValue(scroll.get(key, 0))


def _config():
    from module.config import cfg
    return cfg
