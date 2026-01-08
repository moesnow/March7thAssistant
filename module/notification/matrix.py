from io import BytesIO
from .notifier import Notifier
from nio.client import AsyncClient  # 如果想使用代理则必须使用AsyncClient
from nio.responses import RoomSendError, UploadError
import asyncio
from PIL import Image
from module.logger import log
import sys


async def send_text_image_msg(client, room_id, msg, image_io):
    v = image_io.getvalue()
    image_stream = BytesIO(v)
    im = Image.open(image_stream)
    (width, height) = im.size
    im.close()
    resp, _maybe_keys = await client.upload(
        BytesIO(v),
        content_type="image/png",
        filename="img.png",
        filesize=len(v),
    )
    if isinstance(resp, UploadError):
        raise RuntimeError(f"message img upload error : {resp}")

    content = {
        "msgtype": "m.image",
        "info": {
            "size": len(v),
            "mimetype": "image/png",
            "thumbnail_info": None,
            "w": width,  # width in pixel
            "h": height,  # height in pixel
            "thumbnail_url": None,
        },
        "url": resp.content_uri,
    }

    if msg is not None and msg != "":
        content["body"] = msg
        content["filename"] = "img.png"
    else:
        content["body"] = "img.png"

    rsp = await client.room_send(
        room_id=room_id,
        message_type="m.room.message",
        content=content,
    )
    if isinstance(rsp, RoomSendError):
        raise RuntimeError(f"message send error : {rsp}")


async def send_text_msg(client, room_id, msg):
    if msg is None or msg == '':
        return
    rsp = await client.room_send(
        # Watch out! If you join an old room you'll see lots of old messages
        room_id=room_id,
        message_type="m.room.message",
        content={"msgtype": "m.text", "body": msg},
    )
    if isinstance(rsp, RoomSendError):
        raise RuntimeError(f"message send error : {rsp}")


class MatrixNotifier(Notifier):
    def _get_supports_image(self):
        return True

    def send(self, title: str, content: str, image_io=None):
        # cfg
        homeserver = self.params["homeserver"]
        device_id = self.params["device_id"]
        user_id = self.params["user_id"]
        access_token = self.params["access_token"]
        room_id = self.params["room_id"]
        if sys.platform == 'win32':
            from .pac import match_proxy_url
            proxy = match_proxy_url(self.params.get("proxy", None), homeserver)
        else:
            proxy = None
        separately_text_media = self.params["separately_text_media"]
        # client
        client = AsyncClient(homeserver)
        client.user_id = user_id
        client.access_token = access_token
        client.device_id = device_id
        if proxy is not None:
            client.proxy = proxy
        # 构建消息文本
        message = title if not content else f'{title}\n{content}' if title else content
        loop = asyncio.get_event_loop()
        if image_io:
            if separately_text_media:
                loop.run_until_complete(send_text_msg(client, room_id, message))
            loop.run_until_complete(send_text_image_msg(client, room_id, None if separately_text_media else message, image_io))
        else:
            # 只发送文本消息
            loop.run_until_complete(send_text_msg(client, room_id, message))
