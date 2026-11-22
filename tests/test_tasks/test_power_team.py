from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image, ImageDraw
import pytest

from module.automation.input_base import limit_input_deadline
from tasks.base import list_drag, task_steps
from tasks.power import instance, power, team
from tasks.power.policy import ECHO, GOLDEN_CALYX, InstanceTeamUnavailable, SupportDemand, run_plan
from tasks.touch import power as touch
from utils.pause import RunStopRequested


class TeamPage:
    def __init__(self, *, hidden=None, ignored=None, delay=0, prompt=False):
        self.now = 0
        self.page = 0
        self.selected = "05"
        self.active = self.selected
        self.hidden = hidden
        self.ignored = ignored
        self.delay = delay
        self.prompt = prompt
        self.prompt_open = False
        self.pending = None
        self.inputs = []

    def sleep(self, seconds):
        self.now += seconds

    def take_screenshot(self, crop):
        if self.pending and self.now >= self.pending[1]:
            self.selected, _ = self.pending
            self.pending = None
        numbers = range(1, 8) if self.page == 0 else range(6, 13)
        frame = Image.new("RGB", (930, 88))
        self.ocr_result = []
        self.positions = {}
        for index, number in enumerate(numbers):
            label = f"{number:02}"
            center = 75 + 120 * index
            if label == self.selected:
                ImageDraw.Draw(frame).rectangle((center - 50, 76, center + 50, 78), fill="white")
            if label == self.hidden and self.selected == "05":
                continue
            box = ((center - 20, 14), (center + 20, 14), (center + 20, 49), (center - 20, 49))
            self.ocr_result.append((box, (label, 0.95)))
            self.positions[self.calculate_text_position(box, relative=False)] = label
        return frame, (0, 0, 930, 88), 1

    def perform_ocr(self):
        pass

    def calculate_text_position(self, box, relative):
        return box[0], box[2]

    def drag_mouse(self, start, end, duration):
        self.inputs.append(("drag", start[0] > end[0]))
        self.page = 1 if start[0] > end[0] else 0
        return True

    def find_element(self, target, kind, **options):
        if target == ("启用队伍", "已启用") and options["crop"] == team.TEAM_ACTIVATE:
            if not self.prompt_open:
                self.matched_text = "已启用" if self.selected == self.active else "启用队伍"
                return "activate"
        elif self.prompt_open and target in ("角色命途切换为队伍中预设的命途", "确认启用"):
            return target
        return None

    def click_element_with_pos(self, position):
        if position == "activate":
            self.inputs.append(("activate", self.selected))
            if self.prompt:
                self.prompt_open = True
            else:
                self.active = self.selected
        elif position == "确认启用":
            self.inputs.append(("confirm", self.selected))
            self.prompt_open = False
            self.active = self.selected
        else:
            label = self.positions[position]
            self.inputs.append(("select", label))
            if label != self.ignored:
                self.pending = label, self.now + self.delay
        return True


@pytest.mark.parametrize("target,hidden,delay,expected", [
    ("03", None, 1.4, [("select", "03"), ("activate", "03")]),
    ("08", None, 0, [("drag", True), ("select", "08"), ("activate", "08")]),
    ("12", None, 0, [("drag", True), ("select", "12"), ("activate", "12")]),
    ("03", "03", 0, [("select", "02"), ("select", "03"), ("activate", "03")]),
    ("07", "07", 0, [("drag", True), ("select", "06"), ("select", "07"), ("activate", "07")]),
])
def test_selects_and_activates_only_confirmed_preset(monkeypatch, target, hidden, delay, expected):
    ui = TeamPage(hidden=hidden, delay=delay)
    clock = SimpleNamespace(monotonic=lambda: ui.now, sleep=ui.sleep)
    monkeypatch.setattr(team, "time", clock)
    monkeypatch.setattr(list_drag, "time", clock)
    assert team.select_preset(ui, target, activate=True) is None
    assert ui.active == target
    assert ui.inputs == expected


def test_only_confirms_the_requested_presets_path_change(monkeypatch):
    ui = TeamPage(hidden="03", prompt=True)
    monkeypatch.setattr(team, "time", SimpleNamespace(monotonic=lambda: ui.now, sleep=ui.sleep))
    assert team.select_preset(ui, 3, activate=True) is None
    assert ui.active == "03"
    assert ui.inputs == [("select", "02"), ("select", "03"), ("activate", "03"), ("confirm", "03")]


@pytest.mark.parametrize("failure", ["old_selection", "deadline", "stop"])
def test_old_enabled_label_and_cancelled_inputs_cannot_confirm_target(monkeypatch, failure):
    ui = TeamPage(ignored="03")
    clock = SimpleNamespace(monotonic=lambda: ui.now, sleep=ui.sleep)
    monkeypatch.setattr(team, "time", clock)
    if failure == "stop":
        monkeypatch.setattr(team.pause_ctl, "checkpoint", Mock(side_effect=RunStopRequested))
        with pytest.raises(RunStopRequested):
            team.select_preset(ui, 3, activate=True)
        assert ui.inputs == []
    else:
        with limit_input_deadline(3 if failure == "deadline" else 26):
            assert team.select_preset(ui, 3, activate=True) == "未确认选中目标队伍"
        assert ui.inputs == [("select", "03")] * (1 if failure == "deadline" else 2)
    assert ui.active == "05"


@pytest.mark.parametrize("platform", ["pc", "touch"])
@pytest.mark.parametrize("heal_first", [False, True])
@pytest.mark.parametrize("roster", ["ready", "empty", "blocked"])
def test_echo_task_recovers_single_failed_switch_and_checks_current_team(monkeypatch, platform, heal_first, roster):
    events = []
    name = "坏灭的喜剧"
    rounds = 2 if roster == "ready" else 1
    cfg = SimpleNamespace(instance_team_enable=True, instance_team_number="08", instance_teams=[],
                          instance_names_challenge_count={ECHO: 1}, tp_before_instance=heal_first,
                          borrow_enable=False, save_timestamp=Mock(), echo_of_war_start_day_of_week=1,
                          instance_names={ECHO: name})
    start = ((1630, 970), (1730, 996))
    state = "main"
    auto = Mock()
    screen = Mock()
    monkeypatch.setattr(team, "time", SimpleNamespace(sleep=Mock(), monotonic=lambda: 0.0))
    monkeypatch.setattr(instance, "time", SimpleNamespace(sleep=Mock()))
    monkeypatch.setattr(touch, "time", SimpleNamespace(sleep=Mock()))

    def change_to(target, **_kwargs):
        nonlocal state
        events.append(target)
        state = target

    def enter(*_args):
        events.append("instance")
        change_to("detail")
        return True

    def find(target, kind, *_args, crop=None, **_kwargs):
        if target == "挑战":
            return state == "detail"
        if target == "开始挑战" and state == "team" and roster != "empty":
            auto.screenshot_pos = (1392, 946, 420, 83)
            auto.screenshot_scale_factor = 1
            auto.screenshot = Image.new("RGB", (420, 83), "white" if roster == "ready" else "gray")
            return start
        if target == team.PATHS:
            return state == "team" and roster != "empty"
        if target == "快速编队" or target == ("快速编队", "开始挑战"):
            return state in ("configure_team", "team")
        return None

    def click(target, *_args, **_kwargs):
        if target == "挑战":
            assert state == "detail"
            change_to("team")
        elif target == "编队":
            assert state == "menu"
            change_to("configure_team")
        else:
            assert target == (1848 / 1920, 55 / 1080, 0, 0) and state in ("team", "configure_team")
            change_to("detail" if state == "team" else "main")
        return True

    def start_battle(target):
        assert target == start and state == "team" and roster == "ready"
        change_to("battle")
        return True

    def select(_auto, number, *, activate=False):
        assert number == "08"
        assert state == ("configure_team" if activate else "team")
        events.append("world_selection" if activate else "instance_selection")
        return "未识别到队伍编号"

    def wait(**_kwargs):
        assert state == "battle"
        events.append("settled")
        return True

    auto.click_element.side_effect = click
    auto.click_element_with_pos.side_effect = start_battle
    auto.find_element.side_effect = find
    auto.press_key.side_effect = lambda _key: change_to("detail")
    auto.ocr_result = []
    screen.change_to.side_effect = change_to
    screen.check_screen.side_effect = lambda name: name == state or (name == "echo" and state == "detail")
    monkeypatch.setattr(task_steps, "screen", screen)
    monkeypatch.setattr(instance, "cfg", cfg)

    if platform == "pc":
        monkeypatch.setattr(power, "cfg", cfg)
        monkeypatch.setattr(power, "screen", screen)
        monkeypatch.setattr(instance, "screen", screen)
        monkeypatch.setattr(instance, "auto", auto)
        monkeypatch.setattr(instance, "select_preset", select)
        monkeypatch.setattr(power.Power, "get", Mock(return_value=rounds * 30))
        monkeypatch.setattr(instance.Instance, "prepare_instance", enter)
        monkeypatch.setattr(instance.Instance, "read_echo_rewards", Mock(return_value=rounds))
        monkeypatch.setattr(instance.Instance, "heal_teams", lambda: events.append("heal"))
        monkeypatch.setattr(instance.Instance, "wait_fight", wait)
        monkeypatch.setattr(instance.Instance, "complete_run", lambda _kind: change_to("main"))

        def run_echo():
            return power.Power.process(ECHO, name, support=SupportDemand()) == rounds
    else:
        monkeypatch.setattr(touch, "cfg", cfg)
        monkeypatch.setattr(touch, "screen", screen)
        monkeypatch.setattr(touch, "auto", auto)
        monkeypatch.setattr(touch, "select_preset", select)
        monkeypatch.setattr(touch, "read_power", Mock(return_value=rounds * 30))
        monkeypatch.setattr(touch, "_supplement", lambda value: value)
        monkeypatch.setattr(touch, "_read_echo_rewards", Mock(return_value=rounds))
        monkeypatch.setattr(touch, "_select_category", Mock())
        monkeypatch.setattr(touch, "_enter_instance", enter)
        monkeypatch.setattr(touch, "_heal_teams", lambda: events.append("heal"))
        monkeypatch.setattr(touch, "_wait_battle", wait)
        monkeypatch.setattr(touch, "_exit_result", lambda _screen: change_to("main"))
        run_echo = touch.run_weekly_echo

    assert task_steps.run_steps((("历战余响", run_echo), ("下一项", lambda: events.append("next")))) is (roster == "ready")
    assert events.count("world_selection") == 1
    assert events.count("instance_selection") == (0 if heal_first else 1)
    assert events.count("instance") == rounds + (not heal_first)
    if heal_first:
        assert events.index("world_selection") < events.index("heal") < events.index("instance")
    assert events.count("settled") == (rounds if roster == "ready" else 0)
    assert auto.click_element_with_pos.call_count == events.count("settled")
    assert events[-1] == "next"
    assert cfg.instance_team_number == "08"


def test_plan_keeps_unstarted_instance_and_runs_next_item():
    skipped = [ECHO, "坏灭的喜剧", 1]
    later = [GOLDEN_CALYX, "回忆之蕾", 1]
    config = SimpleNamespace(power_plan_keep=False, set_value=Mock())
    calls = []

    def run(kind, name, count):
        calls.append([kind, name, count])
        if kind == ECHO:
            raise InstanceTeamUnavailable(f"{name}：未确认出战队伍")
        yield count

    with pytest.raises(InstanceTeamUnavailable):
        run_plan(config, [skipped, later], run)
    assert calls == [skipped, later]
    config.set_value.assert_called_once_with("power_plan", [skipped])
