import os
import shutil

import yaml
from module.config import cfg


def auto_config():
    if not os.path.exists(os.path.join(cfg.universe_path, "info_old.yml")):
        shutil.copyfile(os.path.join(cfg.universe_path, "info_example_old.yml"), os.path.join(
            cfg.universe_path, "info_old.yml"))
    with open(os.path.join(cfg.universe_path, "info_old.yml"), 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)
    if ('不配置' != cfg.universe_fate and info['config']['fate'] != cfg.universe_fate) or (cfg.universe_difficulty != 0 and info['config']['difficulty'] != cfg.universe_difficulty):
        if cfg.universe_fate != "不配置":
            info['config']['fate'] = cfg.universe_fate
        if cfg.universe_difficulty != 0:
            info['config']['difficulty'] = cfg.universe_difficulty
        with open(os.path.join(cfg.universe_path, "info_old.yml"), 'w', encoding='utf-8') as f:
            yaml.dump(info, f, default_flow_style=False,
                      allow_unicode=True)


def reload_config_from_asu():
    file = os.path.join(cfg.universe_path, "info_old.yml")
    if not os.path.exists(file):
        return None
    with open(file, 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)
        if info['config']['fate'] != cfg.universe_fate:
            pass
            # todo: save cfg memory/file and reload gui
