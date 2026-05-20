from unittest.mock import MagicMock
from module.notification.webhook import WebhookNotifier


class TestWebhookReplacePlaceholders:
    def _create_notifier(self):
        notif = WebhookNotifier.__new__(WebhookNotifier)
        notif.logger = MagicMock()
        return notif

    def test_string_replacement(self):
        notif = self._create_notifier()
        result = notif._replace_placeholders("{title} - {content}", "T", "C")
        assert result == "T - C"

    def test_dict_replacement(self):
        notif = self._create_notifier()
        obj = {"title": "{title}", "body": "{content}"}
        result = notif._replace_placeholders(obj, "Hello", "World")
        assert result == {"title": "Hello", "body": "World"}

    def test_list_replacement(self):
        notif = self._create_notifier()
        obj = ["{title}", "{content}"]
        result = notif._replace_placeholders(obj, "T", "C")
        assert result == ["T", "C"]

    def test_nested_dict(self):
        notif = self._create_notifier()
        obj = {"outer": {"inner": "{title}"}}
        result = notif._replace_placeholders(obj, "T", "C")
        assert result == {"outer": {"inner": "T"}}

    def test_nested_list_in_dict(self):
        notif = self._create_notifier()
        obj = {"items": ["{title}", "{content}"]}
        result = notif._replace_placeholders(obj, "T", "C")
        assert result == {"items": ["T", "C"]}

    def test_non_string_passthrough(self):
        notif = self._create_notifier()
        obj = {"num": 42, "flag": True, "none": None}
        result = notif._replace_placeholders(obj, "T", "C")
        assert result == {"num": 42, "flag": True, "none": None}

    def test_image_placeholder(self):
        notif = self._create_notifier()
        result = notif._replace_placeholders("img:{image}", "T", "C", "base64data")
        assert result == "img:base64data"

    def test_empty_string(self):
        notif = self._create_notifier()
        result = notif._replace_placeholders("", "T", "C")
        assert result == ""

    def test_no_placeholders(self):
        notif = self._create_notifier()
        result = notif._replace_placeholders("no placeholders here", "T", "C")
        assert result == "no placeholders here"


class TestWebhookInit:
    def test_missing_url_raises(self):
        logger = MagicMock()
        try:
            WebhookNotifier({}, logger)
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "URL is required" in str(e)

    def test_default_method_is_post(self):
        logger = MagicMock()
        notif = WebhookNotifier({"url": "http://example.com"}, logger)
        assert notif.method == "POST"

    def test_custom_method(self):
        logger = MagicMock()
        notif = WebhookNotifier({"url": "http://example.com", "method": "put"}, logger)
        assert notif.method == "PUT"

    def test_headers_json_string(self):
        logger = MagicMock()
        notif = WebhookNotifier({"url": "http://example.com", "headers": '{"Auth": "token"}'}, logger)
        assert notif.headers == {"Auth": "token"}

    def test_headers_invalid_json(self):
        logger = MagicMock()
        notif = WebhookNotifier({"url": "http://example.com", "headers": "not-json"}, logger)
        assert notif.headers == {}

    def test_body_template_json_string(self):
        logger = MagicMock()
        notif = WebhookNotifier({"url": "http://example.com", "body": '{"key": "value"}'}, logger)
        assert notif.body_template == {"key": "value"}

    def test_body_template_plain_string(self):
        logger = MagicMock()
        notif = WebhookNotifier({"url": "http://example.com", "body": "plain text"}, logger)
        assert notif.body_template == "plain text"


class TestWebhookSupportsImage:
    def test_supports_image(self):
        logger = MagicMock()
        notif = WebhookNotifier({"url": "http://example.com"}, logger)
        assert notif._get_supports_image() is True
        assert notif.supports_image is True
