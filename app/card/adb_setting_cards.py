# coding:utf-8
"""设置页的 ADB 卡片：设备后端、设备面板、环境检查、运行状态和高级设置。"""
import os
import sys

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import QButtonGroup, QFileDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget
from qfluentwidgets import (BodyLabel, CaptionLabel, ComboBox, ExpandSettingCard, FluentIcon as FIF, IconWidget,
                            InfoBarIcon, LineEdit, PushButton, RadioButton, SettingCard)
from qfluentwidgets.components.settings.expand_setting_card import GroupSeparator

from app.common.icon import UiIcon
from app.components.ascii_spin_box import AsciiSpinBox
from app.tools import adb_service
from module.config import cfg
from module.game.adb_status import read_status
from module.game.adb_transport import AdbError
from module.localization import tr
from utils.desktop_twin import in_desktop_twin
from .messagebox_custom import MessageBoxEdit


_STATUS_ICONS = {
    adb_service.PASS: InfoBarIcon.SUCCESS,
    adb_service.WARN: InfoBarIcon.WARNING,
    adb_service.FAIL: InfoBarIcon.ERROR,
}


class AdbWorker(QThread):
    """在后台线程执行一次 ADB 调用。函数收到的参数是进度回调。"""

    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str, str)

    def __init__(self, function, parent=None):
        super().__init__(parent)
        self._function = function

    def run(self):
        try:
            result = self._function(self.progress.emit)
        except AdbError as error:
            self.failed.emit(error.code, str(error))
        except Exception as error:
            self.failed.emit("unknown", str(error))
        else:
            self.succeeded.emit(result)


def _caption(text="", parent=None):
    label = CaptionLabel(text, parent)
    label.setWordWrap(True)
    label.setTextColor("#606060", "#d2d2d2")
    return label


def _status_icon(parent=None):
    icon = IconWidget(InfoBarIcon.INFORMATION, parent)
    icon.setFixedSize(16, 16)
    return icon


class AdbBackendSettingCard(SettingCard):
    """设备后端三选一。本地和云游戏沿用旧开关，ADB 写入显式后端和触屏形态。"""

    backendChanged = Signal(str)

    def __init__(self, parent=None, *, blocker=None):
        super().__init__(FIF.CONNECT, tr("设备后端"),
                         tr("选择小助手操作哪里的游戏，对下一次运行的任务生效"), parent)
        self._blocker = blocker
        self.comboBox = ComboBox(self)
        self.comboBox.setMinimumWidth(190)
        if sys.platform == "win32":
            self.comboBox.addItem(tr("本地游戏"), userData="local")
        self.comboBox.addItem(tr("云·星穹铁道"), userData="cloud")
        self.comboBox.addItem(tr("Android 设备（ADB）"), userData="adb")
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

        self._backend = adb_service.current_backend()
        self.setBackend(self._backend)
        # 桌面分身固定使用本地后端，在分身里改动会影响主程序的配置。
        self.comboBox.setEnabled(not in_desktop_twin())
        self.comboBox.currentIndexChanged.connect(self._onCurrentIndexChanged)

    def backend(self):
        return self._backend

    def setBackend(self, backend):
        """只更新显示，不写配置。"""
        self._backend = backend
        index = self.comboBox.findData(backend)
        if index >= 0 and index != self.comboBox.currentIndex():
            self.comboBox.blockSignals(True)
            try:
                self.comboBox.setCurrentIndex(index)
            finally:
                self.comboBox.blockSignals(False)

    def _onCurrentIndexChanged(self, index):
        backend = self.comboBox.itemData(index)
        if backend == self._backend:
            return
        if self._blocker is not None and self._blocker(backend):
            self.setBackend(self._backend)
            return
        changes = adb_service.backend_changes(backend)
        if changes:
            cfg.set_values(changes)
        self._backend = backend
        self.backendChanged.emit(backend)


class _PanelCard(ExpandSettingCard):
    """内容会变化的可展开卡片。内容区高度按当前宽度计算，变化后通知设置页重算高度。"""

    expandStateChanged = Signal(bool)

    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)
        self.body = QWidget(self.view)
        self.bodyLayout = QVBoxLayout(self.body)
        self.bodyLayout.setContentsMargins(0, 0, 0, 0)
        self.bodyLayout.setSpacing(0)
        self.viewLayout.addWidget(self.body)
        self._rows = []
        self.expandAni.finished.connect(self._onExpandFinished)

    def setContent(self, content):
        self.card.setContent(content)

    def _addRow(self, row):
        if self._rows:
            separator = GroupSeparator(self.body)
            self.bodyLayout.addWidget(separator)
            separator.show()
            row._separator = separator
        self.bodyLayout.addWidget(row)
        # 页面显示之后新建的控件要等事件循环才会显示，隐藏的控件在布局里不占高度。
        row.show()
        self._rows.append(row)
        return row

    def _clearRows(self):
        for row in self._rows:
            for widget in (getattr(row, "_separator", None), row):
                if widget is not None:
                    self.bodyLayout.removeWidget(widget)
                    widget.hide()
                    widget.deleteLater()
        self._rows = []

    def _setRowVisible(self, row, visible):
        row.setVisible(visible)
        separator = getattr(row, "_separator", None)
        if separator is not None:
            separator.setVisible(visible)

    def syncHeight(self):
        """内容变化后调用。"""
        width = self.width() if self.width() > 0 else 800
        before = self.height()
        self.bodyLayout.activate()
        if self.bodyLayout.hasHeightForWidth():
            height = self.bodyLayout.heightForWidth(width)
        else:
            height = self.bodyLayout.sizeHint().height()
        if height != self.body.height() or self.body.minimumHeight() != height:
            self.body.setFixedHeight(height)
        self.viewLayout.activate()
        self._adjustViewSize()
        if self.isExpand and self.expandAni.state() != self.expandAni.State.Running:
            self.setFixedHeight(self.card.height() + self.viewLayout.sizeHint().height())
            # 不在当前分页时不打扰设置页：切回本页时它会重新计算高度。
            if self.height() != before and self.isVisible():
                self.expandStateChanged.emit(False)

    def setExpand(self, isExpand):
        if self.isExpand == isExpand:
            return
        if isExpand:
            self.syncHeight()
            self.expandStateChanged.emit(True)
        super().setExpand(isExpand)

    def _onExpandFinished(self):
        if not self.isExpand:
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
            self.setFixedHeight(self.card.height())
        self.expandStateChanged.emit(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            QTimer.singleShot(0, self._syncAfterResize)

    def _syncAfterResize(self):
        try:
            self.syncHeight()
        except RuntimeError:
            pass  # 设置页重建后旧卡片已销毁


class _Row(QWidget):
    """卡片内容区的一行：左侧可选控件，中间标题和说明，右侧可选控件。"""

    def __init__(self, parent=None, leading=None):
        super().__init__(parent)
        self.hBoxLayout = QHBoxLayout(self)
        self.hBoxLayout.setContentsMargins(48, 10, 24, 10)
        self.hBoxLayout.setSpacing(12)
        if leading is not None:
            self.hBoxLayout.addWidget(leading, 0, Qt.AlignmentFlag.AlignTop)
        self.textLayout = QVBoxLayout()
        self.textLayout.setContentsMargins(0, 0, 0, 0)
        self.textLayout.setSpacing(2)
        self.hBoxLayout.addLayout(self.textLayout, 1)

    def addText(self, label):
        self.textLayout.addWidget(label)
        return label


def device_type_text(device_type):
    return {"physical": tr("实体机"), "emulator": tr("模拟器")}.get(device_type, "")


def device_state_text(state):
    return {
        "unauthorized": tr("未授权 USB 调试"),
        "offline": tr("离线"),
        "authorizing": tr("等待授权"),
        "no permissions": tr("没有访问权限"),
    }.get(state, state)


def device_summary(device):
    """设备行的说明文字：序列号、系统版本、设备类型和需要处理的状态。"""
    parts = [tr("序列号 {serial}").format(serial=device.serial)]
    if device.android_version:
        parts.append(f"Android {device.android_version}")
    if device.device_type:
        parts.append(device_type_text(device.device_type))
    if device.state != "device":
        parts.append(device_state_text(device.state))
    return " · ".join(parts)


class AdbDeviceCard(_PanelCard):
    """列出 ADB 设备，支持刷新、选择和手动输入网络地址。"""

    serialChanged = Signal(object)

    def __init__(self, parent=None, *, list_devices=None, connect_device=None):
        super().__init__(UiIcon.PHONE, tr("Android 设备"), tr("自动选择"), parent)
        self._list_devices = list_devices or adb_service.list_devices
        self._connect_device = connect_device or adb_service.connect_device
        self._devices = []
        self._message = (tr("点“刷新”查找已连接的设备"), "")
        self._worker = None
        self._loaded = False
        self._group = QButtonGroup(self)
        self._group.buttonClicked.connect(self._onDeviceClicked)

        self.refreshButton = QPushButton(tr("刷新"), self)
        self.refreshButton.setObjectName("pushButton")
        self.card.addWidget(self.refreshButton)
        self.refreshButton.clicked.connect(self.refresh)

        # 手动连接放在列表之外，刷新列表时保留输入内容。
        self.connectRow = _Row(self.body)
        self.addressEdit = LineEdit(self.connectRow)
        self.addressEdit.setPlaceholderText(tr("模拟器地址，例如 {address}").format(address=adb_service.MUMU_ADDRESS))
        self.addressEdit.setClearButtonEnabled(True)
        self.addressEdit.setMinimumWidth(260)
        self.connectButton = PushButton(tr("连接"), self.connectRow)
        self.connectRow.addText(BodyLabel(tr("手动连接"), self.connectRow))
        self.connectRow.addText(_caption(tr("模拟器和无线调试需要输入地址。MuMu 默认是 127.0.0.1:16384"), self.connectRow))
        self.connectRow.hBoxLayout.addWidget(self.addressEdit, 0, Qt.AlignmentFlag.AlignVCenter)
        self.connectRow.hBoxLayout.addWidget(self.connectButton, 0, Qt.AlignmentFlag.AlignVCenter)
        self.connectButton.clicked.connect(self._onConnectClicked)
        self.addressEdit.returnPressed.connect(self._onConnectClicked)

        self._rebuild()
        self.setExpand(True)
        self.expandAni.setCurrentTime(self.expandAni.duration())

    def showEvent(self, event):
        super().showEvent(event)
        # 已在使用 ADB 后端时，第一次打开页面自动查找设备。
        if not self._loaded and adb_service.current_backend() == "adb":
            QTimer.singleShot(0, self.refreshIfNeeded)

    # ---- 状态 ----
    def selectedSerial(self):
        serial = cfg.get_value("adb_serial")
        return str(serial).strip() if serial else None

    def isBusy(self):
        return self._worker is not None and self._worker.isRunning()

    def refreshIfNeeded(self):
        if not self._loaded and not self.isBusy():
            self.refresh()

    # ---- 刷新 ----
    def refresh(self):
        if self.isBusy():
            return
        self._setBusy(True)
        self._start(lambda _progress: self._list_devices(), self._onDevicesListed, self._onListFailed)

    def _start(self, function, on_success, on_failure):
        worker = AdbWorker(function, self)
        worker.succeeded.connect(on_success)
        worker.failed.connect(on_failure)
        worker.finished.connect(lambda: self._setBusy(False))
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _setBusy(self, busy):
        self.refreshButton.setEnabled(not busy)
        self.connectButton.setEnabled(not busy)
        self.refreshButton.setText(tr("正在刷新…") if busy else tr("刷新"))
        if not busy:
            self._worker = None

    def _onDevicesListed(self, devices):
        self._loaded = True
        self._devices = list(devices)
        if self._devices:
            self._message = None
        else:
            self._message = (tr("没有发现设备"), adb_service.error_guide("device_not_found"))
        self._rebuild()

    def _onListFailed(self, code, message):
        self._loaded = True
        self._devices = []
        self._message = (message, adb_service.error_guide(code))
        self._rebuild()

    # ---- 手动连接 ----
    def _onConnectClicked(self):
        if self.isBusy():
            return
        address = adb_service.normalize_address(self.addressEdit.text())
        if address is None:
            self._message = (tr("地址格式不对"), tr("请输入“IP:端口”，例如 {address}").format(
                address=adb_service.MUMU_ADDRESS))
            self._rebuild()
            return
        self._setBusy(True)
        self._start(lambda _progress: (self._connect_device(address), self._list_devices()),
                    self._onConnected, self._onConnectFailed)

    def _onConnected(self, result):
        device, devices = result
        self.addressEdit.clear()
        self._select(device.serial)
        self._onDevicesListed(devices)

    def _onConnectFailed(self, code, message):
        self._message = (message, adb_service.error_guide(code))
        self._rebuild()

    # ---- 选择 ----
    def _select(self, serial):
        if serial != self.selectedSerial():
            cfg.set_value("adb_serial", serial)
            self.serialChanged.emit(serial)

    def _onDeviceClicked(self, button):
        self._select(button.property("serial"))
        self._updateSummary()

    def setSelectedSerial(self, _serial=None):
        """序列号在高级设置里被修改后，按配置重新标出选中的设备。"""
        self._rebuild()

    def _updateSummary(self):
        serial = self.selectedSerial()
        if not serial:
            ready = [device for device in self._devices if device.ready]
            if len(ready) == 1 and len(self._devices) == 1:
                text = tr("自动选择：{name}").format(name=ready[0].model or ready[0].serial)
            else:
                text = tr("自动选择（只连接了一台设备时可用）")
        else:
            device = next((item for item in self._devices if item.serial == serial), None)
            if device is None:
                text = tr("{serial}（未连接）").format(serial=serial) if self._loaded else serial
            else:
                text = tr("{name}（{serial}）").format(name=device.model or serial, serial=serial)
        self.setContent(text)

    def _deviceRow(self, serial, title, summary, guide=""):
        radio = RadioButton(title, self.body)
        radio.setProperty("serial", serial)
        self._group.addButton(radio)
        row = _Row(self.body)
        row.radio = radio
        row.addText(radio)
        row.summary = row.addText(_caption(summary, row))
        row.summary.setContentsMargins(28, 0, 0, 0)
        if guide:
            row.guide = row.addText(_caption(guide, row))
            row.guide.setContentsMargins(28, 0, 0, 0)
        return row

    def _rebuild(self):
        self.bodyLayout.removeWidget(self.connectRow)
        separator = getattr(self.connectRow, "_separator", None)
        if separator is not None:
            self.bodyLayout.removeWidget(separator)
            separator.deleteLater()
            self.connectRow._separator = None
        for button in self._group.buttons():
            self._group.removeButton(button)
        self._clearRows()

        selected = self.selectedSerial()
        auto = self._addRow(self._deviceRow(None, tr("自动选择"), tr("只连接了一台设备时直接使用它")))
        auto.radio.setChecked(selected is None)
        known = False
        for device in self._devices:
            guide = ""
            if device.error:
                guide = device.error
            elif device.state != "device":
                guide = adb_service.error_guide("device_not_ready", device.state)
            row = self._addRow(self._deviceRow(device.serial, device.model or device.serial,
                                               device_summary(device), guide))
            row.radio.setChecked(device.serial == selected)
            known = known or device.serial == selected
        if selected and not known:
            summary = tr("当前没有连接这台设备") if self._loaded else tr("序列号 {serial}").format(serial=selected)
            row = self._addRow(self._deviceRow(selected, selected, summary))
            row.radio.setChecked(True)
        if self._message:
            row = _Row(self.body)
            row.message = row.addText(BodyLabel(self._message[0], row))
            row.message.setWordWrap(True)
            if self._message[1]:
                row.guide = row.addText(_caption(self._message[1], row))
            self._addRow(row)
            self.messageRow = row
        else:
            self.messageRow = None

        separator = GroupSeparator(self.body)
        self.bodyLayout.addWidget(separator)
        separator.show()
        self.connectRow._separator = separator
        self.bodyLayout.addWidget(self.connectRow)
        self._updateSummary()
        self.syncHeight()

    def deviceRows(self):
        return [row for row in self._rows if hasattr(row, "radio")]


class AdbEnvironmentCard(_PanelCard):
    """一键环境检查，逐项显示结果和下一步做法。"""

    checkFinished = Signal(bool)

    def __init__(self, parent=None, *, run_checks=None, blocker=None):
        super().__init__(UiIcon.CLIPBOARD_TASK, tr("环境检查"),
                         tr("逐项检查电脑和设备能不能运行，不会启动游戏"), parent)
        self._run_checks = run_checks or adb_service.run_environment_checks
        self._blocker = blocker
        self._worker = None
        self.results = {}
        self.checkButton = QPushButton(tr("开始检查"), self)
        self.checkButton.setObjectName("primaryButton")
        self.card.addWidget(self.checkButton)
        self.checkButton.clicked.connect(self.start)

        self.rows = {}
        for key, title in adb_service.check_titles().items():
            icon = _status_icon(self.body)
            row = _Row(self.body, leading=icon)
            row.icon = icon
            row.title = row.addText(BodyLabel(title, row))
            row.detail = row.addText(_caption(tr("还没有检查"), row))
            row.guide = row.addText(BodyLabel("", row))
            row.guide.setWordWrap(True)
            row.guide.hide()
            self.rows[key] = self._addRow(row)
        # 分辨率只对模拟器有意义，拿到结果后才显示。
        self._setRowVisible(self.rows["resolution"], False)
        self.syncHeight()

    def isBusy(self):
        return self._worker is not None and self._worker.isRunning()

    def start(self):
        if self.isBusy() or (self._blocker is not None and self._blocker()):
            return
        self.results = {}
        for key, row in self.rows.items():
            row.icon.setIcon(InfoBarIcon.INFORMATION)
            row.detail.setText(tr("正在检查…"))
            row.guide.hide()
        self._setRowVisible(self.rows["resolution"], False)
        self.checkButton.setEnabled(False)
        self.checkButton.setText(tr("正在检查…"))
        self.setContent(tr("正在检查，通常几秒钟就能完成"))
        self.syncHeight()
        self.setExpand(True)

        worker = AdbWorker(lambda progress: self._run_checks(progress), self)
        worker.progress.connect(self._onResult)
        worker.succeeded.connect(lambda _result: self._onFinished(None))
        worker.failed.connect(lambda _code, message: self._onFinished(message))
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _onResult(self, result):
        row = self.rows.get(result.key)
        if row is None:
            return
        self.results[result.key] = result
        row.icon.setIcon(_STATUS_ICONS.get(result.status, InfoBarIcon.INFORMATION))
        row.detail.setText(result.detail)
        row.guide.setText(result.guide)
        row.guide.setVisible(bool(result.guide))
        if result.key == "resolution":
            self._setRowVisible(row, True)
        self.syncHeight()

    def _onFinished(self, error):
        self._worker = None
        self.checkButton.setEnabled(True)
        self.checkButton.setText(tr("重新检查"))
        for key, row in self.rows.items():
            if key not in self.results and key != "resolution":
                row.detail.setText(error or tr("这一项没有检查"))
        failed = sum(result.status == adb_service.FAIL for result in self.results.values())
        skipped = sum(result.status == adb_service.SKIP for result in self.results.values())
        warned = sum(result.status == adb_service.WARN for result in self.results.values())
        if error:
            self.setContent(tr("检查中断：{error}").format(error=error))
        elif failed:
            self.setContent(tr("有 {count} 项没有通过，请按提示处理后重新检查").format(count=failed + skipped))
        elif warned:
            self.setContent(tr("可以运行，有 {count} 项需要留意").format(count=warned))
        else:
            self.setContent(tr("全部通过，可以运行任务"))
        self.syncHeight()
        self.checkFinished.emit(not error and not failed)


def describe_status(data, backend):
    """把状态文件整理成界面上的六行文字。返回 (摘要, {行: (级别, 文字, 说明)})。"""
    idle = adb_service.SKIP
    rows = {key: (idle, "—", "") for key in ("device", "service", "display", "game", "fps", "error")}
    rows["error"] = (idle, tr("没有错误"), "")
    if not data:
        summary = tr("运行任务后，这里会显示设备的状态") if backend == "adb" else tr("没有使用 Android 设备后端")
        rows["device"] = (idle, tr("未连接"), "")
        rows["service"] = (idle, tr("未启动"), "")
        rows["display"] = (idle, tr("未建立"), "")
        rows["game"] = (idle, tr("游戏未运行"), "")
        return summary, rows

    running = bool(data.get("running"))
    connected = bool(data.get("connected"))
    serial = data.get("serial")
    display_id = data.get("display_id")
    game_display = data.get("game_display_id")
    code = data.get("error_code")

    if connected:
        rows["device"] = (adb_service.PASS, tr("已连接 {serial}").format(serial=serial or ""), "")
        rows["service"] = (adb_service.PASS, tr("运行中，版本 {version}").format(
            version=data.get("service_version") or "?"), "")
    elif running and not code:
        rows["device"] = (adb_service.WARN, tr("正在连接…"), "")
        rows["service"] = (idle, tr("正在启动…"), "")
    else:
        rows["device"] = (idle, tr("未连接"), "")
        rows["service"] = (idle, tr("未启动"), "")

    if not connected or display_id is None:
        rows["display"] = (idle, tr("未建立"), "")
    elif display_id == 0:
        rows["display"] = (adb_service.PASS, tr("不使用虚拟屏，直接用模拟器画面"), "")
    else:
        rows["display"] = (adb_service.PASS, tr("1280×720，display {display}").format(display=display_id), "")

    if not connected or not data.get("game_running"):
        rows["game"] = (idle, tr("游戏未运行"), "")
    elif code == "manual_action_required":
        rows["game"] = (adb_service.FAIL, tr("停在登录界面，等待手动登录"), "")
    elif data.get("sdk_window") or (game_display is not None and display_id is not None
                                    and game_display != display_id):
        if display_id == 0:
            rows["game"] = (adb_service.WARN, tr("在模拟器的其他窗口，正在移回"), "")
        else:
            rows["game"] = (adb_service.WARN, tr("被登录界面带回了实体屏"), tr(
                "游戏启动时，登录界面会把游戏短暂带回手机屏幕，登录完成后小助手会自动把它移回虚拟屏。"
                "这段时间手机上出现游戏画面是正常现象，不需要操作。"))
    elif display_id == 0:
        rows["game"] = (adb_service.PASS, tr("模拟器画面"), "")
    else:
        rows["game"] = (adb_service.PASS, tr("虚拟屏，手机屏幕可以照常使用"), "")

    fps = data.get("capture_fps") or 0
    if connected and fps > 0:
        rows["fps"] = (adb_service.PASS, tr("{fps:.1f} 帧/秒").format(fps=fps), "")
    elif connected:
        rows["fps"] = (idle, tr("暂时没有取帧"), "")

    if code:
        rows["error"] = (adb_service.FAIL, data.get("error_message") or code, adb_service.error_guide(code))

    phase = data.get("phase")
    if running:
        summary = tr("任务正在运行") if connected else tr("任务正在启动")
        if code:
            summary = tr("任务遇到问题，请看“最近一次错误”")
    elif phase == "failed" or code:
        summary = tr("上次运行出错，请看“最近一次错误”")
    elif phase == "stopped":
        summary = tr("上次运行已被停止")
    elif phase == "aborted":
        summary = tr("上次运行的进程已退出")
    else:
        summary = tr("上次运行正常结束")
    return summary, rows


class AdbStatusCard(_PanelCard):
    """显示任务进程写出的 ADB 运行状态。"""

    def __init__(self, parent=None, *, reader=None, backend=None):
        super().__init__(UiIcon.GAUGE, tr("运行状态"), "", parent)
        self._reader = reader or read_status
        self._backend = backend or adb_service.current_backend
        self._last = object()
        self.rows = {}
        titles = {
            "device": tr("设备连接"),
            "service": tr("设备端服务"),
            "display": tr("虚拟屏"),
            "game": tr("游戏所在的显示器"),
            "fps": tr("取帧速率"),
            "error": tr("最近一次错误"),
        }
        for key, title in titles.items():
            icon = _status_icon(self.body)
            row = _Row(self.body, leading=icon)
            row.icon = icon
            name = BodyLabel(title, row)
            name.setFixedWidth(150)
            row.hBoxLayout.insertWidget(1, name, 0, Qt.AlignmentFlag.AlignTop)
            row.value = row.addText(BodyLabel("—", row))
            row.value.setWordWrap(True)
            row.hint = row.addText(_caption("", row))
            row.hint.hide()
            self.rows[key] = self._addRow(row)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.refresh)
        self.refresh()
        self.setExpand(True)
        self.expandAni.setCurrentTime(self.expandAni.duration())

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def refresh(self):
        try:
            data = self._reader()
        except Exception:
            data = None
        backend = self._backend()
        key = (backend, None if data is None else tuple(sorted(
            (name, value) for name, value in data.items() if name != "updated")))
        if key == self._last:
            return
        self._last = key
        summary, rows = describe_status(data, backend)
        self.setContent(summary)
        for name, (level, text, hint) in rows.items():
            row = self.rows[name]
            row.icon.setIcon(_STATUS_ICONS.get(level, InfoBarIcon.INFORMATION))
            row.value.setText(text)
            row.hint.setText(hint)
            row.hint.setVisible(bool(hint))
        self.syncHeight()


class AdbAdvancedCard(ExpandSettingCard):
    """默认收起的 ADB 高级设置。"""

    expandStateChanged = Signal(bool)
    serialChanged = Signal(object)

    def __init__(self, parent=None):
        super().__init__(UiIcon.OPTIONS, tr("高级设置"), tr("adb 路径、设备序列号、设备类型和点按时长，一般不需要修改"), parent)
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)

        self.pathCard = SettingCard(FIF.COMMAND_PROMPT, tr("adb 路径"), self._pathText(), self.view)
        self.pathButton = QPushButton(tr("选择"), self.pathCard)
        self.pathResetButton = QPushButton(tr("自动查找"), self.pathCard)
        self._appendButtons(self.pathCard, self.pathButton, self.pathResetButton)
        self.pathButton.clicked.connect(self._choosePath)
        self.pathResetButton.clicked.connect(lambda: self._setPath(None))

        self.serialCard = SettingCard(FIF.TAG, tr("设备序列号"), self._serialText(), self.view)
        self.serialButton = QPushButton(tr("修改"), self.serialCard)
        self._appendButtons(self.serialCard, self.serialButton)
        self.serialButton.clicked.connect(self._editSerial)

        self.typeCard = SettingCard(UiIcon.PHONE, tr("设备类型"),
                                    tr("自动判断适合绝大多数设备。实体机使用独立的虚拟屏，模拟器直接使用模拟器画面（需要 Android 14）"),
                                    self.view)
        self.typeComboBox = ComboBox(self.typeCard)
        for text, value in ((tr("自动判断"), "auto"), (tr("实体机"), "physical"), (tr("模拟器"), "emulator")):
            self.typeComboBox.addItem(text, userData=value)
        index = self.typeComboBox.findData(cfg.get_value("adb_device_type") or "auto")
        self.typeComboBox.setCurrentIndex(max(index, 0))
        self.typeCard.hBoxLayout.addWidget(self.typeComboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.typeCard.hBoxLayout.addSpacing(16)
        self.typeComboBox.currentIndexChanged.connect(
            lambda index: cfg.set_value("adb_device_type", self.typeComboBox.itemData(index)))

        self.tapCard = SettingCard(UiIcon.TAP, tr("点按时长（毫秒）"),
                                   tr("每次点击按住屏幕的时间，默认 50。点击经常没有反应时可以适当调大"), self.view)
        self.tapSpinBox = AsciiSpinBox(self.tapCard)
        self.tapSpinBox.setRange(1, 10000)
        self.tapSpinBox.setMinimumWidth(150)
        tap = cfg.get_value("adb_tap_ms")
        self.tapSpinBox.setValue(tap if type(tap) is int and 1 <= tap <= 10000 else 50)
        self.tapCard.hBoxLayout.addWidget(self.tapSpinBox, 0, Qt.AlignmentFlag.AlignRight)
        self.tapCard.hBoxLayout.addSpacing(16)
        self.tapSpinBox.valueChanged.connect(lambda value: cfg.set_value("adb_tap_ms", int(value)))

        for card in (self.pathCard, self.serialCard, self.typeCard, self.tapCard):
            self.viewLayout.addWidget(card)
        self._adjustViewSize()

    @staticmethod
    def _appendButtons(card, *buttons):
        for index, button in enumerate(buttons):
            button.setObjectName("pushButton")
            if index:
                card.hBoxLayout.addSpacing(10)
            card.hBoxLayout.addWidget(button, 0, Qt.AlignmentFlag.AlignRight)
        card.hBoxLayout.addSpacing(16)

    def _pathText(self):
        return cfg.get_value("adb_path") or tr("自动查找（先找 PATH，再找常见模拟器的安装目录）")

    def _serialText(self):
        return cfg.get_value("adb_serial") or tr("自动选择")

    def _setPath(self, path):
        cfg.set_value("adb_path", path)
        self.pathCard.setContent(self._pathText())

    def _choosePath(self):
        current = cfg.get_value("adb_path")
        path, _ = QFileDialog.getOpenFileName(
            self.window(), tr("选择 adb"), os.path.dirname(current) if current else "")
        if path:
            self._setPath(os.path.normpath(path))

    def _editSerial(self):
        box = MessageBoxEdit(tr("设备序列号"), cfg.get_value("adb_serial") or "", self.window())
        box.lineEdit.setPlaceholderText(tr("留空表示自动选择"))
        if box.exec():
            serial = box.getText().strip() or None
            cfg.set_value("adb_serial", serial)
            self.refreshSerial()
            self.serialChanged.emit(serial)

    def refreshSerial(self):
        self.serialCard.setContent(self._serialText())

    def setExpand(self, isExpand):
        if self.isExpand == isExpand:
            return
        if isExpand:
            self.expandStateChanged.emit(True)
        super().setExpand(isExpand)
        if not isExpand:
            self.expandAni.finished.connect(self._onCollapseFinished)

    def _onCollapseFinished(self):
        try:
            self.expandAni.finished.disconnect(self._onCollapseFinished)
        except (RuntimeError, TypeError):
            pass
        self.expandStateChanged.emit(False)
