import os
import shutil

import yaml
from module.config import cfg


def auto_config():
    if not os.path.exists(os.path.join(cfg.universe_path, "info.yml")):
        shutil.copyfile(os.path.join(cfg.universe_path, "info_example.yml"), os.path.join(
            cfg.universe_path, "info.yml"))
    with open(os.path.join(cfg.universe_path, "info.yml"), 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)
    if info['config']['fate'] != cfg.universe_fate:
        info['config']['fate'] = cfg.universe_fate
        with open(os.path.join(cfg.universe_path, "info.yml"), 'w', encoding='utf-8') as f:
            yaml.dump(info, f, default_flow_style=False,
                      allow_unicode=True)


def reload_config_from_asu():
    file = os.path.join(cfg.universe_path, "info.yml")
    if not os.path.exists(file):
        return None
    with open(file, 'r', encoding='utf-8') as f:
        info = yaml.safe_load(f)
        if info['config']['fate'] != cfg.universe_fate:
            pass
            # todo: save cfg memory/file and reload gui
