"""向导的五个步骤和完成页。每一步只管显示和收集，读取、保存都在 SetupModel 里。"""
from dataclasses import replace
from types import SimpleNamespace

from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QButtonGroup, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, FluentIcon, IndeterminateProgressRing, PushButton,
                            ScrollArea, SimpleCardWidget, StrongBodyLabel, SubtitleLabel, TimePicker, setFont)

from app.common.mascot import Mascot
from app.gacha.chips import Chip
from app.overview.widgets import ElidedLabel, IconTile, LinkButton
from app.pages import style
from app.pages.common import Divider, NoticeStrip, bare_switch, icon_of, is_evernight, secondary
from module.localization import tr
from .widgets import CandidateRow, Choice, ElidedComboBox, FieldRow, Group, Notes, PowerTile, TaskTile


def mode_notes(value):
    return {
        "local": (("check", tr("支持全部任务，可以在前台运行，也可以设成后台运行，边挂机边用电脑")),
                  ("check", tr("分辨率会自动调成 1920×1080，不用自己改")),
                  ("alert", tr("默认在前台运行，任务期间会操作鼠标和键盘，先别用电脑"))),
        "cloud": (("check", tr("在浏览器里运行，不占显卡，也可以无窗口运行")),
                  ("check", tr("Windows、macOS、Linux 都能用")),
                  ("alert", tr("需要云游戏时长；锄大地和模拟宇宙要有窗口才能运行"))),
        "adb": (("check", tr("用数据线或网络连接手机、模拟器，手机屏幕可以照常使用")),
                ("alert", tr("只支持清体力、每日实训、领取奖励和历战余响")),
                ("alert", tr("需要安卓 10 以上、国服客户端，并打开 USB 调试"))),
    }.get(value, ())


QUICK_TIMES = ("04:10", "08:00", "12:30", "22:00")
STEP_ICONS = {"run_mode": "FIF.CONNECT", "game": "FIF.GAME", "tasks": "FIF.CHECKBOX", "schedule": "FIF.HISTORY",
              "notify": "FIF.RINGER"}


class Step(QWidget):
    """标题、说明、可以滚动的内容和出错提示。"""
    poseChanged = Signal()
    nextChanged = Signal()

    def __init__(self, dialog):
        super().__init__(dialog.panel)
        self.dialog, self.model = dialog, dialog.model
        self.titleLabel = SubtitleLabel(self)
        setFont(self.titleLabel, 24, QFont.Weight.DemiBold)
        self.titleLabel.setWordWrap(True)
        self.leadLabel = secondary(BodyLabel(self))
        self.leadLabel.setWordWrap(True)
        self.scroll = ScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.enableTransparentBackground()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view = QWidget()
        self.view.setObjectName("view")
        self.scroll.setWidget(self.view)
        self.view.setStyleSheet("#view{background: transparent}")
        self.body = QVBoxLayout(self.view)
        self.body.setContentsMargins(0, 0, 28, 8)
        self.body.setSpacing(12)
        self.errorStrip = NoticeStrip(self, kind="error")
        self.errorStrip.hide()
        head = QVBoxLayout()
        head.setContentsMargins(0, 0, 60, 0)
        head.setSpacing(4)
        head.addWidget(self.titleLabel)
        head.addWidget(self.leadLabel)
        error = QHBoxLayout()
        error.setContentsMargins(0, 0, 28, 0)
        error.addWidget(self.errorStrip)
        self.errorRow = error
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(head)
        layout.addSpacing(12)
        layout.addWidget(self.scroll, 1)
        layout.addLayout(error)

    def setHeading(self, title, lead):
        self.titleLabel.setText(title)
        self.leadLabel.setText(lead)
        self.leadLabel.setVisible(bool(lead))

    def showError(self, text):
        self.errorStrip.setKind("error", is_evernight())
        self.errorStrip.setText(text)
        self.errorStrip.setVisible(bool(text))
        self.errorRow.setContentsMargins(0, 8 if text else 0, 28, 12 if text else 0)

    def enter(self):
        """每次走到这一步时调用。"""

    def leave(self):
        """点「下一步」时保存。返回 (成功, 说明)。"""
        return True, ""

    def pose(self):
        return Mascot.OK

    def nextText(self):
        return tr("下一步")

    def nextEnabled(self):
        return True


def outcome(result):
    return result.ok, result.text


class RunModeStep(Step):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.setHeading(tr("游戏在哪里运行？"), tr("以后可以在「设置 › 运行方式」更换。"))
        self.cards = {}
        row = QHBoxLayout()
        row.setSpacing(10)
        for option in self.model.backends():
            card = Choice(option, self.view)
            card.setMinimumHeight(148)
            card.clicked.connect(self._select)
            row.addWidget(card, 1)
            self.cards[option.value] = card
        self.noteTitle = StrongBodyLabel(self.view)
        self.notes = Notes(self.view)
        self.body.addLayout(row)
        self.body.addSpacing(6)
        self.body.addWidget(self.noteTitle)
        self.body.addWidget(self.notes)
        self.body.addStretch(1)
        self._value = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fitTags()

    def _fitTags(self):
        """有的语言标签很长，三张卡放不下时从最宽的那张起少显示一个标签，不让卡片超出右边距。"""
        cards = list(self.cards.values())
        for card in cards:
            for pill in card.tags:
                pill.show()
            card.layout().activate()
        room = self.width() - 28 - 28
        while sum(card.minimumSizeHint().width() for card in cards) + 10 * (len(cards) - 1) > room:
            tags = {card: [pill for pill in card.tags if not pill.isHidden()] for card in cards}
            widest = max((card for card in cards if len(tags[card]) > 1), key=lambda card: card.minimumSizeHint().width(), default=None)
            if widest is None:
                break
            tags[widest][-1].hide()
            widest.layout().activate()

    def enter(self):
        if self._value is None:
            value = self.model.backend()
            card = self.cards.get(value)
            if card is None or not card.option.available:
                value = next((v for v, c in self.cards.items() if c.option.available), value)
            self._select(value)

    def value(self):
        return self._value

    def _select(self, value):
        self._value = value
        for key, card in self.cards.items():
            card.setSelected(key == value)
        self.noteTitle.setText(self.cards[value].option.name if value in self.cards else "")
        self.notes.setNotes(mode_notes(value))
        self.showError("")
        self.poseChanged.emit()

    def pose(self):
        return Mascot.CLOUD if self._value == "cloud" else Mascot.OK

    def leave(self):
        return outcome(self.model.set_backend(self._value))


class LocalGame(QWidget):
    """本地客户端：自动找到的位置、手动选择和运行前要确认的事。"""
    changed = Signal()

    def __init__(self, step):
        super().__init__(step.view)
        self.model = step.model
        self._path = ""
        self._epic = False
        self._manual = None
        self._touched = False
        self.rows = []
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.searchCard = SimpleCardWidget(self)
        self.searchCard.setBorderRadius(8)
        self.ring = IndeterminateProgressRing(self.searchCard)
        self.ring.setFixedSize(28, 28)
        self.ring.setStrokeWidth(3)
        self.searchLabel = BodyLabel(tr("正在查找游戏…"), self.searchCard)
        inner = QHBoxLayout(self.searchCard)
        inner.setContentsMargins(20, 18, 20, 18)
        inner.setSpacing(14)
        inner.addWidget(self.ring)
        inner.addWidget(self.searchLabel, 1)
        self.missing = NoticeStrip(self, kind="warning")
        self.listLayout = QVBoxLayout()
        self.listLayout.setSpacing(8)
        self.browseButton = PushButton(FluentIcon.FOLDER, tr("选择其他位置"), self)
        self.browseButton.clicked.connect(self._browse)
        self.retryButton = PushButton(FluentIcon.SYNC, tr("重新查找"), self)
        self.retryButton.clicked.connect(self._retry)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.browseButton)
        buttons.addWidget(self.retryButton)
        buttons.addStretch(1)
        self.epicGroup = Group(self)
        self.epicSwitch = bare_switch(self.epicGroup)
        self.epicSwitch.checkedChanged.connect(self._epicChanged)
        self.epicRow = self.epicGroup.addRow(FieldRow(
            tr("通过 Epic 启动"), tr("Epic 渠道版需要从 Epic 启动，请提前在 Epic 里登录"), self.epicSwitch, self.epicGroup))
        self.noteTitle = StrongBodyLabel(tr("运行前请确认"), self)
        self.notes = Notes(self)
        self.notes.setNotes((("dot", tr("游戏已经登录过一次，能正常进入")),
                             ("dot", tr("游戏语言是简体中文")),
                             ("dot", tr("关闭 HDR、N 卡滤镜、帧率显示和微星小飞机等悬浮窗"))))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.searchCard)
        layout.addWidget(self.missing)
        layout.addLayout(self.listLayout)
        layout.addLayout(buttons)
        layout.addWidget(self.epicGroup)
        layout.addSpacing(4)
        layout.addWidget(self.noteTitle)
        layout.addWidget(self.notes)
        layout.addStretch(1)
        self.model.searchFinished.connect(self._searched)

    def enter(self):
        if not self._touched:
            game = self.model.game()
            self._path, self._epic = (game.path, game.epic) if game else ("", False)
        if not self.model.candidates() and not self.model.searching():
            self.model.search_game()
        self._pickFirst()
        self.refresh()

    def _retry(self):
        self.model.search_game()
        self.refresh()

    def _searched(self):
        self._pickFirst()
        self.refresh()

    def _pickFirst(self):
        """没有能用的当前设置时，直接选中找到的第一个。"""
        found = self.model.candidates()
        if found and not self._path and not self._touched:
            self._path, self._epic = found[0].path, found[0].epic

    def candidates(self):
        items = list(self.model.candidates())
        if self._manual is not None and all(item.path != self._manual.path for item in items):
            items.append(self._manual)
        return items

    def refresh(self):
        searching = self.model.searching()
        items = self.candidates()
        self.searchCard.setVisible(searching)
        self.ring.setVisible(searching)
        self.retryButton.setEnabled(not searching)
        self.missing.setKind("warning", is_evernight())
        self.missing.setText(tr("没有自动找到游戏，请选择安装目录里的 StarRail.exe。也可以先跳过，以后在「设置 › 运行方式」设置。"))
        self.missing.setVisible(not searching and not items)
        for row in self.rows:
            self.group.removeButton(row)
            self.listLayout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        for item in items:
            row = CandidateRow(item, self)
            row.setChecked(item.path == self._path)
            row.clicked.connect(lambda _=False, chosen=item: self._choose(chosen))
            self.group.addButton(row)
            self.listLayout.addWidget(row)
            row.show()
            self.rows.append(row)
        self._refreshEpic()
        self.changed.emit()

    def _refreshEpic(self):
        chosen = next((item for item in self.candidates() if item.path == self._path), None)
        self.epicGroup.setVisible(bool(chosen and (chosen.epic or self._epic)))
        self.epicSwitch.blockSignals(True)
        self.epicSwitch.setChecked(self._epic)
        self.epicSwitch.blockSignals(False)

    def _choose(self, item):
        self._touched = True
        self._path, self._epic = item.path, item.epic
        self._refreshEpic()
        self.changed.emit()

    def _epicChanged(self, on):
        self._touched = True
        self._epic = on

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self.window(), tr("选择 StarRail.exe"), self._path,
                                              tr("可执行文件 (*.exe)"))
        if not path:
            return
        item = self.model.inspect(path)
        problem = self.model.check_game(item.path)
        if problem:
            self.missing.setKind("error", is_evernight())
            self.missing.setText(problem)
            self.missing.show()
            return
        self._manual = item
        self._choose(item)
        self.refresh()

    def path(self):
        return self._path

    def searching(self):
        return self.model.searching()

    def leave(self):
        if not self._path:
            return True, ""
        return outcome(self.model.set_game(self._path, self._epic))


class CloudGame(QWidget):
    def __init__(self, step):
        super().__init__(step.view)
        self.model = step.model
        self._touched = False
        self.group = Group(self)
        self.browserCombo = ComboBox(self.group)
        self.browserCombo.setMinimumWidth(240)
        self.headlessSwitch = bare_switch(self.group)
        self.group.addRow(FieldRow(tr("浏览器"), tr("集成浏览器会在第一次运行时自动下载，效果最好"), self.browserCombo, self.group))
        self.group.addRow(FieldRow(tr("无窗口运行"), tr("在后台运行，看不到画面；锄大地和模拟宇宙不支持"), self.headlessSwitch, self.group))
        self.noteTitle = StrongBodyLabel(tr("第一次运行"), self)
        self.notes = Notes(self)
        self.notes.setNotes((("dot", tr("小助手会打开浏览器，请在里面登录米哈游账号，之后会记住登录")),
                             ("dot", tr("无窗口运行时如果没有登录，会自动换成有窗口让你登录")),
                             ("dot", tr("需要有云游戏时长，高峰期可能要排队"))))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.group)
        layout.addSpacing(4)
        layout.addWidget(self.noteTitle)
        layout.addWidget(self.notes)
        layout.addStretch(1)
        self.browserCombo.currentIndexChanged.connect(self._mark)
        self.headlessSwitch.checkedChanged.connect(self._mark)

    def _mark(self, *_):
        self._touched = True

    def enter(self):
        if self._touched:
            return
        view = self.model.cloud()
        for widget in (self.browserCombo, self.headlessSwitch):
            widget.blockSignals(True)
        self.browserCombo.clear()
        for value, text in view.browsers:
            self.browserCombo.addItem(text, userData=value)
        self.browserCombo.setCurrentIndex(max(0, self.browserCombo.findData(view.browser)))
        self.headlessSwitch.setChecked(view.headless)
        for widget in (self.browserCombo, self.headlessSwitch):
            widget.blockSignals(False)

    def leave(self):
        return outcome(self.model.set_cloud(self.browserCombo.currentData(), self.headlessSwitch.isChecked()))


class AndroidGame(QWidget):
    """设备列表和环境检查沿用设置页的卡片。"""

    def __init__(self, step):
        super().__init__(step.view)
        from app.card.adb_setting_cards import AdbDeviceCard, AdbEnvironmentCard
        from app.content.backend import block_while_running
        self.deviceCard = AdbDeviceCard(parent=self)
        self.environmentCard = AdbEnvironmentCard(
            blocker=lambda: block_while_running(step.dialog, tr("环境检查会占用设备，请等任务结束后再检查")), parent=self)
        self.notes = Notes(self)
        self.notes.setNotes((("dot", tr("手机：在开发者选项打开 USB 调试，用数据线连接后允许调试")),
                             ("dot", tr("模拟器：填地址后点「连接」，MuMu 默认是 127.0.0.1:16384")),
                             ("dot", tr("请先在设备上安装国服客户端并登录一次"))))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.deviceCard)
        layout.addWidget(self.environmentCard)
        layout.addSpacing(6)
        layout.addWidget(self.notes)
        layout.addStretch(1)

    def enter(self):
        self.deviceCard.refreshIfNeeded()

    def leave(self):
        return True, ""


class GameStep(Step):
    PAGES = {"local": LocalGame, "cloud": CloudGame, "adb": AndroidGame}

    def __init__(self, dialog):
        super().__init__(dialog)
        self.pages = {}
        self._backend = None

    def title(self):
        return {"cloud": tr("准备云游戏"), "adb": tr("连接设备")}.get(self.model.backend(), tr("找到游戏"))

    def enter(self):
        self._backend = backend = self.model.backend()
        if backend == "cloud":
            self.setHeading(tr("准备云游戏"), tr("云·星穹铁道在浏览器里运行，登录一次就能一直用。"))
        elif backend == "adb":
            self.setHeading(tr("连接设备"), tr("连接要运行游戏的手机或模拟器。"))
        else:
            self.setHeading(tr("游戏安装在哪里？"), tr("小助手需要知道 StarRail.exe 的位置，才能替你启动游戏。"))
        if backend not in self.pages:
            page = self.PAGES[backend](self)
            self.pages[backend] = page
            self.body.addWidget(page)
            if isinstance(page, LocalGame):
                page.changed.connect(self._changed)
        for key, page in self.pages.items():
            page.setVisible(key == backend)
        self.page().enter()
        self._changed()

    def page(self):
        return self.pages.get(self._backend)

    def _changed(self):
        self.showError("")
        self.poseChanged.emit()
        self.nextChanged.emit()

    def pose(self):
        return {"local": Mascot.VIEWFINDER, "cloud": Mascot.CLOUD}.get(self._backend, Mascot.SEARCH)

    def nextText(self):
        page = self.page()
        if isinstance(page, LocalGame) and not page.path() and not page.searching():
            return tr("先跳过")
        return tr("下一步")

    def nextEnabled(self):
        page = self.page()
        return not (isinstance(page, LocalGame) and page.searching() and not page.path())

    def leave(self):
        return self.page().leave()


class TasksStep(Step):
    def __init__(self, dialog):
        super().__init__(dialog)
        self._draft = None
        self._instance = None
        self._shown = None
        self._touched = False
        self.tiles = {}
        self.chips = {}
        self.accountLabel = ElidedLabel(self.view, size=12)
        self.accountLabel.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        presets = QHBoxLayout()
        presets.setSpacing(8)
        self.presetLabel = secondary(BodyLabel(tr("快速选择"), self.view))
        presets.addWidget(self.presetLabel)
        for key, text in self.model.presets():
            chip = Chip(text, self.view, soft=True)
            chip.setAccessibleName(text)
            chip.clicked.connect(lambda _=False, preset=key: self._applyPreset(preset))
            self.chips[key] = chip
            presets.addWidget(chip)
        presets.addWidget(self.accountLabel, 1)
        self.grid = QGridLayout()
        self.grid.setSpacing(8)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.estimateStrip = NoticeStrip(self.view, kind="info")
        self.body.setSpacing(10)
        self.body.addLayout(presets)
        self.body.addLayout(self.grid)
        self.body.addWidget(self.estimateStrip)
        self.body.addStretch(1)

    def enter(self):
        self.setHeading(tr("每天想让小助手做什么？"),
                        tr("打开的项目会加入「完整运行」，已经做完的会自动跳过。之后可以在「任务」页细调。"))
        tasks = self.model.tasks()
        ids = tuple(task.id for task in tasks)
        # 换了运行方式，能选的任务变了；还没改过就按新的重新给默认值。
        if self._draft is None or ids != self._shown and not self._touched:
            self._draft = frozenset(self.model.initial_tasks())
            self._instance = self.model.instance()
        if ids != self._shown:
            self._build(tasks)
        self.accountLabel.setFullText(self.model.account_note())
        color = style.link()
        self.accountLabel.setTextColor(color, color)
        self._refresh()

    def _build(self, tasks):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            widget.hide()
            widget.deleteLater()
        self.tiles = {}
        cell = 0
        for task in tasks:
            if task.id == "power":
                tile = PowerTile(task, self.view)
                tile.setInstances(self.model.instances(), self._instance, self.model.instance_names())
                tile.setNote(self.model.instance_note())
                tile.instanceChanged.connect(self._instanceChanged)
                self.grid.addWidget(tile, 0, 0, 1, 2)
            else:
                tile = TaskTile(task, self.view)
                self.grid.addWidget(tile, 1 + cell // 2, cell % 2)
                cell += 1
            tile.toggled.connect(self._toggled)
            self.tiles[task.id] = tile
        self._shown = tuple(task.id for task in tasks)

    def _refresh(self):
        for key, tile in self.tiles.items():
            tile.setChecked(key in self._draft)
        shown = self._draft & frozenset(self.tiles)
        current = self.model.match_preset(shown)
        for key, chip in self.chips.items():
            chip.setChecked(key == current)
        self.estimateStrip.setKind("info", is_evernight())
        self.estimateStrip.setText(self.model.estimate(shown))

    def _applyPreset(self, preset):
        self._touched = True
        hidden = self._draft - frozenset(self.tiles)
        self._draft = frozenset(self.model.preset_tasks(preset)) | hidden
        self._refresh()

    def _toggled(self, task_id, on):
        self._touched = True
        self._draft = self._draft | {task_id} if on else self._draft - {task_id}
        self._refresh()

    def _instanceChanged(self):
        self._touched = True
        self._instance = self.tiles["power"].instance()

    def pose(self):
        return Mascot.SERIOUS

    def leave(self):
        return outcome(self.model.save_tasks(self._draft & frozenset(self.tiles), self._instance))


class ScheduleStep(Step):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.setHeading(tr("什么时候运行？"), tr("可以自己点，也可以让小助手按时开始。"))
        self._draft = None
        self._afters = {}
        self.info = self.model.run_info()
        self.cards = {}
        options = [SimpleNamespace(value="manual", name=tr("我自己点开始"), icon="FIF.PLAY", available=True,
                                   description=tr("打开小助手，点总览的「开始完整运行」。")),
                   SimpleNamespace(value="daily", name=tr("每天定时运行"), icon="FIF.HISTORY", available=True,
                                   description=tr("到点自动开始，需要小助手保持打开。"))]
        if self.info.login_supported:
            options.append(SimpleNamespace(value="login", name=tr("登录 Windows 后运行"), icon="FIF.POWER_BUTTON", available=True,
                                           description=tr("每次登录后自动打开小助手，开始完整运行。")))
        row = QHBoxLayout()
        row.setSpacing(10)
        for option in options:
            card = Choice(option, self.view)
            card.setMinimumHeight(96)
            card.clicked.connect(self._select)
            row.addWidget(card, 1)
            self.cards[option.value] = card
        self.group = Group(self.view)
        self.timePicker = TimePicker(self.group)
        self.timePicker.timeChanged.connect(self._timeChanged)
        self.timeChips = {}
        times = QWidget(self.group)
        timeRow = QHBoxLayout(times)
        timeRow.setContentsMargins(0, 0, 0, 0)
        timeRow.setSpacing(6)
        for text in QUICK_TIMES:
            chip = Chip(text, times, soft=True)
            chip.clicked.connect(lambda _=False, value=text: self._setTime(value))
            self.timeChips[text] = chip
            timeRow.addWidget(chip)
        timeRow.addSpacing(6)
        timeRow.addWidget(self.timePicker)
        self.timeRow = self.group.addRow(FieldRow(tr("开始时间"), tr("每天，按电脑时间"), times, self.group))
        self.loginSwitch = bare_switch(self.group)
        self.loginSwitch.checkedChanged.connect(self._loginChanged)
        self.loginRow = self.group.addRow(FieldRow(tr("登录 Windows 后自动打开小助手"), tr("最小化到托盘，不会忘记打开"),
                                                   self.loginSwitch, self.group))
        self.afterCombo = ComboBox(self.group)
        self.afterCombo.setMinimumWidth(180)
        self.afterCombo.currentIndexChanged.connect(self._afterChanged)
        self.afterRow = self.group.addRow(FieldRow(tr("跑完之后"), "", self.afterCombo, self.group))
        self.refreshCombo = ComboBox(self.group)
        self.refreshCombo.setMinimumWidth(120)
        for hour in range(24):
            self.refreshCombo.addItem(f"{hour:02d}:00", userData=hour)
        self.refreshCombo.currentIndexChanged.connect(self._refreshChanged)
        self.refreshRow = self.group.addRow(FieldRow(
            tr("游戏每日刷新时间"), tr("国际服各服务器不同，请换算成电脑时间，用来判断今天做没做完"), self.refreshCombo, self.group))
        self.hint = NoticeStrip(self.view, kind="info")
        self.body.addLayout(row)
        self.body.addWidget(self.group)
        self.body.addWidget(self.hint)
        self.body.addStretch(1)

    def enter(self):
        if self._draft is None:
            self._draft = self.model.run_plan()
            self._afters = {self._draft.mode: self._draft.after}
        self.info = self.model.run_info()
        if self._draft.mode not in self.cards:
            self._draft = replace(self._draft, mode="manual")
        self._fill()

    def _fill(self):
        plan = self._draft
        for key, card in self.cards.items():
            card.setSelected(key == plan.mode)
        daily = plan.mode == "daily"
        self.group.setRowVisible(self.timeRow, daily)
        self.group.setRowVisible(self.loginRow, daily and self.info.login_supported)
        self.group.setRowVisible(self.refreshRow, self.info.show_refresh)
        for widget in (self.timePicker, self.loginSwitch, self.afterCombo, self.refreshCombo):
            widget.blockSignals(True)
        self.timePicker.setTime(QTime.fromString(plan.time, "HH:mm"))
        self.loginSwitch.setChecked(plan.open_at_login)
        self.afterCombo.clear()
        for value, text in self.model.after_options(plan.mode):
            self.afterCombo.addItem(text, userData=value)
        self.afterCombo.setCurrentIndex(max(0, self.afterCombo.findData(plan.after)))
        self.refreshCombo.setCurrentIndex(max(0, self.refreshCombo.findData(plan.refresh_hour)))
        for widget in (self.timePicker, self.loginSwitch, self.afterCombo, self.refreshCombo):
            widget.blockSignals(False)
        for text, chip in self.timeChips.items():
            chip.setChecked(text == plan.time)
        hint = {"daily": tr("定时运行需要小助手保持打开，可以最小化到托盘；电脑不能睡眠。"),
                "login": tr("登录后大约半分钟开始，小助手会最小化到托盘。今天已经做完的任务会自动跳过。")}.get(plan.mode, "")
        if plan.mode == "daily" and self.info.other_schedules:
            hint = tr("{hint}另外还有 {count} 个启用的定时计划，可以在「运行」页调整。").format(hint=hint, count=self.info.other_schedules)
        self.hint.setKind("info", is_evernight())
        self.hint.setText(hint)
        self.hint.setVisible(bool(hint))
        self.showError("")

    def _change(self, **values):
        self._draft = replace(self._draft, **values)

    def _select(self, mode):
        if mode == self._draft.mode:
            return
        # 「跑完之后」在每种方式里是不同的设置：换回来时用刚才选的，第一次选用那种方式现在的值。
        self._afters[self._draft.mode] = self._draft.after
        self._change(mode=mode, after=self._afters.get(mode, self.model.after_value(mode)))
        self._fill()

    def _setTime(self, text):
        self._change(time=text)
        self._fill()

    def _timeChanged(self, time):
        self._change(time=time.toString("HH:mm"))
        self._fill()

    def _loginChanged(self, on):
        self._change(open_at_login=on)

    def _afterChanged(self, index):
        self._change(after=self.afterCombo.itemData(index))

    def _refreshChanged(self, index):
        self._change(refresh_hour=self.refreshCombo.itemData(index))

    def pose(self):
        return Mascot.FULL

    def leave(self):
        result = self.model.save_run_plan(self._draft)
        if result.ok:
            self._draft = None
        return outcome(result)


class NotifyStep(Step):
    def __init__(self, dialog):
        super().__init__(dialog)
        from app.pages.notify import ChannelPanel
        self.setHeading(tr("做完了怎么通知你？"),
                        tr("任务完成或失败时告诉你。可以跳过，以后在「设置 › 消息推送」添加。"))
        self.panel = ChannelPanel(dialog, self.model.notify_model(), self.view)
        self.body.addWidget(self.panel)
        self.body.addStretch(1)

    def enter(self):
        self.panel.refresh()

    def pose(self):
        return Mascot.WAVE

    def nextText(self):
        return tr("完成设置")


class SummaryLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(52)
        self.tile = IconTile(self, size=32, icon_size=16)
        self.titleLabel = secondary(CaptionLabel(self))
        self.textLabel = ElidedLabel(self, size=14)
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(1)
        texts.addStretch(1)
        texts.addWidget(self.titleLabel)
        texts.addWidget(self.textLabel)
        texts.addStretch(1)
        self.editButton = LinkButton(tr("修改"), self, size=13)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(14)
        layout.addWidget(self.tile)
        layout.addLayout(texts, 1)
        layout.addWidget(self.editButton)

    def setRow(self, row):
        self.tile.setIcon(icon_of(STEP_ICONS.get(row.step)), "accent" if row.kind == "success" else "neutral",
                          evernight=is_evernight())
        self.titleLabel.setText(row.title)
        self.textLabel.setFullText(row.text)
        color = style.status_line("warning") if row.kind == "warning" else style.primary()
        self.textLabel.setTextColor(color, color)
        self.editButton.setEvernight(is_evernight())


class DonePage(Step):
    editRequested = Signal(int)
    linkClicked = Signal(str)

    def __init__(self, dialog):
        super().__init__(dialog)
        self.setHeading(tr("设置好了"), tr("接下来点「开始完整运行」就可以，以后改主意随时再调。"))
        self.card = SimpleCardWidget(self.view)
        self.card.setBorderRadius(8)
        self.column = QVBoxLayout(self.card)
        self.column.setContentsMargins(0, 2, 0, 2)
        self.column.setSpacing(0)
        self.lines = []
        for index, step in enumerate(self.model.STEPS):
            if index:
                self.column.addWidget(Divider(self.card, inset=16))
            line = SummaryLine(self.card)
            line.editButton.clicked.connect(lambda _=False, i=index: self.editRequested.emit(i))
            self.column.addWidget(line)
            self.lines.append(line)
        self.moreLabel = secondary(BodyLabel(tr("还想多了解一点？"), self.view))
        more = QHBoxLayout()
        more.setSpacing(18)
        more.addWidget(self.moreLabel)
        self.links = []
        for text, link in ((tr("细调每个任务"), "task:power"), (tr("边挂机边用电脑"), "doc:Background"),
                           (tr("使用教程"), "doc:Tutorial")):
            button = LinkButton(text, self.view, size=13)
            button.clicked.connect(lambda _=False, target=link: self.linkClicked.emit(target))
            more.addWidget(button)
            self.links.append(button)
        more.addStretch(1)
        self.body.addWidget(self.card)
        self.body.addSpacing(2)
        self.body.addLayout(more)
        self.body.addStretch(1)

    def enter(self):
        for line, row in zip(self.lines, self.model.summary()):
            line.setRow(row)
        for button in self.links:
            button.setEvernight(is_evernight())

    def pose(self):
        return Mascot.STAMP

    def nextText(self):
        return tr("完成")
