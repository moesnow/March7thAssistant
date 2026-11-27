"""两个桌面的「当前运行」日志通过本机命名管道单向同步。"""
import json

from PySide6.QtCore import QCoreApplication, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from module.overview.run_log import LogEntry
from utils.desktop_twin import launcher_server_key


def log_server_key(session, host_pid):
    return f"{launcher_server_key(session.session_id)}_log_{session.logon_time}_{host_pid}"


class TwinLogServer(QLocalServer):
    received = Signal(bool, list)
    snapshotLost = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.has_snapshot = False
        self._peer = None
        self.newConnection.connect(self._accept)

    def _accept(self):
        peer = self.nextPendingConnection()
        if self._peer is not None:
            self._peer.abort()
        self._peer = peer
        peer.readyRead.connect(self._read)
        peer.disconnected.connect(self._disconnected)
        self._read()

    def _disconnected(self):
        peer = self.sender()
        if self._peer is peer:
            self._read()
            self._peer = None
            had_snapshot = self.has_snapshot
            self.has_snapshot = False
            if had_snapshot and self.isListening():
                self.snapshotLost.emit()
        peer.deleteLater()

    def _read(self):
        peer = self._peer
        while peer is not None and peer.canReadLine():
            try:
                reset, rows = json.loads(bytes(peer.readLine()))
                if type(reset) is not bool or not isinstance(rows, list):
                    raise ValueError
                entries = [LogEntry(**row) for row in rows]
                if any(not all(isinstance(field, str) for field in (e.time, e.level, e.text, e.kind))
                       or type(e.important) is not bool for e in entries):
                    raise ValueError
            except (ValueError, TypeError):
                peer.abort()
                return
            self.has_snapshot |= reset
            self.received.emit(reset, entries)

    def close(self):
        super().close()
        peer = self._peer
        if peer is not None:
            self._read()
            peer.abort()


class TwinLogPublisher(QLocalSocket):
    def __init__(self, key, controller):
        super().__init__(controller)
        self._controller = controller
        self._needs_snapshot = False
        self.connected.connect(self._snapshot)
        self.bytesWritten.connect(self._drained)
        controller.logAppended.connect(self._append)
        controller.logCleared.connect(self._clear)
        self._retry = QTimer(self, singleShot=True, interval=1000)
        self._retry.timeout.connect(lambda: self.connectToServer(key))
        self.errorOccurred.connect(lambda *_: self._retry.start())
        self.disconnected.connect(self._retry.start)
        QCoreApplication.instance().aboutToQuit.connect(self._finish)
        self.connectToServer(key)

    def _snapshot(self):
        self._retry.stop()
        self._needs_snapshot = False
        self._send(True, self._controller.log_entries())

    def _append(self, entries):
        self._send(False, entries)

    def _clear(self):
        self._send(True, [])

    def _send(self, reset, entries):
        if self.state() != QLocalSocket.LocalSocketState.ConnectedState:
            return
        # 宿主暂停响应时不堆积输出，恢复后重发子窗口保留的最近 5000 行。
        if self._needs_snapshot or self.bytesToWrite() > 1024 * 1024:
            self._needs_snapshot = True
            return
        self._write_frame(reset, entries)

    def _write_frame(self, reset, entries):
        frame = json.dumps([reset, [vars(entry) for entry in entries]], separators=(",", ":"))
        self.write(frame.encode("ascii") + b"\n")

    def _drained(self, _):
        if self._needs_snapshot and not self.bytesToWrite():
            self._snapshot()

    def _finish(self):
        # 任务结束后可能立即退出，此时事件循环来不及送出最后一批日志。
        if self.state() == QLocalSocket.LocalSocketState.ConnectedState:
            if self._needs_snapshot:
                self._needs_snapshot = False
                self._write_frame(True, self._controller.log_entries())
            self.disconnectFromServer()
            if self.state() != QLocalSocket.LocalSocketState.UnconnectedState:
                self.waitForDisconnected(1000)
        self._retry.stop()
