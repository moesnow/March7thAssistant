import pytest
from module.workflow import (
    parse_int,
    parse_float,
    _parse_text_targets,
    parse_crop_expression,
    format_crop_expression,
    build_crop_expression,
    normalize_step,
    normalize_workflow,
    parse_workflow_step_path,
    get_workflow_step_by_path,
    duplicate_workflow_name,
    create_default_workflow,
    summarize_step,
    is_workflow_read_only,
    _serialize_workflow,
    _find_workflow_by_name,
    _allocate_workflow_directory_name,
)


class TestParseInt:
    def test_valid_int(self):
        assert parse_int("42", 0) == 42

    def test_invalid_returns_default(self):
        assert parse_int("abc", 10) == 10

    def test_none_returns_default(self):
        assert parse_int(None, 5) == 5

    def test_minimum_constraint(self):
        assert parse_int("1", 0, minimum=5) == 5

    def test_above_minimum(self):
        assert parse_int("10", 0, minimum=5) == 10

    def test_float_string_returns_default(self):
        # int("3.7") raises ValueError, so it returns default
        assert parse_int("3.7", 0) == 0


class TestParseFloat:
    def test_valid_float(self):
        assert parse_float("3.14", 0.0) == pytest.approx(3.14)

    def test_invalid_returns_default(self):
        assert parse_float("abc", 1.5) == pytest.approx(1.5)

    def test_none_returns_default(self):
        assert parse_float(None, 2.0) == pytest.approx(2.0)

    def test_minimum_constraint(self):
        assert parse_float("0.5", 0.0, minimum=1.0) == pytest.approx(1.0)

    def test_above_minimum(self):
        assert parse_float("2.0", 0.0, minimum=1.0) == pytest.approx(2.0)


class TestParseTextTargets:
    def test_single_text(self):
        assert _parse_text_targets("hello") == ["hello"]

    def test_semicolon_separated(self):
        assert _parse_text_targets("hello;world") == ["hello", "world"]

    def test_with_spaces(self):
        assert _parse_text_targets(" hello ; world ") == ["hello", "world"]

    def test_empty_parts_ignored(self):
        assert _parse_text_targets("hello;;world") == ["hello", "world"]

    def test_all_empty_returns_original(self):
        assert _parse_text_targets("") == [""]


class TestParseCropExpression:
    def test_none_returns_fullscreen(self):
        assert parse_crop_expression(None) == (0.0, 0.0, 1.0, 1.0)

    def test_empty_string_returns_fullscreen(self):
        assert parse_crop_expression("") == (0.0, 0.0, 1.0, 1.0)

    def test_list_input(self):
        assert parse_crop_expression([0.1, 0.2, 0.3, 0.4]) == (0.1, 0.2, 0.3, 0.4)

    def test_tuple_input(self):
        assert parse_crop_expression((0.1, 0.2, 0.3, 0.4)) == (0.1, 0.2, 0.3, 0.4)

    def test_pixel_format(self):
        result = parse_crop_expression("100, 200, 300, 400")
        assert result == (100.0, 200.0, 300.0, 400.0)

    def test_percentage_format(self):
        result = parse_crop_expression("1/10, 2/10, 3/10, 4/10")
        assert result == pytest.approx((0.1, 0.2, 0.3, 0.4))

    def test_parentheses_format(self):
        result = parse_crop_expression("(100, 200, 300, 400)")
        assert result == (100.0, 200.0, 300.0, 400.0)

    def test_invalid_count_raises(self):
        with pytest.raises(ValueError, match="4 个值"):
            parse_crop_expression("1, 2, 3")

    def test_zero_denominator_raises(self):
        with pytest.raises(ValueError, match="分母不能为 0"):
            parse_crop_expression("1/0, 2/1, 3/1, 4/1")


class TestFormatCropExpression:
    def test_none_returns_fullscreen_text(self):
        result = format_crop_expression(None)
        assert isinstance(result, str)

    def test_empty_returns_fullscreen_text(self):
        result = format_crop_expression("")
        assert isinstance(result, str)

    def test_string_passthrough(self):
        assert format_crop_expression("test") == "test"

    def test_list_formatting(self):
        result = format_crop_expression([0.1, 0.2, 0.3, 0.4])
        assert result == "(0.1, 0.2, 0.3, 0.4)"


class TestBuildCropExpression:
    def test_build_expression(self):
        result = build_crop_expression(100, 200, 300, 400, 1920, 1080)
        assert result == "(100 / 1920, 200 / 1080, 300 / 1920, 400 / 1080)"


class TestNormalizeStep:
    def test_none_returns_wait(self):
        result = normalize_step(None)
        assert result["type"] == "wait"
        assert result["seconds"] == 1.0

    def test_empty_dict_returns_wait(self):
        result = normalize_step({})
        assert result["type"] == "wait"

    def test_click_text_step(self):
        step = {"type": "click_text", "text": "确定"}
        result = normalize_step(step)
        assert result["type"] == "click_text"
        assert result["text"] == "确定"
        assert result["max_retries"] == 1

    def test_wait_step(self):
        step = {"type": "wait", "seconds": 2.5}
        result = normalize_step(step)
        assert result["type"] == "wait"
        assert result["seconds"] == 2.5

    def test_for_step_with_children(self):
        step = {
            "type": "for",
            "count": 3,
            "children": [{"type": "wait", "seconds": 1.0}],
        }
        result = normalize_step(step)
        assert result["type"] == "for"
        assert result["count"] == 3
        assert len(result["children"]) == 1
        assert result["children"][0]["type"] == "wait"

    def test_invalid_condition_type_defaults(self):
        step = {"type": "if", "condition_type": "invalid"}
        result = normalize_step(step)
        assert result["condition_type"] == "text_exists"


class TestNormalizeWorkflow:
    def test_none_returns_default(self):
        result = normalize_workflow(None)
        assert "name" in result
        assert "steps" in result

    def test_empty_dict_returns_default(self):
        result = normalize_workflow({})
        assert "name" in result
        assert "steps" in result

    def test_valid_workflow(self):
        workflow = {
            "name": "Test",
            "steps": [{"type": "wait", "seconds": 1.0}],
        }
        result = normalize_workflow(workflow)
        assert result["name"] == "Test"
        assert len(result["steps"]) == 1

    def test_preserves_meta_keys(self):
        workflow = {
            "name": "Test",
            "steps": [],
            "_workflow_source": "user",
            "_workflow_read_only": False,
        }
        result = normalize_workflow(workflow)
        assert result["_workflow_source"] == "user"
        assert result["_workflow_read_only"] is False


class TestParseWorkflowStepPath:
    def test_none_returns_none(self):
        assert parse_workflow_step_path(None) is None

    def test_empty_string_returns_none(self):
        assert parse_workflow_step_path("") is None

    def test_empty_list_returns_none(self):
        assert parse_workflow_step_path([]) is None

    def test_string_path(self):
        assert parse_workflow_step_path("0/1/2") == (0, 1, 2)

    def test_string_path_with_slashes(self):
        assert parse_workflow_step_path("/0/1/") == (0, 1)

    def test_list_path(self):
        assert parse_workflow_step_path([0, 1, 2]) == (0, 1, 2)

    def test_tuple_path(self):
        assert parse_workflow_step_path((0, 1, 2)) == (0, 1, 2)

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            parse_workflow_step_path("abc")

    def test_negative_index_raises(self):
        with pytest.raises(ValueError):
            parse_workflow_step_path("-1")

    def test_single_index(self):
        assert parse_workflow_step_path("5") == (5,)


class TestGetWorkflowStepByPath:
    def test_get_first_step(self):
        workflow = {
            "name": "Test",
            "steps": [
                {"type": "wait", "seconds": 1.0},
                {"type": "wait", "seconds": 2.0},
            ],
        }
        result = get_workflow_step_by_path(workflow, "0")
        assert result["seconds"] == 1.0

    def test_get_second_step(self):
        workflow = {
            "name": "Test",
            "steps": [
                {"type": "wait", "seconds": 1.0},
                {"type": "wait", "seconds": 2.0},
            ],
        }
        result = get_workflow_step_by_path(workflow, "1")
        assert result["seconds"] == 2.0

    def test_get_nested_step(self):
        workflow = {
            "name": "Test",
            "steps": [
                {
                    "type": "for",
                    "count": 3,
                    "children": [
                        {"type": "wait", "seconds": 1.0},
                        {"type": "wait", "seconds": 2.0},
                    ],
                }
            ],
        }
        result = get_workflow_step_by_path(workflow, "0/1")
        assert result["seconds"] == 2.0

    def test_out_of_range_raises(self):
        workflow = {"name": "Test", "steps": [{"type": "wait"}]}
        with pytest.raises(IndexError):
            get_workflow_step_by_path(workflow, "5")

    def test_empty_path_raises(self):
        workflow = {"name": "Test", "steps": []}
        with pytest.raises(ValueError):
            get_workflow_step_by_path(workflow, "")


class TestDuplicateWorkflowName:
    def test_no_duplicate(self):
        assert duplicate_workflow_name("Test", set()) == "Test"

    def test_with_duplicate(self):
        assert duplicate_workflow_name("Test", {"Test"}) == "Test 2"

    def test_with_existing_number(self):
        assert duplicate_workflow_name("Test", {"Test", "Test 2"}) == "Test 3"


class TestCreateDefaultWorkflow:
    def test_returns_valid_workflow(self):
        workflow = create_default_workflow()
        assert "name" in workflow
        assert "steps" in workflow
        assert len(workflow["steps"]) > 0

    def test_steps_are_normalized(self):
        workflow = create_default_workflow()
        for step in workflow["steps"]:
            assert "type" in step


class TestSummarizeStep:
    def test_wait_step(self):
        step = {"type": "wait", "seconds": 2.5}
        title, detail = summarize_step(step)
        assert "等待" in title or "wait" in title.lower()

    def test_break_step(self):
        step = {"type": "break"}
        title, detail = summarize_step(step)
        assert detail == ""

    def test_continue_step(self):
        step = {"type": "continue"}
        title, detail = summarize_step(step)
        assert detail == ""


class TestIsWorkflowReadOnly:
    def test_dict_with_read_only_true(self):
        assert is_workflow_read_only({"_workflow_read_only": True}) is True

    def test_dict_with_read_only_false(self):
        assert is_workflow_read_only({"_workflow_read_only": False}) is False

    def test_dict_without_read_only(self):
        assert is_workflow_read_only({}) is False


class TestSerializeWorkflow:
    def test_serialize(self):
        workflow = {
            "name": "Test",
            "steps": [{"type": "wait", "seconds": 1.0}],
        }
        result = _serialize_workflow(workflow)
        assert result["name"] == "Test"
        assert len(result["steps"]) == 1


class TestAllocateWorkflowDirectoryName:
    def test_generates_unique_name(self):
        reserved = set()
        name = _allocate_workflow_directory_name(reserved)
        assert name in reserved  # 已被添加到 reserved 中

    def test_avoids_existing_names(self):
        existing = set()
        name1 = _allocate_workflow_directory_name(existing)
        name2 = _allocate_workflow_directory_name(existing)
        assert name1 != name2


class TestBuildSelectedStepWorkflow:
    def test_build_from_first_step(self):
        from module.workflow import build_selected_step_workflow
        workflow = {
            "name": "Test",
            "steps": [
                {"type": "wait", "seconds": 1.0},
                {"type": "wait", "seconds": 2.0},
            ],
        }
        result = build_selected_step_workflow(workflow, "0")
        assert result is not None
        assert "Test" in result["name"]
        assert len(result["steps"]) == 1

    def test_invalid_path_returns_none(self):
        from module.workflow import build_selected_step_workflow
        workflow = {"name": "Test", "steps": []}
        result = build_selected_step_workflow(workflow, "")
        assert result is None


class TestFindWorkflowByName:
    def test_find_existing(self):
        workflows = [
            {"name": "Flow1", "steps": []},
            {"name": "Flow2", "steps": []},
        ]
        result = _find_workflow_by_name("Flow1", workflows)
        assert result is not None
        assert result["name"] == "Flow1"

    def test_find_nonexistent(self):
        workflows = [{"name": "Flow1", "steps": []}]
        result = _find_workflow_by_name("Flow3", workflows)
        assert result is None

    def test_empty_name(self):
        result = _find_workflow_by_name("", [])
        assert result is None

    def test_none_name(self):
        result = _find_workflow_by_name(None, [])
        assert result is None


class TestNormalizeStepExtended:
    def test_if_step(self):
        step = {
            "type": "if",
            "condition_type": "text_exists",
            "text": "确定",
            "children": [{"type": "click_text", "text": "确定"}],
        }
        result = normalize_step(step)
        assert result["type"] == "if"
        assert result["condition_type"] == "text_exists"
        assert len(result["children"]) == 1

    def test_while_step(self):
        step = {
            "type": "while",
            "condition_type": "image_exists",
            "template_path": "test.png",
            "max_iterations": 10,
        }
        result = normalize_step(step)
        assert result["type"] == "while"
        assert result["max_iterations"] == 10

    def test_switch_screen_step(self):
        step = {"type": "switch_screen", "target_screen": "main"}
        result = normalize_step(step)
        assert result["type"] == "switch_screen"
        assert result["target_screen"] == "main"

    def test_press_key_step(self):
        step = {"type": "press_key", "key": "enter", "key_duration": 0.5}
        result = normalize_step(step)
        assert result["type"] == "press_key"
        assert result["key"] == "enter"
        assert result["key_duration"] == 0.5


class TestBuildCropExpression:
    def test_basic(self):
        from module.workflow import build_crop_expression
        result = build_crop_expression(100, 200, 300, 400, 1920, 1080)
        assert "100 / 1920" in result
        assert "200 / 1080" in result
        assert "300 / 1920" in result
        assert "400 / 1080" in result

    def test_starts_with_paren(self):
        from module.workflow import build_crop_expression
        result = build_crop_expression(0, 0, 100, 100, 100, 100)
        assert result.startswith("(")
        assert result.endswith(")")


class TestToWorkspaceRelativePath:
    def test_relative_path(self):
        from module.workflow import to_workspace_relative_path
        result = to_workspace_relative_path("./test.txt")
        assert result.startswith("./")

    def test_absolute_path_within_workspace(self):
        from module.workflow import to_workspace_relative_path
        import os
        result = to_workspace_relative_path(os.path.join(os.getcwd(), "test.txt"))
        assert "test.txt" in result

    def test_returns_string(self):
        from module.workflow import to_workspace_relative_path
        result = to_workspace_relative_path("some_file.txt")
        assert isinstance(result, str)


class TestResolveWorkflowPath:
    def test_empty_path(self):
        from module.workflow import resolve_workflow_path
        assert resolve_workflow_path("") == ""

    def test_absolute_path(self):
        from module.workflow import resolve_workflow_path
        import os
        result = resolve_workflow_path("C:\\test\\file.txt")
        assert os.path.isabs(result)

    def test_relative_path(self):
        from module.workflow import resolve_workflow_path
        import os
        result = resolve_workflow_path("./test.txt")
        assert os.path.isabs(result)


class TestNormalizeWorkflowExtended:
    def test_meta_keys_preserved(self):
        from module.workflow import normalize_workflow
        workflow = {
            "name": "Test",
            "description": "desc",
            "_workflow_read_only": True,
            "steps": [{"type": "wait", "seconds": 1}],
        }
        result = normalize_workflow(workflow)
        assert result["description"] == "desc"
        assert result["_workflow_read_only"] is True

    def test_missing_name_default(self):
        from module.workflow import normalize_workflow
        workflow = {"steps": [{"type": "wait", "seconds": 1}]}
        result = normalize_workflow(workflow)
        assert "name" in result

    def test_missing_steps_default(self):
        from module.workflow import normalize_workflow
        workflow = {"name": "Test"}
        result = normalize_workflow(workflow)
        assert "steps" in result
        assert isinstance(result["steps"], list)


class TestSummarizeStepExtended:
    def test_if_step(self):
        from module.workflow import summarize_step
        step = {
            "type": "if",
            "condition_type": "text_exists",
            "text": "确定",
            "children": [{"type": "click_text", "text": "确定"}],
        }
        title, detail = summarize_step(step)
        assert isinstance(title, str)
        assert len(title) > 0

    def test_for_step(self):
        from module.workflow import summarize_step
        step = {"type": "for", "count": 5, "children": []}
        title, detail = summarize_step(step)
        assert "5" in detail or "5" in title

    def test_click_text_step(self):
        from module.workflow import summarize_step
        step = {"type": "click_text", "text": "确认"}
        title, detail = summarize_step(step)
        assert "确认" in title or "确认" in detail

    def test_screenshot_step(self):
        from module.workflow import summarize_step
        step = {"type": "screenshot"}
        title, detail = summarize_step(step)
        assert isinstance(title, str)

    def test_unknown_type(self):
        from module.workflow import summarize_step
        step = {"type": "unknown_xyz"}
        title, detail = summarize_step(step)
        assert isinstance(title, str)


class TestParseCropExpressionExtended:
    def test_tuple_input(self):
        from module.workflow import parse_crop_expression
        result = parse_crop_expression((0.1, 0.2, 0.3, 0.4))
        assert result == (0.1, 0.2, 0.3, 0.4)

    def test_list_input(self):
        from module.workflow import parse_crop_expression
        result = parse_crop_expression([0.1, 0.2, 0.3, 0.4])
        assert result == (0.1, 0.2, 0.3, 0.4)

    def test_fraction_format(self):
        from module.workflow import parse_crop_expression
        result = parse_crop_expression("(100 / 1920, 200 / 1080, 300 / 1920, 400 / 1080)")
        assert abs(result[0] - 100 / 1920) < 0.001

    def test_invalid_count_raises(self):
        from module.workflow import parse_crop_expression
        with pytest.raises(ValueError, match="4 个值"):
            parse_crop_expression("1, 2, 3")

    def test_zero_denominator_raises(self):
        from module.workflow import parse_crop_expression
        with pytest.raises(ValueError, match="分母不能为 0"):
            parse_crop_expression("1 / 0, 2, 3, 4")


class TestDuplicateWorkflowNameExtended:
    def test_preserves_base_name(self):
        from module.workflow import duplicate_workflow_name
        result = duplicate_workflow_name("MyFlow", set())
        assert result == "MyFlow"

    def test_handles_high_numbers(self):
        from module.workflow import duplicate_workflow_name
        existing = {"Test", "Test 2", "Test 3", "Test 4"}
        result = duplicate_workflow_name("Test", existing)
        assert result == "Test 5"

    def test_unicode_name(self):
        from module.workflow import duplicate_workflow_name
        result = duplicate_workflow_name("测试流程", set())
        assert result == "测试流程"
