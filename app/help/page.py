"""一篇文档的阅读页：页眉、标题和正文。负责滚到锚点、目录随滚动高亮，以及保存和恢复阅读位置。"""
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (CaptionLabel, FluentIcon, InfoBar, InfoBarPosition, PushButton, ScrollArea,
                            TransparentToolButton, setFont)

from app.navigation import highlight
from app.pages.common import NoticeStrip, is_evernight, secondary
from module.docs.catalog import DOCUMENTS, current_version, source_for, website_url
from module.docs.formats import release_for_anchor, split_faq
from module.docs.model import Heading, Text
from module.docs.reader import resolve_anchor
from module.localization import tr
from . import style
from .blocks import BlockContext, DetailsView, TableView, build_blocks
from .richtext import RichText
from .sections import FoldCard, QuestionCard, VersionCard

LAYOUT_REQUEST = int(getattr(QEvent.Type.LayoutRequest, "value", QEvent.Type.LayoutRequest))


class MetaRow(QWidget):
    """页眉：返回、「帮助 › 文档」、随哪个版本更新、在官网查看。"""

    def __init__(self, page):
        super().__init__(page.column)
        self.backButton = TransparentToolButton(FluentIcon.LEFT_ARROW, self)
        self.backButton.setFixedSize(28, 28)
        self.backButton.setIconSize(QSize(12, 12))
        self.backButton.hide()
        self.crumbLabel = secondary(CaptionLabel(self))
        self.versionLabel = secondary(CaptionLabel(self))
        self.websiteButton = PushButton(FluentIcon.GLOBE, "", self)
        setFont(self.websiteButton, 13)
        self.websiteButton.setFixedHeight(30)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.backButton)
        layout.addWidget(self.crumbLabel)
        layout.addWidget(self.versionLabel)
        layout.addStretch(1)
        layout.addWidget(self.websiteButton)
        self.retranslate(page)

    def retranslate(self, page):
        manual = page.manual
        name = tr(manual.name) if manual is not None else page.doc.title
        self.crumbLabel.setText(tr("帮助") + "  ›  " + name)
        version = current_version()
        # 简体文档随程序更新；英日韩译本更新得晚，不写版本以免误导。
        show = page.doc.language in ("zh_CN", "zh_TW") and version and version != "unknown"
        self.versionLabel.setText("·  " + tr("随 {version} 更新").format(version=version) if show else "")
        self.versionLabel.setVisible(bool(show))
        self.backButton.setToolTip(tr("返回"))
        self.websiteButton.setText(tr("在官网查看"))


class DocPage(ScrollArea):
    anchorChanged = Signal(str)

    def __init__(self, interface, doc):
        super().__init__(interface)
        self.interface = interface
        self.doc = doc
        self.manual = DOCUMENTS.get(doc.id)
        self.kind = self.manual.kind if self.manual is not None else "article"
        self.dirty = False
        self.cards = {}
        self._current = ""
        self._pending = None
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        outer = QHBoxLayout(self.view)
        outer.setContentsMargins(36, 16, 36, 48)
        outer.setSpacing(0)
        self.column = QWidget(self.view)
        self.column.setMaximumWidth(style.READING_WIDTH)
        outer.addStretch(1)
        outer.addWidget(self.column, 100)
        outer.addStretch(1)
        self.vBoxLayout = QVBoxLayout(self.column)
        self.vBoxLayout.setContentsMargins(0, 0, 0, 0)
        self.vBoxLayout.setSpacing(0)
        self.meta = MetaRow(self)
        self.meta.backButton.clicked.connect(interface.goBack)
        self.meta.websiteButton.clicked.connect(self.openWebsite)
        title = doc.title or (tr(self.manual.name) if self.manual is not None else doc.id)
        self.titleText = RichText((Text(title),), self.column, size=28, weight=QFont.Weight.DemiBold, ratio=1.3)
        self.vBoxLayout.addWidget(self.meta)
        self.vBoxLayout.addSpacing(6)
        self.vBoxLayout.addWidget(self.titleText)
        self.vBoxLayout.addSpacing(18)
        self.ctx = BlockContext(self)
        if doc.degraded:
            notice = NoticeStrip(self.column, kind="warning")
            notice.setText(tr("这篇文档的排版出了问题，下面按原文显示。"))
            self.vBoxLayout.addWidget(notice)
            self.vBoxLayout.addSpacing(14)
        self._buildBody()
        self.vBoxLayout.addStretch(1)
        self._syncTimer = QTimer(self)
        self._syncTimer.setSingleShot(True)
        self._syncTimer.setInterval(40)
        self._syncTimer.timeout.connect(self._sync)
        self.verticalScrollBar().valueChanged.connect(self._scheduleSync)

    def _scheduleSync(self, *_):
        self._syncTimer.start()

    # 正文 ---------------------------------------------------------------

    def _buildBody(self):
        blocks = list(self.doc.blocks)
        if blocks and isinstance(blocks[0], Heading) and blocks[0].level == 1:
            blocks.pop(0)
        if self.kind == "faq":
            faq = split_faq(self.doc)
            intro = [b for b in faq.intro if not (isinstance(b, Heading) and b.level == 1)]
            self._addBlocks(intro)
            for index, question in enumerate(faq.questions):
                card = QuestionCard(question, self.ctx, self.column)
                self.cards[question.anchor] = card
                self.vBoxLayout.addSpacing(18 if index == 0 and intro else 8 if index else 0)
                self.vBoxLayout.addWidget(card)
        elif self.kind == "changelog":
            self._addBlocks(blocks)
            current = current_version()
            for index, entry in enumerate(self.doc.versions):
                card = VersionCard(entry, self.doc, self.ctx, self.column, current=entry.version == current)
                self.cards[entry.anchor] = card
                self.vBoxLayout.addSpacing(18 if index == 0 and blocks else 8 if index else 0)
                self.vBoxLayout.addWidget(card)
                if index == 0:
                    card.setExpanded(True)
        else:
            self._addBlocks(blocks)

    def _addBlocks(self, blocks):
        if not blocks:
            return
        holder = QWidget(self.column)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        build_blocks(blocks, self.ctx, holder, layout)
        self.vBoxLayout.addWidget(holder)

    def activate(self, target):
        self.interface.activate(target)

    def copySectionLink(self, anchor):
        url = website_url(self.doc.id, anchor, self.doc.language)
        QApplication.clipboard().setText(url)
        InfoBar.success(title="", content=tr("已复制本节的官网链接"), duration=1800,
                        position=InfoBarPosition.TOP, parent=self.interface.window())

    def openWebsite(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl(website_url(self.doc.id, self.currentAnchor(), self.doc.language)))

    def restyle(self):
        for text in self.findChildren(RichText):
            text.restyle()
        for table in self.findChildren(TableView):
            table.refresh()
        for notice in self.findChildren(NoticeStrip):
            notice.setKind("warning", is_evernight())
        self.dirty = False
        self.update()

    def retranslate(self):
        self.meta.retranslate(self)

    # 位置 ---------------------------------------------------------------

    def tocEntries(self):
        return self.doc.toc

    def _target(self, anchor):
        return self.cards.get(anchor) or self.ctx.anchors.get(anchor)

    def _y(self, widget):
        return widget.mapTo(self.view, QPoint(0, 0)).y()

    def currentAnchor(self):
        entries = self.doc.toc
        if not entries:
            return ""
        bar = self.verticalScrollBar()
        top = bar.value() + 56
        current = entries[0].anchor
        positions = []
        for entry in entries:
            widget = self._target(entry.anchor)
            if widget is None or not widget.isVisibleTo(self.view):
                continue
            y = self._y(widget)
            positions.append((y, entry.anchor))
            if y <= top:
                current = entry.anchor
        if bar.maximum() > 0 and bar.value() >= bar.maximum() - 4:
            bottom = bar.value() + self.viewport().height() - 40
            visible = [anchor for y, anchor in positions if y <= bottom]
            if visible:
                current = visible[-1]
        return current

    def _sync(self):
        anchor = self.currentAnchor()
        if anchor != self._current:
            self._current = anchor
            self.anchorChanged.emit(anchor)

    def _reveal(self, anchor):
        widget = self._target(anchor)
        if widget is None and self.kind == "changelog":
            entry = release_for_anchor(self.doc, anchor)
            card = self.cards.get(entry.anchor) if entry is not None else None
            if card is not None:
                card.setExpanded(True)
                widget = self.ctx.anchors.get(anchor) or card
        if widget is None:
            return None
        if isinstance(widget, FoldCard):
            widget.setExpanded(True)
        parent = widget.parentWidget()
        while parent is not None and parent is not self.view:
            if isinstance(parent, (FoldCard, DetailsView)) and not parent.isExpanded():
                parent.setExpanded(True)
            parent = parent.parentWidget()
        return widget

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending is not None:
            QTimer.singleShot(0, self, self._applyScroll)

    def scrollToTop(self):
        self._pending = None
        self.verticalScrollBar().setValue(0)
        self._syncTimer.start()

    def scrollToAnchor(self, anchor, *, flash=True, smooth=False, offset=None):
        widget = self._reveal(anchor)
        if widget is None:
            return False
        self._pending = (anchor, widget, flash, smooth, offset)
        QTimer.singleShot(0, self, self._applyScroll)
        return True

    def _applyScroll(self):
        # 隐藏页按临时宽度排版，等页面显示后再计算标题的位置。
        if self._pending is None or not self.isVisible():
            return
        _, widget, flash, smooth, offset = self._pending
        self._pending = None
        QCoreApplication.sendPostedEvents(None, LAYOUT_REQUEST)
        y = max(0, self._y(widget) - (16 if offset is None else offset))
        delegate = getattr(self, "scrollDelagate", None)
        if smooth and delegate is not None and hasattr(delegate, "vScrollBar"):
            delegate.vScrollBar.scrollTo(y)
        else:
            self.verticalScrollBar().setValue(y)
        if flash:
            if hasattr(widget, "flash"):
                widget.flash()
            else:
                highlight(widget)
        self._syncTimer.start()

    def captureState(self):
        bar = self.verticalScrollBar()
        if self._pending is not None:
            # 再次切换语言时，沿用尚未显示的小节。
            anchor, _, _, _, inset = self._pending
            offset = -(16 if inset is None else inset)
        else:
            anchor = self.currentAnchor()
            widget = self._target(anchor) if anchor else None
            offset = bar.value() - self._y(widget) if widget is not None else 0
        return {"anchor": anchor, "offset": offset, "scroll": bar.value(),
                "expanded": [a for a, card in self.cards.items() if card.isExpanded()]}

    def restoreState(self, state, written_language=None):
        source = source_for(self.doc.id, self.doc.language)

        def convert(anchor):
            if not anchor:
                return ""
            return resolve_anchor(source, anchor, written_language=written_language) or ""

        if "expanded" in state:
            expanded = {convert(a) for a in state.get("expanded") or ()}
            for anchor, card in self.cards.items():
                card.setExpanded(anchor in expanded)
        anchor = convert(state.get("anchor", ""))
        if anchor and self.scrollToAnchor(anchor, flash=False, offset=-int(state.get("offset", 0))):
            return
        self._restoreScroll = int(state.get("scroll", 0))
        QTimer.singleShot(0, self, self._applyRestoreScroll)

    def _applyRestoreScroll(self):
        self.verticalScrollBar().setValue(getattr(self, "_restoreScroll", 0))
        self._syncTimer.start()
