"""设备端服务的最小测试客户端，只用标准库。

给冒烟测试和手工调试用，协议见 ../PROTOCOL.md。正式的 Python 客户端属于桌面 ADB 后端，不在这里。
"""

from __future__ import annotations

import json
import re
import secrets
import socket
import statistics
import struct
import subprocess
import time
import zlib
from pathlib import Path

PROTOCOL_VERSION = 1
MAIN_CLASS = "org.march7th.deviceservice.Main"
REMOTE_JAR = "/data/local/tmp/m7a-device-service.jar"
REMOTE_LOG = "/data/local/tmp/m7a-device-service.log"
DEFAULT_JAR = Path(__file__).resolve().parent.parent / "build" / "outputs" / "m7a-device-service.jar"

# 1280×720 下会出现 UID 的区域：手机菜单右上角、左下角水印、右下角。保存截图前涂黑。
UID_MASKS_720P = ((725, 0, 1280, 195), (0, 644, 540, 720), (980, 671, 1280, 720))


class DeviceError(Exception):
    """服务返回的错误响应。"""

    def __init__(self, code: str, message: str, details: dict):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.details = details


class DeviceClient:
    """一条到设备端服务的连接。请求串行发送；服务推送的事件收在 self.events 里。"""

    def __init__(self, host: str, port: int, token: str, *, events: bool = False,
                 protocol: int = PROTOCOL_VERSION, timeout: float = 10.0):
        self.events: list[dict] = []
        self._next_id = 1
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self._default_timeout = timeout
        try:
            self.hello, _ = self.request("hello", protocol=protocol, token=token, events=events)
        except BaseException:
            self._sock.close()
            raise

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def __enter__(self) -> "DeviceClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _send(self, header: dict, payload: bytes = b"") -> None:
        data = json.dumps(header, separators=(",", ":")).encode("utf-8")
        self._sock.sendall(struct.pack(">II", len(data), len(payload)) + data + payload)

    def _read_exact(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            chunk = self._sock.recv(min(size - len(chunks), 1 << 20))
            if not chunk:
                raise ConnectionError("connection closed by the service")
            chunks += chunk
        return bytes(chunks)

    def _read_message(self) -> tuple[dict, bytes]:
        header_length, payload_length = struct.unpack(">II", self._read_exact(8))
        header = json.loads(self._read_exact(header_length).decode("utf-8"))
        payload = self._read_exact(payload_length) if payload_length else b""
        return header, payload

    def request(self, cmd: str, *, timeout: float | None = None, **params) -> tuple[dict, bytes]:
        """发一条命令并等它的响应。等待期间到达的事件追加到 self.events。"""
        request_id = self._next_id
        self._next_id += 1
        self._sock.settimeout(timeout if timeout is not None else self._default_timeout)
        self._send({"id": request_id, "cmd": cmd, **params})
        while True:
            header, payload = self._read_message()
            if "event" in header:
                self.events.append(header)
                continue
            if header.get("id") != request_id:
                raise ConnectionError(f"unexpected response id {header.get('id')!r}")
            if not header.get("ok"):
                error = header.get("error", {})
                raise DeviceError(error.get("code", "unknown"), error.get("message", ""), error)
            return header, payload

    def wait_event(self, predicate, timeout: float) -> dict | None:
        """等一条满足条件的事件。已经收到的事件先检查一遍。"""
        checked = 0
        deadline = time.monotonic() + timeout
        while True:
            while checked < len(self.events):
                event = self.events[checked]
                checked += 1
                if predicate(event):
                    return event
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            self._sock.settimeout(remaining)
            try:
                header, _ = self._read_message()
            except (socket.timeout, TimeoutError):
                return None
            if "event" in header:
                self.events.append(header)

    def frame(self, *, min_seq: int = 0, timeout_ms: int = 2000, **params) -> tuple[dict, bytes]:
        """取一帧，返回 (响应头, 解码后紧密排列的像素)。"""
        header, payload = self.request("frame", min_seq=min_seq, timeout_ms=timeout_ms,
                                       timeout=timeout_ms / 1000 + 10, **params)
        return header, decode_frame(header, payload)

    def frame_after(self, input_result: dict, *, min_seq: int = 0, **params) -> tuple[dict, bytes]:
        """按输入完成时间取帧。min_seq 可由上一张已消费帧的序号加一得到。"""
        if "frame_after_ns" not in self.hello.get("features", ()) or "input_ns" not in input_result:
            raise DeviceError("frame_clock_unavailable", "the service does not expose a timestamp boundary", {})
        after_ns = input_result["input_ns"]
        header, pixels = self.frame(min_seq=min_seq, after_ns=after_ns, **params)
        if not header["timestamp_comparable"] or header["image_ns"] <= after_ns or header["seq"] < min_seq:
            raise ConnectionError("frame did not meet the input boundary")
        return header, pixels


def decode_frame(header: dict, payload: bytes) -> bytes:
    """把一帧的负载还原成 width × height × channels 的原始像素。"""
    if "chunks" not in header:
        return payload
    parts = []
    offset = 0
    for length in header["chunks"]:
        parts.append(zlib.decompress(payload[offset:offset + length]))
        offset += length
    data = b"".join(parts)
    predictor = header.get("predictor", "none")
    if predictor == "none":
        return data
    import numpy as np  # 只有用了预测才需要

    pixels = np.frombuffer(data, dtype=np.uint8).reshape(header["height"], header["width"], header["channels"])
    axis = 1 if predictor == "left" else 0
    return np.cumsum(pixels, axis=axis, dtype=np.uint8).tobytes()


def measure_frame_encoding(client: DeviceClient, seconds: float, options: dict) -> dict:
    """分别测取最新帧（含解码）和连续新帧（端到端只计到收完负载）。"""
    def sample(fresh: bool):
        header, _ = client.frame(**options)
        first_seq = last_seq = header["seq"]
        samples = []
        begin = time.perf_counter()
        while time.perf_counter() - begin < seconds:
            t0 = time.perf_counter()
            try:
                header, payload = client.request("frame", min_seq=last_seq + 1 if fresh else 0,
                                                 timeout_ms=1000, **options)
            except DeviceError as error:
                if error.code != "timeout":
                    raise
                continue
            received_ms = (time.perf_counter() - t0) * 1000
            pixels = decode_frame(header, payload)
            decoded_ms = (time.perf_counter() - t0) * 1000
            if fresh and header["seq"] <= last_seq:
                raise ConnectionError("fresh frame sequence did not increase")
            if len(pixels) != header["width"] * header["height"] * header["channels"]:
                raise ConnectionError("decoded size mismatch")
            last_seq = header["seq"]
            server_ms = header["copy_ms"] + header["encode_ms"]
            samples.append({
                "seq": last_seq, "cached": header["cached"], "size": header["size"],
                "request_ms": decoded_ms, "received_ms": received_ms, "age_ms": header["age_ms"],
                "copy_ms": header["copy_ms"], "encode_ms": header["encode_ms"], "wait_ms": header["wait_ms"],
                "end_to_end_ms": header["age_ms"] + max(0.0, received_ms - server_ms - header["wait_ms"]),
            })
        elapsed = time.perf_counter() - begin
        if not samples:
            raise DeviceError("timeout", "no frame received during the benchmark", {})
        return samples, elapsed, last_seq - first_seq

    def percentiles(samples, field):
        values = sorted(row[field] for row in samples)
        return round(statistics.median(values), 1), round(values[min(len(values) - 1, int(len(values) * 0.95))], 1)

    latest, _, _ = sample(fresh=False)
    fresh, elapsed, source_frames = sample(fresh=True)
    latest_p50, latest_p95 = percentiles(latest, "request_ms")
    fresh_p50, fresh_p95 = percentiles(fresh, "request_ms")
    e2e_p50, e2e_p95 = percentiles(fresh, "end_to_end_ms")
    return {
        "frames": len(fresh), "fps": round(len(fresh) / elapsed, 1), "source_fps": round(source_frames / elapsed, 1),
        "size_kb": round(statistics.mean(row["size"] for row in fresh) / 1024),
        "server_ms": round(statistics.median(row["copy_ms"] + row["encode_ms"] for row in fresh), 1),
        "latest_request_ms_p50": latest_p50, "latest_request_ms_p95": latest_p95,
        "latest_cached": sum(row["cached"] for row in latest), "latest_samples": len(latest),
        "fresh_request_ms_p50": fresh_p50, "fresh_request_ms_p95": fresh_p95,
        "end_to_end_ms_p50": e2e_p50, "end_to_end_ms_p95": e2e_p95,
        "samples": {"latest": latest, "fresh": fresh},
    }


def write_png(path: Path, width: int, height: int, channels: int, pixels: bytes,
              masks=UID_MASKS_720P) -> None:
    """把像素存成 PNG。masks 里的矩形 (x0, y0, x1, y1) 会被涂黑，默认遮住 720p 下的 UID。"""
    rows = bytearray()
    row_bytes = width * channels
    for y in range(height):
        row = bytearray(pixels[y * row_bytes:(y + 1) * row_bytes])
        for x0, y0, x1, y1 in masks or ():
            if y0 <= y < y1:
                x0, x1 = max(0, x0), min(width, x1)
                if x1 > x0:
                    row[x0 * channels:x1 * channels] = bytes((x1 - x0) * channels)
        rows.append(0)
        rows += row

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    color_type = 2 if channels == 3 else 6
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(rows), 6))
    png += chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def changed_ratio(a: bytes, b: bytes, channels: int) -> float:
    """两块同尺寸像素里不相同的像素占比。"""
    if len(a) != len(b):
        raise ValueError("size mismatch")
    total = len(a) // channels
    different = sum(1 for i in range(0, len(a), channels) if a[i:i + channels] != b[i:i + channels])
    return different / total if total else 0.0


class Adb:
    """对一台设备执行 adb 命令。只用 PATH 里的 adb。"""

    def __init__(self, serial: str | None = None):
        self.serial = serial

    def run(self, *args: str, timeout: float = 30, check: bool = True) -> str:
        command = ["adb"]
        if self.serial:
            command += ["-s", self.serial]
        command += list(args)
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        output = result.stdout.decode("utf-8", errors="replace")
        if check and result.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} failed: {output}{result.stderr.decode('utf-8', errors='replace')}")
        return output

    def shell(self, command: str, timeout: float = 30, check: bool = True) -> str:
        return self.run("shell", command, timeout=timeout, check=check)

    def forward(self, socket_name: str) -> int:
        """把本机的一个空闲端口转发到设备上的抽象套接字，返回端口号。"""
        return int(self.run("forward", "tcp:0", f"localabstract:{socket_name}").strip())

    def remove_forward(self, port: int) -> None:
        self.run("forward", "--remove", f"tcp:{port}", check=False)


class ServiceHandle:
    """一次服务启动：令牌、套接字名和转发端口。"""

    def __init__(self, adb: Adb, token: str, socket_name: str, port: int, pid: int):
        self.adb = adb
        self.token = token
        self.socket_name = socket_name
        self.port = port
        self.pid = pid

    def connect(self, **kwargs) -> DeviceClient:
        return DeviceClient("127.0.0.1", self.port, self.token, **kwargs)

    def running(self) -> bool:
        return f"{self.pid}" in self.adb.shell(f"ls -d /proc/{self.pid} 2>/dev/null", check=False)

    def remove_forward(self) -> None:
        self.adb.remove_forward(self.port)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def start_service(adb: Adb, jar: Path = DEFAULT_JAR, *, token: str | None = None, socket_name: str | None = None,
                  idle_timeout: float = 30, push: bool = True, ready_timeout: float = 15) -> ServiceHandle:
    """推送 jar，以 shell 身份后台启动服务，等它就绪，建立端口转发。"""
    token = token or new_token()
    socket_name = socket_name or f"m7a-{secrets.token_hex(4)}"
    if push:
        adb.run("push", str(jar), REMOTE_JAR, timeout=60)
    # setsid + nohup：adb 会话结束后服务继续运行，生命周期由空闲超时和 shutdown 决定
    adb.shell(
        f"CLASSPATH={REMOTE_JAR} setsid nohup app_process / {MAIN_CLASS} "
        f"--token {token} --socket {socket_name} --idle-timeout {idle_timeout} "
        f"> {REMOTE_LOG} 2>&1 < /dev/null &")
    deadline = time.monotonic() + ready_timeout
    pid = None
    log = ""
    while time.monotonic() < deadline:
        log = adb.shell(f"cat {REMOTE_LOG} 2>/dev/null", check=False)
        match = re.search(r"M7A_DEVICE_SERVICE_READY .*pid=(\d+)", log)
        if match:
            pid = int(match.group(1))
            break
        time.sleep(0.2)
    if pid is None:
        raise RuntimeError(f"service did not become ready:\n{log}")
    return ServiceHandle(adb, token, socket_name, adb.forward(socket_name), pid)
