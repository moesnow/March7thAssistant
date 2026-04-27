import copy
import io
import os
import shutil
import tempfile
import time
import traceback
import uuid
import zipfile
from datetime import datetime

from module.automation import auto
from module.config import cfg
from module.logger import log
from module.localization import tr
from module.notification import notif

WORKFLOW_FILE_NAME = "workflow.yaml"
WORKFLOW_USER_ROOT = os.path.abspath("./config/workflows")
WORKFLOW_EXAMPLE_ROOT = os.path.abspath("./assets/config/workflows")
WORKFLOW_OFFICIAL_CONFIG_FILE = "official_workflows.yaml"
WORKFLOW_OFFICIAL_CONFIG_PATH = os.path.join(WORKFLOW_EXAMPLE_ROOT, WORKFLOW_OFFICIAL_CONFIG_FILE)
WORKFLOW_CURRENT_FILE = os.path.join(WORKFLOW_USER_ROOT, ".current")
WORKFLOW_TEMPLATE_DIR_NAME = "templates"
WORKFLOW_OCR_DIR_NAME = "ocr"

WORKFLOW_USER_INFO_KEYS = ("author", "version", "description")

DEFAULT_WORKFLOW_NAME = "示例流程"
WORKFLOW_META_KEYS = (
    "_workflow_source",
    "_workflow_dir_name",
    "_workflow_base_dir",
    "_workflow_read_only",
)

STEP_TYPE_LABELS = {
    "click_image": "点击图片",
    "click_text": "点击文字",
    "click_crop": "点击坐标",
    "find_image": "查找图片",
    "find_text": "查找文字",
    "play_audio": "播放音频",
    "send_message": "消息推送",
    "switch_screen": "切换界面",
    "press_key": "按下按键",
    "wait": "等待",
    "if": "如果",
    "for": "循环次数",
    "while": "条件循环",
    "break": "结束循环",
    "continue": "继续循环",
}

CONDITION_TYPE_LABELS = {
    "image_exists": "图片存在",
    "image_not_exists": "图片不存在",
    "text_exists": "文字存在",
    "text_not_exists": "文字不存在",
    "last_result": "上一步成功",
    "last_result_failed": "上一步失败",
}


def ensure_workflow_directories():
    os.makedirs(WORKFLOW_USER_ROOT, exist_ok=True)
    os.makedirs(WORKFLOW_EXAMPLE_ROOT, exist_ok=True)


def _workflow_asset_directory(base_dir: str, kind: str) -> str:
    asset_dir_name = WORKFLOW_TEMPLATE_DIR_NAME if kind == "template" else WORKFLOW_OCR_DIR_NAME
    return os.path.join(base_dir, asset_dir_name)


def _read_yaml_file(path: str):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return cfg.yaml.load(file) or {}
    except FileNotFoundError:
        return None
    except Exception:
        log.error(traceback.format_exc())
        return None


def _write_yaml_file(path: str, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        cfg.yaml.dump(data, file)


def _write_current_workflow_name(name: str):
    ensure_workflow_directories()
    with open(WORKFLOW_CURRENT_FILE, "w", encoding="utf-8") as file:
        file.write(name.strip())


def _read_current_workflow_name() -> str:
    try:
        with open(WORKFLOW_CURRENT_FILE, "r", encoding="utf-8") as file:
            return file.read().strip()
    except FileNotFoundError:
        return ""


def _allocate_workflow_directory_name(reserved_names: set[str]) -> str:
    reserved_lower = {item.lower() for item in reserved_names}
    candidate = str(uuid.uuid4())
    while candidate.lower() in reserved_lower:
        candidate = str(uuid.uuid4())
    reserved_names.add(candidate)
    return candidate


def _serialize_workflow(workflow: dict) -> dict:
    normalized = normalize_workflow(workflow)
    return {
        "name": normalized["name"],
        "steps": normalized["steps"],
    }


def _serialize_workflow_with_info(workflow: dict) -> dict:
    serialized = _serialize_workflow(workflow)
    for key in WORKFLOW_USER_INFO_KEYS:
        if key in workflow:
            serialized[key] = workflow[key]
    return serialized


def _read_official_workflow_config() -> tuple[set[str] | None, str]:
    """读取官方流程配置，返回(允许目录名集合, 默认目录名)。"""
    data = _read_yaml_file(WORKFLOW_OFFICIAL_CONFIG_PATH)
    if not isinstance(data, dict):
        return None, ""

    allowed = data.get("allowed_workflows")
    allowed_set = None
    if isinstance(allowed, list):
        parsed = {str(item).strip() for item in allowed if str(item).strip()}
        if parsed:
            allowed_set = parsed

    default_workflow = str(data.get("default_workflow", "") or "").strip()
    return allowed_set, default_workflow


def _load_workflows_from_root(root_dir: str, read_only: bool, allowed_dirs: set[str] | None = None) -> list[dict]:
    workflows = []
    if not os.path.isdir(root_dir):
        return workflows

    for directory_name in sorted(os.listdir(root_dir)):
        if allowed_dirs is not None and directory_name not in allowed_dirs:
            continue
        workflow_dir = os.path.join(root_dir, directory_name)
        workflow_path = os.path.join(workflow_dir, WORKFLOW_FILE_NAME)
        if not os.path.isdir(workflow_dir) or not os.path.isfile(workflow_path):
            continue

        data = _read_yaml_file(workflow_path)
        if not isinstance(data, dict):
            continue

        workflow = normalize_workflow(data)
        workflow["_workflow_source"] = "example" if read_only else "user"
        workflow["_workflow_dir_name"] = directory_name
        workflow["_workflow_base_dir"] = workflow_dir
        workflow["_workflow_read_only"] = read_only
        workflows.append(workflow)

    return workflows


def _write_workflow_file(workflow: dict):
    directory_name = workflow["_workflow_dir_name"]
    workflow_dir = os.path.join(WORKFLOW_USER_ROOT, directory_name)
    workflow_path = os.path.join(workflow_dir, WORKFLOW_FILE_NAME)
    _write_yaml_file(workflow_path, _serialize_workflow_with_info(workflow))
    os.makedirs(_workflow_asset_directory(workflow_dir, "template"), exist_ok=True)


def _unique_file_path(directory: str, file_name: str) -> str:
    base_name, extension = os.path.splitext(file_name)
    candidate = os.path.join(directory, file_name)
    index = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base_name}_{index}{extension}")
        index += 1
    return candidate


def _cleanup_removed_user_workflows(active_directory_names: set[str]):
    if not os.path.isdir(WORKFLOW_USER_ROOT):
        return

    for directory_name in os.listdir(WORKFLOW_USER_ROOT):
        workflow_dir = os.path.join(WORKFLOW_USER_ROOT, directory_name)
        if not os.path.isdir(workflow_dir):
            continue
        if directory_name in active_directory_names:
            continue
        shutil.rmtree(workflow_dir, ignore_errors=True)


def _find_workflow_by_name(name: str, workflows: list[dict] | None = None):
    if not name:
        return None
    for workflow in workflows or load_workflows():
        if workflow["name"] == name:
            return workflow
    return None


def get_workflow_by_name(name: str, workflows: list[dict] | None = None):
    workflow = _find_workflow_by_name(name, workflows)
    if workflow is None:
        return None
    return normalize_workflow(workflow)


def parse_workflow_step_path(step_path) -> tuple[int, ...] | None:
    if step_path in (None, "", [], ()):
        return None

    if isinstance(step_path, str):
        normalized = step_path.strip().replace("\\", "/").strip("/")
        if not normalized:
            return None
        parts = [part.strip() for part in normalized.split("/") if part.strip()]
    elif isinstance(step_path, (list, tuple)):
        parts = list(step_path)
    else:
        raise ValueError(f"invalid workflow step path: {step_path}")

    parsed = []
    for part in parts:
        if isinstance(part, int):
            index = part
        else:
            text = str(part).strip()
            if not text or not text.isdigit():
                raise ValueError(f"invalid workflow step path: {step_path}")
            index = int(text)
        if index < 0:
            raise ValueError(f"invalid workflow step path: {step_path}")
        parsed.append(index)

    return tuple(parsed) if parsed else None


def get_workflow_step_by_path(workflow: dict, step_path) -> dict:
    parsed_path = parse_workflow_step_path(step_path)
    if not parsed_path:
        raise ValueError("workflow step path is required")

    normalized_workflow = normalize_workflow(workflow)
    steps = normalized_workflow["steps"]
    current_step = None
    for depth, index in enumerate(parsed_path):
        if index >= len(steps):
            raise IndexError(f"workflow step path out of range: {step_path}")
        current_step = steps[index]
        if depth < len(parsed_path) - 1:
            steps = current_step.get("children", [])

    return current_step


def build_selected_step_workflow(workflow: dict, step_path) -> dict | None:
    parsed_path = parse_workflow_step_path(step_path)
    if not parsed_path:
        return None

    normalized_workflow = normalize_workflow(workflow)
    step = copy.deepcopy(get_workflow_step_by_path(normalized_workflow, parsed_path))
    title, _ = summarize_step(step)
    selected_workflow = {
        "name": f"{normalized_workflow['name']} - {title}",
        "steps": [step],
    }
    for key in WORKFLOW_META_KEYS:
        if key in normalized_workflow:
            selected_workflow[key] = normalized_workflow[key]
    return selected_workflow


def load_workflow_execution_payload(workflow_name: str, step_path=None) -> dict:
    workflow = get_workflow_by_name(workflow_name)
    if workflow is None:
        raise ValueError(f"workflow not found: {workflow_name}")

    parsed_path = parse_workflow_step_path(step_path)
    if parsed_path is None:
        return workflow

    selected_workflow = build_selected_step_workflow(workflow, parsed_path)
    if selected_workflow is None:
        raise ValueError(f"invalid workflow step path: {step_path}")
    return selected_workflow


def get_workflow_directory(workflow=None) -> str | None:
    if isinstance(workflow, dict):
        base_dir = workflow.get("_workflow_base_dir")
        if base_dir:
            return base_dir
        workflow = workflow.get("name", "")

    if isinstance(workflow, str) and workflow:
        matched_workflow = _find_workflow_by_name(workflow)
        if matched_workflow is not None:
            return matched_workflow.get("_workflow_base_dir")

    workflows = load_workflows()
    if workflow is None:
        current_name = _read_current_workflow_name()
        if current_name:
            matched_workflow = _find_workflow_by_name(current_name, workflows)
            if matched_workflow is not None:
                return matched_workflow.get("_workflow_base_dir")

    if workflows:
        return workflows[0].get("_workflow_base_dir")
    return None


def ensure_asset_directories(kind: str, workflow=None):
    base_dir = get_workflow_directory(workflow)
    if not base_dir:
        return
    os.makedirs(_workflow_asset_directory(base_dir, kind), exist_ok=True)


def is_workflow_read_only(workflow=None) -> bool:
    if isinstance(workflow, dict):
        return bool(workflow.get("_workflow_read_only", False))

    if isinstance(workflow, str) and workflow:
        matched_workflow = _find_workflow_by_name(workflow)
        return bool(matched_workflow and matched_workflow.get("_workflow_read_only", False))

    current_name = get_current_workflow_name()
    matched_workflow = _find_workflow_by_name(current_name)
    return bool(matched_workflow and matched_workflow.get("_workflow_read_only", False))


def get_asset_directory(kind: str, workflow=None) -> str:
    ensure_workflow_directories()
    base_dir = get_workflow_directory(workflow)
    if not base_dir:
        base_dir = WORKFLOW_USER_ROOT
    asset_dir = _workflow_asset_directory(base_dir, kind)
    os.makedirs(asset_dir, exist_ok=True)
    return asset_dir


def import_asset_to_workflow(source_path: str, kind: str, workflow=None) -> str:
    if not source_path:
        return ""

    source_absolute_path = os.path.abspath(source_path)
    if not os.path.isfile(source_absolute_path):
        return source_path

    target_directory = get_asset_directory(kind, workflow)
    try:
        relative_path = os.path.relpath(source_absolute_path, target_directory).replace("\\", "/")
    except ValueError:
        relative_path = None
    if relative_path and not relative_path.startswith("../"):
        return to_workflow_relative_path(source_absolute_path, workflow)

    target_path = _unique_file_path(target_directory, os.path.basename(source_absolute_path))
    shutil.copy2(source_absolute_path, target_path)
    return to_workflow_relative_path(target_path, workflow)


def to_workspace_relative_path(path: str) -> str:
    absolute_path = os.path.abspath(path)
    current_dir = os.path.abspath(os.getcwd())
    try:
        relative_path = os.path.relpath(absolute_path, current_dir)
    except ValueError:
        return absolute_path.replace("\\", "/")

    relative_path = relative_path.replace("\\", "/")
    if relative_path.startswith("../"):
        return absolute_path.replace("\\", "/")
    if not relative_path.startswith("./"):
        relative_path = f"./{relative_path}"
    return relative_path


def to_workflow_relative_path(path: str, workflow=None) -> str:
    workflow_dir = get_workflow_directory(workflow)
    absolute_path = os.path.abspath(path)
    if workflow_dir:
        try:
            relative_path = os.path.relpath(absolute_path, workflow_dir).replace("\\", "/")
        except ValueError:
            relative_path = None
        if relative_path and not relative_path.startswith("../"):
            return relative_path
    return to_workspace_relative_path(path)


def resolve_workflow_path(path: str, workflow=None) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.abspath(path)

    normalized_path = str(path).replace("\\", "/")
    if normalized_path.startswith("./") or normalized_path.startswith("../"):
        return os.path.abspath(os.path.join(os.getcwd(), path))

    workflow_dir = get_workflow_directory(workflow)
    if workflow_dir:
        return os.path.abspath(os.path.join(workflow_dir, path))
    return os.path.abspath(path)


def build_crop_expression(x: int, y: int, width: int, height: int, screen_width: int, screen_height: int) -> str:
    return f"({x} / {screen_width}, {y} / {screen_height}, {width} / {screen_width}, {height} / {screen_height})"


def generate_capture_path(kind: str, workflow=None) -> str:
    ensure_asset_directories(kind, workflow)
    prefix = "template" if kind == "template" else "ocr"
    file_name = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.png"
    return os.path.join(get_asset_directory(kind, workflow), file_name)


def create_default_workflow() -> dict:
    return {
        "name": DEFAULT_WORKFLOW_NAME,
        "steps": [
            {
                "type": "if",
                "condition_type": "text_exists",
                "text": "开始挑战",
                "include": True,
                "crop": "",
                "children": [
                    {
                        "type": "click_text",
                        "text": "开始挑战",
                        "include": False,
                        "crop": "",
                        "max_retries": 1,
                    }
                ],
            },
            {
                "type": "for",
                "count": 3,
                "children": [
                    {
                        "type": "wait",
                        "seconds": 1.0,
                    }
                ],
            },
        ],
    }


def parse_int(value, default: int, minimum: int | None = None) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    return result


def parse_float(value, default: float, minimum: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    if minimum is not None:
        result = max(minimum, result)
    return result


def _parse_text_targets(text: str) -> list[str]:
    """将文字字段按 ; 拆分为多目标列表，忽略空项。"""
    targets = [t.strip() for t in text.split(";") if t.strip()]
    return targets if targets else [text]


def parse_crop_expression(crop_text) -> tuple[float, float, float, float]:
    if crop_text in (None, "", []):
        return 0.0, 0.0, 1.0, 1.0

    if isinstance(crop_text, (list, tuple)) and len(crop_text) == 4:
        return tuple(float(item) for item in crop_text)

    normalized = str(crop_text).strip()
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()

    parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if len(parts) != 4:
        raise ValueError("crop 需要包含 4 个值")

    values = []
    for part in parts:
        if "/" in part:
            numerator, denominator = part.split("/", 1)
            denominator_value = float(denominator.strip())
            if denominator_value == 0:
                raise ValueError("crop 分母不能为 0")
            values.append(float(numerator.strip()) / denominator_value)
        else:
            values.append(float(part))

    return tuple(values)


def format_crop_expression(crop_text) -> str:
    if crop_text in (None, "", []):
        return tr("全屏")
    if isinstance(crop_text, str):
        return crop_text
    if isinstance(crop_text, (list, tuple)) and len(crop_text) == 4:
        return f"({crop_text[0]}, {crop_text[1]}, {crop_text[2]}, {crop_text[3]})"
    return str(crop_text)


def get_switchable_screen_targets(start_screen: str = "main", include_start: bool = True) -> list[tuple[str, str]]:
    try:
        from module.screen import screen as screen_manager

        return screen_manager.get_switchable_screens(start_screen, include_start=include_start)
    except Exception:
        log.error(traceback.format_exc())
        return []


def get_switchable_screen_name(screen_id: str) -> str:
    if not screen_id:
        return ""

    try:
        from module.screen import screen as screen_manager

        return screen_manager.get_name(screen_id)
    except Exception:
        return screen_id


def can_change_to_screen_from_main(screen_id: str) -> bool:
    if not screen_id:
        return False

    try:
        from module.screen import screen as screen_manager

        return screen_manager.can_change_from("main", screen_id)
    except Exception:
        log.error(traceback.format_exc())
        return False


def normalize_step(step: dict) -> dict:
    if not isinstance(step, dict):
        return {"type": "wait", "seconds": 1.0}

    step_type = str(step.get("type", "wait") or "wait")
    condition_type = str(step.get("condition_type", "text_exists") or "text_exists")
    if condition_type not in CONDITION_TYPE_LABELS:
        condition_type = "text_exists"
    normalized = {
        "type": step_type,
        "text": str(step.get("text", "") or ""),
        "audio_path": str(step.get("audio_path", "./assets/audio/pa.mp3") or "./assets/audio/pa.mp3"),
        "target_screen": str(step.get("target_screen", "") or ""),
        "template_path": str(step.get("template_path", "") or ""),
        "threshold": parse_float(step.get("threshold", 0.9), 0.9, 0.0),
        "crop": step.get("crop", "") or "",
        "include": bool(step.get("include", False)),
        "max_retries": parse_int(step.get("max_retries", 1), 1, 1),
        "seconds": parse_float(step.get("seconds", 1.0), 1.0, 0.0),
        "count": parse_int(step.get("count", 1), 1, 0),
        "condition_type": condition_type,
        "max_iterations": parse_int(step.get("max_iterations", 20), 20, 0),
        "children": [],
        "with_screenshot": bool(step.get("with_screenshot", False)),
        "key": str(step.get("key", "") or ""),
        "key_duration": parse_float(step.get("key_duration", 0.1), 0.1, 0.0),
        "key_action": str(step.get("key_action", "press_and_release") or "press_and_release"),
        "click_action": str(step.get("click_action", "press_and_release") or "press_and_release"),
        "press_duration": parse_float(step.get("press_duration", 0.1), 0.1, 0.0),
    }

    normalized["children"] = [normalize_step(child) for child in step.get("children", []) if isinstance(child, dict)]
    return normalized


def normalize_workflow(workflow: dict) -> dict:
    if not isinstance(workflow, dict):
        workflow = create_default_workflow()

    name = str(workflow.get("name", DEFAULT_WORKFLOW_NAME) or DEFAULT_WORKFLOW_NAME)
    steps = [normalize_step(step) for step in workflow.get("steps", []) if isinstance(step, dict)]
    normalized = {"name": name, "steps": steps}
    for key in WORKFLOW_META_KEYS:
        if key in workflow:
            normalized[key] = workflow[key]
    for key in WORKFLOW_USER_INFO_KEYS:
        if key in workflow:
            normalized[key] = str(workflow[key])
    return normalized


def load_workflows() -> list[dict]:
    ensure_workflow_directories()

    allowed_sample_dirs, _ = _read_official_workflow_config()
    sample_workflows = _load_workflows_from_root(WORKFLOW_EXAMPLE_ROOT, read_only=True, allowed_dirs=allowed_sample_dirs)
    user_workflows = _load_workflows_from_root(WORKFLOW_USER_ROOT, read_only=False)

    if not sample_workflows and not user_workflows:
        save_workflows([create_default_workflow()])
        user_workflows = _load_workflows_from_root(WORKFLOW_USER_ROOT, read_only=False)

    workflows = sample_workflows + user_workflows
    existing_names = set()
    renamed_user_workflow = False
    for workflow in workflows:
        unique_name = duplicate_workflow_name(workflow["name"], existing_names)
        if unique_name != workflow["name"]:
            workflow["name"] = unique_name
            if not workflow.get("_workflow_read_only", False):
                renamed_user_workflow = True
        existing_names.add(workflow["name"])

    if renamed_user_workflow:
        save_workflows(workflows)
        user_workflows = _load_workflows_from_root(WORKFLOW_USER_ROOT, read_only=False)
        workflows = sample_workflows + user_workflows

    return workflows


def save_workflows(workflows: list[dict]):
    ensure_workflow_directories()
    reserved_directory_names = {
        directory_name
        for directory_name in os.listdir(WORKFLOW_USER_ROOT)
        if os.path.isdir(os.path.join(WORKFLOW_USER_ROOT, directory_name))
    }
    active_directory_names = set()

    for workflow in workflows:
        if not isinstance(workflow, dict):
            continue
        normalized = normalize_workflow(workflow)
        if normalized.get("_workflow_read_only", False):
            continue

        directory_name = normalized.get("_workflow_dir_name")
        if not directory_name:
            directory_name = _allocate_workflow_directory_name(reserved_directory_names)
        else:
            reserved_directory_names.add(directory_name)

        normalized["_workflow_source"] = "user"
        normalized["_workflow_dir_name"] = directory_name
        normalized["_workflow_base_dir"] = os.path.join(WORKFLOW_USER_ROOT, directory_name)
        normalized["_workflow_read_only"] = False
        _write_workflow_file(normalized)
        active_directory_names.add(directory_name)

    _cleanup_removed_user_workflows(active_directory_names)


def get_current_workflow_name() -> str:
    current_name = _read_current_workflow_name()
    workflows = load_workflows()
    for workflow in workflows:
        if workflow["name"] == current_name:
            return current_name

    fallback = ""
    _, default_sample_dir = _read_official_workflow_config()
    if default_sample_dir:
        for workflow in workflows:
            if workflow.get("_workflow_source") == "example" and workflow.get("_workflow_dir_name") == default_sample_dir:
                fallback = workflow["name"]
                break
    if not fallback:
        fallback = workflows[0]["name"]

    _write_current_workflow_name(fallback)
    return fallback


def set_current_workflow_name(name: str):
    _write_current_workflow_name(name)


def export_workflow_to_zip(workflow: dict, zip_path: str):
    """将工作流目录打包为 ZIP（workflow.yaml + templates/ + ocr/）。"""
    workflow_dir = workflow.get("_workflow_base_dir")
    if not workflow_dir or not os.path.isdir(workflow_dir):
        raise ValueError(tr("工作流目录不存在"))

    data = _serialize_workflow_with_info(workflow)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".yaml")
    try:
        os.close(tmp_fd)
        _write_yaml_file(tmp_path, data)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tmp_path, WORKFLOW_FILE_NAME)
            for asset_dir_name in (WORKFLOW_TEMPLATE_DIR_NAME, WORKFLOW_OCR_DIR_NAME):
                asset_dir = os.path.join(workflow_dir, asset_dir_name)
                if os.path.isdir(asset_dir):
                    for root, _, files in os.walk(asset_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, workflow_dir).replace("\\", "/")
                            zf.write(file_path, arcname)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def import_workflow_from_zip(zip_path: str) -> dict:
    """从 ZIP 文件导入工作流，返回 workflow 字典（含 meta 信息）。"""
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(tr("不是有效的 ZIP 文件"))

    ensure_workflow_directories()
    reserved_names = {
        d for d in os.listdir(WORKFLOW_USER_ROOT)
        if os.path.isdir(os.path.join(WORKFLOW_USER_ROOT, d))
    }
    dir_name = _allocate_workflow_directory_name(reserved_names)
    target_dir = os.path.join(WORKFLOW_USER_ROOT, dir_name)
    os.makedirs(target_dir, exist_ok=True)

    try:
        real_target = os.path.realpath(target_dir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                member_path = os.path.realpath(os.path.join(target_dir, member))
                if not member_path.startswith(real_target + os.sep) and member_path != real_target:
                    raise ValueError(tr("ZIP 文件包含不安全路径，已拒绝导入"))
            zf.extractall(target_dir)
    except Exception:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise

    workflow_path = os.path.join(target_dir, WORKFLOW_FILE_NAME)
    if not os.path.isfile(workflow_path):
        shutil.rmtree(target_dir, ignore_errors=True)
        raise ValueError(tr("ZIP 中未找到 workflow.yaml"))

    data = _read_yaml_file(workflow_path)
    if not isinstance(data, dict):
        shutil.rmtree(target_dir, ignore_errors=True)
        raise ValueError(tr("workflow.yaml 格式无效"))

    workflow = normalize_workflow(data)
    workflow["_workflow_source"] = "user"
    workflow["_workflow_dir_name"] = dir_name
    workflow["_workflow_base_dir"] = target_dir
    workflow["_workflow_read_only"] = False
    return workflow


def duplicate_workflow_name(base_name: str, existing_names: set[str]) -> str:
    if base_name not in existing_names:
        return base_name
    index = 2
    while f"{base_name} {index}" in existing_names:
        index += 1
    return f"{base_name} {index}"


def _get_click_action_label(action: str) -> str:
    """获取点击动作的标签。"""
    action_labels = {
        "press": tr("按下"),
        "release": tr("松开"),
        "press_and_release": tr("点击"),
    }
    return action_labels.get(action, action)


def summarize_step(step: dict) -> tuple[str, str]:
    normalized = normalize_step(step)
    step_type = normalized["type"]
    label = tr(STEP_TYPE_LABELS.get(step_type, step_type))

    if step_type in {"break", "continue"}:
        return label, ""

    if step_type == "click_image":
        title = f"{label} · {os.path.basename(normalized['template_path']) or tr('未选择模板')}"
        action_label = _get_click_action_label(normalized["click_action"])
        detail = f"{tr('阈值')} {normalized['threshold']:.2f} / {action_label} / {format_crop_expression(normalized['crop'])}"
        return title, detail

    if step_type == "click_text":
        compare_text = tr("包含") if normalized["include"] else tr("精确")
        title = f"{label} · {normalized['text'] or tr('未填写文字')}"
        action_label = _get_click_action_label(normalized["click_action"])
        detail = f"{compare_text}{tr('匹配')} / {action_label} / {tr('重试')} {normalized['max_retries']} {tr('次')} / {format_crop_expression(normalized['crop'])}"
        return title, detail

    if step_type == "click_crop":
        title = f"{label} · {format_crop_expression(normalized['crop'])}"
        action_label = _get_click_action_label(normalized["click_action"])
        return title, action_label

    if step_type == "find_image":
        title = f"{label} · {os.path.basename(normalized['template_path']) or tr('未选择模板')}"
        retries_text = f" / {tr('重试')} {normalized['max_retries']} {tr('次')}" if normalized['max_retries'] > 1 else ""
        detail = f"{tr('阈值')} {normalized['threshold']:.2f}{retries_text} / {format_crop_expression(normalized['crop'])}"
        return title, detail

    if step_type == "find_text":
        compare_text = tr("包含") if normalized["include"] else tr("精确")
        title = f"{label} · {normalized['text'] or tr('未填写文字')}"
        retries_text = f" / {tr('重试')} {normalized['max_retries']} {tr('次')}" if normalized['max_retries'] > 1 else ""
        detail = f"{compare_text}{tr('匹配')}{retries_text} / {format_crop_expression(normalized['crop'])}"
        return title, detail

    if step_type == "play_audio":
        title = f"{label} · {os.path.basename(normalized['audio_path']) or tr('未填写音频路径')}"
        return title, normalized["audio_path"]

    if step_type == "send_message":
        message_text = normalized.get("text", "").strip() or tr("未填写消息内容")
        screenshot_text = tr("包含截图") if normalized["with_screenshot"] else tr("不含截图")
        return f"{label} · {message_text}", screenshot_text

    if step_type == "switch_screen":
        screen_id = normalized["target_screen"]
        screen_name = get_switchable_screen_name(screen_id)
        target_text = screen_name or screen_id or tr("未选择目标界面")
        detail = screen_id if screen_name and screen_name != screen_id else ""
        return f"{label} · {target_text}", detail

    if step_type == "press_key":
        action_labels = {
            "press": tr("按下"),
            "release": tr("松开"),
            "press_and_release": tr("点击"),
        }
        action_label = action_labels.get(normalized["key_action"], normalized["key_action"])
        title = f"{label} · {normalized['key'] or tr('未填写按键')} · {action_label}"
        duration_text = f"{tr('时长')} {normalized['key_duration']:.2f}s" if normalized["key_action"] != "release" else tr("松开")
        return title, duration_text

    if step_type == "wait":
        return f"{label} · {normalized['seconds']:.1f} {tr('秒')}", tr("用于给界面或动画留出时间")

    if step_type == "for":
        child_count = len(normalized["children"])
        count_text = tr("无限") if normalized["count"] == 0 else f"{normalized['count']} {tr('次')}"
        return f"{label} · {count_text}", f"{tr('子步骤')} {child_count} {tr('个')}"

    if step_type in {"if", "while"}:
        condition_type = normalized["condition_type"]
        condition_label = tr(CONDITION_TYPE_LABELS.get(condition_type, condition_type))
        if condition_type in {"image_exists", "image_not_exists"}:
            condition_value = os.path.basename(normalized["template_path"]) or tr("未选择模板")
        elif condition_type == "last_result":
            condition_value = tr("上一步返回 True")
        elif condition_type == "last_result_failed":
            condition_value = tr("上一步返回 False")
        else:
            condition_value = normalized["text"] or tr("未填写文字")
        child_count = len(normalized["children"])
        if step_type == "while":
            extra = tr("无限次") if normalized["max_iterations"] == 0 else f"{tr('最多')} {normalized['max_iterations']} {tr('次')}"
        else:
            extra = f"{tr('子步骤')} {child_count} {tr('个')}"
        return f"{label} · {condition_label} · {condition_value}", extra if step_type == "while" else f"{tr('子步骤')} {child_count} {tr('个')}"

    return label, ""


class WorkflowRunner:
    LOOP_CONTROL_BREAK = "break"
    LOOP_CONTROL_CONTINUE = "continue"

    def __init__(self, log_callback=None, sleep_func=None, mirror_to_project_log: bool = True):
        self.log_callback = log_callback or (lambda message: None)
        self.sleep_func = sleep_func or time.sleep
        self.mirror_to_project_log = mirror_to_project_log
        self.stop_requested = False
        self.last_result = False
        self.current_workflow = None

    def stop(self):
        self.stop_requested = True

    def run(self, workflow: dict) -> bool:
        normalized = normalize_workflow(workflow)
        self.stop_requested = False
        self.last_result = False
        self.current_workflow = normalized
        self._log(tr("开始执行流程：") + normalized['name'])
        success, _ = self._execute_steps(normalized["steps"], 0)
        if self.stop_requested:
            self._log(tr("流程已停止"))
            return False
        self._log(tr("流程执行完成"))
        return success

    def _log(self, message: str):
        self.log_callback(message)
        if self.mirror_to_project_log:
            log.info(f"[Workflow] {message}")

    def _execute_steps(self, steps: list[dict], depth: int, in_loop: bool = False) -> tuple[bool, str | None]:
        for index, step in enumerate(steps, start=1):
            if self.stop_requested:
                return False, None
            title, _ = summarize_step(step)
            self._log(f"{'  ' * depth}[{index}/{len(steps)}] {title}")
            try:
                self.last_result, loop_control = self._execute_step(step, depth, in_loop)
            except Exception as exc:
                self.last_result = False
                loop_control = None
                self._log(tr("步骤执行异常：") + str(exc))
                log.error(traceback.format_exc())
            if loop_control is not None:
                return self.last_result, loop_control
            if self.stop_requested:
                return False, None
        return True, None

    def _execute_step(self, step: dict, depth: int, in_loop: bool = False) -> tuple[bool, str | None]:
        normalized = normalize_step(step)
        step_type = normalized["type"]

        if step_type == "click_image":
            return self._click_image(normalized), None
        if step_type == "click_text":
            return self._click_text(normalized), None
        if step_type == "click_crop":
            return self._click_crop(normalized), None
        if step_type == "find_image":
            return self._find_image(normalized), None
        if step_type == "find_text":
            return self._find_text(normalized), None
        if step_type == "play_audio":
            return self._play_audio(normalized), None
        if step_type == "send_message":
            return self._send_message(normalized), None
        if step_type == "switch_screen":
            return self._switch_screen(normalized), None
        if step_type == "press_key":
            return self._press_key(normalized), None
        if step_type == "wait":
            self.sleep_func(normalized["seconds"])
            return True, None
        if step_type in {self.LOOP_CONTROL_BREAK, self.LOOP_CONTROL_CONTINUE}:
            return self._handle_loop_control_step(step_type, depth, in_loop)
        if step_type == "if":
            condition_result = self._evaluate_condition(normalized)
            if condition_result:
                return self._execute_steps(normalized["children"], depth + 1, in_loop=in_loop)
            return False, None
        if step_type == "for":
            result = True
            if normalized["count"] == 0:
                iteration = 0
                while not self.stop_requested:
                    iteration += 1
                    self._log(f"{'  ' * depth}{tr('第')} {iteration} {tr('次循环')}")
                    result, loop_control = self._execute_steps(normalized["children"], depth + 1, in_loop=True)
                    if loop_control == self.LOOP_CONTROL_BREAK:
                        break
                    if loop_control == self.LOOP_CONTROL_CONTINUE:
                        continue
            else:
                for iteration in range(normalized["count"]):
                    if self.stop_requested:
                        return False, None
                    self._log(f"{'  ' * depth}{tr('第')} {iteration + 1}/{normalized['count']} {tr('次循环')}")
                    result, loop_control = self._execute_steps(normalized["children"], depth + 1, in_loop=True)
                    if loop_control == self.LOOP_CONTROL_BREAK:
                        break
                    if loop_control == self.LOOP_CONTROL_CONTINUE:
                        continue
            return result, None
        if step_type == "while":
            iteration = 0
            result = False
            max_iter = normalized["max_iterations"]
            while (max_iter == 0 or iteration < max_iter) and not self.stop_requested:
                if not self._evaluate_condition(normalized):
                    break
                iteration += 1
                iter_label = f"∞ ({iteration})" if max_iter == 0 else f"{iteration}/{max_iter}"
                self._log(f"{'  ' * depth}While {tr('第')} {iter_label} {tr('次执行')}")
                result, loop_control = self._execute_steps(normalized["children"], depth + 1, in_loop=True)
                if loop_control == self.LOOP_CONTROL_BREAK:
                    break
                if loop_control == self.LOOP_CONTROL_CONTINUE:
                    continue
            if max_iter > 0 and iteration >= max_iter:
                self._log(f"{tr('达到 While 最大循环次数')} {max_iter}，{tr('已自动停止循环')}")
            return result, None
        return False, None

    def _handle_loop_control_step(self, step_type: str, depth: int, in_loop: bool) -> tuple[bool, str | None]:
        if not in_loop:
            self._log(f"{'  ' * depth}{tr('循环控制步骤只能在循环内使用')}")
            return True, None

        if step_type == self.LOOP_CONTROL_BREAK:
            return True, self.LOOP_CONTROL_BREAK

        return True, self.LOOP_CONTROL_CONTINUE

    def _evaluate_condition(self, step: dict) -> bool:
        condition_type = step["condition_type"]
        if condition_type in {"image_exists", "image_not_exists"}:
            result = self._find_image(step)
            return result if condition_type == "image_exists" else not result
        if condition_type in {"text_exists", "text_not_exists"}:
            result = self._find_text(step)
            return result if condition_type == "text_exists" else not result
        if condition_type in {"last_result", "last_result_failed"}:
            result = bool(self.last_result)
            return result if condition_type == "last_result" else not result
        return False

    def _crop(self, step: dict) -> tuple[float, float, float, float]:
        return parse_crop_expression(step.get("crop", ""))

    def _click_image(self, step: dict) -> bool:
        if not step["template_path"]:
            self._log(tr("点击图片失败：未选择模板"))
            return False
        template_path = resolve_workflow_path(step["template_path"], self.current_workflow)

        # 映射点击动作
        action_map = {
            "press": "down",
            "release": "up",
            "press_and_release": "click",
        }
        action = action_map.get(step["click_action"], "click")

        return bool(auto.click_element(
            template_path,
            "image",
            step["threshold"],
            max_retries=step["max_retries"],
            crop=self._crop(step),
            action=action,
            press_duration=step.get("press_duration", 0.0),
        ))

    def _click_text(self, step: dict) -> bool:
        if not step["text"]:
            self._log(tr("点击文字失败：未填写目标文字"))
            return False
        targets = _parse_text_targets(step["text"])
        target = targets[0] if len(targets) == 1 else tuple(targets)

        # 映射点击动作
        action_map = {
            "press": "down",
            "release": "up",
            "press_and_release": "click",
        }
        action = action_map.get(step["click_action"], "click")

        return bool(auto.click_element(
            target,
            "text",
            max_retries=step["max_retries"],
            crop=self._crop(step),
            include=step["include"],
            action=action,
            press_duration=step.get("press_duration", 0.0),
        ))

    def _click_crop(self, step: dict) -> bool:
        if not str(step.get("crop", "")).strip():
            self._log(tr("点击坐标失败：未填写检测区域"))
            return False

        action_map = {
            "press": "down",
            "release": "up",
            "press_and_release": "click",
        }
        action = action_map.get(step["click_action"], "click")

        return bool(auto.click_element(
            self._crop(step),
            "crop",
            crop=(0, 0, 1, 1),
            action=action,
            press_duration=step.get("press_duration", 0.0),
        ))

    def _find_image(self, step: dict) -> bool:
        if not step["template_path"]:
            self._log(tr("查找图片失败：未选择模板"))
            return False
        template_path = resolve_workflow_path(step["template_path"], self.current_workflow)
        return bool(auto.find_element(
            template_path,
            "image",
            step["threshold"],
            max_retries=step["max_retries"],
            crop=self._crop(step),
        ))

    def _find_text(self, step: dict) -> bool:
        if not step["text"]:
            self._log(tr("OCR 判断失败：未填写文字"))
            return False
        targets = _parse_text_targets(step["text"])
        target = targets[0] if len(targets) == 1 else tuple(targets)
        return bool(auto.find_element(
            target,
            "text",
            max_retries=step["max_retries"],
            crop=self._crop(step),
            include=step["include"],
        ))

    def _play_audio(self, step: dict) -> bool:
        audio_path = step.get("audio_path", "").strip()
        if not audio_path:
            self._log(tr("播放音频失败：未填写音频路径"))
            return False
        try:
            from playsound3 import playsound

            resolved_path = resolve_workflow_path(audio_path, self.current_workflow)
            self._log(f"{tr('开始播放音频')} {resolved_path}")
            playsound(resolved_path)
            self._log(tr("播放音频完成"))
            return True
        except Exception as e:
            self._log(f"{tr('播放音频时发生错误')}：{e}")
            return False

    def _send_message(self, step: dict) -> bool:
        """发送消息通知。"""
        try:
            message_text = step.get("text", "").strip()
            with_screenshot = step.get("with_screenshot", False)
            image = None

            if not message_text:
                self._log(tr("消息推送失败：未填写消息内容"))
                return False

            if with_screenshot:
                try:
                    # 获取当前截图
                    result = auto.take_screenshot()
                    if result:
                        screenshot, _, _ = result
                        image = screenshot
                    self._log(tr("消息通知：包含截图"))
                except Exception as e:
                    self._log(f"{tr('获取截图失败')}：{e}")

            # 发送通知
            notif.notify(
                content=message_text,
                image=image,
            )
            self._log(tr("消息推送完成"))
            return True
        except Exception as e:
            self._log(f"{tr('消息推送失败')}：{e}")
            return False

    def _switch_screen(self, step: dict) -> bool:
        target_screen = step.get("target_screen", "").strip()
        if not target_screen:
            self._log(tr("切换界面失败：未选择目标界面"))
            return False

        if not can_change_to_screen_from_main(target_screen):
            self._log(tr("切换界面失败：目标界面不可切换"))
            return False

        from module.screen import screen as screen_manager

        screen_manager.change_to(target_screen)
        return True

    def _press_key(self, step: dict) -> bool:
        """按下指定按键。"""
        key = step.get("key", "").strip()
        if not key:
            self._log(tr("按键操作失败：未填写按键"))
            return False

        action = step.get("key_action", "press_and_release")
        duration = step.get("key_duration", 0.1)

        try:
            if action == "press":
                self._log(f"{tr('按下按键')}：{key}")
                auto.press_key_down(key)
                if duration > 0:
                    self.sleep_func(duration)
                    auto.press_key_up(key)
                    self._log(f"{tr('释放按键')}：{key}")
            elif action == "release":
                self._log(f"{tr('释放按键')}：{key}")
                auto.press_key_up(key)
            elif action == "press_and_release":
                self._log(f"{tr('按下并释放按键')}：{key}，{tr('时长')} {duration:.2f}s")
                auto.press_key(key, duration)
            else:
                self._log(f"{tr('未知按键动作')}：{action}")
                return False
            return True
        except Exception as e:
            self._log(f"{tr('按键操作失败')}：{e}")
            return False
