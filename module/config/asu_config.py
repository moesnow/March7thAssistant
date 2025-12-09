import os
import shutil

import yaml
from module.config import cfg


def auto_config_divergent():
    if not os.path.exists(os.path.join(cfg.universe_path, "info.yml")):
        shutil.copyfile(os.path.join(cfg.universe_path, "info_example.yml"), os.path.join(cfg.universe_path, "info.yml"))
    with open(os.path.join(cfg.universe_path, "info.yml"), 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)

    info['config']['weekly_mode'] = True if cfg.divergent_type == "cycle" else False
    info['config']['team'] = cfg.divergent_team_type
    with open(os.path.join(cfg.universe_path, "info.yml"), 'w', encoding='utf-8') as f:
        yaml.dump(info, f, default_flow_style=False, allow_unicode=True)


def auto_config_divergent_weekly():
    if not os.path.exists(os.path.join(cfg.universe_path, "info.yml")):
        shutil.copyfile(os.path.join(cfg.universe_path, "info_example.yml"), os.path.join(cfg.universe_path, "info.yml"))
    with open(os.path.join(cfg.universe_path, "info.yml"), 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)

    info['config']['weekly_mode'] = True if cfg.weekly_divergent_type == "cycle" else False
    info['config']['team'] = cfg.divergent_team_type
    with open(os.path.join(cfg.universe_path, "info.yml"), 'w', encoding='utf-8') as f:
        yaml.dump(info, f, default_flow_style=False, allow_unicode=True)


def auto_config():
    if not os.path.exists(os.path.join(cfg.universe_path, "info_old.yml")):
        shutil.copyfile(os.path.join(cfg.universe_path, "info_example_old.yml"), os.path.join(cfg.universe_path, "info_old.yml"))
    with open(os.path.join(cfg.universe_path, "info_old.yml"), 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)
    if ('不配置' != cfg.universe_fate and info['config']['fate'] != cfg.universe_fate) or (cfg.universe_difficulty != 0 and info['config']['difficulty'] != cfg.universe_difficulty):
        if cfg.universe_fate != "不配置":
            info['config']['fate'] = cfg.universe_fate
        if cfg.universe_difficulty != 0:
            info['config']['difficulty'] = cfg.universe_difficulty
        with open(os.path.join(cfg.universe_path, "info_old.yml"), 'w', encoding='utf-8') as f:
            yaml.dump(info, f, default_flow_style=False, allow_unicode=True)
