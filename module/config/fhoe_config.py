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
            "allow_snack_buy": False
        }
    else:
        with open(os.path.join(cfg.fight_path, "config.json"), 'r', encoding='utf-8') as f:
            config = json.load(f)
    if config['allow_map_buy'] != cfg.fight_allow_map_buy or config['allow_snack_buy'] != cfg.fight_allow_snack_buy or config['main_map'] != cfg.fight_main_map:
        config['allow_map_buy'] = cfg.fight_allow_map_buy
        config['allow_snack_buy'] = cfg.fight_allow_snack_buy
        config['main_map'] = cfg.fight_main_map
        with open(os.path.join(cfg.fight_path, "config.json"), 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
