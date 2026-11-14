import pytest

from module.workflow import WorkflowRunner


def make_group(step_type, children):
    return {
        "type": step_type,
        "condition_type": "image_exists",
        "template_path": "condition.png",
        "count": 2,
        "max_iterations": 2,
        "children": children,
    }


@pytest.fixture
def runner():
    return WorkflowRunner(sleep_func=lambda _: None, mirror_to_project_log=False)


@pytest.mark.parametrize("step_type", ["if", "for", "while"])
def test_failed_child_enables_following_failure_branch(runner, monkeypatch, step_type):
    sleeps = []
    runner.sleep_func = sleeps.append
    monkeypatch.setattr(runner, "_find_image", lambda step: step["template_path"] == "condition.png")

    result = runner.run({
        "steps": [
            make_group(step_type, [{"type": "find_image", "template_path": "missing.png"}]),
            {
                "type": "if",
                "condition_type": "last_result_failed",
                "children": [{"type": "wait", "seconds": 3}],
            },
        ],
    })

    assert sleeps == [3]
    assert result is True


def test_failure_propagates_through_three_nested_conditions(runner, monkeypatch):
    monkeypatch.setattr(runner, "_find_image", lambda step: step["template_path"] == "condition.png")
    inner = {"type": "if", "condition_type": "image_exists", "template_path": "missing.png"}
    steps = [make_group("if", [make_group("if", [inner])])]

    assert runner.run({"steps": steps}) is True
    assert runner.last_result is False


@pytest.mark.parametrize("step_type", ["for", "while"])
@pytest.mark.parametrize("results", [[False, True], [True, False]])
def test_loop_result_comes_from_last_iteration(runner, monkeypatch, step_type, results):
    pending_results = iter(results)

    def find_image(step):
        if step["template_path"] == "condition.png":
            return True
        return next(pending_results)

    monkeypatch.setattr(runner, "_find_image", find_image)
    steps = [make_group(step_type, [{"type": "find_image", "template_path": "target.png"}])]

    assert runner.run({"steps": steps}) is True
    assert runner.last_result is results[-1]


@pytest.mark.parametrize("step_type", ["if", "for", "while"])
def test_empty_child_list_still_succeeds_after_previous_failure(runner, monkeypatch, step_type):
    monkeypatch.setattr(runner, "_find_image", lambda step: step["template_path"] == "condition.png")
    steps = [
        {"type": "find_image", "template_path": "missing.png"},
        make_group(step_type, []),
    ]

    assert runner.run({"steps": steps}) is True
    assert runner.last_result is True


def test_child_exception_is_not_masked_by_parent(runner, monkeypatch):
    def find_image(step):
        if step["template_path"] == "condition.png":
            return True
        raise RuntimeError("image lookup failed")

    monkeypatch.setattr(runner, "_find_image", find_image)
    steps = [make_group("if", [{"type": "find_image", "template_path": "target.png"}])]

    assert runner.run({"steps": steps}) is True
    assert runner.last_result is False


@pytest.mark.parametrize("step_type", ["if", "while"])
def test_skipped_final_condition_preserves_workflow_success(runner, step_type):
    sleeps = []
    runner.sleep_func = sleeps.append
    optional_recovery = make_group(step_type, [{"type": "wait", "seconds": 3}])
    optional_recovery["condition_type"] = "last_result_failed"

    assert runner.run({"steps": [{"type": "wait", "seconds": 1}, optional_recovery]}) is True
    assert sleeps == [1]
    assert runner.last_result is False


def test_stop_workflow_still_returns_failure(runner):
    sleeps = []
    runner.sleep_func = sleeps.append
    steps = [
        make_group("for", [{"type": "stop_workflow"}]),
        {"type": "wait", "seconds": 1},
    ]

    assert runner.run({"steps": steps}) is False
    assert sleeps == []
