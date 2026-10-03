import hashlib
import io
import json
import threading
import time
from typing import Any, Dict, Optional, Tuple
import requests
from utils.logger.logger import Logger
from .notifier import Notifier

try:
    import websocket
except Exception:  # websocket-client 仅在自动绑定 openid 时需要，缺失不影响文本推送
    websocket = None


class QqBotNotifier(Notifier):
    """QQ 官方机器人（QQ 开放平台）通知器。

    仅需 AppID 与 AppSecret 即可推送消息，无需部署 NapCat / Lagrange 等 OneBot 协议端。
    收件方使用 openid / group_openid 标识，需通过机器人收到的事件获取后填入配置。
    """

    TOKEN_API = "https://bots.qq.com/app/getAppAccessToken"
    API_BASE = "https://api.sgroup.qq.com"
    TOKEN_EXPIRE_MARGIN = 60  # access_token 提前 60 秒视为过期，避免边界失效
    MAX_CONTENT_LENGTH = 2000  # 主动消息正文长度上限
    FILE_TYPE_IMAGE = 1  # 富媒体文件类型：图片（png/jpg）
    MD5_10M_SIZE = 10002432  # 分片上传秒传判断：文件前 10002432 字节的 MD5
    UPLOAD_RETRIES = 3  # 分片上传重试次数

    # access_token 类级缓存：{appid: (access_token, 有效截止时间戳)}
    _token_cache: Dict[str, Tuple[str, float]] = {}

    def _get_supports_image(self):
        return True

    def __init__(self, params: Dict[str, Any], logger: Logger):
        """
        初始化 QQ 官方机器人通知器。

        :param params: 发送通知所需的参数字典（appid、client_secret、openid、group_openid）。
        :param logger: 日志记录器实例。
        """
        super().__init__(params, logger)
        # YAML 中未加引号的纯数字会被解析为 int（GUI 的 eval 修改同理），
        # 而服务端要求凭证为字符串，统一归一化，避免以 JSON 数字发送导致 100002 internal err
        self.appid = str(params.get("appid") or "")
        self.client_secret = str(params.get("client_secret") or "")
        if not self.appid or not self.client_secret:
            raise ValueError("AppID and client_secret are required for QqBotNotifier")

    def _post_json(self, url: str, payload: Dict[str, Any], access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        POST JSON 请求并解析响应体，失败时抛出带服务端原文的异常。

        :param url: 请求地址。
        :param payload: 请求体。
        :param access_token: 可选，调用开放接口时携带的 access_token。
        :return: 响应体字典。
        :raises RuntimeError: 响应体含业务错误码或 HTTP 请求失败时抛出。
        """
        headers = {"Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"QQBot {access_token}"
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        try:
            data = response.json()
        except Exception:
            data = None
        # 业务错误可能随 HTTP 200 返回（如换 token 接口），优先依据响应体中的 code 判断
        if isinstance(data, dict) and not data.get("code"):
            return data
        # 失败时附上服务端原文，便于定位 40034105（主动消息无权限）等业务错误
        detail = (getattr(response, "text", "") or "").strip() or f"HTTP {response.status_code}"
        raise RuntimeError(detail)

    def _get_access_token(self) -> str:
        """
        获取 access_token（带类级缓存，提前 60 秒过期避免边界失效）。

        :return: access_token 字符串。
        """
        cached = self._token_cache.get(self.appid)
        if cached and cached[1] > time.time():
            return cached[0]

        try:
            data = self._post_json(self.TOKEN_API, {"appId": self.appid, "clientSecret": self.client_secret})
        except Exception as e:
            raise RuntimeError(f"获取 access_token 失败: {e}")
        token = data.get("access_token")
        if not token:
            raise RuntimeError("获取 access_token 失败: 服务端未返回 access_token")
        try:
            expires_in = int(data.get("expires_in"))
        except (TypeError, ValueError):
            expires_in = 7200
        self._token_cache[self.appid] = (token, time.time() + max(expires_in - self.TOKEN_EXPIRE_MARGIN, 0))
        return token

    def _send_message(self, url_path: str, content: str, access_token: str):
        """
        发送主动消息。

        :param url_path: 接口路径，如 /v2/users/{openid}/messages。
        :param content: 消息文本内容。
        :param access_token: access_token。
        """
        self._post_json(f"{self.API_BASE}{url_path}", {"content": content, "msg_type": 0}, access_token)

    def send(self, title: str, content: str, image_io: Optional[io.BytesIO] = None):
        """
        发送 QQ 官方机器人通知。

        :param title: 通知标题。
        :param content: 通知内容。
        :param image_io: 可选，发送的图片，为 io.BytesIO 对象（png/jpg，走官方分片上传）。
        """
        openid = str(self.params.get("openid") or "")
        group_openid = str(self.params.get("group_openid") or "")
        if not openid and not group_openid:
            raise ValueError("openid or group_openid is required for QqBotNotifier")

        # 与 OneBot/Telegram 等聊天类渠道一致：标题与正文之间只用单个换行
        message = title if not content else f'{title}\n{content}' if title else content
        if len(message) > self.MAX_CONTENT_LENGTH:
            message = message[: self.MAX_CONTENT_LENGTH - 1] + "…"

        access_token = self._get_access_token()

        targets = []
        if group_openid:
            targets.append(("群聊", f"/v2/groups/{group_openid}"))
        if openid:
            targets.append(("单聊", f"/v2/users/{openid}"))

        errors = []
        for name, base_path in targets:
            if message:
                try:
                    self._send_message(f"{base_path}/messages", message, access_token)
                except Exception as e:
                    errors.append(f"{name}消息发送失败: {e}")
            if image_io:
                try:
                    image_io.seek(0)
                    self._send_image(base_path, image_io.read(), access_token)
                except Exception as e:
                    errors.append(f"{name}图片发送失败: {e}")
        if errors:
            raise RuntimeError("；".join(errors))

    def _put_part(self, url: str, chunk: bytes):
        """
        上传单个分片（预签名 URL，带简单重试）。

        :param url: 预签名上传地址。
        :param chunk: 分片二进制内容。
        """
        if not url:
            raise RuntimeError("服务端未返回分片上传地址")
        last_error = None
        for attempt in range(self.UPLOAD_RETRIES):
            try:
                response = requests.put(url, data=chunk, headers={"Content-Type": "application/octet-stream"}, timeout=120)
                response.raise_for_status()
                return
            except requests.RequestException as e:
                last_error = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"分片上传失败: {last_error}")

    def _send_image(self, base_path: str, image_bytes: bytes, access_token: str):
        """
        分片上传图片并发送图片消息（msg_type=7）。

        官方图片消息需先分片上传（upload_prepare → PUT → upload_part_finish → files）
        换取 file_info，再以 msg_type=7 发送；单聊/群聊上传接口不互通。

        :param base_path: 目标接口前缀，如 /v2/users/{openid}。
        :param image_bytes: 图片二进制内容（png/jpg）。
        :param access_token: access_token。
        """
        file_name = "screenshot.jpg"
        prepare = self._post_json(
            f"{self.API_BASE}{base_path}/upload_prepare",
            {
                "file_type": self.FILE_TYPE_IMAGE,
                "file_size": str(len(image_bytes)),
                "file_name": file_name,
                "md5": hashlib.md5(image_bytes).hexdigest(),
                "sha1": hashlib.sha1(image_bytes).hexdigest(),
                "md5_10m": hashlib.md5(image_bytes[: self.MD5_10M_SIZE]).hexdigest(),
            },
            access_token,
        )
        upload_id = prepare.get("upload_id")
        if not upload_id:
            raise RuntimeError(f"服务端未返回 upload_id: {prepare}")

        # 按返回的分片顺序依次上传，块大小以响应为准（index 基值不可依赖）
        offset = 0
        for part in prepare.get("parts") or []:
            block_size = int(part.get("block_size") or 0)
            chunk = image_bytes[offset: offset + block_size] if block_size else image_bytes[offset:]
            if not chunk:
                break
            self._put_part(part.get("presigned_url"), chunk)
            self._post_json(
                f"{self.API_BASE}{base_path}/upload_part_finish",
                {
                    "upload_id": upload_id,
                    "part_index": part.get("index"),
                    "block_size": str(len(chunk)),
                    "md5": hashlib.md5(chunk).hexdigest(),
                },
                access_token,
            )
            offset += len(chunk)

        uploaded = self._post_json(
            f"{self.API_BASE}{base_path}/files",
            {"file_type": self.FILE_TYPE_IMAGE, "upload_id": upload_id, "file_name": file_name},
            access_token,
        )
        file_info = uploaded.get("file_info")
        if not file_info:
            raise RuntimeError(f"服务端未返回 file_info: {uploaded}")
        self._post_json(
            f"{self.API_BASE}{base_path}/messages",
            {"msg_type": 7, "media": {"file_info": file_info}},
            access_token,
        )


class QqBotOpenIdBinder:
    """通过临时 WebSocket 监听机器人事件，自动获取 openid / group_openid。

    openid / group_openid 无法通过 REST 查询，只能在机器人收到事件时获取：
    单聊对应 C2C_MESSAGE_CREATE / FRIEND_ADD，群聊对应 GROUP_AT_MESSAGE_CREATE / GROUP_ADD_ROBOT。
    """

    GATEWAY_API = f"{QqBotNotifier.API_BASE}/gateway"
    INTENTS = 1 << 25  # GROUP_AND_C2C_EVENT：单聊/群聊消息与机器人事件
    BIND_TIMEOUT = 60  # 绑定监听超时（秒）

    def __init__(self, params: Dict[str, Any], logger: Optional[Logger] = None):
        """
        初始化绑定器。

        :param params: 参数字典（appid、client_secret），复用 QqBotNotifier 获取 access_token。
        :param logger: 日志记录器实例，可选。
        """
        self.logger = logger
        self._notifier = QqBotNotifier(params, logger)

    @staticmethod
    def parse_event(event_type: Optional[str], data: Dict[str, Any]) -> Optional[Tuple[str, str, bool]]:
        """
        解析网关事件中的收件标识。

        :param event_type: 网关事件名（payload 的 t 字段）。
        :param data: 事件体（payload 的 d 字段）。
        :return: (目标类型 user/group, 标识值, 是否需要校验码)，无法识别时返回 None。
        """
        if event_type == "C2C_MESSAGE_CREATE":
            return "user", (data.get("author") or {}).get("user_openid"), True
        if event_type == "FRIEND_ADD":
            return "user", data.get("openid"), False
        if event_type in ("GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"):
            return "group", data.get("group_openid"), True
        if event_type == "GROUP_ADD_ROBOT":
            return "group", data.get("group_openid"), False
        return None

    def _get_gateway_url(self, access_token: str) -> str:
        """
        获取 WebSocket 网关地址。

        :param access_token: access_token。
        :return: wss 网关地址。
        """
        response = requests.get(self.GATEWAY_API, headers={"Authorization": f"QQBot {access_token}"}, timeout=30)
        try:
            data = response.json()
        except Exception:
            data = None
        if isinstance(data, dict) and data.get("url"):
            return data["url"]
        detail = (getattr(response, "text", "") or "").strip() or f"HTTP {response.status_code}"
        raise RuntimeError(f"获取网关地址失败: {detail}")

    def capture(self, mode: str, verify_code: Optional[str] = None, timeout: float = BIND_TIMEOUT) -> str:
        """
        临时监听网关事件，直到捕获目标收件标识（参考 BetterGI 的绑定体验）。

        :param mode: "user"（单聊 openid）或 "group"（群聊 group_openid）。
        :param verify_code: 校验码。消息类事件的内容需包含该码才接受，避免绑错人；
                            好友添加 / 机器人入群等事件没有消息内容，直接接受。
        :param timeout: 监听超时（秒）。
        :return: 捕获到的 openid / group_openid。
        :raises ValueError: mode 不合法。
        :raises TimeoutError: 超时未捕获到目标标识。
        :raises RuntimeError: 鉴权失败、网关异常或缺少依赖。
        """
        if mode not in ("user", "group"):
            raise ValueError('mode must be "user" or "group"')
        if websocket is None:
            raise RuntimeError("缺少 websocket-client 依赖，无法自动绑定，请先安装后重试")

        access_token = self._notifier._get_access_token()
        gateway_url = self._get_gateway_url(access_token)

        result: Dict[str, Any] = {"value": None, "error": None, "timed_out": False, "seq": None}
        stop_event = threading.Event()

        def _heartbeat_loop(ws, interval: float):
            # 必须按 Hello 的 heartbeat_interval 发业务心跳（op=1），协议层 ping 不能替代
            while not stop_event.wait(interval):
                try:
                    ws.send(json.dumps({"op": 1, "d": result["seq"]}))
                except Exception:
                    break

        def _on_open(ws):
            ws.send(json.dumps({
                "op": 2,
                "d": {"token": f"QQBot {access_token}", "intents": self.INTENTS, "shard": [0, 1]},
            }))

        def _on_message(ws, raw):
            try:
                payload = json.loads(raw)
            except Exception:
                return
            op = payload.get("op")
            if op == 10:  # Hello
                interval = (payload.get("d") or {}).get("heartbeat_interval") or 45000
                threading.Thread(target=_heartbeat_loop, args=(ws, interval / 1000), daemon=True).start()
                return
            if op == 11:  # 心跳 ACK
                return
            if op == 1:  # 服务端催心跳，立即回包
                ws.send(json.dumps({"op": 1, "d": result["seq"]}))
                return
            if op == 9:
                result["error"] = "鉴权失败或未开通单聊/群聊事件权限，请在 QQ 开放平台申请后重试"
                ws.close()
                return
            if op == 7:
                result["error"] = "网关要求重连，请重新发起绑定"
                ws.close()
                return
            if op != 0:
                return
            if payload.get("s") is not None:
                result["seq"] = payload["s"]  # 心跳须携带最新序列号
            data = payload.get("d") or {}
            parsed = self.parse_event(payload.get("t"), data)
            if not parsed:
                return
            target_type, value, need_verify = parsed
            if target_type != mode or not value:
                return
            if need_verify and verify_code and verify_code not in (data.get("content") or ""):
                return  # 校验码不匹配，继续监听
            result["value"] = value
            ws.close()

        def _on_error(ws, error):
            if result["value"] is None and result["error"] is None:
                result["error"] = str(error)

        ws = websocket.WebSocketApp(gateway_url, on_open=_on_open, on_message=_on_message, on_error=_on_error)

        def _on_timeout():
            result["timed_out"] = True
            ws.close()

        timer = threading.Timer(timeout, _on_timeout)
        timer.start()
        try:
            ws.run_forever()
        finally:
            timer.cancel()
            stop_event.set()

        if result["value"]:
            return result["value"]
        if result["timed_out"]:
            if mode == "user":
                raise TimeoutError(f"绑定超时，请在 {int(timeout)} 秒内用 QQ 私聊机器人并发送验证码")
            raise TimeoutError(f"绑定超时，请在 {int(timeout)} 秒内在群聊中 @ 机器人并发送验证码，或将机器人拉进目标群")
        raise RuntimeError(result["error"] or "网关连接已关闭，请重新发起绑定")
