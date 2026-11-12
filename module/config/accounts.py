"""多账号列表及独立任务配置，复用 Config 的 YAML 读写。"""
import copy
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


PROFILE_ROOT = Path("settings/profiles")
TASK_PREFIXES = (
    "power_", "instance_", "build_target_", "weekly_", "echo_of_war_",
    "borrow_", "reward_", "daily_", "activity_", "asset_", "currencywars_",
    "divergent_", "universe_", "fight_", "forgottenhall_", "purefiction_",
    "apocalyptic_", "immortal_",
)
TASK_KEYS = {
    "tp_before_instance", "break_down_level_four_relicset", "merge_immersifier",
    "merge_immersifier_limit", "use_reserved_trailblaze_power", "use_fuel",
    "last_run_timestamp",
    "redemption_code", "already_used_codes",
}


def is_task_key(key):
    return key.startswith(TASK_PREFIXES) or key in TASK_KEYS


def profile_path(account):
    return PROFILE_ROOT / f"{account['id']}.yaml"


def add_account(cfg):
    account = {"id": uuid4().hex, "enabled": True, "name": "", "login_name": "", "uid": ""}
    PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
    original_path, original_config = cfg.config_path, cfg.config
    try:
        cfg.config_path = str(profile_path(account))
        cfg.config = copy.deepcopy(original_config)
        # 新账号沿用任务设置，完成时间和差分宇宙完成次数从零开始。
        for key in cfg.config:
            if is_task_key(key) and (key.endswith("_timestamp") or key.endswith("_completed_count")):
                cfg.config[key] = 0
        cfg.config["daily_tasks"] = []
        cfg.config["already_used_codes"] = []
        cfg.save_config()
    finally:
        cfg.config_path, cfg.config = original_path, original_config
    return account


@contextmanager
def account_config(cfg, account):
    """在原 cfg 对象上切换文件，使现有设置控件和任务继续使用同一套接口。"""
    original_path, original_config = cfg.config_path, cfg.config
    try:
        cfg.config = copy.deepcopy(original_config)
        cfg.config_path = str(profile_path(account))
        cfg._load_config(save=False)
        # 游戏路径、界面、通知和完成后操作继续沿用默认配置。
        for key, value in original_config.items():
            if not is_task_key(key):
                cfg.config[key] = copy.deepcopy(value)
        cfg.save_config()
        yield
    finally:
        cfg.config_path, cfg.config = original_path, original_config


def bind_uid(cfg, account_id, uid):
    accounts = cfg.get_value("multi_accounts", [])
    for account in accounts:
        if account["id"] == account_id:
            account["uid"] = str(uid)
            break
    cfg.set_value("multi_accounts", accounts)
