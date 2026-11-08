import sys
from unittest.mock import Mock

import pytest

from module.update.version_check import UpdateInfo, VersionCheckError

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="更新器窗口仅支持 Windows")


@pytest.fixture
def helper_app():
    # 非 Windows 下导入即抛 RuntimeError，不能放在模块顶层
    from module.update import helper_app
    return helper_app


@pytest.fixture
def engine(helper_app, monkeypatch):
    engine = Mock(spec=helper_app.UpdateEngine, download_url=None)
    monkeypatch.setattr(helper_app, "UpdateEngine", Mock(return_value=engine))
    return engine


@pytest.fixture
def make_window(helper_app, engine, monkeypatch):
    """构造不创建真实窗口、不执行真实更新的更新器窗口。"""
    monkeypatch.setattr(helper_app, "user32", Mock())

    def _make_window(check):
        monkeypatch.setattr(helper_app, "check_for_update", check)
        return helper_app.NativeUpdaterWindow(helper_app.parse_args([]))

    return _make_window


class TestVersionCheckResult:
    @pytest.mark.parametrize("error", [
        VersionCheckError("检测更新失败: 请稍后重试"),
        OSError("检测更新失败: 请稍后重试"),
    ])
    def test_check_failure_is_not_reported_as_latest(self, make_window, error):
        window = make_window(Mock(side_effect=error))

        window._worker_main()

        assert window._current_result.kind == "failed"
        assert window._current_result.message == "检测更新失败: 请稍后重试"
        assert window._status_text == "检测更新失败: 请稍后重试"
        assert window._no_update_deadline is None

    def test_no_update_is_still_reported(self, helper_app, make_window):
        window = make_window(Mock(return_value=None))

        window._worker_main()

        assert window._current_result.kind == "no-update"
        assert window._current_result.message == helper_app.tr("当前已是最新版本")
        assert window._no_update_deadline is not None

    def test_new_version_still_starts_update(self, helper_app, make_window, engine):
        info = UpdateInfo(source="GitHub", url="https://example.com/a.7z", file_name="a.7z", version="v9.9.9")
        window = make_window(Mock(return_value=info))

        window._worker_main()

        engine.set_update_info.assert_called_once_with(info)
        engine.run_full_update.assert_called_once()
        assert window._current_result.kind == "success"


class TestVersionCheckRetry:
    def test_failure_dialog_retries_check(self, helper_app, make_window):
        check = Mock(side_effect=[VersionCheckError("检测更新失败: 请稍后重试"), None])
        window = make_window(check)
        window._worker_main()
        helper_app.user32.MessageBoxW.return_value = helper_app.IDRETRY

        window._process_result_state()
        window._thread.join(timeout=5)

        _, text, _, flags = helper_app.user32.MessageBoxW.call_args.args
        assert "请稍后重试" in text
        assert flags & helper_app.MB_RETRYCANCEL == helper_app.MB_RETRYCANCEL
        assert check.call_count == 2
        assert window._current_result.kind == "no-update"
        helper_app.user32.DestroyWindow.assert_not_called()

    def test_failure_dialog_cancel_closes_window(self, helper_app, make_window):
        check = Mock(side_effect=VersionCheckError("检测更新失败"))
        window = make_window(check)
        window._worker_main()
        helper_app.user32.MessageBoxW.return_value = helper_app.IDCANCEL

        window._process_result_state()

        assert check.call_count == 1
        helper_app.user32.DestroyWindow.assert_called_once()

    def test_retry_replaces_failure_text_while_checking(self, helper_app, make_window):
        seen = []

        def check(*args):
            seen.append((window._title_text, window._status_text, window._indeterminate))
            if len(seen) == 1:
                raise VersionCheckError("检测更新失败")

        window = make_window(check)
        window._worker_main()
        helper_app.user32.MessageBoxW.return_value = helper_app.IDRETRY

        window._process_result_state()
        window._thread.join(timeout=5)

        assert seen[1] == (helper_app.tr("正在更新 March7th Assistant"), helper_app.tr("正在检测更新"), True)


class TestVersionCheckCancel:
    def test_cancel_during_failing_check_closes_without_dialog(self, helper_app, make_window):
        def check(*args):
            window._request_cancel_from_ui()
            raise VersionCheckError("检测更新失败")

        window = make_window(check)

        window._worker_main()
        window._process_result_state()

        assert window._current_result.kind == "cancelled"
        helper_app.user32.MessageBoxW.assert_not_called()
        helper_app.user32.DestroyWindow.assert_called_once()
