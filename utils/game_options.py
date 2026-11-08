"""游戏优化总开关：保留子开关原值，只在执行时求有效值。"""


def game_option_enabled(config, name):
    # 旧配置没有总开关时沿用原行为；新画质选项始终默认关闭。
    return bool(getattr(config, "game_optimization_enable", True)
                and getattr(config, name, name != "auto_lower_graphics_enable"))
