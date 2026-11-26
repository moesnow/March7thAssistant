"""游戏登录框里切换账号的判断规则。用假号码和实机截图量出来的坐标，不碰游戏。"""

import pytest

from module.accounts.errors import AccountError
from module.accounts.login_records import (
    Line,
    LoginSwitch,
    accounts_in,
    banner_account,
    classify,
    mask_hint,
    same_account,
)

TARGET, OTHER = "155******08", "166******08"  # 后两位相同，只能靠开头区分


def line(text, x, y, w=100, h=28):
    return Line(text, x, y, w, h)


def title():
    return [line("登出", 1809, 384, 41, 34), line("退出", 1805, 483, 47, 26), line("点击进入", 906, 999, 106, 31)]


def start_screen():
    return [line("登出", 1807, 388, 43, 27), line("退出", 1806, 484, 46, 25), line("开始游戏", 871, 814, 196, 48),
            line("星穹列车", 927, 898, 103, 28)]


def logout_dialog():
    return title() + [
        line("退出登录", 910, 397, 100, 28),
        line("退出并清除登录记录", 691, 465, 218, 22),
        line("下次在该设备需要重新登录当前账号", 718, 500, 288, 23),
        line("退出并保留登录记录", 714, 558, 195, 23),
        line("下次在该设备支持自动登录当前账号，请确保设备可信", 718, 593, 433, 22),
        line("取消", 784, 662, 57, 33),
        line("退出", 1059, 662, 58, 33),
    ]


def logged_out():
    return [line("12+", 52, 67, 86, 56), line("登入", 1807, 185, 43, 44), line("退出", 1806, 292, 45, 26)]


def record_box(current):
    return logged_out() + [line("miHoYo", 870, 368, 179, 60), line(current, 785, 482, 115, 27),
                           line("进入游戏", 909, 611, 104, 31), line("登录其他账号", 887, 690, 146, 27)]


def record_list(current, rows):
    lines = logged_out() + [line("miHoYo", 870, 368, 179, 60), line(current, 785, 482, 115, 27)]
    y = 549
    for text, when in rows:
        lines += [line(text, 785, y, 115, 27), line(when, 789, y + 42, 68, 24)]
        y += 89
    return lines + [line("登录其他账号", 898, y + 1, 123, 23)]


def welcome(shown):
    return start_screen() + [line(f"{shown}，欢迎进入游戏", 827, 170, 351, 32)]


class FakeGame:
    """按点击切换画面的假游戏。点到删除记录、清除登录记录或退出游戏就直接判错。"""

    def __init__(self, *, current=OTHER, records=((OTHER, "刚刚"), (TARGET, "46分钟前")), keep=True,
                 keep_clickable=True, valid=(TARGET, OTHER), screen="title"):
        self.screen, self.current, self.records = screen, current, list(records)
        self.keep, self.keep_clickable, self.valid = keep, keep_clickable, set(valid)
        self.clicks, self.time = [], 0.0

    def frame(self):
        self.time += 10
        if self.screen == "welcome":
            self.screen = "start"
            return welcome(self.current)
        return {
            "title": title,
            "start": start_screen,
            "logout": logout_dialog,
            "box": lambda: record_box(self.current),
            "list": lambda: record_list(self.current, self.records),
            "credentials": lambda: [line("输入手机号", 800, 480, 200, 28), line("获取验证码", 900, 560, 120, 28)],
            "verify": lambda: [line("请完成安全验证", 820, 420, 280, 30)],
        }[self.screen]()

    def checked(self, keep_line, clear_line):
        return self.keep, not self.keep

    def click(self, x, y):
        self.clicks.append((round(x), round(y)))
        assert not (x >= 1740 and 470 <= y <= 520), "点到了退出游戏"
        assert not (x >= 1230 and 330 <= y <= 390), "点到了登录框的关闭按钮"
        if self.screen == "title" or self.screen == "start":
            if x >= 1740 and 370 <= y <= 430:
                self.screen = "logout"
        elif self.screen == "logout":
            assert not (y < 520 and x < 960), "点到了退出并清除登录记录"
            if 1040 <= x <= 1140 and 650 <= y <= 700:
                if self.keep:
                    self.screen = "box"
            elif 760 <= x <= 860 and 650 <= y <= 700:
                self.screen = "title"
            elif 540 <= y <= 600 and self.keep_clickable:
                self.keep = True
        elif self.screen == "box":
            if abs(x - 1198) < 30 and abs(y - 495) < 20:
                self.screen = "list"
            elif 900 <= x <= 1020 and 600 <= y <= 650:
                self.screen = "welcome" if self.current in self.valid else "credentials"
        elif self.screen == "list":
            assert x < 1140, "点到了删除登录记录"
            for index, (text, _) in enumerate(self.records):
                if abs(y - (562 + 89 * index)) < 20:
                    self.current = text
                    self.screen = "box"

    def switch(self, **options):
        options.setdefault("logout", True)
        return LoginSwitch(TARGET, frame=self.frame, click=self.click, checked=self.checked,
                           clock=lambda: self.time, **options)


def run(switch, limit=30):
    for _ in range(limit):
        if switch.step() == "done":
            return True
    return False


@pytest.mark.parametrize(("value", "expected"), [
    ("15512345608", "155******08"),
    ("+86 155-1234-5608", "155******08"),
    ("155＊＊＊＊＊＊08", "155******08"),
    ("Player.One@Example.com", "p***@example.com"),
    ("pl***@example.com", "pl***@example.com"),
    ("", ""),
])
def test_hint_keeps_only_masked_form(value, expected):
    assert mask_hint(value) == expected


@pytest.mark.parametrize("value", ["155", "******08", "155******", "1*5", "昵称", "x" * 70])
def test_hint_needs_both_ends(value):
    with pytest.raises(ValueError):
        mask_hint(value)


def test_matching_ignores_star_count_but_needs_both_ends():
    assert same_account(TARGET, "155*****08")  # OCR 常把 6 个星号读成 5 个
    assert same_account(TARGET, " 155******08 ")
    assert not same_account(TARGET, OTHER)
    assert not same_account(TARGET, "155******09")
    assert same_account("p***@example.com", "pl****@Example.com")
    assert not same_account("p***@example.com", "pl****@example.org")
    assert banner_account(f"{TARGET}，欢迎进入游戏") == TARGET
    assert banner_account("欢迎进入游戏") == ""


@pytest.mark.parametrize(("lines", "screen"), [
    (title(), "title"),
    (start_screen(), "title"),
    (logout_dialog(), "logout_dialog"),
    (record_box(TARGET), "record_box"),
    (record_list(TARGET, [(TARGET, "刚刚"), (OTHER, "3天前")]), "record_list"),
    (welcome(TARGET), "welcome"),
    (logged_out(), "logged_out"),
    ([line("请完成安全验证", 820, 420, 280, 30)], "verification"),
    ([line("输入手机号", 800, 480, 200, 28)], "credentials"),
    ([line("bilibili账号登录", 800, 480, 200, 28)], "bilibili"),
    ([line("正在检查数据更新...", 229, 934, 229, 28)], "other"),
])
def test_screens(lines, screen):
    assert classify(lines) == screen


def test_header_is_the_selected_account():
    shown = accounts_in(record_list(OTHER, [(OTHER, "刚刚"), (TARGET, "46分钟前")]))
    assert [item.text for item in shown] == [OTHER, OTHER, TARGET]


def test_switches_through_saved_records_without_touching_danger():
    game = FakeGame()
    switch = game.switch()
    assert run(switch)
    assert switch.entered and game.current == TARGET
    # 登出 → 弹窗里的退出 → 展开 → 目标那行的号码 → 进入游戏
    assert game.clicks == [(1830, 401), (1088, 678), (1198, 496), (825, 652), (961, 626)]


def test_selected_record_is_entered_directly():
    game = FakeGame(screen="box", current=TARGET)
    assert run(game.switch())
    assert game.clicks == [(961, 626)]


def test_keep_option_is_selected_first():
    game = FakeGame(keep=False)
    assert run(game.switch())
    assert game.clicks[1][1] == 570 and game.clicks[2] == (1088, 678)


def test_unconfirmed_keep_option_cancels_logout():
    game = FakeGame(keep=False, keep_clickable=False)
    switch = game.switch()
    with pytest.raises(AccountError, match="已取消登出") as error:
        run(switch)
    assert error.value.reason == "account_switch_failed"
    assert game.clicks[-1] == (812, 678) and game.screen == "title"


def test_dialog_without_cancel_button_stops_without_logging_out():
    game = FakeGame(screen="logout", keep=False, keep_clickable=False)
    frame = game.frame
    game.frame = lambda: [item for item in frame() if item.text != "取消"]
    with pytest.raises(AccountError, match="已停止切换") as error:
        run(game.switch())
    assert error.value.reason == "account_switch_failed"
    assert all(y == 570 for _, y in game.clicks) and game.screen == "logout"


def test_missing_and_ambiguous_records_fail_closed():
    game = FakeGame(records=[(OTHER, "刚刚")])
    with pytest.raises(AccountError) as error:
        run(game.switch())
    assert error.value.reason == "account_record_missing"
    game = FakeGame(records=[(OTHER, "刚刚"), (TARGET, "1小时前"), ("155*****08", "2天前")])
    with pytest.raises(AccountError) as error:
        run(game.switch())
    assert error.value.reason == "account_record_ambiguous"


def test_expired_record_is_reported_or_handed_to_password_login():
    expired = []
    game = FakeGame(valid=[OTHER])
    with pytest.raises(AccountError) as error:
        run(game.switch(on_expired=lambda: expired.append(True)))
    assert error.value.reason == "account_login_expired" and expired
    game = FakeGame(valid=[OTHER])
    switch = game.switch(allow_password=True)
    assert run(switch) and switch.password_fallback


def test_verification_stops_immediately():
    game = FakeGame(screen="verify")
    with pytest.raises(AccountError) as error:
        game.switch().step()
    assert error.value.reason == "account_verification" and game.clicks == []


def test_wrong_account_after_entering_is_refused():
    game = FakeGame(screen="box", current=TARGET)
    switch = game.switch()
    switch.step()
    game.current = OTHER  # 例如点进入后游戏登录了别的记录
    with pytest.raises(AccountError) as error:
        run(switch)
    assert error.value.reason == "account_mismatch"


def test_no_logout_when_the_game_already_signed_in_the_target():
    game = FakeGame()
    switch = game.switch(logout=False)
    assert switch.step() == "done" and game.clicks == []
    # 注册表说是目标账号，但游戏自动登录的是别人：登出重选。
    game = FakeGame(screen="welcome", current=OTHER)
    switch = game.switch(logout=False)
    assert run(switch) and game.current == TARGET
    x, y = game.clicks[0]
    assert x >= 1800 and 380 <= y <= 420


def test_unexpected_logout_dialog_is_cancelled():
    game = FakeGame(screen="logout")
    game.switch(logout=False).step()
    assert game.clicks == [(812, 678)] and game.screen == "title"


def test_switch_gives_up_after_timeout():
    game = FakeGame(screen="logout", keep=True)
    game.click = lambda x, y: None  # 游戏不响应
    with pytest.raises(AccountError) as error:
        run(game.switch(), limit=60)
    assert error.value.reason == "account_switch_failed"


def test_missing_hint_is_reported_at_the_record_box():
    game = FakeGame(screen="box")
    switch = LoginSwitch("", logout=True, frame=game.frame, click=game.click, checked=game.checked,
                         clock=lambda: game.time)
    with pytest.raises(AccountError) as error:
        switch.step()
    assert error.value.reason == "account_no_login_record"
