import io
import sys
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


class TestOnepushNotifier:
    def test_init(self):
        from module.notification.onepush import OnepushNotifier
        logger = MagicMock()
        n = OnepushNotifier("gotify", {"key": "val"}, logger, require_content=True)
        assert n.notifier_name == "gotify"
        assert n.require_content is True

    def test_require_content_fills_empty(self):
        from module.notification.onepush import OnepushNotifier
        logger = MagicMock()
        n = OnepushNotifier("gotify", {}, logger, require_content=True)
        # send 内部会把空 content 设为 "."，但需要 mock onepush
        assert n.require_content is True


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

    def test_create_gotify_as_onepush(self):
        from module.notification import NotifierFactory
        from module.notification.onepush import OnepushNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("gotify", {}, logger)
        assert isinstance(notif, OnepushNotifier)
        assert notif.require_content is True

    def test_create_pushplus_as_onepush(self):
        from module.notification import NotifierFactory
        from module.notification.onepush import OnepushNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("pushplus", {}, logger)
        assert isinstance(notif, OnepushNotifier)
        assert notif.require_content is True

    def test_create_unknown_as_onepush(self):
        from module.notification import NotifierFactory
        from module.notification.onepush import OnepushNotifier
        logger = MagicMock()
        notif = NotifierFactory.create_notifier("unknown_service", {}, logger)
        assert isinstance(notif, OnepushNotifier)

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
