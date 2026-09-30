import os
import shutil

import json
from module.config import cfg


def auto_config():
    if not os.path.exists(os.path.join(cfg.fight_path, "config.json")):
        config = {
            "version": "2.1.18",
            "real_width": 0,
            "real_height": 0,
            "map_debug": False,
            "github_proxy": "",
            "rawgithub_proxy": "",
            "webhook_url": "",
            "start": False,
            "picture_version": "0",
            "star_version": "0",
            "open_map": "m",
            "script_debug": False,
            "auto_shutdown": 0,
            "taskkill_name": "",
            "auto_final_fight_e": False,
            "auto_final_fight_e_cnt": 20,
            "allow_fight_e_buy_prop": False,
            "auto_run_in_map": True,
            "detect_fight_status_time": 5,
            "map_version": "default",
            "main_map": "1",
            "allow_run_again": False,
            "allow_run_next_day": False,
            "allow_map_buy": False,
            "allow_snack_buy": False,
            "allow_memory_token": False
        }
    else:
        with open(os.path.join(cfg.fight_path, "config.json"), 'r', encoding='utf-8') as f:
            config = json.load(f)
            
    # 三项「特殊物品领取」由总开关统一控制（键名即 FightGroup 里「启用「特殊物品领取」」那个卡片）：
    # 总开关关闭时完全不碰锄大地那边的这三项，让用户自己在锄大地里设置的值说了算。
    updates = {}
    if cfg.fight_reward_enable:
        for key, value in (
            ("allow_map_buy", cfg.fight_allow_map_buy),
            ("allow_snack_buy", cfg.fight_allow_snack_buy),
            ("allow_memory_token", cfg.fight_allow_memory_token),
        ):
            if value != "不配置" and config.get(key) != value:
                updates[key] = value
    # 优先星球与地图版本与总开关无关，各自独立同步
    if cfg.fight_main_map != "0" and config.get("main_map") != cfg.fight_main_map:
        updates["main_map"] = cfg.fight_main_map
    if cfg.fight_map_version != "不配置" and config.get("map_version") != cfg.fight_map_version:
        updates["map_version"] = cfg.fight_map_version
    if updates:
        config.update(updates)
        with open(os.path.join(cfg.fight_path, "config.json"), 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
