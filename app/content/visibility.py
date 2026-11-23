from module.config import cfg
from module.content_visibility import Visibility
from module.settings_registry import SETTINGS


def page_visible(page_id, config=cfg):
    return Visibility.read(config).page(page_id)


def setting_visible(item, config=cfg, *, platform=None):
    return Visibility.read(config, platform).setting(item)


def section_visible(page_id, section_id, config=cfg):
    visibility = Visibility.read(config)
    return any(visibility.setting(item) for item in SETTINGS if item.page == page_id and item.section == section_id)
