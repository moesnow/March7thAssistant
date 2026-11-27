from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from module.content_visibility import Visibility
from module.game.adb_transport import AdbError
from module.settings_registry import find_setting
from tasks.daily import redemption
from utils.pause import RunStopRequested
from utils.tasks import task_is_supported


class ExchangeUI:
    """按界面推进的兑换窗口；漏读只影响识别，不能再次提交兑换。"""

    def __init__(self, outcomes, *, permission=False, input_delay=1, result_delay=1, stop=False):
        self.outcomes = outcomes
        self.permission = permission
        self.input_delay = input_delay
        self.result_delay = result_delay
        self.stop = stop
        self.index = -1
        self.page = "menu"
        self.pastes = []
        self.submits = []
        self.keys = []
        self.polls = 0
        self.input_polls = 0
        self.permission_clicks = 0

    def change_to(self, target):
        assert target == "redemption"
        self.index += 1
        self.page = "input"
        self.polls = self.input_polls = 0

    def find_element(self, target, kind, *args, **kwargs):
        if isinstance(target, str) and target.endswith("clear.png"):
            # PC 内部 find_element 的多次截图在这里一并模拟。
            self.input_polls += kwargs.get("max_retries", 1)
            return self.page == "input" and not self.permission and self.input_polls >= self.input_delay
        if target == redemption.CLIPBOARD_PROMPT:
            return self.permission and self.index in self.pastes
        if target == "兑换提示":
            return self.page == "result" and self.outcomes[self.index] == "兑换成功"
        assert target[0] in ("兑换成功", "兑换码已过期")
        if self.stop:
            raise RunStopRequested()
        self.polls += 1
        if self.polls >= self.result_delay and self.outcomes[self.index]:
            # 1280×720 实机：成功文字在弹窗正文，已使用等错误在输入框下方的提示条。
            outcome = self.outcomes[self.index]
            if outcome not in target:
                return False
            box = (577, 315, 705, 345) if outcome == "兑换成功" else (577, 433, 705, 457)
            x, y, width, height = kwargs.get("crop", (0, 0, 1, 1))
            if not (x * 1280 <= box[0] and y * 720 <= box[1]
                    and (x + width) * 1280 >= box[2] and (y + height) * 720 >= box[3]):
                return False
            self.matched_text = self.outcomes[self.index]
            return True
        return False

    def click_element(self, target, kind, *args, **kwargs):
        if isinstance(target, str) and target.endswith("paste.png"):
            self.pastes.append(self.index)
        elif target == "粘贴":
            assert self.permission
            self.permission = False
            self.permission_clicks += 1
        elif isinstance(target, str) and target.endswith("confirm.png") and self.page == "input":
            self.submits.append(self.index)
            self.page = "result"
        else:
            assert target in ("确认", "取消") or target.endswith("confirm.png")
            self.page = "menu"
        return True

    def press_key(self, key):
        self.keys.append(key)
        self.page = "menu"

    def wait_for_screen_change(self, target):
        assert target == self.page == "menu"


def install(monkeypatch, backend, outcomes, **options):
    config = SimpleNamespace(control_backend=backend, already_used_codes=[], redemption_code=["CODE1", "CODE2"])
    config.set_value = lambda key, value: setattr(config, key, list(value))
    ui = ExchangeUI(outcomes, **options)
    game = Mock()
    mail = Mock(side_effect=RuntimeError("邮件暂时不可用"))
    monkeypatch.setattr(redemption, "cfg", config)
    monkeypatch.setattr(redemption, "auto", ui)
    monkeypatch.setattr(redemption, "screen", ui)
    monkeypatch.setattr(redemption, "get_game_controller", lambda: game)
    monkeypatch.setattr(redemption, "time", SimpleNamespace(sleep=lambda _: None))
    monkeypatch.setattr("tasks.reward.start_specific", mail)
    monkeypatch.setattr("tasks.touch.rewards.claim_mail", mail)
    return config, ui, game, mail


@pytest.mark.parametrize("backend", ["local", "cloud", "adb"])
@pytest.mark.parametrize("outcome", ["兑换成功", "兑换码已过期", "无效的兑换码", "兑换码已被使用", None])
def test_shared_batch_keeps_confirmed_outcomes_and_never_resubmits(monkeypatch, backend, outcome):
    cfg, ui, game, mail = install(monkeypatch, backend, [outcome, "兑换成功"], input_delay=3, result_delay=4)
    assert redemption.Redemption.start() is (outcome is not None)
    assert cfg.already_used_codes == (["CODE2"] if outcome is None else ["CODE1", "CODE2"])
    assert ui.pastes == ui.submits == [0, 1]
    assert game.copy.call_count == 2
    mail.assert_called_once()
    if backend == "adb":
        assert ui.keys == []


def test_batch_reports_how_many_codes_got_each_result(monkeypatch):
    install(monkeypatch, "adb", ["兑换码已被使用", "兑换成功"])
    summary = Mock()
    assert redemption.Redemption.start(on_summary=summary)
    summary.assert_called_once_with("兑换成功 1 个，兑换码已被使用 1 个")


def test_adb_accepts_first_clipboard_prompt_without_pasting_twice(monkeypatch):
    cfg, ui, _, _ = install(monkeypatch, "adb", ["兑换成功"], permission=True)
    assert redemption.Redemption.start(["中文兑换码"])
    assert ui.permission_clicks == 1
    assert ui.pastes == ui.submits == [0]
    assert cfg.already_used_codes == ["中文兑换码"]


def test_failed_clipboard_does_not_paste_the_previous_code(monkeypatch):
    cfg, ui, game, _ = install(monkeypatch, "adb", [None, "兑换成功"])
    game.copy.side_effect = [False, True]
    assert redemption.Redemption.start() is False
    assert ui.pastes == ui.submits == [1]
    assert cfg.already_used_codes == ["CODE2"]


@pytest.mark.parametrize("backend", ["local", "cloud", "adb"])
@pytest.mark.parametrize("outcomes, expected", [
    (["兑换码已过期"] * 3, True),
    (["兑换码已被使用"] * 3, True),
    (["无效的兑换码"] * 3, True),
    (["兑换码已过期", "兑换码已被使用", "无效的兑换码"], True),
    (["兑换成功", "兑换码已过期", "兑换码已被使用"], True),
    (["兑换成功", None, "兑换码已过期"], False),
    (["兑换码已过期", None, "兑换码已被使用"], False),
    ([None] * 3, False),
])
def test_batch_completion_depends_on_confirmed_results_not_new_rewards(monkeypatch, backend, outcomes, expected):
    cfg, ui, _, mail = install(monkeypatch, backend, outcomes)
    codes = ["CODE1", "CODE2", "CODE3"]
    assert redemption.Redemption.start(codes) is expected
    assert cfg.already_used_codes == [code for code, outcome in zip(codes, outcomes) if outcome]
    assert ui.pastes == ui.submits == [0, 1, 2]
    assert mail.call_count == (1 if "兑换成功" in outcomes else 0)


@pytest.mark.parametrize("backend", ["local", "cloud", "adb"])
def test_previous_history_does_not_hide_this_runs_unconfirmed_results(monkeypatch, backend):
    cfg, _, _, _ = install(monkeypatch, backend, [None, None])
    cfg.already_used_codes = cfg.redemption_code.copy()
    assert redemption.Redemption.start() is False


def test_unavailable_clipboard_fails_only_the_redemption_step(monkeypatch):
    cfg, ui, game, _ = install(monkeypatch, "adb", [None])
    game.copy.side_effect = AdbError("unsupported", "剪贴板不可用")
    assert redemption.Redemption.start(["CODE1"]) is False
    assert not cfg.already_used_codes and not ui.pastes


def test_persistent_input_failure_is_bounded_and_the_next_code_continues(monkeypatch):
    cfg, ui, _, _ = install(monkeypatch, "adb", [None, None], input_delay=100)
    assert redemption.Redemption.start() is False
    assert ui.pastes == [0, 1] and not ui.submits and ui.input_polls == 6
    assert not cfg.already_used_codes and not ui.keys


def test_user_stop_propagates_without_dismiss_or_next_code(monkeypatch):
    cfg, ui, game, mail = install(monkeypatch, "adb", [None, "兑换成功"], stop=True)
    with pytest.raises(RunStopRequested):
        redemption.Redemption.start()
    assert ui.submits == [0] and ui.page == "result"
    assert game.copy.call_count == 1
    assert not cfg.already_used_codes and not mail.called


def test_adb_automatic_fetch_uses_cn_server_and_leaves_unknown_codes_for_next_time(monkeypatch):
    cfg, _, _, _ = install(monkeypatch, "adb", ["兑换码已过期", None])
    fetch = Mock(return_value=["CODE1", "CODE2"])
    monkeypatch.setattr(redemption, "valid_codes_for_server", fetch)
    assert redemption.Redemption.get() is False
    fetch.assert_called_once_with("cn")
    assert cfg.already_used_codes == ["CODE1"]


def test_adb_catalog_opens_manual_and_automatic_redemption():
    from module.content_samples import SampleConfig
    cfg = SampleConfig()
    cfg.set_values({"control_backend": "adb", "ui_profile": "touch_720"})
    assert task_is_supported("redemption", cfg)
    visibility = Visibility.read(cfg)
    assert visibility.tool("redemption")
    assert visibility.setting(find_setting("reward_redemption_code_enable"))
    assert not task_is_supported("character_export", cfg)


def test_touch_navigation_reaches_redemption_and_returns_to_mail():
    from module.screen.screen import Screen
    navigator = object.__new__(Screen)
    navigator.__init__(config_path="assets/touch_720/screens.json", logger=Mock())
    assert navigator.find_shortest_path("main", "redemption") == ["main", "menu", "redemption"]
    assert navigator.find_shortest_path("redemption", "mail") == ["redemption", "menu", "mail"]


def test_automatic_redemption_failure_keeps_later_independent_tasks(monkeypatch):
    from module.content_samples import SampleConfig
    from tasks.base import task_steps
    from tasks.touch import rewards
    cfg = SampleConfig()
    cfg.set_values({"control_backend": "adb", "reward_enable": True, "reward_redemption_code_enable": True,
                    "power_enable": False})
    monkeypatch.setattr(rewards, "cfg", cfg)
    monkeypatch.setattr(redemption.Redemption, "get", Mock(return_value=False))
    claim = Mock(return_value=True)
    training = Mock(return_value=True)
    monkeypatch.setattr(rewards, "claim", claim)
    monkeypatch.setattr(rewards.daily, "run", training)
    recover = Mock()
    monkeypatch.setattr(task_steps, "screen", recover)
    assert rewards.routine() is False
    claim.assert_called_once()
    training.assert_called_once()
    recover.change_to.assert_called_once_with("main", max_recursion=1)
