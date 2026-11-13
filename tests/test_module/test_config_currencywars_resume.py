"""续跑为显式 opt-in；旧配置和开关持久化不能改变已选模式或策略。"""
from module.config.config import Config


def load_config(path):
    instance = Config.__new__(Config)
    Config.__init__(instance, "assets/config/version.txt", "assets/config/config.example.yaml", str(path))
    return instance


def test_old_configuration_keeps_new_run_behavior(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("currencywars_type: normal\ncurrencywars_strategy: seele\n", encoding="utf-8")
    config = load_config(path)

    assert config.currencywars_resume_enable is False
    assert config.currencywars_type == "normal"
    assert config.currencywars_strategy == "seele"


def test_resume_preference_roundtrips_without_changing_strategy_or_mode(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("currencywars_type: overclock\ncurrencywars_strategy: aglaea\n", encoding="utf-8")
    config = load_config(path)

    for enabled in (True, False):
        config.set_value("currencywars_resume_enable", enabled)
        loaded = load_config(path)
        assert loaded.currencywars_resume_enable is enabled
        assert loaded.currencywars_type == "overclock"
        assert loaded.currencywars_strategy == "aglaea"
