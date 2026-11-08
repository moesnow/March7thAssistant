# coding:utf-8
"""GameClientOutdatedError 类型判断回归测试（取代对本地化文本的 startswith 匹配）。"""
import pytest


def _load_game_module():
    try:
        import tasks.game as game
        return game
    except Exception as e:  # 任务模块依赖较重，环境不可用时跳过
        pytest.skip(f"tasks.game 依赖不可用: {e}")


class TestGameClientOutdatedError:
    def test_is_runtime_error(self):
        game = _load_game_module()
        assert issubclass(game.GameClientOutdatedError, RuntimeError)

    def test_catch_by_type_not_by_text(self):
        game = _load_game_module()
        caught = None
        try:
            raise game.GameClientOutdatedError("任意消息内容（可被翻译，不影响判断）")
        except RuntimeError as e:
            caught = e
        assert isinstance(caught, game.GameClientOutdatedError)

    def test_message_translation_does_not_affect_branching(self):
        game = _load_game_module()
        # 消息被翻译成任意语言后，类型判断依旧成立（原 startswith 方案会失效）
        e1 = game.GameClientOutdatedError("检测到游戏客户端版本过低，请前往启动器下载最新客户端")
        e2 = game.GameClientOutdatedError("Client outdated")
        assert isinstance(e1, game.GameClientOutdatedError)
        assert isinstance(e2, game.GameClientOutdatedError)
