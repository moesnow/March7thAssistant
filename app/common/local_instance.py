"""与同一安装的 GUI 实例通信。"""

from PySide6.QtNetwork import QLocalSocket


def notify_existing_instance(key, payload_bytes=None, timeout=500):
    """连接已有实例，可选择发送一条消息。"""
    sock = QLocalSocket()
    try:
        sock.connectToServer(key)
        if not sock.waitForConnected(timeout):
            return False
        if payload_bytes is not None:
            sock.write(payload_bytes)
            sock.flush()
            if sock.bytesToWrite() and not sock.waitForBytesWritten(200):
                return False
        return True
    except Exception:
        return False
    finally:
        sock.disconnectFromServer()
        sock.close()
