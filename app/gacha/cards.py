"""统计页：四张数字卡、当前保底、五星出货分布和五星记录。"""
import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import CaptionLabel, ScrollArea, SimpleCardWidget, StrongBodyLabel, setFont

from app.common.design_tokens import CARD_SPACING, PAGE_MARGIN
from app.overview.widgets import ElidedLabel, LinkButton, Pill
from app.pages.common import secondary
from module.localization import tr

from . import style
from .charts import DistributionChart, FiveList, PityBar, ValueText


class Card(SimpleCardWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBorderRadius(8)
        self.vBox = QVBoxLayout(self)
        self.vBox.setContentsMargins(16, 14, 16, 14)
        self.vBox.setSpacing(0)


def title_label(parent):
    label = StrongBodyLabel(parent)
    setFont(label, 15, QFont.Weight.DemiBold)
    return label


class RichCaption(QLabel):
    """说明文字里的数字加粗、用正文色，其余用次要色。模板里的 {名字} 换成对应的值。"""

    def __init__(self, parent=None, *, size=13):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        setFont(self, size)
        self._template = ""
        self._values = {}

    def setTemplate(self, template, **values):
        self._template, self._values = template or "", values
        self.refresh()

    def plainText(self):
        return self._template.format(**self._values)

    def refresh(self):
        strong = style.primary().name()
        values = {key: f'<span style="color:{strong}; font-weight:600">{html.escape(str(value))}</span>'
                  for key, value in self._values.items()}
        body = html.escape(self._template, quote=False).format(**values)
        self.setText(f'<span style="color:{style.muted().name()}">{body}</span>')


class HeadingLabel(QLabel):
    """卡片标题后面紧跟一段小字说明，两段文字共用一条基线。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextFormat(Qt.TextFormat.RichText)
        self._title = ""
        self._caption = ""

    def setParts(self, title, caption=""):
        self._title, self._caption = title, caption
        self.refresh()

    def plainText(self):
        return f"{self._title} {self._caption}".strip()

    def refresh(self):
        text = (f'<span style="font-size:15px; font-weight:600; color:{style.primary().name()}">'
                f'{html.escape(self._title)}</span>')
        if self._caption:
            text += (f'&nbsp;&nbsp;<span style="font-size:12px; color:{style.muted().name()}">'
                     f'{html.escape(self._caption)}</span>')
        self.setText(text)


class FigureCard(Card):
    """一个数字：标题、数值和单位、补充说明。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = secondary(CaptionLabel(self))
        setFont(self.titleLabel, 13)
        self.value = ValueText(26, self)
        self.noteLabel = secondary(ElidedLabel(self, size=12))
        self.vBox.addWidget(self.titleLabel)
        self.vBox.addSpacing(6)
        self.vBox.addWidget(self.value)
        self.vBox.addSpacing(8)
        self.vBox.addWidget(self.noteLabel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setFigure(self, title, value, unit, note):
        self.titleLabel.setText(title)
        self.value.setParts(value, unit)
        self.noteLabel.setFullText(note)


class PityCard(Card):
    def __init__(self, parent=None):
        super().__init__(parent)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.titleLabel = title_label(self)
        self.chip = Pill(self, height=24)
        header.addWidget(self.titleLabel)
        header.addStretch(1)
        header.addWidget(self.chip)
        self.value = ValueText(34, self, unit_size=14)
        self.bar = PityBar(self)
        footer = QHBoxLayout()
        footer.setSpacing(12)
        self.distanceLabel = RichCaption(self)
        self.fourLabel = RichCaption(self)
        footer.addWidget(self.distanceLabel)
        footer.addStretch(1)
        footer.addWidget(self.fourLabel)
        self.vBox.addLayout(header)
        self.vBox.addSpacing(10)
        self.vBox.addWidget(self.value)
        self.vBox.addSpacing(10)
        self.vBox.addWidget(self.bar)
        self.vBox.addSpacing(6)
        self.vBox.addLayout(footer)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setStats(self, stats):
        pool = stats.pool
        self.titleLabel.setText(tr("当前保底"))
        self.chip.setPill(tr("{category} · {limit} 抽保底").format(category=pool.category_label, limit=pool.five_limit))
        self.fourLabel.setTemplate(tr("四星 {count} / {limit}"), count=stats.four_pity, limit=pool.four_limit)
        self.fourLabel.show()
        if stats.ended:
            self.value.setParts(style.number(stats.total), tr("抽 · 已结束"))
            self.bar.setData(stats.total, pool.five_limit, pool.soft_start)
            self.distanceLabel.setTemplate(tr("新手跃迁最多 {limit} 抽，已经抽完"), limit=pool.five_limit)
            self.fourLabel.hide()
        elif stats.remaining is None:
            # 新手跃迁提前出了唯一保证的五星，之后只剩可抽的次数。
            self.value.setParts(style.number(stats.total), tr("抽 · 已获得五星"))
            self.bar.setData(stats.total, pool.five_limit, pool.soft_start)
            self.distanceLabel.setTemplate(tr("还能再抽 {pulls} 抽"), pulls=max(0, pool.five_limit - stats.total))
        else:
            self.value.setParts(str(stats.five_pity), tr("抽未出五星"))
            self.bar.setData(stats.five_pity, pool.five_limit, pool.soft_start)
            self.distanceLabel.setTemplate(tr("距离保底 {pulls} 抽（约 {jade} 星琼）"), pulls=stats.remaining,
                                           jade=style.number(stats.remaining_jade or 0))
        if stats.ended or stats.remaining is None:
            self.bar.setToolTip(self.distanceLabel.plainText())

    def refresh(self):
        self.distanceLabel.refresh()
        self.fourLabel.refresh()


class DistributionCard(Card):
    def __init__(self, parent=None):
        super().__init__(parent)
        header = QHBoxLayout()
        self.titleLabel = title_label(self)
        self.captionLabel = secondary(CaptionLabel(self))
        setFont(self.captionLabel, 12)
        header.addWidget(self.titleLabel)
        header.addStretch(1)
        header.addWidget(self.captionLabel)
        self.chart = DistributionChart(self)
        self.noteLabel = secondary(CaptionLabel(self))
        setFont(self.noteLabel, 12)
        self.noteLabel.setWordWrap(True)
        self.noteLabel.hide()
        self.vBox.addLayout(header)
        self.vBox.addSpacing(8)
        self.vBox.addWidget(self.chart, 1)
        self.vBox.addWidget(self.noteLabel)

    def setStats(self, stats):
        self.titleLabel.setText(tr("五星出货分布"))
        self.captionLabel.setText(tr("按出金时的抽数分段"))
        self.chart.setBuckets(stats.distribution)
        outside = stats.outside_distribution
        self.noteLabel.setVisible(bool(outside))
        if outside:
            self.noteLabel.setText(tr("另有 {count} 个五星超过 {limit} 抽，可能是记录不完整").format(
                count=outside, limit=stats.pool.five_limit))


class FiveCard(Card):
    openDetails = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stats = None
        self.heading = HeadingLabel(self)
        self.list = FiveList(self)
        self.list.capacityChanged.connect(self._updateFooter)
        footer = QHBoxLayout()
        footer.setSpacing(12)
        self.footLabel = secondary(ElidedLabel(self, size=12))
        self.detailsButton = LinkButton("", self, size=13)
        self.detailsButton.clicked.connect(self.openDetails)
        footer.addWidget(self.footLabel, 1)
        footer.addWidget(self.detailsButton)
        self.vBox.addWidget(self.heading)
        self.vBox.addSpacing(8)
        self.vBox.addWidget(self.list, 1)
        self.vBox.addSpacing(8)
        self.vBox.addLayout(footer)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def setStats(self, stats, now=None):
        self._stats = stats
        self.heading.setParts(tr("五星记录"), tr("最近在前"))
        self.detailsButton.setText(tr("打开明细表 ›"))
        self.detailsButton.setVisible(stats.total > 0)
        self.list.setRows(stats.fives, stats.pool.five_limit, stats.pool.soft_start, now)
        self._updateFooter()

    def _updateFooter(self):
        stats = self._stats
        if stats is None:
            return
        shown = self.list.shown()
        if not stats.total:
            text = tr("这个卡池还没有记录")
        elif not stats.five_count:
            text = tr("还没有五星，表格中可按星级、名称筛选")
        elif shown < stats.five_count:
            text = tr("共 {count} 个五星，这里显示最近 {shown} 个").format(count=stats.five_count, shown=shown)
        else:
            text = tr("共 {count} 个五星 · 表格中可按星级、名称筛选").format(count=stats.five_count)
        self.footLabel.setFullText(text)

    def refresh(self):
        self.heading.refresh()
        self.detailsButton.setEvernight(style.evernight())


class Dashboard(ScrollArea):
    """一个卡池的统计。切换卡池只换数据，不重建控件。"""
    openDetails = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = QWidget(self)
        self.view.setObjectName("view")
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.enableTransparentBackground()
        layout = QVBoxLayout(self.view)
        layout.setContentsMargins(PAGE_MARGIN, 2, PAGE_MARGIN, 24)
        layout.setSpacing(CARD_SPACING)
        figures = QHBoxLayout()
        figures.setSpacing(CARD_SPACING)
        self.totalCard, self.fiveCountCard, self.averageCard, self.fourCard = (FigureCard(self.view) for _ in range(4))
        for card in (self.totalCard, self.fiveCountCard, self.averageCard, self.fourCard):
            figures.addWidget(card, 1)
        lower = QHBoxLayout()
        lower.setSpacing(CARD_SPACING)
        left = QVBoxLayout()
        left.setSpacing(CARD_SPACING)
        self.pityCard = PityCard(self.view)
        self.distributionCard = DistributionCard(self.view)
        left.addWidget(self.pityCard)
        left.addWidget(self.distributionCard, 1)
        self.fiveCard = FiveCard(self.view)
        self.fiveCard.openDetails.connect(self.openDetails)
        lower.addLayout(left, 5)
        lower.addWidget(self.fiveCard, 7)
        layout.addLayout(figures)
        layout.addLayout(lower)
        layout.addStretch(1)

    def setStats(self, stats, now=None):
        total = stats.total
        none = tr("还没有记录")
        span = (tr("{start} 至 {end}").format(start=style.date_text(stats.first_time), end=style.date_text(stats.last_time))
                if total else none)
        self.totalCard.setFigure(tr("总抽数"), style.number(total), "", span)
        if stats.five_count:
            note = tr("最近一次：{date}").format(date=style.short_date(stats.last_five_time, now))
        else:
            note = tr("还没有五星") if total else none
        self.fiveCountCard.setFigure(tr("五星"), style.number(stats.five_count),
                                     tr("出率 {rate}").format(rate=style.percent(stats.five_rate, 2)) if total else "", note)
        if stats.five_average is not None:
            self.averageCard.setFigure(tr("平均出金"), f"{stats.five_average:.1f}", tr("抽"),
                                       tr("最快 {fast} 抽 · 最慢 {slow} 抽").format(fast=stats.five_min, slow=stats.five_max))
        else:
            self.averageCard.setFigure(tr("平均出金"), "—", "", tr("出过五星后显示") if total else none)
        if stats.four_average is not None:
            note = tr("平均每 {pulls} 抽一个四星").format(pulls=f"{stats.four_average:.1f}")
        else:
            note = tr("还没有四星") if total else none
        self.fourCard.setFigure(tr("四星"), style.number(stats.four_count),
                                tr("出率 {rate}").format(rate=style.percent(stats.four_rate, 1)) if total else "", note)
        self.pityCard.setStats(stats)
        self.distributionCard.setStats(stats)
        self.fiveCard.setStats(stats, now)

    def refresh(self):
        self.pityCard.refresh()
        self.fiveCard.refresh()
        self.view.update()
