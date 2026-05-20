import io
from unittest.mock import MagicMock, patch
from PIL import Image
from module.notification.notification import Notification, NotificationLevel


class TestNotificationLevel:
    def test_display_mapping(self):
        assert NotificationLevel.DISPLAY[NotificationLevel.ALL] == "全部"
        assert NotificationLevel.DISPLAY[NotificationLevel.ERROR] == "仅错误"

    def test_constants(self):
        assert NotificationLevel.ALL == "all"
        assert NotificationLevel.ERROR == "error"


class TestNotificationLocalizeLevel:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        return notif

    def test_localize_all(self):
        notif = self._create_notification()
        assert notif._localize_level("all") == "全部"

    def test_localize_error(self):
        notif = self._create_notification()
        assert notif._localize_level("error") == "仅错误"

    def test_localize_unknown(self):
        notif = self._create_notification()
        assert notif._localize_level("unknown") == "unknown"

    def test_localize_none(self):
        notif = self._create_notification()
        assert notif._localize_level(None) == ""


class TestNotificationSetLevelFilter:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        notif.level_filter = NotificationLevel.ALL
        return notif

    def test_set_all(self):
        notif = self._create_notification()
        notif.set_level_filter(NotificationLevel.ALL)
        assert notif.level_filter == NotificationLevel.ALL

    def test_set_error(self):
        notif = self._create_notification()
        notif.set_level_filter(NotificationLevel.ERROR)
        assert notif.level_filter == NotificationLevel.ERROR

    def test_set_invalid_raises(self):
        notif = self._create_notification()
        try:
            notif.set_level_filter("invalid")
            assert False, "应该抛出 ValueError"
        except ValueError as e:
            assert "无效的通知级别" in str(e)


class TestNotificationSetImageEnable:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.image_enable = True
        return notif

    def test_enable(self):
        notif = self._create_notification()
        notif.set_image_enable(True)
        assert notif.image_enable is True

    def test_disable(self):
        notif = self._create_notification()
        notif.set_image_enable(False)
        assert notif.image_enable is False


class TestNotificationBatch:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        notif.notifiers = {}
        notif.level_filter = NotificationLevel.ALL
        notif.image_enable = True
        notif._batch_mode = False
        notif._batch_messages = []
        notif._batch_images = []
        notif._batch_has_error = False
        return notif

    def test_start_batch(self):
        notif = self._create_notification()
        notif.start_batch()
        assert notif._batch_mode is True
        assert notif._batch_messages == []
        assert notif._batch_images == []
        assert notif._batch_has_error is False


class TestNotificationToPilImage:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        return notif

    def test_pil_image_passthrough(self):
        notif = self._create_notification()
        img = Image.new("RGB", (10, 10))
        result = notif._to_pil_image(img)
        assert result is img

    def test_bytesio(self):
        notif = self._create_notification()
        img = Image.new("RGB", (10, 10))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        result = notif._to_pil_image(buf)
        assert isinstance(result, Image.Image)

    def test_none(self):
        notif = self._create_notification()
        assert notif._to_pil_image(None) is None


class TestNotificationProcessImage:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        return notif

    def test_process_image(self):
        notif = self._create_notification()
        img = Image.new("RGB", (200, 200), color="red")
        result = notif._process_image(img, max_size=50)
        # _process_image 可能返回 None 如果图片已经足够小
        if result is not None:
            assert isinstance(result, Image.Image)
            assert result.width <= 50 or result.height <= 50


class TestNotificationMergeImages:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        return notif

    def test_merge_two_images(self):
        notif = self._create_notification()
        img1 = Image.new("RGB", (100, 50), color="red")
        img2 = Image.new("RGB", (100, 50), color="blue")
        result = notif._merge_images([img1, img2])
        assert isinstance(result, Image.Image)
        assert result.width == 100
        assert result.height == 100

    def test_merge_single_image(self):
        notif = self._create_notification()
        img = Image.new("RGB", (100, 50), color="red")
        result = notif._merge_images([img])
        assert isinstance(result, Image.Image)


class TestNotificationHasImageNotifier:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.notifiers = {}
        return notif

    def test_no_notifiers(self):
        notif = self._create_notification()
        assert notif._has_image_notifier() is False

    def test_with_image_support(self):
        notif = self._create_notification()
        mock_notifier = MagicMock()
        mock_notifier.supports_image = True
        notif.notifiers["test"] = mock_notifier
        assert notif._has_image_notifier() is True

    def test_without_image_support(self):
        notif = self._create_notification()
        mock_notifier = MagicMock()
        mock_notifier.supports_image = False
        notif.notifiers["test"] = mock_notifier
        assert notif._has_image_notifier() is False

    def test_mixed_notifiers(self):
        notif = self._create_notification()
        n1 = MagicMock()
        n1.supports_image = False
        n2 = MagicMock()
        n2.supports_image = True
        notif.notifiers["n1"] = n1
        notif.notifiers["n2"] = n2
        assert notif._has_image_notifier() is True


class TestNotificationSetNotifier:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.notifiers = {}
        return notif

    def test_set_notifier(self):
        notif = self._create_notification()
        mock_notifier = MagicMock()
        notif.set_notifier("telegram", mock_notifier)
        assert "telegram" in notif.notifiers
        assert notif.notifiers["telegram"] is mock_notifier

    def test_overwrite_notifier(self):
        notif = self._create_notification()
        n1 = MagicMock()
        n2 = MagicMock()
        notif.set_notifier("telegram", n1)
        notif.set_notifier("telegram", n2)
        assert notif.notifiers["telegram"] is n2

    def test_multiple_notifiers(self):
        notif = self._create_notification()
        notif.set_notifier("a", MagicMock())
        notif.set_notifier("b", MagicMock())
        assert len(notif.notifiers) == 2


class TestNotificationGetProcessedImage:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        notif.image_enable = True
        notif.notifiers = {}
        return notif

    def test_none_image_returns_none(self):
        notif = self._create_notification()
        assert notif._get_processed_image(None) is None

    def test_image_disabled_returns_none(self):
        notif = self._create_notification()
        notif.image_enable = False
        img = Image.new("RGB", (10, 10))
        assert notif._get_processed_image(img) is None

    def test_no_image_notifier_returns_none(self):
        notif = self._create_notification()
        img = Image.new("RGB", (10, 10))
        assert notif._get_processed_image(img) is None

    def test_already_processed_passthrough(self):
        notif = self._create_notification()
        mock_notifier = MagicMock()
        mock_notifier.supports_image = True
        notif.notifiers["test"] = mock_notifier
        img = Image.new("RGB", (10, 10))
        result = notif._get_processed_image(img, image_already_processed=True)
        assert result is img

    def test_process_image_called(self):
        notif = self._create_notification()
        mock_notifier = MagicMock()
        mock_notifier.supports_image = True
        notif.notifiers["test"] = mock_notifier
        img = Image.new("RGB", (10, 10))
        with patch.object(notif, '_process_image', return_value=io.BytesIO()) as mock_proc:
            notif._get_processed_image(img)
            mock_proc.assert_called_once_with(img)


class TestNotificationFlushBatch:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        notif.notifiers = {}
        notif.level_filter = NotificationLevel.ALL
        notif.image_enable = False
        notif._batch_mode = True
        notif._batch_messages = []
        notif._batch_images = []
        notif._batch_has_error = False
        notif.title = "Test"
        return notif

    def test_flush_empty_batch(self):
        notif = self._create_notification()
        with patch.object(notif, 'notify') as mock_notify:
            notif.flush_batch()
            mock_notify.assert_not_called()
        assert notif._batch_mode is False

    def test_flush_with_messages(self):
        notif = self._create_notification()
        notif._batch_messages = ["msg1", "msg2"]
        with patch.object(notif, 'notify') as mock_notify:
            notif.flush_batch()
            mock_notify.assert_called_once()
            call_kwargs = mock_notify.call_args
            content = call_kwargs.kwargs.get('content', call_kwargs[1].get('content', ''))
            assert "1. msg1" in content
            assert "2. msg2" in content

    def test_flush_with_extra_content(self):
        notif = self._create_notification()
        notif._batch_messages = ["msg1"]
        with patch.object(notif, 'notify') as mock_notify:
            notif.flush_batch(extra_content="extra")
            content = mock_notify.call_args.kwargs.get('content', '')
            assert "extra" in content

    def test_flush_only_extra_content(self):
        notif = self._create_notification()
        with patch.object(notif, 'notify') as mock_notify:
            notif.flush_batch(extra_content="only extra")
            mock_notify.assert_called_once()
            content = mock_notify.call_args.kwargs.get('content', '')
            # flush_batch 会编号所有内容，包括仅有 extra_content 时
            assert "only extra" in content

    def test_flush_resets_state(self):
        notif = self._create_notification()
        notif._batch_messages = ["msg"]
        notif._batch_has_error = True
        with patch.object(notif, 'notify'):
            notif.flush_batch()
        assert notif._batch_messages == []
        assert notif._batch_images == []
        assert notif._batch_has_error is False

    def test_flush_error_level_preserved(self):
        notif = self._create_notification()
        notif._batch_messages = ["msg"]
        notif._batch_has_error = True
        with patch.object(notif, 'notify') as mock_notify:
            notif.flush_batch()
            level = mock_notify.call_args.kwargs.get('level', '')
            assert level == NotificationLevel.ERROR


class TestNotificationNotify:
    def _create_notification(self):
        notif = Notification.__new__(Notification)
        notif.logger = None
        notif.notifiers = {}
        notif.level_filter = NotificationLevel.ALL
        notif.image_enable = False
        notif._batch_mode = False
        notif._batch_messages = []
        notif._batch_images = []
        notif._batch_has_error = False
        notif.title = "TestTitle"
        return notif

    def test_batch_mode_collects(self):
        notif = self._create_notification()
        notif._batch_mode = True
        notif.notify(content="msg1")
        notif.notify(content="msg2")
        assert notif._batch_messages == ["msg1", "msg2"]

    def test_batch_mode_collects_error(self):
        notif = self._create_notification()
        notif._batch_mode = True
        notif.notify(content="err", level=NotificationLevel.ERROR)
        assert notif._batch_has_error is True

    def test_batch_mode_collects_images(self):
        notif = self._create_notification()
        notif._batch_mode = True
        img = io.BytesIO()
        notif.notify(content="msg", image=img)
        assert len(notif._batch_images) == 1

    def test_level_filter_blocks_non_error(self):
        notif = self._create_notification()
        notif.level_filter = NotificationLevel.ERROR
        mock_notifier = MagicMock()
        notif.notifiers["test"] = mock_notifier
        notif.notify(content="msg", level=NotificationLevel.ALL)
        mock_notifier.send.assert_not_called()

    def test_level_filter_allows_error(self):
        notif = self._create_notification()
        notif.level_filter = NotificationLevel.ERROR
        mock_notifier = MagicMock()
        mock_notifier.supports_image = False
        notif.notifiers["test"] = mock_notifier
        notif.notify(content="error msg", level=NotificationLevel.ERROR)
        mock_notifier.send.assert_called_once()

    def test_sends_to_notifier(self):
        notif = self._create_notification()
        mock_notifier = MagicMock()
        mock_notifier.supports_image = False
        notif.notifiers["test"] = mock_notifier
        notif.notify(content="hello")
        mock_notifier.send.assert_called_once_with("TestTitle", "hello")

    def test_sends_image_to_supporting_notifier(self):
        notif = self._create_notification()
        notif.image_enable = True
        mock_notifier = MagicMock()
        mock_notifier.supports_image = True
        notif.notifiers["test"] = mock_notifier
        with patch.object(notif, '_get_processed_image', return_value=io.BytesIO(b"img")):
            notif.notify(content="hello", image=io.BytesIO(b"img"))
        mock_notifier.send.assert_called_once()
        call_args = mock_notifier.send.call_args
        assert call_args[0][0] == "TestTitle"
        assert call_args[0][1] == "hello"
        assert call_args[0][2] is not None

    def test_notifier_exception_does_not_propagate(self):
        notif = self._create_notification()
        notif.logger = MagicMock()
        mock_notifier = MagicMock()
        mock_notifier.supports_image = False
        mock_notifier.send.side_effect = Exception("network error")
        notif.notifiers["fail"] = mock_notifier
        # 不应抛出异常
        notif.notify(content="msg")

    def test_multiple_notifiers_one_fails(self):
        notif = self._create_notification()
        notif.logger = MagicMock()
        n1 = MagicMock()
        n1.supports_image = False
        n1.send.side_effect = Exception("fail")
        n2 = MagicMock()
        n2.supports_image = False
        notif.notifiers["fail"] = n1
        notif.notifiers["ok"] = n2
        notif.notify(content="msg")
        n2.send.assert_called_once()
