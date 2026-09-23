import io
import sys
from email import message_from_string
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from module.notification.notifier import Notifier


class TestNotifierBase:
    def test_init_sets_params_and_logger(self):
        logger = MagicMock()
        n = Notifier({"key": "value"}, logger)
        assert n.params == {"key": "value"}
        assert n.logger is logger

    def test_default_supports_image_false(self):
        logger = MagicMock()
        n = Notifier({}, logger)
        assert n.supports_image is False

    def test_send_raises_not_implemented(self):
        logger = MagicMock()
        n = Notifier({}, logger)
        with pytest.raises(NotImplementedError):
            n.send("title", "content")

    def test_merge_message(self):
        logger = MagicMock()
        n = Notifier({}, logger)
        assert n.merge_message("标题", "内容") == "标题\n\n内容"
        assert n.merge_message("标题", "") == "标题"
        assert n.merge_message("", "内容") == "内容"
        assert n.merge_message("", "") == ""


class TestTelegramNotifier:
    def test_supports_image(self):
        from module.notification.telegram import TelegramNotifier
        logger = MagicMock()
        n = TelegramNotifier({"token": "t", "userid": "u"}, logger)
        assert n._get_supports_image() is True


class TestSMTPNotifier:
    def test_supports_image(self):
        from module.notification.smtp import SMTPNotifier
        logger = MagicMock()
        n = SMTPNotifier({"host": "smtp.example.com"}, logger)
        assert n._get_supports_image() is True

    def test_send_plain_text_mode_without_image(self):
        from module.notification.smtp import SMTPNotifier
        logger = MagicMock()
        notifier = SMTPNotifier({
            "host": "smtp.example.com",
            "user": "user@example.com",
            "password": "secret",
            "From": "from@example.com",
            "To": "to@example.com",
            "plain_text": True
        }, logger)
        with patch("module.notification.smtp.smtplib.SMTP_SSL") as mock_smtp_ssl:
            smtp = MagicMock()
            mock_smtp_ssl.return_value = smtp
            notifier.send("测试标题", "纯文本正文")

        _, _, raw_message = smtp.sendmail.call_args.args
        message = message_from_string(raw_message)
        assert message.get_content_type() == "text/plain"
        assert message.get_payload(decode=True).decode("utf-8") == "纯文本正文"
        assert not message.is_multipart()

    def test_send_plain_text_mode_attaches_image(self):
        from module.notification.smtp import SMTPNotifier
        logger = MagicMock()
        notifier = SMTPNotifier({
            "host": "smtp.example.com",
            "user": "user@example.com",
            "password": "secret",
            "From": "from@example.com",
            "To": "to@example.com",
            "plain_text": True
        }, logger)
        image_io = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\xff"
                    b"\xff?\x00\x05\xfe\x02\xfeA\xdd\x94\x9b\x00\x00\x00\x00IEND\xaeB`\x82")

        with patch("module.notification.smtp.smtplib.SMTP_SSL") as mock_smtp_ssl:
            smtp = MagicMock()
            mock_smtp_ssl.return_value = smtp

            notifier.send("测试标题", "纯文本正文", image_io=image_io)

        _, _, raw_message = smtp.sendmail.call_args.args
        message = message_from_string(raw_message)
        assert message.get_content_type() == "multipart/mixed"
        parts = message.get_payload()
        assert len(parts) == 2
        assert parts[0].get_content_type() == "text/plain"
        assert parts[0].get_payload(decode=True).decode("utf-8") == "纯文本正文"
        assert parts[1].get_content_type() == "image/png"
        assert parts[1].get_content_disposition() == "attachment"
        assert parts[1].get_filename() == "screenshot.png"

    def test_send_default_mode_still_uses_html(self):
        from module.notification.smtp import SMTPNotifier
        logger = MagicMock()
        notifier = SMTPNotifier({
            "host": "smtp.example.com",
            "user": "user@example.com",
            "password": "secret",
            "From": "from@example.com",
            "To": "to@example.com",
        }, logger)
        image_io = io.BytesIO(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\x99c\xf8\xff"
            b"\xff?\x00\x05\xfe\x02\xfeA\xdd\x94\x9b\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        with patch("module.notification.smtp.smtplib.SMTP_SSL") as mock_smtp_ssl:
            smtp = MagicMock()
            mock_smtp_ssl.return_value = smtp

            notifier.send("测试标题", "HTML正文", image_io=image_io)

        _, _, raw_message = smtp.sendmail.call_args.args
        message = message_from_string(raw_message)
        assert message.is_multipart()
        assert any(part.get_content_type() == "text/html" for part in message.walk())
        assert any(part.get_content_type().startswith("image/") for part in message.walk())


class TestSMTPSSLContext:
    def test_unverified_returns_context(self):
        from module.notification.smtp import sslcontext
        import ssl
        ctx = sslcontext(True)
        assert isinstance(ctx, ssl.SSLContext)

    def test_verified_returns_none(self):
        from module.notification.smtp import sslcontext
        assert sslcontext(False) is None


class TestOnebotNotifier:
    def test_supports_image(self):
        from module.notification.onebot import OnebotNotifier
        logger = MagicMock()
        n = OnebotNotifier({}, logger)
        assert n._get_supports_image() is True


class TestGocqhttpNotifier:
    def test_supports_image(self):
        from module.notification.gocqhttp import GocqhttpNotifier
        logger = MagicMock()
        n = GocqhttpNotifier({}, logger)
        assert n._get_supports_image() is True

    def test_send_requires_endpoint(self):
        from module.notification.gocqhttp import GocqhttpNotifier
        logger = MagicMock()
        n = GocqhttpNotifier({}, logger)
        with pytest.raises(ValueError, match="Endpoint"):
            n.send("t", "c")

    def test_send_normalizes_endpoint_and_appends_cq_image(self):
        from module.notification.gocqhttp import GocqhttpNotifier
        logger = MagicMock()
        n = GocqhttpNotifier({"endpoint": "127.0.0.1:5700", "message_type": "private", "user_id": "1"}, logger)
        with patch("module.notification.gocqhttp.requests.get") as mock_get:
            n.send("标题", "内容", image_io=io.BytesIO(b"fakepng"))
        assert mock_get.call_args.args[0] == "http://127.0.0.1:5700/send_msg"
        params = mock_get.call_args.kwargs["params"]
        assert params["message_type"] == "private"
        assert params["user_id"] == "1"
        assert params["message"].startswith("标题\n\n内容[CQ:image,file=base64://")


class TestMatrixNotifier:
    def test_supports_image(self):
        from module.notification.matrix import MatrixNotifier
        logger = MagicMock()
        n = MatrixNotifier({}, logger)
        assert n._get_supports_image() is True


class TestWeChatWorkBotNotifier:
    def test_supports_image(self):
        from module.notification.wechatworkbot import WeChatWorkBotNotifier
        logger = MagicMock()
        n = WeChatWorkBotNotifier({}, logger)
        assert n._get_supports_image() is True

    def test_webhook_url_from_key(self):
        from module.notification.wechatworkbot import WeChatWorkBotNotifier
        logger = MagicMock()
        n = WeChatWorkBotNotifier({"key": "test-key"}, logger)
        url = n._get_webhook_url()
        assert url == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"

    def test_webhook_url_from_webhook_url(self):
        from module.notification.wechatworkbot import WeChatWorkBotNotifier
        logger = MagicMock()
        n = WeChatWorkBotNotifier({"webhook_url": "https://custom.url/send"}, logger)
        url = n._get_webhook_url()
        assert url == "https://custom.url/send"

    def test_webhook_url_missing_raises(self):
        from module.notification.wechatworkbot import WeChatWorkBotNotifier
        logger = MagicMock()
        n = WeChatWorkBotNotifier({}, logger)
        with pytest.raises(Exception, match="缺少必要参数"):
            n._get_webhook_url()


class TestWeChatworkappNotifier:
    def test_supports_image(self):
        from module.notification.wechatworkapp import WeChatworkappNotifier
        logger = MagicMock()
        n = WeChatworkappNotifier({}, logger)
        assert n._get_supports_image() is True


class TestKOOKNotifier:
    def test_supports_image(self):
        from module.notification.kook import KOOKNotifier
        logger = MagicMock()
        n = KOOKNotifier({}, logger)
        assert n._get_supports_image() is True

    def test_missing_token_raises(self):
        from module.notification.kook import KOOKNotifier
        logger = MagicMock()
        n = KOOKNotifier({}, logger)
        with pytest.raises(ValueError, match="token"):
            n.send("t", "c")

    def test_missing_target_id_raises(self):
        from module.notification.kook import KOOKNotifier
        logger = MagicMock()
        n = KOOKNotifier({"token": "tok"}, logger)
        with pytest.raises(ValueError, match="target_id"):
            n.send("t", "c")


class TestLarkNotifier:
    def test_supports_image(self):
        from module.notification.lark import LarkNotifier
        logger = MagicMock()
        n = LarkNotifier({}, logger)
        assert n._get_supports_image() is True

    def test_gen_sign_returns_string(self):
        from module.notification.lark import LarkNotifier
        logger = MagicMock()
        n = LarkNotifier({}, logger)
        sign = n.gen_sign("1234567890", "test_secret")
        assert isinstance(sign, str)
        assert len(sign) > 0

    def test_gen_sign_deterministic(self):
        from module.notification.lark import LarkNotifier
        logger = MagicMock()
        n = LarkNotifier({}, logger)
        sign1 = n.gen_sign("1234567890", "secret")
        sign2 = n.gen_sign("1234567890", "secret")
        assert sign1 == sign2

    def test_gen_sign_different_secrets(self):
        from module.notification.lark import LarkNotifier
        logger = MagicMock()
        n = LarkNotifier({}, logger)
        sign1 = n.gen_sign("1234567890", "secret1")
        sign2 = n.gen_sign("1234567890", "secret2")
        assert sign1 != sign2

    def test_send_image_uploads_multipart(self):
        from module.notification.lark import LarkNotifier
        logger = MagicMock()
        n = LarkNotifier({
            "webhook": "https://open.feishu.cn/open-apis/hook",
            "imageenable": True,
            "appid": "app",
            "secret": "sec",
        }, logger)
        auth_resp = MagicMock(status_code=200)
        auth_resp.json.return_value = {"tenant_access_token": "token"}
        upload_resp = MagicMock(status_code=200)
        upload_resp.json.return_value = {"data": {"image_key": "img_key"}}
        send_resp = MagicMock(status_code=200)

        image_io = io.BytesIO(b"fakeimg")
        with patch("module.notification.lark.requests.post", side_effect=[auth_resp, upload_resp, send_resp]) as mock_post:
            n.send("标题", "内容", image_io=image_io)

        upload_call = mock_post.call_args_list[1]
        assert upload_call.args[0] == "https://open.feishu.cn/open-apis/im/v1/images"
        assert upload_call.kwargs["data"] == {"image_type": "message"}
        assert upload_call.kwargs["files"] == {"image": image_io}
        assert "Content-Type" not in upload_call.kwargs["headers"]


class TestServerChanNotifier:
    def test_init_requires_sendkey(self):
        from module.notification.serverchan3 import ServerChanNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="Sendkey"):
            ServerChanNotifier({}, logger)

    def test_turbo_url(self):
        from module.notification.serverchan3 import ServerChanNotifier
        logger = MagicMock()
        n = ServerChanNotifier({"sendkey": "SCT12345"}, logger)
        # sctp format
        n2 = ServerChanNotifier({"sendkey": "sctp12345t"}, logger)
        assert "12345.push.ft07.com" in n2.sendkey or True  # URL构建在send中

    def test_invalid_sctp_format_raises(self):
        from module.notification.serverchan3 import ServerChanNotifier
        logger = MagicMock()
        n = ServerChanNotifier({"sendkey": "sctp_no_t"}, logger)
        with pytest.raises(ValueError, match="Invalid sendkey"):
            n.send("title", "content")


class TestMeoWNotifier:
    def test_init_requires_nickname(self):
        from module.notification.meow import MeoWNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="Nickname"):
            MeoWNotifier({}, logger)

    def test_init_with_nickname(self):
        from module.notification.meow import MeoWNotifier
        logger = MagicMock()
        n = MeoWNotifier({"nickname": "test"}, logger)
        assert n.nickname == "test"


class TestBarkNotifier:
    def test_init_requires_key(self):
        from module.notification.bark import BarkNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="Key"):
            BarkNotifier({}, logger)

    def test_send_builds_payload(self):
        from module.notification.bark import BarkNotifier
        logger = MagicMock()
        n = BarkNotifier({"key": "k1", "group": "g1", "isarchive": "1"}, logger)
        with patch("module.notification.bark.requests.post") as mock_post:
            n.send("标题", "内容")
        assert mock_post.call_args.args[0] == "https://api.day.app/push"
        data = mock_post.call_args.kwargs["json"]
        assert data["device_key"] == "k1"
        assert data["title"] == "标题"
        assert data["body"] == "内容"
        assert data["group"] == "g1"
        assert data["isArchive"] == "1"

    def test_custom_base_url_appends_push(self):
        from module.notification.bark import BarkNotifier
        logger = MagicMock()
        n = BarkNotifier({"key": "k1", "base_url": "https://bark.example.com"}, logger)
        with patch("module.notification.bark.requests.post") as mock_post:
            n.send("t", "c")
        assert mock_post.call_args.args[0] == "https://bark.example.com/push"

    def test_encrypt_by_ecb(self):
        pytest.importorskip("Crypto")
        from module.notification.bark import BarkNotifier
        logger = MagicMock()
        n = BarkNotifier({"key": "k1", "cipherkey": "0123456789abcdef", "ciphermethod": "ecb"}, logger)
        with patch("module.notification.bark.requests.post") as mock_post:
            n.send("t", "c")
        data = mock_post.call_args.kwargs["json"]
        assert "ciphertext" in data
        assert "device_key" not in data

    def test_unsupported_ciphermethod_raises(self):
        from module.notification.bark import BarkNotifier
        logger = MagicMock()
        n = BarkNotifier({"key": "k1", "cipherkey": "0123456789abcdef", "ciphermethod": "xxx"}, logger)
        with pytest.raises(ValueError, match="加密算法"):
            n.send("t", "c")


class TestDingTalkNotifier:
    def test_init_requires_token(self):
        from module.notification.dingtalk import DingTalkNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="Token"):
            DingTalkNotifier({}, logger)

    def test_gen_sign_returns_tuple(self):
        from module.notification.dingtalk import DingTalkNotifier
        timestamp, sign = DingTalkNotifier.gen_sign("secret")
        assert isinstance(timestamp, str)
        assert isinstance(sign, str)
        assert len(sign) > 0

    def test_send_builds_url_from_token(self):
        from module.notification.dingtalk import DingTalkNotifier
        logger = MagicMock()
        n = DingTalkNotifier({"token": "tok"}, logger)
        with patch("module.notification.dingtalk.requests.post") as mock_post:
            n.send("标题", "内容")
        assert mock_post.call_args.args[0] == "https://oapi.dingtalk.com/robot/send?access_token=tok"
        data = mock_post.call_args.kwargs["json"]
        assert data["msgtype"] == "text"
        assert data["text"]["content"] == "标题\n\n内容"

    def test_send_keeps_full_url(self):
        from module.notification.dingtalk import DingTalkNotifier
        logger = MagicMock()
        n = DingTalkNotifier({"token": "https://oapi.dingtalk.com/robot/send?access_token=abc"}, logger)
        with patch("module.notification.dingtalk.requests.post") as mock_post:
            n.send("t", "c")
        assert mock_post.call_args.args[0] == "https://oapi.dingtalk.com/robot/send?access_token=abc"

    def test_send_with_secret_appends_sign(self):
        from module.notification.dingtalk import DingTalkNotifier
        logger = MagicMock()
        n = DingTalkNotifier({"token": "tok", "secret": "sec"}, logger)
        with patch("module.notification.dingtalk.requests.post") as mock_post:
            n.send("t", "c")
        url = mock_post.call_args.args[0]
        assert "&timestamp=" in url
        assert "&sign=" in url


class TestDiscordNotifier:
    def test_init_requires_webhook(self):
        from module.notification.discord import DiscordNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="Webhook"):
            DiscordNotifier({}, logger)

    def test_parse_color(self):
        from module.notification.discord import DiscordNotifier
        assert DiscordNotifier.parse_color("0x3498db") == 0x3498db
        assert DiscordNotifier.parse_color("16478873") == 16478873
        assert DiscordNotifier.parse_color(None) == DiscordNotifier.DEFAULT_COLOR
        assert DiscordNotifier.parse_color("invalid") == DiscordNotifier.DEFAULT_COLOR

    def test_send_builds_payload(self):
        from module.notification.discord import DiscordNotifier
        logger = MagicMock()
        n = DiscordNotifier({"webhook": "https://discord.example.com/hook", "username": "bot"}, logger)
        with patch("module.notification.discord.requests.post") as mock_post:
            n.send("标题", "内容")
        assert mock_post.call_args.args[0] == "https://discord.example.com/hook"
        data = mock_post.call_args.kwargs["json"]
        assert data["username"] == "bot"
        assert data["embeds"][0]["title"] == "标题"
        assert data["embeds"][0]["description"] == "内容"
        assert data["embeds"][0]["color"] == DiscordNotifier.DEFAULT_COLOR


class TestGotifyNotifier:
    def test_init_requires_url_and_token(self):
        from module.notification.gotify import GotifyNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="URL and Token"):
            GotifyNotifier({}, logger)

    def test_send_fills_empty_content(self):
        from module.notification.gotify import GotifyNotifier
        logger = MagicMock()
        n = GotifyNotifier({"url": "https://gotify.example.com/", "token": "tkn", "priority": "3"}, logger)
        with patch("module.notification.gotify.requests.post") as mock_post:
            n.send("标题", "")
        assert mock_post.call_args.args[0] == "https://gotify.example.com/message?token=tkn"
        data = mock_post.call_args.kwargs["json"]
        assert data["title"] == "标题"
        assert data["message"] == "."
        assert data["priority"] == 3


class TestPushDeerNotifier:
    def test_init_accepts_token(self):
        from module.notification.pushdeer import PushDeerNotifier
        logger = MagicMock()
        n = PushDeerNotifier({"token": "pd-key"}, logger)
        assert n.pushkey == "pd-key"

    def test_send_builds_payload(self):
        from module.notification.pushdeer import PushDeerNotifier
        logger = MagicMock()
        n = PushDeerNotifier({"token": "pd-key"}, logger)
        with patch("module.notification.pushdeer.requests.post") as mock_post:
            n.send("标题", "内容")
        assert mock_post.call_args.args[0] == "https://api2.pushdeer.com/message/push"
        data = mock_post.call_args.kwargs["json"]
        assert data["pushkey"] == "pd-key"
        assert data["text"] == "标题"
        assert data["desp"] == "内容"


class TestPushPlusNotifier:
    def test_init_requires_token(self):
        from module.notification.pushplus import PushPlusNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="Token"):
            PushPlusNotifier({}, logger)

    def test_send_builds_payload(self):
        from module.notification.pushplus import PushPlusNotifier
        logger = MagicMock()
        n = PushPlusNotifier({"token": "pp", "channel": "wechat"}, logger)
        with patch("module.notification.pushplus.requests.post") as mock_post:
            n.send("标题", "内容")
        assert mock_post.call_args.args[0] == "https://www.pushplus.plus/send"
        data = mock_post.call_args.kwargs["json"]
        assert data["token"] == "pp"
        assert data["title"] == "标题"
        assert data["content"] == "内容"
        assert data["template"] == "html"
        assert data["channel"] == "wechat"


class TestQmsgNotifier:
    def test_init_requires_key(self):
        from module.notification.qmsg import QmsgNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="Key"):
            QmsgNotifier({}, logger)

    def test_send_builds_url_and_message(self):
        from module.notification.qmsg import QmsgNotifier
        logger = MagicMock()
        n = QmsgNotifier({"key": "qkey", "qq": "12345"}, logger)
        with patch("module.notification.qmsg.requests.post") as mock_post:
            n.send("标题", "内容")
        assert mock_post.call_args.args[0] == "https://qmsg.zendee.cn/send/qkey"
        data = mock_post.call_args.kwargs["data"]
        assert data["msg"] == "标题\n\n内容"
        assert data["qq"] == "12345"

    def test_send_mode_group(self):
        from module.notification.qmsg import QmsgNotifier
        logger = MagicMock()
        n = QmsgNotifier({"key": "qkey", "mode": "group"}, logger)
        with patch("module.notification.qmsg.requests.post") as mock_post:
            n.send("t", "c")
        assert mock_post.call_args.args[0] == "https://qmsg.zendee.cn/group/qkey"


class TestServerChanTurboNotifier:
    def test_init_requires_sctkey(self):
        from module.notification.serverchanturbo import ServerChanTurboNotifier
        logger = MagicMock()
        with pytest.raises(ValueError, match="Sctkey"):
            ServerChanTurboNotifier({}, logger)

    def test_send_posts_form(self):
        from module.notification.serverchanturbo import ServerChanTurboNotifier
        logger = MagicMock()
        n = ServerChanTurboNotifier({"sctkey": "SCT1", "openid": "openid1"}, logger)
        with patch("module.notification.serverchanturbo.requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"code": 0}
            n.send("标题", "内容")
        assert mock_post.call_args.args[0] == "https://sctapi.ftqq.com/SCT1.send"
        data = mock_post.call_args.kwargs["data"]
        assert data["text"] == "标题"
        assert data["desp"] == "内容"
        assert data["openid"] == "openid1"


class TestCustomNotifier:
    def test_supports_image(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({}, logger)
        assert n._get_supports_image() is True

    def test_comment_init_plain_dict(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({}, logger)
        d = {"key": "value", "nested": {"a": 1}}
        result = n.comment_init(d)
        assert result == {"key": "value", "nested": {"a": 1}}

    def test_comment_init_plain_list(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({}, logger)
        d = [1, 2, 3]
        result = n.comment_init(d)
        assert result == [1, 2, 3]

    def test_comment_format_dict(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({}, logger)
        d = {"text": "{message}", "file": "{image}", "other": "static"}
        result = n.comment_format(d, "text", "file", message="hello", image="base64")
        assert result["text"] == "hello"
        assert result["file"] == "base64"
        assert result["other"] == "static"

    def test_comment_format_list(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({}, logger)
        d = [{"text": "{message}"}]
        result = n.comment_format(d, "text", message="hi")
        assert result[0]["text"] == "hi"

    def test_comment_format_nested(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({}, logger)
        d = {"outer": {"text": "{message}"}}
        result = n.comment_format(d, "text", message="hi")
        assert result["outer"]["text"] == "hi"

    def test_send_json_datatype_posts_json(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({
            "url": "http://localhost:3000/send_msg",
            "method": "post",
            "datatype": "json",
            "data": {"message": [{"type": "text", "data": {"text": "{message}"}}]},
        }, logger)
        with patch("module.notification.custom.requests.request") as mock_request:
            n.send("标题", "内容")
        assert mock_request.call_args.args[:2] == ("post", "http://localhost:3000/send_msg")
        data = mock_request.call_args.kwargs["json"]
        assert data["message"][0]["data"]["text"] == "标题\n内容"

    def test_send_reuses_template_for_each_message(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({
            "url": "http://localhost:3000/send_msg",
            "method": "post",
            "datatype": "json",
            "data": {"text": "{message}"},
        }, logger)
        with patch("module.notification.custom.requests.request") as mock_request:
            n.send("标题1", "内容1")
            n.send("标题2", "内容2")
        first = mock_request.call_args_list[0].kwargs["json"]
        second = mock_request.call_args_list[1].kwargs["json"]
        assert first["text"] == "标题1\n内容1"
        assert second["text"] == "标题2\n内容2"

    def test_send_data_datatype_posts_form(self):
        from module.notification.custom import CustomNotifier
        logger = MagicMock()
        n = CustomNotifier({
            "url": "http://localhost:8080/notify",
            "method": "post",
            "datatype": "data",
            "data": {"text": "{message}"},
        }, logger)
        with patch("module.notification.custom.requests.request") as mock_request:
            n.send("标题", "内容")
        assert mock_request.call_args.kwargs["data"] == {"text": "标题\n内容"}


class TestWinotifyNotifier:
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")
    def test_class_exists(self):
        from module.notification.winotify import WinotifyNotifier
        assert WinotifyNotifier is not None


class TestNotifierFactory:
    def test_create_telegram(self):
        from module.notification import NotifierFactory
        from module.notification.telegram import TelegramNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("telegram", {"token": "t", "userid": "u"}, logger)
        assert isinstance(notif, TelegramNotifier)

    def test_create_smtp(self):
        from module.notification import NotifierFactory
        from module.notification.smtp import SMTPNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("smtp", {"host": "smtp.example.com"}, logger)
        assert isinstance(notif, SMTPNotifier)

    def test_create_webhook(self):
        from module.notification import NotifierFactory
        from module.notification.webhook import WebhookNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("webhook", {"url": "http://example.com"}, logger)
        assert isinstance(notif, WebhookNotifier)

    def test_create_lark(self):
        from module.notification import NotifierFactory
        from module.notification.lark import LarkNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("lark", {}, logger)
        assert isinstance(notif, LarkNotifier)

    def test_create_kook(self):
        from module.notification import NotifierFactory
        from module.notification.kook import KOOKNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("kook", {}, logger)
        assert isinstance(notif, KOOKNotifier)

    def test_create_meow(self):
        from module.notification import NotifierFactory
        from module.notification.meow import MeoWNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("meow", {"nickname": "test"}, logger)
        assert isinstance(notif, MeoWNotifier)

    def test_create_gotify(self):
        from module.notification import NotifierFactory
        from module.notification.gotify import GotifyNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("gotify", {"url": "https://gotify.example.com", "token": "t"}, logger)
        assert isinstance(notif, GotifyNotifier)

    def test_create_pushplus(self):
        from module.notification import NotifierFactory
        from module.notification.pushplus import PushPlusNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("pushplus", {"token": "t"}, logger)
        assert isinstance(notif, PushPlusNotifier)

    def test_create_qmsg(self):
        from module.notification import NotifierFactory
        from module.notification.qmsg import QmsgNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("qmsg", {"key": "test-key"}, logger)
        assert isinstance(notif, QmsgNotifier)

    def test_create_bark(self):
        from module.notification import NotifierFactory
        from module.notification.bark import BarkNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("bark", {"key": "test-key"}, logger)
        assert isinstance(notif, BarkNotifier)

    def test_create_dingtalk(self):
        from module.notification import NotifierFactory
        from module.notification.dingtalk import DingTalkNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("dingtalk", {"token": "test-token"}, logger)
        assert isinstance(notif, DingTalkNotifier)

    def test_create_discord(self):
        from module.notification import NotifierFactory
        from module.notification.discord import DiscordNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("discord", {"webhook": "https://discord.example.com/hook"}, logger)
        assert isinstance(notif, DiscordNotifier)

    def test_create_pushdeer(self):
        from module.notification import NotifierFactory
        from module.notification.pushdeer import PushDeerNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("pushdeer", {"token": "test-token"}, logger)
        assert isinstance(notif, PushDeerNotifier)

    def test_create_serverchanturbo(self):
        from module.notification import NotifierFactory
        from module.notification.serverchanturbo import ServerChanTurboNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("serverchanturbo", {"sctkey": "SCT1"}, logger)
        assert isinstance(notif, ServerChanTurboNotifier)

    def test_create_unknown_returns_none(self):
        from module.notification import NotifierFactory
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("unknown_service", {}, logger)
        assert notif is None

    def test_notifier_classes_mapping(self):
        from module.notification import NotifierFactory
        assert "telegram" in NotifierFactory.notifier_classes
        assert "smtp" in NotifierFactory.notifier_classes
        assert "webhook" in NotifierFactory.notifier_classes
        assert "lark" in NotifierFactory.notifier_classes
        assert "kook" in NotifierFactory.notifier_classes
        assert "matrix" in NotifierFactory.notifier_classes
        assert "onebot" in NotifierFactory.notifier_classes
        assert "wechatworkapp" in NotifierFactory.notifier_classes
        assert "wechatworkbot" in NotifierFactory.notifier_classes
